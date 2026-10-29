# Shared page components

Two components for the "Big and quiet" pages of Plato's Chair. Both are plain JS + CSS (no build), colour tokens only,
and both work without JavaScript. Piloted on `/plato/damage` (both) and `/damaged` (carousel). Full usage notes are at the
top of each JS file.

## Hero carousel (`static/js/hero-carousel.js`, `static/css/hero-carousel.css`)

The picture area of a first screen: slides, each a picture or a strip of pictures with a caption of at most 10 words.

```html
<figure class="fl-visual" data-hero-carousel aria-label="...">
  <script type="application/json">{"slides":[{"caption":"rocking chair → car","href":"/optional",
    "images":[{"src":"/static/img/a.webp","alt":"...","label":"undamaged"}]}]}</script>
  <div class="hc-static"> first slide written out: .hc-strip (style="--n:N") of figure.hc-pic, then p.hc-cap </div>
</figure>
```

API: `HeroCarousel.mount(el, {slides, label, interval})` returns `{go(i), play(), pause(), destroy()}`;
`HeroCarousel.slideHtml(slide, i, n)` is the pure markup. Auto-advance 7 s; holds on hover, focus, hidden tab and
off screen; Pause/Play, arrows, dots, arrow keys; `prefers-reduced-motion` means no motion and no auto-advance.
Keep every slide to the same number of pictures (in the row layout, up to six: a tile is a sixth of the row).
Row layout: `data-layout="row"` on the figure (or `{layout:'row'}` to `mount`): one horizontal row of equal square tiles per slide, left to right,
full width under the text (`.fl-wide` in `plato_firstscreen.css`); a scroll strip up to 640px. Used by `/damaged` and `/plato/damage` only. WAI-ARIA carousel pattern (like `quote-carousel.js`).

## Findings (`static/js/findings.js`, `static/css/findings.css`)

A row of picture cards under the first screen; one opens at a time into a full-width panel.

```html
<section class="fd" data-findings aria-label="...">
  <article class="fd-item" id="finding-ID" data-title="<= 6 words" data-line="<= 10 words" data-img="/static/img/x.webp" data-alt="">
    <div class="fd-main">
      <div class="fd-media"><figure><img src="..." alt="..."><figcaption>label</figcaption></figure>...</div>
      <div class="fd-text"><h3>...</h3><p>Sentence.</p><p>Sentence.</p>
        <div class="fd-number"><p class="fd-num-v">38 vs 25</p><p class="fd-num-l">label</p><p class="fd-verdict yes">As predicted</p></div></div>
    </div>
    <div class="fd-extra"> any HTML: existing charts, sliders, figures (keep their ids) </div>
    <details class="how-we-know fd-more"><summary>More detail</summary> method and caveats </details>
  </article>
</section>
```

API: `Findings.render(el, items)` builds the markup from data and mounts it; `Findings.mount(el)` enhances markup already
in the page and returns `{open(id), close(), current()}`; `Findings.itemHtml(item)` is the pure markup.
The Aristotle badge is added to the "More detail" summary. A hash `#finding-ID`, or a hash pointing at anything inside a
panel, opens its card. Real buttons with `aria-expanded` and `aria-controls`; the open card has an orange underline.
Without JavaScript every panel shows, expanded, under its own h3.

## Rolling out to another page

1. Link the CSS and JS. 2. Replace the picture area with the carousel figure; keep its first slide written out.
3. Wrap each existing section in an `article.fd-item` (move, do not copy; keep ids so links and scripts still work;
change the section's `h2` to `h4`). 4. Move method and caveats into the card's "More detail". 5. If a card shows a number,
fill `.fd-num-*` from the page's own data (see `renderCardNumbers` in `plato_damage.js`). 6. Add a test like
`tests/test_hero_carousel_findings.py`.
