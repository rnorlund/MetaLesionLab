# Draw a chair: opt-in drawing donations

Visitors of Draw a chair (the landing page's pad and `/draw`) can choose to donate their drawing for
research. **The feature is off by default** and stays off until the IRB status is confirmed.

| | |
|---|---|
| Switch | `TIPPA_DONATIONS=1` turns it on. Unset (the default), the page shows no checkbox, says drawings are never stored, and the server stores nothing. |
| Where | `TIPPA_DONATIONS_DIR`, else `<data dir>/donations/` (`TIPPA_DATA_DIR` or `TOT_DATA_DIR`; locally `runs/donations/`, which git ignores). |
| Code | `metalesionlab/web/draw_donations.py` (consent text, checks, storage), `metalesionlab/web/draw_routes.py` (when it's called), `static/js/draw.js` (the checkboxes) |
| Export | `python scripts/export_donations.py --out dist/draw_donations` |

## What the visitor sees (when switched on)

Next to "See where it lands", an unticked box **"Donate my drawing to research (optional)"** and a
"What this means" notice. Ticking it shows a second box, **"I am 18 or older"**, which is required: the
page won't send a donation without it, and the server refuses one without it (scoring still works).
The privacy line changes from "never stored or logged" to **"Not stored unless you choose to donate it."**

Consent text (version `draft-2026-10-27`, in `draw_donations.CONSENT`):

- **What we keep:** your drawing as the black-on-white picture the model sees (for drawings on the pad,
  also your pen strokes), the thing you drew, whether you drew it here or uploaded a photo, whether you
  drew it before seeing the AI's pictures, how long you took, your scores and the date. Nothing else: no
  name, email, IP address, cookie or location. For a photo, we keep only the cleaned-up drawing, never the
  photo itself.
- **Why:** to study how people and AI picture everyday things.
- **Sharing:** donated drawings may be shared with other researchers as an open dataset.
- **No take-backs:** because nothing links a drawing to you, it can't be found or deleted later.
- **Questions:** `{{CONTACT}}`, and the IRB line `{{IRB_NOTE}}`: placeholders in `draw_donations.py`
  (`CONTACT`, `IRB_NOTE`) to fill in once the IRB status is known.

## Data minimisation

- **Uploads:** only the processed 256 px black-on-white picture that goes into DINOv2 is kept (paper
  flattened to white, cropped to the ink). The photo itself never leaves `draw.prepare_upload`, so
  backgrounds, anything else in the scene, EXIF and location are never stored. (The browser already
  shrinks the photo to 1024 px and re-encodes it, which drops EXIF before it's sent.)
- **Pad drawings:** the strokes in Quick, Draw! simplified format (aligned, scaled to 0-255, resampled,
  RDP 2.0) plus the same 256 px picture.
- **Identifiers:** a random UUID per donation, not linked to any session, cookie or address; the date
  without a time. No IP address is written (the rate limiter keeps addresses in memory only, as before).
- **Refused donations** (the score is still shown): a photo that fails the drawing-on-paper check (a photo
  of a thing or a scene, blank paper, the paper's edge in view), and any picture that looks like it has
  writing in it (a row of four or more letter-sized marks; a name, say). The writing check flags about 1% of
  people's Quick, Draw! drawings and Muse Image's doodles, and all of 48 test pictures with typed words.

## Storage

Append-only:

```
donations/donations.jsonl   one JSON object per line
donations/png/<uuid>.png    the 256 px picture (written with exclusive create, never overwritten)
```

Record schema:

| Field | Type | Meaning |
|---|---|---|
| `id` | string | random UUID (also the PNG's name) |
| `date` | string | UTC date, `YYYY-MM-DD` |
| `concept` | string | the thing drawn, e.g. `chair` |
| `source` | string | `pad` or `upload` |
| `blind` | bool or null | drawn before this browser tab showed Muse Image's drawings |
| `draw_seconds` | number or null | first stroke to submit (pad only) |
| `scores` | object | `originality`, `d_human`, `d_ai`, `people_closer_to_muse`, `muse_closer`, `own_rank`, `d_doodle`, `nearest_ai`, `nearest_human` |
| `strokes` | array or null | pad only: `[[xs], [ys]]` per stroke, 0-255 |
| `png` | string | `png/<id>.png` |
| `model` | string | `facebook/dinov2-base` |
| `consent` | string | consent text version |

`donations/` is git-ignored, and `scripts/build_site_bundle.py` refuses to put a `donations` path into a
site bundle.

## Deploying with donations: storage must persist

**On a free Hugging Face Space, donations would be lost on every restart**: the container's disk is wiped
when the Space rebuilds, changes settings, or wakes after 48 hours idle. Keeping donations needs one of:

- **Persistent storage on the Space** (Settings → Persistent storage, a paid tier on Roger's account), with
  `TIPPA_DONATIONS_DIR=/data/donations`; or
- **A private Hugging Face dataset repository** on Roger's account that the app appends to (needs a write
  token as a Space secret; not built yet).

Either way it needs Roger's account. Until then, leave `TIPPA_DONATIONS` unset.

## Export for review

```
python scripts/export_donations.py --out dist/draw_donations [--since 2026-11-01]
```

writes `README.md` (consent text, fields, counts), `LICENSE` (CC BY 4.0, pending review),
`drawings.jsonl` (documented fields only), `png/` and `summary.json`. It never changes the donations
themselves. Review the pictures and the IRB status before sharing anything.
