# HTTP Request Anomaly Detector — CSIC 2010

A reproducible MLOps pipeline that classifies HTTP requests as **normal** or **attack**, exported to ONNX for production inference.

## Dataset
- **CSIC 2010** — 36,000 normal + 25,065 attack requests in `dataset/csic_database.csv`
- Attack types: SQL injection, XSS, path traversal, command injection, parameter tampering

## Repo Structure
```
dataset/            # raw data (untouched)
src/
  parse.py          # CSV -> structured records + deduplication
  features.py       # pure function: record -> fixed-length feature vector
  train.py          # training pipeline (LR baseline + LightGBM)
  evaluate.py       # metrics, plots, error analysis
  export_onnx.py    # ONNX export + latency benchmark
  predict.py        # production inference
models/             # trained artifacts (pkl, json, onnx)
reports/            # metrics.json, plots
tests/              # pytest suite
```

## Setup (always use a virtual environment)

```bash
# 1. Create a virtual environment (one-time setup)
python3 -m venv venv

# 2. Activate it
source venv/bin/activate        # Linux / Mac
# venv\Scripts\activate         # Windows

# 3. Install dependencies into the venv (NOT your global Python)
pip install -r requirements.txt

# 4. Run the full pipeline
make train       # parse -> feature extraction -> train -> save models
make evaluate    # plots + error analysis
make export      # ONNX export + latency benchmark
make test        # run pytest suite
make ci-check    # fails if prod holdout FPR > 1.5%
```

> To leave the venv: `deactivate`
> The `venv/` folder is gitignored — each person creates their own locally.

## Local MLOps Demo

The local Docker API, prediction examples, Prometheus metrics, and MLflow tracking steps are documented in [LOCAL_DEMO.md](LOCAL_DEMO.md). Start serving with `docker compose up --build -d`; the API docs are available at `http://127.0.0.1:8000/docs`.

## Model Choice: LightGBM over XGBoost
- **Speed**: LightGBM's leaf-wise growth is 3–5× faster on this dataset size
- **PR-AUC**: Consistently higher in CV experiments due to better minority-class handling
- **class_weight='balanced'**: Compensates for 36k/25k imbalance

## Primary Metrics
The headline metric is **FPR on normal traffic** (must be ≤ 1.5% for CI gate) and **PR-AUC**.
Accuracy is intentionally not the headline metric.

| Metric | Description |
|--------|-------------|
| `fpr`  | False positive rate on clean traffic — CI gate |
| `pr_auc` | Area under Precision-Recall curve |
| `roc_auc` | Area under ROC curve |
| `recall` | Fraction of attacks detected |

## Optional DVC workflow

DVC versions the dataset and training inputs/outputs locally. Install its optional dependency, initialize DVC once in the repository, add the dataset, then reproduce the training stage:

```bash
python -m pip install -r requirements-dvc.txt
make dvc-setup
make dvc-data
make dvc-repro
```

The dataset was previously tracked directly by Git. To let DVC own its content while keeping the CSV in your working folder, run `git rm --cached dataset/csic_database.csv` once; this stages its removal from Git without deleting the local file. Then commit `dvc.yaml`, `dvc.lock`, `params.yaml`, `dataset/csic_database.csv.dvc`, and `.gitignore`. DVC cache files stay local unless a remote is configured; no remote is required. The pipeline tracks generated model binaries and intermediate predictions in DVC, while small configs, metrics, plots, and reports remain Git-managed.

## GitHub Actions CI

The workflow in `.github/workflows/ci.yml` runs on pushes and pull requests to `main`. It installs the lightweight CI dependencies, runs Ruff checks and pytest, then enforces a 1.5% limit on the committed clean-holdout FPR in `reports/metrics.json`. Fresh training and ONNX integration checks are not run on GitHub because the DVC data/model cache has no remote configured.

## Feature Groups
- **Content**: lengths, Shannon entropy, special char counts/ratios, encoding, injection keywords (SQL, XSS, path-traversal, cmd)
- **Structure-aware**: unknown endpoint, unknown param names, param count deviation, value-length z-score, unseen chars (learned from normal traffic only)
