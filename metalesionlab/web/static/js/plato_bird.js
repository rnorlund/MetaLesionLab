/* Plato's Bird (/plato/bird): name one member of a category, people vs. Muse Spark vs. Muse Glimmer.
   Reads /api/plato/bird (public_data/plato_bird.json). The "You vs. the AI" game runs here and stores nothing. */
(function () {
  'use strict';
  var h = TOT.h;
  var SVGNS = 'http://www.w3.org/2000/svg';
  // the site's colour tokens (app.css): a theme switch recolours the charts
  var COLORS = { people: 'var(--orange)', spark: 'var(--blue)', glimmer: 'var(--s-glimmer)', axis: 'var(--chart-axis)', grid: 'var(--chart-grid)',
                 ink: 'var(--ink)', ink2: 'var(--ink-2)', muted: 'var(--faint)', chart: 'var(--chart-bg)' };
  var QUICK = ['bird', 'fruit', 'fish', 'emotion', 'hat', 'gemstone', 'colour', 'insect', 'game'];
  var GAME_CATS = ['fruit', 'bird', 'colour', 'flower', 'fish', 'vegetable', 'musical instrument', 'sport', 'insect',
                   'tree', 'gemstone', 'weapon', 'snake', 'hat', 'emotion', 'furniture', 'metal', 'spice'];
  var D = null, BY = {}, current = 'bird', scatterSrc = 'spark', gameIdx = 0;

  function pct(x) { return x == null || isNaN(x) ? '–' : Math.round(100 * x) + '%'; }
  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }
  function svg(tag, attrs, parent) {
    var el = document.createElementNS(SVGNS, tag);
    Object.keys(attrs || {}).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(el);
    return el;
  }
  function svgText(parent, x, y, text, attrs) {
    var t = svg('text', Object.assign({ x: x, y: y, 'font-size': 12, fill: COLORS.muted,
                                        'font-family': 'IBM Plex Sans, system-ui, sans-serif' }, attrs || {}), parent);
    t.textContent = text;
    return t;
  }

  // ---------- answer panels ----------
  function panel(kind, title, meta, table, highlight) {
    var list = h('ul', { class: 'pb-bars' });
    var total = (table || []).reduce(function (a, r) { return a + r[1]; }, 0) || 1;
    var max = 0;
    (table || []).forEach(function (r) { if (r[0] !== '(other)') max = Math.max(max, r[1] / total); });
    var rows = (table || []).filter(function (r) { return r[0] !== '(other)'; }).slice(0, 7);
    var shown = rows.reduce(function (a, r) { return a + r[1]; }, 0);
    if (total - shown > 0) rows = rows.concat([['(other)', total - shown]]);
    rows.forEach(function (r) {
      var share = r[1] / total;
      var other = r[0] === '(other)';
      var fill = h('span', { class: 'fill' });
      fill.style.width = Math.max(1.5, 100 * share) + '%';
      list.appendChild(h('li', { class: 'pb-bar' + (other ? ' other' : '') + (highlight && r[0] === highlight ? ' hit' : ''),
                                 title: (other ? 'Other answers' : cap(r[0])) + ': ' + r[1] + ' of ' + total }, [
        h('span', { class: 'lab', text: other ? 'Other answers' : cap(r[0]) }),
        h('span', { class: 'track' }, [fill]),
        h('span', { class: 'n', text: String(r[1]) })
      ]));
    });
    if (!rows.length) list.appendChild(h('li', { class: 'pb-note', text: 'No data for this category.' }));
    return h('div', { class: 'pb-panel ' + kind }, [
      h('h3', null, [h('span', { class: 'key', 'aria-hidden': 'true' }), title]),
      h('p', { class: 'meta', text: meta }), list
    ]);
  }

  function trio(el, row) {
    el.innerHTML = '';
    var t = row.tables || {};
    if (t.human_first) {
      el.appendChild(panel('people', 'People', row.n_human + ' UK adults, first answer', t.human_first));
    } else {
      el.appendChild(h('div', { class: 'pb-panel people' }, [
        h('h3', null, [h('span', { class: 'key', 'aria-hidden': 'true' }), 'People']),
        h('p', { class: 'meta', text: 'The study of people’s answers has no “' + row.category + '” category, so this one is AI only.' })]));
    }
    el.appendChild(panel('spark', 'Muse Spark', 'asked 50 separate times', t.spark));
    el.appendChild(panel('glimmer', 'Muse Glimmer', 'asked 50 times, standard randomness', t['glimmer_T1.0']));
  }

  // ---------- the first screen: everyone's answers as one bar each, and three numbers drawn (FirstLook) ----------
  function shareBar(kind, title, meta, table) {
    var rows = (table || []).slice().sort(function (a, b) {
      var ao = a[0] === '(other)' ? 1 : 0, bo = b[0] === '(other)' ? 1 : 0;
      return ao - bo || b[1] - a[1];
    });
    var total = rows.reduce(function (a, r) { return a + r[1]; }, 0) || 1;
    var named = rows.filter(function (r) { return r[0] !== '(other)'; }).length;
    var said = rows.map(function (r) { return (r[0] === '(other)' ? 'other answers' : r[0]) + ' ' + r[1]; }).join(', ');
    var bar = h('div', { class: 'pb-share-bar', role: 'img', 'aria-label': title + ', ' + total + ' answers: ' + said });
    rows.forEach(function (r) {
      var share = r[1] / total, other = r[0] === '(other)';
      var seg = h('span', { class: 'pb-piece' + (other ? ' other' : ''), title: (other ? 'Other answers' : cap(r[0])) + ': ' + r[1] + ' of ' + total });
      seg.style.flexGrow = String(r[1]);
      // a name only where it fits: the narrower the bar, the fewer pieces are named (plato_firstscreen.css); the title has every one
      if (share >= 0.1) seg.appendChild(h('span', { class: 'lab' + (share < 0.15 ? ' sm' : share < 0.3 ? ' mid' : ''),
        text: (other ? 'other' : r[0]) + (share >= 0.5 ? ' ×' + r[1] : '') }));
      bar.appendChild(seg);
    });
    return h('div', { class: 'pb-share ' + kind }, [
      h('p', { class: 'pb-share-h' }, [h('span', { class: 'key', 'aria-hidden': 'true' }), h('b', { text: title }),
        h('span', { text: ' ' + meta + ' · ' + named + (named === 1 ? ' answer' : ' different answers') })]),
      bar]);
  }
  function hero() {
    var bird = BY.bird, s = D.summary.spark.dominance, g = D.summary.glimmer_logits.dominance;
    var spark = bird.tables.spark, sTop = spark[0], nSpark = spark.reduce(function (a, r) { return a + r[1]; }, 0);
    document.getElementById('hero-answer').textContent = 'Meta’s chat AI, Muse Spark, says “' + sTop[0] + '” ' + sTop[1] +
      ' times in ' + nSpark + '; ' + bird.n_human + ' people named ' + bird.human.distinct + ' different birds.';
    var sh = document.getElementById('hero-shares');
    sh.innerHTML = '';
    sh.appendChild(shareBar('people', 'People', bird.n_human + ' UK adults', bird.tables.human_first));
    sh.appendChild(shareBar('spark', 'Muse Spark', 'asked ' + nSpark + ' times', spark));
    if (bird.tables['glimmer_T1.0']) sh.appendChild(shareBar('glimmer', 'Muse Glimmer', 'asked 50 times', bird.tables['glimmer_T1.0']));
    var pic = (D.pictures || {}).bird;
    if (pic && pic.spark) {
      document.getElementById('hero-drawn-cap').textContent = 'And when we asked Meta’s image AI, Muse Image, to draw “a bird” 12 times, it drew the same ' +
        'little songbird every time (Muse Spark called ' + pic.spark.top_count + ' of them a ' + pic.spark.top[0] + ').';
    }
    if (!window.FirstLook) return;
    var ai = Math.round(100 * s.ai_mean.mean), hu = Math.round(100 * s.human_mean.mean);
    var gt = (D.summary['glimmer_T1.0'] || {}).dominance, gl = gt ? Math.round(100 * gt.ai_mean.mean) : null;
    // the planned prediction: the AI's favourite answer takes a larger share than people's, for Spark and for Glimmer at T = 1
    var sparkYes = s.diff.ci95[0] > 0, glimYes = gt ? gt.diff.ci95[0] > 0 : null;
    var glimSaid = !gt ? '' : gt.diff.ci95[0] <= 0 && gt.diff.ci95[1] >= 0 ? 'was as varied as people.' :
      gt.diff.mean > 0 ? 'stuck to its favourite more than people too.' : 'was more varied than people.';
    var stats = [
      { kind: 'bars', ask: 'Answers that go to its favourite', verdict: sparkYes && glimYes === false ? { tone: 'part', text: 'Partly as predicted' } :
          sparkYes ? { tone: 'yes', text: 'As predicted' } : { tone: 'no', text: 'Prediction failed' },
        o: { values: gl == null ? [ai, hu] : [ai, hu, gl], labels: ['Spark', 'People', 'Glimmer'], tones: ['blue', 'orange', 'green'], max: 100, suffix: '%',
          label: 'of answers go to its favourite, against ' + hu + '% for people',
          alt: 'Across ' + s.n + ' categories, Muse Spark’s favourite answer takes ' + ai + '% of its answers; people’s favourite takes ' + hu + '%' +
            (gl == null ? '.' : '; Muse Glimmer’s, at its standard randomness setting, ' + gl + '%.') },
        q: 'The average over ' + s.n + ' categories: how much of Muse Spark’s answers go to its single favourite. We predicted both AIs would stick to one favourite more than people do. Muse Spark ' + (sparkYes ? 'did' : 'didn’t') + '.' +
          (gt ? ' Muse Glimmer, at its standard randomness setting, ' + glimSaid : '') + ' Each side is measured on the same number of answers.' },
      { kind: 'dots',
        o: { k: s.n_ai_higher, n: s.n, tone: 'blue', cols: 18, label: 'categories where it sticks to one answer more',
          alt: 'Muse Spark sticks to one answer more than people in ' + s.n_ai_higher + ' of ' + s.n + ' categories.' },
        q: 'Categories in which Muse Spark sticks to its favourite answer more than people do. In ' + s.n_ai_lower + ', people stuck to one answer more.' + (s.abstract_minus_concrete && s.abstract_minus_concrete.ci95[0] <= 0 &&
          s.abstract_minus_concrete.ci95[1] >= 0 ? ' We also predicted a bigger gap for abstract categories (emotion, crime) than for concrete ones ' +
          '(fruit, bird). That didn’t happen: the gap is about the same.' : '') }
    ];
    if (pic && pic.spark) {
      var nPics = (pic.spark.labels || []).length || 12, rest = nPics - pic.spark.top_count;
      stats.push({ kind: 'dots', ask: 'Muse Image birds that look like a ' + pic.spark.top[0],
        o: { k: pic.spark.top_count, n: nPics, tone: 'ink', cols: 6, label: 'of Muse Image’s birds look like a ' + pic.spark.top[0],
          alt: pic.spark.top_count + ' of the ' + nPics + ' birds Muse Image drew look like a ' + pic.spark.top[0] + ' to Muse Spark.' },
        q: 'We asked Muse Spark which bird each drawing shows.' + (rest > 0 ? ' The other ' + rest + ' show the same small songbird.' : '') });
    }
    window.FirstLook.render(document.getElementById('hero-stats'), { stats: stats });
    document.getElementById('hero-qual').textContent = 'Muse Glimmer’s own odds for each answer are about as varied as people’s answers too: on average it gives its favourite a ' +
      pct(g.ai_mean.mean) + ' chance. Muse Spark answered once each time we asked, at its usual settings. People named as many as they could aloud ' +
      'for a minute, and we kept the first.';
  }

  // ---------- pick a category ----------
  function fact(label, value) { return h('div', null, [h('dt', { text: label }), h('dd', { text: value })]); }

  function showCategory(name, scroll) {
    var row = BY[name];
    if (!row) return;
    current = name;
    document.getElementById('cat-select').value = name;
    [].forEach.call(document.querySelectorAll('#cat-quick button'), function (b) {
      b.setAttribute('aria-pressed', b.dataset.cat === name ? 'true' : 'false');
    });
    document.getElementById('pick-q').textContent = '“Name one member of the category ' + name + '.”';
    trio(document.getElementById('pick-trio'), row);
    var f = document.getElementById('pick-facts');
    f.innerHTML = '';
    var sp = row.spark || {}, gl = row['glimmer_T1.0'] || {};
    if (row.human) {
      f.appendChild(fact('Share of answers going to the favourite (out of ' + row.n_human + ')',
        'People ' + pct(row.human.dominance) + ' · Spark ' + pct(sp.dominance) + ' · Glimmer ' + pct(gl.dominance)));
      f.appendChild(fact('Different answers, out of ' + row.n_human + ' (AI: on average)',
        'People ' + row.human.distinct + ' · Spark ' + (sp.distinct || 0).toFixed(1) + ' · Glimmer ' + (gl.distinct || 0).toFixed(1)));
      if (sp.top && sp.top.length) {
        f.appendChild(fact('People who said “' + sp.top[0] + '” at any point in their minute',
          sp.top_human_prod == null ? '–' : sp.top_human_prod + ' of ' + (row.n_people || 20) + ' people'));
        f.appendChild(fact('How typical people rate it, from 1 to 5',
          '“' + sp.top[0] + '” ' + (sp.top_typicality ? sp.top_typicality.toFixed(1) : 'not rated') + ' · people’s favourite ' +
          (row.human.top_typicality ? row.human.top_typicality.toFixed(1) : 'not rated')));
      }
    } else {
      f.appendChild(fact('Share of answers going to the favourite (out of 50)', 'Spark ' + pct(sp.dominance) + ' · Glimmer ' + pct(gl.dominance)));
    }
    if (scroll) document.getElementById('pick').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function picker() {
    var sel = document.getElementById('cat-select');
    var groups = { Concrete: h('optgroup', { label: 'Concrete' }), Abstract: h('optgroup', { label: 'Abstract' }),
                   AI: h('optgroup', { label: 'AI only (no people’s norms)' }) };
    D.categories.concat(D.ai_only || []).slice().sort(function (a, b) { return a.category < b.category ? -1 : 1; })
      .forEach(function (r) {
        groups[r.tables && r.tables.human_first ? r.domain : 'AI'].appendChild(h('option', { value: r.category, text: r.category }));
      });
    [groups.Concrete, groups.Abstract, groups.AI].forEach(function (g) { if (g.children.length) sel.appendChild(g); });
    sel.addEventListener('change', function () { showCategory(sel.value); });
    var quick = document.getElementById('cat-quick');
    QUICK.forEach(function (c) {
      if (!BY[c]) return;
      quick.appendChild(h('button', { type: 'button', 'data-cat': c, 'aria-pressed': 'false', text: c,
                                      onclick: function () { showCategory(c); } }));
    });
    showCategory(current);
  }

  // ---------- all categories: scatter ----------
  var tip = null;
  function showTip(evt, row, src, wrap) {
    var ai = row[src] || {};
    tip.innerHTML = '';
    tip.appendChild(h('b', { text: row.category }));
    tip.appendChild(h('div', { text: 'People: “' + (row.human.top[0] || '–') + '” ' + pct(row.human.dominance) }));
    tip.appendChild(h('div', { text: (src === 'spark' ? 'Spark' : 'Glimmer') + ': “' + ((ai.top || [])[0] || '–') + '” ' + pct(ai.dominance) }));
    tip.appendChild(h('div', { text: row.domain + ' · click to see the answers', style: { opacity: 0.75 } }));
    tip.hidden = false;
    var box = wrap.getBoundingClientRect();
    var x, y;
    if (evt && evt.clientX != null) { x = evt.clientX - box.left; y = evt.clientY - box.top; }
    else { var r = evt.target.getBoundingClientRect(); x = r.left - box.left + r.width / 2; y = r.top - box.top; }
    tip.style.left = Math.min(box.width - 270, Math.max(0, x + 14)) + 'px';
    tip.style.top = Math.max(0, y - 10) + 'px';
  }

  function scatter() {
    var wrap = document.querySelector('.pb-scatter-wrap');
    var el = document.getElementById('scatter');
    tip = document.getElementById('tip');
    el.innerHTML = '';
    // a narrower coordinate system on phones keeps the 12 px labels readable
    var narrow = (el.clientWidth || 760) < 600;
    var W = narrow ? 400 : 760, H = narrow ? 400 : 520, m = { l: narrow ? 50 : 64, r: 14, t: 16, b: 50 };
    var pw = W - m.l - m.r, ph = H - m.t - m.b;
    var s = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, 'aria-hidden': 'true' }, el);
    var X = function (v) { return m.l + v * pw; }, Y = function (v) { return m.t + (1 - v) * ph; };
    [0, 0.25, 0.5, 0.75, 1].forEach(function (v) {
      svg('line', { x1: X(v), x2: X(v), y1: Y(0), y2: Y(1), stroke: COLORS.grid, 'stroke-width': 1 }, s);
      svg('line', { x1: X(0), x2: X(1), y1: Y(v), y2: Y(v), stroke: COLORS.grid, 'stroke-width': 1 }, s);
      svgText(s, X(v), Y(0) + 18, Math.round(v * 100) + '%', { 'text-anchor': 'middle' });
      svgText(s, X(0) - 8, Y(v) + 4, Math.round(v * 100) + '%', { 'text-anchor': 'end' });
    });
    svg('line', { x1: X(0), y1: Y(0), x2: X(1), y2: Y(1), stroke: COLORS.axis, 'stroke-width': 1.5 }, s);
    svgText(s, X(0.5), H - 12, 'People: share going to their favourite first answer', { 'text-anchor': 'middle', fill: COLORS.ink2, 'font-size': 13 });
    svgText(s, 16, Y(0.5), 'AI: share going to its favourite answer', { 'text-anchor': 'middle', fill: COLORS.ink2, 'font-size': 13,
                                                                      transform: 'rotate(-90 16 ' + Y(0.5) + ')' });
    var color = scatterSrc === 'spark' ? COLORS.spark : COLORS.glimmer;
    D.categories.forEach(function (row) {
      var ai = row[scatterSrc];
      if (!ai || !row.human) return;
      var g = svg('g', { class: 'pt' + (row.category === current ? ' sel' : ''), tabindex: 0, role: 'button',
                         'aria-label': row.category + ': people ' + pct(row.human.dominance) + ', AI ' + pct(ai.dominance) }, s);
      var cx = X(row.human.dominance), cy = Y(ai.dominance);
      svg('circle', { class: 'hit', cx: cx, cy: cy, r: 12 }, g);
      var concrete = row.domain === 'Concrete';
      svg('circle', { class: 'dot', cx: cx, cy: cy, r: 5.5, fill: concrete ? color : COLORS.chart, stroke: color,
                      'stroke-width': concrete ? 2 : 2, 'paint-order': 'stroke' }, g);
      g.addEventListener('pointermove', function (e) { showTip(e, row, scatterSrc, wrap); });
      g.addEventListener('pointerleave', function () { tip.hidden = true; });
      g.addEventListener('focus', function (e) { showTip(e, row, scatterSrc, wrap); });
      g.addEventListener('blur', function () { tip.hidden = true; });
      var pick = function () { tip.hidden = true; showCategory(row.category, true); scatter(); };
      g.addEventListener('click', pick);
      g.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } });
    });
    var leg = document.getElementById('scatter-legend');
    leg.innerHTML = '';
    var sw1 = h('span', { class: 'sw' }); sw1.style.background = color;
    var sw2 = h('span', { class: 'sw' }); sw2.style.border = '2px solid ' + color; sw2.style.background = COLORS.chart;
    var ln = h('span', { class: 'ln' }); ln.style.background = COLORS.axis;
    leg.appendChild(h('span', null, [sw1, 'Concrete category, like fruit (' + D.categories.filter(function (r) { return r.domain === 'Concrete'; }).length + ')']));
    leg.appendChild(h('span', null, [sw2, 'Abstract category, like emotion (' + D.categories.filter(function (r) { return r.domain === 'Abstract'; }).length + ')']));
    leg.appendChild(h('span', null, [ln, 'Diagonal: the AI sticks to one answer exactly as much as people']));
    allText();
  }

  function card(big, text) { return h('div', { class: 'pb-card' }, [h('span', { class: 'big', text: big }), h('p', { text: text })]); }

  function ciText(c) { return 'probably between ' + c.ci95[0].toFixed(2) + ' and ' + c.ci95[1].toFixed(2); }

  function allText() {
    var S = D.summary, src = scatterSrc, name = src === 'spark' ? 'Muse Spark' : 'Muse Glimmer (standard randomness setting)';
    var d = S[src].dominance, e = S[src].entropy_bits;
    document.getElementById('all-sub').textContent = 'Each dot is one category. Across: how many of people’s answers went to their favourite. ' +
      'Up: the same for the AI. Above the diagonal line, ' + name + ' sticks to one answer more than people do. Both sides use the same number ' +
      'of answers. Click a dot to see its answers.';
    var cards = document.getElementById('all-cards');
    cards.innerHTML = '';
    cards.appendChild(card(pct(d.ai_mean.mean) + ' vs. ' + pct(d.human_mean.mean),
      'Average share of answers going to the favourite: ' + name + ' against people. Difference ' + (d.diff.mean >= 0 ? '+' : '') +
      d.diff.mean.toFixed(2) + ', ' + ciText(d.diff) + ' (95% confidence interval over categories).'));
    cards.appendChild(card(d.n_ai_higher + ' of ' + d.n, 'Categories in which ' + name + ' sticks to one answer more than people do.'));
    cards.appendChild(card(e.ai_mean.mean.toFixed(1) + ' vs. ' + e.human_mean.mean.toFixed(1) + ' bits',
      'How unpredictable the answers are, in bits (we call this entropy): 0 means always the same answer, 1 is like a coin toss between two, ' +
      '2 like four equally likely answers. Difference ' + e.diff.mean.toFixed(2) + ', ' + ciText(e.diff) + '.'));
    var bd = d.by_domain, gap = d.abstract_minus_concrete;
    var sg = function (x) { return (x >= 0 ? '+' : '') + x.toFixed(2); };
    cards.appendChild(card(sg(bd.Concrete.diff.mean) + ' vs. ' + sg(bd.Abstract.diff.mean),
      'How much more the AI sticks to its favourite than people do, for concrete things (fruit, bird) against abstract ones (emotion, crime): ' +
      'about the same. Difference ' + gap.diff.toFixed(2) + ', probably between ' + gap.ci95[0].toFixed(2) + ' and ' + gap.ci95[1].toFixed(2) + '.'));
    var tb = document.querySelector('#all-table tbody');
    tb.innerHTML = '';
    D.categories.forEach(function (r) {
      var tops = [r.human, r.spark, r['glimmer_T1.0']].map(function (m) {
        return m && m.top && m.top.length ? m.top[0] + ' (' + pct(m.dominance) + ')' : '–';
      });
      tb.appendChild(h('tr', null, [h('th', { scope: 'row', text: r.category }), h('td', { text: r.domain })].concat(
        tops.map(function (t) { return h('td', { text: t }); }))));
    });
  }

  function who() {
    [].forEach.call(document.querySelectorAll('#who-seg button'), function (b) {
      b.addEventListener('click', function () {
        scatterSrc = b.dataset.src;
        [].forEach.call(document.querySelectorAll('#who-seg button'), function (o) {
          o.setAttribute('aria-pressed', o === b ? 'true' : 'false');
        });
        scatter();
      });
    });
  }

  // ---------- drawn vs named ----------
  function drawn() {
    var grid = document.getElementById('draw-grid');
    var pics = D.pictures || {};
    var keys = Object.keys(pics);
    var match = 0;
    keys.forEach(function (k) {
      var p = pics[k], lab = p.spark || p.glimmer || {};
      var named = (p.named_top.spark || [])[0];
      var ok = lab.matches && lab.matches.spark;
      if (ok) match += 1;
      var noun = p.phrase.replace(/^an? /, '').replace(/^piece of /, '');
      var nGeneric = 12 - (lab.n_specific || 0);
      var drawnText;
      if (!lab.top || !lab.top.length) drawnText = 'no particular kind';
      else if (nGeneric >= 6) drawnText = 'just “a ' + noun + '” (' + nGeneric + ' of 12); ' + lab.top[0] + ' ' + lab.top_count;
      else drawnText = cap(lab.top[0]) + ' (' + lab.top_count + ' of 12)' + (nGeneric ? '; ' + nGeneric + ' just “' + noun + '”' : '');
      var people = (p.named_top.human || []).join(' / ') || 'not in the study';
      grid.appendChild(h('article', { class: 'pb-draw' }, [
        h('img', { src: '/static/img/plato_bird/' + k + '.webp', width: 596, height: 196, loading: 'lazy',
                   alt: '12 quick drawings of “' + p.phrase + '” by Muse Image. Muse Spark names most of them as: ' + drawnText + '.' }),
        h('div', { class: 'body' }, [
          h('h3', null, ['“' + p.phrase + '”', h('span', { class: 'verdict' + (ok ? '' : ' no'), text: ok ? 'draws what Spark names' : 'draws something else' })]),
          h('div', { class: 'who' }, [h('span', { class: 'k', text: 'Draws' }), h('b', { text: drawnText })]),
          h('div', { class: 'who' }, [h('span', { class: 'k', text: 'Names' }), h('span', { text: named ? cap(named) + ' (Spark, ' + ((BY[p.norms_category] || {}).tables || { spark: [[0, 0]] }).spark[0][1] + ' of 50)' : '–' })]),
          h('div', { class: 'who' }, [h('span', { class: 'k', text: 'People' }), h('span', { text: cap(people) })])
        ])
      ]));
    });
    document.getElementById('draw-sub').textContent = 'Asked for “a chair”, Meta’s image AI, Muse Image, draws the same plain chair nearly every time. ' +
      'Does it draw the same favourite that Muse Spark names? We asked Muse Image for 12 quick drawings of each of ' + keys.length +
      ' categories. Then Muse Spark looked at each drawing and said which member it shows. The favourite drawn matches the favourite named in ' +
      match + ' of ' + keys.length + '. Muse Spark names a car, but Muse Image draws a pickup truck; a rose, but it draws a daisy; chess, but it draws Super Mario.';
  }

  // ---------- temperature ----------
  function temperature() {
    var S = D.summary, el = document.getElementById('temp-chart');
    el.innerHTML = '';
    document.getElementById('temp-legend').innerHTML = '';
    var narrow = (el.clientWidth || 760) < 600;
    var W = narrow ? 400 : 760, H = narrow ? 330 : 380, m = { l: narrow ? 50 : 64, r: narrow ? 104 : 150, t: 20, b: 50 };
    var pw = W - m.l - m.r, ph = H - m.t - m.b;
    var s = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, 'aria-hidden': 'true' }, el);
    var X = function (t) { return m.l + (t - 0.4) / 1.7 * pw; }, Y = function (v) { return m.t + (1 - v) * ph; };
    [0, 0.25, 0.5, 0.75, 1].forEach(function (v) {
      svg('line', { x1: X(0.4), x2: X(2.1), y1: Y(v), y2: Y(v), stroke: COLORS.grid }, s);
      svgText(s, X(0.4) - 8, Y(v) + 4, Math.round(v * 100) + '%', { 'text-anchor': 'end' });
    });
    [0.5, 1, 1.5, 2].forEach(function (t) { svgText(s, X(t), Y(0) + 18, String(t), { 'text-anchor': 'middle' }); });
    svgText(s, X(1.25), H - 10, 'Randomness setting, or temperature (higher = more random)', { 'text-anchor': 'middle', fill: COLORS.ink2, 'font-size': 13 });
    svgText(s, 16, Y(0.5), 'Average share going to the favourite', { 'text-anchor': 'middle', fill: COLORS.ink2, 'font-size': 13, transform: 'rotate(-90 16 ' + Y(0.5) + ')' });
    function hline(v, color, label) {
      svg('line', { x1: X(0.4), x2: X(2.1), y1: Y(v), y2: Y(v), stroke: color, 'stroke-width': 2 }, s);
      svgText(s, X(2.1) + 8, Y(v) + 4, label + ' ' + pct(v), { fill: COLORS.ink2 });
    }
    hline(S.spark.dominance.human_mean.mean, COLORS.people, 'People');
    hline(S.spark.dominance.ai_mean.mean, COLORS.spark, narrow ? 'Spark' : 'Spark, usual');
    // keys are the analysis's own strings ("0.5", "1.0"): keep them, never round-trip through Number
    var temps = Object.keys(S.logit_temperature).sort(function (a, b) { return +a - +b; });
    var pts = temps.map(function (t) { return [X(+t), Y(S.logit_temperature[t].dominance.mean)]; });
    svg('polyline', { points: pts.map(function (p) { return p.join(','); }).join(' '), fill: 'none', stroke: COLORS.glimmer,
                      'stroke-width': 2, 'stroke-linejoin': 'round' }, s);
    pts.forEach(function (p, i) {
      var c = svg('circle', { cx: p[0], cy: p[1], r: 4, fill: COLORS.glimmer, stroke: COLORS.chart, 'stroke-width': 2 }, s);
      var t = svg('title', {}, c); t.textContent = 'Glimmer’s own odds at setting ' + (+temps[i]) + ': ' + pct(S.logit_temperature[temps[i]].dominance.mean) + ' on the favourite';
    });
    ['0.7', '1.0', '1.5'].forEach(function (t) {
      var k = 'glimmer_T' + t;
      if (!S[k]) return;
      var c = svg('circle', { cx: X(+t), cy: Y(S[k].dominance.ai_mean.mean), r: 6, fill: COLORS.chart, stroke: COLORS.glimmer, 'stroke-width': 2 }, s);
      var tt = svg('title', {}, c); tt.textContent = 'Glimmer, 50 answers at setting ' + t + ': ' + pct(S[k].dominance.ai_mean.mean) + ' on the favourite';
    });
    var sk = Object.keys(S).filter(function (k) { return k.indexOf('spark_T') === 0; })[0];
    if (sk) {
      var T = +sk.slice(7), v = S[sk].dominance.mean;
      var dmd = svg('rect', { x: X(T) - 6, y: Y(v) - 6, width: 12, height: 12, fill: COLORS.spark, transform: 'rotate(45 ' + X(T) + ' ' + Y(v) + ')' }, s);
      var tt2 = svg('title', {}, dmd); tt2.textContent = 'Spark at setting ' + T + ' (' + S[sk].n_categories + ' categories): ' + pct(v) + ' on the favourite';
      svgText(s, X(T) + 12, Y(v) + 20, 'Spark at ' + T, { fill: COLORS.ink2 });
    }
    var leg = document.getElementById('temp-legend');
    var l1 = h('span', { class: 'ln' }); l1.style.background = COLORS.glimmer;
    var l2 = h('span', { class: 'sw' }); l2.style.border = '2px solid ' + COLORS.glimmer;
    var l3 = h('span', { class: 'sw' }); l3.style.background = COLORS.spark; l3.style.borderRadius = '2px'; l3.style.transform = 'rotate(45deg)';
    leg.appendChild(h('span', null, [l1, 'Glimmer: its own odds, worked out at each setting']));
    leg.appendChild(h('span', null, [l2, 'Glimmer: 50 real answers']));
    leg.appendChild(h('span', null, [l3, 'Spark at a higher setting']));
    var lt = S.logit_temperature;
    document.getElementById('temp-sub').textContent = 'An AI picks each answer partly at random, and a setting called temperature controls how much ' +
      '(higher = more random). Could the AI’s narrowness just be this setting? At Glimmer’s standard setting (1), its own odds are about as varied as ' +
      'people’s answers. Turn the setting down and they pile onto one answer (' + pct(lt['0.5'].dominance.mean) + ' on the favourite at 0.5); ' +
      'turn it up past 1 and they spread out. Muse Spark barely moves.';
    if (sk) {
      document.getElementById('temp-note').textContent = 'We also asked Muse Spark at setting ' + sk.slice(7) + ', 20 times each for ' + S[sk].n_categories +
        ' categories. Its favourite still took ' + pct(S[sk].dominance.mean) + ' of answers (' +
        pct(S[sk].dominance_default_same_n.mean) + ' at its usual setting). The extra randomness mostly added garbled answers (“Se trav Node” for a bird), not new birds.';
    }
  }

  // ---------- you vs. the AI ----------
  var SING_KEEP = /(ss|us|is|ics|ese)$/;
  function norm(text) {
    var s = String(text || '').toLowerCase().normalize('NFKC').trim();
    s = s.split(/[,;\n]| or /)[0].replace(/[*_`"“”‘’.!?]/g, '').trim();
    s = s.replace(/^(a|an|the|one|some)\s+/, '').replace(/\s+/g, ' ');
    var words = s.split(' '), w = words[words.length - 1] || '';
    if (w.length > 3 && !SING_KEEP.test(w)) {
      if (/ies$/.test(w)) w = w.slice(0, -3) + 'y';
      else if (/(ches|shes|sses|xes)$/.test(w)) w = w.slice(0, -2);
      else if (/s$/.test(w)) w = w.slice(0, -1);
    }
    words[words.length - 1] = w;
    s = words.join(' ');
    var syn = D.synonyms || {};
    return syn[s] || s;
  }
  function squash(s) { return String(s).replace(/[\s\-']/g, ''); }
  function lookup(table, ans, head) {
    if (!table) return null;
    for (var i = 0; i < table.length; i++) {
      var k = table[i][0];
      if (k === '(other)') continue;
      if (squash(k) === squash(ans) || (head && squash(k) === squash(ans + ' ' + head)) ||
          (head && squash(k + ' ' + head) === squash(ans))) return table[i];
    }
    return null;
  }

  function gameSetup() {
    var cat = GAME_CATS[gameIdx % GAME_CATS.length];
    while (!BY[cat]) { gameIdx += 1; cat = GAME_CATS[gameIdx % GAME_CATS.length]; }
    document.getElementById('game-label').textContent = 'Name ' + (/^[aeiou]/.test(cat) ? 'an ' : 'a ') + cat;
    document.getElementById('game-input').value = '';
    document.getElementById('game-out').innerHTML = '';
    return cat;
  }

  function verdict(kind, big, text) {
    return h('div', { class: 'pb-verdict ' + kind }, [h('span', { class: 'big', text: big }), h('p', { text: text })]);
  }

  function gamePlay(cat, raw) {
    var out = document.getElementById('game-out');
    out.innerHTML = '';
    var ans = norm(raw);
    if (!ans) return;
    var row = BY[cat], t = row.tables, head = cat.split(' ').pop();
    var pFirst = lookup(t.human_first, ans, head), pNamed = lookup(t.human_named, ans, head);
    var sp = lookup(t.spark, ans, head), gl = lookup(t.glimmer_logits, ans, head);
    var sTop = t.spark[0][0], pTop = (row.human.top || [])[0];
    var msg;
    if (sp && sp[0] === sTop) msg = 'You think like Muse Spark: “' + sTop + '” is its answer ' + sp[1] + ' times out of 50.';
    else if (pFirst && pFirst[0] === pTop) msg = 'You’re with the crowd: “' + pTop + '” was people’s most common first answer.';
    else if (!pFirst && !sp && !gl && !pNamed) msg = 'Original! Nobody in our data said “' + ans + '”.';
    else msg = 'Less common than the favourites, but you’re not alone.';
    out.appendChild(h('p', { class: 'pb-game-msg', text: msg }));
    var n = row.n_human;
    out.appendChild(h('div', { class: 'pb-verdicts' }, [
      verdict('people', pFirst ? pFirst[1] + ' of ' + n : '0 of ' + n,
        'people said “' + ans + '” first. People’s favourite: “' + pTop + '” (' + pct(row.human.dominance) + ').' +
        (pNamed ? ' ' + pNamed[1] + ' of ' + (row.n_people || 20) + ' named it at some point in a minute.' : '')),
      verdict('spark', sp ? sp[1] + ' of 50' : '0 of 50', 'of Muse Spark’s answers were “' + ans + '”. Its favourite: “' + sTop + '”.'),
      verdict('glimmer', gl ? pct(gl[1]) : '< 1%', 'chance that Muse Glimmer answers “' + ans + '”, by its own odds.')
    ]));
  }

  function game() {
    var cat = gameSetup();
    document.getElementById('game-form').addEventListener('submit', function (e) {
      e.preventDefault();
      gamePlay(cat, document.getElementById('game-input').value);
    });
    document.getElementById('game-next').addEventListener('click', function () {
      gameIdx += 1;
      cat = gameSetup();
      document.getElementById('game-input').focus();
    });
  }

  // ---------- load ----------
  TOT.api('/api/plato/bird').then(function (data) {
    D = data;
    D.categories.concat(D.ai_only || []).forEach(function (r) { BY[r.category] = r; });
    hero();
    picker();
    who();
    scatter();
    drawn();
    temperature();
    game();
    var lastNarrow = window.innerWidth < 700, timer = null;
    window.addEventListener('resize', function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        var narrow = window.innerWidth < 700;
        if (narrow !== lastNarrow) { lastNarrow = narrow; scatter(); temperature(); }
      }, 150);
    });
  }).catch(function (err) {
    var el = document.getElementById('load-error');
    el.textContent = err.message || 'Could not load the data.';
    el.hidden = false;
  });
})();
