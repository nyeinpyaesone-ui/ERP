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
    "setuptools>=84.1.0" \
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

# Copy only application runtime dependencies into the final image.
COPY --from=builder /install /usr/local

# Package installers and build tooling are not needed to execute the API.
# Removing their entire package trees also removes setuptools' bundled
# vulnerable jaraco.context/wheel copies from the shipped runtime image.
RUN find /usr/local /usr/lib -type d \
        \( -name 'pip' -o -name 'pip-*.dist-info' -o -name 'pip*.egg-info' \
        -o -name 'setuptools' -o -name 'setuptools-*.dist-info' -o -name 'setuptools*.egg-info' \
        -o -name 'wheel' -o -name 'wheel-*.dist-info' -o -name 'wheel*.egg-info' \) \
        -prune -exec rm -rf {} + \
    && rm -f /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.11 \
        /usr/local/bin/easy_install /usr/local/bin/easy_install-* /usr/local/bin/wheel \
    && python -c 'from importlib.metadata import distributions; forbidden={"pip", "setuptools", "wheel"}; found=sorted({(item.metadata.get("Name") or "").lower() for item in distributions()} & forbidden); assert not found, f"Build tools leaked into runtime: {found}"; print("Verified runtime image contains no pip, setuptools, or wheel distributions")'

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
