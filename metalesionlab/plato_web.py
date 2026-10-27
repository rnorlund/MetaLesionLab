"""Plato's Chair for the web page: compact statistics from the result files, no pictures.

The Plato's Chair data folder (AI and human pictures, embeddings, raw results) lives outside this
repository. scripts/plato_web_export.py calls build() on it and writes the small JSON the /plato page
reads (metalesionlab/web/data/plato.json). sdxl_block() is shared with the web route, which reads a
newer SDXL comparison from the data folder when one is there. Light imports only: json and math.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

QUICKDRAW_CREDIT = ("Human drawings: Google Quick, Draw! dataset (Google Creative Lab), CC BY 4.0, "
                    "https://github.com/googlecreativelab/quickdraw-dataset")
DATA_FOLDER_NOTE = ("The full Plato's Chair data folder (pictures, embeddings and raw results) lives outside "
                    "this repository; this file holds statistics only.")
# The hero's four concepts: (core key, page key, label, plural shown in the toggle)
HERO = [("chair", "chair", "Chair", "chairs"), ("sailboat", "boat", "Boat", "sailboats"),
        ("face", "face", "Face", "faces"), ("yoga", "person", "Person", "people doing yoga")]
# Targeted lesions for the "honest null" (inside_glimmer family keys) and how the page names them.
LESIONS = [("naming-mlp-mean@0.2", "Naming neurons switched to their average"),
           ("naming-heads-zero", "Naming attention heads switched off"),
           ("late-band-noise", "Noise in layers 41–48")]
CONTROLS = ["naming-mlp-mean@0.2-random-matched", "naming-heads-zero-random-matched", "random-mlp-mean@0.36"]
BENCH_ITEM = 44          # inside_glimmer/raw/intact.json: a person's bench, named "Table" (bench/148.png)
BENCH_LAYERS = range(38, 53)


def clean(x):
    """JSON-safe: NaN and infinities become None, floats are rounded."""
    if isinstance(x, float):
        return round(x, 4) if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return x


def _read(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _corr(c: dict | None) -> dict | None:
    if not isinstance(c, dict) or c.get("rho") is None:
        return None
    return {"rho": c["rho"], "ci95": c.get("ci95"), "p": c.get("p_perm"), "n": c.get("n")}


def core_block(res: dict) -> dict:
    s = res["summary"]
    concepts = [{"key": c["key"], "label": c["label"], "quickdraw": c["quickdraw"], "kind": c.get("kind"),
                 "n_ai": c.get("n_ai"), "ai_spread": c["ai_spread"], "human_spread": c["human_spread"],
                 "index": c["homogenization_index"], "index_ci95": c.get("homogenization_index_ci95")}
                for c in res["concepts"]]
    return {"n_concepts": s["n_concepts"], "median_index": s["median_homogenization_index"],
            "below_1": s["concepts_with_index_below_1"], "ci_below_1": s["concepts_with_index_ci_below_1"],
            "below_every_human_subset": s.get("concepts_ai_below_every_human_subset"),
            "mean_spread": s.get("mean_within_spread"), "rho_ai_human": _corr(s.get("rank_correlation_ai_vs_human_spread")),
            "most_uniform": s.get("most_uniform_ai"), "least_homogenized": s.get("least_homogenized"),
            "concepts": concepts}


def hero_block(core: dict) -> list[dict]:
    by_key = {c["key"]: c for c in core["concepts"]}
    out = []
    for key, page_key, label, plural in HERO:
        c = by_key.get(key)
        if not c:
            continue
        out.append({"key": page_key, "core_key": key, "label": label, "plural": plural, "n": c["n_ai"],
                    "ai_spread": c["ai_spread"], "human_spread": c["human_spread"], "index": c["index"],
                    "index_ci95": c["index_ci95"], "ai_img": f"grid_{page_key}_ai.webp",
                    "people_img": f"grid_{page_key}_people.webp"})
    return out


def languages_block(pub: dict) -> dict:
    """Group shares (how much of the variation the language or country explains), [estimate, lo, hi]."""
    pc = pub["per_concept"]
    keep = ("share_ai", "share_ai_p", "share_ai_style_removed", "share_ai_style_removed_p", "share_human", "share_human_style_removed",
            "spread_ai", "spread_human")
    return {"concepts": pub["concepts"], "languages": pub["languages"], "countries": pub["countries"],
            "words": {lang: {k: pub["words"][lang][k] for k in ("chair", "hat", "bird")} for lang in pub["words"]},
            "per_concept": {k: {f: pc[k].get(f) for f in keep} for k in pc},
            "summary": {k: pub["summary"].get(k) for k in ("mean_share_ai", "mean_share_human", "concepts_ai_gt_human")},
            "summary_style_removed": {k: pub["summary_style_removed"].get(k) for k in ("mean_share_ai", "mean_share_human")},
            "n": pub["n"]}


def inside_block(res: dict, intact: dict | None) -> dict:
    pc = res["per_concept"]
    scatter = []
    for key, c in pc.items():
        spread = (c.get("spread") or {}).get("dinov2_core", {}).get("human")
        acc = ((c.get("naming") or {}).get("human") or {}).get("accuracy")
        if spread is not None and acc is not None:
            scatter.append({"key": key, "label": c.get("label", key), "spread": spread, "accuracy": acc})
    lesions = []
    for fam, label in LESIONS:
        L = res["lesions"].get(fam) or {}
        r = _corr((L.get("spread_vs_lost_rate") or {}).get("dinov2_core"))
        if r:
            lesions.append({"family": fam, "label": label, "accuracy": L.get("accuracy"), **r})
    controls = [_corr(((res["lesions"].get(f) or {}).get("spread_vs_lost_rate") or {}).get("dinov2_core")) for f in CONTROLS]
    controls = [c["rho"] for c in controls if c]
    layers = {k: {"ai": v["ai_mean"], "human": v["human_mean"], "gap_ci95": v["ci95"], "human_wider": v["concepts_human_wider"],
                  "n": v["n"]} for k, v in res["ai_vs_human_spread"].items()}
    bench = None
    if intact and len(intact.get("items", [])) > BENCH_ITEM:
        it = intact["items"][BENCH_ITEM]
        if it.get("key") == "bench" and it.get("source") == "human":
            bench = {"said": it["said"], "layers": list(BENCH_LAYERS),
                     "top": [str(it["top"][i - 1]).strip() for i in BENCH_LAYERS],
                     "p_name": [it["p_word"][i - 1] for i in BENCH_LAYERS]}
    bench_naming = ((pc.get("bench") or {}).get("naming") or {}).get("human") or {}
    return {"accuracy": res["intact"]["accuracy"], "first_layer_median": res["intact"]["first_layer_median"],
            "layer_spread": layers,
            "naming": _corr(res["spread_vs_naming"]["dinov2_core"]["human"]["accuracy"]),
            "naming_projector": _corr(res["spread_vs_naming"]["projector"]["human"]["accuracy"]),
            "scatter": sorted(scatter, key=lambda x: x["key"]),
            "bench": bench, "bench_human": {"n": bench_naming.get("n"), "accuracy": bench_naming.get("accuracy"),
                                            "answers": bench_naming.get("answers")},
            "lesions": lesions, "control_rhos": controls,
            "typicality_auc": (res.get("item_typicality") or {}).get("intact_error", {}).get("projector")}


def sdxl_block(res: dict | None, n_total: int = 35) -> dict | None:
    """The second-image-model comparison, from core/results_sdxl.json (or SDXL fields in core/results.json)."""
    if not isinstance(res, dict):
        return None
    if "sdxl" in res and isinstance(res["sdxl"], dict):  # SDXL fields nested in the core results
        res = res["sdxl"]
    s = res.get("summary") or {}
    vs_h, vs_m = s.get("sdxl_vs_human"), s.get("muse_vs_sdxl")
    if not (isinstance(vs_h, dict) and isinstance(vs_m, dict) and s.get("n_concepts")):
        return None
    n = int(s["n_concepts"])
    style = (s.get("style") or {}).get("sdxl") or {}
    ctrl = s.get("style_controlled") or {}
    concepts = [{"label": c.get("label"), "sdxl_index": c.get("sdxl_index"), "sdxl_index_ci95": c.get("sdxl_index_ci95"),
                 "muse_index": c.get("muse_index"), "sdxl_spread": c.get("sdxl_spread"), "muse_spread": c.get("muse_spread"),
                 "human_spread": c.get("human_spread")} for c in res.get("concepts") or [] if c.get("sdxl_index") is not None]
    return clean({
        "model": (res.get("image_models") or {}).get("sdxl", "stabilityai/stable-diffusion-xl-base-1.0"),
        "license": (res.get("sdxl_settings") or {}).get("license"),
        "n_concepts": n, "n_total": n_total, "complete": n >= n_total,
        "median_index": vs_h.get("median_index"),
        "index_above_1": len(vs_h.get("concepts_with_index_above_1") or []),
        "index_ci_above_1": vs_h.get("concepts_with_index_ci_above_1"),
        "index_ci_below_1": vs_h.get("concepts_with_index_ci_below_1"),
        "muse_more_uniform": vs_m.get("concepts_muse_more_uniform"),
        "muse_more_uniform_ci": vs_m.get("concepts_muse_more_uniform_ci"),
        "median_muse_over_sdxl": vs_m.get("median_muse_over_sdxl"),
        "mean_spread": vs_m.get("mean_spread"),
        "full_bleed_share": style.get("full_bleed_share"),
        "style_controlled": {"n_concepts": ctrl.get("n_concepts"), "median_index": ctrl.get("median_index")} if ctrl else None,
        "rho_muse_sdxl": _corr(s.get("rank_correlation_sdxl_vs_muse_spread")),
        "concepts": concepts,
    })


VARIETY_CONDITIONS = ["default", "any", "unusual", "listed", "sdxl_default", "sdxl_any", "sdxl_listed"]
VARIETY_FOCUS = ["chair", "umbrella", "hat"]


def variety_block(res: dict | None) -> dict | None:
    """'Can you prompt it out of the Platonic chair?', from core/results_variety.json: visual spread by
    prompt (ratio to people), the chair and umbrella numbers, and the kind labels (Glimmer) summary."""
    if not isinstance(res, dict) or not isinstance(res.get("visual"), dict):
        return None
    vis = res["visual"].get("all") or {}
    conds = {}
    for cond in VARIETY_CONDITIONS:
        s = vis.get(cond)
        if s:
            conds[cond] = {"n": s["n_concepts"], "median_ratio": s["median_ratio_vs_people"],
                           "above_people": s["concepts_above_people"], "ci_above_people": s.get("concepts_ci_above_people"),
                           "median_vs_default": s.get("median_ratio_vs_default"),
                           "recognised": s.get("nearest_own_human_centroid")}
    if "default" not in conds or len(conds) < 2:
        return None
    concepts, focus = [], {}
    for r in res.get("concepts") or []:
        row = {"key": r["key"], "label": r["label"]}
        for cond in VARIETY_CONDITIONS:
            if isinstance(r.get(cond), dict):
                row[cond] = r[cond].get("ratio_vs_people")
        concepts.append(row)
        if r["key"] in VARIETY_FOCUS:
            kinds = r.get("kinds") or {}
            focus[r["key"]] = {
                "people_spread": (r.get("default") or {}).get("human_spread"),
                "spread": {c: r[c]["spread"] for c in VARIETY_CONDITIONS if isinstance(r.get(c), dict)},
                "ratio": {c: r[c]["ratio_vs_people"] for c in VARIETY_CONDITIONS if isinstance(r.get(c), dict)},
                "recognised": {c: r[c].get("nearest_own_human_centroid") for c in VARIETY_CONDITIONS
                               if isinstance(r.get(c), dict)},
                "kinds": {c: {f: kinds[c].get(f) for f in ("n", "distinct_at_n", "simpson", "share_plain", "share_none",
                                                          "prototype", "prototype_share")}
                          for c in ("default", "any", "unusual", "listed", "people") if isinstance(kinds.get(c), dict)}}
    k = res.get("kinds") or {}
    val = k.get("validation") or {}
    rel = k.get("reliable") or {}
    kinds = None
    if val.get("n_pictures"):
        kinds = {"accuracy": val.get("accuracy"), "lenient_accuracy": val.get("lenient_accuracy"),
                 "n_pictures": val.get("n_pictures"), "chance": val.get("mean_chance"),
                 "reliable": len(val.get("reliable_concepts") or []), "n_concepts": val.get("n_concepts"),
                 "summary": {c: {f: (rel.get(c) or {}).get(f) for f in ("n_concepts", "median_simpson", "mean_simpson",
                                                                     "mean_share_plain", "mean_share_none",
                                                                     "mean_distinct_at_n", "concepts_prototype_plain")}
                             for c in ("default", "any", "unusual", "listed", "people", "sdxl_default") if rel.get(c)},
                 "people_vs_default": rel.get("people_vs_default"),
                 "people_spread_within_prototype": rel.get("people_spread_within_prototype")}
    return clean({"conditions": conds, "concepts": concepts, "focus": focus, "kinds": kinds,
                  "prompts": res.get("conditions")})


def build(core_dir: Path, lang_results_public: Path, inside_dir: Path) -> dict:
    """Everything the /plato page shows, from the data folder (core/, inside_glimmer/) and the public
    languages statistics. Statistics only: no pictures, embeddings or per-drawing data."""
    core_res = json.loads((core_dir / "results.json").read_text())
    core = core_block(core_res)
    pub_lang = json.loads(lang_results_public.read_text())
    inside_res = json.loads((inside_dir / "results.json").read_text())
    sdxl = sdxl_block(_read(core_dir / "results_sdxl.json"), core["n_concepts"]) or sdxl_block(core_res, core["n_concepts"])
    return clean({
        "about": "Plato's Chair: how varied Muse Image's doodles of a concept are, compared with people's drawings "
                 "of the same word (Google Quick, Draw!), measured with Meta DINOv2; what happens when it is asked "
                 "for variety; the same across six prompt languages; and inside Muse Glimmer. Derived statistics only.",
        "credits": {"human_drawings": QUICKDRAW_CREDIT, "ai_drawings": "Muse Image 1.0 (Meta)",
                    "embeddings": "DINOv2 (facebook/dinov2-base, Meta, Apache-2.0)",
                    "namer": "Muse Glimmer 30B (Meta, open weights, self-hosted)",
                    "kind_lists": "Muse Spark 1.3 (Meta)"},
        "data_folder": DATA_FOLDER_NOTE,
        "core": core, "hero": hero_block(core), "languages": languages_block(pub_lang),
        "inside": inside_block(inside_res, _read(inside_dir / "raw" / "intact.json")),
        "sdxl": sdxl,
        "variety": variety_block(_read(core_dir / "results_variety.json")),
    })
