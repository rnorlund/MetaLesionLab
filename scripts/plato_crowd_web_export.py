"""Ask it to be a crowd, step 3: the shipped data and sprites.

Usage: python -I scripts/plato_crowd_web_export.py

Reads $PLATO_CROWD_DIR/results.json and the persona pictures (outside the repository). Writes:
  metalesionlab/web/data/plato_crowd.json         statistics for /plato's "Ask it to be a crowd" section and
                                                   God's result, for /plato/ideas to show later
  metalesionlab/web/static/img/draw/chair_crowd_muse.webp, god_crowd_muse.webp
                                                   the 16 persona doodles as one sprite in the draw pad's format
                                                   (scripts/draw_export.py: cell 112 px, 8 columns, ink-cropped as
                                                   DINOv2 saw them); the default rows are the pad's <key>_muse.webp
No people's drawings are shipped. No network, no API calls.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from draw_export import IMG, SPRITES, sprite  # noqa: E402

from metalesionlab import plato  # noqa: E402
from metalesionlab import plato_crowd as pc  # noqa: E402

OUT = REPO / "metalesionlab" / "web" / "data" / "plato_crowd.json"
SPRITE_KEYS = ("chair", "god")


def r(x, d=4):
    return None if x is None else round(float(x), d)


def rl(xs, d=4):
    return [r(x, d) for x in xs]


def answer(res: dict) -> str:
    """The one-line answer, worded as the plan fixed it."""
    h2 = res["H2"]
    return {
        "default_not_limit": "The AI has a default, not a limit: told 16 different ages, it draws like 16 different people.",
        "some_variety": (f"A stated age adds some variety, but not people's: {h2['n_reach_people']} of "
                         f"{res['H1']['n_things']} things reach people's spread. The sameness mostly survives."),
        "no_change": "A stated age changes nothing, like “any kind of chair”.",
    }[res["verdict"]]


def main() -> None:
    res = json.loads((pc.CROWD_DIR / "results.json").read_text())
    sprites = {}
    for key in SPRITE_KEYS:
        files = [p for p in plato.load_dir(pc.folder(key)) if "_age" in p.stem]
        s = sprite(files, **SPRITES["muse"], out=IMG / f"{key}_crowd_muse.webp")
        s["ages"] = [pc.age_of(f.name) for f in files]
        s["default"] = f"/static/img/draw/{key}_muse.webp"  # the pad's sprite of the default doodles, same layout
        sprites[key] = s
        print(f"{key}: sprite {s['bytes'] // 1024} KB")
    h1, h2, h3 = res["H1"], res["H2"], res["H3"]
    things = [{
        "key": b["key"], "label": b["label"], "n_default": b["n_default"], "n_persona": b["n_persona"],
        "default": r(b["default_spread"]), "default_ci95": rl(b["default_spread_ci95"]),
        "persona": r(b["persona_spread"]), "persona_ci95": rl(b["persona_spread_ci95"]),
        "people": r(b["people_spread"]), "people_ci95": rl(b["people_spread_ci95"]),
        "persona_vs_default": r(b["ratio_vs_default"], 2), "persona_vs_default_ci95": rl(b["ratio_vs_default_ci95"], 2),
        "persona_vs_people": r(b["persona_vs_people"], 2), "persona_vs_people_ci95": rl(b["persona_vs_people_ci95"], 2),
        "reaches_people": b["reaches_people"], "age_rho": r(b["age_rho"], 2),
    } for b in res["things"]]
    god = res.get("god") or {}
    lab = god.get("labels_by_eye") or {}
    data = {
        "about": "Ask it to be a crowd: 16 Muse Image doodles per concept, each prompt prefixed with one stated age "
                 "(20 to 80), against the same prompt with no age and people's Quick, Draw! drawings. Written by "
                 "scripts/plato_crowd_web_export.py from PlatosChair/crowd/results.json.",
        "plan": "docs/plato_crowd_plan.md", "doc": "docs/plato_crowd.md",
        "ages": res["ages"], "prompt_example": res["prompt_example"], "model": res["model"],
        "verdict": res["verdict"], "answer": answer(res),
        "h1": {"mean_diff": r(h1["D"]), "ci95": rl(h1["ci95"]), "p": r(h1["p_signflip_one_sided"], 4),
               "passes": h1["passes"], "n_things": h1["n_things"], "n_up": h1["n_persona_above_default"],
               "median_ratio_vs_default": r(h1["median_ratio_vs_default"], 2),
               "mean_default": r(h1["mean_default_spread"]), "mean_persona": r(h1["mean_persona_spread"]),
               "mean_people": r(h1["mean_people_spread"])},
        "h2": {"n_reach": h2["n_reach_people"], "reach": h2["reach"], "n_clearly_below": h2["n_clearly_below_people"],
               "median_persona_vs_people": r(h2["median_persona_vs_people"], 2),
               "default_n_reach": h2["default_n_reach_people"],
               "median_default_vs_people": r(h2["median_default_vs_people"], 2)},
        "h3": {"mean_rho": r(h3["mean_rho"], 2), "ci95": rl(h3["ci95"], 2), "p": r(h3["p_perm_two_sided"], 4)},
        "things": things,
        "sprites": sprites,
        "god": {
            "label": "God", "n_default": god.get("n_default"), "n_persona": god.get("n_persona"),
            "default": r(god.get("default_spread")), "default_ci95": rl(god.get("default_spread_ci95") or []),
            "persona": r(god.get("persona_spread")), "persona_ci95": rl(god.get("persona_spread_ci95") or []),
            "persona_vs_default": r(god.get("ratio_vs_default"), 2),
            "persona_vs_default_ci95": rl(god.get("ratio_vs_default_ci95") or [], 2),
            "age_rho": r(god.get("age_rho"), 2),
            "default_by_eye": {"n": 16, "bearded_man": 16, "halo": 16, "source": "docs/plato_ideas.md"},
            "persona_by_eye": {k: lab.get(k) for k in ("n", "bearded_man", "halo", "bearded_man_with_halo")}
            | {"emblems": (lab.get("concentration") or {}).get("counts"),
               "by_age": {a: v.get("emblem") + (" with a halo" if v.get("halo") else "")
                          for a, v in (lab.get("by_age") or {}).items()}},
            "how": "Labelled by eye, blind to the stated age (a shuffled contact sheet), with the invisible Forms' "
                   "God options; Muse Glimmer was busy. AI only: there are no people's drawings of God here.",
            "sentence": god_sentence(lab),
        },
        "credits": ["AI drawings: Meta Muse Image 1.0", "Similarity: Meta DINOv2 (facebook/dinov2-base)",
                    plato.QUICKDRAW_CREDIT],
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {OUT.relative_to(REPO)} ({OUT.stat().st_size // 1024} KB): {data['answer']}")


def god_sentence(lab: dict) -> str | None:
    if not lab:
        return None
    n, both = lab["n"], lab["bearded_man_with_halo"]
    if both == n:
        return f"Given 16 different ages, Muse Image still drew God as a bearded man with a halo, {both} of {n} times."
    return (f"Given 16 different ages, Muse Image drew God as a bearded man with a halo {both} of {n} times "
            f"(16 of 16 with no age).")


if __name__ == "__main__":
    main()
