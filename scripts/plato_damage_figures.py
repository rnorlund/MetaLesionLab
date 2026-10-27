"""Plato's Chair, damage: figures (on the Mac, after plato_damage_analyze.py stats).

  python scripts/plato_damage_figures.py [--run main] [--clocks clocks]

Writes to $DAMAGE_DIR/figures/:
  hero_<kind>_<method>.png   one picture across the damage levels, language part vs. drawing part
  melt_<family>.png          every chair kind (rows) across the damage levels (columns), one seed
  dissociation.{png,svg}     what it is (kind kept) and how it is drawn (clean line drawing) vs. how
                             much the picture changed, language vs. drawing damage
  prototype.{png,svg}        distance to the plain-chair prototype vs. how much the picture changed
  clocks_<method>.png        clock faces across the damage levels
  clock_features.{png,svg}   which clock features survive each kind of damage
  glimmer_arm.{png,svg}      what a damaged Glimmer calls Muse Image's named-kind doodles
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from metalesionlab.plato_damage import BY_KEY, CONCEPT_KINDS, parse_condition  # noqa: E402
from plato_damage_analyze import DAMAGE_DIR, conditions_in, font  # noqa: E402

LANG, DRAW = "#1D4ED8", "#C2410C"  # site colours (validated pair); method is the line style
INK, MUTED, GRID = "#111827", "#4B5563", "#E5E7EB"
TITLES = {"text": "Language part damaged (text encoders)", "unet": "Drawing part damaged (UNet)"}
METHOD = {"zero": "neurons switched off", "noise": "noise added to neurons"}


def doses_of(run: Path, family: str) -> list[float]:
    return sorted(parse_condition(c)[1] for c in conditions_in(run) if parse_condition(c)[0] == family)


def picture(run: Path, cond: str, key: str, seed: int, side: int) -> Image.Image | None:
    f = run / cond / key / f"s{seed}.png"
    return Image.open(f).convert("RGB").resize((side, side), Image.LANCZOS) if f.exists() else None


def levels(run: Path, family: str, n: int = 4) -> list[str]:
    """intact + n doses spread over the family's range (always including the top dose)."""
    d = doses_of(run, family)
    if len(d) > n:
        idx = np.unique(np.round(np.linspace(0, len(d) - 1, n)).astype(int))
        d = [d[i] for i in idx]
    return ["intact"] + [f"{family}@{x:g}" for x in d]


def strip_figure(run: Path, rows: list[tuple[str, list[str], str, int]], out: Path, side: int = 220,
                 col_labels: list[str] | None = None, title: str = "") -> None:
    """rows: (label, conditions, key, seed); one picture per condition."""
    label_w, gap, head = 250, 8, 70 if title else 40
    n_cols = max(len(r[1]) for r in rows)
    W = label_w + n_cols * (side + gap)
    H = head + len(rows) * (side + gap) + 10
    sheet = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(sheet)
    if title:
        d.text((12, 10), title, fill=INK, font=font(24))
    for j, lab in enumerate(col_labels or []):
        d.text((label_w + j * (side + gap) + 4, head - 28), lab, fill=MUTED, font=font(17))
    for i, (lab, conds, key, seed) in enumerate(rows):
        y = head + i * (side + gap)
        colour = LANG if lab.lower().startswith("language") else DRAW if lab.lower().startswith("drawing") else INK
        for k, line in enumerate(lab.split("\n")):
            d.text((12, y + side // 2 - 22 + 24 * k), line, fill=colour, font=font(18 if k == 0 else 15))
        for j, c in enumerate(conds):
            im = picture(run, c, key, seed, side)
            if im is not None:
                sheet.paste(im, (label_w + j * (side + gap), y))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(out)


def fig_hero(run: Path, figs: Path, key: str, seed: int, method: str) -> None:
    rows = []
    for site in ("text", "unet"):
        fam = f"{site}-{method}"
        rows.append((("Language part" if site == "text" else "Drawing part") + "\n" + METHOD[method], levels(run, fam),
                     key, seed))
    kind = BY_KEY[key].kind
    strip_figure(run, rows, figs / f"hero_{key.split('__')[1]}_{method}.png",
                 col_labels=["intact", "level 1", "level 2", "level 3", "level 4"],
                 title=f"SDXL asked for {kind}, the same seed at each damage level")


def fig_melt(run: Path, figs: Path, family: str, seed: int = 0) -> None:
    kinds = [p for p in BY_KEY.values() if p.concept == "chair"]
    rows = [(p.kind if not p.is_plain else "a chair (plain)", levels(run, family), p.key, seed) for p in kinds]
    site = "Language" if family.startswith("text") else "Drawing"
    strip_figure(run, rows, figs / f"melt_{family}.png", side=170,
                 col_labels=["intact", "level 1", "level 2", "level 3", "level 4"],
                 title=f"{site} part damaged ({family}), seed {seed}: every chair kind")


def fig_clocks(run: Path, figs: Path, method: str, seed: int = 0) -> None:
    keys = [p.key for p in BY_KEY.values() if p.concept == "clock"]
    for site in ("text", "unet"):
        fam = f"{site}-{method}"
        rows = [(f"{BY_KEY[k].kind}", levels(run, fam, 3), k, seed) for k in keys]
        strip_figure(run, rows, figs / f"clocks_{fam}.png", side=170, col_labels=["intact", "level 1", "level 2",
                                                                                  "level 3"],
                     title=f"Clock faces, {TITLES[site].lower()}, {METHOD[method]}")


# ---------- charts ----------

def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#9CA3AF")
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def _curve(table: list[dict], family: str, measure: str):
    xs, ys, lo, hi = [0.0], [0.0], [0.0], [0.0]
    for row in table:
        if row["family"] == family and measure in row and "d_intact" in row:
            xs.append(row["d_intact"]["mean"])
            ys.append(row[measure]["mean"])
            lo.append(row[measure]["ci95"][0])
            hi.append(row[measure]["ci95"][1])
    return np.array(xs), np.array(ys), np.array(lo), np.array(hi)


def fig_lines(res: dict, figs: Path, panels: list[tuple[str, str, float]], name: str, concept: str = "chair",
              families=("text-zero", "unet-zero", "text-noise", "unet-noise"), title: str = "") -> None:
    """panels: (measure, y label, value added to the change, e.g. 1 to show a rate instead of a change)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    table = res["concepts"][concept]["table_named"]
    fig, axes = plt.subplots(1, len(panels), figsize=(4.6 * len(panels), 3.8), dpi=150)
    axes = np.atleast_1d(axes)
    for ax, (measure, ylab, offset) in zip(axes, panels):
        _style(ax)
        for fam in families:
            x, y, lo, hi = _curve(table, fam, measure)
            if len(x) < 2:
                continue
            colour = LANG if fam.startswith("text") else DRAW
            ls = "-" if fam.endswith("zero") else (0, (4, 2))
            ax.fill_between(x, lo + offset, hi + offset, color=colour, alpha=0.10, lw=0)
            ax.plot(x, y + offset, color=colour, ls=ls, lw=2, marker="o", ms=4, mec="white", mew=1)
            ax.annotate(("language" if fam.startswith("text") else "drawing") + (", off" if fam.endswith("zero")
                                                                                   else ", noise"),
                        (x[-1], y[-1] + offset), xytext=(4, 0), textcoords="offset points", fontsize=8, color=INK,
                        va="center")
        ax.set_xlabel("how much the picture changed\n(DINOv2 distance to its intact twin)", fontsize=9, color=MUTED)
        ax.set_ylabel(ylab, fontsize=9, color=MUTED)
        ax.set_xlim(0, None)
    if title:
        fig.suptitle(title, fontsize=11, color=INK, x=0.02, ha="left")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(figs / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)
    print(figs / f"{name}.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="main")
    ap.add_argument("--clocks", default="clocks")
    ap.add_argument("--hero", nargs="*", default=["chair__rocking_chair:1", "chair__wheelchair:2"],
                    help="key:seed pairs for hero strips")
    args = ap.parse_args()
    run, figs = DAMAGE_DIR / args.run, DAMAGE_DIR / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    for spec in args.hero:
        key, seed = spec.split(":")
        for method in ("zero", "noise"):
            fig_hero(run, figs, key, int(seed), method)
    for fam in ("text-zero", "unet-zero", "text-noise", "unet-noise"):
        fig_melt(run, figs, fam)
    res_path = DAMAGE_DIR / f"results_{args.run}.json"
    if res_path.exists():
        res = json.loads(res_path.read_text())
        fig_lines(res, figs, [("delta_correct", "share still the asked kind (Glimmer)", 1.0),
                              ("delta_p_clean", "change in P(clean line drawing) (Glimmer)", 0.0)],
                  "dissociation", title="What it is vs. how it is drawn, as damage grows (8 chair kinds × 8 seeds)")
        fig_lines(res, figs, [("delta_d_proto", "change in distance to the plain chair", 0.0),
                              ("delta_drift", "drift index (d_kind − d_proto), change", 0.0)],
                  "prototype", title="Does a damaged rocking chair turn into the plain chair?")
    clocks = DAMAGE_DIR / args.clocks
    if clocks.exists():
        for method in ("zero", "noise"):
            fig_clocks(clocks, figs, method)


if __name__ == "__main__":
    main()
