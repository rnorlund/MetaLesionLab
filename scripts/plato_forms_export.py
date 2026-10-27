"""Plato's Forms: derived statistics for the repository, from the results in the data folder.

Usage: python -I scripts/plato_forms_export.py
Reads $PLATO_FORMS_DIR/results_clock.json and results_concepts.json (and the core results.json for the
35-concept reference) and writes
- public_data/plato_forms.json            derived statistics only: shares, CIs, counts of read times,
                                           spreads and ranks; no pictures, embeddings or per-picture readings
- metalesionlab/web/data/plato_forms.json the same, which the /plato/forms page reads
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab.plato import PLATO_DIR, QUICKDRAW_CREDIT  # noqa: E402
from metalesionlab.plato_forms import CLOCK_TIMES, FORMS_DIR, PHOTO_TIMES, REPUBLIC_X, clock_prompt, my_spend  # noqa: E402
from metalesionlab.plato_web import clean  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
GROUP_KEEP = ("n", "status", "share_no_hands", "ten_ten", "ten_ten_of_readable", "ten_ten_p_vs_chance", "ten_ten_exact",
              "times", "accuracy", "accuracy_ci95_cluster", "accuracy_either_order", "accuracy_either_order_ci95_cluster",
              "ten_ten_ci95_cluster", "hour_correct_of_readable", "median_error_min", "mean_error_min",
              "ten_ten_hour_slack", "ten_ten_hour_slack_p_vs_chance", "accuracy_hour_slack",
              "accuracy_hour_slack_ci95_cluster", "minute_correct")
CONCEPT_KEEP = ("key", "label", "quickdraw", "note", "n_ai", "n_human_pool", "ai_spread", "ai_spread_ci95", "human_spread",
                "human_spread_ci95", "human_spread_range95_for_n", "homogenization_index", "homogenization_index_ci95",
                "share_of_human_sets_as_uniform_as_ai", "patch_mean", "ai_relative_spread", "human_relative_spread",
                "relative_homogenization_index", "ai_nearest_human_centroid_is_own_of_37",
                "human_nearest_human_centroid_is_own_of_37", "ai_confused_with", "human_confused_with", "conditions",
                "muse_over_sdxl", "muse_over_sdxl_ci95", "ranks_among_core", "listed_kinds",
                "ai_same_call_distance", "ai_cross_call_distance")


def clock_block(res: dict) -> dict:
    groups = {}
    for name, g in res["groups"].items():
        out = {k: g[k] for k in GROUP_KEEP if k in g}
        if "per_time" in g:  # per requested time: counts only
            out["per_time"] = {t: {k: x[k] for k in ("n", "correct", "correct_either_order", "ten_ten", "no_time")}
                               | {"read": sorted({r for r in x["read"] if r}, key=lambda r: -x["read"].count(r))[:3]}
                               for t, x in g["per_time"].items()}
            out["asked_vs_read"] = [[t, r, x["read"].count(r)] for t, x in g["per_time"].items()
                                    for r in sorted({r for r in x["read"] if r})]
            out["asked_no_time"] = {t: x["read"].count(None) for t, x in g["per_time"].items()}
        groups[name] = out
    val = res.get("validation") or {}
    spot = res.get("spotcheck") or {}
    return {
        "question": "What time does an AI draw on a clock? Image generators are widely reported to draw about 10:10, "
                    "the time on watch adverts, whatever time is asked for.",
        "prompts": {"doodle_no_time": clock_prompt("doodle"), "doodle_time": clock_prompt("doodle", "3:00"),
                    "photo_no_time": clock_prompt("photo"), "photo_time": clock_prompt("photo", "3:00")},
        "times_asked": CLOCK_TIMES, "photo_times_asked": PHOTO_TIMES,
        "reader": "Muse Spark 1.3 (vision), prompt v1, minimal reasoning; validated on clocks drawn by code",
        "window_min": res["window_min"], "correct_within_min": res["correct_within_min"],
        "chance_ten_ten": res["chance_ten_ten"], "chance_ten_ten_hour_slack": res["chance_ten_ten_hour_slack"],
        "groups": groups, "comparisons_ten_ten": res["comparisons_ten_ten"],
        "byeye_no_time": res.get("byeye_no_time"),
        "predictions": res["predictions"],
        "validation": val,
        "spotcheck": {k: spot[k] for k in ("n_sample", "n_scored", "agree", "agreement", "agree_on_ten_ten",
                                           "unclear_by_eye", "by_source") if k in spot} or None,
    }


def concepts_block(cres: dict) -> dict:
    core = json.loads((PLATO_DIR / "results.json").read_text())["concepts"]
    return {
        "republic_x": REPUBLIC_X,
        "core_reference": cres["core_reference"],
        "core_concepts": [{"label": c["label"], "index": c["homogenization_index"], "index_ci95": c["homogenization_index_ci95"],
                           "ai_spread": c["ai_spread"], "human_spread": c["human_spread"]} for c in core],
        "prediction_B2_table_in_most_homogenized_third": cres["prediction_B2_table_in_most_homogenized_third"],
        "items": {r["key"]: {k: r[k] for k in CONCEPT_KEEP if k in r} for r in cres["concepts"]},
    }


def main():
    res = json.loads((FORMS_DIR / "results_clock.json").read_text())
    cres = json.loads((FORMS_DIR / "results_concepts.json").read_text())
    data = {
        "about": "Plato's Forms: (1) what time Muse Image, Stable Diffusion XL and people draw on a clock, read by "
                 "Muse Spark; (2) Plato's own examples, the bed and the table, in the Plato's Chair spread measure "
                 "(Meta DINOv2). Derived statistics only: no pictures, embeddings or per-picture readings. "
                 "See docs/plato_forms.md; plan in docs/plato_forms_plan.md.",
        "attribution": QUICKDRAW_CREDIT,
        "credits": {"human_drawings": "Google Quick, Draw! (CC BY 4.0)", "ai": "Muse Image 1.0 and Muse Spark 1.3 (Meta); "
                    "Stable Diffusion XL base 1.0 (Stability AI, CreativeML OpenRAIL++-M); DINOv2 (Meta, Apache 2.0)"},
        "embedding_model": cres["embedding_model"],
        "clock": clock_block(res),
        "concepts": concepts_block(cres),
        "cost_usd": round(my_spend(), 2),
    }
    data = clean(data)
    for path in (REPO / "public_data" / "plato_forms.json", REPO / "metalesionlab" / "web" / "data" / "plato_forms.json"):
        path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
        print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
