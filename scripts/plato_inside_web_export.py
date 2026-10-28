"""Write web/data/plato_inside.json and static/img/plato_inside/: the data behind /plato/inside, a layer-by-layer
map of Muse Image's doodles and people's doodles inside Muse Glimmer 30B.

Reads the data folder (outside the repository):
- inside_glimmer/raw/intact_arrays.npz: Glimmer's residual stream at the answer position after each of its 52
  decoder layers, for all 920 pictures (920 x 52 x 6,656);
- inside_glimmer/raw/pictures.json and intact.json: which picture is which, what Glimmer said, and the first
  layer where the word lens reads the name;
- inside_glimmer/results.json: each thing's median word-lens layer, as in docs/plato_glimmer.md;
- core/: the pictures themselves, for the small thumbnails.

For every thing and layer it writes:
- the spread of each source (mean pairwise cosine distance on states centered over all 920 pictures, exactly
  the measure in docs/plato_glimmer.md and public_data/plato_glimmer_inside.json);
- a 2-D map of the thing's 24-32 pictures. Each layer is flattened with weighted metric MDS (SMACOF) on the
  pictures' real distances, so a cluster's size on the map tracks its spread: pairs within one source weigh
  1, pairs across sources WEIGHT_ACROSS. Layer 1 starts from classical MDS; every later layer starts from the
  layer before, with a light pull toward it (ANCHOR), and is then rotated onto it (orthogonal Procrustes), so
  the dots move only as far as the model's states change. Plain PCA was tried first and dropped: its two
  biggest directions mostly separate Muse's drawing style from people's and keep a small part of the
  within-source spread in the middle layers.

Thumbnails: one sprite per thing (Muse Image's doodles, then people's, in the map's order), recolored in the
series color on transparency. Derived statistics only: no states, embeddings or distance matrices ship.

    python scripts/plato_inside_web_export.py [--root /path/to/PlatosChair] [--no-sprites]
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = Path("/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair")
OUT = ROOT / "metalesionlab" / "web" / "data" / "plato_inside.json"
SPRITES = ROOT / "metalesionlab" / "web" / "static" / "img" / "plato_inside"
PUBLIC = ROOT / "public_data" / "plato_glimmer_inside.json"
N_LAYERS = 52
RATIO = 0.5            # the collapse rule of public_data/plato_glimmer_inside.json
OTHER_RATIOS = (0.4, 0.6)  # the same rule at other thresholds, for the caveat (0.5 was chosen after seeing the data)
WEIGHT_ACROSS = 0.2    # MDS weight of a Muse-people pair (a pair within one source weighs 1)
ANCHOR = 0.05          # pull toward the previous layer's map, per point, relative to the mean weight
ITERS = 300
GRID = 1000            # map coordinates ship as integers 0..GRID
CELL = 56              # thumbnail side in the sprites, px
INK = {"ai": (29, 78, 216), "human": (194, 65, 12)}  # app.css --blue, --orange
FIRST = "chair"


# --- the map -----------------------------------------------------------------------------------

def unit_states(resid: np.ndarray, layer: int) -> np.ndarray:
    """One layer's answer-position states, centered over all pictures and scaled to length 1 (cosine)."""
    x = np.asarray(resid[:, layer], dtype=np.float64)
    x = x - x.mean(0)
    return x / np.linalg.norm(x, axis=1, keepdims=True)


def spread(u: np.ndarray) -> float:
    """Mean pairwise cosine distance among unit vectors."""
    n = len(u)
    c = u @ u.T
    return float((1 - c)[np.triu_indices(n, 1)].mean())


def classical_mds(d: np.ndarray) -> np.ndarray:
    n = len(d)
    j = np.eye(n) - 1.0 / n
    g = -0.5 * j @ (d ** 2) @ j
    w, v = np.linalg.eigh(g)
    w, v = w[::-1], v[:, ::-1]
    return v[:, :2] * np.sqrt(np.maximum(w[:2], 0))


def smacof(d: np.ndarray, w: np.ndarray, x0: np.ndarray, prev: np.ndarray | None, anchor: float,
           iters: int = ITERS) -> np.ndarray:
    """Weighted metric MDS by majorization, optionally pulled toward prev (a dynamic-MDS penalty)."""
    n = len(d)
    v = -w.copy()
    np.fill_diagonal(v, 0)
    np.fill_diagonal(v, -v.sum(1))
    lam = anchor * w.sum() / n if prev is not None else 0.0
    inv = np.linalg.pinv(v + lam * np.eye(n))
    x = x0.copy()
    for _ in range(iters):
        dist = np.sqrt(((x[:, None] - x[None]) ** 2).sum(-1))
        b = -w * d / np.maximum(dist, 1e-12)
        np.fill_diagonal(b, 0)
        np.fill_diagonal(b, -b.sum(1))
        x = inv @ (b @ x + (lam * prev if prev is not None else 0))
    return x - x.mean(0)


def procrustes(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """The orthogonal matrix q that best maps a onto b (a @ q ~ b)."""
    u, _, vt = np.linalg.svd(a.T @ b)
    return u @ vt


def collapse_layer(muse: list[float], people: list[float], ratio: float = RATIO) -> int | None:
    ratios = [a / b for a, b in zip(muse, people)]
    for k in range(len(ratios)):
        if all(r < ratio for r in ratios[k:]):
            return k + 1
    return None


def map_spread(x: np.ndarray) -> float:
    n = len(x)
    d2 = ((x[:, None] - x[None]) ** 2).sum(-1) / 2  # for unit vectors, cosine distance = squared chord / 2
    return float(d2[np.triu_indices(n, 1)].mean())


# --- thumbnails ----------------------------------------------------------------------------------

def thumbnail(path: Path, source: str, side: int = CELL):
    """The doodle cropped to its ink, as colored ink on transparency."""
    from PIL import Image

    g = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
    bg = float(np.median(g))
    alpha = np.clip((bg - 15 - g) / max(bg - 75, 1), 0, 1)
    ys, xs = np.nonzero(alpha > 0.35)
    if len(xs):
        cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
        r = max(xs.max() - xs.min(), ys.max() - ys.min()) / 2 * 1.08 + 2
    else:
        cy, cx, r = g.shape[0] / 2, g.shape[1] / 2, max(g.shape) / 2
    a = Image.fromarray((alpha * 255).astype(np.uint8))
    a = a.crop((int(cx - r), int(cy - r), int(cx + r), int(cy + r))).resize((side, side), Image.LANCZOS)
    a = np.clip(np.asarray(a, np.float32) * 1.5, 0, 255).astype(np.uint8)  # thin strokes survive the shrink
    rgba = np.zeros((side, side, 4), np.uint8)
    rgba[..., :3] = INK[source]
    rgba[..., 3] = a
    return Image.fromarray(rgba, "RGBA")


def write_sprite(key: str, paths: list[tuple[Path, str]]) -> str:
    from PIL import Image

    sheet = Image.new("RGBA", (CELL * len(paths), CELL), (0, 0, 0, 0))
    for j, (p, src) in enumerate(paths):
        sheet.paste(thumbnail(p, src), (j * CELL, 0))
    SPRITES.mkdir(parents=True, exist_ok=True)
    name = f"{key}.webp"
    sheet.save(SPRITES / name, "WEBP", quality=60, method=6)
    return name


# --- main ------------------------------------------------------------------------------------------

def local_path(core: Path, server_path: str, source: str) -> Path:
    parts = Path(server_path).parts  # .../data/core/ai/doodle/<key>/c0_0.png or .../human/<key>/003.png
    return core.joinpath(*parts[len(parts) - (4 if source == "ai" else 3):])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=DEFAULT_DATA, help="the PlatosChair data folder")
    ap.add_argument("--no-sprites", action="store_true", help="keep the thumbnails already written")
    args = ap.parse_args()
    raw = args.root / "inside_glimmer" / "raw"
    res = json.loads((args.root / "inside_glimmer" / "results.json").read_text())
    pics = json.loads((raw / "pictures.json").read_text())["pictures"]
    items = json.loads((raw / "intact.json").read_text())["items"]
    assert len(pics) == len(items) and all(p["key"] == i["key"] and p["source"] == i["source"]
                                           for p, i in zip(pics, items))
    public = json.loads(PUBLIC.read_text())
    pub = {c["key"]: c for c in public["concepts"]}
    resid = np.load(raw / "intact_arrays.npz")["resid"]
    assert resid.shape[:2] == (len(pics), N_LAYERS), resid.shape

    keys = sorted(pub, key=lambda k: (k != FIRST, pub[k]["label"]))
    groups = {k: ([i for i, p in enumerate(pics) if p["key"] == k and p["source"] == "ai"],
                  [i for i, p in enumerate(pics) if p["key"] == k and p["source"] == "human"]) for k in keys}

    coords = {k: [] for k in keys}
    spreads = {k: {"muse": [], "people": []} for k in keys}
    fidelity = {"muse": [], "people": []}
    for layer in range(N_LAYERS):
        u = unit_states(resid, layer)
        for k in keys:
            ia, ih = groups[k]
            pts = u[ia + ih]
            n, m = len(ia), len(pts)
            spreads[k]["muse"].append(spread(pts[:n]))
            spreads[k]["people"].append(spread(pts[n:]))
            d = np.sqrt(np.maximum(2 - 2 * pts @ pts.T, 0))
            np.fill_diagonal(d, 0)
            w = np.full((m, m), WEIGHT_ACROSS)
            w[:n, :n] = w[n:, n:] = 1.0
            np.fill_diagonal(w, 0)
            prev = coords[k][-1] if coords[k] else None
            x = smacof(d, w, prev if prev is not None else classical_mds(d), prev, ANCHOR)
            if prev is not None:
                x = x @ procrustes(x, prev)
            coords[k].append(x)
            fidelity["muse"].append(map_spread(x[:n]) / spreads[k]["muse"][-1])
            fidelity["people"].append(map_spread(x[n:]) / spreads[k]["people"][-1])

    # One rotation per thing, the same at every layer: Muse's doodles end up left of people's at layer 52.
    for k in keys:
        n = len(groups[k][0])
        last = coords[k][-1]
        v = last[n:].mean(0) - last[:n].mean(0)
        t = np.arctan2(v[1], v[0])
        rot = np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])  # turns v onto +x
        coords[k] = [x @ rot for x in coords[k]]

    extent = max(float(np.abs(x).max()) for k in keys for x in coords[k])
    jumps = []
    concepts = []
    for k in keys:
        ia, ih = groups[k]
        n = len(ia)
        muse, people = spreads[k]["muse"], spreads[k]["people"]
        cl = collapse_layer(muse, people)
        assert cl == pub[k]["collapse_layer"], (k, cl, pub[k]["collapse_layer"])
        assert abs(muse[38] - pub[k]["spread"]["L39"]["muse"]) < 2e-3, k
        for a, b in zip(coords[k], coords[k][1:]):
            jumps.append(float(np.linalg.norm(b - a, axis=1).mean()) / extent)
        nm = res["per_concept"][k]["naming"]
        pictures = []
        for i in ia + ih:
            it = items[i]
            ok = it["code"] == "Correct"
            pictures.append({"said": it["said"].split("\n")[0].strip()[:40], "ok": ok,
                             "lens": it.get("first_correct_layer") if ok else None})
        xy = [[int(round((v + extent) / (2 * extent) * GRID)) for v in x.ravel()] for x in coords[k]]
        entry = {
            "key": k, "label": pub[k]["label"],
            "n": {"muse": n, "people": len(ih)},
            "collapse_layer": cl,
            "name_layer": {"muse": nm["ai"]["first_layer_median"], "people": nm["human"]["first_layer_median"]},
            "named": {"muse": sum(p["ok"] for p in pictures[:n]), "people": sum(p["ok"] for p in pictures[n:])},
            "spread": {"muse": [round(s, 3) for s in muse], "people": [round(s, 3) for s in people]},
            "pictures": pictures,
            "xy": xy,
        }
        if not args.no_sprites:
            entry["sprite"] = write_sprite(k, [(local_path(args.root / "core", pics[i]["path"], pics[i]["source"]),
                                                pics[i]["source"]) for i in ia + ih])
        else:
            entry["sprite"] = f"{k}.webp"
        concepts.append(entry)

    collapsed = [c for c in concepts if c["collapse_layer"]]
    gaps = [c["name_layer"]["muse"] - c["collapse_layer"] for c in collapsed if c["name_layer"]["muse"]]
    other = []
    for r in OTHER_RATIOS:
        cls = {k: collapse_layer(spreads[k]["muse"], spreads[k]["people"], r) for k in keys}
        got = [c for c in concepts if cls[c["key"]]]
        other.append({"ratio": r, "median_collapse_layer": statistics.median(cls[c["key"]] for c in got),
                      "never_collapse": [c["label"] for c in concepts if not cls[c["key"]]],
                      "collapse_at_or_before_name": sum(cls[c["key"]] <= c["name_layer"]["muse"] for c in got
                                                        if c["name_layer"]["muse"]),
                      "n_with_both": sum(1 for c in got if c["name_layer"]["muse"])})
    nn = res["concept_identity"]["nn_accuracy"]
    s = public["summary"]
    out = {
        "about": "Plato's Chair inside Muse Glimmer 30B, layer by layer: for each of 35 things, a 2-D map of Muse "
                 "Image's doodles and people's doodles (Google Quick, Draw!) at each of Glimmer's 52 layers, how "
                 "spread out each source is, the layer where Muse's doodles collapse and the layer where the word "
                 "lens reads the name. Derived statistics only. Exploratory. See docs/plato_glimmer.md.",
        "attribution": public["attribution"],
        "models": public["models"],
        "n_layers": N_LAYERS,
        "definitions": {
            "spread": public["definitions"]["spread"],
            "collapse_layer": public["definitions"]["collapse_layer"],
            "name_layer": "median first layer where the word lens (a logit lens) reads the accepted name, among "
                          "the pictures Glimmer named correctly",
            "lens": "per picture: the first layer where the word lens reads the accepted name; null when Glimmer "
                    "did not name the picture correctly",
            "xy": f"per layer, the pictures' map positions as x0, y0, x1, y1, ... (Muse Image's doodles first), "
                  f"integers 0-{GRID} on one square frame shared by every thing and layer",
            "map": f"weighted metric MDS (SMACOF) on the chord distances between the pictures' centered, unit-length "
                   f"states (cosine distance = squared chord / 2); pairs within a source weigh 1, across sources "
                   f"{WEIGHT_ACROSS:g}. Layer 1 starts from classical MDS; each later layer starts from the one "
                   f"before with a light pull toward it ({ANCHOR:g}) and is rotated onto it (orthogonal "
                   f"Procrustes). The axes have no meaning; distances do.",
        },
        "map": {
            "spread_kept": {src: round(float(np.median(v)), 2) for src, v in fidelity.items()},
            "spread_kept_range": {src: [round(float(np.percentile(v, 5)), 2), round(float(np.percentile(v, 95)), 2)]
                                  for src, v in fidelity.items()},
            "median_step": round(float(np.median(jumps)), 4),
            "max_step": round(float(max(jumps)), 4),
        },
        "summary": {
            "n_concepts": len(concepts),
            "median_collapse_layer": s["median_collapse_layer"],
            "earliest_collapse": s["earliest_collapse"], "latest_collapse": s["latest_collapse"],
            "never_collapse": s["never_collapse"],
            "collapse_at_or_before_name": sum(g >= 0 for g in gaps), "n_with_both": len(gaps),
            "median_layers_between": statistics.median(gaps),
            "named_correctly_pct": s["named_correctly_pct"],
            "mean_spread": {"muse": s["mean_spread_by_layer"]["muse"], "people": s["mean_spread_by_layer"]["people"]},
            "other_thresholds": other,
            "same_thing_neighbour": {
                "what": "share of pictures whose nearest picture (same source, leave-one-out, all 35 things) is a "
                        "picture of the same thing, by layer: how much the state says which thing it is",
                "muse": [round(nn[f"L{i}"]["ai"], 3) for i in range(1, N_LAYERS + 1)],
                "people": [round(nn[f"L{i}"]["human"], 3) for i in range(1, N_LAYERS + 1)],
            },
        },
        "concepts": concepts,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")
    size = OUT.stat().st_size / 1024
    sprites = sum(f.stat().st_size for f in SPRITES.glob("*.webp")) / 1024 if SPRITES.exists() else 0
    print(f"wrote {OUT.relative_to(ROOT)} ({size:.0f} KB) and {len(concepts)} sprites ({sprites:.0f} KB)")
    print(f"map keeps {out['map']['spread_kept']} of each source's spread (5-95%: {out['map']['spread_kept_range']}); "
          f"step per layer median {out['map']['median_step']:.3f}, max {out['map']['max_step']:.3f} of the frame")
    print(f"collapse at or before the name in {out['summary']['collapse_at_or_before_name']} of "
          f"{out['summary']['n_with_both']}; median {out['summary']['median_layers_between']} layers between")


if __name__ == "__main__":
    main()
