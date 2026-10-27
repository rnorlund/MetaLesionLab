/* Plato's Chair: the hero toggle, the 35-thing chart, six languages, inside Glimmer, and the second model.
   Everything comes from /api/plato (statistics only) and static figures; no API calls. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var IMG = '/static/img/plato/';
  var BLUE = '#1D4ED8', BLUE_SOFT = '#93C5FD', ORANGE = '#C2410C', TEAL = '#0D9488', GRID = '#E5E7EB', AXIS = '#9CA3AF';
  var NS = 'http://www.w3.org/2000/svg';
  var S = { data: null, concept: 'chair', who: 'ai', lang: 'chair' };
  var readyResolve;
  var ready = new Promise(function (r) { readyResolve = r; });

  // Stat-line nouns, and alt text that says what each grid shows.
  var NOUN = { chair: 'chairs', boat: 'sailboats', face: 'faces', person: 'yoga figures' };
  var ALT = {
    chair: { ai: 'Sixteen chair doodles by Muse Image: nearly the same wooden dining chair with a slatted back, in the same three-quarter view, every time.',
             people: 'Sixteen chairs drawn by people in 20 seconds: side views, front views, stools and boxy outlines, each one different.' },
    boat: { ai: 'Sixteen sailboat doodles by Muse Image: the same hull with one or two triangular sails and a pennant, many with little waves.',
            people: 'Sixteen sailboats drawn by people: flags on sticks, single lines, rounded and flat hulls, in many shapes.' },
    face: { ai: 'Sixteen face doodles by Muse Image: round smiling faces with dot eyes and scribbled hair, all very similar.',
            people: 'Sixteen faces drawn by people: ovals and squares, open and closed mouths, glasses, tongues and different eyes.' },
    person: { ai: 'Twelve doodles by Muse Image of a person doing yoga: almost all the same cartoon woman in tree pose or lotus pose.',
              people: 'Twelve yoga drawings by people: stick figures in many poses, some with mats, some barely recognisable.' }
  };

  function $(id) { return document.getElementById(id); }
  function f2(x) { return Number(x).toFixed(2); }
  function pct(x) { return Math.round(x * 100); }
  function listAnd(a) { return a.length < 2 ? a.join('') : a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1]; }
  function ci(c) { return c ? f2(c[0]) + '–' + f2(c[1]) : '–'; }
  function minus(x) { return String(x).replace(/-/g, '−'); }
  function s(tag, attrs, kids) {
    var el = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) el.setAttribute(k, attrs[k]); });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c == null) return;
      el.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return el;
  }
  function heroConcept(key) { return (S.data.hero || []).filter(function (c) { return c.key === key; })[0]; }

  // --- tooltips ------------------------------------------------------------------------------
  function tipFor(wrap) {
    var tip = wrap.querySelector('.pc-tip');
    if (!tip) { tip = h('div', { class: 'pc-tip', role: 'presentation' }); tip.hidden = true; wrap.appendChild(tip); }
    return tip;
  }
  function showTip(wrap, evt, lines) {
    var tip = tipFor(wrap);
    tip.innerHTML = '';
    lines.forEach(function (l, i) { tip.appendChild(i === 0 ? h('b', { text: l }) : h('div', { text: l })); });
    tip.hidden = false;
    var r = wrap.getBoundingClientRect(), x = evt.clientX - r.left, y = evt.clientY - r.top;
    var left = x + 14, top = y + 12;
    if (left + tip.offsetWidth > r.width) left = Math.max(0, x - tip.offsetWidth - 14);
    if (top + tip.offsetHeight > r.height) top = Math.max(0, y - tip.offsetHeight - 12);
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
  }
  function hideTip(wrap) { var tip = wrap.querySelector('.pc-tip'); if (tip) tip.hidden = true; }

  // --- hero ----------------------------------------------------------------------------------
  function setWho(who) {
    if (who !== 'ai' && who !== 'people') return;
    S.who = who;
    renderHero();
  }
  function setConcept(key) {
    if (!heroConcept(key)) return;
    S.concept = key;
    renderHero();
    renderRank();
  }
  function swapImage(img, src, alt) {
    if (img.getAttribute('src') === src) { img.alt = alt; return; }
    img.classList.add('swapping');
    var pre = new Image();
    pre.onload = pre.onerror = function () {
      img.src = src;
      img.alt = alt;
      requestAnimationFrame(function () { img.classList.remove('swapping'); });
    };
    pre.src = src;
  }
  function renderHero() {
    var c = heroConcept(S.concept);
    if (!c) return;
    document.querySelectorAll('#who-seg button').forEach(function (b) {
      var who = b.getAttribute('data-who');
      b.setAttribute('aria-pressed', String(who === S.who));
      b.textContent = who === 'ai' ? 'Ask an AI to draw ' + c.n + ' ' + c.plural : 'Ask ' + c.n + ' people';
    });
    document.querySelectorAll('#concept-seg button').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.getAttribute('data-concept') === S.concept));
    });
    swapImage($('grid-img'), IMG + (S.who === 'ai' ? c.ai_img : c.people_img), ALT[c.key][S.who]);
    var stand = c.key === 'boat' ? ' Quick, Draw! has no “boat”, so both sides drew sailboats.' :
      c.key === 'person' ? ' Quick, Draw! has no “person”; its whole-body figure is “yoga”, so the AI was asked for “a person doing yoga”.' : '';
    $('grid-cap').textContent = S.who === 'ai'
      ? c.n + ' doodles by Meta’s Muse Image, from the same prompt every time (“a quick simple doodle sketch of ' +
        (c.key === 'boat' ? 'a sailboat' : c.key === 'person' ? 'a person doing yoga' : 'a ' + c.key) + '”). Spread ' + f2(c.ai_spread) + '.' + stand
      : c.n + ' drawings by people playing Google’s Quick, Draw!, who had 20 seconds each. Spread ' + f2(c.human_spread) +
        ' (average over random sets of ' + c.n + '). Quick, Draw! dataset, Google Creative Lab, CC BY 4.0.' + stand;
    var less = pct(1 - c.index);
    $('stat-num').textContent = less + '%';
    $('stat-text').textContent = 'Muse Image’s ' + NOUN[c.key] + ' are ' + less + '% less varied than people’s.';
    var sub = $('stat-sub');
    sub.innerHTML = '';
    var k1 = h('span', { class: 'k' }); k1.style.background = BLUE;
    var k2 = h('span', { class: 'k' }); k2.style.background = ORANGE;
    sub.appendChild(document.createTextNode('Spread: '));
    sub.appendChild(k1);
    sub.appendChild(document.createTextNode('Muse Image ' + f2(c.ai_spread) + ', '));
    sub.appendChild(k2);
    sub.appendChild(document.createTextNode('people ' + f2(c.human_spread) + '. Ratio ' + f2(c.index) + ' (95% CI ' + ci(c.index_ci95) + ').'));
  }
  function preloadHero() {
    (S.data.hero || []).forEach(function (c) { [c.ai_img, c.people_img].forEach(function (f) { new Image().src = IMG + f; }); });
  }

  // --- 35 things -----------------------------------------------------------------------------
  function sortedConcepts() {
    return S.data.core.concepts.slice().sort(function (a, b) { return a.index - b.index; });
  }
  function renderRank() {
    var wrap = $('rank-chart');
    if (!wrap || !S.data) return;
    var rows = sortedConcepts(), hero = heroConcept(S.concept);
    var W = Math.max(280, wrap.clientWidth), rowH = 19, top = 26, bottom = 36, left = W < 420 ? 78 : 92, right = 14;
    var H = top + rows.length * rowH + bottom, xMax = 1.25;
    var x = function (v) { return left + (Math.min(v, xMax) / xMax) * (W - left - right); };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'img',
      'aria-label': 'Dot chart of the ratio of the AI’s spread to people’s spread for 35 things, sorted from umbrella (0.14, most uniform) to book (1.04, the only one at or above 1). The table below lists every value.' });
    [0, 0.25, 0.5, 0.75, 1, 1.25].forEach(function (t) {
      svg.appendChild(s('line', { x1: x(t), x2: x(t), y1: top - 6, y2: H - bottom + 4, stroke: t === 1 ? '#6B7280' : GRID, 'stroke-width': 1 }));
      svg.appendChild(s('text', { x: x(t), y: H - bottom + 18, 'text-anchor': 'middle', 'font-size': 12, fill: '#4B5563' }, String(t)));
    });
    svg.appendChild(s('text', { x: x(1) - 4, y: top - 12, 'text-anchor': 'end', 'font-size': 12, fill: '#374151' }, 'as varied as people →'));
    svg.appendChild(s('text', { x: left + (W - left - right) / 2, y: H - 4, 'text-anchor': 'middle', 'font-size': 12, fill: '#4B5563' },
      W < 520 ? 'Muse spread ÷ people’s (lower = more alike)' : 'Muse Image’s spread ÷ people’s spread  (lower = drawn more alike)'));
    rows.forEach(function (c, i) {
      var y = top + i * rowH + rowH / 2, em = hero && c.key === hero.core_key;
      var g = s('g', {});
      var hit = s('rect', { class: 'row-hit' + (em ? ' on' : ''), x: 0, y: y - rowH / 2, width: W, height: rowH, rx: 4 });
      g.appendChild(hit);
      g.appendChild(s('text', { class: 'lbl' + (em ? ' em' : ''), x: left - 10, y: y + 4, 'text-anchor': 'end' }, c.label));
      if (c.index_ci95) {
        g.appendChild(s('line', { x1: x(c.index_ci95[0]), x2: x(c.index_ci95[1]), y1: y, y2: y, stroke: BLUE_SOFT, 'stroke-width': 3, 'stroke-linecap': 'round' }));
      }
      g.appendChild(s('circle', { cx: x(c.index), cy: y, r: em ? 6 : 4.5, fill: BLUE, stroke: '#FFFFFF', 'stroke-width': 2 }));
      hit.addEventListener('pointermove', function (e) {
        showTip(wrap, e, [c.label + (c.quickdraw !== c.label ? ' (' + c.quickdraw + ')' : ''),
          'Ratio ' + f2(c.index) + ' (95% CI ' + ci(c.index_ci95) + ')',
          c.index < 1 ? 'Muse Image’s are ' + pct(1 - c.index) + '% less varied' : 'As varied as people’s',
          'Spread: Muse Image ' + f2(c.ai_spread) + ', people ' + f2(c.human_spread)]);
      });
      hit.addEventListener('pointerleave', function () { hideTip(wrap); });
      svg.appendChild(g);
    });
    var old = wrap.querySelector('svg');
    if (old) wrap.replaceChild(svg, old); else wrap.insertBefore(svg, wrap.firstChild);
  }
  function renderEverything() {
    var core = S.data.core, rows = sortedConcepts(), lo = rows[0], hi = rows[rows.length - 1];
    $('ev-lede').textContent = 'We did the same for ' + core.n_concepts + ' things, from apples to umbrellas. Meta’s Muse Image drew ' + core.below_1 + ' of them more alike than people did.';
    var facts = $('ev-facts');
    facts.innerHTML = '';
    [[core.below_1 + ' of ' + core.n_concepts, 'things Muse Image drew more alike than people did. For ' + core.ci_below_1 + ', even the 95% interval stays below people’s level.'],
     [lo.label.charAt(0).toUpperCase() + lo.label.slice(1), 'is the most uniform: Muse Image’s ' + lo.label + 's are ' + pct(1 - lo.index) + '% less varied than people’s.'],
     [hi.label.charAt(0).toUpperCase() + hi.label.slice(1), 'is the only exception (ratio ' + f2(hi.index) + '). Muse Image drew books open, closed, stacked and at an angle, as varied as people’s.'],
     [f2(core.median_index), 'is the typical ratio: overall, Muse Image’s drawings are about half as varied as people’s.']
    ].forEach(function (f) { facts.appendChild(h('div', { class: 'pc-fact' }, [h('b', { text: f[0] }), h('span', { text: f[1] })])); });
    var t = $('rank-table');
    t.innerHTML = '';
    t.appendChild(h('thead', null, h('tr', null, [h('th', { text: 'Thing' }), h('th', { text: 'Quick, Draw! category' }), h('th', { class: 'num', text: 'AI pictures' }),
      h('th', { class: 'num', text: 'AI spread' }), h('th', { class: 'num', text: 'People’s spread' }), h('th', { class: 'num', text: 'Ratio' }), h('th', { class: 'num', text: '95% CI' })])));
    var tb = h('tbody');
    rows.forEach(function (c) {
      tb.appendChild(h('tr', null, [h('td', { text: c.label }), h('td', { text: c.quickdraw }), h('td', { class: 'num', text: String(c.n_ai) }),
        h('td', { class: 'num', text: f2(c.ai_spread) }), h('td', { class: 'num', text: f2(c.human_spread) }), h('td', { class: 'num', text: f2(c.index) }),
        h('td', { class: 'num', text: ci(c.index_ci95) })]));
    });
    t.appendChild(tb);
    renderRank();
  }

  // --- ask for variety ------------------------------------------------------------------------
  var VAR_ROWS = [['Usual prompt', 'default'], ['“Any kind”', 'any'], ['“An unusual kind”', 'unusual'], ['Named kinds, one each', 'listed']];
  function times(x) { return '×' + (x < 1 ? f2(x) : Number(x).toFixed(1)); }
  /* One row of dots per prompt: every thing's spread ÷ people's spread, the median as a black bar, people at 1. */
  function renderVarietyChart() {
    var wrap = $('var-chart'), v = S.data && S.data.variety;
    if (!wrap || !v) return;
    var rows = VAR_ROWS.filter(function (r) { return v.conditions[r[1]]; });
    var W = Math.max(280, wrap.clientWidth || 420), band = 44, gapY = 26, top = 22, left = 12, right = 14, bottom = 36;
    var H = top + rows.length * (band + gapY) + bottom;
    var all = [];
    v.concepts.forEach(function (c) { rows.forEach(function (r) { if (c[r[1]] != null) all.push(c[r[1]]); }); });
    var xMax = Math.min(4, Math.max(1.5, Math.ceil(Math.max.apply(null, all) * 2) / 2));
    var x = function (val) { return left + Math.min(val, xMax) / xMax * (W - left - right); };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'img',
      'aria-label': 'Dots: each thing’s spread with each prompt, divided by people’s spread. ' + rows.map(function (r) {
        return r[0] + ': median ' + f2(v.conditions[r[1]].median_ratio); }).join('; ') + '. People are at 1.' });
    for (var t = 0; t <= xMax + 1e-9; t += 0.5) {
      svg.appendChild(s('line', { x1: x(t), x2: x(t), y1: top, y2: H - bottom + 4, stroke: GRID }));
      svg.appendChild(s('text', { x: x(t), y: H - bottom + 18, 'text-anchor': 'middle', 'font-size': 11, fill: '#4B5563' }, String(t)));
    }
    svg.appendChild(s('text', { x: left + (W - left - right) / 2, y: H - 4, 'text-anchor': 'middle', 'font-size': 12, fill: '#374151' },
      'Muse Image’s spread ÷ people’s spread'));
    var labels = [];
    rows.forEach(function (row, ri) {
      var y0 = top + ri * (band + gapY) + 22, mid = y0 + band / 2, cond = row[1], med = v.conditions[cond].median_ratio;
      var pts = v.concepts.filter(function (c) { return c[cond] != null; });
      labels.push(s('text', { x: left, y: y0 - 7, 'font-size': 12, 'font-weight': 600, fill: '#111827', stroke: '#FFFFFF', 'stroke-width': 4,
        'paint-order': 'stroke', 'pointer-events': 'none' }, row[0] + ' · median ' + f2(med) + (pts.length < 20 ? ' (' + pts.length + ' things)' : '')));
      svg.appendChild(s('line', { x1: x(med), x2: x(med), y1: y0 + 2, y2: y0 + band - 2, stroke: '#111827', 'stroke-width': 2 }));
      pts.forEach(function (c, i) {
        var jitter = ((i * 37) % 11 - 5) / 5 * (band / 2 - 7), cy = mid + jitter, em = c.key === 'chair';
        svg.appendChild(s('circle', { cx: x(c[cond]), cy: cy, r: em ? 6 : 4.5, fill: BLUE, stroke: em ? '#111827' : '#FFFFFF', 'stroke-width': 2 }));
        if (em) labels.push(s('text', { x: x(c[cond]) + 9, y: cy + 4, 'font-size': 11, 'font-weight': 600, fill: '#111827', stroke: '#FFFFFF',
          'stroke-width': 3, 'paint-order': 'stroke', 'pointer-events': 'none' }, 'chair'));
        var hit = s('circle', { cx: x(c[cond]), cy: cy, r: 11, fill: 'transparent' });
        hit.addEventListener('pointermove', function (e) {
          showTip(wrap, e, [c.label + ': ' + f2(c[cond]), row[0] + (c[cond] < 1 ? ': less varied than people' : ': as varied as people or more')]);
        });
        hit.addEventListener('pointerleave', function () { hideTip(wrap); });
        svg.appendChild(hit);
      });
    });
    svg.appendChild(s('line', { x1: x(1), x2: x(1), y1: top, y2: H - bottom + 4, stroke: ORANGE, 'stroke-width': 2 }));
    labels.forEach(function (l) { svg.appendChild(l); });
    svg.appendChild(s('text', { x: x(1) + 5, y: 12, 'font-size': 11, fill: '#374151' }, 'people = 1'));
    var old = wrap.querySelector('svg');
    if (old) wrap.replaceChild(svg, old); else wrap.insertBefore(svg, wrap.firstChild);
  }
  function renderVariety() {
    var v = S.data.variety, sec = $('variety');
    if (!v || !v.conditions || !v.conditions.default) return;
    sec.hidden = false;
    $('var-jump').hidden = false;
    var C = v.conditions, chair = (v.focus || {}).chair;
    var best = ['listed', 'unusual', 'any'].filter(function (k) { return C[k]; });
    $('var-lede').textContent = 'With the usual prompt, Muse Image draws the textbook chair every time. Does it know any other chairs? ' +
      'We asked three more ways: for “any kind of chair”, for “an unusual or different kind”, and for each of 16 kinds that Meta’s Muse Spark listed (rocking chair, beanbag, wheelchair, throne …), one doodle each.';
    var fig = (S.data.figures || {}).variety_chair;
    if (fig) {
      $('var-fig').hidden = false;
      $('var-img').src = IMG + fig;
      $('var-img').alt = 'Five rows of 16 chair doodles. Usual prompt: the same slatted wooden chair. “Any kind”: the same slatted chair again. ' +
        '“An unusual kind”: spring chairs, egg chairs and other designer chairs. Named kinds: a rocking chair, armchair, folding chair, office chair, beanbag, wheelchair, throne and more. ' +
        'People: quick line drawings, mostly the same simple chair seen from the side.';
      $('var-cap').textContent = 'The same request, five ways. Spread: the average difference between two pictures of a row. Kinds: how many different kinds of chair Muse Glimmer recognised in the row. People’s drawings: Google Quick, Draw! dataset, CC BY 4.0.';
    }
    var facts = $('var-facts');
    facts.innerHTML = '';
    var add = function (big, text) { facts.appendChild(h('div', { class: 'pc-fact' }, [h('b', { text: big }), h('span', { text: text })])); };
    if (C.any) {
      add(times(C.any.median_ratio), '“Any kind” changes nothing: the typical spread stays at ' + times(C.any.median_ratio) + ' of people’s (usual prompt ' +
        times(C.default.median_ratio) + '), and the chairs are the same slatted chair.');
    }
    if (C.listed) {
      add(times(C.listed.median_ratio), 'Naming the kinds works: one doodle of each named kind is as varied as people’s drawings, or more, for ' +
        C.listed.above_people + ' of ' + C.listed.n + ' things' + (C.listed.median_vs_default ? ' (' + Number(C.listed.median_vs_default).toFixed(1) + ' times the usual prompt’s spread)' : '') + '.');
    }
    if (chair && chair.ratio) {
      var r = chair.ratio, top = best.filter(function (k) { return r[k] != null; })[0];
      add(times(r.default) + ' → ' + times(r[top]), 'Chairs: Muse Image’s spread compared with people’s, with the usual prompt and when ' +
        (top === 'listed' ? 'asked for named kinds' : top === 'unusual' ? 'asked for an unusual kind' : 'asked for any kind') + '.');
    }
    if (C.listed && C.listed.recognised != null && C.default.recognised != null) {
      add(pct(C.default.recognised) + '% → ' + pct(C.listed.recognised) + '%', 'of the pictures look most like people’s drawings of the same thing. Variety has a price: some named kinds come from other meanings of the word (a piano key, a clock face).');
    }
    renderVarietyChart();
    var lg = $('var-legend');
    lg.innerHTML = '';
    var key = function (color, label, line) { var i = h('i', { class: line ? 'line' : '' }); i.style.background = color; return h('span', null, [i, label]); };
    [key(BLUE, 'one thing (Muse Image)'), key(ORANGE, 'People', true), h('span', { text: 'Black bar: median' })].forEach(function (k) { lg.appendChild(k); });
    renderVarietyKinds();
  }
  function renderVarietyKinds() {
    var v = S.data.variety, k = v.kinds, box = $('var-kinds');
    box.innerHTML = '';
    if (!k || !k.summary || !k.summary.people || !k.summary.default) return;
    var P = k.summary.people, D = k.summary.default, L = k.summary.listed, pv = k.people_vs_default || {};
    box.appendChild(h('h3', { text: 'Do people draw different chairs, or the same chair differently?' }));
    box.appendChild(h('p', { text: 'Spread measures how different pictures look, and people’s quick drawings differ a lot just in how they are drawn. ' +
      'So we also asked which kind of thing each picture shows. Muse Glimmer picked one option per picture from Muse Spark’s list of kinds, plus “a plain, ordinary one” and “can’t tell”.' }));
    var same = pv.n_concepts ? pv.same_prototype + ' of ' + pv.n_concepts : null;
    box.appendChild(h('p', { text: 'People mostly draw the textbook version too. ' + pct(P.mean_share_plain) + '% of their recognisable drawings are the plain, ordinary kind, the same as for Muse Image’s usual prompt (' +
      pct(D.mean_share_plain) + '%)' + (same ? ', and for ' + same + ' things the most common kind is the same for both' : '') + '. ' +
      'Pick two drawings of the same thing at random: they show different kinds ' + pct(P.mean_simpson) + '% of the time for people, ' + pct(D.mean_simpson) +
      '% for Muse Image’s usual prompt' + (L ? ', and ' + pct(L.mean_simpson) + '% when it draws the named kinds.' : '.') +
      ' So people draw a few more kinds than Muse Image does by default, and far fewer than it can.' }));
    var noise = k.people_spread_within_prototype;
    box.appendChild(h('p', { text: chairPeopleText() + (noise && noise.median_share ? 'Across things, people’s drawings of their most common kind alone are ' +
      pct(noise.median_share) + '% as varied as all their drawings. People vary in how they draw a thing far more than in which one they draw.' : '') }));
    var hat = ((v.focus || {}).hat || {}).kinds;
    if (hat && hat.people && hat.default && hat.default.n) {
      box.appendChild(h('p', { text: 'The exception is hats: two of people’s hats are different kinds ' + pct(hat.people.simpson) + '% of the time (brimmed hats, caps, top hats, party hats), while Muse Image drew a baseball cap for ' +
        Math.round(hat.default.prototype_share * hat.default.n) + ' of its ' + hat.default.n + ' hats.' }));
    }
    box.appendChild(h('p', { class: 'pc-caveat', text: 'How we checked the labels: on Muse Image’s named-kind doodles, where we know the right answer, Glimmer picked the right kind ' +
      pct(k.accuracy) + '% of the time (' + k.n_pictures + ' pictures; chance about ' + pct(k.chance) + '%), often choosing “plain” for kinds that look ordinary. ' +
      'The numbers above use the ' + k.reliable + ' of ' + k.n_concepts + ' things where it got at least half right. Glimmer can miss kinds in rough 20-second drawings; ' +
      'a second labeler, Muse Spark, sees more kinds in both people’s and Muse Image’s drawings, but puts them in the same order.' }));
  }
  function chairPeopleText() {
    var c = ((S.data.variety || {}).focus || {}).chair;
    if (!c || !c.kinds || !c.kinds.people || !c.kinds.default) return '';
    var p = c.kinds.people, d = c.kinds.default;
    return 'Chairs: ' + pct(p.share_plain) + '% of people’s recognisable chairs are a plain, ordinary chair (Muse Image’s usual prompt: ' + pct(d.share_plain) + '%). ';
  }

  // --- six languages ------------------------------------------------------------------------
  var LANG_ALT = {
    chair: ['Grid of chair doodles by Muse Image, four for each prompt language (English, Spanish, Hindi, Mandarin Chinese, Arabic, Swahili): the same slatted wooden chair in every column.',
            'Pixel averages of the chair drawings. Top row, Muse Image by prompt language: six sharp, nearly identical chairs. Bottom row, people by country: six blurry chair shapes.'],
    hat: ['Grid of hat doodles by Muse Image, four per prompt language: baseball caps in the Hindi, Mandarin, Arabic and Swahili columns and most of the English one; brimmed hats in the Spanish column.',
          'Pixel averages of the hat drawings. Top row: the AI’s average hat is a baseball cap for five languages and a brimmed hat for Spanish. Bottom row: people’s average hat has a brim in all six countries.']
  };
  function word(lang, concept) {
    var w = S.data.languages.words[lang][concept];
    return h('i', { lang: lang, dir: lang === 'ar' ? 'rtl' : null, text: w });
  }
  function renderLang() {
    var L = S.data.languages, key = S.lang, pc = L.per_concept[key];
    document.querySelectorAll('#lang-seg button').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.getAttribute('data-lang-concept') === key));
    });
    swapImage($('lang-img'), IMG + 'lang_' + key + '_ai.webp', LANG_ALT[key][0]);
    swapImage($('lang-avg'), IMG + 'lang_' + key + '_average.webp', LANG_ALT[key][1]);
    $('lang-cap').textContent = '“' + key + '” drawn by Muse Image from the same prompt in six languages: 4 of 10 doodles per language, picked at random.';
    $('lang-avg-cap').textContent = 'The average drawing: the AI by prompt language (10 each, top) and people by country (200 each, bottom). People’s drawings: Google Quick, Draw! dataset, CC BY 4.0.';
    var box = $('lang-text');
    box.innerHTML = '';
    var ai = pc.share_ai_style_removed, hu = pc.share_human_style_removed;
    var share = function (v) { return (v[0] * 100).toFixed(1) + '%'; };
    if (key === 'chair') {
      box.appendChild(h('h3', { text: 'The same chair in all six' }));
      box.appendChild(h('p', null, ['All 60 chairs are the same slatted wooden dining chair, whether we asked for ', word('en', 'chair'), ', ', word('es', 'chair'), ', ',
        word('hi', 'chair'), ', ', word('zh', 'chair'), ', ', word('ar', 'chair'), ' or ', word('sw', 'chair'), '. Plato would be pleased.']));
      box.appendChild(h('p', { text: 'With drawing style removed, the prompt’s language explains ' + share(ai) + ' of the variation in the AI’s chairs (95% CI ' +
        minus((ai[1] * 100).toFixed(1)) + ' to ' + (ai[2] * 100).toFixed(1) + '%): no measurable difference. People’s chairs differ more by country (' + share(hu) +
        '), more than any other of the 10 things.' }));
    } else {
      box.appendChild(h('h3', { text: 'The word changes the hat' }));
      box.appendChild(h('p', null, ['In Hindi (', word('hi', 'hat'), '), Mandarin (', word('zh', 'hat'), '), Arabic (', word('ar', 'hat'), ') and Swahili (', word('sw', 'hat'),
        '), all 10 hats were baseball caps; in English, 7 of 10. Spanish ', word('es', 'hat'), ' gave brimmed hats, 3 of them Mexican sombreros.']));
      box.appendChild(h('p', { text: 'Even with drawing style removed, the language explains ' + share(ai) + ' of the variation in the AI’s hats. People in all six countries drew a brimmed hat.' }));
    }
  }

  // --- inside the AI ------------------------------------------------------------------------
  function renderScatter() {
    var wrap = $('scatter-chart'), I = S.data.inside, pts = I.scatter;
    if (!wrap || !pts || !pts.length) return;
    var W = Math.max(260, wrap.clientWidth), H = Math.round(Math.min(340, Math.max(240, W * 0.62)));
    var m = { l: 44, r: 12, t: 30, b: 40 };
    var xs = pts.map(function (p) { return p.spread; });
    var x0 = Math.floor(Math.min.apply(null, xs) * 50) / 50, x1 = Math.ceil(Math.max.apply(null, xs) * 50) / 50;
    var x = function (v) { return m.l + (v - x0) / (x1 - x0) * (W - m.l - m.r); };
    var y = function (v) { return m.t + (1 - v) * (H - m.t - m.b); };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'img',
      'aria-label': 'Scatter plot of 35 things: how varied people’s drawings are against how often Glimmer named them correctly. The more varied, the lower the accuracy on average; bench is lowest at 17%.' });
    [0, 0.25, 0.5, 0.75, 1].forEach(function (t) {
      svg.appendChild(s('line', { x1: m.l, x2: W - m.r, y1: y(t), y2: y(t), stroke: GRID }));
      svg.appendChild(s('text', { x: m.l - 6, y: y(t) + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#4B5563' }, pct(t) + '%'));
    });
    var step = (x1 - x0) > 0.2 ? 0.05 : 0.02;
    for (var t = Math.ceil(x0 / step) * step; t <= x1 + 1e-9; t += step) {
      svg.appendChild(s('text', { x: x(t), y: H - m.b + 16, 'text-anchor': 'middle', 'font-size': 11, fill: '#4B5563' }, t.toFixed(2)));
    }
    svg.appendChild(s('line', { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, stroke: AXIS }));
    svg.appendChild(s('text', { x: m.l + (W - m.l - m.r) / 2, y: H - 4, 'text-anchor': 'middle', 'font-size': 12, fill: '#374151' }, 'How varied people’s drawings are (spread) →'));
    svg.appendChild(s('text', { x: 0, y: 12, 'font-size': 12, fill: '#374151' }, W < 480 ? '↑ Named correctly by Glimmer' : '↑ How often Glimmer names people’s drawings correctly'));
    var LABEL = W < 480 ? { bench: 1, helicopter: 1, harp: 1 } : { bench: 1, helicopter: 1, harp: 1, clock: 1, guitar: 1, face: 1 };
    pts.forEach(function (p) {
      var cx = x(p.spread), cy = y(p.accuracy);
      svg.appendChild(s('circle', { cx: cx, cy: cy, r: 4.5, fill: ORANGE, stroke: '#FFFFFF', 'stroke-width': 2 }));
      if (LABEL[p.label]) {
        var right = cx > W - 90;
        svg.appendChild(s('text', { x: cx + (right ? -8 : 8), y: cy + 4, 'text-anchor': right ? 'end' : 'start', 'font-size': 11, fill: '#111827' }, p.label));
      }
      var hit = s('circle', { cx: cx, cy: cy, r: 12, fill: 'transparent' });
      hit.addEventListener('pointermove', function (e) {
        showTip(wrap, e, [pct(p.accuracy) + '% named correctly', p.label + ': people’s spread ' + f2(p.spread)]);
      });
      hit.addEventListener('pointerleave', function () { hideTip(wrap); });
      svg.appendChild(hit);
    });
    var old = wrap.querySelector('svg');
    if (old) wrap.replaceChild(svg, old); else wrap.insertBefore(svg, wrap.firstChild);
  }
  function renderInside() {
    var I = S.data.inside, L = I.layer_spread || {}, last = L.L52, r = I.naming;
    if (last) {
      $('collapse-text').textContent = 'How spread out a thing’s doodles are inside Glimmer, layer by layer (blue: Muse Image’s, orange: people’s). From about layer 30, ' +
        'Glimmer files all of Muse Image’s doodles of a thing in essentially one place, while people’s stay spread out: at the last layer, ' + f2(last.ai) +
        ' against ' + f2(last.human) + ', wider for people in ' + last.human_wider + ' of ' + last.n + ' things.';
    }
    if (r) {
      $('scatter-text').textContent = 'Each dot is one thing, drawn by people. The more different ways people draw it, the less often Glimmer names it correctly: rank correlation ' +
        minus(f2(r.rho)) + ' (95% CI ' + minus(f2(r.ci95[0])) + ' to ' + minus(f2(r.ci95[1])) + '). Glimmer named ' + pct(I.accuracy.ai) + '% of Muse Image’s doodles but only ' +
        pct(I.accuracy.human) + '% of people’s.';
    }
    renderScatter();
    renderBench();
    renderNull();
  }
  function renderBench() {
    var b = S.data.inside.bench, box = $('bench-lens');
    if (!b) { box.closest('.pc-card').hidden = true; return; }
    box.innerHTML = '';
    var maxP = Math.max.apply(null, b.p_name.concat([0.01]));
    var bars = h('div', { class: 'pc-lens-row', 'aria-hidden': 'true' }), words = h('div', { class: 'pc-lens-row' }), nums = h('div', { class: 'pc-lens-row', 'aria-hidden': 'true' });
    var list = h('ol', { class: 'sr-only' });
    b.layers.forEach(function (L, i) {
      var wd = b.top[i] || '', low = wd.toLowerCase();
      var bar = h('span');
      bar.style.height = Math.max(1, Math.round(54 * b.p_name[i] / maxP)) + 'px';
      bars.appendChild(h('div', { class: 'pc-lens-bar', title: 'p(bench) at layer ' + L + ': ' + b.p_name[i].toFixed(3) }, bar));
      words.appendChild(h('div', { class: 'pc-lens-word' + (low === 'bench' ? ' hit' : low === 'table' ? ' wrong' : ''), 'aria-hidden': 'true', text: wd }));
      nums.appendChild(h('div', { class: 'pc-lens-layer', text: String(L) }));
      list.appendChild(h('li', { text: 'Layer ' + L + ': ' + wd }));
    });
    box.appendChild(bars);
    box.appendChild(words);
    box.appendChild(nums);
    box.appendChild(h('div', { class: 'pc-lens-cap', 'aria-hidden': 'true' }, [h('span', { text: 'Bars: the chance of “bench”. Words: top guess.' }), h('span', { text: 'layer →' })]));
    box.appendChild(list);
    var peak = b.layers[b.p_name.indexOf(Math.max.apply(null, b.p_name))];
    var hb = S.data.inside.bench_human || {};
    var fewest = S.data.inside.scatter.slice().sort(function (a, c) { return a.accuracy - c.accuracy; })[0];
    $('bench-text').textContent = 'One person’s drawing of a bench. Reading Glimmer’s best guess after each layer (the word lens), “bench” wins at layer ' + peak +
      '. Later layers overwrite it: “sofa”, “стол” (Russian for table), then “table”. Its answer: “' + b.said + '”.' +
      (hb.n ? ' Glimmer named only ' + Math.round(hb.accuracy * hb.n) + ' of ' + hb.n + ' people’s benches correctly' + (fewest && fewest.key === 'bench' ? ', the fewest of all 35 things.' : '.') : '');
  }
  function renderNull() {
    var I = S.data.inside, t = $('null-table');
    t.innerHTML = '';
    t.appendChild(h('thead', null, h('tr', null, [h('th', { text: 'Damage' }), h('th', { class: 'num', text: 'Accuracy after' }), h('th', { class: 'num', text: 'Link with spread (95% CI)' })])));
    var tb = h('tbody');
    (I.lesions || []).forEach(function (l) {
      tb.appendChild(h('tr', null, [h('td', { text: l.label }), h('td', { class: 'num', text: pct(l.accuracy) + '%' }),
        h('td', { class: 'num' }, [minus(f2(l.rho)), h('span', { class: 'ci', text: minus(f2(l.ci95[0])) + ' to ' + minus(f2(l.ci95[1])) })])]));
    });
    t.appendChild(tb);
    var c = I.control_rhos || [];
    $('null-lede').textContent = 'Does spread predict which things Glimmer loses first when we damage it on purpose? No. The idea comes from people: unusual members of a category are named more slowly and are thought to be more fragile after brain damage.';
    $('null-note').textContent = 'Link: rank correlation between how varied people draw a thing and how many of its names were lost, over 35 things. 0 means no link; every interval includes 0' +
      (c.length ? ', and random damage of the same size gives ' + minus(f2(Math.min.apply(null, c))) + ' to ' + minus(f2(Math.max.apply(null, c))) : '') + '.';
  }

  // --- second image model ---------------------------------------------------------------------
  /* Two rows of dots on one axis: every thing's ratio for Muse Image and for SDXL, with the people line at 1. */
  function median(a) { var b = a.slice().sort(function (x, y) { return x - y; }), m = b.length >> 1; return b.length % 2 ? b[m] : (b[m - 1] + b[m]) / 2; }
  function renderSdxlChart(wrap, sx) {
    var rows = sx.concepts || [];
    if (!rows.length) return;
    var W = Math.max(280, wrap.clientWidth || 420), band = 56, top = 22, left = 12, right = 14, bottom = 36;
    var H = top + 2 * (band + 30) + bottom;
    var hi = Math.max.apply(null, rows.map(function (r) { return r.sdxl_index; }).concat([1.5]));
    var xMax = Math.ceil(hi * 2) / 2;
    var x = function (v) { return left + Math.min(v, xMax) / xMax * (W - left - right); };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'img',
      'aria-label': 'Each dot is one of ' + rows.length + ' things: the ratio of the model’s spread to people’s. Muse Image’s dots sit left of the people line at 1 (median ' +
        f2(median(rows.map(function (r) { return r.muse_index; }))) + '); Stable Diffusion XL’s spread around and right of it (median ' + f2(sx.median_index) + ').' });
    for (var t = 0; t <= xMax + 1e-9; t += 0.5) {
      svg.appendChild(s('line', { x1: x(t), x2: x(t), y1: top, y2: H - bottom + 4, stroke: GRID }));
      svg.appendChild(s('text', { x: x(t), y: H - bottom + 18, 'text-anchor': 'middle', 'font-size': 11, fill: '#4B5563' }, String(t)));
    }
    svg.appendChild(s('text', { x: left + (W - left - right) / 2, y: H - 4, 'text-anchor': 'middle', 'font-size': 12, fill: '#374151' }, 'model’s spread ÷ people’s spread'));
    var labels = [];
    [['Muse Image (Meta)', 'muse_index', BLUE], ['Stable Diffusion XL', 'sdxl_index', TEAL]].forEach(function (row, ri) {
      var y0 = top + ri * (band + 30) + 26, mid = y0 + band / 2, vals = rows.map(function (r) { return r[row[1]]; }), med = median(vals);
      labels.push(s('text', { x: left, y: y0 - 8, 'font-size': 12, 'font-weight': 600, fill: '#111827', stroke: '#FFFFFF', 'stroke-width': 4,
        'paint-order': 'stroke', 'pointer-events': 'none' }, row[0] + ' · median ' + f2(med)));
      svg.appendChild(s('line', { x1: x(med), x2: x(med), y1: y0 + 4, y2: y0 + band - 4, stroke: '#111827', 'stroke-width': 2 }));
      rows.forEach(function (r, i) {
        var jitter = ((i * 37) % 11 - 5) / 5 * (band / 2 - 8), cy = mid + jitter, chair = r.label === 'chair';
        svg.appendChild(s('circle', { cx: x(r[row[1]]), cy: cy, r: chair ? 6 : 4.5, fill: row[2], stroke: chair ? '#111827' : '#FFFFFF', 'stroke-width': 2 }));
        if (chair) labels.push(s('text', { x: x(r[row[1]]) + 9, y: cy + 4, 'font-size': 11, 'font-weight': 600, fill: '#111827', stroke: '#FFFFFF',
          'stroke-width': 3, 'paint-order': 'stroke', 'pointer-events': 'none' }, 'chair'));
        var hit = s('circle', { cx: x(r[row[1]]), cy: cy, r: 11, fill: 'transparent' });
        hit.addEventListener('pointermove', function (e) {
          showTip(wrap, e, [r.label + ': ' + f2(r[row[1]]), row[0] + (r[row[1]] < 1 ? ', more alike than people' : ', as varied as people or more'),
            'Spread: Muse ' + f2(r.muse_spread) + ', SDXL ' + f2(r.sdxl_spread) + ', people ' + f2(r.human_spread)]);
        });
        hit.addEventListener('pointerleave', function () { hideTip(wrap); });
        svg.appendChild(hit);
      });
    });
    svg.appendChild(s('line', { x1: x(1), x2: x(1), y1: top, y2: H - bottom + 4, stroke: ORANGE, 'stroke-width': 2 }));
    labels.forEach(function (l) { svg.appendChild(l); });
    svg.appendChild(s('text', { x: x(1) + 5, y: 12, 'font-size': 11, fill: '#374151' }, 'people = 1'));
    var old = wrap.querySelector('svg');
    if (old) wrap.replaceChild(svg, old); else wrap.insertBefore(svg, wrap.firstChild);
  }
  function renderSdxl() {
    var box = $('sdxl-card'), sx = S.data.sdxl;
    box.innerHTML = '';
    if (!sx || !sx.n_concepts) {
      box.className = 'pc-sdxl pending';
      box.appendChild(h('p', { class: 'pc-pending' }, [h('span', { class: 'spinner', 'aria-hidden': 'true' }), ' Comparison with a second image model: in progress']));
      return;
    }
    box.className = 'pc-sdxl';
    var text = h('div', { class: 'pc-sdxl-text' });
    if (!sx.complete) text.appendChild(h('span', { class: 'pc-badge', text: 'Early result: ' + sx.n_concepts + ' of ' + sx.n_total + ' things so far' }));
    var mi = sx.median_index, n = sx.n_concepts, specific = sx.muse_more_uniform >= 0.9 * n && mi >= 0.9;
    var times = sx.median_muse_over_sdxl ? (1 / sx.median_muse_over_sdxl).toFixed(1) : null;
    if ($('not-all')) $('not-all').hidden = !specific;
    if (specific) {
      text.appendChild(h('p', { class: 'pc-verdict', text: 'No. It’s Meta’s Muse Image, not AI image models in general.' }));
      text.appendChild(h('p', { text: 'With the same prompt, Stable Diffusion XL, an open model from Stability AI, drew far more varied pictures' +
        (times ? ': about ' + times + ' times Muse Image’s spread' : '') + ', and more varied for ' + sx.muse_more_uniform + ' of ' + n + ' things.' }));
      text.appendChild(h('p', { text: 'Muse Image draws the textbook version of each object. That’s useful for standardized test pictures, which need clear, typical drawings that everyone names the same way, and it’s why Test Studio uses it. But it underrepresents how differently people picture things.' }));
    } else {
      text.appendChild(h('p', { text: 'We gave Stable Diffusion XL, an open model from Stability AI, the same prompt. ' +
        (mi < 1 ? 'Its drawings were also more alike than people’s (median ratio ' + f2(mi) + ').' : 'Its drawings were not more alike than people’s (median ratio ' + f2(mi) + ', people = 1).') +
        ' Muse Image was more uniform for ' + sx.muse_more_uniform + ' of ' + n + ' things.' }));
    }
    if (sx.full_bleed_share != null) {
      var sc = sx.style_controlled;
      text.appendChild(h('p', { class: 'pc-caveat', text: 'Part of SDXL’s variety is style, not different objects: it ignored “no shading” and added frames and scenes, with ink reaching the edges in ' +
        pct(sx.full_bleed_share) + '% of its pictures. So its ratio to people (median ' + f2(mi) + ') is only an upper bound' +
        (sc && sc.median_index != null ? ' (' + f2(sc.median_index) + ' without those pictures)' : '') + '; the solid result is the contrast between the two AIs.' }));
    }
    var c = sx.concepts || [];
    if (sx.rho_muse_sdxl && c.length > 5) {
      var rank = function (key) { var r = {}; c.slice().sort(function (a, b) { return a[key] - b[key]; }).forEach(function (x, i) { r[x.label] = i; }); return r; };
      var rm = rank('muse_spread'), rs = rank('sdxl_spread');
      var plural = function (x) { return /s$/.test(x.label) ? x.label : x.label + 's'; };
      var top = c.length - 6;  // the 6 most varied things of each model
      var alike = c.filter(function (x) { return rm[x.label] < 4 && rs[x.label] < 4; }).sort(function (a, b) { return rm[a.label] - rm[b.label]; });
      var varied = c.filter(function (x) { return rm[x.label] >= top && rs[x.label] >= top; }).sort(function (a, b) { return rm[b.label] - rm[a.label]; });
      var shared = [alike.length ? 'both draw ' + listAnd(alike.map(plural)) + ' almost the same way every time' : '',
        varied.length ? 'both vary ' + listAnd(varied.map(plural)) + ' the most' : ''].filter(Boolean);
      text.appendChild(h('p', { text: 'The two AIs agree only weakly on which things they flatten (rank correlation ' + f2(sx.rho_muse_sdxl.rho) + ')' +
        (shared.length ? ': ' + shared.join(', and ') : '') + '.' }));
    }
    text.appendChild(h('p', null, h('b', { text: 'Plato’s Chair is a way to measure this for any image model.' })));
    box.appendChild(text);
    if (sx.concepts && sx.concepts.length) {
      var key = function (color, label, line) { var i = h('i', { class: line ? 'line' : '' }); i.style.background = color; return h('span', null, [i, label]); };
      var chart = h('div', { class: 'pc-chart', id: 'sdxl-chart' });
      box.appendChild(h('div', { class: 'pc-sdxl-chart' }, [h('p', { class: 'pc-chart-title', text: 'How varied each thing is, compared with people' }), chart,
        h('div', { class: 'pc-legend' }, [key(BLUE, 'Muse Image (Meta)'), key(TEAL, 'Stable Diffusion XL'), key(ORANGE, 'People', true), h('span', { text: 'Black bar: median' })])]));
      renderSdxlChart(chart, sx);
    }
    var fig = (S.data.figures || {}).sdxl_chair;
    if (fig) {
      box.appendChild(h('figure', { class: 'pc-sdxl-fig' }, [
        h('img', { src: IMG + fig, width: 1500, height: 633, loading: 'lazy',
          alt: 'Three grids of 16 chairs from the same prompt. Muse Image: the same slatted wooden chair every time. Stable Diffusion XL: armchairs, office chairs and lounge chairs, many in shaded rooms or frames. People: quick line drawings, each different.' }),
        h('figcaption', { class: 'pc-cap', text: 'The same prompt, two AIs, and people. SDXL: Stability AI, CreativeML OpenRAIL++-M. People’s drawings: Google Quick, Draw! dataset, CC BY 4.0.' })]));
    }
  }

  // --- wiring --------------------------------------------------------------------------------
  function bind() {
    document.querySelectorAll('#who-seg button').forEach(function (b) { b.addEventListener('click', function () { setWho(b.getAttribute('data-who')); }); });
    document.querySelectorAll('#concept-seg button').forEach(function (b) { b.addEventListener('click', function () { setConcept(b.getAttribute('data-concept')); }); });
    document.querySelectorAll('#lang-seg button').forEach(function (b) {
      b.addEventListener('click', function () { S.lang = b.getAttribute('data-lang-concept'); renderLang(); });
    });
    var lastW = window.innerWidth, timer = null;
    window.addEventListener('resize', function () {
      if (window.innerWidth === lastW) return;
      lastW = window.innerWidth;
      clearTimeout(timer);
      timer = setTimeout(function () { if (S.data) { renderRank(); renderVarietyChart(); renderScatter(); if ($('sdxl-chart')) renderSdxlChart($('sdxl-chart'), S.data.sdxl); } }, 120);
    });
  }

  bind();
  T.api('/api/plato').then(function (d) {
    S.data = d;
    renderHero();
    renderEverything();
    renderVariety();
    renderLang();
    renderInside();
    renderSdxl();
    setTimeout(preloadHero, 600);
    readyResolve();
  }).catch(function (e) {
    var el = $('load-error');
    el.textContent = 'Couldn’t load the Plato’s Chair results: ' + e.message;
    el.hidden = false;
    readyResolve();
  });

  T.plato = { ready: ready, setWho: setWho, setConcept: setConcept, state: function () { return S; } };
})();
