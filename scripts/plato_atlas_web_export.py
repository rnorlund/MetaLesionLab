"""The Atlas of Forms, step 5: the /plato/atlas page's data and pictures (and the figures for the write-up).

Usage: python -I scripts/plato_atlas_web_export.py [--figures]
(after plato_atlas_analyze.py pixels and stats)

Writes
- metalesionlab/web/data/plato_atlas.json: per concept the statistics the page shows (no pictures, no
  embeddings), the summary, the predictors, and picture names;
- metalesionlab/web/static/img/plato_atlas/<slug>-f{m,p,s}.webp: the pixel-average Forms of Muse's, people's
  and SDXL's 12 pictures (FORM_PX square, grayscale WebP);
- metalesionlab/web/static/img/plato_atlas/<slug>-t{m,p}.webp: the 12 ink-cropped pictures behind each Form,
  6 x 2 cells of TILE_PX, loaded only when a card is opened. One flat folder (package data globs are shallow).
- with --figures: $PLATO_ATLAS_DIR/figures/atlas_forms.png (a wall of Forms) and atlas_rank.png.
Human drawings: Google Quick, Draw! (CC BY 4.0); the 12 shown are a seeded random 12 of the 200.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from metalesionlab import plato_atlas as A  # noqa: E402
from metalesionlab.plato import QUICKDRAW_CREDIT, to_jsonable  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
WEB = REPO / "metalesionlab" / "web"
IMG = WEB / "static" / "img" / "plato_atlas"
DATA = WEB / "data" / "plato_atlas.json"
FORMS = A.ATLAS_DIR / "forms"
FORM_PX, TILE_PX, GAP = 152, 80, 2
SOURCES = {"muse": "m", "people": "p", "sdxl": "s"}


def save_webp(img: Image.Image, path: Path, quality: int) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "WEBP", quality=quality, method=6)
    return path.stat().st_size


def form_image(key: str, source: str) -> Image.Image | None:
    p = FORMS / f"{key}_{source}.png"
    return Image.open(p).convert("L").resize((FORM_PX, FORM_PX), Image.LANCZOS) if p.exists() else None


def tile_sheet(key: str, source: str, cols: int = 6) -> Image.Image | None:
    p = FORMS / f"{key}_{source}_tiles.png"
    if not p.exists():
        return None
    strip = Image.open(p).convert("L")
    side = strip.height
    n = strip.width // side
    rows = (n + cols - 1) // cols
    sheet = Image.new("L", (cols * TILE_PX + (cols - 1) * GAP, rows * TILE_PX + (rows - 1) * GAP), 236)
    for i in range(n):
        tile = strip.crop((i * side, 0, (i + 1) * side, side)).resize((TILE_PX, TILE_PX), Image.LANCZOS)
        sheet.paste(tile, ((i % cols) * (TILE_PX + GAP), (i // cols) * (TILE_PX + GAP)))
    return sheet


def r3(x):
    return None if x is None else round(float(x), 3)


def export(res: dict, pix: dict) -> dict:
    sizes = {"forms": 0, "tiles": 0}
    concepts = []
    for r in sorted(res["concepts"], key=lambda r: r["rank"]):
        c = A.BY_KEY[r["key"]]
        slug = A.slug(c.key)
        imgs = {}
        for source, tag in SOURCES.items():
            f = form_image(c.key, source)
            if f is not None:
                sizes["forms"] += save_webp(f, IMG / f"{slug}-f{tag}.webp", 72)
                imgs[f"form_{source}"] = f"{slug}-f{tag}.webp"
            if source != "sdxl":
                t = tile_sheet(c.key, source)
                if t is not None:
                    sizes["tiles"] += save_webp(t, IMG / f"{slug}-t{tag}.webp", 52)
                    imgs[f"tiles_{source}"] = f"{slug}-t{tag}.webp"
        px = r.get("pixel") or {}
        concepts.append({
            "key": slug, "label": r["label"], "quickdraw": r["quickdraw"], "domain": r["domain"],
            "natural": r["natural"], "origin": r["origin"], "rank": r["rank"], "n_ai": r["n_ai"],
            "ratio": r3(r["ratio"]), "ci": [r3(v) for v in r["ratio_ci95"]],
            "muse_spread": r3(r["muse_spread"]), "human_spread": r3(r["human_spread"]),
            "sdxl_ratio": r3(r.get("sdxl_ratio")),
            "sdxl_ci": [r3(v) for v in r["sdxl_ratio_ci95"]] if r.get("sdxl_ratio_ci95") else None,
            "sdxl_spread": r3(r.get("sdxl_spread")), "n_sdxl": r.get("n_sdxl"),
            "pixel_ratio": r3(px.get("ratio")), "zipf": round(float(r["zipf"]), 2),
            "recognized": r3(r["muse_nearest_human_centroid_is_own"]),
            "people_sample": pix.get(r["key"], {}).get("people_sample"), **imgs})
    s = res["summary"]
    keep_pred = ("P1_muse_spread_vs_human_spread", "P1_ratio_vs_human_spread", "P2_ratio_vs_zipf",
                 "P2_muse_spread_vs_zipf", "P2_human_spread_vs_zipf", "P3_natural_minus_artifact_log_ratio",
                 "P3_median_ratio", "P4_ols_log_muse_spread", "sdxl_spread_vs_human_spread")
    out = {
        "about": "The Atlas of Forms: Muse Image's spread vs people's (Quick, Draw!) for 135 everyday things. "
                 "Statistics and picture names only.",
        "attribution": QUICKDRAW_CREDIT, "plan_commit": "376195c",
        "summary": {"n_concepts": s["n_concepts"], "n_new": s["n_new"], "all": s["all"], "new": s["new"],
                    "core": s["core"], "confirmatory": s["confirmatory_new_98"], "sdxl": s["sdxl"],
                    "muse_vs_sdxl": s["muse_vs_sdxl"], "robustness": s["robustness"],
                    "recognizability": s["recognizability"], "mean_spread": s["mean_spread"],
                    "domains": s["domains"], "above_1": s["above_1"]},
        "predictors": {k: s["predictors"][k] for k in keep_pred},
        "domains": A.DOMAINS,
        "concepts": concepts,
    }
    out["image_bytes"] = sizes
    return to_jsonable(out)


def figures(res: dict) -> None:
    """A wall of Forms (Muse above people) for the most and least Platonic things, and the ranking."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig_dir = A.ATLAS_DIR / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    rows = sorted(res["concepts"], key=lambda r: r["rank"])
    pick = rows[:8] + rows[-8:]
    fig, axes = plt.subplots(2, len(pick), figsize=(1.35 * len(pick), 3.3))
    for j, r in enumerate(pick):
        for i, source in enumerate(("muse", "people")):
            ax = axes[i, j]
            p = FORMS / f"{r['key']}_{source}.png"
            if p.exists():
                ax.imshow(np.asarray(Image.open(p).convert("L")), cmap="gray", vmin=0, vmax=255)
            ax.set_xticks([])
            ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_color("#1D4ED8" if source == "muse" else "#C2410C")
            if i == 0:
                ax.set_title(f"{r['label']}\n{r['ratio']:.2f}", fontsize=8)
    axes[0, 0].set_ylabel("Muse", fontsize=9)
    axes[1, 0].set_ylabel("people", fontsize=9)
    fig.suptitle("Pixel-average Forms of 12 pictures: the 8 most and 8 least Platonic things (Muse/people ratio)",
                 fontsize=10, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(fig_dir / "atlas_forms.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 3.6))
    x = np.arange(len(rows))
    ax.bar(x, [r["ratio"] for r in rows], color=["#1D4ED8" if r["origin"] == "new" else "#93C5FD" for r in rows],
           width=0.8)
    ax.scatter(x, [r.get("sdxl_ratio", np.nan) for r in rows], s=8, color="#0D9488", zorder=3, label="SDXL")
    ax.axhline(1, color="#6B7280", lw=1)
    ax.set_xlim(-1, len(rows))
    ax.set_xticks([])
    ax.set_ylabel("spread ÷ people's spread")
    ax.set_title("135 things, from most Platonic (left) to least; dark blue = the 98 new concepts", fontsize=10,
                 loc="left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(fig_dir / "atlas_rank.png", dpi=160)
    plt.close(fig)
    print(f"wrote figures in {fig_dir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--figures", action="store_true")
    args = ap.parse_args()
    res = json.loads((A.ATLAS_DIR / "results.json").read_text())
    pix = json.loads((A.ATLAS_DIR / "pixels.json").read_text())
    out = export(res, pix)
    DATA.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    total = sum(out["image_bytes"].values())
    print(f"wrote {DATA} ({DATA.stat().st_size / 1024:.0f} KB); pictures {total / 1024 / 1024:.2f} MB "
          f"(forms {out['image_bytes']['forms'] / 1024:.0f} KB, tiles {out['image_bytes']['tiles'] / 1024:.0f} KB)")
    if args.figures:
        figures(res)


if __name__ == "__main__":
    main()
