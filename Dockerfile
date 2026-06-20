# Patient Context Board / Office Assistant — portable container.
# Synthetic data only; runs fully offline (no model, no network) by default.
FROM python:3.13-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FORCE_MOCK=1 \
    FORCE_DETERMINISTIC=1

# Deps first for layer caching.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# App.
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY config/ ./config/
COPY run.py ./

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3).status==200 else 1)"

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
