FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY README.md ./README.md
COPY pyproject.toml ./pyproject.toml
COPY src ./src

RUN pip install --no-cache-dir .

RUN mkdir -p /app/posters

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser

CMD ["python", "-m", "src.main"]
