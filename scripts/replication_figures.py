"""Figures for the n = 100 replication, from runs/replication/results.json (scripts/replication_analyze.py).

  effects.png      every pre-registered difference, first run (n = 20) vs replication (n = 100),
                   with 95% CIs over pictures
  error_types.png  share of errors of each type at each damage site, n = 20 vs n = 100

Usage: python scripts/replication_figures.py [--results runs/replication/results.json] [--out docs/figures/replication]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Reference palette (dataviz skill, light mode), as scripts/bilingual_figures.py.
NEW, OLD = "#2a78d6", "#8f8e89"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
LANG = {"es": "Spanish", "fr": "French", "pt": "Portuguese", "es_xen": "Spanish, English instruction"}
LOC = {"naming mlp": "Naming localizer, neurons", "visual mlp": "Visual localizer, neurons",
       "language mlp": "Language localizer, neurons", "naming heads": "Naming localizer, heads"}
SITE = {"vision tower": "Vision\ntower", "layers 40-47": "Layers\n41–48", "layers 0-7": "Layers\n1–8"}
TYPE = {"meaning": "Meaning errors\n(Semantic, Mixed)", "sound": "Sound errors\n(Nonword, Formal)",
        "self_correction": "Self-corrections", "jargon": "Jargon"}


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False, "font.size": 10,
        "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": INK, "legend.frameon": False})


def rows(res: dict) -> list[tuple[str, str, dict | None, dict | None]]:
    """(section, label, old, new) with diff and ci95 in proportions."""
    out = []
    tv = res["targeted_vs_random"]
    for k, label in LOC.items():
        out.append(("Targeted minus random-unit damage\n(accuracy lost, same number of units)", label,
                    tv["old"].get(k), tv["new"].get(k)))
    b_old, b_new = (res["bilingual"]["old"] or {}), (res["bilingual"]["new"] or {})
    for v, label in LANG.items():
        out.append(("Bilingual: extra drop outside English\n(same pictures, same damage)", label,
                    (b_old.get("primary") or {}).get(v), (b_new.get("primary") or {}).get(v)))
    sf = res["spanish_fallback"]
    for k, label in (("english_answer", "Answers in English"), ("english_name", "The picture's English name")):
        out.append(("Spanish test, naming neurons off:\nEnglish answers, targeted minus random", label,
                    (sf["old"] or {}).get(k), (sf["new"] or {}).get(k)))
    return out


def fig_effects(res: dict, out: Path):
    data = rows(res)
    sections = list(dict.fromkeys(s for s, *_ in data))
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(data) + 0.6 * len(sections) + 1.4))
    y, ticks, labels = 0, [], []
    for sec in sections:
        ax.text(0.0, y - 0.15, sec, ha="left", va="bottom", fontsize=9.5, fontweight="bold", color=INK,
                transform=ax.get_yaxis_transform(), zorder=4,
                bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 1.5})
        y -= 0.95
        for s, label, old, new in data:
            if s != sec:
                continue
            for d, off, color, filled in ((old, 0.16, OLD, False), (new, -0.16, NEW, True)):
                if not d:
                    continue
                lo, hi = d["ci95"]
                ax.plot([100 * lo, 100 * hi], [y + off] * 2, color=color, lw=2, solid_capstyle="round", zorder=2)
                ax.plot(100 * d["diff"], y + off, "o", ms=7, color=color, mfc=color if filled else SURFACE,
                        mew=2, zorder=3)
            if new:
                ax.text(100 * new["ci95"][1] + 1.5, y - 0.16, f"{100 * new['diff']:+.0f}", va="center", fontsize=8.5,
                        color=INK2)
            ticks.append(y)
            labels.append(label)
            y -= 0.8
        y -= 0.35
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(ticks, labels)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(-30, 108)
    ax.set_ylim(y + 0.3, 0.4)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Difference in percentage points, with 95% CI over pictures (0 = no effect)")
    handles = [plt.Line2D([], [], marker="o", ls="-", color=OLD, mfc=SURFACE, mew=2, label="First run, n = 20 pictures"),
               plt.Line2D([], [], marker="o", ls="-", color=NEW, label="Replication, n = 100 new pictures")]
    ax.legend(handles=handles, loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=2)
    ax.set_title("Pre-registered effects, first run vs replication", loc="left", pad=28)
    fig.tight_layout()
    fig.savefig(out / "effects.png", dpi=150)
    plt.close(fig)


def fig_errors(res: dict, out: Path):
    ep = res["error_profiles"]
    fig, axes = plt.subplots(1, 4, figsize=(13, 4.2), sharey=False)
    for ax, (t, title) in zip(axes, TYPE.items()):
        for i, (site, label) in enumerate(SITE.items()):
            for d, off, color, filled in ((ep["old"].get(t, {}).get("shares", {}).get(site), -0.18, OLD, False),
                                          (ep["new"].get(t, {}).get("shares", {}).get(site), 0.18, NEW, True)):
                if not d:
                    continue
                lo, hi = d["ci95"]
                ax.plot([i + off] * 2, [100 * lo, 100 * hi], color=color, lw=2, solid_capstyle="round", zorder=2)
                ax.plot(i + off, 100 * d["share"], "o", ms=7, color=color, mfc=color if filled else SURFACE, mew=2,
                        zorder=3)
        ax.set_xticks(range(len(SITE)), list(SITE.values()), rotation=0, fontsize=8.5)
        ax.set_xlim(-0.6, len(SITE) - 0.4)
        ax.set_ylim(0, 100)
        ax.grid(axis="x", visible=False)
        pred = ep["new"].get(t, {}).get("predicted_site")
        ok = ep["new"].get(t, {}).get("replicated")
        ax.set_title(title, loc="left", fontsize=9.5, pad=22)
        if pred:
            ax.text(0.0, 1.02, f"Predicted: {SITE[pred].replace(chr(10), ' ').lower()}. "
                    f"{'Replicated.' if ok else 'Not replicated.'}", transform=ax.transAxes, fontsize=8.5,
                    color=INK2, va="bottom")
    axes[0].set_ylabel("% of errors at that site")
    handles = [plt.Line2D([], [], marker="o", ls="-", color=OLD, mfc=SURFACE, mew=2, label="First run, n = 20"),
               plt.Line2D([], [], marker="o", ls="-", color=NEW, label="Replication, n = 100")]
    fig.legend(handles=handles, loc="upper left", ncol=2, bbox_to_anchor=(0.005, 0.93))
    fig.suptitle("Each damage site has its own kind of error (noise dose series pooled, 95% CI over pictures)",
                 x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout(rect=(0, 0.0, 1, 0.88))
    fig.savefig(out / "error_types.png", dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=Path("runs/replication/results.json"))
    ap.add_argument("--out", type=Path, default=Path("docs/figures/replication"))
    args = ap.parse_args()
    res = json.loads(args.results.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    style()
    fig_effects(res, args.out)
    fig_errors(res, args.out)
    print(f"figures -> {args.out}")


if __name__ == "__main__":
    main()
