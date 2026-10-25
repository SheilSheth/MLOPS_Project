# Two-Hour Local MLOps MVP Roadmap

## Goal

Build a small, runnable local MLOps system from the trained HTTP anomaly detector. A user can start the services, submit a request for analysis synchronously or through a Redis-backed worker, and receive a prediction. The API exposes basic Prometheus metrics. The system runs without cloud services or a cluster.

This is a time-boxed MVP, not the full production architecture in `project_md.md`. The API runs locally with Docker Compose, and MLflow tracking uses a local SQLite store. Kubernetes and all remote deployment are out of scope. CI/CD publishing, Airflow, automatic retraining, and production security guarantees are also out of scope.

## What is already in the repository

- CSIC 2010 parsing, deduplication, feature extraction, and model training code.
- Trained LightGBM, preprocessing artifacts, and an ONNX export.
- A prediction interface, evaluation reports, and a pytest suite.
- A saved clean holdout FPR of 1.24% (3/241). This is a small offline holdout result, not a guarantee for live traffic.

## Implementation order and time budget

| Order | Time | Work | Result | Status |
|---|---:|---|---|---|
| 1 | 15 min | Confirm model artifacts and inference contract | ONNX prediction path uses the matching feature extractor, scaler, and threshold | Complete |
| 2 | 20 min | Add local MLflow tracking to training | Log training parameters, evaluation metrics, and model artifacts to local `mlflow.db` | Implemented; a new training run is needed to populate it |
| 3 | 25 min | Add a small FastAPI app | Health and prediction endpoints accept method, URL, and optional body | Complete |
| 4 | 20 min | Add local Docker packaging | Dockerfile and Compose services run API, Redis, worker, Prometheus, and Grafana | Complete; all services are running locally |
| 5 | 15 min | Add Prometheus metrics and Grafana dashboard | Request count, prediction count, status, latency, and queue depth scraped and visualized | Complete; target is up and dashboard is provisioned |
| 6 | 10 min | Add a simple local smoke/demo path | Example requests and concise run instructions in `LOCAL_DEMO.md` | Complete |
| 7 | 15 min | Fix integration issues and verify the local flow | Build/start the stack and confirm health, benign/attack predictions, and metrics work | Complete |
|  | **120 min** | **Total** | **Local inference and experiment-tracking MVP** |

Time estimates include implementation and a small amount of integration debugging. If the existing Python environment, Docker, or model artifact compatibility causes setup issues, prioritize a working local API first and defer metrics or container polish.

## Local MVP acceptance criteria

- Start the app using documented local commands (preferably `docker compose up --build`).
- `GET /health` reports that the API and model are ready.
- `POST /predict` accepts a request and returns a binary label and probability.
- `POST /jobs` queues a request and `GET /jobs/{job_id}` returns its eventual result.
- A known benign example and a known attack example both complete successfully.
- `GET /metrics` exposes basic Prometheus-compatible request metrics.
- A training run can be viewed in the local MLflow UI, with its parameters, metrics, and model artifact recorded.
- The model artifacts and dataset remain local; no external service is required to run inference.

## Explicitly out of scope for this two-hour pass

- Kubernetes, HPA, Minikube/Kind, Locust, and any remote deployment.
- Cloud storage, DVC remote, container registry, and image publishing.
- Evidently/drift monitoring, scheduled retraining, Airflow, and automatic model replacement.
- GitHub Actions CI/CD and production-grade authentication, rate limiting, and security hardening.
- Fairness claims for geography or VPN subgroups, since the current dataset may not contain reliable labels for those groups.

## Follow-up, only if more time is available

1. Add drift alerts and a reviewed candidate retraining workflow.
2. Improve queue reliability, retries, and concurrency beyond the one-worker local demonstration.

## Follow-up progress

- **DVC pipeline: implemented and run locally.** `dvc.yaml` runs training, ONNX export, and evaluation; `params.yaml` holds the seed and dataset path; `dvc.lock` records the successful run. DVC tracks model binaries, intermediate predictions, and the dataset pointer while Git retains readable configs and reports. The CSV has been removed from Git tracking; its local copy remains available and is ignored by Git.
- **GitHub Actions CI: implemented.** `.github/workflows/ci.yml` runs lint, unit tests, and the committed holdout FPR gate on pushes and pull requests to `main`. It does not retrain or run model-artifact integration tests because the DVC cache has no remote.

## Practical constraint

Two hours is enough for a narrow local demonstration if the current artifacts load cleanly and Docker is ready. MLflow records training runs locally and is not required by the serving API. This time is not enough to implement and validate the complete asynchronous, drift-aware, retraining MLOps system described in `project_md.md`.
