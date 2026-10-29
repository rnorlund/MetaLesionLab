/* The Atlas of Forms: the Gallery of Forms (search, sort, filter, a detail view per thing), the ranking of all
   135 things, the predictor charts and the numbers. Data: /api/plato/atlas (statistics and picture names only);
   no API calls, nothing stored. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var IMG = '/static/img/plato_atlas/';
  var NS = 'http://www.w3.org/2000/svg';
  // the theme's tokens (app.css), so the charts follow the light or dark theme without redrawing
  var C = { muse: 'var(--blue)', sdxl: 'var(--teal)', people: 'var(--orange)', natural: 'var(--green)', artifact: 'var(--violet)',
            ink: 'var(--ink)', ink2: 'var(--ink-2)', muted: 'var(--faint)', grid: 'var(--line)', axis: 'var(--line-3)', surface: 'var(--chart-halo)' };
  var BAR_MAX = 1.6;
  var D = null, BY = {}, S = { q: '', sort: 'platonic', domain: '', all: false }, shown = [], cur = -1;

  function $(id) { return document.getElementById(id); }
  function f2(x) { return x == null ? '–' : Number(x).toFixed(2); }
  function ci(c) { return c ? f2(c[0]) + '–' + f2(c[1]) : ''; }
  function pct(x) { return Math.round(x * 100); }
  function plural(label) {
    var irregular = { mouse: 'mice', person: 'people', tooth: 'teeth', foot: 'feet', knife: 'knives', leaf: 'leaves',
                      sheep: 'sheep', fish: 'fish', 'roller skates': 'pairs of roller skates', pants: 'pairs of pants',
                      'flip flops': 'pairs of flip flops', binoculars: 'pairs of binoculars', headphones: 'pairs of headphones',
                      scissors: 'pairs of scissors', drums: 'drum kits', grapes: 'bunches of grapes', peas: 'pea pods',
                      rain: 'rain clouds', asparagus: 'asparagus', 'ice cream': 'ice creams', moon: 'moons', face: 'faces' };
    if (irregular[label]) return irregular[label];
    if (/(s|x|ch|sh)$/.test(label)) return label + 'es';
    if (/[^aeiou]y$/.test(label)) return label.slice(0, -1) + 'ies';
    return label + 's';
  }
  function s(tag, attrs, kids) {
    var el = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) el.setAttribute(k, attrs[k]); });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c == null) return;
      el.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return el;
  }
  function domainName(d) { return d.charAt(0).toUpperCase() + d.slice(1); }

  // --- tooltips ------------------------------------------------------------------------------
  function showTip(wrap, px, py, lines) {
    var tip = wrap.querySelector('.at-tip');
    if (!tip) { tip = h('div', { class: 'at-tip', role: 'presentation' }); wrap.appendChild(tip); }
    tip.innerHTML = '';
    lines.forEach(function (l, i) {
      if (i === 0) { tip.appendChild(h('b', { text: l })); return; }
      var row = h('div');
      if (l.color) { var k = h('span', { class: 'k' }); k.style.background = l.color; row.appendChild(k); }
      row.appendChild(document.createTextNode(l.text || l));
      tip.appendChild(row);
    });
    tip.hidden = false;
    var w = wrap.clientWidth, left = px + 14, top = py + 12;
    if (left + tip.offsetWidth > w) left = Math.max(0, px - tip.offsetWidth - 14);
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
  }
  function hideTip(wrap) { var t = wrap.querySelector('.at-tip'); if (t) t.hidden = true; }

  // --- hero ----------------------------------------------------------------------------------
  function hero() {
    var lead = window.FirstLook.atlas(D);
    window.FirstLook.render($('tiles'), lead);
    $('hero-note').textContent = lead.note;
    var box = $('hero-forms');
    box.innerHTML = '';
    var pick = [BY.chair].concat(D.concepts.filter(function (c) { return c.key !== 'chair'; }).slice(0, 7));
    pick.forEach(function (c) {
      if (!c) return;
      box.appendChild(h('figure', { class: 'at-hf' }, [
        h('img', { class: 'm', src: IMG + c.form_muse, width: 152, height: 152, alt: 'The average of Muse Image’s 12 ' + plural(c.label) + ': crisp lines.' }),
        h('img', { class: 'p', src: IMG + c.form_people, width: 152, height: 152, alt: 'The average of 12 people’s ' + plural(c.label) + ': a blurred cloud.' }),
        h('span', null, [c.label, h('small', { text: f2(c.ratio) + '× as varied' })])
      ]));
    });
  }

  // --- the gallery ---------------------------------------------------------------------------
  function controls() {
    var sel = $('domain');
    D.domains.forEach(function (d) {
      var n = D.concepts.filter(function (c) { return c.domain === d; }).length;
      if (n) sel.appendChild(h('option', { value: d, text: domainName(d) + ' (' + n + ')' }));
    });
    sel.addEventListener('change', function () { S.domain = sel.value; gallery(); });
    var q = $('q'), timer = null;
    q.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(function () { S.q = q.value; gallery(); }, 120); });
    $('more').addEventListener('click', function () {
      var first = $('grid').children.length;
      S.all = true;
      gallery();
      var next = $('grid').children[first];
      if (next) next.focus();
    });
    $('sort').addEventListener('click', function (e) {
      var b = e.target.closest('button[data-sort]');
      if (!b) return;
      S.sort = b.dataset.sort;
      $('sort').querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      gallery();
    });
  }

  function filtered() {
    var q = S.q.trim().toLowerCase();
    var list = D.concepts.filter(function (c) {
      return (!S.domain || c.domain === S.domain) &&
        (!q || c.label.toLowerCase().indexOf(q) >= 0 || c.quickdraw.toLowerCase().indexOf(q) >= 0 || c.domain.indexOf(q) >= 0);
    });
    if (S.sort === 'varied') list.sort(function (a, b) { return b.ratio - a.ratio; });
    else if (S.sort === 'az') list.sort(function (a, b) { return a.label.localeCompare(b.label); });
    else list.sort(function (a, b) { return a.rank - b.rank; });
    return list;
  }

  function bar(r) {
    var b = h('span', { class: 'at-bar', 'aria-hidden': 'true' }, [h('i'), h('s')]);
    b.firstChild.style.width = Math.min(100, r / BAR_MAX * 100) + '%';
    b.lastChild.style.left = 'calc(' + (100 / BAR_MAX) + '% - 1px)';
    return b;
  }

  function card(c, i) {
    var el = h('button', { type: 'button', class: 'at-card' + (c.ratio >= 1 ? ' over' : ''),
      'aria-label': c.label + ': Muse Image’s drawings are ' + f2(c.ratio) + ' times as varied as people’s, rank ' + c.rank + ' of ' + D.concepts.length +
        '. Open the drawings.' }, [
      h('span', { class: 'at-pair' }, [
        h('figure', null, [h('img', { src: IMG + c.form_muse, width: 152, height: 152, loading: 'lazy', decoding: 'async', alt: '' }), h('figcaption', { text: 'Muse' })]),
        h('figure', null, [h('img', { src: IMG + c.form_people, width: 152, height: 152, loading: 'lazy', decoding: 'async', alt: '' }), h('figcaption', { text: 'people' })])
      ]),
      h('span', { class: 'at-card-name' }, [h('b', { text: c.label }), h('span', { class: 'rank', text: '#' + c.rank })]),
      h('span', { class: 'at-card-ratio' }, [h('span', { class: 'v', text: f2(c.ratio) }), bar(c.ratio), h('span', { class: 'ci', text: ci(c.ci) })])
    ]);
    el.addEventListener('click', function () { openDetail(i); });
    return el;
  }

  function firstRows() {
    // four rows of whatever the grid's column count is at this width (two columns on a phone: 12 cards)
    var cols = getComputedStyle($('grid')).gridTemplateColumns.split(' ').filter(Boolean).length || 4;
    return cols * (cols <= 2 ? 6 : 4);
  }

  function gallery() {
    shown = filtered();
    var grid = $('grid'), frag = document.createDocumentFragment();
    grid.innerHTML = '';
    // the whole list when searching or filtering; otherwise the first rows, then a button for the rest
    var limit = S.q || S.domain || S.all ? shown.length : Math.min(shown.length, firstRows());
    shown.slice(0, limit).forEach(function (c, i) { frag.appendChild(card(c, i)); });
    if (!shown.length) frag.appendChild(h('p', { class: 'at-empty', text: 'No thing matches “' + S.q + '”. The Atlas has ' + D.concepts.length + ' things; try “cat”, “rain” or “chair”.' }));
    grid.appendChild(frag);
    var more = $('more');
    more.hidden = limit >= shown.length;
    more.textContent = 'Show all ' + shown.length + ' things';
    var below = shown.filter(function (c) { return c.ratio < 1; }).length;
    $('count').textContent = shown.length === D.concepts.length
      ? 'All ' + shown.length + ' things · Muse Image draws ' + below + ' of them more alike than people do'
      : shown.length + ' of ' + D.concepts.length + ' things · Muse Image draws ' + below + ' of these more alike than people do';
  }

  // --- the detail view -----------------------------------------------------------------------
  function verdict(c) {
    var things = plural(c.label);
    var range = f2(c.ratio) + ' times as varied; probably between ' + f2(c.ci[0]) + ' and ' + f2(c.ci[1]) + ', a 95% confidence interval';
    if (c.ratio < 1) {
      return 'Muse Image’s ' + things + ' are ' + pct(1 - c.ratio) + '% less varied than people’s (' + range + ').' +
        (c.ci[1] >= 1 ? ' That range reaches 1 (just as varied), so people may vary them as little.' : '');
    }
    return 'Muse Image varies its ' + things + (c.ci[0] > 1 ? ' more than people do' : ' about as much as people do') +
      ' (' + range + ').' + (c.ci[0] > 1 ? '' : ' That range includes 1 (just as varied).');
  }

  function stat(dt, dd) { return h('div', null, [h('dt', { text: dt }), h('dd', { text: dd })]); }

  function openDetail(i) {
    if (i < 0 || i >= shown.length) return;
    cur = i;
    var c = shown[i], n = D.concepts.length;
    $('d-rank').textContent = 'Rank ' + c.rank + ' of ' + n + ' (1 = drawn most alike) · ' + domainName(c.domain) +
      (c.origin === 'new' ? ' · new in the Atlas' : c.origin === 'forms' ? ' · Plato’s own example' : ' · one of the 35 things of our first experiment');
    $('d-title').textContent = c.label;
    $('d-verdict').textContent = verdict(c);
    $('d-muse-n').textContent = c.n_ai > 12 ? 'its first 12 of ' + c.n_ai + ' (the numbers use all ' + c.n_ai + ')' : 'the same request, in 3 batches of 4';
    [['m', 'muse'], ['p', 'people']].forEach(function (p) {
      var who = p[1] === 'muse' ? 'Muse Image’s' : 'people’s';
      $('d-form-' + p[0]).src = IMG + c['form_' + p[1]];
      $('d-form-' + p[0]).alt = 'The pixel average of ' + who + ' 12 ' + plural(c.label) + '.';
      $('d-tiles-' + p[0]).src = IMG + c['tiles_' + p[1]];
      $('d-tiles-' + p[0]).alt = who.charAt(0).toUpperCase() + who.slice(1) + ' 12 drawings of ' + (c.label) + ', cropped to their ink.';
    });
    var dl = $('d-stats');
    dl.innerHTML = '';
    dl.appendChild(stat('Muse Image’s spread (how different its drawings are; 0 = identical)', f2(c.muse_spread)));
    dl.appendChild(stat('People’s spread (same number of drawings)', f2(c.human_spread)));
    if (c.sdxl_ratio != null) dl.appendChild(stat('Stable Diffusion XL (an open image AI), compared with people', f2(c.sdxl_ratio) + '× as varied (' + ci(c.sdxl_ci) + ')'));
    if (c.pixel_ratio != null) dl.appendChild(stat('Muse Image compared with people, measured on raw pixels', f2(c.pixel_ratio) + '× as varied'));
    dl.appendChild(stat('How common the word is (Zipf scale: 4 = once per 100,000 words)', c.zipf.toFixed(1)));
    dl.appendChild(stat('Muse Image’s drawings that look closer to people’s ' + plural(c.label) + ' than to any of the other ' + (n - 1) + ' things', pct(c.recognized) + '%'));
    $('d-prev').disabled = i === 0;
    $('d-next').disabled = i === shown.length - 1;
    var dlg = $('detail');
    if (!dlg.open) { if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', ''); }
  }

  function closeDetail() {
    var dlg = $('detail');
    if (dlg.open) { if (dlg.close) dlg.close(); else dlg.removeAttribute('open'); }
    var cards = $('grid').querySelectorAll('.at-card');
    if (cards[cur]) cards[cur].focus();
  }

  function detailEvents() {
    $('d-close').addEventListener('click', closeDetail);
    $('d-prev').addEventListener('click', function () { openDetail(cur - 1); });
    $('d-next').addEventListener('click', function () { openDetail(cur + 1); });
    $('detail').addEventListener('click', function (e) { if (e.target === $('detail')) closeDetail(); });
    $('detail').addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') { openDetail(cur - 1); e.preventDefault(); }
      if (e.key === 'ArrowRight') { openDetail(cur + 1); e.preventDefault(); }
    });
  }

  function openByKey(key) {
    S.q = ''; S.domain = ''; S.all = true; $('q').value = ''; $('domain').value = '';
    gallery();
    var i = shown.findIndex(function (c) { return c.key === key; });
    if (i >= 0) openDetail(i);
  }

  // --- the ranking ---------------------------------------------------------------------------
  function legend(el, items) {
    el.innerHTML = '';
    items.forEach(function (it) {
      var k = h('i', { class: it.shape || '' });
      k.style.background = it.color;
      el.appendChild(h('span', null, [k, it.label]));
    });
  }

  function ranking() {
    var wrap = $('rank-chart'), rows = D.concepts.slice().sort(function (a, b) { return a.rank - b.rank; });
    var W = Math.max(300, wrap.clientWidth), small = W < 600, H = small ? 230 : Math.round(Math.min(400, Math.max(300, W * 0.2)));
    var m = { l: 34, r: 8, t: 22, b: 26 }, n = rows.length, band = (W - m.l - m.r) / n;
    var ymax = Math.ceil(Math.max.apply(null, rows.map(function (r) { return Math.max(r.ratio, r.sdxl_ratio || 0); })) * 2) / 2;
    var y = function (v) { return m.t + (H - m.t - m.b) * (1 - v / ymax); };
    var x = function (i) { return m.l + band * i; };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'img',
      'aria-label': 'Columns: how varied Muse Image’s drawings are compared with people’s, for all ' + n + ' things, from the most alike to the most varied; ' +
        'dots: the same for Stable Diffusion XL. A line marks people’s level, 1. The table below has every number.' });
    for (var t = 0; t <= ymax + 1e-9; t += 0.5) {
      svg.appendChild(s('line', { x1: m.l, x2: W - m.r, y1: y(t), y2: y(t), stroke: t === 1 ? C.ink2 : C.grid, 'stroke-width': t === 1 ? 1.5 : 1 }));
      svg.appendChild(s('text', { x: m.l - 6, y: y(t) + 4, 'text-anchor': 'end', 'font-size': 11, fill: C.muted }, t.toFixed(1)));
    }
    svg.appendChild(s('text', { x: m.l + 4, y: y(1) - 6, 'font-size': 11.5, fill: C.ink2 }, 'people = 1'));
    var gap = band > 4 ? 1.5 : 0.5, cw = Math.min(24, Math.max(1, band - gap));
    var cols = s('g'), dots = s('g'), hl = s('rect', { fill: 'var(--tint-2)', width: band, height: H - m.t - m.b + 6, y: m.t - 6, visibility: 'hidden' });
    svg.appendChild(hl);
    rows.forEach(function (r, i) {
      var top = y(r.ratio), base = y(0), rad = Math.min(cw / 2, 3);
      var path = 'M' + (x(i) + (band - cw) / 2) + ',' + base + 'V' + (top + rad) + 'q0,-' + rad + ' ' + rad + ',-' + rad +
        'h' + (cw - 2 * rad) + 'q' + rad + ',0 ' + rad + ',' + rad + 'V' + base + 'Z';
      cols.appendChild(s('path', { d: path, fill: C.muse }));
      if (r.sdxl_ratio != null) {
        dots.appendChild(s('circle', { cx: x(i) + band / 2, cy: y(r.sdxl_ratio), r: small ? 2.2 : 3.4, fill: C.sdxl,
          stroke: C.surface, 'stroke-width': small ? 0.8 : 1.2 }));
      }
    });
    svg.appendChild(cols);
    svg.appendChild(dots);
    // direct labels: the two ends
    var first = rows[0], last = rows[n - 1];
    svg.appendChild(s('text', { x: x(0), y: m.t - 8, 'font-size': 11.5, fill: C.ink2 }, '← most alike: ' + first.label));
    svg.appendChild(s('text', { x: W - m.r, y: m.t - 8, 'text-anchor': 'end', 'font-size': 11.5, fill: C.ink2 }, 'most varied: ' + last.label + ' →'));
    var hit = s('rect', { x: m.l, y: 0, width: W - m.l - m.r, height: H, fill: 'transparent', tabindex: 0,
      'aria-label': 'Ranking chart. Use the left and right arrow keys to step through the things; Enter opens one.', style: 'cursor:pointer;outline:none' });
    svg.appendChild(hit);
    wrap.innerHTML = '';
    wrap.appendChild(svg);
    var at = -1;
    function point(i, px, py) {
      at = Math.max(0, Math.min(n - 1, i));
      var r = rows[at];
      hl.setAttribute('x', x(at));
      hl.setAttribute('visibility', 'visible');
      showTip(wrap, px == null ? x(at) * wrap.clientWidth / W : px, py == null ? y(Math.max(r.ratio, r.sdxl_ratio || 0)) * wrap.clientWidth / W : py, [
        '#' + r.rank + ' ' + r.label,
        { text: 'Muse Image: ' + f2(r.ratio) + '× as varied as people (' + ci(r.ci) + ')', color: C.muse },
        r.sdxl_ratio != null ? { text: 'Stable Diffusion XL: ' + f2(r.sdxl_ratio) + '×', color: C.sdxl } : '',
        'Click to see the drawings'].filter(Boolean));
    }
    hit.addEventListener('pointermove', function (e) {
      var b = wrap.getBoundingClientRect(), sc = W / b.width;
      point(Math.floor(((e.clientX - b.left) * sc - m.l) / band), e.clientX - b.left, e.clientY - b.top);
    });
    hit.addEventListener('pointerleave', function () { hl.setAttribute('visibility', 'hidden'); hideTip(wrap); });
    hit.addEventListener('blur', function () { hl.setAttribute('visibility', 'hidden'); hideTip(wrap); });
    hit.addEventListener('click', function () { if (at >= 0) openByKey(rows[at].key); });
    hit.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { point(at + (e.key === 'ArrowRight' ? 1 : -1)); e.preventDefault(); }
      if (e.key === 'Enter' && at >= 0) openByKey(rows[at].key);
    });
    legend($('rank-legend'), [{ color: C.muse, label: 'Muse Image' }, { color: C.sdxl, label: 'Stable Diffusion XL (an open image AI, same request)', shape: 'dot' }]);
  }

  function rankText() {
    var a = D.summary.all, sd = D.summary.sdxl.all, mv = D.summary.muse_vs_sdxl.all;
    var over = D.summary.above_1;
    $('ranking-lede').textContent = 'Each column is one thing: how varied Muse Image’s drawings of it are, compared with people’s. Below the line at 1, ' +
      'Muse Image draws the thing more alike than people do. Only ' + (over.length ? over.length + ' things (' + over.join(', ') + ')' : 'none') +
      ' reach' + (over.length === 1 ? 'es' : '') + ' the line. ' +
      'The dots are Stable Diffusion XL, an open image AI from Stability AI, given the same request. It draws ' + mv.muse_more_uniform + ' of the ' + mv.n +
      ' things more varied than Muse Image does, and a typical thing ' + f2(sd.median) + ' times as varied as people. So drawing everything the same way is ' +
      'Muse Image’s habit, not something every image AI does.';
    $('rank-cap').textContent = 'For a typical thing, Muse Image’s drawings are ' + f2(a.median) + ' times as varied as people’s (probably between ' +
      f2(a.median_ci95[0]) + ' and ' + f2(a.median_ci95[1]) + '). Hover or tap a column for its numbers; click to see the drawings. ' +
      'With only 12 pictures per thing, one thing’s exact rank is uncertain: the table gives each one’s likely range.';
    var tb = $('rank-table');
    tb.innerHTML = '';
    tb.appendChild(h('thead', null, h('tr', null, ['Rank', 'Thing', 'Kind', 'Muse Image ÷ people', 'Likely range (95% CI)', 'Stable Diffusion XL ÷ people', 'Muse Image’s spread', 'People’s spread', 'From'].map(function (t) { return h('th', { scope: 'col', text: t }); }))));
    var body = h('tbody');
    D.concepts.slice().sort(function (a, b) { return a.rank - b.rank; }).forEach(function (c) {
      body.appendChild(h('tr', null, [h('td', { class: 'n', text: String(c.rank) }), h('td', { text: c.label }), h('td', { text: domainName(c.domain) }),
        h('td', { class: 'n', text: f2(c.ratio) }), h('td', { class: 'n', text: ci(c.ci) }), h('td', { class: 'n', text: f2(c.sdxl_ratio) }),
        h('td', { class: 'n', text: f2(c.muse_spread) }), h('td', { class: 'n', text: f2(c.human_spread) }),
        h('td', { text: c.origin === 'new' ? 'new' : c.origin === 'forms' ? 'Plato’s own example' : 'our first 35' })]));
    });
    tb.appendChild(body);
  }

  // --- what makes a thing Platonic? ----------------------------------------------------------
  function scatter(wrap, pts, o) {
    var W = Math.max(260, wrap.clientWidth), H = Math.round(Math.min(440, W * 0.78));
    var m = { l: 40, r: 10, t: 12, b: 40 };
    var xs = pts.map(function (p) { return p.x; }), ys = pts.map(function (p) { return p.y; });
    var x0 = o.x0 != null ? o.x0 : Math.min.apply(null, xs), x1 = o.x1 != null ? o.x1 : Math.max.apply(null, xs);
    var y0 = o.y0 != null ? o.y0 : 0, y1 = o.y1 != null ? o.y1 : Math.max.apply(null, ys);
    var px = (x1 - x0) * 0.04; x0 -= px; x1 += px;
    var X = function (v) { return m.l + (W - m.l - m.r) * (v - x0) / (x1 - x0); };
    var Y = function (v) { return m.t + (H - m.t - m.b) * (1 - (v - y0) / (y1 - y0)); };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'img', 'aria-label': o.aria });
    o.yticks.forEach(function (t) {
      svg.appendChild(s('line', { x1: m.l, x2: W - m.r, y1: Y(t), y2: Y(t), stroke: C.grid }));
      svg.appendChild(s('text', { x: m.l - 6, y: Y(t) + 4, 'text-anchor': 'end', 'font-size': 11, fill: C.muted }, o.yfmt ? o.yfmt(t) : String(t)));
    });
    o.xticks.forEach(function (t) {
      svg.appendChild(s('text', { x: X(t), y: H - m.b + 16, 'text-anchor': 'middle', 'font-size': 11, fill: C.muted }, o.xfmt ? o.xfmt(t) : String(t)));
    });
    svg.appendChild(s('line', { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, stroke: C.axis }));
    if (o.diag) {
      var d0 = Math.max(x0, y0), d1 = Math.min(x1, y1);
      svg.appendChild(s('line', { x1: X(d0), y1: Y(d0), x2: X(d1), y2: Y(d1), stroke: C.ink2, 'stroke-width': 1.5 }));
      svg.appendChild(s('text', { x: X(d1) - 4, y: Y(d1) + 14, 'text-anchor': 'end', 'font-size': 11, fill: C.ink2 }, o.diag));
    }
    if (o.hline != null) {
      svg.appendChild(s('line', { x1: m.l, x2: W - m.r, y1: Y(o.hline), y2: Y(o.hline), stroke: C.ink2, 'stroke-width': 1.5 }));
      svg.appendChild(s('text', { x: m.l + 4, y: Y(o.hline) + 14, 'font-size': 11, fill: C.ink2 }, o.hlabel || ''));
    }
    svg.appendChild(s('text', { x: m.l + (W - m.l - m.r) / 2, y: H - 6, 'text-anchor': 'middle', 'font-size': 12, fill: C.ink2 }, o.xlabel));
    svg.appendChild(s('text', { x: m.l, y: m.t - 1, 'font-size': 12, fill: C.ink2, 'dominant-baseline': 'hanging', dx: 4 }, o.ylabel));
    var g = s('g');
    pts.forEach(function (p) {
      p.sx = X(p.x); p.sy = Y(Math.min(p.y, y1));
      g.appendChild(s('circle', { cx: p.sx, cy: p.sy, r: 4, fill: p.color, 'fill-opacity': 0.85, stroke: C.surface, 'stroke-width': 1.5 }));
    });
    svg.appendChild(g);
    var ring = s('circle', { r: 7, fill: 'none', stroke: C.ink, 'stroke-width': 2, visibility: 'hidden' });
    svg.appendChild(ring);
    wrap.innerHTML = '';
    wrap.appendChild(svg);
    var near = null;
    svg.addEventListener('pointermove', function (e) {
      var b = wrap.getBoundingClientRect(), sc = W / b.width, mx = (e.clientX - b.left) * sc, my = (e.clientY - b.top) * sc;
      near = null;
      var best = 24 * 24;
      pts.forEach(function (p) { var d = (p.sx - mx) * (p.sx - mx) + (p.sy - my) * (p.sy - my); if (d < best) { best = d; near = p; } });
      if (!near) { ring.setAttribute('visibility', 'hidden'); hideTip(wrap); svg.style.cursor = ''; return; }
      ring.setAttribute('cx', near.sx); ring.setAttribute('cy', near.sy); ring.setAttribute('visibility', 'visible');
      svg.style.cursor = 'pointer';
      showTip(wrap, near.sx / sc, near.sy / sc, o.tip(near.c));
    });
    svg.addEventListener('pointerleave', function () { ring.setAttribute('visibility', 'hidden'); hideTip(wrap); });
    svg.addEventListener('click', function () { if (near) openByKey(near.c.key); });
  }

  // a rank correlation in words: "0.26 on a scale from −1 to 1 (probably between 0.08 and 0.42)"
  function rhoText(r) { return f2(r.rho) + ' on a scale from −1 to 1 (probably between ' + f2(r.ci95[0]) + ' and ' + f2(r.ci95[1]) + ')'; }
  function clear(r) { return r.ci95[0] > 0 || r.ci95[1] < 0; }

  function predictors() {
    var P = D.predictors, cs = D.concepts;
    var col = function (c) { return c.natural ? C.natural : C.artifact; };
    var p1 = P.P1_muse_spread_vs_human_spread;
    var under = cs.filter(function (c) { return c.muse_spread < c.human_spread; }).length;
    $('p1-text').textContent = (clear(p1) && p1.rho > 0
      ? 'A little. Things people draw in more ways are somewhat more likely to be ones Muse Image varies too, but the link is weak: '
      : 'No clear link between how varied people’s drawings are and how varied Muse Image’s are: ') + rhoText(p1) +
      '. ' + under + ' of ' + cs.length + ' dots sit below the line, where Muse Image is less varied than people.';
    legend($('p1-legend'), [{ color: C.natural, label: 'natural', shape: 'dot' }, { color: C.artifact, label: 'made by people', shape: 'dot' }]);
    var hs = cs.map(function (c) { return c.human_spread; }), ms = cs.map(function (c) { return c.muse_spread; });
    var top = Math.ceil(Math.max(Math.max.apply(null, hs), Math.max.apply(null, ms)) * 10) / 10;
    var left = Math.floor(Math.min.apply(null, hs) * 10) / 10;
    scatter($('p1-chart'), cs.map(function (c) { return { x: c.human_spread, y: c.muse_spread, color: col(c), c: c }; }), {
      x0: left, x1: top, y0: 0, y1: top, xticks: [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6].filter(function (t) { return t >= left - 1e-9 && t <= top; }),
      yticks: [0, 0.1, 0.2, 0.3, 0.4, 0.5].filter(function (t) { return t <= top; }), xfmt: function (t) { return t.toFixed(1); }, yfmt: function (t) { return t.toFixed(1); },
      diag: 'as varied as people', xlabel: 'How varied people’s drawings are (spread) →', ylabel: '↑ Muse Image’s spread',
      aria: 'Each dot is one of ' + cs.length + ' things: how varied people’s drawings of it are (across) against how varied Muse Image’s are (up). ' +
        'Nearly all lie below the diagonal, where Muse Image is less varied.',
      tip: function (c) { return [c.label, { text: 'Muse Image’s spread ' + f2(c.muse_spread), color: C.muse }, { text: 'people’s spread ' + f2(c.human_spread), color: C.people }, c.natural ? 'natural' : 'made by people']; } });

    var p2 = P.P2_ratio_vs_zipf;
    $('p2-text').textContent = (clear(p2)
      ? (p2.rho < 0 ? 'A little: Muse Image draws things with common names a little more alike than things with rare ones: '
        : 'A little: Muse Image draws things with rare names a little more alike than things with common ones: ')
      : 'No clear link: Muse Image draws things with common names (cat, house) and rare ones (anvil, hedgehog) about equally alike: ') + rhoText(p2) + '.';
    var zs = cs.map(function (c) { return c.zipf; }), rmax = Math.max(1.2, Math.ceil(Math.max.apply(null, cs.map(function (c) { return c.ratio; })) * 5) / 5);
    var zt = [];
    for (var z = Math.ceil(Math.min.apply(null, zs)); z <= Math.max.apply(null, zs); z++) zt.push(z);
    scatter($('p2-chart'), cs.map(function (c) { return { x: c.zipf, y: c.ratio, color: C.muse, c: c }; }), {
      y0: 0, y1: rmax, xticks: zt, yticks: [0, 0.5, 1].concat(rmax >= 1.5 ? [1.5] : []), yfmt: function (t) { return t.toFixed(1); },
      hline: 1, hlabel: 'people = 1', xlabel: 'How common the word is (4 = once per 100,000 words) →', ylabel: '↑ Muse Image, × as varied as people',
      aria: 'Each dot is one thing: how common its name is (across) against how varied Muse Image’s drawings are compared with people’s (up); no clear trend.',
      tip: function (c) { return [c.label, { text: 'Muse Image: ' + f2(c.ratio) + '× as varied as people', color: C.muse }, 'word frequency ' + c.zipf.toFixed(1) + ' (Zipf scale)']; } });

    var p3 = P.P3_natural_minus_artifact_log_ratio, med = P.P3_median_ratio;
    var rel = Math.exp(p3.diff) - 1, sameish = !clear(p3);
    $('p3-text').textContent = (sameish ? 'No clear difference. ' : '') + 'For a typical natural thing, Muse Image’s drawings are ' + f2(med.natural) +
      ' times as varied as people’s (' + med.n_natural + ' things); for a typical thing made by people, ' + f2(med.artifact) + ' (' + med.n_artifact +
      ' things). On average the number is ' + (rel >= 0 ? pct(rel) + '% higher' : pct(-rel) + '% lower') + ' for natural things (likely range ' +
      pct(Math.exp(p3.ci95[0]) - 1) + '% to ' + pct(Math.exp(p3.ci95[1]) - 1) + '%).';
    strip($('p3-chart'), cs, rmax);
  }

  function strip(wrap, cs, rmax) {
    var W = Math.max(260, wrap.clientWidth), H = Math.round(Math.min(440, Math.max(220, W * 0.6))), m = { l: 92, r: 10, t: 10, b: 40 };
    var X = function (v) { return m.l + (W - m.l - m.r) * v / rmax; };
    var groups = [{ name: 'Natural', key: true, color: C.natural }, { name: 'Made by people', key: false, color: C.artifact }];
    var rowH = (H - m.t - m.b) / 2;
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'img',
      'aria-label': 'How varied Muse Image’s drawings are compared with people’s, for natural things and for things made by people, one dot each, with each group’s middle value.' });
    [0, 0.5, 1, 1.5].filter(function (t) { return t <= rmax; }).forEach(function (t) {
      svg.appendChild(s('line', { x1: X(t), x2: X(t), y1: m.t, y2: H - m.b, stroke: t === 1 ? C.ink2 : C.grid, 'stroke-width': t === 1 ? 1.5 : 1 }));
      svg.appendChild(s('text', { x: X(t), y: H - m.b + 16, 'text-anchor': 'middle', 'font-size': 11, fill: C.muted }, t.toFixed(1)));
    });
    svg.appendChild(s('text', { x: m.l + (W - m.l - m.r) / 2, y: H - 6, 'text-anchor': 'middle', 'font-size': 12, fill: C.ink2 }, 'Muse Image, × as varied as people →'));
    var pts = [];
    groups.forEach(function (g, gi) {
      var cy = m.t + rowH * (gi + 0.5);
      svg.appendChild(s('text', { x: m.l - 10, y: cy + 4, 'text-anchor': 'end', 'font-size': 12, fill: C.ink2 }, g.name));
      var rs = cs.filter(function (c) { return c.natural === g.key; }).sort(function (a, b) { return a.ratio - b.ratio; });
      rs.forEach(function (c, i) {
        var jy = ((i * 37) % 11 - 5) / 5 * rowH * 0.32;  // deterministic jitter
        var p = { sx: X(Math.min(c.ratio, rmax)), sy: cy + jy, c: c };
        pts.push(p);
        svg.appendChild(s('circle', { cx: p.sx, cy: p.sy, r: 4, fill: g.color, 'fill-opacity': 0.8, stroke: C.surface, 'stroke-width': 1.5 }));
      });
      var vals = rs.map(function (c) { return c.ratio; }), mid = vals.length % 2 ? vals[(vals.length - 1) / 2] : (vals[vals.length / 2 - 1] + vals[vals.length / 2]) / 2;
      svg.appendChild(s('line', { x1: X(mid), x2: X(mid), y1: cy - rowH * 0.42, y2: cy + rowH * 0.42, stroke: C.ink, 'stroke-width': 3, 'stroke-linecap': 'round' }));
    });
    var ring = s('circle', { r: 7, fill: 'none', stroke: C.ink, 'stroke-width': 2, visibility: 'hidden' });
    svg.appendChild(ring);
    wrap.innerHTML = '';
    wrap.appendChild(svg);
    var near = null;
    svg.addEventListener('pointermove', function (e) {
      var b = wrap.getBoundingClientRect(), sc = W / b.width, mx = (e.clientX - b.left) * sc, my = (e.clientY - b.top) * sc;
      near = null;
      var best = 24 * 24;
      pts.forEach(function (p) { var d = (p.sx - mx) * (p.sx - mx) + (p.sy - my) * (p.sy - my); if (d < best) { best = d; near = p; } });
      if (!near) { ring.setAttribute('visibility', 'hidden'); hideTip(wrap); return; }
      ring.setAttribute('cx', near.sx); ring.setAttribute('cy', near.sy); ring.setAttribute('visibility', 'visible');
      showTip(wrap, near.sx / sc, near.sy / sc, [near.c.label, { text: 'Muse Image: ' + f2(near.c.ratio) + '× as varied as people', color: C.muse }]);
    });
    svg.addEventListener('pointerleave', function () { ring.setAttribute('visibility', 'hidden'); hideTip(wrap); });
    svg.addEventListener('click', function () { if (near) openByKey(near.c.key); });
  }

  function whyCaption() {
    var ols = D.predictors.P4_ols_log_muse_spread, b = ols.coefficients;
    $('why-cap').textContent = 'Taken together, the three guesses explain only ' + pct(ols.r2) + '% of the differences in how varied Muse Image’s drawings are: ' +
      'most of why it draws one thing more alike than another is something else. (In detail: a regression of log Muse Image spread on log people’s spread, ' +
      'word frequency and natural; people’s spread ' + f2(b.log_human_spread.b) + ' [95% CI ' + ci(b.log_human_spread.ci95) + '], word frequency ' +
      f2(b.zipf.b) + ' [' + ci(b.zipf.ci95) + '], natural ' + f2(b.natural.b) + ' [' + ci(b.natural.ci95) + '].) ' +
      'Hover a dot for its name; click it to see the drawings.';
    var px = D.summary.robustness.pixel.all;
    $('pixel-agree').textContent = 'typically ' + f2(px.median) + ' times as varied as people, and less varied for ' + px.below_1 + ' of ' + px.n + ' things';
  }

  // --- start ---------------------------------------------------------------------------------
  function drawCharts() { ranking(); predictors(); }

  T.api('/api/plato/atlas').then(function (d) {
    D = d;
    D.concepts.forEach(function (c) { BY[c.key] = c; });
    hero();
    controls();
    gallery();
    rankText();
    drawCharts();
    whyCaption();
    detailEvents();
    var w = window.innerWidth, timer = null;
    window.addEventListener('resize', function () {
      if (window.innerWidth === w) return;
      w = window.innerWidth;
      clearTimeout(timer);
      timer = setTimeout(drawCharts, 150);
    });
    var hash = decodeURIComponent((location.hash || '').slice(1));
    if (hash.indexOf('thing=') === 0 && BY[hash.slice(6)]) openByKey(hash.slice(6));
  }).catch(function (err) {
    var box = $('load-error');
    box.textContent = err.message || 'The Atlas of Forms results could not be loaded.';
    box.hidden = false;
  });
})();
