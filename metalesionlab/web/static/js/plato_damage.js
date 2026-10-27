/* Plato's Chair, damaged: the damage slider, the Form-or-hand dissociation, prototype drift, the damaged
   Glimmer arm and clocks. Everything comes from /api/plato/damage (statistics only) and precomputed
   WebP pictures; no API calls. */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var LANG = '#1D4ED8', DRAW = '#C2410C', GRID = '#E5E7EB', AXIS = '#9CA3AF', INK = '#111827';
  var S = { data: null, kind: null, method: 'noise', level: 0 };
  var OUTCOME = { correct: 'the asked kind', plain: 'a plain, ordinary one', other_kind: 'another kind',
                  cant_tell: 'can’t tell, or not one', specific: 'a specific kind' };

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
  function ciPts(c) { return c ? '95% CI ' + pts(c[0]) + ' to ' + pts(c[1]) : ''; }
  function excludesZero(c) { return c && (c[0] > 0 || c[1] < 0); }

  // ---------- slider ----------
  function fams() { var m = S.data.slider.methods[S.method]; return [m.lang, m.draw]; }

  function readout(p) {
    if (!p) return '';
    var bits = [];
    if (p.change != null && p.change > 0.0005) bits.push('changed ' + f2(p.change));
    if (p.outcome) bits.push('Glimmer: <b>' + (OUTCOME[p.outcome] || p.outcome) + '</b>');
    if (p.name) bits.push('named it “' + p.name.replace(/[<>&]/g, '') + '”');
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
    $('img-lang').alt = 'SDXL asked for a ' + kindLabel + ', language part damaged, ' + (S.level ? 'level ' + S.level : 'intact') +
      (a.name ? '; Glimmer names it ' + a.name : '');
    $('img-draw').alt = 'SDXL asked for a ' + kindLabel + ', drawing part damaged, ' + (S.level ? 'level ' + S.level : 'intact') +
      (b.name ? '; Glimmer names it ' + b.name : '');
    $('read-lang').innerHTML = S.level ? lev[S.level].label + ' · ' + readout(a) : readout(a);
    $('read-draw').innerHTML = S.level ? levD[S.level].label + ' · ' + readout(b) : readout(b);
    var txt = S.level === 0 ? 'intact' : 'level ' + S.level + ' of ' + max;
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
    var W = 440, H = 260, m = { l: 46, r: 92, t: 10, b: 40 };
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
    var labelY = {};
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
        var dot = s('circle', { cx: X(q.x), cy: Y(q.y), r: 4, fill: se.colour, stroke: '#fff', 'stroke-width': 2 });
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
      svg.appendChild(s('text', { x: X(last.x) + 8, y: labelY[k] + 4, class: 'dlab' }, se.name));
    });
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
          '<br>changed ' + f2(q.d_intact) + '<br>value ' + f2(q[measure] + offset) });
    });
    return { name: name, colour: colour, dash: dash, points: points };
  }

  function famPair() { var m = S.data.slider.methods[S.method]; return [m.lang, m.draw]; }

  function tile(host, q, m, unitFn, langWord, drawWord) {
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
    t.appendChild(el('div', { class: 'verdict', text: ok ? 'As predicted.' : rev ? 'Opposite to the prediction.' :
      'Not distinguishable at this n.' }));
    host.appendChild(t);
  }

  function renderDissociation() {
    var d = S.data, f = famPair(), key = f[0] + ' vs ' + f[1], m = d.matched[key] || {};
    var tiles = $('diss-tiles'); tiles.innerHTML = '';
    tile(tiles, 'Still the kind we asked for (Glimmer), change from intact at matched picture change', m.delta_correct,
      pts, 'language', 'drawing');
    tile(tiles, 'Still a clean line drawing (Glimmer’s yes), change from intact', m.delta_p_clean, pts, 'language', 'drawing');
    tile(tiles, '“Is this a drawing of a chair?” (Glimmer’s yes), change from intact', m.delta_p_is_a, pts, 'language', 'drawing');
    var charts = $('diss-charts'); charts.innerHTML = '';
    var c1 = el('div', { class: 'pd-chart' }, [el('h3', { text: 'What it is: still the asked kind' })]);
    var c2 = el('div', { class: 'pd-chart' }, [el('h3', { text: 'How it is drawn: Glimmer says “clean line drawing”' })]);
    charts.appendChild(c1); charts.appendChild(c2);
    var xlab = 'how much the picture changed (DINOv2 distance to its intact twin)';
    lineChart(c1, { label: 'Share of chairs still read as the asked kind, by how much damage changed the picture',
      series: [series(f[0], 'delta_correct', 1, 'language', LANG, false), series(f[1], 'delta_correct', 1, 'drawing', DRAW, true)],
      xlab: xlab, ymin: 0, ymax: 1, yfmt: pct });
    lineChart(c2, { label: 'Change in Glimmer’s P(clean line drawing), by how much damage changed the picture',
      series: [series(f[0], 'delta_p_clean', 0, 'language', LANG, false), series(f[1], 'delta_p_clean', 0, 'drawing', DRAW, true)],
      xlab: xlab, yfmt: f2 });
    $('diss-legend').innerHTML = '<span><i style="border-color:' + LANG + '"></i>language part damaged</span>' +
      '<span><i class="dash" style="border-color:' + DRAW + '"></i>drawing part damaged</span>' +
      '<span>shaded: 95% CI over 64 pictures</span>';
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
    left.appendChild(el('p', { class: 'pd-verdict', text: closer ? 'Partly: some language damage moves the chairs toward the plain chair.' :
      'No. Damaged language does not bring back the plain chair. It wanders off to other things.' }));
    var txt = 'Distance to the plain chair (the average of SDXL’s own “a chair” pictures), change from intact, averaged over the damage levels: ';
    ['text-zero', 'text-noise', 'unet-zero', 'unet-noise'].forEach(function (fam, i) {
      var v = pooled[fam] && pooled[fam].delta_d_proto;
      if (!v) return;
      txt += (i ? '; ' : '') + (fam.indexOf('text') === 0 ? 'language' : 'drawing') + (fam.indexOf('zero') > 0 ? ' (off) ' : ' (noise) ') +
        (v.mean >= 0 ? '+' : '−') + Math.abs(v.mean).toFixed(2) + ' [' + f2(v.ci95[0]) + ', ' + f2(v.ci95[1]) + ']';
    });
    left.appendChild(el('p', { text: txt + '. Positive means farther from the plain chair.' }));
    if (m) left.appendChild(el('p', { text: 'At matched picture change, language minus drawing damage: ' + (m.difference >= 0 ? '+' : '−') +
      Math.abs(m.difference).toFixed(3) + ' (95% CI ' + f2(m.ci95[0]) + ' to ' + f2(m.ci95[1]) + '). The prediction was below zero.' }));
    host.appendChild(left);
    var c = el('div', { class: 'pd-chart' }, [el('h3', { text: 'Distance to the plain chair, change from intact' })]);
    host.appendChild(c);
    lineChart(c, { label: 'Change in distance to the plain-chair prototype by how much the picture changed',
      series: [series('text-zero', 'delta_d_proto', 0, 'language, off', LANG, false), series('text-noise', 'delta_d_proto', 0, 'language, noise', LANG, true),
        series('unet-zero', 'delta_d_proto', 0, 'drawing, off', DRAW, false), series('unet-noise', 'delta_d_proto', 0, 'drawing, noise', DRAW, true)],
      xlab: 'how much the picture changed', yfmt: f2 });
    // what it turned into
    var names = $('names'); names.innerHTML = '';
    [['text-noise', 'lang', 'Language part, noise'], ['text-zero', 'lang', 'Language part, neurons off'],
     ['unet-noise', 'draw', 'Drawing part, noise'], ['unet-zero', 'draw', 'Drawing part, neurons off']].forEach(function (x) {
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
    if (!g || !g.conditions) { host.textContent = 'Still running.'; return; }
    host.innerHTML = '';
    var left = el('div'), right = el('div', { class: 'pd-chart' });
    var vs = g.vs_random || {}, best = null;
    Object.keys(vs).forEach(function (c) { if (c.indexOf('language') === 0 && (!best || vs[c].plain.lesion > vs[best].plain.lesion)) best = c; });
    left.appendChild(el('p', { text: 'Intact, Glimmer picks the right kind for ' + pct(g.intact_accuracy) + ' of ' + g.n_pictures +
      ' doodles of 22 things. Among the ' + g.n_intact_correct + ' it got right, we counted what the damaged Glimmer says instead.' }));
    if (best) {
      var p = vs[best].plain, ct = vs[best].cant_tell;
      left.appendChild(el('p', { class: 'pd-verdict', text: 'Language-neuron damage: ' + pct(p.lesion) + ' of the specific kinds become “a plain, ordinary one”; random neurons: ' + pct(p.random) + '.' }));
      left.appendChild(el('p', { text: 'Difference ' + pts(p.difference.mean) + ' (' + ciPts(p.difference.ci95) + '; by thing ' + ciPts(p.difference_by_concept.ci95).replace('95% CI ', '') +
        '). The same lesion makes “can’t tell” ' + pct(ct.lesion) + ' (random ' + pct(ct.random) + '). That is the semantic-dementia-like pattern: the specific kind falls back to the general one.' }));
    }
    host.appendChild(left);
    host.appendChild(right);
    // dot chart: plain rate, lesion vs random, per family and dose
    var rows = Object.keys(vs).sort();
    var W = 440, rowH = 22, H = 40 + rows.length * rowH, m = { l: 170, r: 20 };
    var X = function (v) { return m.l + (W - m.l - m.r) * v; };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'Share of specific kinds called plain, lesion vs random control' });
    [0, 0.25, 0.5, 0.75, 1].forEach(function (v) {
      svg.appendChild(s('line', { x1: X(v), x2: X(v), y1: 20, y2: H - 10, stroke: GRID }));
      svg.appendChild(s('text', { x: X(v), y: 14, 'text-anchor': 'middle', class: 'lab' }, pct(v)));
    });
    rows.forEach(function (c, i) {
      var y = 32 + i * rowH, v = vs[c];
      var fam = c.split('-')[0], dose = c.split('@')[1];
      svg.appendChild(s('text', { x: m.l - 8, y: y + 4, 'text-anchor': 'end', class: 'dlab' }, fam + ' neurons, top ' + Math.round(dose * 100) + '%'));
      svg.appendChild(s('line', { x1: X(v.plain.random), x2: X(v.plain.lesion), y1: y, y2: y, stroke: AXIS }));
      svg.appendChild(s('circle', { cx: X(v.plain.random), cy: y, r: 4.5, fill: '#fff', stroke: LANG, 'stroke-width': 2 }));
      svg.appendChild(s('circle', { cx: X(v.plain.lesion), cy: y, r: 5, fill: LANG, stroke: '#fff', 'stroke-width': 1.5 }));
    });
    right.appendChild(el('h3', { text: 'Specific kinds now called “a plain, ordinary …”' }));
    right.appendChild(svg);
    right.appendChild(el('div', { class: 'pd-legend' }, [el('span', {}, [el('i', { style: 'border-color:' + LANG + ';width:10px;height:10px;border-radius:50%;background:' + LANG + ';border:0' }), 'targeted lesion']),
      el('span', {}, [el('i', { style: 'width:10px;height:10px;border-radius:50%;border:2px solid ' + LANG }), 'same number of random neurons'])]));
  }

  // ---------- clocks ----------
  function renderClocks() {
    var c = S.data.clocks, host = $('clocks');
    if (!c) { host.textContent = 'Still running.'; return; }
    host.innerHTML = '';
    var left = el('div'), right = el('div');
    if (c.summary) c.summary.forEach(function (t) { left.appendChild(el('p', { text: t })); });
    if (c.features) {
      var tb = el('table', { class: 'pd-table' });
      var head = el('tr', {}, [el('th', { text: 'Condition' })]);
      c.feature_names.forEach(function (n) { head.appendChild(el('th', { class: 'num', text: n })); });
      tb.appendChild(el('thead', {}, head));
      var body = el('tbody');
      c.features.forEach(function (r) {
        var tr = el('tr', {}, [el('td', { text: r.label })]);
        r.values.forEach(function (v) { tr.appendChild(el('td', { class: 'num', text: pct(v) })); });
        body.appendChild(tr);
      });
      tb.appendChild(body);
      left.appendChild(tb);
    }
    var strip = c.strip || {}, method = 'noise';
    ['3_00', '8_45'].forEach(function (t) {
      var grid = el('div', { class: 'pd-clockgrid' });
      grid.appendChild(el('div', { class: 'h', text: t.replace('_', ':') }));
      ['intact', 'level 1', 'level 2', 'level 3'].forEach(function (h) { grid.appendChild(el('div', { class: 'h', text: h })); });
      [['text-' + method, 'lang', 'language'], ['unet-' + method, 'draw', 'drawing']].forEach(function (x) {
        var seq = (strip[x[0]] || {})[t] || [];
        grid.appendChild(el('div', { class: 'r ' + x[1], text: x[2] }));
        seq.forEach(function (p) { grid.appendChild(el('img', { src: p.img, alt: 'Clock asked to show ' + t.replace('_', ':') + ', ' + x[2] + ' part damaged, ' + p.label, loading: 'lazy' })); });
      });
      right.appendChild(grid);
    });
    host.appendChild(left);
    host.appendChild(right);
  }

  function boot() {
    fetch('/api/plato/damage').then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).then(function (d) {
      S.data = d;
      if (d.hero_answer) $('hero-answer').innerHTML = d.hero_answer;
      setupSlider();
      renderDissociation();
      renderProto();
      renderGlimmer();
      renderClocks();
    }).catch(function (e) {
      var n = $('load-error');
      n.hidden = false;
      n.textContent = 'Could not load the results (' + e.message + ').';
    });
  }
  boot();
})();
