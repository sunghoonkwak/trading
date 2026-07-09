FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

FROM base AS test

RUN pip install --no-cache-dir -r requirements-dev.txt \
    && mkdir -p /app/KIS_config \
    && cp templates/strategy_config.json /app/KIS_config/strategy_config.json \
    && chown -R 1000:1000 /app

FROM base AS runtime

EXPOSE 8080

CMD ["python", "src/main.py"]
