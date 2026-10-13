# syntax=docker/dockerfile:1
###############################################################################
# ERP SOLUTION — backend image
#
# Multi-arch: python:3.11-slim is a manifest list covering linux/amd64 and
# linux/arm64 (and ppc64le/s390x), so this Dockerfile builds natively on both
# without any architecture-specific layer. Build for several platforms with:
#   docker buildx build --platform linux/amd64,linux/arm64 --push ...
# or locally via ./docker-build.sh --platform=linux/amd64,linux/arm64 --push
#
# Builder note: `pip install --prefix=/install` (not --user) is used because
# the --user site lives under /root/.local in the builder; copying it into a
# non-root home made the interpreter skip it unless PYTHONNOUSERSITE happened
# to be unset. The prefix has no such dependency.
###############################################################################

# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Pip's wheel cache resolves manylinux wheels per-interpreter; installing into
# an isolated prefix keeps the runtime stage free of build tooling.
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Runtime stage
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 postgresql-client redis-tools curl wget ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash app

COPY --from=builder /install /usr/local
COPY --chown=app:app . .

RUN chmod +x /app/entrypoint.sh
RUN mkdir -p uploads static && chown -R app:app uploads static

USER app

# With --prefix=/install the console scripts land in /usr/local/bin, already
# on PATH; PYTHONPATH only points at the application code.
ENV PYTHONPATH=/app

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]