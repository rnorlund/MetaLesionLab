/* Scorer: give a test by voice (or typed), get every response transcribed and coded, review, export. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var STORE = 'tot-scorer-v1';
  var NAMING_MAX_S = 25, DESCRIPTION_MAX_S = 180, FLUENCY_S = 60;  // the server accepts 30, 240 and 120 s
  var S = {
    status: null, langs: [], sets: [], scenes: [], set: null, items: [],
    rows: [], results: [], running: false, busy: false, idx: 0, nextId: 1,
    rec: { stream: null, recorder: null, chunks: [], mime: '', started: 0, timer: null, limit: 0, onLimit: null }
  };
  function $(id) { return document.getElementById(id); }
  function task() { return $('task').value; }
  function mode() { var el = document.querySelector('input[name="mode"]:checked'); return el ? el.value : 'typed'; }
  function simple(s) { return String(s || '').toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim(); }
  function fmt(s) { s = Math.max(0, Math.floor(s)); return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2); }

  // --- persistence ------------------------------------------------------------------------
  function save() {
    if (S.demo) return;  // the tour's replayed rows are never stored
    var rows = S.rows.map(function (r) {
      var c = Object.assign({}, r);
      delete c.blob; delete c.audioUrl;
      return c;
    });
    try { localStorage.setItem(STORE, JSON.stringify({ rows: rows, results: S.results, speaker: $('speaker').value })); } catch (e) { /* storage off */ }
  }
  function restore() {
    var data = null;
    try { data = JSON.parse(localStorage.getItem(STORE) || 'null'); } catch (e) { data = null; }
    if (!data) return;
    S.rows = (data.rows || []).map(function (r) {
      if (r.status === 'pending') { r.status = 'error'; r.error = 'Interrupted before it was scored.'; }
      return r;
    });
    S.results = data.results || [];
    S.nextId = S.rows.reduce(function (m, r) { return Math.max(m, r.id || 0); }, 0) + 1;
    if (data.speaker) $('speaker').value = data.speaker;
    var n = S.rows.length + S.results.length;
    if (n) {
      var note = $('restored');
      note.hidden = false;
      note.textContent = 'Restored ' + n + ' result' + (n > 1 ? 's' : '') + ' from your last session in this browser. Audio clips aren\'t kept after a reload.';
    }
  }

  // --- status and options -------------------------------------------------------------------
  function refreshStatus() {
    T.status.p = null;
    return T.status().then(function (st) { S.status = st; applyFeatures(); return st; });
  }

  function applyFeatures() {
    var st = S.status, f = st ? st.features : { meta_api: false, audio: false, scorer: false };
    var notes = [];
    var voice = document.querySelector('input[name="mode"][value="voice"]');
    var canRecord = !!(window.MediaRecorder && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    if (!f.audio || !canRecord) {
      voice.disabled = true;
      document.querySelector('input[name="mode"][value="typed"]').checked = true;
      notes.push(!canRecord ? 'This browser can\'t record audio here; typed responses work.'
        : 'Voice scoring turns on when the audio converter is installed on this server. Typed responses work now.');
    } else {
      voice.disabled = false;
    }
    ['description', 'fluency'].forEach(function (t) {
      var opt = $('task').querySelector('option[value="' + t + '"]');
      opt.disabled = !f.scorer;
      opt.textContent = (t === 'description' ? 'Picture description' : 'Category fluency') + (f.scorer ? '' : ' · coming soon');
    });
    if (!f.scorer && task() !== 'naming') { $('task').value = 'naming'; onTask(); }
    var second = $('second');
    second.disabled = !f.scorer;
    if (!f.scorer) {
      second.checked = false;
      $('second-field').lastChild.textContent = ' Second rater (Muse Spark) · coming soon';
    }
    if (!f.meta_api) notes = ['Live scoring is off: this server has no Meta API key. You can still review and export.'];
    var fn = $('feature-note');
    fn.hidden = !notes.length;
    fn.textContent = notes.join(' ');
    $('start-btn').disabled = !f.meta_api || S.running;
    if (st) $('limit-note').textContent = st.limits.score.remaining + ' of ' + st.limits.score.per_day + ' scored responses left today on this demo.';
  }

  function loadSets() {
    return T.api('/api/sets').then(function (sets) {
      S.sets = sets.filter(function (s) { return s.status === 'done' && s.kept > 0; });
      var sel = $('set');
      sel.innerHTML = '';
      if (!S.sets.length) sel.appendChild(h('option', { value: '', text: 'No picture sets yet: build one in Test Studio' }));
      S.sets.forEach(function (s) {
        sel.appendChild(h('option', { value: s.id, text: (s.demo ? 'Demo set' : s.name) + ' · ' + s.kept + ' pictures · ' + T.langName(S.langs, s.lang) }));
      });
      var has = function (id) { return id && S.sets.some(function (s) { return s.id === id; }); };
      var want = T.param('set');
      var demo = has('demo_en') ? 'demo_en' : (S.sets.filter(function (s) { return s.demo; })[0] || {}).id;
      if (has(want)) sel.value = want;
      else if (has(demo)) sel.value = demo;
      return onSet();
    }).catch(function (e) { T.toast(e.message, 'error'); });
  }

  function onSet() {
    var id = $('set').value;
    if (!id) { S.set = null; S.items = []; return Promise.resolve(); }
    return T.api('/api/sets/' + encodeURIComponent(id)).then(function (d) {
      S.set = d;
      S.items = (d.manifest ? d.manifest.items : []).map(function (it, i) { return { index: i, word: it.word, image: it.image, status: it.status }; })
        .filter(function (it) { return it.status === 'kept' && it.image; });
      if (d.lang) $('lang').value = d.lang;
      if (task() === 'naming') $('resp-empty').textContent = S.items.length + ' pictures ready. Press Start test; each response is transcribed, coded and listed here for review.';
    }).catch(function (e) { T.toast(e.message, 'error'); });
  }

  function loadScenes() {
    return T.api('/api/scenes').then(function (scenes) {
      S.scenes = scenes;
      var sel = $('scene');
      sel.innerHTML = '';
      if (!scenes.length) sel.appendChild(h('option', { value: '', text: 'No scenes yet: draw one in Test Studio' }));
      scenes.forEach(function (s) { sel.appendChild(h('option', { value: s.id, text: (s.theme || 'Scene ' + s.id) + ' · ' + (s.content_units || []).length + ' content units' })); });
      var want = T.param('scene');
      if (want) sel.value = want;
    }).catch(function () { /* optional */ });
  }

  function onTask() {
    var t = task();
    $('set-field').hidden = t !== 'naming';
    $('scene-field').hidden = t !== 'description';
    $('category-field').hidden = t !== 'fluency';
    $('second-field').hidden = t !== 'naming';
    $('naming-results').hidden = t !== 'naming';
    $('task-results').hidden = t === 'naming' || !S.results.length;
    $('start-btn').textContent = { naming: 'Start test', description: 'Start describing', fluency: 'Start ' + FLUENCY_S + '-second test' }[t];
    renderSummary();
    renderResults();
  }

  // --- microphone ---------------------------------------------------------------------------
  function pickMime() {
    var c = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'];
    for (var i = 0; i < c.length; i++) if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(c[i])) return c[i];
    return '';
  }
  function ext(type) { return /mp4|m4a|aac/.test(type) ? '.m4a' : /ogg/.test(type) ? '.ogg' : /wav/.test(type) ? '.wav' : '.webm'; }
  function ensureMic() {
    if (S.rec.stream) return Promise.resolve(S.rec.stream);
    return navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }).then(function (stream) {
      S.rec.stream = stream;
      S.rec.mime = pickMime();
      return stream;
    });
  }
  function releaseMic() {
    if (S.rec.stream) S.rec.stream.getTracks().forEach(function (t) { t.stop(); });
    S.rec.stream = null;
  }
  function micError(e) {
    var msg = e && e.name === 'NotAllowedError' ? 'Microphone access was blocked. Allow it in the browser, or switch to Typed responses.'
      : 'Couldn\'t start the microphone (' + (e && e.message || e) + '). You can switch to Typed responses.';
    T.toast(msg, 'error');
  }
  function startClip(limitS, onLimit) {
    var r = S.rec;
    r.chunks = [];
    r.recorder = new MediaRecorder(r.stream, r.mime ? { mimeType: r.mime } : undefined);
    r.recorder.ondataavailable = function (e) { if (e.data && e.data.size) r.chunks.push(e.data); };
    r.recorder.start();
    r.started = Date.now();
    r.limit = limitS || 0;
    r.onLimit = onLimit || null;
    $('stage-rec').hidden = false;
    tick();
    clearInterval(r.timer);
    r.timer = setInterval(tick, 250);
  }
  function tick() {
    var r = S.rec, el = (Date.now() - r.started) / 1000;
    $('stage-timer').textContent = r.limit ? fmt(r.limit - el) + ' left' : fmt(el);
    if (r.limit && el >= r.limit && r.onLimit) { var f = r.onLimit; r.onLimit = null; f(); }
  }
  function stopClip() {
    var r = S.rec;
    clearInterval(r.timer);
    $('stage-rec').hidden = true;
    return new Promise(function (resolve) {
      var rec = r.recorder;
      if (!rec || rec.state === 'inactive') return resolve(null);
      rec.onstop = function () { resolve(new Blob(r.chunks, { type: rec.mimeType || r.mime || 'audio/webm' })); };
      rec.stop();
    });
  }

  // --- stage --------------------------------------------------------------------------------
  function showStage(noScroll) {
    var st = $('stage');
    $('stage-picture').classList.remove('compact');
    st.hidden = false;
    if (!noScroll) st.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  function hideStage() {
    $('stage').hidden = true;
    if (document.fullscreenElement) document.exitFullscreen();
  }
  function setControls(buttons) {
    var c = $('stage-controls');
    c.innerHTML = '';
    buttons.forEach(function (b) { c.appendChild(b); });
    var first = c.querySelector('button:not(.secondary)');
    if (first) first.focus({ preventScroll: true });
  }
  function btn(label, cls, onClick) { return h('button', { type: 'button', class: 'btn ' + (cls || ''), onclick: onClick }, label); }
  function setRunning(on) {
    S.running = on;
    $('start-btn').disabled = on || !(S.status && S.status.features.meta_api);
    $('start-btn').textContent = on ? 'Test in progress…' : { naming: 'Start test', description: 'Start describing', fluency: 'Start ' + FLUENCY_S + '-second test' }[task()];
    ['task', 'set', 'scene', 'lang', 'category'].forEach(function (id) { $(id).disabled = on; });
  }

  $('fullscreen-btn').addEventListener('click', function () {
    if (document.fullscreenElement) document.exitFullscreen();
    else if ($('stage').requestFullscreen) $('stage').requestFullscreen();
  });

  // --- picture naming -----------------------------------------------------------------------
  function startNaming() {
    if (!S.items.length) { T.toast('Choose a picture set with kept pictures first.', 'error'); return; }
    var go = mode() === 'voice' ? ensureMic() : Promise.resolve();
    go.then(function () {
      setRunning(true);
      S.idx = 0;
      $('resp-empty').hidden = true;
      showStage();
      renderNamingItem();
    }).catch(micError);
  }

  function renderNamingItem() {
    var it = S.items[S.idx], voice = mode() === 'voice';
    $('stage-count').textContent = 'Item ' + (S.idx + 1) + ' of ' + S.items.length;
    var pic = $('stage-picture');
    pic.innerHTML = '';
    pic.appendChild(h('img', { src: T.mediaUrl(S.set.id, it.image), alt: 'Picture to name, item ' + (S.idx + 1) }));
    var next = S.items[S.idx + 1];
    if (next) new Image().src = T.mediaUrl(S.set.id, next.image);
    $('stage-typed').hidden = voice;
    $('typed-response').hidden = false;
    $('typed-long').hidden = true;
    var last = S.idx === S.items.length - 1;
    if (voice) {
      setControls([btn(last ? 'Finish' : 'Next picture →', 'btn-record', nextNaming), btn('Redo', 'secondary', redoNaming), btn('End test', 'secondary', endNaming)]);
      $('stage-help').textContent = 'Recording starts with each picture. Press Next (or the space bar) when the speaker has answered. End test stops without scoring this picture.';
      startClip(NAMING_MAX_S, nextNaming);
    } else {
      $('typed-response').value = '';
      setControls([btn(last ? 'Score and finish' : 'Score and next →', 'btn-primary', nextNaming), btn('End test', 'secondary', endNaming)]);
      $('stage-help').textContent = 'Type exactly what was said, including errors. Press Enter for the next picture; leave it empty for no response.';
      $('typed-response').focus({ preventScroll: true });
    }
  }

  function newRow(it) {
    var row = { id: S.nextId++, n: S.rows.length + 1, index: it.index, target: it.word, image: it.image, set: S.set.id,
      lang: $('lang').value, speaker: $('speaker').value.trim(), mode: mode(), status: 'pending', second_on: $('second').checked };
    S.rows.push(row);
    return row;
  }

  function nextNaming() {
    if (S.busy || !S.running) return;
    S.busy = true;
    var row = newRow(S.items[S.idx]);
    if (mode() === 'voice') {
      stopClip().then(function (blob) {
        row.blob = blob;
        row.audioUrl = blob ? URL.createObjectURL(blob) : null;
        uploadAudio(row);
        advance();
      });
    } else {
      row.response = $('typed-response').value.trim();
      submitTyped(row);
      advance();
    }
    renderTable();
  }
  function advance() {
    S.busy = false;
    S.idx++;
    if (S.idx >= S.items.length) finishNaming(); else renderNamingItem();
  }
  function redoNaming() { stopClip().then(function () { startClip(NAMING_MAX_S, nextNaming); T.toast('Recording again.'); }); }
  function endNaming() { stopClip().then(finishNaming); }
  function finishNaming() {
    releaseMic();
    setRunning(false);
    $('stage-count').textContent = '';
    $('stage-typed').hidden = true;
    var pic = $('stage-picture');
    pic.innerHTML = '';
    pic.classList.add('compact');
    pic.appendChild(h('div', { class: 'done' }, [h('h3', { text: 'Test complete' }), h('p', { class: 'muted', text: 'Codes appear in the table below as each response is scored. Review them, then export.' })]));
    $('stage-help').textContent = '';
    setControls([btn('Close', 'btn-dark', hideStage)]);
  }

  function uploadAudio(row) {
    row.status = 'pending';
    row.error = null;
    if (!row.blob) { row.status = 'error'; row.error = 'No audio was recorded.'; renderTable(); return; }
    var fd = new FormData();
    fd.append('audio', row.blob, 'clip' + ext(row.blob.type));
    fd.append('target', row.target);
    fd.append('lang', row.lang);
    fd.append('set_id', row.set);
    fd.append('item', String(row.index));
    fd.append('second_rater', row.second_on ? 'true' : 'false');
    T.api('/api/score/naming', { method: 'POST', body: fd })
      .then(function (res) { applyResult(row, res); })
      .catch(function (e) { failRow(row, e); });
  }
  function submitTyped(row) {
    row.status = 'pending';
    row.error = null;
    T.api('/api/score/naming/text', { method: 'POST', json: { target: row.target, response: row.response || '', lang: row.lang,
      set_id: row.set, item: row.index, second_rater: !!row.second_on } })
      .then(function (res) { applyResult(row, res); })
      .catch(function (e) { failRow(row, e); });
  }
  function applyResult(row, res) {
    row.status = 'done';
    row.response = res.transcript != null ? res.transcript : res.response;
    row.scored = res.scored_response;
    row.code = res.code;
    row.second = res.second;
    row.second_status = res.second_status;
    row.agree = res.agree;
    row.duration = res.duration_s;
    if (!row.reviewer) row.reviewer = res.code;
    row.scored_at = new Date().toISOString();
    save();
    renderTable();
    renderSummary();
    refreshStatus();
  }
  function failRow(row, e) {
    row.status = 'error';
    row.error = e.message;
    save();
    renderTable();
    if (e.status === 429 || e.status === 503) T.toast(e.message, 'error');
  }
  function retry(row) {
    if (row.blob) uploadAudio(row);
    else if (row.mode === 'typed' || row.response != null) submitTyped(row);
    renderTable();
  }

  // --- review table ---------------------------------------------------------------------------
  function codeSelect(row) {
    var sel = h('select', { 'aria-label': 'Reviewer code for item ' + row.n + ', ' + row.target });
    T.ORDER.forEach(function (c) { sel.appendChild(h('option', { value: c, text: T.codeInfo(c).label, selected: c === T.normCode(row.reviewer) })); });
    sel.addEventListener('change', function () {
      row.reviewer = sel.value;
      save();
      renderTable();
      renderSummary();
    });
    return sel;
  }

  function secondCell(row) {
    if (row.status !== 'done') return '';
    if (row.second_status === 'ok' && row.second) {
      var main = row.agree ? h('span', { class: 'agree', text: 'agrees' }) : h('span', { class: 'disagree', text: 'says ' + T.codeInfo(row.second.code).label });
      return h('span', null, [main, row.second.rationale ? h('span', { class: 'rationale', text: row.second.rationale }) : null]);
    }
    var label = { off: 'off', unavailable: 'not available yet', error: 'didn\'t answer' }[row.second_status] || '–';
    return h('span', { class: 'xsmall muted', text: label });
  }

  function renderTable() {
    var body = $('resp-body');
    body.innerHTML = '';
    $('resp-empty').hidden = S.rows.length > 0 || S.running;
    $('resp-table').hidden = !S.rows.length;
    S.rows.forEach(function (row) {
      var heard;
      if (row.status === 'pending') heard = h('span', { class: 'muted' }, [h('span', { class: 'spinner', 'aria-hidden': 'true' }), row.mode === 'voice' ? ' transcribing…' : ' scoring…']);
      else if (row.status === 'error') heard = h('span', null, [h('span', { class: 'xsmall', style: { color: '#7F1D1D' }, text: row.error || 'Failed' }), ' ',
        (row.blob || row.mode === 'typed') ? h('button', { type: 'button', class: 'btn btn-small', onclick: function () { retry(row); } }, 'Retry') : null]);
      else if (!row.response) heard = h('span', { class: 'muted', text: '(nothing)' });
      else if (row.scored != null && simple(row.scored) !== simple(row.response)) {
        heard = h('span', null, [row.response, h('span', { class: 'rationale', text: 'scored as "' + row.scored + '"' + (simple(row.scored) ? '' : ' (nothing)') })]);
      } else heard = row.response;
      var changed = row.status === 'done' && T.normCode(row.reviewer) !== T.normCode(row.code);
      var del = h('button', { type: 'button', class: 'icon-btn', 'aria-label': 'Remove item ' + row.n, title: 'Remove', onclick: function () {
        S.rows = S.rows.filter(function (r) { return r !== row; });
        save(); renderTable(); renderSummary();
      } }, '×');
      body.appendChild(h('tr', { class: changed ? 'changed' : null }, [
        h('td', { class: 'mono muted', text: String(row.n) }),
        h('td', null, row.image ? h('img', { class: 'thumb', src: T.mediaUrl(row.set, row.image, 160), alt: '' }) : null),
        h('td', { class: 'target', text: row.target }),
        h('td', { class: 'heard' }, heard),
        h('td', null, row.status === 'done' ? T.pill(row.code) : null),
        h('td', null, secondCell(row)),
        h('td', null, row.status === 'done' ? codeSelect(row) : null),
        h('td', null, h('div', { class: 'clip-actions' }, [row.audioUrl ? h('audio', { controls: true, src: row.audioUrl, preload: 'none', 'aria-label': 'Recording for item ' + row.n }) : null, del]))
      ]));
    });
    var done = S.rows.filter(function (r) { return r.status === 'done'; });
    var correct = done.filter(function (r) { return T.normCode(r.reviewer) === 'Correct'; }).length;
    var disagree = done.filter(function (r) { return r.second_status === 'ok' && r.agree === false; }).length;
    var speaker = $('speaker').value.trim();
    $('resp-h').textContent = 'Responses' + (speaker ? ' · ' + speaker : '');
    $('resp-meta').textContent = done.length ? correct + ' of ' + done.length + ' correct' + (disagree ? ' · ' + disagree + ' disagreement' + (disagree > 1 ? 's' : '') + ' to review' : '') : '';
  }

  function renderSummary() {
    var box = $('summary');
    box.innerHTML = '';
    if (task() !== 'naming') {
      var n = S.results.filter(function (r) { return r.kind === task(); }).length;
      box.appendChild(h('p', { class: 'small muted', style: { margin: 0 }, text: n ? n + (n === 1 ? ' result' : ' results') + ' above, newest first.' : 'No results yet.' }));
      return;
    }
    var done = S.rows.filter(function (r) { return r.status === 'done'; });
    if (!done.length) { box.appendChild(h('p', { class: 'small muted', style: { margin: 0 }, text: 'No scored responses yet.' })); return; }
    var counts = {};
    done.forEach(function (r) { var c = T.normCode(r.reviewer); counts[c] = (counts[c] || 0) + 1; });
    box.appendChild(T.stackBar(counts, done.length, 'Final codes: ' + T.describeCounts(counts, done.length)));
    box.appendChild(h('div', { style: { height: '10px' } }));
    box.appendChild(T.legend(T.ORDER.filter(function (c) { return counts[c]; }).map(function (c) {
      return c;
    })));
    var lines = T.ORDER.filter(function (c) { return counts[c]; }).map(function (c) { return T.codeInfo(c).label + ' ' + counts[c]; });
    box.appendChild(h('p', { class: 'small', style: { margin: '10px 0 0' }, text: lines.join(' · ') }));
  }

  // --- picture description and category fluency -------------------------------------------------
  function startDescription() {
    var scene = S.scenes.filter(function (s) { return s.id === $('scene').value; })[0];
    if (!scene) { T.toast('Choose a scene first, or draw one in Test Studio.', 'error'); return; }
    var voice = mode() === 'voice';
    (voice ? ensureMic() : Promise.resolve()).then(function () {
      setRunning(true);
      showStage();
      $('stage-count').textContent = 'Describe everything happening in this picture';
      var pic = $('stage-picture');
      pic.innerHTML = '';
      pic.appendChild(h('img', { src: scene.image_url, alt: 'Scene to describe' + (scene.theme ? ': ' + scene.theme : '') }));
      var finish = function (transcript, blob) { scoreTask('description', { scene_id: scene.id, theme: scene.theme || scene.id }, transcript, blob); };
      if (voice) {
        $('stage-typed').hidden = true;
        var stop = function () { stopClip().then(function (blob) { releaseMic(); finish(null, blob); }); };
        setControls([btn('Stop and score', 'btn-record', stop), btn('Cancel', 'secondary', cancelTask)]);
        $('stage-help').textContent = 'Recording. Up to ' + DESCRIPTION_MAX_S / 60 + ' minutes; it stops on its own at the limit.';
        startClip(DESCRIPTION_MAX_S, stop);
      } else {
        showLongTyped('Type the description exactly as spoken');
        setControls([btn('Score description', 'btn-primary', function () { finish($('typed-long').value, null); }), btn('Cancel', 'secondary', cancelTask)]);
        $('stage-help').textContent = 'Typed descriptions have no timing, so words per minute isn\'t computed.';
      }
    }).catch(micError);
  }

  function startFluency() {
    var category = $('category').value.trim();
    if (!category) { T.toast('Enter a category, e.g. animals.', 'error'); return; }
    var voice = mode() === 'voice';
    (voice ? ensureMic() : Promise.resolve()).then(function () {
      setRunning(true);
      showStage();
      $('stage-count').textContent = 'Category fluency · ' + FLUENCY_S + ' seconds';
      var pic = $('stage-picture');
      pic.innerHTML = '';
      pic.appendChild(h('div', { class: 'category' }, [h('small', { text: 'Name as many as you can' }), category]));
      var finish = function (transcript, blob) { scoreTask('fluency', { category: category }, transcript, blob); };
      if (voice) {
        $('stage-typed').hidden = true;
        var go = function () {
          var stop = function () { stopClip().then(function (blob) { releaseMic(); finish(null, blob); }); };
          setControls([btn('Stop early and score', 'btn-record', stop), btn('Cancel', 'secondary', cancelTask)]);
          $('stage-help').textContent = 'Recording. It stops on its own after ' + FLUENCY_S + ' seconds.';
          startClip(FLUENCY_S, stop);
        };
        setControls([btn('Start the ' + FLUENCY_S + ' seconds', 'btn-record', go), btn('Cancel', 'secondary', cancelTask)]);
        $('stage-help').textContent = 'Read the category aloud to the speaker, then start the timer.';
      } else {
        showLongTyped('Type the words in the order said, separated by commas');
        setControls([btn('Score list', 'btn-primary', function () { finish($('typed-long').value, null); }), btn('Cancel', 'secondary', cancelTask)]);
        $('stage-help').textContent = 'Keep repetitions and wrong-category words: they are counted, not removed.';
      }
    }).catch(micError);
  }

  function showLongTyped(placeholder) {
    $('stage-typed').hidden = false;
    $('typed-response').hidden = true;
    var ta = $('typed-long');
    ta.hidden = false;
    ta.value = '';
    ta.placeholder = placeholder;
    ta.setAttribute('aria-label', placeholder);
    setTimeout(function () { ta.focus({ preventScroll: true }); }, 0);
  }

  function cancelTask() {
    stopClip().then(function () { releaseMic(); setRunning(false); hideStage(); });
  }

  function scoreTask(kind, info, transcript, blob) {
    if (!blob && !(transcript || '').trim()) { T.toast('Nothing to score yet.', 'error'); return; }
    var fd = new FormData();
    fd.append('lang', $('lang').value);
    if (kind === 'description') fd.append('scene_id', info.scene_id); else fd.append('category', info.category);
    if (blob) fd.append('audio', blob, 'clip' + ext(blob.type)); else fd.append('transcript', transcript);
    setControls([]);
    $('stage-typed').hidden = true;
    $('stage-help').innerHTML = '<span class="spinner" aria-hidden="true"></span> ' + (blob ? 'Transcribing and scoring…' : 'Scoring…');
    T.api('/api/score/' + kind, { method: 'POST', body: fd }).then(function (res) {
      S.results.unshift(Object.assign({ kind: kind, speaker: $('speaker').value.trim(), lang: $('lang').value, at: new Date().toISOString() }, info, res));
      save();
      setRunning(false);
      hideStage();
      $('task-results').hidden = false;
      renderResults();
      renderSummary();
      refreshStatus();
      $('task-results').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }).catch(function (e) {
      T.toast(e.message, 'error');
      setRunning(false);
      hideStage();
    });
  }

  function stat(value, label) { return h('div', { class: 'stat' }, [h('b', { text: value == null ? '–' : String(value) }), h('span', { text: label })]); }
  function chips(list, cls) { return h('div', { class: 'chips-list ' + (cls || '') }, (list || []).map(function (x) { return h('span', { text: typeof x === 'string' ? x : JSON.stringify(x) }); })); }

  var FLUENCY_STATUS = { valid: 'Valid', repetition: 'Repetition', intrusion: 'Intrusion', comment: 'Not an item' };
  function recount(r) {
    r.valid = []; r.repetitions = []; r.intrusions = [];
    r.items.forEach(function (it) {
      if (it.status === 'valid') r.valid.push(it.text);
      else if (it.status === 'repetition') r.repetitions.push(it.text);
      else if (it.status === 'intrusion') r.intrusions.push(it.text);
    });
    r.count = r.valid.length;
  }
  function fluencyItems(r) {
    var rows = r.items.map(function (it, i) {
      var sel = h('select', { 'aria-label': 'Status of item ' + (i + 1) + ', ' + it.text });
      Object.keys(FLUENCY_STATUS).forEach(function (k) { sel.appendChild(h('option', { value: k, text: FLUENCY_STATUS[k], selected: k === it.status })); });
      sel.addEventListener('change', function () {
        if (it.auto == null) it.auto = it.status;
        it.status = sel.value;
        r.reviewed = true;
        recount(r);
        save();
        renderResults();
      });
      return h('tr', { class: it.auto != null && it.auto !== it.status ? 'changed' : null }, [
        h('td', { class: 'mono muted', text: String(i + 1) }), h('td', { text: it.text }), h('td', null, sel)]);
    });
    return h('details', { open: r.items.length <= 30 }, [
      h('summary', { class: 'small', text: 'Review items (' + r.items.length + ')' }),
      h('div', { class: 'table-wrap' }, h('table', { class: 'data' }, [
        h('thead', null, h('tr', null, [h('th', { text: '#' }), h('th', { text: 'Item as said' }), h('th', { text: 'Status' })])),
        h('tbody', null, rows)]))
    ]);
  }

  function renderResults() {
    var box = $('task-res-body');
    box.innerHTML = '';
    var list = S.results.filter(function (r) { return r.kind === task(); });
    $('task-results').hidden = task() === 'naming' || !list.length;
    $('task-res-h').textContent = task() === 'description' ? 'Picture description results' : 'Category fluency results';
    $('task-res-meta').textContent = list.length + ' result' + (list.length === 1 ? '' : 's');
    list.forEach(function (r) {
      var card = h('article', { class: 'result-card' });
      var when = new Date(r.at).toLocaleString();
      if (r.kind === 'description') {
        card.appendChild(h('div', { class: 'kv' }, [h('span', { text: (r.speaker || '–') + ' · ' + (r.theme || r.scene_id) }), h('span', { class: 'xsmall', text: when })]));
        card.appendChild(h('div', { class: 'stats' }, [stat(r.words, 'words'), stat(r.words_per_min == null ? null : Math.round(r.words_per_min), 'words per minute'),
          stat(r.cu_count, 'content units'), stat(r.cu_per_min == null ? null : (+r.cu_per_min).toFixed(1), 'content units per minute')]));
        card.appendChild(h('div', null, [h('span', { class: 'xsmall muted', text: 'Mentioned' }), chips(r.content_units_mentioned, 'ok')]));
        card.appendChild(h('div', null, [h('span', { class: 'xsmall muted', text: 'Missed' }), chips(r.content_units_missed, 'miss')]));
      } else {
        card.appendChild(h('div', { class: 'kv' }, [h('span', { text: (r.speaker || '–') + ' · ' + r.category }), h('span', { class: 'xsmall', text: when })]));
        card.appendChild(h('div', { class: 'stats' }, [stat(r.count, 'valid, unique'), stat((r.repetitions || []).length, 'repetitions'), stat((r.intrusions || []).length, 'intrusions')]));
        if ((r.items || []).length) card.appendChild(fluencyItems(r));
        else {
          card.appendChild(h('div', null, [h('span', { class: 'xsmall muted', text: 'Valid' }), chips(r.valid, 'ok')]));
          if ((r.repetitions || []).length) card.appendChild(h('div', null, [h('span', { class: 'xsmall muted', text: 'Repetitions' }), chips(r.repetitions, 'warn')]));
          if ((r.intrusions || []).length) card.appendChild(h('div', null, [h('span', { class: 'xsmall muted', text: 'Intrusions' }), chips(r.intrusions, 'miss')]));
        }
      }
      card.appendChild(h('p', { class: 'small', style: { margin: 0 } }, [h('span', { class: 'muted', text: 'Transcript: ' }), r.transcript || '']));
      box.appendChild(card);
    });
  }

  // --- export -------------------------------------------------------------------------------------
  $('export-csv').addEventListener('click', function () {
    var stamp = new Date().toISOString().slice(0, 10);
    var speaker = ($('speaker').value.trim() || 'session').replace(/[^\w-]+/g, '_');
    if (task() === 'naming') {
      var rows = S.rows.filter(function (r) { return r.status === 'done'; }).map(function (r) {
        return { speaker: r.speaker, set: r.set, item: r.index + 1, target: r.target, lang: r.lang, response: r.response,
          scored_response: r.scored == null ? r.response : r.scored,
          auto_code: r.code, second_rater_code: r.second ? r.second.code : '', second_rater_rationale: r.second ? r.second.rationale : '',
          raters_agree: r.agree == null ? '' : r.agree, reviewer_code: T.normCode(r.reviewer), reviewer_changed: T.normCode(r.reviewer) !== T.normCode(r.code),
          mode: r.mode, duration_s: r.duration == null ? '' : r.duration, scored_at: r.scored_at };
      });
      if (!rows.length) { T.toast('No scored responses to export yet.', 'error'); return; }
      T.downloadCSV('naming_' + speaker + '_' + stamp + '.csv', Object.keys(rows[0]), rows);
    } else {
      var list = S.results.filter(function (r) { return r.kind === task(); });
      if (!list.length) { T.toast('No results to export yet.', 'error'); return; }
      var out = list.map(function (r) {
        var o = {};
        Object.keys(r).forEach(function (k) {
          var v = r[k];
          if (k === 'items' && Array.isArray(v)) o[k] = v.map(function (x) { return x.text + ' (' + x.status + ')'; }).join('; ');
          else o[k] = Array.isArray(v) ? v.map(function (x) { return typeof x === 'string' ? x : JSON.stringify(x); }).join('; ') : v;
        });
        return o;
      });
      var cols = Object.keys(out.reduce(function (acc, o) { return Object.assign(acc, o); }, {}));
      T.downloadCSV(task() + '_' + speaker + '_' + stamp + '.csv', cols, out);
    }
  });

  $('clear-session').addEventListener('click', function () {
    if (!S.rows.length && !S.results.length) return;
    if (!confirm('Clear all responses and results in this browser? Export first if you need them.')) return;
    S.rows = [];
    S.results = [];
    save();
    $('restored').hidden = true;
    renderTable();
    renderSummary();
    renderResults();
  });

  // --- wiring -------------------------------------------------------------------------------------
  $('start-btn').addEventListener('click', function () {
    if (S.running) return;
    ({ naming: startNaming, description: startDescription, fluency: startFluency })[task()]();
  });
  $('task').addEventListener('change', onTask);
  $('set').addEventListener('change', onSet);
  $('speaker').addEventListener('change', function () { save(); renderTable(); });
  $('typed-response').addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); nextNaming(); } });
  document.addEventListener('keydown', function (e) {
    if (!S.running || task() !== 'naming' || mode() !== 'voice') return;
    var tag = (e.target.tagName || '').toLowerCase();
    if (tag === 'button' || tag === 'input' || tag === 'select' || tag === 'textarea' || tag === 'audio') return;
    if (e.key === ' ' || e.key === 'ArrowRight') { e.preventDefault(); nextNaming(); }
  });
  window.addEventListener('beforeunload', function (e) { if (S.running) { e.preventDefault(); e.returnValue = ''; } });

  // --- guided-tour replay ---------------------------------------------------------------------------
  /* The tour replays answers recorded once with the real pipeline (static/tour/scorer_demo.json):
     no microphone, no API calls, nothing saved. The visitor's own rows come back afterwards. */
  function demoStart(fx) {
    if (S.demo) return;
    S.demo = { saved: S.rows, fx: fx };
    S.rows = [];
    if (task() !== 'naming') { $('task').value = 'naming'; onTask(); }
    if (S.sets.some(function (s) { return s.id === fx.set; }) && $('set').value !== fx.set) { $('set').value = fx.set; onSet(); }
    $('restored').hidden = true;
    renderTable();
    renderSummary();
  }
  function demoShow(i) {
    var fx = S.demo.fx, it = fx.items[i];
    showStage(true);
    $('stage').classList.add('demo');
    $('stage-count').textContent = 'Item ' + (i + 1) + ' of ' + fx.items.length + ' · recorded demo';
    $('stage-rec').hidden = true;
    $('stage-typed').hidden = true;
    var pic = $('stage-picture');
    pic.innerHTML = '';
    pic.appendChild(h('img', { src: T.mediaUrl(fx.set, it.image), alt: 'Picture to name, item ' + (i + 1) }));
    setControls([]);
    $('stage-help').textContent = 'Replaying a recorded answer: no microphone and no API calls.';
  }
  function demoAdd(i) {
    var fx = S.demo.fx, it = fx.items[i];
    var row = { id: S.nextId++, n: S.rows.length + 1, index: it.item, target: it.target, image: it.image, set: fx.set,
      lang: fx.lang, speaker: 'DEMO', mode: 'voice', status: 'pending', second_on: true, demo: true };
    S.rows.push(row);
    renderTable();
    return new Promise(function (resolve) {
      setTimeout(function () {
        if (!S.demo) return resolve(row);
        Object.assign(row, { status: 'done', response: it.transcript, scored: it.scored_response, code: it.code, second: it.second,
          second_status: it.second_status, agree: it.agree, duration: it.duration_s, reviewer: it.code, scored_at: fx.recorded });
        renderTable();
        renderSummary();
        resolve(row);
      }, 900);
    });
  }
  function demoEnd() {
    if (!S.demo) return;
    S.rows = S.demo.saved;
    S.demo = null;
    $('stage').classList.remove('demo');
    hideStage();
    renderTable();
    renderSummary();
  }

  restore();
  var ready = T.status().then(function (st) {
    S.status = st;
    S.langs = st ? st.languages : [{ code: 'en', name: 'English', verified: true }, { code: 'es', name: 'Spanish', verified: true }];
    T.fillLanguages($('lang'), S.langs, 'en');
    var wantTask = T.param('task');
    if (wantTask && $('task').querySelector('option[value="' + wantTask + '"]')) $('task').value = wantTask;
    applyFeatures();
    onTask();
    renderTable();
    loadScenes();
    return loadSets();
  });

  T.scorer = {
    ready: ready,
    demoStart: demoStart, demoShow: demoShow, demoAdd: demoAdd, demoEnd: demoEnd,
    demoRows: function () { return S.demo ? S.rows.length : 0; }
  };
})();
