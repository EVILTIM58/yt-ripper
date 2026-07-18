FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir yt-dlp

WORKDIR /app
# logo.png* glob: build succeeds even before the logo file is added to the repo
COPY server.py CHANGELOG.md logo.png* ./
COPY pages ./pages

RUN mkdir -p /downloads
ENV DOWNLOAD_DIR=/downloads PORT=8000 PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["python", "server.py"]
