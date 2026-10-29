/* Plato's Forms (/plato/forms): the Platonic clock and Plato's bed and table.
   Everything comes from /api/plato/forms (derived statistics only) and static images; no API calls. */
(function () {
  'use strict';
  var T = window.TOT;
  var IMG = '/static/img/plato_forms/';
  // colours are the site's tokens (app.css), so a theme switch recolours the charts
  var BLUE = 'var(--blue)', ORANGE = 'var(--orange)', TEAL = 'var(--teal)', GRID = 'var(--line)', AXIS = 'var(--line-3)', INK = 'var(--ink)', MUTED = 'var(--muted)';
  var HALO = 'var(--chart-halo)';
  var NS = 'http://www.w3.org/2000/svg';
  var S = { d: null, ai: 'muse', asked: 'doodle', dial: 'doodle', k: 'bed', who: 'ai' };
  var NAME = { muse: 'Muse Image', sdxl: 'Stable Diffusion XL', people: 'People' };
  var COLOR = { muse: BLUE, sdxl: TEAL, people: ORANGE };

  function $(id) { return document.getElementById(id); }
  function pct(x) { return Math.round(x * 100); }
  function f2(x) { return Number(x).toFixed(2); }
  function s(tag, attrs, kids) {
    var el = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) el.setAttribute(k, attrs[k]); });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c == null) return;
      el.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return el;
  }
  function html(el, markup) { el.innerHTML = markup; }

  // ---- time arithmetic (the same as metalesionlab/plato_forms.py) ----
  function parseT(t) { var p = String(t).split(':'); return [Number(p[0]), Number(p[1])]; }
  function marks(hm) { return [((hm[0] % 12) + hm[1] / 60) % 12, (hm[1] / 5) % 12]; }
  function fromHands(hour, minute) {
    var m = Math.round(5 * (minute % 12)) % 60;
    var h = ((Math.round((hour % 12) - m / 60) % 12) + 12) % 12;
    return [h || 12, m];
  }
  function dialMin(hm) { return ((hm[0] % 12) * 60 + hm[1]) % 720; }
  function dist(a, b) { var d = Math.abs(dialMin(a) - dialMin(b)) % 720; return Math.min(d, 720 - d); }
  function swap(hm) { var k = marks(hm); return fromHands(k[1], k[0]); }
  function isTenTen(t) { var hm = parseT(t); return dist(hm, [10, 10]) <= 10 || dist(swap(hm), [10, 10]) <= 10; }

  // ---- tooltip ----
  var tip = $('tip');
  function showTip(evt, markup) {
    html(tip, markup);
    tip.hidden = false;
    var x = evt.pageX, y = evt.pageY;
    var w = tip.offsetWidth;
    tip.style.left = Math.max(8, Math.min(x + 14, window.scrollX + document.documentElement.clientWidth - w - 8)) + 'px';
    tip.style.top = (y + 14) + 'px';
  }
  function hideTip() { tip.hidden = true; }
  function hoverable(el, markup) {
    el.addEventListener('mousemove', function (e) { showTip(e, markup); });
    el.addEventListener('mouseleave', hideTip);
    el.addEventListener('click', function (e) { showTip(e, markup); e.stopPropagation(); });
  }
  document.addEventListener('click', hideTip);

  function press(seg, attr, value) {
    [].forEach.call(seg.querySelectorAll('button'), function (b) { b.setAttribute('aria-pressed', String(b.getAttribute(attr) === value)); });
  }
  function swapImg(img, src, alt) {
    if (img.getAttribute('src') === src) return;
    img.classList.add('swapping');
    var pre = new Image();
    pre.onload = pre.onerror = function () { img.src = src; if (alt != null) img.alt = alt; img.classList.remove('swapping'); };
    pre.src = src;
  }

  // ---- hero ----
  var WALL_ALT = {
    muse: 'Sixteen clock doodles by Muse Image, no time asked. Nearly all show the same time: the hands make a V pointing at the 10 and the 2.',
    sdxl: 'Sixteen clock doodles by Stable Diffusion XL, no time asked: ornate faces with Roman numerals and hands at many different times.'
  };
  function g(name) { return S.d.clock.groups[name]; }
  function eye(name) { return (S.d.clock.byeye_no_time || {})[name]; }
  function eyeCount(e) { return e.sure === e.max ? String(e.sure) : e.sure + '–' + e.max; }
  // people's favourite: the hands on the 12 and the 3 (3:00, or 12:15 with the hands the other way round)
  function twelveThree(grp) {
    return (grp.times || []).reduce(function (n, tc) {
      var hm = parseT(tc[0]);
      return n + (dist(hm, [3, 0]) <= 5 || dist(swap(hm), [3, 0]) <= 5 ? tc[1] : 0);
    }, 0);
  }

  function hero() {
    var wall = g(S.ai + '_doodle_default'), e = eye(S.ai + '_doodle_default');
    var who = NAME[S.ai] + (S.ai === 'sdxl' ? ', an open image AI from Stability AI,' : ',');
    if (e) {
      $('wall-ai-stat').textContent = eyeCount(e) + ' of ' + e.n + ' show 10:10';
      $('wall-ai-sub').textContent = who + ' asked for “a clock” with no time. Counted by eye (our automatic clock reader counted ' + wall.ten_ten.k + ').';
    } else {
      $('wall-ai-stat').textContent = wall.ten_ten.k + ' of ' + wall.ten_ten.n + ' show about 10:10';
      $('wall-ai-sub').textContent = who + ' asked for “a clock” with no time.';
    }
    swapImg($('wall-ai'), IMG + 'wall_' + S.ai + '.webp', WALL_ALT[S.ai]);
  }

  function heroStatic() {
    var p = g('people');
    var l = twelveThree(p);
    $('wall-people-stat').textContent = p.ten_ten.k + ' of ' + p.n + ' show about 10:10';
    html($('wall-people-sub'), '(' + pct(p.ten_ten.share) + '%). Their favourite: hands on the 12 and the 3, as in 3:00 (' + l + ' of ' + p.n +
      '). 16 of their drawings shown. <span class="credit">Google Quick, Draw! (CC BY 4.0)</span>');
    var lead = window.FirstLook.forms(S.d);
    window.FirstLook.render($('hero-stats'), lead);
    $('hero-note').textContent = lead.note;
  }

  // ---- asked: time asked against time drawn ----
  function hour(t) { var hm = parseT(t); return (hm[0] % 12) + hm[1] / 60; }

  function askedChart() {
    var box = $('asked-chart');
    box.innerHTML = '';
    var W = 560, H = 380, m = { l: 46, r: 12, t: 12, b: 42 };
    var x = function (v) { return m.l + (v + 0.5) / 13 * (W - m.l - m.r); };
    var y = function (v) { return H - m.b - (v + 1.2) / 13.5 * (H - m.t - m.b); };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'Time asked for against the time drawn, for Muse Image and Stable Diffusion XL' });
    svg.appendChild(s('rect', { x: m.l, y: y(10 + 1 / 3), width: W - m.l - m.r, height: y(10) - y(10 + 1 / 3), fill: 'var(--pf-ten)', opacity: 0.7 }));
    svg.appendChild(s('text', { x: W - m.r - 4, y: y(10 + 1 / 3) - 4, 'text-anchor': 'end', 'font-size': 11, fill: 'var(--amber-ink)' }, 'about 10:10'));
    [0, 3, 6, 9, 12].forEach(function (v) {
      var lab = String(v === 0 ? 12 : v);
      svg.appendChild(s('line', { x1: x(v), x2: x(v), y1: m.t, y2: H - m.b, stroke: GRID }));
      svg.appendChild(s('line', { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), stroke: GRID }));
      svg.appendChild(s('text', { x: x(v), y: H - m.b + 16, 'text-anchor': 'middle', 'font-size': 12, fill: MUTED }, lab));
      svg.appendChild(s('text', { x: m.l - 8, y: y(v) + 4, 'text-anchor': 'end', 'font-size': 12, fill: MUTED }, lab));
    });
    svg.appendChild(s('line', { x1: x(0), y1: y(0), x2: x(12), y2: y(12), stroke: AXIS, 'stroke-dasharray': '4 4' }));
    svg.appendChild(s('text', { x: m.l + (W - m.l - m.r) / 2, y: H - 6, 'text-anchor': 'middle', 'font-size': 12, fill: INK }, 'Time asked for (hour) →'));
    svg.appendChild(s('text', { x: 12, y: m.t + (H - m.t - m.b) / 2, 'text-anchor': 'middle', 'font-size': 12, fill: INK,
      transform: 'rotate(-90 12 ' + (m.t + (H - m.t - m.b) / 2) + ')' }, 'Time drawn (hour) →'));
    svg.appendChild(s('text', { x: m.l - 8, y: y(-0.7) + 4, 'text-anchor': 'end', 'font-size': 11, fill: MUTED }, 'none'));
    var seed = 1;
    function rnd() { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }
    ['muse', 'sdxl'].forEach(function (gen, gi) {
      var grp = g(gen + '_' + S.asked + '_asked');
      if (!grp) return;
      var off = gi ? 0.17 : -0.17;
      (grp.asked_vs_read || []).forEach(function (row) {
        var xv = hour(row[0]), yv = hour(row[1]), n = row[2];
        var ok = dist(parseT(row[1]), parseT(row[0])) <= S.d.clock.correct_within_min;
        for (var i = 0; i < n; i++) {
          var c = s('circle', { cx: x(xv + off + (rnd() - 0.5) * 0.22), cy: y(yv) + (rnd() - 0.5) * 6, r: 5, fill: COLOR[gen],
            'fill-opacity': 0.8, stroke: HALO, 'stroke-width': 1.2 });
          hoverable(c, '<b>' + NAME[gen] + '</b><br>asked ' + row[0] + ', drew ' + row[1] + '<br>' + n + ' of ' +
            grp.per_time[row[0]].n + ' pictures' + (ok ? ' · right time' : '') + (isTenTen(row[1]) ? ' · about 10:10' : ''));
          svg.appendChild(c);
        }
      });
      Object.keys(grp.asked_no_time || {}).forEach(function (t) {
        for (var i = 0; i < grp.asked_no_time[t]; i++) {
          var c = s('path', { d: 'M-4,-4L4,4M-4,4L4,-4', stroke: COLOR[gen], 'stroke-width': 2,
            transform: 'translate(' + x(hour(t) + off + (rnd() - 0.5) * 0.22) + ',' + y(-0.7) + ')' });
          hoverable(c, '<b>' + NAME[gen] + '</b><br>asked ' + t + ': no hands or unreadable');
          svg.appendChild(c);
        }
      });
    });
    box.appendChild(svg);
    html($('asked-legend'), '<span><i style="background:' + BLUE + '"></i>Muse Image</span><span><i style="background:' + TEAL +
      '"></i>Stable Diffusion XL</span><span>× no hands or unreadable</span>');
  }

  function askedFacts() {
    var m = g('muse_doodle_asked'), x = g('sdxl_doodle_asked'), mp = g('muse_photo_asked'), xp = g('sdxl_photo_asked');
    var ci = function (c) { return c ? ' (probably between ' + pct(c[0]) + '% and ' + pct(c[1]) + '%)' : ''; };
    var out = [];
    if (m) {
      out.push('<div class="pf-fact muse"><b>' + m.ten_ten.k + ' of ' + m.n + '</b><span>of Muse Image’s doodles with a time asked for show 10:10.</span></div>');
      out.push('<div class="pf-fact muse"><b>' + pct(m.minute_correct) + '%</b><span>have the minute hand right. With the hour hand too, ' +
        pct(m.accuracy) + '% are right to within 5 minutes' + ci(m.accuracy_ci95_cluster) + ', and ' + pct(m.accuracy_hour_slack) +
        '% if the hour may be one off. The hour hand often sits a number too far, as in 7:30 for 6:30.</span></div>');
    }
    if (x) out.push('<div class="pf-fact sdxl"><b>' + pct(x.accuracy) + '%</b><span>of Stable Diffusion XL’s doodles show the time asked for' + ci(x.accuracy_ci95_cluster) +
      '. ' + pct(x.ten_ten.share) + '% show 10:10 instead' + (xp ? ', and so do ' + pct(xp.ten_ten.share) + '% of its photos' : '') + '.</span></div>');
    html($('asked-facts'), out.join(''));
    html($('asked-lede'), 'So for Muse Image, 10:10 is a habit, not a limit. Asked for 3:00 or 7:50, it drew 3:00 or 7:50, and it never drew 10:10. ' +
      (mp ? 'Its realistic photos were the same: ' + pct(mp.accuracy) + '% right to within 5 minutes, ' + mp.ten_ten.k + ' of ' + mp.n + ' at 10:10. ' : '') +
      (x ? 'Stable Diffusion XL, an open image AI from Stability AI, is different: it mostly ignored the time asked for and often fell back on 10:10, as others have found with image AIs.' : ''));
  }

  // ---- dials: every read time as a pair of hands ----
  function dial(name, label, gen) {
    var grp = g(name);
    var fig = document.createElement('figure');
    fig.className = 'pf-dial';
    if (!grp) { fig.classList.add('empty'); html(fig, '<h3>' + label + '</h3><p>Not drawn in this style.</p>'); return fig; }
    var R = 100, C = 120;
    var svg = s('svg', { viewBox: '0 0 240 240', role: 'img', 'aria-label': label + ': every clock’s hands on one dial' });
    svg.appendChild(s('circle', { cx: C, cy: C, r: R, fill: HALO, stroke: AXIS, 'stroke-width': 1.5 }));
    for (var k = 0; k < 60; k++) {
      var a = 2 * Math.PI * k / 60, r0 = k % 5 ? 0.95 : 0.89;
      svg.appendChild(s('line', { x1: C + r0 * R * Math.sin(a), y1: C - r0 * R * Math.cos(a), x2: C + R * Math.sin(a), y2: C - R * Math.cos(a),
        stroke: AXIS, 'stroke-width': k % 5 ? 0.6 : 1.4 }));
    }
    [12, 3, 6, 9].forEach(function (num) {
      var a = 2 * Math.PI * (num % 12) / 12;
      svg.appendChild(s('text', { x: C + 0.77 * R * Math.sin(a), y: C - 0.77 * R * Math.cos(a) + 4, 'text-anchor': 'middle', 'font-size': 12, fill: MUTED }, String(num)));
    });
    var times = (grp.times || []).slice().sort(function (p, q) { return p[1] - q[1]; });
    var top = times.length ? times[times.length - 1][1] : 1;
    times.forEach(function (tc) {
      var mk = marks(parseT(tc[0])), c = tc[1];
      var op = Math.min(1, 0.14 + 0.86 * Math.pow(c / top, 0.8)), w = 1.5 + 16 * c / grp.n;
      var gEl = s('g', {});
      [[mk[0], 0.5], [mk[1], 0.8]].forEach(function (hl) {
        var a = 2 * Math.PI * hl[0] / 12;
        gEl.appendChild(s('line', { class: 'hand', x1: C, y1: C, x2: C + hl[1] * R * Math.sin(a), y2: C - hl[1] * R * Math.cos(a),
          stroke: COLOR[gen], 'stroke-opacity': op, 'stroke-width': w, 'stroke-linecap': 'round' }));
      });
      // a wider invisible line makes thin hands easy to hover
      [[mk[0], 0.5], [mk[1], 0.8]].forEach(function (hl) {
        var a = 2 * Math.PI * hl[0] / 12;
        gEl.appendChild(s('line', { x1: C, y1: C, x2: C + hl[1] * R * Math.sin(a), y2: C - hl[1] * R * Math.cos(a), stroke: 'transparent', 'stroke-width': Math.max(w, 10) }));
      });
      hoverable(gEl, '<b>' + tc[0] + '</b><br>' + c + ' of ' + grp.n + ' clocks' + (isTenTen(tc[0]) ? ' · about 10:10' : ''));
      svg.appendChild(gEl);
    });
    svg.appendChild(s('circle', { cx: C, cy: C, r: 3.5, fill: INK }));
    fig.appendChild(svg);
    var none = (grp.status.no_hands || 0) + (grp.status.unreadable || 0) + (grp.status.unparsed || 0);
    var common = (grp.times || []).length && grp.times[0][1] > 1
      ? 'Most common: ' + grp.times.slice(0, 3).filter(function (tc) { return tc[1] > 1; }).map(function (tc) { return tc[0] + ' (' + tc[1] + ')'; }).join(', ')
      : 'No time appears twice.';
    var cap = document.createElement('figcaption');
    var e = eye(name);
    html(cap, '<h3>' + label + '</h3><p><b>' + pct(grp.ten_ten.share) + '%</b> about 10:10 (' + grp.ten_ten.k + ' of ' + grp.n + ')' +
      (e ? '; by eye ' + eyeCount(e) + ' of ' + e.n : '') + (none ? '; ' + none + ' with no hands or unreadable' : '') +
      '</p><p class="top">' + common + '</p>');
    fig.appendChild(cap);
    return fig;
  }

  function dials() {
    var box = $('dials-box');
    box.innerHTML = '';
    box.appendChild(dial('muse_' + S.dial + '_default', 'Muse Image', 'muse'));
    box.appendChild(dial('sdxl_' + S.dial + '_default', 'Stable Diffusion XL', 'sdxl'));
    box.appendChild(dial('people', S.dial === 'photo' ? 'People (drawings)' : 'People', 'people'));
  }

  // ---- bed and table ----
  var BT_ALT = {
    bed: { ai: 'Sixteen bed doodles by Muse Image.', people: 'Sixteen beds drawn by people in 20 seconds.' },
    table: { ai: 'Sixteen table doodles by Muse Image.', people: 'Sixteen tables drawn by people in 20 seconds.' }
  };
  function bedTable() {
    var it = S.d.concepts.items[S.k];
    if (!it) return;
    swapImg($('bt-img'), IMG + 'grid_' + S.k + '_' + S.who + '.webp', (S.d.concepts.alt && S.d.concepts.alt[S.k] && S.d.concepts.alt[S.k][S.who]) || BT_ALT[S.k][S.who]);
    $('bt-cap').textContent = S.who === 'ai' ? '16 doodles by Meta’s Muse Image, each from the same request: “a ' + S.k + '”.'
      : '16 of 200 drawings by people, at random. Google Quick, Draw! (CC BY 4.0).';
    var idx = it.homogenization_index, rk = it.ranks_among_core.homogenization_index;
    var less = Math.round((1 - idx) * 100);
    html($('bt-stat'), '<span class="num">' + (less > 0 ? less + '%' : '×' + f2(idx)) + '</span><p>' +
      (less > 0 ? 'Muse Image’s ' + S.k + 's are ' + less + '% less varied than people’s.' : 'Muse Image’s ' + S.k + 's vary as much as people’s.') +
      '</p><p class="sub">How different the drawings are from one another (we call this spread): ' + f2(it.ai_spread) + ' for Muse Image, ' + f2(it.human_spread) +
      ' for people. Muse Image’s spread is ' + f2(idx) + ' of people’s (probably between ' + f2(it.homogenization_index_ci95[0]) + ' and ' +
      f2(it.homogenization_index_ci95[1]) + ').</p>');
    var c = it.conditions || {}, facts = [];
    facts.push('<div class="pf-fact muse"><b>' + ordinal(rk.rank) + ' of ' + rk.of + '</b><span>Added to the 35 everyday things of the main Plato’s Chair test, the ' + S.k +
      ' ranks ' + ordinal(rk.rank) + ' (1st = the thing Muse Image draws most alike, compared with people). The chair is ' +
      ordinal(S.d.concepts.core_reference.chair_index_rank) + '; the umbrella is 1st. The ranking comes from one picture-comparing AI (DINOv2): with others ' +
      'the order shifts, while the overall result holds.</span></div>');
    if (c.any) facts.push('<div class="pf-fact muse"><b>×' + f2(c.any.ratio_vs_default) + '</b><span>Asking for “any kind of ' + S.k + '” adds no clear variety: ' +
      f2(c.any.ratio_vs_default) + ' times as varied as with our plain request, “a ' + S.k + '” (probably between ' + f2(c.any.ratio_vs_default_ci95[0]) + ' and ' +
      f2(c.any.ratio_vs_default_ci95[1]) + ').</span></div>');
    if (c.listed) facts.push('<div class="pf-fact muse"><b>' + f2(c.listed.ratio_vs_people) + '×</b><span>as varied as people’s, when Meta’s chat AI, Muse Spark, listed 16 kinds of ' +
      S.k + ' and Muse Image drew one of each.</span></div>');
    if (c.sdxl_default) facts.push('<div class="pf-fact sdxl"><b>' + f2(c.sdxl_default.ratio_vs_people) + '×</b><span>as varied as people’s: Stable Diffusion XL, an open image AI, from our plain request.</span></div>');
    html($('bt-facts'), facts.join(''));
    if (it.listed_kinds) {
      $('bt-kinds').hidden = false;
      $('bt-kinds-h').textContent = 'Asked for 16 named kinds of ' + S.k + ', it draws them all';
      swapImg($('bt-kinds-img'), IMG + 'kinds_' + S.k + '_ai.webp', 'Sixteen doodles by Muse Image, one of each kind of ' + S.k + ' Muse Spark listed: ' + it.listed_kinds.join(', ') + '.');
      $('bt-kinds-cap').textContent = 'The kinds Muse Spark listed, in order: ' + it.listed_kinds.join(', ') + '.';
    }
  }
  function ordinal(n) { var v = n % 100; return n + (v >= 11 && v <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][n % 10] || 'th'); }

  function rankChart() {
    var box = $('rank-chart');
    var rows = S.d.concepts.core_concepts.map(function (c) { return { label: c.label, v: c.index, ci: c.index_ci95, isNew: false }; });
    Object.keys(S.d.concepts.items).forEach(function (k) {
      var it = S.d.concepts.items[k];
      rows.push({ label: it.label, v: it.homogenization_index, ci: it.homogenization_index_ci95, isNew: true });
    });
    rows.sort(function (a, b) { return a.v - b.v; });
    var W = 640, rowH = 15, m = { l: 92, r: 16, t: 18, b: 34 }, H = m.t + m.b + rows.length * rowH;
    var hi = Math.max(1.3, Math.max.apply(null, rows.map(function (r) { return r.ci[1]; })) + 0.05);
    var x = function (v) { return m.l + v / hi * (W - m.l - m.r); };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'The bed and the table among the 35 things, ranked by how alike Muse Image draws them compared with people' });
    [0, 0.5, 1].forEach(function (t) {
      svg.appendChild(s('line', { x1: x(t), x2: x(t), y1: m.t - 6, y2: H - m.b + 4, stroke: t === 1 ? 'var(--faint)' : GRID }));
      svg.appendChild(s('text', { x: x(t), y: H - m.b + 18, 'text-anchor': 'middle', 'font-size': 12, fill: MUTED }, String(t)));
    });
    svg.appendChild(s('text', { x: x(1) + 5, y: m.t - 6, 'font-size': 11, fill: MUTED }, 'as varied as people'));
    svg.appendChild(s('text', { x: m.l + (W - m.l - m.r) / 2, y: H - 2, 'text-anchor': 'middle', 'font-size': 12, fill: INK }, 'Muse Image’s spread ÷ people’s (1 = just as varied)'));
    rows.forEach(function (r, i) {
      var y = m.t + i * rowH + rowH / 2, em = r.isNew || r.label === 'chair';
      var gEl = s('g', {});
      gEl.appendChild(s('rect', { x: 0, y: y - rowH / 2, width: W, height: rowH, fill: r.isNew ? 'var(--amber-soft)' : 'transparent' }));
      gEl.appendChild(s('line', { x1: x(r.ci[0]), x2: x(Math.min(r.ci[1], hi)), y1: y, y2: y, stroke: r.isNew ? INK : 'var(--blue-mid)', 'stroke-width': r.isNew ? 2 : 1.5 }));
      gEl.appendChild(s('circle', { cx: x(r.v), cy: y, r: r.isNew ? 5.5 : 4, fill: r.isNew ? INK : BLUE, stroke: HALO, 'stroke-width': 1.5 }));
      gEl.appendChild(s('text', { x: m.l - 8, y: y + 4, 'text-anchor': 'end', 'font-size': em ? 12 : 11, 'font-weight': em ? 700 : 400, fill: em ? INK : MUTED }, r.label));
      hoverable(gEl, '<b>' + r.label + '</b>' + (r.isNew ? ' (Plato’s example)' : '') + '<br>Muse Image ÷ people ' + f2(r.v) + ' (likely range ' + f2(r.ci[0]) + '–' + f2(r.ci[1]) + ')<br>' + (i + 1) + ' of ' + rows.length + ', most alike first');
      svg.appendChild(gEl);
    });
    box.innerHTML = '';
    box.appendChild(svg);
  }

  // ---- method lines ----
  function method() {
    var v = S.d.clock.validation, sp = S.d.clock.spotcheck;
    if (v && v.within5) {
      $('val-line').textContent = 'it read ' + v.within5.k + ' of ' + v.within5.n + ' within 5 minutes, found all ' + v.no_hands_found.n +
        ' clocks with no hands, and never called a non-10:10 clock 10:10 (' + v.false_ten_ten.k + ' of ' + v.false_ten_ten.n + ').';
    }
    if (sp && sp.n_scored) {
      $('spot-line').textContent = 'our reading agreed with it on ' + sp.agree + ' of ' + sp.n_scored + ' clocks (within 5 minutes, or both “no hands”)' +
        (sp.unclear_by_eye ? '; ' + sp.unclear_by_eye + ' were too unclear to read by eye.' : '.');
    } else {
      $('spot-line').textContent = 'see the write-up.';
    }
    var p = S.d.clock.predictions || {};
    var held = Object.keys(p).filter(function (k) { return p[k]; }).length;
    $('pred-line').textContent = held + ' of ' + Object.keys(p).length + ' clock predictions held. We were wrong that Muse Image ignores the time asked for ' +
      '(it doesn’t), and that Stable Diffusion XL’s plain doodles would show 10:10 clearly more often than chance (its photos do). ' +
      'The four bed-and-table predictions held.';
  }

  function wire() {
    $('ai-seg').addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      S.ai = b.getAttribute('data-ai'); press($('ai-seg'), 'data-ai', S.ai); hero();
    });
    $('asked-seg').addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      S.asked = b.getAttribute('data-g'); press($('asked-seg'), 'data-g', S.asked); askedChart();
    });
    $('dial-seg').addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      S.dial = b.getAttribute('data-style'); press($('dial-seg'), 'data-style', S.dial); dials();
    });
    $('bt-seg').addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      S.k = b.getAttribute('data-k'); press($('bt-seg'), 'data-k', S.k); bedTable();
    });
    $('who-seg').addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      S.who = b.getAttribute('data-who'); press($('who-seg'), 'data-who', S.who); bedTable();
    });
  }

  T.api('/api/plato/forms').then(function (d) {
    S.d = d;
    heroStatic(); hero(); askedChart(); askedFacts(); dials(); bedTable(); rankChart(); method(); wire();
  }).catch(function (err) {
    var el = $('load-error');
    el.textContent = 'Could not load the results: ' + err.message;
    el.hidden = false;
  });
})();
