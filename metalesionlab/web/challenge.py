"""You vs. the AI: a 10-picture naming game that sets a visitor's answers beside Muse Glimmer's.

Glimmer's answers and its word lens come from runs made ahead of time on a GPU
(TOT_DATA_DIR/lesion/<set>/intact.json plus one damaged condition), or from the shipped sample,
which the page labels as sample data. Typed answers are scored here with the naming_errors rules
and the meaning judge's disk cache only, so a typed game never calls a Meta API. Spoken answers go
through the Scorer's /api/score/naming route and its per-visitor limit.

app.py includes this router with one line.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from metalesionlab.naming_errors import JUDGE_PROMPT_VERSION, classify
from metalesionlab.web import app as web

router = APIRouter()

N_ITEMS = 10
LENS_LAYERS = 52
# Pictures in the order they're shown (an easy warm-up first), and the picture and damaged
# condition preferred for the "inside the AI" moment. Anything missing falls back to a search.
GAMES = {
    "en": {"set": "demo_en", "words": ["cat", "umbrella", "anchor", "ladder", "glove", "scissors", "pineapple",
                                       "snail", "cactus", "harp"],
           "inside": [("umbrella", "layers-40-47-noise-x2.181"), ("glove", "layers-40-43-zero")]},
    "es": {"set": "demo_es", "words": ["gato", "paraguas", "ancla", "escalera", "guante", "tijeras", "piña",
                                       "caracol", "silbato", "iglú"],
           "inside": [("piña", "layers-40-47-noise-x2.181"), ("paraguas", "layers-40-47-noise-x2.181")]},
}
HOW = {"zero": "switched off", "mean": "replaced with their average activity", "noise": "disturbed with random noise"}
SHORT_ERRORS = ("Nonword", "Formal", "Semantic", "Mixed", "Neologism", "Unrelated")


# --- loading -----------------------------------------------------------------------------

def _read(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _is_condition(d) -> bool:
    return isinstance(d, dict) and isinstance(d.get("items"), list) and "accuracy" in d


def _first_line(said: str, limit: int = 48) -> str:
    """A model answer as shown: the first non-empty line, cut to a readable length."""
    line = next((x.strip() for x in str(said or "").replace("​", "").splitlines() if x.strip()), "")
    return line if len(line) <= limit else line[:limit - 1].rstrip() + "…"


def _lens(item: dict) -> dict | None:
    lens = item.get("lens") or {}
    tops, p = lens.get("top"), lens.get("p_correct")
    if not (isinstance(tops, list) and isinstance(p, list) and len(tops) == len(p) == LENS_LAYERS):
        return None
    top1 = [str(t[0] if isinstance(t, list) and t else t) for t in tops]
    return {"top": [("\\n" if t == "\n" else t.strip() or "␣") for t in top1], "p": [round(float(x), 4) for x in p]}


def _real_runs(set_id: str) -> tuple[dict | None, Path | None]:
    """The intact run for a set, from TOT_DATA_DIR/lesion/<set>/ or a top-level file naming the set."""
    folder = web.LESION_DIR / set_id
    intact = _read(folder / "intact.json") if folder.is_dir() else None
    if _is_condition(intact):
        return intact, folder
    if web.LESION_DIR.is_dir():
        for path in sorted(web.LESION_DIR.glob("*.json")):
            for c in web._conditions_in(path):
                if c.get("set") == set_id and web.is_baseline(c) and "accuracy" in c:
                    return c, None
    return None, None


def _sample_runs() -> tuple[dict | None, list[dict]]:
    conds = web._conditions_in(web.SAMPLE_LAB)
    base = next((c for c in conds if web.is_baseline(c)), None)
    return base, [c for c in conds if not web.is_baseline(c)]


# --- the damaged condition ---------------------------------------------------------------

def _damage(cond: dict, sample: bool) -> dict:
    """A plain description of a lesion condition. The engine numbers decoder layers from 0;
    the page (and the word lens) count from 1, so real layer lists are shifted by one."""
    spec = cond.get("spec") if isinstance(cond.get("spec"), dict) else {}
    method = str(spec.get("method") or "").lower()
    how = HOW.get(method, "damaged")
    layers = sorted(int(x) for x in spec.get("layers") or [] if str(x).lstrip("-").isdigit())
    shown = layers if sample else [x + 1 for x in layers]
    units = cond.get("units") if isinstance(cond.get("units"), dict) else {}
    comps = list((spec.get("components") or {}).keys())
    if sample:
        plain = web.describe_spec(spec)
    elif shown:
        plain = (f"Layers {shown[0]}–{shown[-1]} of {LENS_LAYERS} {how}" if shown == list(range(shown[0], shown[-1] + 1))
                 else f"Layers {', '.join(map(str, shown))} {how}")
    elif comps:
        names = " and ".join(c.replace("_", " ") for c in comps)
        plain = f"The {names} {how}"
    else:
        parts = [f"{units['mlp']:,} neurons" if units.get("mlp") else None,
                 f"{units['heads']:,} attention heads" if units.get("heads") else None]
        plain = (" and ".join(p for p in parts if p) or "Some units") + f" {how}"
    acc = cond.get("accuracy")
    acc = float(acc) if acc is not None else None
    n = len(cond.get("items") or [])
    return {"id": str(cond.get("id") or cond.get("condition") or ""), "plain": plain, "method": method or None,
            "layers": shown, "noise_scale": spec.get("noise_scale") if method == "noise" else None,
            "accuracy": None if acc is None else round(acc * 100 if acc <= 1 else acc, 1),
            "correct": None if acc is None else round((acc if acc <= 1 else acc / 100) * n), "n": n}


def _pick_inside(lang: str, words: list[str], intact: dict, folder: Path | None, sample_damaged: list[dict]):
    """(word, damaged condition, sample?) for the inside moment: the configured choice if its files
    exist, else the mildest targeted condition that gets one of the game's pictures wrong."""
    by_word = {it.get("word"): it for it in intact.get("items", [])}
    def usable(cond, word):
        it = next((x for x in cond.get("items", []) if x.get("word") == word), None)
        return (it is not None and it.get("code") != "Correct" and by_word.get(word, {}).get("code") == "Correct"
                and _lens(it) and _lens(by_word[word]))
    if folder is not None:
        for word, cond_id in GAMES[lang]["inside"]:
            cond = _read(folder / f"{cond_id}.json")
            if word in words and _is_condition(cond) and usable(cond, word):
                return word, {**cond, "id": cond_id}
        best = None
        for path in sorted(folder.glob("*.json")):
            if path.stem == "intact" or "random" in path.stem:
                continue
            cond = _read(path)
            if not _is_condition(cond):
                continue
            for it in cond["items"]:
                w = it.get("word")
                if (w in words and it.get("code") in SHORT_ERRORS and len(_first_line(it.get("said"), 999)) <= 24
                        and usable(cond, w)):
                    key = (float(cond["accuracy"]), -SHORT_ERRORS.index(it["code"]))
                    if best is None or key > best[0]:
                        best = (key, w, {**cond, "id": path.stem})
        if best:
            return best[1], best[2]
        return None, None
    for cond in sorted(sample_damaged, key=lambda c: (not re.search("naming", str(c.get("label", "")), re.I),
                                                    -float(c.get("accuracy") or 0))):
        for word in words:
            if usable(cond, word):
                return word, cond
    return None, None


# --- the game ----------------------------------------------------------------------------

_cache: dict[tuple, dict] = {}


def _stamp(*paths: Path) -> tuple:
    out = []
    for p in paths:
        try:
            out.append(p.stat().st_mtime_ns)
        except OSError:
            out.append(None)
    return tuple(out)


def build_game(lang: str) -> dict:
    cfg = GAMES[lang]
    set_id = cfg["set"]
    manifest_path = web.SETS_DIR / set_id / "manifest.json"
    key = (lang, str(web.DATA_DIR), _stamp(manifest_path, web.LESION_DIR / set_id, web.LESION_DIR / set_id / "intact.json",
                                           web.SAMPLE_LAB))
    if key in _cache:
        return _cache[key]
    manifest = _read(manifest_path)
    if not isinstance(manifest, dict) or not manifest.get("items"):
        raise HTTPException(503, "The demo pictures for this game aren't on this server yet.")
    kept = [(i, it) for i, it in enumerate(manifest["items"]) if it.get("status") == "kept" and it.get("image")]

    intact, folder = _real_runs(set_id)
    sample = intact is None
    sample_damaged: list[dict] = []
    if sample:
        intact, sample_damaged = _sample_runs()
        if intact is not None and intact.get("set", "demo_en") != set_id:
            intact, sample_damaged = None, []
    ai = {it.get("word"): it for it in (intact or {}).get("items", [])}

    order = cfg["words"]
    chosen = [(i, it) for w in order for i, it in kept if it["word"] == w and w in ai]
    chosen += [(i, it) for i, it in kept if it["word"] in ai and (i, it) not in chosen]
    chosen += [(i, it) for i, it in kept if (i, it) not in chosen]
    chosen = chosen[:N_ITEMS]
    words = [it["word"] for _, it in chosen]

    items = []
    for i, it in chosen:
        a = ai.get(it["word"])
        items.append({"word": it["word"], "item": i, "alternates": it.get("alternates") or [],
                      "image": web_media(set_id, it["image"]),
                      "ai": {"said": _first_line(a.get("said")), "code": web.norm_code(a.get("code"))} if a else None})

    inside = None
    if intact is not None:
        word, cond = _pick_inside(lang, words, intact, folder, sample_damaged)
        if word:
            base = ai[word]
            dam = next(x for x in cond["items"] if x.get("word") == word)
            gloss = next((it.get("gloss") for _, it in chosen if it["word"] == word), None)
            inside = {"word": word, "gloss": gloss if lang != "en" and gloss and gloss != word else None,
                      "image": next(x["image"] for x in items if x["word"] == word),
                      "damage": _damage(cond, sample),
                      "intact": {"said": _first_line(base.get("said")), "code": web.norm_code(base.get("code")), **_lens(base)},
                      "damaged": {"said": _first_line(dam.get("said")), "code": web.norm_code(dam.get("code")), **_lens(dam)}}

    answered = [x for x in items if x["ai"]]
    run = intact or {}
    out = {
        "lang": lang, "set": set_id, "sample": sample, "model": "Muse Glimmer 30B",
        "note": (str(intact.get("note") or "") if sample and intact else
                 "Glimmer took this test ahead of time on one GPU; this page replays its answers."),
        "items": items, "inside": inside,
        "ai_summary": {"correct": sum(x["ai"]["code"] == "Correct" for x in answered), "n": len(answered),
                       "run_seconds": run.get("seconds"), "run_n": len(run.get("items") or [])} if intact else None,
    }
    if len(_cache) > 8:
        _cache.clear()
    _cache[key] = out
    return out


def web_media(set_id: str, file: str, width: int = 640) -> str:
    path = "/".join(quote(part) for part in str(file).split("/"))
    return f"/media/sets/{quote(set_id)}/{path}?w={width}"


def _bare(word: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", word) if unicodedata.category(c) != "Mn")


# --- routes ------------------------------------------------------------------------------

@router.get("/challenge", include_in_schema=False)
def challenge_page():
    return FileResponse(web.HERE / "pages" / "challenge.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/pages")
def pages():
    """Which optional pages this server has, so links to them can wait until they exist."""
    paths = {getattr(r, "path", None) for r in web.app.routes}
    return {"assess": "/assess" in paths, "challenge": True}


@router.get("/api/challenge")
def challenge(lang: Literal["en", "es"] = Query("en")):
    """Ten pictures, Glimmer's answers to them, and one word lens, intact and damaged."""
    return build_game(lang)


class Answer(BaseModel):
    word: str = Field(..., min_length=1, max_length=60)
    response: str = Field("", max_length=120)


class Answers(BaseModel):
    lang: Literal["en", "es"] = "en"
    answers: list[Answer] = Field(..., min_length=1, max_length=20)


_judge_cache: dict = {"stamp": None, "data": {}}


def cached_judgments() -> dict:
    path = web.CACHE_DIR / "semantic_judge.json"
    stamp = _stamp(path)
    if _judge_cache["stamp"] != (str(path), stamp):
        data = _read(path)
        _judge_cache.update(stamp=(str(path), stamp), data=data if isinstance(data, dict) else {})
    return _judge_cache["data"]


@router.post("/api/challenge/score")
def score(body: Answers):
    """Score typed answers for free: the classifier's rules, WordNet, and the meaning judge's cached
    answers. A pair the judge has never seen counts as not related in meaning ("meaning_checked": false);
    nothing is sent to a Meta API and nothing is stored."""
    cache = cached_judgments()
    manifest = _read(web.SETS_DIR / GAMES[body.lang]["set"] / "manifest.json") or {}
    alternates = {it.get("word"): tuple(it.get("alternates") or ()) for it in manifest.get("items", [])}

    def accepted(target: str) -> tuple[str, ...]:
        """The set's alternate names, plus accent-free spellings: many keyboards can't type ñ or ú."""
        names = (target, *alternates.get(target, ()))
        bare = tuple(dict.fromkeys(_bare(n) for n in names if _bare(n) != n))
        return alternates.get(target, ()) + bare
    results = []
    for a in body.answers:
        target = a.word.strip().lower()
        missed: list[str] = []

        def judge(t: str, r: str, lang: str) -> bool:
            k = f"v{JUDGE_PROMPT_VERSION}|{lang}|{t}|{r}"
            if k in cache:
                return bool(cache[k])
            missed.append(r)
            return False

        scored = web.collapse_repeat(a.response, body.lang, target)
        coding = classify(target, scored, body.lang, alternates=accepted(target), judge=judge)
        results.append({"word": target, "response": a.response, "scored_response": scored, "code": coding.code,
                        "correct": coding.code == "Correct", "head": coding.head, "meaning_checked": not missed})
    return {"results": results, "correct": sum(r["correct"] for r in results), "n": len(results)}
