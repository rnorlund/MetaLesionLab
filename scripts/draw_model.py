"""Draw your chair: get the DINOv2-base model the /draw page runs, as ONNX for onnxruntime on CPU.

The model file is about 350 MB, far over the repository's 5 MB data guard, so it is never committed.
Make it at build time, either way:

  python scripts/draw_model.py export     # from facebook/dinov2-base with torch + transformers
                                          # (a Docker builder stage; the runtime needs neither)
  python scripts/draw_model.py download   # a pinned community ONNX export of the same weights
                                          # (no torch at all; checked against its SHA-256; the
                                          # Dockerfile runs metalesionlab/draw_fetch.py, the same code)

Both write $DRAW_MODEL (default runs/models/dinov2-base-cls.onnx), which metalesionlab/draw.py loads
on the first /api/draw request. Then check and time it (both need torch, so run them on a dev machine):

  python scripts/draw_model.py verify [--n 20]   # cosine similarity to the torch embeddings, >= 0.999
  python scripts/draw_model.py bench             # CPU latency and memory, torch vs. onnxruntime

DINOv2: Meta AI, Apache-2.0 (https://huggingface.co/facebook/dinov2-base).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from metalesionlab.draw import MODEL_PATH  # noqa: E402
from metalesionlab.plato import DINO_MODEL  # noqa: E402

PLATO_DIR = Path(os.environ.get("PLATO_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/core"))


def export(out: Path, opset: int = 17) -> None:
    """DINOv2-base -> ONNX with one output, the CLS token (batch dimension dynamic, 224 x 224 input)."""
    import torch
    from transformers import AutoModel

    class ClsOnly(torch.nn.Module):
        def __init__(self, model):
            super().__init__()
            self.model = model

        def forward(self, pixel_values):
            return self.model(pixel_values=pixel_values).last_hidden_state[:, 0]

    model = ClsOnly(AutoModel.from_pretrained(DINO_MODEL).eval())
    dummy = torch.zeros(1, 3, 224, 224)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp.onnx")
    with torch.no_grad():
        torch.onnx.export(model, (dummy,), str(tmp), input_names=["pixel_values"], output_names=["cls"],
                          dynamic_axes={"pixel_values": {0: "batch"}, "cls": {0: "batch"}},
                          opset_version=opset, do_constant_folding=True, dynamo=False)
    os.replace(tmp, out)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.0f} MB)")


def download(out: Path) -> None:
    """The pinned community export (metalesionlab/draw_fetch.py), checked against its SHA-256."""
    from metalesionlab.draw_fetch import fetch

    fetch(out)


def sample_images(n: int):
    """n drawings from the experiment: half Muse Image doodles, half people's (ink-cropped, as embedded)."""
    from PIL import Image

    from metalesionlab.plato import ink_crop, load_dir

    keys = ["chair", "umbrella", "house", "cat", "tree", "bicycle", "face", "book", "cup", "car"]
    files = []
    for i in range(n):
        key = keys[i % len(keys)]
        src = (PLATO_DIR / "ai" / "doodle" / key) if i % 2 == 0 else (PLATO_DIR / "human" / key)
        files.append(load_dir(src)[i // len(keys)])
    return files, [ink_crop(Image.open(f).convert("RGB")) for f in files]


def verify(path: Path, n: int) -> dict:
    import numpy as np

    from metalesionlab.draw import OnnxEmbedder, TorchEmbedder

    files, imgs = sample_images(n)
    t = TorchEmbedder()(imgs)
    o = OnnxEmbedder(path)(imgs)
    cos = (t * o).sum(1) / np.linalg.norm(t, axis=1) / np.linalg.norm(o, axis=1)
    res = {"model": str(path), "n": n, "cos_min": float(cos.min()), "cos_mean": float(cos.mean()),
           "max_abs_diff": float(np.abs(t - o).max())}
    print(json.dumps(res, indent=1))
    if cos.min() < 0.999:
        raise SystemExit(f"FAIL: min cosine {cos.min():.5f} < 0.999")
    return res


BENCH_CHILD = r"""
import json, os, resource, sys, time
t0 = time.perf_counter()
backend, path, threads, n = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
sys.path.insert(0, sys.argv[5])
from PIL import Image, ImageDraw
from metalesionlab import draw
def rss_mb():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 1e6 if sys.platform == "darwin" else r / 1e3
import random
random.seed(0)
strokes = [[[random.randint(0, 400) for _ in range(30)], [random.randint(0, 400) for _ in range(30)]] for _ in range(6)]
base = rss_mb()
t1 = time.perf_counter()
if backend == "onnx":
    emb = draw.OnnxEmbedder(draw.Path(path), threads=threads)
else:
    emb = draw.TorchEmbedder(threads=threads)
t2 = time.perf_counter()
load_rss = rss_mb()
first = time.perf_counter(); emb([draw.render(strokes)]); first = time.perf_counter() - first
lat, pre = [], []
for i in range(n):
    a = time.perf_counter(); img = draw.render(strokes); b = time.perf_counter()
    emb([img]); c = time.perf_counter()
    pre.append(b - a); lat.append(c - a)
lat.sort(); pre.sort()
print(json.dumps({"backend": backend, "threads": threads, "import_and_start_s": round(t1 - t0, 2),
                  "load_s": round(t2 - t1, 2), "first_call_s": round(first, 3),
                  "median_s": round(lat[len(lat) // 2], 3), "p90_s": round(lat[int(len(lat) * 0.9)], 3),
                  "render_median_s": round(pre[len(pre) // 2], 4),
                  "rss_before_model_mb": round(base), "rss_after_load_mb": round(load_rss),
                  "peak_rss_mb": round(rss_mb())}))
"""


def bench(path: Path, n: int, threads: list[int]) -> list[dict]:
    """Each backend in a fresh process, so imports, load time and peak memory are its own."""
    rows = []
    for t in threads:
        for backend in ("torch", "onnx"):
            r = subprocess.run([sys.executable, "-c", BENCH_CHILD, backend, str(path), str(t), str(n), str(REPO)],
                               capture_output=True, text=True, env={**os.environ, "OMP_NUM_THREADS": str(t)})
            if r.returncode:
                print(r.stderr[-2000:])
                continue
            row = json.loads(r.stdout.strip().splitlines()[-1])
            rows.append(row)
            print(json.dumps(row), flush=True)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["export", "download", "verify", "bench"])
    ap.add_argument("--out", type=Path, default=MODEL_PATH)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--threads", type=int, nargs="*", default=[2])
    ap.add_argument("--opset", type=int, default=17)
    args = ap.parse_args()
    if args.cmd == "export":
        export(args.out, args.opset)
    elif args.cmd == "download":
        download(args.out)
    elif args.cmd == "verify":
        verify(args.out, args.n)
    else:
        bench(args.out, args.n, args.threads)


if __name__ == "__main__":
    main()
