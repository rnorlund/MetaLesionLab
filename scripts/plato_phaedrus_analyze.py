"""Seven meanings, step 3: the analysis (free). Reads the stimuli, transcripts and Spark's answers from
$PLATO_PHAEDRUS_DIR, runs the prosody reader on every clip and tests the pre-registered predictions
(docs/plato_phaedrus_plan.md).

Usage:
  python scripts/plato_phaedrus_analyze.py [--write]

--write also writes
  public_data/plato_phaedrus.json            the statistics, every transcript and every guess (no audio)
  public_data/plato_phaedrus_audio/<voice>/  the Kokoro clips the page plays (24 kHz MP3, Apache-2.0 voice)
  metalesionlab/web/data/plato_phaedrus.json what /plato/phaedrus shows
  metalesionlab/web/data/phaedrus_templates.json  the aligner's templates for visitors' recordings
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import wave
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from metalesionlab import plato_phaedrus as P  # noqa: E402
from plato_phaedrus_stimuli import ESPEAK_VOICES, FOCUS, KOKORO_TEMPLATES, KOKORO_TEST, SAY_VOICES  # noqa: E402

FAMILIES = {"kokoro": KOKORO_TEST, "say": SAY_VOICES, "espeak": ESPEAK_VOICES}
FAMILY_LABEL = {"kokoro": "Kokoro + WORLD focus", "say": "macOS say commands", "espeak": "eSpeak NG emphasis"}
CLIPS = [f"{i}_{w.lower()}" for i, w in enumerate(P.WORDS)]


def load(p: Path) -> np.ndarray:
    with wave.open(str(p)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64) / 32768


def jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def edges(word_times) -> list[float]:
    wt = word_times
    return [wt[0][0]] + [(wt[k][1] + wt[k + 1][0]) / 2 for k in range(P.N - 1)] + [wt[-1][1]]


def acc_block(correct, clusters=None) -> dict:
    correct = [bool(c) for c in correct]
    k, n = sum(correct), len(correct)
    out = {"k": k, "n": n, "acc": k / n if n else None, "ci": P.exact_ci(k, n) if n else None,
           "p_above_chance": P.binom_p_greater(k, n) if n else None,
           "p_two_sided": P.binom_p_two_sided(k, n) if n else None}
    if clusters is not None and len(set(clusters)) > 1:
        out["ci_voices"] = P.cluster_bootstrap(np.array(correct), clusters)
    return out


def confusion(truth, guess) -> list[list[int]]:
    m = [[0] * P.N for _ in range(P.N)]
    for t, g in zip(truth, guess):
        if g is not None:
            m[t][g] += 1
    return m


def templates(root: Path) -> list[P.Template]:
    out = []
    for v in KOKORO_TEST + KOKORO_TEMPLATES:
        folder = root / "stimuli" / "kokoro" / v
        meta = json.loads((folder / "meta.json").read_text())
        out.append(P.make_template(v, load(folder / "neutral.wav"), meta["clips"]["neutral"]["word_times"]))
    return out


def run_reader(root: Path, temps: list[P.Template]) -> list[dict]:
    rows = []
    for family, voices in FAMILIES.items():
        for v in voices:
            folder = root / "stimuli" / family / v
            meta = json.loads((folder / "meta.json").read_text())
            use = [t for t in temps if t.name != v]  # a Kokoro voice never meets its own template
            for k, name in enumerate(CLIPS):
                x = load(folder / f"{name}.wav")
                r = P.read_stress(x, use)
                row = {"family": family, "voice": v, "clip": name, "truth": k, "guess": r["guess"],
                       "raw_guess": r["raw"]["guess"],
                       "cue_guess": {c: int(np.argmax(r["prominence"][c])) for c in P.CUES},
                       "bounds": [round(b, 3) for b in r["bounds"]],
                       "prominence": [round(float(z), 3) for z in r["prominence"]["total"]],
                       "contour": P.contour(r)}
                if family == "kokoro":
                    true_b = edges(meta["clips"][name]["word_times"])
                    o = P.read_stress(x, use, bounds_s=true_b)
                    row["oracle_guess"] = o["guess"]
                    row["bound_err_ms"] = round(float(np.median(np.abs(np.array(r["bounds"]) - true_b))) * 1000, 1)
                rows.append(row)
    return rows


def analyse(root: Path) -> dict:
    trans = jsonl(root / "transcripts.jsonl")
    spark = jsonl(root / "spark.jsonl")
    temps = templates(root)

    # --- H1: the shadow
    voices = []
    for family, vs in FAMILIES.items():
        for v in vs:
            ts = {e["clip"]: e["transcript"] for e in trans if e["family"] == family and e["voice"] == v}
            stressed = [ts[c] for c in CLIPS if c in ts]
            allv = [ts.get("neutral", "")] + stressed
            lk = P.leaks(allv)
            voices.append({"family": family, "voice": v, "neutral": ts.get("neutral"),
                           "transcripts": {c: ts.get(c) for c in CLIPS}, **lk,
                           "identical_stressed": len(set(stressed)) == 1,
                           "same_words_stressed": len({" ".join(P.words_of(t)) for t in stressed}) == 1})
    canonical = " ".join(w.lower() for w in P.WORDS)
    all_t = [e for e in trans]
    exact_canonical = sum(e["transcript"] == P.SENTENCE for e in all_t)
    words_canonical = sum(" ".join(P.words_of(e["transcript"])) == canonical for e in all_t)
    n_same_words = sum(v["same_words"] for v in voices)
    # which way do the transcripts differ? repeated words, a lower-case i, punctuation
    def kinds(t: str) -> list[str]:
        out = []
        w = P.words_of(t)
        if " ".join(w) != canonical:
            out.append("words")
        if t[:1] == "i":
            out.append("lower-case i")
        tail = t[len(t.rstrip(".!?,")):] if t else ""
        if tail != ".":
            out.append(f"ends {tail!r}" if tail else "no full stop")
        return out
    by_kind = Counter(k for e in all_t for k in kinds(e["transcript"]))
    lower_by_stress = {c: sum(e["transcript"][:1] == "i" for e in all_t if e["clip"] == c) for c in ["neutral"] + CLIPS}
    words_by_stress = {c: sum(" ".join(P.words_of(e["transcript"])) != canonical for e in all_t if e["clip"] == c)
                       for c in ["neutral"] + CLIPS}
    h1 = {"voices_same_words": n_same_words, "voices": len(voices), "passes": n_same_words >= 12,
          "clips": len(all_t), "exact_canonical": exact_canonical, "same_words_as_sentence": words_canonical,
          "kinds": dict(by_kind), "lower_case_i_by_clip": lower_by_stress, "word_changes_by_clip": words_by_stress,
          "distinct_transcripts": Counter(e["transcript"] for e in all_t).most_common()}
    # exploratory: a lower-case "i" when "I" isn't stressed (neutral and "I"-stressed clips against the other six)
    from scipy.stats import fisher_exact
    a_low = lower_by_stress["neutral"] + lower_by_stress["0_i"]
    b_low = sum(v for c, v in lower_by_stress.items() if c not in ("neutral", "0_i"))
    n_a = sum(e["clip"] in ("neutral", "0_i") for e in all_t)
    n_b = len(all_t) - n_a
    h1["lower_case_i_test"] = {"neutral_or_I_stressed": [a_low, n_a], "other_word_stressed": [b_low, n_b],
                               "fisher_p_two_sided": float(fisher_exact([[a_low, n_a - a_low], [b_low, n_b - b_low]])[1])}
    # exploratory: every clip transcribed a second time (added after the main run)
    retest = jsonl(root / "transcripts_retest.jsonl")
    if retest:
        first = {(e["family"], e["voice"], e["clip"]): e["transcript"] for e in trans}
        pairs = [(first[(e["family"], e["voice"], e["clip"])], e["transcript"]) for e in retest
                 if (e["family"], e["voice"], e["clip"]) in first]

        def changed(t):
            return " ".join(P.words_of(t)) != canonical
        h1["retest"] = {"clips": len(pairs), "identical_to_first": sum(a == b for a, b in pairs),
                        "same_words_as_first": sum(P.words_of(a) == P.words_of(b) for a, b in pairs),
                        "word_changes": [sum(changed(a) for a, _ in pairs), sum(changed(b) for _, b in pairs),
                                         sum(changed(a) and changed(b) for a, b in pairs)],
                        "lower_case_i": [sum(a[:1] == "i" for a, _ in pairs), sum(b[:1] == "i" for _, b in pairs),
                                         sum(a[:1] == "i" and b[:1] == "i" for a, b in pairs)],
                        "lower_case_i_retest_by_clip": {c: sum(e["transcript"][:1] == "i" for e in retest if e["clip"] == c)
                                                        for c in ["neutral"] + CLIPS}}
        lr = h1["retest"]["lower_case_i_retest_by_clip"]
        ra, rb = lr["neutral"] + lr["0_i"], sum(v for c, v in lr.items() if c not in ("neutral", "0_i"))
        rn_a = sum(e["clip"] in ("neutral", "0_i") for e in retest)
        rn_b = len(retest) - rn_a
        h1["retest"]["lower_case_i_test"] = {
            "neutral_or_I_stressed": [ra, rn_a], "other_word_stressed": [rb, rn_b],
            "fisher_p_two_sided": float(fisher_exact([[ra, rn_a - ra], [rb, rn_b - rb]])[1])}
        h1["retest"]["changed_words_retest_by_clip"] = {
            c: sum(" ".join(P.words_of(e["transcript"])) != canonical for e in retest if e["clip"] == c)
            for c in ["neutral"] + CLIPS}

    # --- H2, H3: Spark
    def cond(c):
        return [e for e in spark if e["condition"] == c]
    tr = cond("transcript")
    h2 = acc_block([e["choice"] == e["truth"] for e in tr], [f"{e['family']}/{e['voice']}" for e in tr])
    h2["passes"] = h2["ci"][0] <= P.CHANCE <= h2["ci"][1] if h2["n"] else None
    h2["choices"] = {P.WORDS[k]: v for k, v in sorted(Counter(e["choice"] for e in tr if e["choice"] is not None).items())}
    h2["no_answer"] = sum(e["choice"] is None for e in tr)
    h2["confusion"] = confusion([e["truth"] for e in tr], [e["choice"] for e in tr])
    h2["by_family"] = {f: acc_block([e["choice"] == e["truth"] for e in tr if e["family"] == f]) for f in FAMILIES}
    # with the canonical words only (the transcripts that carry no stray word), and the rest
    clean = [e for e in tr if " ".join(P.words_of(e["text"])) == canonical]
    h2["canonical_words_only"] = acc_block([e["choice"] == e["truth"] for e in clean])
    dup = [e for e in tr if " ".join(P.words_of(e["text"])) != canonical]
    h2["changed_words"] = {**acc_block([e["choice"] == e["truth"] for e in dup]),
                           "choices": {P.WORDS[k]: v for k, v in Counter(e["choice"] for e in dup if e["choice"] is not None).items()}}
    h3 = {}
    for style in ("caps", "italics"):
        rows = cond(style)
        b = acc_block([e["choice"] == e["truth"] for e in rows])
        b["passes"] = bool(b["n"] and b["acc"] >= 0.8 and b["ci"][0] > P.CHANCE)
        b["confusion"] = confusion([e["truth"] for e in rows], [e["choice"] for e in rows])
        b["by_word"] = {P.WORDS[k]: sum(e["choice"] == k for e in rows if e["truth"] == k) for k in range(P.N)}
        h3[style] = b
    h3["passes"] = all(h3[s]["passes"] for s in ("caps", "italics"))
    spark_usd = sum(e.get("usd", 0) for e in spark)

    # --- H4: the living word
    rows = run_reader(root, temps)
    clusters = [f"{r['family']}/{r['voice']}" for r in rows]
    h4 = acc_block([r["guess"] == r["truth"] for r in rows], clusters)
    h4["by_family"] = {}
    for f in FAMILIES:
        sub = [r for r in rows if r["family"] == f]
        h4["by_family"][f] = acc_block([r["guess"] == r["truth"] for r in sub],
                                       [f"{r['family']}/{r['voice']}" for r in sub])
    fam = h4["by_family"]
    h4["passes"] = bool(h4["acc"] >= 0.6 and h4["p_above_chance"] < 0.001 and fam["kokoro"]["acc"] >= 0.7
                        and fam["say"]["acc"] >= 0.7 and fam["espeak"]["p_above_chance"] < 0.05)
    h4["confusion"] = confusion([r["truth"] for r in rows], [r["guess"] for r in rows])
    h4["by_word"] = {P.WORDS[k]: acc_block([r["guess"] == k for r in rows if r["truth"] == k]) for k in range(P.N)}
    kok = [r for r in rows if r["family"] == "kokoro"]
    h4["oracle_kokoro"] = acc_block([r["oracle_guess"] == r["truth"] for r in kok])
    h4["kokoro_boundary_error_ms"] = float(np.median([r["bound_err_ms"] for r in kok]))
    h4["no_baseline"] = acc_block([r["raw_guess"] == r["truth"] for r in rows])
    h4["single_cue"] = {c: acc_block([r["cue_guess"][c] == r["truth"] for r in rows]) for c in P.CUES}
    h4["single_cue_by_family"] = {c: {f: acc_block([r["cue_guess"][c] == r["truth"] for r in rows if r["family"] == f])
                                      for f in FAMILIES} for c in P.CUES}

    return {"h1": h1, "h2": h2, "h3": h3, "h4": h4, "voices": voices, "reader_rows": rows, "spark": spark,
            "templates": temps, "spark_usd": spark_usd}


def pct(x) -> str:
    return "–" if x is None else f"{100 * x:.0f}%"


def report(a: dict) -> None:
    h1, h2, h3, h4 = a["h1"], a["h2"], a["h3"], a["h4"]
    print(f"H1 shadow: {h1['voices_same_words']}/{h1['voices']} voices same words -> {'PASS' if h1['passes'] else 'FAIL'}")
    print(f"   {h1['exact_canonical']}/{h1['clips']} transcripts exactly the sentence; {h1['same_words_as_sentence']} its words")
    print(f"   kinds: {h1['kinds']}")
    print(f"   lower-case i by clip: {h1['lower_case_i_by_clip']}")
    print(f"   word changes by clip: {h1['word_changes_by_clip']}")
    print(f"   lower-case i test: {h1['lower_case_i_test']}")
    if "retest" in h1:
        print(f"   retest: {h1['retest']}")
    for v in a["voices"]:
        print(f"   {v['family']:<7}{v['voice']:<11} identical={v['identical']!s:<5} same_words={v['same_words']!s:<5} "
              f"distinct={v['n_distinct']} punct={v['punctuation']}")
    print(f"H2 text only: {h2['k']}/{h2['n']} = {pct(h2['acc'])} CI {pct(h2['ci'][0])}-{pct(h2['ci'][1])} "
          f"(voices {pct(h2['ci_voices'][0])}-{pct(h2['ci_voices'][1])}), p>chance {h2['p_above_chance']:.3g} -> "
          f"{'PASS' if h2['passes'] else 'FAIL'}; choices {h2['choices']}; no answer {h2['no_answer']}")
    print(f"   canonical-words transcripts: {h2['canonical_words_only']['k']}/{h2['canonical_words_only']['n']}; "
          f"changed: {h2['changed_words']['k']}/{h2['changed_words']['n']} {h2['changed_words']['choices']}")
    for s in ("caps", "italics"):
        b = h3[s]
        if not b["n"]:
            continue
        print(f"H3 {s}: {b['k']}/{b['n']} = {pct(b['acc'])} CI {pct(b['ci'][0])}-{pct(b['ci'][1])} by word {b['by_word']}")
    print(f"   -> {'PASS' if h3['passes'] else 'FAIL'}")
    print(f"H4 reader: {h4['k']}/{h4['n']} = {pct(h4['acc'])} CI {pct(h4['ci'][0])}-{pct(h4['ci'][1])} "
          f"(voices {pct(h4['ci_voices'][0])}-{pct(h4['ci_voices'][1])}), p {h4['p_above_chance']:.2g} -> "
          f"{'PASS' if h4['passes'] else 'FAIL'}")
    for f, b in h4["by_family"].items():
        print(f"   {f:<7} {b['k']}/{b['n']} = {pct(b['acc'])} CI {pct(b['ci'][0])}-{pct(b['ci'][1])} p {b['p_above_chance']:.2g}")
    print(f"   by word: " + ", ".join(f"{w} {b['k']}/{b['n']}" for w, b in h4["by_word"].items()))
    print(f"   oracle (Kokoro): {h4['oracle_kokoro']['k']}/{h4['oracle_kokoro']['n']}; boundary err "
          f"{h4['kokoro_boundary_error_ms']:.0f} ms; no baseline {h4['no_baseline']['k']}/{h4['no_baseline']['n']}")
    for c, b in h4["single_cue"].items():
        byf = h4["single_cue_by_family"][c]
        print(f"   {c} only: {b['k']}/{b['n']} ({', '.join(f'{f} {x['k']}/{x['n']}' for f, x in byf.items())})")
    print(f"   confusion (rows truth): {h4['confusion']}")
    print(f"Spark spend ${a['spark_usd']:.4f}")


def round_block(b):
    if isinstance(b, dict):
        return {k: round_block(v) for k, v in b.items()}
    if isinstance(b, list):
        return [round_block(v) for v in b]
    if isinstance(b, float):
        return float(f"{b:.3g}") if 0 < abs(b) < 1e-3 else round(b, 4)  # keep small p-values
    return b


def write(a: dict, root: Path) -> None:
    spend = jsonl(root / "spend.jsonl")
    usd = {"transcription": round(sum(e["usd"] for e in spend if e["kind"] == "asr"), 4),
           "spark": round(sum(e["usd"] for e in spend if e["kind"] == "chat"), 4)}
    stats = {k: round_block(a[k]) for k in ("h1", "h2", "h3", "h4")}
    for k in ("confusion",):
        pass
    public = {
        "about": "Seven meanings (/plato/phaedrus): \"I never said she stole my money.\" spoken with each word stressed in "
                 "13 synthetic voices, written down by Meta's Voice Transcribe, read by Muse Spark from the transcript and "
                 "from CAPITALS or italics, and read from the sound by a plain prosody reader. Pre-registered in "
                 "docs/plato_phaedrus_plan.md; results in docs/plato_phaedrus.md. Written by scripts/plato_phaedrus_analyze.py.",
        "license": "Our statistics, transcripts and model answers: Apache 2.0. The audio in plato_phaedrus_audio/ is "
                   "Kokoro-82M's voice (hexgrad, Apache-2.0) with stress added by the WORLD vocoder (pyworld, MIT). The macOS "
                   "and eSpeak NG clips are not included.",
        "sentence": P.SENTENCE, "words": list(P.WORDS),
        "meanings": [{"word": m.word, "gloss": m.gloss, "option": m.option} for m in P.MEANINGS],
        "prompt": P.PROMPT, "models": {"transcribe": "muse-voice-transcribe-1.0", "spark": "muse-spark-1.3",
                                       "spark_reasoning_effort": "minimal"},
        "families": {f: {"label": FAMILY_LABEL[f], "voices": v} for f, v in FAMILIES.items()},
        "focus": FOCUS, "chance": P.CHANCE, "cost_usd": usd, **stats,
        "transcripts": [{k: v for k, v in e.items() if k in ("family", "voice", "clip", "transcript")}
                        for e in jsonl(root / "transcripts.jsonl")],
        "spark_trials": [{k: e[k] for k in ("condition", "item", "text", "truth", "choice", "answer", "order")}
                         for e in a["spark"]],
        "reader": [{k: r[k] for k in ("family", "voice", "clip", "truth", "guess", "raw_guess", "cue_guess", "bounds",
                                      "prominence")} for r in a["reader_rows"]],
    }
    (ROOT / "public_data" / "plato_phaedrus.json").write_text(json.dumps(public, indent=1, ensure_ascii=False) + "\n")

    # the shipped clips
    audio_dir = ROOT / "public_data" / "plato_phaedrus_audio"
    for v in KOKORO_TEST:
        dst = audio_dir / v
        dst.mkdir(parents=True, exist_ok=True)
        for name in ["neutral"] + CLIPS:
            shutil.copyfile(root / "ship" / v / f"{name}.mp3", dst / f"{name}.mp3")

    # the page
    spark_by_item = {e["item"]: e for e in a["spark"] if e["condition"] == "transcript"}
    reader_by = {(r["family"], r["voice"], r["clip"]): r for r in a["reader_rows"]}
    tr_by = {(e["family"], e["voice"], e["clip"]): e["transcript"] for e in jsonl(root / "transcripts.jsonl")}
    page_voices = []
    labels = {"af_heart": "Heart (US)", "am_michael": "Michael (US)", "bf_emma": "Emma (UK)", "bm_george": "George (UK)"}
    for v in KOKORO_TEST:
        clips = []
        for k, name in enumerate(CLIPS):
            s = spark_by_item.get(f"kokoro/{v}/{name}", {})
            r = reader_by[("kokoro", v, name)]
            clips.append({"word": P.WORDS[k], "src": f"/api/plato/phaedrus/audio/{v}/{name}.mp3",
                          "transcript": tr_by.get(("kokoro", v, name)), "spark": s.get("choice"),
                          "reader": r["guess"], "contour": r["contour"]})
        page_voices.append({"key": v, "label": labels[v], "neutral": {
            "src": f"/api/plato/phaedrus/audio/{v}/neutral.mp3", "transcript": tr_by.get(("kokoro", v, "neutral"))},
            "clips": clips})
    h1, h2, h3, h4 = a["h1"], a["h2"], a["h3"], a["h4"]

    def tile(b):
        return {"k": b["k"], "n": b["n"], "acc": round(b["acc"], 4), "ci": [round(x, 4) for x in b["ci"]],
                "p": b["p_above_chance"]}
    page = {
        "sentence": P.SENTENCE, "words": list(P.WORDS), "chance": P.CHANCE,
        "meanings": [{"word": m.word, "gloss": m.gloss, "option": m.option} for m in P.MEANINGS],
        "voices": page_voices,
        "shadow": {"voices": h1["voices"], "voices_same_words": h1["voices_same_words"], "clips": h1["clips"],
                   "exact": h1["exact_canonical"], "same_words": h1["same_words_as_sentence"], "kinds": h1["kinds"],
                   "distinct": h1["distinct_transcripts"][:12], "passes": h1["passes"],
                   "word_changes_by_clip": h1["word_changes_by_clip"], "lower_case_i_by_clip": h1["lower_case_i_by_clip"],
                   "lower_case_i_test": h1["lower_case_i_test"], "retest": h1.get("retest")},
        "spark": {"transcript": {**tile(h2), "choices": h2["choices"], "confusion": h2["confusion"],
                                 "passes": h2["passes"]},
                  "caps": {**tile(h3["caps"]), "confusion": h3["caps"]["confusion"]},
                  "italics": {**tile(h3["italics"]), "confusion": h3["italics"]["confusion"]}},
        "reader": {**tile(h4), "confusion": h4["confusion"], "passes": h4["passes"],
                   "by_family": {f: {**tile(b), "label": FAMILY_LABEL[f]} for f, b in h4["by_family"].items()},
                   "single_cue": {c: tile(b) for c, b in h4["single_cue"].items()}},
        "families": {f: {"label": FAMILY_LABEL[f], "n_voices": len(v)} for f, v in FAMILIES.items()},
        "cost_usd": usd,
    }
    (ROOT / "metalesionlab" / "web" / "data" / "plato_phaedrus.json").write_text(json.dumps(page, ensure_ascii=False) + "\n")
    tpl = {"about": "Neutral Kokoro-82M readings of the sentence with their word boundaries: the templates the prosody "
                    "reader aligns a recording to (plato_phaedrus.align). MFCC frames, not audio.",
           "templates": [t.to_json() for t in a["templates"]]}
    for t in tpl["templates"]:
        t["feats"] = [[round(v, 2) for v in row] for row in t["feats"]]
    (ROOT / "metalesionlab" / "web" / "data" / "phaedrus_templates.json").write_text(json.dumps(tpl) + "\n")
    print("wrote public_data/plato_phaedrus.json, the audio, web/data/plato_phaedrus.json and the templates")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=P.PHAEDRUS_DIR)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    a = analyse(args.root)
    report(a)
    if args.write:
        write(a, args.root)


if __name__ == "__main__":
    main()
