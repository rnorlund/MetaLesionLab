"""Copy small derived numbers from results.json into public_data/plato_languages.json for the site.

Only group-level statistics are copied (no drawings, no embeddings, no Quick, Draw! records).
Usage: python scripts/plato_lang_public.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab.plato_lang import OUT, REPO_ROOT  # noqa: E402


def main():
    res = json.loads((OUT / "results.json").read_text())
    concepts = res["concepts"]
    uni = res["style_control_uniform_lines"]
    public = {
        "about": ("Plato's chair across languages and countries: how much quick doodles of everyday objects "
                  "change with the language of the prompt (Muse Image) or the country of the drawer "
                  "(people, Quick, Draw!). Group-level statistics only."),
        "attribution": {
            "human_drawings": "Quick, Draw! dataset by Google, CC BY 4.0, https://quickdraw.withgoogle.com/data "
                              "(statistics derived from 200 recognized drawings per country per concept)",
            "ai_drawings": "Muse Image 1.0 (Meta), 10 doodles per language per concept",
            "embeddings": "DINOv2 ViT-B/14 (facebook/dinov2-base, Meta, Apache-2.0)",
        },
        "date": res["date"],
        "concepts": concepts, "languages": res["languages"], "countries": res["countries"],
        "words": res["words"],
        "n": res["n"],
        "definitions": {
            "share": "share of all variation in the drawings explained by group (language or country), "
                     "[estimate, 95% CI low, high]; 0 means the group makes no difference",
            "spread": "average DINOv2 cosine distance between two drawings of the same group",
            "between": "chance-corrected distance between two groups' average drawings (x1000 in heatmap)",
        },
        "per_concept": {c: {
            "share_ai": res["ai"][c]["share"], "share_ai_p": res["ai"][c]["share_p"],
            "share_human": res["human"][c]["share"], "share_human_p": res["human"][c]["share_p"],
            "spread_ai": res["ai"][c]["spread_mean"], "spread_human": res["human"][c]["spread_mean"],
            "share_ai_style_removed": uni["share"][c]["ai"], "share_ai_style_removed_p": uni["share"][c]["ai_p"],
            "share_human_style_removed": uni["share"][c]["human"],
        } for c in concepts},
        "summary": {k: res["summary"][k] for k in (
            "mean_share_ai", "mean_share_human", "mean_share_diff", "concepts_ai_gt_human",
            "mean_between_ai", "mean_between_human",
            "rank_ai", "rank_human", "spearman_ai_human", "spearman_p", "mean_spread_ai", "mean_spread_human")},
        "summary_style_removed": {k: uni["summary"][k] for k in (
            "mean_share_ai", "mean_share_human", "mean_share_diff", "mean_between_ai", "mean_between_human",
            "rank_ai", "rank_human", "spearman_ai_human", "spearman_p")},
        "style_removed_note": "every drawing binarized, thinned and redrawn with one 3 px line before embedding",
        "heatmap": res["heatmap"],
        "heatmap_style_removed": uni["heatmap"],
        "alignment": {k: res["alignment"][k] for k in ("matched_mean_cos", "null_mean", "p")},
    }
    path = REPO_ROOT / "public_data" / "plato_languages.json"
    path.write_text(json.dumps(public, ensure_ascii=False, indent=1))
    print(f"wrote {path} ({path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
