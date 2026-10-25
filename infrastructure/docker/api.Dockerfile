# API, worker, migration and dispatch roles share this image; no secrets, books or model weights are baked in.
FROM ghcr.io/astral-sh/uv:0.12.15@sha256:62f8c047d0a0e9ece6b53fc63df902585a67a47a7f318ddec4a37db586edc8e3 AS uv

FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv \
    PYTHONUNBUFFERED=1 PATH=/opt/venv/bin:$PATH
WORKDIR /app
COPY apps/api/pyproject.toml apps/api/uv.lock apps/api/.python-version ./
RUN uv sync --locked --no-dev --no-install-project
COPY apps/api/alembic.ini ./
COPY apps/api/migrations ./migrations
COPY apps/api/app ./app
RUN useradd --uid 10001 --create-home vision \
    && install -d -m 700 -o vision /data/originals /data/renders
ARG VISION_REVISION=unknown
LABEL org.opencontainers.image.revision=$VISION_REVISION
USER vision
# Local models are mounted read-only and never downloaded at run time.
ENV VISION_SOURCE_ROOT=/data/originals VISION_RENDER_ROOT=/data/renders HF_HUB_OFFLINE=1 \
    HF_HOME=/models/huggingface VISION_DOCLING_ARTIFACTS=/models/docling
CMD ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]
