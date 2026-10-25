"""Local HTTP API for the HTTP request anomaly detector."""

from contextlib import asynccontextmanager
import json
import os
import time
from typing import Any
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from prometheus_client import Gauge
from redis import Redis
from starlette.responses import Response

from src.parse import _parse_row
from src.predict import Predictor


HTTP_REQUESTS = Counter(
    'http_api_requests_total',
    'Number of HTTP API requests, excluding the metrics scrape endpoint.',
    ['method', 'status_code'],
)
HTTP_REQUEST_DURATION = Histogram(
    'http_api_request_duration_seconds',
    'HTTP API request duration in seconds.',
    ['method'],
)
HTTP_PREDICTIONS = Counter(
    'http_threat_predictions_total',
    'Number of completed model predictions by predicted class.',
    ['result'],
)
QUEUED_JOBS = Counter('http_threat_jobs_submitted_total', 'Prediction jobs submitted to Redis.')
QUEUE_DEPTH = Gauge('http_threat_queue_depth', 'Prediction jobs waiting in the Redis queue.')
PROCESSING_DEPTH = Gauge(
    'http_threat_processing_depth', 'Prediction jobs currently held by the worker.'
)
FEATURE_DRIFT_SCORE = Histogram(
    'http_threat_feature_drift_score',
    'Mean absolute standardized feature value for accepted prediction inputs.',
)
FEATURE_DRIFT_THRESHOLD = Gauge(
    'http_threat_feature_drift_threshold',
    'Training-baseline threshold for the feature drift score.',
)


class PredictionRequest(BaseModel):
    method: str = Field(default='GET', min_length=1, max_length=16)
    url: str = Field(min_length=1, max_length=8192)
    body: str = Field(default='', max_length=1_000_000)
    headers: dict[str, str] = Field(default_factory=dict)


class PredictionResponse(BaseModel):
    label: int
    probability: float
    is_attack: bool
    backend: str
    feature_drift_score: float


def _to_record(payload: PredictionRequest) -> dict[str, Any]:
    """Convert an API payload into the record format used by training."""
    url = payload.url.strip()
    if not url.endswith((' HTTP/1.0', ' HTTP/1.1', ' HTTP/2')):
        url = f'{url} HTTP/1.1'

    headers = {name.lower(): value for name, value in payload.headers.items()}
    row = pd.Series({
        'Method': payload.method.strip().upper(),
        'URL': url,
        'content': payload.body or None,
        'classification': 0,  # Required by the shared parser; ignored at inference.
        'User-Agent': headers.get('user-agent', ''),
        'Pragma': headers.get('pragma', ''),
        'Cache-Control': headers.get('cache-control', ''),
        'Accept': headers.get('accept', ''),
        'Accept-encoding': headers.get('accept-encoding', ''),
        'Accept-charset': headers.get('accept-charset', ''),
        'language': headers.get('accept-language', ''),
        'host': headers.get('host', ''),
        'cookie': headers.get('cookie', ''),
        'content-type': headers.get('content-type', ''),
        'connection': headers.get('connection', ''),
        'lenght': headers.get('content-length', ''),
    })
    return _parse_row(row)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load ONNX and preprocessing artifacts once when the service starts.
    app.state.predictor = Predictor(backend='onnx')
    if app.state.predictor.feature_drift_threshold is not None:
        FEATURE_DRIFT_THRESHOLD.set(app.state.predictor.feature_drift_threshold)
    app.state.redis = Redis.from_url(
        os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
        decode_responses=True,
    )
    app.state.redis.ping()
    yield
    app.state.redis.close()


app = FastAPI(
    title='HTTP Threat Detector',
    description='Local ML inference for classifying HTTP requests.',
    version='0.1.0',
    lifespan=lifespan,
)


@app.middleware('http')
async def observe_http_requests(request: Request, call_next):
    """Record request volume, response codes, and duration with bounded labels."""
    if request.url.path == '/metrics':
        return await call_next(request)

    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        HTTP_REQUESTS.labels(
            method=request.method,
            status_code=str(status_code),
        ).inc()
        HTTP_REQUEST_DURATION.labels(method=request.method).observe(
            time.perf_counter() - started
        )


@app.get('/metrics', include_in_schema=False)
def metrics(request: Request) -> Response:
    redis = request.app.state.redis
    QUEUE_DEPTH.set(redis.llen('http-threat:queue'))
    PROCESSING_DEPTH.set(redis.llen('http-threat:processing'))
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get('/health')
def health(request: Request) -> dict[str, str]:
    if not hasattr(request.app.state, 'predictor'):
        raise HTTPException(status_code=503, detail='Model is not ready')
    try:
        request.app.state.redis.ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail='Redis is not ready') from exc
    return {'status': 'ok', 'backend': 'onnx', 'queue': 'redis-ready'}


@app.post('/predict', response_model=PredictionResponse)
def predict(payload: PredictionRequest, request: Request) -> dict[str, Any]:
    predictor: Predictor | None = getattr(request.app.state, 'predictor', None)
    if predictor is None:
        raise HTTPException(status_code=503, detail='Model is not ready')
    try:
        record = _to_record(payload)
        result = predictor.predict_one(record)
        FEATURE_DRIFT_SCORE.observe(result['feature_drift_score'])
        HTTP_PREDICTIONS.labels(
            result='attack' if result['is_attack'] else 'normal'
        ).inc()
        return result
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f'Invalid HTTP request payload: {exc}') from exc


@app.post('/jobs', status_code=202)
def submit_job(payload: PredictionRequest, request: Request) -> dict[str, str]:
    """Queue a request for the separate inference worker."""
    predictor: Predictor | None = getattr(request.app.state, 'predictor', None)
    if predictor is None:
        raise HTTPException(status_code=503, detail='Model is not ready')
    try:
        drift_score = predictor.feature_drift_score(_to_record(payload))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f'Invalid HTTP request payload: {exc}') from exc
    job_id = str(uuid4())
    job = {
        'job_id': job_id,
        'status': 'queued',
        'request': payload.model_dump(),
    }
    redis = request.app.state.redis
    pipeline = redis.pipeline()
    pipeline.set(f'http-threat:job:{job_id}', json.dumps(job), ex=3600)
    pipeline.rpush('http-threat:queue', json.dumps(job))
    pipeline.execute()
    FEATURE_DRIFT_SCORE.observe(drift_score)
    QUEUED_JOBS.inc()
    return {'job_id': job_id, 'status': 'queued'}


@app.get('/jobs/{job_id}')
def get_job(job_id: str, request: Request) -> dict[str, Any]:
    """Fetch queued job status or its prediction result."""
    value = request.app.state.redis.get(f'http-threat:job:{job_id}')
    if value is None:
        raise HTTPException(status_code=404, detail='Job not found or expired')
    return json.loads(value)
