"""Figures for the bilingual lesion test, from runs/bilingual/results.json (scripts/bilingual_analyze.py).

  accuracy_en_vs_lang.png  accuracy per lesion condition: English (x) vs each other language (y), 95% CIs
  switch_rate.png          English answers on non-English trials, and the reverse, per lesion family
  dose_response.png        accuracy against dose for every lesion family and language
  english_pivot.png        word lens: English name vs target name by layer, intact and lesioned

Usage: python scripts/bilingual_figures.py [--dir runs/bilingual]
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# Reference palette (dataviz skill, light mode). One hue per language, fixed everywhere.
COLOR = {"en": "#2a78d6", "es": "#eb6834", "fr": "#1baf7a", "pt": "#eda100", "es_xen": "#eb6834"}
DASH = {"es_xen": (0, (4, 2))}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
LABEL = {"en": "English", "es": "Spanish", "fr": "French", "pt": "Portuguese",
         "es_xen": "Spanish, English instruction"}
MARK = {"decoder noise": "o", "vision tower noise": "^", "unit ablation or pruning": "s"}
NON_EN = ("es", "fr", "pt", "es_xen")


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "font.size": 10, "axes.titlesize": 11,
        "axes.titleweight": "bold", "axes.titlecolor": INK, "legend.frameon": False, "lines.linewidth": 2})


def ci_err(mean, ci):
    return [[max(mean - ci[0], 0)], [max(ci[1] - mean, 0)]]


def fig_accuracy(res: dict, out: Path):
    conds = [c for c in res["conditions"] if c["group"]]
    fig, axes = plt.subplots(2, 2, figsize=(10, 9.4), sharex=True, sharey=True)
    for ax, v in zip(axes.flat, NON_EN):
        ax.plot([0, 1], [0, 1], color=INK2, lw=1, ls=(0, (3, 3)), zorder=1)
        for c in conds:
            e, l = c["by_variant"]["en"], c["by_variant"].get(v)
            if l is None:
                continue
            ax.errorbar(e["accuracy"], l["accuracy"], xerr=ci_err(e["accuracy"], e["accuracy_ci95"]),
                        yerr=ci_err(l["accuracy"], l["accuracy_ci95"]), fmt=MARK[c["group"]], ms=6,
                        color=COLOR[v], mfc=COLOR[v], mec=SURFACE, mew=1, elinewidth=0.8, alpha=0.85, zorder=3)
        it = res["intact"]
        ax.plot(it["en"]["accuracy"], it[v]["accuracy"], marker="*", ms=14, color=INK, mec=SURFACE, zorder=4)
        p = res["primary"][v]
        ax.set_title(LABEL[v], loc="left", pad=18)
        pval = "p < 0.0001" if p["p_sign_flip"] < 1e-4 else f"p = {p['p_sign_flip']:.2g}"
        ax.text(0.0, 1.005, f"extra drop vs English {p['diff']:+.2f} [{p['ci95'][0]:+.2f}, {p['ci95'][1]:+.2f}], "
                f"{pval}", transform=ax.transAxes, ha="left", va="bottom",
                color=INK2, fontsize=9)
        ax.text(0.03, 0.97, f"below the line:\n{LABEL[v].split(',')[0]} worse", transform=ax.transAxes,
                ha="left", va="top", color=INK2, fontsize=9)
        ax.set_xlim(-0.03, 1.03)
        ax.set_ylim(-0.03, 1.03)
        ax.set_aspect("equal")
    for ax in axes[1]:
        ax.set_xlabel("English accuracy (same pictures, same lesion)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Accuracy in the other language")
    handles = [plt.Line2D([], [], marker=m, ls="", color=INK2, ms=7, label=g) for g, m in MARK.items()]
    handles.append(plt.Line2D([], [], marker="*", ls="", color=INK, ms=11, label="intact"))
    fig.legend(handles=handles, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.005))
    n = res["meta"]["n_pictures"]
    fig.suptitle(f"Naming accuracy under the same lesions: English vs other languages\n{n} pictures; each point "
                 "is one lesion condition (mean of its seeds) with 95% CIs over pictures and seeds", x=0.02,
                 ha="left", fontsize=11.5, color=INK)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(out / "accuracy_en_vs_lang.png", dpi=150)
    plt.close(fig)


def fig_switch(res: dict, out: Path):
    sw = res["switching"]
    names = list(sw["by_family"])
    fig, axes = plt.subplots(1, 2, figsize=(14, 0.5 * len(names) + 3.0), sharey=True)
    y = np.arange(len(names))[::-1]
    offs = {"es": 0.27, "fr": 0.09, "pt": -0.09, "es_xen": -0.27}
    panels = ((axes[0], sw["by_family"], "a. First attempt in English",
               "English answer on {lang} trials", "Spanish/French/Portuguese answer on English trials\n(detector "
               "noise floor: mostly garbled letters)"),
              (axes[1], sw["wrong_name_by_family"], "b. The picture's own name, in the wrong language",
               "English name on {lang} trials", "Spanish/French/Portuguese name on English trials"))
    for ax, fam, title, lab, rev_lab in panels:
        for v, dy in offs.items():
            m = np.array([fam[f][v]["mean"] for f in names])
            lo = m - np.array([fam[f][v]["ci95"][0] for f in names])
            hi = np.array([fam[f][v]["ci95"][1] for f in names]) - m
            ax.errorbar(m, y + dy, xerr=[np.clip(lo, 0, None), np.clip(hi, 0, None)],
                        fmt="o" if v != "es_xen" else "D", ms=5, color=COLOR[v], mec=SURFACE, elinewidth=1,
                        label=lab.format(lang=LABEL[v]), ls="")
        ax.plot([fam[f]["en"]["mean"] for f in names], y - 0.42, "x", color=INK, ms=6, mew=1.5, label=rev_lab)
        ax.set_title(title, loc="left")
        ax.set_xlim(-0.02, 1.02)
        ax.set_xlabel("share of trials (pooled over doses and seeds; 95% CI over pictures and seeds)", fontsize=9)
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.36 - 0.1 * (len(names) < 10)), fontsize=8.3, ncol=1)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(names)
    les, rev = sw["lesioned"], sw["reverse_on_english_trials"]
    fig.suptitle("Language switching under damage, pooled over all lesions. First attempt in English: Spanish "
                 f"{les['es']['english_answers']['mean']:.1%}, French {les['fr']['english_answers']['mean']:.1%}, "
                 f"Portuguese {les['pt']['english_answers']['mean']:.1%}.\nThe picture's English name: Spanish "
                 f"{les['es']['english_name']['mean']:.1%}, French {les['fr']['english_name']['mean']:.1%}, "
                 f"Portuguese {les['pt']['english_name']['mean']:.1%}; reverse (another language's name on English "
                 f"trials) {rev['item_name_in_other_language']['mean']:.1%}.", x=0.01, ha="left", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out / "switch_rate.png", dpi=150)
    plt.close(fig)


def fig_dose(res: dict, out: Path):
    fams = list(res["dose_response"])
    cols = 4
    rows = int(np.ceil(len(fams) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(13, 3.0 * rows + 0.8), sharey=True, squeeze=False)
    for ax, f in zip(axes.flat, fams):
        pts = defaultdict(lambda: defaultdict(list))
        for r in res["dose_response"][f]:
            for v in ("en",) + NON_EN:
                if f"acc_{v}" in r:
                    pts[v][r["dose"]].append(r[f"acc_{v}"])
        for v in ("en",) + NON_EN:
            xs = sorted(pts[v])
            ax.plot(xs, [np.mean(pts[v][x]) for x in xs], marker="o", ms=5, color=COLOR[v], ls=DASH.get(v, "-"),
                    mec=SURFACE, label=LABEL[v], lw=1.8 if v != "en" else 2.4, zorder=3 if v == "en" else 2)
        ax.set_title(f, loc="left", fontsize=10)
        ax.set_ylim(-0.03, 1.03)
        ax.set_xlabel({"pruned": "layers removed"}.get(f, "fraction of units" if f.startswith(("naming", "random"))
                                                       else "noise (x unit sd)"), fontsize=9)
    for ax in axes.flat[len(fams):]:
        ax.set_visible(False)
    for ax in axes[:, 0]:
        ax.set_ylabel("accuracy")
    h, lab = axes.flat[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=5, bbox_to_anchor=(0.5, -0.005))
    fig.suptitle("Dose-response: naming accuracy by lesion strength and language (mean of seeds; "
                 "random = matched random-unit controls)", x=0.02, ha="left", fontsize=11.5)
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    fig.savefig(out / "dose_response.png", dpi=150)
    plt.close(fig)


def fig_pivot(res: dict, out: Path):
    lens = res["lens"]
    first = 28  # before this layer both names have lens probability ~0 on every trial
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(15, 4.9))
    es = lens["es"]
    layers = np.arange(len(es["intact"]["mean_p_other"]))
    show = layers >= first
    for k, ls in (("intact", "-"), ("lesioned", (0, (4, 2)))):
        a.plot(layers[show], np.array(es[k]["mean_p_other"])[show], color=COLOR["en"], ls=ls,
               label=f"English name, {k}")
        a.plot(layers[show], np.array(es[k]["mean_p_lang"])[show], color=COLOR["es"], ls=ls,
               label=f"Spanish name, {k}")
    a.set_title(f"Spanish trials: mean word-lens probability\nof each name's first token ({es['n_items']} pictures)",
                loc="left")
    a.set_ylabel("mean probability")
    a.legend(fontsize=8.5, loc="upper left")
    for ax, key, title in ((b, "frac_top1_other", "Lens top guess is the English name"),
                           (c, "frac_top1_lang", "Lens top guess is the asked-for name")):
        for v in ("es", "fr", "pt"):
            e = lens[v]
            ax.plot(layers[show], np.array(e["intact"][key])[show], color=COLOR[v],
                    label=f"{LABEL[v]} trials, intact (n={e['n_items']})")
            ax.plot(layers[show], np.array(e["lesioned"][key])[show], color=COLOR[v], ls=(0, (4, 2)),
                    label=f"{LABEL[v]} trials, lesioned")
        ax.set_ylim(-0.02, 1.02)
        ax.set_title(title + "\n(share of trials)", loc="left")
    rev = lens["reverse_en_trials_es_above_en"]
    b.plot(layers[show], np.array(rev["intact"]["frac_top1_other"])[show], color=INK2, lw=1.4,
           label="English trials, intact: Spanish name")
    c.plot(layers[show], np.array(rev["intact"]["frac_top1_lang"])[show], color=COLOR["en"], lw=1.4,
           label="English trials, intact: English name")
    b.legend(fontsize=7.8, loc="upper left")
    c.legend(fontsize=7.8, loc="upper left")
    for ax in (a, b, c):
        ax.set_xlabel(f"decoder layer (0-{first - 1} not shown: both near 0)")
        ax.set_xlim(first - 0.5, layers[-1] + 0.5)
    fig.suptitle("Word lens on the same pictures: the English name rises first, then the asked-for language takes "
                 "over (dashed: pooled over all lesions)", x=0.01, ha="left", fontsize=11.5)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out / "english_pivot.png", dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=Path("runs/bilingual"))
    args = ap.parse_args()
    res = json.loads((args.dir / "results.json").read_text())
    out = args.dir / "figures"
    out.mkdir(parents=True, exist_ok=True)
    style()
    fig_accuracy(res, out)
    fig_switch(res, out)
    fig_dose(res, out)
    fig_pivot(res, out)
    print(f"figures -> {out}")


if __name__ == "__main__":
    main()
