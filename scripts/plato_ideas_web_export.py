"""The invisible Forms, step 5: the data and small pictures the site needs (the draw pad and /plato/ideas).

Reads $PLATO_IDEAS_DIR (outside the repository): results.json (scripts/plato_ideas_analyze.py stats), the DINOv2
embeddings, the Glimmer labels and the pictures. Writes:

  metalesionlab/web/data/draw_ideas.json        the pad's ideas: per idea Muse's leave-one-out distances, each doodle's
                                                emblem label, the emblem counts and the sprite layout (AI only: no
                                                people's numbers exist for these ideas)
  metalesionlab/web/data/draw/<key>.json        server only: Muse's centroid and unit vectors (int8)
  metalesionlab/web/static/img/draw/<key>_muse.webp      the pad's thumbnail sprite, ink-cropped as DINOv2 saw it
  metalesionlab/web/static/img/plato_ideas/<key>.webp    the page's larger sprite, the whole doodle as Muse drew it
  metalesionlab/web/data/plato_ideas.json       the findings page: statistics, tests, emblem counts, things' spreads
  metalesionlab/web/data/series/ideas.json      the series card's finding
  public_data/plato_ideas.json                  statistics only, no pictures

and, outside the repository, $PLATO_IDEAS_DIR/social/: a 4 x 4 grid of Muse's 16 drawings of God and a few
single drawings, candidates for posts. No network, no API calls.

    python scripts/plato_ideas_web_export.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from draw_export import loo_distances, sprite  # noqa: E402  the pad's own sprite and distance code

from metalesionlab import plato  # noqa: E402
from metalesionlab import plato_ideas as I  # noqa: E402
from metalesionlab.draw import pack, pack_int8, unit  # noqa: E402

WEB = REPO / "metalesionlab" / "web"
PAD_OUT = WEB / "data" / "draw_ideas.json"
VEC_DIR = WEB / "data" / "draw"
PAD_IMG = WEB / "static" / "img" / "draw"
PAGE_IMG = WEB / "static" / "img" / "plato_ideas"
PAGE_OUT = WEB / "data" / "plato_ideas.json"
SERIES_OUT = WEB / "data" / "series" / "ideas.json"
PUBLIC_OUT = REPO / "public_data" / "plato_ideas.json"
# The pad lists God first (the brief), then the ideas a visitor is most likely to try.
PAD_ORDER = ["god", "love", "time", "death", "justice", "beauty", "the_good", "the_soul", "freedom", "happiness", "truth"]
SOCIAL = ["c1_2", "c2_1", "c3_3"]  # God drawings picked by eye for posts: a radiant halo, rays, a ringed halo
CREDITS = ["AI drawings: Meta Muse Image (muse-image-1.0), the same doodle prompt as the things",
           "Emblem labels: Meta Muse Glimmer 30B, run on our own GPU",
           "Embeddings: Meta DINOv2 (facebook/dinov2-base, Apache-2.0)"]


def page_sprite(files: list[Path], cell: int, cols: int, out: Path) -> dict:
    """The whole doodle as Muse drew it (no ink crop), downscaled, on white: for the page, not for scoring."""
    rows = -(-len(files) // cols)
    sheet = Image.new("L", (cols * cell, rows * cell), 255)
    for i, f in enumerate(files):
        tile = Image.open(f).convert("L").resize((cell, cell), Image.LANCZOS)
        sheet.paste(tile, ((i % cols) * cell, (i // cols) * cell))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, "WEBP", quality=80, method=6)
    return {"src": f"/static/img/plato_ideas/{out.name}", "cell": cell, "cols": cols, "n": len(files),
            "bytes": out.stat().st_size}


def r4(a):
    return [round(float(v), 4) for v in a]


def main() -> None:
    res = json.loads((I.IDEAS_DIR / "results.json").read_text())
    by_key = {r["key"]: r for r in res["ideas"]}
    s = res["summary"]
    pad, page_ideas = [], []
    for key in PAD_ORDER:
        idea, r = I.BY_KEY[key], by_key[key]
        z = np.load(I.IDEAS_DIR / "embeddings" / "ai_doodle" / f"{key}.npz")
        files = [str(f) for f in z["files"]]
        if files != r["files"]:
            raise SystemExit(f"{key}: embeddings and results list different pictures")
        ai = unit(z["cls"].astype(np.float64))
        g = r["glimmer"]
        shorts, names = g["labels"], g["names"]
        emblems = [I.display(sh, nm) for sh, nm in zip(shorts, names)]
        counts = {}
        for sh in shorts:
            counts[sh] = counts.get(sh, 0) + 1
        emblem_counts = [[I.display(k) if k not in ("something else", "can't tell") else k, v]
                         for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
        (VEC_DIR / f"{key}.json").write_text(json.dumps({
            "key": key, "model": plato.DINO_MODEL, "embedding": "CLS, unit length", "mode": "ai_only",
            "ai_centroid": pack(ai.mean(0)), "ai": pack_int8(ai)}, separators=(",", ":")) + "\n")
        folder = I.folder(key)
        pics = [folder / f for f in files]
        pad_sprite = sprite(pics, cell=112, cols=8, out=PAD_IMG / f"{key}_muse.webp")
        big = page_sprite(pics, cell=320 if key == "god" else 224, cols=8, out=PAGE_IMG / f"{key}.webp")
        top = {"emblem": I.display(g["top"]), "short": g["top"], "n": g["top_n"], "share": g["share"],
               "share_ci95": g["share_ci95"]}
        pad.append({
            "key": key, "label": idea.label, "phrase": idea.phrase, "idea_group": idea.group, "n_ai": len(files),
            "vectors": f"draw/{key}.json", "prompt": r["prompt"],
            "ai_loo": r4(loo_distances(ai)), "ai_to_ai": r4(1.0 - ai @ unit(ai.mean(0))),
            "emblems": emblems, "emblem_counts": emblem_counts, "top": top,
            "spread": r["spread"]["spread"], "sprites": {"muse": pad_sprite},
        })
        eye = r["by_eye"]
        page_ideas.append({
            "key": key, "label": idea.label, "phrase": idea.phrase, "group": idea.group, "n": r["n"],
            "prompt": r["prompt"], "predicted": I.display(idea.predicted), "predicted_short": idea.predicted,
            "top": top, "emblem_counts": emblem_counts, "emblems": emblems,
            "effective_emblems": g["effective_emblems"], "names": names,
            "spread": r["spread"]["spread"], "spread_ci95": r["spread"]["spread_ci95"], "pixel_spread": r["pixel_spread"],
            "by_eye": {"top": I.display(eye["top"]), "short": eye["top"], "n": eye["top_n"], "share": eye["share"],
                       "counts": [[I.display(k), v] for k, v in eye["counts"].items()]},
            "agreement": r["agreement"], "refused": r["refusals"]["refused"], "attempts": r["refusals"]["attempts"],
            "sprite": big, "pad_sprite": pad_sprite,
            **({"human_like": r["human_like"]} if "human_like" in r else {}),
        })
        print(f"{key:10s} top {top['emblem']!r} {top['n']}/16; spread {r['spread']['spread']:.3f}; "
              f"sprites {pad_sprite['bytes'] // 1024} + {big['bytes'] // 1024} KB")

    eye_file = json.loads((I.IDEAS_DIR / "labels_by_eye.json").read_text())
    things = sorted(res["things"], key=lambda t: t["spread"])
    page = {
        "about": "The invisible Forms: Muse Image's doodles of 11 abstract ideas. Written by scripts/plato_ideas_web_export.py.",
        "plan": "docs/plato_ideas_plan.md", "writeup": "docs/plato_ideas.md",
        "prompt_template": plato.STYLES["doodle"].format(phrase="{God}"),
        "summary": {k: s[k] for k in ("n_ideas", "pictures", "refused_attempts", "attempts", "H1", "H2", "H3_vs_atlas",
                                      "H3_vs_pad", "E1_concentration_vs_spread", "E4_pixels", "label_check",
                                      "text_in_pictures")},
        "present": eye_file["present"],
        "ideas": page_ideas,
        "things": [{"key": t["key"], "label": t["label"], "spread": t["spread"], "pad": t["pad"]} for t in things],
        "lausanne": {
            "cite": "Brandt, Dandarova-Robert, Dessart, Muthert & Schaap-Jonker (2023). Integrative Model of Children’s "
                    "Representations of God in Drawings. In When Children Draw Gods (Springer, open access), ch. 2.",
            "url": "https://doi.org/10.1007/978-3-030-94429-2_2", "project": "https://ddd.unil.ch",
            "anthropomorphic_share": 0.876, "n": 532, "ages": "5–17",
        },
        "credits": CREDITS,
    }
    PAGE_OUT.write_text(json.dumps(plato.to_jsonable(page), ensure_ascii=False, separators=(",", ":")) + "\n")

    PAD_OUT.write_text(json.dumps(plato.to_jsonable({
        "about": "Draw the invisible: Muse Image's doodles of 11 abstract ideas, for placing a visitor's drawing among "
                 "them. AI only: Quick, Draw! has no people's drawings of these ideas. Written by "
                 "scripts/plato_ideas_web_export.py.",
        "model": plato.DINO_MODEL, "embedding": "CLS token", "distance": "cosine",
        "groups": [{"id": "things", "label": "Or draw:"},
                   {"id": "ideas", "label": "Draw the invisible:",
                    "note": "No one has drawn these for Quick, Draw!, so a drawing is compared with Muse Image's 16 only."}],
        "credits": CREDITS, "concepts": pad}), ensure_ascii=False, separators=(",", ":")) + "\n")

    god = next(p for p in page_ideas if p["key"] == "god")
    full = sum(p["top"]["n"] == p["n"] for p in page_ideas)
    SERIES_OUT.write_text(json.dumps({"finding": (
        f"Asked to draw God, Meta’s Muse Image drew the same bearded figure with a halo {god['top']['n']} times out of "
        f"{god['n']}. Love was a heart and death a hooded reaper every time; for "
        f"{s['H1']['ideas_with_concentration_at_least_half']} of {s['H1']['of']} ideas, one emblem filled at least half "
        f"the drawings.")}, ensure_ascii=False) + "\n")

    PUBLIC_OUT.write_text(json.dumps(plato.to_jsonable({
        "experiment": "The invisible Forms", "plan": "docs/plato_ideas_plan.md", "writeup": "docs/plato_ideas.md",
        "license": "statistics only: no drawings and no embeddings",
        "summary": page["summary"],
        "ideas": [{k: p[k] for k in ("key", "label", "group", "n", "prompt", "predicted", "top", "emblem_counts",
                                      "spread", "spread_ci95", "pixel_spread", "by_eye", "agreement", "refused",
                                      "attempts")} for p in page_ideas],
        "credits": CREDITS}), ensure_ascii=False, indent=1) + "\n")

    social = I.IDEAS_DIR / "social"
    social.mkdir(exist_ok=True)
    gf = [I.folder("god") / f for f in by_key["god"]["files"]]
    grid = plato.grid([Image.open(f) for f in gf], cols=4, cell=512, gap=16)
    grid.save(social / "god_16_grid.png")
    for stem in SOCIAL:
        shutil.copy(I.folder("god") / f"{stem}.png", social / f"god_{stem}.png")
    total = sum(p.stat().st_size for p in [PAD_OUT, PAGE_OUT] + list(PAGE_IMG.glob("*.webp")))
    print(f"wrote {PAD_OUT.name}, {PAGE_OUT.name}, {SERIES_OUT.name}, {PUBLIC_OUT.name}; page data and pictures "
          f"{total / 1e6:.2f} MB; social candidates in {social}")


if __name__ == "__main__":
    main()
