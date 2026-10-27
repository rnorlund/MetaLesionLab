"""Shapes from line drawings, for Plato's Cave and the Cratylus.

Everything here is plain code on numpy arrays (scipy only, no model):
  ink_mask         dark pixels of a black-on-white drawing, specks removed
  silhouette_mask  the drawing filled in by flooding the background from the picture's edge; outlines
                   with small gaps are closed first (morphological closing with the smallest radius
                   that seals them). Enclosed holes are filled, as in the silhouette norms of
                   Wagemans et al. (2008), whose main silhouettes also filled holes.
  outline_mask     the silhouette's outer contour only, as a line
  cast_shadow      the silhouette as a blurred, sheared shadow on a lit gray wall
  solidity         area / convex-hull area of a mask (1 = convex; a star is far below 1)
  corner_count     sharp convex corners ("points") along the outer contour
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage as ndi

INK_THRESHOLD = 200       # gray level below which a pixel is ink (anti-aliased black lines on white)
MIN_SPECK_FRACTION = 2e-5  # ink components smaller than this share of the picture are paper grain
CLOSE_RADII = (0, 2, 3, 5, 8, 12, 18)  # closing radii tried, in px at WORK_SIDE
WORK_SIDE = 1024


def to_gray(img: Image.Image, side: int | None = WORK_SIDE) -> np.ndarray:
    """The picture as uint8 gray, scaled so its longer side is `side` (None keeps the size).
    Transparency is composited on white."""
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, rgba)
    g = img.convert("L")
    if side and max(g.size) != side:
        s = side / max(g.size)
        g = g.resize((max(1, round(g.width * s)), max(1, round(g.height * s))), Image.LANCZOS)
    return np.asarray(g)


def ink_mask(gray: np.ndarray, threshold: int = INK_THRESHOLD, min_fraction: float = MIN_SPECK_FRACTION) -> np.ndarray:
    ink = gray < threshold
    lab, n = ndi.label(ink, structure=np.ones((3, 3)))
    if n:
        sizes = ndi.sum(ink, lab, index=np.arange(1, n + 1))
        keep = np.zeros(n + 1, bool)
        keep[1:] = sizes >= max(1, min_fraction * ink.size)
        ink = keep[lab]
    return ink


def _dilate(mask: np.ndarray, r: float) -> np.ndarray:
    return mask if r <= 0 else ndi.distance_transform_edt(~mask) <= r


def _erode(mask: np.ndarray, r: float) -> np.ndarray:
    return mask if r <= 0 else ndi.distance_transform_edt(mask) > r


def flood_fill(ink: np.ndarray, radius: float = 0) -> np.ndarray:
    """Everything the background can't reach from the picture's edge, after closing gaps narrower than
    2 * radius. The closing is undone on the outside (erosion by the same radius), and the ink itself is
    always kept, so thin parts (stems, antennae) survive."""
    closed = _dilate(ink, radius)
    padded = np.pad(closed, 1)  # the edge itself is background, so objects touching it still fill
    outside = ~padded
    lab, _ = ndi.label(outside)
    edge_labels = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    reach = np.isin(lab, edge_labels[edge_labels > 0])[1:-1, 1:-1]
    filled = ~reach
    if radius > 0:
        filled = _erode(filled, radius)
    return filled | ink


@dataclass
class Silhouette:
    mask: np.ndarray
    radius: float          # closing radius used (px at the working size)
    fill_ratio: float      # filled area / ink area
    areas: dict            # filled area for every radius tried


def silhouette_mask(ink: np.ndarray, radii=CLOSE_RADII, jump: float = 1.6, settle: float = 1.15,
                    radius: float | None = None) -> Silhouette:
    """Fill the drawing from outside. An outline with a gap leaks: the background floods the inside and
    the 'silhouette' is little more than the ink. So try closing radii from small to large and keep the
    smallest one after which the filled area stops jumping: the first radius r whose area is within
    `settle` of the next radius's area, after any jump of `jump` times or more has happened. A fixed
    `radius` skips the search (used for checked overrides)."""
    ink_area = max(int(ink.sum()), 1)
    if radius is not None:
        m = flood_fill(ink, radius)
        return Silhouette(m, radius, float(m.sum()) / ink_area, {radius: int(m.sum())})
    masks = {r: flood_fill(ink, r) for r in radii}
    areas = {r: int(m.sum()) for r, m in masks.items()}
    rs = list(radii)
    # the last big jump marks where a leak got sealed; settle on the first stable radius after it
    start = 0
    for i in range(len(rs) - 1):
        if areas[rs[i + 1]] >= jump * max(areas[rs[i]], 1):
            start = i + 1
    chosen = rs[start]
    for i in range(start, len(rs) - 1):
        if areas[rs[i + 1]] <= settle * max(areas[rs[i]], 1):
            chosen = rs[i]
            break
    m = masks[chosen]
    return Silhouette(m, chosen, float(m.sum()) / ink_area, areas)


def seal_open_drawing(ink: np.ndarray, min_length: float = 0.08, width: int = 3) -> tuple[np.ndarray, tuple]:
    """Fill an open drawing (a foot cut off at the ankle, an ear or a nose drawn as one curve) by closing
    its biggest opening: every edge of the ink's convex hull at least `min_length` of the picture's size
    long is tried alone as a straight line, and the one whose closure encloses the most area wins.
    Returns the filled mask and the chosen edge ((x0, y0), (x1, y1))."""
    from PIL import ImageDraw
    from scipy.spatial import ConvexHull

    ys, xs = np.nonzero(ink)
    hull = ConvexHull(np.stack([xs, ys], 1).astype(float))
    verts = hull.points[hull.vertices]
    best, best_area, best_edge = flood_fill(ink), -1, None
    for a, b in zip(verts, np.roll(verts, -1, 0)):
        if np.hypot(*(b - a)) < min_length * max(ink.shape):
            continue
        img = Image.fromarray(ink.astype(np.uint8) * 255)
        ImageDraw.Draw(img).line([tuple(a), tuple(b)], fill=255, width=width)
        filled = flood_fill(np.asarray(img) > 127)
        if filled.sum() > best_area:
            best, best_area, best_edge = filled, int(filled.sum()), (tuple(a), tuple(b))
    return best, best_edge


def stroke_width(ink: np.ndarray) -> float:
    """Typical line width of a drawing: twice the median distance-to-background along the lines' ridges."""
    d = ndi.distance_transform_edt(ink)
    ridge = (d == ndi.maximum_filter(d, 3)) & ink
    return float(2 * np.median(d[ridge])) if ridge.any() else 0.0


def outline_mask(sil: np.ndarray, width: float = 4.0) -> np.ndarray:
    """The silhouette's outer contour as a line about `width` px wide (inside the silhouette)."""
    filled = ndi.binary_fill_holes(sil)
    return filled & ~_erode(filled, width)


def bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def square_crop_box(box, size, margin: float = 0.08) -> tuple[int, int, int, int]:
    """A square box around `box` with a margin, possibly extending past the picture (filled white later)."""
    x0, y0, x1, y1 = box
    side = max(x1 - x0, y1 - y0)
    side = int(round(side * (1 + 2 * margin))) or 1
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return int(round(cx - side / 2)), int(round(cy - side / 2)), int(round(cx - side / 2)) + side, \
        int(round(cy - side / 2)) + side


def crop_square(arr: np.ndarray, box, fill) -> np.ndarray:
    """arr[y0:y1, x0:x1] with out-of-range parts set to fill."""
    x0, y0, x1, y1 = box
    h, w = arr.shape[:2]
    out = np.full((y1 - y0, x1 - x0) + arr.shape[2:], fill, dtype=arr.dtype)
    sx0, sy0, sx1, sy1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if sx1 > sx0 and sy1 > sy0:
        out[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = arr[sy0:sy1, sx0:sx1]
    return out


def mask_image(mask: np.ndarray, side: int) -> Image.Image:
    """Black shape on white, resized to side x side (anti-aliased)."""
    img = Image.fromarray(np.where(mask, 0, 255).astype(np.uint8))
    return img.resize((side, side), Image.LANCZOS).convert("RGB")


def cast_shadow(mask: np.ndarray, side: int = 512, shear: float = 0.32, squash: float = 0.92,
                blur: float = 0.012, darkness: float = 0.42, wall: int = 182, seed: int = 0) -> Image.Image:
    """The silhouette as a shadow cast on a wall: sheared sideways (the light comes from one side),
    slightly squashed, with soft edges (penumbra), darker gray on a light gray wall lit from the
    middle, with faint stone texture. `mask` is a square crop (the object with a margin)."""
    small = Image.fromarray((mask * 255).astype(np.uint8)).resize((side, side), Image.LANCZOS)
    # Forward map, about the bottom edge (where the object meets the floor):
    #   y_out = side - squash * (side - y_in),  x_out = x_in + shear * (side - y_in)
    # PIL's affine wants the inverse (output -> input):
    #   y_in = side - (side - y_out) / squash,  x_in = x_out - shear * (side - y_out) / squash
    pad = int(side * (abs(shear) + 0.1))
    canvas = Image.new("L", (side + pad, side), 0)
    canvas.paste(small, (0 if shear >= 0 else pad, 0))
    inv = (1, shear / squash, -shear * side / squash, 0, 1 / squash, side - side / squash)
    sheared = canvas.transform(canvas.size, Image.AFFINE, inv, resample=Image.BILINEAR)
    sheared = sheared.filter(ImageFilter.GaussianBlur(radius=max(0.5, blur * side)))
    # crop back to a square around the shadow
    m = np.asarray(sheared) > 24
    box = bbox(m) or (0, 0, side, side)
    sq = square_crop_box(box, sheared.size, margin=0.08)
    shade = crop_square(np.asarray(sheared).astype(np.float32) / 255.0, sq, 0.0)
    shade = np.asarray(Image.fromarray((shade * 255).astype(np.uint8)).resize((side, side), Image.LANCZOS),
                       np.float32) / 255.0
    # the wall: light in the middle, darker at the edges, faint texture
    yy, xx = np.mgrid[0:side, 0:side] / side - 0.5
    light = 1.08 - 0.55 * (xx ** 2 + (yy * 1.2) ** 2)
    rng = np.random.default_rng(seed)
    grain = ndi.gaussian_filter(rng.normal(0, 1, (side, side)), 2.0)
    grain = grain / (grain.std() or 1) * 0.025
    wall_img = np.clip(wall * (light + grain), 0, 255)
    out = wall_img * (1 - (1 - darkness) * shade)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).convert("RGB")


# --- roundness measures ----------------------------------------------------------------

def solidity(mask: np.ndarray) -> float:
    """Area / convex-hull area of a binary mask (holes filled). 1 for a convex shape."""
    from scipy.spatial import ConvexHull, QhullError

    filled = ndi.binary_fill_holes(mask)
    area = float(filled.sum())
    if area < 3:
        return float("nan")
    ys, xs = np.nonzero(filled)
    # pixel corners, so a one-pixel-wide shape still has a hull with area
    pts = np.concatenate([np.stack([xs + dx, ys + dy], 1) for dx in (0, 1) for dy in (0, 1)]).astype(float)
    try:
        hull = ConvexHull(pts)
    except QhullError:
        return float("nan")
    return min(1.0, area / hull.volume)


def outer_contour(mask: np.ndarray) -> np.ndarray:
    """Ordered (x, y) points around the boundary of the mask's largest component (holes filled), by
    tracing the boundary pixels (Moore neighbour tracing)."""
    filled = ndi.binary_fill_holes(mask)
    lab, n = ndi.label(filled)
    if not n:
        return np.zeros((0, 2))
    sizes = ndi.sum(filled, lab, index=np.arange(1, n + 1))
    comp = np.pad(lab == (1 + int(np.argmax(sizes))), 1)
    ys, xs = np.nonzero(comp)
    start = (int(ys[0]), int(xs[0]))  # topmost-leftmost pixel
    # neighbours clockwise starting west
    nbr = [(0, -1), (-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1)]
    pts = [start]
    cur, back = start, 0  # we entered `start` from the west (outside)
    for _ in range(4 * comp.size):
        for k in range(8):
            d = (back + 1 + k) % 8
            y, x = cur[0] + nbr[d][0], cur[1] + nbr[d][1]
            if comp[y, x]:
                back = (d + 4) % 8
                cur = (y, x)
                break
        else:
            break  # a single pixel
        if cur == start:
            break
        pts.append(cur)
    arr = np.array(pts, float)[:, ::-1] - 1  # (x, y), undo the padding
    return arr


def resample_closed(pts: np.ndarray, n: int) -> np.ndarray:
    """n points evenly spaced by arc length around a closed polyline."""
    closed = np.vstack([pts, pts[:1]])
    seg = np.hypot(*np.diff(closed, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seg)])
    if s[-1] == 0:
        return np.repeat(pts[:1], n, 0)
    t = np.linspace(0, s[-1], n, endpoint=False)
    return np.stack([np.interp(t, s, closed[:, 0]), np.interp(t, s, closed[:, 1])], 1)


def turning_angles(pts: np.ndarray, step: int) -> np.ndarray:
    """Signed turning angle (radians) at each point, between the chords to the points `step` before and
    after. The sign is normalized by the contour's orientation so that convex corners are positive and
    concave ones (the notches between a star's points) negative."""
    prev = np.roll(pts, step, 0)
    nxt = np.roll(pts, -step, 0)
    a = pts - prev
    b = nxt - pts
    cross = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
    dot = (a * b).sum(1)
    ang = np.arctan2(cross, dot)
    # orientation: make convex turns positive (shoelace area sign)
    x, y = pts[:, 0], pts[:, 1]
    signed_area = 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)
    return ang if signed_area > 0 else -ang


def corner_count(mask: np.ndarray, n_points: int = 400, window: float = 0.02, min_angle_deg: float = 60.0,
                 min_separation: float = 0.03) -> int:
    """Sharp convex corners along the outer contour: places where the outline turns by more than
    `min_angle_deg` within a short stretch (a `window` share of the perimeter on each side). A circle or
    blob has 0; a five-pointed star has 5; a square has 4. Peaks closer than `min_separation` of the
    perimeter count once. Scale-free: measured on n_points evenly spaced around the contour."""
    pts = outer_contour(mask)
    if len(pts) < 8:
        return 0
    pts = resample_closed(pts, n_points)
    step = max(1, int(round(window * n_points)))
    ang = np.degrees(turning_angles(pts, step))
    sep = max(1, int(round(min_separation * n_points)))
    above = ang >= min_angle_deg
    if above.all() or not above.any():
        return 0
    # walk the closed loop from a point below threshold, so no run of corner points is split at the start
    start = int(np.argmin(above))
    order = np.roll(np.arange(n_points), -start)
    peaks: list[int] = []
    run: list[int] = []
    for k in range(n_points + 1):
        if k < n_points and above[order[k]]:
            run.append(k)
            continue
        if run:
            peaks.append(run[int(np.argmax(ang[order[run]]))])
            run = []
    kept: list[int] = []
    for p in peaks:
        if not kept or p - kept[-1] >= sep:
            kept.append(p)
    if len(kept) > 1 and kept[0] + n_points - kept[-1] < sep:  # the first and last meet across the start
        kept.pop()
    return len(kept)


def circularity(mask: np.ndarray) -> float:
    """4 pi area / perimeter^2 of the outer contour (1 for a circle)."""
    pts = outer_contour(mask)
    if len(pts) < 3:
        return float("nan")
    filled = ndi.binary_fill_holes(mask)
    per = float(np.hypot(*np.diff(np.vstack([pts, pts[:1]]), axis=0).T).sum())
    # pixel-step contours overestimate the perimeter of curves; smooth by resampling a polygon
    poly = resample_closed(pts, 200)
    per = float(np.hypot(*np.diff(np.vstack([poly, poly[:1]]), axis=0).T).sum())
    return float(4 * math.pi * filled.sum() / per ** 2) if per else float("nan")
