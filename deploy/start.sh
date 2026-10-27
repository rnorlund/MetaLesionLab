#!/bin/sh
# Container entry point. Started as root (Fly.io, Render, plain docker run): make /data, which may be
# a freshly mounted root-owned volume, writable by the app user, then run the app as that user.
# Started as user 1000 (Hugging Face Spaces): run the app directly.
set -e
if [ "$(id -u)" = "0" ]; then
  mkdir -p /data
  chown app:app /data
  exec setpriv --reuid=app --regid=app --init-groups "$0" "$@"
fi
# Proxy headers are read by web/limits.py (right end of X-Forwarded-For), not by uvicorn.
exec uvicorn metalesionlab.web.app:app --host 0.0.0.0 --port "${PORT:-7860}" --no-proxy-headers
