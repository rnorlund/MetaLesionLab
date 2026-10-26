"""The Naming Assessment's PDF report: one summary page, then an item appendix.

Measurements only, beside published group references; a qualified person interprets them.
Rendered in memory from what the browser sends; nothing is stored.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

DISCLAIMER = "For use by clinicians and researchers. Measurements only; no diagnosis or prognosis."
CODE_LABELS = {"Correct": "Correct", "Semantic": "Semantic", "Formal": "Formal", "Mixed": "Mixed",
               "Nonword": "Nonword", "Neologism": "Neologism", "Unrelated": "Unrelated",
               "Description": "Description", "Visual": "Visual", "NoResponse": "No response"}
CODE_RGB = {"Correct": (17, 24, 39), "Semantic": (37, 99, 235), "Formal": (194, 65, 12), "Mixed": (124, 58, 237),
            "Nonword": (15, 118, 110), "Neologism": (190, 24, 93), "Unrelated": (146, 64, 14),
            "Description": (162, 28, 175), "Visual": (21, 128, 61), "NoResponse": (107, 114, 128)}
FLAG_TEXT = {"speech_at_onset": "speech already under way when the picture appeared",
             "noisy_lead_in": "background sound before the picture",
             "no_onset_found": "speech heard but no clear onset"}
FONT_PAIRS = [
    (os.environ.get("TOT_PDF_FONT", ""), os.environ.get("TOT_PDF_FONT_BOLD", "")),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", ""),
]
INK, MUTED, LINE = (17, 24, 39), (75, 85, 99), (209, 213, 219)


class _Doc:
    def __init__(self):
        from fpdf import FPDF

        self.pdf = FPDF(format="letter", unit="mm")
        self.pdf.set_auto_page_break(False)
        self.pdf.set_creator("Tippa Lingua")
        self.pdf.set_title("Picture-naming assessment report")
        self.family, self.bold, self.unicode = "Helvetica", True, False
        for regular, bold in FONT_PAIRS:
            if regular and Path(regular).exists():
                self.pdf.add_font("R", "", regular)
                self.bold = bool(bold and Path(bold).exists())
                if self.bold:
                    self.pdf.add_font("R", "B", bold)
                self.family, self.unicode = "R", True
                break
        self.m = 14.0
        self.w = self.pdf.w - 2 * self.m

    def t(self, s) -> str:
        s = "" if s is None else str(s)
        return s if self.unicode else s.encode("latin-1", "replace").decode("latin-1")

    def font(self, size, bold=False, rgb=INK):
        self.pdf.set_font(self.family, "B" if bold and self.bold else "", size)
        self.pdf.set_text_color(*rgb)

    def text(self, x, y, s, size=9, bold=False, rgb=INK):
        self.font(size, bold, rgb)
        self.pdf.text(x, y, self.t(s))

    def cell(self, x, y, w, h, s, size=9, bold=False, rgb=INK, align="L", fill=None):
        self.font(size, bold, rgb)
        self.pdf.set_xy(x, y)
        if fill:
            self.pdf.set_fill_color(*fill)
        s = self.t(s)
        while s and self.pdf.get_string_width(s) > w - 1.5:  # keep cells to one line
            s = s[:-2] + "…" if self.unicode else s[:-4] + "..."
        self.pdf.cell(w, h, s, align=align, fill=bool(fill))

    def footer(self, page_label: str):
        self.text(self.m, self.pdf.h - 8, DISCLAIMER, 7.5, rgb=MUTED)
        self.font(7.5, rgb=MUTED)
        self.pdf.set_xy(self.m, self.pdf.h - 11)
        self.pdf.cell(self.w, 4, self.t(page_label), align="R")


def _fmt_ms(v) -> str:
    return "–" if v is None else f"{v / 1000:.2f} s"


def render(session: dict, summary: dict, reference: dict, history: list[dict]) -> bytes:
    d = _Doc()
    pdf, m, w = d.pdf, d.m, d.w
    pdf.add_page()
    stamp = time.strftime("%Y-%m-%d %H:%M")

    # Title and disclaimer
    d.text(m, m + 5, "Picture-naming assessment · session report", 15, bold=True)
    d.text(m, m + 11, "Tippa Lingua · automatic transcription and coding, reviewed by a person", 8.5, rgb=MUTED)
    pdf.set_fill_color(254, 243, 199)
    pdf.set_draw_color(252, 211, 77)
    pdf.rect(m, m + 14, w, 8, style="DF")
    d.cell(m + 3, m + 14, w - 6, 8, DISCLAIMER, 9.5, bold=True)
    y = m + 27

    # Session details
    started = (session.get("started") or "")[:16].replace("T", " ")
    rows = [("Speaker code", session.get("speaker") or "–"), ("Date", started or stamp),
            ("Test", (session.get("set_name") or "–") + (" (private set)" if session.get("private_set") else "")),
            ("Language", session.get("lang") or "–"),
            ("Items scored", f"{summary['n']}" + (" (practice items excluded)" if any(i.get("practice") for i in session["items"]) else "")),
            ("Time limit per item", f"{session.get('time_limit_s', 20):g} s"),
            ("Form", session.get("form") or "whole set"),
            ("Second rater (Muse Spark)", "on" if session.get("second_rater") else "off")]
    col_w = w / 2
    for k, (label, value) in enumerate(rows):
        x = m + (k % 2) * col_w
        yy = y + (k // 2) * 5.2
        d.cell(x, yy, 42, 5, label, 8.5, rgb=MUTED)
        d.cell(x + 42, yy, col_w - 44, 5, value, 9)
    y += 4 * 5.2 + 3

    # Key measures
    tiles = [("Accuracy (first complete response)",
              f"{summary['correct']} / {summary['n']}" + (f"  ({summary['accuracy_pct']:g}%)" if summary["n"] else "")),
             ("Median naming latency, correct", _fmt_ms(summary["latency_median_ms"])),
             ("Interquartile range (n = %d)" % summary["latency_n"],
              f"{_fmt_ms(summary['latency_q1_ms'])} – {_fmt_ms(summary['latency_q3_ms'])}" if summary["latency_n"] else "–"),
             ("Reached the time limit", str(len(summary["timeouts"])))]
    tw = (w - 3 * 3) / 4
    for k, (label, value) in enumerate(tiles):
        x = m + k * (tw + 3)
        pdf.set_fill_color(243, 244, 246)
        pdf.rect(x, y, tw, 16, style="F")
        d.cell(x + 2, y + 1.5, tw - 4, 5, label, 7.5, rgb=MUTED)
        d.cell(x + 2, y + 7, tw - 4, 7, value, 12.5, bold=True)
    y += 21

    # Error types (left) and latency per item (right)
    d.text(m, y, "Responses by type (reviewer's final codes)", 10, bold=True)
    d.text(m + w * 0.42, y, "Naming latency per item", 10, bold=True)
    y0 = y + 3
    n = max(summary["n"], 1)
    yy = y0
    for code in CODE_LABELS:
        count = summary["counts"].get(code, 0)
        if not count:
            continue
        pdf.set_fill_color(*CODE_RGB[code])
        pdf.rect(m, yy + 1.2, 2.6, 2.6, style="F")
        d.cell(m + 4, yy, 30, 5, CODE_LABELS[code], 8.5)
        d.cell(m + 34, yy, 10, 5, str(count), 8.5, align="R")
        d.cell(m + 45, yy, 14, 5, f"{100 * count / n:.0f}%", 8.5, rgb=MUTED, align="R")
        bar = (w * 0.42 - 64) * count / n
        pdf.rect(m + 61, yy + 1.2, max(bar, 0.4), 2.6, style="F")
        yy += 5
    if not summary["counts"]:
        d.text(m, yy + 4, "No scored items.", 9, rgb=MUTED)
    _latency_chart(d, session, m + w * 0.42, y0 + 1, w * 0.58, 46)
    y = max(yy, y0 + 50) + 4

    # Published references
    d.text(m, y, "Published group references", 10, bold=True)
    d.font(7.5, rgb=MUTED)
    pdf.set_xy(m, y + 1.5)
    pdf.multi_cell(w, 3.4, d.t(reference["caption"]))
    y = pdf.get_y() + 1
    heads = [("Group", 74), ("N", 12), ("Accuracy", 18), ("Semantic", 16), ("Formal", 14), ("Nonword", 16),
             ("No resp.", 15), ("Source", w - 165)]
    x = m
    for label, cw in heads:
        d.cell(x, y, cw, 4.5, label, 7.5, rgb=MUTED)
        x += cw
    y += 4.8
    ref_rows = [(c["label"], c["n"], c["accuracy"], None, c["source"]) for c in reference["controls"]] + \
               [(g["label"], None, g["accuracy"], g, g["source"]) for g in reference["groups"]]
    for label, nn, acc, g, src in ref_rows:
        pdf.set_draw_color(*LINE)
        pdf.line(m, y, m + w, y)
        shares = (g or {}).get("shares", {})
        cells = [label, "" if nn is None else str(nn), acc] + [
            ("–" if code in (g or {}).get("missing", []) or g is None else f"{100 * shares.get(code, 0):.0f}%")
            for code in ("Semantic", "Formal", "Nonword", "NoResponse")] + [src]
        x = m
        for (_, cw), value in zip(heads, cells):
            d.cell(x, y + 0.3, cw, 4.5, value, 7.8)
            x += cw
        y += 4.8
    d.text(m, y + 3, "Nonword includes neologisms; No resp. includes descriptions (as in the sources). "
                     "Full citations are in the item appendix.", 7, rgb=MUTED)
    y += 7

    # Earlier sessions for this speaker (measurements only; no trend lines or predictions)
    past = [h for h in history if h.get("accuracy_pct") is not None][-8:]
    if past:
        d.text(m, y + 3, f"Sessions for {session.get('speaker') or 'this speaker'} in this browser", 10, bold=True)
        y += 5.5
        heads2 = [("Date", 34), ("Test", 70), ("Form", 22), ("Items", 16), ("Accuracy", 22), ("Median latency", w - 164)]
        x = m
        for label, cw in heads2:
            d.cell(x, y, cw, 4.5, label, 7.5, rgb=MUTED)
            x += cw
        y += 4.8
        for h in past:
            pdf.line(m, y, m + w, y)
            vals = [str(h.get("date", ""))[:16].replace("T", " "), h.get("set_name", ""), h.get("form") or "whole set",
                    str(h.get("n", "")), f"{h['accuracy_pct']:g}%", _fmt_ms(h.get("latency_median_ms"))]
            x = m
            for (_, cw), v in zip(heads2, vals):
                d.cell(x, y + 0.3, cw, 4.5, v, 7.8)
                x += cw
            y += 4.8

    # Sign-off
    y = max(y + 6, pdf.h - 36)
    pdf.set_draw_color(*LINE)
    pdf.line(m, y, m + w, y)
    d.text(m, y + 5, "Reviewed by: ________________________________     Date: ______________", 9)
    d.font(7.5, rgb=MUTED)
    pdf.set_xy(m, y + 8)
    pdf.multi_cell(w, 3.4, d.t(
        "Responses were transcribed by Muse Voice Transcribe and coded automatically with Philadelphia Naming Test "
        "categories (Roach et al., 1996), scoring the first complete response; the reviewer's codes are final. "
        "Latency is the time from picture onset to the start of speech, found by an energy-based detector; device "
        f"audio and display delays (typically tens of ms) are not corrected. Generated {stamp}."))
    d.footer("Page 1 · summary")

    _appendix(d, session, reference)
    return bytes(pdf.output())


def _latency_chart(d: _Doc, session: dict, x: float, y: float, w: float, h: float) -> None:
    pdf = d.pdf
    items = [i for i in session["items"] if not i.get("practice")]
    if not items:
        return
    lat = [(i.get("reviewer_latency_ms") if i.get("reviewer_latency_ms") is not None else i.get("latency_ms")) for i in items]
    top = max([v for v in lat if v is not None] + [1000.0]) * 1.12
    step = 500 if top <= 3000 else 1000 if top <= 8000 else 5000
    left, bottom = x + 9, y + h - 5
    ph, pw = h - 7, w - 11
    pdf.set_draw_color(*LINE)
    pdf.set_line_width(0.2)
    tick = 0.0
    while tick <= top:
        yy = bottom - ph * tick / top
        pdf.line(left, yy, left + pw, yy)
        d.text(x, yy + 1, f"{tick / 1000:g}s", 6.5, rgb=MUTED)
        tick += step
    bw = pw / len(items)
    for k, (it, v) in enumerate(zip(items, lat)):
        code = it.get("reviewer") or it.get("code") or "NoResponse"
        cx = left + k * bw
        if v is None:
            d.text(cx + bw / 2 - 0.9, bottom - 0.8, "×", 7, rgb=CODE_RGB.get(code, MUTED))
        else:
            pdf.set_fill_color(*CODE_RGB.get(code, MUTED))
            bh = ph * v / top
            pdf.rect(cx + bw * 0.18, bottom - bh, bw * 0.64, bh, style="F")
        if len(items) <= 40 or k % 5 == 4:
            d.text(cx + bw / 2 - 1.2, bottom + 3.5, str(it.get("n") or k + 1), 5.5, rgb=MUTED)
    d.text(left, y + h + 1.5, f"Bars: latency to speech onset, colored by final code. ×: no response "
                              f"(limit {session.get('time_limit_s', 20):g} s).", 6.5, rgb=MUTED)


def _appendix(d: _Doc, session: dict, reference: dict) -> None:
    pdf, m, w = d.pdf, d.m, d.w
    heads = [("#", 8), ("Target", 26), ("Heard (transcript)", 46), ("Scored", 28), ("Auto", 18), ("2nd rater", 18),
             ("Final", 18), ("Latency", 14), ("Notes", w - 176)]
    page = 1

    def new_page():
        nonlocal page
        page += 1
        pdf.add_page()
        d.text(m, m + 4, f"Item appendix · {session.get('speaker') or ''} · {session.get('set_name') or ''}", 11, bold=True)
        x = m
        for label, cw in heads:
            d.cell(x, m + 8, cw, 4.5, label, 7.5, rgb=MUTED)
            x += cw
        d.footer(f"Page {page} · items")
        return m + 13

    y = new_page()
    for k, it in enumerate(session["items"], 1):
        if y > pdf.h - 20:
            y = new_page()
        lat = it.get("reviewer_latency_ms") if it.get("reviewer_latency_ms") is not None else it.get("latency_ms")
        notes = []
        if it.get("practice"):
            notes.append("practice")
        if it.get("timeout"):
            notes.append("time limit")
        if it.get("reviewer") and it.get("code") and it["reviewer"] != it["code"]:
            notes.append("reviewer changed")
        if it.get("reviewer_latency_ms") is not None:
            notes.append("latency edited")
        notes += [FLAG_TEXT.get(f, f) for f in it.get("flags") or []]
        second = (it.get("second") or {}).get("code")
        vals = [str(it.get("n") or k), it.get("target"), it.get("transcript") or "(nothing)", it.get("scored_response") or "",
                CODE_LABELS.get(it.get("code"), it.get("code") or ""), CODE_LABELS.get(second, second or ""),
                CODE_LABELS.get(it.get("reviewer") or it.get("code"), ""), "–" if lat is None else f"{lat:.0f} ms",
                "; ".join(notes)]
        pdf.set_draw_color(*LINE)
        pdf.line(m, y, m + w, y)
        x = m
        for (_, cw), v in zip(heads, vals):
            d.cell(x, y + 0.3, cw, 4.6, v, 7.5)
            x += cw
        y += 4.9
    if y > pdf.h - 60:
        y = new_page()
    y += 5
    d.text(m, y, "Sources for the published references", 9, bold=True)
    d.font(7, rgb=MUTED)
    pdf.set_xy(m, y + 2)
    seen = []
    for r in reference["controls"] + reference["groups"]:
        if r["citation"] and r["citation"] not in seen:
            seen.append(r["citation"])
    pdf.multi_cell(w, 3.3, d.t("\n".join(seen)))
