FROM python:3.12-slim AS builder

RUN apt-get update && \
    apt-get install -y build-essential libmariadb-dev pkg-config && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y libmariadb-dev && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app