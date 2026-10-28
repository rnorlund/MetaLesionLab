/* Seven meanings (/plato/phaedrus). The seven recordings first (Kokoro voices, stress added with the WORLD vocoder),
   each with what Voice Transcribe wrote down; then Muse Spark's and the prosody reader's accuracy, their confusion
   tables, the reader's contour for the recording last played, and "Try it with your voice".
   Data: /api/plato/phaedrus. Listening costs nothing. The voice test records in the browser, resamples to a
   16 kHz mono WAV and sends it to /api/phaedrus/listen (free: the reader, on our server) and /api/phaedrus/read
   (paid: Voice Transcribe and Muse Spark). Nothing is stored, here or there. Colours are app.css variables, used
   through var() so the charts follow the site's theme. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var NS = 'http://www.w3.org/2000/svg';
  var D = null, voice = 0, audioEl = null, playing = -1, heard = {};
  var REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function $(id) { return document.getElementById(id); }
  function pct(x) { return Math.round(x * 100) + '%'; }
  function s(tag, attrs, kids) {
    var el = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (attrs[k] == null) return;
      if (k === 'style') el.setAttribute('style', attrs[k]);
      else el.setAttribute(k, attrs[k]);
    });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c == null) return;
      el.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return el;
  }
  function words() { return D.words; }
  function canon() { return D.words.map(function (w) { return w.toLowerCase(); }); }
  function sentenceWith(k) {
    var out = [];
    D.words.forEach(function (w, i) {
      if (i) out.push(' ');
      out.push(i === k ? h('b', { text: w }) : w);
    });
    out.push('.');
    return out;
  }
  /* The transcript with the tokens that aren't the sentence's words, in order, marked. */
  function markedTranscript(t) {
    var want = canon(), j = 0, out = [];
    String(t || '').split(/(\s+)/).forEach(function (tok) {
      if (!tok) return;
      if (/^\s+$/.test(tok)) { out.push(tok); return; }
      var bare = tok.toLowerCase().replace(/[^a-z']/g, '');
      if (j < want.length && bare === want[j]) { out.push(tok); j += 1; }
      else out.push(h('mark', { text: tok, title: 'not one of the sentence’s words, in order' }));
    });
    return out.length ? out : ['(nothing)'];
  }

  // --- the seven recordings ------------------------------------------------------------------------------------

  var PLAY = '<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M2 1L9 5L2 9Z"/></svg>';
  var STOP = '<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M2 2H8V8H2Z"/></svg>';

  function renderVoices() {
    var box = $('voices');
    box.innerHTML = '';
    D.voices.forEach(function (v, i) {
      var b = h('button', { type: 'button', role: 'radio', 'aria-checked': String(i === voice), tabindex: i === voice ? '0' : '-1',
                            text: v.label });
      b.addEventListener('click', function () { pickVoice(i, true); });
      b.addEventListener('keydown', function (e) {
        var d = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
        if (!d) return;
        e.preventDefault();
        pickVoice((voice + d + D.voices.length) % D.voices.length, true);
      });
      box.appendChild(b);
    });
  }

  function pickVoice(i, focus) {
    stop();
    voice = i;
    heard = {};
    renderVoices();
    if (focus) $('voices').children[i].focus();
    renderCards();
    renderTranscripts();
    drawContour($('contour-demo'), D.voices[voice].clips[0].contour, { truth: 0, title: titleFor(0) });
  }

  function titleFor(k) {
    return [D.voices[voice].label + ', ', h('b', { text: D.words[k].toUpperCase() }), ' stressed'];
  }

  function chip(label, k, truth) {
    var right = k === truth;
    return h('span', { class: 'ph-chip ' + (k == null ? '' : right ? 'right' : 'wrong') }, [
      label + ': ', h('i', { text: k == null ? 'no answer' : D.words[k] }), right ? ' ✓' : ' ✗']);
  }

  function renderCards() {
    var list = $('cards');
    list.innerHTML = '';
    D.voices[voice].clips.forEach(function (c, k) {
      var btn = h('button', { type: 'button', class: 'ph-play', 'aria-pressed': 'false' });
      btn.innerHTML = '<span class="icon">' + PLAY + '</span>';
      btn.appendChild(h('span', { class: 'say' }, sentenceWith(k)));
      btn.appendChild(h('span', { class: 'gloss', text: D.meanings[k].gloss }));
      btn.setAttribute('aria-label', 'Play: ' + D.words.map(function (w, i) { return i === k ? w.toUpperCase() : w; }).join(' ')
        + '. ' + D.meanings[k].gloss);
      btn.addEventListener('click', function () { toggle(k); });
      var wrote = h('div', { class: 'ph-wrote' }, [
        h('span', { class: 'label', text: 'What a text-only AI receives:' }),
        h('span', { class: 'text' }, markedTranscript(c.transcript)),
        h('div', { class: 'ph-chips', 'aria-live': 'polite' })]);
      list.appendChild(h('li', { class: 'ph-row' }, [btn, wrote]));
    });
  }

  function revealChips(k) {
    heard[k] = true;
    var c = D.voices[voice].clips[k];
    var box = $('cards').children[k].querySelector('.ph-chips');
    box.innerHTML = '';
    box.appendChild(chip('Spark, reading', c.spark, k));
    box.appendChild(chip('Reader, listening', c.reader, k));
  }

  function renderTranscripts() {
    var same = D.voices[voice].clips.filter(function (c) {
      return String(c.transcript || '').toLowerCase().replace(/[^a-z' ]/g, '').trim().split(/\s+/).join(' ') === canon().join(' ');
    }).length;
    $('shadow-sub').textContent = 'Meta’s Voice Transcribe wrote down each recording. ' +
      (same === 7 ? 'In this voice all seven came back as the same words: the stress is gone.' :
        'In this voice ' + same + ' of 7 came back as exactly the sentence’s words; the others have a doubled or stray ' +
        'word (marked), a slip that turned up in the neutral readings too. The stress itself is gone.') +
      ' Press a recording to see what Muse Spark and the prosody reader made of it.';
  }

  function stop() {
    if (audioEl) { audioEl.pause(); audioEl = null; }
    if (playing >= 0) setPlaying(playing, false);
    playing = -1;
  }

  function setPlaying(k, on) {
    var li = $('cards').children[k];
    if (!li) return;
    var b = li.querySelector('.ph-play');
    b.setAttribute('aria-pressed', String(on));
    b.querySelector('.icon').innerHTML = on ? STOP : PLAY;
    li.classList.toggle('on', on);
  }

  function toggle(k) {
    var was = playing;
    stop();
    if (was === k) return;
    var c = D.voices[voice].clips[k];
    audioEl = new Audio(c.src);
    playing = k;
    setPlaying(k, true);
    audioEl.addEventListener('ended', function () { if (playing === k) stop(); });
    audioEl.addEventListener('error', function () {
      if (playing === k) stop();
      T.toast('That recording couldn’t be played in this browser.', 'error');
    });
    var p = audioEl.play();
    if (p && p.catch) p.catch(function () { if (playing === k) stop(); });
    revealChips(k);
    drawContour($('contour-demo'), c.contour, { truth: k, title: titleFor(k) });
  }

  // --- the answer and the charts -------------------------------------------------------------------------------

  function renderAnswer() {
    var tr = D.spark.transcript, caps = D.spark.caps, it = D.spark.italics, rd = D.reader;
    var chance = Math.round(D.chance * tr.n);
    $('answer').innerHTML = '';
    $('answer').appendChild(document.createTextNode('Reading these, Muse Spark picked the meaning the speaker intended ' +
      tr.k + ' times in ' + tr.n + ' (' + pct(tr.acc) + '): no better than guessing (' + chance + '). With the stressed word in '));
    $('answer').appendChild(h('i', { text: 'italics' }));
    $('answer').appendChild(document.createTextNode(', ' + it.k + ' of ' + it.n + '.'));
    $('answer').appendChild(h('small', { text: 'A plain prosody reader, listening to the sound instead, found the stressed word ' +
      rd.k + ' times in ' + rd.n + ' (' + pct(rd.acc) + '). Thirteen voices, seven stressed words each.' }));
    $('results-lede').textContent = 'Every recording of every voice, 91 in all. Chance is 1 in 7 (14%). The bars show each ' +
      'reader’s accuracy with its exact 95% confidence interval.';
  }

  function bars() {
    var rows = [
      { label: 'Muse Spark, reading the transcript', b: D.spark.transcript, color: 'var(--text)' },
      { label: 'Muse Spark, stressed word in CAPITALS', b: D.spark.caps, color: 'var(--text)' },
      { label: 'Muse Spark, stressed word in *italics*', b: D.spark.italics, color: 'var(--text)' },
      { label: 'Prosody reader, listening to the sound', b: D.reader, color: 'var(--sound)' }
    ];
    // drawn at the container's own width, so text stays at its stated size; narrow: labels above the bars
    var W = Math.min(1100, widthOf($('bars'))), narrow = W < 640;
    var L = narrow ? 8 : 330, R = narrow ? 76 : 120, rowH = narrow ? 70 : 52, top = 26, H = top + rows.length * rowH + 30;
    var dy = narrow ? 18 : 0;
    var x = function (v) { return L + v * (W - L - R); };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'presentation' });
    [0, 0.25, 0.5, 0.75, 1].forEach(function (v) {
      svg.appendChild(s('line', { x1: x(v), x2: x(v), y1: top - 6, y2: H - 26, style: 'stroke: var(--line); stroke-width: 1' }));
      svg.appendChild(s('text', { x: x(v), y: H - 8, 'text-anchor': 'middle', style: 'fill: var(--muted); font-size: 13px' }, pct(v)));
    });
    rows.forEach(function (r, i) {
      var y = top + i * rowH;
      svg.appendChild(s('text', narrow ? { x: L, y: y + 12, style: 'fill: var(--ink-2); font-size: 14px' } :
        { x: L - 14, y: y + 22, 'text-anchor': 'end', style: 'fill: var(--ink-2); font-size: 15px' }, r.label));
      y += dy;
      svg.appendChild(s('rect', { x: x(0), y: y + 6, width: Math.max(2, x(r.b.acc) - x(0)), height: 26, rx: 4, style: 'fill: ' + r.color }));
      svg.appendChild(s('line', { x1: x(r.b.ci[0]), x2: x(r.b.ci[1]), y1: y + 19, y2: y + 19, style: 'stroke: var(--ink); stroke-width: 2' }));
      [r.b.ci[0], r.b.ci[1]].forEach(function (v) {
        svg.appendChild(s('line', { x1: x(v), x2: x(v), y1: y + 12, y2: y + 26, style: 'stroke: var(--ink); stroke-width: 2' }));
      });
      svg.appendChild(s('text', { x: x(1) + 10, y: y + 24, style: 'fill: var(--ink); font-size: 15px; font-weight: 600' },
        r.b.k + ' of ' + r.b.n));
    });
    svg.appendChild(s('line', { x1: x(D.chance), x2: x(D.chance), y1: top - 12, y2: H - 26,
      style: 'stroke: var(--ink); stroke-width: 1.5; stroke-dasharray: 5 4' }));
    svg.appendChild(s('text', { x: x(D.chance) + 6, y: top - 12, style: 'fill: var(--ink-2); font-size: 13px' }, 'chance, 1 in 7'));
    $('bars').innerHTML = '';
    $('bars').appendChild(svg);
    $('bars').setAttribute('aria-label', rows.map(function (r) { return r.label + ': ' + r.b.k + ' of ' + r.b.n + ' (' + pct(r.b.acc) +
      ', 95% CI ' + pct(r.b.ci[0]) + ' to ' + pct(r.b.ci[1]) + ')'; }).join('; ') + '. Chance is 14%.');
    var capsI = D.spark.caps.confusion[0][0];
    $('bars-cap').textContent = 'Bars: share right; whiskers: exact 95% CI; dashed line: chance. Spark from transcripts: 91 recordings ' +
      '(13 voices × 7). CAPITALS and italics: each word 5 times, options shuffled. Prosody reader: the same 91 recordings.' +
      (capsI === 0 ? ' CAPITALS missed only “I”, which is always written in capitals: there, writing can’t show the stress.' : '');
  }

  function grid(el, capEl, m, color, who) {
    var n = m.length, cell = 46, L = 92, top = 64, W = L + n * cell + 8, H = top + n * cell + 8;
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img' });
    var total = 0, diag = 0;
    svg.appendChild(s('text', { x: L + n * cell / 2, y: 14, 'text-anchor': 'middle', style: 'fill: var(--muted); font-size: 12px' },
      who + '’s guess →'));
    D.words.forEach(function (w, j) {
      svg.appendChild(s('text', { x: L + j * cell + cell / 2, y: top - 10, 'text-anchor': 'middle', style: 'fill: var(--ink-2); font-size: 13px' }, w));
    });
    m.forEach(function (row, i) {
      var rt = row.reduce(function (a, b) { return a + b; }, 0) || 1;
      svg.appendChild(s('text', { x: L - 10, y: top + i * cell + cell / 2 + 5, 'text-anchor': 'end', style: 'fill: var(--ink-2); font-size: 13px' },
        D.words[i]));
      row.forEach(function (v, j) {
        total += v; if (i === j) diag += v;
        svg.appendChild(s('rect', { x: L + j * cell + 1, y: top + i * cell + 1, width: cell - 2, height: cell - 2, rx: 4,
          style: 'fill: ' + color + '; fill-opacity: ' + (v ? 0.12 + 0.88 * v / rt : 0) + '; stroke: ' +
            (i === j ? 'var(--ink)' : 'var(--line)') + '; stroke-width: ' + (i === j ? 1.5 : 1) }));
        if (v) svg.appendChild(s('text', { x: L + j * cell + cell / 2, y: top + i * cell + cell / 2 + 5, 'text-anchor': 'middle',
          style: 'font-size: 14px; font-weight: 600; fill: ' + (v / rt > 0.55 ? 'var(--panel)' : 'var(--ink)') }, v));
      });
    });
    svg.appendChild(s('text', { x: 12, y: top + n * cell / 2, transform: 'rotate(-90 12 ' + (top + n * cell / 2) + ')',
      'text-anchor': 'middle', style: 'fill: var(--muted); font-size: 12px' }, 'stressed word'));
    svg.setAttribute('aria-label', who + ': ' + diag + ' of ' + total + ' on the diagonal (right). ' + m.map(function (row, i) {
      return D.words[i] + ' stressed: ' + row.map(function (v, j) { return v ? v + '× ' + D.words[j] : ''; }).filter(Boolean).join(', ');
    }).join('; '));
    el.innerHTML = '';
    el.appendChild(svg);
    return { diag: diag, total: total };
  }

  function grids() {
    var sp = grid($('grid-spark'), null, D.spark.transcript.confusion, 'var(--text)', 'Spark');
    var choices = D.spark.transcript.choices || {};
    var top = Object.keys(choices).sort(function (a, b) { return choices[b] - choices[a]; });
    $('grid-spark-cap').textContent = 'Rows: the word that was stressed. Columns: the meaning Spark picked. Right answers sit on ' +
      'the outlined diagonal (' + sp.diag + ' of ' + sp.total + '). With the same words in every row, Spark mostly picked ' +
      top.slice(0, 2).map(function (w) { return '“' + w + '” (' + choices[w] + ')'; }).join(' and ') + ', whatever was said.';
    var rd = grid($('grid-reader'), null, D.reader.confusion, 'var(--sound)', 'Reader');
    var hardest = D.words.map(function (w, i) { return { w: w, k: D.reader.confusion[i][i] }; })
      .sort(function (a, b) { return a.k - b.k; })[0];
    $('grid-reader-cap').textContent = 'The same 91 recordings, heard instead of read: ' + rd.diag + ' of ' + rd.total +
      ' on the diagonal. Hardest: “' + hardest.w + '” (' + hardest.k + ' of 13), often heard as “I”.';
  }

  // --- the reader's contour -------------------------------------------------------------------------------------

  var lastContour = {};
  function widthOf(el) { return Math.max(300, Math.round(el.getBoundingClientRect().width || 1000)); }

  function drawContour(el, c, opts) {
    opts = opts || {};
    el.innerHTML = '';
    if (!c) return;
    var head = h('div', { class: 'ph-contour-head' });
    if (opts.title) head.appendChild(h('span', {}, opts.title));
    var g = c.guess;
    head.appendChild(h('span', {}, ['The reader picked ', h('b', { text: '“' + D.words[g] + '”' }),
      opts.truth == null ? '' : (g === opts.truth ? ' ✓ right' : ' ✗ (it was “' + D.words[opts.truth] + '”)')]));
    el.appendChild(head);
    var W = Math.min(1400, widthOf(el)), narrow = W < 640;
    var L = narrow ? 34 : 44, R = 8, top = 12, pitchH = narrow ? 120 : 150;
    var levelTop = pitchH + 26, levelH = narrow ? 60 : 70, labY = levelTop + levelH + 26, H = labY + 58;
    lastContour[el.id] = [c, opts];
    var t0 = Math.min(c.t[0], c.bounds[0]), t1 = Math.max(c.t[c.t.length - 1], c.bounds[c.bounds.length - 1]);
    var x = function (t) { return L + (t - t0) / Math.max(1e-6, t1 - t0) * (W - L - R); };
    var ps = c.pitch.filter(function (v) { return v != null; });
    var pmin = Math.min(-6, Math.min.apply(null, ps.length ? ps : [0])), pmax = Math.max(8, Math.max.apply(null, ps.length ? ps : [0]));
    var yp = function (v) { return top + (pmax - v) / (pmax - pmin) * pitchH; };
    var lmin = -30, lmax = 12;
    var yl = function (v) { return levelTop + (lmax - Math.max(lmin, Math.min(lmax, v))) / (lmax - lmin) * levelH; };
    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img' });
    // word bands
    for (var k = 0; k < c.words.length; k++) {
      var a = x(c.bounds[k]), b = x(c.bounds[k + 1]);
      if (k === g) svg.appendChild(s('rect', { x: a, y: top - 6, width: Math.max(1, b - a), height: labY + 44 - top, rx: 6,
        style: 'fill: var(--sound-soft)' }));
      svg.appendChild(s('line', { x1: a, x2: a, y1: top - 6, y2: labY + 38, style: 'stroke: var(--line-2); stroke-width: 1' }));
    }
    svg.appendChild(s('line', { x1: x(c.bounds[c.bounds.length - 1]), x2: x(c.bounds[c.bounds.length - 1]), y1: top - 6, y2: labY + 38,
      style: 'stroke: var(--line-2); stroke-width: 1' }));
    // loudness: an area under the level line
    var lp = 'M' + x(c.t[0]) + ' ' + yl(lmin);
    c.t.forEach(function (t, i) { lp += 'L' + x(t).toFixed(1) + ' ' + yl(c.level[i]).toFixed(1); });
    lp += 'L' + x(c.t[c.t.length - 1]) + ' ' + yl(lmin) + 'Z';
    svg.appendChild(s('path', { d: lp, style: 'fill: var(--ink-2); fill-opacity: 0.22; stroke: none' }));
    // pitch: a line broken where unvoiced
    var d = '', pen = false;
    c.t.forEach(function (t, i) {
      var v = c.pitch[i];
      if (v == null) { pen = false; return; }
      d += (pen ? 'L' : 'M') + x(t).toFixed(1) + ' ' + yp(v).toFixed(1);
      pen = true;
    });
    svg.appendChild(s('line', { x1: L, x2: W - R, y1: yp(0), y2: yp(0), style: 'stroke: var(--line); stroke-dasharray: 3 4' }));
    svg.appendChild(s('path', { d: d, style: 'fill: none; stroke: var(--sound); stroke-width: 3; stroke-linejoin: round; stroke-linecap: round' }));
    svg.appendChild(s('text', { x: 4, y: top + 10, style: 'fill: var(--muted); font-size: 12px' }, 'pitch'));
    svg.appendChild(s('text', { x: 4, y: levelTop + 12, style: 'fill: var(--muted); font-size: 12px' }, 'loud'));
    // labels and prominence
    var tot = c.words.map(function (w) { return w.total; });
    var pm = Math.max.apply(null, tot.map(Math.abs).concat([1]));
    c.words.forEach(function (w, k) {
      var a = x(c.bounds[k]), b = x(c.bounds[k + 1]), mid = (a + b) / 2, win = k === g;
      svg.appendChild(s('text', { x: mid, y: labY, 'text-anchor': 'middle',
        style: 'font-size: ' + (narrow ? (win ? 14 : 12) : (win ? 17 : 15)) + 'px; font-weight: ' + (win ? 700 : 400) + '; fill: ' +
          (win ? 'var(--ink)' : 'var(--ink-2)') }, w.word));
      var bh = Math.max(2, Math.abs(w.total) / pm * 24);
      svg.appendChild(s('rect', { x: mid - 10, y: w.total >= 0 ? labY + 32 - bh : labY + 32, width: 20, height: bh, rx: 2,
        style: 'fill: ' + (win ? 'var(--sound)' : 'var(--line-2)') }));
    });
    svg.setAttribute('aria-label', 'Pitch and loudness over the sentence. The reader’s prominence per word: ' +
      c.words.map(function (w) { return w.word + ' ' + w.total.toFixed(1); }).join(', ') + '. It picked “' + D.words[g] + '”.');
    el.appendChild(svg);
    el.appendChild(h('div', { class: 'ph-legend' }, [
      h('span', {}, [h('i', { class: 'line', style: 'background: var(--sound)' }), 'pitch (semitones from the speaker’s middle)']),
      h('span', {}, [h('i', { style: 'background: var(--ink-2); opacity: 0.3' }), 'loudness']),
      h('span', {}, [h('i', { style: 'background: var(--sound-soft); border: 1px solid var(--sound)' }), 'the reader’s pick']),
      h('span', {}, [h('i', { style: 'background: var(--line-2)' }), 'small bars: prominence, pitch + loudness + length'])]));
  }

  // --- try it with your voice ------------------------------------------------------------------------------------

  var MAX_S = 10, rec = null, lastTry = null;

  function canRecord() {
    return !!(window.MediaRecorder && navigator.mediaDevices && navigator.mediaDevices.getUserMedia &&
              (window.AudioContext || window.webkitAudioContext) && window.OfflineAudioContext);
  }
  function status(text) { $('rec-status').textContent = text; }

  function toRate(samples, from, to) {
    if (from === to || !samples.length) return Promise.resolve(samples);
    var n = Math.max(1, Math.round(samples.length * to / from));
    var off = new OfflineAudioContext(1, n, to);
    var buf = off.createBuffer(1, samples.length, from);
    buf.copyToChannel(samples, 0);
    var src = off.createBufferSource();
    src.buffer = buf;
    src.connect(off.destination);
    src.start();
    return off.startRendering().then(function (r) { return r.getChannelData(0); });
  }

  function wavBlob(samples, rate) {
    var buf = new ArrayBuffer(44 + samples.length * 2), v = new DataView(buf);
    function str(o, x) { for (var i = 0; i < x.length; i++) v.setUint8(o + i, x.charCodeAt(i)); }
    str(0, 'RIFF'); v.setUint32(4, 36 + samples.length * 2, true); str(8, 'WAVE'); str(12, 'fmt ');
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, rate, true);
    v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); str(36, 'data');
    v.setUint32(40, samples.length * 2, true);
    for (var i = 0; i < samples.length; i++) {
      var x = Math.max(-1, Math.min(1, samples[i]));
      v.setInt16(44 + i * 2, x < 0 ? x * 32768 : x * 32767, true);
    }
    return new Blob([buf], { type: 'audio/wav' });
  }

  function start() {
    var btn = $('rec');
    btn.disabled = true;
    navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 } })
      .then(function (stream) {
        var AC = window.AudioContext || window.webkitAudioContext;
        var ctx = new AC(), an = ctx.createAnalyser();
        ctx.createMediaStreamSource(stream).connect(an);
        an.fftSize = 1024;
        var data = new Float32Array(an.fftSize), chunks = [];
        var mr = new MediaRecorder(stream);
        rec = { stream: stream, ctx: ctx, mr: mr, t0: performance.now(), raf: 0, timer: 0 };
        mr.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
        mr.onstop = function () { finish(new Blob(chunks, { type: mr.mimeType || 'audio/webm' })); };
        mr.start();
        btn.disabled = false;
        btn.classList.add('on');
        btn.textContent = 'Stop';
        status('Recording… say “I never said she stole my money”, stressing one word.');
        (function meter() {
          if (!rec) return;
          an.getFloatTimeDomainData(data);
          var m = 0;
          for (var i = 0; i < data.length; i++) m = Math.max(m, Math.abs(data[i]));
          $('meter').style.width = Math.min(100, Math.round(Math.sqrt(m) * 140)) + '%';
          var left = MAX_S - (performance.now() - rec.t0) / 1000;
          if (left <= 0) { stopRec(); return; }
          rec.raf = requestAnimationFrame(meter);
        })();
      })
      .catch(function () {
        btn.disabled = false;
        status('The page can’t hear a microphone (none found, or permission refused). The seven recordings above still work.');
      });
  }

  function stopRec() {
    if (!rec) return;
    var r = rec;
    rec = null;
    cancelAnimationFrame(r.raf);
    $('meter').style.width = '0';
    $('rec').classList.remove('on');
    $('rec').textContent = 'Record';
    $('rec').disabled = true;
    try { r.mr.stop(); } catch (e) { /* already stopped */ }
    r.stream.getTracks().forEach(function (t) { t.stop(); });
    r.ctx.close();
    status('Working…');
  }

  function finish(blob) {
    var AC = window.AudioContext || window.webkitAudioContext;
    var ctx = new AC();
    blob.arrayBuffer().then(function (ab) {
      return new Promise(function (res, rej) { ctx.decodeAudioData(ab, res, rej); });
    }).then(function (buf) {
      ctx.close();
      var ch = buf.getChannelData(0);
      if (buf.duration < 0.8) throw new Error('That was too short. Say the whole sentence.');
      return toRate(ch.slice(0, Math.min(ch.length, Math.round(11.5 * buf.sampleRate))), buf.sampleRate, 16000);
    }).then(function (pcm) {
      send(wavBlob(pcm, 16000));
    }).catch(function (e) {
      $('rec').disabled = false;
      status(e && e.message ? e.message : 'That recording couldn’t be read. Please try again.');
    });
  }

  function post(path, wav) {
    return T.api(path, { method: 'POST', body: wav, headers: { 'Content-Type': 'audio/wav' } })
      .then(function (r) { return { ok: true, data: r }; }, function (e) { return { ok: false, error: e }; });
  }

  function send(wav) {
    var out = $('try-out');
    out.hidden = false;
    $('try-transcript').textContent = 'Writing it down…';
    $('try-spark').textContent = '';
    $('try-reader').textContent = 'Listening…';
    $('contour-try').innerHTML = '';
    $('verdict').textContent = '';
    lastTry = { reader: null, spark: null, picked: null };
    renderWhich();
    var a = post('/api/phaedrus/listen', wav).then(function (r) {
      if (!r.ok) { $('try-reader').textContent = r.error.message; return; }
      lastTry.reader = r.data.reader.guess;
      $('try-reader').innerHTML = '';
      $('try-reader').appendChild(h('span', {}, ['It heard the most stress on ', h('b', { text: '“' + r.data.reader.word + '”' }), '.']));
      drawContour($('contour-try'), r.data.contour, { title: 'Your recording' });
    });
    var b = post('/api/phaedrus/read', wav).then(function (r) {
      if (!r.ok) {
        $('try-transcript').textContent = '(not written down)';
        $('try-spark').textContent = r.error.message;
        return;
      }
      var d = r.data;
      $('try-transcript').innerHTML = '';
      markedTranscript(d.transcript || '(nothing heard)').forEach(function (n) {
        $('try-transcript').appendChild(typeof n === 'string' ? document.createTextNode(n) : n);
      });
      if (d.spark) {
        lastTry.spark = d.spark.guess;
        $('try-spark').innerHTML = '';
        $('try-spark').appendChild(h('span', {}, ['From these words alone, Muse Spark guessed you meant: ',
          h('b', { text: d.spark.gloss || 'no answer' }), d.spark.word ? ' (stress on “' + d.spark.word + '”)' : '']));
      } else {
        $('try-spark').textContent = d.note || '';
      }
      if (d.capitalised && d.capitalised.length) {
        $('try-spark').appendChild(h('span', { text: ' Voice Transcribe wrote ' + d.capitalised.join(', ') +
          ' in capitals: the writing kept a trace of your voice.' }));
      }
    });
    Promise.all([a, b]).then(function () {
      $('rec').disabled = false;
      status('Done. Tell us which word you stressed, or record again.');
      verdict();
    });
  }

  function renderWhich() {
    var row = $('which-row');
    row.innerHTML = '';
    D.words.forEach(function (w, k) {
      var b = h('button', { type: 'button', 'aria-pressed': 'false', text: w });
      b.addEventListener('click', function () {
        lastTry.picked = k;
        Array.prototype.forEach.call(row.children, function (x, i) { x.setAttribute('aria-pressed', String(i === k)); });
        verdict();
      });
      row.appendChild(b);
    });
  }

  function verdict() {
    var v = $('verdict');
    if (!lastTry || lastTry.picked == null) { v.textContent = ''; return; }
    var k = lastTry.picked, parts = ['You stressed “' + D.words[k] + '”: ' + D.meanings[k].gloss];
    if (lastTry.spark != null) parts.push('Muse Spark, reading, was ' + (lastTry.spark === k ? 'right.' : 'wrong (it guessed “' + D.words[lastTry.spark] + '”).'));
    if (lastTry.reader != null) parts.push('The prosody reader, listening, was ' + (lastTry.reader === k ? 'right.' : 'wrong (it heard “' + D.words[lastTry.reader] + '”).'));
    v.textContent = parts.join(' ');
  }

  function setupRecorder() {
    var btn = $('rec');
    if (!canRecord()) {
      btn.disabled = true;
      status('This browser can’t record here. The seven recordings above still work.');
      return;
    }
    btn.addEventListener('click', function () { if (rec) stopRec(); else start(); });
    T.api('/api/phaedrus/status').then(function (st) {
      if (!st.enabled) status('Writing down and Muse Spark’s guess are off on this server; the prosody reader still works. Press Record.');
    }).catch(function () {});
  }

  // --- method notes --------------------------------------------------------------------------------------------

  function method() {
    var sh = D.shadow;
    var rt = sh.retest;
    $('m-shadow').textContent = sh.exact + ' of ' + sh.clips + ' transcripts were exactly “' + D.sentence + '”, and ' + sh.same_words +
      ' had exactly its words. The rest repeated a word (“I never never said…”, “II never said…”) or dropped a capital or the full stop. ' +
      'Those slips came with every stressed word and with the neutral readings too.' + (rt ? ' Transcribed a second time, the same ' +
      'recordings came out differently: ' + rt.identical_to_first + ' of ' + rt.clips + ' transcripts matched the first exactly, and a ' +
      'repeated word came back on the same recording only ' + rt.word_changes[2] + ' times in ' + rt.word_changes[0] + '. They are the ' +
      'transcriber’s noise, not traces of the stress.' : '');
    var v = [];
    v.push('The shadow: ' + (sh.passes ? 'passed.' : 'failed as written: we predicted the same words for nearly every voice, and stray words broke that in ' +
      (sh.voices - sh.voices_same_words) + ' of ' + sh.voices + ' voices.'));
    v.push('Spark at chance from transcripts: ' + (D.spark.transcript.passes ? 'passed.' : 'failed.'));
    v.push('Spark with CAPITALS and italics at 80% or more: ' + (D.spark.caps.acc >= 0.8 && D.spark.italics.acc >= 0.8 ? 'passed.' : 'failed.'));
    v.push('The prosody reader: ' + (D.reader.passes ? 'passed.' : 'failed.') + ' After the main run a test found its pitch tracker ' +
      'could read a steady high voice an octave low; we fixed that, and it changed one guess (79 of 91 right before, 80 after).');
    $('m-verdicts').textContent = v.join(' ');
  }

  function init(d) {
    D = d;
    renderVoices();
    renderCards();
    renderTranscripts();
    renderAnswer();
    bars();
    grids();
    drawContour($('contour-demo'), D.voices[0].clips[0].contour, { truth: 0, title: titleFor(0) });
    method();
    setupRecorder();
    var lastW = window.innerWidth, timer = 0;
    window.addEventListener('resize', function () {  // charts are drawn at their container's width: redraw on resize
      clearTimeout(timer);
      timer = setTimeout(function () {
        if (Math.abs(window.innerWidth - lastW) < 40) return;
        lastW = window.innerWidth;
        bars();
        Object.keys(lastContour).forEach(function (id) { drawContour($(id), lastContour[id][0], lastContour[id][1]); });
      }, 200);
    });
  }

  T.api('/api/plato/phaedrus').then(init).catch(function (e) {
    var el = $('load-error');
    el.hidden = false;
    el.textContent = e.message || 'The results couldn’t be loaded.';
  });
  void REDUCED;
})();
