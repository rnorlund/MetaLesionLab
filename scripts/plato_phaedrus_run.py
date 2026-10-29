"""Seven meanings, step 2: the paid calls. Voice Transcribe writes down every clip; Muse Spark guesses the meaning
from each transcript, and from the sentence with the stressed word in CAPITALS or *italics* (the control).

Usage:
  python scripts/plato_phaedrus_run.py transcribe          every clip in $PLATO_PHAEDRUS_DIR/stimuli (resumable)
  python scripts/plato_phaedrus_run.py spark               Spark on every stressed clip's transcript, and the control
  python scripts/plato_phaedrus_run.py pilot               2 clips and 2 Spark calls into pilot/ (not analysed)
  python scripts/plato_phaedrus_run.py retest              every clip transcribed again (added after the main run,
                                                           to see whether the transcripts' stray words recur)
  python scripts/plato_phaedrus_run.py transcribe --root $PLATO_PHAEDRUS_DIR/v2 --budget 1.5
  python scripts/plato_phaedrus_run.py spark --root $PLATO_PHAEDRUS_DIR/v2 --no-control --budget 1.5
                                                           v2, the Kokoro clips remade with stronger stress (a revision
                                                           after the run): only their transcripts and Spark's guesses;
                                                           the CAPITALS and italics control doesn't depend on the clips

Each clip gets 0.5 s of silence before and after (the synthetic voices start at once, and Voice Transcribe
sometimes returns nothing for clips without a lead-in) and the language hint English. Spark gets the fixed
prompt (plato_phaedrus.PROMPT) with the seven meanings in an order shuffled per trial from a fixed seed, at
reasoning effort "minimal"; its ledger entries carry the tag "phaedrus".

Spend: every call goes through MetaAPI, so the shared ledger books it (set MLL_LEDGER to the main repository's
runs/costs.jsonl when running from a worktree). The task's own spend is summed in spend.jsonl; no call is made
past plato_phaedrus.BUDGET_USD, or once the shared ledger reaches SHARED_STOP.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab import audio, meta_api  # noqa: E402
from metalesionlab import plato_phaedrus as P  # noqa: E402
from metalesionlab.meta_api import MetaAPI  # noqa: E402

PAD_S = 0.5
CONTROL_STYLES = ("caps", "italics")
CONTROL_REPEATS = 5


def jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


def append(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps({"ts": round(time.time(), 2), **entry}) + "\n")


class Budget:
    def __init__(self, root: Path, cap: float = P.BUDGET_USD):
        self.log = root / "spend.jsonl"
        self.cap = cap

    def mine(self) -> float:
        return sum(e["usd"] for e in jsonl(self.log))

    def check(self, estimate: float) -> None:
        shared = meta_api.spent()
        if shared >= P.SHARED_STOP:
            raise SystemExit(f"stopping: the shared ledger is at ${shared:.2f} (stop at ${P.SHARED_STOP:.2f})")
        if self.mine() + estimate > self.cap:
            raise SystemExit(f"stopping: this task has spent ${self.mine():.4f} of ${self.cap:.2f}")

    def book(self, kind: str, usd: float, **extra) -> None:
        append(self.log, {"kind": kind, "usd": round(usd, 6), **extra})


def tested_clips(root: Path) -> list[tuple[str, str, str, Path]]:
    """(family, voice, clip name, path) of every clip that is tested (Kokoro's template-only voices aren't)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from plato_phaedrus_stimuli import ESPEAK_VOICES, KOKORO_TEST, SAY_VOICES
    out = []
    for family, voices in (("kokoro", KOKORO_TEST), ("say", SAY_VOICES), ("espeak", ESPEAK_VOICES)):
        for v in voices:
            folder = root / "stimuli" / family / v
            for name in ["neutral"] + [f"{i}_{w.lower()}" for i, w in enumerate(P.WORDS)]:
                p = folder / f"{name}.wav"
                if p.exists():
                    out.append((family, v, name, p))
    return out


def transcribe_one(api: MetaAPI, budget: Budget, path: Path) -> dict:
    wav = audio.pad_silence(path.read_bytes(), PAD_S)
    est = audio.duration_s(wav) / 3600 * meta_api.ASR_PRICE_PER_HOUR
    budget.check(est)
    body = api.transcribe(wav, language="en")
    usd = (body.get("audioDurationMs") or 0) / 3.6e6 * meta_api.ASR_PRICE_PER_HOUR
    budget.book("asr", usd, clip=str(path))
    return {"transcript": body.get("transcript", ""), "audio_ms": body.get("audioDurationMs"),
            "keys": sorted(body.keys()), "turns": body.get("turns")}


def spark_one(api: MetaAPI, budget: Budget, text: str, order: list[int]) -> dict:
    budget.check(0.003)
    prompt = P.build_prompt(text, order)
    resp = api.chat([{"role": "user", "content": prompt}], reasoning_effort="minimal", ledger_tag="phaedrus",
                    timeout=90)  # one call hung for 10 minutes; the client retries a timeout
    usd = meta_api.token_cost(meta_api.CHAT_MODEL, resp.usage)
    budget.book("chat", usd)
    answer = (resp.choices[0].message.content or "").strip()
    return {"answer": answer, "choice": P.parse_choice(answer, order), "order": order, "usd": round(usd, 6),
            "model": meta_api.CHAT_MODEL}


def run_transcribe(root: Path, api: MetaAPI, budget: Budget, name: str = "transcripts.jsonl") -> None:
    out = root / name
    done = {(e["family"], e["voice"], e["clip"]) for e in jsonl(out)}
    for family, voice, name, path in tested_clips(root):
        if (family, voice, name) in done:
            continue
        r = transcribe_one(api, budget, path)
        append(out, {"family": family, "voice": voice, "clip": name, **r})
        print(f"{family:<7}{voice:<11}{name:<9} {r['transcript']!r}")


def run_spark(root: Path, api: MetaAPI, budget: Budget, control: bool = True) -> None:
    out = root / "spark.jsonl"
    done = {(e["condition"], e["item"]) for e in jsonl(out)}
    rng = random.Random(P.SEED)
    trials = []
    for e in jsonl(root / "transcripts.jsonl"):
        if e["clip"] == "neutral":
            continue
        k = int(e["clip"].split("_")[0])
        trials.append(("transcript", f"{e['family']}/{e['voice']}/{e['clip']}", e["transcript"], k,
                       {"family": e["family"], "voice": e["voice"]}))
    for style in CONTROL_STYLES if control else ():
        for k in range(P.N):
            for r in range(CONTROL_REPEATS):
                trials.append((style, f"{style}/{k}/{r}", P.stressed_text(k, style), k, {}))
    orders = {t[1]: P.option_order(rng) for t in trials}  # drawn for every trial in a fixed order, so resuming keeps them
    for condition, item, text, k, extra in trials:
        if (condition, item) in done:
            continue
        r = spark_one(api, budget, text, orders[item])
        append(out, {"condition": condition, "item": item, "text": text, "truth": k, **extra, **r})
        mark = "ok" if r["choice"] == k else "  "
        print(f"{mark} {condition:<10} {item:<28} -> {r['answer']!r} ({P.WORDS[r['choice']] if r['choice'] is not None else '?'})")


def run_pilot(root: Path, api: MetaAPI, budget: Budget) -> None:
    pilot = root / "pilot"
    pilot.mkdir(parents=True, exist_ok=True)
    picks = [c for c in tested_clips(root) if c[0] == "kokoro" and c[2] in ("3_she", "4_stole")][:2]
    rng = random.Random(1)
    for family, voice, name, path in picks:
        r = transcribe_one(api, budget, path)
        append(pilot / "transcripts.jsonl", {"family": family, "voice": voice, "clip": name, **r})
        print("transcript:", json.dumps(r))
        s = spark_one(api, budget, r["transcript"], P.option_order(rng))
        append(pilot / "spark.jsonl", {"item": f"{family}/{voice}/{name}", **s})
        print("spark:", json.dumps(s))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("step", choices=["transcribe", "spark", "pilot", "retest"])
    ap.add_argument("--root", type=Path, default=P.PHAEDRUS_DIR)
    ap.add_argument("--budget", type=float, default=P.BUDGET_USD, help="this run's own cap, summed in ROOT/spend.jsonl")
    ap.add_argument("--no-control", action="store_true", help="spark: the transcripts only, not the CAPITALS/italics control")
    args = ap.parse_args()
    print(f"ledger {meta_api.LEDGER}: ${meta_api.spent():.4f}")
    api, budget = MetaAPI(), Budget(args.root, args.budget)
    if args.step == "retest":  # added after the main run (a deviation): every clip transcribed a second time
        run_transcribe(args.root, api, budget, "transcripts_retest.jsonl")
    elif args.step == "spark":
        run_spark(args.root, api, budget, control=not args.no_control)
    else:
        {"transcribe": run_transcribe, "pilot": run_pilot}[args.step](args.root, api, budget)
    print(f"this task: ${budget.mine():.4f}; ledger: ${meta_api.spent():.4f}")


if __name__ == "__main__":
    main()
