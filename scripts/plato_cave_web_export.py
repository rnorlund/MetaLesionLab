"""Plato's Cave: the page's data (metalesionlab/web/data/plato_cave.json) and the public statistics
(public_data/plato_cave.json), from $CAVE_DIR/results.json.

Both hold derived statistics and Muse Glimmer's / Muse Spark's own answers only. People's item-level
silhouette rates (Wagemans et al. 2008) carry no licence, so neither file contains them: only the published
means, our correlation with them, and which concepts fall in each agree/disagree group.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab import plato_cave as pc  # noqa: E402
from metalesionlab.plato import to_jsonable  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
GAME_WORDS = ["rabbit", "anchor", "hat", "scissors", "glove", "bicycle", "sock", "guitar", "igloo", "cat", "eye",
              "helicopter"]
CREDITS = {
    "human_norms": pc.CREDIT_NORMS + " Published means and our concept-level comparison only; no licence is "
                   "stated for the item-level data, so they are not redistributed.",
    "pictures": "Line drawings: Meta Muse Image 1.0 (the project's checked core naming set). Outlines, silhouettes "
                "and shadows: made by code from them.",
    "models": "Naming: Muse Glimmer 30B (open weights, self-hosted) and Muse Spark 1.3. Visual-error coding: "
              "Muse Spark as second rater.",
}


def r3(x):
    return None if x is None else round(float(x), 3)


def main():
    res = json.loads((pc.CAVE_DIR / "results.json").read_text())
    acc = {v: {"accuracy": r3(e["accuracy"]), "ci95": [r3(c) for c in e["ci95"]], "n": e["n"],
               **({"diff_vs_original": r3(e["diff_vs_original"]), "diff_ci95": [r3(c) for c in e["diff_ci95"]],
                   "mcnemar_p": r3(e["mcnemar_p"])} if "diff_vs_original" in e else {})}
           for v, e in res["glimmer_accuracy"].items()}
    sp = res.get("spark", {})
    spark = {"n_items": sp.get("n_items"),
             "accuracy": {v: {"accuracy": r3(e["accuracy"]), "ci95": [r3(c) for c in e["ci95"]]}
                          for v, e in sp.get("accuracy", {}).items()},
             "glimmer_on_same": {v: r3(e["accuracy"]) for v, e in sp.get("glimmer_on_same", {}).items()},
             "medium_answers": {v: m["medium"] for v, m in res.get("spark_medium_answers", {}).items()}}
    hum = res["human"]
    human = {"published": hum["published"], "n_shared_concepts": len(hum["shared"])}
    for v in ("silhouette", "outline"):
        h = hum[v]
        human[v] = {"rho_correct": {k: r3(x) if not isinstance(x, list) else [r3(c) for c in x]
                                    for k, x in h["rho_correct"].items()},
                    "rho_p_name": {k: r3(x) if not isinstance(x, list) else [r3(c) for c in x]
                                   for k, x in h["rho_p_name"].items()},
                    "ai_accuracy_on_shared": r3(h["ai_accuracy"]), "people_mean_on_shared": r3(h["human_mean"]),
                    "ai_acc_where_people_below_50": r3(h["ai_acc_human_hard"]), "n_people_below_50": h["n_human_hard"],
                    "ai_acc_where_people_below_50_ci95": [r3(c) for c in h["ai_acc_human_hard_ci95"] or []],
                    "ai_acc_where_people_above_90": r3(h["ai_acc_human_easy"]), "n_people_above_90": h["n_human_easy"],
                    "both_fail": h["both_fail"], "people_fail_ai_names": h["people_fail_ai_names"],
                    "ai_fails_people_name": h["ai_fails_people_name"]}
    errors = {v: {"counts": e["counts"], "n_errors": e["n_errors"], "rated": e["rated"], "visual": e["visual"],
                  "rater_codes": e["rater_codes"]} for v, e in res["errors"].items()}
    medium = res["medium_answers"]
    lens = {v: {"mean_p_name_by_layer": [r3(x) for x in res["word_lens"][v]["mean_p_name_by_layer"]],
                **{k: (r3(x) if not isinstance(x, list) else [r3(c) for c in x])
                   for k, x in res["word_lens"][v].items() if k.startswith(("first_layer", "stable_layer"))}}
            for v in pc.VERSIONS}
    surv = res["survival"]
    survival = {k: surv[k] for k in ("all_four", "lost_as_silhouette", "lost_as_shadow", "lost_in_all_three",
                                     "most_robust", "least_robust")}
    per = surv["per_item"]
    spark_rows = {(r["word"], r["version"]): r for r in sp.get("rows", [])}
    alts = {it["word"]: it["alternates"] for it in res["stimuli"]["items"]}
    items = [{"word": w, "alternates": alts.get(w, []),
              **{v: {"said": per[w][v]["said"], "code": per[w][v]["code"]} for v in pc.VERSIONS}}
             for w in sorted(per)]
    game = []
    for w in GAME_WORDS:
        g = {"word": w, "alternates": alts.get(w, []), "shadow_img": f"cave_shadow_{w}.webp",
             "original_img": f"cave_original_{w}.webp",
             "glimmer": {v: {"said": per[w][v]["said"], "code": per[w][v]["code"]} for v in pc.VERSIONS}}
        if (w, "shadow") in spark_rows:
            g["spark"] = {"said": spark_rows[(w, "shadow")]["said"], "code": spark_rows[(w, "shadow")]["code"]}
        game.append(g)
    common = {
        "title": "Plato's Cave: name the shadow",
        "n_pictures": res["n_pictures"], "versions": res["versions"], "prompt": res["prompt"],
        "accuracy": acc, "spark": spark, "human": human, "errors": errors, "medium_answers": medium,
        "word_lens": lens, "word_lens_n_layers": res["word_lens"]["n_layers"], "survival": survival,
        "open_drawings_sealed": list(pc.OPEN_ITEMS), "credits": CREDITS,
        "data_folder": "Pictures, raw answers and the human norms table live outside this repository.",
    }
    page = {**common, "game": game, "items": items}
    (REPO / "metalesionlab" / "web" / "data" / "plato_cave.json").write_text(
        json.dumps(to_jsonable(page), ensure_ascii=False, separators=(",", ":")))
    (REPO / "public_data" / "plato_cave.json").write_text(json.dumps(to_jsonable(common), ensure_ascii=False, indent=1))
    print("wrote web/data/plato_cave.json and public_data/plato_cave.json")


if __name__ == "__main__":
    main()
