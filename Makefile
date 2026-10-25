.PHONY: all parse train evaluate export test serve docker-up docker-down mlflow-ui dvc-setup dvc-data dvc-repro dvc-status clean

CSV      := dataset/csic_database.csv
PYTHON   := python3

all: train evaluate export

parse:
	$(PYTHON) -m src.parse $(CSV)

train:
	$(PYTHON) -m src.train --csv $(CSV)

evaluate:
	$(PYTHON) -m src.evaluate

export:
	$(PYTHON) -m src.export_onnx

test:
	$(PYTHON) -m pytest tests/ -v

serve:
	$(PYTHON) -m uvicorn src.api:app --host 127.0.0.1 --port 8000

docker-up:
	docker compose up --build

docker-down:
	docker compose down

ci-check:
	@$(PYTHON) -c "\
import json, sys; \
m = json.load(open('reports/metrics.json')); \
fpr = m['prod_clean_holdout']['fpr']; \
print(f'Prod holdout FPR: {fpr:.4f}'); \
sys.exit(1 if fpr > 0.015 else 0)"
	@echo 'CI quality gate PASSED (FPR <= 1.5%)'

mlflow-ui:
	$(PYTHON) -m mlflow server --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5000

# Optional DVC workflow. Install requirements-dvc.txt before running these.
dvc-setup:
	dvc init

dvc-data:
	dvc add $(CSV)

dvc-repro:
	dvc repro

dvc-status:
	dvc status

clean:
	rm -rf models/*.pkl models/*.json models/*.onnx models/*.txt \
	       reports/*.npy reports/*.pkl reports/*.json reports/*.png \
	       reports/*.txt __pycache__ src/__pycache__ tests/__pycache__
