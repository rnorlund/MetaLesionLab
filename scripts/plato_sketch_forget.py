"""Watch an AI forget what a chair is (docs/plato_sketch_forget_plan.md): damage the trained sketch model step by
step and watch its chairs fall apart.

The larger Sketch-RNN of "Watch an AI learn" (scripts/plato_sketch_big.py; LSTM 2,048, 102,400 steps, seeds 1-4)
is loaded at its last checkpoint and damaged with reversible forward hooks (never a weight edit):
  silence  - a growing, nested share of the LSTM's hidden units is switched off (h = 0, to the head and back into
             the recurrence);
  noise    - Gaussian noise on every unit's h, scaled to the unit's standard deviation on 1,000 people's chairs;
  readout  - the same nested units cut off from the mixture head only (exploratory).
At every dose it draws 200 drawings at temperatures 1.0 and 0.4 from the learning run's fixed noise
(plato_sketch.make_noise), so drawing i starts from the same random numbers at every dose and training step.

Usage
  server (PYTHONPATH reaching metalesionlab and scipy; checkpoints in runs/big_s<seed>/ckpt/step102400.pt):
    python scripts/plato_sketch_forget.py unitsd --seed 1 --ckpt runs/big_s1/ckpt/step102400.pt \
        --data data/train_chair_all.ndjson --ref ref_big/chair_train1000.npz --out forget/forget_s1
    python scripts/plato_sketch_forget.py sample --seed 1 --ckpt runs/big_s1/ckpt/step102400.pt --scale 50.90 \
        --out forget/forget_s1
    python scripts/plato_sketch_forget.py embed --run forget/forget_s1
    python scripts/plato_sketch_forget.py refdraw --data data/train_chair_all.ndjson --ref ref_big/chair_train1000.npz \
        --out forget/ref_drawings.json
  Mac:
    python -I scripts/plato_sketch_forget.py analyze [--public public_data/plato_sketch_forget.json]
    python -I scripts/plato_sketch_forget.py web
Data on the Mac: $PLATO_FORGET_DIR (default PlatosChair/sketch_forget/): runs/forget_s<seed>/{samples,emb,unit_sd.npy,
check.json}, ref_drawings.json, maps/ (ink-map cache), results.json, figures/. The learning runs are read from
$PLATO_LIFESPAN_DIR/sketch/big/. Drawings are the model's own; it learned from Google Quick, Draw! (CC BY 4.0).
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

from metalesionlab.plato_sketch import BIG, N_REF, boot_counts, boot_spread, make_noise, sample_name, t_interval  # noqa: E402
from metalesionlab.plato_sketch_forget import (ARMS, COARSE, DISPLAY, FINE, HIDDEN, MARGIN, N_SAMPLES, PRIMARY_ARM,  # noqa: E402
                                               PRIMARY_DOSES, PRIMARY_TEMP, SEEDS, STEP, TEMPS, TEST_SEEDS, UNIT_NOISE_KEY,
                                               boot_rng, gap_verdict, half_forgotten, ink_maps, keep_mask, kept_share,
                                               nearest_person, nearest_step, path_doses, path_gap, run_name, set_name,
                                               sign_verdict, unit_order)

FORGET_DIR = Path(os.environ.get("PLATO_FORGET_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/sketch_forget"))
WEB = ROOT / "metalesionlab" / "web" / "static" / "img" / "plato_forget"
PUBLIC = ROOT / "public_data" / "plato_sketch_forget.json"


# ---------- the damage: reversible forward hooks ----------

class Damage:
    """Damage a Sketch-RNN decoder (plato_lifespan_sketch.build) while inside a `with` block; the hooks are removed
    on exit and the weights are never touched.

    silence: the LSTM's output h is multiplied by `mask` at every time step, both where it goes to the mixture head
      and where it is carried to the next step (the cell state c is left alone: with h = 0 a unit has no effect).
    noise: k x sd x eps[t] is added to h at every time step (eps: max_len x n x hidden standard normals, fixed per
      seed; t counts the decoder's calls, one per drawing step).
    readout: the mixture head's input is multiplied by `mask`; the recurrence is untouched.
    """

    def __init__(self, model, arm: str, mask=None, k: float = 0.0, sd=None, eps=None):
        self.model, self.arm, self.mask, self.k, self.sd, self.eps = model, arm, mask, k, sd, eps
        self.handles, self.t = [], 0

    def _lstm_hook(self, mod, inp, out):
        y, (h, c) = out
        if self.arm == "silence":
            return y * self.mask, (h * self.mask, c)
        # noise: one step at a time (sampling), so y[:, 0] is h[0]
        noisy = h[0] + self.k * self.sd * self.eps[self.t]
        self.t += 1
        return noisy[:, None, :], (noisy[None], c)

    def _readout_hook(self, mod, args):
        return (args[0] * self.mask,)

    def __enter__(self):
        self.t = 0
        if self.arm in ("silence", "noise"):
            self.handles.append(self.model.lstm.register_forward_hook(self._lstm_hook))
        elif self.arm == "readout":
            self.handles.append(self.model.out.register_forward_pre_hook(self._readout_hook))
        else:
            raise ValueError(self.arm)
        return self

    def __exit__(self, *exc):
        for hd in self.handles:
            hd.remove()
        self.handles = []


def load_model(ckpt: Path, device: str):
    import torch

    from plato_lifespan_sketch import build

    model = build(device, hidden=BIG["hidden"])
    model.load_state_dict(torch.load(ckpt, map_location=device))
    model.eval()
    return model


def unit_sd(seed: int, ckpt: Path, data: Path, ref: Path, out: Path, device: str):
    """Each hidden unit's standard deviation (over drawings and time steps) while the intact model reads the 1,000
    reference training chairs (teacher forcing): the scale of the noise arm."""
    import torch

    from plato_lifespan_sketch import MAX_LEN
    from plato_sketch_seeds import load_training

    lines, seqs, used = load_training(data)
    scale = float(np.std(np.concatenate([s[:-1, :2] for s in seqs]).ravel()))
    pos = {ln: i for i, ln in enumerate(used)}
    pick = [pos[int(ln)] for ln in np.load(ref)["lines"]]
    X = np.zeros((len(pick), MAX_LEN + 1, 5), np.float32)
    L = np.zeros(len(pick), int)
    for j, i in enumerate(pick):
        s = seqs[i].copy()
        s[:, :2] /= scale
        X[j, 0, 2] = 1
        X[j, 1:len(s) + 1] = s
        X[j, len(s) + 1:, 4] = 1
        L[j] = len(s)
    model = load_model(ckpt, device)
    with torch.no_grad():
        h, _ = model.lstm(torch.tensor(X[:, :-1], device=device))
    mask = torch.arange(MAX_LEN, device=device)[None] < torch.tensor(L, device=device)[:, None]
    hv = h[mask].double()
    sd = hv.std(0).cpu().numpy().astype(np.float32)
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "unit_sd.npy", sd)
    meta = {"seed": seed, "n_drawings": len(pick), "n_steps": int(mask.sum()), "scale": scale,
            "sd_median": float(np.median(sd)), "sd_min": float(sd.min()), "sd_max": float(sd.max()),
            "abs_h_mean": float(hv.abs().mean())}
    (out / "unit_sd.json").write_text(json.dumps(meta, indent=1))
    print(f"seed {seed}: unit sd median {meta['sd_median']:.3f} [{meta['sd_min']:.3f}, {meta['sd_max']:.3f}]", flush=True)


def sample(seed: int, ckpt: Path, scale: float, out: Path, device: str):
    """Every arm x dose x temperature: 200 drawings from the learning run's fixed noise. Then the reversibility
    check: with every hook removed, the intact model draws exactly what it drew first."""
    import torch

    from plato_lifespan_sketch import MAX_LEN
    from plato_sketch_seeds import sample_fixed

    model = load_model(ckpt, device)
    noise = make_noise(seed, N_SAMPLES, MAX_LEN)
    order = unit_order(seed)
    sd = torch.tensor(np.load(out / "unit_sd.npy"), device=device)
    gen = torch.Generator(device=device).manual_seed(seed * 1000 + UNIT_NOISE_KEY)
    eps = torch.randn(MAX_LEN, N_SAMPLES, HIDDEN, generator=gen, device=device)
    (out / "samples").mkdir(parents=True, exist_ok=True)
    t0, done = time.time(), {}
    for temp in TEMPS:
        for arm, doses in ARMS.items():
            for dose in doses:
                if dose == 0 and arm != "silence":
                    continue  # the intact model is shared by all arms: silence_d0.00
                mask = torch.tensor(keep_mask(order, dose), device=device)
                with Damage(model, arm, mask=mask, k=dose, sd=sd, eps=eps):
                    d = sample_fixed(model, noise, temp, scale, device)
                model.eval()  # sample_fixed leaves the model in train mode
                name = set_name(arm, dose, temp)
                (out / "samples" / f"{name}.json").write_text(json.dumps(d))
                done[name] = sum(1 for x in d if x)
        print(f"seed {seed} T={temp}: {len(done)} sets ({time.time() - t0:.0f}s)", flush=True)
    check = {}
    for temp in TEMPS:  # hooks gone: the intact model must draw exactly what it drew at dose 0
        d = sample_fixed(model, noise, temp, scale, device)
        model.eval()
        first = json.loads((out / "samples" / f"{set_name('silence', 0.0, temp)}.json").read_text())
        check[f"t{temp:.1f}"] = {"identical": sum(a == b for a, b in zip(d, first)), "of": len(d)}
    meta = {"seed": seed, "ckpt": str(ckpt), "step": STEP, "scale": scale, "device": device, "arms": ARMS,
            "temps": TEMPS, "n_samples": N_SAMPLES, "kept": done, "reversible": check,
            "seconds": round(time.time() - t0, 1)}
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"seed {seed}: reversible {check}; {meta['seconds']}s", flush=True)


def embed(run: Path, device: str, workers: int):
    from plato_sketch_seeds import embed_set

    (run / "emb").mkdir(exist_ok=True)
    t0 = time.time()
    for f in sorted((run / "samples").glob("*.json")):
        out = run / "emb" / f"{f.stem}.npz"
        if out.exists():
            continue
        n = embed_set(json.loads(f.read_text()), out, device, workers)
        print(f"{run.name} {f.stem}: {n} drawings ({time.time() - t0:.0f}s)", flush=True)


def refdraw(data: Path, ref: Path, out: Path):
    """The 1,000 reference training chairs (people's drawings, as drawn) for the ink-map comparison."""
    lines = data.read_text().splitlines()
    out.write_text(json.dumps([json.loads(lines[int(i)]) for i in np.load(ref)["lines"]]))
    print(f"wrote {out}")


# ---------- analysis (Mac) ----------

LEARN_DIR = None  # set in analyze(): $PLATO_LIFESPAN_DIR/sketch/big


def _render_maps(d):
    from metalesionlab.plato import ink_crop, render_strokes

    return ink_maps(ink_crop(render_strokes(d)))


def maps_for(drawings: list, cache: Path, workers: int = 8) -> tuple[np.ndarray, np.ndarray]:
    """Coarse and fine ink maps of the non-empty drawings (in the embeddings' order), cached."""
    if cache.exists():
        z = np.load(cache)
        return z["coarse"].astype(np.float32), z["fine"].astype(np.float32)
    from multiprocessing import get_context

    kept = [d for d in drawings if d]
    with get_context("fork").Pool(workers) as pool:
        res = pool.map(_render_maps, kept, chunksize=8)
    c = np.stack([r[0] for r in res]) if res else np.zeros((0, COARSE, COARSE), np.float32)
    f = np.stack([r[1] for r in res]) if res else np.zeros((0, FINE, FINE), np.float32)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, coarse=c.astype(np.float16), fine=f.astype(np.float16))
    return c, f


class SetData:
    """One set of drawings: per-drawing recognized / distance / nearest-person matches, its pairwise distances,
    and point estimates of every measure."""

    def __init__(self, emb: Path, samples: Path, cache: Path, M, ref_maps, ref_spread: float):
        from metalesionlab.plato_lifespan import matched_spread, proto_distances, recognized
        from metalesionlab.plato import cosine_distances

        z = np.load(emb)
        x = z["cls"].astype(np.float64)
        self.n, self.n_empty = len(x), int(z["n_empty"])
        self.ok = self.n >= 16
        self.row = {"n": self.n, "n_empty": self.n_empty}
        if not self.ok:
            return
        drawings = json.loads(samples.read_text())
        c, f = maps_for(drawings, cache)
        assert len(c) == self.n, (emb, len(c), self.n)
        ki = M.ki
        self.rec = recognized(x, ki, M.protos).astype(float)
        self.dist = proto_distances(x, M.protos[ki])
        self.D = cosine_distances(x)
        self.shape = nearest_person(c, ref_maps[0])
        self.detail = nearest_person(f, ref_maps[1])
        sp = matched_spread(self.D, 16, 200, M.rng)
        self.row.update({"recog": float(self.rec.mean()), "d_adult": float(self.dist.mean()), "spread": sp,
                         "delta": sp - ref_spread, "shape": float(self.shape.mean()), "detail": float(self.detail.mean()),
                         "strokes": float(z["strokes"].mean()), "points": float(z["points"].mean())})

    def boot(self, reps: int, rng) -> dict:
        """Bootstrap replicates (resampling drawings) of every measure, with the same resamples for all."""
        if not self.ok:
            return None
        cn = boot_counts(self.n, reps, rng)
        tot = cn.sum(1)
        return {"recog": cn @ self.rec / tot, "d_adult": cn @ self.dist / tot, "spread": boot_spread(self.D, cn),
                "shape": cn @ self.shape / tot, "detail": cn @ self.detail / tot}


class Measurer:
    def __init__(self, rng):
        from metalesionlab.plato import PLATO_DIR
        from metalesionlab.plato_lifespan import CANDIDATES, prototype

        self.protos = np.stack([prototype(np.load(PLATO_DIR / "embeddings" / "human" / f"{k}.npz")["cls"].astype(np.float64))
                                for k in CANDIDATES])
        self.ki = CANDIDATES.index("chair")
        self.rng = rng


MEAS = ["recog", "d_adult", "spread", "delta", "shape", "detail", "n", "strokes", "points"]


def _two_level(per_seed: dict, rng, reps: int) -> np.ndarray:
    """Mean over seeds, resampling seeds and (through each seed's replicates) drawings."""
    seeds = sorted(per_seed)
    arr = np.stack([per_seed[s] for s in seeds])  # S x R
    pick = rng.integers(0, len(seeds), (reps, len(seeds)))
    return np.nanmean(arr[pick, np.arange(reps)[:, None]], axis=1)


def _summ(vals: dict, boots: dict, rng, reps: int) -> dict:
    """Mean over seeds with its t-interval and two-level bootstrap CI."""
    from metalesionlab.plato import ci

    tb = t_interval([vals[s] for s in sorted(vals)])
    b = _two_level(boots, rng, reps)
    b = b[np.isfinite(b)]
    return {"mean": tb["mean"], "t_ci95": tb["ci95"], "boot_ci95": ci(b) if len(b) else [float("nan")] * 2,
            "per_seed": {str(s): vals[s] for s in sorted(vals)}, "n_seeds": tb["n"], "sd": tb["sd"]}


def analyze(reps: int, public: Path | None):
    global LEARN_DIR
    from metalesionlab.plato import DINO_MODEL, to_jsonable
    from metalesionlab.plato_lifespan import LIFESPAN_DIR

    LEARN_DIR = LIFESPAN_DIR / "sketch" / "big"
    rng = np.random.default_rng(20261028)
    M = Measurer(rng)
    brng = boot_rng()
    # the people's chairs it learned from: DINOv2 reference (as in "learn") and ink maps
    from metalesionlab.plato import cosine_distances
    from metalesionlab.plato_lifespan import matched_spread

    xr = np.load(LEARN_DIR / "ref" / f"chair_train{N_REF}.npz")["cls"].astype(np.float64)
    ref_spread = matched_spread(cosine_distances(xr), 16, 200, rng)
    ref_draw = json.loads((FORGET_DIR / "ref_drawings.json").read_text())
    ref_maps = maps_for(ref_draw, FORGET_DIR / "maps" / "ref_train1000.npz")
    learn_steps = MODELS_BIG["steps"]
    sets, boots = {}, {}
    for seed in SEEDS:
        lrun = LEARN_DIR / "runs" / f"big_s{seed}"
        frun = FORGET_DIR / "runs" / run_name(seed)
        for temp in TEMPS:
            for step in learn_steps:
                nm = sample_name(step, temp)
                sd = SetData(lrun / "emb" / f"{nm}.npz", lrun / "samples" / f"{nm}.json",
                             FORGET_DIR / "maps" / f"big_s{seed}" / f"{nm}.npz", M, ref_maps, ref_spread)
                sets[(seed, "learn", step, temp)] = sd
                boots[(seed, "learn", step, temp)] = sd.boot(reps, brng)
            for arm, doses in ARMS.items():
                for dose in doses:
                    nm = set_name("silence" if dose == 0 else arm, dose, temp)
                    if not (frun / "emb" / f"{nm}.npz").exists():
                        continue
                    sd = sets.get((seed, "silence", 0.0, temp)) if dose == 0 and arm != "silence" else None
                    sd = sd or SetData(frun / "emb" / f"{nm}.npz", frun / "samples" / f"{nm}.json",
                                       FORGET_DIR / "maps" / run_name(seed) / f"{nm}.npz", M, ref_maps, ref_spread)
                    sets[(seed, arm, dose, temp)] = sd
                    boots[(seed, arm, dose, temp)] = boots.get((seed, "silence", 0.0, temp)) if dose == 0 and arm != "silence" \
                        else sd.boot(reps, brng)
        print(f"seed {seed}: measured", flush=True)
    seeds_done = [s for s in SEEDS if (s, "silence", 0.0, PRIMARY_TEMP) in sets]

    def row(seed, kind, x, temp, m):
        sd = sets.get((seed, kind, x, temp))
        return sd.row.get(m, float("nan")) if sd else float("nan")

    def curves(kind, xs, temp, seeds):
        out = {}
        for m in MEAS:
            mean, cis, per = [], [], {}
            for x in xs:
                tb = t_interval([row(s, kind, x, temp, m) for s in seeds])
                mean.append(tb["mean"])
                cis.append(tb["ci95"])
            for s in seeds:
                per[str(s)] = [row(s, kind, x, temp, m) for x in xs]
            out[m] = {"mean": mean, "ci95": cis, "per_seed": per}
        return out

    res = {"experiment": "Watch an AI forget what a chair is: the larger sketch model, damaged step by step",
           "plan": "docs/plato_sketch_forget_plan.md", "model": MODELS_BIG_NAME, "step": STEP, "embedding_model": DINO_MODEL,
           "reps": reps, "seeds": seeds_done, "test_seeds": [s for s in TEST_SEEDS if s in seeds_done], "temps": TEMPS,
           "primary_temp": PRIMARY_TEMP, "arms": ARMS, "primary_arm": PRIMARY_ARM, "primary_doses": PRIMARY_DOSES,
           "margin": MARGIN, "n_samples": N_SAMPLES, "learn_steps": learn_steps, "display": DISPLAY,
           "reference": {"spread": ref_spread, "n": N_REF},
           "credits": {"drawings": "Google Quick, Draw! dataset (Google Creative Lab), CC BY 4.0",
                       "model": "Sketch-RNN design: Ha & Eck (2017)", "embedding": "Meta DINOv2, Apache-2.0"},
           "learn": {}, "forget": {}, "tests": {}, "checks": {}}
    for temp in TEMPS:
        tk = f"t{temp:.1f}"
        res["learn"][tk] = curves("learn", learn_steps, temp, seeds_done)
        res["forget"][tk] = {arm: curves(arm, doses, temp, seeds_done) for arm, doses in ARMS.items()}
        res["tests"][tk] = {}
        for arm, doses in ARMS.items():
            res["tests"][tk][arm] = {"test_seeds": run_tests(arm, doses, temp, res["test_seeds"], sets, boots, brng, reps, learn_steps)}
            if arm == PRIMARY_ARM:
                res["tests"][tk][arm]["all_seeds"] = run_tests(arm, doses, temp, seeds_done, sets, boots, brng, reps, learn_steps)
    # dose 0 is the fully trained model: its drawings must be exactly the learning run's last ones
    for seed in seeds_done:
        meta = json.loads((FORGET_DIR / "runs" / run_name(seed) / "meta.json").read_text())
        same = {}
        for temp in TEMPS:
            a = json.loads((FORGET_DIR / "runs" / run_name(seed) / "samples" / f"{set_name('silence', 0.0, temp)}.json").read_text())
            b = json.loads((LEARN_DIR / "runs" / f"big_s{seed}" / "samples" / f"{sample_name(STEP, temp)}.json").read_text())
            same[f"t{temp:.1f}"] = {"identical_to_learning_run": sum(p == q for p, q in zip(a, b)), "of": len(a)}
        res["checks"][str(seed)] = {"dose0_vs_learning": same, "hooks_removed": meta.get("reversible")}
    ds = sets
    dt = f"t{DISPLAY['temp']:.1f}"
    res["animation"] = {**DISPLAY, "doses": SILENCE_DOSES, "learn_steps": learn_steps,
                        "recog": [ds[(DISPLAY["seed"], "silence", x, DISPLAY["temp"])].row.get("recog") for x in SILENCE_DOSES],
                        "spread": [ds[(DISPLAY["seed"], "silence", x, DISPLAY["temp"])].row.get("spread") for x in SILENCE_DOSES],
                        "n": [ds[(DISPLAY["seed"], "silence", x, DISPLAY["temp"])].row.get("n") for x in SILENCE_DOSES],
                        "learn_recog": res["learn"][dt]["recog"]["per_seed"][str(DISPLAY["seed"])],
                        "learn_spread": res["learn"][dt]["spread"]["per_seed"][str(DISPLAY["seed"])]}
    out = FORGET_DIR / "results.json"
    out.write_text(json.dumps(no_nan(to_jsonable(res)), indent=1))
    print(f"wrote {out}")
    report(res)
    if public:
        public.write_text(json.dumps(no_nan(to_jsonable(public_block(res))), indent=1))
        print(f"wrote {public}")


def run_tests(arm, doses, temp, seeds, sets, boots, rng, reps, learn_steps) -> dict:
    """The plan's three questions for one arm and temperature over these seeds."""
    if len(seeds) < 2:
        return None
    S = sorted(seeds)
    prim = path_doses(arm)

    def val(s, kind, x, m):
        sd = sets.get((s, kind, x, temp))
        return sd.row.get(m, np.nan) if sd and sd.ok else np.nan

    def bval(s, kind, x, m):
        b = boots.get((s, kind, x, temp))
        return b[m] if b is not None else np.full(reps, np.nan)

    # the half-forgotten dose, from recognizability alone (mean over these seeds)
    intact = float(np.mean([val(s, arm, 0.0, "recog") for s in S]))
    untrained = float(np.mean([val(s, "learn", 0, "recog") for s in S]))
    rmean = [float(np.nanmean([val(s, arm, x, "recog") for s in S])) for x in doses]
    half = half_forgotten(doses, rmean, intact, untrained, last=prim[-1])
    out = {"seeds": S, "half_forgotten_dose": half, "recog_intact": intact, "recog_untrained": untrained}

    # Q1: at the same recognizability, is the damaged model as far from the adult chair as the learner was?
    for m, key in (("d_adult", "q1_distance_gap"), ("spread", "q2_variety_gap")):
        vals, bts, per_dose = {}, {}, {}
        for s in S:
            lr = [val(s, "learn", st, "recog") for st in learn_steps]
            ly = [val(s, "learn", st, m) for st in learn_steps]
            dr = [val(s, arm, x, "recog") for x in prim]
            dy = [val(s, arm, x, m) for x in prim]
            vals[s], gaps = path_gap(lr, ly, dr, dy)
            per_dose[s] = gaps
            LR = np.stack([bval(s, "learn", st, "recog") for st in learn_steps], 1)
            LY = np.stack([bval(s, "learn", st, m) for st in learn_steps], 1)
            DR = np.stack([bval(s, arm, x, "recog") for x in prim], 1)
            DY = np.stack([bval(s, arm, x, m) for x in prim], 1)
            bts[s] = np.array([path_gap(LR[b], LY[b], DR[b], DY[b])[0] for b in range(reps)])
        sm = _summ(vals, bts, rng, reps)
        sm["verdict"] = gap_verdict(sm["t_ci95"], sm["boot_ci95"]) if m == "d_adult" else \
            sign_verdict(sm["t_ci95"], sm["boot_ci95"], "more varied", "less varied", "no clear difference")
        sm["doses"] = prim
        sm["per_dose_mean"] = [float(np.nanmean([per_dose[s][i] for s in S])) for i in range(len(prim))]
        sm["doses_in_range"] = [int(sum(np.isfinite(per_dose[s][i]) for s in S)) for i in range(len(prim))]
        out[key] = sm
    # Q1, descriptive: which training step each dose looks like (mean path over these seeds)
    LRm = [float(np.nanmean([val(s, "learn", st, "recog") for s in S])) for st in learn_steps]
    LDm = [float(np.nanmean([val(s, "learn", st, "d_adult") for s in S])) for st in learn_steps]
    out["q1_looks_like_step"] = {str(x): nearest_step(LRm, LDm, learn_steps, float(np.nanmean([val(s, arm, x, "recog") for s in S])),
                                                       float(np.nanmean([val(s, arm, x, "d_adult") for s in S]))) for x in doses}

    # Q2: variety at each dose minus the intact model's; the primary test at the half-forgotten dose
    q2 = {}
    for x in doses[1:]:
        vals = {s: val(s, arm, x, "spread") - val(s, arm, 0.0, "spread") for s in S}
        bts = {s: bval(s, arm, x, "spread") - bval(s, arm, 0.0, "spread") for s in S}
        sm = _summ(vals, bts, rng, reps)
        sm["verdict"] = sign_verdict(sm["t_ci95"], sm["boot_ci95"], "more varied", "less varied", "no clear change")
        q2[f"{x:.2f}"] = sm
    out["q2_variety_change"] = q2
    out["q2_primary"] = q2.get(f"{half:.2f}")

    # Q3: share of what training built that is left, for the overall shape and the details
    q3 = {}
    for x in doses[1:]:
        vals, bts, sh, de = {}, {}, {}, {}
        sh_b, de_b = {}, {}
        for s in S:
            ks = kept_share(val(s, arm, x, "shape"), val(s, "learn", 0, "shape"), val(s, arm, 0.0, "shape"))
            kd = kept_share(val(s, arm, x, "detail"), val(s, "learn", 0, "detail"), val(s, arm, 0.0, "detail"))
            sh[s], de[s], vals[s] = float(ks), float(kd), float(ks - kd)
            kb_s = kept_share(bval(s, arm, x, "shape"), bval(s, "learn", 0, "shape"), bval(s, arm, 0.0, "shape"))
            kb_d = kept_share(bval(s, arm, x, "detail"), bval(s, "learn", 0, "detail"), bval(s, arm, 0.0, "detail"))
            sh_b[s], de_b[s], bts[s] = kb_s, kb_d, kb_s - kb_d
        sm = _summ(vals, bts, rng, reps)
        sm["verdict"] = sign_verdict(sm["t_ci95"], sm["boot_ci95"], "details go first", "shape goes first", "together")
        sm["shape_kept"] = _summ(sh, sh_b, rng, reps)
        sm["detail_kept"] = _summ(de, de_b, rng, reps)
        q3[f"{x:.2f}"] = sm
    out["q3_shape_minus_detail"] = q3
    out["q3_primary"] = q3.get(f"{half:.2f}")
    # Q3 in the learning direction (descriptive): the share of the final level reached at each training step
    lq = {}
    for m in ("shape", "detail"):
        lq[m] = [float(np.nanmean([kept_share(val(s, "learn", st, m), val(s, "learn", 0, m), val(s, "learn", learn_steps[-1], m))
                                   for s in S])) for st in learn_steps]
    out["q3_learning_share"] = lq
    return out


def no_nan(obj):
    if isinstance(obj, dict):
        return {k: no_nan(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [no_nan(v) for v in obj]
    if isinstance(obj, float) and obj != obj:
        return None
    return obj


def public_block(res: dict) -> dict:
    """Group-level numbers only (no drawings, no embeddings). Per-seed curves are kept for the three page
    measures, as in the learning block."""
    out = {k: v for k, v in res.items() if k not in ("learn", "forget")}
    keep = ("recog", "d_adult", "spread", "shape", "detail", "n")
    out["learn"] = {t: {m: c for m, c in cv.items() if m in keep} for t, cv in res["learn"].items()}
    out["forget"] = {t: {a: {m: c for m, c in cv.items() if m in keep} for a, cv in arms.items()} for t, arms in res["forget"].items()}
    return out


def report(res: dict):
    for tk, arms in res["tests"].items():
        for arm, blocks in arms.items():
            for which, t in blocks.items():
                if not t:
                    continue
                q1, q2g, q2, q3 = t["q1_distance_gap"], t["q2_variety_gap"], t["q2_primary"], t["q3_primary"]
                f = lambda c: f"[{c[0]:+.3f}, {c[1]:+.3f}]" if c and c[0] is not None and c[0] == c[0] else "[nan]"  # noqa: E731
                print(f"\n{tk} {arm} ({which}, seeds {t['seeds']}): half-forgotten at {t['half_forgotten_dose']:.2f} "
                      f"(recog {t['recog_intact']:.2f} -> untrained {t['recog_untrained']:.2f})")
                print(f"  Q1 distance gap {q1['mean']:+.3f} t {f(q1['t_ci95'])} boot {f(q1['boot_ci95'])} -> {q1['verdict']}; "
                      f"per dose {[round(v, 3) if v == v else None for v in q1['per_dose_mean']]}")
                print(f"  Q1 looks like step {t['q1_looks_like_step']}")
                print(f"  Q2 variety gap vs learning {q2g['mean']:+.3f} t {f(q2g['t_ci95'])} boot {f(q2g['boot_ci95'])} -> {q2g['verdict']}")
                if q2:
                    print(f"  Q2 variety change at half {q2['mean']:+.3f} t {f(q2['t_ci95'])} boot {f(q2['boot_ci95'])} -> {q2['verdict']}")
                if q3:
                    print(f"  Q3 shape-detail at half {q3['mean']:+.3f} t {f(q3['t_ci95'])} boot {f(q3['boot_ci95'])} -> {q3['verdict']} "
                          f"(shape kept {q3['shape_kept']['mean']:.2f}, details kept {q3['detail_kept']['mean']:.2f})")
    for tk in res["forget"]:
        for arm, cv in res["forget"][tk].items():
            print(f"\n{tk} {arm}: dose " + " ".join(f"{x:6.2f}" for x in res["arms"][arm]))
            for m in ("recog", "d_adult", "spread", "shape", "detail", "n"):
                print(f"   {m:8s}" + " ".join(f"{v:6.3f}" if v is not None and v == v else "   nan" for v in cv[m]["mean"]))
    print("\nchecks:", json.dumps(res["checks"]))


# ---------- pictures for the page (Mac) ----------

def web():
    """The page's sprite (seed 1, temperature 0.4, the first 16 drawings at every silencing dose: 12 frames, 4 across
    and 3 down) and the hub card's strip (the learning page's stroke-by-stroke chair at 0, 30, 60 and 90%)."""
    from PIL import Image

    sys.path.insert(0, str(ROOT / "scripts"))
    from plato_sketch_animate import PAPER, grid, tile

    run = FORGET_DIR / "runs" / run_name(DISPLAY["seed"])
    frames = []
    for x in SILENCE_DOSES:
        d = json.loads((run / "samples" / f"{set_name('silence', x, DISPLAY['temp'])}.json").read_text())[:DISPLAY["n"]]
        frames.append(grid(d, 180, 8, bg=PAPER))
    fw, cols = frames[0].width, 4
    rows = -(-len(frames) // cols)
    sheet = Image.new("RGB", (cols * fw, rows * fw), PAPER)
    for i, fr in enumerate(frames):
        sheet.paste(fr, ((i % cols) * fw, (i // cols) * fw))
    WEB.mkdir(parents=True, exist_ok=True)
    sheet.save(WEB / "forget_sprite.webp", "WEBP", quality=70, method=6)
    idx = json.loads((ROOT / "metalesionlab" / "web" / "static" / "img" / "plato_lifespan" / "sketch" / "stroke_order.json").read_text())["index"]
    cell, gap, card = 240, 12, [0.0, 0.3, 0.6, 0.9]
    strip = Image.new("RGB", (len(card) * cell + (len(card) - 1) * gap, cell), PAPER)
    for k, x in enumerate(card):
        d = json.loads((run / "samples" / f"{set_name('silence', x, DISPLAY['temp'])}.json").read_text())[idx]
        strip.paste(tile(d, cell), (k * (cell + gap), 0))
    strip.save(WEB / "forget_card.webp", "WEBP", quality=80, method=6)
    for p in sorted(WEB.iterdir()):
        print(f"{p.name}: {p.stat().st_size / 1024:.0f} KB")


from metalesionlab.plato_sketch import MODELS as _MODELS  # noqa: E402
from metalesionlab.plato_sketch_forget import SILENCE as SILENCE_DOSES  # noqa: E402

MODELS_BIG = _MODELS["big"]
MODELS_BIG_NAME = _MODELS["big"]["model"]


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("unitsd")
    for p in (u,):
        p.add_argument("--seed", type=int, required=True)
        p.add_argument("--ckpt", type=Path, required=True)
        p.add_argument("--data", type=Path, required=True)
        p.add_argument("--ref", type=Path, required=True)
        p.add_argument("--out", type=Path, required=True)
        p.add_argument("--device", default="cuda")
    s = sub.add_parser("sample")
    s.add_argument("--seed", type=int, required=True)
    s.add_argument("--ckpt", type=Path, required=True)
    s.add_argument("--scale", type=float, required=True)
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--device", default="cuda")
    e = sub.add_parser("embed")
    e.add_argument("--run", type=Path, nargs="+", required=True)
    e.add_argument("--device", default="cuda")
    e.add_argument("--workers", type=int, default=8)
    r = sub.add_parser("refdraw")
    r.add_argument("--data", type=Path, required=True)
    r.add_argument("--ref", type=Path, required=True)
    r.add_argument("--out", type=Path, required=True)
    a = sub.add_parser("analyze")
    a.add_argument("--reps", type=int, default=2000)
    a.add_argument("--public", type=Path)
    sub.add_parser("web")
    args = ap.parse_args()
    if args.cmd == "unitsd":
        unit_sd(args.seed, args.ckpt, args.data, args.ref, args.out, args.device)
    elif args.cmd == "sample":
        sample(args.seed, args.ckpt, args.scale, args.out, args.device)
    elif args.cmd == "embed":
        for run in args.run:
            embed(run, args.device, args.workers)
    elif args.cmd == "refdraw":
        refdraw(args.data, args.ref, args.out)
    elif args.cmd == "analyze":
        analyze(args.reps, args.public)
    else:
        web()


if __name__ == "__main__":
    main()
