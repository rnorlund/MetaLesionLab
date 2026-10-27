"""Plato's Chair, can you prompt it out of the Platonic chair? Figures.

Usage: python -I scripts/plato_variety_figures.py   (after plato_variety_analyze.py)
Reads $PLATO_DIR/results_variety.json, the pictures and the kind labels; writes $PLATO_DIR/figures/:
  variety_<key>.png        tier-1 concepts: five rows of 16 ink-cropped pictures (default prompt, "any kind",
                           "an unusual kind", one of each listed kind, and 16 people), with each row's spread
                           and the number of kinds Glimmer saw in it
  variety_spread.{png,svg} visual spread / people's, by prompt, one dot per concept (Muse Image and SDXL)
  variety_kinds.{png,svg}  kind diversity (chance two pictures show different kinds), by prompt and people
Human drawings: Google Quick, Draw! (CC BY 4.0); the credit is printed on every figure that shows them.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import patheffects  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from plato_figures import AI_C, CREDIT, GRID, HUMAN_C, INK, INK2, MUTED, SURFACE, embeddings, human_subset  # noqa: E402
from plato_variety_analyze import labels_for  # noqa: E402

from metalesionlab.plato import BY_KEY, PLATO_DIR, TIER1, cosine_distances, grid, ink_crop, load_dir, spread  # noqa: E402

FIG = PLATO_DIR / "figures"
SDXL_C = "#1baf7a"  # reference palette slot 3 (aqua); slots 1-3 validate all-pairs
RES = json.loads((PLATO_DIR / "results_variety.json").read_text())
BY = {r["key"]: r for r in RES["concepts"]}
VCREDIT = ("AI: Meta Muse Image (kinds listed by Muse Spark). People: Google Quick, Draw! dataset (CC BY 4.0). "
           "Spread: Meta DINOv2. Kinds: Muse Glimmer.")


def row_specs(key: str) -> list[tuple[str, str, str, str]]:
    """(condition, picture folder, title, subtitle) for the grid rows."""
    c = BY_KEY[key]
    noun = c.quickdraw
    n = c.n_ai
    return [("default", "ai/doodle", "The usual prompt", f"“a quick doodle of {c.phrase}”"),
            ("any", "ai/doodle_any", "“Any kind”", f"“{c.phrase} (any kind of {noun})”"),
            ("unusual", "ai/doodle_unusual", "“An unusual kind”", "“… pick an unusual or different kind”"),
            ("listed", "ai/doodle_listed", f"{n} named kinds", f"Muse Spark listed {n} kinds; one doodle of each"),
            ("people", "human", f"{n} people", "Quick, Draw! players, 20 seconds each")]


def distinct_kinds(source: str, key: str, files: list[str]) -> int | None:
    lab = labels_for(source, key)
    if not lab:
        return None
    by_file = dict(zip(lab["files"], lab["labels"]))
    return len({by_file[f] for f in files if f in by_file and by_file[f] != lab["none"]})


def grid_figure(key: str) -> Path | None:
    c = BY_KEY[key]
    n = c.n_ai
    rows = []
    for cond, folder, title, sub in row_specs(key):
        if cond == "people":
            idx = human_subset(key, n)
            files = [load_dir(PLATO_DIR / "human" / key)[i] for i in idx]
            s = spread(cosine_distances(embeddings("human", key)), idx)
            source = "human"
        else:
            files = load_dir(PLATO_DIR / folder / key)[:n]
            if len(files) < n:
                continue
            s = BY[key][cond]["spread"]
            source = {"default": "ai_doodle", "any": "ai_doodle_any", "unusual": "ai_doodle_unusual",
                      "listed": "ai_doodle_listed"}[cond]
        kinds = distinct_kinds(source, key, [f.name for f in files])
        strip = grid([ink_crop(Image.open(f)) for f in files], cols=n, cell=120, gap=8, bg=SURFACE)
        rows.append((cond, title, sub, s, kinds, strip))
    if len(rows) < 3:
        return None
    w = 3.1 + 0.62 * n
    fig = plt.figure(figsize=(w, 1.0 + 1.12 * len(rows)))
    top, h = 0.86, 0.80 / len(rows)
    left = 2.9 / w
    for i, (cond, title, sub, s, kinds, strip) in enumerate(rows):
        y0 = top - (i + 1) * h
        ax = fig.add_axes((left, y0 + 0.08 * h, 1 - left - 0.01, 0.84 * h))
        ax.imshow(strip)
        ax.set_axis_off()
        color = HUMAN_C if cond == "people" else AI_C
        fig.patches.append(plt.Rectangle((0.012, y0 + 0.22 * h), 0.004, 0.56 * h, transform=fig.transFigure,
                                         color=color, clip_on=False))
        fig.text(0.024, y0 + 0.66 * h, title, fontsize=13, fontweight="bold", color=INK, va="center")
        fig.text(0.024, y0 + 0.45 * h, sub, fontsize=8.5, color=INK2, va="center")
        stat = f"spread {s:.2f}" + (f"  ·  {kinds} kind{'s' if kinds != 1 else ''}" if kinds is not None else "")
        fig.text(0.024, y0 + 0.24 * h, stat, fontsize=10, color=INK2, va="center")
        if i < len(rows) - 1:
            fig.add_artist(plt.Line2D([0.012, 0.99], [y0, y0], transform=fig.transFigure, color=GRID, lw=0.8))
    noun = {"sailboat": "sailboats", "face": "faces", "key": "keys", "cup": "cups"}.get(key, c.label + "s")
    fig.text(0.012, 0.95, f"Ask Muse Image for {n} {noun}, four ways", fontsize=17, fontweight="bold", color=INK,
             va="center")
    fig.text(0.012, 0.905, "Spread: average difference between two pictures of a row (Meta DINOv2). "
             "Kinds: how many different kinds Muse Glimmer recognised in the row.", fontsize=9.5, color=INK2,
             va="center")
    fig.text(0.012, 0.025, VCREDIT, fontsize=8, color=MUTED)
    out = FIG / f"variety_{key}.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def strip_chart(rows: list[tuple[str, list[float], list[str], str]], xlabel: str, title: str, subtitle: str,
                name: str, xlim: tuple[float, float], log: bool = False, ref: tuple[float, str] | None = None,
                note: str = "", breaks: tuple[int, ...] = ()) -> list[Path]:
    """One row per condition: a dot per concept (jittered), the median as a black bar. `breaks` are row
    indices before which a thin separator line is drawn (between groups of rows)."""
    halo = [patheffects.withStroke(linewidth=3, foreground=SURFACE)]
    fig, ax = plt.subplots(figsize=(10, 0.62 * len(rows) + 2.2))
    for i, (label, vals, labels, color) in enumerate(rows):
        y = len(rows) - 1 - i
        vals = np.asarray(vals, float)
        jit = ((np.arange(len(vals)) * 37) % 11 - 5) / 5 * 0.2
        ax.scatter(vals, y + jit, s=34, color=color, edgecolors=SURFACE, linewidths=1.2, zorder=3, alpha=0.9)
        for v, j, lab in zip(vals, jit, labels):
            if lab in ("chair", "umbrella"):
                ax.scatter([v], [y + j], s=60, facecolors=color, edgecolors=INK, linewidths=1.4, zorder=4)
                ax.annotate(lab, (v, y + j), xytext=(7, -10 if lab == "umbrella" else 5), textcoords="offset points",
                            fontsize=8.5, color=INK, zorder=6, path_effects=halo)
        med = float(np.median(vals))
        ax.plot([med, med], [y - 0.32, y + 0.32], color=INK, lw=2.4, zorder=5, solid_capstyle="butt")
        ax.annotate(f"{med:.2f}", (med, y + 0.32), xytext=(0, 3), textcoords="offset points", ha="center",
                    fontsize=9, color=INK, fontweight="bold", zorder=6, path_effects=halo)
        if i in breaks:
            ax.axhline(y + 0.5, color=GRID, lw=1.2, zorder=1)
    if ref:
        ax.axvline(ref[0], color=HUMAN_C, lw=2, zorder=2)
        ax.text(ref[0], len(rows) - 0.45, "  " + ref[1], color=INK2, fontsize=9, va="bottom")
    if log:
        ax.set_xscale("log", base=2)
        ticks = [t for t in (0.125, 0.25, 0.5, 1, 2, 4) if xlim[0] <= t <= xlim[1]]
        ax.set_xticks(ticks, [f"{t:g}" for t in ticks])
        ax.minorticks_off()
    ax.set_xlim(*xlim)
    ax.set_ylim(-0.6, len(rows) - 0.1)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows][::-1], fontsize=10.5)
    ax.tick_params(axis="y", length=0)
    for t in ax.get_yticklabels():
        t.set_color(INK)
    ax.set_xlabel(xlabel)
    ax.grid(True, axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    top = 1 - 0.95 / fig.get_figheight()
    fig.text(0.012, 1 - 0.3 / fig.get_figheight(), title, fontsize=14, fontweight="bold", color=INK, va="center")
    fig.text(0.012, 1 - 0.62 / fig.get_figheight(), subtitle, fontsize=10.5, color=INK2, va="center")
    fig.text(0.012, 0.012, (note + " " if note else "") + "Black bar: median.\n" + VCREDIT, fontsize=7.5,
             color=MUTED, linespacing=1.5)
    fig.tight_layout(rect=(0, 0.06, 1, top))
    outs = []
    for ext in ("png", "svg"):
        out = FIG / f"{name}.{ext}"
        fig.savefig(out, dpi=150)
        outs.append(out)
    plt.close(fig)
    return outs


def spread_chart() -> list[Path]:
    names = [("default", "Muse: usual prompt", AI_C), ("any", "Muse: “any kind”", AI_C),
             ("unusual", "Muse: “an unusual kind”", AI_C), ("listed", "Muse: one of each named kind", AI_C),
             ("sdxl_default", "SDXL: usual prompt", SDXL_C), ("sdxl_any", "SDXL: “any kind”", SDXL_C),
             ("sdxl_listed", "SDXL: one of each named kind", SDXL_C)]
    rows = []
    for cond, label, color in names:
        rs = [r for r in RES["concepts"] if cond in r]
        if rs:
            rows.append((f"{label} ({len(rs)})", [r[cond]["ratio_vs_people"] for r in rs], [r["label"] for r in rs], color))
    lo = min(min(v) for _, v, _, _ in rows)
    hi = max(max(v) for _, v, _, _ in rows)
    n_muse = sum(r[0].startswith("Muse") for r in rows)
    return strip_chart(rows, "Spread of the AI's pictures ÷ spread of people's drawings (log scale)",
                       "“Any kind” changes nothing; naming the kinds makes Muse Image as varied as people",
                       "How varied each thing's pictures are with each prompt, compared with people's drawings",
                       "variety_spread", (max(0.06, lo * 0.85), hi * 1.2), log=True, ref=(1, "people = 1"),
                       note="Each dot is one thing; in brackets, the number of things (“an unusual kind”: tier 1 only).",
                       breaks=(n_muse,))


def kinds_chart() -> list[Path]:
    reliable = set(RES["kinds"]["validation"]["reliable_concepts"])
    names = [("default", "Muse: usual prompt", AI_C), ("any", "Muse: “any kind”", AI_C),
             ("unusual", "Muse: “an unusual kind”", AI_C), ("listed", "Muse: one of each named kind", AI_C),
             ("people", "People", HUMAN_C), ("sdxl_default", "SDXL: usual prompt", SDXL_C),
             ("sdxl_any", "SDXL: “any kind”", SDXL_C)]
    rows = []
    for cond, label, color in names:
        rs = [r for r in RES["concepts"] if r["key"] in reliable and cond in (r.get("kinds") or {})
              and r["kinds"][cond].get("simpson") is not None and np.isfinite(r["kinds"][cond]["simpson"])]
        if rs:
            rows.append((f"{label} ({len(rs)})", [r["kinds"][cond]["simpson"] for r in rs], [r["label"] for r in rs],
                         color))
    med = {lab.split(" (")[0]: float(np.median(v)) for lab, v, _, _ in rows}
    people, usual = med.get("People"), med.get("Muse: usual prompt")
    title = ("People draw a few more kinds than Muse Image's usual prompt, and far fewer than it can"
             if people is not None and usual is not None and people > usual else "Which kind of thing does each picture show?")
    i_people = next((i for i, r in enumerate(rows) if r[0].startswith("People")), None)
    return strip_chart(rows, "Kind diversity: chance that two pictures show different kinds (0 = always the same kind)",
                       title, "Which kind of the thing each picture shows, as labeled by Muse Glimmer",
                       "variety_kinds", (-0.04, 1.04),
                       note=f"Only the {len(reliable)} of 35 things whose kinds Glimmer tells apart reliably; in brackets, "
                            "the number of things.",
                       breaks=tuple(i for i in (i_people, (i_people or 0) + 1) if i_people is not None))


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    made = [p for k in TIER1 if (p := grid_figure(k.replace(" ", "_")))]
    made += spread_chart()
    if RES["kinds"]["validation"]["reliable_concepts"]:
        made += kinds_chart()
    print("\n".join(str(p) for p in made))


if __name__ == "__main__":
    main()
