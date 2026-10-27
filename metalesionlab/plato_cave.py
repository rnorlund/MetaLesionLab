"""Plato's Cave: name the shadow.

Plato's prisoners see only shadows on the cave wall and take them for the things themselves. How much of
an everyday object survives as a bare shadow, and does an AI lose the same objects people do?

For each of the 100 checked pictures of the core naming set (runs/sets/core100_en), four versions:
  original    the line drawing, cropped to the object
  outline     only the silhouette's outer contour, as a line (no inner detail)
  silhouette  the drawing filled black (holes filled, as in Wagemans et al. 2008)
  shadow      the silhouette as a blurred, sheared shadow cast on a lit gray wall
All four share one square crop around the object, so size and position don't differ between versions.

Silhouettes come from code (plato_shapes.silhouette_mask). Three open drawings (foot, ear, nose) are
closed across their biggest opening first (plato_shapes.seal_open_drawing).

Human comparison: Wagemans, De Winter, Op de Beeck, Ploeger, Beckers & Vanroose (2008), "Identification
of everyday objects on the basis of silhouette and outline versions", Perception 37:207-244, Table 2:
per-item identification of silhouettes and outlines of the 260 Snodgrass & Vanderwart (1980) pictures by
Flemish students. No licence is stated for those data, so the repository quotes published numbers only
(public_data/plato_cave.json holds derived statistics) and never ships the table.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from metalesionlab import plato_shapes as ps

CAVE_DIR = Path(os.environ.get("CAVE_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/cave"))
SET_DIR = Path(os.environ.get("CAVE_SET_DIR",
                              "/Users/super/Documents/Meta_Hacking_Challenge/MetaLesionLab/runs/sets/core100_en"))
VERSIONS = ("original", "outline", "silhouette", "shadow")
SIDE = 512                # stimulus size (Glimmer's probe pads and resizes to 448)
OUTLINE_WIDTH = (4.0, 10.0)  # outline width range, px at the 1024 working size; each picture's own stroke width
# Pictures whose closing radius was checked by eye on the QC sheet and set by hand (px at 1024).
RADIUS_OVERRIDES: dict[str, float] = {"feather": 12}  # the barbs' lines leave gaps to the outside
# Open drawings that flooding can't fill (a foot cut off at the ankle, an ear and a nose drawn as open
# curves): closed across their biggest opening instead (plato_shapes.seal_open_drawing). SAM 3.1 was tried
# on these three first: its foot mask was patchy, its nose mask covered a small patch, and it found no ear.
OPEN_ITEMS = ("foot", "ear", "nose")
NAMING_PROMPT = "Name the object in this picture with exactly one word."
CREDIT_NORMS = ("Wagemans, J., De Winter, J., Op de Beeck, H., Ploeger, A., Beckers, T., & Vanroose, P. (2008). "
                "Identification of everyday objects on the basis of silhouette and outline versions. "
                "Perception, 37(2), 207-244. doi:10.1068/p5825")


@dataclass
class CaveItem:
    word: str
    alternates: tuple[str, ...]
    image: Path


def load_items(set_dir: Path = SET_DIR) -> list[CaveItem]:
    manifest = json.loads((Path(set_dir) / "manifest.json").read_text())
    return [CaveItem(it["word"], tuple(it.get("alternates") or ()), Path(set_dir) / it["image"])
            for it in manifest["items"] if it.get("status") == "kept" and it.get("image")]


@dataclass
class Versions:
    images: dict[str, Image.Image]
    radius: float
    fill_ratio: float
    source: str           # "code" (flood fill) or "sealed" (biggest opening closed first)
    solidity: float


def make_versions(img: Image.Image, side: int = SIDE, radius: float | None = None, seal: bool = False,
                  seed: int = 0) -> Versions:
    """The four versions of one picture, all in the same square crop around the object."""
    gray = ps.to_gray(img)
    ink = ps.ink_mask(gray)
    if seal:
        mask, _ = ps.seal_open_drawing(ink)
        r, fill, source = 0.0, float(mask.sum()) / max(ink.sum(), 1), "sealed"
    else:
        sil = ps.silhouette_mask(ink, radius=radius)
        mask, r, fill, source = sil.mask, sil.radius, sil.fill_ratio, "code"
    box = ps.square_crop_box(ps.bbox(mask | ink), gray.shape[::-1], margin=0.08)
    g = ps.crop_square(gray, box, 255)
    m = ps.crop_square(mask, box, False)
    original = Image.fromarray(g).resize((side, side), Image.LANCZOS).convert("RGB")
    width = float(np.clip(ps.stroke_width(ink), *OUTLINE_WIDTH))
    outline = ps.mask_image(ps.outline_mask(m, width), side)
    silhouette = ps.mask_image(m, side)
    shadow = ps.cast_shadow(m, side, seed=seed)
    return Versions({"original": original, "outline": outline, "silhouette": silhouette, "shadow": shadow},
                    r, fill, source, ps.solidity(m))
