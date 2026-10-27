/* Draw a chair (/draw): a drawing pad, the scores from /api/draw, two strip charts, a map, the closest
   drawings and a share card. Reference data comes from /api/draw/concepts; drawings are sent once to be
   scored and are never stored. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;

  // The address shared on X and printed on the card. A placeholder until the live demo has a URL: change
  // this line. When the page is served from a real host (not localhost), that host's /draw is used instead.
  var SITE_URL = 'https://tippa-lingua.example/draw';
  var SITE_NAME = T.BRAND;  // the product name, from metalesionlab/brand.py
  var HASHTAGS = 'Muse,MetaAI,Hackathon';

  var BLUE = '#1D4ED8', ORANGE = '#C2410C', TEAL = '#0D9488', INK = '#111827', INK2 = '#374151', MUTED = '#4B5563',
    GRID = '#E5E7EB', PAPER = '#F7F6F1';
  var NS = 'http://www.w3.org/2000/svg';
  var TIME_S = 20;  // Quick, Draw! players had 20 seconds
  var S = { data: null, key: 'chair', strokes: [], current: null, result: null, sent: null, busy: false,
    timerStart: 0, timerId: 0, images: {} };

  function $(id) { return document.getElementById(id); }
  function svg(tag, attrs, kids) {
    var el = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) el.setAttribute(k, attrs[k]); });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c != null) el.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return el;
  }
  function f2(x) { return Number(x).toFixed(2); }
  function median(a) { var b = a.slice().sort(function (x, y) { return x - y; }); var m = b.length >> 1; return b.length % 2 ? b[m] : (b[m - 1] + b[m]) / 2; }
  function min(a) { return Math.min.apply(null, a); }
  function max(a) { return Math.max.apply(null, a); }
  function plural(label) { return label + 's'; }
  function article(label) { return (/^[aeiou]/i.test(label) ? 'an ' : 'a ') + label; }
  function concept() { return S.data.concepts.filter(function (c) { return c.key === S.key; })[0]; }
  function shareUrl() {
    var local = /^(localhost|127\.|0\.0\.0\.0|\[::1\])/.test(location.hostname) || location.protocol === 'file:';
    return local ? SITE_URL : location.origin + '/draw';
  }
  function reduced() { return window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches; }

  // ---------- copy ----------

  function hook(c) {
    var idx = c.stats.index, pl = plural(c.label);
    if (idx < 0.45) return 'Muse Image drew the same ' + c.label + ' ' + c.n_ai + ' times.';
    if (idx < 0.9) return 'Muse Image drew ' + c.n_ai + ' ' + pl + ', ' + Math.round(100 * (1 - idx)) + '% less varied than people’s.';
    return 'Muse Image drew ' + c.n_ai + ' ' + pl + ', about as varied as people’s.';
  }
  function fmt1(r) { return (Math.round(r * 10) / 10).toFixed(1); }
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
  function image(src) {
    if (!S.images[src]) {
      S.images[src] = new Promise(function (resolve, reject) {
        var im = new Image();
        im.onload = function () { resolve(im); };
        im.onerror = reject;
        im.src = src;
      });
    }
    return S.images[src];
  }

  // ---------- hero ----------

  function renderHero() {
    var c = concept();
    document.querySelectorAll('[data-label]').forEach(function (el) { el.textContent = c.label; });
    document.querySelectorAll('[data-article]').forEach(function (el) { el.textContent = article(c.label); });
    document.title = 'Draw ' + article(c.label) + ' · ' + T.BRAND;
    $('hook').textContent = hook(c) + ' How original is yours?';
    var strip = $('muse-strip');
    strip.textContent = '';
    for (var i = 0; i < c.n_ai; i++) strip.appendChild(cell(c.sprites.muse, i));
    strip.setAttribute('aria-label', 'Muse Image’s ' + c.n_ai + ' doodles of ' + article(c.label));
    $('muse-cap').textContent = 'Muse Image’s ' + c.n_ai + ' doodles of “' + article(c.label) + '”, one prompt each time.';
    $('fair').textContent = fair(c);
    document.querySelectorAll('#chips button').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.key === S.key)); });
    image(c.sprites.muse.src);
  }

  function renderChips() {
    var box = $('chips');
    S.data.concepts.forEach(function (c) {
      box.appendChild(h('button', { type: 'button', 'data-key': c.key, 'aria-pressed': 'false', text: c.label,
        onclick: function () { choose(c.key); } }));
    });
  }

  function choose(key) {
    if (key === S.key) return;
    S.key = key;
    var url = new URL(location.href);
    url.searchParams.set('thing', concept().label);
    history.replaceState(null, '', url);
    clearPad();
    hideResults();
    renderHero();
  }

  // ---------- drawing pad ----------

  var pad, ctx, dpr = 1, side = 0;

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
    strokeAll(ctx, S.strokes, side / 1000, Math.max(3, side / 110), 0, 0);
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
  function onDown(e) {
    if (S.busy || (e.button != null && e.button > 0)) return;
    e.preventDefault();
    pad.setPointerCapture(e.pointerId);
    S.current = [[], []];
    S.strokes.push(S.current);
    addPoint(point(e));
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
    var has = S.strokes.length > 0;
    $('undo').disabled = !has || S.busy;
    $('clear').disabled = !has || S.busy;
    $('go').disabled = totalPoints() < 3 || S.busy;
    $('placeholder').hidden = has;
  }
  function clearPad() {
    S.strokes = [];
    S.current = null;
    stopTimer(true);
    redraw();
    updateButtons();
    status('');
  }

  function startTimer() {
    if (S.timerStart) return;
    S.timerStart = Date.now();
    var el = $('timer');
    el.hidden = false;
    el.classList.remove('up');
    var tick = function () {
      var left = Math.max(0, TIME_S - Math.floor((Date.now() - S.timerStart) / 1000));
      el.textContent = left ? left + ' s' : 'Time! Quick, Draw! players stopped here';
      if (!left) { el.classList.add('up'); clearInterval(S.timerId); }
    };
    tick();
    S.timerId = setInterval(tick, 250);
  }
  function stopTimer(reset) {
    clearInterval(S.timerId);
    if (reset) {
      S.timerStart = 0;
      $('timer').hidden = true;
    }
  }

  function status(msg, kind) {
    var el = $('status');
    el.textContent = '';
    el.className = 'dw-status' + (kind === 'error' ? ' error' : '');
    if (kind === 'busy') el.appendChild(h('span', { class: 'spinner', 'aria-hidden': 'true' }));
    if (msg) el.appendChild(document.createTextNode((kind === 'busy' ? ' ' : '') + msg));
  }

  // ---------- scoring ----------

  function submit() {
    if (S.busy || totalPoints() < 3) return;
    S.busy = true;
    stopTimer(false);
    updateButtons();
    status('Measuring your ' + concept().label + ' with DINOv2…', 'busy');
    var slow = setTimeout(function () { status('Waking up the model (only the first drawing takes a few seconds)…', 'busy'); }, 1800);
    var sent = { key: S.key, strokes: S.strokes.map(function (s) { return [s[0].slice(), s[1].slice()]; }) };
    T.api('/api/draw', { method: 'POST', json: { concept: S.key, strokes: sent.strokes } })
      .then(function (r) {
        S.result = r;
        S.sent = sent;
        var c = concept();
        status('Done: ' + origSentence(r.originality, c) + '.');
        showResults(r, c);
      })
      .catch(function (e) { status(e.message || 'Something went wrong. Please try again.', 'error'); })
      .then(function () { clearTimeout(slow); S.busy = false; updateButtons(); });
  }

  function hideResults() {
    $('results').hidden = true;
    S.result = null;
  }

  function showResults(r, c) {
    var p = r.originality;
    $('results').hidden = false;
    $('orig-num').textContent = Math.round(p) + '%';
    $('orig-text').textContent = 'Your ' + c.label + ' is ' + origSentence(p, c) + '.';
    $('orig-verdict').textContent = '';
    $('orig-verdict').appendChild(h('b', { text: verdict(p, c.label) + '. ' }));
    $('orig-verdict').appendChild(document.createTextNode('Original here means far from the typical person’s ' + c.label + ', as Meta’s DINOv2 sees it.'));
    var oops = $('looks-like');
    if (r.own_rank && r.own_rank > 3 && r.looks_like && r.looks_like.length) {
      var names = r.looks_like.map(function (x) { return '“' + x.label + '”'; });
      oops.textContent = 'To DINOv2 this looks more like people’s drawings of ' + names.slice(0, -1).join(', ') + ' or ' +
        names[names.length - 1] + ' than of “' + c.label + '”, so part of that originality may be that it reads as something else.';
      oops.hidden = false;
    } else {
      oops.hidden = true;
    }
    $('orig-note').textContent = 'Each dot is one person’s drawing from Google’s Quick, Draw! game, placed by its distance from the average of the other people’s.';
    $('muse-text').textContent = museSentence(r, c);
    showResultsCharts(c, r);
    $('muse-note').textContent = 'Muse’s own ' + plural(c.label) + ' sit ' + f2(min(c.ai_loo)) + '–' + f2(max(c.ai_loo)) +
      ' from its prototype; yours is ' + f2(r.d_ai) + ' away. Everyone’s drawings sit far from Muse’s, partly because DINOv2 also sees style: clean marker sketches against quick mouse or finger doodles.';

    var ex = c.map.explained || [];
    $('map-note').textContent = 'A flat map of DINOv2’s 768 numbers: its two main directions' +
      (ex.length ? ' (' + Math.round(100 * (ex[0] + ex[1])) + '% of the variation)' : '') +
      ', so closeness here is approximate. Hover or tap a dot to see the drawing.';
    renderNear(r, c);
    renderNumbers(r, c);
    drawCard().catch(function () {});
    updateShareLinks();
    socratesLink(r, c);
    var res = $('results');
    setTimeout(function () { res.scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth', block: 'start' }); }, 60);
  }

  // ---------- charts ----------

  var tip = null;
  function tooltip(container, html, x, y) {
    if (!tip) tip = h('div', { class: 'dw-tip', role: 'presentation' });
    if (tip.parentNode !== container) container.appendChild(tip);
    tip.textContent = '';
    html.forEach(function (n) { tip.appendChild(n); });
    tip.hidden = false;
    var w = 132, cw = container.clientWidth;
    var left = Math.min(Math.max(0, x - w / 2), cw - w);
    var below = y < 180;  // near the top of the chart the card's heading is above: open downward instead
    tip.style.left = left + 'px';
    tip.style.top = (below ? y + 14 : y - 12) + 'px';
    tip.style.transform = below ? 'none' : 'translateY(-100%)';
  }
  function hideTip() { if (tip) tip.hidden = true; }
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
      if (!hit.best) { hideTip(); ring.setAttribute('visibility', 'hidden'); return; }
      ring.setAttribute('cx', hit.best.x);
      ring.setAttribute('cy', hit.best.y);
      ring.setAttribute('visibility', 'visible');
      tooltip(container, tipFor(hit.best), hit.best.x / hit.k, hit.best.y / hit.k);
    }
    svgEl.addEventListener('pointermove', move);
    svgEl.addEventListener('pointerdown', move);
    svgEl.addEventListener('pointerleave', function () { hideTip(); ring.setAttribute('visibility', 'hidden'); });
  }

  function niceMax(v) { return Math.min(1, Math.ceil(v * 1.08 * 10) / 10); }

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

  function mapChart(el, c, r) {
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
    var lg = $('map-legend');
    lg.textContent = '';
    [[BLUE, 'Muse Image (' + c.n_ai + ')'], [ORANGE, 'People (' + c.n_human + ')'], [TEAL, 'You']].forEach(function (e, i) {
      lg.appendChild(h('span', null, [h('i', { class: i === 2 ? 'you' : null, style: { background: e[0] } }), e[1]]));
    });
  }

  // ---------- closest drawings and numbers ----------

  function renderNear(r, c) {
    var box = $('near');
    box.textContent = '';
    var mine = h('canvas', { width: 300, height: 300, 'aria-label': 'Your drawing' });
    drawMine(mine.getContext('2d'), 0, 0, 300, 18, 5);
    box.appendChild(h('figure', null, [mine, h('figcaption', null, [h('span', { class: 'k', style: { background: TEAL } }), 'Yours'])]));
    box.appendChild(h('figure', null, [cell(c.sprites.muse, r.nearest_ai),
      h('figcaption', null, [h('span', { class: 'k', style: { background: BLUE } }), 'Closest of Muse’s ' + c.n_ai,
        h('span', { class: 'd', text: 'distance ' + f2(r.d_nearest_ai) })])]));
    box.appendChild(h('figure', null, [cell(c.sprites.people, r.nearest_human),
      h('figcaption', null, [h('span', { class: 'k', style: { background: ORANGE } }), 'Closest of ' + c.n_human + ' people’s',
        h('span', { class: 'd', text: 'distance ' + f2(r.d_nearest_human) })])]));
  }

  function renderNumbers(r, c) {
    var t = $('numbers');
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

  // Your strokes, fitted into a square box (used by the closest-drawings row and the share card).
  function drawMine(g, x, y, size, pad, width) {
    var strokes = (S.sent && S.sent.strokes) || S.strokes;
    var xsAll = [], ysAll = [];
    strokes.forEach(function (s) { xsAll = xsAll.concat(s[0]); ysAll = ysAll.concat(s[1]); });
    g.fillStyle = '#FFFFFF';
    g.fillRect(x, y, size, size);
    if (!xsAll.length) return;
    var bx0 = min(xsAll), bx1 = max(xsAll), by0 = min(ysAll), by1 = max(ysAll);
    var ext = Math.max(bx1 - bx0, by1 - by0, 1);
    var k = (size - 2 * pad) / ext;
    var ox = x + pad + ((size - 2 * pad) - (bx1 - bx0) * k) / 2 - bx0 * k;
    var oy = y + pad + ((size - 2 * pad) - (by1 - by0) * k) / 2 - by0 * k;
    strokeAll(g, strokes, k, width, ox, oy);
  }

  // ---------- share card ----------

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
  function drawCard() {
    var c = concept(), r = S.result;
    if (!r) return Promise.resolve();
    return Promise.all([image(c.sprites.muse.src), fonts()]).then(function (got) {
      var sprite = got[0], cv = $('card'), g = cv.getContext('2d'), W = 1200, H = 675;
      var sans = '"IBM Plex Sans", system-ui, sans-serif', mono = '"IBM Plex Mono", ui-monospace, monospace';
      g.fillStyle = PAPER;
      g.fillRect(0, 0, W, H);
      // your drawing
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
      // the score
      var x = 660, mw = 492;
      g.fillStyle = '#9A3412';
      g.font = '500 22px ' + mono;
      g.fillText(('Draw ' + article(c.label)).toUpperCase(), x, 92);
      g.fillStyle = INK;
      g.font = '700 132px ' + sans;
      g.fillText(Math.round(r.originality) + '%', x - 6, 222);
      g.font = '600 32px ' + sans;
      var y = wrap(g, origSentence(r.originality, c).replace(/^./, function (ch) { return ch.toUpperCase(); }) + '.', x, 272, mw, 40);
      g.fillStyle = INK2;
      g.font = '400 24px ' + sans;
      var other = r.own_rank > 3 && r.looks_like && r.looks_like[0];
      wrap(g, other ? verdict(r.originality, c.label) + ', though Meta’s DINOv2 thinks it looks more like “' + other.label + '”.'
        : verdict(r.originality, c.label) + ', says Meta’s DINOv2.', x, y + 6, mw, 32);
      // Muse's doodles
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
      // footer
      g.fillStyle = INK;
      g.font = '600 22px ' + sans;
      g.fillText(SITE_NAME, 48, 650);
      var nameW = g.measureText(SITE_NAME).width;
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
    var url = 'https://x.com/intent/tweet?text=' + encodeURIComponent(shareText()) + '&url=' + encodeURIComponent(shareUrl()) +
      '&hashtags=' + encodeURIComponent(HASHTAGS);
    $('share-x').href = url;
    var canFiles = navigator.canShare && window.File;
    $('share-native').hidden = !canFiles;
  }
  // "Discuss your chair with Socrates" (/socrates): only the numbers go in the link; the drawing stays here.
  function socratesLink(r, c) {
    var a = $('socrates-link');
    if (!a) {
      a = h('a', { class: 'btn', id: 'socrates-link' });
      $('again').parentNode.insertBefore(a, $('again'));
    }
    var q = { draw: S.key, label: c.label, originality: r.originality, people_closer_to_muse: r.people_closer_to_muse,
      muse_closer: r.muse_closer, d_nearest_ai: r.d_nearest_ai, d_nearest_human: r.d_nearest_human, n_people: c.n_human,
      looks_like: (r.looks_like || []).map(function (x) { return x.key; }).join(',') };
    a.textContent = 'Discuss your ' + c.label + ' with Socrates';
    a.href = '/socrates?' + Object.keys(q).filter(function (k) { return q[k] != null && q[k] !== ''; })
      .map(function (k) { return k + '=' + encodeURIComponent(q[k]); }).join('&');
  }
  function cardBlob() {
    return new Promise(function (resolve) { $('card').toBlob(resolve, 'image/png'); });
  }
  function fileName() { return 'draw-' + (concept().label.replace(/\W+/g, '-')) + '-tippa-lingua.png'; }
  function download() {
    drawCard().then(cardBlob).then(function (blob) {
      if (!blob) return;
      var a = h('a', { href: URL.createObjectURL(blob), download: fileName() });
      document.body.appendChild(a);
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
    });
  }
  function nativeShare() {
    drawCard().then(cardBlob).then(function (blob) {
      var file = new File([blob], fileName(), { type: 'image/png' });
      var data = { files: [file], text: shareText() + ' ' + shareUrl() };
      if (navigator.canShare && navigator.canShare(data)) return navigator.share(data);
      return navigator.share({ text: shareText(), url: shareUrl() });
    }).catch(function () {});
  }

  // ---------- start ----------

  function init() {
    pad = $('pad');
    ctx = pad.getContext('2d');
    pad.addEventListener('pointerdown', onDown);
    pad.addEventListener('pointermove', onMove);
    pad.addEventListener('pointerup', onUp);
    pad.addEventListener('pointercancel', onUp);
    $('undo').addEventListener('click', function () { S.strokes.pop(); redraw(); updateButtons(); });
    $('clear').addEventListener('click', clearPad);
    $('go').addEventListener('click', submit);
    $('download').addEventListener('click', download);
    $('share-native').addEventListener('click', nativeShare);
    $('again').addEventListener('click', function () {
      clearPad();
      hideResults();
      $('canvas-wrap').scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth', block: 'center' });
    });
    var resizeTimer = 0, lastWidth = window.innerWidth;
    window.addEventListener('resize', function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        // Phones resize the window as the address bar slides on scroll; only a new width needs a redraw.
        if (window.innerWidth === lastWidth) return;
        lastWidth = window.innerWidth;
        sizePad();
        if (S.result) {
          var c = concept();
          showResultsCharts(c, S.result);
        }
      }, 150);
    });
    sizePad();
    updateButtons();
    T.api('/api/draw/concepts').then(function (data) {
      S.data = data;
      var want = (new URL(location.href).searchParams.get('thing') || '').toLowerCase();
      var match = data.concepts.filter(function (c) { return c.key === want || c.label === want; })[0];
      S.key = match ? match.key : (data.concepts[0] || {}).key;
      renderChips();
      renderHero();
    }).catch(function (e) {
      var el = $('load-error');
      el.textContent = 'Couldn’t load the drawing game: ' + e.message;
      el.hidden = false;
    });
  }
  function showResultsCharts(c, r) {
    stripChart($('orig-chart'), {
      axis: 'distance from the typical person’s ' + c.label + ' →',
      rows: [{ name: c.n_human + ' people’s ' + plural(c.label), color: ORANGE, values: c.human_loo, sprite: c.sprites.people, who: 'person' }],
      you: r.d_human
    });
    stripChart($('muse-chart'), {
      axis: 'distance from Muse Image’s prototype ' + c.label + ' →',
      rows: [
        { name: 'Muse Image’s ' + c.n_ai + ' ' + plural(c.label), color: BLUE, values: c.ai_loo, sprite: c.sprites.muse, who: 'muse' },
        { name: c.n_human + ' people’s ' + plural(c.label), color: ORANGE, values: c.human_to_ai, sprite: c.sprites.people, who: 'person' }
      ],
      you: r.d_ai
    });
    mapChart($('map-chart'), c, r);
  }

  window.TOT_DRAW = { state: S, submit: submit };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
