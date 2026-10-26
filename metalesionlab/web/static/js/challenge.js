/* You vs. the AI: name 10 pictures, then compare with Muse Glimmer's recorded answers and look inside it.
   Typed answers are scored by /api/challenge/score: rules and cached judgments only, no Meta API calls.
   Spoken answers go to the Scorer's /api/score/naming (Muse Voice Transcribe; per-visitor daily limit). */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var LIMIT_S = 15, LENS_FROM = 36, LAYERS = 52;
  var SILENCE_MS = 1300, ONSET_RMS = 0.035;
  var LANG_NAMES = { en: 'English', es: 'Spanish' };
  var FRIENDLY = {
    Correct: 'right', Semantic: 'related meaning', Formal: 'similar sound', Mixed: 'similar meaning and sound',
    Nonword: 'not a word, similar sound', Neologism: 'not a word', Unrelated: 'a different word',
    Description: 'described it', NoResponse: 'no answer', Visual: 'looks similar'
  };
  var G = { lang: 'en', mode: 'type', data: null, loading: null, i: -1, answers: [], running: false,
            tick: null, t0: 0, firstKey: null, voiceOK: false, voiceWhy: '', remaining: null, rec: {} };
  function $(id) { return document.getElementById(id); }
  function show(id) { ['intro', 'play', 'wait', 'results'].forEach(function (s) { $(s).hidden = s !== id; }); }
  function quote(s) { return '“' + s + '”'; }
  function now() { return performance.now(); }
  function norm(w) { return String(w || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-zñ]/g, ''); }
  function matches(top, word) {
    var a = norm(top), b = norm(word);
    return a.length >= 2 && (b.indexOf(a) === 0 || a.indexOf(b) === 0);
  }
  function secs(ms) { return ms == null ? '–' : (ms / 1000).toFixed(1) + ' s'; }
  function median(xs) {
    xs = xs.filter(function (x) { return x != null; }).sort(function (a, b) { return a - b; });
    if (!xs.length) return null;
    var m = Math.floor(xs.length / 2);
    return xs.length % 2 ? xs[m] : (xs[m - 1] + xs[m]) / 2;
  }
  function track(e) { if (window.console && e) console.info('challenge:', e.message || e); }

  // --- loading -------------------------------------------------------------------------------
  function load(lang) {
    G.lang = lang;
    G.data = null;
    $('start-btn').disabled = true;
    $('load-state').textContent = 'Loading the pictures…';
    var p = G.loading = T.api('/api/challenge?lang=' + lang).then(function (d) {
      if (p !== G.loading) return;
      G.data = d;
      d.items.forEach(function (it) { var im = new Image(); im.src = it.image; });
      $('start-btn').disabled = false;
      $('load-state').textContent = d.items.length + ' pictures ready.';
      var note = $('sample-note');
      if (d.sample) {
        note.hidden = false;
        note.textContent = 'Sample data: the AI answers shown after the game are illustrative, not real model output, until real runs are on this server.';
      } else if (!d.ai_summary) {
        note.hidden = false;
        note.textContent = 'The AI’s answers for these pictures aren’t on this server yet, so you’ll see your own results only.';
      } else note.hidden = true;
    }).catch(function (e) {
      if (p !== G.loading) return;
      $('load-state').textContent = e.message || 'Couldn’t load the game.';
    });
    return p;
  }

  function setSeg(seg, attr, value) {
    seg.querySelectorAll('button').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute(attr) === value)); });
  }

  function voiceCheck() {
    var canRecord = !!(window.MediaRecorder && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    return T.status().then(function (st) {
      var f = st && st.features || {};
      G.remaining = st && st.limits && st.limits.score ? st.limits.score.remaining : null;
      if (!canRecord) G.voiceWhy = 'This browser can’t record audio here, so typing is the way to play.';
      else if (!f.audio || !f.meta_api) G.voiceWhy = 'Speaking isn’t switched on for this server, so typing is the way to play.';
      else if (G.remaining != null && G.remaining < 10) G.voiceWhy = 'You’ve used today’s spoken answers on this site. Typing still works.';
      else G.voiceWhy = '';
      G.voiceOK = !G.voiceWhy;
      var btn = document.querySelector('#mode-seg [data-mode="voice"]');
      btn.disabled = !G.voiceOK;
      if (!G.voiceOK && G.mode === 'voice') setMode('type');
      modeHint();
    });
  }
  function setMode(mode) {
    G.mode = mode;
    setSeg($('mode-seg'), 'data-mode', mode);
    modeHint();
  }
  function modeHint() {
    $('mode-hint').textContent = G.mode === 'voice'
      ? 'Your browser will ask to use the microphone. Say the name, and the next picture comes after a short pause (or press Next).'
      : (G.voiceWhy && !G.voiceOK ? G.voiceWhy : 'Type the name and press Enter. Spelling counts, but “a” and plurals are fine.');
  }

  // --- the run -------------------------------------------------------------------------------
  function start() {
    if (!G.data) return;
    G.answers = G.data.items.map(function (it) { return { word: it.word, item: it.item, response: '', time: null, result: null, pending: null }; });
    G.i = -1;
    var ready = G.mode === 'voice' ? micOn() : Promise.resolve();
    ready.then(function () {
      G.running = true;
      show('play');
      $('typed').hidden = G.mode === 'voice';
      $('voice').hidden = G.mode !== 'voice';
      $('main').scrollIntoView({ block: 'start' });
      next();
    }).catch(function (e) {
      T.toast(e && e.name === 'NotAllowedError' ? 'Microphone access was blocked, so let’s play by typing.' : 'Couldn’t start the microphone, so let’s play by typing.', 'error');
      setMode('type');
      start();
    });
  }

  function next() {
    G.i += 1;
    if (G.i >= G.answers.length) return finish();
    var it = G.data.items[G.i], pic = $('pic');
    $('progress').textContent = 'Picture ' + (G.i + 1) + ' of ' + G.answers.length;
    pic.alt = 'Picture ' + (G.i + 1) + ' of ' + G.answers.length;
    pic.src = it.image;
    var shown = pic.decode ? pic.decode().catch(function () {}) : Promise.resolve();
    $('answer').value = '';
    G.firstKey = null;
    shown.then(function () {
      if (!G.running) return;
      G.t0 = now();
      startClock();
      if (G.mode === 'voice') clipStart(); else $('answer').focus({ preventScroll: true });
    });
  }

  function startClock() {
    clearInterval(G.tick);
    var bar = $('timer-bar'), clock = $('clock');
    function step() {
      var left = Math.max(0, LIMIT_S - (now() - G.t0) / 1000);
      bar.style.width = (100 * left / LIMIT_S) + '%';
      bar.classList.toggle('low', left < 4);
      clock.textContent = Math.ceil(left) + ' s';
      if (left <= 0) timeUp();
    }
    step();
    G.tick = setInterval(step, 100);
  }

  function timeUp() {
    clearInterval(G.tick);
    if (G.mode === 'voice') clipStop('time');
    else record($('answer').value, $('answer').value.trim() ? LIMIT_S * 1000 : null);
  }

  function record(response, ms) {
    clearInterval(G.tick);
    var a = G.answers[G.i];
    if (!a || a.done) return;
    a.done = true;
    a.response = String(response || '').trim();
    a.time = a.response ? ms : null;
    a.firstKey = G.firstKey;
    next();
  }

  function skip() {
    if (G.mode === 'voice') clipStop('skip'); else record('', null);
  }

  // --- voice ---------------------------------------------------------------------------------
  function pickMime() {
    var c = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'];
    for (var i = 0; i < c.length; i++) if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(c[i])) return c[i];
    return '';
  }
  function ext(type) { return /mp4|m4a|aac/.test(type) ? '.m4a' : /ogg/.test(type) ? '.ogg' : /wav/.test(type) ? '.wav' : '.webm'; }

  function micOn() {
    var r = G.rec;
    if (r.stream) return Promise.resolve();
    return navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }).then(function (stream) {
      r.stream = stream;
      r.mime = pickMime();
      try {
        var Ctx = window.AudioContext || window.webkitAudioContext;
        r.ctx = new Ctx();
        r.analyser = r.ctx.createAnalyser();
        r.analyser.fftSize = 1024;
        r.ctx.createMediaStreamSource(stream).connect(r.analyser);
        r.buf = new Float32Array(r.analyser.fftSize);
      } catch (e) { r.analyser = null; }
    });
  }
  function micOff() {
    var r = G.rec;
    if (r.stream) r.stream.getTracks().forEach(function (t) { t.stop(); });
    if (r.ctx && r.ctx.close) r.ctx.close().catch(function () {});
    G.rec = {};
  }

  function clipStart() {
    var r = G.rec;
    r.chunks = [];
    r.onset = null;
    r.quietSince = null;
    r.recorder = new MediaRecorder(r.stream, r.mime ? { mimeType: r.mime } : undefined);
    r.recorder.ondataavailable = function (e) { if (e.data && e.data.size) r.chunks.push(e.data); };
    r.recorder.start();
    r.started = now();
    if (r.ctx && r.ctx.state === 'suspended') r.ctx.resume();
    $('voice-status').textContent = 'Listening: say its name';
    $('voice-next').disabled = false;
    cancelAnimationFrame(r.raf);
    (function listen() {
      if (!r.recorder || r.recorder.state !== 'recording') return;
      if (r.analyser) {
        r.analyser.getFloatTimeDomainData(r.buf);
        var sum = 0;
        for (var i = 0; i < r.buf.length; i++) sum += r.buf[i] * r.buf[i];
        var rms = Math.sqrt(sum / r.buf.length), t = now();
        $('level').style.width = Math.min(100, rms * 600) + '%';
        if (rms > ONSET_RMS) {
          if (r.onset == null) { r.onset = t - G.t0; $('voice-status').textContent = 'Heard you…'; }
          r.quietSince = null;
        } else if (r.onset != null) {
          if (r.quietSince == null) r.quietSince = t;
          else if (t - r.quietSince > SILENCE_MS) { clipStop('pause'); return; }
        }
      }
      r.raf = requestAnimationFrame(listen);
    })();
  }

  function clipStop(why) {
    var r = G.rec, a = G.answers[G.i];
    clearInterval(G.tick);
    cancelAnimationFrame(r.raf);
    $('voice-next').disabled = true;
    if (!a || a.done || !r.recorder) return;
    a.done = true;
    var rec = r.recorder, onset = r.onset, stoppedAt = now() - G.t0;
    r.recorder = null;
    var blob = new Promise(function (resolve) {
      rec.onstop = function () { resolve(new Blob(r.chunks, { type: rec.mimeType || r.mime || 'audio/webm' })); };
      if (rec.state !== 'inactive') rec.stop(); else resolve(null);
    });
    a.time = why === 'skip' ? null : (onset != null ? onset : stoppedAt);
    a.voice = true;
    a.pending = why === 'skip' ? Promise.resolve(null) : blob.then(function (b) { return upload(a, b); });
    next();
  }

  function upload(a, blob) {
    if (!blob || !blob.size) return null;
    var fd = new FormData();
    fd.append('audio', blob, 'clip' + ext(blob.type));
    fd.append('target', a.word);
    fd.append('lang', G.lang);
    fd.append('set_id', G.data.set);
    fd.append('item', String(a.item));
    fd.append('second_rater', 'false');
    return T.api('/api/score/naming', { method: 'POST', body: fd }).then(function (res) {
      a.response = (res.transcript || '').trim();
      a.result = { code: T.normCode(res.code), correct: T.normCode(res.code) === 'Correct', scored: res.scored_response };
      if (!a.response) a.time = null;
    }).catch(function (e) {
      a.error = e.message || 'Couldn’t score this answer.';
    });
  }

  // --- scoring and results ---------------------------------------------------------------------
  function finish() {
    G.running = false;
    clearInterval(G.tick);
    show('wait');
    $('wait-text').textContent = G.mode === 'voice' ? 'Writing down and scoring your answers…' : 'Scoring your answers…';
    var done;
    if (G.mode === 'voice') {
      done = Promise.all(G.answers.map(function (a) { return a.pending; })).then(function () {
        micOff();
        G.answers.forEach(function (a) {
          if (!a.result && !a.error) a.result = { code: 'NoResponse', correct: false };
        });
      });
    } else {
      done = T.api('/api/challenge/score', { method: 'POST', json: { lang: G.lang, answers: G.answers.map(function (a) { return { word: a.word, response: a.response }; }) } })
        .then(function (res) {
          res.results.forEach(function (r, k) {
            G.answers[k].result = { code: T.normCode(r.code), correct: r.correct, scored: r.scored_response, meaningChecked: r.meaning_checked };
          });
        }).catch(function (e) {
          G.answers.forEach(function (a) { a.error = e.message || 'Couldn’t score the answers.'; });
        });
    }
    done.then(renderResults).catch(function (e) { track(e); renderResults(); });
  }

  function aiCount() {
    var s = G.data.ai_summary;
    return s && s.n ? s : null;
  }
  function myCount() {
    return G.answers.filter(function (a) { return a.result && a.result.correct; }).length;
  }

  function renderResults() {
    show('results');
    var mine = myCount(), n = G.answers.length, ai = aiCount();
    var med = median(G.answers.map(function (a) { return a.result && a.result.correct ? a.time : null; }));
    var score = $('score');
    score.innerHTML = '';
    score.appendChild(h('div', { class: 'cg-stat cg-stat-me' }, [
      h('span', { class: 'cg-stat-label', text: 'You' }),
      h('span', { class: 'cg-stat-num' }, [String(mine), h('small', { text: ' of ' + n })]),
      h('span', { class: 'cg-stat-sub', text: med != null ? 'Median time on right answers: ' + secs(med) : 'No right answers timed' })
    ]));
    score.appendChild(h('div', { class: 'cg-vs', 'aria-hidden': 'true', text: 'vs.' }));
    score.appendChild(h('div', { class: 'cg-stat cg-stat-ai' }, ai ? [
      h('span', { class: 'cg-stat-label', text: G.data.model + (G.data.sample ? ' (sample)' : '') }),
      h('span', { class: 'cg-stat-num' }, [String(ai.correct), h('small', { text: ' of ' + ai.n })]),
      h('span', { class: 'cg-stat-sub', text: ai.run_seconds && ai.run_n ? 'Not a fair race: it looked at all ' + ai.run_n + ' demo pictures at once on one GPU, in ' + Math.round(ai.run_seconds) + ' s.' : 'Recorded ahead of time.' })
    ] : [h('span', { class: 'cg-stat-label', text: 'The AI' }), h('span', { class: 'cg-stat-sub', text: 'Its answers for these pictures aren’t on this server yet.' })]));
    var errs = G.answers.filter(function (a) { return a.error; });
    if (errs.length) score.appendChild(h('p', { class: 'note note-warn cg-errs', text: errs.length + ' answer' + (errs.length > 1 ? 's' : '') + ' couldn’t be scored: ' + errs[0].error }));

    renderTable();
    renderInside();
    renderShare(mine, n, ai, med);
    $('other-lang-btn').textContent = G.lang === 'en' ? 'Play in Spanish' : 'Play in English';
    $('results').scrollIntoView({ block: 'start' });
    $('main').focus({ preventScroll: true });
  }

  function mark(ok) { return h('span', { class: 'cg-mark ' + (ok ? 'ok' : 'no'), 'aria-label': ok ? 'right' : 'not right' }, ok ? '✓' : '✗'); }

  function renderTable() {
    var tb = $('cg-table');
    tb.innerHTML = '';
    tb.appendChild(h('thead', null, h('tr', null, [
      h('th', { scope: 'col', text: 'Picture' }), h('th', { scope: 'col', text: 'You' }), h('th', { scope: 'col', text: G.data.model })
    ])));
    var body = h('tbody');
    G.data.items.forEach(function (it, k) {
      var a = G.answers[k], r = a.result || {}, ai = it.ai;
      var you = a.error ? [h('span', { class: 'muted', text: 'not scored' })]
        : [mark(r.correct), ' ', a.response ? h('b', { text: a.response }) : h('span', { class: 'muted', text: 'no answer' }),
           !r.correct && a.response ? h('span', { class: 'cg-why', text: FRIENDLY[r.code] || r.code }) : null,
           r.correct && a.time != null ? h('span', { class: 'cg-time mono', text: secs(a.time) }) : null];
      var them = ai ? [mark(ai.code === 'Correct'), ' ', h('b', { text: ai.said || '…' }),
                       ai.code !== 'Correct' ? h('span', { class: 'cg-why', text: FRIENDLY[ai.code] || ai.code }) : null]
        : [h('span', { class: 'muted', text: '–' })];
      body.appendChild(h('tr', null, [
        h('td', { class: 'cg-pic-cell' }, [h('img', { src: it.image, alt: '', width: 64, height: 48, loading: 'lazy' }), h('span', { text: it.word })]),
        h('td', null, h('div', { class: 'cg-cell' }, you)),
        h('td', null, h('div', { class: 'cg-cell' }, them))
      ]));
    });
    tb.appendChild(body);
    $('table-meta').textContent = LANG_NAMES[G.lang] + ' pictures' + (G.mode === 'voice' ? ' · spoken' : ' · typed');
  }

  // --- inside the AI -----------------------------------------------------------------------------
  function renderInside() {
    var ins = G.data.inside, box = $('inside');
    box.hidden = !ins;
    if (!ins) return;
    var dmg = ins.damage, set = {};
    (dmg.layers || []).forEach(function (l) { set[l] = true; });
    var word = ins.word;
    $('inside-pic').src = ins.image;
    $('inside-pic').alt = 'The ' + word + ' picture';

    var first = null;
    for (var l = 1; l <= LAYERS; l++) if (matches(ins.intact.top[l - 1], word)) { first = l; break; }
    var lostIn = (dmg.layers || []).filter(function (L) { return matches(ins.intact.top[L - 1], word) && !matches(ins.damaged.top[L - 1], word); });
    var said = ins.damaged.said || '';
    var tip = said && norm(said).length >= 2 && norm(word).indexOf(norm(said)) === 0 && norm(said) !== norm(word);
    var parts = [];
    parts.push('This is Glimmer’s word lens for the ' + word + ' picture: its top guess after each of its ' + LAYERS + ' layers.');
    if (first) parts.push('Intact, the right word reaches first place at layer ' + first + '.');
    parts.push('Then we damaged it: ' + dmg.plain.charAt(0).toLowerCase() + dmg.plain.slice(1) + ' (orange).');
    if (lostIn.length) parts.push('In ' + lostIn.length + ' of those ' + dmg.layers.length + ' layers the right word drops out of first place.');
    parts.push(tip ? 'Out came only ' + quote(said) + ': the start of the word, but not the rest. The tip of the tongue.'
      : 'Out came ' + (said ? quote(said) : 'nothing') + ' (' + (FRIENDLY[ins.damaged.code] || ins.damaged.code) + ').');
    if (dmg.correct != null && dmg.n) {
      parts.push(dmg.accuracy >= 70 ? 'The damage is mild: the same model still named ' + dmg.correct + ' of ' + dmg.n + ' demo pictures.'
        : 'With this damage the model named ' + dmg.correct + ' of ' + dmg.n + ' demo pictures.');
    }
    if (G.data.sample) parts.push('(Sample data: illustrative.)');
    $('inside-text').textContent = parts.join(' ');

    var wrap = $('lens-wrap');
    wrap.innerHTML = '';
    var table = h('table', { class: 'cg-lens' });
    table.appendChild(h('caption', { class: 'sr-only', text: 'Top guess at layers ' + LENS_FROM + ' to ' + LAYERS + ', intact and damaged. Damaged layers: ' + (dmg.layers || []).join(', ') }));
    var head = [h('th', { scope: 'col', text: 'Layer' })];
    for (var c = LENS_FROM; c <= LAYERS; c++) head.push(h('th', { scope: 'col', class: set[c] ? 'dmg' : null, text: String(c) }));
    table.appendChild(h('thead', null, h('tr', null, head)));
    var tb = h('tbody');
    [['Intact', ins.intact], ['Damaged', ins.damaged]].forEach(function (row) {
      var cells = [h('th', { scope: 'row', class: 'row-' + row[0].toLowerCase(), text: row[0] })];
      for (var L = LENS_FROM; L <= LAYERS; L++) {
        var top = row[1].top[L - 1], p = Math.max(0, Math.min(1, row[1].p[L - 1] || 0));
        var cell = h('td', { class: (set[L] ? 'dmg ' : '') + (matches(top, word) ? 'hit' : ''), title: 'Layer ' + L + ': p(' + word + ') = ' + p.toFixed(2) }, top);
        cell.style.setProperty('--p', p.toFixed(3));
        if (p > 0.45) cell.classList.add('dark');
        cells.push(cell);
      }
      tb.appendChild(h('tr', null, cells));
    });
    table.appendChild(tb);
    wrap.appendChild(table);

    var saidBox = $('inside-said');
    saidBox.innerHTML = '';
    saidBox.appendChild(h('div', { class: 'cg-said-one intact' }, [h('span', { text: 'Intact, it said' }), h('b', { text: quote(ins.intact.said) })]));
    saidBox.appendChild(h('div', { class: 'cg-said-one damaged' }, [h('span', { text: 'Damaged, it said' }), h('b', { text: quote(ins.damaged.said || '…') })]));
    $('inside-key').textContent = 'Blue shading: how likely the right word is at that layer. Bold: the top guess is (the start of) the right word. Orange columns: the damaged layers. Measured ahead of time; the damage is switched on and off with code, and the model itself is never changed.';
  }

  // --- share card ------------------------------------------------------------------------------
  var cardBlob = null;
  function renderShare(mine, n, ai, med) {
    var W = 1200, H = 630, cv = document.createElement('canvas');
    cv.width = W; cv.height = H;
    var x = cv.getContext('2d');
    var fontsReady = document.fonts && document.fonts.load ? Promise.all([
      document.fonts.load('700 64px "IBM Plex Sans"'), document.fonts.load('500 24px "IBM Plex Mono"')]).catch(function () {}) : Promise.resolve();
    fontsReady.then(function () {
      x.fillStyle = '#111827'; x.fillRect(0, 0, W, H);
      x.fillStyle = '#C2410C'; x.fillRect(0, 0, W, 10);
      x.fillStyle = '#FDBA74'; x.font = '500 24px "IBM Plex Mono", monospace';
      x.fillText('TIPPA LINGUA', 72, 92);
      x.fillStyle = '#F9FAFB'; x.font = '700 76px "IBM Plex Sans", sans-serif';
      x.fillText('You vs. the AI', 72, 182);
      x.fillStyle = '#D1D5DB'; x.font = '400 28px "IBM Plex Sans", sans-serif';
      x.fillText('Name 10 pictures. ' + LANG_NAMES[G.lang] + '.', 72, 232);
      function row(y, label, results, color, total) {
        x.fillStyle = '#F9FAFB'; x.font = '600 34px "IBM Plex Sans", sans-serif';
        x.fillText(label, 72, y + 40);
        results.forEach(function (ok, k) {
          var sx = 400 + k * 58;
          x.lineWidth = 3;
          if (ok) { x.fillStyle = color; x.fillRect(sx, y, 46, 46); }
          else { x.strokeStyle = '#4B5563'; x.strokeRect(sx + 1.5, y + 1.5, 43, 43); }
        });
        x.fillStyle = '#F9FAFB'; x.font = '700 44px "IBM Plex Sans", sans-serif';
        x.textAlign = 'right';
        x.fillText(total, W - 72, y + 42);
        x.textAlign = 'left';
      }
      row(300, 'Me', G.answers.map(function (a) { return !!(a.result && a.result.correct); }), '#EA580C', mine + '/' + n);
      if (ai) row(380, 'Muse Glimmer', G.data.items.map(function (it) { return !!(it.ai && it.ai.code === 'Correct'); }), '#60A5FA', ai.correct + '/' + ai.n);
      x.fillStyle = '#9CA3AF'; x.font = '400 24px "IBM Plex Sans", sans-serif';
      if (med != null) x.fillText('My median time on right answers: ' + secs(med), 72, 500);
      x.fillStyle = '#E5E7EB'; x.font = '500 26px "IBM Plex Sans", sans-serif';
      x.fillText('The tip-of-the-tongue test, for people and AI.', 72, 568);
      x.fillStyle = '#9CA3AF'; x.font = '400 22px "IBM Plex Mono", monospace';
      x.textAlign = 'right';
      x.fillText(location.host + '/challenge', W - 72, 568);
      x.textAlign = 'left';
      var img = $('card-img');
      img.src = cv.toDataURL('image/png');
      img.alt = 'Result card: You vs. the AI. Me ' + mine + ' of ' + n + (ai ? ', Muse Glimmer ' + ai.correct + ' of ' + ai.n : '') + '.';
      cv.toBlob(function (b) {
        cardBlob = b;
        var file = b && window.File ? new File([b], 'you-vs-the-ai.png', { type: 'image/png' }) : null;
        $('native-share').hidden = !(file && navigator.canShare && navigator.canShare({ files: [file] }));
      }, 'image/png');
    });
    var text = 'I named ' + mine + ' of ' + n + ' pictures' + (ai ? '. Meta’s open AI model Muse Glimmer named ' + ai.correct + ' of ' + ai.n : '') +
      '. Then I watched a word get lost inside the AI. Your turn:';
    var url = location.origin + '/challenge';
    $('x-btn').href = 'https://x.com/intent/tweet?text=' + encodeURIComponent(text) + '&url=' + encodeURIComponent(url);
    G.shareText = text;
    G.shareUrl = url;
  }

  function download() {
    if (!cardBlob) return;
    var a = h('a', { href: URL.createObjectURL(cardBlob), download: 'you-vs-the-ai.png' });
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
  function nativeShare() {
    if (!cardBlob) return;
    var file = new File([cardBlob], 'you-vs-the-ai.png', { type: 'image/png' });
    navigator.share({ files: [file], text: G.shareText + ' ' + G.shareUrl }).catch(function () {});
  }

  // --- wiring ------------------------------------------------------------------------------------
  function quit() {
    G.running = false;
    clearInterval(G.tick);
    if (G.rec.recorder && G.rec.recorder.state !== 'inactive') G.rec.recorder.stop();
    micOff();
    show('intro');
  }

  $('lang-seg').addEventListener('click', function (e) {
    var b = e.target.closest('button[data-lang]');
    if (!b || b.getAttribute('data-lang') === G.lang) return;
    setSeg($('lang-seg'), 'data-lang', b.getAttribute('data-lang'));
    load(b.getAttribute('data-lang'));
  });
  $('mode-seg').addEventListener('click', function (e) {
    var b = e.target.closest('button[data-mode]');
    if (!b || b.disabled) return;
    setMode(b.getAttribute('data-mode'));
  });
  $('start-btn').addEventListener('click', start);
  $('typed').addEventListener('submit', function (e) {
    e.preventDefault();
    if (!G.running) return;
    var v = $('answer').value;
    if (!v.trim()) { $('answer').focus(); return; }
    record(v, now() - G.t0);
  });
  $('answer').addEventListener('input', function () { if (G.firstKey == null) G.firstKey = now() - G.t0; });
  $('voice-next').addEventListener('click', function () { clipStop('next'); });
  $('skip-btn').addEventListener('click', skip);
  $('quit-btn').addEventListener('click', quit);
  $('again-btn').addEventListener('click', function () { show('intro'); start(); });
  $('other-lang-btn').addEventListener('click', function () {
    var other = G.lang === 'en' ? 'es' : 'en';
    setSeg($('lang-seg'), 'data-lang', other);
    show('intro');
    load(other).then(function () { if (G.data) start(); });
  });
  $('download-btn').addEventListener('click', download);
  $('native-share').addEventListener('click', nativeShare);
  document.addEventListener('keydown', function (e) {
    if (!G.running || G.mode !== 'voice') return;
    if ((e.key === 'Enter' || e.key === ' ') && document.activeElement && document.activeElement.tagName !== 'BUTTON') {
      e.preventDefault();
      clipStop('next');
    }
  });

  // The Naming test link shows only once that page exists on this server.
  T.api('/api/pages').then(function (pages) {
    if (pages && pages.assess) document.querySelectorAll('[data-assess-box]').forEach(function (el) { el.hidden = false; });
  }).catch(function () {});

  var urlLang = T.param('lang');
  if (urlLang === 'es') setSeg($('lang-seg'), 'data-lang', 'es');
  load(urlLang === 'es' ? 'es' : 'en');
  voiceCheck();
  modeHint();

  window.TOT.challenge = { state: function () { return G; }, ready: function () { return G.loading; } };
})();
