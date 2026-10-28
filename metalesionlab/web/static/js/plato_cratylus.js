/* Plato's Cratylus: the first screen's numbers, "Which one is bouba?" (your choice stays in the browser), every word's roundness,
   sound vs. famous word, and the choice arm next to people's published rates. Data: /api/plato/cratylus
   (statistics only); no API calls. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var IMG = '/static/img/plato_cratylus/';
  var NS = 'http://www.w3.org/2000/svg';
  var SOUND = { round: '#2a78d6', spiky: '#eb6834', mixed: '#6250d6', neutral: '#8a8984' };
  var SOUND_LABEL = { round: 'sounds round', spiky: 'sounds spiky', mixed: 'mixed sounds', neutral: 'neutral / no name' };
  var WHO = { glimmer_picture: ['#2a78d6', 'Muse Glimmer, picture'], glimmer_text: ['#1baf7a', 'Muse Glimmer, words only'],
              spark: ['#6250d6', 'Muse Spark, picture'] };
  var PEOPLE = '#eb6834', GRID = '#E5E7EB', MUTED = '#6B7280';
  var MEASURE = {
    solidity: { label: 'Solidity', lo: 0.45, hi: 1.0, note: 'Solidity: the shape’s area over the area of a rubber band stretched around it. 1 = a blob with no dents; a star is about 0.5. Further left = spikier.', spikyLeft: true },
    corners: { label: 'Sharp corners', lo: 0, hi: 12, note: 'Sharp corners: places where the outline turns by 60° or more within a short stretch. A blob has none, a five-pointed star five.' },
    axis: { label: 'People’s round→spiky scale', lo: -0.1, hi: 1.1, note: 'Where the drawing sits in Meta’s DINOv2 picture space between people’s circles and clouds (0) and their stars, zigzags and lightning bolts (1).' }
  };
  var D = null, S = { m: 'solidity', word: 'bouba' };

  function $(id) { return document.getElementById(id); }
  function pct(x) { return Math.round(x * 100); }
  function f2(x) { var v = Number(x); return (Math.abs(v) < 0.005 ? '0.00' : v.toFixed(2)).replace('-', '−'); }
  function s(tag, attrs, kids) {
    var el = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) el.setAttribute(k, attrs[k]); });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c == null) return;
      el.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return el;
  }
  function fact(big, text) { return h('div', { class: 'ck-fact' }, [h('b', { text: big }), h('span', { text: text })]); }
  function word(w) { return D.words.filter(function (x) { return x.word === w; })[0]; }
  function label(w) { return w === '(no name)' ? 'no name' : w; }
  function showTip(wrap, evt, lines) {
    var tip = wrap.querySelector('.ck-tip');
    if (!tip) { tip = h('div', { class: 'ck-tip', role: 'presentation' }); wrap.appendChild(tip); }
    tip.innerHTML = '';
    lines.forEach(function (l, i) { if (l) tip.appendChild(i === 0 ? h('b', { text: l }) : h('div', { text: l })); });
    tip.hidden = false;
    var r = wrap.getBoundingClientRect(), x = evt.clientX - r.left, y = evt.clientY - r.top;
    var left = x + 14;
    if (left + tip.offsetWidth > r.width) left = Math.max(0, x - tip.offsetWidth - 14);
    tip.style.left = left + 'px';
    tip.style.top = (y + 12) + 'px';
  }
  function hideTip(wrap) { var t = wrap.querySelector('.ck-tip'); if (t) t.hidden = true; }

  // --- the first screen: three numbers as small graphics (statviz.js) -------------------------------------------
  function corners(w) { var x = word(w); return x ? { k: Math.round(x.share_with_corners * x.n), n: x.n } : { k: 0, n: 0 }; }
  function heroStat(host, opts, chip) {
    var g = h('div');
    host.appendChild(h('li', { class: 'fs-stat' }, chip ? [g, chip] : [g]));
    if (window.StatViz) window.StatViz.render(g, opts);
  }
  function chip(cls, words) { return h('p', { class: 'fs-verdict ' + cls, text: words }); }
  function hero() {
    var host = $('hero-stats');
    host.innerHTML = '';
    var ki = corners('kiki'), ke = corners('keti'), te = corners('tepi'), kiw = word('kiki'), bw = word('bouba');
    heroStat(host, { kind: 'dots', k: ki.k, n: ki.n, tone: 'orange', cols: 6,
      label: '“kiki” pictures with sharp corners: stars, every one spikier than every “bouba”',
      alt: ki.k + ' of ' + ki.n + ' pictures of kiki have sharp corners (solidity ' + f2(kiw.solidity.mean) + ' vs ' + f2(bw.solidity.mean) + ' for bouba).' },
      // pre-registered: kiki spikier than bouba, the AUC's CI above 0.5 on at least two of the three measures
      ['solidity', 'corners', 'axis'].filter(function (m) { var c = D.contrasts.kiki_vs_bouba[m]; return c && c.auc_ci && c.auc_ci[0] > 0.5; }).length >= 2 ?
        chip('yes', 'As predicted') : chip('no', 'Prediction failed'));
    heroStat(host, { kind: 'dots', k: ke.k + te.k, n: ke.n + te.n, tone: 'orange', cols: 12,
      label: '“keti” and “tepi” pictures with a sharp corner: kiki’s hard sounds, drawn as blobs',
      alt: (ke.k + te.k) + ' of ' + (ke.n + te.n) + ' pictures of the new words keti and tepi have a sharp corner (solidity ' +
        f2(word('keti').solidity.mean) + ' and ' + f2(word('tepi').solidity.mean) + ').' },
      // pre-registered: words with kiki's sounds come out spikier than words with bouba's (solidity, CI above 0)
      D.contrasts.spiky_vs_round_class.solidity.diff_ci[0] > 0 ? chip('yes', 'As predicted') : chip('no', 'Prediction failed'));
    var sp = pct(D.choice.spark_both_match.p), pe = pct(D.people.both_trials_match), gl = pct(D.choice.glimmer_both_match.p);
    heroStat(host, { kind: 'bars', values: [sp, pe, gl], labels: ['Spark', 'people', 'Glimmer'], tones: ['ink', 'orange', 'muted'], max: 100,
      value: sp + '%', unit: 'vs ' + pe + '%', label: 'chose round for “bouba” and spiky for “kiki”',
      alt: 'Matched both words: Muse Spark ' + sp + '% of its answers, people ' + pe + '% (' + D.people.n_people + ' people, ' + D.people.n_languages +
        ' languages), Muse Glimmer ' + gl + '%.' },
      sp >= pe && gl >= pe ? chip('yes', 'As predicted') : sp >= pe ? chip('part', 'Partly: Glimmer no') : chip('no', 'Prediction failed'));
    $('hero-qual').textContent = 'People: ' + D.people.n_people + ' in ' + D.people.n_languages + ' languages (Ćwiek et al., 2022), who heard the words; the models only saw letters. ' +
      'Muse Glimmer, Meta’s open model, leans round for “bouba” but has no preference for “kiki”. The classic words appear on thousands of web pages about this very effect.';
  }

  // --- your turn ---------------------------------------------------------------------------------
  var TRY = [{ word: 'bouba', img: 'pair_0.webp', roundSide: 'left' }, { word: 'kiki', img: 'pair_3.webp', roundSide: 'left', flip: true }];
  var tryState = { step: 0, answers: [] };
  function tryRender() {
    var t = TRY[tryState.step];
    $('try-q').innerHTML = '';
    $('try-q').appendChild(document.createTextNode('Which one is '));
    $('try-q').appendChild(h('i', { text: t.word }));
    $('try-q').appendChild(document.createTextNode('?'));
    var img = $('try-img');
    img.src = IMG + t.img;
    img.style.transform = t.flip ? 'scaleX(-1)' : '';
    t.roundSideShown = t.flip ? 'right' : 'left';
    img.alt = 'Two black shapes: a rounded blob with soft lobes on the ' + t.roundSideShown + ', a spiky star on the ' + (t.roundSideShown === 'left' ? 'right' : 'left') + '.';
    [].forEach.call(document.querySelectorAll('.ck-pair .sides button'), function (b) { b.setAttribute('aria-pressed', 'false'); });
    $('try-steps').textContent = 'Word ' + (tryState.step + 1) + ' of 2';
  }
  function tryPick(side) {
    if (tryState.step > 1) return;
    var t = TRY[tryState.step];
    var round = side === t.roundSideShown;
    tryState.answers.push({ word: t.word, round: round });
    [].forEach.call(document.querySelectorAll('.ck-pair .sides button'), function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-side') === side)); });
    var out = $('try-out');
    out.innerHTML = '';
    var c = D.choice, p = D.people;
    if (t.word === 'bouba') {
      out.appendChild(h('p', {}, [h('b', { text: 'You picked the ' + (round ? 'round' : 'spiky') + ' one. ' }),
        'About ' + pct(p.bouba_round_first_trials) + '% of people pick the round one for “bouba” on a first trial. Muse Spark picked it ' + c.spark.bouba.n + ' times out of ' + c.spark.bouba.n + '. Muse Glimmer gives it a ' + pct(c.glimmer_picture.bouba.p_round) + '% chance.']));
      tryState.step = 1;
      setTimeout(tryRender, 1400);
    } else {
      var both = tryState.answers[0].round && !round;
      out.appendChild(h('p', {}, [h('b', { text: 'You picked the ' + (round ? 'round' : 'spiky') + ' one. ' }),
        'About ' + pct(p.kiki_spiky_first_trials) + '% of people pick the spiky one for “kiki”. Muse Spark did, ' + c.spark.kiki.n + ' times out of ' + c.spark.kiki.n + '. Muse Glimmer: a ' + pct(1 - c.glimmer_picture.kiki.p_round) + '% chance, a coin toss.']));
      out.appendChild(h('p', {}, [h('b', { text: both ? 'You matched both words, ' : 'You didn’t match both words. ' }),
        (both ? 'like ' : '') + pct(p.both_trials_match) + '% of 917 people in 25 languages' + (both ? '' : ' did') + ' (English speakers: about ' + pct(p.english_raw) + '%).']));
      tryState.step = 2;
      out.appendChild(h('p', { class: 'ck-actions' }, [h('button', { type: 'button', text: 'Try again', onclick: function () { tryState = { step: 0, answers: [] }; $('try-out').innerHTML = '<p>Pick the left or the right shape.</p>'; tryRender(); } })]));
    }
  }

  // --- every word ---------------------------------------------------------------------------------
  var ORDER = ['bouba', 'maluma', 'bomu', 'lobu', 'bemi', 'limi', 'kotu', 'tupo', 'keti', 'tepi', 'kiki', 'takete',
               'fana', 'hasa', 'nafa', 'safa', '(no name)', 'b-o-u-b-a', 'bouba (pronounced BOO-bah)', 'k-i-k-i', 'kiki (pronounced KEE-kee)'];
  function wordsChart() {
    var wrap = $('words-chart'), m = MEASURE[S.m];
    wrap.innerHTML = '';
    var list = ORDER.map(word).filter(Boolean);
    var rowH = 22, L = 200, R = 20, Tp = 24, W = 640, H = Tp + list.length * rowH + 26;
    var x = function (v) { return L + (v - m.lo) / (m.hi - m.lo) * (W - L - R); };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': m.label + ' of Muse Image’s drawings for each word, with 95% intervals' });
    var ticks = S.m === 'corners' ? [0, 3, 6, 9, 12] : S.m === 'solidity' ? [0.5, 0.6, 0.7, 0.8, 0.9, 1.0] : [0, 0.25, 0.5, 0.75, 1];
    ticks.forEach(function (t) {
      svg.appendChild(s('line', { x1: x(t), x2: x(t), y1: Tp - 6, y2: H - 22, stroke: GRID }));
      svg.appendChild(s('text', { x: x(t), y: H - 6, 'text-anchor': 'middle', class: 'lbl' }, S.m === 'corners' ? t : t.toFixed(2).replace(/0$/, '')));
    });
    if (S.m === 'axis') {
      svg.appendChild(s('text', { x: x(0), y: 12, 'text-anchor': 'middle', class: 'lbl' }, 'circles'));
      svg.appendChild(s('text', { x: x(1), y: 12, 'text-anchor': 'middle', class: 'lbl' }, 'stars'));
    } else if (S.m === 'solidity') {
      svg.appendChild(s('text', { x: x(0.5), y: 12, 'text-anchor': 'middle', class: 'lbl' }, '← spikier'));
      svg.appendChild(s('text', { x: x(0.98), y: 12, 'text-anchor': 'end', class: 'lbl' }, 'rounder →'));
    }
    list.forEach(function (w, i) {
      var y = Tp + i * rowH + rowH / 2, e = w[S.m], col = SOUND[w.sound];
      var g = s('g', { class: 'row' + (w.word === S.word ? ' on' : '') });
      var hit = s('rect', { x: 0, y: y - rowH / 2, width: W, height: rowH, class: 'hit' });
      g.appendChild(hit);
      g.appendChild(s('text', { x: L - 10, y: y + 4, 'text-anchor': 'end', class: 'lbl' + (w.word === S.word ? ' em' : ''), fill: col, style: 'fill:' + col }, label(w.word)));
      if (e.ci95) g.appendChild(s('line', { x1: x(e.ci95[0]), x2: x(e.ci95[1]), y1: y, y2: y, stroke: col, 'stroke-width': 2, 'stroke-linecap': 'round' }));
      g.appendChild(s('circle', { cx: x(e.mean), cy: y, r: 5, fill: col, stroke: '#fff', 'stroke-width': 2 }));
      hit.addEventListener('mousemove', function (evt) {
        showTip(wrap, evt, [label(w.word), m.label + ': ' + (S.m === 'corners' ? e.mean.toFixed(1) : f2(e.mean)) + (e.ci95 ? ' (95% CI ' + (S.m === 'corners' ? e.ci95[0].toFixed(1) + '–' + e.ci95[1].toFixed(1) : f2(e.ci95[0]) + '–' + f2(e.ci95[1])) + ')' : ''), SOUND_LABEL[w.sound] + ' · ' + w.n + ' pictures']);
      });
      hit.addEventListener('mouseleave', function () { hideTip(wrap); });
      hit.addEventListener('click', function () { S.word = w.word; wordsChart(); strip(); });
      svg.appendChild(g);
    });
    wrap.appendChild(svg);
    $('measure-note').textContent = m.note;
    var leg = $('words-legend');
    leg.innerHTML = '';
    ['round', 'spiky', 'mixed', 'neutral'].forEach(function (k) { leg.appendChild(h('span', {}, [h('i', { style: { background: SOUND[k] } }), SOUND_LABEL[k]])); });
  }
  function strip() {
    var w = word(S.word);
    $('strip-img').src = IMG + w.img;
    $('strip-img').alt = 'Six of Muse Image’s drawings for “' + label(w.word) + '”.';
    $('strip-cap').textContent = 'Six of the ' + w.n + ' drawings for “' + label(w.word) + '” (click a row in the chart to see another word).';
  }
  function wordsTable() {
    var tb = $('words-table');
    tb.innerHTML = '';
    tb.appendChild(h('tr', {}, [h('th', { text: 'Word' }), h('th', { class: 'num', text: 'Solidity' }), h('th', { class: 'num', text: 'Corners' }), h('th', { class: 'num', text: 'Round→spiky' }), h('th', { class: 'num', text: 'n' })]));
    ORDER.map(word).filter(Boolean).forEach(function (w) {
      tb.appendChild(h('tr', {}, [h('td', { text: label(w.word) }), h('td', { class: 'num', text: f2(w.solidity.mean) }), h('td', { class: 'num', text: w.corners.mean.toFixed(1) }), h('td', { class: 'num', text: f2(w.axis.mean) }), h('td', { class: 'num', text: w.n })]));
    });
    var k = D.contrasts.kiki_vs_bouba, t = D.contrasts.takete_vs_maluma;
    $('words-lede').textContent = 'Every kiki drawing is spikier than every bouba drawing on solidity and on people’s round-to-spiky scale (probability of superiority ' +
      f2(k.solidity.auc) + ' and ' + f2(k.axis.auc) + '); takete against maluma, the same. Every other made-up word, whatever its sounds, came out as a rounded blob. Ask for “a shape” with no name, and you get stars and polygons.';
    void t;
  }

  // --- sound or famous word ------------------------------------------------------------------
  function sound() {
    var g = D.grid.solidity, c = D.contrasts.spiky_vs_round_class.solidity, sp = D.choice.grid.spark;
    $('sound-lede').textContent = 'Bouba, kiki, maluma and takete are famous: they appear in thousands of papers and web pages about this effect. So we made up eight new words that cross the sounds people link to round shapes (b, m, l; o, u) with the sounds they link to spiky ones (k, t, p; i, e). The image model ignores the sounds. The chat model does not.';
    var a = $('sound-facts');
    a.innerHTML = '';
    a.appendChild(fact('Drawings: no', 'Muse Image drew all eight new words as rounded blobs. Hard consonants made no difference to solidity (' + (g.consonant_effect.diff >= 0.005 ? '+' : '') + f2(g.consonant_effect.diff) + ', 95% CI ' + f2(g.consonant_effect.diff_ci[0]) + ' to ' + f2(g.consonant_effect.diff_ci[1]) + '). Across the classic and new words, the spiky-sounding words are spikier only because of kiki and takete: ' + f2(c.diff) + ' (CI ' + f2(c.diff_ci[0]) + ' to ' + f2(c.diff_ci[1]) + ').'));
    var nn = word('(no name)');
    a.appendChild(fact('Any name rounds it', 'With no name, “a shape” came out as stars and polygons (solidity ' + f2(nn.solidity.mean) + '). With a made-up name, even fana or keti, it became a soft blob, unless the name was kiki or takete.'));
    var b = $('sound-facts-2');
    b.innerHTML = '';
    if (sp) {
      b.appendChild(fact('Choices: yes', 'Asked which shape is “keti”, Muse Spark picked the spiky one. For new words with soft consonants it picked the round shape ' + pct(sp.cells['soft/rounded']) + '% and ' + pct(sp.cells['soft/unrounded']) + '% of the time; with hard consonants, ' + pct(sp.cells['hard/rounded']) + '% and ' + pct(sp.cells['hard/unrounded']) + '%. Consonant effect ' + pct(sp.consonant_effect.diff) + ' points (CI ' + pct(sp.consonant_effect.diff_ci[0]) + ' to ' + pct(sp.consonant_effect.diff_ci[1]) + '); vowel effect ' + pct(sp.vowel_effect.diff) + ' points (CI ' + pct(sp.vowel_effect.diff_ci[0]) + ' to ' + pct(sp.vowel_effect.diff_ci[1]) + ').'));
    }
    b.appendChild(fact('Like people', 'Consonants mattering more than vowels is what experiments with people find too (Fort, Martin and Peperkamp, 2015). Spelling the word out (k-i-k-i) or adding how to say it changed nothing: kiki stayed a star.'));
  }

  // --- choice chart -------------------------------------------------------------------------------
  function choiceChart() {
    var wrap = $('choice-chart');
    wrap.innerHTML = '';
    var list = ['bouba', 'maluma', 'bomu', 'lobu', 'bemi', 'limi', 'kotu', 'tupo', 'keti', 'tepi', 'kiki', 'takete', 'fana', 'hasa', 'nafa', 'safa'];
    var rowH = 24, L = 80, R = 20, Tp = 22, W = 600, H = Tp + list.length * rowH + 26;
    var x = function (v) { return L + v * (W - L - R); };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'Probability of picking the round shape for each word, by model, with people for bouba and kiki' });
    [0, 0.25, 0.5, 0.75, 1].forEach(function (t) {
      svg.appendChild(s('line', { x1: x(t), x2: x(t), y1: Tp - 6, y2: H - 22, stroke: t === 0.5 ? '#9CA3AF' : GRID }));
      svg.appendChild(s('text', { x: x(t), y: H - 6, 'text-anchor': 'middle', class: 'lbl' }, pct(t) + '%'));
    });
    svg.appendChild(s('text', { x: x(0), y: 12, class: 'lbl' }, '← picks the spiky shape'));
    svg.appendChild(s('text', { x: x(1), y: 12, 'text-anchor': 'end', class: 'lbl' }, 'picks the round shape →'));
    list.forEach(function (wd, i) {
      var y = Tp + i * rowH + rowH / 2, w = word(wd);
      svg.appendChild(s('text', { x: L - 10, y: y + 4, 'text-anchor': 'end', class: 'lbl', style: 'fill:' + SOUND[w.sound] }, wd));
      Object.keys(WHO).forEach(function (k, j) {
        var e = D.choice[k][wd];
        if (!e || e.p_round == null) return;
        var cy = y + (j - 1) * 6;
        var dot = s('circle', { cx: x(e.p_round), cy: cy, r: 4.5, fill: WHO[k][0], stroke: '#fff', 'stroke-width': 1.5 });
        svg.appendChild(dot);
        var hit = s('circle', { cx: x(e.p_round), cy: cy, r: 9, class: 'hit' });
        hit.addEventListener('mousemove', function (evt) { showTip(wrap, evt, [wd, WHO[k][1] + ': picks round ' + pct(e.p_round) + '%', e.n ? e.n + ' answers' : '']); });
        hit.addEventListener('mouseleave', function () { hideTip(wrap); });
        svg.appendChild(hit);
      });
      if (wd === 'bouba' || wd === 'kiki') {
        var p = wd === 'bouba' ? D.people.bouba_round_first_trials : 1 - D.people.kiki_spiky_first_trials;
        var cx = x(p), cy = y;
        svg.appendChild(s('rect', { x: cx - 5, y: cy - 5, width: 10, height: 10, fill: PEOPLE, stroke: '#fff', 'stroke-width': 1.5, transform: 'rotate(45 ' + cx + ' ' + cy + ')' }));
        var ph = s('circle', { cx: cx, cy: cy, r: 9, class: 'hit' });
        ph.addEventListener('mousemove', function (evt) { showTip(wrap, evt, [wd, 'People: picks round ' + pct(p) + '%', 'Ćwiek et al. 2022, first trials (read from Fig. 6)']); });
        ph.addEventListener('mouseleave', function () { hideTip(wrap); });
        svg.appendChild(ph);
      }
    });
    wrap.appendChild(svg);
    var leg = $('choice-legend');
    leg.innerHTML = '';
    Object.keys(WHO).forEach(function (k) { leg.appendChild(h('span', {}, [h('i', { style: { background: WHO[k][0] } }), WHO[k][1]])); });
    leg.appendChild(h('span', {}, [h('i', { class: 'd', style: { background: PEOPLE } }), 'People (published)']));
    var c = D.choice, p = D.people;
    $('choice-lede').textContent = 'Shown a round blob and a spiky star, which is “bouba”? Muse Spark answered like a person, only more so. Muse Glimmer, Meta’s open model, leans toward the round shape for every word and barely tells bouba from kiki.';
    var f = $('choice-facts');
    f.innerHTML = '';
    f.appendChild(fact(pct(c.spark_both_match.p) + '% vs ' + pct(p.both_trials_match) + '%', 'Matched both bouba and kiki: Muse Spark (' + c.spark_both_match.n + ' paired trials) vs. 917 people in 25 languages (95% credible interval ' + pct(p.both_trials_match_cri95[0]) + '–' + pct(p.both_trials_match_cri95[1]) + '%; English speakers about ' + pct(p.english_posterior) + '%).'));
    f.appendChild(fact(pct(c.glimmer_both_match.p) + '%', 'Muse Glimmer’s chance of matching both (picture). It gives “bouba” the round shape ' + pct(c.glimmer_picture.bouba.p_round) + '% of the time but “kiki” the spiky one only ' + pct(1 - c.glimmer_picture.kiki.p_round) + '%. Told the shapes in words instead, it does better: ' + pct(c.glimmer_text.bouba.p_round) + '% round for bouba, ' + pct(1 - c.glimmer_text.kiki.p_round) + '% spiky for kiki.'));
  }

  function credits() {
    var c = D.credits;
    $('credits').textContent = c.people + ' ' + c.quickdraw + '. ' + c.models;
  }

  function init() {
    T.api('/api/plato/cratylus').then(function (d) {
      D = d;
      hero(); tryRender(); wordsChart(); strip(); wordsTable(); sound(); choiceChart(); credits();
    }).catch(function (e) {
      var el = $('load-error');
      el.hidden = false;
      el.textContent = e.message || 'Could not load the results.';
    });
    [].forEach.call(document.querySelectorAll('.ck-pair .sides button'), function (b) {
      b.addEventListener('click', function () { if (D) tryPick(b.getAttribute('data-side')); });
    });
    [].forEach.call(document.querySelectorAll('#measure-seg button'), function (b) {
      b.addEventListener('click', function () {
        S.m = b.getAttribute('data-m');
        [].forEach.call(document.querySelectorAll('#measure-seg button'), function (o) { o.setAttribute('aria-pressed', String(o === b)); });
        if (D) wordsChart();
      });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
