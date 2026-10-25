# Local MLOps Demo

This guide runs the HTTP threat detector locally with Docker Compose. Docker Desktop must be running, and the trained files must exist in `models/` (`model.onnx`, `scaler.pkl`, `feature_extractor.pkl`, and `config.json`). Compose starts the API, Redis, one inference worker, Prometheus, and Grafana; training and MLflow are run separately on the host.

## Start the API

From the repository root:

```powershell
docker compose up --build -d
```

Check that the model loaded:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok","backend":"onnx"}
```

Interactive API documentation is at <http://127.0.0.1:8000/docs>.
For click-by-click UI instructions and sample predictions, see [UI_GUIDE.md](UI_GUIDE.md).

## Try a benign request

```powershell
$body = @{ method = 'GET'; url = 'http://localhost/tienda1/index.jsp' } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/predict -Method Post -ContentType 'application/json' -Body $body
```

## Try a SQL injection request

```powershell
$body = @{ method = 'GET'; url = "http://localhost/tienda1/publico/anadir.jsp?id=2&nombre='; DROP TABLE usuarios; SELECT * FROM datos" } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/predict -Method Post -ContentType 'application/json' -Body $body
```

Each prediction returns `label` (`0` normal, `1` attack), `probability`, `is_attack`, `backend`, and `feature_drift_score`.

## Submit an asynchronous job

`POST /jobs` returns a job ID immediately. The separate worker processes it, and `GET /jobs/{job_id}` returns `queued`, `processing`, `completed` with a prediction result, or `failed`.

```powershell
$body = @{ method = 'GET'; url = 'http://localhost/tienda1/index.jsp' } | ConvertTo-Json
$job = Invoke-RestMethod http://127.0.0.1:8000/jobs -Method Post -ContentType 'application/json' -Body $body
$job
Invoke-RestMethod "http://127.0.0.1:8000/jobs/$($job.job_id)"
```

Jobs and results are held in local Redis for up to one hour. The Compose setup runs one worker and is intended for a local demonstration.

## Inspect Prometheus metrics

After making predictions, open <http://127.0.0.1:8000/metrics> or run:

```powershell
(Invoke-WebRequest http://127.0.0.1:8000/metrics).Content
```

The endpoint includes API request totals, response status codes, request duration histograms, prediction counts by result, jobs submitted, and current queued/processing job counts.

Prometheus scrapes the API every five seconds. Grafana is provisioned with a dashboard for request rate and p95 latency, predictions, HTTP responses, async job submissions, and queue depth. Open <http://127.0.0.1:3000> and sign in with `admin` / `admin`; this local demo account should not be exposed beyond your machine. Prometheus's own query UI is at <http://127.0.0.1:9090>.

## View MLflow training runs

MLflow tracking is local and separate from the serving container. Install project dependencies, run training to create a new tracked run, then start the MLflow UI in another terminal:

```powershell
python -m pip install -r requirements.txt
python -m src.train --csv dataset/csic_database.csv
make mlflow-ui
```

Open <http://127.0.0.1:5000>. Training records its parameters, evaluation metrics, model bundle, and evaluation report in the local `mlflow.db` store. The API can serve the existing model without starting MLflow or rerunning training.

## Stop the API

```powershell
docker compose down
```
