# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-runtime.txt .
RUN pip install --no-cache-dir --user -r requirements-runtime.txt \
    && pip install --no-cache-dir --user --upgrade "setuptools>=78.1.1" wheel

# Runtime stage
FROM python:3.11-slim AS runtime

WORKDIR /app

# Keep the runtime OS footprint small. PostgreSQL and Redis readiness are
# checked through the already-installed Python drivers, not external CLIs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder --chown=10001:10001 /root/.local /home/app/.local
COPY --chown=10001:10001 . .

RUN chmod +x /app/entrypoint.sh \
    && install -d -m 0755 -o 10001 -g 10001 /app/uploads /app/static /home/app

USER 10001:10001

ENV HOME=/home/app
ENV PATH="/home/app/.local/bin:${PATH}"
ENV PYTHONPATH=/app

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]