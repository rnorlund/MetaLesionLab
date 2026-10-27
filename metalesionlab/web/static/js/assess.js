/* Naming Assessment for clinicians and researchers: set up, administer, review, report, track. */
(function () {
  'use strict';
  var T = window.TOT, A = window.TLA, h = T.h;
  var ITI_MS = 500;
  var S = {
    config: null, status: null, langs: [], publicSets: [], privateSets: [], test: null, forms: {}, sessions: [],
    session: null, cap: null, run: null, reference: null, objectUrls: []
  };
  function $(id) { return document.getElementById(id); }
  function today() { return new Date().toISOString(); }
  function fmtDate(iso) { var d = new Date(iso); return isNaN(d) ? '' : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) + ' ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }); }
  function shortDate(iso) { var d = new Date(iso); return isNaN(d) ? '' : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }); }
  function btn(label, cls, onClick, attrs) { return h('button', Object.assign({ type: 'button', class: 'btn ' + (cls || ''), onclick: onClick }, attrs || {}), label); }

  // --- tests: public sets and private sets --------------------------------------------------
  function loadTests() {
    return Promise.all([
      T.api('/api/sets').catch(function () { return []; }),
      A.store.all('sets').catch(function () { return []; })
    ]).then(function (res) {
      S.publicSets = res[0].filter(function (s) { return s.status === 'done' && s.kept > 0; });
      S.privateSets = (res[1] || []).sort(function (a, b) { return (b.created || '').localeCompare(a.created || ''); });
      renderTestOptions();
      renderTestList();
    });
  }
  function testKey(t) { return (t.private ? 'p:' : 's:') + t.id; }
  function renderTestOptions() {
    var sel = $('test'), want = sel.value || T.param('set');
    sel.innerHTML = '';
    if (S.privateSets.length) {
      var g = h('optgroup', { label: 'Private sets (this browser)' });
      S.privateSets.forEach(function (s) { g.appendChild(h('option', { value: 'p:' + s.id, text: s.name + ' · ' + s.items.length + ' pictures · Private set' })); });
      sel.appendChild(g);
    }
    var pub = h('optgroup', { label: 'Picture sets' });
    S.publicSets.forEach(function (s) {
      pub.appendChild(h('option', { value: 's:' + s.id, text: (s.demo ? 'Demo set (' + T.langName(S.langs, s.lang) + ')' : s.name) + ' · ' + s.kept + ' pictures' }));
    });
    sel.appendChild(pub);
    if (want && sel.querySelector('option[value="' + want + '"]')) sel.value = want;
    else if (want && sel.querySelector('option[value="s:' + want + '"]')) sel.value = 's:' + want;
    else if (sel.querySelector('option[value="s:demo_en"]')) sel.value = 's:demo_en';
    return onTest();
  }
  function renderTestList() {
    var ul = $('test-list');
    ul.innerHTML = '';
    if (!S.privateSets.length) ul.appendChild(h('li', { class: 'small muted', text: 'No private sets yet. Import one or make one from a photo.' }));
    S.privateSets.forEach(function (s) {
      var practice = s.items.filter(function (it) { return it.practice; }).length;
      ul.appendChild(h('li', { class: 'test-row' }, [
        h('button', { type: 'button', onclick: function () { $('test').value = 'p:' + s.id; onTest(); $('test').focus(); } }, [
          h('span', null, [h('span', { class: 'name', text: s.name }), h('br'),
            h('span', { class: 'sub', text: [s.lang, s.items.length + ' pictures', practice ? practice + ' practice' : null, s.source].filter(Boolean).join(' · ') })]),
          h('span', { class: 'pill pill-private', text: 'Private set' })]),
        h('button', { type: 'button', class: 'icon-btn', 'aria-label': 'Delete private set ' + s.name, title: 'Delete', onclick: function () { deleteSet(s); } }, '×')
      ]));
    });
  }
  function deleteSet(s) {
    if (!confirm('Delete the private set "' + s.name + '" from this browser? Sessions already given keep their results.')) return;
    A.store.del('sets', s.id).then(loadTests).then(function () { T.toast('Deleted "' + s.name + '".'); });
  }

  function onTest() {
    var key = $('test').value;
    S.objectUrls.forEach(URL.revokeObjectURL);
    S.objectUrls = [];
    if (!key) { S.test = null; return Promise.resolve(); }
    var id = key.slice(2);
    if (key[0] === 'p') {
      var s = S.privateSets.filter(function (x) { return x.id === id; })[0];
      if (!s) return Promise.resolve();
      S.test = { id: s.id, name: s.name, private: true, lang: s.lang, items: s.items.map(function (it, i) {
        var url = URL.createObjectURL(it.image);
        S.objectUrls.push(url);
        return { index: i, target: it.target, alternates: it.alternates || [], practice: !!it.practice, url: url };
      }) };
      return applyTest();
    }
    return T.api('/api/sets/' + encodeURIComponent(id)).then(function (d) {
      if ($('test').value !== key) return;  // the selection changed while this loaded
      var items = (d.manifest ? d.manifest.items : []).map(function (it, i) {
        return { index: i, target: it.word, alternates: it.alternates || [], practice: false, image: it.image, status: it.status,
          url: it.image ? T.mediaUrl(id, it.image) : null };
      }).filter(function (it) { return it.status === 'kept' && it.url; });
      S.test = { id: id, name: d.demo ? 'Demo set (' + T.langName(S.langs, d.lang) + ')' : d.name, private: false, lang: d.lang, items: items };
      return applyTest();
    }).catch(function (e) { T.toast(e.message, 'error'); });
  }
  function applyTest() {
    var t = S.test;
    if (t.lang && $('lang').querySelector('option[value="' + t.lang + '"]')) $('lang').value = t.lang;
    onLang();
    var practice = t.items.filter(function (it) { return it.practice; }).length;
    $('practice-field').hidden = !practice;
    $('form').value = 'all';
    $('form-hint').textContent = 'Forms A and B split the set into halves matched on word frequency and length, for re-testing without repeating pictures.';
    $('form').querySelector('option[value="all"]').textContent = 'Whole set (' + (t.items.length - practice) + ' pictures)';
    return Promise.resolve();
  }
  function scoredItems() { return S.test.items.filter(function (it) { return !it.practice; }); }
  function onForm() {
    var f = $('form').value;
    if (f === 'all' || !S.test) return Promise.resolve();
    return ensureForms().catch(function (e) { T.toast(e.message, 'error'); $('form').value = 'all'; });
  }
  function ensureForms() {
    var key = testKey(S.test) + '|' + $('lang').value;
    if (S.forms[key]) return Promise.resolve(S.forms[key]);
    var words = scoredItems().map(function (it) { return it.target; });
    $('form-hint').textContent = 'Matching the halves…';
    return T.api('/api/assess/forms', { method: 'POST', json: { lang: $('lang').value, words: words } }).then(function (r) {
      S.forms[key] = r;
      var a = r.stats.A, b = r.stats.B;
      $('form-hint').textContent = 'Form A: ' + a.n + ' pictures, word frequency ' + a.zipf_mean + ' (Zipf), ' + a.phonemes_mean + ' sounds. ' +
        'Form B: ' + b.n + ' pictures, ' + b.zipf_mean + ', ' + b.phonemes_mean + ' sounds.';
      return r;
    });
  }

  // --- languages: measured status and how to answer -------------------------------------------
  function langInfo(code) { return ((S.config && S.config.languages) || []).filter(function (l) { return l.code === code; })[0] || null; }
  function fillLangs(select, selected) {
    var list = (S.config && S.config.languages) || S.langs.map(function (l) { return { code: l.code, name: l.name, status: l.verified ? 'verified' : 'experimental' }; });
    select.innerHTML = '';
    list.forEach(function (l) { select.appendChild(h('option', { value: l.code, text: l.name + (l.status === 'verified' ? '' : ' (' + l.status + ')') })); });
    if (selected) select.value = selected;
  }
  function answerText(code) {
    var l = langInfo(code);
    if (!l) return '';
    return l.instruction + (l.example ? ' For example: "' + l.example + '".' : '');
  }
  function onLang() {
    var l = langInfo($('lang').value);
    $('lang-hint').textContent = l ? 'How to answer: ' + answerText(l.code) + (l.status === 'verified' ? ''
      : l.status === 'works with review' ? ' Spoken scoring in this language works with review: check every code that isn\'t Correct.'
        : ' Spoken scoring in this language is experimental: check every code.') : '';
  }

  // --- status ----------------------------------------------------------------------------
  function applyFeatures() {
    var st = S.status, notes = [];
    if (!A.Capture.supported()) notes.push('This browser can\'t record audio here (it needs AudioWorklet and microphone access over HTTPS). Try a current Chrome, Edge, Firefox or Safari.');
    if (st && !st.features.meta_api) notes.push('Live scoring is off: this server has no Meta API key. Stored sessions can still be reviewed and exported.');
    if (st && !st.features.scorer) $('second').disabled = true;
    $('feature-note').hidden = !notes.length;
    $('feature-note').textContent = notes.join(' ');
    $('start').disabled = !!notes.length || !!S.run;
    if (st) $('limit-note').textContent = st.limits.score.remaining + ' of ' + st.limits.score.per_day + ' scored responses left today on this server. A local install can raise this (TOT_LIMIT_SCORE).';
  }

  // --- administration ----------------------------------------------------------------------
  var CODE_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,23}$/;
  function start() {
    if (S.run || !S.test) return;
    var speaker = $('speaker').value.trim();
    if (!speaker) { T.toast('Enter a speaker code (not a name).', 'error'); $('speaker').focus(); return; }
    if (!CODE_RE.test(speaker)) { T.toast('Use letters, digits, dot, dash or underscore for the speaker code, with no spaces; never a name.', 'error'); $('speaker').focus(); return; }
    var limit = Math.max(3, Math.min(60, +$('limit').value || 20));
    var form = $('form').value;
    var getItems = form === 'all' ? Promise.resolve(scoredItems()) : ensureForms().then(function (r) {
      var list = scoredItems();
      return r[form].map(function (i) { return list[i]; });
    });
    getItems.then(function (items) {
      var practice = $('practice').checked ? S.test.items.filter(function (it) { return it.practice; }) : [];
      var all = practice.concat(items);
      S.session = {
        id: A.uid('s-'), speaker: speaker, set_id: S.test.id, set_name: S.test.name, private_set: S.test.private,
        lang: $('lang').value, started: today(), time_limit_s: limit, form: form === 'all' ? null : 'Form ' + form,
        second_rater: $('second').checked, lead_in_ms: A.LEAD_IN_MS,
        items: all.map(function (it, k) {
          return { n: k + 1, index: it.index, target: it.target, alternates: it.alternates, practice: it.practice, url: it.url,
            image: it.image || null, status: 'waiting' };
        })
      };
      S.cap = new A.Capture();
      return S.cap.start();
    }).then(function () {
      S.run = { k: 0, phase: 'ready', paused: false, timer: null };
      applyFeatures();
      openAdmin();
      preload();
      var how = answerText(S.session.lang);
      showMessage('Ready', 'Tell the person: "I\'ll show you some pictures, one at a time. Tell me the name of each one."' +
        (how ? ' ' + how : ''), 'Start');
    }).catch(function (e) {
      if (S.cap) S.cap.stop();
      S.cap = null;
      S.run = null;
      T.toast(e && e.name === 'NotAllowedError' ? 'Microphone access was blocked. Allow it in the browser to give the test.' : (e.message || String(e)), 'error');
      applyFeatures();
    });
  }
  function preload() {
    S.session.items.forEach(function (it) { if (it.url) { var img = new Image(); img.src = it.url; } });
  }
  function openAdmin() {
    $('admin').hidden = false;
    document.body.classList.add('admin-open');
    var el = $('admin');
    if (el.requestFullscreen && !document.fullscreenElement && window.matchMedia('(pointer: coarse)').matches) el.requestFullscreen().catch(function () {});
    $('admin-next').focus({ preventScroll: true });
  }
  function closeAdmin() {
    $('admin').hidden = true;
    document.body.classList.remove('admin-open');
    if (document.fullscreenElement) document.exitFullscreen().catch(function () {});
  }
  function showMessage(title, text, nextLabel) {
    $('admin-img').hidden = true;
    var msg = $('admin-msg');
    msg.hidden = false;
    msg.innerHTML = '';
    msg.appendChild(h('h2', { text: title }));
    if (text) msg.appendChild(h('p', { text: text }));
    $('admin-next').textContent = nextLabel || 'Next';
    $('admin-rec').hidden = !S.cap;
  }
  function counter() {
    var it = S.session.items[S.run.k], scored = S.session.items.filter(function (x) { return !x.practice; }).length;
    var pos = S.session.items.slice(0, S.run.k + 1).filter(function (x) { return !x.practice; }).length;
    $('admin-count').textContent = it.practice ? 'Practice' : pos + ' / ' + scored;
  }

  function runItem() {
    var run = S.run, it = S.session.items[run.k];
    run.phase = 'blank';
    $('admin-msg').hidden = true;
    $('admin-img').hidden = true;
    $('admin-next').textContent = 'Next';
    counter();
    var minLead = (A.LEAD_IN_MS + 100) / 1000 * S.cap.rate;
    setTimeout(function () {
      var wait = S.cap.total >= minLead ? Promise.resolve() : S.cap.waitFor(minLead);
      wait.then(function () { return A.reveal($('admin-img'), it.url); }).then(function (onsetPerf) {
        if (S.run !== run || run.phase !== 'blank') return;
        run.phase = 'picture';
        run.onsetFrame = S.cap.frameAt(onsetPerf);
        run.timer = setTimeout(function () { endItem('limit'); }, S.session.time_limit_s * 1000);
      });
    }, ITI_MS);
  }
  function endItem(reason, perfTs) {
    var run = S.run;
    if (!run || run.phase !== 'picture') return;
    clearTimeout(run.timer);
    run.phase = 'between';
    var it = S.session.items[run.k], cap = S.cap, rate = cap.rate;
    var limitFrame = run.onsetFrame + Math.round(S.session.time_limit_s * rate);
    var endFrame = reason === 'limit' ? limitFrame : Math.min(limitFrame, cap.frameAt(perfTs || performance.now()));
    var startFrame = run.onsetFrame - Math.round(A.LEAD_IN_MS / 1000 * rate);
    $('admin-img').hidden = true;
    it.status = 'pending';
    it.ended_by = reason;
    cap.clip(startFrame, endFrame).then(function (blob) {
      it.blob = blob;
      it.audioUrl = URL.createObjectURL(blob);
      upload(it);
    });
    run.k++;
    if (run.k >= S.session.items.length) return finish();
    if (run.paused) { run.phase = 'paused'; showMessage('Paused', 'The next picture appears when you continue.', 'Continue'); return; }
    runItem();
  }
  function onNext(e) {
    var run = S.run;
    if (!run) return;
    var ts = e && e.timeStamp ? e.timeStamp : performance.now();
    if (run.phase === 'ready' || run.phase === 'paused') { run.paused = false; $('admin-pause').textContent = 'Pause'; runItem(); }
    else if (run.phase === 'picture') endItem('next', ts);
  }
  function togglePause() {
    var run = S.run;
    if (!run) return;
    if (run.phase === 'paused') { onNext(); return; }
    run.paused = !run.paused;
    $('admin-pause').textContent = run.paused ? 'Resume' : 'Pause';
    if (run.paused && run.phase === 'blank') T.toast('Pausing after this picture.');
  }
  function endSession() {
    var run = S.run;
    if (!run) return;
    if (!confirm('End the session now? Pictures not yet shown are left out; the current picture is not scored.')) return;
    clearTimeout(run.timer);
    S.session.items = S.session.items.filter(function (it) { return it.status !== 'waiting'; });
    run.phase = 'done';
    finish();
  }
  function finish() {
    var run = S.run;
    run.phase = 'done';
    S.session.finished = today();
    setTimeout(function () { if (S.cap) { S.cap.stop(); S.cap = null; } }, 1600);  // let the last clip finish
    showMessage('Session complete', 'Responses are being scored. Close this screen to review them.', 'See the report');
    $('admin-count').textContent = '';
    run.closeOnNext = true;
    saveSession();
  }
  function closeAfterFinish() {
    S.run = null;
    closeAdmin();
    applyFeatures();
    showReport(S.session);
    loadSessions();
  }

  // --- scoring ---------------------------------------------------------------------------
  function upload(it) {
    var sess = S.session;
    it.status = 'pending';
    it.error = null;
    renderIfShown(sess);
    A.scoreClip(it.blob, { target: it.target, lang: sess.lang, onsetMs: A.LEAD_IN_MS, limitS: sess.time_limit_s,
      setId: sess.private_set ? null : sess.set_id, index: it.index, alternates: sess.private_set ? it.alternates : null,
      secondRater: sess.second_rater && !it.practice
    }).then(function (res) { apply(it, res); }).catch(function (e) {
      it.status = 'error';
      it.error = e.message;
      if (e.status === 429 || e.status === 503) T.toast(e.message, 'error');
      saveSession(sess);
      renderIfShown(sess);
    });
  }
  function apply(it, res) {
    var sess = S.session;
    ['transcript', 'scored_response', 'attempts', 'split', 'code', 'second', 'second_status', 'agree', 'latency_ms',
      'duration_ms', 'timeout', 'flags', 'clip_s'].forEach(function (k) { if (k in res) it[k] = res[k]; });
    it.status = 'done';
    it.scored_at = today();
    saveSession(sess);
    renderIfShown(sess);
  }
  function rescore(sess, it) {
    var text = prompt('Correct the transcript for "' + it.target + '" (what was actually said). It will be coded again.', it.transcript || '');
    if (text == null) return;
    T.api('/api/assess/rescore', { method: 'POST', json: { target: it.target, response: text, lang: sess.lang,
      set_id: sess.private_set ? null : sess.set_id, item: sess.private_set ? null : it.index,
      alternates: sess.private_set ? it.alternates || [] : [], second_rater: false } }).then(function (res) {
      it.transcript_edited = true;
      it.transcript = text;
      it.scored_response = res.scored_response;
      it.attempts = res.attempts;
      it.code = res.code;
      it.reviewer = null;
      saveSession(sess);
      showReport(sess);
    }).catch(function (e) { T.toast(e.message, 'error'); });
  }

  // --- persistence ------------------------------------------------------------------------
  var saveTimers = {};
  function plain(sess) {
    return Object.assign({}, sess, { items: sess.items.map(function (it) {
      var c = Object.assign({}, it);
      delete c.blob; delete c.audioUrl;
      if (sess.private_set) delete c.url;  // a blob URL; dead after reload
      return c;
    }) });
  }
  function saveSession(sess) {
    sess = sess || S.session;
    if (!sess) return;
    clearTimeout(saveTimers[sess.id]);
    saveTimers[sess.id] = setTimeout(function () {
      A.store.put('sessions', plain(sess)).then(function () { if (!S.run) refreshTracking(); })
        .catch(function (e) { T.toast('Couldn\'t save the session in this browser: ' + e.message, 'error'); });
    }, 150);
  }
  var trackTimer = null;
  function refreshTracking() {
    clearTimeout(trackTimer);
    trackTimer = setTimeout(loadSessions, 400);
  }

  // --- report --------------------------------------------------------------------------------
  var shown = null;
  function renderIfShown(sess) { if (shown === sess) showReport(sess); }
  function tile(value, label, sub) { return h('div', { class: 'stat' }, [h('b', { text: value }), h('span', { text: label }), sub ? h('small', { text: sub }) : null]); }

  function showReport(sess) {
    shown = sess;
    $('report').hidden = false;
    $('about').hidden = true;
    var sum = A.summarize(sess.items);
    $('report-meta').textContent = [sess.speaker, sess.set_name + (sess.private_set ? ' (private set)' : ''), sess.form, fmtDate(sess.started)].filter(Boolean).join(' · ');
    var pending = sess.items.filter(function (it) { return it.status === 'pending'; }).length;
    var failed = sess.items.filter(function (it) { return it.status === 'error'; }).length;
    var prog = $('report-progress');
    prog.innerHTML = '';
    if (pending) prog.appendChild(h('p', { class: 'note' }, [h('span', { class: 'spinner', 'aria-hidden': 'true' }), ' Scoring ' + pending + ' response' + (pending > 1 ? 's' : '') + '…']));
    if (failed) prog.appendChild(h('p', { class: 'note note-error', text: failed + ' response' + (failed > 1 ? 's' : '') + ' couldn\'t be scored. Use Retry in the table (only while this page is open).' }));

    var st = $('report-stats');
    st.innerHTML = '';
    st.appendChild(tile(sum.n ? sum.correct + ' / ' + sum.n : '–', 'Accuracy, first complete response', sum.n ? sum.accuracy_pct + '%' : null));
    st.appendChild(tile(A.seconds(sum.latency_median_ms), 'Median naming latency, correct', sum.latency_n ? 'n = ' + sum.latency_n : null));
    st.appendChild(tile(sum.latency_n ? A.seconds(sum.latency_q1_ms) + ' – ' + A.seconds(sum.latency_q3_ms) : '–', 'Interquartile range'));
    st.appendChild(tile(String(sum.timeouts.length), 'Reached the ' + sess.time_limit_s + ' s limit', sum.timeouts.length ? sum.timeouts.join(', ') : null));

    var types = $('report-types');
    types.innerHTML = '';
    if (sum.n) {
      types.appendChild(T.stackBar(sum.counts, sum.n, 'Final codes: ' + T.describeCounts(sum.counts, sum.n)));
      var tbl = h('table', { class: 'data compact' }, [h('thead', null, h('tr', null, [h('th', { text: 'Type' }), h('th', { class: 'num', text: 'Count' }), h('th', { class: 'num', text: 'Share' })]))]);
      var body = h('tbody');
      T.ORDER.forEach(function (c) {
        if (!sum.counts[c]) return;
        var sw = h('span', { class: 'swatch' });
        sw.style.background = T.codeInfo(c).color;
        body.appendChild(h('tr', null, [h('td', null, [sw, ' ', T.codeInfo(c).label]), h('td', { class: 'num', text: String(sum.counts[c]) }),
          h('td', { class: 'num', text: Math.round(100 * sum.counts[c] / sum.n) + '%' })]));
      });
      tbl.appendChild(body);
      types.appendChild(tbl);
    } else types.appendChild(h('p', { class: 'small muted', text: 'No scored items yet.' }));
    A.latencyChart($('report-latency'), sess.items, sess.time_limit_s);
    renderReview(sess);
    renderReference();
  }

  function renderReview(sess) {
    var body = $('review-body');
    body.innerHTML = '';
    sess.items.forEach(function (it) {
      var heard;
      if (it.status === 'pending' || it.status === 'waiting') heard = h('span', { class: 'muted' }, [h('span', { class: 'spinner', 'aria-hidden': 'true' }), ' scoring…']);
      else if (it.status === 'error') heard = h('span', null, [h('span', { class: 'xsmall err', text: it.error || 'Failed' }), ' ',
        it.blob ? btn('Retry', 'btn-small', function () { upload(it); }) : null]);
      else {
        heard = h('span', null, [it.transcript ? it.transcript : h('span', { class: 'muted', text: '(nothing)' })]);
        if (it.split || (it.scored_response && simple(it.scored_response) !== simple(it.transcript))) {
          heard.appendChild(h('span', { class: 'rationale', text: 'coded: "' + (it.scored_response || '') + '"' + (it.split ? ' (first complete response)' : '') }));
        }
        if (it.transcript_edited) heard.appendChild(h('span', { class: 'rationale', text: 'transcript corrected by reviewer' }));
      }
      var done = it.status === 'done';
      var codeSel = null, latInput = null;
      if (done) {
        codeSel = h('select', { 'aria-label': 'Final code for item ' + it.n + ', ' + it.target });
        T.ORDER.forEach(function (c) { codeSel.appendChild(h('option', { value: c, text: T.codeInfo(c).label, selected: c === A.finalCode(it) })); });
        codeSel.addEventListener('change', function () { it.reviewer = codeSel.value === it.code ? null : codeSel.value; saveSession(sess); showReport(sess); });
        latInput = h('input', { type: 'number', min: '0', max: '60000', step: '10', class: 'lat-input', inputmode: 'numeric',
          'aria-label': 'Latency in ms for item ' + it.n + ', ' + it.target, value: A.finalLatency(it) == null ? '' : String(Math.round(A.finalLatency(it))),
          placeholder: '–' });
        latInput.addEventListener('change', function () {
          var v = latInput.value.trim();  // a number overrides the automatic latency; empty restores it
          it.reviewer_latency_ms = v === '' || +v === it.latency_ms ? null : Math.max(0, Math.round(+v));
          saveSession(sess);
          showReport(sess);
        });
      }
      var notes = [];
      if (it.practice) notes.push('practice');
      if (it.timeout) notes.push('time limit');
      (it.flags || []).forEach(function (f) { notes.push({ speech_at_onset: 'already speaking at onset', noisy_lead_in: 'noise before picture', no_onset_found: 'no clear onset' }[f] || f); });
      if (it.reviewer_latency_ms != null) notes.push('latency edited');
      var changed = done && it.reviewer && it.reviewer !== it.code;
      body.appendChild(h('tr', { class: [changed ? 'changed' : '', it.practice ? 'practice' : ''].join(' ').trim() || null }, [
        h('td', { class: 'mono muted', text: String(it.n) }),
        h('td', null, thumbUrl(sess, it) ? h('img', { class: 'thumb', src: thumbUrl(sess, it), alt: '' }) : null),
        h('td', { class: 'target' }, [it.target, it.practice ? h('span', { class: 'pill pill-soft', text: 'practice' }) : null]),
        h('td', { class: 'heard' }, heard),
        h('td', null, done ? T.pill(it.code) : null),
        h('td', null, secondCell(it)),
        h('td', null, codeSel),
        h('td', null, [latInput, notes.length ? h('span', { class: 'rationale', text: notes.join(' · ') }) : null]),
        h('td', null, h('div', { class: 'clip-actions' }, [
          it.audioUrl ? h('audio', { controls: true, src: it.audioUrl, preload: 'none', 'aria-label': 'Recording for item ' + it.n }) : null,
          done ? btn('Edit', 'btn-small', function () { rescore(sess, it); }, { 'aria-label': 'Correct the transcript for item ' + it.n }) : null]))
      ]));
    });
  }
  function thumbUrl(sess, it) {
    if (sess.private_set) return it.url && S.objectUrls.indexOf(it.url) >= 0 ? it.url : null;  // blob URLs die on reload
    return it.image ? T.mediaUrl(sess.set_id, it.image, 160) : it.url;
  }
  function simple(s) { return String(s || '').toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim(); }
  function secondCell(it) {
    if (it.status !== 'done') return '';
    if (it.second_status === 'ok' && it.second) {
      var main = it.agree ? h('span', { class: 'agree', text: 'agrees' }) : h('span', { class: 'disagree', text: 'says ' + T.codeInfo(it.second.code).label });
      return h('span', null, [main, it.second.rationale ? h('span', { class: 'rationale', text: it.second.rationale }) : null]);
    }
    return h('span', { class: 'xsmall muted', text: { off: 'off', unavailable: 'not available', error: 'didn\'t answer' }[it.second_status] || '–' });
  }

  function renderReference() {
    var go = S.reference ? Promise.resolve(S.reference) : T.api('/api/assess/reference').then(function (r) { S.reference = r; return r; });
    go.then(function (ref) {
      $('reference-caption').textContent = ref.caption;
      var tbl = $('reference-table');
      tbl.innerHTML = '';
      var cols = ['Semantic', 'Formal', 'Nonword', 'NoResponse'];
      tbl.appendChild(h('thead', null, h('tr', null, [h('th', { text: 'Published group' }), h('th', { class: 'num', text: 'N' }), h('th', { class: 'num', text: 'Accuracy' })]
        .concat(cols.map(function (c) { return h('th', { class: 'num', text: c === 'NoResponse' ? 'No response' : c }); }))
        .concat([h('th', { text: 'Source' })]))));
      var body = h('tbody');
      ref.controls.forEach(function (c) {
        body.appendChild(h('tr', null, [h('td', { text: c.label }), h('td', { class: 'num', text: String(c.n) }), h('td', { class: 'num', text: c.accuracy })]
          .concat(cols.map(function () { return h('td', { class: 'num muted', text: '–' }); }))
          .concat([h('td', { class: 'xsmall', title: c.citation, text: c.source })])));
      });
      ref.groups.forEach(function (g) {
        var n = (g.label.match(/N = (\d+)/) || [])[1];
        body.appendChild(h('tr', null, [h('td', { text: g.label.replace(/\s*\(N = \d+\)/, '') }), h('td', { class: 'num', text: n || '' }), h('td', { class: 'num', text: g.accuracy })]
          .concat(cols.map(function (c) { return h('td', { class: 'num', text: g.missing.indexOf(c) >= 0 ? '–' : Math.round(100 * (g.shares[c] || 0)) + '%' }); }))
          .concat([h('td', { class: 'xsmall', title: g.citation, text: g.source })])));
      });
      tbl.appendChild(body);
    }).catch(function () { $('reference-caption').textContent = 'Published references couldn\'t be loaded.'; });
  }

  // --- exports ------------------------------------------------------------------------------
  function exportCSV() {
    var sess = shown;
    if (!sess) return;
    var rows = sess.items.map(function (it) {
      return { speaker: sess.speaker, session: sess.id, started: sess.started, test: sess.set_name, private_set: sess.private_set,
        lang: sess.lang, form: sess.form || 'whole set', time_limit_s: sess.time_limit_s, item: it.n, set_item: it.index + 1,
        target: it.target, practice: !!it.practice, transcript: it.transcript || '', transcript_corrected: !!it.transcript_edited,
        scored_response: it.scored_response || '', attempts: (it.attempts || []).join(' | '), auto_code: it.code || '',
        second_rater_code: it.second ? it.second.code : '', second_rater_rationale: it.second ? it.second.rationale : '',
        final_code: A.finalCode(it) || '', reviewer_changed_code: !!(it.reviewer && it.reviewer !== it.code),
        latency_ms: it.latency_ms == null ? '' : it.latency_ms, final_latency_ms: A.finalLatency(it) == null ? '' : A.finalLatency(it),
        response_duration_ms: it.duration_ms == null ? '' : it.duration_ms, reached_time_limit: !!it.timeout,
        flags: (it.flags || []).join(' '), status: it.status, scored_at: it.scored_at || '' };
    });
    T.downloadCSV('naming_' + sess.speaker + '_' + sess.started.slice(0, 10) + '.csv', Object.keys(rows[0] || { item: 1 }), rows);
  }
  function history(sess) {
    return S.sessions.filter(function (s) { return s.speaker === sess.speaker && s.id !== sess.id && s.started < sess.started; })
      .map(function (s) { var m = A.summarize(s.items); return { date: fmtDate(s.started), set_name: s.set_name, form: s.form, n: m.n, accuracy_pct: m.accuracy_pct, latency_median_ms: m.latency_median_ms }; })
      .concat([(function () { var m = A.summarize(sess.items); return { date: fmtDate(sess.started), set_name: sess.set_name, form: sess.form, n: m.n, accuracy_pct: m.accuracy_pct, latency_median_ms: m.latency_median_ms }; })()]);
  }
  function exportPDF() {
    var sess = shown;
    if (!sess) return;
    var b = $('export-pdf');
    b.disabled = true;
    var items = sess.items.filter(function (it) { return it.status === 'done'; }).map(function (it) {
      return { n: it.n, target: it.target, transcript: it.transcript, scored_response: it.scored_response, code: it.code, second: it.second,
        reviewer: it.reviewer || null, latency_ms: it.latency_ms, reviewer_latency_ms: it.reviewer_latency_ms,
        duration_ms: it.duration_ms, timeout: !!it.timeout, practice: !!it.practice, flags: it.flags || [] };
    });
    var body = { session: { speaker: sess.speaker, set_name: sess.set_name, private_set: sess.private_set, lang: sess.lang, started: fmtDate(sess.started),
      time_limit_s: sess.time_limit_s, form: sess.form, second_rater: sess.second_rater, items: items }, history: history(sess).filter(function (x) { return x.accuracy_pct != null; }) };
    fetch('/api/assess/report.pdf', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (r) { if (!r.ok) throw new Error('The report couldn\'t be made (' + r.status + ').'); return r.blob(); })
      .then(function (blob) { A.download('naming_report_' + sess.speaker + '_' + sess.started.slice(0, 10) + '.pdf', blob); })
      .catch(function (e) { T.toast(e.message, 'error'); })
      .then(function () { b.disabled = false; });
  }

  // --- tracking ------------------------------------------------------------------------------
  function loadSessions() {
    return A.store.all('sessions').then(function (list) {
      S.sessions = (list || []).sort(function (a, b) { return a.started.localeCompare(b.started); });
      var speakers = S.sessions.map(function (s) { return s.speaker; }).filter(function (v, i, a) { return a.indexOf(v) === i; }).sort();
      var sel = $('track-speaker'), want = sel.value || (S.session && S.session.speaker) || $('speaker').value.trim();
      sel.innerHTML = '';
      if (!speakers.length) sel.appendChild(h('option', { value: '', text: 'No sessions yet' }));
      speakers.forEach(function (sp) { sel.appendChild(h('option', { value: sp, text: sp })); });
      if (speakers.indexOf(want) >= 0) sel.value = want;
      renderTracking();
    }).catch(function (e) { T.toast('Couldn\'t read stored sessions: ' + e.message, 'error'); });
  }
  function renderTracking() {
    var speaker = $('track-speaker').value;
    var list = S.sessions.filter(function (s) { return s.speaker === speaker; });
    $('track-meta').textContent = list.length ? list.length + ' session' + (list.length > 1 ? 's' : '') : '';
    $('sessions-empty').hidden = !!list.length;
    $('sessions-table').hidden = !list.length;
    ['export-sessions', 'delete-speaker'].forEach(function (id) { $(id).disabled = !list.length; });
    var body = $('sessions-body');
    body.innerHTML = '';
    var acc = [], lat = [];
    var days = list.map(function (s) { return shortDate(s.started); });
    list.forEach(function (s, k) {
      var short = days.indexOf(days[k]) !== days.lastIndexOf(days[k])
        ? days[k] + ' ' + new Date(s.started).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : days[k];
      var m = A.summarize(s.items);
      var label = fmtDate(s.started) + ' · ' + s.set_name + (s.form ? ' · ' + s.form : '');
      acc.push({ value: m.accuracy_pct, label: label, short: short, note: m.n ? m.correct + ' of ' + m.n + ' correct' : null });
      lat.push({ value: m.latency_median_ms, label: label, short: short, note: m.latency_n ? 'IQR ' + A.seconds(m.latency_q1_ms) + ' – ' + A.seconds(m.latency_q3_ms) : null });
      body.appendChild(h('tr', null, [
        h('td', { text: fmtDate(s.started) }),
        h('td', null, [s.set_name, s.private_set ? h('span', { class: 'pill pill-private', text: 'Private set' }) : null, s.form ? h('span', { class: 'xsmall muted', text: ' ' + s.form }) : null]),
        h('td', { class: 'num', text: String(m.n) }),
        h('td', { class: 'num', text: m.n ? m.correct + '/' + m.n + ' (' + m.accuracy_pct + '%)' : '–' }),
        h('td', { class: 'num', text: A.seconds(m.latency_median_ms) }),
        h('td', { class: 'num', text: m.latency_n ? A.seconds(m.latency_q1_ms) + ' – ' + A.seconds(m.latency_q3_ms) : '–' }),
        h('td', null, h('div', { class: 'clip-actions' }, [
          btn('Open', 'btn-small', function () { showReport(s); $('report').scrollIntoView({ behavior: 'smooth', block: 'start' }); }, { 'aria-label': 'Open the session of ' + fmtDate(s.started) }),
          h('button', { type: 'button', class: 'icon-btn', title: 'Delete', 'aria-label': 'Delete the session of ' + fmtDate(s.started), onclick: function () { deleteSession(s); } }, '×')]))
      ]));
    });
    A.trendChart($('trend-acc'), acc, { min: 0, max: 100, label: 'Accuracy (%)', fmt: function (v, long) { return Math.round(v) + '%'; } });
    A.trendChart($('trend-lat'), lat, { min: 0, label: 'Median naming latency', fmt: function (v, long) { return long ? A.seconds(v) : (v / 1000).toFixed(1) + ' s'; } });
  }
  function deleteSession(s) {
    if (!confirm('Delete this session (' + fmtDate(s.started) + ') from this browser? Export it first if you need it.')) return;
    A.store.del('sessions', s.id).then(function () { if (shown && shown.id === s.id) closeReport(); return loadSessions(); });
  }
  function exportSessions() {
    var speaker = $('track-speaker').value;
    var list = S.sessions.filter(function (s) { return s.speaker === speaker; });
    var data = { format: 'tippa-lingua-sessions', version: 1, exported: today(), note: 'Naming Assessment sessions. Measurements only; no diagnosis or prognosis.', sessions: list };
    A.download('sessions_' + speaker + '_' + today().slice(0, 10) + '.json', new Blob([JSON.stringify(data, null, 1)], { type: 'application/json' }));
  }
  function importSessions(file) {
    file.text().then(function (text) {
      var data = JSON.parse(text);
      if (!data || data.format !== 'tippa-lingua-sessions' || !Array.isArray(data.sessions)) throw new Error('That file isn\'t a Tippa Lingua sessions export.');
      var ok = data.sessions.filter(function (s) { return s && s.id && s.speaker && s.started && Array.isArray(s.items); });
      return Promise.all(ok.map(function (s) { return A.store.put('sessions', s); })).then(function () {
        T.toast('Imported ' + ok.length + ' session' + (ok.length === 1 ? '' : 's') + '.');
        $('track-speaker').value = ok.length ? ok[0].speaker : $('track-speaker').value;
        return loadSessions().then(function () { if (ok.length) { $('track-speaker').value = ok[0].speaker; renderTracking(); } });
      });
    }).catch(function (e) { T.toast(e.message.indexOf('JSON') >= 0 ? 'That file isn\'t valid JSON.' : e.message, 'error'); });
  }
  function deleteSpeaker() {
    var speaker = $('track-speaker').value;
    var list = S.sessions.filter(function (s) { return s.speaker === speaker; });
    if (!list.length || !confirm('Delete all ' + list.length + ' sessions for ' + speaker + ' from this browser? This can\'t be undone.')) return;
    Promise.all(list.map(function (s) { return A.store.del('sessions', s.id); })).then(function () {
      if (shown && shown.speaker === speaker) closeReport();
      $('track-speaker').value = '';
      return loadSessions();
    });
  }
  function closeReport() { shown = null; $('report').hidden = true; $('about').hidden = false; }

  // --- import a test ---------------------------------------------------------------------------
  var pendingImport = null;
  function previewImport(promise, fallbackName) {
    var box = $('import-preview');
    box.innerHTML = '';
    box.appendChild(h('p', { class: 'small' }, [h('span', { class: 'spinner', 'aria-hidden': 'true' }), ' Reading…']));
    $('import-save').disabled = true;
    promise.then(A.buildTest).then(function (res) {
      pendingImport = res;
      box.innerHTML = '';
      var practice = res.items.filter(function (it) { return it.practice; }).length;
      box.appendChild(h('p', { class: 'note note-ok', text: res.items.length + ' pictures matched to targets' + (practice ? ', ' + practice + ' practice' : '') + ' (from ' + res.csvName.split('/').pop() + ').' }));
      if (res.problems.length) box.appendChild(h('div', { class: 'note note-warn' }, [h('p', { text: res.problems.length + ' row' + (res.problems.length > 1 ? 's' : '') + ' skipped:' }),
        h('ul', { class: 'xsmall' }, res.problems.slice(0, 8).map(function (p) { return h('li', { text: p }); }))]));
      var strip = h('div', { class: 'import-strip' });
      res.items.slice(0, 12).forEach(function (it) {
        var url = URL.createObjectURL(it.image);
        strip.appendChild(h('figure', null, [h('img', { src: url, alt: '' }), h('figcaption', { text: it.target + (it.practice ? ' (practice)' : '') })]));
      });
      box.appendChild(strip);
      $('import-meta').hidden = false;
      if (!$('import-name').value) $('import-name').value = fallbackName || 'Imported test';
      $('import-save').disabled = false;
    }).catch(function (e) {
      pendingImport = null;
      box.innerHTML = '';
      box.appendChild(h('p', { class: 'note note-error', text: e.message }));
    });
  }
  function saveImport() {
    if (!pendingImport) return;
    var set = { id: A.uid('p-'), name: $('import-name').value.trim() || 'Imported test', lang: $('import-lang').value, created: today(),
      source: 'imported', items: pendingImport.items.map(function (it) { return { target: it.target, alternates: it.alternates, practice: it.practice, file: it.file, image: it.image }; }) };
    A.store.put('sets', set).then(function () {
      $('import-dlg').close();
      T.toast('Saved "' + set.name + '" as a private set in this browser.');
      return loadTests().then(function () { $('test').value = 'p:' + set.id; onTest(); });
    }).catch(function (e) { T.toast('Couldn\'t save the set: ' + e.message, 'error'); });
  }

  // --- a test from a photo -----------------------------------------------------------------------
  var photoResult = null;
  function startPhoto() {
    var file = $('photo-file').files[0];
    if (!file) { T.toast('Choose a photo first.', 'error'); return; }
    var fd = new FormData();
    fd.append('photo', file, file.name);
    fd.append('lang', $('photo-lang').value);
    fd.append('style', document.querySelector('input[name="photo-style"]:checked').value);
    fd.append('max_items', String(Math.max(2, Math.min(12, +$('photo-max').value || 8))));
    $('photo-go').disabled = true;
    $('photo-items').innerHTML = '';
    $('photo-save').hidden = true;
    $('photo-save-row').hidden = true;
    setPhotoStatus('Sending the photo…', true);
    T.api('/api/assess/photo-test', { method: 'POST', body: fd }).then(function (r) { pollPhoto(r.job); })
      .catch(function (e) { setPhotoStatus(e.message, false, true); $('photo-go').disabled = false; });
  }
  function setPhotoStatus(text, busy, error) {
    var box = $('photo-status');
    box.innerHTML = '';
    if (text) box.appendChild(h('p', { class: 'note' + (error ? ' note-error' : '') }, [busy ? h('span', { class: 'spinner', 'aria-hidden': 'true' }) : null, (busy ? ' ' : '') + text]));
  }
  function pollPhoto(job) {
    T.api('/api/assess/photo-test/' + encodeURIComponent(job)).then(function (r) {
      if (r.status === 'done') { $('photo-go').disabled = false; return showPhoto(r.result); }
      if (r.status === 'error') { $('photo-go').disabled = false; return setPhotoStatus(r.error, false, true); }
      setPhotoStatus((r.stage || 'Working') + '… (about a minute)', true);
      setTimeout(function () { pollPhoto(job); }, 1500);
    }).catch(function (e) { $('photo-go').disabled = false; setPhotoStatus(e.message, false, true); });
  }
  function showPhoto(result) {
    photoResult = result;
    var usable = result.items.filter(function (it) { return it.image; });
    setPhotoStatus(usable.length + ' pictures from ' + result.listed + ' objects Muse Spark listed. Check each one; untick any to leave out.', false);
    var box = $('photo-items');
    box.innerHTML = '';
    result.items.forEach(function (it, k) {
      it.include = it.status === 'kept';
      var checks = it.checks ? [
        h('span', { class: it.checks.sam_ok ? 'check-ok' : 'check-bad', text: (it.checks.sam_ok ? '✓' : '✗') + ' SAM 3.1: ' + it.checks.sam_objects + ' object' + (it.checks.sam_objects === 1 ? '' : 's') }),
        h('span', { class: it.checks.spark_ok ? 'check-ok' : 'check-bad', text: (it.checks.spark_ok ? '✓' : '✗') + ' Muse Spark: "' + it.checks.spark_name + '"' })] : [];
      var target = h('input', { type: 'text', value: it.target, maxlength: '40', 'aria-label': 'Target word for picture ' + (k + 1) });
      target.addEventListener('change', function () { it.target = target.value.trim().toLowerCase(); });
      var alts = h('input', { type: 'text', value: (it.alternates || []).join('; '), maxlength: '120', 'aria-label': 'Accepted alternates for picture ' + (k + 1), placeholder: 'alternates; separated; like this' });
      alts.addEventListener('change', function () { it.alternates = alts.value.split(/[;|,]/).map(function (a) { return a.trim().toLowerCase(); }).filter(Boolean); });
      var inc = h('input', { type: 'checkbox', checked: it.include && !!it.image, disabled: !it.image });
      inc.addEventListener('change', function () { it.include = inc.checked; });
      box.appendChild(h('div', { class: 'card' }, [
        h('div', { class: 'pic' }, it.image ? h('img', { src: it.image, alt: 'Picture of ' + it.target }) : h('span', { text: 'not found in the photo' })),
        h('div', { class: 'body' }, [h('label', { class: 'check' }, [inc, ' Include']), target, alts].concat(checks)
          .concat([it.note ? h('span', { class: 'flag', text: it.note }) : null]))
      ]));
    });
    $('photo-save-row').hidden = false;
    $('photo-save').hidden = false;
  }
  function savePhoto() {
    if (!photoResult) return;
    var chosen = photoResult.items.filter(function (it) { return it.include && it.image && it.target; });
    if (chosen.length < 2) { T.toast('Include at least two pictures.', 'error'); return; }
    Promise.all(chosen.map(function (it) { return fetch(it.image).then(function (r) { return r.blob(); }); })).then(function (blobs) {
      var set = { id: A.uid('p-'), name: $('photo-name').value.trim() || 'Objects at home', lang: photoResult.lang, created: today(),
        source: photoResult.style === 'photo' ? 'from a photo (crops)' : 'from a photo (drawings)',
        items: chosen.map(function (it, i) { return { target: it.target, alternates: it.alternates || [], practice: false, file: 'photo_' + (i + 1), image: blobs[i] }; }) };
      return A.store.put('sets', set).then(function () {
        $('photo-dlg').close();
        T.toast('Saved "' + set.name + '" as a private set in this browser.');
        return loadTests().then(function () { $('test').value = 'p:' + set.id; onTest(); });
      });
    }).catch(function (e) { T.toast('Couldn\'t save the set: ' + e.message, 'error'); });
  }

  // --- wiring --------------------------------------------------------------------------------
  $('start').addEventListener('click', start);
  $('test').addEventListener('change', onTest);
  $('form').addEventListener('change', onForm);
  $('lang').addEventListener('change', function () { onLang(); if ($('form').value !== 'all') onForm(); });
  $('admin-next').addEventListener('click', function (e) { if (S.run && S.run.closeOnNext) closeAfterFinish(); else onNext(e); });
  $('admin-pause').addEventListener('click', togglePause);
  $('admin-end').addEventListener('click', function () { if (S.run && S.run.closeOnNext) closeAfterFinish(); else endSession(); });
  document.addEventListener('keydown', function (e) {
    if (!S.run || $('admin').hidden) return;
    if (e.key === ' ' || e.key === 'ArrowRight' || e.key === 'Enter') {
      e.preventDefault();
      if (S.run.closeOnNext) closeAfterFinish(); else onNext(e);
    } else if (e.key === 'p' || e.key === 'P') togglePause();
    else if (e.key === 'Escape') { e.preventDefault(); if (S.run.closeOnNext) closeAfterFinish(); else togglePause(); }
  });
  window.addEventListener('beforeunload', function (e) {
    var pending = S.session && S.session.items.some(function (it) { return it.status === 'pending'; });
    if (S.run && !S.run.closeOnNext || pending) { e.preventDefault(); e.returnValue = ''; }
  });
  $('export-csv').addEventListener('click', exportCSV);
  $('export-pdf').addEventListener('click', exportPDF);
  $('close-report').addEventListener('click', closeReport);
  $('track-speaker').addEventListener('change', renderTracking);
  $('export-sessions').addEventListener('click', exportSessions);
  $('import-sessions').addEventListener('change', function () { var f = this.files[0]; if (f) importSessions(f); this.value = ''; });
  $('delete-speaker').addEventListener('click', deleteSpeaker);
  document.querySelectorAll('dialog [data-close]').forEach(function (b) { b.addEventListener('click', function () { b.closest('dialog').close(); }); });
  $('import-open').addEventListener('click', function () {
    pendingImport = null;
    $('import-preview').innerHTML = '';
    $('import-meta').hidden = true;
    $('import-save').disabled = true;
    $('import-name').value = '';
    $('import-lang').value = $('lang').value;
    $('import-dlg').showModal();
  });
  $('import-zip').addEventListener('change', function () {
    var f = this.files[0];
    if (f) previewImport(A.readZip(f), f.name.replace(/\.zip$/i, ''));
  });
  $('import-folder').addEventListener('change', function () {
    var files = Array.prototype.map.call(this.files, function (f) { return { name: f.webkitRelativePath || f.name, blob: f }; });
    if (files.length) previewImport(Promise.resolve(files), (files[0].name.split('/')[0] || 'Imported test'));
  });
  $('import-save').addEventListener('click', saveImport);
  $('photo-open').addEventListener('click', function () { $('photo-lang').value = $('lang').value; $('photo-dlg').showModal(); });
  $('photo-go').addEventListener('click', startPhoto);
  $('photo-save').addEventListener('click', savePhoto);

  // --- start up ------------------------------------------------------------------------------
  Promise.all([T.status(), T.api('/api/assess/config').catch(function () { return null; })]).then(function (res) {
    S.status = res[0];
    S.config = res[1];
    S.langs = S.status ? S.status.languages : [{ code: 'en', name: 'English', verified: true }, { code: 'es', name: 'Spanish', verified: true }];
    ['lang', 'import-lang', 'photo-lang'].forEach(function (id) { fillLangs($(id), 'en'); });
    onLang();
    if (S.config) $('limit').value = S.config.time_limit_s;
    applyFeatures();
    return Promise.all([loadTests(), loadSessions()]);
  }).then(function () {
    A.store.persistent().then(function (ok) {
      if (!ok) $('storage-note').textContent = 'This browser is blocking storage (a private window?), so sessions last only until the page closes. Export them before leaving.';
    });
  });

  T.assess = { state: S };
})();
