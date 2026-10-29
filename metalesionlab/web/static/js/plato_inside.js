/* Inside the model: a layer slider over Muse Glimmer 30B's 52 layers. For one thing at a time, a precomputed map of
   Muse Image's doodles and people's doodles, each set's spread by layer, the collapse layer and the word lens.
   Data: /api/plato/inside (statistics and map positions only). No Meta API calls; nothing is stored. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var NS = 'http://www.w3.org/2000/svg';
  var C = { muse: 'var(--blue)', people: 'var(--orange)', ink: 'var(--ink)', ink2: 'var(--ink-2)', muted: 'var(--muted)', grid: 'var(--line)',
            axis: 'var(--line-3)', surface: 'var(--chart-halo)', paper: 'var(--paper-mat)' };
  var SPRITES = '/static/img/plato_inside/';
  var GRID = 1000;
  var N_LAYERS = 52;
  var MQ = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  var S = { data: null, c: null, layer: 1, view: 'drawings', shown: null, els: [], geom: null, anim: 0, timer: 0,
            hot: -1, touched: false, spriteOk: {} };

  function $(id) { return document.getElementById(id); }
  function reduced() { return !!(MQ && MQ.matches); }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function f2(x) { return x == null ? '–' : x.toFixed(2); }
  function pct(x) { return Math.round(x * 100) + '%'; }
  function s(tag, attrs, kids) {
    var e = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) e.setAttribute(k, attrs[k]); });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c != null) e.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return e;
  }
  function cap(t) { return t.charAt(0).toUpperCase() + t.slice(1); }
  var MASS = { scissors: 1 };
  function aThing(t) { return MASS[t] ? t : (/^[aeiou]/.test(t) ? 'an ' : 'a ') + t; }
  function nameLayer(c) { return c.name_layer.muse == null ? null : Math.ceil(c.name_layer.muse); }
  function layerWord(x) { return x == null ? '–' : (x % 1 ? x.toFixed(1) : String(x)); }

  // --- per-layer text -----------------------------------------------------------------------------
  function phase(c, L) {
    var cl = c.collapse_layer, nl = nameLayer(c);
    if (nl && L >= nl) return { key: 'named', label: 'The name can be read' };
    if (cl && L >= cl) return { key: 'collapsed', label: 'Muse Image’s drawings in one place' };
    if (L <= 12) return { key: 'seeing', label: 'Seeing the drawing' };
    if (L <= 30) return { key: 'middle', label: 'In the middle' };
    return { key: 'settling', label: 'Settling on a name' };
  }

  function lensCounts(c, L) {
    var n = c.n.muse, a = 0, b = 0;
    c.pictures.forEach(function (p, i) { if (p.lens && p.lens <= L) { if (i < n) a++; else b++; } });
    return [a, b];
  }

  function phaseText(c, L) {
    var nb = S.data.summary.same_thing_neighbour, t = c.label, ph = phase(c, L), nl = nameLayer(c);
    var nm = pct(nb.muse[L - 1]), np = pct(nb.people[L - 1]);
    if (ph.key === 'seeing') {
      return 'Glimmer has just taken in the picture. Drawings of the same thing still sit near each other: at this stage, for ' + nm +
        ' of Muse Image’s drawings and ' + np + ' of people’s, the closest drawing is another drawing of the same thing (all 35 things).';
    }
    if (ph.key === 'middle') {
      return 'At the spot where Glimmer will write its answer, it holds little here about which thing a drawing shows: only ' + np +
        ' of people’s drawings (and ' + nm + ' of Muse Image’s) sit closest to a drawing of the same thing. Both sets are spread out.';
    }
    if (ph.key === 'settling') {
      return 'Which thing it is comes back (the closest drawing shows the same thing for ' + nm + ' of Muse Image’s drawings and ' + np +
        ' of people’s). ' + (c.collapse_layer ? 'Glimmer files Muse Image’s drawings of ' + aThing(t) + ' in one place from stage ' + c.collapse_layer + '.'
          : 'Glimmer never files Muse Image’s drawings of ' + aThing(t) + ' in one place.');
    }
    if (ph.key === 'collapsed') {
      return 'From here to the last stage, Muse Image’s drawings of ' + aThing(t) + ' stay less than half as far apart as people’s: Glimmer files them in one place. ' +
        'The word lens can’t read “' + t + '” yet; that comes at stage ' + nl + '.';
    }
    var k = lensCounts(c, L);
    var lead = 'The word lens (a tool that reads which word Glimmer is heading towards) can now read “' + t + '” for ' + k[0] + ' of ' + c.n.muse +
      ' of Muse Image’s drawings and ' + k[1] + ' of ' + c.n.people + ' of people’s. ';
    if (!c.collapse_layer) {
      return lead + 'But Muse Image’s drawings never stay under half of people’s spread: ' + t + ' is the one thing of 35 that Glimmer never files in one place.';
    }
    return lead + 'Muse Image’s drawings sit almost on one point; people’s are still spread out.';
  }

  // --- the map ---------------------------------------------------------------------------------------
  function geometry() {
    var W = $('map').clientWidth || 320;
    var pic = S.view === 'drawings';
    var size = pic ? Math.round(clamp(W * 0.072, 26, 46)) : (W < 420 ? 11 : 13);
    var pad = pic ? size / 2 + 8 : 16;
    return { W: W, size: size, pad: pad, px: function (v) { return pad + v / GRID * (W - 2 * pad); } };
  }

  function buildPoints() {
    var box = $('points'), c = S.c, n = c.n.muse, N = c.pictures.length;
    S.geom = geometry();
    box.innerHTML = '';
    S.els = [];
    var pic = S.view === 'drawings', g = S.geom;
    for (var i = 0; i < N; i++) {
      var src = i < n ? 'muse' : 'people';
      var el = h('span', { class: 'pt ' + src + (pic ? ' pic' : ' dot') });
      el.style.width = el.style.height = g.size + 'px';
      if (pic) {
        el.style.backgroundImage = 'url("' + SPRITES + c.sprite + '")';
        el.style.backgroundSize = (N * g.size) + 'px ' + g.size + 'px';
        el.style.backgroundPosition = (-i * g.size) + 'px 0';
      }
      box.appendChild(el);
      S.els.push(el);
    }
    S.hot = -1;
    $('map').classList.toggle('as-dots', !pic);
  }

  function place(coords) {
    var g = S.geom, half = g.size / 2, n = S.c.n.muse;
    for (var i = 0; i < S.els.length; i++) {
      var x = g.px(coords[2 * i]) - half, y = g.px(coords[2 * i + 1]) - half;
      var extra = (S.view === 'dots' && i >= n ? ' rotate(45deg)' : '') + (i === S.hot ? ' scale(1.45)' : '');
      S.els[i].style.transform = 'translate(' + x.toFixed(1) + 'px,' + y.toFixed(1) + 'px)' + extra;
    }
    drawHalos(coords);
  }

  function groupStats(coords, from, to) {
    var cx = 0, cy = 0, k = to - from, r2 = 0, i;
    for (i = from; i < to; i++) { cx += coords[2 * i]; cy += coords[2 * i + 1]; }
    cx /= k; cy /= k;
    for (i = from; i < to; i++) { var dx = coords[2 * i] - cx, dy = coords[2 * i + 1] - cy; r2 += dx * dx + dy * dy; }
    return { x: cx, y: cy, r: Math.sqrt(r2 / k) };
  }

  function drawHalos(coords) {
    var svg = $('halos'), g = S.geom, n = S.c.n.muse, N = S.c.pictures.length, scale = (g.W - 2 * g.pad) / GRID;
    svg.setAttribute('viewBox', '0 0 ' + g.W + ' ' + g.W);
    if (!svg.firstChild) {
      ['people', 'muse'].forEach(function (src) {
        svg.appendChild(s('circle', { class: 'halo ' + src, fill: C[src], 'fill-opacity': 0.07, stroke: C[src], 'stroke-opacity': 0.45, 'stroke-width': 1.5 }));
        svg.appendChild(s('circle', { class: 'core ' + src, r: 3, fill: C[src] }));
      });
    }
    var groups = { muse: groupStats(coords, 0, n), people: groupStats(coords, n, N) };
    ['muse', 'people'].forEach(function (src) {
      var st = groups[src];
      var circ = svg.querySelector('circle.halo.' + src), core = svg.querySelector('circle.core.' + src);
      var cx = g.px(st.x), cy = g.px(st.y);
      circ.setAttribute('cx', cx.toFixed(1)); circ.setAttribute('cy', cy.toFixed(1));
      circ.setAttribute('r', Math.max(4, st.r * scale).toFixed(1));
      core.setAttribute('cx', cx.toFixed(1)); core.setAttribute('cy', cy.toFixed(1));
    });
  }

  function tweenTo(target, dur) {
    cancelAnimationFrame(S.anim);
    if (!S.shown || reduced() || !dur) { S.shown = target.slice(); place(S.shown); return; }
    var from = S.shown.slice(), t0 = performance.now();
    function step(now) {
      var t = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - t, 3);
      for (var i = 0; i < from.length; i++) S.shown[i] = from[i] + (target[i] - from[i]) * e;
      place(S.shown);
      if (t < 1) S.anim = requestAnimationFrame(step);
    }
    S.anim = requestAnimationFrame(step);
  }

  function mapLabel(c, L) {
    var m = c.spread.muse[L - 1], p = c.spread.people[L - 1];
    return 'Map of ' + c.pictures.length + ' drawings of ' + aThing(c.label) + ' inside Muse Glimmer at stage ' + L + ' of 52: Muse Image’s ' +
      c.n.muse + ' drawings have a spread of ' + f2(m) + ', people’s ' + c.n.people + ' have ' + f2(p) + ' (0 would mean all in one spot)' +
      (m < 0.5 * p ? '. Muse Image’s sit in a tight cluster; people’s are spread out.' : '. Both sets are spread out.');
  }

  // --- tooltip on the map ------------------------------------------------------------------------------
  function nearest(evt) {
    var r = $('map').getBoundingClientRect(), x = evt.clientX - r.left, y = evt.clientY - r.top, g = S.geom;
    var best = -1, bd = Infinity, n = S.c.n.muse;
    for (var i = 0; i < S.els.length; i++) {
      var dx = g.px(S.shown[2 * i]) - x, dy = g.px(S.shown[2 * i + 1]) - y, d = dx * dx + dy * dy;
      // Muse's doodles sit on top of the pile, so they win ties
      if (d < bd - (i < n ? 4 : 0)) { bd = d; best = i; }
    }
    var reach = Math.max(14, g.size / 2 + 6);
    return bd <= reach * reach ? { i: best, x: x, y: y } : null;
  }

  function showTip(hit) {
    var tip = $('map-tip'), c = S.c, n = c.n.muse, i = hit.i, p = c.pictures[i], muse = i < n;
    tip.innerHTML = '';
    var thumb = h('span', { class: 'tip-thumb' });
    thumb.style.backgroundImage = 'url("' + SPRITES + c.sprite + '")';
    thumb.style.backgroundSize = (c.pictures.length * 64) + 'px 64px';
    thumb.style.backgroundPosition = (-i * 64) + 'px 0';
    if (!S.spriteOk[c.sprite]) thumb.hidden = true;
    var said = p.said || '(no answer)';
    tip.appendChild(thumb);
    tip.appendChild(h('div', { class: 'tip-body' }, [
      h('b', { text: (muse ? 'Muse Image’s drawing ' + (i + 1) : 'A person’s drawing ' + (i - n + 1)) }),
      h('span', { text: 'Glimmer said “' + said + '”' + (p.ok ? '' : ' (not counted as ' + c.label + ')') }),
      h('span', { class: 'tip-lens', text: p.lens ? 'Word lens reads the name from stage ' + p.lens : 'Word lens never settles on the name' })
    ]));
    tip.hidden = false;
    var W = S.geom.W, left = hit.x + 14, top = hit.y + 14;
    if (left + tip.offsetWidth > W) left = Math.max(0, hit.x - tip.offsetWidth - 14);
    if (top + tip.offsetHeight > W) top = Math.max(0, hit.y - tip.offsetHeight - 14);
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
  }

  function onMapPointer(evt) {
    if (!S.c || !S.shown) return;
    var hit = nearest(evt);
    var idx = hit ? hit.i : -1;
    if (idx !== S.hot) {
      if (S.hot >= 0 && S.els[S.hot]) S.els[S.hot].classList.remove('hot');
      S.hot = idx;
      if (idx >= 0) S.els[idx].classList.add('hot');
      place(S.shown);
    }
    if (hit) showTip(hit); else $('map-tip').hidden = true;
  }
  function clearHot() {
    if (S.hot >= 0 && S.els[S.hot]) S.els[S.hot].classList.remove('hot');
    S.hot = -1;
    $('map-tip').hidden = true;
    if (S.shown) place(S.shown);
  }

  // --- the readout ---------------------------------------------------------------------------------------
  function renderBars(c, L) {
    var box = $('bars'), m = c.spread.muse[L - 1], p = c.spread.people[L - 1], top = 1;
    box.innerHTML = '';
    [['muse', 'Muse', m], ['people', 'People', p]].forEach(function (r) {
      var fill = h('span', { class: 'fill ' + r[0] });
      fill.style.width = (100 * clamp(r[2] / top, 0, 1)) + '%';
      var track = h('span', { class: 'track' }, fill);
      if (r[0] === 'muse') {
        var tick = h('span', { class: 'half', title: 'Half of people’s spread' });
        tick.style.left = (100 * clamp(0.5 * p / top, 0, 1)) + '%';
        track.appendChild(tick);
      }
      box.appendChild(h('div', { class: 'bar-row' }, [
        h('span', { class: 'bar-lab' }, [h('i', { class: 'key ' + r[0], 'aria-hidden': 'true' }),
          h('span', null, [r[1], r[0] === 'muse' ? h('span', { class: 'long', text: ' Image' }) : null])]),
        track,
        h('span', { class: 'bar-val', text: f2(r[2]) })
      ]));
    });
    var ratio = m / p;
    box.appendChild(h('p', { class: 'bar-note' }, [
      'Spread, how far apart the drawings are: 0 would mean all in one spot. Muse Image’s ÷ people’s: ', h('b', { text: f2(ratio) }),
      ratio < 0.5 ? ' (left of the tick: under half)' : ' (the tick marks half of people’s)'
    ]));
  }

  function renderReadout() {
    var c = S.c, L = S.layer, ph = phase(c, L);
    $('layer-num').textContent = String(L);
    var pill = $('phase');
    pill.textContent = ph.label;
    pill.className = 'pi-phase ' + ph.key;
    $('phase-text').textContent = phaseText(c, L);
    renderBars(c, L);
    var k = lensCounts(c, L);
    $('lens-line').textContent = 'Word lens reads “' + c.label + '” at this stage: ' + k[0] + ' of ' + c.n.muse + ' Muse Image drawings · ' +
      k[1] + ' of ' + c.n.people + ' people’s.';
    $('watermark').innerHTML = '';
    $('watermark').appendChild(h('span', { text: 'stage' }));
    $('watermark').appendChild(h('b', { text: String(L) }));
    $('map').setAttribute('aria-label', mapLabel(c, L));
    var r = $('layer');
    r.value = String(L);
    r.setAttribute('aria-valuetext', 'Stage ' + L + ' of 52: ' + ph.label.toLowerCase() + '. Spread: Muse Image ' + f2(c.spread.muse[L - 1]) +
      ', people ' + f2(c.spread.people[L - 1]) + '.');
    $('prev').disabled = L <= 1;
    $('next').disabled = L >= N_LAYERS;
    moveCursor();
  }

  // --- slider marks and jump buttons ------------------------------------------------------------------
  function trackPos(L) { return 'calc(11px + ' + ((L - 1) / (N_LAYERS - 1)) + ' * (100% - 22px))'; }

  function renderMarks() {
    var c = S.c, box = $('marks'), cl = c.collapse_layer, nl = nameLayer(c);
    box.innerHTML = '';
    box.appendChild(h('span', { class: 'rail' }));
    if (cl) {
      var band = h('span', { class: 'band' });
      band.style.left = trackPos(cl);
      band.style.right = '11px';
      box.appendChild(band);
      var m1 = h('span', { class: 'mark collapse' });
      m1.style.left = trackPos(cl);
      box.appendChild(m1);
    }
    if (nl) {
      var m2 = h('span', { class: 'mark name' });
      m2.style.left = trackPos(nl);
      box.appendChild(m2);
    }
    var jumps = $('jumps');
    jumps.innerHTML = '';
    function jump(label, L, cls) {
      jumps.appendChild(h('button', { type: 'button', class: 'pi-jump' + (cls ? ' ' + cls : ''), onclick: function () { stop(); S.touched = true; go(L); } },
        [cls ? h('i', { 'aria-hidden': 'true' }) : null, label]));
    }
    jump('Stage 1', 1);
    if (cl) jump('In one place · ' + cl, cl, 'collapse');
    else jumps.appendChild(h('span', { class: 'pi-jump-note', text: 'Muse Image’s drawings are never filed in one place' }));
    if (nl) jump('Name readable · ' + nl, nl, 'name');
    jump('Stage 52', N_LAYERS);
  }

  // --- the spread chart ---------------------------------------------------------------------------------
  var CH = null;
  function renderChart() {
    var wrap = $('spread-chart'), c = S.c;
    var W = Math.max(280, wrap.clientWidth), H = W < 420 ? 200 : 228;
    var m = { l: 34, r: 58, t: 30, b: 30 };
    var all = c.spread.muse.concat(c.spread.people);
    var ymax = Math.max(0.8, Math.ceil(Math.max.apply(null, all) * 10) / 10);
    var x = function (L) { return m.l + (L - 1) / (N_LAYERS - 1) * (W - m.l - m.r); };
    var y = function (v) { return m.t + (1 - v / ymax) * (H - m.t - m.b); };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'img',
      'aria-label': 'Line chart of how far apart the drawings of ' + aThing(c.label) + ' are, stage by stage. Muse Image’s drawings: ' + f2(c.spread.muse[0]) + ' at stage 1, ' +
        f2(Math.max.apply(null, c.spread.muse)) + ' at most, ' + f2(c.spread.muse[N_LAYERS - 1]) + ' at stage 52. People’s: ' + f2(c.spread.people[0]) +
        ', ' + f2(Math.max.apply(null, c.spread.people)) + ' at most, ' + f2(c.spread.people[N_LAYERS - 1]) + ' at stage 52.' +
        (c.collapse_layer ? ' Muse Image’s filed in one place from stage ' + c.collapse_layer + '.' : ' Muse Image’s never filed in one place.') });
    var cl = c.collapse_layer, nl = nameLayer(c);
    if (cl) {
      svg.appendChild(s('rect', { x: x(cl), y: m.t, width: x(N_LAYERS) - x(cl), height: H - m.t - m.b, fill: C.ink, 'fill-opacity': 0.045 }));
    }
    for (var t = 0; t <= ymax + 1e-9; t += 0.2) {
      svg.appendChild(s('line', { x1: m.l, x2: x(N_LAYERS), y1: y(t), y2: y(t), stroke: t === 0 ? C.axis : C.grid, 'stroke-width': 1 }));
      svg.appendChild(s('text', { x: m.l - 6, y: y(t) + 4, 'text-anchor': 'end', class: 'tick' }, t.toFixed(1)));
    }
    [1, 13, 26, 39, 52].forEach(function (L) {
      svg.appendChild(s('text', { x: x(L), y: H - m.b + 16, 'text-anchor': 'middle', class: 'tick' }, String(L)));
    });
    svg.appendChild(s('text', { x: x(N_LAYERS) + 8, y: H - m.b + 16, class: 'tick' }, 'stage'));
    // event markers: collapse (with the shaded band) and the word lens; one label when they sit close
    var labels = [];
    if (cl) {
      svg.appendChild(s('line', { x1: x(cl), x2: x(cl), y1: m.t - 4, y2: H - m.b, stroke: C.ink, 'stroke-opacity': 0.55, 'stroke-width': 1 }));
      labels.push({ x: x(cl), text: 'one place ' + cl });
    }
    if (nl) {
      svg.appendChild(s('line', { x1: x(nl), x2: x(nl), y1: m.t - 4, y2: H - m.b, stroke: C.axis, 'stroke-width': 1 }));
      labels.push({ x: x(nl), text: 'name ' + nl });
    }
    if (labels.length === 2 && labels[1].x - labels[0].x < 74) {
      labels = [{ x: labels[0].x, text: labels[0].text + ' · ' + labels[1].text }];
    }
    labels.forEach(function (lb, i) {
      var anchor = lb.x > W - m.r - 40 ? 'end' : (i === 0 && labels.length === 2 ? 'end' : 'start');
      svg.appendChild(s('text', { x: lb.x + (anchor === 'end' ? -4 : 4), y: m.t - 10, 'text-anchor': anchor, class: 'mark-lab' }, lb.text));
    });
    // the two lines
    ['people', 'muse'].forEach(function (src) {
      var d = c.spread[src].map(function (v, i) { return (i ? 'L' : 'M') + x(i + 1).toFixed(1) + ',' + y(v).toFixed(1); }).join('');
      svg.appendChild(s('path', { d: d, fill: 'none', stroke: C[src], 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
    });
    // end labels, nudged apart when the lines end close together
    var ey = { muse: y(c.spread.muse[N_LAYERS - 1]), people: y(c.spread.people[N_LAYERS - 1]) };
    if (Math.abs(ey.muse - ey.people) < 14) {
      var mid = (ey.muse + ey.people) / 2, up = ey.muse < ey.people ? 'muse' : 'people';
      ey[up] = mid - 7; ey[up === 'muse' ? 'people' : 'muse'] = mid + 7;
    }
    svg.appendChild(s('text', { x: x(N_LAYERS) + 6, y: ey.muse + 4, class: 'end-lab' }, 'Muse'));
    svg.appendChild(s('text', { x: x(N_LAYERS) + 6, y: ey.people + 4, class: 'end-lab' }, 'people'));
    // the current layer, and a hover crosshair
    var cursor = s('g', { class: 'cursor' }, [
      s('line', { y1: m.t - 4, y2: H - m.b, stroke: C.ink, 'stroke-width': 1.5 }),
      s('circle', { r: 4.5, fill: C.people, stroke: C.surface, 'stroke-width': 2, class: 'cp' }),
      s('circle', { r: 4.5, fill: C.muse, stroke: C.surface, 'stroke-width': 2, class: 'cm' })
    ]);
    svg.appendChild(cursor);
    var hover = s('line', { y1: m.t, y2: H - m.b, stroke: C.axis, 'stroke-width': 1, visibility: 'hidden' });
    svg.appendChild(hover);
    var hit = s('rect', { x: m.l, y: m.t - 14, width: x(N_LAYERS) - m.l, height: H - m.t - m.b + 14, fill: 'transparent', class: 'hit' });
    svg.appendChild(hit);
    function layerAt(evt) {
      var r = svg.getBoundingClientRect(), px = (evt.clientX - r.left) * (W / r.width);
      return clamp(Math.round((px - m.l) / (x(N_LAYERS) - m.l) * (N_LAYERS - 1)) + 1, 1, N_LAYERS);
    }
    var dragging = false;
    hit.addEventListener('pointerdown', function (evt) {
      dragging = true; stop(); S.touched = true;
      try { hit.setPointerCapture(evt.pointerId); } catch (e) { /* older browsers */ }
      go(layerAt(evt));
    });
    hit.addEventListener('pointerup', function () { dragging = false; });
    hit.addEventListener('pointercancel', function () { dragging = false; });
    hit.addEventListener('pointermove', function (evt) {
      var L = layerAt(evt);
      if (dragging) go(L);
      hover.setAttribute('x1', x(L)); hover.setAttribute('x2', x(L)); hover.setAttribute('visibility', 'visible');
      chartTip(wrap, evt, L);
    });
    hit.addEventListener('pointerleave', function () { hover.setAttribute('visibility', 'hidden'); hideChartTip(wrap); });
    var old = wrap.querySelector('svg');
    if (old) wrap.replaceChild(svg, old); else wrap.insertBefore(svg, wrap.firstChild);
    CH = { x: x, y: y, cursor: cursor, W: W };
    moveCursor();
  }

  function moveCursor() {
    if (!CH || !S.c) return;
    var L = S.layer, X = CH.x(L);
    CH.cursor.querySelector('line').setAttribute('x1', X);
    CH.cursor.querySelector('line').setAttribute('x2', X);
    var cm = CH.cursor.querySelector('.cm'), cp = CH.cursor.querySelector('.cp');
    cm.setAttribute('cx', X); cm.setAttribute('cy', CH.y(S.c.spread.muse[L - 1]));
    cp.setAttribute('cx', X); cp.setAttribute('cy', CH.y(S.c.spread.people[L - 1]));
  }

  function chartTip(wrap, evt, L) {
    var tip = wrap.querySelector('.pi-ctip');
    if (!tip) { tip = h('div', { class: 'pi-ctip', role: 'presentation' }); wrap.appendChild(tip); }
    var c = S.c, m = c.spread.muse[L - 1], p = c.spread.people[L - 1];
    tip.innerHTML = '';
    tip.appendChild(h('div', { class: 'tl' }, 'Stage ' + L + (L === c.collapse_layer ? ' · in one place' : '') + (L === nameLayer(c) ? ' · name readable' : '')));
    [['muse', 'Muse Image', m], ['people', 'People', p]].forEach(function (r) {
      tip.appendChild(h('div', { class: 'tr' }, [h('i', { class: 'lk ' + r[0] }), h('b', { text: f2(r[2]) }), h('span', { text: r[1] })]));
    });
    tip.appendChild(h('div', { class: 'tn', text: 'Muse Image ÷ people ' + f2(m / p) }));
    tip.hidden = false;
    var r = wrap.getBoundingClientRect(), left = evt.clientX - r.left + 14, top = evt.clientY - r.top - 10;
    if (left + tip.offsetWidth > r.width) left = evt.clientX - r.left - tip.offsetWidth - 14;
    tip.style.left = Math.max(0, left) + 'px';
    tip.style.top = Math.max(0, top) + 'px';
  }
  function hideChartTip(wrap) { var t = wrap.querySelector('.pi-ctip'); if (t) t.hidden = true; }

  function renderTable() {
    var c = S.c, t = $('spread-table'), nl = nameLayer(c), np = c.name_layer.people == null ? null : Math.ceil(c.name_layer.people);
    t.innerHTML = '';
    t.appendChild(h('caption', { class: 'sr-only', text: 'Spread of the drawings of ' + aThing(c.label) + ' at each stage' }));
    t.appendChild(h('thead', null, h('tr', null, [h('th', { text: 'Stage' }), h('th', { class: 'num', text: 'Muse Image' }),
      h('th', { class: 'num', text: 'People' }), h('th', { class: 'num', text: 'Muse Image ÷ people' }), h('th', { text: 'Note' })])));
    var tb = h('tbody');
    for (var L = 1; L <= N_LAYERS; L++) {
      var m = c.spread.muse[L - 1], p = c.spread.people[L - 1], notes = [];
      if (L === c.collapse_layer) notes.push('Muse Image’s drawings filed in one place');
      if (L === nl) notes.push('name readable, Muse Image’s (typical)');
      if (L === np) notes.push('name readable, people’s (typical)');
      tb.appendChild(h('tr', { class: c.collapse_layer && L >= c.collapse_layer ? 'after' : '' }, [h('td', { text: String(L) }),
        h('td', { class: 'num', text: f2(m) }), h('td', { class: 'num', text: f2(p) }), h('td', { class: 'num', text: f2(m / p) }),
        h('td', { text: notes.join('; ') })]));
    }
    t.appendChild(tb);
  }

  // --- the 35 things --------------------------------------------------------------------------------------
  var DOM = [28, 52];
  function dpos(L) { return (3 + (L - DOM[0]) / (DOM[1] - DOM[0]) * 94).toFixed(2) + '%'; }

  function renderDumbbell() {
    var box = $('dumbbell'), D = S.data;
    box.innerHTML = '';
    var axis = h('div', { class: 'd-axis', 'aria-hidden': 'true' }, [h('span'), h('span', { class: 'd-ticks' }), h('span')]);
    [30, 35, 40, 45, 50].forEach(function (L) {
      var tk = h('span', { class: 'd-tick', text: String(L) });
      tk.style.left = dpos(L);
      axis.children[1].appendChild(tk);
    });
    axis.children[1].appendChild(h('span', { class: 'd-unit', text: 'stage' }));
    box.appendChild(axis);
    var rows = D.concepts.slice().sort(function (a, b) {
      var ca = a.collapse_layer || 99, cb = b.collapse_layer || 99;
      return ca - cb || (a.name_layer.muse || 0) - (b.name_layer.muse || 0) || a.label.localeCompare(b.label);
    });
    var list = h('div', { class: 'd-rows', role: 'group', 'aria-label': 'Choose a thing to explore above' });
    var med = h('span', { class: 'd-median', 'aria-hidden': 'true' }, h('span', { text: 'typical ' + D.summary.median_collapse_layer }));
    med.style.left = dpos(D.summary.median_collapse_layer);
    var overlay = h('div', { class: 'd-overlay', 'aria-hidden': 'true' }, [h('span'), h('span', { class: 'd-ov-track' }, med), h('span')]);
    rows.forEach(function (c) {
      var cl = c.collapse_layer, nl = c.name_layer.muse;
      var svg = s('svg', { width: '100%', height: 18, 'aria-hidden': 'true', class: 'd-svg' });
      if (cl && nl) svg.appendChild(s('line', { x1: dpos(cl), x2: dpos(nl), y1: 9, y2: 9, stroke: C.axis, 'stroke-width': 2, 'stroke-linecap': 'round' }));
      if (nl && nl !== cl) svg.appendChild(s('circle', { cx: dpos(nl), cy: 9, r: 4.5, fill: C.surface, stroke: C.muse, 'stroke-width': 2 }));
      if (cl) svg.appendChild(s('circle', { cx: dpos(cl), cy: 9, r: 5, fill: C.muse, stroke: C.surface, 'stroke-width': 2 }));
      if (nl && nl === cl) svg.appendChild(s('circle', { cx: dpos(nl), cy: 9, r: 8, fill: 'none', stroke: C.muse, 'stroke-width': 2 }));  // same layer: a ring around the dot
      var val = cl ? cl + ' → ' + layerWord(nl) : 'never · ' + layerWord(nl);
      var b = h('button', { type: 'button', class: 'd-row', 'data-key': c.key, 'aria-pressed': c === S.c ? 'true' : 'false',
        'aria-label': cap(c.label) + ': ' + (cl ? 'filed in one place at stage ' + cl : 'never filed in one place') + ', name readable at stage ' + layerWord(nl),
        onclick: function () { stop(); S.touched = true; choose(c.key, true); } }, [
        h('span', { class: 'd-lab', text: c.label }), h('span', { class: 'd-track' }, svg), h('span', { class: 'd-val', text: val })]);
      list.appendChild(b);
    });
    var body = h('div', { class: 'd-body' }, [overlay, list]);
    box.appendChild(body);
  }
  function markDumbbell() {
    document.querySelectorAll('#dumbbell .d-row').forEach(function (b) {
      b.setAttribute('aria-pressed', b.getAttribute('data-key') === S.c.key ? 'true' : 'false');
    });
  }

  // --- the first look: the chair at three layers, and three numbers drawn as graphics ----------------------
  var TRIP = [1, 26, 52];

  function tripPanel(c, L) {
    var n = c.n.muse, N = c.pictures.length, xy = c.xy[L - 1], pad = 72, size = 124, sc = (1000 - 2 * pad) / GRID;
    var px = function (v) { return pad + v * sc; };
    var svg = s('svg', { viewBox: '0 0 1000 1000', class: 'pi-trip-svg', 'aria-hidden': 'true' });
    var groups = { muse: groupStats(xy, 0, n), people: groupStats(xy, n, N) };
    ['people', 'muse'].forEach(function (src) {
      var g = groups[src];
      svg.appendChild(s('circle', { class: 'pi-trip-halo ' + src, cx: px(g.x).toFixed(1), cy: px(g.y).toFixed(1), r: Math.max(24, g.r * sc).toFixed(1) }));
    });
    // people's doodles first, so Muse's sit on top of the pile; a dot under each stands in if the sprite is missing
    for (var k = 0; k < N; k++) {
      var i = (k + n) % N, x = px(xy[2 * i]), y = px(xy[2 * i + 1]), src = i < n ? 'muse' : 'people';
      svg.appendChild(s('circle', { class: 'pi-trip-dot ' + src, cx: x.toFixed(1), cy: y.toFixed(1), r: 15 }));
      svg.appendChild(s('svg', { x: (x - size / 2).toFixed(1), y: (y - size / 2).toFixed(1), width: size, height: size, viewBox: i + ' 0 1 1',
        class: 'pi-trip-pic' }, s('image', { href: SPRITES + c.sprite, width: N, height: 1, preserveAspectRatio: 'none' })));
    }
    var ph = phase(c, L);
    return h('div', { class: 'pi-trip-p' }, [
      h('div', { class: 'pi-trip-paper' }, svg),
      h('p', { class: 'pi-trip-lab' }, [h('b', { text: 'Stage ' + L }), h('span', { text: ph.label })])
    ]);
  }

  function renderTrip() {
    var D = S.data, c = D.concepts.filter(function (x) { return x.key === 'chair'; })[0] || D.concepts[0];
    var box = $('hero-trip'), last = TRIP[TRIP.length - 1];
    box.innerHTML = '';
    TRIP.forEach(function (L) { box.appendChild(tripPanel(c, L)); });
    var m0 = c.spread.muse[0], p0 = c.spread.people[0], m1 = c.spread.muse[last - 1], p1 = c.spread.people[last - 1];
    box.setAttribute('aria-label', c.n.muse + ' of Muse Image’s drawings of ' + aThing(c.label) + ' and ' + c.n.people + ' of people’s, mapped inside Muse Glimmer at stages ' +
      TRIP.join(', ') + ' of ' + N_LAYERS + '. At stage 1 both sets are spread out (spread ' + f2(m0) + ' and ' + f2(p0) + '). At stage ' + last +
      ' Muse Image’s drawings sit in a tight pile (' + f2(m1) + ') while people’s stay spread out (' + f2(p1) + ').');
    var img = new Image();
    img.onerror = function () { box.classList.add('no-sprite'); };
    img.src = SPRITES + c.sprite;
  }

  function renderLead() {
    var lead = window.FirstLook.inside(S.data);
    window.FirstLook.render($('hero-stats'), lead);
    $('hero-note').textContent = lead.note;
    renderTrip();
  }

  // --- static text from the data -----------------------------------------------------------------------
  function renderText() {
    var D = S.data, sm = D.summary, ms = sm.mean_spread, nb = sm.same_thing_neighbour;
    var last = N_LAYERS - 1, mid = 25;
    var times = ms.people[last] / ms.muse[last];
    renderLead();

    var steps = $('steps');
    steps.innerHTML = '';
    var L39 = 38;
    [[1, 'Seeing the drawing', 'Stages 1–12', 'Glimmer takes in the picture. Drawings of the same thing sit near each other: at stage 1, for ' + pct(nb.muse[0]) +
      ' of Muse Image’s drawings and ' + pct(nb.people[0]) + ' of people’s, the closest drawing shows the same thing.'],
     [20, 'In the middle', 'Stages 13–30', 'At the spot where Glimmer will write its answer, it now holds little about which thing a drawing shows. At stage 26, only ' +
      pct(nb.people[mid]) + ' of people’s drawings and ' + pct(nb.muse[mid]) + ' of Muse Image’s sit closest to a drawing of the same thing. Both sets are spread out (spread ' +
      f2(ms.muse[mid]) + ' for Muse Image and ' + f2(ms.people[mid]) + ' for people, averaged over 35 things).'],
     [44, 'Settling on a name', 'Stages 31–52', 'Which thing it is comes back: from stage 39, ' + pct(nb.muse[L39]) + ' of Muse Image’s drawings and ' + pct(nb.people[L39]) +
      ' of people’s sit closest to one of the same thing. Glimmer files Muse Image’s drawings of a thing in one place (typically by stage ' + sm.median_collapse_layer +
      '). A few stages later, the word lens (a tool that reads which word Glimmer is heading towards) can read the name.']
    ].forEach(function (st, i) {
      steps.appendChild(h('li', { class: 'pi-step' }, [
        h('span', { class: 'n', 'aria-hidden': 'true', text: String(i + 1) }),
        h('div', null, [h('h3', { text: st[1] }), h('span', { class: 'when', text: st[2] }), h('p', { text: st[3] }),
          h('button', { type: 'button', class: 'pi-jump', onclick: function () { stop(); S.touched = true; go(st[0]); scrollToMap(); } }, 'Show stage ' + st[0])])
      ]));
    });

    $('why-text').textContent = 'Muse Image draws nearly the same chair every time, so its drawings start out more alike than people’s: that is the main finding of Plato’s Chair. ' +
      'Inside Glimmer the gap grows. Through the middle stages both sets are about equally spread out. By the last stage, Muse Image’s drawings of a thing are about ' +
      (times >= 5.5 && times < 6.5 ? 'a sixth' : '1/' + Math.round(times)) + ' as far apart as people’s (spread ' + f2(ms.muse[last]) + ' against ' + f2(ms.people[last]) +
      '). Glimmer files them in nearly one place, almost as if they were one drawing. People’s drawings of a thing stay many different drawings to the last stage.';

    var o = sm.other_thresholds || [];
    var lo = o.filter(function (r) { return r.ratio < 0.5; })[0], hi = o.filter(function (r) { return r.ratio > 0.5; })[0];
    $('every-lede').textContent = 'For each of the ' + sm.n_concepts + ' things: the stage where Glimmer files Muse Image’s drawings in one place (filled dot), and the typical stage ' +
      'where the word lens, a tool that reads which word Glimmer is heading towards, first reads the name (ring). ' +
      'In all ' + sm.n_with_both + ' things that get filed in one place, it happens at or before the name, typically ' + sm.median_layers_between + ' stages earlier. ' +
      'Drawings of “' + sm.never_collapse.join('”, “') + '” are never filed in one place. Choose a thing to explore it above.';
    var cav = 'Two caveats. We chose the line for “in one place” (Muse Image’s spread under half of people’s) after seeing the data.';
    if (lo) cav += ' If the line were ' + lo.ratio + ' of people’s spread instead, the typical stage would be ' + lo.median_collapse_layer + ', drawings of ' +
      lo.never_collapse.join(', ') + ' would never be filed together, and ' + lo.collapse_at_or_before_name + ' of ' + lo.n_with_both +
      ' things would still get there at or before the name.';
    if (hi) cav += ' At ' + hi.ratio + ', it would be ' + hi.median_collapse_layer + (hi.never_collapse.length ? '' : ' and every thing would get filed in one place') + '.';
    cav += ' And the word lens shows when a name becomes readable, not when an idea forms. So “first filed together, then named” compares two measurements; it doesn’t say what Glimmer thinks first.';
    $('every-caveat').textContent = cav;

    var lt = $('cav-threshold');
    if (lt && lo && hi) {
      lt.appendChild(document.createTextNode(' At ' + lo.ratio + ' the typical (median) stage would be ' + lo.median_collapse_layer + ' (' + lo.never_collapse.length +
        ' things never get there); at ' + hi.ratio + ', ' + hi.median_collapse_layer + '.'));
    }

    var mp = D.map, kept = mp.spread_kept;
    var capEl = $('map-cap');
    capEl.innerHTML = '';
    capEl.appendChild(h('b', { text: 'How the map is drawn. ' }));
    capEl.appendChild(document.createTextNode('Inside Glimmer each drawing is a list of 6,656 numbers. The map squeezes them into two, keeping the real distances between ' +
      'drawings as closely as it can (weighted multidimensional scaling, most faithful within each set). Each stage starts from the one before and is turned to ' +
      'line up with it (Procrustes). All stages share one scale, so a drawing moves only as far as Glimmer’s view of it changes, and a shrinking cluster really ' +
      'shrinks. The map keeps about ' + Math.round(kept.muse * 100) + '% of Muse Image’s spread and ' + Math.round(kept.people * 100) + '% of people’s; its two directions mean ' +
      'nothing. We tried a simpler map first (PCA), but it mostly showed the difference in drawing style and hid most of the middle stages’ spread. The chart uses all 6,656 numbers.'));
  }

  function scrollToMap() {
    var el = $('explorer');
    if (el.scrollIntoView) el.scrollIntoView({ behavior: reduced() ? 'auto' : 'smooth', block: 'start' });
  }

  // --- state changes -------------------------------------------------------------------------------------
  var urlTimer = 0;
  function saveUrl() {
    clearTimeout(urlTimer);
    urlTimer = setTimeout(function () {
      try {
        var q = new URLSearchParams(location.search);
        q.set('thing', S.c.key); q.set('layer', String(S.layer));
        if (S.view === 'dots') q.set('view', 'dots'); else q.delete('view');
        history.replaceState(null, '', location.pathname + '?' + q.toString() + location.hash);
      } catch (e) { /* not essential */ }
    }, 250);
  }

  function go(L, dur) {
    L = clamp(Math.round(L), 1, N_LAYERS);
    S.layer = L;
    renderReadout();
    tweenTo(S.c.xy[L - 1], dur == null ? 260 : dur);
    if (S.touched) saveUrl();  // a shared link opens where its sender was; an untouched page keeps a clean address
  }

  function loadSprite(c) {
    if (S.spriteOk[c.sprite] != null) return;
    S.spriteOk[c.sprite] = false;
    var img = new Image();
    img.onload = function () { S.spriteOk[c.sprite] = true; };
    img.onerror = function () {
      // no thumbnails on this server: show dots
      var btn = document.querySelector('#view-seg [data-view="drawings"]');
      if (btn) btn.disabled = true;
      if (S.view === 'drawings' && S.c === c) { var t = S.touched; setView('dots'); S.touched = t; }
    };
    img.src = SPRITES + c.sprite;
  }

  function choose(key, announce) {
    var c = S.data.concepts.filter(function (x) { return x.key === key; })[0] || S.data.concepts[0];
    S.c = c;
    $('thing').value = c.key;
    loadSprite(c);
    buildPoints();
    S.shown = null;
    renderMarks();
    renderChart();
    renderTable();
    go(S.layer, 0);
    markDumbbell();
    $('chart-h').textContent = 'How far apart each set of ' + (MASS[c.label] ? c.label : c.label + ' drawings') + ' is, stage by stage';
    if (announce) {
      $('thing-note').textContent = cap(c.label) + ': ' + (c.collapse_layer ? 'Muse Image’s drawings filed in one place at stage ' + c.collapse_layer : 'Muse Image’s drawings never filed in one place') +
        '; the word lens reads the name at stage ' + nameLayer(c) + '.';
    }
  }

  function setView(v) {
    S.view = v;
    S.touched = true;
    document.querySelectorAll('#view-seg button').forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-view') === v ? 'true' : 'false'); });
    buildPoints();
    if (S.shown) place(S.shown);
    saveUrl();
  }

  // --- play ----------------------------------------------------------------------------------------------
  function setPlaying(on) {
    var b = $('play');
    b.classList.toggle('playing', on);
    b.setAttribute('aria-label', on ? 'Pause' : 'Play through the layers');
  }
  function stop() {
    if (S.timer) { clearInterval(S.timer); S.timer = 0; setPlaying(false); }
  }
  function play() {
    if (S.timer) { stop(); return; }
    var every = reduced() ? 450 : 150;
    if (S.layer >= N_LAYERS) go(1, 0);
    setPlaying(true);
    S.timer = setInterval(function () {
      if (S.layer >= N_LAYERS) { stop(); return; }
      go(S.layer + 1, reduced() ? 0 : every);
    }, every);
  }

  // --- wiring ----------------------------------------------------------------------------------------------
  function wire() {
    var sel = $('thing');
    S.data.concepts.forEach(function (c) { sel.appendChild(h('option', { value: c.key, text: cap(c.label) })); });
    sel.addEventListener('change', function () { stop(); S.touched = true; choose(sel.value, true); });
    var range = $('layer');
    range.addEventListener('input', function () { stop(); S.touched = true; go(+range.value, 200); });
    $('prev').addEventListener('click', function () { stop(); S.touched = true; go(S.layer - 1); });
    $('next').addEventListener('click', function () { stop(); S.touched = true; go(S.layer + 1); });
    $('play').addEventListener('click', function () { S.touched = true; play(); });
    document.querySelectorAll('#view-seg button').forEach(function (b) {
      b.addEventListener('click', function () { setView(b.getAttribute('data-view')); });
    });
    var map = $('map');
    map.addEventListener('pointermove', onMapPointer);
    map.addEventListener('pointerdown', onMapPointer);
    map.addEventListener('pointerleave', clearHot);
    var lastW = map.clientWidth, lastC = $('spread-chart').clientWidth;
    var onResize = function () {
      if (map.clientWidth !== lastW) { lastW = map.clientWidth; buildPoints(); if (S.shown) place(S.shown); }
      if ($('spread-chart').clientWidth !== lastC) { lastC = $('spread-chart').clientWidth; renderChart(); }
    };
    if (window.ResizeObserver) new ResizeObserver(onResize).observe(document.body);
    else window.addEventListener('resize', onResize);
  }

  // Play once, from layer 1, the first time the map comes into view (never with reduced motion or a shared layer).
  function autoplay(fromUrl) {
    if (fromUrl || reduced() || !window.IntersectionObserver) return;
    var io = new IntersectionObserver(function (entries) {
      if (!entries.some(function (e) { return e.isIntersecting; })) return;
      io.disconnect();
      setTimeout(function () { if (!S.touched && S.layer === 1) play(); }, 500);
    }, { threshold: 0.6 });
    io.observe($('map'));
  }

  function init(data) {
    S.data = data;
    N_LAYERS = data.n_layers || 52;
    var q = new URLSearchParams(location.search);
    var L = parseInt(q.get('layer'), 10);
    S.layer = L >= 1 && L <= N_LAYERS ? L : 1;
    if (q.get('view') === 'dots') S.view = 'dots';
    document.querySelectorAll('#view-seg button').forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-view') === S.view ? 'true' : 'false'); });
    renderText();
    wire();
    renderDumbbell();
    choose(q.get('thing') || data.concepts[0].key, false);
    autoplay(!!q.get('layer'));
  }

  T.api('/api/plato/inside').then(init).catch(function (err) {
    var box = $('load-error');
    box.textContent = (err && err.message) || 'The inside-the-model data could not be loaded.';
    box.hidden = false;
    $('explorer').hidden = true;
  });
})();
