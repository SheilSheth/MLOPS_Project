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

## 3. Read the response fields

- `label`: `0` means the model classified the request as normal; `1` means attack.
- `probability`: model's attack probability from `0` to `1`.
- `is_attack`: the same result as a boolean.
- `backend`: should be `onnx` in the API.
- `feature_drift_score`: how unusual the request's feature values are against the normal training baseline. It is separate from the attack probability.

These are sample predictions, not guarantees. A model can misclassify a request, and a high drift score does not by itself mean an attack.

## 4. View the dashboard and alert

In Grafana, open the **HTTP Threat Detector** dashboard and find **Input feature drift score**. It plots the recent mean request score and the training threshold. To see the rule state, open **Alerting → Alert rules → Input feature drift detected**.

The alert needs at least 10 accepted `/predict` or `/jobs` inputs in a five-minute window. It fires when their five-minute mean score stays above the training threshold for one minute. It appears in Grafana; email or chat notifications and automatic model rollback are not configured.

## 5. Stop the local services

When you are done, run this in PowerShell:

```powershell
docker compose down
```
