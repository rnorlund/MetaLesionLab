/* Plato's Chair, damaged: the damage slider, the Form-or-hand dissociation, prototype drift, the damaged
   Glimmer arm and clocks. Everything comes from /api/plato/damage (statistics only) and precomputed
   WebP pictures; no API calls. */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var LANG = 'var(--blue)', DRAW = 'var(--orange)', GRID = 'var(--line)', AXIS = 'var(--line-3)', INK = 'var(--ink)';
  var S = { data: null, kind: null, method: 'noise', level: 3 };  // open on a damaged pair: the striking picture first
  var OUTCOME = { correct: 'the kind we asked for', plain: 'a plain, ordinary one', other_kind: 'another kind',
                  cant_tell: 'can’t tell, or not a chair', specific: 'a specific kind' };

  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'text') e.textContent = attrs[k]; else if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c != null) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return e;
  }
  function s(tag, attrs, kids) {
    var e = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) e.setAttribute(k, attrs[k]); });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c != null) e.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return e;
  }
  function f2(x) { return x == null ? '–' : (x < 0 ? '−' : '') + Math.abs(x).toFixed(2); }
  function pct(x) { return x == null ? '–' : Math.round(x * 100) + '%'; }
  function pts(x) { return x == null ? '–' : (x < 0 ? '−' : '+') + Math.abs(Math.round(x * 100)) + ' pts'; }
  function ciPts(c) { return c ? 'likely range ' + pts(c[0]) + ' to ' + pts(c[1]) : ''; }
  function excludesZero(c) { return c && (c[0] > 0 || c[1] < 0); }
  // "probably between 4 and 20 points" when the range is all one side of zero; the signed range otherwise
  function between(c) {
    if (!c) return '';
    var a = Math.abs(Math.round(c[0] * 100)), b = Math.abs(Math.round(c[1] * 100));
    return excludesZero(c) ? 'probably between ' + Math.min(a, b) + ' and ' + Math.max(a, b) + ' points' : 'somewhere between ' + pts(c[0]) + ' and ' + pts(c[1]);
  }
  // the data's own summary sentences, in the page's words (never its numbers)
  function plainWords(t) {
    return String(t).replace(/\bSDXL\b/g, 'Stable Diffusion XL').replace(/\bdoodles\b/g, 'drawings').replace(/\bdose\b/g, 'damage step')
      .replace(/\bLanguage damage\b/g, 'Damage to the words part').replace(/\bDrawing damage\b/g, 'Damage to the drawing part').replace(/\bintact\b/g, 'undamaged');
  }
  function partName(label) { return String(label).replace(/^language\b/, 'words part').replace(/^drawing\b/, 'drawing part'); }

  // ---------- slider ----------
  function fams() { var m = S.data.slider.methods[S.method]; return [m.lang, m.draw]; }

  function readout(p) {
    if (!p) return '';
    var bits = [];
    if (p.change != null && p.change > 0.0005) bits.push('picture changed ' + f2(p.change));
    if (p.outcome) bits.push('Glimmer: <b>' + (OUTCOME[p.outcome] || p.outcome) + '</b>');
    if (p.name) bits.push('calls it “' + p.name.replace(/[<>&]/g, '') + '”');
    return bits.join(' · ');
  }

  function renderSlider() {
    var sl = S.data.slider, f = fams(), pics = sl.pictures[S.kind];
    var lev = sl.levels[f[0]], levD = sl.levels[f[1]];
    var max = Math.min(lev.length, levD.length) - 1;
    var r = $('level');
    r.max = String(max);
    if (S.level > max) S.level = max;
    r.value = String(S.level);
    var a = pics[f[0]][S.level], b = pics[f[1]][S.level];
    var kindLabel = sl.kinds.filter(function (k) { return k.key === S.kind; })[0].label;
    $('img-lang').src = a.img;
    $('img-draw').src = b.img;
    $('img-lang').alt = 'Stable Diffusion XL asked for a ' + kindLabel + ', words part damaged, ' + (S.level ? 'step ' + S.level : 'undamaged') +
      (a.name ? '; Glimmer calls it ' + a.name : '');
    $('img-draw').alt = 'Stable Diffusion XL asked for a ' + kindLabel + ', drawing part damaged, ' + (S.level ? 'step ' + S.level : 'undamaged') +
      (b.name ? '; Glimmer calls it ' + b.name : '');
    $('read-lang').innerHTML = S.level ? lev[S.level].label + ' · ' + readout(a) : readout(a);
    $('read-draw').innerHTML = S.level ? levD[S.level].label + ' · ' + readout(b) : readout(b);
    var txt = S.level === 0 ? 'undamaged' : 'step ' + S.level + ' of ' + max;
    $('level-out').textContent = txt;
    r.setAttribute('aria-valuetext', txt);
  }

  function setupSlider() {
    var sl = S.data.slider, seg = $('kind-seg');
    S.kind = sl.kinds[0].key;
    sl.kinds.forEach(function (k, i) {
      var b = el('button', { type: 'button', 'aria-pressed': i === 0 ? 'true' : 'false', text: k.label });
      b.addEventListener('click', function () {
        S.kind = k.key;
        [].forEach.call(seg.children, function (x) { x.setAttribute('aria-pressed', String(x === b)); });
        renderSlider();
      });
      seg.appendChild(b);
    });
    [].forEach.call($('method-seg').querySelectorAll('button'), function (b) {
      b.addEventListener('click', function () {
        S.method = b.getAttribute('data-method');
        [].forEach.call($('method-seg').children, function (x) { x.setAttribute('aria-pressed', String(x === b)); });
        renderSlider();
        renderDissociation();
        renderHeroClocks();
      });
    });
    $('level').addEventListener('input', function (e) { S.level = Number(e.target.value); renderSlider(); });
    // preload every picture so sliding is instant
    Object.keys(sl.pictures).forEach(function (k) {
      Object.keys(sl.pictures[k]).forEach(function (f) { sl.pictures[k][f].forEach(function (p) { (new Image()).src = p.img; }); });
    });
    renderSlider();
  }

  // ---------- charts ----------
  function lineChart(host, opts) {
    // opts: series [{name, colour, dash, points: [{x, y, lo, hi, tip}]}], xlab, ylab, ymin, ymax
    var W = 440, H = 260, m = { l: 46, r: 100, t: 10, b: 40 };
    var xmax = 0, ymin = opts.ymin, ymax = opts.ymax;
    opts.series.forEach(function (se) { se.points.forEach(function (p) {
      xmax = Math.max(xmax, p.x);
      if (opts.ymin == null) ymin = Math.min(ymin == null ? p.y : ymin, p.lo != null ? p.lo : p.y);
      if (opts.ymax == null) ymax = Math.max(ymax == null ? p.y : ymax, p.hi != null ? p.hi : p.y);
    }); });
    xmax = Math.ceil(xmax * 10) / 10 || 1;
    if (ymin === ymax) { ymin -= 0.1; ymax += 0.1; }
    var X = function (v) { return m.l + (W - m.l - m.r) * v / xmax; };
    var Y = function (v) { return m.t + (H - m.t - m.b) * (1 - (v - ymin) / (ymax - ymin)); };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': opts.label });
    var g = s('g', { class: 'axis' });
    var ticks = 4;
    for (var i = 0; i <= ticks; i++) {
      var v = ymin + (ymax - ymin) * i / ticks;
      g.appendChild(s('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: GRID }));
      g.appendChild(s('text', { x: m.l - 6, y: Y(v) + 4, 'text-anchor': 'end' }, opts.yfmt ? opts.yfmt(v) : f2(v)));
    }
    for (var j = 0; j <= 4; j++) {
      var xv = xmax * j / 4;
      g.appendChild(s('text', { x: X(xv), y: H - m.b + 16, 'text-anchor': 'middle' }, xv.toFixed(2)));
    }
    if (ymin < 0 && ymax > 0) g.appendChild(s('line', { x1: m.l, x2: W - m.r, y1: Y(0), y2: Y(0), stroke: AXIS }));
    g.appendChild(s('line', { x1: m.l, x2: m.l, y1: m.t, y2: H - m.b, stroke: AXIS }));
    g.appendChild(s('text', { x: (m.l + W - m.r) / 2, y: H - 4, 'text-anchor': 'middle', class: 'lab' }, opts.xlab));
    svg.appendChild(g);
    var tip = el('div', { class: 'pd-tip', hidden: '' });
    // direct labels at the line ends, nudged apart so they never overlap
    var ends = opts.series.map(function (se, k) {
      var q = se.points[se.points.length - 1];
      return { k: k, y: Y(q.y), x: X(q.x) };
    }).sort(function (a, b) { return a.y - b.y; });
    for (var e = 1; e < ends.length; e++) if (ends[e].y - ends[e - 1].y < 13) ends[e].y = ends[e - 1].y + 13;
    var labelY = {}, labels = [];
    ends.forEach(function (o) { labelY[o.k] = o.y; });
    opts.series.forEach(function (se, k) {
      var p = se.points;
      if (p.length > 1 && p[0].lo != null) {
        var band = p.map(function (q) { return X(q.x) + ',' + Y(q.hi); }).join(' ') + ' ' +
          p.slice().reverse().map(function (q) { return X(q.x) + ',' + Y(q.lo); }).join(' ');
        svg.appendChild(s('polygon', { points: band, fill: se.colour, opacity: 0.10 }));
      }
      svg.appendChild(s('polyline', { points: p.map(function (q) { return X(q.x) + ',' + Y(q.y); }).join(' '),
        fill: 'none', stroke: se.colour, 'stroke-width': 2, 'stroke-dasharray': se.dash ? '5 3' : null,
        'stroke-linejoin': 'round' }));
      p.forEach(function (q) {
        var dot = s('circle', { cx: X(q.x), cy: Y(q.y), r: 4, fill: se.colour, stroke: 'var(--chart-halo)', 'stroke-width': 2 });
        var hit = s('circle', { cx: X(q.x), cy: Y(q.y), r: 12, fill: 'transparent', tabindex: 0 });
        var show = function () {
          tip.innerHTML = '<b>' + se.name + '</b><br>' + q.tip;
          tip.hidden = false;
          var box = host.getBoundingClientRect(), sb = svg.getBoundingClientRect();
          tip.style.left = Math.min(box.width - 200, (X(q.x) / W) * sb.width + 10) + 'px';
          tip.style.top = ((Y(q.y) / H) * sb.height - 10) + 'px';
        };
        hit.addEventListener('mouseenter', show); hit.addEventListener('focus', show);
        hit.addEventListener('mouseleave', function () { tip.hidden = true; });
        hit.addEventListener('blur', function () { tip.hidden = true; });
        svg.appendChild(dot); svg.appendChild(hit);
      });
      var last = p[p.length - 1];
      labels.push(s('text', { x: X(last.x) + 8, y: labelY[k] + 4, class: 'dlab' }, se.name));
    });
    labels.forEach(function (t) { svg.appendChild(t); });  // on top of every line
    host.appendChild(svg);
    host.appendChild(tip);
  }

  function series(fam, measure, offset, name, colour, dash) {
    var c = S.data.curves[fam] || [];
    var points = [{ x: 0, y: offset, lo: offset, hi: offset, tip: 'intact' }];
    c.forEach(function (q) {
      if (q[measure] == null) return;
      points.push({ x: q.d_intact, y: q[measure] + offset, lo: q[measure + '_ci'][0] + offset,
        hi: q[measure + '_ci'][1] + offset,
        tip: (fam.indexOf('zero') > 0 ? Math.round(q.dose * 100) + '% of neurons off' : 'noise × ' + q.dose) +
          '<br>picture changed ' + f2(q.d_intact) + '<br>value ' + f2(q[measure] + offset) });
    });
    return { name: name, colour: colour, dash: dash, points: points };
  }

  function famPair() { var m = S.data.slider.methods[S.method]; return [m.lang, m.draw]; }

  function tile(host, q, m, unitFn, langWord, drawWord, predicted) {
    if (!m) return;
    var t = el('div', { class: 'pd-tile' });
    t.appendChild(el('div', { class: 'q', text: q }));
    var row = el('div', { class: 'row' });
    row.appendChild(el('span', { class: 'v lang', text: unitFn(m.language) }));
    row.appendChild(el('span', { class: 'vs', text: langWord + ' vs.' }));
    row.appendChild(el('span', { class: 'v draw', text: unitFn(m.drawing) }));
    row.appendChild(el('span', { class: 'vs', text: drawWord }));
    t.appendChild(row);
    t.appendChild(el('div', { class: 'ci', text: 'difference ' + pts(m.difference) + ' (' + ciPts(m.ci95) + ')' }));
    var ok = excludesZero(m.ci95) && Math.sign(m.difference) === m.predicted_sign;
    var rev = excludesZero(m.ci95) && Math.sign(m.difference) === -m.predicted_sign;
    t.appendChild(el('div', { class: 'verdict', text: (predicted ? 'We predicted ' + predicted + ' ' : '') + (ok ? 'As predicted.' :
      rev ? 'The opposite happened.' : 'Too close to call with this many pictures.') }));
    host.appendChild(t);
  }

  function renderDissociation() {
    var d = S.data, f = famPair(), key = f[0] + ' vs ' + f[1], m = d.matched[key] || {};
    var tiles = $('diss-tiles'); tiles.innerHTML = '';
    var prim = (d.matched['text-zero vs unet-zero'] || {}).delta_correct;
    var note = $('diss-primary');
    if (prim && note) {
      note.textContent = 'Our planned main test (neurons switched off): when both kinds of damage had changed the picture equally, damage to the words part left ' +
        Math.abs(Math.round(prim.difference * 100)) + ' points fewer chairs that Glimmer reads as the kind we asked for (' + between(prim.ci95) +
        '). Below: ' + (S.method === 'zero' ? 'neurons switched off (the main test).' : 'noise added to neurons (a second test); switch with the buttons at the top.');
    }
    tile(tiles, 'Still the kind we asked for, says Glimmer: change from undamaged', m.delta_correct,
      pts, 'words part', 'drawing part', 'the words part would lose the kind faster.');
    tile(tiles, 'Still a clean line drawing, says Glimmer: change from undamaged', m.delta_p_clean, pts, 'words part', 'drawing part',
      'the drawing part would lose clean lines faster.');
    tile(tiles, 'Glimmer says yes to “Is this a drawing of a chair?”: change from undamaged', m.delta_p_is_a, pts, 'words part', 'drawing part',
      'the words part would lose “chair” faster.');
    var charts = $('diss-charts'); charts.innerHTML = '';
    var c1 = el('div', { class: 'pd-chart' }, [el('h3', { text: 'What it draws: still the kind we asked for' })]);
    var c2 = el('div', { class: 'pd-chart' }, [el('h3', { text: 'How it draws: Glimmer says “clean line drawing”' })]);
    charts.appendChild(c1); charts.appendChild(c2);
    var xlab = 'how much the picture changed from its undamaged twin';
    lineChart(c1, { label: 'Share of chairs still read as the kind we asked for, by how much damage changed the picture',
      series: [series(f[0], 'delta_correct', 1, 'words part', LANG, false), series(f[1], 'delta_correct', 1, 'drawing part', DRAW, true)],
      xlab: xlab, ymin: 0, ymax: 1, yfmt: pct });
    lineChart(c2, { label: 'Change in how sure Glimmer is that it is a clean line drawing, by how much damage changed the picture',
      series: [series(f[0], 'delta_p_clean', 0, 'words part', LANG, false), series(f[1], 'delta_p_clean', 0, 'drawing part', DRAW, true)],
      xlab: xlab, yfmt: f2 });
    $('diss-legend').innerHTML = '<span><i style="border-color:' + LANG + '"></i>words part damaged</span>' +
      '<span><i class="dash" style="border-color:' + DRAW + '"></i>drawing part damaged</span>' +
      '<span>shaded: the likely range (95% interval) over 64 pictures</span>';
    if (d.diss_caveat) $('diss-caveat').textContent = d.diss_caveat;
  }

  // ---------- prototype drift ----------
  function renderProto() {
    var d = S.data, host = $('proto'); host.innerHTML = '';
    var m = (d.matched['text-zero vs unet-zero'] || {}).delta_d_proto;
    var pooled = d.pooled || {};
    var left = el('div');
    var tz = pooled['text-zero'] && pooled['text-zero'].delta_d_proto, tn = pooled['text-noise'] && pooled['text-noise'].delta_d_proto;
    var closer = (tz && tz.ci95[1] < 0) || (tn && tn.ci95[1] < 0);
    left.appendChild(el('p', { class: 'pd-verdict', text: closer ? 'Partly: some damage to the words part moves the chairs toward the plain chair.' :
      'No. Damage to the words part does not bring back the plain chair. The pictures wander off to other things.' }));
    var txt = 'How much farther the damaged pictures are from the plain chair than the undamaged ones, averaged over the damage steps ' +
      '(0 = no change; positive = farther). The plain chair is the average of the AI’s own pictures of just “a chair”, and a Meta AI that ' +
      'compares pictures (DINOv2) measures the distance. ';
    ['text-zero', 'text-noise', 'unet-zero', 'unet-noise'].forEach(function (fam, i) {
      var v = pooled[fam] && pooled[fam].delta_d_proto;
      if (!v) return;
      txt += (i ? '; ' : '') + (fam.indexOf('text') === 0 ? (i ? 'words part' : 'Words part') : 'drawing part') + (fam.indexOf('zero') > 0 ? ', neurons off: ' : ', noise: ') +
        (v.mean >= 0 ? '+' : '−') + Math.abs(v.mean).toFixed(2) + ' [' + f2(v.ci95[0]) + ', ' + f2(v.ci95[1]) + ']';
    });
    left.appendChild(el('p', { text: txt + '. In brackets: the likely range (95% interval).' }));
    if (m) left.appendChild(el('p', { text: 'Compared at equal picture change, words damage minus drawing damage: ' + (m.difference >= 0 ? '+' : '−') +
      Math.abs(m.difference).toFixed(3) + ' (likely range ' + f2(m.ci95[0]) + ' to ' + f2(m.ci95[1]) + '). We predicted a number below zero: ' +
      'words damage moving the chairs closer to the plain chair.' }));
    host.appendChild(left);
    var c = el('div', { class: 'pd-chart' }, [el('h3', { text: 'Distance from the plain chair: change from undamaged' })]);
    host.appendChild(c);
    lineChart(c, { label: 'Change in distance from the plain chair, by how much the picture changed',
      series: [series('text-zero', 'delta_d_proto', 0, 'words, off', LANG, false), series('text-noise', 'delta_d_proto', 0, 'words, noise', LANG, true),
        series('unet-zero', 'delta_d_proto', 0, 'drawing, off', DRAW, false), series('unet-noise', 'delta_d_proto', 0, 'drawing, noise', DRAW, true)],
      xlab: 'how much the picture changed', yfmt: f2 });
    // what it turned into
    var names = $('names'); names.innerHTML = '';
    [['text-noise', 'lang', 'Words part, noise added'], ['text-zero', 'lang', 'Words part, neurons off'],
     ['unet-noise', 'draw', 'Drawing part, noise added'], ['unet-zero', 'draw', 'Drawing part, neurons off']].forEach(function (x) {
      var list = (d.names || {})[x[0]];
      if (!list || !list.length) return;
      var card = el('div', { class: 'card ' + x[1] }, [el('h3', { text: x[2] + ': what Glimmer called the most damaged chairs' })]);
      var ul = el('ul');
      list.slice(0, 10).forEach(function (n) { ul.appendChild(el('li', {}, [n[0] + ' ', el('b', { text: '×' + n[1] })])); });
      card.appendChild(ul);
      names.appendChild(card);
    });
  }

  // ---------- Glimmer arm ----------
  function renderGlimmer() {
    var g = S.data.glimmer, host = $('glim');
    if (!g || !g.conditions) { host.textContent = 'Pending.'; return; }
    host.innerHTML = '';
    var left = el('div'), right = el('div', { class: 'pd-chart' });
    var ml = g.matched_loss || {}, cond = g.conditions || {};
    left.appendChild(el('p', { text: 'Undamaged, Glimmer picks the right kind for ' + pct(g.intact_accuracy) + ' of ' + g.n_pictures +
      ' drawings of 22 things. For the ' + g.n_intact_correct + ' it got right, we counted what the damaged Glimmer answers instead. ' +
      'We only trust an answer that stays the same when we list the options in reverse order. The rest are habits, like always picking ' +
      'the same letter, not real readings.' }));
    var L = [0.1, 0.2, 0.3].map(function (d) { return cond['language-mlp-mean@' + d]; });
    if (L[0] && L[2]) {
      left.appendChild(el('p', { class: 'pd-verdict', text: 'When a damaged Glimmer still answers steadily, its mistakes are “a plain, ordinary …”, almost never another specific kind. With its language neurons damaged, ' +
        L.map(function (x) { return pct(x.strict_plain.mean); }).join(', ').replace(/, ([^,]*)$/, ' and $1') + ' of the specific kinds become “plain” at the three damage steps.' }));
    }
    if (ml['language-mlp-mean']) {
      var a = ml['language-mlp-mean'].strict_plain, v = ml['visual-mlp-mean'];
      left.appendChild(el('p', { text: 'That looks like the slide from the specific to the general seen in semantic dementia. But it is not a sign of language damage: ' +
        'switching off the same number of random neurons, compared at the same loss of right answers, does the same (difference ' +
        pts(a.difference) + ', ' + ciPts(a.ci95) + '). It is what any damaged reader falls back on.' +
        (v ? ' Damage to the seeing neurons is different: almost no “plain” answers (' + pts(v.strict_plain.difference) + ' against random) and many more ' +
          'letter guesses (' + pts(v.strict_order_bias.difference) + ', ' + ciPts(v.strict_order_bias.ci95) + ').' : '') }));
    }
    host.appendChild(left);
    host.appendChild(right);
    // dot chart: steady "plain" answers, lesion vs its random control, per family and dose
    var rows = [];
    ['language', 'naming', 'visual'].forEach(function (f) {
      [0.1, 0.2, 0.3].forEach(function (d) {
        var a = cond[f + '-mlp-mean@' + d], b = cond[f + '-mlp-mean-random@' + d];
        if (a && b) rows.push({ f: f, d: d, a: a.strict_plain.mean, b: b.strict_plain.mean, acc: a.correct.mean, accr: b.correct.mean });
      });
    });
    var W = 440, rowH = 22, H = 40 + rows.length * rowH, m = { l: 170, r: 20 };
    var X = function (v) { return m.l + (W - m.l - m.r) * v / 0.5; };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'Share of specific kinds steadily called plain, lesion vs random control' });
    [0, 0.1, 0.2, 0.3, 0.4, 0.5].forEach(function (v) {
      svg.appendChild(s('line', { x1: X(v), x2: X(v), y1: 20, y2: H - 10, stroke: GRID }));
      svg.appendChild(s('text', { x: X(v), y: 14, 'text-anchor': 'middle', class: 'lab' }, pct(v)));
    });
    var NAME = { language: 'language', naming: 'naming', visual: 'seeing' };
    rows.forEach(function (r, i) {
      var y = 32 + i * rowH;
      svg.appendChild(s('text', { x: m.l - 8, y: y + 4, 'text-anchor': 'end', class: 'dlab' }, NAME[r.f] + ' neurons, top ' + Math.round(r.d * 100) + '%'));
      svg.appendChild(s('line', { x1: X(r.b), x2: X(r.a), y1: y, y2: y, stroke: AXIS }));
      var c1 = s('circle', { cx: X(r.b), cy: y, r: 4.5, fill: 'var(--chart-halo)', stroke: LANG, 'stroke-width': 2 });
      var c2 = s('circle', { cx: X(r.a), cy: y, r: 5, fill: LANG, stroke: 'var(--chart-halo)', 'stroke-width': 1.5 });
      c1.appendChild(s('title', {}, 'random neurons: ' + pct(r.b) + ' plain; ' + pct(r.accr) + ' still right'));
      c2.appendChild(s('title', {}, NAME[r.f] + ' neurons: ' + pct(r.a) + ' plain; ' + pct(r.acc) + ' still right'));
      svg.appendChild(c1); svg.appendChild(c2);
    });
    right.appendChild(el('h3', { text: 'Specific kinds now steadily called “a plain, ordinary …”' }));
    right.appendChild(svg);
    right.appendChild(el('div', { class: 'pd-legend' }, [el('span', {}, [el('i', { style: 'width:10px;height:10px;border-radius:50%;background:' + LANG + ';border:0' }), 'targeted neurons']),
      el('span', {}, [el('i', { style: 'width:10px;height:10px;border-radius:50%;border:2px solid ' + LANG }), 'same number of random neurons'])]));
  }

  // ---------- Janus: one model draws and reads ----------
  function renderJanus() {
    var j = S.data.janus, host = $('janus');
    if (!j || !j.read) { host.textContent = 'Pending.'; return; }
    host.innerHTML = '';
    var doses = {};
    Object.keys(j.read).forEach(function (c) { doses[j.read[c].dose] = doses[j.read[c].dose] || {}; doses[j.read[c].dose].read = j.read[c]; });
    Object.keys(j.draw || {}).forEach(function (c) { doses[j.draw[c].dose] = doses[j.draw[c].dose] || {}; doses[j.draw[c].dose].draw = j.draw[c]; });
    var tb = el('table', { class: 'pd-table' });
    tb.appendChild(el('thead', {}, el('tr', {}, [el('th', { text: 'Neurons switched off' }),
      el('th', { class: 'num', text: 'reads the right kind' }), el('th', { class: 'num', text: 'draws the asked kind' }),
      el('th', { class: 'num', text: 'drawing changed' })])));
    var body = el('tbody');
    Object.keys(doses).map(Number).sort(function (a, b) { return a - b; }).forEach(function (d) {
      var r = doses[d].read, w = doses[d].draw;
      body.appendChild(el('tr', {}, [el('td', { text: d ? Math.round(d * 100) + '%' : 'none (undamaged)' }),
        el('td', { class: 'num', text: r ? pct(r.correct.mean) + ' of ' + r.n : '–' }),
        el('td', { class: 'num', text: w ? pct(w.kind_kept.mean) + ' of ' + w.n : 'pending' }),
        el('td', { class: 'num', text: w ? f2(w.d_intact.mean) : '–' })]));
    });
    tb.appendChild(body);
    var left = el('div');
    if (j.summary) left.appendChild(el('p', { class: 'pd-verdict', text: plainWords(j.summary).replace(/\bJanus reads\b/, 'Janus-Pro reads') }));
    left.appendChild(el('div', { class: 'pd-tablewrap' }, tb));
    left.appendChild(el('p', { class: 'pd-caveat', text: 'Reading: 40 Muse Image drawings of named chairs, hats and birds, picking the kind from a list. ' +
      'Drawing: 8 kinds of chair and the plain chair, each from 4 random starting points. “Draws the asked kind” means the drawing looks most like ' +
      'the undamaged drawings of its own kind, to a Meta AI that compares pictures (DINOv2). Few pictures: a first look only.' }));
    host.appendChild(left);
    if (j.strip && j.strip.length) {
      var strip = el('div', { class: 'pd-jstrip' });
      j.strip.forEach(function (p) {
        strip.appendChild(el('figure', {}, [el('img', { src: p.img, alt: 'Janus-Pro asked for a wheelchair, ' + (p.dose ? Math.round(p.dose * 100) + '% of language neurons off' : 'undamaged'), loading: 'lazy' }),
          el('figcaption', { text: p.dose ? Math.round(p.dose * 100) + '% off' : 'undamaged' })]));
      });
      host.appendChild(strip);
    }
  }

  // ---------- clocks ----------
  function renderClocks() {
    var c = S.data.clocks, host = $('clocks');
    if (!c) { host.textContent = 'Still running.'; return; }
    host.innerHTML = '';
    var left = el('div'), right = el('div');
    if (c.summary) c.summary.forEach(function (t) { left.appendChild(el('p', { text: plainWords(t).replace(/^Intact /, 'Undamaged ') })); });
    if (c.features) {
      var tb = el('table', { class: 'pd-table' });
      var head = el('tr', {}, [el('th', { text: 'Condition' })]);
      c.feature_names.forEach(function (n) { head.appendChild(el('th', { class: 'num', text: n })); });
      tb.appendChild(el('thead', {}, head));
      var body = el('tbody');
      c.features.forEach(function (r) {
        var tr = el('tr', {}, [el('td', { text: r.cond === 'intact' ? 'undamaged' : partName(r.label) })]);
        r.values.forEach(function (v) { tr.appendChild(el('td', { class: 'num', text: pct(v) })); });
        body.appendChild(tr);
      });
      tb.appendChild(body);
      left.appendChild(el('div', { class: 'pd-tablewrap' }, tb));
    }
    var strip = c.strip || {}, method = 'noise';
    ['3_00', '8_45'].forEach(function (t) {
      var grid = el('div', { class: 'pd-clockgrid' });
      grid.appendChild(el('div', { class: 'h', text: t.replace('_', ':') }));
      ['undamaged', 'step 1', 'step 2', 'step 3'].forEach(function (h) { grid.appendChild(el('div', { class: 'h', text: h })); });
      [['text-' + method, 'lang', 'words'], ['unet-' + method, 'draw', 'drawing']].forEach(function (x) {
        var seq = (strip[x[0]] || {})[t] || [];
        grid.appendChild(el('div', { class: 'r ' + x[1], text: x[2] }));
        seq.forEach(function (p) { grid.appendChild(el('img', { src: p.img, alt: 'Clock asked to show ' + t.replace('_', ':') + ', ' +
          (p.label === 'intact' ? 'undamaged' : x[2] + ' part damaged, ' + p.label), loading: 'lazy' })); });
      });
      right.appendChild(grid);
    });
    host.appendChild(left);
    host.appendChild(right);
  }

  // ---------- the first screen: three headline numbers drawn (FirstLook, statviz.js), and the clocks ----------
  // How a planned prediction came out, from its matched test: {tone, text} for FirstLook's verdict.
  function verdictOf(t) {
    var held = excludesZero(t.ci95) && Math.sign(t.difference) === t.predicted_sign;
    var rev = excludesZero(t.ci95) && Math.sign(t.difference) === -t.predicted_sign;
    return held ? { tone: 'yes', text: 'As predicted' } : rev ? { tone: 'no', text: 'Prediction reversed' } : { tone: 'part', text: 'Too close to call' };
  }

  function renderHero() {
    var d = S.data, host = $('hero-stats');
    if (!host || !window.FirstLook) return;
    var m = d.matched['text-zero vs unet-zero'] || {}, stats = [];
    // 1. What: the asked kind, lost faster after language damage (the pre-registered primary test)
    var kc = m.delta_correct;
    if (kc) {
      var lang = Math.round(-kc.language * 100), draw = Math.round(-kc.drawing * 100);
      var v1 = verdictOf(kc);
      stats.push({ kind: 'bars', verdict: v1,
        o: { values: [lang, draw], labels: ['words', 'drawing'], tones: ['blue', 'orange'], max: 100, value: lang + ' vs ' + draw, unit: ' pts',
          label: 'fewer chairs still the kind we asked for, in percentage points, when damage to either part changed the picture equally',
          alt: 'Words part damaged: ' + lang + ' points fewer chairs still read as the kind we asked for; drawing part damaged: ' + draw +
            ' points fewer, at the same amount of picture change (neurons switched off).' },
        q: 'We predicted damage to the words part would lose the asked kind faster. ' + (v1.tone === 'yes' ? 'It did: ' : v1.tone === 'no' ?
          'The opposite happened: ' : 'Too close to call: ') + 'a gap of ' + Math.abs(Math.round(kc.difference * 100)) + ' points, ' + between(kc.ci95) +
          '. This was our planned main test.' });
    }
    // 2. Back to the plain chair? Farther from it, not closer
    var pz = (d.pooled['text-zero'] || {}).delta_d_proto, pd = (d.pooled['unet-zero'] || {}).delta_d_proto, h2 = m.delta_d_proto;
    if (pz && pd) {
      var held2 = h2 && verdictOf(h2).tone === 'yes';
      stats.push({ kind: 'bars', verdict: h2 ? (held2 ? verdictOf(h2) : { tone: 'no', text: 'Prediction failed' }) : null,
        o: { values: [pz.mean, pd.mean], labels: ['words', 'drawing'], tones: ['blue', 'orange'], digits: 2,
          value: pz.ci95[0] > 0 ? 'Farther' : 'No closer', unit: '',
          label: 'from the AI’s plain, ordinary chair, not back toward it: how much more different the damaged pictures look',
          alt: 'Back to the plain chair? No. Distance from the plain chair grew by ' + pz.mean.toFixed(2) + ' after damage to the words part and by ' +
            pd.mean.toFixed(2) + ' after damage to the drawing part (neurons switched off, averaged over the damage steps).' },
        q: 'We predicted damage to the words part would turn the rocking chair back into a plain chair, as happens in semantic dementia, ' +
          'a brain disease that wears away what words mean. ' + (held2 ? 'It did.' : pz.ci95[0] > 0 ? 'It didn’t: the pictures moved farther away.' :
          'It didn’t: they came no closer.') });
    }
    // 3. Clocks: the mildest drawing damage strips the numbers first
    var c = d.clocks, fi = c && c.feature_names ? c.feature_names.indexOf('12 numbers in order') : -1;
    if (fi >= 0) {
      var intact = c.features.filter(function (r) { return r.cond === 'intact'; })[0];
      var mild = c.features.filter(function (r) { return r.cond.indexOf('unet-zero@') === 0; })
        .sort(function (x, y) { return parseFloat(x.cond.split('@')[1]) - parseFloat(y.cond.split('@')[1]); })[0];
      if (intact && mild) {
        var a = Math.round(intact.values[fi] * 100), b = Math.round(mild.values[fi] * 100);
        stats.push({ kind: 'bars',
          o: { values: [a, b], labels: ['undamaged', 'drawing'], tones: ['ink', 'orange'], max: 100, value: a + '% → ' + b + '%', unit: '',
            label: 'of clocks have all 12 numbers in order, undamaged and then after the lightest damage to the drawing part: the numbers go first',
            alt: 'Clocks with all 12 numbers in order: ' + a + '% undamaged, ' + b + '% after the lightest damage to the drawing part (' + mild.label + ').' },
          q: 'Meta’s chat AI, Muse Spark, checked each clock. Damage to the words part removes the whole clock instead.' });
      }
    }
    window.FirstLook.render(host, { stats: stats });
    // the note: the dissociation's verdict, from the same numbers
    var q = $('hero-qual'), clean = m.delta_p_clean, cn = (d.matched['text-noise vs unet-noise'] || {}).delta_p_clean;
    if (q && kc && clean && cn) {
      var whatHeld = verdictOf(kc).tone === 'yes', heldNoise = verdictOf(cn).tone === 'yes';
      var heldOff = verdictOf(clean).tone === 'yes', revOff = verdictOf(clean).tone === 'no';
      q.innerHTML = '';
      q.appendChild(el('b', { text: whatHeld && heldNoise && heldOff ? 'Supported. ' : whatHeld || heldNoise || heldOff ? 'Partly supported. ' : 'Not supported. ' }));
      q.appendChild(document.createTextNode('We predicted damage to the words part would make it forget what to draw, and damage to the drawing part ' +
        'how to draw. The “what” half ' + (whatHeld ? 'held' : 'did not hold') + '; the “how” half ' + (heldNoise ? 'held for added noise' : 'did not hold for added noise') +
        (revOff ? ' but reversed for neurons switched off' : '') + ' ('));
      q.appendChild(el('a', { href: '#diss-h', text: 'details' }));
      q.appendChild(document.createTextNode('). The judges are AI models, and this is an analogy, not a claim about people.'));
    }
    renderHeroClocks();
  }

  // three clocks asked to show 8:45: intact, and the most damaged language and drawing parts, for the chosen kind of damage
  function renderHeroClocks() {
    var c = S.data.clocks, fig = $('hero-clocks'), row = $('hero-clocks-row');
    if (!fig || !c || !c.strip) return;
    var m = S.data.slider.methods[S.method], t = '8_45';
    var lang = ((c.strip[m.lang] || {})[t] || []), draw = ((c.strip[m.draw] || {})[t] || []);
    if (!lang.length || !draw.length) { fig.hidden = true; return; }
    row.innerHTML = '';
    [[lang[0], 'undamaged', ''], [lang[lang.length - 1], 'words part', 'lang'], [draw[draw.length - 1], 'drawing part', 'draw']].forEach(function (x) {
      var p = x[0];
      row.appendChild(el('figure', { class: 'pd-heroclock ' + x[2] }, [
        el('img', { src: p.img, width: 180, height: 180, loading: 'lazy',
          alt: 'A clock asked to show 8:45, ' + (x[2] ? x[1] + ' damaged, ' + p.label : 'undamaged') }),
        el('figcaption', {}, [el('b', { text: x[1] }), x[2] ? el('span', { text: p.label }) : null])]));
    });
    $('hero-clocks-cap').innerHTML = '';
    $('hero-clocks-cap').appendChild(document.createTextNode('And clocks: the same AI asked for “a simple clock face showing 8:45”, undamaged and at the heaviest damage to each part. '));
    $('hero-clocks-cap').appendChild(el('a', { href: '#clock-h', text: 'See all the clocks' }));
    fig.hidden = false;
  }

  // parts of the experiment still running are named, never guessed
  function renderStatus() {
    var st = S.data.status;
    if (!st) return;
    Object.keys(st).forEach(function (id) {
      var host = $(id);
      if (host) host.insertBefore(el('p', { class: 'pd-pending', text: st[id] }), host.firstChild);
    });
  }

  function boot() {
    fetch('/api/plato/damage').then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).then(function (d) {
      S.data = d;
      if (d.hero_answer) $('hero-answer').innerHTML = d.hero_answer;
      setupSlider();
      renderHero();
      renderDissociation();
      renderProto();
      renderGlimmer();
      renderJanus();
      renderClocks();
      renderStatus();
    }).catch(function (e) {
      var n = $('load-error');
      n.hidden = false;
      n.textContent = 'Could not load the results (' + e.message + ').';
    });
  }
  boot();
})();
