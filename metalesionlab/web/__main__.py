"""python -m metalesionlab.web [--host 127.0.0.1] [--port 8000] [--reload]"""
import argparse

import uvicorn


def main():
    ap = argparse.ArgumentParser(description="Run the Tip of the Tongue web app")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--reload", action="store_true")
    args = ap.parse_args()
    uvicorn.run("metalesionlab.web.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
