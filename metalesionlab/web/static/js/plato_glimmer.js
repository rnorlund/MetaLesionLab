/* Damage Meta's open AI: what does it forget first? (/plato/glimmer)

   Everything comes from /api/plato/glimmer (derived numbers, the AI's own short sentences, the sprite layout) and the
   drawings' sprites in /static/img/plato_glimmer/. No API calls.

   The first screen: a damage slider (where the damage is, and how much) showing Muse Glimmer's chair, clock and God
   at each step beside its own one-sentence descriptions; the answer in one sentence and three numbers drawn with
   FirstLook (plato_firstlook.js), so this first screen reads like the other series pages. Then the word against the
   picture as two lines per kind of damage, every answer at every step, and the method.

   GlimmerPage.headline(data) is pure string work (no DOM), so node can check the first screen against the data in the
   tests. Colours come from the site's tokens through classes (plato_glimmer.css); nothing here names a colour. */
(function (root) {
  'use strict';

  var FL = root && root.FirstLook ? root.FirstLook : (typeof require === 'function' ? require('./plato_firstlook.js') : null);
  var PIC = 'named', WORD = 'correct';
  var ORDER = {
    'picture first': 'the drawing went first',
    'word first': 'the words went first',
    together: 'too close to call: the drawing and the words faded together',
    neither: 'neither fell below half',
    'not testable': 'not testable'
  };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function pct(x) { return x == null || !isFinite(x) ? '–' : Math.round(x * 100) + '%'; }
  function signed(x, d) { return (x > 0 ? '+' : x < 0 ? '−' : '') + Math.abs(x).toFixed(d == null ? 2 : d); }
  function byKey(list) { var o = {}; list.forEach(function (x) { o[x.key] = x; }); return o; }
  function list(xs) { return xs.length < 2 ? xs.join('') : xs.slice(0, -1).join(', ') + ' and ' + xs[xs.length - 1]; }

  // How many of a thing's 12 answers at one step passed a measure.
  function count(d, cond, thing, m) { return d.conditions[cond][thing][m]; }

  // A kind of damage's two lines: the share of its undamaged ability left at each step (the things in the test,
  // each counting the same), as worked out by the analysis.
  function curves(d, type) { return d.verdict.types[type].curves; }

  function thingNames(d, keys) {
    var t = byKey(d.things);
    return keys.map(function (k) { return k === 'god' ? 'God' : 'a ' + t[k].name; });
  }

  // ---------- the first screen (pure) ----------

  function headline(d) {
    var types = byKey(d.damage), V = d.verdict.types, all = V.all, early = V.early, late = V.late;
    var stepsAll = types.all.steps, inc = d.verdict.included;
    // the telling step: the first where either line is below half (or the heaviest)
    var k = Math.min(all.step_picture || 99, all.step_word || 99);
    if (k === 99) k = stepsAll.length - 1;
    var c = all.curves, last = stepsAll.length - 1;
    var answer = {
      'picture first': 'Damaged, Meta’s open AI stops drawing recognisable pictures before it stops describing things correctly.',
      'word first': 'Damaged, Meta’s open AI stops describing things correctly before it stops drawing recognisable pictures.',
      together: 'Damaged, Meta’s open AI loses its drawings and its descriptions together; neither clearly goes first.',
      neither: 'Even heavily damaged, Meta’s open AI kept both its drawings and its descriptions.',
      'not testable': 'We could not tell which goes first.'
    }[all.verdict];
    var predicted = { tone: all.verdict === 'picture first' ? 'yes' : 'no',
      text: all.verdict === 'picture first' ? 'As we predicted' : 'Not what we predicted' };
    var stats = [
      { kind: 'pbars', verdict: predicted, o: {
        value: '', unit: '',
        rows: [{ label: 'drawing', v: Math.min(1, c[PIC][k]), tone: 'blue' }, { label: 'describing', v: Math.min(1, c[WORD][k]), tone: 'orange' }],
        label: 'left at step ' + k + ' of ' + last + ': drawing against describing' },
        q: ORDER[all.order].charAt(0).toUpperCase() + ORDER[all.order].slice(1) + '. Averaged over the whole ladder, the words kept ' +
          signed(all.gap * 100, 0) + ' points more of their undamaged level (likely between ' + signed(all.ci95[0] * 100, 0) + ' and ' +
          signed(all.ci95[1] * 100, 0) + ').' }
    ];
    if (early && late && early.curves && late.curves) {
      var e = early.curves, l = late.curves, eL = 3, lL = 3;
      var evl = d.verdict.early_vs_late;
      stats.push({ kind: 'pbars', o: {
        value: '', unit: '',
        rows: [{ label: 'first third: drawing', v: Math.min(1, e[PIC][eL]), tone: 'blue' },
               { label: 'first third: describing', v: Math.min(1, e[WORD][eL]), tone: 'orange' },
               { label: 'last third: drawing', v: Math.min(1, l[PIC][lL]), tone: 'blue' },
               { label: 'last third: describing', v: Math.min(1, l[WORD][lL]), tone: 'orange' }],
        label: 'left at step 3 of 5, damage early or late' },
        q: 'First third: ' + ORDER[early.verdict] + '. Last third: ' + ORDER[late.verdict] + '.' +
          (evl ? ' The difference between the two is ' + (evl.verdict === 'different' ? 'clear' : 'too close to call') +
            ' (gap ' + signed(evl.difference * 100, 0) + ' points, likely between ' + signed(evl.ci95[0] * 100, 0) + ' and ' +
            signed(evl.ci95[1] * 100, 0) + ').' : '') });
    }
    var cond = stepsAll[last].cond, fl = 0, cr = 0, n = 0;
    d.things.forEach(function (t) { fl += count(d, cond, t.key, 'fluent'); cr += count(d, cond, t.key, WORD); n += d.n; });
    stats.push({ kind: 'pbars', o: {
      value: '', unit: '',
      rows: [{ label: 'proper sentences', v: fl / n, tone: 'muted' }, { label: 'correct descriptions', v: cr / n, tone: 'orange' }],
      label: 'of its ' + n + ' sentences at the heaviest step' },
      q: fl > cr ? 'Many sentences still read smoothly but say the wrong thing.' : 'When the sentences go wrong, they stop reading smoothly too.' });
    var note = 'We wrote down the question, the measures and how we would decide before the main run. 12 answers per step; the test uses ' +
      list(thingNames(d, inc)) + (inc.length < d.things.length ? ' (undamaged, its other drawings were too rarely named right to measure a loss)' : '') + '.';
    return { answer: answer, stats: stats, note: note };
  }

  var api = { headline: headline, curves: curves };
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (!root || !root.document) return;
  root.GlimmerPage = api;

  // ---------- the page ----------

  var NS = 'http://www.w3.org/2000/svg';
  var S = { d: null, type: 'all', level: 0, gridType: 'all', gridThing: 'clock', gridStep: 0 };
  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'text') e.textContent = attrs[k]; else if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c != null) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return e;
  }
  function svg(tag, attrs, kids) {
    var e = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) e.setAttribute(k, attrs[k]); });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c != null) e.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return e;
  }
  function type(k) { return byKey(S.d.damage)[k]; }
  function sprite(kind, t, thing) { return S.d.sprites[kind].replace('{type}', t).replace('{thing}', thing); }
  function mark(cond, thing, m, i) { return S.d.marks[cond][thing][m].charAt(i) === '1'; }

  function seg(box, items, current, onPick) {
    box.innerHTML = '';
    items.forEach(function (it) {
      var b = el('button', { type: 'button', 'aria-pressed': String(it.key === current), text: it.label });
      b.addEventListener('click', function () {
        [].forEach.call(box.children, function (x) { x.setAttribute('aria-pressed', String(x === b)); });
        onPick(it.key);
      });
      box.appendChild(b);
    });
  }

  // ---------- the slider ----------

  function renderTrio() {
    var d = S.d, T = type(S.type), step = T.steps[S.level], cond = step.cond, rows = d.sprites.rows;
    var box = $('trio');
    box.innerHTML = '';
    d.things.forEach(function (t, k) {
      var i = d.featured[t.key], drew = mark(cond, t.key, 'drew', i), named = mark(cond, t.key, PIC, i);
      var said = d.sentences[cond][t.key][i], ok = mark(cond, t.key, WORD, i), fluent = mark(cond, t.key, 'fluent', i);
      var nm = t.key === 'god' ? 'God' : 'a ' + t.name;
      var alt = 'Muse Glimmer’s drawing of ' + nm + ', ' + step.label + ': ' + (drew ? (named ? 'the AI reader named it correctly' :
        'the AI reader didn’t name it correctly') : 'no drawing came out');
      var pic = el('div', { class: 'gl-pic' + (drew ? '' : ' none'), role: 'img', 'aria-label': alt,
        style: 'background-image:url(' + sprite('featured', S.type, '') + ');background-size:' + (d.things.length * 100) + '% ' +
          (rows * 100) + '%;background-position:' + (k * 100 / (d.things.length - 1)) + '% ' + (S.level * 100 / (rows - 1)) + '%' });
      var tags = el('p', { class: 'gl-tags' }, [
        el('span', { class: 'gl-tag pic' + (named ? ' ok' : ''), text: drew ? (named ? 'drawing: named right' : 'drawing: not named right') : 'no drawing' }),
        el('span', { class: 'gl-tag word' + (ok ? ' ok' : ''), text: ok ? 'sentence: correct' : (fluent ? 'sentence: smooth but wrong' : 'sentence: wrong') })]);
      box.appendChild(el('figure', { class: 'gl-panel' }, [
        el('h2', { text: t.key === 'god' ? 'God' : 'A ' + t.name }), pic,
        el('blockquote', { class: 'gl-said' }, [el('p', { text: '“' + said + '”' })]), tags]));
    });
    var r = $('level');
    r.max = String(T.steps.length - 1);
    r.value = String(S.level);
    var txt = S.level === 0 ? 'undamaged' : 'step ' + S.level + ' of ' + (T.steps.length - 1) + ': ' + step.label;
    $('level-out').textContent = S.level === 0 ? 'undamaged' : 'step ' + S.level + ' of ' + (T.steps.length - 1);
    r.setAttribute('aria-valuetext', txt);
    $('slider-cap').textContent = (S.level ? 'Step ' + S.level + ': ' + step.label + '. ' : 'Undamaged. ') +
      'One of its 12 answers at each step, with the same random starting point at every step, so you see what the damage did to that one answer. A grey square means no drawing came out.';
  }

  function setupSlider() {
    var items = S.d.damage.map(function (t) { return { key: t.key, label: t.short }; });
    seg($('type-seg'), items, S.type, function (k) { S.type = k; renderTrio(); });
    $('level').addEventListener('input', function (e) { S.level = +e.target.value; renderTrio(); });
    renderTrio();
  }

  // ---------- the two lines ----------

  function chart(t) {
    var V = S.d.verdict.types[t.key], c = V.curves, W = 440, H = 250, L = 44, R = 14, T = 16, B = 46;
    var n = t.steps.length, top = Math.max(1.2, Math.min(1.6, Math.max.apply(null, c[PIC].concat(c[WORD], c.fluent))));
    function X(i) { return L + i * (W - L - R) / (n - 1); }
    function Y(v) { return T + (1 - Math.min(v, top) / top) * (H - T - B); }
    var g = [];
    [0, 0.5, 1].forEach(function (v) {
      g.push(svg('line', { class: v === 1 ? 'gl-ref' : v === 0.5 ? 'gl-half' : 'gl-grid', x1: L, x2: W - R, y1: Y(v), y2: Y(v) }));
      g.push(svg('text', { class: 'gl-ax', x: L - 6, y: Y(v) + 4, 'text-anchor': 'end' }, pct(v)));
    });
    g.push(svg('text', { class: 'gl-ax', x: W - R, y: Y(0.5) - 5, 'text-anchor': 'end' }, 'half left'));
    t.steps.forEach(function (s, i) {
      g.push(svg('text', { class: 'gl-ax', x: X(i), y: H - B + 18, 'text-anchor': 'middle' }, i === 0 ? 'none' : String(i)));
    });
    g.push(svg('text', { class: 'gl-ax', x: (L + W - R) / 2, y: H - 8, 'text-anchor': 'middle' }, 'step of damage'));
    [['fluent', 'fluent'], [PIC, 'pic'], [WORD, 'word']].forEach(function (p) {
      var m = p[0], cls = p[1], pts = c[m].map(function (v, i) { return X(i).toFixed(1) + ',' + Y(v).toFixed(1); });
      g.push(svg('polyline', { class: 'gl-line ' + cls, points: pts.join(' ') }));
      c[m].forEach(function (v, i) {
        var what = { named: 'drawn so an AI can name it', correct: 'described correctly', fluent: 'a proper sentence' }[m];
        g.push(svg('circle', { class: 'gl-dot ' + cls, cx: X(i), cy: Y(v), r: m === 'fluent' ? 2.5 : 4, tabindex: m === 'fluent' ? null : '0' },
          svg('title', {}, (i ? 'Step ' + i + ' (' + t.steps[i].label + ')' : 'Undamaged') + ': ' + what + ', ' + pct(v) + ' of its undamaged level')));
      });
    });
    var alt = t.label + ': drawn so an AI can name it ' + c[PIC].map(pct).join(', ') + '; described correctly ' + c[WORD].map(pct).join(', ') + '.';
    var box = el('figure', { class: 'gl-chart' + (t.primary ? '' : ' extra') }, [
      el('h3', { text: t.short === 'Attention heads' ? 'Attention heads switched off (extra test)' : 'Neurons switched off: ' + t.label.replace(/^neurons switched off /, '') })]);
    box.appendChild(svg('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': alt }, g));
    var word = ORDER[V.verdict];
    box.appendChild(el('figcaption', {}, [el('b', { text: word.charAt(0).toUpperCase() + word.slice(1) + '.' }),
      ' Below half: the drawing ' + (V.step_picture ? 'at step ' + V.step_picture : 'never') + ', the words ' +
      (V.step_word ? 'at step ' + V.step_word : 'never') + '. Words kept ' + signed(V.gap * 100, 0) + ' points more on average (likely between ' +
      signed(V.ci95[0] * 100, 0) + ' and ' + signed(V.ci95[1] * 100, 0) + ').']));
    return box;
  }

  function renderCharts() {
    var box = $('charts');
    box.innerHTML = '';
    S.d.damage.forEach(function (t) { if (S.d.verdict.types[t.key].curves) box.appendChild(chart(t)); });
    var all = S.d.verdict.types.all, evl = S.d.verdict.early_vs_late;
    var Vt = S.d.verdict.types, together = Object.keys(Vt).filter(function (k) { var x = Vt[k].secondary; return x && x.drew_vs_correct && x.drew_vs_correct.verdict === 'together'; }).length;
    $('verdict-note').textContent = 'A caution: “drawn so an AI can name it” is stricter than “a drawing came out at all”. By that second count the drawing and the words fell together in ' +
      together + ' of ' + Object.keys(Vt).length + ' kinds of damage. Damage first makes the drawings unrecognisable, and only then stops them coming out.';
    $('verdict').textContent = 'Our main test, neurons switched off in every stage: ' + ORDER[all.verdict] + '.' +
      (evl ? ' Damage only in the first third against only in the last third: ' + (evl.verdict === 'different' ? 'they differ.' : 'too close to call.') : '');
  }

  function renderTable() {
    var d = S.d, rows = ['<table class="gl-table"><thead><tr><th scope="col">Damage</th><th scope="col">Step</th>'];
    d.things.forEach(function (t) { rows.push('<th scope="col" colspan="4">' + esc(t.key === 'god' ? 'God' : t.name) + '</th>'); });
    rows.push('</tr><tr><th></th><th></th>');
    d.things.forEach(function () { rows.push('<th class="num">drew</th><th class="num">named</th><th class="num">correct</th><th class="num">proper</th>'); });
    rows.push('</tr></thead><tbody>');
    d.damage.forEach(function (t) {
      t.steps.forEach(function (s, i) {
        if (i === 0 && t.key !== 'all') return;
        rows.push('<tr><th scope="row">' + esc(i === 0 ? 'none' : t.short) + '</th><td>' + esc(i === 0 ? 'undamaged' : s.label) + '</td>');
        d.things.forEach(function (th) {
          var r = d.conditions[s.cond][th.key];
          ['drew', PIC, WORD, 'fluent'].forEach(function (m) { rows.push('<td class="num">' + r[m] + '</td>'); });
        });
        rows.push('</tr>');
      });
    });
    rows.push('</tbody></table><p class="gl-note">Out of 12 answers each. Drew: a web browser drew something from its code. Named: Google’s SigLIP 2 put the thing among its three best guesses of 36 names. Correct: the sentence names the thing and says something typical about it, in under 60 words. Proper: a well-formed sentence, right or wrong.</p>');
    $('table').innerHTML = '<div class="gl-tablewrap">' + rows.join('') + '</div>';
  }

  // ---------- every answer ----------

  function renderGrid() {
    var d = S.d, T = type(S.gridType), box = $('grid'), cols = d.sprites.cols, rows = d.sprites.rows;
    box.innerHTML = '';
    T.steps.forEach(function (s, r) {
      var c = d.conditions[s.cond][S.gridThing];
      var row = el('button', { type: 'button', class: 'gl-row', 'aria-pressed': String(r === S.gridStep),
        'aria-label': (r ? 'Step ' + r + ', ' + s.label : 'Undamaged') + ': ' + c.drew + ' of 12 drew something, ' + c[PIC] + ' named right, ' + c[WORD] + ' sentences correct. Show its sentences.' }, [
        el('span', { class: 'gl-row-h' }, [el('b', { text: r ? 'Step ' + r : 'Undamaged' }), el('small', { text: c[PIC] + ' of 12 named · ' + c[WORD] + ' correct' })]),
        el('span', { class: 'gl-strip', style: 'background-image:url(' + sprite('grid', S.gridType, S.gridThing) + ');background-size:100% ' + (rows * 100) +
          '%;background-position:0 ' + (r * 100 / (rows - 1)) + '%;aspect-ratio:' + cols + '/1' })]);
      row.addEventListener('click', function () { S.gridStep = r; renderGrid(); });
      box.appendChild(row);
    });
    var s = T.steps[S.gridStep], said = d.sentences[s.cond][S.gridThing];
    var ul = el('ol', { class: 'gl-said-list' });
    said.forEach(function (x, i) {
      var ok = mark(s.cond, S.gridThing, WORD, i);
      ul.appendChild(el('li', { class: ok ? 'ok' : '' }, [el('span', { class: 'gl-tag word' + (ok ? ' ok' : ''), text: ok ? 'correct' : 'not correct' }), ' “' + x + '”']));
    });
    var name = S.gridThing === 'god' ? 'God' : 'a ' + byKey(d.things)[S.gridThing].name;
    $('sentences').innerHTML = '';
    $('sentences').appendChild(el('h3', { text: 'Its 12 sentences describing ' + name + ', ' + (S.gridStep ? 'step ' + S.gridStep + ' (' + s.label + ')' : 'undamaged') }));
    $('sentences').appendChild(ul);
  }

  function setupGrid() {
    seg($('grid-type'), S.d.damage.map(function (t) { return { key: t.key, label: t.short }; }), S.gridType, function (k) { S.gridType = k; renderGrid(); });
    seg($('grid-thing'), S.d.things.map(function (t) { return { key: t.key, label: t.key === 'god' ? 'God' : t.name.charAt(0).toUpperCase() + t.name.slice(1) }; }),
      S.gridThing, function (k) { S.gridThing = k; renderGrid(); });
    renderGrid();
  }

  function fail(msg) { var n = $('load-error'); n.hidden = false; n.textContent = msg; }

  function start(d) {
    S.d = d;
    var h = headline(d);
    $('hero-answer').textContent = h.answer;
    if (FL) FL.render($('hero-stats'), h);
    $('hero-note').textContent = h.note;
    setupSlider();
    renderCharts();
    renderTable();
    setupGrid();
    $('credits').textContent = d.credits.join('. ') + '.';
  }

  fetch('/api/plato/glimmer').then(function (r) {
    if (!r.ok) throw new Error('The results aren’t on this server yet.');
    return r.json();
  }).then(start).catch(function (e) { fail(e.message || 'Could not load the results.'); });
})(typeof window !== 'undefined' ? window : this);
