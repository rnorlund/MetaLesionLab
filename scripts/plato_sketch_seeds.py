"""Watch an AI learn what a chair is: train the Mac run's sketch model with many seeds, draw, render and embed.

The model, loss and stroke conversion are imported from scripts/plato_lifespan_sketch.py (the Mac run), so the
runs are comparable. What is new (docs/plato_sketch_plan.md): 20 log-spaced checkpoints, three temperatures,
200 drawings each, and sampling noise that is fixed per seed (inverse-CDF sampling; the training random-number
generator is never touched by sampling).

Usage (on the GPU server; PYTHONPATH must reach metalesionlab and a scipy):
  python scripts/plato_sketch_seeds.py fetch --concept cat --out data/train_cat.ndjson
  python scripts/plato_sketch_seeds.py train --concept chair --seed 1 --data data/train_chair.ndjson --out runs/chair_s1
  python scripts/plato_sketch_seeds.py embed --run runs/chair_s1
  python scripts/plato_sketch_seeds.py ref --concept chair --data data/train_chair.ndjson --out ref

Files per run: samples/step<k>_t<T>.json (drawings in Quick, Draw! [[xs], [ys]] format, None for a single point),
ckpt/step<k>.pt, meta.json, emb/step<k>_t<T>.npz (cls float32, patch_mean float16, strokes, points).
Quick, Draw!: Google Creative Lab, CC BY 4.0.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402

from metalesionlab.plato_sketch import (N_REF, N_SAMPLES, REF_SEED, STEPS, TEMPS, categorical_from_uniform_torch,  # noqa: E402
                                        make_noise, offset_from_noise, sample_name, stroke_stats)
from plato_lifespan_sketch import MAX_LEN, build, from_stroke5, nll, to_stroke5  # noqa: E402


# ---------- data ----------

def fetch(concept: str, n: int, out: Path):
    """The first n recognized drawings after the 200 used as the adult reference (plato.stream_quickdraw order)."""
    import httpx

    from metalesionlab.plato import QUICKDRAW_URL

    out.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(6):
        kept, seen_rec = [], 0
        try:
            with httpx.stream("GET", QUICKDRAW_URL.format(category=concept.replace(" ", "%20")), timeout=120) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    if rec.get("recognized") is True and rec.get("word") == concept:
                        seen_rec += 1
                        if seen_rec > 200:
                            kept.append(rec["drawing"])
                    if len(kept) >= n:
                        break
            break
        except Exception as e:  # network hiccup: retry the stream from the start
            print(f"attempt {attempt} failed ({type(e).__name__}); retrying", flush=True)
            time.sleep(5 * 2 ** attempt)
    out.write_text("\n".join(json.dumps(d) for d in kept))
    print(f"wrote {len(kept)} {concept} drawings to {out}", flush=True)


def load_training(data: Path):
    """The drawings the model learns from (stroke-5, at most MAX_LEN - 1 points) and their line numbers."""
    lines = data.read_text().splitlines()
    seqs, used = [], []
    for i, line in enumerate(lines):
        s = to_stroke5(json.loads(line))
        if s is not None:
            seqs.append(s)
            used.append(i)
    return lines, seqs, used


# ---------- sampling with fixed noise ----------

def sample_fixed(model, noise: dict, temp: float, scale: float, device: str, max_len: int = MAX_LEN) -> list:
    """Drawings from the model given the per-drawing noise (see plato_sketch.make_noise)."""
    import torch

    t = {k: torch.tensor(v, device=device, dtype=torch.float32) for k, v in noise.items()}
    n = t["e1"].shape[0]
    model.eval()
    out = np.zeros((n, max_len, 5))
    with torch.no_grad():
        x = torch.zeros(n, 1, 5, device=device)
        x[:, 0, 2] = 1  # start token: pen down at the origin
        state = None
        done = torch.zeros(n, dtype=torch.bool, device=device)
        for i in range(max_len):
            y, state = model(x, state)
            logpi, mx, my, sx, sy, rho, pen = model.params(y[:, -1])
            k = categorical_from_uniform_torch(logpi, t["u_mix"][:, i], temp)[:, None]
            dx, dy = offset_from_noise(mx.gather(1, k)[:, 0], my.gather(1, k)[:, 0], sx.gather(1, k)[:, 0],
                                       sy.gather(1, k)[:, 0], rho.gather(1, k)[:, 0], t["e1"][:, i], t["e2"][:, i], temp)
            p = categorical_from_uniform_torch(pen, t["u_pen"][:, i], temp)
            step = torch.zeros(n, 5, device=device)
            step[:, 0], step[:, 1] = dx, dy
            step[torch.arange(n, device=device), 2 + p] = 1
            out[:, i] = step.cpu().numpy()
            done |= p == 2
            if bool(done.all()):
                break
            x = step[:, None]
    model.train()
    drawings = []
    for s5 in out:
        s5 = s5.copy()
        s5[:, :2] *= scale
        d = from_stroke5(s5)
        drawings.append(d if d else None)
    return drawings


def train(concept: str, seed: int, data: Path, out: Path, device: str, batch: int = 100, lr: float = 1e-3):
    """The Mac run's training loop (same model, optimizer, schedule, batch and length), with this seed."""
    import torch

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    lines, seqs, _ = load_training(data)
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
    print(f"{concept} seed {seed}: {len(seqs)} of {len(lines)} drawings, offset scale {scale:.2f}, {device}", flush=True)
    model = build(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.ExponentialLR(opt, 0.9999)
    for sub in ("samples", "ckpt"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    noise = make_noise(seed, N_SAMPLES, MAX_LEN)
    meta = {"model": "Sketch-RNN-style decoder (LSTM 512, 20 mixtures), unconditional; scripts/plato_lifespan_sketch.py",
            "concept": concept, "seed": seed, "n_lines": len(lines), "n_train": len(seqs), "scale": scale,
            "batch": batch, "lr": lr, "steps": STEPS, "temps": TEMPS, "n_samples": N_SAMPLES, "device": device,
            "data": f"Google Quick, Draw! {concept} drawings (CC BY 4.0), recognized, after the 200 reference drawings",
            "log": [], "sample_s": 0.0}
    t0 = time.time()
    Xt = torch.tensor(X, device=device)
    mask_all = (torch.arange(MAX_LEN, device=device)[None] < torch.tensor(L, device=device)[:, None]).float()
    for step in range(STEPS[-1] + 1):
        if step in STEPS:
            ts = time.time()
            for temp in TEMPS:
                d = sample_fixed(model, noise, temp, scale, device)
                (out / "samples" / f"{sample_name(step, temp)}.json").write_text(json.dumps(d))
            torch.save(model.state_dict(), out / "ckpt" / f"step{step}.pt")
            meta["sample_s"] += time.time() - ts
            print(f"step {step}: sampled ({time.time() - t0:.0f}s)", flush=True)
        if step == STEPS[-1]:
            break
        idx = torch.tensor(rng.integers(0, len(seqs), batch), device=device)
        xb = Xt[idx]
        y, _ = model(xb[:, :-1])
        loss = nll(model, y, xb[:, 1:], mask_all[idx])
        if not torch.isfinite(loss):
            meta["failed"] = f"loss {float(loss)} at step {step}"
            (out / "meta.json").write_text(json.dumps(meta, indent=1))
            raise SystemExit(f"non-finite loss at step {step}")
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if step % 200 == 0:
            meta["log"].append({"step": step, "loss": float(loss), "s": round(time.time() - t0, 1)})
            if step % 3200 == 0:
                print(f"step {step} loss {float(loss):.3f}", flush=True)
    meta["seconds"] = round(time.time() - t0, 1)
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"done in {meta['seconds']:.0f}s", flush=True)


# ---------- rendering and embedding ----------

def _render(d):
    from metalesionlab.plato import ink_crop, render_strokes

    return np.asarray(ink_crop(render_strokes(d)))


def render_all(drawings: list, workers: int) -> list:
    from multiprocessing import get_context

    from PIL import Image

    with get_context("fork").Pool(workers) as pool:
        arrs = pool.map(_render, drawings, chunksize=8)
    return [Image.fromarray(a) for a in arrs]


_EMB = None


def embedder(device: str):
    global _EMB
    if _EMB is None:
        from metalesionlab.plato import DINO_MODEL, Embedder

        _EMB = Embedder(DINO_MODEL, device=device)
    return _EMB


def embed_set(drawings: list, out: Path, device: str, workers: int, **extra):
    kept = [d for d in drawings if d]
    vecs = embedder(device)(render_all(kept, workers), batch=100)
    st = np.array([stroke_stats(d) for d in kept]).reshape(-1, 2)
    tmp = out.with_name(out.stem + f".tmp{os.getpid()}.npz")  # written whole, then renamed: never half a file
    np.savez(tmp, cls=vecs["cls"].astype(np.float32), patch_mean=vecs["patch_mean"].astype(np.float16),
             n_empty=len(drawings) - len(kept), strokes=st[:, 0], points=st[:, 1], **extra)
    os.replace(tmp, out)
    return len(kept)


def embed_run(run: Path, device: str, workers: int):
    (run / "emb").mkdir(exist_ok=True)
    t0 = time.time()
    for f in sorted((run / "samples").glob("step*_t*.json")):
        out = run / "emb" / f"{f.stem}.npz"
        if out.exists():  # resumable; two embedders on one run only duplicate work (writes are atomic)
            continue
        n = embed_set(json.loads(f.read_text()), out, device, workers)
        print(f"{run.name} {f.stem}: {n} drawings ({time.time() - t0:.0f}s)", flush=True)


def embed_ref(concept: str, data: Path, out: Path, device: str, workers: int):
    """The drawings it learned from: a fixed random 1,000 of the training drawings it used, rendered as they are
    and after the samples' stroke-5 round trip; for the chair also the Mac run's 200 (embedding check)."""
    out.mkdir(parents=True, exist_ok=True)
    lines, seqs, used = load_training(data)
    pick = np.sort(np.random.default_rng(REF_SEED).choice(len(used), N_REF, replace=False))
    raw = [json.loads(lines[used[i]]) for i in pick]
    rt = [from_stroke5(seqs[i]) for i in pick]
    n1 = embed_set(raw, out / f"{concept}_train{N_REF}.npz", device, workers, lines=np.array([used[i] for i in pick]))
    n2 = embed_set(rt, out / f"{concept}_train{N_REF}_roundtrip.npz", device, workers)
    print(f"{concept} reference: {n1} raw, {n2} round trip ({len(used)} of {len(lines)} used in training)", flush=True)
    if concept == "chair":  # the Mac run's train_sample: random 200 of all 20,000 lines, seed 20261027
        mac = np.random.default_rng(20261027).choice(len(lines), 200, replace=False)
        embed_set([json.loads(lines[i]) for i in mac], out / "chair_mac200_check.npz", device, workers)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--concept", required=True)
    f.add_argument("--n", type=int, default=20000)
    f.add_argument("--out", type=Path, required=True)
    t = sub.add_parser("train")
    t.add_argument("--concept", required=True)
    t.add_argument("--seed", type=int, required=True)
    t.add_argument("--data", type=Path, required=True)
    t.add_argument("--out", type=Path, required=True)
    t.add_argument("--device", default="cuda")
    e = sub.add_parser("embed")
    e.add_argument("--run", type=Path, nargs="+", required=True)
    e.add_argument("--device", default="cuda")
    e.add_argument("--workers", type=int, default=8)
    r = sub.add_parser("ref")
    r.add_argument("--concept", required=True)
    r.add_argument("--data", type=Path, required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--device", default="cuda")
    r.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    if args.cmd == "fetch":
        fetch(args.concept, args.n, args.out)
    elif args.cmd == "train":
        train(args.concept, args.seed, args.data, args.out, args.device)
    elif args.cmd == "embed":
        for run in args.run:
            embed_run(run, args.device, args.workers)
    else:
        embed_ref(args.concept, args.data, args.out, args.device, args.workers)


if __name__ == "__main__":
    main()
