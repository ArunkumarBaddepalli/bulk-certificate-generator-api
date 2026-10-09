FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////data/certificates.db \
    CERT_STORAGE_DIR=/data/storage/certificates

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Run as a non-root user; /data is the volume for the DB and PDFs.
RUN useradd --create-home appuser \
    && mkdir -p /data/storage/certificates \
    && chown -R appuser:appuser /data /app
USER appuser

EXPOSE 8000
# Shell form so $PORT is honoured on hosts that inject it (Render, Heroku-style).
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
