# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Refresh the Debian package index and apply available security updates before
# installing build dependencies. This keeps the image from retaining stale
# packages inherited from the upstream Python base image.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt \
    && pip install --no-cache-dir --user --upgrade --ignore-installed \
        "setuptools>=78.1.1" \
        "wheel>=0.46.2" \
        "jaraco.context>=6.1.0"

# Runtime stage
FROM python:3.11-slim AS runtime

WORKDIR /app

# Apply available Debian security updates in the final runtime image too;
# updating only the builder would leave vulnerable OS packages in production.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        ca-certificates \
        zlib1g \
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
