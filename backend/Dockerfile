# Build stage: Alpine 3.24 carries patched packages for the Debian 13
# advisories that remain unresolved in the current slim base image.
FROM python:3.11-alpine3.24 AS builder

WORKDIR /app

# Build native Python wheels for both amd64 and arm64. matplotlib and
# uvloop may need source builds on musl/aarch64.
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
    && pip install --no-cache-dir --user -r requirements.txt \
    && pip install --no-cache-dir --user --upgrade --ignore-installed \
        "setuptools>=78.1.1" \
        "wheel>=0.46.2" \
        "jaraco.context>=6.1.0"

# Runtime stage: keep compilers and development headers out of production.
FROM python:3.11-alpine3.24 AS runtime

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

COPY --from=builder --chown=app:app /root/.local /home/app/.local
COPY --chown=app:app . .

RUN chmod +x /app/entrypoint.sh \
    && mkdir -p uploads static \
    && chown -R app:app uploads static

USER app

ENV PATH="/home/app/.local/bin:${PATH}"
ENV PYTHONPATH=/app

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
