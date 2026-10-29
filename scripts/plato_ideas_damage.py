"""God and the other ideas, damaged (docs/plato_ideas_damage_plan.md): the Mac's part.

  crop     ink-cropped 448 px copies of every SDXL picture, for Glimmer      -> damage/crop448/<cond>/<key>/s<i>.png
  embed    DINOv2-base CLS of every ink-cropped picture (the house PREP)     -> damage/embeddings/<cond>.npz
  sheets   God's pictures, one numbered 4 x 4 sheet per condition, for the check by eye; and one overview sheet per
           key (seeds x conditions)                                          -> damage/sheets/
  pick     each key's strip seed by the pre-registered rule (the intact DINOv2 medoid) -> damage/picks.json
  stats    the plan's predictions D1-D6 and the descriptive tables          -> damage/results.json

The pictures come from scripts/draw_damage_sdxl.py run --ideas on a lab GPU, copied to $PLATO_IDEAS_DIR/damage/run/;
Glimmer's answers from scripts/plato_ideas_damage_glimmer.py, copied to damage/labels/. No network, no API calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from metalesionlab import plato  # noqa: E402
from metalesionlab import plato_ideas as I  # noqa: E402
from metalesionlab import plato_ideas_damage as ID  # noqa: E402
from metalesionlab.plato_damage import at_severity, boot_matched_contrast, parse_condition  # noqa: E402

DIR = I.IDEAS_DIR / "damage"
RUN, CROP, EMB, LABELS = DIR / "run", DIR / "crop448", DIR / "embeddings", DIR / "labels"
EYE = DIR / "god_by_eye.json"
PREP = "flatten_paper(21, 215) + ink_crop(256, margin 0.06, threshold 200, speck 3px)"  # = scripts/plato_embed.py
LANG, DRAW = ID.PAIRS["noise"]
LISTED = lambda key: [s for s, _ in I.ANY[key].emblems]  # noqa: E731


def conditions_on_disk() -> list[str]:
    conds = [p.name for p in RUN.iterdir() if p.is_dir()]
    return sorted(conds, key=lambda c: (c != "intact", parse_condition(c)))


def files_in(cond: str, key: str | None = None) -> list[Path]:
    pattern = f"{key}/s*.png" if key else "*/s*.png"
    return sorted((RUN / cond).glob(pattern), key=lambda p: (ID.KEYS.index(p.parent.name), int(p.stem[1:])))


# ---------- preparing ----------

def cmd_crop(args):
    made = 0
    for cond in conditions_on_disk():
        for f in files_in(cond):
            out = CROP / cond / f.parent.name / f.name
            if out.exists():
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            plato.ink_crop(Image.open(f).convert("RGB"), side=448).save(out)
            made += 1
    print(f"cropped {made} new pictures into {CROP}")


def cmd_embed(args):
    embed, t0, count = None, time.time(), 0
    for cond in conditions_on_disk():
        files = files_in(cond)
        names = [f"{f.parent.name}/{f.name}" for f in files]
        out = EMB / f"{cond}.npz"
        if out.exists():
            old = np.load(out)
            if list(old["files"]) == names and str(old["prep"]) == PREP:
                continue
        embed = embed or plato.Embedder(plato.DINO_MODEL, args.device)
        vecs = embed([plato.ink_crop(Image.open(f).convert("RGB")) for f in files])
        out.parent.mkdir(parents=True, exist_ok=True)
        np.savez(out, files=np.array(names), model=plato.DINO_MODEL, prep=PREP, cls=vecs["cls"])
        count += len(files)
        print(f"{cond:20s} {len(files):4d} pictures ({time.time() - t0:.0f}s)", flush=True)
    print(f"embedded {count} pictures")


def load_cls() -> dict[str, dict[str, np.ndarray]]:
    """condition -> key -> (seeds, 768) CLS in seed order."""
    out = {}
    for f in sorted(EMB.glob("*.npz")):
        z = np.load(f)
        if str(z["prep"]) != PREP:
            raise SystemExit(f"{f}: made with a different preparation")
        by: dict[str, list] = {}
        for name, v in zip(z["files"], z["cls"]):
            key, fname = str(name).split("/")
            by.setdefault(key, []).append((int(fname[1:-4]), v.astype(np.float64)))
        out[f.stem] = {k: np.array([v for _, v in sorted(rows, key=lambda t: t[0])]) for k, rows in by.items()}
    return out


def numbered_grid(paths: list[Path], cols: int, cell: int, labels: list[str]) -> Image.Image:
    rows = -(-len(paths) // cols)
    sheet = Image.new("RGB", (cols * cell, rows * cell), "white")
    g = ImageDraw.Draw(sheet)
    for i, (p, lab) in enumerate(zip(paths, labels)):
        x, y = (i % cols) * cell, (i // cols) * cell
        if p.exists():
            sheet.paste(Image.open(p).convert("RGB").resize((cell - 6, cell - 6), Image.LANCZOS), (x + 3, y + 3))
        g.rectangle((x, y, x + cell - 1, y + cell - 1), outline=(200, 200, 200))
        g.rectangle((x + 3, y + 3, x + 12 + 7 * len(lab), y + 17), fill=(255, 255, 255))
        g.text((x + 6, y + 5), lab, fill=(200, 0, 0))
    return sheet


def cmd_sheets(args):
    out = DIR / "sheets"
    out.mkdir(parents=True, exist_ok=True)
    for cond in ID.conditions("god"):
        paths = [RUN / cond / "god" / f"s{i}.png" for i in range(ID.n_seeds("god"))]
        numbered_grid(paths, 4, 300, [f"{i + 1} s{i}" for i in range(len(paths))]).save(out / f"god_{cond}.png")
    for key in ID.IDEA_KEYS + ID.WORD_KEYS:
        conds = [c for c in ID.conditions(key) if not c.startswith(("text-zero", "unet-zero"))]
        paths, labs = [], []
        for i in range(ID.n_seeds(key)):
            for c in conds:
                paths.append(RUN / c / key / f"s{i}.png")
                labs.append(f"s{i} {c.replace('-noise@', ' x')}" if c != "intact" else f"s{i} intact")
        numbered_grid(paths, len(conds), 150, labs).save(out / f"overview_{key}.png")
    print(f"wrote sheets to {out}")


def cmd_pick(args):
    cls = load_cls()["intact"]
    picks = {k: ID.medoid(cls[k]) for k in ID.IDEA_KEYS + ID.WORD_KEYS if k in cls}
    (DIR / "picks.json").write_text(json.dumps({"rule": "intact DINOv2 medoid (plato_ideas_damage.medoid)",
                                                "picks": picks}, indent=1) + "\n")
    print(json.dumps(picks))


# ---------- statistics ----------

def load_rows() -> list[dict]:
    """One row per picture: key, seed, condition, severity, Glimmer's answers, God's by-eye features."""
    cls = load_cls()
    glim = {}
    for f in LABELS.glob("*.json"):
        d = json.loads(f.read_text())
        for it in d["items"]:
            glim[(d["condition"], it["key"], it["seed_index"])] = it
    eye = json.loads(EYE.read_text()) if EYE.exists() else None
    rows = []
    for cond, by in cls.items():
        fam, dose = parse_condition(cond)
        for key, x in by.items():
            x0 = cls["intact"][key]
            u, u0 = x / np.linalg.norm(x, axis=1, keepdims=True), x0 / np.linalg.norm(x0, axis=1, keepdims=True)
            d = 1.0 - (u * u0).sum(1)  # d_intact: cosine distance to the same seed's intact picture
            for i in range(len(x)):
                g = glim.get((cond, key, i), {})
                r = {"key": key, "seed_index": i, "cond": cond, "family": fam, "dose": dose, "d_intact": float(d[i]),
                     "emblem": g.get("emblem"), "name": g.get("name"),
                     "p_person": g.get("p_person"), "p_clean": g.get("p_clean"),
                     "p_beard": g.get("p_beard"), "p_halo": g.get("p_halo")}
                for f in ("person", "beard", "halo"):
                    p = r[f"p_{f}"]
                    r[f] = None if p is None else bool(p > 0.5)
                if key == "god" and eye:
                    e = eye["features"].get(cond, {}).get(f"s{i}")
                    if e is not None:
                        r["eye"] = {f: bool(e[f]) for f in ID.GOD_FEATURES}
                rows.append(r)
    by_unit = {(r["key"], r["seed_index"]): r for r in rows if r["cond"] == "intact"}
    for r in rows:
        t = by_unit[(r["key"], r["seed_index"])]
        listed = LISTED(r["key"])
        r["intact_emblem"] = t["emblem"]
        r["same_emblem"] = (None if t["emblem"] not in listed or r["emblem"] is None
                            else float(r["emblem"] == t["emblem"]))
        r["intact_person"] = t["person"]
    return rows


def matrix(rows, family, measure, units, intact_measure=None):
    """(units, doses) of a measure under a family, as a change from the unit's intact value."""
    doses = sorted({r["dose"] for r in rows if r["family"] == family})
    idx = {u: i for i, u in enumerate(units)}
    m = np.full((len(units), len(doses)), np.nan)
    base = {(r["key"], r["seed_index"]): r for r in rows if r["cond"] == "intact"}
    for r in rows:
        u = (r["key"], r["seed_index"])
        if r["family"] != family or u not in idx:
            continue
        v = r[measure] if not callable(measure) else measure(r)
        b = base[u][measure] if not callable(measure) else measure(base[u])
        if v is None or b is None:
            continue
        m[idx[u], doses.index(r["dose"])] = float(v) - (0.0 if intact_measure == "zero" else float(b))
    return m, doses


def contrast(rows, units, measure, rng, reps=4000, intact_measure=None, pair=(LANG, DRAW), groups=True):
    da, _ = matrix(rows, pair[0], "d_intact", units, "zero")
    db, _ = matrix(rows, pair[1], "d_intact", units, "zero")
    va, _ = matrix(rows, pair[0], measure, units, intact_measure)
    vb, _ = matrix(rows, pair[1], measure, units, intact_measure)
    ok = np.isfinite(va).all(1) & np.isfinite(vb).all(1)
    r1 = boot_matched_contrast(da[ok], va[ok], db[ok], vb[ok], reps=reps, rng=rng)
    out = {"difference": r1["estimate"], "ci95": r1["ci95"], "targets": r1["targets"], "n_units": r1["n_units"],
           "language": float(np.mean(at_severity(da[ok].mean(0), va[ok].mean(0), r1["targets"]))),
           "drawing": float(np.mean(at_severity(db[ok].mean(0), vb[ok].mean(0), r1["targets"])))}
    if groups:
        g = np.array([u[0] for u, k in zip(units, ok) if k])
        if len(set(g)) > 1:
            out["ci95_by_key"] = boot_matched_contrast(da[ok], va[ok], db[ok], vb[ok], reps=reps // 2, rng=rng,
                                                       groups=g)["ci95"]
    return out


def rates(rows, key, family, features, source="glimmer"):
    """Per dose (intact first) the share of the key's pictures with each feature."""
    doses = [0.0] + sorted({r["dose"] for r in rows if r["family"] == family and r["key"] == key})
    out = {f: [] for f in features}
    for d in doses:
        sel = [r for r in rows if r["key"] == key and ((r["family"] == family and r["dose"] == d) or
                                                     (d == 0.0 and r["cond"] == "intact"))]
        for f in features:
            if f == "generic":
                vals = [ID.generic_person(*(feat(r, x, source) for x in ID.GOD_FEATURES)) for r in sel]
            else:
                vals = [feat(r, f, source) for r in sel]
            vals = [v for v in vals if v is not None]
            out[f].append(float(np.mean(vals)) if vals else None)
    return {"doses": doses, **out}


def feat(r, f, source):
    if source == "eye":
        return (r.get("eye") or {}).get(f)
    return r.get(f)


def god_tests(rows, source) -> dict:
    out = {}
    feats = list(ID.GOD_FEATURES) + ["generic"]
    for fam in ("text-noise", "unet-noise", "text-zero", "unet-zero"):
        out[fam] = rates(rows, "god", fam, feats, source)
    intact = {f: out["text-noise"][f][0] for f in feats}
    n = sum(1 for r in rows if r["key"] == "god" and r["cond"] == "intact")
    out["D1"] = {f: round(intact[f] * n) for f in ID.GOD_FEATURES}
    out["D1"]["n"] = n
    out["D1"]["passes"] = {"a_person_ge_12": out["D1"]["person"] >= 12, "b_beard_ge_8": out["D1"]["beard"] >= 8,
                           "c_halo_le_12": out["D1"]["halo"] <= 12}
    for fam in ("text-noise", "text-zero", "unet-noise", "unet-zero"):
        r = out[fam]
        ff = ID.fails_first({f: r[f][1:] for f in ID.GOD_FEATURES}, {f: r[f][0] for f in ID.GOD_FEATURES})
        emb = [ff[f] for f in ("beard", "halo") if ff[f] is not None]
        first = min(emb) if emb else None
        sup = first is not None and (ff["person"] is None or first < ff["person"])
        r["fails_first"] = ff
        r["emblem_before_figure"] = bool(sup)
        r["generic_peak_rise"] = (max(v for v in r["generic"][1:] if v is not None) - r["generic"][0]
                                  if any(v is not None for v in r["generic"][1:]) else None)
    out["D2"] = {"primary": out["text-noise"]["emblem_before_figure"], "secondary_zero": out["text-zero"]["emblem_before_figure"]}
    lr, dr = out["text-noise"]["generic_peak_rise"], out["unet-noise"]["generic_peak_rise"]
    out["D3"] = {"language_rise": lr, "drawing_rise": dr, "passes": bool(lr is not None and dr is not None and lr >= 0.25 and lr > dr)}
    return out


def cmd_stats(args):
    rng = np.random.default_rng(20261028)
    rows = load_rows()
    keys = ID.IDEA_KEYS + ID.WORD_KEYS
    labelled = all(r["emblem"] is not None for r in rows)
    res = {"plan": "docs/plato_ideas_damage_plan.md", "n_pictures": len(rows), "labelled": labelled,
           "conditions": sorted({r["cond"] for r in rows}, key=lambda c: (c != "intact", parse_condition(c)))}
    # severity curves per family (mean d_intact per dose), over all keys and for God
    sev = {}
    for fam in ("text-noise", "unet-noise", "text-zero", "unet-zero"):
        for scope, sel in (("all", lambda r: True), ("god", lambda r: r["key"] == "god")):
            pts = {}
            for r in rows:
                if r["family"] == fam and sel(r):
                    pts.setdefault(r["dose"], []).append(r["d_intact"])
            if pts:
                sev.setdefault(fam, {})[scope] = {f"{d:g}": float(np.mean(v)) for d, v in sorted(pts.items())}
    res["severity"] = sev
    if labelled:
        units = sorted({(r["key"], r["seed_index"]) for r in rows})
        listed_units = [u for u in units if next(r for r in rows if r["cond"] == "intact" and (r["key"], r["seed_index"]) == u)["emblem"]
                        in LISTED(u[0])]
        noperson = [u for u in units if not next(r for r in rows if r["cond"] == "intact" and (r["key"], r["seed_index"]) == u)["person"]]
        res["D4"] = contrast(rows, listed_units, "same_emblem", rng)
        res["D4"]["passes"] = bool(res["D4"]["ci95"][1] < 0)
        res["D5"] = contrast(rows, units, "p_clean", rng)
        res["D5"]["passes"] = bool(res["D5"]["ci95"][0] > 0)
        res["D6"] = contrast(rows, noperson, "person", rng, intact_measure="zero")
        res["D6"]["passes"] = bool(res["D6"]["ci95"][0] > 0)
        god_units = [u for u in units if u[0] == "god"]
        bearded = lambda r: None if r["emblem"] is None else float(r["emblem"] == "bearded man")  # noqa: E731
        res["god_bearded"] = {m: contrast(rows, god_units, bearded, rng, groups=False, pair=ID.PAIRS[m])
                              for m in ("noise", "zero")}
        res["god"] = {"glimmer": god_tests(rows, "glimmer")}
        # per key and family: emblem kept, person, clean, by dose; the names at the strongest doses
        per_key = {}
        for key in keys:
            kr = [r for r in rows if r["key"] == key]
            entry = {"intact_emblems": dict(Counter(r["emblem"] for r in kr if r["cond"] == "intact").most_common())}
            for fam in ("text-noise", "unet-noise") + (("text-zero", "unet-zero") if key == "god" else ()):
                doses = sorted({r["dose"] for r in kr if r["family"] == fam})
                entry[fam] = {
                    "doses": doses,
                    "same_emblem": [_mean([r["same_emblem"] for r in kr if r["family"] == fam and r["dose"] == d]) for d in doses],
                    "person": [_mean([r["person"] for r in kr if r["family"] == fam and r["dose"] == d]) for d in doses],
                    "clean": [_mean([r["p_clean"] for r in kr if r["family"] == fam and r["dose"] == d]) for d in doses],
                    "d_intact": [_mean([r["d_intact"] for r in kr if r["family"] == fam and r["dose"] == d]) for d in doses],
                    "names_top_dose": Counter(_short(r["name"]) for r in kr if r["family"] == fam and r["dose"] == doses[-1]).most_common(6),
                }
            entry["intact"] = {"person": _mean([r["person"] for r in kr if r["cond"] == "intact"]),
                               "clean": _mean([r["p_clean"] for r in kr if r["cond"] == "intact"]),
                               "names": Counter(_short(r["name"]) for r in kr if r["cond"] == "intact").most_common(6)}
            per_key[key] = entry
        res["per_key"] = per_key
    if EYE.exists():
        eye = json.loads(EYE.read_text())
        res["god_by_eye_sha256"] = hashlib.sha256(EYE.read_bytes()).hexdigest()
        res.setdefault("god", {})["by_eye"] = god_tests(rows, "eye")
        if labelled:
            agree = {}
            for f in ID.GOD_FEATURES:
                pairs = [(r[f], r["eye"][f]) for r in rows if r["key"] == "god" and r.get("eye") and r[f] is not None]
                agree[f] = {"n": len(pairs), "agreement": float(np.mean([a == b for a, b in pairs])),
                            "kappa": I.cohen_kappa([str(a) for a, _ in pairs], [str(b) for _, b in pairs])}
            res["god_agreement"] = agree
        res["god_by_eye_notes"] = eye.get("notes", {})
    (DIR / "results.json").write_text(json.dumps(plato.to_jsonable(res), indent=1))
    show = {k: v for k, v in res.items() if k not in ("per_key",)}
    print(json.dumps(plato.to_jsonable(show), indent=1)[:12000])


def _mean(v):
    v = [float(x) for x in v if x is not None]
    return float(np.mean(v)) if v else None


def _short(name):
    return (name or "").strip().strip(".").lower()[:40]


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("crop").set_defaults(fn=cmd_crop)
    p = sub.add_parser("embed")
    p.add_argument("--device")
    p.set_defaults(fn=cmd_embed)
    sub.add_parser("sheets").set_defaults(fn=cmd_sheets)
    sub.add_parser("pick").set_defaults(fn=cmd_pick)
    sub.add_parser("stats").set_defaults(fn=cmd_stats)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
