"""Plato's Chair, damage: export the web page's data and pictures (on the Mac, after the analysis).

  python scripts/plato_damage_web.py [--run main] [--clocks clocks]

Writes metalesionlab/web/data/plato_damage.json (derived statistics only), public_data/plato_damage.json
(the same numbers without picture paths) and small WebP pictures for the damage slider and the clock
strip in metalesionlab/web/static/img/plato_damage/ (kept under 2 MB in all).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from metalesionlab.plato import to_jsonable  # noqa: E402
from metalesionlab.plato_damage import BY_KEY, clean_name, parse_condition  # noqa: E402
from plato_damage_analyze import DAMAGE_DIR, conditions_in  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
WEB = REPO / "metalesionlab" / "web"
IMG = WEB / "static" / "img" / "plato_damage"
URL = "/static/img/plato_damage/"
METHODS = {"noise": ("text-noise", "unet-noise"), "zero": ("text-zero", "unet-zero")}
CREDITS = ["Drawer: Stable Diffusion XL base 1.0 (Stability AI), CreativeML OpenRAIL++-M",
           "Named-kind doodles: Meta Muse Image 1.0", "Readers: Meta Muse Glimmer 30B; clocks: Meta Muse Spark 1.3",
           "Similarity: Meta DINOv2 (facebook/dinov2-base, Apache-2.0)"]


def level_conditions(run: Path, family: str, n: int = 4) -> list[str]:
    d = sorted(parse_condition(c)[1] for c in conditions_in(run) if parse_condition(c)[0] == family)
    if len(d) > n:
        idx = np.unique(np.round(np.linspace(0, len(d) - 1, n)).astype(int))
        d = [d[i] for i in idx]
    return ["intact"] + [f"{family}@{x:g}" for x in d]


def dose_label(cond: str) -> str:
    fam, dose = parse_condition(cond)
    if fam == "intact":
        return "intact"
    if fam.endswith("zero"):
        return f"{dose * 100:g}% of neurons off"
    return f"noise × {dose:g}"


def save_webp(src: Path, out: Path, side: int, quality: int = 72) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(src).convert("RGB")
    im.thumbnail((side, side), Image.LANCZOS)
    im.save(out, "WEBP", quality=quality, method=6)


def slider(run: Path, rows: list[dict], kinds: list[tuple[str, int]], side: int) -> dict:
    by = {(r["condition"], r["key"], r["seed_index"]): r for r in rows}
    out = {"kinds": [], "methods": {m: {"lang": a, "draw": b} for m, (a, b) in METHODS.items()}, "levels": {},
           "pictures": {}}
    fams = [f for pair in METHODS.values() for f in pair]
    for fam in fams:
        out["levels"][fam] = [{"cond": c, "label": dose_label(c)} for c in level_conditions(run, fam)]
    for key, seed in kinds:
        p = BY_KEY[key]
        out["kinds"].append({"key": key, "label": p.kind.removeprefix("a ").removeprefix("an "), "seed": seed})
        out["pictures"][key] = {}
        for fam in fams:
            seq = []
            for i, lev in enumerate(out["levels"][fam]):
                c = lev["cond"]
                name = f"{key.split('__')[1]}_{fam}_{i}.webp" if c != "intact" else f"{key.split('__')[1]}_intact.webp"
                save_webp(run / c / key / f"s{seed}.png", IMG / name, side)
                r = by.get((c, key, seed), {})
                seq.append({"img": URL + name, "change": r.get("d_intact"), "outcome": r.get("outcome"),
                            "name": " ".join(clean_name(r.get("said")).split()[:3]) if r.get("said") else None})
            out["pictures"][key][fam] = seq
    return out


def curves(res: dict, concept: str = "chair") -> dict:
    out = {}
    for row in res["concepts"][concept]["table_named"]:
        fam = row["family"]
        if fam == "intact":
            continue
        pt = {"dose": row["dose"], "n": row["n"]}
        for k in ("d_intact", "delta_correct", "is_plain", "is_cant", "delta_p_clean", "delta_p_is_a", "delta_d_proto",
                  "delta_drift", "midtone", "colorfulness"):
            if k in row:
                pt[k] = row[k]["mean"]
                pt[k + "_ci"] = row[k]["ci95"]
        if "names" in row:
            pt["names"] = row["names"]
        out.setdefault(fam, []).append(pt)
    return out


def finite(obj):
    """NaN and infinity become None: browsers' JSON has no NaN (FastAPI refuses to send it)."""
    import math

    if isinstance(obj, dict):
        return {k: finite(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [finite(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def clock_table(cr: dict) -> dict:
    """Rows for the page's clock table: intact and each family's doses, the share of clocks with each feature."""
    feats = ["clock", "contour", "numbers_ok", "two_hands", "numbers_given_clock"]
    names = {"clock": "a clock", "contour": "outline", "numbers_ok": "12 numbers in order", "two_hands": "two hands",
             "numbers_given_clock": "numbers, among clocks"}
    rows = []
    for cond, row in cr["conditions"].items():
        fam, dose = parse_condition(cond)
        label = "intact" if fam == "intact" else (("language" if fam.startswith("text") else "drawing") + ", "
                                                  + dose_label(cond))
        rows.append({"cond": cond, "label": label, "values": [row[f]["mean"] if row[f]["n"] else None for f in feats],
                     "n": row["n"]})
    b = cr["intact_1010_bias"]
    n_o = b["n_other"]
    summary = [f"Intact SDXL, asked for a time other than 10:10, drew hands at 10:10 on "
               f"{round(b['share_showing_1010_when_asked_other']['mean'] * n_o)} of {n_o} clocks and the asked time on "
               f"{round(b['share_right_time_when_asked_other']['mean'] * n_o)}. It cannot set a clock, so the asked time "
               f"could not fail under damage.",
               "Drawing damage strips the numbers first: at the mildest dose the outline survives but 12 numbers in "
               "order fall from {:.0f}% to {:.0f}%.".format(cr["conditions"]["intact"]["numbers_ok"]["mean"] * 100,
                                                             cr["conditions"]["unet-zero@0.1"]["numbers_ok"]["mean"] * 100),
               "Language damage removes the whole clock instead (a portrait, a robot, a street), and the clocks it still "
               "draws keep their numbers at the intact rate."]
    return {"features": rows, "feature_names": [names[f] for f in feats], "summary": summary}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="main")
    ap.add_argument("--clocks", default="clocks")
    ap.add_argument("--kinds", nargs="*", default=["chair__rocking_chair:1", "chair__wheelchair:2", "chair__throne:0",
                                                   "chair__high_chair:0"])
    ap.add_argument("--side", type=int, default=256)
    ap.add_argument("--status", help="JSON object of parts still pending, shown on the page")
    args = ap.parse_args()
    run = DAMAGE_DIR / args.run
    res = json.loads((DAMAGE_DIR / f"results_{args.run}.json").read_text())
    rows = json.loads((run / "measures_labeled.json").read_text())
    kinds = [(k.split(":")[0], int(k.split(":")[1])) for k in args.kinds]
    data = {"slider": slider(run, rows, kinds, args.side), "curves": curves(res),
            "matched": res["concepts"]["chair"]["matched"], "pooled": res["concepts"]["chair"]["pooled"],
            "names": res["concepts"]["chair"]["names"],
            "generality": {c: res["concepts"][c]["matched"] for c in res["concepts"] if c != "chair"},
            "targeted": res["concepts"]["chair"].get("targeted_vs_random"), "credits": CREDITS}
    arm = DAMAGE_DIR / "results_glimmer_arm.json"
    if arm.exists():
        data["glimmer"] = json.loads(arm.read_text())
    clocks_res = DAMAGE_DIR / "results_clocks.json"
    if clocks_res.exists():
        cr = json.loads(clocks_res.read_text())
        data["clocks"] = {k: v for k, v in cr.items() if k != "pictures"}
        crun = DAMAGE_DIR / args.clocks
        strip = {}
        for method, fams in METHODS.items():
            for fam in fams:
                conds = level_conditions(crun, fam, 3)
                for t in ("3_00", "8_45"):
                    seq = []
                    for i, c in enumerate(conds):
                        name = f"clock_{t}_{fam}_{i}.webp" if c != "intact" else f"clock_{t}_intact.webp"
                        src = crun / c / f"clock__{t}" / "s0.png"
                        if src.exists():
                            save_webp(src, IMG / name, 180, quality=70)
                            seq.append({"img": URL + name, "label": dose_label(c)})
                    strip.setdefault(fam, {})[t] = seq
        data["clocks"]["strip"] = strip
        data["clocks"].update(clock_table(cr))
    janus = DAMAGE_DIR / "results_janus.json"
    if janus.exists():
        data["janus"] = json.loads(janus.read_text())
        jdir, seq = DAMAGE_DIR / "janus_draw", []
        for c in sorted(data["janus"].get("draw", {}), key=lambda c: data["janus"]["draw"][c]["dose"]):
            src = jdir / c / "chair__wheelchair" / "s0.png"
            if src.exists():
                name = f"janus_wheelchair_{c.replace('@', '_')}.webp"
                save_webp(src, IMG / name, 200, quality=72)
                seq.append({"img": URL + name, "dose": data["janus"]["draw"][c]["dose"]})
        data["janus"]["strip"] = seq
        rd, dr = data["janus"].get("read", {}), data["janus"].get("draw", {})
        if "lm-zero@0.35" in rd and "lm-zero@0.35" in dr and "intact" in rd and "intact" in dr:
            data["janus"]["summary"] = (
                "The same damage takes both, reading first. With 35% of its language neurons off, Janus reads the right "
                f"kind for {rd['lm-zero@0.35']['correct']['mean'] * 100:.0f}% of doodles (intact "
                f"{rd['intact']['correct']['mean'] * 100:.0f}%) and draws the asked kind "
                f"{dr['lm-zero@0.35']['kind_kept']['mean'] * 100:.0f}% of the time (intact "
                f"{dr['intact']['kind_kept']['mean'] * 100:.0f}%). Its wheelchair becomes a tricycle, then a car.")
    if args.status:
        data["status"] = json.loads(args.status)
    data = finite(to_jsonable(data))
    (WEB / "data").mkdir(parents=True, exist_ok=True)
    (WEB / "data" / "plato_damage.json").write_text(json.dumps(data, separators=(",", ":")))
    public = {k: v for k, v in data.items() if k != "slider"}
    public["note"] = ("Derived statistics from the Plato's Chair damage experiment (docs/plato_damage.md). No pictures. "
                      "SDXL: Stability AI, CreativeML OpenRAIL++-M.")
    (REPO / "public_data" / "plato_damage.json").write_text(json.dumps(public, indent=1))
    size = sum(f.stat().st_size for f in IMG.glob("*.webp"))
    print(f"web data -> {WEB / 'data' / 'plato_damage.json'} ({(WEB / 'data' / 'plato_damage.json').stat().st_size / 1e3:.0f} kB); "
          f"{len(list(IMG.glob('*.webp')))} pictures, {size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
