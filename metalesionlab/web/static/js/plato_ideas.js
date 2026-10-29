/* The invisible Forms: Muse Image's 16 drawings of God first, then the eleven ideas, the emblem bars, ideas against
   things in spread, links to draw one, and the method. Data: /api/plato/ideas (statistics, labels and sprite
   layouts only); no API calls, nothing stored. There are no people's drawings of these ideas: every number here
   is about the AI, apart from the cited study of children's drawings of god (context, not a comparison). */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var NS = 'http://www.w3.org/2000/svg';
  // the site's colour tokens (app.css), so a theme switch recolours the charts
  var C = { muse: 'var(--blue)', muse2: 'var(--blue-mid)', thing: 'var(--faint)', people: 'var(--orange)', ink: 'var(--ink)', ink2: 'var(--ink-2)',
            muted: 'var(--faint)', grid: 'var(--line)', surface: 'var(--chart-halo)', none: 'var(--line-2)' };
  var D = null, BY = {};

  function $(id) { return document.getElementById(id); }
  function f2(x) { return x == null ? '–' : Number(x).toFixed(2); }
  function sgn(x) { return (x >= 0 ? '+' : '−') + Math.abs(x).toFixed(2); }
  function ci(c) { return c ? f2(c[0]) + '–' + f2(c[1]) : ''; }
  function ciS(c) { return c ? sgn(c[0]) + ' to ' + sgn(c[1]) : ''; }
  function pct(x) { return Math.round(x * 100); }
  function s(tag, attrs, kids) {
    var el = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) el.setAttribute(k, attrs[k]); });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c == null) return;
      el.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return el;
  }
  // One drawing out of a sprite sheet (cols per row, n in all), as a square div.
  function cell(sp, i) {
    var cols = sp.cols, rows = Math.ceil(sp.n / cols), col = i % cols, row = Math.floor(i / cols);
    var el = h('div', { class: 'iv-cell' });
    el.style.backgroundImage = 'url("' + sp.src + '")';
    el.style.backgroundSize = (cols * 100) + '% ' + (rows * 100) + '%';
    el.style.backgroundPosition = (cols > 1 ? col / (cols - 1) * 100 : 0) + '% ' + (rows > 1 ? row / (rows - 1) * 100 : 0) + '%';
    return el;
  }
  function tipIn(wrap) {
    var tip = wrap.querySelector('.iv-tip');
    if (!tip) { tip = h('div', { class: 'iv-tip', role: 'presentation' }); tip.hidden = true; wrap.appendChild(tip); }
    return tip;
  }
  function showTip(wrap, px, py, title, lines) {
    var tip = tipIn(wrap);
    tip.textContent = '';
    tip.appendChild(h('b', { text: title }));
    lines.forEach(function (l) { tip.appendChild(h('div', { text: l })); });
    tip.hidden = false;
    var w = wrap.clientWidth, left = px + 14;
    if (left + tip.offsetWidth > w) left = Math.max(0, px - tip.offsetWidth - 14);
    tip.style.left = left + 'px';
    tip.style.top = (py + 12) + 'px';
  }
  function hideTip(wrap) { var t = wrap.querySelector('.iv-tip'); if (t) t.hidden = true; }
  function nOf(k, n) { return k === n ? 'all ' + n : k + ' of ' + n; }

  // --- hero: God first ----------------------------------------------------------------------
  function hero() {
    var g = BY.god, S = D.summary, n = g.n, h1 = S.H1, h3 = S.H3_vs_atlas;
    $('answer').textContent = 'Asked to draw God, Meta’s Muse Image drew the same figure ' + nOf(g.top.n, n) +
      ' times: a bearded man with long hair, a robe and a halo, as in Western religious art.';
    var grid = $('god-grid');
    grid.textContent = '';
    for (var i = 0; i < n; i++) grid.appendChild(cell(g.sprite, i));
    $('god-cap').textContent = 'Muse Image’s ' + n + ' drawings of God, in the order they came. One prompt each time: “' + g.prompt +
      '” ' + (g.refused ? g.refused + ' calls were refused.' : 'None was refused.') + ' The page describes what the model drew; it makes no claim about God.';
    var all = D.ideas.filter(function (x) { return x.top.n === x.n; });
    var tiles = $('tiles');
    tiles.textContent = '';
    [[g.top.n + ' of ' + n, 'drawings of God show a bearded man with a halo', 'Muse Glimmer and our check by eye agree on all ' + n],
     [h1.ideas_with_concentration_at_least_half + ' of ' + h1.of, 'ideas drawn as one emblem at least half the time',
      'pre-registered: at least 7 · passed'],
     [all.length + ' of ' + D.ideas.length, 'ideas drawn as the same emblem every time',
      all.map(function (x) { return x.label; }).join(', ')],
     [f2(h3.median_ideas) + ' vs ' + f2(h3.median_things), 'median spread: ideas against 135 everyday things',
      'difference ' + sgn(h3.difference) + ', 95% CI ' + ciS(h3.difference_ci95) + ' · pre-registered “more varied” failed', 'fail']
    ].forEach(function (t) {
      tiles.appendChild(h('div', { class: 'iv-tile' + (t[3] ? ' ' + t[3] : '') }, [h('b', { text: t[0] }), h('span', { text: t[1] }), h('small', { text: t[2] })]));
    });
  }

  // --- how people picture God: the cited study beside Muse ------------------------------------
  function people() {
    var L = D.lausanne, g = BY.god, hl = (g.human_like && g.human_like.glimmer) || 0;
    var box = $('compare');
    box.textContent = '';
    box.appendChild(h('h3', { text: 'A human figure, in drawings of god' }));
    [[C.people, 'Children, Swiss sample (' + L.n + ', ages ' + L.ages + ')', (L.anthropomorphic_share * 100).toFixed(1) + '% of god figures', L.anthropomorphic_share],
     [C.muse, 'Muse Image, plain doodle prompt', Math.round(hl * g.n) + ' of ' + g.n + ' drawings', hl]
    ].forEach(function (r) {
      var bar = h('div', { class: 'iv-cmp-bar' }, h('i', { style: { width: (100 * r[3]) + '%', background: r[0] } }));
      box.appendChild(h('div', { class: 'iv-cmp' }, [h('div', { class: 'iv-cmp-top' }, [h('span', { text: r[1] }), h('b', { text: r[2] })]), bar]));
    });
    box.appendChild(h('p', { class: 'iv-cmp-note', text: 'Muse’s figure has a halo in all ' + g.n + ', one of the marks the study describes ' +
      'children adding, more often as they grow older, to show a figure is more than human. Different tasks and different drawings: shown ' +
      'side by side for context, not tested.' }));
  }

  // --- eleven ideas -----------------------------------------------------------------------------
  function grid() {
    var box = $('grid');
    box.textContent = '';
    D.ideas.forEach(function (x) {
      var strip = h('div', { class: 'iv-strip', role: 'img', 'aria-label': 'Muse Image’s ' + x.n + ' drawings of ' + x.phrase + ': mostly ' + x.top.emblem });
      for (var i = 0; i < x.n; i++) strip.appendChild(cell(x.sprite, i));
      box.appendChild(h('article', { class: 'iv-card' + (x.key === 'god' ? ' is-god' : '') }, [
        h('div', { class: 'iv-card-head' }, [h('b', { text: x.label }), h('span', { text: 'spread ' + f2(x.spread) })]),
        strip,
        h('p', { class: 'iv-card-top' }, [h('b', { text: x.top.emblem }), document.createTextNode(' in ' + x.top.n + ' of ' + x.n),
          h('small', { text: 'spread ' + f2(x.spread) + ' (95% CI ' + ci(x.spread_ci95) + ')' })])
      ]));
    });
  }

  // --- emblem bars ---------------------------------------------------------------------------
  function bars() {
    var S = D.summary, h1 = S.H1, h2 = S.H2, lc = S.label_check;
    var missed = D.ideas.filter(function (x) { return x.top.short !== x.predicted_short; })
      .map(function (x) { return x.label + ' as ' + x.top.emblem + ', not ' + x.predicted; });
    $('emblems-lede').textContent = 'Before the main run we predicted that for at least 7 of the 11 ideas one emblem would fill at least half ' +
      'the drawings. It did for ' + h1.ideas_with_concentration_at_least_half + ' of ' + h1.of + ' (the median idea’s top emblem: ' +
      pct(h1.median_concentration) + '% of its drawings, 95% CI ' + pct(h1.median_concentration_ci95[0]) + '–' + pct(h1.median_concentration_ci95[1]) +
      '%). We also predicted which emblem, and needed at least 6 right. We got ' + h2.predicted_emblem_on_top + ' of ' + h2.of +
      ', so that prediction failed. Muse drew ' + missed.join('; ') + '.';
    var legend = $('emblem-legend');
    legend.textContent = '';
    [['top emblem', C.muse], ['other emblems', C.muse2], ['something else, or no clear symbol', C.none]].forEach(function (l) {
      legend.appendChild(h('span', null, [h('i', { style: { background: l[1] } }), l[0]]));
    });
    legend.appendChild(h('span', null, [h('i', { class: 'line', style: { background: C.ink2 } }), 'half the drawings (8 of 16)']));
    var box = $('bars');
    box.textContent = '';
    var order = D.ideas.slice().sort(function (a, b) {  // most concentrated first; God leads its tie
      return b.top.share - a.top.share || (b.key === 'god') - (a.key === 'god') || a.spread - b.spread;
    });
    order.forEach(function (x) {
      var bar = h('div', { class: 'iv-bar', role: 'img', 'aria-label': x.label + ': ' + x.emblem_counts.map(function (e) { return e[0] + ' ' + e[1]; }).join(', ') });
      x.emblem_counts.forEach(function (e, i) {
        var none = e[0] === 'something else' || e[0] === 'can\'t tell';
        var name = e[0] === 'can\'t tell' ? 'no clear symbol' : e[0];
        var seg = h('span', { class: i === 0 && !none ? 'top' : none ? 'none' : 'other', tabindex: '0',
          'aria-label': name + ': ' + e[1] + ' of ' + x.n });
        seg.style.flex = e[1] + ' 1 0';
        function show() {
          var r = seg.getBoundingClientRect(), w = box.getBoundingClientRect();
          showTip(box, r.left - w.left + r.width / 2, r.bottom - w.top, x.label, [name + ': ' + e[1] + ' of ' + x.n]);
        }
        seg.addEventListener('pointerenter', show);
        seg.addEventListener('focus', show);
        seg.addEventListener('pointerleave', function () { hideTip(box); });
        seg.addEventListener('blur', function () { hideTip(box); });
        bar.appendChild(seg);
      });
      bar.appendChild(h('i', { class: 'iv-bar-half', 'aria-hidden': 'true' }));
      var hit = x.top.short === x.predicted_short;
      box.appendChild(h('div', { class: 'iv-bar-row' }, [
        h('span', { class: 'iv-bar-name', text: x.label }), bar,
        h('span', { class: 'iv-bar-label' }, [h('b', { text: x.top.emblem }), document.createTextNode(' ' + x.top.n + ' of ' + x.n),
          h('small', { text: hit ? 'as predicted' : 'predicted: ' + x.predicted })])
      ]));
    });
    $('bars-cap').textContent = 'Labels: Muse Glimmer 30B. Our labels by eye, made before seeing Glimmer’s, agreed on ' + pct(lc.agreement) +
      '% of the ' + lc.pictures + ' drawings (Cohen’s kappa ' + f2(lc.kappa) + ') and on the top emblem for ' + lc.same_top_emblem + ' of ' + lc.of +
      ' ideas. The exception is freedom: Glimmer chose broken chains, we chose the bird, and every drawing of freedom has both. By eye, ' +
      lc.by_eye_H2 + ' of ' + lc.of + ' top emblems were the predicted ones. Glimmer read some of the soul’s ghostly figures as jellyfish.';
    var t = $('emblem-table');
    t.textContent = '';
    t.appendChild(h('thead', null, h('tr', null, ['Idea', 'Top emblem (Glimmer)', 'Share, 95% CI', 'Top emblem by eye', 'Labels agree', 'Predicted',
      'Spread, 95% CI'].map(function (c, i) { return h('th', { class: i === 2 || i === 4 || i === 6 ? 'n' : null, text: c }); }))));
    t.appendChild(h('tbody', null, D.ideas.map(function (x) {
      return h('tr', null, [h('td', { text: x.label }), h('td', { text: x.top.emblem + ' (' + x.top.n + '/' + x.n + ')' }),
        h('td', { class: 'n', text: pct(x.top.share) + '% (' + pct(x.top.share_ci95[0]) + '–' + pct(x.top.share_ci95[1]) + '%)' }),
        h('td', { text: x.by_eye.top + ' (' + x.by_eye.n + '/' + x.n + ')' }), h('td', { class: 'n', text: pct(x.agreement) + '%' }),
        h('td', { text: x.predicted }), h('td', { class: 'n', text: f2(x.spread) + ' (' + ci(x.spread_ci95) + ')' })]);
    })));
  }

  // --- ideas against things ------------------------------------------------------------------
  function spreadText() {
    var a = D.summary.H3_vs_atlas, p = D.summary.H3_vs_pad, e1 = D.summary.E1_concentration_vs_spread;
    var chair = D.things.filter(function (t) { return t.key === 'chair'; })[0];
    var top = D.ideas.slice().sort(function (x, y) { return y.spread - x.spread; });
    var maxThing = Math.max.apply(null, D.things.map(function (t) { return t.spread; }));
    var over = top.filter(function (x) { return x.spread > maxThing; }).map(function (x) { return x.label; });
    $('spread-lede').textContent = 'We predicted that ideas would be more spread out than things, because an emblem can be drawn in many ways and ' +
      'with company. Not clearly. The median idea’s spread is ' + f2(a.median_ideas) + ' (95% CI ' + ci(a.median_ideas_ci95) + '), against ' +
      f2(a.median_things) + ' for ' + a.n_things + ' everyday things (CI ' + ci(a.median_things_ci95) + '). The difference, ' + sgn(a.difference) +
      ', has a CI of ' + ciS(a.difference_ci95) + ', so the pre-registered test failed. Against the draw pad’s ' + p.n_things +
      ' things, which are among Muse’s most uniform (median ' + f2(p.median_things) + '), ideas are more spread out (' + sgn(p.difference) +
      ', CI ' + ciS(p.difference_ci95) + ').';
    var overText = over.join(' and ').replace(/^./, function (ch) { return ch.toUpperCase(); });
    $('spread-cap').textContent = (over.length ? overText + (over.length > 1 ? ' are' : ' is') + ' more spread out than any of the ' +
      a.n_things + ' things: truth mixes scales, an eye, a light and a mirror, and freedom’s bird and chains come in many arrangements. ' : '') +
      'Love (' + f2(BY.love.spread) + ') is about as uniform as Muse’s chair' + (chair ? ' (' + f2(chair.spread) + ')' : '') + '. Across the 11 ideas, ' +
      'the more one emblem dominates, the less spread out the drawings (rank correlation ' + f2(e1.rho).replace('-', '−') + ', 95% CI ' + ciS(e1.ci95) +
      '; exploratory). Spread is DINOv2’s distance, which sees drawing style as well as content. Hover a dot for its name.';
  }
  // One row per idea (its spread and 95% CI) under a strip of the 135 things; dashed lines mark both medians.
  function spreadChart() {
    var wrap = $('spread-chart');
    wrap.textContent = '';
    var W = Math.max(300, wrap.clientWidth || 800), narrow = W < 560;
    var a = D.summary.H3_vs_atlas, ideas = D.ideas.slice().sort(function (p, q) { return p.spread - q.spread; });
    var L = narrow ? 92 : 190, R = 18, top = 46, stripH = narrow ? 70 : 84, rowH = narrow ? 26 : 30;
    var H = top + stripH + rowH * ideas.length + 56;
    var hiCI = Math.max.apply(null, ideas.map(function (p) { return p.spread_ci95[1]; }));
    var xmax = Math.max(0.5, Math.ceil(hiCI * 10) / 10);
    var x = function (v) { return L + (W - L - R) * v / xmax; };
    var yAxis = H - 30;
    var root = s('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img',
      'aria-label': 'Spread of Muse Image’s drawings. ' + D.things.length + ' everyday things: median ' + f2(a.median_things) +
        '. 11 ideas: median ' + f2(a.median_ideas) + '. ' + ideas.map(function (p) { return p.label + ' ' + f2(p.spread); }).join(', ') });
    var step = xmax > 0.6 ? 0.2 : 0.1;
    for (var t = 0; t <= xmax + 1e-9; t += step) {
      root.appendChild(s('line', { x1: x(t), x2: x(t), y1: top - 6, y2: yAxis, stroke: C.grid, 'stroke-width': 1 }));
      root.appendChild(s('text', { class: 'tick', x: x(t), y: yAxis + 18, 'text-anchor': t === 0 ? 'start' : 'middle' }, f2(t)));
    }
    root.appendChild(s('text', { class: 'lbl', x: W - R, y: H - 2, 'text-anchor': 'end' },
      narrow ? 'spread →' : 'spread: how different two drawings look, on average →'));
    var hits = [];
    // the things: a jittered strip
    var cy0 = top + stripH / 2 - 6;
    root.appendChild(s('text', { class: 'lbl-b', x: 8, y: cy0 - 2 }, narrow ? D.things.length + ' things' : D.things.length + ' everyday things'));
    root.appendChild(s('text', { class: 'lbl', x: 8, y: cy0 + 15 }, 'median ' + f2(a.median_things)));
    D.things.slice().sort(function (p, q) { return p.spread - q.spread; }).forEach(function (it, i) {
      var cx = x(it.spread), cy = cy0 + ((i * 37) % 11 - 5) * (narrow ? 2.6 : 3.4);
      root.appendChild(s('circle', { cx: cx, cy: cy, r: narrow ? 3.5 : 4.5, fill: C.thing, 'fill-opacity': 0.8, stroke: C.surface, 'stroke-width': 1 }));
      hits.push({ x: cx, y: cy, name: it.label, lines: ['everyday thing · spread ' + f2(it.spread)] });
    });
    // the ideas: one row each, a CI whisker and a dot
    var y1 = top + stripH;
    ideas.forEach(function (p, i) {
      var cy = y1 + rowH * i + rowH / 2, cx = x(p.spread);
      root.appendChild(s('text', { class: p.key === 'god' ? 'lbl-b' : 'lbl', x: 8, y: cy + 4 }, p.label));
      root.appendChild(s('line', { x1: x(p.spread_ci95[0]), x2: x(p.spread_ci95[1]), y1: cy, y2: cy, stroke: C.muse2, 'stroke-width': 3,
        'stroke-linecap': 'round' }));
      root.appendChild(s('circle', { cx: cx, cy: cy, r: narrow ? 5.5 : 6.5, fill: C.muse, stroke: C.surface, 'stroke-width': 2 }));
      hits.push({ x: cx, y: cy, name: p.label, lines: ['idea · spread ' + f2(p.spread), '95% CI ' + ci(p.spread_ci95),
        'top emblem: ' + p.top.emblem + ' (' + p.top.n + ' of ' + p.n + ')'] });
    });
    // the medians, as reference lines over everything
    [[a.median_things, C.thing, 'things’ median ' + f2(a.median_things), 'end'], [a.median_ideas, C.muse, 'ideas’ median ' + f2(a.median_ideas), 'start']]
      .forEach(function (m) {
        var mx = x(m[0]);
        root.appendChild(s('line', { x1: mx, x2: mx, y1: top - 6, y2: yAxis, stroke: m[1], 'stroke-width': 1.5, 'stroke-dasharray': '5 4' }));
        root.appendChild(s('text', { class: 'lbl', x: mx + (m[3] === 'end' ? -5 : 5), y: top - 12, 'text-anchor': m[3], stroke: C.surface,
          'stroke-width': 4, 'paint-order': 'stroke' }, m[2]));
      });
    wrap.appendChild(root);
    root.addEventListener('pointermove', function (e) {
      var rect = root.getBoundingClientRect(), k = W / rect.width;
      var px = (e.clientX - rect.left) * k, py = (e.clientY - rect.top) * k, best = null, bd = 16 * k;
      hits.forEach(function (q) { var d = Math.hypot(q.x - px, q.y - py); if (d < bd) { bd = d; best = q; } });
      if (!best) { hideTip(wrap); return; }
      showTip(wrap, best.x / k, best.y / k, best.name, best.lines);
    });
    root.addEventListener('pointerleave', function () { hideTip(wrap); });
    var legend = $('spread-legend');
    legend.textContent = '';
    legend.appendChild(h('span', null, [h('i', { class: 'dot', style: { background: C.thing } }), 'Muse Image’s everyday things (the Atlas)']));
    legend.appendChild(h('span', null, [h('i', { class: 'dot', style: { background: C.muse } }), 'Muse Image’s ideas, with 95% CIs']));
    legend.appendChild(h('span', null, [h('i', { class: 'line', style: { background: C.ink2 } }), 'medians (dashed)']));
  }

  // --- God under damage (Stable Diffusion XL, an open model; not Muse Image) ------------------------------
  // The slider shows one seed of SDXL's God (the pre-registered medoid) with its words part or its drawing part
  // damaged; the charts count person, beard and halo over all its seeds (Muse Glimmer's answers).
  var DM = { method: 'noise', level: 0 };
  var FEATS = [['person', 'a person', 's-person'], ['beard', 'a beard', 's-beard'], ['halo', 'a halo', 's-halo'],
               ['generic', 'a person with neither', 's-generic']];
  function verdict(ok) { return ok ? 'supported' : 'not supported'; }
  function pts1(x) { var v = Math.round(Math.abs(x) * 1000) / 10; return (x >= 0 ? '+' : '−') + v.toFixed(1); }  // share → ±points, half away from 0
  function share(v) { return v == null ? '–' : pct(v) + '%'; }
  function fams() { var m = D.damage.methods[DM.method]; return [m.lang, m.draw]; }
  function readout(lv, f) {
    var bits = [];
    if (lv.cond !== 'intact') bits.push(lv.label);
    bits.push('Glimmer: ' + f.emblem);
    var has = ['person', 'beard', 'halo'].filter(function (k) { return f[k]; });
    bits.push(has.length ? 'shows ' + has.join(', ') : 'no person');
    return bits.join(' · ');
  }
  function renderDamageSlider() {
    var X = D.damage, f = fams(), la = X.levels[f[0]], ld = X.levels[f[1]];
    var max = Math.min(la.length, ld.length) - 1, r = $('dmg-level');
    r.max = String(max);
    if (DM.level > max) DM.level = max;
    r.value = String(DM.level);
    var a = X.frames[f[0]][DM.level], b = X.frames[f[1]][DM.level];
    var step = DM.level ? 'damage step ' + DM.level + ' of ' + max : 'intact';
    $('dmg-img-lang').src = a.img;
    $('dmg-img-draw').src = b.img;
    $('dmg-img-lang').alt = 'Stable Diffusion XL’s drawing of God, words part damaged, ' + step + '; Muse Glimmer reads ' + a.emblem;
    $('dmg-img-draw').alt = 'Stable Diffusion XL’s drawing of God, drawing part damaged, ' + step + '; Muse Glimmer reads ' + b.emblem;
    $('dmg-read-lang').textContent = readout(la[DM.level], a);
    $('dmg-read-draw').textContent = readout(ld[DM.level], b);
    $('dmg-level-out').textContent = step;
    r.setAttribute('aria-valuetext', step);
  }
  // One small line chart per part: the share of SDXL's drawings of God showing each feature at each step.
  function featureChart(host, fam, title) {
    var R = D.damage.rates[fam], n = R.doses.length;
    var W = Math.max(280, host.clientWidth || 420), H = Math.round(Math.min(300, Math.max(210, W * 0.55)));
    var m = { l: 40, r: W < 380 ? 12 : 104, t: 30, b: 40 };
    var x = function (i) { return m.l + (W - m.l - m.r) * i / (n - 1); };
    var y = function (v) { return m.t + (H - m.t - m.b) * (1 - v); };
    var root = s('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': title + ': ' + FEATS.map(function (ft) {
      return ft[1] + ' ' + R[ft[0]].map(function (v) { return v == null ? '–' : pct(v) + '%'; }).join(', ');
    }).join('; ') });
    root.appendChild(s('text', { class: 'lbl-b', x: m.l, y: 16 }, title));
    [0, 0.25, 0.5, 0.75, 1].forEach(function (v) {
      root.appendChild(s('line', { class: 'grid', x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) }));
      root.appendChild(s('text', { class: 'tick', x: m.l - 6, y: y(v) + 4, 'text-anchor': 'end' }, pct(v) + '%'));
    });
    for (var i = 0; i < n; i++) {
      root.appendChild(s('text', { class: 'tick', x: x(i), y: H - m.b + 18, 'text-anchor': 'middle' }, i === 0 ? 'intact' : String(i)));
    }
    root.appendChild(s('text', { class: 'tick', x: W - m.r, y: H - 4, 'text-anchor': 'end' }, 'more damage →'));
    var ends = [];
    FEATS.forEach(function (ft) {
      var pts = R[ft[0]].map(function (v, i) { return v == null ? null : [x(i), y(v)]; }).filter(Boolean);
      root.appendChild(s('polyline', { class: 'ln ' + ft[2], points: pts.map(function (p) { return p.join(','); }).join(' ') }));
      pts.forEach(function (p) { root.appendChild(s('circle', { class: 'dt ' + ft[2], cx: p[0], cy: p[1], r: 4 })); });
      if (pts.length) ends.push({ y: pts[pts.length - 1][1], text: ft[1].replace('a person with neither', 'neither') });
    });
    if (m.r > 40) {  // direct end labels, nudged apart
      ends.sort(function (p, q) { return p.y - q.y; });
      for (var k = 1; k < ends.length; k++) if (ends[k].y - ends[k - 1].y < 14) ends[k].y = ends[k - 1].y + 14;
      ends.forEach(function (e) { root.appendChild(s('text', { class: 'lbl', x: W - m.r + 10, y: e.y + 4 }, e.text)); });
    }
    var cross = s('line', { class: 'cross', x1: 0, x2: 0, y1: m.t, y2: H - m.b, visibility: 'hidden' });
    root.appendChild(cross);
    host.appendChild(root);
    var labels = D.damage.levels[fam].map(function (lv) { return lv.label; });
    root.addEventListener('pointermove', function (e) {
      var rect = root.getBoundingClientRect(), k = W / rect.width, px = (e.clientX - rect.left) * k;
      var i = Math.max(0, Math.min(n - 1, Math.round((px - m.l) / ((W - m.l - m.r) / (n - 1)))));
      cross.setAttribute('x1', x(i)); cross.setAttribute('x2', x(i)); cross.setAttribute('visibility', 'visible');
      showTip(host, x(i) / k, (e.clientY - rect.top), title + ' · ' + labels[i], FEATS.map(function (ft) {
        var v = R[ft[0]][i];
        return ft[1] + ': ' + (v == null ? '–' : Math.round(v * D.damage.n_seeds) + ' of ' + D.damage.n_seeds);
      }));
    });
    root.addEventListener('pointerleave', function () { hideTip(host); cross.setAttribute('visibility', 'hidden'); });
  }
  function renderDamageCharts() {
    var box = $('dmg-charts'), f = fams();
    box.textContent = '';
    var parts = [[f[0], 'Words part damaged'], [f[1], 'Drawing part damaged']];
    var cells = parts.map(function () { var c = h('div', { class: 'iv-chart iv-dmg-chart' }); box.appendChild(c); return c; });
    parts.forEach(function (p, i) { featureChart(cells[i], p[0], p[1]); });  // measured once both cells are laid out
    var t = $('dmg-table'), X = D.damage;
    t.textContent = '';
    t.appendChild(h('thead', null, h('tr', null, ['Part damaged', 'Step'].concat(FEATS.map(function (ft) { return ft[1]; }))
      .map(function (c, i) { return h('th', { class: i > 1 ? 'n' : null, text: c }); }))));
    var body = h('tbody');
    [[f[0], 'words'], [f[1], 'drawing']].forEach(function (p) {
      X.levels[p[0]].forEach(function (lv, i) {
        body.appendChild(h('tr', null, [h('td', { text: p[1] }), h('td', { text: lv.label })].concat(FEATS.map(function (ft) {
          var v = X.rates[p[0]][ft[0]][i];
          return h('td', { class: 'n', text: v == null ? '–' : Math.round(v * X.n_seeds) + ' / ' + X.n_seeds });
        }))));
      });
    });
    t.appendChild(body);
  }
  function damage() {
    var X = D.damage;
    if (!X) return;
    $('damage').hidden = false;
    var T1 = X.tests, d1 = T1.D1, nn = X.n_seeds;
    $('dmg-n').textContent = String(nn);
    $('dmg-answer').textContent = X.answer || '';
    var lv = $('dmg-legend');
    lv.textContent = '';
    FEATS.forEach(function (ft) {
      lv.appendChild(h('span', null, [h('i', { class: 'line ' + ft[2] }), ft[0] === 'generic' ? 'a person with neither beard nor halo' : ft[1]]));
    });
    // the pre-registered predictions, with what Glimmer (primary) and our eye found
    var rows = [
      ['Intact, SDXL draws a person (≥ 12 of ' + nn + '), a beard (≥ 8) and a halo less often than Muse (≤ 12)',
       d1.person + ', ' + d1.beard + ' and ' + d1.halo + ' of ' + nn + (T1.D1_eye ? ' (by eye ' + T1.D1_eye.person + ', ' + T1.D1_eye.beard + ', ' + T1.D1_eye.halo + ')' : ''),
       d1.passes.a_person_ge_12 && d1.passes.b_beard_ge_8 && d1.passes.c_halo_le_12],
      ['Words damage takes the beard or halo before the figure', T1.D2_eye ? 'Glimmer: ' + verdict(T1.D2.primary) + '; by eye: ' + verdict(T1.D2_eye.primary) : verdict(T1.D2.primary), T1.D2.primary],
      ['…and God drifts toward an ordinary person (≥ 4 of ' + nn + ' more), more than under drawing damage',
       '+' + Math.round(T1.D3.language_rise * nn) + ' vs +' + Math.round(T1.D3.drawing_rise * nn) + ' of ' + nn + (T1.D3_eye ? ' (by eye +' + Math.round(T1.D3_eye.language_rise * nn) + ' vs +' + Math.round(T1.D3_eye.drawing_rise * nn) + ')' : ''), T1.D3.passes],
      ['All 15 ideas and words: words damage changes the emblem more than drawing damage, at equal picture change',
       pts1(T1.D4.difference) + ' points, 95% CI ' + pts1(T1.D4.ci95[0]) + ' to ' + pts1(T1.D4.ci95[1]), T1.D4.passes],
      ['…and drawing damage costs more of the clean line drawing', sgn(T1.D5.difference) + ', CI ' + ciS(T1.D5.ci95), T1.D5.passes],
      ['…and people appear where there were none, more under words damage', pts1(T1.D6.difference) + ' points, CI ' +
        pts1(T1.D6.ci95[0]) + ' to ' + pts1(T1.D6.ci95[1]), T1.D6.passes]
    ];
    var vb = $('dmg-verdicts');
    vb.textContent = '';
    vb.appendChild(h('h3', { class: 'iv-h3', text: 'Predicted before the run' }));
    var ul = h('ul', { class: 'iv-dmg-list' });
    rows.forEach(function (r) {
      ul.appendChild(h('li', { class: r[2] ? 'ok' : 'no' }, [h('b', { text: r[2] ? 'Held' : 'Failed' }), h('span', { text: r[0] }), h('small', { text: r[1] })]));
    });
    vb.appendChild(ul);
    // controls
    [].forEach.call($('dmg-method').querySelectorAll('button'), function (b) {
      b.addEventListener('click', function () {
        DM.method = b.getAttribute('data-method');
        [].forEach.call($('dmg-method').children, function (x) { x.setAttribute('aria-pressed', String(x === b)); });
        renderDamageSlider();
        renderDamageCharts();
      });
    });
    $('dmg-level').addEventListener('input', function (e) { DM.level = Number(e.target.value); renderDamageSlider(); });
    Object.keys(X.frames).forEach(function (f) { X.frames[f].forEach(function (p) { (new Image()).src = p.img; }); });
    renderDamageSlider();
    renderDamageCharts();
    $('dmg-charts-cap').textContent = X.charts_note || '';
    // every other idea and word: intact, the most words damage, the most drawing damage (one seed each)
    $('dmg-others-lede').textContent = X.others_note || '';
    var ob = $('dmg-others');
    ob.textContent = '';
    X.others.forEach(function (o) {
      ob.appendChild(h('figure', { class: 'iv-dmg-other' }, [
        h('img', { src: o.trio, alt: 'Stable Diffusion XL’s drawing of ' + o.phrase + ': intact, with the most words-part damage, and with the most drawing-part damage',
          width: 528, height: 176, loading: 'lazy', decoding: 'async' }),
        h('figcaption', null, [h('b', { text: o.label }),
          h('span', { text: o.same_emblem_lang_top == null ? 'no listed emblem when intact'
            : 'emblem kept: words ' + share(o.same_emblem_lang_top) + ' · drawing ' + share(o.same_emblem_draw_top) }),
          h('span', { text: 'a person: intact ' + share(o.person_intact) + ' · words ' + share(o.person_lang_top) + ' · drawing ' + share(o.person_draw_top) })])
      ]));
    });
    $('dmg-others-cap').textContent = 'Each strip: intact · most damage to the words part · most damage to the drawing part, one seed (the intact ' +
      'picture closest to the others). Percentages are over all 8 seeds at the most damage, by Muse Glimmer: the share still showing ' +
      'its intact emblem, and the share with a person in it. All pictures ' +
      'Stable Diffusion XL’s. ' + X.credit + '. Each idea’s full strip is on the draw pad, after you draw it.';
  }

  // --- beyond nouns: two verbs and two adjectives ---------------------------------------------------
  function words() {
    var W8 = D.words;
    if (!W8) return;
    $('words').hidden = false;
    $('words-lede').textContent = W8.lede || '';
    var box = $('words-grid');
    box.textContent = '';
    W8.words.forEach(function (x) {
      var strip = h('div', { class: 'iv-strip', role: 'img', 'aria-label': 'Muse Image’s ' + x.n + ' drawings of ' + x.phrase + ': mostly ' + x.top.emblem });
      for (var i = 0; i < x.n; i++) strip.appendChild(cell(x.sprite, i));
      var hit = x.top.short === x.predicted_short;
      box.appendChild(h('article', { class: 'iv-card' }, [
        h('div', { class: 'iv-card-head' }, [h('b', { text: x.label }), h('span', { text: x.kind.toLowerCase() })]),
        strip,
        h('p', { class: 'iv-card-top' }, [h('b', { text: x.top.emblem }), document.createTextNode(' in ' + x.top.n + ' of ' + x.n),
          h('small', { text: (hit ? 'as predicted' : 'predicted: ' + x.predicted) + ' · spread ' + f2(x.spread) + ' (95% CI ' + ci(x.spread_ci95) + ')' })])
      ]));
    });
    $('words-cap').textContent = W8.caption || '';
  }

  // --- draw one, and the method notes -------------------------------------------------------------
  function tryLinks() {
    var box = $('try-links');
    box.textContent = '';
    if (T.hasPage && !T.hasPage('/draw')) { $('try').hidden = true; return; }
    D.ideas.concat(D.words ? D.words.words : []).forEach(function (x, i) {
      box.appendChild(h('a', { class: i === 0 ? 'lead' : null, href: '/draw?thing=' + encodeURIComponent(x.key), text: 'Draw ' + x.phrase }));
    });
  }
  function method() {
    var S = D.summary, lc = S.label_check;
    $('refusals').textContent = S.refused_attempts ? S.refused_attempts + ' of ' + S.attempts + ' calls were refused.'
      : 'None of the ' + S.attempts + ' calls was refused or came back short, God’s included. No drawing has written words in it.';
    $('agree').textContent = 'We agreed on ' + pct(lc.agreement) + '% of the ' + lc.pictures + ' drawings (Cohen’s kappa ' + f2(lc.kappa) +
      '), least on freedom and the soul, where a drawing shows several symbols or none Glimmer could name.';
  }

  function render() {
    hero();
    damage();
    people();
    grid();
    bars();
    spreadText();
    spreadChart();
    words();
    tryLinks();
    method();
  }

  T.api('/api/plato/ideas').then(function (d) {
    D = d;
    d.ideas.forEach(function (x) { BY[x.key] = x; });
    render();
    var last = window.innerWidth, timer = 0;
    window.addEventListener('resize', function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        if (window.innerWidth !== last) { last = window.innerWidth; spreadChart(); if (D.damage) renderDamageCharts(); }
      }, 150);
    });
  }).catch(function (e) {
    var el = $('load-error');
    el.textContent = 'Couldn’t load the results: ' + e.message;
    el.hidden = false;
  });
})();
