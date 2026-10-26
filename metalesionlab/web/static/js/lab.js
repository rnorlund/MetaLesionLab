/* Model Lab: replay precomputed lesion conditions of Muse Glimmer with the word lens. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var LAYERS = 52, BLUE = '#1D4ED8', ORANGE = '#C2410C';
  var NS = 'http://www.w3.org/2000/svg';
  var L = { list: [], sample: false, cache: {}, base: null, cur: null, word: null, allLayers: false };
  function $(id) { return document.getElementById(id); }

  function svg(tag, attrs, children) {
    var el = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) el.setAttribute(k, attrs[k]); });
    [].concat(children || []).forEach(function (c) { if (c != null) el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return el;
  }

  // --- spec helpers -------------------------------------------------------------------------
  /* Lesioned decoder layers as 1-based numbers. Lists are taken as 1-based unless they contain 0. */
  function lesionedLayers(spec) {
    spec = spec || {};
    var ls = spec.layers, nums = [];
    if (Array.isArray(ls)) {
      nums = ls.map(Number).filter(function (n) { return !isNaN(n); });
      if (nums.indexOf(0) >= 0) nums = nums.map(function (n) { return n + 1; });
    } else if (typeof ls === 'string') {
      var m = ls.match(/(\d+)\s*[-–]\s*(\d+)/);
      if (m) for (var i = +m[1]; i <= +m[2]; i++) nums.push(i);
    } else if (ls && typeof ls === 'object' && ls.from != null) {
      for (var j = +ls.from; j <= +ls.to; j++) nums.push(j);
    }
    if (!nums.length && /decoder|language/i.test(spec.site || '') && !Array.isArray(ls)) {
      for (var k = 1; k <= LAYERS; k++) nums.push(k);
    }
    var set = {};
    nums.forEach(function (n) { if (n >= 1 && n <= LAYERS) set[n] = true; });
    return set;
  }
  function ranges(set) {
    var out = [], start = null;
    for (var l = 1; l <= LAYERS + 1; l++) {
      if (set[l] && start == null) start = l;
      if (!set[l] && start != null) { out.push([start, l - 1]); start = null; }
    }
    return out;
  }
  function rangeText(set) {
    return ranges(set).map(function (r) { return r[0] === r[1] ? String(r[0]) : r[0] + '–' + r[1]; }).join(', ');
  }
  function norm(w) { return String(w == null ? '' : w).replace(/^[\s▁Ġ]+/, '').trim().toLowerCase(); }
  function shown(w) {
    if (w == null) return '–';
    var s = String(w);
    if (s === '\n') return '\\n';
    return s.trim() === '' ? '␣' : s.trim();
  }
  function pct(v) { return v == null ? '–' : Math.round(v) + '%'; }

  // --- data ---------------------------------------------------------------------------------
  function load(id) {
    if (!L.cache[id]) L.cache[id] = T.api('/api/lab/conditions/' + encodeURIComponent(id));
    return L.cache[id];
  }
  function baselineId() {
    var b = L.list.filter(function (c) { return c.baseline; })[0];
    return b ? b.id : null;
  }

  function select(id, word) {
    var bid = baselineId();
    return Promise.all([bid ? load(bid) : Promise.resolve(null), load(id)]).then(function (res) {
      L.base = res[0];
      L.cur = res[1];
      var items = L.cur.items;
      var keep = word && items.some(function (it) { return it.word === word; });
      if (!keep) {
        var err = items.filter(function (it) { return T.normCode(it.code) !== 'Correct'; })[0];
        word = (err || items[0] || {}).word;
      }
      L.word = word;
      history.replaceState(null, '', '/lab?c=' + encodeURIComponent(id) + (word ? '&item=' + encodeURIComponent(word) : ''));
      renderAll();
    }).catch(function (e) { T.toast(e.message, 'error'); });
  }

  // --- left column ----------------------------------------------------------------------------
  function renderMap() {
    var spec = L.cur.spec || {}, set = lesionedLayers(spec), site = String(spec.site || '');
    var vision = /vision/i.test(site), projector = /project|adapter/i.test(site);
    var box = $('model-map');
    box.innerHTML = '';
    var where = L.cur.baseline ? 'No lesion' : [vision ? 'vision tower' : null, projector ? 'projector' : null,
      rangeText(set) ? 'decoder layers ' + rangeText(set) : null].filter(Boolean).join(', ') || site;
    box.setAttribute('role', 'img');
    box.setAttribute('aria-label', 'Model map. Lesioned: ' + where + '.');
    box.appendChild(h('div', { class: 'map-block' + (vision ? ' lesioned' : '') }, [h('span', { text: 'Vision tower' }), h('span', { class: 'muted', text: vision ? 'lesioned' : '50 layers' })]));
    box.appendChild(h('div', { class: 'map-block' + (projector ? ' lesioned' : '') }, [h('span', { text: 'Projector' }), h('span', { class: 'muted', text: projector ? 'lesioned' : 'adapter + projection' })]));
    var grid = h('div', { class: 'decoder-grid' });
    for (var b = 0; b < LAYERS / 4; b++) {
      grid.appendChild(h('span', { class: 'lab', text: 'L' + (b * 4 + 1) }));
      for (var k = 0; k < 4; k++) {
        var layer = b * 4 + k + 1;
        grid.appendChild(h('div', { class: 'cell' + (set[layer] ? ' on' : ''), title: 'layer ' + layer + (k === 3 ? ' (full attention)' : ' (sliding window)') + (set[layer] ? ', lesioned' : '') }));
      }
    }
    var on = h('span', { class: 'swatch' }), off = h('span', { class: 'swatch' });
    on.style.background = ORANGE;
    off.style.background = '#DBEAFE';
    box.appendChild(h('div', { class: 'decoder' }, [
      h('div', { class: 'kv', style: { marginBottom: '8px' } }, [h('span', { text: 'Language decoder' }), h('span', { class: 'muted', text: '52 layers' })]),
      grid,
      h('div', { class: 'map-legend' }, [h('span', null, [on, ' lesioned']), h('span', null, [off, ' intact']), h('span', { text: 'each row: 3 sliding-window + 1 full-attention layer' })])
    ]));
  }

  function renderConds() {
    var box = $('cond-list');
    box.innerHTML = '';
    var list = L.list.slice().sort(function (a, b) { return (b.baseline ? 1 : 0) - (a.baseline ? 1 : 0); });
    list.forEach(function (c) {
      var input = h('input', { type: 'radio', name: 'cond', value: c.id, checked: L.cur && c.id === L.cur.id });
      input.addEventListener('change', function () { select(c.id, L.word); });
      box.appendChild(h('label', { class: 'cond' }, [input, h('span', null, [
        h('span', { class: 'name', text: c.label }),
        h('span', { class: 'acc', text: 'naming accuracy ' + pct(c.accuracy) + ' · ' + c.n_items + ' items' })
      ])]));
    });
  }

  function renderSpec() {
    var spec = L.cur.spec || {}, dl = $('spec');
    dl.innerHTML = '';
    if (L.cur.baseline) return;
    var set = lesionedLayers(spec);
    var rows = [['Site', spec.site], ['Units chosen by', spec.localizer ? spec.localizer + ' localizer' : null], ['Method', spec.method],
      ['Decoder layers', rangeText(set) || null],
      ['Amount', spec.fraction != null ? (spec.fraction <= 1 ? spec.fraction * 100 : spec.fraction) + '% of units' : spec.units != null ? spec.units + ' units' : null]];
    rows.forEach(function (r) { if (r[1] != null && r[1] !== '') { dl.appendChild(h('dt', { text: r[0] })); dl.appendChild(h('dd', { text: String(r[1]) })); } });
  }

  // --- items ----------------------------------------------------------------------------------
  function renderItems() {
    var c = L.cur, base = L.base;
    $('items-h').innerHTML = '';
    $('items-h').appendChild(document.createTextNode(c.baseline ? 'Naming, intact model ' : 'Naming, intact vs. lesioned '));
    $('items-h').appendChild(h('span', { class: 'sub', text: '· ' + c.label }));
    $('items-meta').textContent = (c.baseline || !base ? 'accuracy ' + pct(c.accuracy) : 'accuracy ' + pct(base.accuracy) + ' → ' + pct(c.accuracy)) + ' · ' + c.n_items + ' items';
    var grid = $('items');
    grid.innerHTML = '';
    c.items.forEach(function (it) {
      var pic = it.image_url ? h('img', { src: it.image_url + '?w=320', alt: 'Muse Image drawing: ' + it.word, loading: 'lazy' }) : h('span', { text: '[' + it.word + ']' });
      grid.appendChild(h('button', { type: 'button', class: 'card', 'aria-pressed': it.word === L.word ? 'true' : 'false', onclick: function () { L.word = it.word; history.replaceState(null, '', '/lab?c=' + encodeURIComponent(c.id) + '&item=' + encodeURIComponent(it.word)); renderItems(); renderLens(); } }, [
        h('div', { class: 'pic' }, pic),
        h('div', { class: 'body' }, [
          h('div', { class: 'kv' }, [h('span', { text: 'target' }), h('span', { style: { fontFamily: 'var(--sans)', fontWeight: '600' }, text: it.word })]),
          h('div', { class: 'kv' }, [h('span', { text: c.baseline ? 'model said' : 'lesioned said' }), h('span', { text: it.said ? it.said : '—' })]),
          h('span', { style: { alignSelf: 'flex-start' } }, T.pill(it.code))
        ])
      ]));
    });
  }

  // --- word lens ------------------------------------------------------------------------------
  function itemIn(cond, word) { return cond ? cond.items.filter(function (it) { return it.word === word; })[0] : null; }

  function renderLens() {
    var word = L.word, les = L.cur.baseline ? null : itemIn(L.cur, word), intact = itemIn(L.base, word) || (L.cur.baseline ? itemIn(L.cur, word) : null);
    $('lens-h').textContent = 'Word lens · "' + (word || '') + '"';
    var chart = $('lens-chart');
    chart.innerHTML = '';
    var series = [];
    if (intact && intact.lens) series.push({ name: 'intact', color: BLUE, item: intact });
    if (les && les.lens) series.push({ name: 'lesioned', color: ORANGE, item: les });
    if (!series.length) {
      chart.appendChild(h('div', { class: 'empty', text: 'No word-lens data for this item.' }));
      $('lens-legend').innerHTML = '';
      $('lens-table').innerHTML = '';
      $('lens-caption').textContent = '';
      return;
    }
    drawChart(chart, series, L.cur.baseline ? {} : lesionedLayers(L.cur.spec), word);
    var lg = $('lens-legend');
    lg.innerHTML = '';
    series.forEach(function (s) {
      var key = h('span', { class: 'key-line' });
      key.style.background = s.color;
      lg.appendChild(h('span', null, [key, 'p(' + word + '), ' + s.name]));
    });
    if (!L.cur.baseline) {
      var band = h('span', { class: 'swatch' });
      band.style.background = 'rgba(194, 65, 12, 0.18)';
      lg.appendChild(h('span', null, [band, 'lesioned layers']));
    }
    drawTable(series, L.cur.baseline ? {} : lesionedLayers(L.cur.spec), word);
    $('lens-caption').textContent = caption(series, word);
  }

  function drawChart(box, series, lesSet, word) {
    // Drawn at the container's real pixel width so text stays 10-11 px on a phone.
    var W = Math.max(300, Math.min(900, Math.round(box.clientWidth || 600))), H = 250, x0 = 40, x1 = W - 52, y0 = 24, y1 = 204;
    var x = function (l) { return x0 + (l - 1) / (LAYERS - 1) * (x1 - x0); };
    var y = function (p) { return y1 - Math.max(0, Math.min(1, p)) * (y1 - y0); };
    var last = series.map(function (s) { return s.item.lens.p_correct[LAYERS - 1]; });
    var label = 'Line chart of p(' + word + ') by decoder layer. ' + series.map(function (s, i) {
      return s.name + ' ends at ' + (+last[i]).toFixed(2) + ' at layer 52, top word ' + shown(s.item.lens.top[LAYERS - 1][0]);
    }).join('; ') + '.';
    var root = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': label });
    ranges(lesSet).forEach(function (r, i) {
      root.appendChild(svg('rect', { x: x(r[0]) - 4.5, y: y0, width: x(r[1]) - x(r[0]) + 9, height: y1 - y0, fill: ORANGE, 'fill-opacity': '0.10' }));
      if (i === 0) root.appendChild(svg('text', { x: (x(r[0]) + x(r[1])) / 2, y: y0 - 8, 'text-anchor': 'middle', class: 'label' }, 'lesioned layers'));
    });
    var axis = svg('g', { class: 'axis' });
    [0, 0.5, 1].forEach(function (p) {
      axis.appendChild(svg('line', { x1: x0, x2: x1, y1: y(p), y2: y(p), stroke: p === 0 ? '#9CA3AF' : '#E5E7EB', 'stroke-width': 1 }));
      axis.appendChild(svg('text', { x: x0 - 8, y: y(p) + 3, 'text-anchor': 'end' }, p === 0.5 ? '0.5' : String(p)));
    });
    (W < 460 ? [1, 26, 52] : [1, 13, 26, 39, 52]).forEach(function (l) { axis.appendChild(svg('text', { x: x(l), y: y1 + 16, 'text-anchor': 'middle' }, String(l))); });
    axis.appendChild(svg('text', { x: (x0 + x1) / 2, y: y1 + 34, 'text-anchor': 'middle' }, 'decoder layer'));
    axis.appendChild(svg('text', { x: x0 - 8, y: y0 - 8, 'text-anchor': 'end' }, 'p'));
    root.appendChild(axis);
    series.forEach(function (s) {
      var pts = s.item.lens.p_correct.map(function (p, i) { return x(i + 1).toFixed(1) + ',' + y(p).toFixed(1); }).join(' ');
      root.appendChild(svg('polyline', { points: pts, fill: 'none', stroke: s.color, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
    });
    // end markers and selective end labels (dropped when they would collide)
    var ys = last.map(function (p) { return y(p); });
    series.forEach(function (s, i) {
      root.appendChild(svg('circle', { cx: x(LAYERS), cy: ys[i], r: 4, fill: s.color, stroke: '#FFFFFF', 'stroke-width': 2 }));
      var clash = i > 0 && Math.abs(ys[i] - ys[0]) < 13;
      if (!clash) root.appendChild(svg('text', { x: x(LAYERS) + 9, y: ys[i] + 4, class: 'end-label' }, (+last[i]).toFixed(2)));
    });
    // hover layer: crosshair + tooltip
    var cross = svg('line', { y1: y0, y2: y1, stroke: '#9CA3AF', 'stroke-width': 1, visibility: 'hidden' });
    var dots = series.map(function (s) { return svg('circle', { r: 4, fill: s.color, stroke: '#FFFFFF', 'stroke-width': 2, visibility: 'hidden' }); });
    root.appendChild(cross);
    dots.forEach(function (d) { root.appendChild(d); });
    var hit = svg('rect', { x: x0 - 6, y: y0, width: x1 - x0 + 12, height: y1 - y0, fill: 'transparent' });
    root.appendChild(hit);
    box.appendChild(root);
    var tip = h('div', { class: 'chart-tip', hidden: true });
    box.appendChild(tip);
    function show(evt) {
      var rect = root.getBoundingClientRect(), scale = W / rect.width;
      var vx = (evt.clientX - rect.left) * scale;
      var layer = Math.max(1, Math.min(LAYERS, Math.round((vx - x0) / (x1 - x0) * (LAYERS - 1)) + 1));
      var cx = x(layer);
      cross.setAttribute('x1', cx); cross.setAttribute('x2', cx); cross.setAttribute('visibility', 'visible');
      tip.innerHTML = '';
      tip.appendChild(h('div', null, [h('b', { text: 'Layer ' + layer }), lesSet[layer] ? ' · lesioned' : '']));
      series.forEach(function (s, i) {
        var p = s.item.lens.p_correct[layer - 1];
        dots[i].setAttribute('cx', cx); dots[i].setAttribute('cy', y(p)); dots[i].setAttribute('visibility', 'visible');
        var k = h('span', { class: 'k' });
        k.style.background = s.color;
        tip.appendChild(h('div', null, [k, s.name + ': p = ' + (+p).toFixed(3) + ' · top "' + shown(s.item.lens.top[layer - 1][0]) + '"']));
      });
      tip.hidden = false;
      // beside the crosshair, on the side with room
      var px = cx / scale, right = px < rect.width / 2;
      tip.style.left = (right ? px + 12 : px - 12 - tip.offsetWidth) + 'px';
      tip.style.top = (y0 / scale + 4) + 'px';
    }
    function hide() {
      tip.hidden = true;
      cross.setAttribute('visibility', 'hidden');
      dots.forEach(function (d) { d.setAttribute('visibility', 'hidden'); });
    }
    hit.addEventListener('pointermove', show);
    hit.addEventListener('pointerdown', show);
    hit.addEventListener('pointerleave', hide);
  }

  function drawTable(series, lesSet, word) {
    var from = L.allLayers ? 1 : 40;
    var layers = [];
    for (var l = from; l <= LAYERS; l++) layers.push(l);
    var table = $('lens-table');
    table.innerHTML = '';
    table.appendChild(h('caption', { class: 'sr-only', text: 'Top word and p(' + word + ') at each decoder layer' }));
    table.appendChild(h('thead', null, h('tr', null, [h('th', { scope: 'col', text: 'layer' })].concat(layers.map(function (l) {
      return h('th', { scope: 'col', class: lesSet[l] ? 'les' : null, text: 'L' + l });
    })))));
    var tb = h('tbody');
    series.forEach(function (s) {
      tb.appendChild(h('tr', null, [h('th', { scope: 'row', class: 'row-' + s.name, text: s.name + ' top' })].concat(layers.map(function (l) {
        var w = s.item.lens.top[l - 1][0];
        return h('td', { class: norm(w) === norm(word) ? 'hit' : null, text: shown(w) });
      }))));
      tb.appendChild(h('tr', null, [h('th', { scope: 'row', class: 'row-' + s.name, text: 'p(' + word + ')' })].concat(layers.map(function (l) {
        return h('td', { text: (+s.item.lens.p_correct[l - 1]).toFixed(3) });
      }))));
    });
    table.appendChild(tb);
  }

  function caption(series, word) {
    var intact = series.filter(function (s) { return s.name === 'intact'; })[0];
    var les = series.filter(function (s) { return s.name === 'lesioned'; })[0];
    var parts = [];
    if (intact) {
      var tops = intact.item.lens.top.map(function (t) { return t[0]; });
      var first = tops.findIndex(function (w) { return norm(w) === norm(word); });
      if (first >= 0) {
        var concept = -1;
        for (var i = Math.max(0, first - 6); i < first; i++) if (/[^\u0000-ɏ]/.test(tops[i] || '')) { concept = i; break; }
        parts.push('Intact: "' + word + '" becomes the top word at layer ' + (first + 1) + (concept >= 0 ? ', after the concept shows up as "' + shown(tops[concept]) + '" at layer ' + (concept + 1) : '') +
          ', and ends at p = ' + (+intact.item.lens.p_correct[LAYERS - 1]).toFixed(2) + '.');
        if (les && concept >= 0 && norm(les.item.lens.top[concept][0]) === norm(tops[concept]) && T.normCode(les.item.code) !== 'Correct') {
          parts.push('Tip of the tongue: the concept is still there after the lesion at layer ' + (concept + 1) + ', but "' + shown(les.item.lens.top[LAYERS - 1][0]) + '" wins.');
          return parts.join(' ');
        }
      } else {
        parts.push('Intact: "' + word + '" is never the top word; it ends at p = ' + (+intact.item.lens.p_correct[LAYERS - 1]).toFixed(2) + '.');
      }
    }
    if (les) {
      var end = les.item.lens.top[LAYERS - 1][0];
      if (T.normCode(les.item.code) === 'Correct') parts.push('Lesioned: still correct, ending at p = ' + (+les.item.lens.p_correct[LAYERS - 1]).toFixed(2) + '.');
      else parts.push('Lesioned: p(' + word + ') ends at ' + (+les.item.lens.p_correct[LAYERS - 1]).toFixed(2) + ' and "' + shown(end) + '" wins (' + T.codeInfo(les.item.code).label.toLowerCase() + ' error).');
    }
    return parts.join(' ');
  }

  var resizeTimer = null, lastWidth = 0;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      var w = $('lens-chart').clientWidth;
      if (L.cur && Math.abs(w - lastWidth) > 8) { lastWidth = w; renderLens(); }
    }, 150);
  });

  $('all-layers').addEventListener('click', function () {
    L.allLayers = !L.allLayers;
    this.setAttribute('aria-pressed', String(L.allLayers));
    this.textContent = L.allLayers ? 'Show layers 40–52' : 'Show all 52 layers';
    renderLens();
  });

  // --- error profiles ---------------------------------------------------------------------------
  function renderProfiles() {
    var box = $('profiles');
    box.innerHTML = '';
    var rows = L.list.slice().sort(function (a, b) {
      var ra = a.baseline ? 0 : a.id === L.cur.id ? 1 : 2, rb = b.baseline ? 0 : b.id === L.cur.id ? 1 : 2;
      return ra - rb;
    }).slice(0, 8);
    var seen = {};
    rows.forEach(function (c) {
      var counts = {}, total = 0;
      Object.keys(c.counts || {}).forEach(function (k) { var code = T.normCode(k); counts[code] = (counts[code] || 0) + c.counts[k]; total += c.counts[k]; seen[code] = true; });
      if (!total) return;
      box.appendChild(h('div', { class: 'profile-row' + (c.id === L.cur.id && !c.baseline ? ' current' : '') }, [
        h('div', { class: 'top' }, [h('b', { text: c.label }), h('span', { text: 'accuracy ' + pct(c.accuracy) })]),
        T.stackBar(counts, total, c.label + ': ' + T.describeCounts(counts, total)),
        h('div', { class: 'counts', text: T.ORDER.filter(function (k) { return counts[k]; }).map(function (k) { return T.codeInfo(k).label + ' ' + counts[k]; }).join(' · ') })
      ]));
    });
    var lg = $('prof-legend');
    lg.innerHTML = '';
    lg.appendChild(T.legend(T.ORDER.filter(function (k) { return seen[k]; })));
  }

  // --- published human profiles -----------------------------------------------------------------
  var SHARED_LABEL = { Nonword: 'Nonword or neologism', NoResponse: 'No response or description' };
  var MERGE = { Neologism: 'Nonword', Description: 'NoResponse' };
  function sharedLabel(c) { return SHARED_LABEL[c] || T.codeInfo(c).label; }

  /* The condition's responses in the shared categories. Visual errors have no published counterpart,
     so they are left out (and counted separately). */
  function conditionShares(c) {
    var shares = {}, total = 0, visual = 0;
    Object.keys(c.counts || {}).forEach(function (k) {
      var code = T.normCode(k), n = c.counts[k];
      code = MERGE[code] || code;
      if (code === 'Visual') { visual += n; return; }
      shares[code] = (shares[code] || 0) + n;
      total += n;
    });
    Object.keys(shares).forEach(function (k) { shares[k] /= total || 1; });
    return { shares: shares, visual: visual, total: total + visual };
  }
  function cosine(a, b, codes) {
    var dot = 0, na = 0, nb = 0;
    codes.forEach(function (c) { var x = a[c] || 0, y = b[c] || 0; dot += x * y; na += x * x; nb += y * y; });
    return na && nb ? dot / Math.sqrt(na * nb) : null;
  }
  function shareBar(shares, codes, label) {
    var bar = h('div', { class: 'stack-bar', role: 'img', 'aria-label': label + ': ' + codes.filter(function (c) { return shares[c]; })
      .map(function (c) { return sharedLabel(c) + ' ' + Math.round(100 * shares[c]) + '%'; }).join(', ') });
    codes.forEach(function (c) {
      if (!shares[c]) return;
      var seg = h('div', { title: sharedLabel(c) + ' ' + Math.round(100 * shares[c]) + '%' });
      seg.style.flex = shares[c] + ' 1 0';
      seg.style.background = T.codeInfo(c).color;
      bar.appendChild(seg);
    });
    return bar;
  }
  function percentList(shares, codes) {
    return codes.filter(function (c) { return shares[c]; }).map(function (c) { return sharedLabel(c) + ' ' + Math.round(100 * shares[c]) + '%'; }).join(' · ');
  }

  function renderHuman() {
    if (!L.human) {
      L.human = T.api('/api/lab/human').catch(function () { return null; });
    }
    L.human.then(function (hp) {
      if (!hp || !hp.pooled.length || !L.cur) return;
      $('human-panel').hidden = false;
      var codes = hp.codes, model = conditionShares(L.cur);
      var box = $('human-pooled');
      box.innerHTML = '';
      var modelNote = (L.sample ? 'sample data · ' : '') + model.total + ' responses' + (model.visual ? ', ' + model.visual + ' visual errors left out' : '');
      box.appendChild(h('div', { class: 'profile-row current-model' }, [
        h('div', { class: 'top' }, [h('b', { text: 'Muse Glimmer · ' + L.cur.label }), h('span', { text: modelNote })]),
        shareBar(model.shares, codes, 'This condition'),
        h('div', { class: 'counts', text: percentList(model.shares, codes) })
      ]));
      hp.pooled.forEach(function (p) {
        var used = codes.filter(function (c) { return c !== 'Correct' && p.missing.indexOf(c) < 0; });
        var sim = cosine(model.shares, p.shares, used);
        var src = p.source || {};
        var cite = h('div', { class: 'cite' }, [
          src.url ? h('a', { href: src.url, target: '_blank', rel: 'noopener', text: src.short }) : src.short,
          src.where ? ', ' + src.where : '',
          p.missing.length ? ' · compared without: ' + p.missing.map(sharedLabel).join(', ') : ''
        ]);
        box.appendChild(h('div', { class: 'profile-row' }, [
          h('div', { class: 'top' }, [h('b', { text: p.name }), h('span', { text: sim == null ? '' : 'error-pattern similarity ' + sim.toFixed(2) + (L.sample ? ' · sample' : '') })]),
          shareBar(p.shares, codes, p.name),
          h('div', { class: 'counts', text: percentList(p.shares, codes) }),
          cite
        ]));
      });
      var lg = $('human-legend');
      lg.innerHTML = '';
      var legend = h('div', { class: 'legend' });
      codes.forEach(function (c) {
        var sw = h('span', { class: 'swatch' });
        sw.style.background = T.codeInfo(c).color;
        legend.appendChild(h('span', null, [sw, sharedLabel(c)]));
      });
      lg.appendChild(legend);
      lg.appendChild(h('p', { class: 'xsmall muted', style: { margin: '6px 0 0' }, text: 'Error-pattern similarity: cosine between the two mixes of error types, leaving out correct responses and any category a source doesn\'t report (1 = the same mix of errors). Compare accuracy separately.' }));

      var table = $('human-subtypes');
      table.innerHTML = '';
      var st = hp.subtypes;
      if (st && st.groups.length) {
        var mAll = {}, nAll = 0;
        Object.keys(L.cur.counts || {}).forEach(function (k) { var code = MERGE[T.normCode(k)] || T.normCode(k); mAll[code] = (mAll[code] || 0) + L.cur.counts[k]; nAll += L.cur.counts[k]; });
        var f = function (v) { return v == null ? '–' : Math.round(v * 100) + '%'; };
        table.appendChild(h('thead', null, h('tr', null, ['Group', 'n', 'Correct', 'Semantic', 'Nonword'].map(function (t) { return h('th', { scope: 'col', text: t }); }))));
        var tb = h('tbody');
        tb.appendChild(h('tr', { class: 'model' }, [h('td', { text: 'This condition' + (L.sample ? ' (sample)' : '') }), h('td', { text: String(nAll) }),
          h('td', { text: f((mAll.Correct || 0) / nAll) }), h('td', { text: f((mAll.Semantic || 0) / nAll) }), h('td', { text: f((mAll.Nonword || 0) / nAll) })]));
        st.groups.forEach(function (g) {
          tb.appendChild(h('tr', null, [h('td', { text: g.subtype }), h('td', { text: String(g.n) }), h('td', { text: f(g.correct) }), h('td', { text: f(g.semantic) }), h('td', { text: f(g.nonword) })]));
        });
        table.appendChild(tb);
        var s = st.source || {};
        var note = $('human-subtype-note');
        note.innerHTML = '';
        note.appendChild(document.createTextNode('Share of all responses. '));
        note.appendChild(s.url ? h('a', { href: s.url, target: '_blank', rel: 'noopener', text: s.short }) : document.createTextNode(s.short || ''));
        note.appendChild(document.createTextNode((s.where ? ', ' + s.where : '') + '. ' + (s.note || '')));
      }
      var ctrl = (hp.controls || []).map(function (c) {
        var acc = c.correct != null ? Math.round(c.correct * 100) + '%' : c.correct_percent ? c.correct_percent.final + '%' : '?';
        return acc + ' (' + c.source.short + ', n = ' + c.n + ')';
      });
      $('human-controls').textContent = ctrl.length ? 'For reference, adults without brain injury name ' + ctrl.join(' and ') + ' of PNT pictures correctly.' : '';
    });
  }

  function renderAll() {
    renderConds();
    renderMap();
    renderSpec();
    renderItems();
    renderLens();
    renderProfiles();
    renderHuman();
  }

  T.api('/api/lab/conditions').then(function (res) {
    L.list = res.conditions;
    L.sample = res.sample || res.conditions.some(function (c) { return c.sample; });
    $('sample-chip').hidden = !L.sample;
    if (L.sample) {
      var note = $('sample-note');
      note.hidden = false;
      var text = (res.conditions[0] && res.conditions[0].note) || 'Sample data: real lesion results replace it when they are ready.';
      note.appendChild(h('p', null, [h('b', { text: 'Sample data. ' }), text]));
    }
    if (!L.list.length) {
      $('items').appendChild(h('div', { class: 'empty', text: 'No lesion conditions yet.' }));
      return;
    }
    var want = T.param('c');
    var first = L.list.filter(function (c) { return !c.baseline; })[0] || L.list[0];
    var id = want && L.list.some(function (c) { return c.id === want; }) ? want : first.id;
    return select(id, T.param('item'));
  }).catch(function (e) { T.toast(e.message, 'error'); });
})();
