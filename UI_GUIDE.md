# Local UI Guide: Try Predictions and View Drift Alerts

This guide uses the API's Swagger UI so you can enter requests in a browser and see predictions immediately. Docker Desktop must be running.

## 1. Start the local services

Open PowerShell in the repository folder and run:

```powershell
docker compose up --build -d
```

Wait for the containers to start, then open:

- API form: <http://127.0.0.1:8000/docs>
- Grafana: <http://127.0.0.1:3000> (local login: `admin` / `admin`)

## 2. Submit a sample in Swagger UI

1. On `/docs`, expand **POST /predict**.
2. Click **Try it out**.
3. Replace the request body with one sample below.
4. Click **Execute**.
5. Read the response body under **Responses**.

Each example below was submitted to the current local model. Probabilities are rounded to four decimal places; a new training run can change them.

### Example 1: Normal page request

Input:

```json
{
  "method": "GET",
  "url": "http://localhost/tienda1/index.jsp",
  "body": "",
  "headers": {}
}
```

Expected output:

```json
{"label":0,"probability":0.0283,"is_attack":false,"backend":"onnx","feature_drift_score":0.4607}
```

### Example 2: SQL injection in the URL query

Input:

```json
{
  "method": "GET",
  "url": "http://localhost/tienda1/publico/anadir.jsp?id=2&nombre='; DROP TABLE usuarios; SELECT * FROM datos",
  "body": "",
  "headers": {}
}
```

Expected output:

```json
{"label":1,"probability":1.0,"is_attack":true,"backend":"onnx","feature_drift_score":1.1008}
```

### Example 3: Script tag in the URL query (XSS-like input)

Input:

```json
{
  "method": "GET",
  "url": "http://localhost/search?q=%3Cscript%3Ealert(1)%3C/script%3E",
  "body": "",
  "headers": {}
}
```

Expected output:

```json
{"label":1,"probability":1.0,"is_attack":true,"backend":"onnx","feature_drift_score":2.9721}
```

### Example 4: Path traversal in the URL query

Input:

```json
{
  "method": "GET",
  "url": "http://localhost/download?file=../../../../etc/passwd",
  "body": "",
  "headers": {}
}
```

Expected output:

```json
{"label":1,"probability":1.0,"is_attack":true,"backend":"onnx","feature_drift_score":2.6658}
```

### Example 5: SQL injection in a POST body

Input:

```json
{
  "method": "POST",
  "url": "http://localhost/login",
  "body": "username=admin' OR '1'='1&password=x",
  "headers": {
    "Content-Type": "application/x-www-form-urlencoded"
  }
}
```

Expected output:

```json
{"label":1,"probability":1.0,"is_attack":true,"backend":"onnx","feature_drift_score":0.9247}
```

## 3. Submit asynchronous prediction jobs

Use `/jobs` when you want the API to queue a request for the background worker. In Swagger UI:

1. Expand **POST /jobs**, click **Try it out**, paste one input below, then click **Execute**.
2. Copy the `job_id` from the response. The API immediately returns HTTP `202` with status `queued`.
3. Expand **GET /jobs/{job_id}**, click **Try it out**, paste that ID into the `job_id` field, and click **Execute**.
4. If the response is still `queued` or `processing`, execute the GET again after a moment. When done, status is `completed` and the `result` contains the prediction. The result fields match `/predict`.

Jobs are kept in Redis for up to one hour. Each input below is a separate job; submit them one at a time and use the ID returned for that specific job.

### Async example 1: Normal page request

POST `/jobs` request body:

```json
{
  "method": "GET",
  "url": "http://localhost/tienda1/index.jsp",
  "body": "",
  "headers": {}
}
```

Immediate response (the ID will be different each time):

```json
{
  "job_id": "<copy-this-id-into-GET-jobs-job_id>",
  "status": "queued"
}
```

### Async example 2: SQL injection in the URL

```json
{
  "method": "GET",
  "url": "http://localhost/tienda1/publico/anadir.jsp?id=2&nombre='; DROP TABLE usuarios; SELECT * FROM datos",
  "body": "",
  "headers": {}
}
```

### Async example 3: Script tag in the URL query

```json
{
  "method": "GET",
  "url": "http://localhost/search?q=%3Cscript%3Ealert(1)%3C/script%3E",
  "body": "",
  "headers": {}
}
```

For examples 2 and 3, the immediate response has the same `job_id` and `status` structure shown above. Poll **GET /jobs/{job_id}** with the new ID from each response. A completed job looks like this; prediction values depend on the model and input:

```json
{
  "job_id": "<your-job-id>",
  "status": "completed",
  "request": { "method": "GET", "url": "...", "body": "", "headers": {} },
  "result": {
    "label": 1,
    "probability": 0.99,
    "is_attack": true,
    "backend": "onnx",
    "feature_drift_score": 1.23
  }
}
```

After the worker completes a job, the **Cumulative predictions by result** Grafana panel adds its `attack` or `normal` result after Prometheus's next scrape. These are cumulative counts over time, so the lines rise as predictions complete and remain visible after processing ends. The **Queue depth** panel can return to zero immediately when the worker drains the queue.

## 4. Read the response fields

- `label`: `0` means the model classified the request as normal; `1` means attack.
- `probability`: model's attack probability from `0` to `1`.
- `is_attack`: the same result as a boolean.
- `backend`: should be `onnx` in the API.
- `feature_drift_score`: how unusual the request's feature values are against the normal training baseline. It is separate from the attack probability.

These are sample predictions, not guarantees. A model can misclassify a request, and a high drift score does not by itself mean an attack.

## 5. View the dashboard and alert

In Grafana, open the **HTTP Threat Detector** dashboard and find **Input feature drift score**. It plots the recent mean request score and the training threshold. To see the rule state, open **Alerting → Alert rules → Input feature drift detected**.

The Grafana drift alert needs at least 10 accepted `/predict` or `/jobs` inputs in a five-minute window. It fires when their five-minute mean score stays above the training threshold for one minute. Separately, Prometheus Alertmanager emails you when at least three synchronous attack predictions occur in five minutes and that condition persists for one minute. SMTP settings are entered directly in the local, Git-ignored `monitoring/alertmanager/alertmanager.yml` file. Automatic model rollback is not configured.

## 6. Stop the local services

When you are done, run this in PowerShell:

```powershell
docker compose down
```
