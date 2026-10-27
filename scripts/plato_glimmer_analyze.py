"""Plato's Chair inside Glimmer, analysis (local, no GPU): spreads with bootstrap CIs, naming
difficulty, lesion vulnerability, figures and results.json.

Usage: python scripts/plato_glimmer_analyze.py [--raw DIR] [--core DIR] [--out DIR]

  --raw   the server's runs/plato_glimmer/raw/ copied back (pictures.json, intact.json,
          distances.npz, calibration.json, one JSON per lesion condition)
  --core  the core Plato's Chair folder (ai/, human/, results.json with the DINOv2 spread)
  --out   where results.json and figures/ go

Also embeds the exact pictures Glimmer saw with DINOv2 (facebook/dinov2-base, CLS token), so the
DINOv2 spread is available on the same sample even before the core results exist.
Exploratory: about 40 concepts, many comparisons, CIs over concepts by bootstrap.
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np

from metalesionlab.plato_glimmer import (NAMED_LAYERS, QUICKDRAW_CREDIT, SOURCES, Picture, bootstrap_spread, ci,
                                         cosine_distance_matrix, names_for, rho_difference, save_json, spearman,
                                         spearman_ci, spread)

# The PlatosChair folder sits next to the repository checkout; PLATO_ROOT overrides it.
ROOT = Path(os.environ.get("PLATO_ROOT", Path(__file__).resolve().parents[2] / "PlatosChair"))
SPACES_NAMED = ["vision_tower", "projector"] + [f"L{n}" for n in NAMED_LAYERS]
NAME_AGREEMENT_ISSUES = {"hat", "yoga"}
PRIMARY_LAYER = "L26"  # mid-decoder: before the name appears in the word lens (~layer 40+)
LOGP_FLOOR = 1e-6

# Figure style: the dataviz reference palette (validated: blue/orange/aqua pass all-pairs CVD checks).
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb"
COLOR = {"ai": "#2a78d6", "human": "#eb6834", "both": "#1baf7a"}
SOURCE_LABEL = {"ai": "AI doodles (Muse Image)", "human": "Human doodles (Quick, Draw!)", "both": "AI + human"}


# --- loading ----------------------------------------------------------------------------

def load_raw(raw: Path, core: Path):
    meta = json.loads((raw / "pictures.json").read_text())
    pics = [Picture(**p) for p in meta["pictures"]]
    for p in pics:  # server paths -> the local copy of the same folder (from the ai/ or human/ segment on)
        parts = Path(p.path).parts
        p.path = str(core.joinpath(*parts[len(parts) - (4 if p.source == "ai" else 3):]))
    intact = json.loads((raw / "intact.json").read_text())
    dist = np.load(raw / "distances.npz", allow_pickle=False)
    conditions = {}
    for f in sorted(raw.glob("*.json")):
        if f.stem in ("pictures", "intact", "calibration"):
            continue
        r = json.loads(f.read_text())
        if "items" in r:
            conditions[r["condition"]] = r
    calibration = json.loads((raw / "calibration.json").read_text()) if (raw / "calibration.json").exists() else {}
    return pics, intact, dist, conditions, calibration


def dinov2_cls(pics: list[Picture], cache: Path) -> np.ndarray:
    """DINOv2-base CLS embeddings of the original pictures (as the core experiment embeds them)."""
    if cache.exists():
        arr = np.load(cache)
        if len(arr) == len(pics):
            return arr
    import torch
    from PIL import Image
    from transformers import AutoImageProcessor, AutoModel

    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    proc = AutoImageProcessor.from_pretrained("facebook/dinov2-base")
    model = AutoModel.from_pretrained("facebook/dinov2-base").to(dev).eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(pics), 32):
            imgs = [Image.open(p.path).convert("RGB") for p in pics[i:i + 32]]
            x = proc(images=imgs, return_tensors="pt").to(dev)
            out.append(model(**x).last_hidden_state[:, 0].float().cpu().numpy())
    arr = np.concatenate(out)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache, arr)
    return arr


def core_dinov2(core: Path, keys: list[str]) -> dict:
    """{source: {key: spread}} from the core experiment's results.json, whatever its layout, as long
    as it has a per-concept DINOv2 spread for AI doodles and human doodles. Empty if not there."""
    f = core / "results.json"
    if not f.exists():
        return {}
    res = json.loads(f.read_text())
    out = {"ai": {}, "human": {}}

    def num(v):
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, dict):
            for k in ("spread", "value", "mean", "estimate"):
                if isinstance(v.get(k), (int, float)):
                    return float(v[k])
        return None

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, path + [str(k)])
        elif isinstance(node, list):
            for i, v in enumerate(node):
                if isinstance(v, dict):
                    key = v.get("key") or v.get("concept") or v.get("quickdraw")
                    walk(v, path + [str(key) if key else str(i)])

    rows = res.get("concepts") or res.get("per_concept") or res.get("items")
    if isinstance(rows, dict):
        rows = [{"key": k, **(v if isinstance(v, dict) else {"value": v})} for k, v in rows.items()]
    for row in rows or []:
        key = str(row.get("key") or row.get("concept") or "").replace(" ", "_")
        if key not in keys:
            continue
        for src, cands in (("ai", ("ai", "ai_doodle", "doodle", "ai_spread", "spread_ai")),
                           ("human", ("human", "human_spread", "spread_human", "quickdraw"))):
            for c in cands:
                v = row.get(c)
                if isinstance(v, dict) and "doodle" in v and src == "ai":
                    v = v["doodle"]
                val = num(v)
                if val is not None:
                    out[src][key] = val
                    break
    return out if out["ai"] or out["human"] else {}


# --- per-concept measures ---------------------------------------------------------------

def group_index(pics: list[Picture]) -> dict[tuple[str, str], list[int]]:
    g: dict[tuple[str, str], list[int]] = {}
    for i, p in enumerate(pics):
        g.setdefault((p.key, p.source), []).append(i)
    return g


def spreads(dist, keys: list[str], reps: int) -> dict:
    """spread[space][centered|raw][source][key] = value; CIs for the named spaces (centered)."""
    groups = [tuple(s.split("|")) for s in dist["groups"].tolist()]
    sizes = dist["sizes"].tolist() if "sizes" in dist.files else [None] * len(groups)
    pos = {g: i for i, g in enumerate(groups)}

    def mat(stack, g):  # unpad a group's matrix
        i = pos[g]
        n = sizes[i] or stack.shape[1]
        return stack[i, :n, :n].astype(np.float64)

    spaces = sorted({k.split("|")[0] for k in dist.files if k not in ("groups", "sizes") and not k.startswith("full|")},
                    key=lambda s: (s[0] == "L", int(s[1:]) if s[0] == "L" else 0))
    out, cis = {}, {}
    rng = np.random.default_rng(0)
    for space in spaces:
        out[space] = {}
        for mode in ("centered", "raw"):
            mats = dist[f"{space}|{mode}"]
            out[space][mode] = {src: {k: spread(mat(mats, (k, src))) for k in keys} for src in SOURCES}
        if space in SPACES_NAMED:
            mats = dist[f"{space}|centered"]
            cis[space] = {src: {k: ci(bootstrap_spread(mat(mats, (k, src)), reps, rng)) for k in keys}
                          for src in SOURCES}
    return {"values": out, "ci95": cis}


def dinov2_spreads(emb: np.ndarray, pics: list[Picture], keys: list[str], reps: int) -> dict:
    gi = group_index(pics)
    rng = np.random.default_rng(1)
    val, cis = {s: {} for s in SOURCES}, {s: {} for s in SOURCES}
    for (k, s), idx in gi.items():
        d = cosine_distance_matrix(emb[idx])
        val[s][k] = spread(d)
        cis[s][k] = ci(bootstrap_spread(d, reps, rng))
    return {"values": val, "ci95": cis}


def naming_measures(items: list[dict], pics: list[Picture], keys: list[str]) -> dict:
    """Per source (ai, human, both) and concept: accuracy, mean log10 p(name) at the last layer,
    and the word-lens layers among correctly named pictures."""
    out = {}
    for src in (*SOURCES, "both"):
        rows = {k: [r for r, p in zip(items, pics) if p.key == k and (src == "both" or p.source == src)] for k in keys}
        m = {}
        for k, rs in rows.items():
            correct = [r for r in rs if r["code"] == "Correct"]
            first = [r["first_correct_layer"] for r in correct if r.get("first_correct_layer")]
            stable = [r["stable_correct_layer"] for r in correct if r.get("stable_correct_layer")]
            m[k] = {
                "n": len(rs), "accuracy": len(correct) / max(len(rs), 1),
                "logp": float(np.mean([np.log10(max(r["p_word_final"], LOGP_FLOOR)) for r in rs])),
                "p_name": float(np.mean([r["p_word_final"] for r in rs])),
                "first_layer_median": float(np.median(first)) if first else None,
                "first_layer_iqr": [float(np.percentile(first, 25)), float(np.percentile(first, 75))] if first else None,
                "stable_layer_median": float(np.median(stable)) if stable else None,
                "n_lens_correct": len(first),
                "answers": dict(sorted(_count([r["said"].split("\n")[0][:30] for r in rs]).items(),
                                       key=lambda kv: -kv[1])[:5]),
            }
        out[src] = m
    return out


def concept_identity(arrays_path: Path, pics: list[Picture], keys: list[str]) -> dict:
    """How much concept identity each space carries, from the saved hidden states. Per space and
    source: leave-one-out 1-nearest-neighbour concept accuracy among that source's pictures, the
    mean within / between concept distance ratio, and each concept's relative spread (its within
    spread divided by its pictures' mean distance to other concepts' pictures)."""
    with np.load(arrays_path) as f:
        spaces = {"vision_tower": f["vision_tower"], "projector": f["projector"]}
        resid = f["resid"]
    for layer in range(resid.shape[1]):
        spaces[f"L{layer + 1}"] = resid[:, layer]
    key = np.array([p.key for p in pics])
    src = np.array([p.source for p in pics])
    out = {"nn_accuracy": {}, "within_between": {}, "relative_spread": {}}
    for name, emb in spaces.items():
        d = cosine_distance_matrix(emb.astype(np.float64), emb.astype(np.float64).mean(0))
        out["nn_accuracy"][name], out["within_between"][name], out["relative_spread"][name] = {}, {}, {}
        for s in SOURCES:
            idx = np.where(src == s)[0]
            ds, ks = d[np.ix_(idx, idx)], key[idx]
            same = ks[:, None] == ks[None, :]
            off = ~np.eye(len(idx), dtype=bool)
            dn = np.where(off, ds, np.inf)
            out["nn_accuracy"][name][s] = float((ks[dn.argmin(1)] == ks).mean())
            out["within_between"][name][s] = float(ds[same & off].mean() / ds[~same].mean())
            rel = {}
            for k in keys:
                m = ks == k
                within = ds[np.ix_(m, m)][~np.eye(m.sum(), dtype=bool)].mean()
                rel[k] = float(within / ds[np.ix_(m, ~m)].mean())
            out["relative_spread"][name][s] = rel
    return out


def _count(xs):
    c = {}
    for x in xs:
        c[x] = c.get(x, 0) + 1
    return c


def vector(d: dict, keys: list[str], field: str | None = None) -> np.ndarray:
    return np.array([np.nan if d.get(k) is None or (field and d[k].get(field) is None)
                     else (d[k][field] if field else d[k]) for k in keys], float)


# --- analysis ---------------------------------------------------------------------------

def correlations(spread_tab: dict, naming: dict, keys: list[str], reps: int) -> dict:
    """rho(spread, naming difficulty) per space x source x measure."""
    out = {}
    for space, by_src in spread_tab.items():
        out[space] = {}
        for src in (*SOURCES, "both"):
            x = (vector(by_src[src], keys) if src in by_src else
                 (vector(by_src["ai"], keys) + vector(by_src["human"], keys)) / 2)
            out[space][src] = {m: spearman_ci(x, vector(naming[src], keys, m), reps=reps)
                               for m in ("accuracy", "logp", "first_layer_median", "stable_layer_median")}
    return out


def lost_rate(intact_items: list[dict], lesion_items: list[dict], pics, keys, source: str | None = None) -> np.ndarray:
    """Per concept: the share of pictures named correctly when intact that the lesioned model misses."""
    out = []
    for k in keys:
        rows = [(a, b) for a, b, p in zip(intact_items, lesion_items, pics)
                if p.key == k and (source is None or p.source == source) and a["code"] == "Correct"]
        out.append(np.mean([b["code"] != "Correct" for _, b in rows]) if rows else np.nan)
    return np.array(out, float)


def lesion_analysis(conditions: dict, intact_naming: dict, intact_items: list[dict], pics, keys, spread_tab: dict,
                    reps: int) -> dict:
    out = {}
    base_acc = vector(intact_naming["both"], keys, "accuracy")
    base_logp = vector(intact_naming["both"], keys, "logp")
    for name, r in sorted(conditions.items()):
        nm = naming_measures(r["items"], pics, keys)
        acc = vector(nm["both"], keys, "accuracy")
        drop = base_acc - acc
        dlogp = base_logp - vector(nm["both"], keys, "logp")
        lost = lost_rate(intact_items, r["items"], pics, keys)
        lost_h = lost_rate(intact_items, r["items"], pics, keys, "human")
        entry = {"family": r.get("family"), "dose": r.get("dose"), "accuracy": r["accuracy"],
                 "accuracy_by_source": {s: float(np.mean(vector(nm[s], keys, "accuracy"))) for s in SOURCES},
                 "lost_rate": float(np.mean([b["code"] != "Correct" for a, b in zip(intact_items, r["items"])
                                             if a["code"] == "Correct"])),
                 "units": {k: r["units"][k] for k in ("mlp", "heads")},
                 "per_concept": {k: {"accuracy": a, "drop": d, "logp_drop": lp, "lost_rate": lo}
                                 for k, a, d, lp, lo in zip(keys, acc, drop, dlogp, lost)},
                 "spread_vs_lost_rate": {}, "spread_vs_lost_rate_partial_intact_logp": {},
                 "human_spread_vs_human_lost_rate": {},
                 "spread_vs_drop": {}, "spread_vs_logp_drop": {}, "spread_vs_drop_partial_intact_logp": {}}
        entry["intact_logp_vs_lost_rate"] = spearman_ci(base_logp, lost, reps=reps)
        for space, by_src in spread_tab.items():
            x = (vector(by_src["ai"], keys) + vector(by_src["human"], keys)) / 2
            entry["spread_vs_lost_rate"][space] = spearman_ci(x, lost, reps=reps)
            entry["spread_vs_lost_rate_partial_intact_logp"][space] = spearman_ci(x, lost, base_logp, reps=reps)
            entry["human_spread_vs_human_lost_rate"][space] = spearman_ci(vector(by_src["human"], keys), lost_h,
                                                                          reps=reps)
            entry["spread_vs_drop"][space] = spearman_ci(x, drop, reps=reps)
            entry["spread_vs_logp_drop"][space] = spearman_ci(x, dlogp, reps=reps)
            entry["spread_vs_drop_partial_intact_logp"][space] = spearman_ci(x, drop, base_logp, reps=reps)
            entry.setdefault("human_spread_vs_human_drop", {})[space] = spearman_ci(
                vector(by_src["human"], keys),
                vector(intact_naming["human"], keys, "accuracy") - vector(nm["human"], keys, "accuracy"), reps=reps)
        entry["intact_logp_vs_drop"] = spearman_ci(base_logp, drop, reps=reps)
        out[name] = entry
    # targeted vs matched random control: does spread predict the targeted drop more?
    for name, e in out.items():
        ctrl = f"{name}-random-matched" if f"{name}-random-matched" in out else None
        for field, other in (("vs_random_matched", ctrl), ("vs_random_matched_damage", MATCHED_DAMAGE.get(name))):
            if other not in out:
                continue
            e[field] = {"control": other}
            for measure in ("lost_rate", "drop"):
                e[field][measure] = {
                    space: rho_difference((vector(spread_tab[space]["ai"], keys)
                                           + vector(spread_tab[space]["human"], keys)) / 2,
                                          vector(e["per_concept"], keys, measure),
                                          vector(out[other]["per_concept"], keys, measure), reps=reps)
                    for space in spread_tab}
    return out


def atypicality(dist_full: np.ndarray, pics: list[Picture]) -> np.ndarray:
    """Per picture: mean distance to the other pictures of its concept and source (high = atypical)."""
    out = np.empty(len(pics))
    groups = group_index(pics)
    for idx in groups.values():
        d = dist_full[np.ix_(idx, idx)].astype(np.float64)
        out[idx] = d.sum(1) / (len(idx) - 1)
    return out


def stratified_auc(score: np.ndarray, label: np.ndarray, pics: list[Picture], mask: np.ndarray | None = None,
                   reps: int = 2000, seed: int = 0) -> dict:
    """P(score of a positive picture > score of a negative picture of the same concept and source),
    pooled over (concept, source) groups. CI: bootstrap over concepts; p: labels shuffled within groups."""
    rng = np.random.default_rng(seed)
    mask = np.ones(len(pics), bool) if mask is None else mask
    per = []
    for (k, _s), idx in group_index(pics).items():
        idx = [i for i in idx if mask[i]]
        per.append((k, score[idx], label[idx].astype(bool)))

    def wins_pairs(s, lab):
        pos, neg = s[lab], s[~lab]
        if not len(pos) or not len(neg):
            return 0.0, 0
        return float((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()), len(pos) * len(neg)

    wp = np.array([wins_pairs(s, lab) for _, s, lab in per])
    if wp[:, 1].sum() == 0:
        return {"auc": float("nan"), "ci95": [float("nan")] * 2, "p_perm": float("nan"), "n_positive": 0}
    auc = wp[:, 0].sum() / wp[:, 1].sum()
    concepts = sorted({k for k, _, _ in per})
    cw = np.array([wp[[i for i, (k, _, _) in enumerate(per) if k == c]].sum(0) for c in concepts])
    idx = rng.integers(0, len(concepts), (reps, len(concepts)))
    boots = cw[idx, 0].sum(1) / np.maximum(cw[idx, 1].sum(1), 1)
    perm = np.empty(reps)
    for r in range(reps):
        w = sum(wins_pairs(s, rng.permutation(lab))[0] for _, s, lab in per)
        perm[r] = w / wp[:, 1].sum()
    p = float(((np.abs(perm - 0.5) >= abs(auc - 0.5) - 1e-12).sum() + 1) / (reps + 1))
    return {"auc": float(auc), "ci95": ci(boots), "p_perm": p, "n_positive": int(sum(lab.sum() for _, _, lab in per)),
            "n_pictures": int(sum(len(lab) for _, _, lab in per))}


def auc_difference(score: np.ndarray, lab1: np.ndarray, lab2: np.ndarray, pics: list[Picture], mask: np.ndarray,
                   reps: int = 4000, seed: int = 0) -> dict:
    """Stratified AUC(lab1) - AUC(lab2) on the same pictures, paired bootstrap over concepts."""
    rng = np.random.default_rng(seed)
    keys = sorted({p.key for p in pics})
    per_concept = np.zeros((len(keys), 4))
    for (k, _s), idx in group_index(pics).items():
        idx = [i for i in idx if mask[i]]
        s = score[idx]
        for j, lab in enumerate((lab1, lab2)):
            lb = lab[idx].astype(bool)
            pos, neg = s[lb], s[~lb]
            if len(pos) and len(neg):
                per_concept[keys.index(k), 2 * j] += (pos[:, None] > neg[None, :]).sum() + 0.5 * (
                    pos[:, None] == neg[None, :]).sum()
                per_concept[keys.index(k), 2 * j + 1] += len(pos) * len(neg)

    def diff(rows):
        t = rows.sum(0)
        return t[0] / max(t[1], 1) - t[2] / max(t[3], 1)

    idx = rng.integers(0, len(keys), (reps, len(keys)))
    boots = np.array([diff(per_concept[i]) for i in idx])
    return {"diff": float(diff(per_concept)), "ci95": ci(boots)}


# Lesions compared at matched damage (similar accuracy) with random neurons, mean-ablated.
MATCHED_DAMAGE = {"naming-mlp-mean@0.2": "random-mlp-mean@0.36", "naming-mlp-mean": "random-mlp-mean"}


def item_typicality(dist, dino_emb: np.ndarray, pics, intact_items, conditions: dict, reps: int) -> dict:
    """Item-level typicality: are a concept's atypical pictures the ones Glimmer misnames, and the
    ones a lesion takes first (among pictures named correctly when intact)?"""
    spaces = {"dinov2": cosine_distance_matrix(dino_emb)}
    for name in ("vision_tower", "projector", PRIMARY_LAYER):
        if f"full|{name}" in dist.files:
            spaces[name] = dist[f"full|{name}"]
    correct = np.array([r["code"] == "Correct" for r in intact_items])
    out = {"what": "stratified AUC within concept and source; > 0.5 means atypical pictures are more often "
                   "misnamed (intact) or lost (lesion, among intact-correct pictures)",
           "intact_error": {}, "lesion_loss": {}}
    for space, d in spaces.items():
        a = atypicality(d, pics)
        out["intact_error"][space] = stratified_auc(a, ~correct, pics, reps=reps)
        lost = {name: np.array([b["code"] != "Correct" for b in r["items"]]) for name, r in conditions.items()}
        for name in sorted(conditions):
            out["lesion_loss"].setdefault(name, {})[space] = stratified_auc(a, lost[name], pics, mask=correct,
                                                                            reps=reps)
        for name in sorted(conditions):
            for kind, ctrl in (("matched_count", f"{name}-random-matched"), ("matched_damage", MATCHED_DAMAGE.get(name))):
                if ctrl in lost:
                    out.setdefault("targeted_minus_random", {}).setdefault(name, {}).setdefault(kind, {"control": ctrl})[
                        space] = auc_difference(a, lost[name], lost[ctrl], pics, correct)
    return out


# --- figures ----------------------------------------------------------------------------

def _style(plt):
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "font.size": 10, "axes.titlesize": 11,
        "axes.titleweight": "bold", "axes.titlelocation": "left", "legend.frameon": False,
    })


def _label_points(ax, xs, ys, labels, fontsize=7.5):
    """Direct labels nudged apart so they don't overlap (simple vertical repel in pixel space)."""
    fig = ax.figure
    fig.canvas.draw()
    trans = ax.transData
    pts = trans.transform(np.column_stack([xs, ys]))
    ok = np.all(np.isfinite(pts), axis=1)
    order = np.argsort(pts[:, 1])
    placed = []
    h, char_w = fontsize * 1.25, fontsize * 0.55
    for i in order:
        if not ok[i]:
            continue
        x, y = pts[i] + np.array([4.0, 2.0])
        w = char_w * len(labels[i])
        for _ in range(60):
            clash = [p for p in placed if abs(p[0] - x) < max(w, p[2]) * 0.9 and abs(p[1] - y) < h]
            if not clash:
                break
            y = max(p[1] for p in clash) + h
        placed.append((x, y, w))
        tx, ty = trans.inverted().transform((x, y))
        ax.annotate(labels[i], (xs[i], ys[i]), xytext=(tx, ty), textcoords="data", fontsize=fontsize, color=INK2,
                    va="bottom", ha="left",
                    arrowprops=dict(arrowstyle="-", color=GRID, lw=0.6, shrinkA=0, shrinkB=2)
                    if abs(y - pts[i][1] - 2) > h * 0.6 else None)


def _footnote(fig, text: str, width: int = 170):
    import textwrap

    fig.text(0.01, 0.005, "\n".join(textwrap.wrap(text, width)), fontsize=7, color=MUTED, va="bottom")


def _rho_text(r: dict) -> str:
    lo, hi = r["ci95"]
    return f"rho = {r['rho']:+.2f} [{lo:+.2f}, {hi:+.2f}], n = {r['n']}"


def fig_spread_vs_naming(path, spread_sets: list[tuple[str, dict]], naming, keys, labels, corr_fn, measure,
                         src: str, title: str):
    """One source, one naming measure; a 2 x 2 grid of spread spaces, points labeled by concept."""
    import matplotlib.pyplot as plt

    _style(plt)
    ncol = 2
    nrow = int(np.ceil(len(spread_sets) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(11, 5.0 * nrow), squeeze=False)
    ylab = {"accuracy": "Glimmer naming accuracy (%)", "logp": "log10 p(correct name), last layer"}[measure]
    for ax, (name, by_src) in zip(axes.flat, spread_sets):
        x = vector(by_src[src], keys)
        y = vector(naming[src], keys, measure)
        ok = np.isfinite(x)
        r = corr_fn(x, y)
        y_plot = y * 100 if measure == "accuracy" else y
        ax.scatter(x[ok], y_plot[ok], s=34, color=COLOR[src], edgecolor=SURFACE, linewidth=1.5, zorder=3)
        _label_points(ax, x[ok], y_plot[ok], [lab for lab, o in zip(labels, ok) if o])
        ax.set_title(f"{name}\n{_rho_text(r)}", fontsize=10)
        ax.set_xlabel("within-concept spread (mean pairwise cosine distance)", fontsize=9)
        ax.set_ylabel(ylab, fontsize=9)
        ax.xaxis.set_major_locator(__import__("matplotlib.ticker", fromlist=["MaxNLocator"]).MaxNLocator(5))
    for ax in list(axes.flat)[len(spread_sets):]:
        ax.axis("off")
    fig.suptitle(title, x=0.01, ha="left", fontsize=14, fontweight="bold")
    _footnote(fig, f"{SOURCE_LABEL[src]}. Each point is one concept (12-16 pictures). Spearman rho with 95% bootstrap "
              "CI over concepts. Exploratory. " + QUICKDRAW_CREDIT)
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    fig.savefig(path, dpi=180)
    plt.close(fig)


def fig_typicality(path, typ: dict, lesions: dict, order: list[str]):
    """Item level: AUC with 95% CI for 'atypical pictures are misnamed (intact) / lost (lesions)'."""
    import matplotlib.pyplot as plt

    _style(plt)
    spaces = [("dinov2", "DINOv2", "#2a78d6"), ("vision_tower", "Glimmer vision tower", "#eb6834"),
              ("projector", "Glimmer projector", "#1baf7a")]
    rows = [("intact: misnamed", typ["intact_error"])] + [
        (short_condition(n, lesions[n]), typ["lesion_loss"][n]) for n in order]
    fig, ax = plt.subplots(figsize=(9.5, 0.62 * len(rows) + 1.6))
    for j, (sp, lab, col) in enumerate(spaces):
        off = (j - 1) * 0.22
        for i, (_, res) in enumerate(rows):
            r = res.get(sp)
            if not r or r["auc"] is None or not np.isfinite(r["auc"]):
                continue
            ax.plot(r["ci95"], [i + off] * 2, color=col, lw=1.6, alpha=0.6, solid_capstyle="round")
            ax.scatter([r["auc"]], [i + off], color=col, s=30, edgecolor=SURFACE, lw=1.2, zorder=3,
                       label=lab if i == 0 else None)
    ax.axvline(0.5, color=MUTED, lw=1)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], fontsize=8)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("AUC: atypical picture misnamed / lost  (0.5 = no typicality effect)")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, fontsize=8)
    ax.set_title("Are atypical doodles misnamed, and lost first?", fontsize=12, pad=26)
    _footnote(fig, "Atypicality = a picture's mean distance to the other pictures of its concept and source. AUC "
              "compares pictures within the same concept and source; lesion rows use only pictures named correctly "
              "when intact. 95% bootstrap CI over concepts.", width=150)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, dpi=180)
    plt.close(fig)


def fig_spread_vs_lesion(path, lesions: dict, spread_tab, keys, labels, space: str, panels: list[str]):
    import matplotlib.pyplot as plt

    _style(plt)
    ncol = min(len(panels), 4)
    nrow = int(np.ceil(len(panels) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.6 * ncol, 4.5 * nrow), squeeze=False)
    x = (vector(spread_tab[space]["ai"], keys) + vector(spread_tab[space]["human"], keys)) / 2
    for ax, name in zip(axes.flat, panels):
        e = lesions[name]
        y = vector(e["per_concept"], keys, "lost_rate") * 100
        is_ctrl = "random" in name
        ax.scatter(x, y, s=30, color=MUTED if is_ctrl else COLOR["both"], edgecolor=SURFACE, linewidth=1.3, zorder=3)
        ax.set_ylim(-4, 104)
        _label_points(ax, x, y, labels, fontsize=6.5)
        ax.set_title(f"{pretty_condition(name, e)}\n{_rho_text(e['spread_vs_lost_rate'][space])}", fontsize=9)
        ax.set_xlabel(f"spread, {space_label(space)} (AI and human mean)", fontsize=8.5)
        ax.set_ylabel("correct names lost (%)", fontsize=8.5)
        ax.xaxis.set_major_locator(__import__("matplotlib.ticker", fromlist=["MaxNLocator"]).MaxNLocator(5))
    for ax in list(axes.flat)[len(panels):]:
        ax.axis("off")
    fig.suptitle("Do spread-out concepts break first when Glimmer is damaged?", x=0.01, ha="left", fontsize=14,
                 fontweight="bold")
    _footnote(fig, "Each point is one concept (24-32 pictures). Correct names lost = share of the pictures Glimmer "
              "named correctly when intact that it misses after the lesion. Gray panels are random-unit controls. "
              "Spearman rho, 95% bootstrap CI over concepts. Exploratory.")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(path, dpi=180)
    plt.close(fig)


def fig_first_layer(path, naming, keys, labels, n_layers: int = 52):
    import matplotlib.pyplot as plt

    _style(plt)
    both = naming["both"]
    order = sorted(keys, key=lambda k: (both[k]["first_layer_median"] or 99, k))
    fig, ax = plt.subplots(figsize=(8.0, 0.24 * len(keys) + 1.6))
    for j, src in enumerate(SOURCES):
        off = (j - 0.5) * 0.28
        for i, k in enumerate(order):
            m = naming[src][k]
            if m["first_layer_median"] is None:
                continue
            lo, hi = m["first_layer_iqr"]
            ax.plot([lo, hi], [i + off, i + off], color=COLOR[src], lw=2, alpha=0.45, solid_capstyle="round")
            ax.scatter([m["first_layer_median"]], [i + off], s=26, color=COLOR[src], edgecolor=SURFACE, lw=1.2,
                       zorder=3, label=SOURCE_LABEL[src] if i == 0 else None)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([f"{labels[keys.index(k)]}  ({100 * both[k]['accuracy']:.0f}%)" for k in order], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(30, n_layers + 0.5)
    ax.set_xlabel("decoder layer where the correct name first becomes the word lens's top guess (of 52)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, fontsize=8)
    ax.set_title("When does Glimmer settle on the name?", fontsize=13, pad=26)
    ax.xaxis.set_major_locator(__import__("matplotlib.ticker", fromlist=["MultipleLocator"]).MultipleLocator(2))
    _footnote(fig, "Median over correctly named pictures, with the interquartile range. In brackets: naming "
              "accuracy on all of the concept's 24-32 pictures.")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(path, dpi=180)
    plt.close(fig)


def fig_rho_by_layer(path, layer_corr: dict, measure: str, n_layers: int = 52, identity: dict | None = None):
    import matplotlib.pyplot as plt

    _style(plt)
    xs_layers = np.arange(1, n_layers + 1)
    if identity:
        fig, (top, ax) = plt.subplots(2, 1, figsize=(9, 7.2), sharex=True, gridspec_kw={"height_ratios": [1, 1.5]})
        for src in SOURCES:
            nn = [identity["nn_accuracy"][f"L{n}"][src] * 100 for n in xs_layers]
            top.plot(xs_layers, nn, color=COLOR[src], lw=2, label=SOURCE_LABEL[src])
            for xpos, space in ((-7, "vision_tower"), (-3, "projector")):
                top.scatter([xpos], [identity["nn_accuracy"][space][src] * 100], color=COLOR[src], s=26, zorder=3)
        top.axvline(0, color=GRID, lw=1.5)
        top.set_ylim(0, 100)
        top.set_ylabel("concept identity\n(1-NN accuracy, %)")
        top.set_title("Concept identity and the spread-naming link, layer by layer", fontsize=12)
        top.legend(loc="upper left", fontsize=8.5)
    else:
        fig, ax = plt.subplots(figsize=(9, 4.4))
    for src in SOURCES:
        rho = np.array([layer_corr[f"L{n}"][src][measure]["rho"] for n in xs_layers], float)
        lo = np.array([layer_corr[f"L{n}"][src][measure]["ci95"][0] for n in xs_layers], float)
        hi = np.array([layer_corr[f"L{n}"][src][measure]["ci95"][1] for n in xs_layers], float)
        ax.fill_between(xs_layers, lo, hi, color=COLOR[src], alpha=0.12, lw=0)
        ax.plot(xs_layers, rho, color=COLOR[src], lw=2, label=SOURCE_LABEL[src])
        for xpos, space in ((-7, "vision_tower"), (-3, "projector")):
            r = layer_corr[space][src][measure]
            ax.errorbar([xpos + (0.3 if src == "human" else -0.3)], [r["rho"]],
                        yerr=[[r["rho"] - r["ci95"][0]], [r["ci95"][1] - r["rho"]]], fmt="o", color=COLOR[src],
                        ms=5, lw=1.2)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xticks([-7, -3, 13, 26, 39, 46, 52])
    ax.set_xticklabels(["vision\ntower", "proj-\nector", "13", "26", "39", "46", "52"])
    ax.set_xlim(-9.5, n_layers + 1)
    ax.axvline(0, color=GRID, lw=1.5)
    ax.set_xlabel("decoder layer (answer position)")
    ylab = {"accuracy": "rho(spread, naming accuracy)", "logp": "rho(spread, log p(correct name))"}[measure]
    ax.set_ylabel(ylab)
    if identity:
        ax.text(0.01, 0.97, "spread vs naming", transform=ax.transAxes, fontsize=9, color=INK2, va="top")
    else:
        ax.legend(loc="lower left", fontsize=8.5)
        ax.set_title("Where in Glimmer does spread track naming?", fontsize=13)
    _footnote(fig, "Top: how often a picture's nearest neighbour (same source, centered cosine) is a picture of the "
              "same concept. Bottom: Spearman rho over concepts between within-concept spread and naming, with 95% "
              "bootstrap band. Late layers partly encode the answer itself, so their spread is not independent of "
              "naming.")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=180)
    plt.close(fig)


def fig_spread_profile(path, spread_tab, keys, n_layers: int = 52):
    import matplotlib.pyplot as plt

    _style(plt)
    fig, ax = plt.subplots(figsize=(9, 4.2))
    xs = np.arange(1, n_layers + 1)
    rng = np.random.default_rng(0)
    for src in SOURCES:
        mat = np.array([[spread_tab[f"L{n}"][src][k] for k in keys] for n in xs])  # (L, C)
        mean = mat.mean(1)
        boots = np.stack([mat[:, rng.integers(0, len(keys), len(keys))].mean(1) for _ in range(1000)])
        lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)
        ax.fill_between(xs, lo, hi, color=COLOR[src], alpha=0.15, lw=0)
        ax.plot(xs, mean, color=COLOR[src], lw=2, label=SOURCE_LABEL[src])
        for xpos, space in ((-7, "vision_tower"), (-3, "projector")):
            v = np.array([spread_tab[space][src][k] for k in keys])
            ax.scatter([xpos], [v.mean()], color=COLOR[src], s=30, zorder=3)
    ax.set_xticks([-7, -3, 13, 26, 39, 46, 52])
    ax.set_xticklabels(["vision\ntower", "proj-\nector", "13", "26", "39", "46", "52"])
    ax.set_xlim(-9.5, n_layers + 1)
    ax.axvline(0, color=GRID, lw=1.5)
    ax.set_xlabel("decoder layer (answer position)")
    ax.set_ylabel("mean within-concept spread")
    ax.legend(loc="upper right", fontsize=8.5)
    ax.set_title("How spread out are a concept's doodles, layer by layer?", fontsize=13)
    _footnote(fig, "Mean over concepts of the centered cosine spread, 95% bootstrap band over concepts. "
              "Spreads are comparable within a layer, not across layers.")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=180)
    plt.close(fig)


def space_label(space: str) -> str:
    return {"vision_tower": "vision tower", "projector": "projector", "dinov2": "DINOv2",
            "dinov2_core": "DINOv2 (core)"}.get(space, f"layer {space[1:]}" if space.startswith("L") else space)


def pretty_condition(name: str, e: dict) -> str:
    fam = e.get("family") or name
    dose = e.get("dose")
    desc = {
        "naming-mlp-mean": "naming-localizer neurons, mean-ablated",
        "naming-heads-zero": "naming-localizer heads, zeroed",
        "late-band-noise": "noise on layers 41-48",
        "early-band-noise": "noise on layers 9-16",
        "random-mlp-mean": "random neurons, mean-ablated",
    }.get(fam, fam)
    if "random-matched" in name:
        desc = "random units, same count per layer\n(control for " + desc.split(",")[0] + ")"
    elif dose is not None:
        desc += f"\n({'noise sd x' if 'noise' in fam else 'top '}{dose:.3g}{'' if 'noise' in fam else ' of units'})"
    return f"{desc}; accuracy {100 * e['accuracy']:.0f}%"


def short_condition(name: str, e: dict) -> str:
    fam = e.get("family") or name
    desc = {"naming-mlp-mean": "naming neurons", "naming-heads-zero": "naming heads",
            "late-band-noise": "noise, layers 41-48", "early-band-noise": "noise, layers 9-16",
            "random-mlp-mean": "random neurons (matched damage)"}.get(fam, fam)
    if "random-matched" in name:
        desc = f"random, same count as {desc}"
    return f"{desc} ({100 * e['accuracy']:.0f}%)"


# --- main -------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=ROOT / "inside_glimmer" / "raw")
    ap.add_argument("--core", type=Path, default=ROOT / "core")
    ap.add_argument("--out", type=Path, default=ROOT / "inside_glimmer")
    ap.add_argument("--reps", type=int, default=4000)
    ap.add_argument("--spread-reps", type=int, default=2000)
    args = ap.parse_args()

    pics, intact, dist, conditions, calibration = load_raw(args.raw, args.core)
    items = intact["items"]
    assert len(items) == len(pics)
    keys = sorted({p.key for p in pics})
    labels = [names_for(k)[0] for k in keys]
    n_layers = len(items[0]["p_word"])

    sp = spreads(dist, keys, args.spread_reps)
    spread_tab = {space: sp["values"][space]["centered"] for space in sp["values"]}
    spread_tab_raw = {space: sp["values"][space]["raw"] for space in sp["values"]}
    dino_emb = dinov2_cls(pics, args.raw / "dinov2_cls.npy")
    dino = dinov2_spreads(dino_emb, pics, keys, args.spread_reps)
    spread_tab["dinov2"] = dino["values"]
    core = core_dinov2(args.core, keys)
    if core:
        spread_tab["dinov2_core"] = {s: {k: core.get(s, {}).get(k, np.nan) for k in keys} for s in SOURCES}

    naming = naming_measures(items, pics, keys)
    corr = correlations(spread_tab, naming, keys, args.reps)
    corr_raw = correlations({s: spread_tab_raw[s] for s in SPACES_NAMED}, naming, keys, 1000)
    # sensitivity: drop the concepts whose misses are name agreement, not recognition (Muse Image's
    # "hat" is a baseball cap that Glimmer calls "cap"; "yoga" pictures get pose names)
    kept = [k for k in keys if k not in NAME_AGREEMENT_ISSUES]
    sens_spaces = ["dinov2", "dinov2_core", "vision_tower", "projector", PRIMARY_LAYER, "L39"]
    sensitivity = {"excluded": sorted(NAME_AGREEMENT_ISSUES), "spread_vs_naming": {
        space: {src: {m: v[src][m] for m in ("accuracy", "logp")} for src in v}
        for space, v in correlations({sp: spread_tab[sp] for sp in sens_spaces if sp in spread_tab},
                                     {s: {k: naming[s][k] for k in kept} for s in naming}, kept, args.reps).items()}}
    arrays = args.raw / "intact_arrays.npz"
    identity = concept_identity(arrays, pics, keys) if arrays.exists() else None
    rel_corr = {}
    if identity:
        rel_tab = {space: identity["relative_spread"][space] for space in SPACES_NAMED}
        rel_corr = {space: {src: {m: v[src][m] for m in ("accuracy", "logp")} for src in v}
                    for space, v in correlations(rel_tab, naming, keys, args.reps).items()}
    lesion_spaces = [s for s in ["dinov2_core", "dinov2", "vision_tower", "projector", PRIMARY_LAYER, "L39"]
                     if s in spread_tab]
    lesions = lesion_analysis(conditions, naming, items, pics, keys, {s: spread_tab[s] for s in lesion_spaces},
                              args.reps)
    typicality = item_typicality(dist, dino_emb, pics, items, conditions, reps=2000)

    # AI vs human spread inside Glimmer, per space: paired over concepts
    ai_vs_human = {}
    for space in ["dinov2", *SPACES_NAMED]:
        a, h = vector(spread_tab[space]["ai"], keys), vector(spread_tab[space]["human"], keys)
        d = h - a
        rng = np.random.default_rng(0)
        boots = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(4000)]
        ai_vs_human[space] = {"ai_mean": float(a.mean()), "human_mean": float(h.mean()),
                              "human_minus_ai": float(d.mean()), "ci95": ci(boots),
                              "concepts_human_wider": int((d > 0).sum()), "n": len(keys),
                              "rho_ai_human": spearman(a, h)}
    # agreement of Glimmer spread with DINOv2 spread
    agreement = {f"{space}~{ref}": {src: spearman_ci(vector(spread_tab[space][src], keys),
                                                     vector(spread_tab[ref][src], keys), reps=args.reps)
                                    for src in SOURCES}
                 for space in SPACES_NAMED for ref in (["dinov2", "dinov2_core"] if core else ["dinov2"])}

    figs = args.out / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    for old in figs.glob("*.png"):  # figures are regenerated from scratch
        old.unlink()
    dino_fig = ("dinov2_core", "DINOv2 (core experiment; human = 200-drawing pool)") if core else \
        ("dinov2", "DINOv2 picture similarity")
    sets = [(dino_fig[1], spread_tab[dino_fig[0]]), ("Glimmer vision tower", spread_tab["vision_tower"]),
            ("Glimmer projector (image embeddings entering the decoder)", spread_tab["projector"]),
            (f"Glimmer decoder {space_label(PRIMARY_LAYER)} (answer position)", spread_tab[PRIMARY_LAYER])]
    corr_fn = lambda x, y: spearman_ci(x, y, reps=args.reps)  # noqa: E731
    fig_spread_vs_naming(figs / "spread_vs_naming_human.png", sets, naming, keys, labels, corr_fn, "accuracy",
                         "human", "Human doodles: are more spread-out concepts harder for Glimmer to name?")
    fig_spread_vs_naming(figs / "spread_vs_naming_ai_logp.png", sets, naming, keys, labels, corr_fn, "logp",
                         "ai", "AI doodles: does spread lower Glimmer's confidence in the name?")
    for measure in ("accuracy", "logp"):
        fig_rho_by_layer(figs / f"rho_by_layer_{measure}.png", corr, measure, n_layers, identity)
    fig_first_layer(figs / "first_correct_layer.png", naming, keys, labels, n_layers)
    fig_spread_profile(figs / "spread_by_layer.png", spread_tab, keys, n_layers)
    order = sorted(lesions, key=lambda n: (lesions[n].get("family") or "", "random" in n, n))
    for space in (dino_fig[0], "projector") if order else ():
        fig_spread_vs_lesion(figs / f"spread_vs_lesion_{space}.png", lesions, spread_tab, keys, labels, space, order)
    fig_typicality(figs / "typicality_items.png", typicality, lesions, order)

    per_concept = {}
    for i, k in enumerate(keys):
        per_concept[k] = {
            "label": labels[i], "accepted_names": [names_for(k)[0], *names_for(k)[1]],
            "spread": {space: {s: spread_tab[space][s][k] for s in SOURCES} for space in ["dinov2", *SPACES_NAMED]
                       + (["dinov2_core"] if core else [])},
            "spread_ci95": {**{space: {s: sp["ci95"][space][s][k] for s in SOURCES} for space in SPACES_NAMED},
                            "dinov2": {s: dino["ci95"][s][k] for s in SOURCES}},
            "naming": {s: naming[s][k] for s in (*SOURCES, "both")},
            "lesion_accuracy": {n: lesions[n]["per_concept"][k]["accuracy"] for n in lesions},
        }
    results = {
        "experiment": "Plato's Chair inside Glimmer (exploratory)",
        "question": "How spread out is each concept inside Muse Glimmer, and does spread predict naming "
                    "difficulty and vulnerability to damage?",
        "status": "exploratory; ~40 concepts; many comparisons; CIs are 95% bootstrap over concepts "
                  "(spread CIs: over pictures)",
        "credit": QUICKDRAW_CREDIT,
        "models": {"namer": "Muse Glimmer 30B (FP8 decoder, self-hosted)", "pictures": "Muse Image 1.0",
                   "embedding": "DINOv2-base (facebook/dinov2-base), CLS token"},
        "method": {
            "prompt": intact.get("prompt"), "picture_side_px": intact.get("side"),
            "pictures_per_source": {k: sum(p.key == k and p.source == "ai" for p in pics) for k in keys},
            "n_concepts": len(keys), "n_pictures": len(pics),
            "spread": "mean pairwise cosine distance among a concept's pictures; Glimmer spaces centered on the "
                      "mean over all pictures; DINOv2 raw cosine (as in the core experiment)",
            "spaces": {"vision_tower": "vision tower output (vision_adapter input, 6144-d), mean over the "
                                       "picture's 256 image tokens",
                       "projector": "projector output (decoder image embeddings, 6656-d), mean over image tokens",
                       "L<n>": "residual stream after decoder layer n (1-indexed, 52 layers) at the answer position"},
            "word_lens": "full-word lens: p(name) at layer l = product over the name's tokens of the lens "
                         "probability (final norm + output head on layer l's residual), summed over accepted "
                         "names and spellings; first correct layer = first layer where every token of an "
                         "accepted name is the lens's top guess",
            "primary": f"human doodles; spread at the vision tower and decoder {space_label(PRIMARY_LAYER)} "
                       "(mid-decoder, before the name appears in the word lens)",
            "lesions": "reversible hooks from metalesionlab/lesions.py; doses calibrated on 2 AI + 2 human "
                       "pictures per concept to roughly half of intact accuracy",
        },
        "calibration": calibration,
        "intact": {"accuracy": {s: float(np.mean(vector(naming[s], keys, "accuracy"))) for s in (*SOURCES, "both")},
                   "first_layer_median": {s: float(np.nanmedian(vector(naming[s], keys, "first_layer_median")))
                                          for s in (*SOURCES, "both")}},
        "ai_vs_human_spread": ai_vs_human,
        "spread_agreement": agreement,
        "spread_vs_naming": {space: corr[space] for space in ["dinov2", *SPACES_NAMED]
                             + (["dinov2_core"] if core else [])},
        "spread_vs_naming_raw_cosine": corr_raw,
        "concept_identity": None if not identity else {
            "what": "leave-one-out 1-NN concept accuracy within each source, and within/between distance ratio",
            "nn_accuracy": identity["nn_accuracy"], "within_between": identity["within_between"]},
        "spread_vs_naming_relative_spread": rel_corr,
        "sensitivity_without_name_agreement_issues": sensitivity,
        "rho_by_layer": {f"L{n}": {s: {m: corr[f'L{n}'][s][m] for m in ("accuracy", "logp")} for s in SOURCES}
                         for n in range(1, n_layers + 1)},
        "lesions": lesions,
        "item_typicality": typicality,
        "per_concept": per_concept,
        "figures": sorted(str(p.relative_to(args.out)) for p in figs.glob("*.png")),
    }
    save_json(results, args.out / "results.json")
    print(f"results -> {args.out / 'results.json'}; figures -> {figs}")


if __name__ == "__main__":
    main()
