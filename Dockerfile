FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY README.md ./README.md
COPY pyproject.toml ./pyproject.toml

RUN mkdir -p /app/posters

CMD ["python", "src/main.py"]