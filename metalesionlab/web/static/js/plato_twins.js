/* Prisoners of the cave (the #twins section of /plato/scale): twins that only read against twins that have also
   seen pictures. Reads /api/plato/twins (public_data/plato_twins.json plus the walls' layout). Tiles are masks over
   one sprite per request (static/img/plato_twins/wall_chair.webp and wall_clock.webp, 12 columns, one row per
   twin), inked in a token so they follow the theme. Every visible sentence is written to stand alone, in plain
   words (docs/style_plain_language.md). */
(function () {
  'use strict';
  var host = document.getElementById('twins-body');
  if (!host) return;
  var SPRITES = { chair: '/static/img/plato_twins/wall_chair.webp', clock: '/static/img/plato_twins/wall_clock.webp' };
  var ARM = { text: 'Trained only on text', vision: 'Also trained on pictures' };
  var SIZE = {
    '7B': ['The smaller twins', 'Qwen2.5 7B and Qwen2.5-VL 7B, from Alibaba’s Qwen team: about 7 billion internal settings each'],
    '32B': ['The larger twins', 'Qwen2.5 32B and Qwen2.5-VL 32B, from the same team: about 32 billion internal settings each']
  };
  var THING = { chair: 'chair', clock: 'clock' };

  function el(tag, attrs, html) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (html != null) e.innerHTML = html;
    return e;
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function words(n) { return ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve'][n] || String(n); }
  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

  function rowOf(d, key, task, temp) {
    for (var i = 0; i < d.rows.length; i++) {
      var r = d.rows[i];
      if (r.key === key && r.task === task && r.temp === temp) return r;
    }
    return null;
  }
  function modelOf(d, key) { return d.models.filter(function (m) { return m.key === key; })[0]; }
  function twinsOf(d, size) {
    var t = d.models.filter(function (m) { return m.size === size; });
    return [t.filter(function (m) { return m.arm === 'text'; })[0], t.filter(function (m) { return m.arm === 'vision'; })[0]];
  }

  function tiles(wallRow, nRows, task, label) {
    var box = el('div', { 'class': 'tw-tiles' });
    var thing = THING[task];
    wallRow.tiles.forEach(function (fail, i) {
      var t = el('div', { 'class': 'tw-tile' + (fail ? ' fail' : '') + (wallRow.read[i] ? ' read' : ''), role: 'img' });
      if (fail) {
        t.setAttribute('aria-label', label + ', answer ' + (i + 1) + ': no drawing (' + fail + ')');
        t.appendChild(el('span', {}, esc(fail)));
      } else {
        t.setAttribute('aria-label', label + ', drawing ' + (i + 1) + ' of 12' +
          (wallRow.read[i] ? ', named a ' + thing + ' by the picture-reading AI' : ''));
        var m = el('i', { 'aria-hidden': 'true' });
        var url = 'url("' + SPRITES[task] + '")';
        var size = (12 * 100) + '% ' + (nRows * 100) + '%';
        var pos = (i / 11 * 100) + '% ' + (nRows > 1 ? wallRow.row / (nRows - 1) * 100 : 0) + '%';
        ['webkitMask', 'mask'].forEach(function (p) {
          m.style[p + 'Image'] = url; m.style[p + 'Size'] = size; m.style[p + 'Position'] = pos;
        });
        t.appendChild(m);
      }
      box.appendChild(t);
    });
    return box;
  }

  function countLine(r, task) {
    if (task === 'chair') {
      return words(r.valid) === 'twelve' ? 'All 12 answers were drawings.' :
        cap(words(r.valid)) + ' of its 12 answers were drawings; the rest were broken code.';
    }
    var s = r.eye_1110 === 0 ? 'None of its 12 clocks showed 10 past 11, judged by eye.' :
      cap(words(r.eye_1110)) + ' of its 12 clocks showed 10 past 11, judged by eye.';
    return r.valid === 12 ? s : s + ' ' + cap(words(12 - r.valid)) + ' of 12 answers were broken code, not drawings.';
  }

  function arm(d, m, task, wallRows) {
    var r = rowOf(d, m.key, task, 1);
    var wr = wallRows.filter(function (w) { return w.key === m.key; })[0];
    var box = el('div', { 'class': 'tw-arm ' + m.arm });
    box.appendChild(el('p', { 'class': 'tw-arm-h' }, '<b>' + ARM[m.arm] + '</b><span>' + esc(m.label) + '</span>'));
    box.appendChild(tiles(wr, wallRows.length, task, m.label + ' (' + ARM[m.arm].toLowerCase() + ')'));
    var c = el('div', { 'class': 'tw-count' });
    var dots = el('div', {
      'data-sv': 'dots', 'data-k': String(r.read_as), 'data-n': '12', 'data-cols': '12', 'data-size': 's',
      'data-tone': m.arm === 'vision' ? 'green' : 'muted', 'data-unit': ' of 12',
      'data-label': 'drawings the picture-reading AI named a ' + THING[task],
      'data-alt': m.label + ': ' + r.read_as + ' of 12 drawings were named a ' + THING[task] + ' by the picture-reading AI'
    });
    c.appendChild(dots);
    c.appendChild(el('p', { 'class': 'tw-sub' }, esc(countLine(r, task))));
    box.appendChild(c);
    return box;
  }

  function quotes(d, pair) {
    var box = el('div', { 'class': 'tw-words-box' });
    box.appendChild(el('p', { 'class': 'tw-words-h' }, 'It knows the word: asked to describe a chair'));
    var g = el('div', { 'class': 'tw-words' });
    pair.forEach(function (m) {
      var q = d.quotes.filter(function (x) { return x.key === m.key; })[0];
      var r = rowOf(d, m.key, 'describe', 1);
      var f = el('figure', { 'class': 'tw-quote' });
      f.appendChild(el('q', {}, esc(q.sentence)));
      f.appendChild(el('span', {}, esc(m.label) + ' · ' + esc(ARM[m.arm].toLowerCase()) + '. Its 12 descriptions named the seat, legs and back ' +
        (r.all_three === 12 ? 'every time.' : 'together in ' + r.all_three + ' of 12.')));
      g.appendChild(f);
    });
    box.appendChild(g);
    return box;
  }

  function pairs(d, task) {
    var g = el('div', { 'class': 'tw-pairs' });
    var wallRows = d.wall.walls[task];
    ['7B', '32B'].forEach(function (size) {
      var pair = twinsOf(d, size);
      var p = el('div', { 'class': 'tw-pair' });
      p.appendChild(el('h3', {}, esc(SIZE[size][0]) + '<span>' + esc(SIZE[size][1]) + '</span>'));
      var duo = el('div', { 'class': 'tw-duo' });
      pair.forEach(function (m) { duo.appendChild(arm(d, m, task, wallRows)); });
      p.appendChild(duo);
      if (task === 'chair') p.appendChild(quotes(d, pair));
      g.appendChild(p);
    });
    return g;
  }

  function table(d) {
    var wrap = el('div', { 'class': 'tw-table-wrap' });
    var people = ((d.anchors || {}).people_spread_n12 || 0.37).toFixed(2);
    var head = ['AI', 'Request', 'Drawings (of 12)', 'Named correctly by the picture-reading AI (of 12)',
      'Judged by eye (of 12): looks like a chair, or shows 10 past 11',
      'How different its chairs are from one another (spread: 0 = identical copies; people’s doodles ' + people + ')'];
    var t = el('table');
    t.appendChild(el('thead', {}, '<tr>' + head.map(function (h) { return '<th scope="col">' + h + '</th>'; }).join('') + '</tr>'));
    var tb = el('tbody');
    d.rows.filter(function (r) { return r.task !== 'describe'; }).forEach(function (r) {
      var eye = r.task === 'chair' ? (r.eye_chair != null ? String(r.eye_chair) : '–') : (r.eye_1110 != null ? String(r.eye_1110) : '–');
      var req = r.task === 'chair' ? 'chair' + (r.temp === 1 ? '' : ' (less random)') : 'clock';
      tb.appendChild(el('tr', {}, '<th scope="row">' + esc(r.label) + '</th><td>' + req + '</td><td>' + r.valid + '</td><td>' + r.read_as +
        '</td><td>' + eye + '</td><td>' + (r.spread == null ? '–' : r.spread.toFixed(2) + ' (' + r.spread_ratio.toFixed(1) + ' × people’s)') + '</td>'));
    });
    d.rows.filter(function (r) { return r.task === 'describe'; }).forEach(function (r) {
      tb.appendChild(el('tr', {}, '<th scope="row">' + esc(r.label) + '</th><td>describe a chair</td><td>–</td><td>–</td><td>' +
        r.score.toFixed(1) + ' of 3 parts named, on average</td><td>–</td>'));
    });
    t.appendChild(tb); wrap.appendChild(t);
    return wrap;
  }

  // ---------- the words: each sentence stands alone, numbers come from the data ----------
  function sumOf(d, arm, task, col) {
    return d.rows.filter(function (r) { return r.arm === arm && r.task === task && r.temp === 1; })
      .reduce(function (a, r) { return a + (r[col] || 0); }, 0);
  }

  function text(d) {
    var P1 = d.predictions.P1.verdict, P2 = d.predictions.P2.verdict;
    var readText = sumOf(d, 'text', 'chair', 'read_as'), readVision = sumOf(d, 'vision', 'chair', 'read_as');
    var eyeText = sumOf(d, 'text', 'chair', 'eye_chair'), eyeVision = sumOf(d, 'vision', 'chair', 'eye_chair');
    var clocks = sumOf(d, 'text', 'clock', 'eye_1110') + sumOf(d, 'vision', 'clock', 'eye_1110');
    var who1110 = d.rows.filter(function (r) { return r.task === 'clock' && r.eye_1110 > 0; });
    var big = { text: rowOf(d, 'qwen25_32b', 'clock', 1), vision: rowOf(d, 'qwen25vl_32b', 'clock', 1) };
    var people = Math.round(((d.anchors || {}).people_read_as_chair || 0.86) * 100);
    var marks = ((d.posthoc || {}).clock_hour_marks) || null;
    var lenient = ((d.posthoc || {}).eye_chair_lenient) || null;
    var answer = {
      'supported': 'Yes. The twins that had also seen pictures drew chairs more often than the twins that had only read, at both sizes.',
      'partly supported': 'Partly. At one size, the twin that had also seen pictures drew chairs more often than its text-only twin.',
      'contradicted': 'No. The twins that had only read drew chairs more often than the twins that had also seen pictures.',
      'unclear': 'No. The twins that had also seen pictures drew chairs no more often than the twins that had only read.'
    }[P1] || '';
    answer += P2 === 'supported' ? ' Yet all four described a chair well in words. They know the word, but none of them could draw the thing in code.' : '';
    return {
      lede: 'An AI trained only on text knows chairs only from words, like the prisoners in Plato’s cave who see only shadows. ' +
        'We tested two pairs of twins from Alibaba’s Qwen team: one trained on text only, one also trained on pictures. Both got the same typed requests, 12 times each.',
      answer: answer,
      key: {
        chair: 'A green dot marks a drawing that another AI, one that reads pictures (Google’s SigLIP 2), named a chair.',
        clock: 'A green dot marks a drawing that another AI, one that reads pictures (Google’s SigLIP 2), named a clock.'
      },
      note: {
        chair: 'We expected the twins that had seen pictures to draw more recognizable chairs. That didn’t happen. ' +
          'Out of 24 drawings for each kind of twin, the picture-reading AI named ' + readText + ' of the text-only twins’ drawings a chair, and ' +
          readVision + ' of the picture-trained twins’. ' +
          'Judged by eye, without knowing which twin drew which, ' + eyeVision + ' of the picture-trained twins’ 24 drawings looked like a chair, against ' +
          eyeText + ' of the text-only twins’. A gap that small is too close to call with 12 tries per AI. ' +
          (lenient ? 'Judging by eye is a judgment call: counting the drawings we had marked as borderline, the larger picture-trained twin had ' +
            lenient.qwen25vl_32b + ' chair-like drawings and its text-only twin ' + lenient.qwen25_32b + '. ' : '') +
          'The solid black shapes are drawings whose code filled every shape in black instead of drawing outlines. ' +
          'For comparison, the picture-reading AI names ' + people + '% of people’s quick doodles of chairs correctly.',
        clock: 'The larger twins both drew proper clock faces: the picture-reading AI named ' + big.text.read_as + ' and ' + big.vision.read_as +
          ' of their 12 drawings a clock. The smaller twins often drew solid black discs, because their code filled the clock face in and hid the hands. ' +
          (clocks === 1 && who1110.length ? 'Only one clock of all 48 showed 10 past 11, judged by eye, and it came from ' + who1110[0].label +
            ', the larger twin trained only on text.' : clocks + ' of all 48 clocks showed 10 past 11, judged by eye.') +
          (marks ? ' One difference we noticed only afterwards, so treat it as a lead rather than a finding: ' + marks.qwen25vl_32b +
            ' of the larger picture-trained twin’s 11 clocks have hour marks around the dial, and ' + words(marks.qwen25_32b) +
            ' of its text-only twin’s 12 do.' : '')
      },
      method: [
        '<b>The twins.</b> Qwen2.5 7B and Qwen2.5 32B were trained on text only. Qwen2.5-VL 7B and Qwen2.5-VL 32B started from the same AIs and were then also trained on pictures with text. All four are free to download and use (Apache-2.0 licence). “7B” and “32B” are their sizes: about 7 and 32 billion internal settings.',
        '<b>What we asked.</b> Three typed requests, 12 times each, with no picture given: “Draw a simple chair as an SVG drawing…” (the same request as in the rest of this page), “Draw a clock showing 10 past 11 as an SVG drawing…”, and “Describe what a chair looks like in two sentences.” SVG is a way of writing a drawing as code; we turned each answer into a picture.',
        '<b>Same conditions.</b> Each AI answered with its usual amount of randomness, so 12 tries give 12 different answers. A check with less randomness also found no clear difference between the twins. The text-only twins’ chairs are the same 24 drawings shown in the rest of this page.',
        '<b>Who judged.</b> A picture-reading AI (Google’s SigLIP 2) chose which of 35 everyday things each drawing looks most like. We also judged every drawing and description by eye, shuffled so we couldn’t tell which twin made it. We locked those judgments with a digital fingerprint before any automatic scoring ran. A description scored a point each for naming the seat, the legs and the back.',
        '<b>Planned first.</b> We wrote down our predictions before we made any drawings (<a href="https://github.com/rnorlund/MetaLesionLab/blob/main/docs/plato_cave_twins_plan.md">the plan</a>), and we report the result whichever way it came out (<a href="https://github.com/rnorlund/MetaLesionLab/blob/main/docs/plato_cave_twins.md">the write-up</a>).',
        '<b>Limits.</b> With 12 tries per AI, only a big difference would show; a small advantage for the picture-trained twins could be missed. The twins differ in more than pictures: the picture-trained ones also had their own later training in conversation, and a slightly different built-in greeting. Writing a drawing as code is a narrow skill, so an AI may know what a chair looks like and still write poor drawing code.'
      ]
    };
  }

  function render(d) {
    var T = text(d);
    host.innerHTML = '';
    host.appendChild(el('p', { 'class': 'tw-lede' }, T.lede));
    host.appendChild(el('p', { 'class': 'tw-answer', id: 'twins-answer' }, esc(T.answer)));
    var chips = el('div', { 'class': 'tw-chips', role: 'group', 'aria-label': 'Which request to show' });
    var stage = el('div', { 'class': 'tw-stage' });
    var key = el('p', { 'class': 'tw-key' });
    var note = el('p', { 'class': 'tw-note' });
    var extra = el('details', { 'class': 'how-we-know' }, '<summary>How we know</summary><p></p>');
    function show(task) {
      stage.innerHTML = '';
      stage.appendChild(pairs(d, task));
      if (window.StatViz) window.StatViz.renderAll(stage);
      key.innerHTML = '<i aria-hidden="true"></i>' + esc(T.key[task]);
      // two short sentences stay in view; the rest of the note is under "How we know"
      var sents = T.note[task].split(/(?<=[.?!])\s+/), more = sents.slice(2).join(' ');
      note.textContent = sents.slice(0, 2).join(' ');
      extra.hidden = !more;
      extra.querySelector('p').textContent = more;
      chips.querySelectorAll('button').forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-task') === task ? 'true' : 'false'); });
    }
    [['chair', 'Draw a chair'], ['clock', 'Draw a clock at 10 past 11']].forEach(function (c) {
      var b = el('button', { type: 'button', 'data-task': c[0], 'aria-pressed': 'false' }, esc(c[1]));
      b.addEventListener('click', function () { show(c[0]); });
      chips.appendChild(b);
    });
    host.appendChild(chips);
    host.appendChild(key);
    host.appendChild(stage);
    host.appendChild(note);
    host.appendChild(extra);
    var det = el('details', { 'class': 'sc-numbers' });
    det.appendChild(el('summary', {}, 'All the numbers'));
    det.appendChild(table(d));
    host.appendChild(det);
    var ul = el('ul', { 'class': 'tw-method' });
    T.method.forEach(function (li) { ul.appendChild(el('li', {}, li)); });
    host.appendChild(ul);
    show('chair');
  }

  fetch('/api/plato/twins').then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(render)
    .catch(function () { host.innerHTML = '<p class="tw-note">These results couldn’t be loaded. Try reloading the page.</p>'; });
})();
