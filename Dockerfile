# Panel Weavers · FBA Trends
FROM python:3.15-slim@sha256:94d3426f1def7db4a106a232ac121bfd975393e5dfd40a619b955fae45fe7913

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

ENV WEAVERS_AUTH_MODE=password

WORKDIR /app
COPY requirements.lock .
RUN pip install --no-deps -r requirements.lock

COPY . .

# Run as a non-root user
RUN useradd --create-home appuser && chown -R appuser /app && mkdir -p /app/data
USER appuser

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
