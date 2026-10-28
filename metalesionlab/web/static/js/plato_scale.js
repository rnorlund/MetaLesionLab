/* An AI growing up (/plato/scale): the two walls of chairs, then what changes with model size and with data.
   Reads /api/plato/scale (public_data/plato_scale.json plus the walls' layout). Tiles are masks over one sprite per
   wall (static/img/plato_scale/wall_*.webp, 12 columns, one row per model or data size). */
(function () {
  'use strict';
  // the theme's tokens (app.css, plato_scale.css), so the charts follow the light or dark theme without redrawing
  var COLOR = { 'Qwen2.5': 'var(--s-blue)', 'OLMo 2': 'var(--s-orange)', 'Qwen3': 'var(--s-green)', 'Muse': 'var(--s-meta)' };
  var FAMILIES = ['Qwen2.5', 'OLMo 2', 'Qwen3'];
  var SPRITES = { models: '/static/img/plato_scale/wall_models.webp', data: '/static/img/plato_scale/wall_data.webp' };
  var $ = function (id) { return document.getElementById(id); };
  var tip = document.createElement('div');
  tip.className = 'sc-tip';
  tip.setAttribute('role', 'tooltip');
  document.body.appendChild(tip);

  function el(tag, attrs, html) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (html != null) e.innerHTML = html;
    return e;
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function pct(v) { return v == null ? '–' : Math.round(v * 100) + '%'; }
  function f2(v) { return v == null ? '–' : v.toFixed(2); }
  function f3(v) { return v == null ? '–' : v.toFixed(3); }
  function ci(c, f) { return c && c[0] != null ? '[' + f(c[0]) + ', ' + f(c[1]) + ']' : ''; }
  function sizeText(m) { return m.kind === 'api' ? 'size undisclosed' : m.params_b.toFixed(1) + 'B parameters'; }

  // ---------- walls ----------
  function tiles(row, nRows, sprite, label) {
    var box = el('div', { 'class': 'sc-tiles' });
    row.tiles.forEach(function (fail, i) {
      var t = el('div', { 'class': 'sc-tile' + (fail ? ' fail' : ''), role: 'img' });
      if (fail) {
        t.setAttribute('aria-label', label + ', sample ' + (i + 1) + ': failed (' + fail + ')');
        t.appendChild(el('span', {}, '<em>' + esc(fail) + '</em>'));
      } else {
        t.setAttribute('aria-label', label + ', drawing ' + (i + 1) + ' of 12');
        var m = el('i', { 'aria-hidden': 'true' });
        var url = 'url("' + sprite + '")';
        var size = (12 * 100) + '% ' + (nRows * 100) + '%';
        var pos = (i / 11 * 100) + '% ' + (nRows > 1 ? row.row / (nRows - 1) * 100 : 0) + '%';
        ['webkitMask', 'mask'].forEach(function (p) {
          m.style[p + 'Image'] = url; m.style[p + 'Size'] = size; m.style[p + 'Position'] = pos;
        });
        t.appendChild(m);
      }
      box.appendChild(t);
    });
    return box;
  }

  function wallModels(w, filter) {
    var host = $('wall-models');
    host.innerHTML = '';
    var last = null, n = w.models.length;
    w.models.forEach(function (m) {
      var fam = m.kind === 'api' || m.family === 'Muse' ? 'Meta' : m.family;
      if (filter !== 'all' && filter !== fam) return;
      if (m.group !== last) { host.appendChild(el('div', { 'class': 'sc-group' }, esc(m.group))); last = m.group; }
      var row = el('div', { 'class': 'sc-row' });
      var spread = m.spread_ratio == null ? 'too few drawings for a spread' : 'spread ' + f2(m.spread_ratio) + '× people’s';
      var read = m.recog_siglip == null ? '' : '<span>read as a chair: ' + Math.round(m.recog_siglip * 12) + ' of 12</span>';
      row.appendChild(el('div', { 'class': 'sc-row-head' },
        '<b><i class="sw" style="background:' + COLOR[m.family] + '"></i>' + esc(m.label) + '</b>' +
        '<span>' + esc(sizeText(m)) + ' · failed ' + m.failed + ' of 12</span><span>' + spread + '</span>' + read));
      row.appendChild(tiles(m, n, SPRITES.models, m.label));
      host.appendChild(row);
    });
  }

  function wallData(w) {
    var host = $('wall-data');
    host.innerHTML = '';
    w.data.forEach(function (r) {
      var row = el('div', { 'class': 'sc-row' });
      row.appendChild(el('div', { 'class': 'sc-row-head' }, '<b>' + r.size.toLocaleString('en-US') + ' chairs</b>' +
        r.lines.map(function (l) { return '<span>' + esc(l) + '</span>'; }).join('')));
      row.appendChild(tiles(r, w.data.length, SPRITES.data, r.size + ' chairs'));
      host.appendChild(row);
    });
  }

  // ---------- charts ----------
  var NS = 'http://www.w3.org/2000/svg';
  function s(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(e);
    return e;
  }
  function showTip(evt, text) {
    tip.textContent = text; tip.style.display = 'block';
    var r = evt.target.getBoundingClientRect();
    var x = Math.min(window.innerWidth - tip.offsetWidth - 8, r.left + r.width / 2 - tip.offsetWidth / 2);
    tip.style.left = Math.max(8, x) + 'px';
    tip.style.top = Math.max(8, r.top - tip.offsetHeight - 8) + 'px';
  }
  function hideTip() { tip.style.display = 'none'; }
  function point(g, x, y, shape, color, text) {
    var p = shape === 'sq' ? s('rect', { x: x - 5, y: y - 5, width: 10, height: 10, rx: 1.5 }, g)
      : shape === 'dia' ? s('path', { d: 'M' + x + ' ' + (y - 6.5) + 'l6.5 6.5-6.5 6.5-6.5-6.5z' }, g)
        : s('circle', { cx: x, cy: y, r: 5 }, g);
    p.setAttribute('fill', color); p.setAttribute('stroke', 'var(--chart)'); p.setAttribute('stroke-width', 1.5);
    p.setAttribute('class', 'pt'); p.setAttribute('tabindex', '0'); p.setAttribute('aria-label', text);
    p.addEventListener('mouseenter', function (e) { showTip(e, text); });
    p.addEventListener('focus', function (e) { showTip(e, text); });
    p.addEventListener('mouseleave', hideTip); p.addEventListener('blur', hideTip);
    return p;
  }

  /* cfg: {x: {min, max, ticks: [[v, label]]} (log), y: {min, max, ticks, fmt}, series: [{name, color, dash, pts:
     [{x, y, lo, hi, tip}]}], marks: [{x, y, name, shape, tip}], side: [{name, y, lo, hi, tip}], refs: [{y, label, dash}]} */
  function chart(host, cfg) {
    var W = 480, H = 290, L = 44, T = cfg.side ? 30 : 14, B = 40, sideW = cfg.side ? 96 : 0, R = 12 + sideW, pw = W - L - R, ph = H - T - B;
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': cfg.aria });
    var lx = function (v) { return L + (Math.log10(v) - Math.log10(cfg.x.min)) / (Math.log10(cfg.x.max) - Math.log10(cfg.x.min)) * pw; };
    var ly = function (v) { return T + (1 - (v - cfg.y.min) / (cfg.y.max - cfg.y.min)) * ph; };
    cfg.y.ticks.forEach(function (v) {
      s('line', { x1: L, x2: W - 12, y1: ly(v), y2: ly(v), stroke: 'var(--gridline)' }, svg);
      s('text', { x: L - 6, y: ly(v) + 4, 'text-anchor': 'end', 'font-size': 12 }, svg).textContent = cfg.y.fmt(v);
    });
    cfg.x.ticks.forEach(function (t) {
      s('text', { x: lx(t[0]), y: H - B + 17, 'text-anchor': 'middle', 'font-size': 12 }, svg).textContent = t[1];
    });
    s('text', { x: L + pw / 2, y: H - 5, 'text-anchor': 'middle', 'font-size': 12 }, svg).textContent = cfg.x.title;
    s('line', { x1: L, x2: L + pw, y1: T + ph, y2: T + ph, stroke: 'var(--axis)' }, svg);
    (cfg.refs || []).forEach(function (r) {
      s('line', { x1: L, x2: W - 12, y1: ly(r.y), y2: ly(r.y), stroke: 'var(--faint)', 'stroke-dasharray': r.dash || '5 4' }, svg);
      s('text', { x: L + 4, y: ly(r.y) - 5, 'font-size': 11.5 }, svg).textContent = r.label;
    });
    var g = s('g', {}, svg);
    (cfg.series || []).forEach(function (se) {
      var pts = se.pts.filter(function (p) { return p.y != null; });
      if (se.band) {
        var up = pts.map(function (p) { return lx(p.x) + ',' + ly(p.hi); }), dn = pts.slice().reverse().map(function (p) { return lx(p.x) + ',' + ly(p.lo); });
        s('polygon', { points: up.concat(dn).join(' '), fill: se.color, 'fill-opacity': 0.1 }, g);
      }
      pts.forEach(function (p) { if (!se.band && p.lo != null) s('line', { x1: lx(p.x), x2: lx(p.x), y1: ly(p.lo), y2: ly(p.hi), stroke: se.color, 'stroke-opacity': 0.35 }, g); });
      if (pts.length > 1) s('polyline', { points: pts.map(function (p) { return lx(p.x) + ',' + ly(p.y); }).join(' '), fill: 'none', stroke: se.color, 'stroke-width': 2, 'stroke-dasharray': se.dash || 'none' }, g);
      if (!se.noPoints) pts.forEach(function (p) { point(g, lx(p.x), ly(p.y), 'dot', se.color, p.tip); });
    });
    (cfg.marks || []).forEach(function (m) {
      if (m.y == null) return;
      point(g, lx(m.x), ly(m.y), m.shape, COLOR.Muse, m.tip);
      s('text', { x: lx(m.x), y: ly(m.y) - 11, 'text-anchor': 'middle', 'font-size': 11.5, 'class': 'lab' }, svg).textContent = m.name;
    });
    if (cfg.side) {  // the API models: their own column, named under the axis, never placed on the size scale
      var x0 = W - sideW + 4, cw = sideW - 12;
      s('rect', { x: x0, y: T, width: cw, height: ph, fill: 'var(--sc-band)', rx: 4 }, svg);
      s('text', { x: x0 + cw / 2, y: T - 16, 'text-anchor': 'middle', 'font-size': 11 }, svg).textContent = 'API models,';
      s('text', { x: x0 + cw / 2, y: T - 4, 'text-anchor': 'middle', 'font-size': 11 }, svg).textContent = 'size undisclosed';
      cfg.side.forEach(function (m, i) {
        var x = x0 + cw * (i + 1) / (cfg.side.length + 1);
        s('text', { x: x, y: H - B + 17, 'text-anchor': 'middle', 'font-size': 12, 'class': 'lab' }, svg).textContent = m.name;
        if (m.y == null) return;
        if (m.lo != null) s('line', { x1: x, x2: x, y1: ly(m.lo), y2: ly(m.hi), stroke: COLOR.Muse, 'stroke-opacity': 0.35 }, svg);
        point(svg, x, ly(m.y), 'sq', COLOR.Muse, m.tip);
      });
    }
    host.appendChild(svg);
  }

  function chartBox(parent, title, sub) {
    var box = el('div', { 'class': 'sc-chart' });
    box.appendChild(el('h3', {}, esc(title)));
    if (sub) box.appendChild(el('p', {}, esc(sub)));
    parent.appendChild(box);
    return box;
  }

  var X_B = { min: 0.38, max: 45, title: 'parameters (log scale)', ticks: [[0.5, '0.5B'], [1, '1B'], [2, '2B'], [5, '5B'], [10, '10B'], [30, '30B']] };
  var X_A = { min: 70, max: 28000, title: 'people’s chairs it learned from (log scale)', ticks: [[100, '100'], [300, '300'], [1000, '1k'], [3000, '3k'], [10000, '10k'], [20000, '20k']] };
  var Y_P = { min: 0, max: 1, ticks: [0, 0.25, 0.5, 0.75, 1], fmt: function (v) { return Math.round(v * 100) + '%'; } };
  var Y_S = { min: 0, max: 0.7, ticks: [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7], fmt: function (v) { return v.toFixed(1); } };

  function chartsB(d) {
    var rows = d.arm_b.rows.filter(function (r) { return r.temp === 1; });
    var read = (d.reader_check || {}).arm_b || {};
    rows.forEach(function (r) { r.recog_siglip = read[r.key + '|1.0']; });
    var by = {}; rows.forEach(function (r) { by[r.key] = r; });
    var host = $('charts-b');
    var defs = [
      ['spread', 'Spread', 'How varied its chairs are (mean pairwise DINOv2 distance). Lower: more alike.', Y_S, 'spread_ci95', f3,
        [{ y: d.anchors.people.spread_n12, label: 'people’s chairs' }, { y: d.anchors.muse_image.spread, label: 'Muse Image’s chairs', dash: '2 3' }]],
      ['recog_all', 'Recognizable', 'Share of all 12 whose nearest of 35 people’s-drawing centroids is the chair.', Y_P, 'recog_all_ci95', pct,
        [{ y: d.anchors.people.recog, label: 'people’s chairs' }]],
      ['recog_siglip', 'Read as a chair (check)', 'Google SigLIP 2, zero-shot among the same 35 names. Added after the plan.', Y_P, null, pct,
        d.reader_check ? [{ y: d.reader_check.people, label: 'people’s chairs' }] : []],
      ['failure_rate', 'Failed to draw', 'No SVG, didn’t render, blank or all ink, out of 12.', Y_P, 'failure_ci95', pct, []]
    ];
    defs.forEach(function (def) {
      var col = def[0], fmt = def[5];
      var tipOf = function (r) { return r.label + ': ' + fmt(r[col]) + (def[4] && r[def[4]] ? ' ' + ci(r[def[4]], fmt) : ''); };
      var box = chartBox(host, def[1], def[2]);
      chart(box, {
        aria: def[1] + ' by model size', x: X_B, y: def[3], refs: def[6],
        series: FAMILIES.map(function (f) {
          return { name: f, color: COLOR[f], pts: rows.filter(function (r) { return r.family === f && r.kind === 'open'; }).sort(function (a, b) { return a.params_b - b.params_b; })
            .map(function (r) { var c = def[4] ? r[def[4]] : null; return { x: r.params_b, y: r[col], lo: c ? c[0] : null, hi: c ? c[1] : null, tip: tipOf(r) }; }) };
        }),
        marks: by.glimmer ? [{ x: by.glimmer.params_b, y: by.glimmer[col], name: 'Glimmer', shape: 'dia', tip: tipOf(by.glimmer) }] : [],
        side: ['spark', 'wonder'].filter(function (k) { return by[k]; }).map(function (k) {
          var r = by[k], c = def[4] ? r[def[4]] : null;
          return { name: k === 'spark' ? 'Spark' : 'Wonder', y: r[col], lo: c ? c[0] : null, hi: c ? c[1] : null, tip: tipOf(r) };
        })
      });
    });
  }

  function chartsA(d) {
    var host = $('charts-a');
    var read = (d.reader_check || {}).arm_a || {};
    var rowsOf = function (ck) { return d.arm_a.rows.filter(function (r) { return r.checkpoint === ck && r.temp === 1; }).sort(function (a, b) { return a.size - b.size; }); };
    var defs = [
      ['spread', 'Spread', 'Mean pairwise DINOv2 distance of 200 drawings (matched n = 16).', Y_S, f3],
      ['recog', 'Recognizable', 'Share of 200 drawings nearest the chair centroid among 35.', Y_P, pct],
      ['siglip', 'Read as a chair (check)', 'SigLIP 2, zero-shot. Added after the plan.', Y_P, pct],
      ['fail', 'Failed to draw', 'Samples that were only a dot.', Y_P, pct]
    ];
    defs.forEach(function (def) {
      var col = def[0], fmt = def[4];
      var series = [['final', 'last step (same compute)', 'none'], ['best', 'best held-out step', '6 4']].map(function (c) {
        return { name: c[1], color: COLOR['Qwen2.5'], dash: c[2], band: true, pts: rowsOf(c[0]).map(function (r) {
          var v = col === 'siglip' ? read[r.size + '|' + c[0]] : r[col];
          var y = v == null ? null : (typeof v === 'object' ? v.mean : v);
          var cc = v && typeof v === 'object' ? (v.ci95 || v.range) : null;
          return { x: r.size, y: y, lo: cc ? cc[0] : y, hi: cc ? cc[1] : y,
            tip: r.size.toLocaleString('en-US') + ' chairs, ' + c[1] + ': ' + fmt(y) + (cc ? ' ' + ci(cc, fmt) : '') };
        }) };
      });
      var refs = [];
      if (col === 'spread') {
        series.push({ name: 'its training chairs', color: 'var(--faint)', dash: '2 3', noPoints: true, pts: rowsOf('final').map(function (r) { return { x: r.size, y: r.train_spread }; }) });
      }
      if (col === 'recog') refs.push({ y: d.anchors.people.recog, label: 'people’s chairs' });
      if (col === 'siglip' && d.reader_check) refs.push({ y: d.reader_check.people, label: 'people’s chairs' });
      chart(chartBox(host, def[1], def[2]), { aria: def[1] + ' by data size', x: X_A, y: def[3], series: series, refs: refs });
    });
  }

  // ---------- tables ----------
  function table(host, head, rows) {
    var wrap = el('div', { 'class': 'sc-table-wrap' });
    var t = el('table');
    t.appendChild(el('thead', {}, '<tr>' + head.map(function (h) { return '<th scope="col">' + h + '</th>'; }).join('') + '</tr>'));
    var tb = el('tbody');
    rows.forEach(function (r) { tb.appendChild(el('tr', {}, r.map(function (c, i) { return i ? '<td>' + c + '</td>' : '<th scope="row">' + c + '</th>'; }).join(''))); });
    t.appendChild(tb); wrap.appendChild(t); host.appendChild(wrap);
  }

  function tables(d) {
    var read = (d.reader_check || {}).arm_b || {};
    [1, 0.7].forEach(function (temp) {
      table($('table-b-' + (temp === 1 ? '10' : '07')), ['Model', 'Size', 'Failed', 'Recognizable', 'Read as chair', 'Spread [95% CI]', '× people’s', 'To people’s chair', 'To Muse’s chair'],
        d.arm_b.rows.filter(function (r) { return r.temp === temp; }).map(function (r) {
          return [esc(r.label), r.kind === 'api' ? 'undisclosed' : r.params_b.toFixed(1) + 'B', r.failed + '/12', pct(r.recog_all),
            pct(read[r.key + '|' + temp.toFixed(1)]), r.spread == null ? '–' : f3(r.spread) + ' ' + ci(r.spread_ci95, f3), f2(r.spread_ratio), f3(r.d_people), f3(r.d_muse)];
        }));
    });
    table($('table-a'), ['Chairs', 'Step', 'Recognizable [95% CI]', 'Spread [95% CI]', 'Its data’s spread', 'Difference', 'To people’s chair', 'Copying gap'],
      d.arm_a.rows.filter(function (r) { return r.temp === 1; }).map(function (r) {
        return [r.size.toLocaleString('en-US'), r.checkpoint === 'final' ? 'last' : 'best (' + r.best_steps.join(', ') + ')',
          pct(r.recog.mean) + ' ' + ci(r.recog.ci95, pct), f3(r.spread.mean) + ' ' + ci(r.spread.ci95, f3), f3(r.train_spread),
          f3(r.spread_minus_train.mean) + ' ' + ci(r.spread_minus_train.ci95, f3), f3(r.d_people.mean), f3(r.copy_gap.mean)];
      }));
    var e1 = (d.arm_b.cross_family || {})['1.0'] || {};
    table($('table-e1'), ['Size band', 'Pairs of models from different makers', 'Gap between their chairs [95% CI]'],
      ['<=2B', '4-8B', '13-15B', '30-33B'].filter(function (b) { return e1[b]; }).map(function (b) {
        return [b.replace('<=', '≤ ').replace('-', '–'), e1[b].pairs.length, f3(e1[b].energy) + ' ' + ci(e1[b].energy_ci95, f3)];
      }));
  }

  function credits(d) { $('credits').innerHTML = (d.credits || []).map(esc).join(' · '); }

  function render(d) {
    wallModels(d.wall, 'all');
    var chips = $('wall-filter');
    ['all', 'Qwen2.5', 'OLMo 2', 'Qwen3', 'Meta'].forEach(function (f) {
      var b = el('button', { type: 'button', 'aria-pressed': f === 'all' ? 'true' : 'false' }, f === 'all' ? 'All models' : esc(f));
      b.addEventListener('click', function () {
        chips.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
        wallModels(d.wall, f);
      });
      chips.appendChild(b);
    });
    wallData(d.wall);
    chartsB(d); chartsA(d); tables(d); credits(d);
  }

  fetch('/api/plato/scale').then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(render)
    .catch(function () { var e = $('load-error'); e.hidden = false; e.textContent = 'The results couldn’t be loaded. Try reloading the page.'; });
})();
