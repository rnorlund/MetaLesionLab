"""The invisible Forms, step 5: the data and small pictures the site needs (the draw pad and /plato/ideas).

Reads $PLATO_IDEAS_DIR (outside the repository): results.json (scripts/plato_ideas_analyze.py stats), the DINOv2
embeddings, the Glimmer labels and the pictures; and, when they exist, words_results.json (the four words beyond
nouns, plato_ideas_analyze.py words) and damage/results.json with SDXL's damaged pictures (scripts/plato_ideas_damage.py,
docs/plato_ideas_damage_plan.md). Writes:

  metalesionlab/web/data/draw_ideas.json        the pad's ideas and words: per item Muse's leave-one-out distances, each
                                                doodle's emblem label, the emblem counts and the sprite layout (AI only:
                                                no people's numbers exist for these)
  metalesionlab/web/data/draw/<key>.json        server only: Muse's centroid and unit vectors (int8)
  metalesionlab/web/static/img/draw/<key>_muse.webp      the pad's thumbnail sprite, ink-cropped as DINOv2 saw it
  metalesionlab/web/static/img/plato_ideas/<key>.webp    the page's larger sprite, the whole doodle as Muse drew it
  metalesionlab/web/static/img/plato_ideas/dmg/*.webp    SDXL's God under damage (the slider's frames, one seed) and
                                                         each other idea's intact / words-part / drawing-part trio
  metalesionlab/web/data/plato_ideas.json       the findings page: statistics, tests, emblem counts, things' spreads,
                                                the words, and God under damage
  metalesionlab/web/data/series/ideas.json      the series card's finding
  public_data/plato_ideas.json                  statistics only, no pictures

and, outside the repository, $PLATO_IDEAS_DIR/social/: a 4 x 4 grid of Muse's 16 drawings of God, a few single
drawings, and SDXL God-damage frames picked by eye (DAMAGE_SOCIAL), candidates for posts. No network, no API calls.

    python scripts/plato_ideas_web_export.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from draw_export import loo_distances, sprite  # noqa: E402  the pad's own sprite and distance code

from metalesionlab import plato  # noqa: E402
from metalesionlab import plato_ideas as I  # noqa: E402
from metalesionlab import plato_ideas_damage as ID  # noqa: E402
from metalesionlab.draw import pack, pack_int8, unit  # noqa: E402

WEB = REPO / "metalesionlab" / "web"
PAD_OUT = WEB / "data" / "draw_ideas.json"
VEC_DIR = WEB / "data" / "draw"
PAD_IMG = WEB / "static" / "img" / "draw"
PAGE_IMG = WEB / "static" / "img" / "plato_ideas"
DMG_IMG = PAGE_IMG / "dmg"
PAGE_OUT = WEB / "data" / "plato_ideas.json"
SERIES_OUT = WEB / "data" / "series" / "ideas.json"
PUBLIC_OUT = REPO / "public_data" / "plato_ideas.json"
DAMAGE = I.IDEAS_DIR / "damage"
# The pad lists God first (the brief), then the ideas a visitor is most likely to try.
PAD_ORDER = ["god", "love", "time", "death", "justice", "beauty", "the_good", "the_soul", "freedom", "happiness", "truth"]
SOCIAL = ["c1_2", "c2_1", "c3_3"]  # God drawings picked by eye for posts: a radiant halo, rays, a ringed halo
# SDXL God-damage frames picked by eye for posts (condition, seed index). Only frames that read as a respectful
# change of the picture; no horned, creature-like or screaming frame (docs/plato_ideas_damage.md).
DAMAGE_SOCIAL = [("text-noise@0.5", 13),    # words part: the crowned face becomes a robed figure with a halo
                 ("text-zero@0.25", 13),    # words part, neurons off: a bearded robed figure on clouds, a staff in hand
                 ("text-noise@0.75", 13)]   # words part: an ordinary man with glasses and headphones
CREDITS = ["AI drawings: Meta Muse Image (muse-image-1.0), the same doodle prompt as the things",
           "Emblem labels: Meta Muse Glimmer 30B, run on our own GPU",
           "Embeddings: Meta DINOv2 (facebook/dinov2-base, Apache-2.0)"]
SDXL_CREDIT = "Stable Diffusion XL base 1.0 (Stability AI), CreativeML OpenRAIL++-M"
WORDS_GROUP = {"id": "words", "label": "Draw an action or a quality:",
               "note": "Not in Quick, Draw! either, so a drawing is compared with Muse Image's 16 only."}
WORDS_KICKER = "Draw an action or a quality"
LEVEL_LABEL = {"noise": "noise × {d:g}", "zero": "{p:g}% of neurons off"}
# How the God slider names Glimmer's two non-emblem answers (its free-text names are never shown for God).
NEUTRAL = {"something else": "none of the listed emblems", "can't tell": "no clear symbol or figure"}


def page_sprite(files: list[Path], cell: int, cols: int, out: Path) -> dict:
    """The whole doodle as Muse drew it (no ink crop), downscaled, on white: for the page, not for scoring."""
    rows = -(-len(files) // cols)
    sheet = Image.new("L", (cols * cell, rows * cell), 255)
    for i, f in enumerate(files):
        tile = Image.open(f).convert("L").resize((cell, cell), Image.LANCZOS)
        sheet.paste(tile, ((i % cols) * cell, (i // cols) * cell))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, "WEBP", quality=80, method=6)
    return {"src": f"/static/img/plato_ideas/{out.name}", "cell": cell, "cols": cols, "n": len(files),
            "bytes": out.stat().st_size}


def r4(a):
    return [round(float(v), 4) for v in a]


def counts_of(shorts: list[str]) -> list:
    counts: dict[str, int] = {}
    for sh in shorts:
        counts[sh] = counts.get(sh, 0) + 1
    return [[I.display(k) if k not in ("something else", "can't tell") else k, v]
            for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def common(key: str, idea: I.Idea, r: dict) -> tuple[dict, dict]:
    """The pad's entry and the page's shared fields for one idea or word: vectors, sprites, emblems."""
    z = np.load(I.IDEAS_DIR / "embeddings" / "ai_doodle" / f"{key}.npz")
    files = [str(f) for f in z["files"]]
    if files != r["files"]:
        raise SystemExit(f"{key}: embeddings and results list different pictures")
    ai = unit(z["cls"].astype(np.float64))
    g = r["glimmer"]
    shorts, names = g["labels"], g["names"]
    emblems = [I.display(sh, nm) for sh, nm in zip(shorts, names)]
    (VEC_DIR / f"{key}.json").write_text(json.dumps({
        "key": key, "model": plato.DINO_MODEL, "embedding": "CLS, unit length", "mode": "ai_only",
        "ai_centroid": pack(ai.mean(0)), "ai": pack_int8(ai)}, separators=(",", ":")) + "\n")
    pics = [I.folder(key) / f for f in files]
    pad_sprite = sprite(pics, cell=112, cols=8, out=PAD_IMG / f"{key}_muse.webp")
    big = page_sprite(pics, cell=320 if key == "god" else 224, cols=8, out=PAGE_IMG / f"{key}.webp")
    top = {"emblem": I.display(g["top"]), "short": g["top"], "n": g["top_n"], "share": g["share"],
           "share_ci95": g["share_ci95"]}
    pad = {"key": key, "label": idea.label, "phrase": idea.phrase, "idea_group": idea.group, "n_ai": len(files),
           "vectors": f"draw/{key}.json", "prompt": r["prompt"],
           "ai_loo": r4(loo_distances(ai)), "ai_to_ai": r4(1.0 - ai @ unit(ai.mean(0))),
           "emblems": emblems, "emblem_counts": counts_of(shorts), "top": top,
           "spread": r["spread"]["spread"], "sprites": {"muse": pad_sprite}}
    page = {"key": key, "label": idea.label, "phrase": idea.phrase, "group": idea.group, "n": r["n"],
            "prompt": r["prompt"], "predicted": I.display(idea.predicted), "predicted_short": idea.predicted,
            "top": top, "emblem_counts": counts_of(shorts), "emblems": emblems,
            "effective_emblems": g["effective_emblems"], "names": names,
            "spread": r["spread"]["spread"], "spread_ci95": r["spread"]["spread_ci95"], "pixel_spread": r["pixel_spread"],
            "sprite": big, "pad_sprite": pad_sprite}
    print(f"{key:16s} top {top['emblem']!r} {top['n']}/{r['n']}; spread {r['spread']['spread']:.3f}; "
          f"sprites {pad_sprite['bytes'] // 1024} + {big['bytes'] // 1024} KB")
    return pad, page


def words_block(pad: list, groups: list) -> dict | None:
    """Beyond nouns: the four words on the pad (their own row) and on the page."""
    path = I.IDEAS_DIR / "words_results.json"
    if not path.exists():
        return None
    res = json.loads(path.read_text())
    by_key = {r["key"]: r for r in res["words"]}
    if not all("glimmer" in by_key.get(w.key, {}) and "spread" in by_key[w.key] for w in I.WORDS):
        return None
    out = []
    for w in I.WORDS:
        r = by_key[w.key]
        p, page = common(w.key, w, r)
        pad.append({**p, "group": "words", "kicker": WORDS_KICKER})
        eye = r["by_eye"]
        out.append({**page, "kind": I.WORD_GROUPS[w.group],
                    "by_eye": {"top": I.display(eye["top"]), "short": eye["top"], "n": eye["top_n"], "share": eye["share"],
                               "counts": [[I.display(k), v] for k, v in eye["counts"].items()]},
                    "agreement": r["agreement"], "refused": r["refusals"]["refused"], "attempts": r["refusals"]["attempts"]})
    groups.append(WORDS_GROUP)
    eye_file = json.loads((I.IDEAS_DIR / "labels_by_eye_words.json").read_text())
    t, by = res["tests"], {w["key"]: w for w in out}
    nth = lambda k: f"{by[k]['top']['n']} of {by[k]['n']}"  # noqa: E731
    present = eye_file["present"]
    lede = ("Plato’s Forms were nouns. We also asked Muse Image for two actions and two qualities, 16 times each, with the "
            "prompt the chair got: running, thinking, something fast and something heavy. (Not “quick”: the prompt already "
            "says “a quick simple doodle”.) The verbs came out as one stock figure each: a stick figure running in "
            f"{nth('running')}, and a person pondering under a thought bubble. The adjectives left Muse to pick the thing, "
            f"and it picked few: a rocket in {nth('something_fast')} for fast, an anvil in {nth('something_heavy')} for heavy.")
    caption = (f"Predicted before the run: running → a runner, thinking → a person pondering, hand on chin, something fast → a "
               f"race car, something heavy → a weight. The emblem predictions failed: {t['W1']['predicted_on_top']} of 4 by Muse "
               f"Glimmer, {t['W1_by_eye']['predicted_on_top']} by eye, and 3 were needed. For thinking, Glimmer chose the "
               f"thought bubble ({nth('thinking')}) and our eye the pondering person "
               f"({by['thinking']['by_eye']['n']} of 16); by eye, a hand at the chin is in "
               f"{present['thinking']['hand on chin or cheek']} and a bubble in {present['thinking']['thought bubble (outlined cloud)']}. "
               f"The other predictions held: the verbs are as uniform as most ideas (spread {by['running']['spread']:.2f} and "
               f"{by['thinking']['spread']:.2f}), and the adjectives vary more than the verbs, more than the median idea "
               f"({t['W4']['ideas_median']:.2f}) and, as point estimates, more than any of the 135 everyday things "
               f"({by['something_fast']['spread']:.2f} and {by['something_heavy']['spread']:.2f}; their 95% CIs are wide). "
               "No call was refused and no drawing has words in it.")
    return {"plan": "docs/plato_ideas_damage_plan.md", "writeup": "docs/plato_ideas_damage.md", "words": out,
            "tests": t, "present": present, "lede": lede, "caption": caption}


def webp(src: Path, out: Path, side: int, quality: int = 72) -> str:
    out.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(src).convert("RGB")
    im.thumbnail((side, side), Image.LANCZOS)
    im.save(out, "WEBP", quality=quality, method=6)
    return f"/static/img/plato_ideas/dmg/{out.name}"


def trio(key: str, seed: int, run: Path) -> str:
    """One idea's intact picture, its strongest words-part damage and its strongest drawing-part damage, side by side."""
    cell = 176
    conds = ["intact", ID.cond("text-noise", ID.NOISE["text-noise"][-1]), ID.cond("unet-noise", ID.NOISE["unet-noise"][-1])]
    sheet = Image.new("RGB", (3 * cell, cell), "white")
    for k, c in enumerate(conds):
        im = Image.open(run / c / key / f"s{seed}.png").convert("RGB").resize((cell, cell), Image.LANCZOS)
        sheet.paste(im, (k * cell, 0))
    out = DMG_IMG / f"{key}_trio.webp"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, "WEBP", quality=66, method=6)
    return f"/static/img/plato_ideas/dmg/{out.name}"


def damage_block() -> dict | None:
    """God under damage (SDXL): the slider's frames for God's strip seed, the feature rates and the tests; and every
    other idea's and word's trio. These are Stable Diffusion XL's pictures, not Muse Image's."""
    path = DAMAGE / "results.json"
    if not path.exists() or not (DAMAGE / "picks.json").exists():
        return None
    res = json.loads(path.read_text())
    if not res.get("labelled"):
        return None
    picks = json.loads((DAMAGE / "picks.json").read_text())["picks"]
    run = DAMAGE / "run"
    labels = {}
    for f in (DAMAGE / "labels").glob("*.json"):
        d = json.loads(f.read_text())
        for it in d["items"]:
            labels[(d["condition"], it["key"], it["seed_index"])] = it
    cls = {f.stem: np.load(f) for f in (DAMAGE / "embeddings").glob("*.npz")}

    def change(cond, key, i):
        def vec(c):
            z = cls[c]
            j = list(z["files"]).index(f"{key}/s{i}.png")
            v = z["cls"][j].astype(np.float64)
            return v / np.linalg.norm(v)
        return round(float(1.0 - vec(cond) @ vec("intact")), 4)

    for old in DMG_IMG.glob("*.webp"):
        old.unlink()
    seed = picks["god"]
    god = I.BY_KEY["god"]
    levels, frames = {}, {}
    for method, (lang, draw) in ID.PAIRS.items():
        for fam in (lang, draw):
            doses = (ID.NOISE if method == "noise" else ID.ZERO)[fam]
            levels[fam] = [{"cond": "intact", "label": "intact"}] + [
                {"cond": ID.cond(fam, d), "label": LEVEL_LABEL[method].format(d=d, p=round(d * 100))} for d in doses]
            frames[fam] = []
            for lv in levels[fam]:
                c = lv["cond"]
                it = labels[(c, "god", seed)]
                name = f"god_{c.replace('@', '_')}.webp"
                img = webp(run / c / "god" / f"s{seed}.png", DMG_IMG / name, 320)
                # Only Glimmer's multiple choice and yes/no answers reach the page. Its free-text names often name a
                # particular religion's or mythology's figure, so for God they stay in the write-up's data only.
                frames[fam].append({"img": img, "change": 0.0 if c == "intact" else change(c, "god", seed),
                                    "emblem": NEUTRAL.get(it["emblem"]) or I.display(it["emblem"]),
                                    "person": it["p_person"] > 0.5, "beard": it["p_beard"] > 0.5, "halo": it["p_halo"] > 0.5})
    g = res["god"]["glimmer"]
    eye = res["god"].get("by_eye", {})
    keep = ("doses", "person", "beard", "halo", "generic", "fails_first", "emblem_before_figure", "generic_peak_rise")
    others = []
    for key in PAD_ORDER[1:] + ID.WORD_KEYS:
        pk = res["per_key"][key]
        others.append({"key": key, "label": I.ANY[key].label, "phrase": I.ANY[key].phrase,
                       "group": "words" if key in I.WORDS_BY_KEY else "ideas",
                       "trio": trio(key, picks[key], run), "seed": picks[key],
                       "intact_emblems": pk["intact_emblems"],
                       "same_emblem_lang_top": pk["text-noise"]["same_emblem"][-1],
                       "same_emblem_draw_top": pk["unet-noise"]["same_emblem"][-1],
                       "person_intact": pk["intact"]["person"], "person_lang_top": pk["text-noise"]["person"][-1],
                       "person_draw_top": pk["unet-noise"]["person"][-1]})
    nn = ID.n_seeds("god")
    gn, ge = g["text-noise"], eye.get("text-noise", {})
    count = lambda v: round(v * nn)  # noqa: E731
    agree = res.get("god_agreement", {})
    d4, d6 = res["D4"], res["D6"]
    by_key = {o["key"]: o for o in others}
    answer = (f"Intact, Stable Diffusion XL draws God as ornate, icon-like line art, mostly a bearded man (a beard in "
              f"{g['D1']['beard']} of {nn} drawings). Damage the part that handles words and the beard and halo go first, "
              f"while a human figure stays and turns into an ordinary person: at the most words damage, {count(gn['generic'][-1])} "
              f"of {nn} show a person with neither beard nor halo, against {count(gn['generic'][0])} intact"
              + (f" ({count(ge['generic'][-1])} against {count(ge['generic'][0])} by eye)" if ge else "")
              + ". Damage the part that draws and the same face dissolves into scribbles.")
    charts_note = (f"Muse Glimmer’s yes/no answers for all {nn} of Stable Diffusion XL’s drawings of God at each step "
                   f"(a feature counts when Glimmer says yes with p > 0.5). The steps are the draw pad’s doses. Our labels by "
                   f"eye, made before Glimmer’s, agree with them on the beard for {round(100 * agree['beard']['agreement'])}% of the "
                   f"320 pictures, the person for {round(100 * agree['person']['agreement'])}% and the halo for "
                   f"{round(100 * agree['halo']['agreement'])}%; the halo is the least certain, because SDXL’s ornament puts rings "
                   f"and arches near heads. Glimmer counts a face alone less often as “a person” than we did. Hover a step "
                   f"for its counts.") if agree else ""
    others_note = (f"Damage to the words part turns nearly every idea into people, as it turned the chair into cafés and "
                   f"cars. At the most words damage, Glimmer sees a person in {round(100 * by_key['death']['person_lang_top'])}% "
                   f"of death’s pictures and {round(100 * by_key['time']['person_lang_top'])}% of time’s (none intact); the most "
                   f"drawing damage dissolves the same pictures and adds no one. Across all 11 ideas and 4 words, at equal "
                   f"amounts of picture change, words damage lost the intact emblem {-100 * d4['difference']:.1f} points more "
                   f"often than drawing damage (95% CI {-100 * d4['ci95'][1]:.1f} to {-100 * d4['ci95'][0]:.1f}), and "
                   f"put a person into {100 * d6['difference']:.1f} points more of the pictures that had none (CI "
                   f"{100 * d6['ci95'][0]:.1f} to {100 * d6['ci95'][1]:.1f}).")
    return {
        "about": "God under damage: Stable Diffusion XL (an open model), not Muse Image (closed, can't be damaged), "
                 "drawing God and the other ideas with its words part or its drawing part damaged. "
                 "Plan: docs/plato_ideas_damage_plan.md; write-up: docs/plato_ideas_damage.md.",
        "model": "stabilityai/stable-diffusion-xl-base-1.0", "credit": SDXL_CREDIT,
        "prompt": I.prompt_for(god), "seed_index": seed, "n_seeds": ID.n_seeds("god"),
        "methods": {m: {"lang": a, "draw": b} for m, (a, b) in ID.PAIRS.items()},
        "levels": levels, "frames": frames,
        "rates": {fam: {k: g[fam][k] for k in keep if k in g[fam]} for fam in ("text-noise", "unet-noise", "text-zero", "unet-zero")},
        "rates_eye": {fam: {k: eye[fam][k] for k in keep if k in eye.get(fam, {})} for fam in ("text-noise", "unet-noise", "text-zero", "unet-zero")} if eye else None,
        "tests": {"D1": g["D1"], "D1_eye": eye.get("D1"), "D2": g["D2"], "D2_eye": eye.get("D2"), "D3": g["D3"],
                  "D3_eye": eye.get("D3"), "D4": res["D4"], "D5": res["D5"], "D6": res["D6"],
                  "god_bearded": res["god_bearded"], "agreement": res.get("god_agreement")},
        "severity": res["severity"],
        "intact": res["per_key"]["god"]["intact_emblems"],
        "others": others,
        "answer": answer, "charts_note": charts_note, "others_note": others_note,
    }


def main() -> None:
    res = json.loads((I.IDEAS_DIR / "results.json").read_text())
    by_key = {r["key"]: r for r in res["ideas"]}
    s = res["summary"]
    pad, page_ideas = [], []
    for key in PAD_ORDER:
        idea, r = I.BY_KEY[key], by_key[key]
        p, page = common(key, idea, r)
        pad.append(p)
        eye = r["by_eye"]
        page_ideas.append({
            **page,
            "by_eye": {"top": I.display(eye["top"]), "short": eye["top"], "n": eye["top_n"], "share": eye["share"],
                       "counts": [[I.display(k), v] for k, v in eye["counts"].items()]},
            "agreement": r["agreement"], "refused": r["refusals"]["refused"], "attempts": r["refusals"]["attempts"],
            **({"human_like": r["human_like"]} if "human_like" in r else {}),
        })
    groups = [{"id": "things", "label": "Or draw:"},
              {"id": "ideas", "label": "Draw the invisible:",
               "note": "No one has drawn these for Quick, Draw!, so a drawing is compared with Muse Image's 16 only."}]
    words = words_block(pad, groups)
    damage = damage_block()

    eye_file = json.loads((I.IDEAS_DIR / "labels_by_eye.json").read_text())
    things = sorted(res["things"], key=lambda t: t["spread"])
    page = {
        "about": "The invisible Forms: Muse Image's doodles of 11 abstract ideas. Written by scripts/plato_ideas_web_export.py.",
        "plan": "docs/plato_ideas_plan.md", "writeup": "docs/plato_ideas.md",
        "prompt_template": plato.STYLES["doodle"].format(phrase="{God}"),
        "summary": {k: s[k] for k in ("n_ideas", "pictures", "refused_attempts", "attempts", "H1", "H2", "H3_vs_atlas",
                                      "H3_vs_pad", "E1_concentration_vs_spread", "E4_pixels", "label_check",
                                      "text_in_pictures")},
        "present": eye_file["present"],
        "ideas": page_ideas,
        "things": [{"key": t["key"], "label": t["label"], "spread": t["spread"], "pad": t["pad"]} for t in things],
        "lausanne": {
            "cite": "Brandt, Dandarova-Robert, Dessart, Muthert & Schaap-Jonker (2023). Integrative Model of Children’s "
                    "Representations of God in Drawings. In When Children Draw Gods (Springer, open access), ch. 2.",
            "url": "https://doi.org/10.1007/978-3-030-94429-2_2", "project": "https://ddd.unil.ch",
            "anthropomorphic_share": 0.876, "n": 532, "ages": "5–17",
        },
        "credits": CREDITS,
        **({"words": words} if words else {}),
        **({"damage": damage} if damage else {}),
    }
    PAGE_OUT.write_text(json.dumps(plato.to_jsonable(page), ensure_ascii=False, separators=(",", ":")) + "\n")

    PAD_OUT.write_text(json.dumps(plato.to_jsonable({
        "about": "Draw the invisible: Muse Image's doodles of 11 abstract ideas, and of two actions and two qualities, "
                 "for placing a visitor's drawing among them. AI only: Quick, Draw! has no people's drawings of these. "
                 "Written by scripts/plato_ideas_web_export.py.",
        "model": plato.DINO_MODEL, "embedding": "CLS token", "distance": "cosine",
        "groups": groups, "credits": CREDITS, "concepts": pad}), ensure_ascii=False, separators=(",", ":")) + "\n")

    god = next(p for p in page_ideas if p["key"] == "god")
    SERIES_OUT.write_text(json.dumps({"finding": (
        f"Asked to draw God, Meta’s Muse Image drew the same bearded figure with a halo {god['top']['n']} times out of "
        f"{god['n']}. Love was a heart and death a hooded reaper every time; for "
        f"{s['H1']['ideas_with_concentration_at_least_half']} of {s['H1']['of']} ideas, one emblem filled at least half "
        f"the drawings.")}, ensure_ascii=False) + "\n")

    public = {
        "experiment": "The invisible Forms", "plan": "docs/plato_ideas_plan.md", "writeup": "docs/plato_ideas.md",
        "license": "statistics only: no drawings and no embeddings",
        "summary": page["summary"],
        "ideas": [{k: p[k] for k in ("key", "label", "group", "n", "prompt", "predicted", "top", "emblem_counts",
                                      "spread", "spread_ci95", "pixel_spread", "by_eye", "agreement", "refused",
                                      "attempts")} for p in page_ideas],
        "credits": CREDITS}
    if words:
        public["words"] = {"plan": words["plan"], "tests": words["tests"],
                           "words": [{k: p[k] for k in ("key", "label", "group", "n", "prompt", "predicted", "top",
                                                         "emblem_counts", "spread", "spread_ci95", "by_eye", "agreement",
                                                         "refused", "attempts")} for p in words["words"]]}
    if damage:
        public["damage"] = {"model": damage["model"], "credit": damage["credit"], "plan": "docs/plato_ideas_damage_plan.md",
                            "seed_index": damage["seed_index"], "rates": damage["rates"], "rates_eye": damage["rates_eye"],
                            "tests": damage["tests"], "severity": damage["severity"]}
    PUBLIC_OUT.write_text(json.dumps(plato.to_jsonable(public), ensure_ascii=False, indent=1) + "\n")

    social = I.IDEAS_DIR / "social"
    social.mkdir(exist_ok=True)
    gf = [I.folder("god") / f for f in by_key["god"]["files"]]
    grid = plato.grid([Image.open(f) for f in gf], cols=4, cell=512, gap=16)
    grid.save(social / "god_16_grid.png")
    for stem in SOCIAL:
        shutil.copy(I.folder("god") / f"{stem}.png", social / f"god_{stem}.png")
    for cond, i in DAMAGE_SOCIAL:
        shutil.copy(DAMAGE / "run" / cond / "god" / f"s{i}.png", social / f"sdxl_god_{cond.replace('@', '_')}_s{i}.png")
    if damage:  # God's two damage rows as one picture: words part on top, drawing part below (SDXL, one seed)
        i, rows = damage["seed_index"], []
        for fam in ("text-noise", "unet-noise"):
            conds = ["intact"] + [ID.cond(fam, d) for d in ID.NOISE[fam]]
            rows.append([Image.open(DAMAGE / "run" / c / "god" / f"s{i}.png").convert("RGB") for c in conds])
        cell, gap = 384, 12
        strip = Image.new("RGB", (6 * cell + 5 * gap, 2 * cell + gap), "white")
        for r, row in enumerate(rows):
            for c, im in enumerate(row):
                strip.paste(im.resize((cell, cell), Image.LANCZOS), (c * (cell + gap), r * (cell + gap)))
        strip.save(social / f"sdxl_god_strip_s{i}.png")
    total = sum(p.stat().st_size for p in [PAD_OUT, PAGE_OUT] + list(PAGE_IMG.glob("**/*.webp")))
    print(f"wrote {PAD_OUT.name}, {PAGE_OUT.name}, {SERIES_OUT.name}, {PUBLIC_OUT.name}; page data and pictures "
          f"{total / 1e6:.2f} MB; words {'yes' if words else 'no'}; damage {'yes' if damage else 'no'}; social candidates in {social}")


if __name__ == "__main__":
    main()
