"""An AI growing up: the walls, the curves and the page's assets (docs/plato_scale.md).

Usage: python -I scripts/plato_scale_figures.py [--web]

Reads $PLATO_SCALE_DIR/results.json, svg/ (measure.json, png/), sketch/runs/*/samples and reader_siglip.json.
Writes to $PLATO_SCALE_DIR/figures/:
  wall_models.png          12 chairs per model at temperature 1.0: each family smallest to largest, then Muse
                           Glimmer, then the API models (size undisclosed); failures are labelled empty tiles
  wall_models_primary.png  the same for Qwen2.5 and Meta's models only
  wall_data.png            the sketch model's chairs by data size (seed 1, noise indices 0-11, last step, T 1.0)
  curves.{png,svg}         spread, recognizability (DINOv2; SigLIP 2 check) and failure rate, by model size and
                           by data size
With --web also the page's sprites and wall.json in metalesionlab/web/static/img/plato_scale/.
"""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from metalesionlab import plato_scale as ps  # noqa: E402
from metalesionlab.plato import ink_crop, render_strokes  # noqa: E402
from metalesionlab.plato_sketch import STEPS, sample_name  # noqa: E402

FIG = ps.SCALE_DIR / "figures"
WEB = ROOT / "metalesionlab" / "web" / "static" / "img" / "plato_scale"
SVG_DIR = ps.SCALE_DIR / "svg"
SK_DIR = ps.SCALE_DIR / "sketch"
PAPER, WHITE, INK, MUTED, LINE, SOFT = "#F7F6F1", "#FFFFFF", "#111827", "#5E6472", "#D8D6CE", "#ECEAE3"
FAMILY_COLOR = {"Qwen2.5": "#2a78d6", "OLMo 2": "#eb6834", "Qwen3": "#1baf7a"}  # reference palette, slots 1-3
META = "#171a22"
FONT_DIRS = ["/System/Library/Fonts", "/Library/Fonts", "/usr/share/fonts"]
N = ps.N_B
TILE = 128


def font(size: int, bold: bool = False, mono: bool = False):
    names = (["SFNSMono.ttf", "Menlo.ttc", "DejaVuSansMono.ttf"] if mono else
             ["SF-Pro-Display-Bold.otf", "HelveticaNeue.ttc", "DejaVuSans-Bold.ttf"] if bold else
             ["SF-Pro-Text-Regular.otf", "SFNS.ttf", "HelveticaNeue.ttc", "DejaVuSans.ttf"])
    for n in names:
        for d in FONT_DIRS:
            for p in Path(d).rglob(n):
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


# ---------- tiles ----------

def llm_tile(name: str, i: int) -> Image.Image:
    return ink_crop(Image.open(SVG_DIR / "png" / f"{name}_{i}.png").convert("RGB")).convert("L")


def sketch_tile(drawing, width: int = 5) -> Image.Image:
    return ink_crop(render_strokes(drawing, width=width)).convert("L")


def model_order() -> list:
    """Each family smallest to largest, then Glimmer, then the API models (size undisclosed)."""
    order = [m for fam in ps.FAMILIES for m in ps.family_models(fam)]
    return order + [ps.BY_KEY["glimmer"], ps.BY_KEY["spark"], ps.BY_KEY["wonder"]]


def group_of(m) -> str:
    if m.kind == "api":
        return "Meta API models · size undisclosed"
    if m.family == "Muse":
        return "Meta open weights"
    return {"Qwen2.5": "Qwen2.5-Instruct (Alibaba) · primary family", "OLMo 2": "OLMo 2 Instruct (AI2)",
            "Qwen3": "Qwen3 (Alibaba), thinking off"}[m.family]


def size_text(m) -> str:
    return "size undisclosed" if m.kind == "api" else f"{m.params_b:.1f}B parameters"


# ---------- walls ----------

def wall(rows: list, title: str, sub: str, path: Path, cell: int = 112, gap: int = 6, label_w: int = 300):
    """rows: dicts with group (heading, optional), label, lines (list of str), tiles (12 x Image or failure str)."""
    pad, head_h, group_h = 28, 92, 38
    h = pad + head_h
    for k, r in enumerate(rows):
        if r.get("group") and (k == 0 or rows[k - 1].get("group") != r["group"]):
            h += group_h
        h += cell + gap
    W = pad * 2 + label_w + N * cell + (N - 1) * gap
    img = Image.new("RGB", (W, h + pad), PAPER)
    d = ImageDraw.Draw(img)
    d.text((pad, pad), title, fill=INK, font=font(30, bold=True))
    d.text((pad, pad + 42), sub, fill=MUTED, font=font(17))
    y = pad + head_h
    f_lab, f_sm, f_fail, f_grp = font(19, bold=True), font(15), font(12, mono=True), font(15, mono=True)
    for k, r in enumerate(rows):
        if r.get("group") and (k == 0 or rows[k - 1].get("group") != r["group"]):
            y += 10
            d.text((pad, y), r["group"].upper(), fill="#C2410C", font=f_grp)
            d.line((pad, y + 24, W - pad, y + 24), fill=LINE, width=1)
            y += group_h - 10
        d.text((pad, y + 14), r["label"], fill=INK, font=f_lab)
        for j, line in enumerate(r["lines"]):
            d.text((pad, y + 42 + 20 * j), line, fill=MUTED, font=f_sm)
        for i, t in enumerate(r["tiles"]):
            x = pad + label_w + i * (cell + gap)
            if isinstance(t, Image.Image):
                d.rectangle((x, y, x + cell - 1, y + cell - 1), fill=WHITE, outline=LINE)
                tile = t.convert("RGB").resize((cell - 8, cell - 8), Image.LANCZOS)
                img.paste(tile, (x + 4, y + 4))
            else:
                d.rectangle((x, y, x + cell - 1, y + cell - 1), fill=SOFT, outline=LINE)
                d.line((x + 10, y + cell - 10, x + cell - 10, y + 10), fill=LINE, width=2)
                tw = d.textlength(t, font=f_fail)
                d.rectangle((x + (cell - tw) / 2 - 4, y + cell / 2 - 11, x + (cell + tw) / 2 + 4, y + cell / 2 + 10), fill=SOFT)
                d.text((x + (cell - tw) / 2, y + cell / 2 - 9), t, fill=MUTED, font=f_fail)
        y += cell + gap
    img.save(path, optimize=True)
    print("wrote", path, img.size)


def model_rows(res: dict, keys=None) -> list:
    meas = json.loads((SVG_DIR / "measure.json").read_text())
    by = {(r["key"], r["temp"]): r for r in res["arm_b"]["rows"]}
    rows = []
    for m in model_order():
        if keys and m.key not in keys:
            continue
        name = f"{m.key}_t{ps.PRIMARY_TEMP_B:.1f}"
        if name not in meas:
            continue
        r = by[(m.key, ps.PRIMARY_TEMP_B)]
        tiles = []
        for s in sorted(meas[name]["samples"], key=lambda s: s["i"]):
            tiles.append(llm_tile(name, s["i"]) if s["reason"] is None else ps.FAILURE_LABELS[s["reason"]])
        sp = f"spread {r['spread_ratio']:.2f}× people's" if r["spread_ratio"] is not None else "spread: too few drawings"
        rows.append({"group": group_of(m), "label": m.label, "key": m.key, "tiles": tiles,
                     "lines": [size_text(m), f"failed {r['failed']} of {r['n']} · {sp}"]})
    return rows


def data_rows(res: dict, step=None) -> list:
    rows = []
    by = {(r["size"], r["checkpoint"], r["temp"]): r for r in res["arm_a"]["rows"]}
    for size in ps.SIZES:
        run = SK_DIR / "runs" / ps.run_name_a(size, ps.WALL_A["seed"])
        f = run / "samples" / f"{sample_name(step or STEPS[-1], ps.PRIMARY_TEMP_A)}.json"
        if not f.exists():
            continue
        drawings = json.loads(f.read_text())[:ps.WALL_A["n"]]
        tiles = [sketch_tile(dr) if dr else "a dot" for dr in drawings]
        r = by.get((size, "final", ps.PRIMARY_TEMP_A))
        lines = []
        if r:
            lines = [f"recognizable {r['recog']['mean']:.0%} (3 seeds)",
                     f"spread {r['spread']['mean']:.3f} · its data {r['train_spread']:.3f}"]
        rows.append({"label": f"{size:,} chairs", "tiles": tiles, "lines": lines, "size": size})
    return rows


# ---------- curves ----------

PANELS = [("spread", "Spread (DINOv2)"),
          ("recog_all", "Recognizable as a chair"),
          ("recog_siglip", "Check: SigLIP 2 says chair"),
          ("failure_rate", "Failed to draw")]


def siglip_share_b(siglip, row) -> float | None:
    lab = ((siglip or {}).get("arm_b") or {}).get(f"{row['key']}_t{row['temp']:.1f}")
    return sum(v == "chair" for v in lab.values()) / row["n"] if lab is not None else None


def siglip_share_a(siglip, size: int, ck: str) -> list:
    vals = []
    for s in ps.SEEDS_A:
        e = ((siglip or {}).get("arm_a") or {}).get(f"{ps.run_name_a(size, s)}|{ck}")
        if e:
            vals.append(sum(v == "chair" for v in e["labels"]) / e["n_all"])
    return vals


def ref_line(ax, y, text, ls="--"):
    ax.axhline(y, color=MUTED, lw=1, ls=ls, zorder=1)
    ax.annotate(text, (0.01, y), xycoords=("axes fraction", "data"), xytext=(0, 3), textcoords="offset points",
                fontsize=7.5, color=MUTED)


def style(ax):
    ax.grid(axis="y", color="#ecebe6", lw=0.8, zorder=0)
    ax.set_facecolor(PAPER)


def curves(res: dict, siglip: dict | None):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    plt.rcParams.update({"font.family": "Helvetica", "font.size": 9.5, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.edgecolor": "#9aa0a6", "axes.labelcolor": INK,
                         "xtick.color": MUTED, "ytick.color": MUTED, "svg.fonttype": "none"})
    rows_b = [dict(r) for r in res["arm_b"]["rows"] if r["temp"] == ps.PRIMARY_TEMP_B]
    for r in rows_b:
        r["recog_siglip"] = siglip_share_b(siglip, r)
    ci_key = {"spread": "spread_ci95", "recog_all": "recog_all_ci95", "failure_rate": "failure_ci95"}
    anchors = res["anchors"]
    sig_people = np.mean([v == "chair" for v in siglip["people"]]) if siglip else None
    fig = plt.figure(figsize=(16, 8.4), facecolor=PAPER)
    outer = fig.add_gridspec(2, 4, hspace=0.42, wspace=0.28)
    for c, (col, title) in enumerate(PANELS):
        inner = outer[0, c].subgridspec(1, 2, width_ratios=[4.2, 1], wspace=0.06)
        ax, axa = fig.add_subplot(inner[0]), None
        axa = fig.add_subplot(inner[1], sharey=ax)
        for fam in ps.FAMILIES:
            pts = sorted((r["params_b"], r[col], r.get(ci_key.get(col, ""), None)) for r in rows_b
                         if r["family"] == fam and r[col] is not None)
            if not pts:
                continue
            x, y, cis = zip(*pts)
            ax.plot(x, y, "-o", color=FAMILY_COLOR[fam], lw=2, ms=5.5, zorder=3, mec=PAPER, mew=1)
            for xx, yy, cc in zip(x, y, cis):
                if cc and None not in cc:
                    ax.plot([xx, xx], cc, color=FAMILY_COLOR[fam], lw=1, alpha=0.35, zorder=2)
        g = next((r for r in rows_b if r["key"] == "glimmer"), None)
        if g and g[col] is not None:
            ax.plot([g["params_b"]], [g[col]], "D", color=META, ms=7, zorder=4, mec=PAPER, mew=1)
            ax.annotate("Glimmer", (g["params_b"], g[col]), xytext=(-14, 9), textcoords="offset points",
                        fontsize=7.5, ha="center", color=INK)
        for i, key in enumerate(("spark", "wonder")):
            r = next((r for r in rows_b if r["key"] == key), None)
            if r is None or r[col] is None:
                continue
            axa.plot([i], [r[col]], "s", color=META, ms=7, zorder=4, mec=PAPER, mew=1)
            cc = r.get(ci_key.get(col, ""))
            if cc and None not in cc:
                axa.plot([i, i], cc, color=META, lw=1, alpha=0.35)
        axa.set_xlim(-0.6, 1.6)
        axa.set_xticks([0, 1])
        axa.set_xticklabels(["Spark", "Wonder"], rotation=90, fontsize=7.5)
        axa.tick_params(axis="y", left=False, labelleft=False)
        axa.spines["left"].set_visible(False)
        axa.set_xlabel("API,\nsize undisclosed", fontsize=7.5, color=MUTED)
        style(axa)
        if col == "spread":
            ref_line(ax, anchors["people"]["spread_n12"], "people's chairs")
            ref_line(ax, anchors["muse_image"]["spread"], "Muse Image's chairs", ls=":")
            for a in (ax, axa):
                a.axhline(anchors["people"]["spread_n12"], color=MUTED, lw=1, ls="--", zorder=1)
                a.axhline(anchors["muse_image"]["spread"], color=MUTED, lw=1, ls=":", zorder=1)
            ax.set_ylim(0.0, 0.75)
        else:
            ax.set_ylim(-0.04, 1.04)
            ref = anchors["people"]["recog"] if col == "recog_all" else sig_people if col == "recog_siglip" else None
            if ref is not None:
                ref_line(ax, ref, "people's chairs")
                axa.axhline(ref, color=MUTED, lw=1, ls="--", zorder=1)
        ax.set_xscale("log")
        ax.set_xticks([0.5, 1, 2, 5, 10, 30])
        ax.set_xticklabels(["0.5B", "1B", "2B", "5B", "10B", "30B"])
        ax.set_xlim(0.38, 45)
        ax.set_xlabel("parameters", fontsize=8, color=MUTED)
        ax.set_title(title, fontsize=9.5, loc="left", color=INK)
        style(ax)
        if c == 0:
            ax.set_ylabel("Language models drawing SVG\n12 per model, temperature 1", color=INK)
    # Arm A: the sketch model by data size
    A = res["arm_a"]
    for c, (col, title) in enumerate(PANELS):
        ax = fig.add_subplot(outer[1, c])
        key = {"recog_all": "recog", "failure_rate": "fail"}.get(col, col)
        for ck, ls, alpha in (("final", "-", 0.14), ("best", "--", 0.07)):
            rr = sorted([r for r in A["rows"] if r["checkpoint"] == ck and r["temp"] == ps.PRIMARY_TEMP_A],
                        key=lambda r: r["size"])
            if not rr:
                continue
            x = [r["size"] for r in rr]
            if col == "recog_siglip":
                vals = [siglip_share_a(siglip, r["size"], ck) for r in rr]
                y = [np.mean(v) if v else np.nan for v in vals]
                lo = [min(v) if v else np.nan for v in vals]
                hi = [max(v) if v else np.nan for v in vals]
            else:
                y = [r[key]["mean"] for r in rr]
                lo = [r[key]["ci95"][0] for r in rr]
                hi = [r[key]["ci95"][1] for r in rr]
            ax.fill_between(x, lo, hi, color="#2a78d6", alpha=alpha, lw=0, zorder=2)
            ax.plot(x, y, ls, marker="o", color="#2a78d6", lw=2, ms=5, zorder=3, mec=PAPER, mew=1)
        if col == "spread":
            tr = sorted((r["size"], r["train_spread"]) for r in A["rows"] if r["checkpoint"] == "final"
                        and r["temp"] == ps.PRIMARY_TEMP_A)
            if tr:
                x, y = zip(*tr)
                ax.plot(x, y, ":", color=MUTED, lw=1.5, zorder=2)
                ax.annotate("the chairs it learned from", (x[0], y[0]), xytext=(0, 6), textcoords="offset points",
                            fontsize=7.5, color=MUTED)
            ax.set_ylim(0.0, 0.75)
        else:
            ax.set_ylim(-0.04, 1.04)
            ref = anchors["people"]["recog"] if col == "recog_all" else sig_people if col == "recog_siglip" else None
            if ref is not None:
                ref_line(ax, ref, "people's chairs")
        ax.set_xscale("log")
        ax.set_xticks(ps.SIZES)
        ax.set_xticklabels(["100", "300", "1k", "3k", "10k", "20k"])
        ax.set_xlim(70, 28000)
        ax.set_xlabel("people's chairs it learned from", fontsize=8, color=MUTED)
        ax.set_title(title, fontsize=9.5, loc="left", color=INK)
        style(ax)
        if c == 0:
            ax.set_ylabel("Small sketch model trained from scratch\n3 seeds × 200 drawings, temperature 1",
                          color=INK)
    handles = [Line2D([], [], color=FAMILY_COLOR[f], marker="o", lw=2, label=f) for f in ps.FAMILIES]
    handles += [Line2D([], [], color=META, marker="D", lw=0, label="Muse Glimmer 30B (Meta, open)"),
                Line2D([], [], color=META, marker="s", lw=0, label="Muse Spark / Wonder (Meta API)"),
                Line2D([], [], color="#2a78d6", lw=2, ls="-", label="sketch model, last step"),
                Line2D([], [], color="#2a78d6", lw=2, ls="--", label="sketch model, best held-out step")]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.07, 0.955), ncol=7, frameon=False, fontsize=8.5)
    fig.suptitle("Does an AI's chair change with a bigger model or more data?", x=0.07, y=0.995, ha="left",
                 fontsize=14, fontweight="bold", color=INK)
    for ext in ("png", "svg"):
        fig.savefig(FIG / f"curves.{ext}", dpi=160, bbox_inches="tight", facecolor=PAPER)
    plt.close(fig)
    print("wrote", FIG / "curves.png")


# ---------- web assets ----------

def sprite(rows: list, path: Path):
    """Ink as opaque black, paper transparent: the page masks it, so the tiles follow light and dark themes."""
    sheet = Image.new("LA", (N * TILE, len(rows) * TILE), (0, 0))
    for k, r in enumerate(rows):
        for i, t in enumerate(r["tiles"]):
            if isinstance(t, Image.Image):
                g = t.resize((TILE, TILE), Image.LANCZOS)
                alpha = Image.eval(g, lambda v: 255 - v)
                tile = Image.merge("LA", (Image.new("L", (TILE, TILE), 0), alpha))
                sheet.paste(tile, (i * TILE, k * TILE))
    sheet.convert("RGBA").save(path, "WEBP", quality=82, method=6)
    print("wrote", path, f"{path.stat().st_size / 1024:.0f} KB")


def web(res: dict, mrows: list, drows: list, siglip: dict | None):
    WEB.mkdir(parents=True, exist_ok=True)
    sprite(mrows, WEB / "wall_models.webp")
    sprite(drows, WEB / "wall_data.webp")
    by = {(r["key"], r["temp"]): r for r in res["arm_b"]["rows"]}
    meas = json.loads((SVG_DIR / "measure.json").read_text())
    models = []
    for k, r in enumerate(mrows):
        m = ps.BY_KEY[r["key"]]
        row = by[(m.key, ps.PRIMARY_TEMP_B)]
        name = f"{m.key}_t{ps.PRIMARY_TEMP_B:.1f}"
        lab = ((siglip or {}).get("arm_b") or {}).get(name, {})
        models.append({"key": m.key, "label": m.label, "family": m.family, "group": group_of(m),
                       "params_b": None if m.kind == "api" else m.params_b, "kind": m.kind, "row": k,
                       "tiles": [None if s["reason"] is None else ps.FAILURE_LABELS[s["reason"]]
                                 for s in sorted(meas[name]["samples"], key=lambda s: s["i"])],
                       "failed": row["failed"], "spread_ratio": row["spread_ratio"], "recog_all": row["recog_all"],
                       "recog_siglip": sum(v == "chair" for v in lab.values()) / row["n"] if lab else None})
    data = [{"size": r["size"], "row": k, "tiles": [None if isinstance(t, Image.Image) else t for t in r["tiles"]],
             "lines": r["lines"]} for k, r in enumerate(drows)]
    out = {"cols": N, "tile": TILE, "models": models, "data": data,
           "about": "Tiles: ink-cropped renders of each model's own drawings (temperature 1). Model wall: 12 SVG "
                    "samples per model. Data wall: the sketch model's seed 1, noise indices 0-11, last step."}
    (WEB / "wall.json").write_text(json.dumps(out, separators=(",", ":")))
    print("wrote", WEB / "wall.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", action="store_true")
    args = ap.parse_args()
    FIG.mkdir(parents=True, exist_ok=True)
    res = json.loads((ps.SCALE_DIR / "results.json").read_text())
    sp = ps.SCALE_DIR / "reader_siglip.json"
    siglip = json.loads(sp.read_text()) if sp.exists() else None
    mrows = model_rows(res)
    wall(mrows, "Chairs by model size", "“Draw a simple chair as an SVG drawing …” · 12 samples per model, "
         "temperature 1 · each family smallest to largest · ink-cropped renders", FIG / "wall_models.png")
    prim = [r for r in mrows if r["key"].startswith("qwen25") or r["key"] in ("glimmer", "spark", "wonder")]
    wall(prim, "Chairs by model size: Qwen2.5 and Meta's models", "12 SVG chairs per model at temperature 1 · "
         "failures are labelled", FIG / "wall_models_primary.png")
    drows = data_rows(res)
    if drows:
        wall(drows, "Chairs by data size", "The same small sketch model trained on 100 to 20,000 people's chairs · "
             "seed 1, the same 12 random starts, last step (25,600), temperature 1", FIG / "wall_data.png",
             label_w=320)
    curves(res, siglip)
    if args.web:
        web(res, mrows, drows, siglip)


if __name__ == "__main__":
    main()
