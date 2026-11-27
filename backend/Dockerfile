# syntax=docker/dockerfile:1
###############################################################################
# ERP SOLUTION — backend image
#
# Both stages use the same Python, Alpine and musl ABI. The builder installs
# native build dependencies; the runtime keeps only shared libraries required
# by the application. Buildx can publish linux/amd64 and linux/arm64 manifests.
###############################################################################

FROM python:3.15-alpine3.24 AS builder

WORKDIR /app

# Native dependencies for psycopg2, uvloop and matplotlib on musl platforms.
RUN apk add --no-cache \
    build-base \
    linux-headers \
    postgresql-dev \
    pkgconf \
    freetype-dev \
    libpng-dev \
    qhull-dev

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade "pip>=26.1.2" \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt \
    && pip install --no-cache-dir --prefix=/install --upgrade --ignore-installed \
        "setuptools>=78.1.1" \
        "wheel>=0.46.2" \
        "jaraco.context>=6.1.0"

FROM python:3.15-alpine3.24 AS runtime

WORKDIR /app

RUN apk add --no-cache \
    bash \
    ca-certificates \
    freetype \
    libgcc \
    libpng \
    libpq \
    libstdc++ \
    && adduser -D -h /home/app -s /bin/bash app \
    && python -m pip install --no-cache-dir --upgrade "pip>=26.1.2"

COPY --from=builder /install /usr/local
COPY --chown=app:app . .

RUN chmod +x /app/entrypoint.sh \
    && mkdir -p uploads static \
    && chown -R app:app uploads static

USER app

ENV PYTHONPATH=/app

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
