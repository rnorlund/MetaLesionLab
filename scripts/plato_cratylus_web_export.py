"""Plato's Cratylus: the page's data (metalesionlab/web/data/plato_cratylus.json) and the public statistics
(public_data/plato_cratylus.json), from $CRATYLUS_DIR/results.json.

Derived statistics only: per-word roundness means and CIs, the pre-registered contrasts, the choice arm, and
people's PUBLISHED rates from Ćwiek et al. (2022) (the OSF data carry no licence, so nothing computed from them).
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab import plato_cratylus as pk  # noqa: E402
from metalesionlab.plato import QUICKDRAW_CREDIT, to_jsonable  # noqa: E402

D = Path(os.environ.get("CRATYLUS_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/cratylus"))
REPO = Path(__file__).resolve().parents[1]
MEASURES = ("solidity", "corners", "axis")
PEOPLE = {
    "source": ("Ćwiek, A., Fuchs, S., Draxler, C., et al. (2022). The bouba/kiki effect is robust across cultures "
               "and writing systems. Philosophical Transactions of the Royal Society B, 377(1841), 20200390 "
               "(CC BY 4.0). Published numbers only; the OSF data carry no licence."),
    "n_people": 917, "n_languages": 25,
    "both_trials_match": 0.72, "both_trials_match_cri95": [0.56, 0.82],
    "english_posterior": 0.84, "english_cri95": [0.71, 0.93], "english_raw": 0.88, "english_n": 41,
    "english_note": "read from Fig. 4 (approximate)",
    "bouba_round_first_trials": 0.82, "bouba_round_cri95": [0.68, 0.90],
    "kiki_spiky_first_trials": 0.68, "kiki_spiky_cri95": [0.53, 0.78],
    "per_word_note": "first trials only, read from Fig. 6 (approximate)",
    "range_by_language": [0.36, 1.0], "roman_script": 0.75, "other_scripts": 0.63,
    "task": "heard a spoken 'bouba' or 'kiki' and picked one of two shapes (a rounded blob, a spiky star)",
}


def r3(x):
    if isinstance(x, list):
        return [r3(v) for v in x]
    return None if x is None else round(float(x), 3)


def main():
    res = json.loads((D / "results.json").read_text())
    words = []
    for w in pk.WORDS:
        e = res["words"].get(w.word)
        if not e or not e["n"]:
            continue
        words.append({"word": w.word, "group": w.group, "consonants": w.consonants, "vowels": w.vowels,
                      "sound": w.sound, "of": w.of, "n": e["n"], "img": f"word_{pk.slug(w.word)}.webp",
                      "prompt": pk.prompt_for(w.word),
                      **{m: {"mean": r3(e[m]["mean"]), "ci95": r3(e[m]["ci95"])} for m in MEASURES},
                      "share_with_corners": r3(e["share_with_corners"])})
    c = res["contrasts"]
    contrasts = {
        name: {m: {k: r3(v) for k, v in c[name][m].items() if k in ("diff", "diff_ci", "d", "d_ci", "auc", "auc_ci")}
               if name != "spiky_vs_round_class" else
               {"diff": r3(c[name][m]["diff"]), "diff_ci": r3(c[name][m]["diff_ci"]),
                "pooled_auc": r3(c[name][m]["pooled"]["auc"]), "pooled_auc_ci": r3(c[name][m]["pooled"]["auc_ci"])}
               for m in MEASURES}
        for name in ("kiki_vs_bouba", "takete_vs_maluma", "spiky_vs_round_class")}
    for name in ("kiki_vs_bouba", "takete_vs_maluma"):
        for m in MEASURES:
            means = c[name][m].get("means")
            if means:
                contrasts[name][m]["means"] = {k: r3(v) for k, v in means.items()}
    grid = {m: {k: ({"diff": r3(v["diff"]), "diff_ci": r3(v["diff_ci"])} if k != "cells" else {kk: r3(vv) for kk, vv in v.items()})
                for k, v in res["grid"][m].items()} for m in MEASURES}
    ch = res["choice"]

    def per_word(block):
        return {w: {"p_round": r3(v.get("p_round")), **({"ci95": r3(v["ci95"])} if v.get("ci95") else {}),
                    **({"n": v["n"]} if "n" in v else {})} for w, v in block.items()}
    choice = {
        "prompt": pk.choice_prompt("<word>"), "text_prompt": pk.text_choice_prompt("<word>", True),
        "pairs": 8, "pair_imgs": ["pair_0.webp", "pair_3.webp"],
        "glimmer_picture": per_word(ch["glimmer_picture"]), "glimmer_text": per_word(ch["glimmer_text"]),
        "spark": per_word(ch.get("spark", {})),
        "glimmer_match": {k: r3(v) for k, v in ch["glimmer_match"].items()},
        "glimmer_text_match": {k: r3(v) for k, v in ch["glimmer_text_match"].items()},
        "spark_match": {k: r3(v) for k, v in ch.get("spark_match", {}).items()},
        "glimmer_both_match": {"p": r3(ch["glimmer_both_match"]["p"]), "ci95": r3(ch["glimmer_both_match"]["ci95"])},
        "spark_both_match": ch.get("spark_both_match"),
        "grid": {who: {k: ({"diff": r3(v["diff"]), "diff_ci": r3(v["diff_ci"])} if k != "cells" else {kk: r3(vv) for kk, vv in v.items()})
                       for k, v in ch[f"{who}_grid"].items()} for who in ("glimmer", "glimmer_text", "spark") if ch.get(f"{who}_grid")},
    }
    common = {
        "title": "Plato's Cratylus: bouba and kiki",
        "prompt": pk.PROMPT, "baseline_prompt": pk.BASELINE_PROMPT, "n_pictures": res["n_pictures"],
        "excluded_for_text": len(res["excluded"]), "words": words, "contrasts": contrasts, "grid": grid,
        "controls": {m: {k: r3(v) for k, v in res["controls"][m].items()} for m in MEASURES},
        "human_axis": {k: {"axis_mean": r3(v["axis_mean"]), "n": v["n"]} for k, v in res["human_axis"].items()},
        "choice": choice, "people": PEOPLE,
        "round_class": list(pk.ROUND_CLASS), "spiky_class": list(pk.SPIKY_CLASS),
        "credits": {"quickdraw": QUICKDRAW_CREDIT, "people": PEOPLE["source"],
                    "models": "Drawings: Meta Muse Image 1.0. Choices: Muse Glimmer 30B (open weights, self-hosted) "
                              "and Muse Spark 1.3. Picture similarity: Meta DINOv2."},
        "data_folder": "Pictures and raw results live outside this repository.",
    }
    page = {**common, "wall_img": "wall.webp"}
    (REPO / "metalesionlab" / "web" / "data" / "plato_cratylus.json").write_text(
        json.dumps(to_jsonable(page), ensure_ascii=False, separators=(",", ":")))
    (REPO / "public_data" / "plato_cratylus.json").write_text(json.dumps(to_jsonable(common), ensure_ascii=False, indent=1))
    print("wrote web/data/plato_cratylus.json and public_data/plato_cratylus.json")


if __name__ == "__main__":
    main()
