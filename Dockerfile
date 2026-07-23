FROM python:3-alpine

RUN apk --no-cache add \
    git \
    gzip \
    openssh \
    tar

COPY pyproject.toml uv.lock /
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    uv export \
        --frozen \
        --no-dev \
        --no-emit-project \
        --output-file requirements.txt && \
    uv pip install --system --no-cache -r requirements.txt && \
    rm pyproject.toml uv.lock requirements.txt

COPY . /app
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    cd /app && \
    uv pip install --system --no-cache --no-deps . && \
    cd / && \
    rm -r /app
