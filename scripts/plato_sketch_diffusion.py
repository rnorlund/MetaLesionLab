"""Watch an AI learn what a chair is, pilot (b): a small pixel diffusion model trained from scratch on chairs.

The chairs are rendered exactly as the site renders people's drawings (plato.render_strokes, 256 px, 3 px lines,
then plato.ink_crop), shrunk to SIDE x SIDE grey pixels, and a small UNet learns to denoise them (v-prediction,
cosine noise schedule). At log-spaced checkpoints it draws 200 chairs by deterministic DDIM sampling (eta = 0)
from noise that is fixed per seed, so across checkpoints only the weights differ and each tile is "the same chair"
taking shape. Weights for sampling are an exponential moving average, as usual for diffusion models.

Usage (on the GPU server; PYTHONPATH must reach metalesionlab and a scipy):
  python scripts/plato_sketch_diffusion.py raster --data data/train_chair_all.ndjson --out data/chair_all_64.npz
  python scripts/plato_sketch_diffusion.py bench --images data/chair_all_64.npz
  python scripts/plato_sketch_diffusion.py train --seed 1 --images data/chair_all_64.npz --out runs/diff_s1
  python scripts/plato_sketch_diffusion.py embed --run runs/diff_s1
  python scripts/plato_sketch_diffusion.py ref --images data/chair_all_64.npz --out ref_diff

Files per run: samples/step<k>.npz (uint8 images, 255 = paper), ckpt/step<k>.pt (EMA weights), meta.json,
emb/step<k>.npz. Quick, Draw!: Google Creative Lab, CC BY 4.0.
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402

from metalesionlab.plato_sketch import DIFF, N_REF, REF_SEED  # noqa: E402


# ---------- data ----------

def _raster(args):
    from PIL import Image

    from metalesionlab.plato import ink_crop, render_strokes

    line, side = args
    im = ink_crop(render_strokes(json.loads(line))).convert("L")
    return np.asarray(im.resize((side, side), Image.LANCZOS), np.uint8)


def raster(data: Path, out: Path, side: int, workers: int):
    """Every drawing the Sketch-RNN learns from (the same filter: at most 199 points), as the site renders it."""
    from multiprocessing import get_context

    from plato_sketch_seeds import load_training

    lines, _, used = load_training(data)
    t0 = time.time()
    with get_context("fork").Pool(workers) as pool:
        imgs = pool.map(_raster, [(lines[i], side) for i in used], chunksize=256)
    np.savez(out, images=np.stack(imgs), lines=np.array(used), side=side)
    print(f"{len(imgs)} chairs at {side} px in {time.time() - t0:.0f}s -> {out}", flush=True)


def to_unit(u8):
    return u8.float() / 127.5 - 1  # paper +1, ink -1


def to_u8(x):
    return ((x.clamp(-1, 1) + 1) * 127.5).round().to("cpu", dtype=__import__("torch").uint8).numpy()


# ---------- model ----------

def build_unet(side: int, base: int = DIFF["base"], mults=None, attn_res=(16, 8), drop: float = 0.1):
    """A small DDPM-style UNet (Ho et al. 2020): two residual blocks per level, self-attention at 16 and 8 px."""
    import torch
    import torch.nn.functional as F
    from torch import nn

    mults = mults or ((1, 2, 2, 4) if side <= 64 else (1, 1, 2, 2, 4))
    tdim = 4 * base

    class Res(nn.Module):
        def __init__(self, cin, cout, attn):
            super().__init__()
            self.n1, self.c1 = nn.GroupNorm(32, cin), nn.Conv2d(cin, cout, 3, padding=1)
            self.t = nn.Linear(tdim, cout)
            self.n2, self.d, self.c2 = nn.GroupNorm(32, cout), nn.Dropout(drop), nn.Conv2d(cout, cout, 3, padding=1)
            nn.init.zeros_(self.c2.weight)
            self.skip = nn.Conv2d(cin, cout, 1) if cin != cout else nn.Identity()
            self.attn = attn
            if attn:
                self.na, self.qkv, self.o = nn.GroupNorm(32, cout), nn.Conv2d(cout, 3 * cout, 1), nn.Conv2d(cout, cout, 1)
                nn.init.zeros_(self.o.weight)

        def forward(self, x, te):
            h = self.c1(F.silu(self.n1(x))) + self.t(F.silu(te))[:, :, None, None]
            h = self.skip(x) + self.c2(self.d(F.silu(self.n2(h))))
            if self.attn:
                b, c, hh, ww = h.shape
                q, k, v = self.qkv(self.na(h)).reshape(b, 3, 4, c // 4, hh * ww).transpose(-1, -2).unbind(1)
                y = F.scaled_dot_product_attention(q, k, v).transpose(-1, -2).reshape(b, c, hh, ww)
                h = h + self.o(y)
            return h

    class Down(nn.Module):
        def __init__(self, c):
            super().__init__()
            self.c = nn.Conv2d(c, c, 3, stride=2, padding=1)

        def forward(self, x, te):
            return self.c(x)

    class Up(nn.Module):
        def __init__(self, c):
            super().__init__()
            self.c = nn.Conv2d(c, c, 3, padding=1)

        def forward(self, x, te):
            return self.c(F.interpolate(x, scale_factor=2, mode="nearest"))

    class UNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.base = base
            self.temb = nn.Sequential(nn.Linear(base, tdim), nn.SiLU(), nn.Linear(tdim, tdim))
            self.inp = nn.Conv2d(1, base, 3, padding=1)
            self.down, chans, c, res = nn.ModuleList(), [base], base, side
            for i, m in enumerate(mults):
                for _ in range(2):
                    self.down.append(Res(c, base * m, res in attn_res))
                    c = base * m
                    chans.append(c)
                if i < len(mults) - 1:
                    self.down.append(Down(c))
                    chans.append(c)
                    res //= 2
            self.mid = nn.ModuleList([Res(c, c, True), Res(c, c, False)])
            self.up = nn.ModuleList()
            for i, m in reversed(list(enumerate(mults))):
                for _ in range(3):
                    self.up.append(Res(c + chans.pop(), base * m, res in attn_res))
                    c = base * m
                if i > 0:
                    self.up.append(Up(c))
                    res *= 2
            self.out = nn.Sequential(nn.GroupNorm(32, c), nn.SiLU(), nn.Conv2d(c, 1, 3, padding=1))
            nn.init.zeros_(self.out[-1].weight)
            nn.init.zeros_(self.out[-1].bias)

        def forward(self, x, t):
            half = self.base // 2
            f = torch.exp(-math.log(10000) * torch.arange(half, device=x.device) / half)
            a = (t * 1000)[:, None] * f[None]
            te = self.temb(torch.cat([a.sin(), a.cos()], 1))
            hs = [self.inp(x)]
            for blk in self.down:
                hs.append(blk(hs[-1], te))
            h = hs[-1]
            for blk in self.mid:
                h = blk(h, te)
            for blk in self.up:
                h = blk(h, te) if isinstance(blk, Up) else blk(torch.cat([h, hs.pop()], 1), te)
            return self.out(h)

    return UNet()


def alpha_sigma(t):
    """Cosine schedule (Nichol & Dhariwal 2021) in continuous time: x_t = a x0 + s eps."""
    import torch

    s = 0.008
    f = torch.cos((t + s) / (1 + s) * math.pi / 2) / math.cos(s / (1 + s) * math.pi / 2)
    a = f.clamp(0, 1)
    return a, torch.sqrt((1 - a ** 2).clamp(min=0))


def make_image_noise(seed: int, n: int, side: int) -> np.ndarray:
    """The starting noise of one seed's n drawings: the same at every checkpoint (own generator, never training's)."""
    return np.random.default_rng([seed, 5, 7]).standard_normal((n, 1, side, side)).astype(np.float32)


def ddim(model, noise, steps: int, batch: int = 100):
    """Deterministic DDIM (eta = 0) with v-prediction: the same noise and weights always give the same picture."""
    import torch

    out = []
    ts = torch.linspace(1, 0, steps + 1, device=noise.device)
    with torch.no_grad(), torch.autocast("cuda", torch.bfloat16, enabled=noise.is_cuda):
        for i in range(0, len(noise), batch):
            x = noise[i:i + batch]
            for k in range(steps):
                t = ts[k].expand(len(x))
                a, s = (v[:, None, None, None] for v in alpha_sigma(t))
                v = model(x, t).float()
                x0 = (a * x - s * v).clamp(-1, 1)
                eps = s * x + a * v
                an, sn = (u[:, None, None, None] for u in alpha_sigma(ts[k + 1].expand(len(x))))
                x = an * x0 + sn * eps
            out.append(x)
    return torch.cat(out)


# ---------- training ----------

def train(seed: int, images: Path, out: Path, device: str, steps: list[int]):
    import copy

    import torch

    torch.manual_seed(seed)
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    z = np.load(images)
    X = torch.tensor(z["images"], device=device)
    side = int(z["side"])
    gen = torch.Generator(device=device).manual_seed(seed)
    model = build_unet(side).to(device)
    ema = copy.deepcopy(model).eval().requires_grad_(False)
    fast = torch.compile(model)
    opt = torch.optim.AdamW(model.parameters(), lr=DIFF["lr"], weight_decay=0.0)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda k: min(1.0, (k + 1) / DIFF["warmup"]))
    for sub in ("samples", "ckpt"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    noise = torch.tensor(make_image_noise(seed, DIFF["n_samples"], side), device=device)
    meta = {"model": f"pixel diffusion UNet (base {DIFF['base']}, v-prediction, cosine schedule), {side} px; "
                     "scripts/plato_sketch_diffusion.py", "concept": "chair", "seed": seed, "n_train": int(len(X)),
            "side": side, "batch": DIFF["batch"], "lr": DIFF["lr"], "steps": steps, "ddim_steps": DIFF["ddim_steps"],
            "n_samples": DIFF["n_samples"], "device": device, "params": sum(p.numel() for p in model.parameters()),
            "data": "Google Quick, Draw! chair drawings (CC BY 4.0), all recognized after the 200 reference "
                    "drawings, rendered as the site renders people's drawings", "log": [], "sample_s": 0.0}
    t0 = time.time()
    for step in range(steps[-1] + 1):
        if step in steps:
            ts = time.time()
            imgs = to_u8(ddim(ema, noise, DIFF["ddim_steps"]))[:, 0]
            np.savez_compressed(out / "samples" / f"step{step}.npz", images=imgs)
            torch.save(ema.state_dict(), out / "ckpt" / f"step{step}.pt")
            meta["sample_s"] += time.time() - ts
            print(f"step {step}: sampled ({time.time() - t0:.0f}s)", flush=True)
            (out / "meta.json").write_text(json.dumps(meta, indent=1))
        if step == steps[-1]:
            break
        idx = torch.randint(0, len(X), (DIFF["batch"],), device=device, generator=gen)
        x0 = to_unit(X[idx])[:, None]
        t = torch.rand(len(idx), device=device, generator=gen)
        eps = torch.randn(x0.shape, device=device, generator=gen)
        a, s = (v[:, None, None, None] for v in alpha_sigma(t))
        with torch.autocast("cuda", torch.bfloat16, enabled=device == "cuda"):
            pred = fast(a * x0 + s * eps, t).float()
        loss = ((pred - (a * eps - s * x0)) ** 2).mean()
        if not torch.isfinite(loss):
            meta["failed"] = f"loss {float(loss)} at step {step}"
            (out / "meta.json").write_text(json.dumps(meta, indent=1))
            raise SystemExit(f"non-finite loss at step {step}")
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        with torch.no_grad():  # EMA with warm-up, so early checkpoints show early weights
            d = min(DIFF["ema"], (1 + step) / (10 + step))
            for pe, pm in zip(ema.parameters(), model.parameters()):
                pe.lerp_(pm, 1 - d)
        if step % 200 == 0:
            meta["log"].append({"step": step, "loss": float(loss), "s": round(time.time() - t0, 1)})
            if step % 3200 == 0:
                print(f"step {step} loss {float(loss):.4f} ({time.time() - t0:.0f}s)", flush=True)
    meta["seconds"] = round(time.time() - t0, 1)
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"done in {meta['seconds']:.0f}s", flush=True)


def bench(images: Path, device: str, n: int = 40):
    import torch

    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    z = np.load(images)
    X = torch.tensor(z["images"][:5000], device=device)
    side = int(z["side"])
    model = build_unet(side).to(device)
    fast = torch.compile(model)
    opt = torch.optim.AdamW(model.parameters(), lr=DIFF["lr"])
    for k in range(n + 10):
        if k == 10:
            torch.cuda.synchronize()
            t0 = time.time()
        x0 = to_unit(X[torch.randint(0, len(X), (DIFF["batch"],), device=device)])[:, None]
        t = torch.rand(len(x0), device=device)
        eps = torch.randn_like(x0)
        a, s = (v[:, None, None, None] for v in alpha_sigma(t))
        with torch.autocast("cuda", torch.bfloat16):
            pred = fast(a * x0 + s * eps, t).float()
        loss = ((pred - (a * eps - s * x0)) ** 2).mean()
        opt.zero_grad()
        loss.backward()
        opt.step()
    torch.cuda.synchronize()
    ms = (time.time() - t0) / n * 1000
    ts = time.time()
    ddim(model.eval(), torch.randn(200, 1, side, side, device=device), DIFF["ddim_steps"])
    torch.cuda.synchronize()
    print(f"{side} px: {ms:.1f} ms per step (batch {DIFF['batch']}), {sum(p.numel() for p in model.parameters()) / 1e6:.1f}M "
          f"parameters; 200 samples in {time.time() - ts:.1f}s", flush=True)


# ---------- measuring ----------

def _prep(a):
    """A model-sized picture back to the measuring size (256 px), then ink-cropped as the pipeline does."""
    from PIL import Image

    from metalesionlab.plato import ink_crop

    return np.asarray(ink_crop(Image.fromarray(a).resize((256, 256), Image.LANCZOS).convert("RGB")))


def has_ink(a: np.ndarray, threshold: int = 200) -> bool:
    """A picture with no pixel darker than the crop threshold is blank (the counterpart of a single-point drawing)."""
    return bool((a < threshold).any())


def embed_images(imgs: np.ndarray, out: Path, device: str, workers: int, **extra):
    from multiprocessing import get_context

    from PIL import Image

    from plato_sketch_seeds import embedder

    kept = [a for a in imgs if has_ink(a)]
    with get_context("fork").Pool(workers) as pool:
        arrs = pool.map(_prep, kept, chunksize=16)
    vecs = embedder(device)([Image.fromarray(a) for a in arrs], batch=100)
    tmp = out.with_name(out.stem + f".tmp{os.getpid()}.npz")
    np.savez(tmp, cls=vecs["cls"].astype(np.float32), patch_mean=vecs["patch_mean"].astype(np.float16),
             n_empty=len(imgs) - len(kept), kept=np.array([has_ink(a) for a in imgs]), **extra)
    os.replace(tmp, out)
    return len(kept)


def embed_run(run: Path, device: str, workers: int):
    (run / "emb").mkdir(exist_ok=True)
    for f in sorted((run / "samples").glob("step*.npz")):
        out = run / "emb" / f.name
        if not out.exists():
            n = embed_images(np.load(f)["images"], out, device, workers)
            print(f"{run.name} {f.stem}: {n} pictures", flush=True)


def embed_ref(images: Path, out: Path, device: str, workers: int):
    """The chairs it learned from, exactly as it saw them: the same random 1,000 of the training drawings as the
    Sketch-RNN reference (REF_SEED over the drawings used), at the model's size."""
    out.mkdir(parents=True, exist_ok=True)
    z = np.load(images)
    pick = np.sort(np.random.default_rng(REF_SEED).choice(len(z["lines"]), N_REF, replace=False))
    n = embed_images(z["images"][pick], out / f"chair_train{N_REF}_{int(z['side'])}px.npz", device, workers,
                     lines=z["lines"][pick])
    print(f"reference: {n} pictures at {int(z['side'])} px", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("raster")
    r.add_argument("--data", type=Path, required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--side", type=int, default=DIFF["side"])
    r.add_argument("--workers", type=int, default=24)
    b = sub.add_parser("bench")
    b.add_argument("--images", type=Path, required=True)
    b.add_argument("--device", default="cuda")
    t = sub.add_parser("train")
    t.add_argument("--seed", type=int, required=True)
    t.add_argument("--images", type=Path, required=True)
    t.add_argument("--out", type=Path, required=True)
    t.add_argument("--device", default="cuda")
    e = sub.add_parser("embed")
    e.add_argument("--run", type=Path, nargs="+", required=True)
    e.add_argument("--device", default="cuda")
    e.add_argument("--workers", type=int, default=12)
    f = sub.add_parser("ref")
    f.add_argument("--images", type=Path, required=True)
    f.add_argument("--out", type=Path, required=True)
    f.add_argument("--device", default="cuda")
    f.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()
    if args.cmd == "raster":
        raster(args.data, args.out, args.side, args.workers)
    elif args.cmd == "bench":
        bench(args.images, args.device)
    elif args.cmd == "train":
        train(args.seed, args.images, args.out, args.device, DIFF["steps"])
    elif args.cmd == "embed":
        for run in args.run:
            embed_run(run, args.device, args.workers)
    else:
        embed_ref(args.images, args.out, args.device, args.workers)


if __name__ == "__main__":
    main()
