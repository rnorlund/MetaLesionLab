/* What can I cut? Replays the layer-removal run: the greedy path with your own guard settings, every layer
   skipped alone, and the cuts deleted for real. Data: /api/lab/cut. No API calls. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var NS = 'http://www.w3.org/2000/svg';
  var BLUE = '#1D4ED8', TEAL = '#0D9488', INK2 = '#374151', GUARD = '#9A3412', GRID = '#E5E7EB', AXIS = '#9CA3AF';
  var RAMP = ['#FFF7ED', '#FED7AA', '#FB923C', '#EA580C', '#9A3412'];
  var CUT_NAMES = { intact: 'Intact', confirmed: 'Safe cut', guarded: 'Both guards, without the held-out check',
    perplexity_only: 'Perplexity check only', deep_10: '10 layers, no check' };
  var S = { d: null, tol: 5, pplTol: 10, guards: { naming: true, heldout: true, ppl: true }, measure: 'naming', selected: null };
  var readyResolve;
  var ready = new Promise(function (r) { readyResolve = r; });

  function $(id) { return document.getElementById(id); }
  function pct(x, d) { return (x * 100).toFixed(d == null ? 0 : d) + '%'; }
  function signed(x, d) { var v = Number(x).toFixed(d == null ? 1 : d); return (x > 0 ? '+' : x < 0 ? '−' : '') + v.replace('-', '') + '%'; }
  function billions(n) { return (n / 1e9).toFixed(2) + ' B'; }
  function listAnd(a) { return a.length < 2 ? a.join('') : a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1]; }
  // The results count layers from 0, as in the model's code; the page shows them 1–52.
  function L1(i) { return String(Number(i) + 1); }
  function s(tag, attrs, kids) {
    var el = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) el.setAttribute(k, attrs[k]); });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c != null) el.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return el;
  }

  // --- the guard logic (as in compress.within_guard / mark_heldout / last_within_guard) -------
  function step0() { return S.d.greedy[0]; }
  function checks(st) {
    var b = step0(), keep = 1 - S.tol / 100;
    return {
      naming: st.correct >= keep * b.correct - 1e-9,
      heldout: st.heldout_correct >= keep * b.heldout_correct - 1e-9,
      ppl: st.ppl <= (1 + S.pplTol / 100) * b.ppl + 1e-9
    };
  }
  function passes(st) {
    var c = checks(st);
    return Object.keys(S.guards).every(function (g) { return !S.guards[g] || c[g]; });
  }
  /* The deepest step in the unbroken run of passing steps from the start: a step that passes again after a
     failure is luck on a small test, not a safe cut. */
  function deepest(steps) {
    var k = 0;
    for (var i = 0; i < steps.length; i++) { if (!passes(steps[i])) break; k = i; }
    return k;
  }
  function perLayer() {
    var p = S.d.pruned, base = p[0];
    var r = p.filter(function (x) { return x.removed && x.removed.length; })[0];
    return r ? (base.params - r.params) / r.removed.length : 0;
  }
  function measuredCut(removed) {
    var key = removed.slice().sort(function (a, b) { return a - b; }).join(',');
    return S.d.pruned.filter(function (p) { return p.removed.slice().sort(function (a, b) { return a - b; }).join(',') === key; })[0];
  }
  function defaultDeepest() {
    var saved = { tol: S.tol, pplTol: S.pplTol, guards: S.guards };
    S.tol = 5; S.pplTol = 10; S.guards = { naming: true, heldout: true, ppl: true };
    var k = deepest(S.d.greedy);
    S.tol = saved.tol; S.pplTol = saved.pplTol; S.guards = saved.guards;
    return k;
  }

  // --- hero tiles ------------------------------------------------------------------------------
  function renderTiles() {
    var d = S.d, k = defaultDeepest(), st = d.greedy[k], cut = measuredCut(st.removed);
    var savedPPL = { tol: S.tol, pplTol: S.pplTol, guards: S.guards };
    S.guards = { naming: false, heldout: false, ppl: true }; S.pplTol = 10;
    var kp = deepest(d.greedy);
    S.tol = savedPPL.tol; S.pplTol = savedPPL.pplTol; S.guards = savedPPL.guards;
    var l0 = d.layers[0], lost0 = Math.round(-l0.skip_d_acc * d.guards.naming.n);
    var sav = cut && cut.savings_pct;
    var tiles = [
      ['good', k + ' of ' + d.intact.layers, 'layers can go (' + listAnd(st.removed.slice().sort(function (a, b) { return a - b; }).map(L1)) + '): about ' +
        (sav ? Math.round(-sav.params) + '% smaller and ' + Math.round(-sav.ms_per_item) + '% faster' : 'that much smaller') + ', with no loss beyond run-to-run noise (at most one picture), even on held-out pictures.'],
      ['warn', kp + ' layers', 'is what the usual check (perplexity alone) would allow. That cut breaks Spanish: the model starts answering in English.'],
      ['', 'Layer 1', 'is critical: skipping it alone loses ' + lost0 + ' of ' + d.guards.naming.n + ' pictures and doubles perplexity.'],
      ['', (d.block_influence_vs_skip.spearman_bi_answer_vs_acc_loss).toFixed(2), 'is how well a popular shortcut (block influence) tracked which layers naming needs: barely at all.']
    ];
    var box = $('cut-tiles');
    box.innerHTML = '';
    tiles.forEach(function (t) { box.appendChild(h('div', { class: 'cut-tile ' + t[0] }, [h('b', { text: t[1] }), h('span', { text: t[2] })])); });
  }

  // --- readout ---------------------------------------------------------------------------------
  function renderReadout() {
    var d = S.d, steps = d.greedy, k = deepest(steps), st = steps[k], b = step0();
    var N = d.guards.naming.n, NH = d.guards.naming.heldout_n, total = d.intact.layers;
    var box = $('readout');
    box.innerHTML = '';
    var active = Object.keys(S.guards).filter(function (g) { return S.guards[g]; });
    var removed = st.removed.slice().sort(function (a, b2) { return a - b2; });
    var big = k === 0 ? 'Nothing can go' : 'Remove ' + k + ' of ' + total + ' layers: ' + listAnd(removed.map(L1));
    if (!active.length) big = 'No checks: nothing stops the cut (' + k + ' layers)';
    box.appendChild(h('div', { class: 'big', text: big }));
    var params = d.intact.params - k * perLayer();
    var cut = measuredCut(st.removed), sav = cut && cut.savings_pct;
    var size = (total - k) + ' layers left · ' + billions(params) + ' parameters (' + signed(-100 * k * perLayer() / d.intact.params) + ')';
    size += sav ? ' · measured: GPU memory ' + signed(sav.mem_gb) + ', time per picture ' + signed(sav.ms_per_item) + ', tokens per second ' + signed(sav.tok_per_s)
      : k ? ' · speed and memory were measured at ' + listAnd(d.pruned.map(function (p) { return String(p.removed.length); })) + ' layers removed' : '';
    box.appendChild(h('p', { text: size }));
    box.appendChild(h('p', { text: 'At this cut: naming ' + st.correct + ' of ' + N + ' pictures (intact ' + b.correct + '), held-out ' + st.heldout_correct + ' of ' + NH +
      ' (intact ' + b.heldout_correct + '), perplexity ' + st.ppl.toFixed(1) + ' (intact ' + b.ppl.toFixed(1) + ').' +
      ' From the search run; a separate run of the same cut can differ by a picture or two.' }));
    var next = steps[k + 1];
    if (next && active.length) {
      var c = checks(next), keep = 1 - S.tol / 100, why = [];
      if (S.guards.naming && !c.naming) why.push('naming falls to ' + next.correct + ' of ' + N + ' (your floor: ' + (keep * b.correct).toFixed(1) + ')');
      if (S.guards.heldout && !c.heldout) why.push('held-out pictures fall to ' + next.heldout_correct + ' of ' + NH + ' (your floor: ' + (keep * b.heldout_correct).toFixed(1) + ')');
      if (S.guards.ppl && !c.ppl) why.push('perplexity rises to ' + next.ppl.toFixed(1) + ' (your ceiling: ' + ((1 + S.pplTol / 100) * b.ppl).toFixed(1) + ')');
      box.appendChild(h('p', { text: 'Why it stops here: removing the next layer (' + L1(next.added) + ') fails your checks: ' + listAnd(why) + '.' }));
    }
    var dflt = defaultDeepest(), warn = k > dflt;
    box.classList.toggle('warn', warn);
    if (warn) {
      var lostList = cut && d.answers_lost && d.answers_lost[cut.name];
      var msg = 'Your tests (5% naming loss, held-out pictures, perplexity +10%) would stop at ' + dflt + ' layers. This cut names ' +
        (b.correct - st.correct > 0 ? (b.correct - st.correct) + ' fewer guard pictures' : 'the guard pictures as well') + ' and ' +
        (b.heldout_correct - st.heldout_correct) + ' fewer held-out pictures.';
      box.appendChild(h('p', { text: msg }));
      if (lostList && lostList.length) {
        box.appendChild(h('p', { class: 'lost', text: 'Lost: ' + lostList.slice(0, 6).map(function (x) {
          return x.word + ' (' + x.lang + ') → “' + x.said + '”';
        }).join(', ') + (lostList.length > 6 ? ', …' : '') }));
      }
      if (lostList && lostList.some(function (x) { return x.lang === 'es' && x.word === 'paraguas' && /umbrella/i.test(x.said); })) {
        box.appendChild(h('p', { text: 'Spanish breaks first: shown the umbrella with a Spanish prompt, the cut model answers in English.' }));
      }
    }
    var on = function (id, v) { var b2 = $(id); if (b2) b2.setAttribute('aria-pressed', String(v)); };
    on('preset-yours', S.guards.naming && S.guards.heldout && S.guards.ppl && S.tol === 5 && S.pplTol === 10);
    on('preset-ppl', !S.guards.naming && !S.guards.heldout && S.guards.ppl && S.pplTol === 10);
  }

  // --- greedy path chart ------------------------------------------------------------------------
  function renderPath() {
    var wrap = $('path-chart'), d = S.d, steps = d.greedy, b = step0();
    var N = d.guards.naming.n, NH = d.guards.naming.heldout_n;
    var W = Math.max(300, wrap.clientWidth), m = { l: 46, r: 16 }, top1 = 22, h1 = W < 520 ? 170 : 210, gap = 46, h2 = W < 520 ? 110 : 130;
    var top2 = top1 + h1 + gap, H = top2 + h2 + 40, n = steps.length - 1;
    var x = function (i) { return m.l + i / n * (W - m.l - m.r); };
    var y1 = function (v) { return top1 + (1 - v) * h1; };
    var pMax = Math.max.apply(null, steps.map(function (st) { return st.ppl; })), pMin = Math.min(40, b.ppl * 0.85);
    pMax = Math.ceil(pMax / 20) * 20;
    var y2 = function (v) { return top2 + (1 - (v - pMin) / (pMax - pMin)) * h2; };
    var k = deepest(steps), keep = 1 - S.tol / 100;
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'img',
      'aria-label': 'Two charts sharing the number of layers removed, 0 to ' + n + '. Top: picture naming on the guard and held-out pictures. Bottom: plain-text perplexity. Your cut is at ' + k + ' layers. The table below lists every value.' });
    // chosen-cut band
    svg.appendChild(s('rect', { x: x(k) - 9, y: top1 - 14, width: 18, height: top2 + h2 - top1 + 14, fill: BLUE, opacity: 0.08, rx: 4 }));
    var overlay = [s('text', { x: Math.min(Math.max(x(k), m.l + 30), W - m.r - 30), y: top1 + h1 - 8, 'text-anchor': 'middle', 'font-size': 11, 'font-weight': 600, fill: BLUE, stroke: '#FFFFFF', 'stroke-width': 4, 'paint-order': 'stroke', 'pointer-events': 'none' }, 'your cut')];
    // panel 1 grid
    [0, 0.25, 0.5, 0.75, 1].forEach(function (t) {
      svg.appendChild(s('line', { x1: m.l, x2: W - m.r, y1: y1(t), y2: y1(t), stroke: GRID }));
      svg.appendChild(s('text', { x: m.l - 6, y: y1(t) + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#4B5563' }, Math.round(t * 100) + '%'));
    });
    svg.appendChild(s('text', { x: m.l, y: top1 - 8 - 6, 'font-size': 12, 'font-weight': 600, fill: '#111827' }, 'Picture naming, % correct'));
    // panel 2 grid
    var pt = [];
    for (var v = Math.ceil(pMin / 20) * 20; v <= pMax; v += 20) pt.push(v);
    pt.forEach(function (t) {
      svg.appendChild(s('line', { x1: m.l, x2: W - m.r, y1: y2(t), y2: y2(t), stroke: GRID }));
      svg.appendChild(s('text', { x: m.l - 6, y: y2(t) + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#4B5563' }, String(t)));
    });
    svg.appendChild(s('text', { x: m.l, y: top2 - 12, 'font-size': 12, 'font-weight': 600, fill: '#111827' }, 'Perplexity on plain text (lower is better)'));
    // x axis
    for (var i = 0; i <= n; i++) {
      if (W < 520 && i % 2) continue;
      svg.appendChild(s('text', { x: x(i), y: top2 + h2 + 16, 'text-anchor': 'middle', 'font-size': 11, fill: '#4B5563' }, String(i)));
    }
    svg.appendChild(s('text', { x: m.l + (W - m.l - m.r) / 2, y: H - 4, 'text-anchor': 'middle', 'font-size': 12, fill: '#374151' }, 'Layers removed (greedy path, one at a time)'));
    svg.appendChild(s('line', { x1: m.l, x2: W - m.r, y1: top1 + h1, y2: top1 + h1, stroke: AXIS }));
    svg.appendChild(s('line', { x1: m.l, x2: W - m.r, y1: top2 + h2, y2: top2 + h2, stroke: AXIS }));
    // guard lines
    if (S.guards.naming || S.guards.heldout) {
      var fy = y1(keep * b.correct / N);
      svg.appendChild(s('line', { x1: m.l, x2: W - m.r, y1: fy, y2: fy, stroke: GUARD, 'stroke-width': 1.5 }));
      overlay.push(s('text', { x: W - m.r, y: fy + 14, 'text-anchor': 'end', 'font-size': 11, fill: GUARD, stroke: '#FFFFFF', 'stroke-width': 4, 'paint-order': 'stroke', 'pointer-events': 'none' }, 'your floor (−' + S.tol + '%)'));
    }
    if (S.guards.ppl) {
      var cy = y2((1 + S.pplTol / 100) * b.ppl);
      if (cy > top2 - 4) {
        svg.appendChild(s('line', { x1: m.l, x2: W - m.r, y1: cy, y2: cy, stroke: GUARD, 'stroke-width': 1.5 }));
        overlay.push(s('text', { x: W - m.r, y: cy + 14, 'text-anchor': 'end', 'font-size': 11, fill: GUARD, stroke: '#FFFFFF', 'stroke-width': 4, 'paint-order': 'stroke', 'pointer-events': 'none' }, 'your ceiling (+' + S.pplTol + '%)'));
      }
    }
    function line(vals, yf, color, on, okKey) {
      var pts = vals.map(function (v2, j) { return x(j).toFixed(1) + ',' + yf(v2).toFixed(1); }).join(' ');
      svg.appendChild(s('polyline', { points: pts, fill: 'none', stroke: color, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round', opacity: on ? 1 : 0.35 }));
      vals.forEach(function (v2, j) {
        var ok = checks(steps[j])[okKey];
        svg.appendChild(s('circle', { cx: x(j), cy: yf(v2), r: 4, fill: ok || !on ? color : '#FFFFFF', stroke: ok || !on ? '#FFFFFF' : color, 'stroke-width': 2, opacity: on ? 1 : 0.35 }));
      });
    }
    line(steps.map(function (st) { return st.heldout_correct / NH; }), y1, TEAL, S.guards.heldout, 'heldout');
    line(steps.map(function (st) { return st.correct / N; }), y1, BLUE, S.guards.naming, 'naming');
    line(steps.map(function (st) { return st.ppl; }), y2, INK2, S.guards.ppl, 'ppl');
    overlay.forEach(function (el) { svg.appendChild(el); });
    // crosshair
    var cross = s('line', { x1: 0, x2: 0, y1: top1 - 4, y2: top2 + h2, stroke: '#111827', 'stroke-width': 1, opacity: 0 });
    svg.appendChild(cross);
    var hit = s('rect', { x: m.l - 10, y: top1 - 10, width: W - m.l - m.r + 20, height: top2 + h2 - top1 + 10, fill: 'transparent' });
    svg.appendChild(hit);
    var tip = wrap.querySelector('.cut-tip') || h('div', { class: 'cut-tip' });
    tip.hidden = true;
    hit.addEventListener('pointermove', function (e) {
      var r = svg.getBoundingClientRect(), px = (e.clientX - r.left) * W / r.width;
      var j = Math.max(0, Math.min(n, Math.round((px - m.l) / (W - m.l - m.r) * n))), st = steps[j];
      cross.setAttribute('x1', x(j)); cross.setAttribute('x2', x(j)); cross.setAttribute('opacity', 0.35);
      tip.innerHTML = '';
      var key = function (color) { var k2 = h('span', { class: 'key' }); k2.style.background = color; return k2; };
      tip.appendChild(h('b', { text: j === 0 ? 'Intact (52 layers)' : j + ' removed (+ layer ' + L1(st.added) + ')' }));
      tip.appendChild(h('div', null, [key(BLUE), st.correct + ' of ' + N + ' named']));
      tip.appendChild(h('div', null, [key(TEAL), st.heldout_correct + ' of ' + NH + ' held-out']));
      tip.appendChild(h('div', null, [key(INK2), 'perplexity ' + st.ppl.toFixed(1)]));
      tip.appendChild(h('div', { text: passes(st) ? 'passes your checks' : 'fails your checks' }));
      tip.hidden = false;
      var wr = wrap.getBoundingClientRect(), lx = e.clientX - wr.left + 14, ly = e.clientY - wr.top + 10;
      if (lx + tip.offsetWidth > wr.width) lx = e.clientX - wr.left - tip.offsetWidth - 14;
      tip.style.left = Math.max(0, lx) + 'px';
      tip.style.top = Math.max(0, Math.min(ly, wr.height - tip.offsetHeight)) + 'px';
    });
    hit.addEventListener('pointerleave', function () { tip.hidden = true; cross.setAttribute('opacity', 0); });
    wrap.innerHTML = '';
    wrap.appendChild(svg);
    wrap.appendChild(tip);
  }
  function renderPathLegend() {
    var box = $('path-legend');
    box.innerHTML = '';
    var item = function (color, text, cls) { var i = h('i', { class: cls || '' }); i.style.background = color; return h('span', null, [i, text]); };
    box.appendChild(item(BLUE, 'Guard pictures (' + S.d.guards.naming.n + ', English and Spanish)'));
    box.appendChild(item(TEAL, 'Held-out pictures (' + S.d.guards.naming.heldout_n + ', same words, new drawings)'));
    box.appendChild(item(INK2, 'Perplexity on ' + S.d.guards.text.sentences + ' plain sentences'));
    box.appendChild(item(GUARD, 'Your limits'));
    box.appendChild(h('span', { text: 'Hollow dot: fails that check' }));
  }
  function renderPathTable() {
    var t = $('path-table'), d = S.d, k = deepest(d.greedy);
    t.innerHTML = '';
    t.appendChild(h('thead', null, h('tr', null, [h('th', { class: 'num', text: 'Removed' }), h('th', { class: 'num', text: 'Layer added' }),
      h('th', { class: 'num', text: 'Naming (' + d.guards.naming.n + ')' }), h('th', { class: 'num', text: 'Held-out (' + d.guards.naming.heldout_n + ')' }),
      h('th', { class: 'num', text: 'Perplexity' }), h('th', { text: 'Your checks' })])));
    var tb = h('tbody');
    d.greedy.forEach(function (st, i) {
      tb.appendChild(h('tr', { class: i === k ? 'chosen' : null }, [h('td', { class: 'num', text: String(i) }), h('td', { class: 'num', text: st.added == null ? '–' : L1(st.added) }),
        h('td', { class: 'num', text: String(st.correct) }), h('td', { class: 'num', text: String(st.heldout_correct) }), h('td', { class: 'num', text: st.ppl.toFixed(1) }),
        h('td', { text: passes(st) ? 'pass' : 'fail' })]));
    });
    t.appendChild(tb);
  }

  // --- layer strip -------------------------------------------------------------------------------
  var MEASURES = {
    naming: { value: function (l) { return Math.max(0, Math.round(-l.skip_d_acc * S.d.guards.naming.n)); }, cuts: [1, 2, 3, 6],
      labels: ['none', '1', '2', '3–5', '6+ pictures'],
      lede: 'Color: how many of the guard pictures Glimmer gets wrong when this one layer is skipped. Dot: a full-attention layer (the others attend only to nearby words). Ringed: the layers in your cut.' },
    ppl: { value: function (l) { return Math.max(0, l.skip_d_ppl_rel * 100); }, cuts: [2, 5, 15, 40],
      labels: ['under 2%', '2–5%', '5–15%', '15–40%', '40%+'],
      lede: 'Color: how much plain-text perplexity rises when this one layer is skipped. Dot: a full-attention layer. Ringed: your cut.' },
    bi: { value: function (l) { return l.block_influence; }, cuts: [0.12, 0.15, 0.2, 0.25],
      labels: ['under 0.12', '0.12–0.15', '0.15–0.20', '0.20–0.25', '0.25+'],
      lede: 'Color: block influence, a popular shortcut that scores each layer without running any test (how much the layer changes what passes through it). Compare it with the other two views: it points at different layers.' }
  };
  function bin(m, v) { var i = 0; while (i < m.cuts.length && v >= m.cuts[i] - 1e-9) i++; return i; }
  function layerText(l) {
    var d = S.d, b = d.intact, N = d.guards.naming.n, lost = Math.round(-l.skip_d_acc * N);
    var type = l.type === 'full_attention' ? 'full attention' : 'sliding window';
    var naming = lost > 0 ? 'naming falls from ' + b.correct + ' to ' + (b.correct - lost) + ' of ' + N + ' (English ' + Math.round(l.acc_en * d.guards.naming.n_en) + '/' + d.guards.naming.n_en +
      ', Spanish ' + Math.round(l.acc_es * d.guards.naming.n_es) + '/' + d.guards.naming.n_es + ')' : lost < 0 ? 'naming gains ' + (-lost) + ' picture' : 'naming is unchanged';
    return 'Layer ' + L1(l.layer) + ' (' + type + '), skipped alone: ' + naming + '; perplexity ' + b.ppl.toFixed(1) + ' → ' + l.ppl.toFixed(1) + ' (' + signed(l.skip_d_ppl_rel * 100) +
      '); shortcut score ' + l.block_influence.toFixed(2) + '.';
  }
  function renderStrip() {
    var d = S.d, m = MEASURES[S.measure], box = $('strip');
    var removed = d.greedy[deepest(d.greedy)].removed;
    document.querySelectorAll('#measure-seg button').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-measure') === S.measure)); });
    $('strip-lede').textContent = m.lede;
    box.innerHTML = '';
    d.layers.forEach(function (l) {
      var bi = bin(m, m.value(l));
      var cell = h('button', { type: 'button', class: 'cut-cell' + (bi >= 3 ? ' dark' : '') + (l.type === 'full_attention' ? ' full' : '') +
        (removed.indexOf(l.layer) >= 0 ? ' removed' : ''), 'aria-pressed': String(S.selected === l.layer), 'aria-label': layerText(l), text: L1(l.layer) });
      cell.style.background = RAMP[bi];
      cell.addEventListener('click', function () { S.selected = S.selected === l.layer ? null : l.layer; renderStrip(); });
      cell.addEventListener('mouseenter', function () { $('layer-detail').textContent = layerText(l); });
      cell.addEventListener('focus', function () { $('layer-detail').textContent = layerText(l); });
      box.appendChild(cell);
    });
    var sel = d.layers.filter(function (l) { return l.layer === S.selected; })[0];
    $('layer-detail').textContent = sel ? layerText(sel) : 'Select a layer for its numbers.';
    var leg = $('strip-legend');
    leg.innerHTML = '';
    var ramp = h('span', { class: 'ramp' });
    RAMP.forEach(function (c, i) { var sw = h('i', { title: m.labels[i] }); sw.style.background = c; ramp.appendChild(sw); });
    leg.appendChild(h('span', null, [m.labels[0] + ' ', ramp, ' ' + m.labels[m.labels.length - 1]]));
    leg.appendChild(h('span', null, [h('span', { class: 'dot' }), 'full attention']));
    leg.appendChild(h('span', null, [h('span', { class: 'ring' }), 'in your cut']));
  }
  function renderFindings() {
    var d = S.d, b = d.intact, l0 = d.layers[0], N = d.guards.naming.n;
    var lostEn = Math.round((b.acc_en - l0.acc_en) * d.guards.naming.n_en), lostEs = Math.round((b.acc_es - l0.acc_es) * d.guards.naming.n_es);
    var ft = d.by_type.full_attention, sw = d.by_type.sliding_attention, bv = d.block_influence_vs_skip;
    var box = $('findings');
    box.innerHTML = '';
    [['Layer 1 is critical', 'Skipped alone, the first layer loses ' + Math.round(-l0.skip_d_acc * N) + ' of ' + N + ' pictures (' + lostEs + ' Spanish, ' + lostEn + ' English) and perplexity rises ' +
       signed(l0.skip_d_ppl_rel * 100, 0) + '.'],
     ['Full attention is not special', 'Skipping one of the ' + ft.n + ' full-attention layers cost a picture for ' + ft.layers_losing_naming + ' of them; for the ' + sw.n +
       ' sliding-window layers, ' + sw.layers_losing_naming + '. About the same share.'],
     ['The shortcut ranked layers poorly', 'Block influence barely tracked what skipping a layer really costs: rank correlation ' + bv.spearman_bi_answer_vs_acc_loss.toFixed(2) +
       ' with lost pictures and ' + bv.spearman_bi_answer_vs_d_ppl.toFixed(2) + ' with the perplexity rise. Measure with your own tests.']
    ].forEach(function (f) { box.appendChild(h('div', { class: 'cut-finding' }, [h('b', { text: f[0] }), f[1]])); });
  }

  // --- real deletion -------------------------------------------------------------------------------
  function renderReal() {
    var d = S.d, t = $('real-table'), base = d.pruned[0], N = d.guards.naming.n, NH = d.guards.naming.heldout_n;
    t.innerHTML = '';
    var cols = ['Cut', 'Layers removed', 'Parameters', 'GPU memory', 'Per picture', 'Tokens/s', 'Naming (' + N + ')', 'Held-out (' + NH + ')', 'Perplexity', 'Real deletion'];
    t.appendChild(h('thead', null, h('tr', null, cols.map(function (c, i) { return h('th', { class: i >= 2 && i <= 8 ? 'num' : null, text: c }); }))));
    var tb = h('tbody'), allMatch = true;
    var cell = function (v, delta) { return h('td', { class: 'num' }, [v, delta != null && delta !== '' ? h('span', { class: 'delta', text: delta }) : null]); };
    var safe = measuredCut(d.greedy[defaultDeepest()].removed);
    d.pruned.forEach(function (p) {
      var sp = p.savings_pct || {}, intact = p.name === 'intact';
      var ok = intact || (p.check && p.check.same_answers_all_pictures && p.check.max_abs_logit_diff === 0);
      allMatch = allMatch && ok;
      tb.appendChild(h('tr', { class: safe && p.name === safe.name ? 'row-best' : null }, [
        h('td', { text: CUT_NAMES[p.name] || p.name }),
        h('td', { text: p.removed.length ? p.removed.length + ': ' + p.removed.map(L1).join(', ') : 'none' }),
        cell(billions(p.params), intact ? '' : signed(sp.params)),
        cell(p.mem_gb.toFixed(2) + ' GiB', intact ? '' : signed(sp.mem_gb)),
        cell(Math.round(p.ms_per_item) + ' ms', intact ? '' : signed(sp.ms_per_item)),
        cell(p.tok_per_s.toFixed(1), intact ? '' : signed(sp.tok_per_s)),
        cell(String(p.correct)),
        cell(String(Math.round(p.heldout_acc * NH))),
        cell(p.ppl.toFixed(1)),
        h('td', { class: 'check-cell', text: intact ? '' : ok ? '✓ matches' : 'differs' })
      ]));
    });
    t.appendChild(tb);
    var badge = $('real-badge');
    if (allMatch) { badge.textContent = '✓ Real deletion matches the skip version'; badge.hidden = false; }
    var r = d.reload, notes = [];
    notes.push('“Matches”: the deleted model gives the same answers on all ' + N + ' pictures as the reversible skip, and the same scores (largest difference 0.0) on spot checks.');
    if (r) notes.push('The ' + r.layers + '-layer model was saved and reloaded with the stock model code: identical logits, ' + r.checkpoint_gb + ' GB on disk, loaded in ' + r.load_seconds + ' s.');
    notes.push('Speed: one L40S, FP8, medians of ' + (base.speed_rounds || 3) + ' rounds. Held-out pictures were never used to choose a cut.');
    $('real-note').textContent = notes.join(' ');
  }
  function renderLimits() {
    var ul = $('limits');
    ul.innerHTML = '';
    (S.d.limits || []).forEach(function (l) { ul.appendChild(h('li', { text: l })); });
    $('source-note').textContent = (S.d.source === 'run' ? 'Results: this server’s run folder (compress/glimmer.json). ' : 'Results: the copy shipped with the app (web/data/cut_glimmer.json). ') +
      S.d.model + ', ' + S.d.precision + ', ' + S.d.hardware + '.';
  }

  // --- wiring ------------------------------------------------------------------------------------
  function update() {
    $('tol-out').textContent = S.tol + '%';
    $('ppl-out').textContent = S.pplTol + '%';
    $('tol').value = S.tol;
    $('ppl-tol').value = S.pplTol;
    $('g-naming').checked = S.guards.naming;
    $('g-heldout').checked = S.guards.heldout;
    $('g-ppl').checked = S.guards.ppl;
    renderReadout();
    renderPath();
    renderPathTable();
    renderStrip();
  }
  function set(opts) {
    if (opts.tol != null) S.tol = +opts.tol;
    if (opts.pplTol != null) S.pplTol = +opts.pplTol;
    if (opts.guards) S.guards = Object.assign({}, S.guards, opts.guards);
    if (S.d) update();
  }
  function bind() {
    $('tol').addEventListener('input', function (e) { set({ tol: e.target.value }); });
    $('ppl-tol').addEventListener('input', function (e) { set({ pplTol: e.target.value }); });
    ['naming', 'heldout', 'ppl'].forEach(function (g) {
      $('g-' + g).addEventListener('change', function (e) { var o = {}; o[g] = e.target.checked; set({ guards: o }); });
    });
    $('preset-yours').addEventListener('click', function () { set({ tol: 5, pplTol: 10, guards: { naming: true, heldout: true, ppl: true } }); });
    $('preset-ppl').addEventListener('click', function () { set({ pplTol: 10, guards: { naming: false, heldout: false, ppl: true } }); });
    document.querySelectorAll('#measure-seg button').forEach(function (b) {
      b.addEventListener('click', function () { S.measure = b.getAttribute('data-measure'); renderStrip(); });
    });
    var lastW = window.innerWidth, timer = null;
    window.addEventListener('resize', function () {
      if (window.innerWidth === lastW) return;
      lastW = window.innerWidth;
      clearTimeout(timer);
      timer = setTimeout(function () { if (S.d) renderPath(); }, 120);
    });
  }

  bind();
  T.api('/api/lab/cut').then(function (d) {
    S.d = d;
    renderTiles();
    renderPathLegend();
    renderFindings();
    renderReal();
    renderLimits();
    update();
    readyResolve();
  }).catch(function (e) {
    var el = $('load-error');
    el.textContent = 'Couldn’t load the layer-removal results: ' + e.message;
    el.hidden = false;
    readyResolve();
  });

  T.cut = { ready: ready, set: set, deepest: function () { return S.d ? deepest(S.d.greedy) : null; }, state: function () { return S; } };
})();
