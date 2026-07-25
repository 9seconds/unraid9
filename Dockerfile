FROM python:3-slim AS ffmpeg

RUN apt-get update && \
    apt-get install \
        --yes \
        --no-install-recommends \
        curl \
        xz-utils
ARG TARGETARCH
RUN case "$TARGETARCH" in \
        amd64) ffmpeg_archive=ffmpeg-master-latest-linux64-gpl.tar.xz ;; \
        arm64) ffmpeg_archive=ffmpeg-master-latest-linuxarm64-gpl.tar.xz ;; \
        *) echo "Unsupported target architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac && \
    curl --fail --location --silent --show-error \
        "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/$ffmpeg_archive" \
        --output "/tmp/$ffmpeg_archive" && \
    curl --fail --location --silent --show-error \
        "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/checksums.sha256" \
        --output /tmp/checksums.sha256 && \
    grep " $ffmpeg_archive$" /tmp/checksums.sha256 > /tmp/ffmpeg.sha256 && \
    cd /tmp && \
    sha256sum -c ffmpeg.sha256 && \
    mkdir /tmp/ffmpeg && \
    tar --extract --xz --file "/tmp/$ffmpeg_archive" \
        --strip-components=1 --directory /usr

# -----------------------------------------------------------------------------

FROM python:3-slim AS main

RUN apt-get update && \
    apt-get install --yes --no-install-recommends \
        git \
        gzip \
        openssh-client \
        tar && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ffmpeg /usr/bin/ffprobe /usr/bin/ffmpeg /usr/bin/

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
