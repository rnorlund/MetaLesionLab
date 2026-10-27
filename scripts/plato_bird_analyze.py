"""Plato's Bird: analysis. Reads the norms, Spark's and Glimmer's answers and the picture labels from
$PLATO_BIRD_DIR (default PlatosChair/bird), writes results.json there, and with --public writes the
derived statistics to public_data/plato_bird.json.

  python scripts/plato_bird_analyze.py [--public] [--review]

--review prints every category's normalized answer lists (people, Spark, Glimmer) for checking the
synonym map by hand.

Human data: Banks & Connell (2023), CC BY 4.0 (see metalesionlab/plato_bird.py).
"""
import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from scipy.stats import spearmanr, wilcoxon  # noqa: E402

from metalesionlab.plato import to_jsonable  # noqa: E402
from metalesionlab.plato_bird import (BIRD_DIR, EXTRA_CATEGORIES, HUMAN_CREDIT, PICTURE_CATEGORIES, PROMPT, SYNONYMS,  # noqa: E402
                                      bootstrap_group_diff, bootstrap_mean_ci, category_aliases, counts_of,
                                      equal_n, exact_measures, from_probs, measures, normalize, safe_float,
                                      synonyms_for, tempered, top_answers)

REPO = Path(__file__).resolve().parents[1]
RAW = BIRD_DIR / "human_raw"
TEMPS = ["0.7", "1.0", "1.5"]
LOGIT_TEMPS = [0.5, 0.7, 1.0, 1.5, 2.0]
REPS = 1000


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_human():
    """Per category: the raw rank-1 responses, every raw response (any rank), the referential member rows,
    and the domain."""
    first, every, domain = defaultdict(list), defaultdict(list), {}
    said = defaultdict(list)  # (raw member, participant) for production frequency after our merging
    for r in read_csv(RAW / "trial_level.csv"):
        every[r["category"]].append(r["category.member"])
        said[r["category"]].append((r["category.member"], r["participant"]))
        domain[r["category"]] = r["domain"]
        if r["rank"] == "1":
            first[r["category"]].append(r["category.member"])
    members = defaultdict(list)
    for r in read_csv(RAW / "ref_item.csv"):
        members[r["category"]].append({
            "member": r["category.member"], "prod_freq": int(r["prod.freq"]),
            "first_freq": int(r["first.rank.freq"]) if r["first.rank.freq"] not in ("NA", "") else 0,
            "typicality": safe_float(r["typicality"])})
    return first, every, members, domain, said


def human_members(said: list, members: list[dict], key) -> tuple[dict, int]:
    """People's members after our normalization: how many different people named each (at any rank, from the
    trial data, so a person who said both 'petrol' and 'gasoline' counts once), and the members' typicality
    ratings (from the authors' item file, averaged over merged forms). Returns (members, number of people)."""
    agg: dict[str, dict] = {}
    for raw, who in said:
        k = key(raw)
        if k:
            agg.setdefault(k, {"who": set(), "typ": []})["who"].add(who)
    for m in members:
        k = key(m["member"])
        if k and m["typicality"] == m["typicality"]:
            agg.setdefault(k, {"who": set(), "typ": []})["typ"].append(m["typicality"])
    out = {k: {"prod": len(v["who"]), "typ": v["typ"]} for k, v in agg.items() if v["who"]}
    return out, len({w for _, w in said})


def load_ai(folder: Path) -> dict:
    out = {}
    for f in sorted(folder.glob("*.json")):
        rec = json.loads(f.read_text())
        out[rec["category"]] = rec
    return out


def logit_probs(rec: dict, key, temperature: float = 1.0) -> dict[str, float]:
    """Glimmer's answer distribution from the expanded first tokens: each first token's probability (tempered
    at the token level) goes to its greedy continuation's normalized answer. Renormalized over the covered
    mass; unusable continuations are dropped."""
    toks = {i: e["p"] for i, e in enumerate(rec["expansion"]) if e["p"] > 0}
    if temperature != 1.0:
        toks = tempered(toks, temperature)
    probs: dict[str, float] = defaultdict(float)
    for i, p in toks.items():
        k = key(rec["expansion"][i]["answer"])
        if k:
            probs[k] += p
    total = sum(probs.values())
    return {k: v / total for k, v in probs.items()} if total else {}


def share_table(counts: Counter, top: int = 10) -> list:
    n = sum(counts.values())
    rows = [[a, c, c / n] for a, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    if len(rows) > top:
        rest = sum(r[1] for r in rows[top:])
        rows = rows[:top] + [["(other)", rest, rest / n]]
    return [[a, int(c), round(s, 4)] for a, c, s in rows]


def prob_table(probs: dict, top: int = 10) -> list:
    rows = sorted(probs.items(), key=lambda kv: -kv[1])
    out = [[a, round(p, 4)] for a, p in rows[:top]]
    if len(rows) > top:
        out.append(["(other)", round(sum(p for _, p in rows[top:]), 4)])
    return out


def wilcoxon_p(d) -> float:
    d = np.asarray([x for x in d if x == x and x != 0], float)
    return float(wilcoxon(d).pvalue) if len(d) >= 5 else float("nan")


def compare(rows: list[dict], ai: str, measure: str, human: str = "human") -> dict:
    """AI minus human per category: mean with a bootstrap CI, count above, Wilcoxon p, by domain."""
    d = [r[ai][measure] - r[human][measure] for r in rows]
    dom = [r["domain"] for r in rows]
    out = {"ai_mean": bootstrap_mean_ci([r[ai][measure] for r in rows]),
           "human_mean": bootstrap_mean_ci([r[human][measure] for r in rows]),
           "diff": bootstrap_mean_ci(d), "n_ai_higher": int(sum(x > 1e-12 for x in d)),
           "n_ai_lower": int(sum(x < -1e-12 for x in d)), "n": len(d), "wilcoxon_p": wilcoxon_p(d), "by_domain": {}}
    for g in ("Concrete", "Abstract"):
        dg = [x for x, gg in zip(d, dom) if gg == g]
        out["by_domain"][g] = {"diff": bootstrap_mean_ci(dg), "ai_mean": float(np.mean(
            [r[ai][measure] for r in rows if r["domain"] == g])), "human_mean": float(np.mean(
            [r[human][measure] for r in rows if r["domain"] == g])), "n_ai_higher": int(sum(x > 1e-12 for x in dg)),
            "n": len(dg)}
    out["abstract_minus_concrete"] = bootstrap_group_diff(d, dom, "Abstract", "Concrete")
    return out


def spearman_rows(agg: dict, ai_prob: dict) -> dict:
    """Within one category, over the members people produced (human_members): AI probability vs. production
    frequency and vs. typicality."""
    keys = list(agg)
    x = np.array([ai_prob.get(k, 0.0) for k in keys])
    out = {}
    prod = np.array([agg[k]["prod"] for k in keys], float)
    if len(keys) >= 5 and x.std() > 0 and prod.std() > 0:
        out["prod_freq"] = float(spearmanr(x, prod).statistic)
    typ_keys = [i for i, k in enumerate(keys) if agg[k]["typ"]]
    if len(typ_keys) >= 5:
        xt = x[typ_keys]
        yt = np.array([np.mean(agg[keys[i]]["typ"]) for i in typ_keys])
        if xt.std() > 0 and yt.std() > 0:
            out["typicality"] = float(spearmanr(xt, yt).statistic)
    return out


def median_ci(x, reps: int = 10000, rng=None) -> dict:
    rng = rng or np.random.default_rng(0)
    x = np.asarray([v for v in x if v == v], float)
    b = np.median(x[rng.integers(0, len(x), (reps, len(x)))], axis=1)
    return {"median": float(np.median(x)), "ci95": [float(np.quantile(b, 0.025)), float(np.quantile(b, 0.975))],
            "n": int(len(x)), "n_positive": int((x > 0).sum())}


def analyze(review: bool = False) -> dict:
    first, every, members, domain, said = load_human()
    spark = load_ai(BIRD_DIR / "spark_text")
    glimmer = load_ai(BIRD_DIR / "glimmer_text")
    spark_t = {p.name.removeprefix("spark_text_T"): load_ai(p) for p in sorted(BIRD_DIR.glob("spark_text_T*"))}
    cats = sorted(set(first) | set(EXTRA_CATEGORIES))
    domain.update(EXTRA_CATEGORIES)
    rng = np.random.default_rng(20261027)
    rows, ai_only, alias_log, unusable = [], [], {}, Counter()
    # judge_glimmer.json, plus judge_glimmer_*.json for pairs added later (after a normalization change)
    judge = {(r["category"], r["answer"]): r["p_yes"] for p in sorted(BIRD_DIR.glob("judge_glimmer*.json"))
             for r in json.loads(p.read_text())["items"]}
    pairs: set[tuple[str, str]] = set()

    for cat in cats:
        syn = synonyms_for(cat)
        sp_raw = [s["answer"] for s in spark.get(cat, {}).get("samples", [])]
        gl = glimmer.get(cat)
        gl_raw = {t: gl["samples"].get(t, []) for t in TEMPS} if gl else {}
        # pool every source's normalized answers, then merge spacing and head-noun variants the same way
        pooled = Counter()
        for raw in [*every.get(cat, []), *sp_raw, *(a for t in TEMPS for a in gl_raw.get(t, [])),
                    *(e["answer"] for e in (gl or {}).get("expansion", [])), *(m["member"] for m in members.get(cat, []))]:
            k = normalize(raw, syn)
            if k:
                pooled[k] += 1
        # name merged groups by the norms' own referential member names where there is one
        preferred = {normalize(m["member"], syn) for m in members.get(cat, [])}
        aliases = category_aliases(cat, pooled, preferred)
        if aliases:
            alias_log[cat] = aliases

        def key(raw, syn=syn, aliases=aliases):
            k = normalize(raw, syn)
            return aliases.get(k, k)

        h = [key(a) for a in first.get(cat, [])]
        s = [key(a) for a in sp_raw]
        unusable["spark"] += sum(1 for a in s if not a)
        g = {t: [key(a) for a in gl_raw.get(t, [])] for t in TEMPS}
        unusable["glimmer_T1.0"] += sum(1 for a in g.get("1.0", []) if not a)
        probs = logit_probs(gl, key) if gl else {}
        n_h = len([a for a in h if a]) or 20
        row = {"category": cat, "domain": domain[cat], "n_human": n_h if cat in first else 0}
        for a in [*h, *s, *(x for t in TEMPS for x in g.get(t, [])), *probs]:
            if a:
                pairs.add((cat, a))
        if judge:
            # exploratory: keep only answers Glimmer judges to be members (P(yes) >= 0.5), every source alike
            ok = lambda xs, cat=cat: [x for x in xs if x and judge.get((cat, x), 0) >= 0.5]  # noqa: E731
            hv, sv, gv = ok(h), ok(s), ok(g.get("1.0", []))
            nv = len(hv) or n_h
            row["valid"] = {
                "share": {"human": len(hv) / max(1, len([x for x in h if x])), "spark": len(sv) / max(1, len([x for x in s if x])),
                          "glimmer_T1.0": len(gv) / max(1, len([x for x in g.get("1.0", []) if x]))},
                "human": measures(hv), "spark": equal_n(sv, nv, REPS, rng), "glimmer_T1.0": equal_n(gv, nv, REPS, rng)}
        if cat in first:
            row["human"] = measures(h)
            # the authors' referential first-rank counts (robustness)
            ref = Counter()
            for m in members[cat]:
                if m["first_freq"]:
                    ref[key(m["member"])] += m["first_freq"]
            row["human_ref"] = measures(list(ref.elements()))
        row["spark_full"] = measures(s)
        row["spark"] = {**equal_n(s, n_h, REPS, rng), "match_probability": row["spark_full"]["match_probability"],
                        "top": row["spark_full"]["top"]}
        for t in TEMPS:
            if g.get(t):
                full = measures(g[t])
                row[f"glimmer_T{t}_full"] = full
                row[f"glimmer_T{t}"] = {**equal_n(g[t], n_h, REPS, rng), "match_probability": full["match_probability"],
                                        "top": full["top"]}
        if probs:
            ex = exact_measures(probs)
            row["glimmer_logits"] = {**from_probs(probs, n_h, REPS, rng), "match_probability": ex["match_probability"],
                                     "top": [ex["top"]], "top_p": ex["dominance"], "entropy_exact": ex["entropy_bits"],
                                     "covered_mass": gl["covered_mass"], "greedy": key(gl["greedy"])}
            row["glimmer_logits_T"] = {str(T): exact_measures(logit_probs(gl, key, T)) for T in LOGIT_TEMPS}
        for T, recs in spark_t.items():
            if cat in recs:
                st = [key(x["answer"]) for x in recs[cat]["samples"]]
                row[f"spark_T{T}"] = {**measures(st), "eq": equal_n(st, min(n_h, len(st)), REPS, rng)}
                # the same number of default-temperature answers, for a like-for-like comparison
                row[f"spark_T{T}"]["default_same_n"] = equal_n(s, len(st), REPS, rng)
        # tables for figures and the web page
        row["tables"] = {"spark": share_table(counts_of(s)), "glimmer_T1.0": share_table(counts_of(g.get("1.0", []))),
                         "glimmer_logits": prob_table(probs, top=15)}
        if cat in first:
            row["tables"]["human_first"] = share_table(counts_of(h), top=20)
            agg, n_people = human_members(said[cat], members[cat], key)
            row["n_people"] = n_people
            human_keys = set(agg)
            row["tables"]["human_named"] = [[k, v["prod"], round(float(np.mean(v["typ"])), 2) if v["typ"] else None]
                                            for k, v in sorted(agg.items(), key=lambda kv: (-kv[1]["prod"], kv[0]))[:25]]
            # prototype agreement
            h_top = set(row["human"]["top"])
            for src in ("spark", "glimmer_logits", "glimmer_T1.0"):
                if src not in row:
                    continue
                top = row[src]["top"][0] if row[src]["top"] else None
                row[src]["top_matches_human"] = bool(set(row[src]["top"]) & h_top)
                row[src]["top_human_prod"] = agg.get(top, {}).get("prod", 0) if top else None
                row[src]["top_human_prod_pct"] = agg.get(top, {}).get("prod", 0) / n_people * 100 if top else None
                typ = agg.get(top, {}).get("typ")
                row[src]["top_typicality"] = float(np.mean(typ)) if typ else None
            row["human"]["top_typicality"] = float(np.nanmean([np.mean(agg[k]["typ"]) if agg.get(k, {}).get("typ")
                                                               else np.nan for k in h_top])) if any(
                agg.get(k, {}).get("typ") for k in h_top) else None
            row["coverage"] = {"spark": float(np.mean([a in human_keys for a in s if a])) if any(s) else None,
                               "glimmer_T1.0": float(np.mean([a in human_keys for a in g.get("1.0", []) if a]))
                               if g.get("1.0") else None}
            row["spearman"] = {"glimmer_logits": spearman_rows(agg, probs),
                               "spark": spearman_rows(agg, {k: c / max(1, len(s)) for k, c in counts_of(s).items()})}
            rows.append(row)
        else:
            ai_only.append(row)
        if review:
            print(f"\n== {cat} ({domain[cat]})")
            if cat in first:
                print("  people :", dict(counts_of(h).most_common(12)))
            print("  spark  :", dict(counts_of(s).most_common(12)))
            print("  glim T1:", dict(counts_of(g.get("1.0", [])).most_common(12)))
            print("  logits :", {k: round(v, 3) for k, v in sorted(probs.items(), key=lambda kv: -kv[1])[:8]})
            if aliases:
                print("  aliases:", aliases)

    # ---------- summary across categories ----------
    sources = ["spark", "glimmer_T1.0", "glimmer_logits", "glimmer_T0.7", "glimmer_T1.5"]
    summary = {}
    for src in sources:
        have = [r for r in rows if src in r]
        if not have:
            continue
        summary[src] = {m: compare(have, src, m) for m in ("dominance", "entropy_bits", "distinct", "match_probability")}
        summary[src]["top_matches_human"] = {
            "n": int(sum(r[src].get("top_matches_human", False) for r in have)), "of": len(have),
            "by_domain": {g: [int(sum(r[src].get("top_matches_human", False) for r in have if r["domain"] == g)),
                              sum(1 for r in have if r["domain"] == g)] for g in ("Concrete", "Abstract")}}
        typ_pairs = [(r[src].get("top_typicality"), r["human"].get("top_typicality")) for r in have]
        typ_pairs = [(a, b) for a, b in typ_pairs if a is not None and b is not None]
        summary[src]["top_typicality"] = {"ai": bootstrap_mean_ci([a for a, _ in typ_pairs]),
                                          "human": bootstrap_mean_ci([b for _, b in typ_pairs]),
                                          "diff": bootstrap_mean_ci([a - b for a, b in typ_pairs])}
        summary[src]["top_human_prod_pct"] = bootstrap_mean_ci([r[src]["top_human_prod_pct"] for r in have
                                                                if r[src].get("top_human_prod_pct") is not None])
    summary["human_ref_vs_trial"] = {m: compare([r for r in rows], "human_ref", m) for m in ("dominance", "entropy_bits")}
    summary["spark_vs_human_ref"] = {m: compare(rows, "spark", m, human="human_ref") for m in ("dominance", "entropy_bits")}
    summary["spearman"] = {src: {y: median_ci([r["spearman"][src].get(y, np.nan) for r in rows])
                                 for y in ("prod_freq", "typicality")} for src in ("glimmer_logits", "spark")}
    summary["coverage"] = {src: bootstrap_mean_ci([r["coverage"][src] for r in rows if r["coverage"][src] is not None])
                           for src in ("spark", "glimmer_T1.0")}
    summary["spark_vs_glimmer_top_agree"] = int(sum(bool(set(r["spark"]["top"]) & set(r.get("glimmer_logits", {}).get("top", [])))
                                                    for r in rows))
    # how often each source's top answer takes the whole sample
    summary["unanimous"] = {src: int(sum(r[src + "_full" if src != "glimmer_logits" else src]["dominance"] >= 0.999
                                          for r in rows if src in r)) for src in ("spark", "glimmer_T1.0")}
    summary["unanimous"]["human"] = int(sum(r["human"]["dominance"] >= 0.999 for r in rows))
    # temperature: Glimmer's logit distribution re-weighted
    summary["logit_temperature"] = {str(T): {
        "dominance": bootstrap_mean_ci([r["glimmer_logits_T"][str(T)]["dominance"] for r in rows if "glimmer_logits_T" in r]),
        "entropy_bits": bootstrap_mean_ci([r["glimmer_logits_T"][str(T)]["entropy_bits"] for r in rows if "glimmer_logits_T" in r])}
        for T in LOGIT_TEMPS}
    summary["unusable"] = dict(unusable)
    if judge:
        vrows = [{"domain": r["domain"], **{k: r["valid"][k] for k in ("human", "spark", "glimmer_T1.0")}}
                 for r in rows if "valid" in r and r["valid"]["human"]["n"]]
        summary["valid_only"] = {
            "share_valid": {src: bootstrap_mean_ci([r["valid"]["share"][src] for r in rows if "valid" in r])
                            for src in ("human", "spark", "glimmer_T1.0")},
            **{src: {m: compare(vrows, src, m) for m in ("dominance", "entropy_bits")} for src in ("spark", "glimmer_T1.0")}}
    (BIRD_DIR / "judge_pairs.json").write_text(json.dumps([{"category": c, "answer": a} for c, a in sorted(pairs)]))
    # Spark at another temperature (exploratory subset)
    for T in spark_t:
        have = [r for r in rows + ai_only if f"spark_T{T}" in r]
        if have:
            summary[f"spark_T{T}"] = {
                "n_categories": len(have),
                "dominance": bootstrap_mean_ci([r[f"spark_T{T}"]["dominance"] for r in have]),
                "dominance_default_same_n": bootstrap_mean_ci([r[f"spark_T{T}"]["default_same_n"]["dominance"] for r in have]),
                "entropy_bits": bootstrap_mean_ci([r[f"spark_T{T}"]["entropy_bits"] for r in have]),
                "entropy_default_same_n": bootstrap_mean_ci([r[f"spark_T{T}"]["default_same_n"]["entropy_bits"] for r in have]),
                "diff_dominance": bootstrap_mean_ci([r[f"spark_T{T}"]["dominance"] - r[f"spark_T{T}"]["default_same_n"]["dominance"]
                                                     for r in have])}

    pictures = analyze_pictures({r["category"]: r for r in rows + ai_only})
    return {"prompt": PROMPT, "n_categories": len(rows), "credit": HUMAN_CREDIT, "summary": summary,
            "categories": rows, "ai_only": ai_only, "pictures": pictures, "aliases": alias_log}


def analyze_pictures(by_cat: dict) -> dict:
    out = {}
    labels = {}
    for name in ("glimmer", "spark"):
        p = BIRD_DIR / f"picture_labels_{name}.json"
        if p.exists():
            labels[name] = json.loads(p.read_text())["labels"]
    if not labels:
        return out
    for key, (phrase, norm_cat) in PICTURE_CATEGORIES.items():
        syn = synonyms_for(norm_cat)
        row = by_cat.get(norm_cat, {})
        # merge the labels with the same spacing/head-noun rule as the naming answers of that category
        pooled = Counter()
        for name in labels:
            for it in labels[name].get(key, {}).get("items", []):
                pooled[normalize(it["answer"], syn)] += 1
        for tbl in ("spark", "human_first", "glimmer_T1.0"):
            for a, c, *_ in row.get("tables", {}).get(tbl, []):
                if a != "(other)":
                    pooled[a] += c
        # labels take the naming answers' names, so a drawn member and a named member compare directly
        named_keys = {a for tbl in ("spark", "human_first", "glimmer_T1.0", "human_named")
                      for a, *_ in row.get("tables", {}).get(tbl, []) if a != "(other)"}
        aliases = category_aliases(norm_cat, pooled, named_keys)
        noun = phrase.split(" ", 1)[1]
        generic = {noun, normalize(noun), norm_cat, "puppy", "kitten", "piece of furniture", "furniture", "dog",
                   "bird", "fish", "flower", "fruit", "vegetable", "vehicle", "tool", "game", "sport",
                   "musical instrument", "instrument"}
        named_pool = {a for tbl in ("spark", "human_first", "glimmer_T1.0", "human_named")
                      for a, *_ in row.get("tables", {}).get(tbl, []) if a != "(other)"}

        def label_key(text, syn=syn, aliases=aliases, generic=generic, named_pool=named_pool):
            """A picture label as a member: generic labels ('a fish', 'puppy') and unusable ones become
            'generic'; a modified label collapses to its head noun when that head is itself an answer people or
            the models gave for the category ('acoustic guitar' -> 'guitar', 'claw hammer' -> 'hammer')."""
            k = normalize(text, syn)
            k = aliases.get(k, k)
            if not k or k in generic or k.startswith(("generic ", "simple ", "stylized ", "cartoon ")):
                return "generic"
            if k not in named_pool and " " in k:
                last = normalize(k.split()[-1], syn)
                if aliases.get(last, last) in named_pool:
                    return aliases.get(last, last)
            return k

        rec = {"phrase": phrase, "norms_category": norm_cat}
        for name in labels:
            items = labels[name].get(key, {}).get("items", [])
            ks = [label_key(it["answer"]) for it in items]
            specific = [k for k in ks if k != "generic"]
            m = measures(specific) if specific else {"top": [], "dominance": float("nan"), "distinct": 0}
            rec[name] = {"labels": [[it["file"], k] for it, k in zip(items, ks)], "top": m["top"],
                         "top_count": max(Counter(specific).values()) if specific else 0, "n_specific": len(specific),
                         "dominance": m["dominance"], "distinct": m["distinct"], "table": share_table(counts_of(ks))}
        named = {"spark": row.get("spark", {}).get("top", []), "glimmer": row.get("glimmer_logits", {}).get("top", []),
                 "human": row.get("human", {}).get("top", [])}
        rec["named_top"] = named
        for name in labels:
            drawn = set(rec[name]["top"])
            rec[name]["matches"] = {who: bool(drawn & {aliases.get(t, t) for t in tops}) for who, tops in named.items()}
            spark_top = named["spark"][0] if named["spark"] else None
            rec[name]["share_showing_spark_top"] = (sum(1 for _, k in rec[name]["labels"] if k == aliases.get(spark_top, spark_top))
                                                   / max(1, len(rec[name]["labels"])))
        out[key] = rec
    return out


def no_nan(obj):
    """Strict JSON for browsers: NaN and infinities become null."""
    if isinstance(obj, dict):
        return {k: no_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [no_nan(v) for v in obj]
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    return obj


def public_view(res: dict) -> dict:
    """Derived statistics only: per-category summaries and short answer tables. No participant rows."""
    def slim(row):
        keep = {k: row[k] for k in ("category", "domain", "n_human", "n_people") if k in row}
        for src in ("human", "spark", "glimmer_logits", "glimmer_T1.0"):
            if src in row:
                keep[src] = {k: v for k, v in row[src].items() if k in (
                    "dominance", "entropy_bits", "distinct", "match_probability", "top", "top_matches_human",
                    "top_human_prod", "top_human_prod_pct", "top_typicality", "top_p", "covered_mass", "n")}
        if "human_ref" in row:
            keep["human_ref"] = {k: row["human_ref"][k] for k in ("dominance", "top")}
        for k in ("coverage", "spearman"):
            if k in row:
                keep[k] = row[k]
        # answer tables: [answer, count] (the share is count / total); human_named is [member, how many of
        # the 20 named it at all, mean typicality]; glimmer_logits is [answer, probability]
        keep["tables"] = {name: ([r[:2] for r in tbl] if name in ("spark", "glimmer_T1.0", "human_first") else tbl)
                          for name, tbl in row.get("tables", {}).items()}
        return keep

    pics = {k: {kk: vv for kk, vv in v.items()} for k, v in res["pictures"].items()}
    return {
        "title": "Plato's Bird: name one member of a category, AI vs. people",
        "credit": res["credit"],
        "human_data": {"citation": "Banks, B., & Connell, L. (2023). Category production norms for 117 concrete and "
                                   "abstract categories. Behavior Research Methods, 55(3), 1292-1313.",
                       "doi": "10.3758/s13428-021-01787-z", "data_url": "https://osf.io/jgcu6/", "license": "CC BY 4.0",
                       "note": "Tables hold aggregate counts of people's first answers (20 UK adults per category) "
                               "and production frequencies and typicality ratings of the most-named members, "
                               "normalized by our own rules; no participant-level rows."},
        "ai": {"spark": "muse-spark-1.3, 50 separate calls per category, default sampling, reasoning effort minimal",
               "glimmer": "Muse Glimmer 30B (FP8, self-hosted): logit distribution of the first answer token, each top "
                          "token continued greedily; and 50 samples at temperatures 0.7, 1.0 and 1.5",
               "image": "muse-image-1.0, 12 doodles per category (3 calls of n=4)"},
        "prompt": res["prompt"], "n_categories": res["n_categories"], "summary": res["summary"],
        "synonyms": SYNONYMS,
        "categories": [slim(r) for r in res["categories"]], "ai_only": [slim(r) for r in res["ai_only"]],
        "pictures": pics,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--public", action="store_true")
    ap.add_argument("--review", action="store_true")
    args = ap.parse_args()
    res = analyze(review=args.review)
    (BIRD_DIR / "results.json").write_text(json.dumps(to_jsonable(res), indent=1))
    s = res["summary"]
    for src in ("spark", "glimmer_logits", "glimmer_T1.0"):
        if src not in s:
            continue
        d, e = s[src]["dominance"], s[src]["entropy_bits"]
        print(f"{src:15s} dominance AI {d['ai_mean']['mean']:.3f} vs people {d['human_mean']['mean']:.3f}; "
              f"diff {d['diff']['mean']:+.3f} {np.round(d['diff']['ci95'], 3)}; AI higher in {d['n_ai_higher']}/{d['n']}"
              f" | entropy AI {e['ai_mean']['mean']:.2f} vs {e['human_mean']['mean']:.2f}; diff {e['diff']['mean']:+.2f} "
              f"{np.round(e['diff']['ci95'], 2)}; abstract-concrete gap diff {d['abstract_minus_concrete']['diff']:+.3f} "
              f"{np.round(d['abstract_minus_concrete']['ci95'], 3)}")
    if args.public:
        out = REPO / "public_data" / "plato_bird.json"
        out.write_text(json.dumps(no_nan(to_jsonable(public_view(res))), separators=(",", ":"), allow_nan=False) + "\n")
        print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
