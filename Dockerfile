FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements-serving.txt ./requirements-serving.txt
RUN pip install --no-cache-dir -r requirements-serving.txt

COPY src/ ./src/
COPY models/ ./models/

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
