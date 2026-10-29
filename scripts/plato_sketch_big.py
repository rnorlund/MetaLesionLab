"""Watch an AI learn what a chair is, with a stronger learner: a larger Sketch-RNN trained on all the chairs.

The small model (scripts/plato_lifespan_sketch.py: LSTM 512, 20,000 chairs, 25,600 steps) ends with chairs that
DINOv2 calls chairs but people find poor. This one is the same architecture, made larger and trained longer on
far more chairs: the small model's decoder (plato_lifespan_sketch.build: an LSTM over stroke-5 points, dropout
0.1, a 20-component bivariate Gaussian mixture and 3 pen states, the same loss) with 2,048 units instead of 512,
trained on every recognized Quick, Draw! chair except the 200 adult reference chairs, for 102,400 steps, with
Ha & Eck's (2017) random scaling of the drawings (+/-15%) and a learning-rate floor of 1e-5.

Ha & Eck's layer-normalized LSTM with recurrent dropout was tried first and dropped: without a fused kernel it
ran about 20 times slower per step in PyTorch (0.9 s against 45 ms at 2,048 units). Magenta's published Sketch-RNN
chair models are plain LSTMs too.

Sampling is the small model's: noise fixed per seed (plato_sketch.make_noise), so at every checkpoint the same
random starts are drawn and only the weights differ.

Usage (on the GPU server; PYTHONPATH must reach metalesionlab and a scipy):
  python scripts/plato_sketch_big.py fetch --out data/train_chair_all.ndjson
  python scripts/plato_sketch_big.py bench --data data/train_chair_all.ndjson
  python scripts/plato_sketch_big.py train --seed 1 --data data/train_chair_all.ndjson --out runs/big_s1
  python scripts/plato_sketch_seeds.py embed --run runs/big_s1
  python scripts/plato_sketch_seeds.py ref --concept chair --data data/train_chair_all.ndjson --out ref_big

Files per run, as for the small model: samples/step<k>_t<T>.json, ckpt/step<k>.pt, meta.json.
Quick, Draw!: Google Creative Lab, CC BY 4.0.
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

from metalesionlab.plato_sketch import BIG, make_noise, sample_name  # noqa: E402
from plato_lifespan_sketch import MAX_LEN, build, nll  # noqa: E402
from plato_sketch_seeds import fetch, load_training, sample_fixed  # noqa: E402


def tensors(data: Path, device: str):
    """All usable drawings (at most MAX_LEN - 1 points) as a padded stroke-5 tensor, offsets divided by their
    standard deviation, exactly as the small model prepares its 20,000."""
    import torch

    lines, seqs, used = load_training(data)
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
    Xt = torch.tensor(X, device=device)
    mask = (torch.arange(MAX_LEN, device=device)[None] < torch.tensor(L, device=device)[:, None]).float()
    return lines, seqs, scale, Xt, mask


def batch_at(Xt, mask, idx, gen):
    """A training batch with Ha & Eck's random scaling: x and y offsets each scaled by U(0.85, 1.15) per drawing."""
    import torch

    xb = Xt[idx].clone()
    s = 1 + BIG["random_scale"] * (2 * torch.rand(len(idx), 1, 2, device=xb.device, generator=gen) - 1)
    xb[:, :, :2] *= s
    return xb, mask[idx]


def lr_at(step: int, lr: float) -> float:
    """The small model's schedule (x 0.9999 per step) with Ha & Eck's floor."""
    return max(BIG["min_lr"], lr * BIG["lr_decay"] ** step)


def train(seed: int, data: Path, out: Path, device: str, steps: list[int], batch: int = 100, lr: float = 1e-3):
    import torch

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    gen = torch.Generator(device=device).manual_seed(seed)
    lines, seqs, scale, Xt, mask = tensors(data, device)
    print(f"seed {seed}: {len(seqs)} of {len(lines)} drawings, offset scale {scale:.2f}, {device}", flush=True)
    model = build(device, hidden=BIG["hidden"])
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda k: lr_at(k, lr) / lr)
    for sub in ("samples", "ckpt"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    noise = make_noise(seed, BIG["n_samples"], MAX_LEN)
    meta = {"model": f"Sketch-RNN-style decoder (LSTM {BIG['hidden']}, 20 mixtures), unconditional; "
                     "scripts/plato_sketch_big.py", "concept": "chair", "seed": seed, "n_lines": len(lines),
            "n_train": len(seqs), "scale": scale, "batch": batch, "lr": lr, "min_lr": BIG["min_lr"],
            "random_scale": BIG["random_scale"], "steps": steps, "temps": BIG["temps"], "n_samples": BIG["n_samples"],
            "device": device, "params": sum(p.numel() for p in model.parameters()),
            "data": "Google Quick, Draw! chair drawings (CC BY 4.0), all recognized after the 200 reference drawings",
            "log": [], "sample_s": 0.0}
    t0 = time.time()
    for step in range(steps[-1] + 1):
        if step in steps:
            ts = time.time()
            for temp in BIG["temps"]:
                d = sample_fixed(model, noise, temp, scale, device)
                (out / "samples" / f"{sample_name(step, temp)}.json").write_text(json.dumps(d))
            torch.save(model.state_dict(), out / "ckpt" / f"step{step}.pt")
            meta["sample_s"] += time.time() - ts
            print(f"step {step}: sampled ({time.time() - t0:.0f}s)", flush=True)
            (out / "meta.json").write_text(json.dumps(meta, indent=1))
        if step == steps[-1]:
            break
        idx = torch.tensor(rng.integers(0, len(seqs), batch), device=device)
        xb, mb = batch_at(Xt, mask, idx, gen)
        y, _ = model(xb[:, :-1])
        loss = nll(model, y, xb[:, 1:], mb)
        if not torch.isfinite(loss):
            meta["failed"] = f"loss {float(loss)} at step {step}"
            (out / "meta.json").write_text(json.dumps(meta, indent=1))
            raise SystemExit(f"non-finite loss at step {step}")
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if step % 200 == 0:
            meta["log"].append({"step": step, "loss": loss.item(), "s": round(time.time() - t0, 1)})
            if step % 3200 == 0:
                print(f"step {step} loss {loss.item():.3f} ({time.time() - t0:.0f}s)", flush=True)
    meta["seconds"] = round(time.time() - t0, 1)
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"done in {meta['seconds']:.0f}s", flush=True)


def bench(data: Path, device: str, hidden: int, n: int = 30):
    """Milliseconds per training step at this size."""
    import torch

    _, seqs, _, Xt, mask = tensors(data, device)
    model = build(device, hidden=hidden)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    gen = torch.Generator(device=device).manual_seed(0)
    rng = np.random.default_rng(0)
    for k in range(n + 5):
        if k == 5:
            torch.cuda.synchronize()
            t0 = time.time()
        idx = torch.tensor(rng.integers(0, len(seqs), 100), device=device)
        xb, mb = batch_at(Xt, mask, idx, gen)
        y, _ = model(xb[:, :-1])
        loss = nll(model, y, xb[:, 1:], mb)
        opt.zero_grad()
        loss.backward()
        opt.step()
    torch.cuda.synchronize()
    ms = (time.time() - t0) / n * 1000
    print(f"hidden {hidden}: {ms:.1f} ms per step, {sum(p.numel() for p in model.parameters()) / 1e6:.1f}M parameters, "
          f"loss {loss.item():.3f}, {len(seqs)} drawings", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--out", type=Path, required=True)
    b = sub.add_parser("bench")
    b.add_argument("--data", type=Path, required=True)
    b.add_argument("--hidden", type=int, default=BIG["hidden"])
    b.add_argument("--device", default="cuda")
    t = sub.add_parser("train")
    t.add_argument("--seed", type=int, required=True)
    t.add_argument("--data", type=Path, required=True)
    t.add_argument("--out", type=Path, required=True)
    t.add_argument("--device", default="cuda")
    args = ap.parse_args()
    if args.cmd == "fetch":
        fetch("chair", 10 ** 7, args.out)
    elif args.cmd == "bench":
        bench(args.data, args.device, args.hidden)
    else:
        train(args.seed, args.data, args.out, args.device, BIG["steps"])


if __name__ == "__main__":
    main()
