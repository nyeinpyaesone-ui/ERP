# syntax=docker/dockerfile:1
###############################################################################
# ERP SOLUTION — backend image
#
# Alpine runtime keeps the production image minimal. The builder contains the
# compiler and PostgreSQL headers; only runtime libraries are copied/installed
# in the final stage. The same Python/Alpine release is used in both stages.
###############################################################################

FROM python:3.11.18-alpine3.24 AS builder

WORKDIR /app

RUN apk update \
    && apk upgrade --no-cache \
    && apk add --no-cache --virtual .build-deps \
        build-base \
        linux-headers \
        postgresql-dev \
        freetype-dev \
        libpng-dev \
        jpeg-dev \
        pkgconf \
    && rm -rf /var/cache/apk/*

# Keep packaging tools at versions containing the fixes reported by Trivy.
RUN python -m pip install --no-cache-dir --upgrade \
    "pip>=26.2.0" \
    "setuptools>=83.0.0" \
    "wheel>=0.46.2"

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11.18-alpine3.24 AS runtime

WORKDIR /app

# Do not install postgresql-client, redis-tools, curl, or wget. The entrypoint
# uses the Python database/Redis clients and Compose healthchecks use urllib.
RUN apk update \
    && apk upgrade --no-cache \
    && apk add --no-cache \
        bash \
        ca-certificates \
        freetype \
        libjpeg-turbo \
        libpng \
        libpq \
        libstdc++ \
    && addgroup -S app \
    && adduser -S -G app -h /home/app -s /bin/bash app \
    && rm -rf /var/cache/apk/*

# The runtime image contains no stale packaging tools from the base image.
RUN python -m pip install --no-cache-dir --upgrade \
    "pip>=26.2.0" \
    "setuptools>=83.0.0" \
    "wheel>=0.46.2"

COPY --from=builder /install /usr/local
COPY --chown=app:app . .

RUN chmod +x /app/entrypoint.sh \
    && mkdir -p uploads static \
    && chown -R app:app uploads static

USER app

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
