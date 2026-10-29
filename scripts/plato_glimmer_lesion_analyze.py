"""Damage Meta's open AI, Mac part (docs/plato_glimmer_lesion_plan.md): render, read, score and analyze.

  render  [--run raw|pilot]   extract and render every drawing (plato_scale.classify), PNGs and measure.json
  read    [--run raw|pilot]   SigLIP 2 reads every valid drawing: which of 36 labels (35 concepts + God) fits best
  embed   [--run raw]         DINOv2 (base, CLS) of every valid ink-cropped drawing
  sheet                       the blinded description sheet for coding by eye (no condition, shuffled)
  score   [--run raw|pilot]   the fixed description rubric (only after the by-eye codes are hashed in the plan)
  analyze                     rates, retention curves, the order verdicts and the bootstrap gaps -> results.json
  pilot                       a one-screen summary of the pilot

Files live in $PLATO_GLIMMER_LESION_DIR (default PlatosChair/glimmer_lesion): <run>/<cond>.json from the GPU,
png/<run>/<cond>/<thing>_<i>.png, <run>_measure.json, <run>_reader.json, <run>_emb.npz, <run>_scores.json,
byeye/sheet.json and byeye/codes.json, results.json.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from metalesionlab import plato_glimmer_lesion as gl  # noqa: E402
from metalesionlab.plato_scale import classify  # noqa: E402

D = gl.OUT_DIR
SIGLIP = "google/siglip2-so400m-patch14-384"
TEMPLATE = "a simple line drawing of {phrase}"
# God's name in the reader. "God" itself pulls every line drawing toward it (it won 16% of people's drawings of the
# 35 other things), so the plan fixed "a god" from a check before the main run: 2% of people's drawings of other
# things, and 16 of 16 of both Muse Image's and Stable Diffusion XL's God drawings (docs/plato_glimmer_lesion_plan.md).
GOD_PHRASE = "a god"


def reader_labels() -> list[str]:
    from metalesionlab.plato import CONCEPTS

    return [c.label for c in CONCEPTS] + ["God"]


def phrase(label: str) -> str:
    if label == "God":
        return GOD_PHRASE
    return ("an " if label[0] in "aeiou" else "a ") + label


def cond_files(run: str) -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in sorted((D / run).glob("*.json"))}


def png_path(run: str, cond: str, thing: str, i: int, browser: bool = True) -> Path:
    """The web browser's drawing (plato_glimmer_lesion_browser.py), or the strict house renderer's (cairosvg)."""
    return D / ("png_browser" if browser else "png") / run / cond / f"{thing}_{i}.png"


# ---------- render ----------

def cmd_render(args):
    out_path = D / f"{args.run}_measure.json"
    res = json.loads(out_path.read_text()) if out_path.exists() else {}
    for cond, rec in cond_files(args.run).items():
        if cond in res:
            continue
        res[cond] = {}
        for t in gl.THINGS:
            rows = []
            for s in rec["things"][t.key]["draw"]:
                c = classify(s["text"])
                row = {"i": s["i"], "reason": c["reason"], "ink": c["ink"], "n_tokens": s["n_tokens"], "stop": s["stop"]}
                if c.get("error"):
                    row["error"] = c["error"]
                if t.key == "clock":
                    row["clock_numbers"] = gl.clock_numbers(c["svg"])["numbers"]
                if c["image"] is not None:
                    p = png_path(args.run, cond, t.key, s["i"], browser=False)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    c["image"].save(p)
                rows.append(row)
            res[cond][t.key] = rows
        reasons = {t.key: sum(r["reason"] is None for r in res[cond][t.key]) for t in gl.THINGS}
        print(f"{cond:14s} valid {reasons}", flush=True)
        out_path.write_text(json.dumps(res, indent=1))


# ---------- SigLIP 2 ----------

class Reader:
    def __init__(self):
        import torch
        from transformers import AutoModel, AutoProcessor

        self.torch = torch
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.proc = AutoProcessor.from_pretrained(SIGLIP)
        self.model = AutoModel.from_pretrained(SIGLIP).to(self.device).eval()
        self.labels = reader_labels()
        with torch.no_grad():
            t = self.proc(text=[TEMPLATE.format(phrase=phrase(lb)) for lb in self.labels], padding="max_length",
                          max_length=64, return_tensors="pt").to(self.device)
            v = self.model.get_text_features(**t)
            v = v if torch.is_tensor(v) else v.pooler_output
        self.text = torch.nn.functional.normalize(v.float(), dim=-1)

    def __call__(self, images, batch: int = 32) -> list[dict]:
        torch, out = self.torch, []
        with torch.no_grad():
            for i in range(0, len(images), batch):
                x = self.proc(images=images[i:i + batch], return_tensors="pt").to(self.device)
                v = self.model.get_image_features(**x)
                v = v if torch.is_tensor(v) else v.pooler_output
                sims = torch.nn.functional.normalize(v.float(), dim=-1) @ self.text.T
                for row in sims.cpu().numpy():
                    order = np.argsort(-row)
                    out.append({"label": self.labels[order[0]], "top3": [self.labels[k] for k in order[:3]],
                                "rank": {lb: int(np.where(order == k)[0][0]) + 1 for k, lb in enumerate(self.labels)
                                         if lb in ("chair", "clock", "God")}})
        return out


def cmd_read(args):
    from metalesionlab.plato import ink_crop

    meas = json.loads((D / f"{args.run}_browser.json").read_text())
    out_path = D / f"{args.run}_reader.json"
    res = json.loads(out_path.read_text()) if out_path.exists() else {"model": SIGLIP, "template": TEMPLATE,
                                                                       "labels": reader_labels(), "read": {}}
    rd = None
    for cond, things in meas.items():
        if cond in res["read"]:
            continue
        rd = rd or Reader()
        res["read"][cond] = {}
        for key, rows in things.items():
            ok = [r["i"] for r in rows if r["reason"] is None]
            imgs = [ink_crop(Image.open(png_path(args.run, cond, key, i)).convert("RGB")) for i in ok]
            got = rd(imgs) if imgs else []
            res["read"][cond][key] = dict(zip(map(str, ok), got))
        summary = {k: sum(v["label"] == gl.BY_KEY[k].reader_label for v in res["read"][cond][k].values())
                   for k in things}
        print(f"{cond:14s} read as itself {summary}", flush=True)
        out_path.write_text(json.dumps(res, indent=1))


# ---------- DINOv2 ----------

def cmd_embed(args):
    from metalesionlab.plato import DINO_MODEL, Embedder, ink_crop

    meas = json.loads((D / f"{args.run}_browser.json").read_text())
    emb = Embedder(DINO_MODEL)
    keys, vecs = [], []
    for cond, things in meas.items():
        imgs = []
        for key, rows in things.items():
            for r in rows:
                if r["reason"] is None:
                    keys.append(f"{cond}|{key}|{r['i']}")
                    imgs.append(ink_crop(Image.open(png_path(args.run, cond, key, r["i"])).convert("RGB")))
        if imgs:
            vecs.append(emb(imgs)["cls"].astype(np.float32))
        print(f"{cond:14s} {len(imgs)} drawings embedded", flush=True)
    np.savez(D / f"{args.run}_emb.npz", keys=np.array(keys), cls=np.concatenate(vecs), model=DINO_MODEL)


# ---------- descriptions: the blinded sheet, then the rubric ----------

SAMPLE = 150


def cmd_sheet(args):
    """A seeded stratified random sample of 150 descriptions for coding by eye (a dated deviation from coding all 756,
    for cost): drawn round-robin over the strata thing x damage type x step (intact counts once per type), so each
    stratum gets as even a share as 150 allows. Shuffled; the sheet shows only an id and the thing, never the condition.
    The key (id -> condition) is written separately and not opened while coding."""
    rng = np.random.default_rng(20261029)
    strata = {}
    for cond, rec in cond_files("raw").items():
        t_, _ = gl.parse_condition(cond)
        for t in gl.THINGS:
            strata[(t.key, cond)] = [{"cond": cond, "thing": t.key, "i": s["i"], "text": s["text"]}
                                     for s in rec["things"][t.key]["describe"]]
    for v in strata.values():
        rng.shuffle(v)
    keys = sorted(strata, key=lambda k: (k[1], k[0]))
    order = rng.permutation(len(keys))
    picked = []
    while len(picked) < SAMPLE:
        for k in order:
            if strata[keys[k]] and len(picked) < SAMPLE:
                picked.append(strata[keys[k]].pop())
    picked = [picked[k] for k in rng.permutation(len(picked))]
    sheet, key = [], {}
    for n, r in enumerate(picked):
        sid = f"d{n:04d}"
        sheet.append({"id": sid, "thing": r["thing"], "text": r["text"]})
        key[sid] = {"cond": r["cond"], "thing": r["thing"], "i": r["i"]}
    (D / "byeye").mkdir(exist_ok=True)
    (D / "byeye" / "sheet.json").write_text(json.dumps(sheet, indent=0, ensure_ascii=False))
    (D / "byeye" / "key.json").write_text(json.dumps(key, indent=0))
    print(f"{len(sheet)} descriptions on the sheet, {len(strata)} strata", flush=True)


def cmd_score(args):
    if args.run == "raw":
        codes = D / "byeye" / "codes.json"
        plan = (ROOT / "docs" / "plato_glimmer_lesion_plan.md").read_text()
        if not codes.exists():
            raise SystemExit("code the sampled descriptions by eye first (byeye/codes.json)")
        digest = hashlib.sha256(codes.read_bytes()).hexdigest()
        if digest not in plan:
            raise SystemExit(f"record the by-eye codes' SHA-256 ({digest}) in the plan before scoring")
    out = {}
    for cond, rec in cond_files(args.run).items():
        out[cond] = {}
        for t in gl.THINGS:
            out[cond][t.key] = [{"i": s["i"], **gl.score_description(s["text"], t.key, s["finished"])}
                                for s in rec["things"][t.key]["describe"]]
    (D / f"{args.run}_scores.json").write_text(json.dumps(out, indent=0))
    print(f"scored {sum(len(v) for c in out.values() for v in c.values())} descriptions", flush=True)


# ---------- per-answer outcomes ----------

def unit(x):
    x = np.asarray(x, float)
    return x / np.linalg.norm(x, axis=-1, keepdims=True)


def outcomes(run: str, byeye: bool = True) -> dict:
    """cond -> thing -> {measure: array of N}: drew (the browser drew something), valid (strict house renderer),
    named (the thing is among SigLIP 2's three best of 36 names), named_first (its best), similarity (DINOv2 cosine
    to the undamaged drawings' average; NaN where nothing was drawn), correct / names / fluent (the rubric), and the
    by-eye codes where they exist."""
    raw = cond_files(run)
    browser = json.loads((D / f"{run}_browser.json").read_text())
    strict = json.loads((D / f"{run}_measure.json").read_text())
    read = json.loads((D / f"{run}_reader.json").read_text())["read"]
    scores = json.loads((D / f"{run}_scores.json").read_text())
    emb_path = D / f"{run}_emb.npz"
    vec = {}
    if emb_path.exists():
        z = np.load(emb_path)
        vec = dict(zip(z["keys"].tolist(), unit(z["cls"])))
    codes, key = {}, {}
    if byeye and (D / "byeye" / "codes.json").exists():
        codes = json.loads((D / "byeye" / "codes.json").read_text())["codes"]
        key = json.loads((D / "byeye" / "key.json").read_text())
    coded = {(k["cond"], k["thing"], k["i"]): codes[sid] for sid, k in key.items() if sid in codes}
    out = {}
    for cond in raw:
        out[cond] = {}
        for t in gl.THINGS:
            n = len(raw[cond]["things"][t.key]["draw"])
            o = {m: np.zeros(n) for m in ("drew", "valid", "named", "named_first", "correct", "names", "fluent")}
            o["similarity"] = np.full(n, np.nan)
            for r in browser[cond][t.key]:
                o["drew"][r["i"]] = r["reason"] is None
            for r in strict[cond][t.key]:
                o["valid"][r["i"]] = r["reason"] is None
            for i, rd in read[cond][t.key].items():
                o["named"][int(i)] = t.reader_label in rd["top3"]
                o["named_first"][int(i)] = rd["label"] == t.reader_label
            for s in scores[cond][t.key]:
                for m in ("correct", "names", "fluent"):
                    o[m][s["i"]] = s[m]
            if t.key == "clock":
                o["all_numbers"] = np.array([len(r.get("clock_numbers") or []) == 12 for r in strict[cond][t.key]], float)
            if coded:
                o["byeye_correct"] = np.array([coded[(cond, t.key, i)]["correct"] for i in range(n)], float)
                o["byeye_fluent"] = np.array([coded[(cond, t.key, i)]["fluent"] for i in range(n)], float)
            out[cond][t.key] = o
    # similarity to the undamaged drawings: each thing's undamaged average, leaving the drawing itself out when it is
    # one of them
    for t in gl.THINGS:
        ref = {i: vec[f"intact|{t.key}|{i}"] for i in range(gl.N) if f"intact|{t.key}|{i}" in vec}
        if not ref:
            continue
        total = np.sum(list(ref.values()), axis=0)
        for cond in out:
            for i in range(len(out[cond][t.key]["drew"])):
                v = vec.get(f"{cond}|{t.key}|{i}")
                if v is None:
                    continue
                c = total - v if cond == "intact" and i in ref else total
                out[cond][t.key]["similarity"][i] = float(v @ unit(c))
    return out


def medoid(run: str, thing: str) -> int:
    """The undamaged drawing nearest on average to the other undamaged drawings of the thing (DINOv2): the answer the
    slider follows through every step (rule fixed in the plan)."""
    z = np.load(D / f"{run}_emb.npz")
    keys = z["keys"].tolist()
    idx = [k for k in keys if k.startswith(f"intact|{thing}|")]
    v = unit(np.stack([z["cls"][keys.index(k)] for k in idx]))
    d = 1 - v @ v.T
    return int(idx[int(np.argmin(d.sum(1)))].split("|")[2])


# ---------- the analysis ----------

PICTURE, WORD = "named", "correct"   # the plan's primary measures
FLOOR = 4                            # a thing enters the primary test if both are at least 4 of 12 undamaged


def stack(out: dict, conds: list[str], things: list[str], m: str) -> np.ndarray:
    return np.stack([np.stack([out[c][t][m] for t in things]) for c in conds])  # (C, T, N)


def curve(out, conds, things, m) -> list[float]:
    return [1.0] + [float(x) for x in gl.retention_curves(stack(out, conds, things, m))]


def type_result(out: dict, dtype: str, things: list[str]) -> dict:
    d = gl.DAMAGE_BY_KEY[dtype]
    conds = ["intact"] + [gl.condition_name(dtype, x) for x in d.doses]
    res = {"type": dtype, "conditions": conds, "things": things}
    if not things:
        res["verdict"] = "not testable"
        return res
    pic, word = stack(out, conds, things, PICTURE), stack(out, conds, things, WORD)
    curves = {m: curve(out, conds, things, m) for m in (PICTURE, WORD, "fluent", "drew", "names")}
    sp = gl.first_below_half(curves[PICTURE][1:], 1.0)
    sw = gl.first_below_half(curves[WORD][1:], 1.0)
    b = gl.boot_gap(pic, word, seed=gl.DAMAGE.index(d))
    res.update(curves=curves, step_picture=sp, step_word=sw, order=gl.order_verdict(sp, sw),
               gap=b["gap"], ci95=b["ci95"], dropped=b["dropped"], verdict=gl.gap_verdict(b["ci95"]), _boot=b)
    sec = {}  # secondary: other measures of each side
    for name, (pm, wm) in {"drew_vs_correct": ("drew", WORD), "named_vs_names": (PICTURE, "names"),
                           "named_vs_fluent": (PICTURE, "fluent")}.items():
        bb = gl.boot_gap(stack(out, conds, things, pm), stack(out, conds, things, wm), seed=7)
        sec[name] = {"gap": bb["gap"], "ci95": bb["ci95"], "verdict": gl.gap_verdict(bb["ci95"])}
    if "byeye_correct" in out["intact"][things[0]]:
        bb = gl.boot_gap(pic, stack(out, conds, things, "byeye_correct"), seed=8)
        by = curve(out, conds, things, "byeye_correct")
        sec["named_vs_byeye_correct"] = {"gap": bb["gap"], "ci95": bb["ci95"], "verdict": gl.gap_verdict(bb["ci95"]),
                                         "order": gl.order_verdict(sp, gl.first_below_half(by[1:], 1.0)), "curve": by}
    res["secondary"] = sec
    per = {}
    for t in things:
        bt = gl.boot_gap(stack(out, conds, [t], PICTURE), stack(out, conds, [t], WORD), seed=9)
        per[t] = {"gap": bt["gap"], "ci95": bt["ci95"], "verdict": gl.gap_verdict(bt["ci95"]),
                  "order": gl.order_verdict(gl.first_below_half(curve(out, conds, [t], PICTURE)[1:], 1.0),
                                            gl.first_below_half(curve(out, conds, [t], WORD)[1:], 1.0))}
    res["per_thing"] = per
    return res


def rates(out: dict) -> dict:
    r = {}
    for cond, things in out.items():
        r[cond] = {}
        for t, o in things.items():
            row = {m: int(np.nansum(v)) for m, v in o.items() if m != "similarity"}
            row["n"] = len(o["drew"])
            sim = o["similarity"][np.isfinite(o["similarity"])]
            row["similarity"] = round(float(sim.mean()), 4) if len(sim) else None
            r[cond][t] = row
    return r


def cmd_analyze(args):
    out = outcomes("raw")
    intact = out["intact"]
    included = [t.key for t in gl.THINGS if intact[t.key][PICTURE].sum() >= FLOOR and intact[t.key][WORD].sum() >= FLOOR]
    res = {"included": included, "floor": FLOOR, "rates": rates(out), "types": {}}
    for d in gl.DAMAGE:
        res["types"][d.key] = type_result(out, d.key, included)
    e, la = res["types"]["early"], res["types"]["late"]
    if "_boot" in e and "_boot" in la:
        ci = gl.boot_gap_difference(e["_boot"], la["_boot"])
        res["early_vs_late"] = {"difference": e["gap"] - la["gap"], "ci95": ci,
                                "verdict": "different" if (ci[0] > 0 or ci[1] < 0) else "too close to call"}
    for v in res["types"].values():
        v.pop("_boot", None)
    res["featured"] = {t.key: medoid("raw", t.key) for t in gl.THINGS}
    (D / "results.json").write_text(json.dumps(res, indent=1, default=float))
    print(f"included: {included}")
    for k, v in res["types"].items():
        if "gap" in v:
            print(f"{k:6s} order {v['order']:14s} (picture step {v['step_picture']}, word step {v['step_word']}); gap "
                  f"{v['gap']:+.3f} [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}] -> {v['verdict']}")
            print("        picture", [round(x, 2) for x in v["curves"][PICTURE]], " word",
                  [round(x, 2) for x in v["curves"][WORD]], " fluent", [round(x, 2) for x in v["curves"]["fluent"]])
            print("        per thing", {t: (round(p["gap"], 2), p["verdict"], p["order"]) for t, p in v["per_thing"].items()})
            print("        secondary", {s: (round(p["gap"], 2), p["verdict"]) for s, p in v["secondary"].items()})
    if "early_vs_late" in res:
        print("early - late:", res["early_vs_late"])


# ---------- the page's data and pictures ----------

WEB = ROOT / "metalesionlab" / "web"
IMG = WEB / "static" / "img" / "plato_glimmer"
URL = "/static/img/plato_glimmer/"
TILE, FEAT = 120, 300
GREY = 214          # a failed answer's tile (no drawing came out): plain grey paper
THING_NAMES = {"chair": "chair", "clock": "clock", "god": "God"}
TYPE_TEXT = {  # plain words for each kind of damage (docs/style_plain_language.md: layer = "stage")
    "all": ("Neurons, all stages", "neurons switched off in all 52 stages"),
    "early": ("Neurons, first third", "neurons switched off in its first 17 stages only"),
    "late": ("Neurons, last third", "neurons switched off in its last 17 stages only"),
    "heads": ("Attention heads", "attention heads switched off in all 52 stages"),
}
CREDITS = ["The damaged AI: Meta Muse Glimmer 30B (open weights), on our own graphics card",
           "The reader of the drawings: Google SigLIP 2 (So400m, Apache-2.0)",
           "Picture similarity: Meta DINOv2 (base, Apache-2.0)",
           "Drawings drawn from the AI's code by headless Chromium (Playwright)"]


def step_label(dtype: str, dose: float) -> str:
    pct = f"{dose * 100:g}%"
    return {"all": f"{pct} of its neurons off, in every stage", "early": f"{pct} of the neurons in its first third off",
            "late": f"{pct} of the neurons in its last third off",
            "heads": f"{pct} of its attention heads off"}[dtype]


def tile(run: str, cond: str, thing: str, i: int, side: int, drew: bool) -> Image.Image:
    if not drew:
        return Image.new("RGB", (side, side), (GREY, GREY, GREY))
    im = Image.open(png_path(run, cond, thing, i)).convert("RGB")
    return im.resize((side, side), Image.LANCZOS)


def clean_sentence(text: str, limit: int = 260) -> str:
    s = " ".join((text or "").replace("*", "").replace("#", "").split())
    return s if len(s) <= limit else s[:limit - 1].rstrip() + "…"


def save_webp(im: Image.Image, path: Path, quality: int = 70) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "WEBP", quality=quality, method=6)


def cmd_web(args):
    res = json.loads((D / "results.json").read_text())
    out = outcomes("raw")
    raw = cond_files("raw")
    feat = res["featured"]
    marks, sentences = {}, {}
    for cond in out:
        marks[cond], sentences[cond] = {}, {}
        for t in gl.THINGS:
            o = out[cond][t.key]
            marks[cond][t.key] = {m: "".join(str(int(x)) for x in o[m]) for m in ("drew", "named", "correct", "fluent")}
            sentences[cond][t.key] = [clean_sentence(s["text"]) for s in raw[cond]["things"][t.key]["describe"]]
    damage = []
    for d in gl.DAMAGE:
        conds = ["intact"] + [gl.condition_name(d.key, x) for x in d.doses]
        steps = [{"cond": "intact", "dose": 0, "label": "undamaged"}]
        steps += [{"cond": c, "dose": x, "label": step_label(d.key, x), "share_of_model": round(gl.units_off(d.key, x)["share_of_model"], 4)}
                  for c, x in zip(conds[1:], d.doses)]
        damage.append({"key": d.key, "short": TYPE_TEXT[d.key][0], "label": TYPE_TEXT[d.key][1],
                       "primary": d.key in gl.PRIMARY_TYPES, "steps": steps})
        # sprites: every answer (6 steps x 12 tries) per thing, and the followed answer of each thing at each step
        for t in gl.THINGS:
            grid = Image.new("RGB", (gl.N * TILE, len(conds) * TILE), (255, 255, 255))
            for r, c in enumerate(conds):
                for i in range(gl.N):
                    grid.paste(tile("raw", c, t.key, i, TILE, bool(out[c][t.key]["drew"][i])), (i * TILE, r * TILE))
            save_webp(grid, IMG / f"grid_{d.key}_{t.key}.webp")
        fs = Image.new("RGB", (len(gl.THINGS) * FEAT, len(conds) * FEAT), (255, 255, 255))
        for r, c in enumerate(conds):
            for k, t in enumerate(gl.THINGS):
                i = feat[t.key]
                fs.paste(tile("raw", c, t.key, i, FEAT, bool(out[c][t.key]["drew"][i])), (k * FEAT, r * FEAT))
        save_webp(fs, IMG / f"featured_{d.key}.webp", quality=74)
    verdict = {k: {kk: vv for kk, vv in v.items() if kk not in ("conditions",)} for k, v in res["types"].items()}
    gpu = json.loads((D / "gpu.json").read_text()) if (D / "gpu.json").exists() else {}
    data = {
        "about": "Damage Meta's open AI: what does it forget first? Derived numbers and the AI's own short sentences; "
                 "docs/plato_glimmer_lesion.md.",
        "credits": CREDITS,
        "things": [{"key": t.key, "name": THING_NAMES[t.key], "draw": t.draw, "describe": t.describe} for t in gl.THINGS],
        "damage": damage,
        "n": gl.N,
        "conditions": res["rates"],
        "marks": marks,
        "sentences": sentences,
        "featured": feat,
        "verdict": {"included": res["included"], "floor": res["floor"], "types": verdict,
                    "early_vs_late": res.get("early_vs_late")},
        "sprites": {"grid": URL + "grid_{type}_{thing}.webp", "featured": URL + "featured_{type}.webp", "tile": TILE,
                    "feat": FEAT, "cols": gl.N, "rows": 1 + len(gl.DAMAGE[0].doses)},
        "cost": {"usd": 0, **gpu},
    }
    errs = gl.validate_public(data)
    if errs:
        raise SystemExit("\n".join(errs))
    (WEB / "data" / "plato_glimmer.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=float))
    size = sum(p.stat().st_size for p in IMG.glob("*.webp"))
    print(f"wrote web/data/plato_glimmer.json and {len(list(IMG.glob('*.webp')))} sprites, {size // 1024} KB", flush=True)


# ---------- the pilot summary ----------

def cmd_pilot(args):
    out = outcomes("pilot", byeye=False)
    conds = sorted(out, key=lambda c: (gl.parse_condition(c)[0] != "intact", gl.parse_condition(c)))
    print(f"{'condition':14s} " + "  ".join(f"{t.key:>20s}" for t in gl.THINGS) + "   (drew/valid/named/correct/fluent)")
    for c in conds:
        cells = []
        for t in gl.THINGS:
            o = out[c][t.key]
            cells.append("/".join(str(int(o[m].sum())) for m in ("drew", "valid", "named", "correct", "fluent"))
                         + f" of {len(o['drew'])}")
        print(f"{c:14s} " + "  ".join(f"{x:>20s}" for x in cells))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("render", "read", "embed", "score"):
        p = sub.add_parser(name)
        p.add_argument("--run", default="raw", choices=["raw", "pilot"])
    sub.add_parser("sheet")
    sub.add_parser("pilot")
    sub.add_parser("analyze")
    sub.add_parser("web")
    args = ap.parse_args()
    {"render": cmd_render, "read": cmd_read, "embed": cmd_embed, "sheet": cmd_sheet, "score": cmd_score,
     "pilot": cmd_pilot, "analyze": cmd_analyze, "web": cmd_web}[args.cmd](args)


if __name__ == "__main__":
    main()
