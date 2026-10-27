"""What can I cut? Run the layer-removal study on Muse Glimmer (see metalesionlab/compress.py).

Stages, each resumable and saved under OUT (default runs/compress/):
  scan    intact guards, block influence, and every layer skipped alone      -> scan.json
  greedy  greedy removal path, with held-out pictures checked at every step  -> greedy.json
  prune   real removal of the chosen cuts (fresh load each), checked against
          the skip version, then size, memory, speed, accuracy, perplexity   -> pruned.json
  reload  save the guarded cut with save_pretrained, load it back with stock
          transformers and check its answers                                 -> reload.json
  export  merge everything into the web app's file                          -> glimmer.json
          (then scripts/cut_web_export.py ships a compact copy with the app)

Usage: python scripts/what_can_i_cut.py STAGE [--sets runs/sets] [--out runs/compress]
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import shutil
import time
from pathlib import Path

import torch

from metalesionlab import compress as C
from metalesionlab import glimmer

REPO = Path(__file__).resolve().parents[1]
GUARD_SETS = C.GUARD_SETS
CHECK_ITEMS = [0, 7, 14, 21, 28, 35]  # pictures compared between the skip and the real-removal model


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def save(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")
    tmp.replace(path)


def load_json(path: Path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def naming_items(sets: Path, heldout: bool = False) -> list[C.NamingItem]:
    return [it for s in GUARD_SETS for it in C.load_naming_set(sets / s, heldout=heldout)]


def guards_for(model, processor, sets: Path, features: bool = True) -> tuple[C.Guards, C.NamingTest]:
    prep = C.NamingTest.prepare if features else C.NamingTest.prepare_pixels
    guard = prep("guard", model, processor, naming_items(sets))
    heldout = prep("heldout", model, processor, naming_items(sets, heldout=True))
    text = C.TextGuard.prepare(processor.tokenizer, C.load_guard_text())
    return C.Guards(guard, text, processor), heldout


# --- stages ------------------------------------------------------------------------------------

def stage_scan(args) -> None:
    path = args.out / "scan.json"
    state = load_json(path, {})
    model, processor = glimmer.load()
    guards, heldout = guards_for(model, processor, args.sets)
    if "intact" not in state:
        intact = guards.evaluate(model, [], keep_items=True)
        intact["heldout"] = heldout.run(model, processor)
        state.update(intact=intact, types=C.layer_types(model),
                     block_influence=guards.naming.block_influence(model),
                     block_influence_text=guards.text.block_influence(model), skips={})
        save(path, state)
        log(f"intact: acc {intact['acc']} ({intact['correct']}/{intact['n']}) ppl {intact['ppl']} "
            f"heldout {intact['heldout']['accuracy']}")
    done = {int(k): v for k, v in state["skips"].items()}

    def keep(i: int, res: dict) -> None:
        state["skips"][str(i)] = res
        save(path, state)

    state["layers"] = C.importance_scan(model, guards, state["intact"], log=log, done=done, on_result=keep)
    save(path, state)


def stage_greedy(args) -> None:
    scan = load_json(args.out / "scan.json")
    path = args.out / "greedy.json"
    state = load_json(path, {"steps": []})
    model, processor = glimmer.load()
    guards, heldout = guards_for(model, processor, args.sets)
    intact = scan["intact"]

    def keep(steps: list[dict]) -> None:
        with C.SkipLayers(model, steps[-1]["removed"]):
            h = heldout.run(model, processor, keep_items=False)
        steps[-1]["heldout_acc"] = h["accuracy"]
        steps[-1]["heldout_by_lang"] = h["by_lang"]
        state["steps"] = steps
        save(path, state)

    state.update(shortlist=args.shortlist, acc_floor=C.ACC_FLOOR, ppl_tolerance=C.PPL_TOLERANCE)
    C.greedy_path(model, guards, intact, shortlist=args.shortlist, max_removed=args.max_removed, log=log,
                  steps=state["steps"], on_step=keep)


TIMING_KEYS = C.TIMING_KEYS


def choose_cuts(steps: list[dict], deep_step: int = 10) -> dict[str, list[int]]:
    """Cuts to build for real, each the deepest unbroken run of greedy steps that passes:
    confirmed (both guards and the held-out pictures), guarded (both guards), perplexity_only and
    naming_only (one guard each); plus one deep cut that ignores the guards, to show the scale."""
    cuts = {"intact": []}
    for name, key in (("confirmed", "confirmed"), ("guarded", "within_guard"), ("perplexity_only", "ppl_ok"),
                      ("naming_only", "acc_ok")):
        s = C.last_within_guard(steps, key)
        if s and s["removed"] not in cuts.values():
            cuts[name] = s["removed"]
    if deep_step and len(steps) >= deep_step and steps[deep_step - 1]["removed"] not in cuts.values():
        cuts[f"deep_{deep_step}"] = steps[deep_step - 1]["removed"]
    return cuts


def measure_cut(name: str, removed: list[int], args, full: bool = True) -> dict:
    """Load a fresh model, delete the layers, and measure it. full=False measures only size, memory
    and speed (the extra timing rounds)."""
    t0 = time.time()
    model, processor = glimmer.load()
    load_s = time.time() - t0
    torch.cuda.synchronize()
    res = {"name": name, "removed": removed, "load_seconds": round(load_s, 1)}
    guards, heldout = guards_for(model, processor, args.sets, features=False)
    if not full:
        C.remove_layers(model, removed)
        gc.collect()
        torch.cuda.empty_cache()
        res.update(mem_gb=round(torch.cuda.memory_allocated() / 2**30, 3),
                   **C.peak_memory(model, processor, guards.naming), **C.time_naming(model, processor, guards.naming),
                   **C.throughput(model, processor, guards.naming), **C.time_generation(model, processor))
        log(f"{name} timing: " + ", ".join(f"{k} {res[k]}" for k in TIMING_KEYS))
        del model
        gc.collect()
        torch.cuda.empty_cache()
        return res
    if removed:
        with C.SkipLayers(model, removed):
            skip_logits = C.answer_logits(model, guards.naming, CHECK_ITEMS, vision=True)
            skip_said = [r["said"] for r in guards.naming.run(model, processor, vision=True)["items"]]
        info = C.remove_layers(model, removed)
        res["config_fields"] = info["fields"]
        rm_logits = C.answer_logits(model, guards.naming, CHECK_ITEMS, vision=True)
        res["check"] = {"items": len(CHECK_ITEMS),
                        "max_abs_logit_diff": round(float((skip_logits - rm_logits).abs().max()), 5),
                        "same_top1": bool((skip_logits.argmax(-1) == rm_logits.argmax(-1)).all())}
    gc.collect()
    torch.cuda.empty_cache()
    cfg = model.config.get_text_config()
    res.update(C.count_params(model), layers=cfg.num_hidden_layers,
               mem_gb=round(torch.cuda.memory_allocated() / 2**30, 3))
    nm = guards.naming.run(model, processor, vision=True)
    if removed:
        res["check"]["same_answers_all_pictures"] = [r["said"] for r in nm["items"]] == skip_said
    ho = heldout.run(model, processor, vision=True, keep_items=False)
    res.update({f"acc_{lg}": v["accuracy"] for lg, v in nm["by_lang"].items()}, acc=nm["accuracy"],
               correct=nm["correct"], n=nm["n"], heldout_acc=ho["accuracy"],
               heldout_by_lang=ho["by_lang"], items=nm["items"])
    res.update(guards.text.run(model))
    res.update(C.peak_memory(model, processor, guards.naming))
    res.update(C.time_naming(model, processor, guards.naming))
    res.update(C.throughput(model, processor, guards.naming))
    res.update(C.time_generation(model, processor))
    log(f"{name}: {res['layers']} layers, {res['params'] / 1e9:.2f}B params, {res['mem_gb']} GiB, "
        f"peak {res['peak_gb']} GiB, {res['ms_per_item']} ms/item, {res['items_per_s']} items/s, "
        f"{res['tok_per_s']} tok/s, acc {res['acc']}, heldout {res['heldout_acc']}, ppl {res['ppl']}"
        + (f", check {res['check']}" if removed else ""))
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return res


def stage_prune(args) -> None:
    """Measure every chosen cut once in full, then repeat the speed measurements in rotated order
    (args.rounds in all) so drift in GPU clocks does not favor one cut. Speed is the median over
    rounds; the range is kept."""
    path = args.out / "pruned.json"
    state = load_json(path, {"cuts": {}})
    scan, greedy = load_json(args.out / "scan.json"), load_json(args.out / "greedy.json")
    C.mark_heldout(greedy["steps"], scan["intact"]["heldout"]["correct"])
    save(args.out / "greedy.json", greedy)
    cuts = choose_cuts(greedy["steps"], args.deep_step)
    for name, removed in json.loads(args.extra or "{}").items():
        cuts[name] = sorted(removed)
    log(f"cuts: {cuts}")
    for name, removed in cuts.items():
        if name not in state["cuts"] or state["cuts"][name]["removed"] != removed:
            state["cuts"][name] = measure_cut(name, removed, args) | {"timing_rounds": []}
            save(path, state)
    names = list(cuts)
    for r in range(args.rounds):
        for name in names[r % len(names):] + names[:r % len(names)]:
            cut = state["cuts"][name]
            if len(cut["timing_rounds"]) > r:
                continue
            first_round = {k: cut[k] for k in TIMING_KEYS} if r == 0 else None
            cut["timing_rounds"].append(first_round or {k: v for k, v in measure_cut(
                name, cut["removed"], args, full=False).items() if k in TIMING_KEYS})
            for k in TIMING_KEYS:
                vals = [t[k] for t in cut["timing_rounds"]]
                cut[k] = C.median(vals)
                cut[f"{k}_range"] = [min(vals), max(vals)]
            save(path, state)


def stage_reload(args) -> None:
    """Prove the guarded cut is a standalone model: save it, reload it with stock from_pretrained,
    and compare its answers with the in-memory pruned model."""
    from transformers import AutoModelForMultimodalLM

    removed = load_json(args.out / "pruned.json")["cuts"]["guarded"]["removed"]
    ckpt = Path(args.ckpt)
    model, processor = glimmer.load()
    C.remove_layers(model, removed)
    test = C.NamingTest.prepare_pixels("guard", model, processor, naming_items(args.sets))
    want = C.answer_logits(model, test, CHECK_ITEMS, vision=True)
    if ckpt.exists():
        shutil.rmtree(ckpt)
    t0 = time.time()
    model.save_pretrained(ckpt)
    save_s = time.time() - t0
    del model
    gc.collect()
    torch.cuda.empty_cache()
    t0 = time.time()
    again = AutoModelForMultimodalLM.from_pretrained(ckpt, dtype=torch.bfloat16, device_map="cuda:0").eval()
    load_s = time.time() - t0
    got = C.answer_logits(again, test, CHECK_ITEMS, vision=True)
    nm = test.run(again, processor, vision=True, keep_items=False)
    size = sum(f.stat().st_size for f in ckpt.glob("*.safetensors"))
    res = {"removed": removed, "layers": again.config.get_text_config().num_hidden_layers,
           "checkpoint_gb": round(size / 2**30, 2), "save_seconds": round(save_s, 1),
           "load_seconds": round(load_s, 1), "mem_gb": round(torch.cuda.memory_allocated() / 2**30, 3),
           "max_abs_logit_diff": round(float((want - got).abs().max()), 5),
           "same_top1": bool((want.argmax(-1) == got.argmax(-1)).all()), "acc": nm["accuracy"],
           "by_lang": nm["by_lang"]}
    log(f"reload: {res}")
    save(args.out / "reload.json", res)
    if not args.keep_ckpt:
        shutil.rmtree(ckpt)


def stage_export(args) -> None:
    save(args.out / "glimmer.json", C.build_report(args.out))
    log(f"wrote {args.out / 'glimmer.json'}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=["scan", "greedy", "prune", "reload", "export"])
    p.add_argument("--sets", type=Path, default=REPO / "runs" / "sets")
    p.add_argument("--out", type=Path, default=REPO / "runs" / "compress")
    p.add_argument("--shortlist", type=int, default=3)
    p.add_argument("--max-removed", type=int, default=20)
    p.add_argument("--extra", help='more cuts to measure, as JSON: {"name": [layers]}')
    p.add_argument("--rounds", type=int, default=3, help="speed measurements per cut, in rotated order")
    p.add_argument("--deep-step", type=int, default=10, help="greedy step to build as the deep cut (0: none)")
    p.add_argument("--ckpt", default=os.path.expanduser("~/mll-compress-ckpt/glimmer-guarded"))
    p.add_argument("--keep-ckpt", action="store_true")
    args = p.parse_args()
    {"scan": stage_scan, "greedy": stage_greedy, "prune": stage_prune, "reload": stage_reload,
     "export": stage_export}[args.stage](args)


if __name__ == "__main__":
    main()
