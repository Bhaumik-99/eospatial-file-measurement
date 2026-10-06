FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1

RUN apt-get update     && apt-get install -y --no-install-recommends gdal-bin libgdal-dev libgeos-dev libproj-dev     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
RUN pip install --upgrade pip     && pip install .[dev]

COPY app ./app
COPY tests ./tests
COPY .env.example ./

RUN useradd --create-home --uid 10001 appuser     && mkdir -p /app/storage /app/data     && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
