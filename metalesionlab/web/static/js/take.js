/* The public naming test: 20 pictures, then accuracy, naming speed and a plain-language breakdown,
   beside the range of adults who took this same test (once enough have). Same engine as /assess.
   Wording rule: report numbers only; never judge the person's result. */
(function () {
  'use strict';
  var T = window.TOT, A = window.TLA, h = T.h;
  var ITI_MS = 500;
  var LANG_LABEL = { en: 'English', es: 'Español', fr: 'Français', pt: 'Português' };
  var HELLO = { en: 'hello', es: 'hola', fr: 'bonjour', pt: 'olá' };
  var PLAIN = {
    Correct: ['named correctly', 'named correctly'],
    Semantic: ['related word (like "dog" for a cat)', 'related words (like "dog" for a cat)'],
    Formal: ['word that sounds similar (like "hat" for cat)', 'words that sound similar (like "hat" for cat)'],
    Mixed: ['word related in both meaning and sound', 'words related in both meaning and sound'],
    Nonword: ['made-up word that sounds like the name', 'made-up words that sound like the name'],
    Neologism: ['made-up word', 'made-up words'],
    Unrelated: ['unrelated word', 'unrelated words'],
    Description: ['description instead of the name', 'descriptions instead of the name'],
    Visual: ['word for something that looks similar', 'words for things that look similar'],
    NoResponse: ['picture with no answer (or "I don\'t know")', 'pictures with no answer (or "I don\'t know")']
  };
  var S = { config: null, sets: [], set: null, items: [], cap: null, run: null, norms: null, limitS: 20 };
  function $(id) { return document.getElementById(id); }
  function show(step) {
    ['step-intro', 'step-mic', 'step-wait', 'step-result'].forEach(function (id) { $(id).hidden = id !== step; });
    $(step).scrollIntoView({ block: 'start' });
  }

  // --- step 1: language and agreement --------------------------------------------------------
  function chooseLang(set) {
    S.set = set;
    Array.prototype.forEach.call($('lang-choice').children, function (b) { b.setAttribute('aria-pressed', b.dataset.set === set.id ? 'true' : 'false'); });
    $('hello-word').textContent = '"' + (HELLO[set.lang] || 'hello') + '"';
    $('how-text').textContent = howText(set.lang);
    updateGo();
  }
  function langInfo(code) { return ((S.config && S.config.languages) || []).filter(function (l) { return l.code === code; })[0] || null; }
  function howText(code) {
    var l = langInfo(code);
    if (!l) return 'say the name with one word.';
    return l.instruction.charAt(0).toLowerCase() + l.instruction.slice(1) + (l.example ? ' For example: "' + l.example + '".' : '');
  }
  function updateGo() { $('go-mic').disabled = !(S.set && $('agree').checked && A.Capture.supported()); }

  // --- step 2: microphone ---------------------------------------------------------------------
  function micCheck() {
    show('step-mic');
    var heard = 0, last = performance.now();
    S.cap = new A.Capture();
    S.cap.onlevel = function (db) {
      var pctLevel = Math.max(0, Math.min(100, (db + 70) * 1.6));
      $('meter').style.width = pctLevel + '%';
      $('meter-box').setAttribute('aria-valuenow', String(Math.round(pctLevel)));
      var now = performance.now();
      if (db > -38) heard += now - last;
      last = now;
      if (heard > 250 && $('go-test').disabled) {
        $('mic-msg').textContent = 'We can hear you. Ready when you are.';
        $('go-test').disabled = false;
        $('go-test').focus();
      }
    };
    loadItems().then(function () { return S.cap.start(); }).then(function () {
      $('mic-msg').textContent = 'Listening… say ' + $('hello-word').textContent + '.';
      setTimeout(function () {
        if ($('go-test').disabled) { $('mic-msg').textContent = 'It\'s quiet here. Check that the right microphone is on, or start anyway.'; $('go-test').disabled = false; }
      }, 7000);
    }).catch(function (e) {
      $('mic-msg').textContent = e && e.name === 'NotAllowedError' ? 'The microphone was blocked. Allow it in your browser\'s settings, then reload this page.'
        : 'The microphone couldn\'t start (' + (e.message || e) + ').';
    });
  }
  function loadItems() {
    return T.api('/api/sets/' + encodeURIComponent(S.set.id)).then(function (d) {
      S.items = (d.manifest ? d.manifest.items : []).map(function (it, i) {
        return { index: i, target: it.word, image: it.image, status: it.status };
      }).filter(function (it) { return it.status === 'kept' && it.image; }).map(function (it, k) {
        return { n: k + 1, index: it.index, target: it.target, image: it.image, url: T.mediaUrl(S.set.id, it.image), status: 'waiting' };
      });
      S.items.forEach(function (it) { var img = new Image(); img.src = it.url; });
    });
  }

  // --- step 3: the test --------------------------------------------------------------------------
  function startTest() {
    S.cap.onlevel = null;
    S.run = { k: 0, phase: 'ready' };
    $('admin').hidden = false;
    document.body.classList.add('admin-open');
    message('Name each picture', 'In ' + ((langInfo(S.set.lang) || {}).name || S.set.lang) + ': ' + howText(S.set.lang) +
      ' Then tap Next or press the space bar.', 'Show the first picture');
    $('admin-next').focus();
  }
  function message(title, text, label) {
    $('admin-img').hidden = true;
    var m = $('admin-msg');
    m.hidden = false;
    m.innerHTML = '';
    m.appendChild(h('h2', { text: title }));
    if (text) m.appendChild(h('p', { text: text }));
    $('admin-next').textContent = label || 'Next';
    $('admin-rec').hidden = false;
  }
  function runItem() {
    var run = S.run, it = S.items[run.k];
    run.phase = 'blank';
    $('admin-msg').hidden = true;
    $('admin-img').hidden = true;
    $('admin-next').textContent = 'Next';
    $('admin-count').textContent = (run.k + 1) + ' of ' + S.items.length;
    setTimeout(function () {
      A.reveal($('admin-img'), it.url).then(function (onset) {
        if (S.run !== run || run.phase !== 'blank') return;
        run.phase = 'picture';
        run.onsetFrame = S.cap.frameAt(onset);
        run.timer = setTimeout(function () { endItem('limit'); }, S.limitS * 1000);
      });
    }, ITI_MS);
  }
  function endItem(reason, ts) {
    var run = S.run;
    if (!run || run.phase !== 'picture') return;
    clearTimeout(run.timer);
    run.phase = 'between';
    var it = S.items[run.k], rate = S.cap.rate;
    var limitFrame = run.onsetFrame + Math.round(S.limitS * rate);
    var endFrame = reason === 'limit' ? limitFrame : Math.min(limitFrame, S.cap.frameAt(ts || performance.now()));
    $('admin-img').hidden = true;
    it.status = 'pending';
    S.cap.clip(run.onsetFrame - Math.round(A.LEAD_IN_MS / 1000 * rate), endFrame).then(function (blob) { score(it, blob); });
    run.k++;
    if (run.k >= S.items.length) finish(); else runItem();
  }
  function next(e) {
    var run = S.run;
    if (!run) return;
    if (run.phase === 'ready') runItem();
    else if (run.phase === 'picture') endItem('next', e && e.timeStamp);
  }
  function stop() {
    if (!S.run || !confirm('Stop the test? Your results so far won\'t be shown.')) return;
    clearTimeout(S.run.timer);
    S.run = null;
    closeAdmin();
    if (S.cap) { S.cap.stop(); S.cap = null; }
    location.reload();
  }
  function closeAdmin() {
    $('admin').hidden = true;
    document.body.classList.remove('admin-open');
  }
  function finish() {
    S.run.phase = 'done';
    closeAdmin();
    setTimeout(function () { if (S.cap) { S.cap.stop(); S.cap = null; } }, 1600);
    show('step-wait');
    progress();
  }

  // --- scoring ---------------------------------------------------------------------------------
  function score(it, blob) {
    A.scoreClip(blob, { target: it.target, lang: S.set.lang, onsetMs: A.LEAD_IN_MS, limitS: S.limitS, setId: S.set.id,
      index: it.index, secondRater: false }).then(function (res) {
      Object.assign(it, { status: 'done', transcript: res.transcript, scored_response: res.scored_response, code: res.code,
        latency_ms: res.latency_ms, timeout: res.timeout, receipt: res.receipt });
    }).catch(function (e) {
      it.status = 'error';
      it.error = e.message;
    }).then(progress);
  }
  function progress() {
    if (!$('step-wait').hidden || S.run && S.run.phase === 'done') {
      var done = S.items.filter(function (it) { return it.status === 'done' || it.status === 'error'; }).length;
      $('wait-bar').style.width = Math.round(100 * done / S.items.length) + '%';
      $('wait-msg').textContent = done + ' of ' + S.items.length + ' answers scored…';
      if (done === S.items.length && S.run && S.run.phase === 'done') { S.run = null; results(); }
    }
  }

  // --- step 4: results ---------------------------------------------------------------------------
  function results() {
    var done = S.items.filter(function (it) { return it.status === 'done'; });
    var failed = S.items.length - done.length;
    var m = A.summarize(done);
    show('step-result');
    $('r-acc').textContent = m.correct + ' / ' + m.n;
    $('r-lat').textContent = m.latency_n ? A.seconds(m.latency_median_ms, 1) : '–';
    var ul = $('r-breakdown');
    ul.innerHTML = '';
    T.ORDER.forEach(function (c) {
      var k = m.counts[c];
      if (!k) return;
      var words = PLAIN[c] || [c, c];
      ul.appendChild(h('li', { text: (c === 'Correct' ? k + ' ' : (k === 1 ? (/^[aeiou]/.test(words[0]) ? 'an ' : 'a ') : k + ' ')) + words[k === 1 ? 0 : 1] }));
    });
    if (failed) ul.appendChild(h('li', { class: 'muted', text: failed + ' answer' + (failed > 1 ? 's' : '') + ' couldn\'t be scored and ' + (failed > 1 ? 'are' : 'is') + ' left out.' }));
    var grid = $('r-heard');
    grid.innerHTML = '';
    S.items.forEach(function (it) {
      grid.appendChild(h('figure', null, [h('img', { src: T.mediaUrl(S.set.id, it.image, 320), alt: 'Picture ' + it.n }),
        h('figcaption', null, [h('b', { text: it.n + '. ' + it.target }),
          h('span', { class: 'said', text: it.status === 'done' ? (it.transcript ? '"' + it.transcript + '"' : '(no answer)') : '(not scored)' }),
          it.status === 'done' ? h('span', { class: 'xsmall muted', text: (PLAIN[T.normCode(it.code)] || ['', ''])[0] + (it.latency_ms != null && it.code === 'Correct' ? ' · ' + A.seconds(it.latency_ms, 1) : '') }) : null])]));
    });
    $('c-lang').textContent = (langInfo(S.set.lang) || {}).name || S.set.lang;
    $('contribute').hidden = !!failed;
    $('other-lang').hidden = S.sets.length < 2;
    reference(m);
    $('result-h').setAttribute('tabindex', '-1');
    $('result-h').focus();
  }
  function reference(m) {
    T.api('/api/assess/norms/' + encodeURIComponent(S.set.id)).then(function (norms) {
      S.norms = norms;
      if (norms.ready) {
        var c = norms.correct, n = norms.n_items || m.n;
        $('r-acc-ref').textContent = 'Adult volunteers who took this test scored ' + Math.round(c.p5) + '–' + Math.round(c.p95) + ' out of ' + n +
          ' (the middle 90% of ' + norms.n + ' volunteers).';
        A.rangeStrip($('r-acc-strip'), m.correct, [c.p5, c.p95], n, function (v) { return String(Math.round(v)); });
        var l = norms.median_latency_ms;
        $('r-lat-ref').textContent = l ? 'Their median naming speed: ' + A.seconds(l.p5, 1) + ' to ' + A.seconds(l.p95, 1) + '.' : '';
      } else {
        $('r-acc-ref').textContent = 'Reference range: being collected (n = ' + norms.n + ' so far).';
        $('r-lat-ref').textContent = '';
        $('r-acc-strip').innerHTML = '';
      }
      $('r-context').textContent = 'For context only: on a different test, the Philadelphia Naming Test (175 other pictures), adults without brain injury ' +
        'scored about 96–97% correct (Roach et al., 1996). Different pictures, so it isn\'t a comparison for your score.';
    }).catch(function () { $('r-acc-ref').textContent = ''; });
  }
  function updateSend() {
    $('c-send').disabled = !($('c-adult').checked && $('c-fluent').checked && $('c-consent').checked);
  }
  function contribute() {
    var receipts = S.items.map(function (it) { return it.receipt; }).filter(Boolean);
    $('c-send').disabled = true;
    T.api('/api/assess/norms/' + encodeURIComponent(S.set.id), { method: 'POST', json: { receipts: receipts, consent: true,
      adult_no_condition: true, age_band: $('c-age').value || null } }).then(function (r) {
      $('c-msg').textContent = 'Thank you! Your summary was added. The reference range now has ' + r.norms.n + ' volunteer' + (r.norms.n === 1 ? '' : 's') + '.';
      ['c-adult', 'c-fluent', 'c-consent', 'c-age'].forEach(function (id) { $(id).disabled = true; });
      S.items.forEach(function (it) { delete it.receipt; });
      reference(A.summarize(S.items.filter(function (it) { return it.status === 'done'; })));
    }).catch(function (e) { $('c-msg').textContent = e.message; updateSend(); });
  }
  function restart(set) {
    S.items = [];
    ['c-adult', 'c-fluent', 'c-consent', 'c-age'].forEach(function (id) { $(id).disabled = false; $(id).checked = false; });
    $('c-msg').textContent = '';
    $('go-test').disabled = true;
    chooseLang(set || S.set);
    micCheck();
  }

  // --- wiring ------------------------------------------------------------------------------------
  $('agree').addEventListener('change', updateGo);
  $('go-mic').addEventListener('click', micCheck);
  $('go-test').addEventListener('click', startTest);
  $('admin-next').addEventListener('click', next);
  $('admin-end').addEventListener('click', stop);
  ['c-adult', 'c-fluent', 'c-consent'].forEach(function (id) { $(id).addEventListener('change', updateSend); });
  $('c-send').addEventListener('click', contribute);
  $('again').addEventListener('click', function () { restart(); });
  $('other-lang').addEventListener('click', function () { location.href = '/take'; });
  document.addEventListener('keydown', function (e) {
    if (!S.run || $('admin').hidden) return;
    if (e.key === ' ' || e.key === 'ArrowRight' || e.key === 'Enter') { e.preventDefault(); next(e); }
  });
  window.addEventListener('beforeunload', function (e) { if (S.run) { e.preventDefault(); e.returnValue = ''; } });

  Promise.all([T.status(), T.api('/api/assess/config')]).then(function (res) {
    S.status = res[0];
    S.config = res[1];
    S.limitS = S.config.time_limit_s;
    S.sets = S.config.public_sets;  // demo sets in verified languages
    var box = $('lang-choice');
    S.sets.forEach(function (s) {
      box.appendChild(h('button', { type: 'button', class: 'btn', 'data-set': s.id, 'aria-pressed': 'false', onclick: function () { chooseLang(s); } },
        (LANG_LABEL[s.lang] || s.lang) + ' · ' + s.n_items + ' pictures'));
    });
    var want = T.param('lang');
    var pick = S.sets.filter(function (s) { return s.lang === want; })[0] || S.sets.filter(function (s) { return s.lang === (navigator.language || 'en').slice(0, 2); })[0] || S.sets[0];
    if (pick) chooseLang(pick);
    var sel = $('c-age');
    sel.appendChild(h('option', { value: '', text: 'Prefer not to say' }));
    S.config.age_bands.forEach(function (b) { sel.appendChild(h('option', { value: b, text: b })); });
    var notes = [];
    if (!A.Capture.supported()) notes.push('This browser can\'t record here. Try a current Chrome, Edge, Firefox or Safari.');
    if (S.status && !S.status.features.meta_api) notes.push('Scoring is off on this server right now.');
    if (!S.sets.length) notes.push('No test is available on this server yet.');
    $('feature-note').hidden = !notes.length;
    $('feature-note').textContent = notes.join(' ');
    updateGo();
  }).catch(function (e) { $('feature-note').hidden = false; $('feature-note').textContent = 'The test couldn\'t load: ' + e.message; });
})();
