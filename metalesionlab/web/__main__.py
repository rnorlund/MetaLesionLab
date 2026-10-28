"""python -m metalesionlab.web [--site plato|lingua] [--host 127.0.0.1] [--port 8000] [--reload]

--site sets MLL_SITE for the server (brand.py): plato (the default) or lingua; brand.py has their names.
"""
import argparse
import os

import uvicorn

from metalesionlab import brand


def main():
    ap = argparse.ArgumentParser(description=f"Run the web app: {brand.PLATO.name} or {brand.LINGUA.name}")
    ap.add_argument("--site", choices=sorted(brand.SITES), default=None,
                    help=f"which site to serve (default: MLL_SITE, else {brand.DEFAULT_SITE})")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--reload", action="store_true")
    args = ap.parse_args()
    if args.site:
        os.environ["MLL_SITE"] = args.site  # the app module reads it on import (also in --reload workers)
    print(f"Serving {brand.brand_for().name} (MLL_SITE={brand.site_key()}) on http://{args.host}:{args.port}")
    uvicorn.run("metalesionlab.web.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
