/* Plato's Cave: the first screen (shadows beside their drawings, three numbers), the "Name the shadow" game (all in the browser, nothing stored), accuracy by version,
   what the AI says instead, the comparison with people and the word lens. Data: /api/plato/cave (statistics
   and the AI's own answers only); no API calls. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var IMG = '/static/img/plato_cave/';
  var NS = 'http://www.w3.org/2000/svg';
  var C = { glimmer: 'var(--s-blue)', spark: 'var(--s-violet)', people: 'var(--s-orange)', ink: 'var(--ink)', grid: 'var(--line)', muted: 'var(--faint)',
            original: 'var(--ink)', outline: 'var(--s-green)', silhouette: 'var(--s-blue)', shadow: 'var(--s-orange)' };
  var LABEL = { original: 'Original', outline: 'Outline', silhouette: 'Silhouette', shadow: 'Cast shadow' };
  var VERSIONS = ['original', 'outline', 'silhouette', 'shadow'];
  var D = null;

  function $(id) { return document.getElementById(id); }
  function pct(x) { return Math.round(x * 100); }
  function pctCi(c) { return c ? pct(c[0]) + '–' + pct(c[1]) + '%' : ''; }
  function listAnd(a) { return a.length < 2 ? a.join('') : a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1]; }
  function s(tag, attrs, kids) {
    var el = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) el.setAttribute(k, attrs[k]); });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c == null) return;
      el.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return el;
  }
  var MASS = { bread: 1 };
  function article(w) { return MASS[w] ? w : (/^[aeiou]/.test(w) ? 'an ' : 'a ') + w; }
  function fact(big, text) { return h('div', { class: 'cv-fact' }, [h('b', { text: big }), h('span', { text: text })]); }

  // --- tooltips ------------------------------------------------------------------------------
  function showTip(wrap, evt, lines) {
    var tip = wrap.querySelector('.cv-tip');
    if (!tip) { tip = h('div', { class: 'cv-tip', role: 'presentation' }); wrap.appendChild(tip); }
    tip.innerHTML = '';
    lines.forEach(function (l, i) { tip.appendChild(i === 0 ? h('b', { text: l }) : h('div', { text: l })); });
    tip.hidden = false;
    var r = wrap.getBoundingClientRect(), x = evt.clientX - r.left, y = evt.clientY - r.top;
    var left = x + 14, top = y + 12;
    if (left + tip.offsetWidth > r.width) left = Math.max(0, x - tip.offsetWidth - 14);
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
  }
  function hideTip(wrap) { var t = wrap.querySelector('.cv-tip'); if (t) t.hidden = true; }

  // --- the first screen: shadows beside the drawings that cast them, and three numbers drawn (FirstLook) ---------
  var PAIRS = ['rabbit', 'anchor', 'hat', 'bicycle', 'guitar', 'glove'];  // four misses and two hits, as on the wall
  function heroPairs() {
    var box = $('hero-pairs');
    box.innerHTML = '';
    PAIRS.map(function (w) { return D.game.filter(function (g) { return g.word === w; })[0]; }).filter(Boolean).forEach(function (item) {
      var g = item.glimmer.shadow, ok = g.code === 'Correct';
      box.appendChild(h('figure', { class: 'cv-pair ' + (ok ? 'ok' : 'no') }, [
        h('div', { class: 'cv-pair-pics' }, [
          h('img', { src: IMG + item.shadow_img, width: 320, height: 320, alt: 'The shadow of ' + article(item.word) }),
          h('img', { class: 'orig', src: IMG + item.original_img, width: 320, height: 320, alt: 'The drawing that cast it: ' + article(item.word) })
        ]),
        h('figcaption', {}, [h('span', { class: 'said' }, ['Glimmer: ', h('q', { text: g.said })]),
          h('span', { class: 'was', text: ok ? '✓ right' : '✗ it was ' + article(item.word) })])
      ]));
    });
  }
  function hero() {
    var a = D.accuracy, m = D.medium_answers.shadow, e = D.errors.shadow, hs = D.human.silhouette, sh = a.shadow;
    var named = Math.round(sh.accuracy * sh.n);
    $('hero-answer').textContent = 'Meta’s open AI model, Muse Glimmer, named ' + named + ' of ' + sh.n + ' shadows; when it failed, its favorite answer was simply the word “Shadow”.';
    heroPairs();
    if (!window.FirstLook) return;
    // planned: drawing > outline ≈ silhouette > shadow, the silhouette at least 15 points below the drawing
    var order = a.original.accuracy >= Math.max(a.outline.accuracy, a.silhouette.accuracy) &&
      Math.min(a.outline.accuracy, a.silhouette.accuracy) > sh.accuracy;
    var gap = Math.round(-a.silhouette.diff_vs_original * 100), r = hs.rho_correct;
    var ai = pct(hs.ai_accuracy_on_shared), pp = pct(hs.people_mean_on_shared);
    window.FirstLook.render($('hero-stats'), { stats: [
      { kind: 'dots', verdict: order && gap >= 15 ? { tone: 'yes', text: 'As predicted' } : order ? { tone: 'part', text: 'Partly as predicted' } : { tone: 'no', text: 'Prediction failed' },
        o: { k: named, n: sh.n, cols: 10, tone: 'ink', label: 'soft cast shadows named correctly',
          alt: 'Muse Glimmer named ' + named + ' of ' + sh.n + ' cast shadows correctly, and ' + pct(a.original.accuracy) + '% of the drawings.' },
        q: 'Predicted: drawings easiest, silhouettes (solid black shapes) at least 15 points lower, shadows hardest. ' + (!order ? 'Not that order' :
          gap >= 15 ? 'That order' : 'That order, but silhouettes only ' + gap + ' points lower') + ' (' + pct(a.original.accuracy) + '%, ' +
          pct(a.silhouette.accuracy) + '%, ' + pct(sh.accuracy) + '%).' },
      { kind: 'dots',
        o: { k: m.just_shadow, n: e.n_errors, cols: 11, tone: 'orange', label: 'wrong answers were just “Shadow”',
          alt: m.just_shadow + ' of its ' + e.n_errors + ' wrong answers to cast shadows were just the word Shadow, and ' + m.ufo + ' were UFO.' },
        q: 'Of its ' + e.n_errors + ' wrong answers for shadows, ' + m.just_shadow + ' were just the word “Shadow”. ' + m.ufo + ' more were “UFO”.' + (D.medium_answers.silhouette.just_shadow === 0 ? ' It never said “Shadow” for a sharp black silhouette.' : '') },
      { kind: 'bars', verdict: r.ci95[0] > 0 ? { tone: 'yes', text: 'As predicted' } : { tone: 'no', text: 'Prediction failed' },
        o: { values: [ai, pp], labels: ['Glimmer', 'people'], tones: ['ink', 'orange'], max: 100, value: ai + '%', unit: 'vs ' + pp + '%',
          label: 'of silhouettes named: Glimmer, then people',
          alt: 'Silhouettes of the same ' + D.human.n_shared_concepts + ' objects: Muse Glimmer named ' + ai + '%, people ' + pp + '% (published, other drawings).' },
        q: 'Silhouettes of the same ' + D.human.n_shared_concepts + ' objects. Predicted: shapes people find hard are hard for the AI too. They were, a modest link (' + r.rho.toFixed(2) +
          ' on a scale from −1 to 1; likely ' + r.ci95[0].toFixed(2) + ' to ' + r.ci95[1].toFixed(2) + ').' }
    ] });
    $('hero-qual').textContent = 'The people, from a published study (Wagemans et al., 2008), saw different drawings of the same objects, so that comparison is by object, ' +
      'not by picture. One drawing per object, one request, one way of casting the shadow.' + (D.spark && D.spark.accuracy ? ' A second AI, Meta’s chat AI Muse Spark, named ' +
      pct(D.spark.accuracy.shadow.accuracy) + '% of its ' + D.spark.n_items + ' shadows.' : '');
  }

  // --- the game ------------------------------------------------------------------------------
  var ARTICLES = /^(a|an|the|some)\s+/;
  function norm(t) {
    return String(t || '').toLowerCase().replace(/[^a-z\s-]/g, ' ').replace(/\s+/g, ' ').trim().replace(ARTICLES, '');
  }
  function singular(w) { return w.replace(/(ies)$/, 'y').replace(/(ches|shes|sses|xes)$/, function (m) { return m.slice(0, -2); }).replace(/s$/, ''); }
  function isRight(guess, item) {
    var g = norm(guess);
    if (!g) return false;
    var words = g.split(/[\s-]+/).map(singular);
    var names = [item.word].concat(item.alternates || []).map(function (n) { return singular(norm(n)); });
    return names.some(function (n) { return n && (words.indexOf(n) >= 0 || singular(g.replace(/[\s-]/g, '')) === n.replace(/[\s-]/g, '')); });
  }
  var game = { done: {}, right: 0 };
  function score() {
    var n = Object.keys(game.done).length;
    $('score-you').innerHTML = '';
    $('score-you').appendChild(document.createTextNode('You: '));
    $('score-you').appendChild(h('b', { text: String(game.right) }));
    $('score-you').appendChild(document.createTextNode(' of ' + n));
    var ai = 0;
    Object.keys(game.done).forEach(function (w) {
      var it = D.game.filter(function (g) { return g.word === w; })[0];
      if (it.glimmer.shadow.code === 'Correct') ai += 1;
    });
    $('score-ai').textContent = n ? 'Muse Glimmer on the same shadows: ' + ai + ' of ' + n + ' (these 12 include many it missed; overall it named ' + pct(D.accuracy.shadow.accuracy) + ' of 100)' : '';
  }
  function reveal(card, item, guess) {
    if (game.done[item.word] !== undefined) return;
    var ok = isRight(guess, item);
    game.done[item.word] = ok;
    if (ok) game.right += 1;
    card.classList.add('revealed');
    card.querySelector('input').disabled = true;
    card.querySelector('button').disabled = true;
    var out = card.querySelector('.cv-out');
    out.innerHTML = '';
    out.appendChild(h('div', { class: 'it', text: 'It was ' + article(item.word) + '.' }));
    out.appendChild(h('div', { class: 'you ' + (ok ? 'ok' : 'no') }, [guess ? h('span', {}, ['You: ', h('q', { text: guess })]) : 'You passed']));
    var g = item.glimmer.shadow;
    out.appendChild(h('div', { class: 'ai ' + (g.code === 'Correct' ? 'ok' : 'no') }, ['Muse Glimmer: ', h('q', { text: g.said })]));
    if (item.spark) {
      out.appendChild(h('div', { class: 'ai ' + (item.spark.code === 'Correct' ? 'ok' : 'no') }, ['Muse Spark: ', h('q', { text: item.spark.said })]));
    }
    var sil = item.glimmer.silhouette;
    out.appendChild(h('div', { class: 'it', text: 'As a sharp silhouette, Glimmer said “' + sil.said + '”.' }));
    score();
  }
  function buildGame() {
    var grid = $('game-grid');
    grid.innerHTML = '';
    game = { done: {}, right: 0 };
    D.game.forEach(function (item, i) {
      var input = h('input', { type: 'text', autocomplete: 'off', spellcheck: 'false', 'aria-label': 'Your answer for shadow ' + (i + 1), placeholder: 'What is it?' });
      var btn = h('button', { type: 'submit', text: 'Reveal' });
      var card = h('article', { class: 'cv-card' }, [
        h('div', { class: 'pic', tabindex: '0' }, [
          h('img', { src: IMG + item.shadow_img, width: 320, height: 320, loading: 'lazy', alt: 'Shadow number ' + (i + 1) }),
          h('img', { class: 'orig', src: IMG + item.original_img, width: 320, height: 320, loading: 'lazy', alt: 'The drawing behind shadow ' + (i + 1) + ': ' + article(item.word) })
        ]),
        h('form', {}, [input, btn]),
        h('div', { class: 'cv-out', 'aria-live': 'polite' })
      ]);
      card.querySelector('form').addEventListener('submit', function (e) { e.preventDefault(); reveal(card, item, input.value.trim()); });
      grid.appendChild(card);
    });
    score();
  }

  // --- accuracy by version ---------------------------------------------------------------
  function accuracyChart() {
    var wrap = $('acc-chart');
    wrap.innerHTML = '';
    var W = 640, H = 300, L = 46, R = 16, Tp = 14, B = 34;
    var x = function (i) { return L + (i + 0.5) * (W - L - R) / VERSIONS.length; };
    var y = function (v) { return Tp + (1 - v) * (H - Tp - B); };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'Share named correctly in each version, with the likely range (95% interval)' });
    [0, 0.25, 0.5, 0.75, 1].forEach(function (t) {
      svg.appendChild(s('line', { x1: L, x2: W - R, y1: y(t), y2: y(t), stroke: C.grid, 'stroke-width': 1 }));
      svg.appendChild(s('text', { x: L - 8, y: y(t) + 4, 'text-anchor': 'end', class: 'lbl' }, pct(t) + '%'));
    });
    VERSIONS.forEach(function (v, i) {
      svg.appendChild(s('text', { x: x(i), y: H - 10, 'text-anchor': 'middle', class: 'lbl em' }, LABEL[v]));
    });
    var series = [{ key: 'glimmer', dx: -12, color: C.glimmer, name: 'Muse Glimmer (100 objects)', get: function (v) { return D.accuracy[v]; } }];
    if (D.spark && D.spark.accuracy && D.spark.accuracy.original) {
      series.push({ key: 'spark', dx: 12, color: C.spark, name: 'Muse Spark (' + D.spark.n_items + ' of them)', get: function (v) { return D.spark.accuracy[v]; } });
    }
    series.forEach(function (se) {
      var pts = VERSIONS.map(function (v, i) { return [x(i) + se.dx, y(se.get(v).accuracy)]; });
      svg.appendChild(s('polyline', { points: pts.map(function (p) { return p.join(','); }).join(' '), fill: 'none', stroke: se.color, 'stroke-width': 2 }));
      VERSIONS.forEach(function (v, i) {
        var e = se.get(v);
        if (e.ci95 && e.ci95.length) svg.appendChild(s('line', { x1: pts[i][0], x2: pts[i][0], y1: y(e.ci95[0]), y2: y(e.ci95[1]), stroke: se.color, 'stroke-width': 2, 'stroke-linecap': 'round' }));
        svg.appendChild(s('circle', { cx: pts[i][0], cy: pts[i][1], r: 5, fill: se.color, stroke: 'var(--chart-halo)', 'stroke-width': 2 }));
        if (se.key === 'glimmer') svg.appendChild(s('text', { x: pts[i][0] - 10, y: pts[i][1] + 4, 'text-anchor': 'end', class: 'lbl em' }, pct(e.accuracy) + '%'));
        var hit = s('rect', { x: pts[i][0] - 12, y: Tp, width: 24, height: H - Tp - B, class: 'hit' });
        hit.addEventListener('mousemove', function (evt) {
          showTip(wrap, evt, [se.name, LABEL[v] + ': ' + pct(e.accuracy) + '% named correctly', e.ci95 ? 'likely range ' + pctCi(e.ci95) : '']);
        });
        hit.addEventListener('mouseleave', function () { hideTip(wrap); });
        svg.appendChild(hit);
      });
    });
    var pub = D.human.published;
    [['outline', pub.outline_mean_260], ['silhouette', pub.silhouette_mean_260]].forEach(function (p) {
      var i = VERSIONS.indexOf(p[0]), cx = x(i) + 30, cy = y(p[1]);
      svg.appendChild(s('rect', { x: cx - 5, y: cy - 5, width: 10, height: 10, fill: C.people, transform: 'rotate(45 ' + cx + ' ' + cy + ')' }));
      var hit = s('rect', { x: cx - 10, y: cy - 10, width: 20, height: 20, class: 'hit' });
      hit.addEventListener('mousemove', function (evt) { showTip(wrap, evt, ['People (published)', LABEL[p[0]] + 's of 260 classic drawings: ' + pct(p[1]) + '%', 'Wagemans et al. 2008, different drawings']); });
      hit.addEventListener('mouseleave', function () { hideTip(wrap); });
      svg.appendChild(hit);
    });
    wrap.appendChild(svg);
    var leg = $('acc-legend');
    leg.innerHTML = '';
    series.forEach(function (se) { leg.appendChild(h('span', {}, [h('i', { style: { background: se.color } }), se.name])); });
    leg.appendChild(h('span', {}, [h('i', { class: 'd', style: { background: C.people } }), 'People, other drawings (published)']));
    var tb = $('acc-table');
    tb.innerHTML = '';
    tb.appendChild(h('tr', {}, [h('th', { text: 'Version' }), h('th', { class: 'num', text: 'Glimmer' }), h('th', { class: 'num', text: 'Likely range (95% CI)' }),
      h('th', { class: 'num', text: 'Change from the original' }), h('th', { class: 'num', text: 'Muse Spark' })]));
    VERSIONS.forEach(function (v) {
      var a = D.accuracy[v], sp = D.spark.accuracy[v];
      tb.appendChild(h('tr', {}, [h('td', { text: LABEL[v] }), h('td', { class: 'num', text: pct(a.accuracy) + '%' }), h('td', { class: 'num', text: pctCi(a.ci95) }),
        h('td', { class: 'num', text: a.diff_vs_original != null ? pct(a.diff_vs_original) + ' pts [' + pct(a.diff_ci95[0]) + ', ' + pct(a.diff_ci95[1]) + ']' : '' }),
        h('td', { class: 'num', text: sp ? pct(sp.accuracy) + '%' : '' })]));
    });
    var a = D.accuracy;
    $('survive-lede').textContent = 'We showed each of 100 drawings four ways: the line drawing, its outline only, a solid black silhouette, and a soft, slanted shadow, ' +
      'as if cast on a wall. Muse Glimmer named every drawing, ' + pct(a.outline.accuracy) +
      '% of the outlines, ' + pct(a.silhouette.accuracy) + '% of the silhouettes and ' + pct(a.shadow.accuracy) +
      '% of the cast shadows. Losing the inside detail cost little; the soft shadow cost a third. ' +
      D.survival.all_four.length + ' objects were named in all four versions.';
  }

  // --- what it says instead ----------------------------------------------------------------
  function medium() {
    var m = D.medium_answers.shadow, e = D.errors.shadow;
    $('medium-lede').textContent = 'Plato’s prisoners take the shadow for the thing. The AI often does the opposite: it names the shadow itself. Of its ' + e.n_errors +
      ' wrong answers to cast shadows, ' + m.just_shadow + ' were just “Shadow”, ' + (m.medium - m.just_shadow) + ' more began “The object is a shadow…”, and ' + m.ufo +
      ' were “UFO”, mostly for soft ovals such as a hat, a loaf of bread and an eye. It never answered “Shadow” for a sharp black silhouette.';
    var box = $('medium-facts');
    box.innerHTML = '';
    box.appendChild(fact('“Shadow” ×' + m.just_shadow, 'for ' + listAnd(m.just_shadow_words.map(article)) + '.'));
    box.appendChild(fact('“UFO” ×' + m.ufo, 'for ' + listAnd(m.ufo_words.map(article)) + '.'));
    if (D.spark.medium_answers && D.spark.medium_answers.shadow != null) {
      box.appendChild(fact('Muse Spark too', 'Muse Spark, Meta’s chat AI, answered “shadow” for ' + D.spark.medium_answers.shadow + ' of its ' + D.spark.n_items + ' shadows.'));
    }
    var ef = $('error-facts');
    ef.innerHTML = '';
    var parts = ['outline', 'silhouette', 'shadow'].filter(function (v) { return D.errors[v].rated; }).map(function (v) {
      return D.errors[v].visual + ' of ' + D.errors[v].rated + ' for ' + LABEL[v].toLowerCase() + 's';
    });
    ef.appendChild(fact('Shape mistakes', 'Many of its other mistakes name something with the same outline: “leaf” for a feather, “submarine” for a whistle, “pumpkin” for a watermelon. A second AI, Muse Spark, looked at the same pictures and marked these as shape (“visual”) mistakes. Of the wrong answers that were real words: ' + listAnd(parts) + '. The original drawings had no mistakes at all.'));
  }

  // --- people ------------------------------------------------------------------------------
  function people() {
    var hs = D.human.silhouette, pub = D.human.published;
    var r = hs.rho_correct, rp = hs.rho_p_name;
    $('people-lede').textContent = 'Partly. ' + D.human.n_shared_concepts + ' of our objects also appear in a classic set of pictures, so we compared the AI with a published study of 356 students naming silhouettes (Wagemans et al., 2008). ' +
      'Objects people found hard as silhouettes were harder for the AI too, with a modest link (rank correlation ' + r.rho.toFixed(2) + ' on a scale from −1 to 1, likely between ' +
      r.ci95[0].toFixed(2) + ' and ' + r.ci95[1].toFixed(2) + '; using how sure the AI was of the right name instead, ' + rp.rho.toFixed(2) + '). But the AI named far more of them: ' +
      pct(hs.ai_accuracy_on_shared) + '% of the silhouettes, where people managed ' + pct(hs.people_mean_on_shared) + '% of those objects.';
    var g = $('people-groups');
    g.innerHTML = '';
    function group(title, words, text) {
      return h('div', { class: 'cv-group' }, [h('h3', { text: title }), h('div', { class: 'cv-chips' }, words.map(function (w) { return h('span', { class: 'cv-chip', text: w }); })), h('p', { text: text })]);
    }
    g.appendChild(group('Lost by both', hs.both_fail, 'Fewer than half of people named these silhouettes, and the AI got them wrong too. A round clock or watermelon, a book seen flat: the outline alone says little.'));
    g.appendChild(group('People lost, the AI named', hs.people_fail_ai_names, 'Some of this is the drawings, not the minds. People saw the classic 1980 line drawings, and some of those fill in badly: a ladder seen from the front becomes a black slab once its holes are filled.'));
    var said = hs.ai_fails_people_name.map(function (w) {
      var it = D.items.filter(function (i) { return i.word === w; })[0];
      return it ? 'the ' + w + ' “' + it.silhouette.said + '”' : w;
    });
    g.appendChild(group('The AI lost, people named', hs.ai_fails_people_name, 'Few objects that people named as silhouettes defeated the AI. It called ' + listAnd(said) + '.'));
    $('people-note').textContent = 'People: ' + pub.participants + '; ' + pub.scoring + '. The drawings differ from ours, so this compares objects, not pictures. The study’s per-object results carry no licence, so we don’t publish them here.';
  }

  // --- word lens ---------------------------------------------------------------------------
  function lensChart() {
    var wrap = $('lens-chart');
    wrap.innerHTML = '';
    var W = 640, H = 290, L = 46, R = 90, Tp = 12, B = 34, first = 30, last = D.word_lens_n_layers;
    var x = function (l) { return L + (l - first) / (last - first) * (W - L - R); };
    var y = function (v) { return Tp + (1 - v) * (H - Tp - B); };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'How sure Glimmer is of the right name (0 to 1, averaged over objects) at each stage, from stage 30 to 52, for each version' });
    [0, 0.2, 0.4, 0.6, 0.8].forEach(function (t) {
      svg.appendChild(s('line', { x1: L, x2: W - R, y1: y(t), y2: y(t), stroke: C.grid }));
      svg.appendChild(s('text', { x: L - 8, y: y(t) + 4, 'text-anchor': 'end', class: 'lbl' }, t.toFixed(1)));
    });
    [30, 35, 40, 45, 50].forEach(function (l) { svg.appendChild(s('text', { x: x(l), y: H - 12, 'text-anchor': 'middle', class: 'lbl' }, 'stage ' + l)); });
    var ends = [];
    VERSIONS.forEach(function (v) {
      var ys = D.word_lens[v].mean_p_name_by_layer;
      var pts = [];
      for (var l = first; l <= last; l++) pts.push(x(l) + ',' + y(ys[l - 1]));
      svg.appendChild(s('polyline', { points: pts.join(' '), fill: 'none', stroke: C[v], 'stroke-width': 2 }));
      ends.push({ v: v, y: y(ys[last - 1]) });
    });
    ends.sort(function (a, b) { return a.y - b.y; });
    for (var i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 14) ends[i].y = ends[i - 1].y + 14;
    ends.forEach(function (e) { svg.appendChild(s('text', { x: W - R + 6, y: e.y + 4, class: 'lbl em' }, LABEL[e.v])); });
    var guide = s('line', { y1: Tp, y2: H - B, stroke: C.muted, 'stroke-width': 1, visibility: 'hidden' });
    svg.appendChild(guide);
    var hit = s('rect', { x: L, y: Tp, width: W - L - R, height: H - Tp - B, class: 'hit' });
    hit.addEventListener('mousemove', function (evt) {
      var r = svg.getBoundingClientRect(), px = (evt.clientX - r.left) * W / r.width;
      var l = Math.max(first, Math.min(last, Math.round(first + (px - L) / (W - L - R) * (last - first))));
      guide.setAttribute('x1', x(l)); guide.setAttribute('x2', x(l)); guide.setAttribute('visibility', 'visible');
      showTip(wrap, evt, ['Stage ' + l].concat(VERSIONS.map(function (v) { return LABEL[v] + ': ' + D.word_lens[v].mean_p_name_by_layer[l - 1].toFixed(2); })));
    });
    hit.addEventListener('mouseleave', function () { guide.setAttribute('visibility', 'hidden'); hideTip(wrap); });
    svg.appendChild(hit);
    wrap.appendChild(svg);
    var leg = $('lens-legend');
    leg.innerHTML = '';
    VERSIONS.forEach(function (v) { leg.appendChild(h('span', {}, [h('i', { style: { background: C[v] } }), LABEL[v]])); });
    var sh = D.word_lens.shadow, si = D.word_lens.silhouette;
    $('lens-lede').textContent = 'Glimmer reads a picture in 52 stages (layers), one after another. A word lens, a tool that reads which word the model is heading towards at each stage, shows when the right name appears. ' +
      'The lines show how sure Glimmer is of the right name, from 0 to 1. For every version the name appears only in the last dozen stages. For cast shadows it arrives a little later, and even at the end the model is less sure.';
    var f = $('lens-facts');
    f.innerHTML = '';
    f.appendChild(fact('+' + sh.first_layer_diff.toFixed(1) + ' stages', 'On average, the right name first appears this much later for shadows than for the same drawings (likely between ' + sh.first_layer_diff_ci95[0].toFixed(1) + ' and ' + sh.first_layer_diff_ci95[1].toFixed(1) + '; ' + sh.first_layer_pairs + ' objects named in both).'));
    var sd = Math.abs(si.first_layer_diff) < 0.05 ? '0.0' : (si.first_layer_diff > 0 ? '+' : '−') + Math.abs(si.first_layer_diff).toFixed(1);
    f.appendChild(fact(sd + ' stages', 'For sharp silhouettes: no delay (likely between ' + si.first_layer_diff_ci95[0].toFixed(1).replace('-', '−') + ' and ' + si.first_layer_diff_ci95[1].toFixed(1) + '). The shape alone is enough; the soft, slanted cast shadow is what slows it.'));
  }

  function credits() {
    var c = D.credits;
    $('credits').textContent = c.human_norms + ' ' + c.pictures + ' ' + c.models;
  }

  function init() {
    T.api('/api/plato/cave').then(function (d) {
      D = d;
      hero(); buildGame(); accuracyChart(); medium(); people(); lensChart(); credits();
    }).catch(function (e) {
      var el = $('load-error');
      el.hidden = false;
      el.textContent = e.message || 'Could not load the results.';
    });
    $('reveal-all').addEventListener('click', function () {
      [].forEach.call(document.querySelectorAll('.cv-card'), function (card, i) {
        reveal(card, D.game[i], card.querySelector('input').value.trim());
      });
    });
    $('reset').addEventListener('click', buildGame);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
