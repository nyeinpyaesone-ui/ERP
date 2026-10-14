# Build stage
FROM python:3.14-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.14-slim AS runtime

WORKDIR /app

# Refresh the base interpreter tooling — the slim image ships pip 24.0 /
# setuptools 79, which carry known advisories that Trivy flags as image
# alerts (code-scanning "usr/local/lib/python3.11/..." findings).
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 postgresql-client redis-tools curl wget ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash app

COPY --from=builder /root/.local /home/app/.local
COPY --chown=app:app . .

RUN chmod +x /app/entrypoint.sh
RUN mkdir -p uploads static && chown -R app:app uploads static

USER app

ENV PATH="/home/app/.local/bin:${PATH}"
ENV PYTHONPATH=/app

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]