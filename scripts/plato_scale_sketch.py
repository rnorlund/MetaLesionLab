"""An AI growing up, Arm A: the sketch model trained on nested subsets of people's chairs (docs/plato_scale_plan.md).

The model, loss, stroke conversion, fixed-noise sampler and embedder are the earlier runs' (imported from
scripts/plato_lifespan_sketch.py and scripts/plato_sketch_seeds.py), so only the amount of data differs. What is
new: nested random subsets (100 ... 20,000), a held-out loss at every checkpoint (for the best-checkpoint rule),
and temperatures 1.0 and 0.6.

Usage (on the GPU server; PYTHONPATH must reach metalesionlab and a scipy):
  python scripts/plato_scale_sketch.py heldout --out data/heldout_chair.ndjson
  python scripts/plato_scale_sketch.py train --size 100 --seed 1 --data data/train_chair.ndjson \
      --heldout data/heldout_chair.ndjson --out runs/n100_s1
  python scripts/plato_scale_sketch.py embed --run runs/n100_s1
  python scripts/plato_scale_sketch.py ref --data data/train_chair.ndjson --heldout data/heldout_chair.ndjson --out ref

Files per run: samples/step<k>_t<T>.json, ckpt/step<k>.pt, emb/step<k>_t<T>.npz, meta.json (subset line numbers,
training and held-out losses per checkpoint). ref/: DINOv2 embeddings of all 20,000 training chairs (line order)
and of the 1,000 held-out chairs. Quick, Draw!: Google Creative Lab, CC BY 4.0.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402

from metalesionlab.plato_scale import N_HELDOUT, N_TRAIN_LOSS, TEMPS_A, nested_subset  # noqa: E402
from metalesionlab.plato_sketch import N_SAMPLES, STEPS, make_noise, sample_name  # noqa: E402
from plato_lifespan_sketch import MAX_LEN, build, nll, to_stroke5  # noqa: E402
from plato_sketch_seeds import embed_run, embed_set, sample_fixed  # noqa: E402


def heldout(out: Path, skip: int = 20200, n: int = N_HELDOUT):
    """Recognized chairs 20,201 to 21,200 in file order: after the 200 reference chairs and the 20,000 training
    chairs, so no run ever trains on them."""
    import httpx

    from metalesionlab.plato import QUICKDRAW_URL

    out.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(6):
        kept, seen = [], 0
        try:
            with httpx.stream("GET", QUICKDRAW_URL.format(category="chair"), timeout=120) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    if rec.get("recognized") is True and rec.get("word") == "chair":
                        seen += 1
                        if seen > skip:
                            kept.append(rec["drawing"])
                    if len(kept) >= n:
                        break
            break
        except Exception as e:  # noqa: BLE001  network hiccup: retry the stream from the start
            print(f"attempt {attempt} failed ({type(e).__name__}); retrying", flush=True)
            time.sleep(5 * 2 ** attempt)
    out.write_text("\n".join(json.dumps(d) for d in kept))
    print(f"wrote {len(kept)} held-out chairs to {out}", flush=True)


def tensors(seqs, scale):
    X = np.zeros((len(seqs), MAX_LEN + 1, 5), np.float32)
    L = np.zeros(len(seqs), int)
    for i, s in enumerate(seqs):
        s = s.copy()
        s[:, :2] /= scale
        X[i, 0, 2] = 1  # start token
        X[i, 1:len(s) + 1] = s
        X[i, len(s) + 1:, 4] = 1  # padding: end state
        L[i] = len(s)
    return X, L


def eval_loss(model, X, L, device: str, batch: int = 500) -> float:
    """The training loss (scripts/plato_lifespan_sketch.nll), in eval mode, averaged over drawings in batches."""
    import torch

    model.eval()
    tot, n = 0.0, 0
    with torch.no_grad():
        for i in range(0, len(X), batch):
            xb = torch.tensor(X[i:i + batch], device=device)
            lb = torch.tensor(L[i:i + batch], device=device)
            mask = (torch.arange(MAX_LEN, device=device)[None] < lb[:, None]).float()
            y, _ = model(xb[:, :-1])
            tot += float(nll(model, y, xb[:, 1:], mask)) * len(xb)
            n += len(xb)
    model.train()
    return tot / n


def train(size: int, seed: int, data: Path, held: Path, out: Path, device: str, batch: int = 100, lr: float = 1e-3):
    """The earlier runs' training loop on this seed's nested subset of `size` chairs."""
    import torch

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    lines = data.read_text().splitlines()
    subset = nested_subset(seed, len(lines), size)
    seqs, used = [], []
    for i in subset:
        s = to_stroke5(json.loads(lines[i]))
        if s is not None:
            seqs.append(s)
            used.append(int(i))
    scale = float(np.std(np.concatenate([s[:-1, :2] for s in seqs]).ravel()))
    X, L = tensors(seqs, scale)
    held_seqs = [s for s in (to_stroke5(json.loads(x)) for x in held.read_text().splitlines()) if s is not None]
    Xh, Lh = tensors(held_seqs, scale)
    pick = np.sort(np.random.default_rng([seed, 11]).choice(len(seqs), min(N_TRAIN_LOSS, len(seqs)), replace=False))
    Xtr, Ltr = X[pick], L[pick]
    print(f"n{size} seed {seed}: {len(seqs)} of {size} chairs, scale {scale:.2f}, {len(held_seqs)} held out, {device}",
          flush=True)
    model = build(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.ExponentialLR(opt, 0.9999)
    for sub in ("samples", "ckpt"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    noise = make_noise(seed, N_SAMPLES, MAX_LEN)
    meta = {"model": "Sketch-RNN-style decoder (LSTM 512, 20 mixtures), unconditional; scripts/plato_lifespan_sketch.py",
            "size": size, "seed": seed, "n_train": len(seqs), "subset_lines": used, "scale": scale, "batch": batch,
            "lr": lr, "steps": STEPS, "temps": TEMPS_A, "n_samples": N_SAMPLES, "device": device,
            "n_heldout": len(held_seqs), "heldout_loss": {}, "train_loss_eval": {}, "log": [],
            "data": "Google Quick, Draw! chairs (CC BY 4.0), recognized, after the 200 reference drawings"}
    t0 = time.time()
    Xt = torch.tensor(X, device=device)
    mask_all = (torch.arange(MAX_LEN, device=device)[None] < torch.tensor(L, device=device)[:, None]).float()
    for step in range(STEPS[-1] + 1):
        if step in STEPS:
            meta["heldout_loss"][str(step)] = eval_loss(model, Xh, Lh, device)
            meta["train_loss_eval"][str(step)] = eval_loss(model, Xtr, Ltr, device)
            for temp in TEMPS_A:
                d = sample_fixed(model, noise, temp, scale, device)
                (out / "samples" / f"{sample_name(step, temp)}.json").write_text(json.dumps(d))
            torch.save(model.state_dict(), out / "ckpt" / f"step{step}.pt")
            print(f"step {step}: held-out {meta['heldout_loss'][str(step)]:.3f} train {meta['train_loss_eval'][str(step)]:.3f}"
                  f" ({time.time() - t0:.0f}s)", flush=True)
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
    meta["seconds"] = round(time.time() - t0, 1)
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"done in {meta['seconds']:.0f}s", flush=True)


def ref(data: Path, held: Path, out: Path, device: str, workers: int):
    """DINOv2 embeddings of every training chair (in line order) and of the held-out chairs, rendered as they are."""
    out.mkdir(parents=True, exist_ok=True)
    lines = data.read_text().splitlines()
    if not (out / "train_all.npz").exists():
        n = embed_set([json.loads(x) for x in lines], out / "train_all.npz", device, workers)
        print(f"training chairs: {n} of {len(lines)}", flush=True)
    if not (out / "heldout.npz").exists():
        hl = held.read_text().splitlines()
        n = embed_set([json.loads(x) for x in hl], out / "heldout.npz", device, workers)
        print(f"held-out chairs: {n} of {len(hl)}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("heldout")
    h.add_argument("--out", type=Path, required=True)
    t = sub.add_parser("train")
    t.add_argument("--size", type=int, required=True)
    t.add_argument("--seed", type=int, required=True)
    t.add_argument("--data", type=Path, required=True)
    t.add_argument("--heldout", type=Path, required=True)
    t.add_argument("--out", type=Path, required=True)
    t.add_argument("--device", default="cuda")
    e = sub.add_parser("embed")
    e.add_argument("--run", type=Path, nargs="+", required=True)
    e.add_argument("--device", default="cuda")
    e.add_argument("--workers", type=int, default=8)
    r = sub.add_parser("ref")
    r.add_argument("--data", type=Path, required=True)
    r.add_argument("--heldout", type=Path, required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--device", default="cuda")
    r.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    if a.cmd == "heldout":
        heldout(a.out)
    elif a.cmd == "train":
        train(a.size, a.seed, a.data, a.heldout, a.out, a.device)
    elif a.cmd == "embed":
        for run in a.run:
            embed_run(run, a.device, a.workers)
    else:
        ref(a.data, a.heldout, a.out, a.device, a.workers)


if __name__ == "__main__":
    main()
