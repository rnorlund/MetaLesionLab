/* Second language (/lab/bilingual): the controlled bilingual lesion test, replayed from /api/lab/bilingual
   (web/data/bilingual.json, written by scripts/bilingual_web_export.py). No API calls.
   Charts are inline SVG drawn at the container's width; colors come from CSS tokens (bilingual.css), and
   every chart has a legend, direct labels and a table or text twin. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var NS = 'http://www.w3.org/2000/svg';
  var LANGS = ['es', 'fr', 'pt'];
  var LENS_FROM = 28;  // before this layer both names have lens probability ~0 on every picture
  var S = { d: null, lang: 'es', site: null, pic: 0 };
  var readyResolve;
  var ready = new Promise(function (r) { readyResolve = r; });

  function $(id) { return document.getElementById(id); }
  function pct(x, dp) { return x == null ? '–' : (x * 100).toFixed(dp || 0) + '%'; }
  function pts(x) { return Math.round(x * 100); }
  function ci(c, unit) { return c ? Math.round(c[0] * 100) + '–' + Math.round(c[1] * 100) + (unit || '') : ''; }
  function num(n) { return Number(n).toLocaleString('en-US'); }
  function name(v) { return v === 'en' ? 'English' : (S.d.languages[v] || {}).name || v; }
  function s(tag, attrs, kids) {
    var el = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) el.setAttribute(k, attrs[k]); });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c != null) el.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return el;
  }
  function key(v, cls) { return h('i', { class: (cls || '') + ' bl-c-' + v }); }
  function runs(layers) {
    var out = [];
    (layers || []).forEach(function (l) {
      var last = out[out.length - 1];
      if (last && l === last[1] + 1) last[1] = l; else out.push([l, l]);
    });
    return out;
  }
  function runText(layers) {
    var r = runs(layers).map(function (x) { return x[0] === x[1] ? String(x[0] + 1) : (x[0] + 1) + '–' + (x[1] + 1); });  // shown 1–52
    return r.length < 2 ? r.join('') : r.slice(0, -1).join(', ') + ' and ' + r[r.length - 1];
  }
  // Data labels count layers from 0, as in the model's code; pages count them 1–52.
  function oneBased(text) { return String(text).replace(/\b(Layers?) (\d+)–(\d+)/g, function (m, w, a, b) { return w + ' ' + (+a + 1) + '–' + (+b + 1); }); }
  function lastRunStart(layers) { var r = runs(layers); return r.length ? r[r.length - 1][0] : null; }

  // --- tooltip: one per chart, positioned inside its wrapper ----------------------------------
  function tipOf(wrap) {
    var t = wrap.querySelector('.bl-tip');
    if (!t) { t = h('div', { class: 'bl-tip', hidden: true }); wrap.appendChild(t); }
    return t;
  }
  /* Swap in a new chart, keeping the chart's one tooltip (its handlers were bound to it while drawing). */
  function mount(wrap, svg) {
    var tip = tipOf(wrap);
    tip.hidden = true;
    [].slice.call(wrap.children).forEach(function (c) { if (c !== tip) c.remove(); });
    wrap.insertBefore(svg, tip);
  }
  function placeTip(wrap, tip, px, py) {
    tip.hidden = false;
    var w = wrap.clientWidth, lx = px + 14;
    if (lx + tip.offsetWidth > w) lx = px - tip.offsetWidth - 14;
    tip.style.left = Math.max(0, lx) + 'px';
    tip.style.top = Math.max(0, Math.min(py + 10, wrap.clientHeight - tip.offsetHeight)) + 'px';
  }
  function tipRow(v, strong, rest) {
    var k = h('span', { class: 'k bl-c-' + v });
    return h('div', null, [k, h('b', { text: strong }), rest ? h('span', { class: 'sub', text: ' ' + rest }) : null]);
  }

  /* A crosshair over n x-positions: pointer, touch and arrow keys move it; the tooltip lists every series. */
  function crosshair(svg, wrap, o) {
    var cross = s('line', { class: 'cross', x1: 0, x2: 0, y1: o.top, y2: o.bottom, opacity: 0 });
    svg.appendChild(cross);
    var hit = s('rect', { class: 'hit', x: o.left - 12, y: o.top - 8, width: o.right - o.left + 24, height: o.bottom - o.top + 16,
      fill: 'transparent', tabindex: 0, role: 'img', 'aria-label': o.label });
    svg.appendChild(hit);
    var tip = tipOf(wrap), cur = null;
    function show(i, px, py) {
      cur = i;
      var x = o.xOf(i);
      cross.setAttribute('x1', x); cross.setAttribute('x2', x); cross.setAttribute('opacity', 0.3);
      tip.innerHTML = '';
      o.content(i).forEach(function (n) { tip.appendChild(n); });
      placeTip(wrap, tip, px == null ? x : px, py == null ? o.top : py);
    }
    function hide() { tip.hidden = true; cross.setAttribute('opacity', 0); }
    hit.addEventListener('pointermove', function (e) {
      var r = svg.getBoundingClientRect(), px = (e.clientX - r.left) * o.W / r.width;
      var wr = wrap.getBoundingClientRect();
      show(o.nearest(px), e.clientX - wr.left, e.clientY - wr.top);
    });
    hit.addEventListener('pointerleave', hide);
    hit.addEventListener('blur', hide);
    hit.addEventListener('focus', function () { show(cur == null ? o.start : cur); });
    hit.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      e.preventDefault();
      var i = cur == null ? o.start : cur + (e.key === 'ArrowRight' ? 1 : -1);
      show(Math.max(0, Math.min(o.n - 1, i)));
    });
  }

  // --- hero ------------------------------------------------------------------------------------
  function renderHero() {
    var d = S.d, src = d.source, sm = d.summary, sw = d.switching, es = sm.es;
    $('bl-sub').textContent = src.n_pictures + ' pictures · ' + src.n_conditions + ' kinds of damage · ' + num(src.trials_per_language) +
      ' answers per language · Meta’s open-weight Muse Glimmer 30B. A study of an AI model, not of people.';
    var others = LANGS.filter(function (v) { return v !== 'es' && sm[v]; })
      .map(function (v) { return name(v) + ' +' + pts(sm[v].extra_drop); }).join(', ');
    var tiles = [
      ['+' + pts(es.extra_drop) + ' points', 'more pictures lost in Spanish than in English under the same damage (95% CI ' + ci(es.ci95) + '). ' + others + '.'],
      [es.items_worse + ' of ' + es.n_items, 'pictures fared worse in Spanish than in English. ' + (es.items_better ? es.items_better + ' fared better.' : 'None fared better.')],
      [pct(sw.es.english_answers.mean), 'of the damaged model’s Spanish answers came out in English. The other way round: about ' + pct(sw.reverse.other_language_answers.mean) + '.']
    ];
    var box = $('bl-tiles');
    box.innerHTML = '';
    tiles.forEach(function (t) { box.appendChild(h('div', { class: 'bl-tile' }, [h('b', { text: t[0] }), h('span', { text: t[1] })])); });
  }

  // --- 1. same damage, more pictures lost (dumbbell) ----------------------------------------------
  function renderDrop() {
    var d = S.d, wrap = $('drop-chart'), W = Math.max(280, wrap.clientWidth), narrow = W < 560;
    var langs = LANGS.filter(function (v) { return d.summary[v]; });
    var m = { l: narrow ? 86 : 112, r: narrow ? 78 : 132, t: 26, b: 34 }, rowH = 50;
    var H = m.t + langs.length * rowH + m.b, x = function (v) { return m.l + v * (W - m.l - m.r); };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'group',
      'aria-label': 'Pictures named correctly under damage, English versus each other language. ' + langs.map(function (v) {
        var x2 = d.summary[v];
        return name(v) + ' ' + pct(x2.acc_lang) + ' versus English ' + pct(x2.acc_en);
      }).join('; ') + '.' });
    [0, 0.25, 0.5, 0.75, 1].forEach(function (t) {
      svg.appendChild(s('line', { class: 'grid', x1: x(t), x2: x(t), y1: m.t - 6, y2: H - m.b }));
      svg.appendChild(s('text', { x: x(t), y: H - m.b + 16, 'text-anchor': 'middle' }, Math.round(t * 100) + '%'));
    });
    svg.appendChild(s('text', { x: m.l, y: H - 4, class: 't-ink2' }, 'Pictures named correctly under damage'));
    svg.appendChild(s('text', { x: W - m.r + 14, y: m.t - 10, class: 't-ink2' }, narrow ? 'vs English' : 'lost vs English'));
    var tip = tipOf(wrap);
    langs.forEach(function (v, i) {
      var r = d.summary[v], y = m.t + i * rowH + rowH / 2, sel = v === S.lang;
      var g = s('g', { 'aria-hidden': 'true' });
      g.appendChild(s('text', { x: 0, y: y + 4, class: sel ? 't-strong' : 't-ink2', 'font-size': 13 }, name(v)));
      g.appendChild(s('line', { class: 'gap', x1: x(r.acc_lang), x2: x(r.acc_en), y1: y, y2: y }));
      g.appendChild(s('g', { class: 'bl-c-en' }, s('circle', { class: 'dot', cx: x(r.acc_en), cy: y, r: 7 })));
      g.appendChild(s('g', { class: 'bl-c-' + v }, s('circle', { class: 'dot', cx: x(r.acc_lang), cy: y, r: 7 })));
      g.appendChild(s('text', { x: x(r.acc_en), y: y - 12, 'text-anchor': 'middle', class: 't-ink2' }, pct(r.acc_en)));
      g.appendChild(s('text', { x: x(r.acc_lang), y: y - 12, 'text-anchor': 'middle', class: 't-ink2' }, pct(r.acc_lang)));
      g.appendChild(s('text', { x: W - m.r + 14, y: y + 4, class: 't-strong', 'font-size': 13 }, '−' + pts(r.extra_drop) + (narrow ? ' pts' : ' points')));
      svg.appendChild(g);
      var hit = s('rect', { class: 'hit', x: 0, y: y - rowH / 2, width: W, height: rowH, fill: 'transparent', tabindex: 0, role: 'img',
        'aria-label': name(v) + ': ' + pct(r.acc_lang) + ' named correctly, English ' + pct(r.acc_en) + '; ' + pts(r.extra_drop) + ' points more lost (95% CI ' + ci(r.ci95) + ').' });
      function show(px, py) {
        tip.innerHTML = '';
        tip.appendChild(h('div', { text: name(v) + ' vs English, ' + r.n_items + ' pictures' }));
        tip.appendChild(tipRow(v, pct(r.acc_lang), name(v)));
        tip.appendChild(tipRow('en', pct(r.acc_en), 'English'));
        tip.appendChild(h('div', { text: pts(r.extra_drop) + ' points more lost (95% CI ' + ci(r.ci95) + ')' }));
        tip.appendChild(h('div', { class: 'sub', text: r.items_worse + ' of ' + r.n_items + ' pictures worse in ' + name(v) }));
        placeTip(wrap, tip, px, py);
      }
      hit.addEventListener('pointermove', function (e) { var wr = wrap.getBoundingClientRect(); show(e.clientX - wr.left, e.clientY - wr.top); });
      hit.addEventListener('pointerleave', function () { tip.hidden = true; });
      hit.addEventListener('focus', function () { show(x(r.acc_lang), y); });
      hit.addEventListener('blur', function () { tip.hidden = true; });
      hit.addEventListener('click', function () { setLang(v); });
      svg.appendChild(hit);
    });
    mount(wrap, svg);
    var lg = $('drop-legend');
    lg.innerHTML = '';
    ['en'].concat(langs).forEach(function (v) { lg.appendChild(h('span', null, [key(v, 'dot'), name(v)])); });
  }
  function renderDropText() {
    var d = S.d, r = d.summary[S.lang], L = name(S.lang), c = r.conditions;
    $('drop-meta').textContent = 'average of ' + r.n_conditions + ' kinds of damage';
    $('drop-lede').textContent = 'Share of pictures named correctly under damage, averaged over all ' + r.n_conditions +
      ' kinds. Only pictures the intact model named correctly in both languages count (' + r.n_items + ' for ' + L +
      '), so both languages start at 100%. The gap is how many more points the other language lost.';
    var note = $('drop-note');
    note.innerHTML = '';
    note.appendChild(h('b', { text: L + ' did worse than English on ' + (r.items_worse === r.n_items ? 'all ' : '') + r.items_worse + ' of ' + r.n_items + ' pictures' }));
    note.appendChild(document.createTextNode((r.items_better ? ' and better on ' + r.items_better : ', and better on none') +
      '. Kind by kind, it lost more than English under ' + c.worse + ' of the ' + r.n_conditions + ' kinds of damage, as much under ' + c.tied +
      ' and less under ' + c.better + '. ' + (c.reliably_better === 0 ? 'Every clear difference (' + c.reliably_worse +
      ' kinds, where the 95% CI excludes zero) went against ' + L + '.' : c.reliably_worse + ' clear differences went against ' + L + ' and ' + c.reliably_better + ' against English.')));
  }

  // --- 2. dose-response -----------------------------------------------------------------------
  function family() {
    return S.d.dose.filter(function (f) { return f.key === S.site; })[0] || S.d.dose[0];
  }
  function fillSites() {
    var sel = $('site'), groups = {};
    sel.innerHTML = '';
    S.d.dose.forEach(function (f) {
      if (!groups[f.group]) { groups[f.group] = h('optgroup', { label: f.group }); sel.appendChild(groups[f.group]); }
      groups[f.group].appendChild(h('option', { value: f.key, text: oneBased(f.label) }));
    });
    sel.value = S.site;
    sel.addEventListener('change', function () { setSite(sel.value); });
  }
  function renderDose() {
    var f = family(), P = f.points, v = S.lang, series = ['en', v];
    var wrap = $('dose-chart'), W = Math.max(280, wrap.clientWidth), narrow = W < 560;
    var m = { l: 42, r: narrow ? 16 : 110, t: 14, b: 50 }, ph = narrow ? 210 : 250, H = m.t + ph + m.b;
    var n = P.length, x = function (i) { return m.l + 14 + i / Math.max(1, n - 1) * (W - m.l - m.r - 28); };
    var y = function (val) { return m.t + (1 - val) * ph; };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H });
    [0, 0.25, 0.5, 0.75, 1].forEach(function (t) {
      svg.appendChild(s('line', { class: 'grid', x1: m.l, x2: W - m.r, y1: y(t), y2: y(t) }));
      svg.appendChild(s('text', { x: m.l - 8, y: y(t) + 4, 'text-anchor': 'end' }, Math.round(t * 100) + '%'));
    });
    svg.appendChild(s('line', { class: 'axis', x1: m.l, x2: W - m.r, y1: y(0), y2: y(0) }));
    P.forEach(function (p, i) {
      svg.appendChild(s('text', { x: x(i), y: y(0) + 18, 'text-anchor': 'middle', class: i ? null : 't-ink2' }, p.tick));
    });
    svg.appendChild(s('text', { x: m.l, y: H - 6, class: 't-ink2' }, 'Damage, from none to strongest →'));
    series.forEach(function (sv) {
      var g = s('g', { class: 'bl-c-' + sv, 'aria-hidden': 'true' });
      var have = P.map(function (p, i) { return p.acc[sv] ? i : -1; }).filter(function (i) { return i >= 0; });
      if (!have.length) return;
      var up = have.map(function (i) { return x(i).toFixed(1) + ',' + y(P[i].acc[sv][2]).toFixed(1); });
      var dn = have.slice().reverse().map(function (i) { return x(i).toFixed(1) + ',' + y(P[i].acc[sv][1]).toFixed(1); });
      g.appendChild(s('polygon', { class: 'band', points: up.concat(dn).join(' ') }));
      g.appendChild(s('polyline', { class: 'ln', points: have.map(function (i) { return x(i).toFixed(1) + ',' + y(P[i].acc[sv][0]).toFixed(1); }).join(' ') }));
      have.forEach(function (i) { g.appendChild(s('circle', { class: 'dot', cx: x(i), cy: y(P[i].acc[sv][0]), r: 4.5 })); });
      svg.appendChild(g);
    });
    // Direct labels at the right end, only when they don't collide (the legend and table carry the rest).
    var last = n - 1, ye = y(P[last].acc.en[0]), yl = P[last].acc[v] ? y(P[last].acc[v][0]) : null;
    if (!narrow && yl != null && Math.abs(ye - yl) >= 16) {
      [['en', ye], [v, yl]].forEach(function (e) {
        svg.appendChild(s('text', { x: x(last) + 10, y: e[1] + 4, class: 't-ink t-halo' }, name(e[0]) + ' ' + pct(P[last].acc[e[0]][0])));
      });
    }
    crosshair(svg, wrap, {
      n: n, W: W, top: m.t, bottom: y(0), left: x(0), right: x(n - 1), start: n - 1, xOf: x,
      label: oneBased(f.label) + ': pictures named correctly by damage strength, English versus ' + name(v) + '. Use the arrow keys to step through the doses; the table below lists every value.',
      nearest: function (px) { return Math.max(0, Math.min(n - 1, Math.round((px - x(0)) / Math.max(1, x(1) - x(0))))); },
      content: function (i) {
        var p = P[i], rows = [h('div', { text: (i ? p.tick + ' · ' : '') + p.detail })];
        series.forEach(function (sv) {
          var a = p.acc[sv];
          if (a) rows.push(tipRow(sv, pct(a[0]), name(sv) + ' (95% CI ' + ci([a[1], a[2]], '%') + ')'));
        });
        if (p.n_conditions > 1) rows.push(h('div', { class: 'sub', text: 'pooled over ' + p.n_conditions + ' random draws' }));
        return rows;
      }
    });
    mount(wrap, svg);
    var lg = $('dose-legend');
    lg.innerHTML = '';
    series.forEach(function (sv) { lg.appendChild(h('span', null, [key(sv), name(sv)])); });
    lg.appendChild(h('span', null, [key('en', 'band'), key(v, 'band'), '95% confidence interval']));
  }
  function renderDoseText() {
    var f = family(), P = f.points, v = S.lang, L = name(v), first = P[1], last = P[P.length - 1];
    $('dose-lede').textContent = 'Share of all ' + S.d.source.n_pictures + ' pictures named correctly as the same damage gets stronger. ' +
      'Shaded: 95% confidence intervals over pictures and noise seeds. The doses were set from earlier English runs to give mild to severe damage in English.';
    var note = $('dose-note');
    note.innerHTML = '';
    if (!first || !first.acc[v]) return;
    var said = function (p) { return 'English named ' + pct(p.acc.en[0]) + ' of the pictures and ' + L + ' ' + pct(p.acc[v][0]); };
    var txt = 'At the mildest dose here (' + first.tick + '), ' + said(first) + '.';
    if (last !== first) txt += ' At the strongest (' + last.tick + '), ' + said(last) + '.';
    note.appendChild(document.createTextNode(txt + ' '));
    var x = f.extra_drop && f.extra_drop[v];
    if (x) note.appendChild(h('b', { text: 'At this damage location, across all doses, ' + L + ' lost ' + pts(x.diff) + ' points more than English (95% CI ' + ci(x.ci95) + ').' }));
    if (/control/.test(f.label)) note.appendChild(document.createTextNode(' This is a control: as many units as the naming lesion, chosen at random in the same layers.'));
    var t = $('dose-table');
    t.innerHTML = '';
    var cols = ['en'].concat(LANGS);
    t.appendChild(h('thead', null, h('tr', null, [h('th', { text: 'Damage' })].concat(cols.map(function (c) { return h('th', { class: 'num', text: name(c) }); })))));
    var tb = h('tbody');
    P.forEach(function (p) {
      tb.appendChild(h('tr', null, [h('td', { text: p.detail })].concat(cols.map(function (c) {
        var a = p.acc[c];
        return h('td', { class: 'num', text: a ? pct(a[0]) + ' [' + ci([a[1], a[2]]) + ']' : '–' });
      }))));
    });
    t.appendChild(tb);
  }

  // --- 3. falls back on English ---------------------------------------------------------------
  function renderSwitch() {
    var d = S.d, v = S.lang, L = name(v), sw = d.switching[v], rev = d.switching.reverse, src = d.source;
    $('switch-meta').textContent = 'all ' + src.n_conditions + ' kinds of damage, ' + num(sw.counts.trials) + ' answers';
    var big = $('switch-big');
    big.innerHTML = '';
    big.appendChild(h('span', { class: 'hero-num', text: pct(sw.english_answers.mean) }));
    big.appendChild(h('p', null, ['of the damaged model’s answers, asked in ', h('b', { text: L }), ', came out in ', h('b', { text: 'English' }), '.']));
    big.appendChild(h('p', { class: 'ci', text: 'Averaged over the kinds of damage; 95% CI ' + ci(sw.english_answers.ci95, '%') + '. That is ' + pct(sw.share_of_errors) + ' of all its mistakes in ' + L + '.' }));
    var meters = $('switch-meters');
    meters.innerHTML = '';
    function meter(label, value, fillClass, sub) {
      var fill = h('div', { class: 'fill ' + fillClass });
      fill.style.width = Math.max(0.5, value * 100) + '%';
      return h('div', { class: 'bl-meter' }, [h('div', { class: 'top' }, [h('span', { text: label }), h('b', { text: pct(value, value < 0.1 ? 1 : 0) })]),
        h('div', { class: 'track', role: 'img', 'aria-label': label + ': ' + pct(value, 1) }, fill), sub ? h('span', { class: 'sub', text: sub }) : null]);
    }
    meters.appendChild(meter('Asked in ' + L + ', answered in English', sw.english_answers.mean, 'bl-c-en', null));
    meters.appendChild(meter('Asked in English, answered in Spanish, French or Portuguese', rev.other_language_answers.mean, 'neutral',
      'Mostly garbled letters the language check can’t place.'));
    meters.appendChild(h('p', { class: 'bl-narr' }, [h('b', { text: 'Counting only the picture’s own name in the wrong language: ' }),
      pct(sw.english_name.mean) + ' of ' + L + ' answers were the English name, while ' + pct(rev.other_language_name.mean, 1) +
      ' of English answers (' + rev.counts.name_in_other_language + ' of ' + num(rev.counts.trials) + ') were another language’s name.']));
    var said = $('switch-said'), ex = sw.examples || {};
    said.innerHTML = '';
    if (ex.names && ex.names.length) {
      said.appendChild(h('h3', { text: 'What it said instead' }));
      said.appendChild(h('ul', { class: 'bl-chips' }, ex.names.map(function (e) {
        return h('li', null, [h('span', { class: 'asked', lang: v, text: e.target }), h('span', { 'aria-hidden': 'true', text: '→' }),
          h('span', { class: 'said', lang: 'en', text: '“' + e.said + '”' })]);
      })));
    }
    if (ex.narration) {
      said.appendChild(h('p', { class: 'bl-narr' }, ['Or it narrated the task in English, the voice of its hidden reasoning: ', h('q', { lang: 'en', text: ex.narration })]));
    }
  }

  // --- 4. word lens -------------------------------------------------------------------------------
  function lensData() { return S.d.lens[S.lang]; }
  function renderPics() {
    var Ld = lensData(), box = $('lens-pics');
    box.innerHTML = '';
    if (S.pic > Ld.examples.length) S.pic = 0;
    Ld.examples.forEach(function (e, i) {
      box.appendChild(h('button', { type: 'button', 'aria-pressed': String(S.pic === i), onclick: function () { S.pic = i; renderLens(); } },
        e.target + ' (' + e.picture + ')'));
    });
    box.appendChild(h('button', { type: 'button', 'aria-pressed': String(S.pic === Ld.examples.length), onclick: function () { S.pic = Ld.examples.length; renderLens(); } },
      'All ' + Ld.n_items + ' pictures, average'));
  }
  function renderLens() {
    renderPics();
    var Ld = lensData(), v = S.lang, ex = Ld.examples[S.pic] || null;
    var pe = ex ? ex.p_english : Ld.mean_p.english, pt = ex ? ex.p_target : Ld.mean_p.target, nL = pe.length;
    var from = Math.min(LENS_FROM, nL - 8), layers = [];
    for (var l = from; l < nL; l++) layers.push(l);
    var wrap = $('lens-chart'), W = Math.max(280, wrap.clientWidth), narrow = W < 560;
    var m = { l: 42, r: narrow ? 14 : 120, t: 14, b: ex ? 82 : 44 }, ph = narrow ? 190 : 230, H = m.t + ph + m.b;
    var x = function (layer) { return m.l + (layer - from) / (nL - 1 - from) * (W - m.l - m.r); };
    var y = function (p) { return m.t + (1 - p) * ph; };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H });
    [0, 0.25, 0.5, 0.75, 1].forEach(function (t) {
      svg.appendChild(s('line', { class: 'grid', x1: m.l, x2: W - m.r, y1: y(t), y2: y(t) }));
      svg.appendChild(s('text', { x: m.l - 8, y: y(t) + 4, 'text-anchor': 'end' }, t.toFixed(t % 1 ? 2 : 0)));
    });
    svg.appendChild(s('line', { class: 'axis', x1: m.l, x2: W - m.r, y1: y(0), y2: y(0) }));
    layers.forEach(function (layer) {
      if ((layer - from) % (narrow ? 4 : 2) && layer !== nL - 1) return;
      svg.appendChild(s('text', { x: x(layer), y: y(0) + 16, 'text-anchor': 'middle' }, String(layer + 1)));
    });
    var tName = ex ? '“' + ex.target + '”' : name(v) + ' name', eName = ex ? '“' + ex.picture + '”' : 'English name';
    [['en', pe], [v, pt]].forEach(function (sr) {
      var g = s('g', { class: 'bl-c-' + sr[0], 'aria-hidden': 'true' });
      g.appendChild(s('polyline', { class: 'ln', points: layers.map(function (layer) { return x(layer).toFixed(1) + ',' + y(sr[1][layer]).toFixed(1); }).join(' ') }));
      var peak = layers.reduce(function (a, b) { return sr[1][b] > sr[1][a] ? b : a; }, layers[0]);
      var endL = sr[0] === 'en' ? peak : nL - 1;
      g.appendChild(s('circle', { class: 'dot', cx: x(endL), cy: y(sr[1][endL]), r: 4.5 }));
      svg.appendChild(g);
      var lab = (sr[0] === 'en' ? eName : tName) + ' ' + sr[1][endL].toFixed(2);
      var lx = sr[0] === 'en' ? x(endL) : (narrow ? x(endL) - 6 : x(endL) + 10), anchor = sr[0] === 'en' ? 'middle' : (narrow ? 'end' : 'start');
      var ly = sr[0] === 'en' ? y(sr[1][endL]) - 12 : (narrow ? y(sr[1][endL]) - 12 : y(sr[1][endL]) + 4);
      svg.appendChild(s('text', { x: lx, y: Math.max(10, ly), 'text-anchor': anchor, class: 't-ink t-halo' }, lab));
    });
    svg.appendChild(s('text', { x: m.l, y: m.t - 2 + ph + (ex ? 66 : 36), class: 't-ink2' }, 'Layer (1–' + from + ' not shown: both near 0)'));
    // Top guess strip: which word the lens ranks first after each layer.
    if (ex) {
      var sy = y(0) + 26, sh = 20, enSet = {}, tgSet = {};
      ex.english_top1_layers.forEach(function (l2) { enSet[l2] = 1; });
      ex.target_top1_layers.forEach(function (l2) { tgSet[l2] = 1; });
      var segs = [];
      layers.forEach(function (layer) {
        var kind = enSet[layer] ? 'en' : tgSet[layer] ? v : 'other', last = segs[segs.length - 1];
        if (last && last.kind === kind && last.tok === ex.top1[layer]) last.to = layer; else segs.push({ kind: kind, from: layer, to: layer, tok: ex.top1[layer] });
      });
      var half = (x(from + 1) - x(from)) / 2;
      svg.appendChild(s('text', { x: x(from) - half - 4, y: sy + 14, 'text-anchor': 'end', 'font-size': 10 }, 'top'));
      segs.forEach(function (sg) {
        var x0 = x(sg.from) - half + 1, x1 = x(sg.to) + half - 1, g = s('g', { class: sg.kind === 'other' ? '' : 'bl-c-' + sg.kind });
        g.appendChild(s('rect', { class: sg.kind === 'other' ? 'seg-other' : 'seg-rect', x: x0, y: sy, width: Math.max(1, x1 - x0), height: sh, rx: 3 }));
        var label = sg.kind === 'other' ? '' : sg.tok;
        if (label && label.length * 7 + 10 < x1 - x0) {
          g.appendChild(s('text', { class: 'seg-text' + (sg.kind === 'pt' || sg.kind === 'fr' ? ' dark' : ''), x: (x0 + x1) / 2, y: sy + 14, 'text-anchor': 'middle' }, label));
        }
        svg.appendChild(g);
      });
    }
    crosshair(svg, wrap, {
      n: layers.length, W: W, top: m.t, bottom: ex ? y(0) + 46 : y(0), left: x(from), right: x(nL - 1), start: layers.indexOf(Math.min(nL - 1, 40)),
      xOf: function (i) { return x(layers[i]); },
      label: 'Word lens on ' + (ex ? 'the ' + ex.picture + ' picture' : 'all ' + Ld.n_items + ' pictures') + ', asked in ' + name(v) +
        ': probability of the English name and of the ' + name(v) + ' name after each layer. Use the arrow keys to step through the layers; the table below lists every value.',
      nearest: function (px) { return Math.max(0, Math.min(layers.length - 1, Math.round((px - x(from)) / ((W - m.l - m.r) / (nL - 1 - from))))); },
      content: function (i) {
        var layer = layers[i], rows = [h('div', { text: 'After layer ' + (layer + 1) })];
        rows.push(tipRow('en', pe[layer].toFixed(2), eName));
        rows.push(tipRow(v, pt[layer].toFixed(2), tName));
        if (ex) rows.push(h('div', { class: 'sub', text: 'top guess: “' + ex.top1[layer] + '”' }));
        else rows.push(h('div', { class: 'sub', text: 'top guess on ' + pct(Ld.top1_share.english[layer]) + ' English, ' + pct(Ld.top1_share.target[layer]) + ' ' + name(v) }));
        return rows;
      }
    });
    mount(wrap, svg);
    var lg = $('lens-legend');
    lg.innerHTML = '';
    lg.appendChild(h('span', null, [key('en'), ex ? 'English name “' + ex.picture + '”' : 'English name (mean)']));
    lg.appendChild(h('span', null, [key(v), ex ? name(v) + ' name “' + ex.target + '”' : name(v) + ' name (mean)']));
    if (ex) lg.appendChild(h('span', null, [h('i', { class: 'gray' }), 'Strip: the top guess after each layer; gray, another word']));
    renderLensText(Ld, ex);
  }
  function renderLensText(Ld, ex) {
    var v = S.lang, L = name(v), et = S.d.lens.english_trials || {};
    $('lens-lede').textContent = 'The word lens reads the model’s best guess after each of its ' + Ld.n_layers + ' layers. Asked for the ' + L +
      ' word, the undamaged model first lands on the English one, and switches to ' + L + ' only near the end. The lines show the chance it gives each name.';
    var note = $('lens-note');
    note.innerHTML = '';
    if (ex) {
      var start = lastRunStart(ex.target_top1_layers);
      note.appendChild(h('b', { text: 'For the ' + ex.picture + ', the top guess is the English “' + ex.picture + '” at layers ' + runText(ex.english_top1_layers) + '.' }));
      note.appendChild(document.createTextNode(' The ' + L + ' word' + (start != null && ex.top1[start] && ex.top1[start].toLowerCase() !== ex.target.toLowerCase() ? ' (its first piece, “' + ex.top1[start] + '”)' : '') +
        ' takes over only at layer ' + (start + 1) + ', ' + (Ld.n_layers - start) + ' layers before the answer. The model said “' + ex.said + '”.'));
    } else {
      note.appendChild(h('b', { text: 'At layer ' + (Ld.peak_top1_layer + 1) + ', the English name is the top guess on ' + pct(Ld.peak_top1_english) + ' of the ' + Ld.n_items + ' pictures.' }));
      note.appendChild(document.createTextNode(' The ' + L + ' word becomes the top guess on most pictures only at layer ' + (Ld.target_majority_layer + 1) + '. ' +
        Ld.items_english_first + ' of ' + Ld.n_items + ' pictures show the English name first.' +
        (et.english_majority_layer != null && v === 'es' ? ' Asked in English, the English name leads from layer ' + (et.english_majority_layer + 1) + ', and the Spanish name is ' +
          (et.max_share_spanish_top1 ? 'rarely' : 'never') + ' the top guess.' : '') +
        ' Pictures whose English and ' + L + ' names start the same way (like cactus) are left out, because the lens can’t tell them apart.'));
    }
    var t = $('lens-table'), nL = Ld.n_layers, from = Math.min(LENS_FROM, nL - 8);
    var pe = ex ? ex.p_english : Ld.mean_p.english, ptg = ex ? ex.p_target : Ld.mean_p.target;
    t.innerHTML = '';
    var head = [h('th', { class: 'num', text: 'Layer' }), h('th', { class: 'num', text: 'English name' }), h('th', { class: 'num', text: L + ' name' })];
    head.push(ex ? h('th', { text: 'Top guess' }) : h('th', { class: 'num', text: 'Top guess: English / ' + L }));
    t.appendChild(h('thead', null, h('tr', null, head)));
    var tb = h('tbody');
    for (var l = from; l < nL; l++) {
      tb.appendChild(h('tr', null, [h('td', { class: 'num', text: String(l + 1) }), h('td', { class: 'num', text: pe[l].toFixed(3) }), h('td', { class: 'num', text: ptg[l].toFixed(3) }),
        ex ? h('td', { text: ex.top1[l] }) : h('td', { class: 'num', text: pct(Ld.top1_share.english[l]) + ' / ' + pct(Ld.top1_share.target[l]) })]));
    }
    t.appendChild(tb);
  }

  // --- 5. what it means -------------------------------------------------------------------------
  function renderMeaning() {
    var d = S.d, sm = d.summary, src = d.source, xen = sm.es_xen;
    var drops = LANGS.filter(function (v) { return sm[v]; }).map(function (v) { return pts(sm[v].extra_drop); });
    var li = function (b, rest) { return h('li', null, [h('b', { text: b }), ' ' + rest]); };
    var means = $('means'), doesnt = $('doesnt');
    means.innerHTML = '';
    doesnt.innerHTML = '';
    means.appendChild(li('Same damage, bigger loss.', 'On the same pictures, the same damage cost this model far more in Spanish, French and Portuguese than in English: ' +
      drops.slice(0, -1).join(', ') + ' and ' + drops[drops.length - 1] + ' points more.'));
    means.appendChild(li('It slips into English, almost never the other way.', 'When another language failed, the answer often came out in English. Damaged English answers almost never came out in another language.'));
    means.appendChild(li('A likely reason.', 'The intact model seems to reach the English word first and turn it into the asked-for word only in its last layers. Damage that disrupts that late step lets the English word out. (Wendler et al., 2024, found the same English detour in Llama 2.)' +
      (xen ? ' Asking for Spanish in English gave about the same loss (' + pts(xen.extra_drop) + ' points), so the weak step is producing the Spanish word, not reading a Spanish instruction.' : '')));
    means.appendChild(li('It echoes the clinic.', 'In bilingual people with aphasia whose two languages are affected differently, the language they knew better and used more before the stroke is often the better preserved one, and some slip into it (Kuzmina et al., 2019; Fabbro, 2001).'));
    doesnt.appendChild(li('It’s a model, not people.', 'This is about one AI, Muse Glimmer 30B. We don’t claim the model works like a brain: the parallel with bilingual aphasia is an analogy.'));
    doesnt.appendChild(li('Nothing about any person.', 'Not a medical test. It says nothing about how a particular bilingual person will do after a stroke.'));
    doesnt.appendChild(li('Small and specific.', src.n_pictures + ' pictures, one model, one precision (FP8). One picture moves a score by ' + Math.round(100 / src.n_pictures) +
      ' points. The intervals cover which pictures and noise seeds were used, not other models.'));
    doesnt.appendChild(li('The lens shows, it doesn’t prove.', 'It shows where the English word can be read out, not that the model needs it: we didn’t switch that step off to test it.'));
    doesnt.appendChild(li('Why English?', 'Glimmer presumably saw more English than other languages in training, as most large models do. We didn’t check.'));
    var sn = $('source-note');
    sn.innerHTML = '';
    sn.appendChild(document.createTextNode('Muse Glimmer 30B (' + (src.precision || 'FP8') + '), analyzed ' + (src.analyzed || '') + '. ' +
      'References: Kuzmina, Goral, Norvik & Weekes (2019), Frontiers in Psychology 10:445; Fabbro (2001), Brain and Language 79:201–210; Wendler et al. (2024), “Do Llamas work in English?”, ACL. Full method and caveats: '));
    sn.appendChild(h('a', { href: 'https://github.com/rnorlund/MetaLesionLab/blob/main/docs/bilingual.md', text: 'docs/bilingual.md' }));
    sn.appendChild(document.createTextNode('.'));
  }

  // --- state ------------------------------------------------------------------------------------
  function renderCharts() { renderDrop(); renderDose(); renderLens(); }
  function setLang(v) {
    if (LANGS.indexOf(v) < 0 || !S.d.summary[v]) return;
    S.lang = v;
    document.querySelectorAll('#lang-seg button').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-lang') === v)); });
    S.pic = Math.min(S.pic, lensData().examples.length);
    renderDropText(); renderDoseText(); renderSwitch(); renderCharts();
  }
  function setSite(k) {
    if (!S.d.dose.some(function (f) { return f.key === k; })) return;
    S.site = k;
    $('site').value = k;
    renderDose(); renderDoseText();
  }

  function init() {
    T.api('/api/lab/bilingual').then(function (d) {
      S.d = d;
      S.site = d.dose.some(function (f) { return f.key === 'layers 8-15'; }) ? 'layers 8-15' : d.dose[0].key;
      var want = T.param('lang');
      if (LANGS.indexOf(want) >= 0 && d.summary[want]) S.lang = want;
      document.querySelectorAll('#lang-seg button').forEach(function (b) {
        var v = b.getAttribute('data-lang');
        b.insertBefore(h('span', { class: 'bl-key bl-c-' + v, 'aria-hidden': 'true' }), b.firstChild);
        b.addEventListener('click', function () { setLang(v); });
        if (!d.summary[v]) b.disabled = true;
      });
      fillSites();
      renderHero();
      renderMeaning();
      setLang(S.lang);
      var t = null;
      window.addEventListener('resize', function () { clearTimeout(t); t = setTimeout(renderCharts, 120); });
      readyResolve();
    }).catch(function (err) {
      var box = $('load-error');
      box.textContent = 'Couldn’t load the results: ' + err.message;
      box.hidden = false;
      readyResolve();
    });
  }

  T.bilingual = { ready: ready, state: function () { return S; }, setLang: setLang, setSite: setSite };
  init();
})();
