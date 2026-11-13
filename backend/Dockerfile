# Build stage: Alpine avoids carrying unused Debian system utilities into runtime.
FROM python:3.11.18-alpine3.24 AS builder

WORKDIR /app

RUN apk update \
    && apk upgrade --no-cache \
    && apk add --no-cache --virtual .build-deps \
        build-base \
        linux-headers \
        freetype-dev \
        libpng-dev \
        libjpeg-turbo-dev \
        postgresql-dev \
        pkgconf \
        zlib-dev

# CVE-2026-23949, CVE-2026-24049 and CVE-2026-8643 fixed toolchain versions.
RUN python -m pip install --no-cache-dir --upgrade \
    "pip>=26.1.2" \
    "setuptools>=82.0.0" \
    "wheel>=0.46.2"

COPY requirements-runtime.txt .
# Matplotlib does not publish musllinux wheels; compile it against Alpine's
# supported system libraries while the other dependencies use compatible wheels.
RUN python -m pip install --no-cache-dir --user --no-binary=matplotlib -r requirements-runtime.txt \
    && python -m pip check

# Runtime stage: no compiler, headers, or package manager cache is shipped.
FROM python:3.11.18-alpine3.24 AS runtime

WORKDIR /app

RUN apk update \
    && apk upgrade --no-cache \
    && apk add --no-cache \
        bash \
        ca-certificates \
        fontconfig \
        freetype \
        libgfortran \
        libjpeg-turbo \
        libpng \
        libpq \
        libstdc++ \
        ttf-dejavu \
        zlib \
    && update-ca-certificates

# Update image-provided Python packaging tools to non-vulnerable releases.
# Remove unused build-time distributions and the old ensurepip bootstrap wheel.
RUN python -m pip install --no-cache-dir --upgrade \
    "pip>=26.1.2" \
    "setuptools>=82.0.0" \
    "wheel>=0.46.2" \
    && python -m pip uninstall --yes setuptools wheel \
    && if [ -d /usr/local/lib/python3.11/ensurepip/_bundled ]; then \
        find /usr/local/lib/python3.11/ensurepip/_bundled -maxdepth 1 -type f -name 'setuptools-*.whl' -delete; \
    fi \
    && python - <<'PY'
from importlib import metadata
from pathlib import Path

for package in ("setuptools", "wheel"):
    matches = [
        str(distribution._path)
        for distribution in metadata.distributions()
        if (distribution.metadata.get("Name") or "").lower() == package
    ]
    if matches:
        raise SystemExit(f"Unexpected runtime build-tool metadata for {package}: {matches}")

bundled = Path("/usr/local/lib/python3.11/ensurepip/_bundled")
remaining = list(bundled.glob("setuptools-*.whl")) if bundled.exists() else []
if remaining:
    raise SystemExit(f"Unused vulnerable ensurepip wheels remain: {remaining}")
print("Runtime packaging tools and bundled setuptools wheels are absent.")
PY

COPY --from=builder --chown=10001:10001 /root/.local /home/app/.local
COPY --chown=10001:10001 . .

# Match the runtime user's user-site package path during the smoke test.
ENV HOME=/home/app
ENV PATH="/home/app/.local/bin:${PATH}"
ENV PYTHONPATH=/app
ENV MPLBACKEND=Agg
ENV MPLCONFIGDIR=/tmp/matplotlib

RUN chmod +x /app/entrypoint.sh \
    && install -d -m 0755 -o 10001 -g 10001 \
        /app/uploads \
        /app/static \
        /home/app \
    && python - <<'PY'
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import psycopg2

figure, axis = plt.subplots()
axis.plot([1, 2], [1, 2])
figure.savefig("/tmp/matplotlib-smoke.png")
plt.close(figure)
PY

USER 10001:10001

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
