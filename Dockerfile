# Tippa Lingua web app as a public demo: no GPU, no torch, spending capped by web/guard.py.
#
#   python scripts/build_site_bundle.py            # writes dist/site_data (gitignored)
#   docker build -t tippa-lingua .
#   docker run -p 7860:7860 -e MODEL_API_KEY=... tippa-lingua
#
# The API key comes from the host's secret store at run time; it is never in the image.
# See deploy/README.md for Hugging Face Spaces, Fly.io and Render.
FROM python:3.12-slim

# ffmpeg reads browser recordings (the Scorer); DejaVu gives the PDF exports Unicode text.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces runs containers as user 1000; use the same user everywhere.
RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt \
    && python -m nltk.downloader -q -d /usr/local/share/nltk_data wordnet

# Draw a chair (/draw) runs Meta's DINOv2-base on the CPU with onnxruntime. The ONNX model is about 350 MB,
# over the repository's 5 MB data guard, so it's fetched here once from a pinned export of the same weights
# and checked against its SHA-256. Only this one file is copied first, so the layer stays cached when the
# rest of the code changes.
COPY metalesionlab/draw_fetch.py /tmp/draw_fetch.py
RUN python /tmp/draw_fetch.py /app/models/dinov2-base.onnx && rm /tmp/draw_fetch.py

COPY pyproject.toml LICENSE ./
COPY public_data ./public_data
COPY metalesionlab ./metalesionlab
# The data bundle is writable by the app: new tiny builds, thumbnails and the meaning-judge cache go
# there (and are lost on restart, which is fine).
COPY --chown=app:app dist/site_data ./site_data
# The spend ledger and volunteers' reference-range summaries. Mount persistent storage at /data to
# keep them across restarts (the daily cap restarts from zero without it). The start script makes a
# mounted volume writable by the app user; if the ledger still can't be written, the guard refuses
# every Meta API call rather than spend without counting.
RUN mkdir -p /data && chown app:app /data
COPY deploy/start.sh /usr/local/bin/tippa-start
RUN chmod 755 /usr/local/bin/tippa-start  # uploads to a Space don't always keep the mode

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PUBLIC_DEMO=1 \
    TOT_PUBLIC=1 \
    TOT_TRUST_PROXY=1 \
    TIPPA_DATA_DIR=/app/site_data \
    TIPPA_NORMS_DIR=/data/norms \
    MLL_LEDGER=/data/costs.jsonl \
    TIPPA_PUBLIC_DAILY_USD=2 \
    MLL_BUDGET_USD=10 \
    PORT=7860 \
    DRAW_MODEL=/app/models/dinov2-base.onnx \
    DRAW_THREADS=2 \
    DRAW_SLOTS=1

EXPOSE 7860
HEALTHCHECK --interval=60s --timeout=5s --start-period=60s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"7860\")}/api/guard', timeout=4)"
# Runs the app as user "app" (uid 1000), on $PORT.
CMD ["tippa-start"]
