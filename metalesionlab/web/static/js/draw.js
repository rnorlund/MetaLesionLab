/* Draw a chair: a mountable drawing game, TOTDraw.mount(el, options), used by /draw and by the landing page.

   Blind first: the visitor draws (or uploads a photo of a drawing on paper) before seeing anything of Muse
   Image's chairs, like the Quick, Draw! players they're compared with. After "See where it lands" come the
   reveal and the results: the originality percentile next to 200 people, the distance from Muse's prototype,
   a map, the closest drawings, a share card and a link to discuss it with Socrates.

   Reference data comes from /api/draw/concepts; a drawing is sent once to be scored (/api/draw, or
   /api/draw/upload for a photo, shrunk and re-encoded here first, which drops EXIF and location) and is
   never stored, unless donations are switched on server-side and the visitor opts in. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;

  // The address shared on X and printed on the card. A placeholder until the live demo has a URL: change
  // this line. When the page is served from a real host (not localhost), that host's /draw is used instead.
  var SITE_URL = 'https://your-site.example/draw';
  var HASHTAGS = 'Muse,MetaAI,Hackathon';
  var SEEN_KEY = 'tot-draw-seen';  // this tab has already shown Muse Image's chairs (so drawings aren't blind)

  var BLUE = '#1D4ED8', ORANGE = '#C2410C', TEAL = '#0D9488', INK = '#111827', INK2 = '#374151', MUTED = '#4B5563',
    GRID = '#E5E7EB', PAPER = '#F7F6F1';
  var NS = 'http://www.w3.org/2000/svg';
  var TIME_S = 20;  // Quick, Draw! players had 20 seconds
  var MAX_SIDE = 1024;  // uploads are shrunk to this before they leave the device

  var PAD_HTML =
    '<div class="dw-ask">' +
    '  <p class="dw-kicker" data-dw="kicker" hidden></p>' +
    '  <h1 class="dw-title" data-dw="title"></h1>' +
    '  <p class="dw-instr" data-dw="instr"></p>' +
    '  <div class="dw-chips" data-dw="chips" role="group" aria-label="What to draw" hidden></div>' +
    '</div>' +
    '<div class="dw-canvas-wrap" data-dw="wrap">' +
    '  <canvas data-dw="pad" role="img" aria-label="Drawing area: draw with a mouse, a finger or a pen"></canvas>' +
    '  <p class="dw-placeholder" data-dw="placeholder" aria-hidden="true"><span>Draw <span data-article>a chair</span> here</span></p>' +
    '  <span class="dw-timer" data-dw="timer" hidden></span>' +
    '  <div class="dw-drop" data-dw="drop" hidden><span>Drop your photo here</span></div>' +
    '</div>' +
    '<div class="dw-actions">' +
    '  <button type="button" class="btn btn-small" data-dw="undo" disabled>Undo</button>' +
    '  <button type="button" class="btn btn-small" data-dw="clear" disabled>Clear</button>' +
    '  <button type="button" class="btn btn-primary dw-go" data-dw="go" disabled>See where it lands</button>' +
    '</div>' +
    '<div class="dw-upload">' +
    '  <label class="dw-upload-btn"><input type="file" accept="image/*" class="sr-only" data-dw="file">' +
    '    <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 11V2.5M4.5 6 8 2.5 11.5 6M2.5 10.5v3h11v-3" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
    '    Or draw on paper and upload a photo</label>' +
    '  <span class="dw-upload-hint">Plain paper, a dark pen, the paper filling the photo. It’s shrunk on your device first, which also drops its location data.</span>' +
    '</div>' +
    '<div class="dw-donate" data-dw="donate-box" hidden>' +
    '  <label class="check"><input type="checkbox" data-dw="donate"><span data-dw="donate-label"></span></label>' +
    '  <details class="dw-consent"><summary>What this means</summary><dl data-dw="consent"></dl><p class="dw-irb" data-dw="irb"></p></details>' +
    '  <label class="check" data-dw="adult-row" hidden><input type="checkbox" data-dw="adult"><span data-dw="adult-label"></span></label>' +
    '</div>' +
    '<p class="dw-status" data-dw="status" role="status" aria-live="polite"></p>' +
    '<p class="dw-privacy"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1 2.5 3.2v4.1c0 3.4 2.3 6.3 5.5 7.2 3.2-.9 5.5-3.8 5.5-7.2V3.2z" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>' +
    '<span data-dw="privacy">Your drawing is processed in memory to compute these numbers and is never stored or logged.</span></p>';

  var RESULTS_HTML =
    '<section class="dw-reveal" data-dw="reveal" aria-labelledby="dw-reveal-h">' +
    '  <h2 class="dw-reveal-h" id="dw-reveal-h" data-dw="reveal-h"></h2>' +
    '  <div class="dw-muse-strip" data-dw="strip" role="img"></div>' +
    '  <p class="dw-cap" data-dw="strip-cap"></p>' +
    '</section>' +
    '<p class="dw-fair" data-dw="fair"></p>' +
    '<div class="dw-tiles">' +
    '  <article class="dw-card dw-orig"><h3>Next to 200 people</h3>' +
    '    <div class="dw-big"><span class="dw-big-num" data-dw="orig-num">–</span><span class="dw-big-text" data-dw="orig-text"></span></div>' +
    '    <p class="dw-verdict" data-dw="orig-verdict"></p><div class="dw-chart" data-dw="orig-chart"></div>' +
    '    <p class="dw-note" data-dw="orig-note"></p><p class="dw-oops" data-dw="looks-like" hidden></p><p class="dw-oops" data-dw="photo-note" hidden></p></article>' +
    '  <article class="dw-card dw-vsmuse"><h3>Next to Muse Image</h3>' +
    '    <p class="dw-headline" data-dw="muse-text"></p><div class="dw-chart" data-dw="muse-chart"></div><p class="dw-note" data-dw="muse-note"></p></article>' +
    '</div>' +
    '<div class="dw-pair">' +
    '  <article class="dw-card"><h3>Where your <span data-label>chair</span> lands</h3><div class="dw-legend" data-dw="map-legend"></div>' +
    '    <div class="dw-chart dw-map" data-dw="map-chart"></div><p class="dw-note" data-dw="map-note"></p></article>' +
    '  <article class="dw-card"><h3>Closest drawings</h3><div class="dw-near" data-dw="near"></div>' +
    '    <p class="dw-note">Closest by DINOv2’s cosine distance, out of all of Muse Image’s doodles and all 200 people’s drawings.</p>' +
    '    <details class="dw-numbers"><summary>See the numbers</summary><div class="table-wrap"><table class="data" data-dw="numbers"></table></div></details></article>' +
    '</div>' +
    '<article class="dw-card dw-share">' +
    '  <div class="dw-share-text"><h3>Share your <span data-label>chair</span></h3>' +
    '    <p>Download the card, or post it. Then dare a friend to beat your score.</p>' +
    '    <div class="dw-actions">' +
    '      <button type="button" class="btn btn-dark" data-dw="download">Download image</button>' +
    '      <a class="btn" data-dw="share-x" href="#" target="_blank" rel="noopener">Share on X</a>' +
    '      <button type="button" class="btn" data-dw="share-native" hidden>Share…</button>' +
    '      <a class="btn" data-dw="socrates-link" hidden></a>' +
    '      <button type="button" class="btn btn-ghost" data-dw="again">Draw another</button>' +
    '    </div></div>' +
    '  <canvas class="dw-card-preview" data-dw="card" width="1200" height="675" aria-label="Your share card"></canvas>' +
    '</article>';

  // ---------- small helpers ----------

  function svg(tag, attrs, kids) {
    var el = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) el.setAttribute(k, attrs[k]); });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c != null) el.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return el;
  }
  function f2(x) { return Number(x).toFixed(2); }
  function fmt1(r) { return (Math.round(r * 10) / 10).toFixed(1); }
  function median(a) { var b = a.slice().sort(function (x, y) { return x - y; }); var m = b.length >> 1; return b.length % 2 ? b[m] : (b[m - 1] + b[m]) / 2; }
  function min(a) { return Math.min.apply(null, a); }
  function max(a) { return Math.max.apply(null, a); }
  function plural(label) { return label + 's'; }
  function article(label) { return (/^[aeiou]/i.test(label) ? 'an ' : 'a ') + label; }
  function cap1(s) { return s.replace(/^./, function (ch) { return ch.toUpperCase(); }); }
  function reduced() { return window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches; }
  function shareUrl() {
    var local = /^(localhost|127\.|0\.0\.0\.0|\[::1\])/.test(location.hostname) || location.protocol === 'file:';
    return local ? SITE_URL : location.origin + '/draw';
  }
  function seen() { try { return window.sessionStorage.getItem(SEEN_KEY) === '1'; } catch (e) { return false; } }
  function markSeen() { try { window.sessionStorage.setItem(SEEN_KEY, '1'); } catch (e) { /* private mode */ } }

  // ---------- copy ----------

  function hook(c) {
    var idx = c.stats.index, pl = plural(c.label);
    if (idx < 0.45) return 'Muse Image drew the same ' + c.label + ' ' + c.n_ai + ' times.';
    if (idx < 0.9) return 'Muse Image drew ' + c.n_ai + ' ' + pl + ', ' + Math.round(100 * (1 - idx)) + '% less varied than people’s.';
    return 'Muse Image drew ' + c.n_ai + ' ' + pl + ', about as varied as people’s.';
  }
  function fair(c) {
    var w = c.stats.when_asked, pl = plural(c.label);
    if (c.stats.index >= 0.9) return 'Muse Image varies its ' + pl + ' about as much as people do, even with the plain prompt.';
    var lead = 'That’s Muse Image’s default: the textbook ' + c.label + '. It can vary when asked. ';
    if (!w) return lead;
    var how = w.prompt === 'unusual' ? 'Asked for an unusual kind of ' + c.label : 'Given a list of different kinds of ' + c.label + ' to draw';
    var ci = w.ratio_vs_people_ci95 || [w.ratio_vs_people, w.ratio_vs_people];
    if (ci[0] > 1) return lead + how + ', its ' + pl + ' were ' + fmt1(w.ratio_vs_people) + ' times as varied as people’s.';
    if (ci[1] >= 1) return lead + how + ', its ' + pl + ' were about as varied as people’s.';
    return lead + how + ', its ' + pl + ' got ' + fmt1(w.ratio_vs_default) + ' times as varied, though still less varied than people’s.';
  }
  function verdict(p, label) {
    if (p >= 95) return 'One of a kind';
    if (p >= 80) return 'A very original ' + label;
    if (p >= 50) return 'An original ' + label;
    if (p >= 20) return 'A familiar ' + label;
    return 'A textbook ' + label;
  }
  function origSentence(p, c) {
    var n = c.n_human, pl = plural(c.label);
    if (p >= 99.5) return 'more original than all ' + n + ' people’s ' + pl;
    if (p <= 0.5) return 'closer to the typical ' + c.label + ' than every one of ' + n + ' people’s';
    return 'more original than ' + Math.round(p) + '% of ' + n + ' people’s ' + pl;
  }
  function museSentence(r, c) {
    var closer = 100 - r.people_closer_to_muse, pl = plural(c.label);
    if (closer <= 0.5) return 'Further from Muse Image’s ' + c.label + ' than every one of ' + c.n_human + ' people’s ' + pl + '.';
    if (closer >= 99.5) return 'Closer to Muse Image’s ' + c.label + ' than all ' + c.n_human + ' people’s ' + pl + '.';
    return 'Closer to Muse Image’s ' + c.label + ' than ' + Math.round(closer) + '% of people’s ' + pl + '.';
  }

  // ---------- sprites: thumbnails of Muse's doodles and people's drawings ----------

  function cell(sprite, i, cls) {
    var cols = sprite.cols, rows = Math.ceil(sprite.n / cols);
    var col = i % cols, row = Math.floor(i / cols);
    var el = h('div', { class: 'dw-cell' + (cls ? ' ' + cls : '') });
    el.style.backgroundImage = 'url("' + sprite.src + '")';
    el.style.backgroundSize = (cols * 100) + '% ' + (rows * 100) + '%';
    el.style.backgroundPosition = (cols > 1 ? col / (cols - 1) * 100 : 0) + '% ' + (rows > 1 ? row / (rows - 1) * 100 : 0) + '%';
    return el;
  }
  var images = {};
  function image(src) {
    if (!images[src]) {
      images[src] = new Promise(function (resolve, reject) {
        var im = new Image();
        im.onload = function () { resolve(im); };
        im.onerror = reject;
        im.src = src;
      });
    }
    return images[src];
  }

  // ---------- charts ----------

  function niceMax(v) { return Math.min(1, Math.ceil(v * 1.08 * 10) / 10); }

  function makeTooltip() {
    var tip = null;
    function show(container, kids, x, y) {
      if (!tip) tip = h('div', { class: 'dw-tip', role: 'presentation' });
      if (tip.parentNode !== container) container.appendChild(tip);
      tip.textContent = '';
      kids.forEach(function (n) { tip.appendChild(n); });
      tip.hidden = false;
      var w = 132, cw = container.clientWidth;
      var below = y < 180;  // near the top of the chart the card's heading is above: open downward instead
      tip.style.left = Math.min(Math.max(0, x - w / 2), cw - w) + 'px';
      tip.style.top = (below ? y + 14 : y - 12) + 'px';
      tip.style.transform = below ? 'none' : 'translateY(-100%)';
    }
    function hide() { if (tip) tip.hidden = true; }
    return { show: show, hide: hide };
  }
  var tooltip = makeTooltip();
  function tipFor(item) {
    var kids = [];
    if (item.sprite) kids.push(cell(item.sprite, item.i));
    var line = h('span');
    line.appendChild(h('span', { class: 'key', style: { background: item.color } }));
    line.appendChild(document.createTextNode(item.label));
    kids.push(line);
    if (item.value != null) kids.push(h('b', { text: 'distance ' + f2(item.value) }));
    return kids;
  }
  // The pointer only has to be closest to a mark (within 24 px), not on it.
  function nearestHover(svgEl, container, items) {
    function at(e) {
      var rect = svgEl.getBoundingClientRect(), vb = svgEl.viewBox.baseVal;
      var k = vb.width / rect.width;
      var x = (e.clientX - rect.left) * k, y = (e.clientY - rect.top) * k;
      var best = null, bd = 24 * k;
      items.forEach(function (it) {
        var d = Math.hypot(it.x - x, it.y - y);
        if (d < bd) { bd = d; best = it; }
      });
      return { best: best, k: k };
    }
    var ring = svg('circle', { r: 9, fill: 'none', stroke: INK, 'stroke-width': 2, visibility: 'hidden', 'pointer-events': 'none' });
    svgEl.appendChild(ring);
    function move(e) {
      var hit = at(e);
      if (!hit.best) { tooltip.hide(); ring.setAttribute('visibility', 'hidden'); return; }
      ring.setAttribute('cx', hit.best.x);
      ring.setAttribute('cy', hit.best.y);
      ring.setAttribute('visibility', 'visible');
      tooltip.show(container, tipFor(hit.best), hit.best.x / hit.k, hit.best.y / hit.k);
    }
    svgEl.addEventListener('pointermove', move);
    svgEl.addEventListener('pointerdown', move);
    svgEl.addEventListener('pointerleave', function () { tooltip.hide(); ring.setAttribute('visibility', 'hidden'); });
  }

  function stripChart(el, o) {
    el.textContent = '';
    var W = Math.max(280, el.clientWidth || 320), L = 8, R = 8, band = 46, top = 30, axisH = 34;
    var H = top + band * o.rows.length + axisH;
    var all = [o.you];
    o.rows.forEach(function (r) { all = all.concat(r.values); });
    var xmax = niceMax(max(all));
    var x = function (v) { return L + (W - L - R) * v / xmax; };
    var root = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img',
      'aria-label': o.rows.map(function (r) { return r.name + ': median ' + f2(median(r.values)); }).join('; ') + '; yours: ' + f2(o.you) });
    var step = xmax > 0.6 ? 0.2 : 0.1;
    for (var t = 0; t <= xmax + 1e-9; t += step) {
      root.appendChild(svg('line', { x1: x(t), x2: x(t), y1: top - 4, y2: H - axisH + 2, stroke: GRID, 'stroke-width': 1 }));
      root.appendChild(svg('text', { class: 'tick', x: x(t), y: H - axisH + 16, 'text-anchor': t === 0 ? 'start' : 'middle' }, f2(t).replace(/^0\./, '.').replace(/^\.00$/, '0')));
    }
    root.appendChild(svg('text', { class: 'lbl', x: W - R, y: H - 2, 'text-anchor': 'end' }, o.axis));
    var items = [];
    o.rows.forEach(function (row, ri) {
      var y0 = top + band * ri;
      root.appendChild(svg('circle', { cx: L + 5, cy: y0 + 6, r: 4, fill: row.color }));
      root.appendChild(svg('text', { class: 'lbl', x: L + 14, y: y0 + 10 }, row.name));
      var dense = row.values.length > 40;
      row.values.forEach(function (v, i) {
        var jitter = dense ? ((i * 37) % 13 - 6) * 1.1 : 0;
        var cx = x(v), cy = y0 + 28 + jitter;
        root.appendChild(svg('circle', { cx: cx, cy: cy, r: dense ? 3.5 : 4.5, fill: row.color, 'fill-opacity': dense ? 0.5 : 0.9,
          stroke: '#FFFFFF', 'stroke-width': dense ? 0.75 : 1.5 }));
        items.push({ x: cx, y: cy, i: i, sprite: row.sprite, color: row.color, value: v,
          label: row.who === 'muse' ? 'Muse Image doodle' : 'A person’s drawing' });
      });
    });
    var yx = x(o.you), yTop = top - 8, yBot = top + band * o.rows.length - 4;
    root.appendChild(svg('line', { x1: yx, x2: yx, y1: yTop, y2: yBot, stroke: TEAL, 'stroke-width': 2 }));
    root.appendChild(svg('circle', { cx: yx, cy: yTop, r: 6, fill: TEAL, stroke: '#FFFFFF', 'stroke-width': 2 }));
    var right = yx > W - 70;
    root.appendChild(svg('text', { class: 'lbl-you', x: yx + (right ? -10 : 10), y: yTop + 4, 'text-anchor': right ? 'end' : 'start',
      stroke: '#FFFFFF', 'stroke-width': 4, 'paint-order': 'stroke' }, 'You ' + f2(o.you)));
    items.push({ x: yx, y: yTop, color: TEAL, label: 'Your drawing', value: o.you });
    el.appendChild(root);
    nearestHover(root, el, items);
  }

  function mapChart(el, legend, c, r) {
    el.textContent = '';
    var W = Math.max(280, el.clientWidth || 320), H = Math.round(W * 0.72), P = 16;
    var pts = c.map.ai.concat(c.map.human, [r.xy]);
    var xs = pts.map(function (p) { return p[0]; }), ys = pts.map(function (p) { return p[1]; });
    var x0 = min(xs), x1 = max(xs), y0 = min(ys), y1 = max(ys);
    var k = Math.min((W - 2 * P) / (x1 - x0 || 1), (H - 2 * P) / (y1 - y0 || 1));  // same scale both ways
    var ox = (W - (x1 - x0) * k) / 2, oy = (H - (y1 - y0) * k) / 2;
    var X = function (v) { return ox + (v - x0) * k; }, Y = function (v) { return H - (oy + (v - y0) * k); };
    var root = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img',
      'aria-label': 'Map of Muse Image’s ' + c.n_ai + ' doodles, ' + c.n_human + ' people’s drawings and yours' });
    root.appendChild(svg('rect', { x: 0.5, y: 0.5, width: W - 1, height: H - 1, rx: 10, fill: '#FCFCFB', stroke: GRID }));
    var items = [];
    c.map.human.forEach(function (p, i) {
      root.appendChild(svg('circle', { cx: X(p[0]), cy: Y(p[1]), r: 4, fill: ORANGE, 'fill-opacity': 0.55, stroke: '#FFFFFF', 'stroke-width': 1 }));
      items.push({ x: X(p[0]), y: Y(p[1]), i: i, sprite: c.sprites.people, color: ORANGE, label: 'A person’s drawing' });
    });
    c.map.ai.forEach(function (p, i) {
      root.appendChild(svg('circle', { cx: X(p[0]), cy: Y(p[1]), r: 5, fill: BLUE, stroke: '#FFFFFF', 'stroke-width': 2 }));
      items.push({ x: X(p[0]), y: Y(p[1]), i: i, sprite: c.sprites.muse, color: BLUE, label: 'Muse Image doodle' });
    });
    var yx = X(r.xy[0]), yy = Y(r.xy[1]);
    root.appendChild(svg('circle', { cx: yx, cy: yy, r: 9, fill: TEAL, stroke: '#FFFFFF', 'stroke-width': 2.5 }));
    var right = yx > W - 60;
    root.appendChild(svg('text', { class: 'lbl-you', x: yx + (right ? -14 : 14), y: yy + 4, 'text-anchor': right ? 'end' : 'start',
      stroke: '#FFFFFF', 'stroke-width': 4, 'paint-order': 'stroke' }, 'You'));
    items.push({ x: yx, y: yy, color: TEAL, label: 'Your drawing' });
    el.appendChild(root);
    nearestHover(root, el, items);
    legend.textContent = '';
    [[BLUE, 'Muse Image (' + c.n_ai + ')'], [ORANGE, 'People (' + c.n_human + ')'], [TEAL, 'You']].forEach(function (e, i) {
      legend.appendChild(h('span', null, [h('i', { class: i === 2 ? 'you' : null, style: { background: e[0] } }), e[1]]));
    });
  }

  // ---------- share card drawing helpers ----------

  function roundRect(g, x, y, w, hgt, r) {
    g.beginPath();
    g.moveTo(x + r, y);
    g.arcTo(x + w, y, x + w, y + hgt, r);
    g.arcTo(x + w, y + hgt, x, y + hgt, r);
    g.arcTo(x, y + hgt, x, y, r);
    g.arcTo(x, y, x + w, y, r);
    g.closePath();
  }
  function wrap(g, text, x, y, maxW, lineH) {
    var words = text.split(' '), line = '';
    words.forEach(function (w) {
      var test = line ? line + ' ' + w : w;
      if (g.measureText(test).width > maxW && line) {
        g.fillText(line, x, y);
        y += lineH;
        line = w;
      } else {
        line = test;
      }
    });
    if (line) g.fillText(line, x, y);
    return y + lineH;
  }
  function fonts() {
    if (!document.fonts || !document.fonts.load) return Promise.resolve();
    return Promise.all(['700 140px "IBM Plex Sans"', '600 34px "IBM Plex Sans"', '400 20px "IBM Plex Mono"']
      .map(function (f) { return document.fonts.load(f).catch(function () {}); }));
  }
  // Strokes are stored in 0-1000 pad units, as [[x, ...], [y, ...]] like Quick, Draw!.
  function strokeAll(g, strokes, k, width, ox, oy) {
    g.strokeStyle = INK;
    g.fillStyle = INK;
    g.lineWidth = width;
    g.lineCap = 'round';
    g.lineJoin = 'round';
    strokes.forEach(function (s) {
      var xs = s[0], ys = s[1];
      if (!xs.length) return;
      if (xs.length === 1) {
        g.beginPath();
        g.arc(ox + xs[0] * k, oy + ys[0] * k, width / 2, 0, 2 * Math.PI);
        g.fill();
        return;
      }
      g.beginPath();
      g.moveTo(ox + xs[0] * k, oy + ys[0] * k);
      for (var i = 1; i < xs.length; i++) g.lineTo(ox + xs[i] * k, oy + ys[i] * k);
      g.stroke();
    });
  }

  // Shrink a photo to MAX_SIDE and re-encode it as JPEG. Drawing it through a canvas keeps only pixels: EXIF,
  // camera details and location stay on the device.
  function prepareFile(file) {
    if (!file || !/^image\//.test(file.type || '')) return Promise.reject(new Error('Please choose a photo (JPEG or PNG).'));
    var load = window.createImageBitmap
      ? createImageBitmap(file, { imageOrientation: 'from-image' }).catch(function () { return createImageBitmap(file); })
      : new Promise(function (resolve, reject) {
        var im = new Image();
        im.onload = function () { resolve(im); };
        im.onerror = reject;
        im.src = URL.createObjectURL(file);
      });
    return load.catch(function () { throw new Error('We couldn’t read that picture. Please choose a JPEG or PNG photo.'); })
      .then(function (bmp) {
        var w = bmp.width, hgt = bmp.height, k = Math.min(1, MAX_SIDE / Math.max(w, hgt));
        var cv = document.createElement('canvas');
        cv.width = Math.max(1, Math.round(w * k));
        cv.height = Math.max(1, Math.round(hgt * k));
        var g = cv.getContext('2d');
        g.fillStyle = '#FFFFFF';
        g.fillRect(0, 0, cv.width, cv.height);
        g.drawImage(bmp, 0, 0, cv.width, cv.height);
        if (bmp.close) bmp.close();
        return new Promise(function (resolve) {
          cv.toBlob(function (blob) { resolve({ blob: blob, canvas: cv }); }, 'image/jpeg', 0.9);
        });
      });
  }

  // ---------- the component ----------

  function mount(el, options) {
    var o = Object.assign({
      title: 'Draw {a thing}.', instruction: 'You have 20 seconds. Don’t overthink it.', kicker: null,
      heading: 'h1', picker: true, deepLink: true, revealStrip: true, results: null,
      onReveal: null, onReset: null
    }, options || {});
    var S = { data: null, key: o.concept || 'chair', strokes: [], current: null, result: null, sent: null, busy: false,
      timerStart: 0, timerId: 0, upload: null, blind: !seen(), started: 0, donations: { enabled: false } };

    el.classList.add('dw-panel');
    el.innerHTML = PAD_HTML;
    if (o.heading !== 'h1') {  // the landing page has its own h1
      var t0 = el.querySelector('[data-dw="title"]'), t1 = document.createElement(o.heading);
      t1.className = t0.className;
      t1.setAttribute('data-dw', 'title');
      t0.replaceWith(t1);
    }
    var res = o.results || h('div');
    if (!o.results) el.after(res);
    res.classList.add('dw-results');
    res.hidden = true;
    res.innerHTML = RESULTS_HTML;
    if (!o.revealStrip) res.querySelector('[data-dw="reveal"]').remove();

    function q(name) { return el.querySelector('[data-dw="' + name + '"]') || res.querySelector('[data-dw="' + name + '"]'); }
    if (!document.getElementById('canvas-wrap')) {  // the guided tour points at these
      q('wrap').id = 'canvas-wrap';
      q('pad').id = 'pad';
    }
    function concept() { return S.data.concepts.filter(function (c) { return c.key === S.key; })[0]; }

    // --- text ---
    function label() { return S.data ? concept().label : 'chair'; }
    function fill(text) { return text.replace('{a thing}', article(label())).replace('{thing}', label()); }
    function renderText() {
      [el, res].forEach(function (root) {
        root.querySelectorAll('[data-label]').forEach(function (n) { n.textContent = label(); });
        root.querySelectorAll('[data-article]').forEach(function (n) { n.textContent = article(label()); });
      });
      q('title').textContent = fill(o.title);
      q('instr').textContent = fill(o.instruction);
      if (o.kicker) { q('kicker').textContent = o.kicker; q('kicker').hidden = false; }
      if (o.picker && S.data) {
        el.querySelectorAll('[data-dw="chips"] button').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.key === S.key)); });
      }
      if (o.onConcept) o.onConcept(label());
    }
    function renderChips() {
      var box = q('chips');
      box.hidden = false;
      box.appendChild(h('span', { class: 'dw-chips-label', text: 'Or draw:' }));
      S.data.concepts.forEach(function (c) {
        box.appendChild(h('button', { type: 'button', 'data-key': c.key, 'aria-pressed': 'false', text: c.label,
          onclick: function () { choose(c.key); } }));
      });
    }
    function choose(key) {
      if (key === S.key || S.busy) return;
      S.key = key;
      if (o.deepLink) {
        var url = new URL(location.href);
        url.searchParams.set('thing', concept().label);
        history.replaceState(null, '', url);
      }
      clearPad();
      hideResults();
      renderText();
    }

    // --- the pad ---
    var pad = q('pad'), ctx = pad.getContext('2d'), dpr = 1, side = 0;
    function sizePad() {
      var rect = pad.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 3);
      side = rect.width;
      pad.width = Math.round(rect.width * dpr);
      pad.height = Math.round(rect.height * dpr);
      redraw();
    }
    function redraw() {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, side, side);
      ctx.fillStyle = '#FFFFFF';
      ctx.fillRect(0, 0, side, side);
      if (S.upload) {
        var cv = S.upload.canvas, k = Math.min(side / cv.width, side / cv.height);
        ctx.drawImage(cv, (side - cv.width * k) / 2, (side - cv.height * k) / 2, cv.width * k, cv.height * k);
        return;
      }
      strokeAll(ctx, S.strokes, side / 1000, Math.max(3, side / 110), 0, 0);
    }
    function point(e) {
      var rect = pad.getBoundingClientRect();
      var x = (e.clientX - rect.left) / rect.width * 1000, y = (e.clientY - rect.top) / rect.height * 1000;
      return [Math.round(Math.max(0, Math.min(1000, x)) * 10) / 10, Math.round(Math.max(0, Math.min(1000, y)) * 10) / 10];
    }
    function addPoint(p) {
      var s = S.current, n = s[0].length;
      if (n && Math.abs(s[0][n - 1] - p[0]) < 1.5 && Math.abs(s[1][n - 1] - p[1]) < 1.5) return;
      s[0].push(p[0]);
      s[1].push(p[1]);
    }
    function begin() {  // the first mark of a new drawing or photo: note whether it is blind and when it started
      if (!S.started) {
        S.started = Date.now();
        S.blind = !seen();
      }
    }
    function onDown(e) {
      if (S.busy || (e.button != null && e.button > 0)) return;
      e.preventDefault();
      if (S.upload) { S.upload = null; S.started = 0; }  // drawing on the pad replaces a photo
      pad.setPointerCapture(e.pointerId);
      S.current = [[], []];
      S.strokes.push(S.current);
      addPoint(point(e));
      begin();
      startTimer();
      redraw();
      updateButtons();
    }
    function onMove(e) {
      if (!S.current) return;
      e.preventDefault();
      var events = e.getCoalescedEvents ? e.getCoalescedEvents() : [e];
      (events.length ? events : [e]).forEach(function (ev) { addPoint(point(ev)); });
      redraw();
    }
    function onUp() {
      if (!S.current) return;
      S.current = null;
      updateButtons();
    }
    function totalPoints() { return S.strokes.reduce(function (n, s) { return n + s[0].length; }, 0); }
    function updateButtons() {
      var has = S.strokes.length > 0 || !!S.upload;
      q('undo').disabled = !S.strokes.length || S.busy;
      q('clear').disabled = !has || S.busy;
      q('go').disabled = (totalPoints() < 3 && !S.upload) || S.busy;
      q('placeholder').hidden = has;
      q('file').disabled = S.busy;
    }
    function clearPad() {
      S.strokes = [];
      S.current = null;
      S.upload = null;
      S.started = 0;
      stopTimer(true);
      redraw();
      updateButtons();
      status('');
    }

    function startTimer() {
      if (S.timerStart) return;
      S.timerStart = Date.now();
      var tm = q('timer');
      tm.hidden = false;
      tm.classList.remove('up');
      var tick = function () {
        var left = Math.max(0, TIME_S - Math.floor((Date.now() - S.timerStart) / 1000));
        tm.textContent = left ? left + ' s' : 'Time! Quick, Draw! players stopped here';
        if (!left) { tm.classList.add('up'); clearInterval(S.timerId); }
      };
      tick();
      S.timerId = setInterval(tick, 250);
    }
    function stopTimer(reset) {
      clearInterval(S.timerId);
      if (reset) {
        S.timerStart = 0;
        q('timer').hidden = true;
      }
    }
    function status(msg, kind) {
      var st = q('status');
      st.textContent = '';
      st.className = 'dw-status' + (kind === 'error' ? ' error' : '');
      if (kind === 'busy') st.appendChild(h('span', { class: 'spinner', 'aria-hidden': 'true' }));
      if (msg) st.appendChild(document.createTextNode((kind === 'busy' ? ' ' : '') + msg));
    }

    // --- a photo instead of the pad ---
    function takeFile(file) {
      if (S.busy || !file) return;
      status('Preparing your photo…', 'busy');
      prepareFile(file).then(function (u) {
        S.strokes = [];
        S.current = null;
        stopTimer(true);
        S.upload = u;
        S.started = 0;
        begin();
        redraw();
        updateButtons();
        status('Photo ready (' + u.canvas.width + ' × ' + u.canvas.height + ' px, location data removed). Press “See where it lands”.');
      }).catch(function (e) { status(e.message, 'error'); });
    }
    q('file').addEventListener('change', function (e) { takeFile(e.target.files && e.target.files[0]); e.target.value = ''; });
    var wrapEl = q('wrap'), drop = q('drop');
    ['dragenter', 'dragover'].forEach(function (type) {
      wrapEl.addEventListener(type, function (e) {
        if (!e.dataTransfer || [].indexOf.call(e.dataTransfer.types || [], 'Files') < 0) return;
        e.preventDefault();
        drop.hidden = false;
      });
    });
    ['dragleave', 'drop'].forEach(function (type) {
      wrapEl.addEventListener(type, function (e) {
        if (type === 'dragleave' && wrapEl.contains(e.relatedTarget)) return;
        drop.hidden = true;
      });
    });
    wrapEl.addEventListener('drop', function (e) {
      e.preventDefault();
      var f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      takeFile(f);
    });

    // --- donating (only when the server has it switched on) ---
    function setupDonations(d) {
      S.donations = d || { enabled: false };
      if (!S.donations.enabled) return;
      q('donate-box').hidden = false;
      q('donate-label').textContent = d.label;
      q('adult-label').textContent = d.adult;
      var dl = q('consent');
      dl.textContent = '';
      (d.points || []).forEach(function (p) { dl.appendChild(h('dt', { text: p[0] })); dl.appendChild(h('dd', { text: p[1] })); });
      q('irb').textContent = d.irb || '';
      q('privacy').textContent = d.summary;
      q('donate').addEventListener('change', function () {
        q('adult-row').hidden = !q('donate').checked;
        if (!q('donate').checked) q('adult').checked = false;
      });
      document.querySelectorAll('[data-privacy-line]').forEach(function (n) { n.textContent = d.summary; });
    }
    function donation() {
      if (!S.donations.enabled || !q('donate').checked) return { donate: false, adult: false };
      return { donate: true, adult: q('adult').checked };
    }

    // --- scoring ---
    function submit() {
      if (S.busy || (totalPoints() < 3 && !S.upload)) return;
      var don = donation();
      if (don.donate && !don.adult) {
        status('To donate your drawing, please confirm you are 18 or older, or untick the donation.', 'error');
        return;
      }
      S.busy = true;
      stopTimer(false);
      updateButtons();
      var c = concept();
      status('Measuring your ' + c.label + ' with DINOv2…', 'busy');
      var slow = setTimeout(function () { status('Waking up the model (only the first drawing takes a few seconds)…', 'busy'); }, 1800);
      var drawMs = S.started && !S.upload ? Date.now() - S.started : null;  // drawing time, on the pad only
      var sent = { key: S.key, strokes: S.strokes.map(function (s) { return [s[0].slice(), s[1].slice()]; }), upload: S.upload, blind: S.blind };
      var call;
      if (S.upload) {
        var qs = '?concept=' + encodeURIComponent(S.key) + '&blind=' + (S.blind ? 1 : 0) + (drawMs != null ? '&draw_ms=' + drawMs : '') +
          (don.donate ? '&donate=1&adult=' + (don.adult ? 1 : 0) : '');
        call = T.api('/api/draw/upload' + qs, { method: 'POST', body: S.upload.blob, headers: { 'Content-Type': 'image/jpeg' } });
      } else {
        call = T.api('/api/draw', { method: 'POST', json: { concept: S.key, strokes: sent.strokes, blind: S.blind, draw_ms: drawMs,
          donate: don.donate, adult: don.adult } });
      }
      call.then(function (r) {
        S.result = r;
        S.sent = sent;
        var msg = 'Done: ' + origSentence(r.originality, c) + '.';
        if (r.donation) msg += r.donation.status === 'saved' ? ' Thank you for donating your drawing to research.' : ' ' + r.donation.reason;
        status(msg);
        if (r.picture) return image(r.picture).then(function (im) { sent.picture = im; });
      }).then(function () {
        if (S.result) reveal();
      }).catch(function (e) { status(e.message || 'Something went wrong. Please try again.', 'error'); })
        .then(function () { clearTimeout(slow); S.busy = false; updateButtons(); });
    }

    function hideResults() {
      res.hidden = true;
      S.result = null;
      if (o.onReset) o.onReset();
    }

    // The reveal: Muse Image's doodles (animated in, unless the visitor prefers less motion), then the results.
    function reveal() {
      var r = S.result, c = concept();
      markSeen();
      res.hidden = false;
      var strip = q('strip');
      if (strip) {
        q('reveal-h').textContent = 'Here’s what Meta’s Muse Image drew when asked for ' + article(c.label) + ', ' + c.n_ai + ' times';
        strip.textContent = '';
        strip.classList.toggle('animate', !reduced());
        for (var i = 0; i < c.n_ai; i++) {
          var cl = cell(c.sprites.muse, i);
          cl.style.animationDelay = (i * 70) + 'ms';
          strip.appendChild(cl);
        }
        strip.setAttribute('aria-label', 'Muse Image’s ' + c.n_ai + ' doodles of ' + article(c.label));
        q('strip-cap').textContent = hook(c) + ' One prompt each time: “a quick simple doodle sketch of ' + article(c.label) + '”.';
      }
      q('fair').textContent = fair(c);
      showResults(r, c);
      if (o.onReveal) o.onReveal({ result: r, concept: c, instance: api });
      var target = o.scrollTo || res;
      setTimeout(function () { target.scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth', block: 'start' }); }, 60);
    }

    function showResults(r, c) {
      var p = r.originality;
      renderText();
      q('orig-num').textContent = Math.round(p) + '%';
      q('orig-text').textContent = 'Your ' + c.label + ' is ' + origSentence(p, c) + '.';
      var v = q('orig-verdict');
      v.textContent = '';
      v.appendChild(h('b', { text: verdict(p, c.label) + '. ' }));
      v.appendChild(document.createTextNode('Original here means far from the typical person’s ' + c.label + ', as Meta’s DINOv2 sees it.'));
      var oops = q('looks-like');
      if (r.own_rank && r.own_rank > 3 && r.looks_like && r.looks_like.length) {
        var names = r.looks_like.map(function (x) { return '“' + x.label + '”'; });
        oops.textContent = 'To DINOv2 this looks more like people’s drawings of ' + names.slice(0, -1).join(', ') + ' or ' +
          names[names.length - 1] + ' than of “' + c.label + '”, so part of that originality may be that it reads as something else.';
        oops.hidden = false;
      } else {
        oops.hidden = true;
      }
      q('photo-note').hidden = r.source !== 'upload';
      q('photo-note').textContent = 'Scored from a photo. Pen, paper and camera change how lines look, and DINOv2 sees that too: in our tests a ' +
        'photo of a drawing scored about 14 points more original, on average, than the same drawing made here.';
      q('orig-note').textContent = 'Each dot is one person’s drawing from Google’s Quick, Draw! game, placed by its distance from the average of the other people’s.';
      q('muse-text').textContent = museSentence(r, c);
      charts(c, r);
      q('muse-note').textContent = 'Muse’s own ' + plural(c.label) + ' sit ' + f2(min(c.ai_loo)) + '–' + f2(max(c.ai_loo)) +
        ' from its prototype; yours is ' + f2(r.d_ai) + ' away. Everyone’s drawings sit far from Muse’s, partly because DINOv2 also sees style: clean marker sketches against quick mouse or finger doodles.';
      var ex = c.map.explained || [];
      q('map-note').textContent = 'A flat map of DINOv2’s 768 numbers: its two main directions' +
        (ex.length ? ' (' + Math.round(100 * (ex[0] + ex[1])) + '% of the variation)' : '') +
        ', so closeness here is approximate. Hover or tap a dot to see the drawing.';
      renderNear(r, c);
      renderNumbers(r, c);
      drawCard().catch(function () {});
      updateShareLinks();
      socratesLink(r, c);
    }
    function charts(c, r) {
      stripChart(q('orig-chart'), {
        axis: 'distance from the typical person’s ' + c.label + ' →',
        rows: [{ name: c.n_human + ' people’s ' + plural(c.label), color: ORANGE, values: c.human_loo, sprite: c.sprites.people, who: 'person' }],
        you: r.d_human
      });
      stripChart(q('muse-chart'), {
        axis: 'distance from Muse Image’s prototype ' + c.label + ' →',
        rows: [
          { name: 'Muse Image’s ' + c.n_ai + ' ' + plural(c.label), color: BLUE, values: c.ai_loo, sprite: c.sprites.muse, who: 'muse' },
          { name: c.n_human + ' people’s ' + plural(c.label), color: ORANGE, values: c.human_to_ai, sprite: c.sprites.people, who: 'person' }
        ],
        you: r.d_ai
      });
      mapChart(q('map-chart'), q('map-legend'), c, r);
    }

    function renderNear(r, c) {
      var box = q('near');
      box.textContent = '';
      var mine = h('canvas', { width: 300, height: 300, 'aria-label': 'Your drawing' });
      drawMine(mine.getContext('2d'), 0, 0, 300, 18, 5);
      box.appendChild(h('figure', null, [mine, h('figcaption', null, [h('span', { class: 'k', style: { background: TEAL } }),
        r.source === 'upload' ? 'Yours, as DINOv2 saw it' : 'Yours'])]));
      box.appendChild(h('figure', null, [cell(c.sprites.muse, r.nearest_ai),
        h('figcaption', null, [h('span', { class: 'k', style: { background: BLUE } }), 'Closest of Muse’s ' + c.n_ai,
          h('span', { class: 'd', text: 'distance ' + f2(r.d_nearest_ai) })])]));
      box.appendChild(h('figure', null, [cell(c.sprites.people, r.nearest_human),
        h('figcaption', null, [h('span', { class: 'k', style: { background: ORANGE } }), 'Closest of ' + c.n_human + ' people’s',
          h('span', { class: 'd', text: 'distance ' + f2(r.d_nearest_human) })])]));
    }
    function renderNumbers(r, c) {
      var t = q('numbers');
      t.textContent = '';
      var range = function (a) { return f2(median(a)) + ' (' + f2(min(a)) + '–' + f2(max(a)) + ')'; };
      var rows = [
        ['Your distance from the typical person’s ' + c.label, f2(r.d_human)],
        ['People’s distances from it: median (range)', range(c.human_loo)],
        ['Your originality percentile', Math.round(r.originality) + '%'],
        ['Your distance from Muse Image’s prototype', f2(r.d_ai)],
        ['Muse’s own doodles: median (range)', range(c.ai_loo)],
        ['People’s drawings: median (range)', range(c.human_to_ai)],
        ['People’s drawings closer to Muse’s prototype than yours', Math.round(r.people_closer_to_muse) + '%']
      ];
      t.appendChild(h('thead', null, h('tr', null, [h('th', { text: 'Measure' }), h('th', { class: 'num', text: 'Cosine distance or share' })])));
      t.appendChild(h('tbody', null, rows.map(function (row) {
        return h('tr', null, [h('td', { text: row[0] }), h('td', { class: 'num', text: row[1] })]);
      })));
    }
    // Your drawing fitted into a square box: the strokes, or the cleaned-up photo DINOv2 saw.
    function drawMine(g, x, y, size, padding, width) {
      g.fillStyle = '#FFFFFF';
      g.fillRect(x, y, size, size);
      var sent = S.sent || {};
      if (sent.picture) {
        g.drawImage(sent.picture, x + padding / 2, y + padding / 2, size - padding, size - padding);
        return;
      }
      var strokes = sent.strokes || S.strokes, xsAll = [], ysAll = [];
      strokes.forEach(function (s) { xsAll = xsAll.concat(s[0]); ysAll = ysAll.concat(s[1]); });
      if (!xsAll.length) return;
      var bx0 = min(xsAll), bx1 = max(xsAll), by0 = min(ysAll), by1 = max(ysAll);
      var k = (size - 2 * padding) / Math.max(bx1 - bx0, by1 - by0, 1);
      var ox = x + padding + ((size - 2 * padding) - (bx1 - bx0) * k) / 2 - bx0 * k;
      var oy = y + padding + ((size - 2 * padding) - (by1 - by0) * k) / 2 - by0 * k;
      strokeAll(g, strokes, k, width, ox, oy);
    }

    // --- share ---
    function drawCard() {
      var c = concept(), r = S.result;
      if (!r) return Promise.resolve();
      return Promise.all([image(c.sprites.muse.src), fonts()]).then(function (got) {
        var sprite = got[0], cv = q('card'), g = cv.getContext('2d'), W = 1200;
        var sans = '"IBM Plex Sans", system-ui, sans-serif', mono = '"IBM Plex Mono", ui-monospace, monospace';
        g.fillStyle = PAPER;
        g.fillRect(0, 0, W, 675);
        g.save();
        roundRect(g, 48, 48, 560, 560, 24);
        g.fillStyle = '#FFFFFF';
        g.fill();
        g.clip();
        drawMine(g, 48, 48, 560, 48, 7);
        g.restore();
        roundRect(g, 48, 48, 560, 560, 24);
        g.lineWidth = 3;
        g.strokeStyle = INK;
        g.stroke();
        var x = 660, mw = 492;
        g.fillStyle = '#9A3412';
        g.font = '500 22px ' + mono;
        g.fillText(('Draw ' + article(c.label)).toUpperCase(), x, 92);
        g.fillStyle = INK;
        g.font = '700 132px ' + sans;
        g.fillText(Math.round(r.originality) + '%', x - 6, 222);
        g.font = '600 32px ' + sans;
        var y = wrap(g, cap1(origSentence(r.originality, c)) + '.', x, 272, mw, 40);
        g.fillStyle = INK2;
        g.font = '400 24px ' + sans;
        var other = r.own_rank > 3 && r.looks_like && r.looks_like[0];
        wrap(g, other ? verdict(r.originality, c.label) + ', though Meta’s DINOv2 thinks it looks more like “' + other.label + '”.'
          : verdict(r.originality, c.label) + ', says Meta’s DINOv2.', x, y + 6, mw, 32);
        var n = c.n_ai, cols = 8, rows = Math.ceil(n / cols), gap = 4, cs = Math.floor((mw - gap * (cols - 1)) / cols);
        var sy = 608 - rows * cs - (rows - 1) * gap;
        g.fillStyle = MUTED;
        g.font = '400 21px ' + sans;
        g.fillText(hook(c), x, sy - 14);
        var sp = c.sprites.muse;
        for (var i = 0; i < n; i++) {
          var cx = x + (i % cols) * (cs + gap), cy = sy + Math.floor(i / cols) * (cs + gap);
          g.fillStyle = '#FFFFFF';
          g.fillRect(cx, cy, cs, cs);
          g.drawImage(sprite, (i % sp.cols) * sp.cell, Math.floor(i / sp.cols) * sp.cell, sp.cell, sp.cell, cx, cy, cs, cs);
        }
        g.fillStyle = INK;
        g.font = '600 22px ' + sans;
        g.fillText(T.BRAND, 48, 650);
        var nameW = g.measureText(T.BRAND).width;
        g.fillStyle = MUTED;
        g.font = '400 18px ' + mono;
        g.fillText(shareUrl().replace(/^https?:\/\//, ''), 48 + nameW + 14, 650);
        g.font = '400 16px ' + sans;
        g.textAlign = 'right';
        g.fillText('Compared with 200 Quick, Draw! drawings (CC BY 4.0) · Embeddings: Meta DINOv2', W - 48, 650);
        g.textAlign = 'left';
      });
    }
    function shareText() {
      var c = concept(), r = S.result;
      return hook(c) + ' Mine is ' + origSentence(r.originality, c) + '. How original is yours?';
    }
    function updateShareLinks() {
      q('share-x').href = 'https://x.com/intent/tweet?text=' + encodeURIComponent(shareText()) + '&url=' +
        encodeURIComponent(shareUrl()) + '&hashtags=' + encodeURIComponent(HASHTAGS);
      q('share-native').hidden = !(navigator.canShare && window.File);
    }
    // "Discuss your chair with Socrates" (/socrates): only the numbers go in the link; the drawing stays here.
    function socratesLink(r, c) {
      var a = q('socrates-link');
      if (T.hasPage && !T.hasPage('/socrates')) { a.hidden = true; return; }
      var params = { draw: S.key, label: c.label, originality: r.originality, people_closer_to_muse: r.people_closer_to_muse,
        muse_closer: r.muse_closer, d_nearest_ai: r.d_nearest_ai, d_nearest_human: r.d_nearest_human, n_people: c.n_human,
        looks_like: (r.looks_like || []).map(function (x) { return x.key; }).join(',') };
      a.textContent = 'Discuss your ' + c.label + ' with Socrates';
      a.href = '/socrates?' + Object.keys(params).filter(function (k) { return params[k] != null && params[k] !== ''; })
        .map(function (k) { return k + '=' + encodeURIComponent(params[k]); }).join('&');
      a.hidden = false;
    }
    function cardBlob() { return new Promise(function (resolve) { q('card').toBlob(resolve, 'image/png'); }); }
    function fileName() {
      var brand = String(T.BRAND || 'draw').toLowerCase().replace(/\W+/g, '-');
      return 'draw-' + concept().label.replace(/\W+/g, '-') + '-' + brand + '.png';
    }
    q('download').addEventListener('click', function () {
      drawCard().then(cardBlob).then(function (blob) {
        if (!blob) return;
        var a = h('a', { href: URL.createObjectURL(blob), download: fileName() });
        document.body.appendChild(a);
        a.click();
        setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
      });
    });
    q('share-native').addEventListener('click', function () {
      drawCard().then(cardBlob).then(function (blob) {
        var file = new File([blob], fileName(), { type: 'image/png' });
        var data = { files: [file], text: shareText() + ' ' + shareUrl() };
        if (navigator.canShare && navigator.canShare(data)) return navigator.share(data);
        return navigator.share({ text: shareText(), url: shareUrl() });
      }).catch(function () {});
    });
    q('again').addEventListener('click', function () {
      clearPad();
      hideResults();
      q('wrap').scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth', block: 'center' });
    });

    // --- start ---
    pad.addEventListener('pointerdown', onDown);
    pad.addEventListener('pointermove', onMove);
    pad.addEventListener('pointerup', onUp);
    pad.addEventListener('pointercancel', onUp);
    q('undo').addEventListener('click', function () { S.strokes.pop(); redraw(); updateButtons(); });
    q('clear').addEventListener('click', clearPad);
    q('go').addEventListener('click', submit);
    var resizeTimer = 0, lastWidth = window.innerWidth;
    window.addEventListener('resize', function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        // Phones resize the window as the address bar slides on scroll; only a new width needs a redraw.
        if (window.innerWidth === lastWidth) return;
        lastWidth = window.innerWidth;
        sizePad();
        if (S.result && !res.hidden) charts(concept(), S.result);
      }, 150);
    });
    sizePad();
    updateButtons();
    renderText();
    var ready = Promise.all([T.api('/api/draw/concepts'), T.api('/api/draw/status').catch(function () { return {}; })])
      .then(function (got) {
        S.data = got[0];
        setupDonations((got[1] || {}).donations);
        var want = o.deepLink ? (new URL(location.href).searchParams.get('thing') || '').toLowerCase() : '';
        var match = S.data.concepts.filter(function (c) { return c.key === want || c.label === want; })[0];
        S.key = match ? match.key : (S.data.concepts.filter(function (c) { return c.key === S.key; })[0] || S.data.concepts[0]).key;
        if (o.picker) renderChips();
        renderText();
        image(concept().sprites.muse.src);
      }).catch(function (e) {
        status('Couldn’t load the drawing game: ' + e.message, 'error');
      });

    var api = {
      state: S, submit: submit, ready: ready,
      markSeen: function () { markSeen(); if (!S.started) S.blind = false; },
      concept: function () { return S.data ? concept() : null; },
      takeFile: takeFile, clear: clearPad
    };
    return api;
  }

  window.TOTDraw = { mount: mount, seen: seen, markSeen: markSeen };
})();
