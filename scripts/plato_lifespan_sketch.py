"""The life of a chair, stretch: an AI that grows up on people's chairs, from scratch.

A small Sketch-RNN-style model (Ha & Eck 2017; decoder only, unconditional: an LSTM over stroke-5 points with a
20-component Gaussian mixture for the pen offsets) is trained from random weights on Quick, Draw! chairs
(Google, CC BY 4.0). At log-spaced training steps it draws 64 chairs; they are rendered exactly like the human
drawings (to_quickdraw + render_strokes) and measured like every other set (plato_lifespan_analyze.py --sketch).

Usage:
  python -I scripts/plato_lifespan_sketch.py fetch [--n 20000]          # on the Mac: stream the training chairs
  python scripts/plato_lifespan_sketch.py train --data DIR --out DIR      # on a GPU server (or --device mps/cpu)
  python -I scripts/plato_lifespan_sketch.py embed                        # on the Mac: render + DINOv2

Files: $PLATO_LIFESPAN_DIR/sketch/train_chair.ndjson (fetch), sketch/samples/step<k>_t<temp>.json (train: list
of drawings in Quick, Draw! [[xs], [ys]] format), embeddings/sketch/step<k>_t<temp>.npz (embed).
The training drawings are the recognized Quick, Draw! chairs AFTER the 200 used as the adult reference, so the
model never sees the reference drawings.
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from metalesionlab.plato_lifespan import LIFESPAN_DIR, to_quickdraw  # noqa: E402

STEPS = [0, 50, 100, 200, 400, 800, 1600, 3200, 6400, 12800, 25600]
TEMPS = [1.0, 0.5]
MAX_LEN = 200
N_SAMPLES = 64


# ---------- data ----------

def to_stroke5(drawing: list, max_len: int = MAX_LEN) -> np.ndarray | None:
    """Quick, Draw! [[xs], [ys]] strokes -> stroke-5 (dx, dy, pen down, pen up, end), start token excluded."""
    pts = []
    for xs, ys in drawing:
        for i, (x, y) in enumerate(zip(xs, ys)):
            pts.append((x, y, 1 if i == len(xs) - 1 else 0))
    if len(pts) < 2 or len(pts) > max_len - 1:
        return None
    a = np.array(pts, float)
    d = np.diff(np.vstack([[0, 0, 0], a]), axis=0)[:, :2]
    d[0] = a[0, :2] - 0  # first point relative to the origin (top-left)
    s5 = np.zeros((len(a) + 1, 5))
    s5[:-1, :2] = d
    s5[:-1, 2] = 1 - a[:, 2]
    s5[:-1, 3] = a[:, 2]
    s5[-1, 4] = 1
    return s5


def from_stroke5(s5: np.ndarray) -> list:
    """Stroke-5 -> Quick, Draw! format (absolute points, split at pen-ups), via to_quickdraw's normalization."""
    x = y = 0.0
    strokes, cur = [], []
    for dx, dy, p1, p2, p3 in s5:
        if p3 > 0.5:
            break
        x, y = x + dx, y + dy
        cur.append((x, y))
        if p2 > 0.5:
            strokes.append(cur)
            cur = []
    if cur:
        strokes.append(cur)
    return to_quickdraw([s for s in strokes if s])


def fetch(n: int):
    """The first n recognized chairs after the 200 used as the adult reference (plato.stream_quickdraw order)."""
    import httpx

    from metalesionlab.plato import QUICKDRAW_URL

    out = LIFESPAN_DIR / "sketch" / "train_chair.ndjson"
    out.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(6):
        kept, seen_rec = [], 0
        try:
            with httpx.stream("GET", QUICKDRAW_URL.format(category="chair"), timeout=60) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    if rec.get("recognized") is True and rec.get("word") == "chair":
                        seen_rec += 1
                        if seen_rec > 200:
                            kept.append(rec["drawing"])
                    if len(kept) >= n:
                        break
            break
        except Exception as e:
            print(f"attempt {attempt} failed ({type(e).__name__}); retrying", flush=True)
            time.sleep(5 * 2 ** attempt)
    out.write_text("\n".join(json.dumps(d) for d in kept))
    print(f"wrote {len(kept)} chairs to {out}")


# ---------- model ----------

def build(device: str, hidden: int = 512, mixtures: int = 20):
    import torch
    from torch import nn

    class Decoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(5, hidden, batch_first=True)
            self.drop = nn.Dropout(0.1)
            self.out = nn.Linear(hidden, 6 * mixtures + 3)
            self.m = mixtures

        def forward(self, x, state=None):
            h, state = self.lstm(x, state)
            return self.out(self.drop(h)), state

        def params(self, y):
            m = self.m
            pi, mx, my, sx, sy, rho = torch.split(y[..., :6 * m], m, dim=-1)
            return (torch.log_softmax(pi, -1), mx, my, torch.exp(sx.clamp(-6, 4)), torch.exp(sy.clamp(-6, 4)),
                    torch.tanh(rho) * 0.999, y[..., 6 * m:])

    return Decoder().to(device)


def nll(model, y, target, mask):
    import torch

    logpi, mx, my, sx, sy, rho, pen = model.params(y)
    dx, dy = target[..., 0:1], target[..., 1:2]
    zx, zy = (dx - mx) / sx, (dy - my) / sy
    z = zx ** 2 + zy ** 2 - 2 * rho * zx * zy
    logn = -z / (2 * (1 - rho ** 2)) - torch.log(2 * math.pi * sx * sy * torch.sqrt(1 - rho ** 2))
    lse = torch.logsumexp(logpi + logn, -1)
    pen_t = target[..., 2:].argmax(-1)
    l_off = -(lse * mask).sum() / mask.sum()
    l_pen = torch.nn.functional.cross_entropy(pen.reshape(-1, 3), pen_t.reshape(-1), reduction="mean")
    return l_off + l_pen


def sample(model, n: int, temp: float, scale: float, device: str, max_len: int = MAX_LEN) -> list:
    import torch

    model.eval()
    out = np.zeros((n, max_len, 5))
    with torch.no_grad():
        x = torch.zeros(n, 1, 5, device=device)
        x[:, 0, 2] = 1  # start token: pen down at the origin
        state = None
        done = np.zeros(n, bool)
        for t in range(max_len):
            y, state = model(x, state)
            logpi, mx, my, sx, sy, rho, pen = model.params(y[:, -1])
            k = torch.distributions.Categorical(logits=logpi / temp).sample()
            idx = k[:, None]
            mux, muy = mx.gather(1, idx)[:, 0], my.gather(1, idx)[:, 0]
            s1, s2 = sx.gather(1, idx)[:, 0] * math.sqrt(temp), sy.gather(1, idx)[:, 0] * math.sqrt(temp)
            r = rho.gather(1, idx)[:, 0]
            e1, e2 = torch.randn(n, device=device), torch.randn(n, device=device)
            dx = mux + s1 * e1
            dy = muy + s2 * (r * e1 + torch.sqrt(1 - r ** 2) * e2)
            p = torch.distributions.Categorical(logits=pen / temp).sample()
            step = torch.zeros(n, 5, device=device)
            step[:, 0], step[:, 1] = dx, dy
            step[torch.arange(n), 2 + p] = 1
            out[:, t] = step.cpu().numpy()
            done |= (p == 2).cpu().numpy()
            if done.all():
                break
            x = step[:, None]
    model.train()
    drawings = []
    for s5 in out:
        s5 = s5.copy()
        s5[:, :2] *= scale
        drawings.append(from_stroke5(s5))
    return drawings


def train(data: Path, out: Path, device: str, batch: int = 100, lr: float = 1e-3, seed: int = 20261027):
    import torch

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    seqs = [s for s in (to_stroke5(json.loads(line)) for line in data.read_text().splitlines()) if s is not None]
    scale = float(np.std(np.concatenate([s[:-1, :2] for s in seqs]).ravel()))
    X = np.zeros((len(seqs), MAX_LEN + 1, 5), np.float32)
    L = np.zeros(len(seqs), int)
    for i, s in enumerate(seqs):
        s = s.copy()
        s[:, :2] /= scale
        X[i, 0, 2] = 1  # start token
        X[i, 1:len(s) + 1] = s
        X[i, len(s) + 1:, 4] = 1  # padding: end state
        L[i] = len(s)
    print(f"{len(seqs)} chairs, offset scale {scale:.2f}, device {device}", flush=True)
    model = build(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.ExponentialLR(opt, 0.9999)
    (out / "samples").mkdir(parents=True, exist_ok=True)
    meta = {"model": "Sketch-RNN-style decoder (LSTM 512, 20 mixtures), unconditional", "n_train": len(seqs),
            "scale": scale, "batch": batch, "lr": lr, "seed": seed, "steps": STEPS, "temps": TEMPS,
            "data": "Google Quick, Draw! chairs (CC BY 4.0), recognized, after the 200 reference drawings", "log": []}
    t0 = time.time()
    Xt = torch.tensor(X, device=device)
    mask_all = (torch.arange(MAX_LEN, device=device)[None] < torch.tensor(L, device=device)[:, None]).float()
    for step in range(STEPS[-1] + 1):
        if step in STEPS:
            for temp in TEMPS:
                torch.manual_seed(seed + step)
                d = sample(model, N_SAMPLES, temp, scale, device)
                (out / "samples" / f"step{step}_t{temp}.json").write_text(json.dumps(d))
            torch.save(model.state_dict(), out / f"step{step}.pt")
            print(f"step {step}: sampled ({time.time() - t0:.0f}s)", flush=True)
        if step == STEPS[-1]:
            break
        idx = torch.tensor(rng.integers(0, len(seqs), batch), device=device)
        xb = Xt[idx]
        y, _ = model(xb[:, :-1])
        loss = nll(model, y, xb[:, 1:], mask_all[idx])
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if step % 200 == 0:
            meta["log"].append({"step": step, "loss": float(loss), "s": round(time.time() - t0, 1)})
            print(f"step {step} loss {float(loss):.3f}", flush=True)
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"done in {time.time() - t0:.0f}s", flush=True)


def embed():
    from metalesionlab.plato import DINO_MODEL, Embedder, ink_crop, render_strokes

    folder = LIFESPAN_DIR / "sketch" / "samples"
    emb = None
    for f in sorted(folder.glob("step*_t*.json")):
        out = LIFESPAN_DIR / "embeddings" / "sketch" / f"{f.stem}.npz"
        if out.exists():
            continue
        drawings = [d for d in json.loads(f.read_text()) if d]
        emb = emb or Embedder(DINO_MODEL)
        vecs = emb([ink_crop(render_strokes(d)) for d in drawings])
        out.parent.mkdir(parents=True, exist_ok=True)
        np.savez(out, n_empty=N_SAMPLES - len(drawings), model=DINO_MODEL, **vecs)
        print(f"{f.stem}: {len(drawings)} drawings", flush=True)
    # the training drawings themselves (a random 200), the "parents" the model learned from
    out = LIFESPAN_DIR / "embeddings" / "sketch" / "train_sample.npz"
    if not out.exists():
        lines = (LIFESPAN_DIR / "sketch" / "train_chair.ndjson").read_text().splitlines()
        pick = np.random.default_rng(20261027).choice(len(lines), 200, replace=False)
        emb = emb or Embedder(DINO_MODEL)
        vecs = emb([ink_crop(render_strokes(json.loads(lines[i]))) for i in pick])
        np.savez(out, model=DINO_MODEL, **vecs)
        print("train sample: 200 drawings")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--n", type=int, default=20000)
    t = sub.add_parser("train")
    t.add_argument("--data", type=Path, required=True)
    t.add_argument("--out", type=Path, required=True)
    t.add_argument("--device", default="cuda")
    sub.add_parser("embed")
    args = ap.parse_args()
    if args.cmd == "fetch":
        fetch(args.n)
    elif args.cmd == "train":
        train(args.data, args.out, args.device)
    else:
        embed()


if __name__ == "__main__":
    main()
