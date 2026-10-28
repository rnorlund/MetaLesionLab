/* Plato's Telephone (/plato/telephone): Muse Spark describes, Muse Image draws, ten times over. Reads
   /api/plato/telephone (public_data/plato_telephone.json plus the Plato passages, quoted only from
   public_data/plato_passages.json). Each chain's 11 pictures are one filmstrip, static/img/plato_telephone/. */
(function () {
  'use strict';
  var h = TOT.h;
  var SVGNS = 'http://www.w3.org/2000/svg';
  // the theme's tokens (app.css, plato_telephone.css), so the charts follow the light or dark theme without redrawing
  var C = { blue: 'var(--blue)', orange: 'var(--orange)', teal: 'var(--teal)', ink: 'var(--ink)', ink2: 'var(--ink-2)', muted: 'var(--faint)',
            grid: 'var(--gridline)', seedLine: 'var(--line-3)', surface: 'var(--chart)' };
  var N = 11;
  var D = null, gen = 10, chain = 0, timer = null;  // open on the last generation: the whole filmstrip shows
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function f2(x) { return x == null || isNaN(x) ? '–' : x.toFixed(2); }
  function f3(x) { return x == null || isNaN(x) ? '–' : x.toFixed(3); }
  function pct(x) { return x == null || isNaN(x) ? '–' : Math.round(100 * x) + '%'; }
  function signed(x, fmt) { return (x > 0 ? '+' : x < 0 ? '−' : '') + fmt(Math.abs(x)); }
  function ciTxt(c, fmt) { return c ? '[' + signedOrPlain(c[0], fmt) + ', ' + signedOrPlain(c[1], fmt) + ']' : ''; }
  function signedOrPlain(x, fmt) { return x < 0 ? '−' + fmt(-x) : fmt(x); }
  function svg(tag, attrs, parent) {
    var el = document.createElementNS(SVGNS, tag);
    Object.keys(attrs || {}).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(el);
    return el;
  }
  function text(parent, x, y, s, attrs) {
    var t = svg('text', Object.assign({ x: x, y: y, class: 'tick' }, attrs || {}), parent);
    t.textContent = s;
    return t;
  }
  function seedOf(key) { return D.seeds.filter(function (s) { return s.key === key; })[0]; }
  function chainOf(key, c) { return D.chains.filter(function (x) { return x.seed === key && x.chain === c; })[0]; }
  function defaultName(s) { return s.concept === 'chair' ? 'default chair' : s.concept === 'hat' ? 'default hat' : 'default clock'; }
  function kindName(s) { return s.label.replace(/ chair$/, '').replace(/^Adirondack$/, 'Adirondack'); }

  // ---------- the first screen: two chains drifting, and three numbers drawn (FirstLook, statviz.js) ----------
  var HERO_GENS = [0, 2, 4, 6, 8, 10];
  function firstClause(t) {  // "A rough black-ink sketch of a semicircular fanlight window" from Spark's whole description
    var s = String(t || ''), cut = s.indexOf(',', 30);
    return cut > 0 && cut < 110 ? s.slice(0, cut) + ' …' : s.length > 110 ? s.slice(0, 108) + ' …' : s;
  }

  function renderHero() {
    var box = document.getElementById('hero-chains');
    box.innerHTML = '';
    var st = D.striking || {};
    [['farthest_from_start', 'drifted farthest from where it started'], ['most_drift_to_form', 'fell into Muse’s textbook chair']].forEach(function (pick) {
      var p = st[pick[0]], s = p && seedOf(p.seed), ch = p && chainOf(p.seed, p.chain);
      if (!s || !ch) return;
      var src = D.sprites[p.seed + '_c' + p.chain];
      var frames = HERO_GENS.map(function (g) {
        var f = h('div', { class: 'frame' });
        f.style.backgroundImage = 'url(' + src + ')';
        f.style.backgroundPosition = (g * 10) + '% 0';
        return h('figure', null, [f, h('figcaption', null, g === 0 ? 'start' : 'copy ' + g)]);
      });
      var fell = pick[0] === 'most_drift_to_form' && ch.d_proto[N - 1] < 2 * D.reference.floor[s.concept];
      if (s.concept === 'chair') {  // the yardstick at the end of each row: Muse's own default chair
        frames.push(h('figure', { class: 'ref' }, [h('img', { src: '/static/img/plato_telephone/default_chair.webp', width: 176, height: 176,
          alt: 'Muse Image’s textbook chair, for comparison' }), h('figcaption', null, 'textbook chair')]));
      }
      var last = ch.descriptions[N - 1];
      box.appendChild(h('div', { class: 'tp-drift-row' + (fell ? ' fell' : '') }, [
        h('p', { class: 'tp-drift-h' }, [h('b', null, s.label.charAt(0).toUpperCase() + s.label.slice(1)),
          ' ' + (pick[0] === 'most_drift_to_form' && !fell ? 'moved closest to Muse’s textbook chair' : pick[1]) +
          ' · distance to the textbook chair ' + f2(ch.d_proto[0]) + ' → ' + f2(ch.d_proto[N - 1])]),
        h('div', { class: 'tp-drift-frames', role: 'img', 'aria-label': 'Chain ' + (p.chain + 1) + ' from ' + s.kind +
          ': the start and every second copy, beside Muse Image’s textbook chair.  Spark’s last description: ' + (last || '') }, frames),
        last ? h('p', { class: 'tp-drift-said' }, [h('span', null, 'Spark, copy 10: '), h('q', null, firstClause(last))]) : null
      ]));
    });
    if (!window.FirstLook) return;
    var t1 = D.tests.P1_drift_to_form, t2 = D.tests.P2_convergence, t3 = D.tests.P3_kind_first;
    var cc = D.chains.filter(function (c) { return !seedOf(c.seed).control; });
    var away = cc.filter(function (c) { return c.d_proto[N - 1] > c.d_proto[0]; }).length;
    var apart = t2.change.ci95[0] > 0, k = t3.first_loss_kind.mean, c = t3.first_loss_category.mean;
    window.FirstLook.render(document.getElementById('hero-stats'), { stats: [
      { kind: 'dots', verdict: t1.supported ? { tone: 'yes', text: 'As predicted' } : { tone: 'no', text: 'Prediction failed' },
        o: { k: away, n: cc.length, cols: 8, tone: 'blue', label: 'chair chains ended farther from the textbook chair than they started',
          alt: away + ' of ' + cc.length + ' chains from the 8 starting chairs ended farther from Muse’s textbook chair than they started.' },
        q: 'On average ' + f2(t1.g0) + ' → ' + f2(t1.g10) + ', change ' + signed(t1.change.mean, f2) + ' ' + ciTxt(t1.change.ci95, f2) + ': no clear pull.' },
      { kind: 'bars', verdict: t2.supported ? { tone: 'yes', text: 'As predicted' } : apart ? { tone: 'no', text: 'Prediction reversed' } : { tone: 'part', text: 'Not supported' },
        o: { values: [t2.g0, t2.g10], labels: ['start', 'copy 10'], tones: ['muted', 'blue'], digits: 2, value: f2(t2.g10), unit: 'from ' + f2(t2.g0),
          label: 'apart, chains from different chairs: they spread out, not together',
          alt: 'The distance between chains from different starting chairs went from ' + f2(t2.g0) + ' at the start to ' + f2(t2.g10) + ' after ten copies.' },
        q: 'Change ' + signed(t2.change.mean, f2) + ' ' + ciTxt(t2.change.ci95, f2) + '. Chains of one chair end ' + f2(t2.within_g10.mean) + ' apart.' },
      { kind: 'bars', verdict: t3.supported ? { tone: 'yes', text: 'As predicted' } : { tone: 'part', text: 'Not supported' },
        o: { values: [k, c], labels: ['the kind', '“chair”'], tones: ['blue', 'orange'], max: N, digits: 1, value: k.toFixed(1) + ' vs ' + c.toFixed(1), unit: '',
          label: 'copies until Spark first dropped the name (11 = never)',
          alt: 'Spark’s descriptions first dropped the kind’s name at copy ' + k.toFixed(1) + ' on average, and the word chair at ' + c.toFixed(1) + '.' },
        q: 'Difference ' + signed(t3.difference.mean, f2) + ' copies ' + ciTxt(t3.difference.ci95, f2) + ', ' + cc.length + ' chains.' }
    ] });
    document.getElementById('hero-qual').textContent = 'Spark’s sentence is the bottleneck: what it doesn’t say can’t survive. Eight starting chairs and two controls, ' +
      'three chains each, one describing and one drawing prompt.';
  }

  // ---------- the chain rows ----------
  var rows = [];

  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  }
  function marked(textIn, kw) {
    var safe = escapeHtml(textIn || '');
    try { return safe.replace(new RegExp('\\b\\w*(?:' + kw + ')\\w*', 'gi'), function (m) { return '<mark>' + m + '</mark>'; }); }
    catch (e) { return safe; }
  }

  function buildRows() {
    var box = document.getElementById('rows');
    box.innerHTML = '';
    rows = D.seeds.map(function (s) {
      var head = h('div', { class: 'tp-row-head' }, [
        h('h3', null, s.label),
        h('span', { class: 'tp-tag' }, s.control ? 'control: not a chair' : 'starting chair'),
        h('span', { class: 'tp-dist' })
      ]);
      var img = h('img', { alt: '', width: 1936, height: 176, loading: 'lazy', decoding: 'async' });
      var dim = h('div', { class: 'tp-dim' });
      var cursor = h('div', { class: 'tp-cursor' + (s.control ? ' is-control' : '') });
      var strip = h('div', { class: 'tp-strip', role: 'img' }, [img, dim, cursor]);
      strip.addEventListener('click', function (e) {
        var r = strip.getBoundingClientRect();
        setGen(Math.max(0, Math.min(N - 1, Math.floor((e.clientX - r.left) / r.width * N))));
      });
      var startFrame = h('div', { class: 'frame' }), nowFrame = h('div', { class: 'frame' });
      var nowCap = h('figcaption');
      var pair = h('div', { class: 'tp-pair', 'aria-hidden': 'true' }, [
        h('figure', null, [startFrame, h('figcaption', null, 'start')]), h('figure', null, [nowFrame, nowCap])]);
      var desc = h('p', { class: 'tp-desc' });
      var status = h('p', { class: 'tp-status tp-note' });
      var row = h('article', { class: 'tp-row', 'aria-label': s.label }, [head, h('div', { class: 'tp-body' }, [pair, strip, desc, status])]);
      box.appendChild(row);
      return { s: s, head: head, img: img, dim: dim, cursor: cursor, strip: strip, startFrame: startFrame, nowFrame: nowFrame,
               nowCap: nowCap, desc: desc, status: status };
    });
  }

  function updateRows() {
    rows.forEach(function (r) {
      var s = r.s, ch = chainOf(s.key, chain);
      if (!ch) return;
      var src = D.sprites[s.key + '_c' + chain];
      if (r.img.getAttribute('src') !== src) r.img.setAttribute('src', src);
      r.strip.setAttribute('aria-label', s.label + ', chain ' + (chain + 1) + ': the starting picture and ten copies, left to right. Showing generation ' + gen + '.');
      r.dim.style.width = (100 * (N - 1 - gen) / N) + '%';
      r.cursor.style.left = (100 * gen / N) + '%';
      ['startFrame', 'nowFrame'].forEach(function (k, i) {
        r[k].style.backgroundImage = 'url(' + src + ')';
        r[k].style.backgroundPosition = (i === 0 ? 0 : gen * 10) + '% 0';
      });
      r.nowCap.textContent = gen === 0 ? 'start' : 'generation ' + gen;
      var d = ch.descriptions[gen];
      r.desc.innerHTML = '<span class="gen">' + (gen === 0 ? 'Spark on the start' : 'Spark on generation ' + gen) + '</span>' +
        (d ? marked(d, s.kind_word) : '<i>missing</i>');
      var dp = ch.d_proto;
      r.head.querySelector('.tp-dist').innerHTML = 'Distance to Muse’s ' + defaultName(s) + ': <b>' + f2(dp[gen]) + '</b>' +
        (gen ? ' <span class="tp-tag">(start ' + f2(dp[0]) + ')</span>' : '');
      var lost = -1;
      for (var g = 0; g < N; g++) { if (ch.kind_word[g] === false) { lost = g; break; } }
      var name = '“' + kindName(s) + '”';
      var st;
      if (ch.kind_word[0] === false) st = 'Spark never said ' + name + ' in this chain’s first description.';
      else if (lost < 0) st = 'Spark said ' + name + ' in every description of this chain.';
      else if (gen < lost) st = 'Spark still says ' + name + '. It drops it at generation ' + lost + '.';
      else st = name + ' was dropped at generation ' + lost + (ch.kind_word.slice(lost).some(function (x) { return x; }) ? ', and came back later.' : '.');
      var lab = ch.labels[gen];
      if (lab) st += ' Shown this picture, Spark picks “' + lab + '”.';
      r.status.textContent = st;
    });
    var ticks = document.getElementById('ticks').children;
    for (var i = 0; i < ticks.length; i++) ticks[i].className = i === gen ? 'on' : '';
    document.getElementById('gen-label').textContent = gen === 0 ? 'The starting pictures (generation 0)' :
      'Generation ' + gen + ': ' + gen + (gen === 1 ? ' copy' : ' copies') + ' after the start';
    var range = document.getElementById('gen');
    range.value = String(gen);
    range.setAttribute('aria-valuetext', gen === 0 ? 'start' : 'generation ' + gen);
  }

  function setGen(g) { gen = g; updateRows(); }

  function stop() {
    if (timer) clearInterval(timer);
    timer = null;
    var b = document.getElementById('play');
    b.setAttribute('aria-pressed', 'false');
    b.querySelector('span').textContent = 'Play';
  }
  function play() {
    var b = document.getElementById('play');
    if (timer) { stop(); return; }
    if (gen >= N - 1) setGen(0);
    b.setAttribute('aria-pressed', 'true');
    b.querySelector('span').textContent = 'Pause';
    timer = setInterval(function () {
      if (gen >= N - 1) { stop(); return; }
      setGen(gen + 1);
    }, reduceMotion ? 1600 : 1100);
  }

  function buildPlayer() {
    var t = document.getElementById('ticks');
    t.innerHTML = '';
    for (var g = 0; g < N; g++) t.appendChild(h('span', null, g === 0 ? 'start' : String(g)));
    var range = document.getElementById('gen');
    range.addEventListener('input', function () { stop(); setGen(+range.value); });
    document.getElementById('play').addEventListener('click', play);
    var cb = document.getElementById('chains');
    cb.innerHTML = '';
    for (var c = 0; c < 3; c++) {
      (function (c) {
        var b = h('button', { type: 'button', role: 'radio', 'aria-checked': c === chain ? 'true' : 'false' }, 'Chain ' + (c + 1));
        b.addEventListener('click', function () {
          chain = c;
          Array.prototype.forEach.call(cb.children, function (x, i) { x.setAttribute('aria-checked', i === c ? 'true' : 'false'); });
          updateRows();
        });
        cb.appendChild(b);
      })(c);
    }
  }

  // ---------- charts: one measure per chart, generations 0-10 on x, 95% CI bands ----------
  function tipper(box) {
    var tip = h('div', { class: 'tp-tip', hidden: true });
    box.appendChild(tip);
    return {
      show: function (evt, html) {
        tip.innerHTML = html;
        tip.hidden = false;
        var r = box.getBoundingClientRect();
        var x = evt.clientX - r.left + 14, y = evt.clientY - r.top + 14;
        if (x + 260 > r.width) x = Math.max(0, evt.clientX - r.left - 272);
        tip.style.left = x + 'px';
        tip.style.top = y + 'px';
      },
      hide: function () { tip.hidden = true; }
    };
  }

  function niceTicks(lo, hi, n) {
    var step = Math.pow(10, Math.floor(Math.log10((hi - lo) / n)));
    [1, 2, 2.5, 5, 10].some(function (m) { if ((hi - lo) / (step * m) <= n) { step *= m; return true; } return false; });
    var out = [];
    for (var v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
    return out;
  }

  /* series: [{name, color, mean[11], ci[11], thin?}] ; refs: [{name, value}] ; opts: {yd, yfmt, ylabel, aria} */
  function lineChart(boxId, series, refs, opts) {
    var box = document.getElementById(boxId);
    box.innerHTML = '';
    var narrow = box.clientWidth < 560;
    var W = narrow ? 420 : 900, H = narrow ? 300 : 340, L = 50, R = narrow ? 16 : 190, T = 14, B = 40;
    var xs = function (g) { return L + (W - L - R) * g / (N - 1); };
    var ys = function (v) { return T + (H - T - B) * (opts.yd[1] - v) / (opts.yd[1] - opts.yd[0]); };
    var s = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': opts.aria }, box);
    var tip = tipper(box);
    niceTicks(opts.yd[0], opts.yd[1], 5).forEach(function (v) {
      svg('line', { x1: L, x2: W - R, y1: ys(v), y2: ys(v), stroke: C.grid }, s);
      text(s, L - 8, ys(v) + 4, opts.yfmt(v), { 'text-anchor': 'end' });
    });
    for (var g = 0; g < N; g++) text(s, xs(g), H - B + 18, g === 0 ? 'start' : String(g), { 'text-anchor': 'middle' });
    text(s, (L + W - R) / 2, H - 4, 'generation (copies after the start)', { 'text-anchor': 'middle', class: 'lbl' });
    refs.forEach(function (r) {
      svg('line', { x1: L, x2: W - R, y1: ys(r.value), y2: ys(r.value), stroke: C.ink2, 'stroke-width': 1 }, s);
      text(s, narrow ? W - R : W - R + 8, narrow ? ys(r.value) - 6 : ys(r.value) + 4, r.name,
           { class: 'lbl', 'text-anchor': narrow ? 'end' : 'start' });
    });
    series.filter(function (x) { return x.thin; }).forEach(function (x) {
      var d = x.mean.map(function (v, i) { return v == null ? '' : (i ? 'L' : 'M') + xs(i) + ' ' + ys(v); }).join('');
      var p = svg('path', { d: d, fill: 'none', stroke: C.seedLine, 'stroke-width': 1.2, opacity: 0.55, 'stroke-linejoin': 'round' }, s);
      p.appendChild(document.createElementNS(SVGNS, 'title')).textContent = x.name;
    });
    var main = series.filter(function (x) { return !x.thin; });
    main.forEach(function (x) {
      if (x.ci) {
        var up = x.ci.map(function (c, i) { return (i ? 'L' : 'M') + xs(i) + ' ' + ys(c[1]); }).join('');
        var dn = x.ci.slice().reverse().map(function (c, j) { return 'L' + xs(N - 1 - j) + ' ' + ys(c[0]); }).join('');
        svg('path', { d: up + dn + 'Z', fill: x.color, opacity: 0.1 }, s);
      }
    });
    var endLabels = [];
    main.forEach(function (x) {
      svg('path', { d: x.mean.map(function (v, i) { return (i ? 'L' : 'M') + xs(i) + ' ' + ys(v); }).join(''), fill: 'none',
                    stroke: x.color, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, s);
      [0, N - 1].forEach(function (i) {
        svg('circle', { cx: xs(i), cy: ys(x.mean[i]), r: 4.5, fill: x.color, stroke: C.surface, 'stroke-width': 2 }, s);
      });
      endLabels.push({ y: ys(x.mean[N - 1]), x: x });
    });
    if (!narrow) {  // direct labels at the line ends, with a leader when they would collide
      endLabels.sort(function (a, b) { return a.y - b.y; });
      var last = -1e9;
      endLabels.forEach(function (e) {
        var y = Math.max(e.y + 4, last + 16);
        last = y;
        if (Math.abs(y - 4 - e.y) > 2) svg('line', { x1: xs(N - 1) + 6, x2: xs(N - 1) + 14, y1: e.y, y2: y - 4, stroke: C.muted }, s);
        text(s, xs(N - 1) + 16, y, e.x.short || e.x.name, { class: 'lbl' });
      });
    }
    // hover: a crosshair at the nearest generation with every main series' value and CI
    var cross = svg('line', { y1: T, y2: H - B, stroke: C.muted, 'stroke-width': 1, visibility: 'hidden' }, s);
    var hit = svg('rect', { x: L - 10, y: T, width: W - L - R + 20, height: H - T - B, fill: 'transparent' }, s);
    hit.addEventListener('mousemove', function (e) {
      var r = s.getBoundingClientRect();
      var px = (e.clientX - r.left) / r.width * W;
      var g = Math.max(0, Math.min(N - 1, Math.round((px - L) / (W - L - R) * (N - 1))));
      cross.setAttribute('x1', xs(g));
      cross.setAttribute('x2', xs(g));
      cross.setAttribute('visibility', 'visible');
      tip.show(e, '<b>' + (g === 0 ? 'Start' : 'Generation ' + g) + '</b>' + main.map(function (x) {
        return '<br>' + x.name + ': ' + opts.yfmt(x.mean[g]) + (x.ci ? ' ' + ciTxt(x.ci[g], opts.yfmt) : '');
      }).join(''));
    });
    hit.addEventListener('mouseleave', function () { cross.setAttribute('visibility', 'hidden'); tip.hide(); });
  }

  function legend(id, items) {
    var el = document.getElementById(id);
    el.innerHTML = '';
    items.forEach(function (it) { el.appendChild(h('span', null, [h('i', { style: 'background:' + it[1] + (it[2] ? ';height:1.5px' : '') }), it[0]])); });
  }

  function table(id, cols, rowsIn, textCols) {  // textCols: no number styling (all columns after the first are numbers otherwise)
    var el = document.getElementById(id);
    el.innerHTML = '';
    var t = h('table');
    var cls = function (i) { return i && !textCols ? 'num' : ''; };
    t.appendChild(h('tr', null, cols.map(function (c, i) { return h('th', { class: cls(i) }, c); })));
    rowsIn.forEach(function (r) { t.appendChild(h('tr', null, r.map(function (v, i) { return h('td', { class: cls(i) }, v); }))); });
    el.appendChild(t);
  }

  function curve(name) { return D.curves[name]; }

  function renderForm() {
    var dp = curve('d_proto'), ref = D.reference;
    var seeds = D.seeds.filter(function (s) { return !s.control; }).map(function (s) {
      return { name: s.label, thin: true, mean: D.per_seed[s.key].d_proto };
    });
    var hi = Math.max.apply(null, seeds.map(function (x) { return Math.max.apply(null, x.mean.filter(function (v) { return v != null; })); }));
    lineChart('form-chart', seeds.concat([{ name: 'Mean of 8 chairs', short: 'mean of 8 chairs', color: C.blue, mean: dp.mean, ci: dp.ci95 }]),
      [{ name: 'Muse’s own default chairs', value: ref.floor.chair }],
      { yd: [0, Math.ceil(hi * 10) / 10], yfmt: f2, aria: 'Distance to Muse’s default chair by generation, for the 8 starting chairs' });
    legend('form-legend', [['Mean of the 8 starting chairs (band: 95% CI)', C.blue], ['One starting chair (mean of its 3 chains)', C.seedLine, true],
      ['Muse’s own default chairs', C.ink2, true]]);
    table('form-table', ['Generation', 'Mean distance', '95% CI'], D.gens.map(function (g) {
      return [g === 0 ? 'start' : String(g), f3(dp.mean[g]), ciTxt(dp.ci95[g], f3)];
    }));
    var t = D.tests.P1_drift_to_form, sp = D.tests.P1_specificity;
    var ctrl = D.seeds.filter(function (s) { return s.control; }).map(function (s) {
      var v = D.per_seed[s.key];
      return 'the ' + s.label + ' ' + f2(v.d_proto[0]) + ' → ' + f2(v.d_proto[N - 1]) + ' from Muse’s ' + defaultName(s);
    }).join(', ');
    document.getElementById('form-note').textContent = 'Change from the start to generation 10: ' + signed(t.change.mean, f3) + ' ' +
      ciTxt(t.change.ci95, f3) + ' (' + (t.supported ? 'closer, as predicted' : 'no clear move toward the default; the prediction is not supported') +
      '). Toward the average of all 35 things Muse draws, the change is ' + signed(sp.change_grand.mean, f3) + ' ' + ciTxt(sp.change_grand.ci95, f3) +
      '. Controls: ' + ctrl + '.';
  }

  function renderConverge() {
    var b = curve('between'), w = curve('within'), ref = D.reference;
    var hi = Math.max(Math.max.apply(null, b.ci95.map(function (c) { return c[1]; })), Math.max.apply(null, w.ci95.map(function (c) { return c[1]; })));
    lineChart('converge-chart', [
      { name: 'Different starting chairs', short: 'different starts', color: C.blue, mean: b.mean, ci: b.ci95 },
      { name: 'Same starting chair', short: 'same start', color: C.orange, mean: w.mean.map(function (v) { return v == null || isNaN(v) ? 0 : v; }),
        ci: w.ci95.map(function (c) { return c[0] == null || isNaN(c[0]) ? [0, 0] : c; }) }],
      [{ name: 'Spread of Muse’s default chairs', value: ref.default_spread.chair }],
      { yd: [0, Math.ceil(hi * 10) / 10], yfmt: f2, aria: 'How far apart chains are, by generation' });
    legend('converge-legend', [['Chains from different starting chairs', C.blue], ['Chains from the same starting chair', C.orange],
      ['Spread of Muse’s 16 default chairs', C.ink2, true]]);
    table('converge-table', ['Generation', 'Different starts', '95% CI', 'Same start', '95% CI'], D.gens.map(function (g) {
      return [g === 0 ? 'start' : String(g), f3(b.mean[g]), ciTxt(b.ci95[g], f3), g ? f3(w.mean[g]) : '0', g ? ciTxt(w.ci95[g], f3) : ''];
    }));
    var t = D.tests.P2_convergence;
    document.getElementById('converge-note').textContent = 'Change in the spread between different starting chairs, start to generation 10: ' +
      signed(t.change.mean, f3) + ' ' + ciTxt(t.change.ci95, f3) + ' (' + (t.supported ? 'they converge, as predicted' : t.change.ci95[0] > 0 ? 'they drift apart: the opposite of the prediction' : 'no convergence; the prediction is not supported') +
      '). At generation 10, chains from different chairs are still ' + signed(t.between_minus_within_g10.mean, f3) + ' ' +
      ciTxt(t.between_minus_within_g10.ci95, f3) + ' farther apart than chains from the same chair.';
  }

  function renderWords() {
    var k = curve('kind_word'), c = curve('category_word'), l = curve('label_kind');
    var series = [{ name: 'Description says “chair”', short: 'says “chair”', color: C.orange, mean: c.mean, ci: c.ci95 },
                  { name: 'Description names the kind', short: 'names the kind', color: C.blue, mean: k.mean, ci: k.ci95 }];
    var hasLabels = l.mean.some(function (v) { return v != null && !isNaN(v); });
    if (hasLabels) series.push({ name: 'Spark picks the kind for the picture', short: 'picture read as the kind', color: C.teal, mean: l.mean, ci: l.ci95 });
    lineChart('words-chart', series, [], { yd: [0, 1], yfmt: pct, aria: 'Share of the 24 chair chains whose description or picture keeps the chair and its kind' });
    legend('words-legend', series.map(function (x) { return [x.name, x.color]; }));
    table('words-table', ['Generation', 'Says “chair”', 'Names the kind', 'Picture read as the kind'], D.gens.map(function (g) {
      return [g === 0 ? 'start' : String(g), pct(c.mean[g]), pct(k.mean[g]), hasLabels ? pct(l.mean[g]) : '–'];
    }));
    var t = D.tests.P3_kind_first;
    document.getElementById('words-note').textContent = 'On average the kind’s name was first missing at description ' + f2(t.first_loss_kind.mean) +
      ' and “chair” at ' + f2(t.first_loss_category.mean) + ' (11 means never). Difference ' + signed(t.difference.mean, f2) + ' ' + ciTxt(t.difference.ci95, f2) +
      ': ' + (t.supported ? 'the kind goes first, as predicted.' : 'the prediction that the kind goes first is not supported.');
    // when each chair lost its name, per chain
    table('loss-table', ['Start', 'Chain 1', 'Chain 2', 'Chain 3', 'Picture read as the kind at 10'], D.seeds.map(function (s) {
      var v = D.per_seed[s.key];
      return [s.label].concat(v.first_loss_kind.map(function (x) {
        return x == null ? '–' : x >= N ? 'kept' : x === 0 ? 'never said' : 'lost at ' + x;
      })).concat([hasLabels ? v.label_kind_g10 + ' of 3' : '–']);
    }), true);
    var ws = document.getElementById('word-shift');
    ws.innerHTML = '';
    function chips(list, title) {
      ws.appendChild(h('p', { class: 'tp-note' }, title));
      ws.appendChild(h('div', { class: 'tp-words' }, list.slice(0, 12).map(function (x) {
        return h('span', null, [x.word, h('small', null, pct(x.start) + ' → ' + pct(x.end))]);
      })));
    }
    chips(D.words.rising, 'More common in the last description than the first (share of 24 chair chains):');
    chips(D.words.falling, 'Less common at the end:');
  }

  function renderPassages() {
    var box = document.getElementById('passages');
    box.innerHTML = '';
    (D.passages || []).forEach(function (p) {
      box.appendChild(h('blockquote', { class: 'tp-quote' }, [p.text, h('cite', null, [p.work + ' ' + (p.book ? p.book + ', ' : '') + p.stephanus +
        ' · ' + p.translation + ' · ', h('a', { href: p.source_url }, 'Project Gutenberg')])]));
    });
  }

  function renderAnswer() {
    var ul = document.getElementById('answer-list');
    ul.innerHTML = '';
    var t1 = D.tests.P1_drift_to_form, t2 = D.tests.P2_convergence, t3 = D.tests.P3_kind_first;
    var cc = D.chains.filter(function (c) { return !seedOf(c.seed).control; });
    var away = cc.filter(function (c) { return c.d_proto[N - 1] > c.d_proto[0]; }).length;
    // chains that end within twice the default chairs' own distance to their average (written for the high chair)
    var formEnd = cc.filter(function (c) { return c.seed === 'high_chair' && c.d_proto[N - 1] < 2 * D.reference.floor.chair; });
    var change = t1.change.ci95[1] < 0 ? 'closer, as predicted' : t1.change.ci95[0] > 0 ? 'farther' : 'no clear change';
    ul.appendChild(h('li', null, [h('b', null, t1.supported ? 'The chains drift toward the textbook chair. ' : 'No pull toward the textbook chair. '),
      'Over ten copies, the 8 chairs’ distance from Muse’s default chair went from ' + f2(t1.g0) + ' to ' + f2(t1.g10) + ' (change ' +
      signed(t1.change.mean, f2) + ', 95% CI ' + ciTxt(t1.change.ci95, f2) + ': ' + change + '). ' + away + ' of ' + cc.length +
      ' chains ended farther from it than they started. Muse’s own default chairs sit at ' + f2(D.reference.floor.chair) + '.']));
    ul.appendChild(h('li', null, [h('b', null, t2.supported ? 'Different chairs end up more alike. ' :
      t2.change.ci95[0] > 0 ? 'Different chairs drift apart instead. ' : 'Different chairs don’t end up alike. '),
      'The distance between chains from different starting chairs went from ' + f2(t2.g0) + ' to ' + f2(t2.g10) + ' (change ' +
      signed(t2.change.mean, f2) + ', ' + ciTxt(t2.change.ci95, f2) + '). Even the three chains of the same chair, which start as one picture, end ' +
      f2(t2.within_g10.mean) + ' apart, nearly three times the spread of Muse’s default chairs.']));
    ul.appendChild(h('li', null, [h('b', null, t3.supported ? 'Names go first. ' : 'Names don’t reliably go first. '),
      'Spark’s descriptions dropped the kind’s name (rocking, beanbag, folding …) at description ' + f2(t3.first_loss_kind.mean) +
      ' on average, and “chair” at ' + f2(t3.first_loss_category.mean) + ' (11 = never; difference ' + signed(t3.difference.mean, f2) + ', ' +
      ciTxt(t3.difference.ci95, f2) + '). No first description called the throne a throne: Spark saw “an armchair with … crown-like points”.']));
    if (formEnd.length) {
      ul.appendChild(h('li', null, [h('b', null, 'Only the high chair fell into the Form. '),
        'In ' + formEnd.length + ' of its 3 chains, the tray that Spark described didn’t make it into Muse Image’s first redraw. From then on Spark described a simple chair, and within a few copies every picture was Muse’s textbook slat-back chair, where it stayed (ending at ' +
        formEnd.map(function (c) { return f2(c.d_proto[N - 1]); }).join(' and ') + '). Without their names, the other chairs didn’t fall back to it: they wandered off (a beanbag became a croissant, then a fan-shaped window) or grew one feature (the throne’s crown on a pole).']));
    }
  }

  function renderCredits() {
    var c = D.cost;
    document.getElementById('credits').textContent = 'Models: Meta Muse Spark and Muse Image; similarity: Meta DINOv2 (Apache 2.0). ' +
      c.images + ' pictures and ' + (c.descriptions + c.labels) + ' Spark calls cost $' + c.total_usd.toFixed(2) + '. Plato in Benjamin Jowett’s public-domain translation. ' +
      'References: Bartlett, F. C. (1932), Remembering, Cambridge University Press; Carbon, C.-C., & Albrecht, S. (2012), QJEP 65(11), 2258–2270; ' +
      'Kirby, S., Cornish, H., & Smith, K. (2008), PNAS 105(31), 10681–10686; Griffiths, T. L., & Kalish, M. L. (2007), Cognitive Science 31(3), 441–480; ' +
      'Xu, J., & Griffiths, T. L. (2010), Cognitive Psychology 60(2), 107–126; Shumailov, I., et al. (2024), Nature 631, 755–759.';
  }

  function renderCharts() { renderForm(); renderConverge(); renderWords(); }

  function init() {
    var q = /(?:^|[#&])gen=(\d+)/.exec(location.hash);
    if (q) gen = Math.min(N - 1, +q[1]);
    var qc = /(?:^|[#&])chain=([123])/.exec(location.hash);
    if (qc) chain = +qc[1] - 1;
    renderHero();  // the first screen first
    buildPlayer();
    buildRows();
    updateRows();
    renderAnswer();
    renderCharts();
    renderPassages();
    renderCredits();
    var lastW = window.innerWidth;
    window.addEventListener('resize', function () {
      if (Math.abs(window.innerWidth - lastW) < 40) return;
      lastW = window.innerWidth;
      renderCharts();
    });
  }

  TOT.api('/api/plato/telephone').then(function (data) { D = data; init(); }).catch(function (e) {
    var el = document.getElementById('load-error');
    el.textContent = 'The results didn’t load: ' + (e && e.message ? e.message : e);
    el.hidden = false;
  });
})();
