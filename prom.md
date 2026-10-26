# Prometheus Metrics

- `http_api_requests_total` — Total HTTP API requests by method and status code, excluding `/metrics` scrapes.
- `http_api_request_duration_seconds` — HTTP API request duration by method.
- `http_threat_predictions_total` — Completed synchronous `/predict` predictions by result (`attack` or `normal`).
- `http_threat_async_predictions_total` — Completed asynchronous `/jobs` predictions by result (`attack` or `normal`).
- `http_threat_jobs_submitted_total` — Total prediction jobs accepted into the queue.
- `http_threat_queue_depth` — Number of jobs currently waiting in the queue.
- `http_threat_processing_depth` — Number of jobs currently being processed by the worker.
- `http_threat_feature_drift_score` — Histogram of feature drift scores for accepted prediction inputs.
- `http_threat_feature_drift_threshold` — Training baseline threshold used to assess feature drift scores.
