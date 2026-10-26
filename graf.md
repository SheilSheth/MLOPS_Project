# Grafana Panels and Prometheus Metrics

- **API request rate** — `http_api_requests_total`
- **API request latency (p95)** — `http_api_request_duration_seconds_bucket`
- **Cumulative predictions by result** — `http_threat_predictions_total`, `http_threat_async_predictions_total`
- **Queue depth** — `http_threat_queue_depth`, `http_threat_processing_depth`
- **API responses by status** — `http_api_requests_total`
- **Async jobs submitted** — `http_threat_jobs_submitted_total`
- **Input feature drift score** — `http_threat_feature_drift_score_sum`, `http_threat_feature_drift_score_count`, `http_threat_feature_drift_threshold`
