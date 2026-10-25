"""Single-process Redis queue worker for ONNX request inference."""

import json
import os
import signal
import time

from redis import Redis

from src.api import PredictionRequest, _to_record
from src.predict import Predictor


QUEUE_KEY = 'http-threat:queue'
PROCESSING_KEY = 'http-threat:processing'
JOB_PREFIX = 'http-threat:job:'
JOB_TTL_SECONDS = 3600
STOP = False


def stop_worker(_signum, _frame):
    global STOP
    STOP = True


def run_worker() -> None:
    redis = Redis.from_url(
        os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
        decode_responses=True,
    )
    redis.ping()
    predictor = Predictor(backend='onnx')

    # This compose MVP runs one worker. Requeue tasks left in the processing
    # list after an abrupt worker exit before starting to consume new work.
    while redis.lmove(PROCESSING_KEY, QUEUE_KEY, 'RIGHT', 'LEFT') is not None:
        pass

    signal.signal(signal.SIGINT, stop_worker)
    signal.signal(signal.SIGTERM, stop_worker)
    print('Redis inference worker started; waiting for jobs.', flush=True)

    while not STOP:
        item = redis.brpoplpush(QUEUE_KEY, PROCESSING_KEY, timeout=1)
        if item is None:
            continue

        job = json.loads(item)
        job_id = job['job_id']
        job_key = f'{JOB_PREFIX}{job_id}'
        try:
            job['status'] = 'processing'
            redis.set(job_key, json.dumps(job), ex=JOB_TTL_SECONDS)

            request = PredictionRequest.model_validate(job['request'])
            result = predictor.predict_one(_to_record(request))
            job.update(status='completed', result=result)
        except Exception as exc:
            # Keep the returned error generic; detailed payloads are not logged.
            print(f'Job {job_id} failed: {type(exc).__name__}', flush=True)
            job.update(status='failed', error=type(exc).__name__)
        finally:
            redis.set(job_key, json.dumps(job), ex=JOB_TTL_SECONDS)
            redis.lrem(PROCESSING_KEY, 1, item)

    redis.close()
    print('Redis inference worker stopped.', flush=True)


if __name__ == '__main__':
    while True:
        try:
            run_worker()
            break
        except Exception as exc:
            print(f'Worker unavailable: {type(exc).__name__}; retrying shortly.', flush=True)
            time.sleep(3)
