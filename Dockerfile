FROM python:3-alpine

ENV UV_SYSTEM_PYTHON=1
ENV UV_NO_DEV=1

RUN apk --no-cache --virtual build-dependencies add \
        git \
        openssh \
        xz && \
    apk del build-dependencies

COPY . /app
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    cd /app && \
    uv sync --locked && \
    uv pip install . && \
    cd / && \
    rm -rf /app
