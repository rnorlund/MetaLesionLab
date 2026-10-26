/* Guided tour: about two minutes across the site, AI science first, with real demo data and no API calls.
   The Scorer part replays answers recorded once with the real pipeline (static/tour/scorer_demo.json).
   The current step lives in sessionStorage, so the tour carries on across page loads. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var STEP_KEY = 'tot-tour-step', OFFER_KEY = 'tot-tour-offer-done';
  var STUDIO_SET = 'demo_es', PHONE = 640;

  function q(sel) { return document.querySelector(sel); }
  function store(kind, key, value) {
    try {
      var s = kind === 'session' ? window.sessionStorage : window.localStorage;
      if (value === undefined) return s.getItem(key);
      if (value === null) s.removeItem(key); else s.setItem(key, value);
    } catch (e) { /* storage off: the tour still works within one page */ }
    return null;
  }
  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function phone() { return window.innerWidth < PHONE; }
  function quote(s) { return '“' + s + '”'; }
  function visible(el) { return el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length); }
  function waitFor(sel, ms) {
    var t0 = Date.now();
    return new Promise(function (resolve) {
      (function poll() {
        var el = q(sel);
        if (visible(el)) return resolve(el);
        if (Date.now() - t0 > (ms || 5000)) return resolve(null);
        setTimeout(poll, 100);
      })();
    });
  }
  var fixture = null;
  function loadFixture() {
    if (!fixture) fixture = fetch('/static/tour/scorer_demo.json').then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    return fixture;
  }

  // --- page data helpers --------------------------------------------------------------------
  function studioItem(word) {
    var d = T.studio && T.studio.data();
    if (!d || !d.manifest || d.id !== STUDIO_SET) return null;
    var i = d.manifest.items.findIndex(function (it) { return it.word === word; });
    return i < 0 ? null : { index: i, item: d.manifest.items[i] };
  }
  function keptCandidate(it) { return (it.candidates || []).filter(function (c) { return c.file === it.image; })[0]; }
  function studioPrep() {
    return T.studio.ready.then(function () { T.studio.closeItem(); return T.studio.openSet(STUDIO_SET); });
  }
  function scorerPrep(upTo) {
    return Promise.all([T.scorer.ready, loadFixture()]).then(function (res) {
      var fx = res[1];
      if (!fx) return;
      T.scorer.demoStart(fx);
      var chain = Promise.resolve();
      for (var i = T.scorer.demoRows(); i <= upTo && i < fx.items.length; i++) {
        (function (k) { chain = chain.then(function () { T.scorer.demoShow(k); return T.scorer.demoAdd(k); }); })(i);
      }
      return chain.then(function () { T.scorer.demoShow(Math.min(upTo, fx.items.length - 1)); });
    });
  }
  var fxData = null;
  loadFixture().then(function (d) { fxData = d; });
  function fxItem(i) { return fxData && fxData.items[i]; }

  /* The lesion condition to show. First choice: the real tip-of-the-tongue example that the landing page
     and the game also use (late layers damaged, umbrella comes out as "Umb"). Otherwise: one where the cat
     is named wrongly, preferring naming-related lesions. */
  var LAB_PICKS = [['layers-40-47-noise-x2.181', 'umbrella'], ['layers-40-47-noise-x2.828', 'umbrella']];
  function labPick(L) {
    var chain = Promise.resolve(false);
    LAB_PICKS.forEach(function (pick) {
      chain = chain.then(function (found) {
        if (found) return true;
        var c = L.list.filter(function (x) { return x.id === pick[0] || String(x.id).split(':').pop() === pick[0]; })[0];
        if (!c) return false;
        return T.lab.select(c.id, pick[1]).then(function () {
          var it = L.cur.items.filter(function (x) { return x.word === pick[1]; })[0];
          return !!(it && T.normCode(it.code) !== 'Correct');
        });
      });
    });
    return chain;
  }
  function labPrep() {
    return T.lab.ready.then(function () {
      var L = T.lab.state();
      if (L.tourPicked && L.cur) return;
      return labPick(L).then(function (found) {
        if (found) { L.tourPicked = true; return; }
        return labSearch(L);
      });
    });
  }
  function labSearch(L) {
    return Promise.resolve().then(function () {
      var cands = L.list.filter(function (c) { return !c.baseline; }).sort(function (a, b) {
        return (/naming/i.test(b.label) ? 1 : 0) - (/naming/i.test(a.label) ? 1 : 0);
      });
      if (!cands.length) return;
      var chain = Promise.resolve(false);
      cands.forEach(function (c) {
        chain = chain.then(function (found) {
          if (found) return true;
          return T.lab.select(c.id, 'cat').then(function () {
            var it = L.cur.items.filter(function (x) { return x.word === 'cat'; })[0];
            return !!(it && T.normCode(it.code) !== 'Correct');
          });
        });
      });
      return chain.then(function (found) {
        if (!found) return T.lab.select(cands[0].id);
      }).then(function () { L.tourPicked = true; });
    });
  }
  function labFacts() { return T.lab.facts(); }
  function L0() { return T.lab.state(); }
  function startsWord(part, word) {
    var a = String(part || '').toLowerCase().replace(/[^a-z\u00e0-\u00ff]/g, ''), b = String(word || '').toLowerCase();
    return a.length >= 2 && a !== b && b.indexOf(a) === 0;
  }
  function sampleNote(f) {
    return f.sample ? ' Sample data for now: real lesion runs replace it this week.' : '';
  }

  // With real lesion files the Model Lab steps follow whatever exists, and skip what doesn't.
  function noLab() { var L = T.lab && T.lab.state(); return !L || !L.cur || !!L.cur.baseline; }
  function noLens() { return noLab() || !labFacts().intact; }
  function noLesionLens() { return noLab() || !labFacts().lesioned; }

  // --- the steps ----------------------------------------------------------------------------
  var STEPS = [
    { page: '/', url: '/', target: function () { return phone() ? '.lens-card' : '.hero-pair'; }, title: 'Tippa Lingua in 2 minutes',
      body: 'One picture-naming test for people and AI. On the left, a person who can’t find a word; on the right, Muse Glimmer, Meta’s open model, whose best guess we can read after every layer. First we look inside the AI, then you can play against it, then the tools for people. Real demo data, no microphone, no AI calls.' },

    { page: '/lab', url: '/lab', id: 'lab', before: labPrep, skip: noLab, target: '#items .card[aria-pressed="true"]', title: '1 · Look inside the AI',
      body: function () {
        var f = labFacts(), spec = f.spec;
        var amount = spec.fraction != null ? +(spec.fraction <= 1 ? spec.fraction * 100 : spec.fraction).toFixed(2) + '% of its units'
          : spec.units != null ? Number(spec.units).toLocaleString('en-US') + ' units' : 'some units';
        var where = f.layers ? 'decoder layers ' + f.layers : (spec.site || 'one part of the model');
        var how = { zero: 'switched off', mean: 'replaced with their average activity', noise: 'disturbed with noise' }[String(spec.method).toLowerCase()] || 'lesioned';
        var said = f.lesioned ? (f.lesioned.said ? 'it now says ' + quote(f.lesioned.said) : 'it now gives no answer') + ' (' + T.codeInfo(f.lesioned.code).label + ')' : 'see what it says';
        var acc = f.baseAccuracy != null && f.accuracy != null ? ' Naming accuracy went from ' + Math.round(f.baseAccuracy) + '% intact to ' + Math.round(f.accuracy) + '%.'
          : f.accuracy != null ? ' Naming accuracy: ' + Math.round(f.accuracy) + '%.' : '';
        var what = L0().cur && L0().cur.featured && f.label ? 'This condition: ' + quote(f.label) + ' (orange on the model map)'
          : 'In this condition ' + amount + ' in ' + where + ' were ' + how + ' (orange on the model map)';
        return 'Muse Glimmer, Meta’s open-weight model, took the same naming test, and we damaged it on purpose. ' + what + '. Shown the ' + f.word + ', ' + said + '.' + acc + sampleNote(f);
      } },

    { page: '/lab', url: '/lab', before: labPrep, skip: noLens, target: '#lens-chart', title: 'The word lens',
      onShow: function () {
        var f = labFacts();
        return T.lab.play(3200).then(function () { if (f.intact) T.lab.showLayer(f.intact.concept || f.intact.emerge || 52); });
      },
      body: function () {
        var f = labFacts(), i = f.intact;
        if (!i) return 'The word lens reads the model’s best guess after each of its 52 layers.';
        var text = 'The word lens reads the model’s best guess after each of its 52 layers. Intact (blue): p(' + f.word + ') stays near zero through layer ' + (i.rise ? i.rise - 1 : '?') + '. ' +
          (i.concept ? 'At layer ' + i.concept + ' the top guess is ' + quote(i.conceptWord) + (i.conceptWord === '猫' ? ', Chinese for cat' : '') + ': the concept is there before the word. ' : '') +
          (i.emerge ? quote(f.word) + ' wins from layer ' + i.emerge + ', ending at p = ' + i.final.toFixed(2) + '.' : '');
        if (f.sample && f.word === 'cat') text += ' These intact cat values at layers 40–52 are real measurements.';
        return text;
      } },

    { page: '/lab', url: '/lab', before: labPrep, skip: noLesionLens, target: '#lens-chart', title: 'Tip of the tongue',
      onShow: function () { T.lab.showLayer(52); },
      body: function () {
        var f = labFacts(), l = f.lesioned, i = f.intact;
        if (!l) return 'Pick a lesion condition to compare its curve with the intact model.';
        if (startsWord(l.said, f.word)) {
          return 'With the damage (orange), the right word drops out of first place in the damaged layers, and only its start comes out: ' + quote(String(l.said).trim()) +
            '. The lens reads only the first piece of a word, which is why p(' + f.word + ') still ends high; the rest never comes. A tip-of-the-tongue moment: some people with aphasia also get the first sound out, but not the word.' + sampleNote(f);
        }
        var start = 'With the lesion (orange), ' + (l.conceptKept && i ? 'the concept is still there at layer ' + i.concept + ', but ' : 'p(' + f.word + ') ends at ' + l.final.toFixed(2) + ' and ');
        var kind = l.code === 'NoResponse' ? 'no answer comes out' : (/^[aeiou]/i.test(l.code) ? 'an ' : 'a ') + T.codeInfo(l.code).label.toLowerCase() + ' error';
        return start + quote(l.winner) + ' wins at the last layer: ' + kind + ', the kind of slip people with aphasia make.' + sampleNote(f);
      } },

    { page: '/lab', url: '/lab', before: labPrep, skip: noLab, target: ['#human-pooled .profile-row:nth-child(1)', '#human-pooled .profile-row:nth-child(2)'],
      title: 'Compared with people',
      body: function () {
        var f = labFacts();
        return 'Across all items, the model’s error profile is set beside published group averages for people with aphasia (cited papers; no participant data). ' +
          'The closer the mix of error types, the higher the similarity. Next: try the same pictures yourself.' + (f.sample ? ' With sample data these numbers are illustrative.' : '');
      } },

    { page: '/challenge', url: '/challenge', id: 'challenge', target: function () { return phone() ? '#intro h1' : '.cg-intro-text'; }, title: '2 · You vs. the AI',
      before: function () { return T.challenge ? T.challenge.ready() : null; },
      body: function () {
        var d = T.challenge && T.challenge.state().data, ins = d && d.inside;
        var moment = ins && ins.damaged && ins.damaged.said ? ' (for the ' + ins.word + ', the damaged model says only ' + quote(ins.damaged.said) + ')' : '';
        return 'Anyone can try the same test: name 10 pictures, then see how Glimmer named them and watch a word get lost inside it' + moment +
          '. Typed answers are scored on our server by fixed rules, with no AI calls, and nothing is stored. A shareable result card comes at the end.';
      } },

    { page: '/scorer', url: '/scorer?set=demo_en', id: 'scorer', before: function () { return scorerPrep(0); },
      skip: function () { return !fxData; },
      target: function () { return phone() ? '#resp-body tr:nth-child(1)' : ['#stage', '#resp-body tr:nth-child(1)']; },
      title: '3 · Score people’s answers',
      body: function () {
        var it = fxItem(0);
        return 'Spoken answers, scored automatically (verified in English, Spanish, French and Brazilian Portuguese). Here we replay three answers recorded once through the real pipeline: no microphone, no API call. For the ' +
          it.target + ' the speaker said ' + quote(it.said) + '. Muse Voice Transcribe heard ' + quote(it.transcript) + ', and the rules coded it ' +
          T.codeInfo(it.code).label + (it.code === 'Semantic' ? ': related in meaning, not in sound.' : '.');
      } },

    { page: '/scorer', url: '/scorer?set=demo_en', before: function () { return scorerPrep(2); }, skip: function () { return !fxData; },
      target: '#resp-table', title: 'Sound errors too',
      body: function () {
        var a = fxItem(1), b = fxItem(2);
        return quote(a.transcript) + ' for ' + a.target + ' shares sounds but not meaning: ' + T.codeInfo(a.code).label + '. ' + quote(b.transcript) + ' for ' + b.target + ' is ' +
          T.codeInfo(b.code).label + '. The codes follow the Philadelphia Naming Test scheme: semantic, formal, mixed, nonword, neologism, unrelated, description and no response.';
      } },

    { page: '/scorer', url: '/scorer?set=demo_en', before: function () { return scorerPrep(2); }, skip: function () { return !fxData; },
      target: '#resp-body tr:nth-child(1) td:nth-child(6)', title: 'A second opinion',
      body: function () {
        var it = fxItem(0), s = it.second || {};
        return 'Muse Spark codes every answer on its own as a second rater, without seeing the first code. Here it ' +
          (it.agree ? 'agrees' : 'says ' + T.codeInfo(s.code).label) + (s.rationale ? ': ' + quote(s.rationale) : '.') + ' Disagreements are highlighted for the reviewer.';
      } },

    { page: '/scorer', url: '/scorer?set=demo_en', before: function () { return scorerPrep(2); }, skip: function () { return !fxData; },
      target: '#resp-body tr:nth-child(2) td:nth-child(7)', title: 'A person has the final say',
      body: 'Change any code here and the summary updates. Exports keep the automatic code, the second rater’s code and the reviewer’s. Nothing is a diagnosis. Last stop: making tests where none exist.' },

    { page: '/studio', url: '/studio?set=' + STUDIO_SET, id: 'studio', before: studioPrep, skip: function () { return !studioItem('gato'); },
      target: '.card[data-word="gato"]', title: '4 · Fill the gaps: a Spanish picture test',
      body: function () {
        var g = studioItem('gato'), c = keptCandidate(g.item), d = T.studio.data();
        return 'Where a language has no ready-made test, Test Studio makes one. Muse Image drew ' + g.item.candidates.length + ' candidate pictures for each of the ' + d.manifest.items.length +
          ' Spanish words. Each is checked: SAM 3.1 found ' + c.sam_objects + ' clear object here (confidence ' + c.sam_confidence.toFixed(2) +
          '), and Muse Spark, asked to name it in Spanish, said ' + quote(c.spark_name) + '. Both checks pass, so it’s kept.';
      } },

    { page: '/studio', url: '/studio?set=' + STUDIO_SET, skip: function () { return !studioItem('sierra'); },
      before: function () {
        return studioPrep().then(function () { T.studio.openItem(studioItem('sierra').index, { modal: false }); });
      },
      target: '#item-dialog .cand',
      title: 'Held for review',
      body: function () {
        var it = studioItem('sierra').item;
        var names = (it.candidates || []).map(function (c) { return c.spark_name.toLowerCase(); });
        var same = names.every(function (n) { return n === names[0]; });
        var said = same ? quote(names[0]) + (names.length === 2 ? ' both times' : ' every time') : names.map(quote).join(' and ');
        return 'For ' + quote('sierra') + ' (' + (it.hint || it.gloss) + '), Muse Spark said ' + said +
          (names[0] === 'serrucho' ? ', the everyday Spanish word for a handsaw' : '') +
          '. People may name this picture differently, so instead of keeping it the tool holds it for a person to decide: accept ' +
          quote(names[0]) + ' as an alternate name, pick another picture or drop the item.';
      } },

    { page: null, title: 'Now try it yourself', finish: true,
      body: 'Everything you saw runs on Meta’s models: Muse Glimmer (open weights), Muse Spark, Muse Voice Transcribe, Muse Image and SAM 3.1. Pick a starting point:' }
  ];

  function firstStep(id) {
    var i = STEPS.findIndex(function (s) { return s.id === id; });
    return i < 0 ? 0 : i;
  }

  // --- UI -------------------------------------------------------------------------------------
  var ui = null, current = -1, busy = false, lastFocus = null;

  function buildUI() {
    if (ui) return ui;
    ui = {};
    ui.shade = h('div', { class: 'tour-shade', 'aria-hidden': 'true' });
    ui.spot = h('div', { class: 'tour-spot', 'aria-hidden': 'true' });
    ui.progress = h('span', { class: 'tour-progress' });
    ui.bar = h('div', { class: 'tour-bar' }, h('div'));
    ui.title = h('h2', { id: 'tour-title' });
    ui.body = h('p', { id: 'tour-body' });
    ui.extra = h('div', { class: 'tour-extra' });
    ui.back = h('button', { type: 'button', class: 'btn btn-small', onclick: function () { go(current - 1, -1); } }, 'Back');
    ui.next = h('button', { type: 'button', class: 'btn btn-primary btn-small', onclick: function () { go(current + 1, 1); } }, 'Next');
    ui.skip = h('button', { type: 'button', class: 'tour-skip', onclick: end }, 'Skip tour');
    ui.card = h('div', { class: 'tour-card', role: 'dialog', 'aria-modal': 'false', 'aria-labelledby': 'tour-title', 'aria-describedby': 'tour-body', tabindex: '-1' }, [
      h('div', { class: 'tour-top' }, [ui.progress, h('button', { type: 'button', class: 'tour-x', 'aria-label': 'Close the tour', onclick: end }, '×')]),
      ui.bar, ui.title, ui.body, ui.extra,
      h('div', { class: 'tour-actions' }, [ui.skip, h('span', { class: 'tour-gap' }), ui.back, ui.next])
    ]);
    document.body.appendChild(ui.shade);
    document.body.appendChild(ui.spot);
    document.body.appendChild(ui.card);
    document.documentElement.classList.add('tour-on');  // room to scroll targets above the phone caption sheet
    window.addEventListener('scroll', place, true);
    window.addEventListener('resize', place);
    return ui;
  }

  function targetsFor(step) {
    var t = typeof step.target === 'function' ? step.target() : step.target;
    if (!t) return [];
    return [].concat(t).map(function (sel) { return q(sel); }).filter(visible);
  }

  function unionRect(els) {
    var r = null;
    els.forEach(function (el) {
      var b = el.getBoundingClientRect();
      r = r ? { top: Math.min(r.top, b.top), left: Math.min(r.left, b.left), right: Math.max(r.right, b.right), bottom: Math.max(r.bottom, b.bottom) }
        : { top: b.top, left: b.left, right: b.right, bottom: b.bottom };
    });
    return r;
  }

  function place() {
    if (!ui || current < 0) return;
    var step = STEPS[current], els = targetsFor(step), card = ui.card, pad = 6;
    var vw = window.innerWidth, vh = window.innerHeight;
    card.classList.toggle('sheet', phone());
    if (!els.length) {
      ui.spot.style.display = 'none';
      ui.shade.style.display = 'block';
      card.classList.add('centered');
      card.style.left = card.style.top = '';
      return;
    }
    card.classList.remove('centered');
    ui.shade.style.display = 'none';
    var r = unionRect(els);
    // Clip to the viewport: a wide table cell must not push the page sideways.
    r = { top: r.top, bottom: r.bottom, left: Math.max(r.left, pad + 2), right: Math.min(r.right, vw - pad - 2) };
    ui.spot.style.display = 'block';
    ui.spot.style.top = (r.top - pad) + 'px';
    ui.spot.style.left = (r.left - pad) + 'px';
    ui.spot.style.width = Math.max(0, r.right - r.left + 2 * pad) + 'px';
    ui.spot.style.height = (r.bottom - r.top + 2 * pad) + 'px';
    if (phone()) { card.style.left = card.style.top = ''; return; }
    var cw = card.offsetWidth, ch = card.offsetHeight, gap = 14, top, left;
    var clampX = function (x) { return Math.max(12, Math.min(vw - cw - 12, x)); };
    var clampY = function (y) { return Math.max(12, Math.min(vh - ch - 12, y)); };
    if (r.bottom + pad + gap + ch < vh - 8) { top = r.bottom + pad + gap; left = clampX(r.left); }
    else if (r.top - pad - gap - ch > 8) { top = r.top - pad - gap - ch; left = clampX(r.left); }
    else if (r.right + pad + gap + cw < vw - 8) { left = r.right + pad + gap; top = clampY(r.top); }
    else if (r.left - pad - gap - cw > 8) { left = r.left - pad - gap - cw; top = clampY(r.top); }
    else {
      // No free side: the corner that covers the least of the spotlight.
      var best = null;
      [[12, 12], [vw - cw - 12, 12], [12, vh - ch - 12], [vw - cw - 12, vh - ch - 12]].forEach(function (c) {
        var ox = Math.max(0, Math.min(r.right + pad, c[0] + cw) - Math.max(r.left - pad, c[0]));
        var oy = Math.max(0, Math.min(r.bottom + pad, c[1] + ch) - Math.max(r.top - pad, c[1]));
        if (!best || ox * oy < best[2]) best = [c[0], c[1], ox * oy];
      });
      left = best[0];
      top = best[1];
    }
    card.style.left = left + 'px';
    card.style.top = top + 'px';
  }

  function scrollToTargets(els) {
    if (!els.length) return;
    // Bring a cell inside a horizontally scrolling table into view first.
    var wrap = els[0].closest('.table-wrap');
    if (wrap && wrap.scrollWidth > wrap.clientWidth) {
      var cb = els[0].getBoundingClientRect(), wb = wrap.getBoundingClientRect();
      if (cb.width >= wb.width) wrap.scrollLeft = 0;  // a whole row: start from its first columns
      else wrap.scrollLeft += (cb.left + cb.width / 2) - (wb.left + wb.width / 2);
    }
    var r = unionRect(els), vh = window.innerHeight;
    var reserve = phone() ? ui.card.offsetHeight + 24 : 0;  // the caption sheet covers the bottom on phones
    var room = vh - reserve;
    var inner = els[0].closest('dialog');
    if (inner) { els[0].scrollIntoView({ block: 'start' }); return; }
    var height = r.bottom - r.top, wantTop;
    if (phone()) {
      wantTop = 12;
      if (r.top >= 8 && r.bottom <= room - 8) return;  // already clear of the caption sheet
    } else {
      // Leave room for the caption below the target when both fit; otherwise centre the target.
      var needed = height + 20 + ui.card.offsetHeight;
      wantTop = needed + 24 <= vh ? (vh - needed) / 2 : Math.max(12, (vh - height) / 2);
    }
    window.scrollBy(0, r.top - wantTop);
  }

  function render(step) {
    buildUI();
    ui.progress.textContent = 'Step ' + (current + 1) + ' of ' + STEPS.length;
    ui.bar.firstChild.style.width = (100 * (current + 1) / STEPS.length) + '%';
    ui.title.textContent = step.title;
    var body = typeof step.body === 'function' ? step.body() : step.body;
    ui.body.textContent = body;
    ui.extra.innerHTML = '';
    ui.back.disabled = current === 0;
    ui.next.hidden = !!step.finish;
    ui.skip.textContent = step.finish ? 'Close' : 'Skip tour';
    if (step.finish) {
      [['Play: You vs. the AI', '/challenge'], ['Explore the Model Lab', '/lab'], ['Score a session', '/scorer'], ['Build a test in your language', '/studio']].forEach(function (b, k) {
        ui.extra.appendChild(h('a', { class: 'btn ' + (k === 0 ? 'btn-primary' : ''), href: b[1], onclick: function () { stop(); } }, b[0]));
      });
    }
  }

  function go(i, dir) {
    if (busy || i < 0 || i >= STEPS.length) return Promise.resolve();
    var step = STEPS[i];
    current = i;
    store('session', STEP_KEY, String(i));
    if (step.page && location.pathname !== step.page) {
      location.href = step.url;
      return Promise.resolve();
    }
    busy = true;
    buildUI();
    ui.card.classList.add('loading');
    var prep = step.before ? Promise.resolve().then(step.before).catch(function () { /* show what we can */ }) : Promise.resolve();
    return prep.then(function () {
      if (step.skip && step.skip()) return 'skip';
      var sels = typeof step.target === 'function' ? step.target() : step.target;
      if (!sels) return 'ok';
      return Promise.all([].concat(sels).map(function (sel) { return waitFor(sel, 6000); })).then(function (els) {
        return els.every(Boolean) ? 'ok' : 'skip';
      });
    }).then(function (state) {
      busy = false;
      ui.card.classList.remove('loading');
      if (state === 'skip') {
        var nextI = i + (dir || 1);
        return nextI >= 0 && nextI < STEPS.length ? go(nextI, dir || 1) : end();
      }
      render(step);
      place();
      scrollToTargets(targetsFor(step));
      place();
      ui.card.focus({ preventScroll: true });
      if (step.onShow) Promise.resolve().then(step.onShow).catch(function () {});
    });
  }

  function stop() {
    store('session', STEP_KEY, null);
    current = -1;
    if (ui) {
      [ui.shade, ui.spot, ui.card].forEach(function (el) { el.remove(); });
      document.documentElement.classList.remove('tour-on');
      window.removeEventListener('scroll', place, true);
      window.removeEventListener('resize', place);
      ui = null;
    }
  }

  function end() {
    stop();
    if (T.scorer) T.scorer.demoEnd();
    if (T.studio) T.studio.closeItem();
    if (T.lab) T.lab.hideLayer();
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  function start(fromId) {
    store('local', OFFER_KEY, '1');
    var offer = q('.tour-offer');
    if (offer) offer.remove();
    lastFocus = document.activeElement;
    return go(firstStep(fromId), 1);
  }

  document.addEventListener('keydown', function (e) {
    if (!ui || current < 0) return;
    if (e.key === 'Escape') { e.preventDefault(); end(); return; }
    if (!ui.card.contains(document.activeElement)) return;
    if (e.key === 'ArrowRight' && !STEPS[current].finish) { e.preventDefault(); go(current + 1, 1); }
    if (e.key === 'ArrowLeft' && current > 0) { e.preventDefault(); go(current - 1, -1); }
  });

  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('[data-tour-start]');
    if (!btn) return;
    e.preventDefault();
    start(btn.getAttribute('data-tour-start') || null);
  });

  function offer() {
    if (store('local', OFFER_KEY) || q('.tour-offer')) return;
    var close = function () { store('local', OFFER_KEY, '1'); box.remove(); };
    var box = h('aside', { class: 'tour-offer', 'aria-label': 'Guided tour' }, [
      h('p', null, [h('b', { text: 'New here?' }), ' Take the 2-minute tour.']),
      h('button', { type: 'button', class: 'btn btn-primary btn-small', 'data-tour-start': '' }, 'Take the tour'),
      h('button', { type: 'button', class: 'tour-x', 'aria-label': 'No thanks', onclick: close }, '×')
    ]);
    document.body.appendChild(box);
  }

  T.tour = { start: start, end: end, go: go, steps: STEPS, current: function () { return current; } };

  // Carry on after the tour itself changed page; if the visitor went somewhere else, drop the tour.
  var saved = store('session', STEP_KEY), step = saved != null ? STEPS[+saved] : null;
  if (step && (!step.page || step.page === location.pathname)) {
    lastFocus = document.body;
    loadFixture().then(function () { go(+saved, 1); });
  } else {
    if (saved != null) store('session', STEP_KEY, null);
    offer();
  }
})();
