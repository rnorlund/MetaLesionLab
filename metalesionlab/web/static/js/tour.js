/* Guided tour: about 90 seconds of Plato's Chair, with Socrates as the guide. Each step shows his portrait
   (a doodle by Meta's Muse Image) and a speech bubble: a question first, then a short pointer. The lines are
   written in advance and every number in them comes from the write-ups (docs/plato*.md; tests/test_site.py
   checks them), so the tour makes no AI calls. Blind draw first: on the landing page Socrates asks for a
   chair before anything of Muse Image's is shown; the chairs appear when the visitor draws or presses Next.
   The current step lives in sessionStorage, so the tour carries on across page loads. At most 10 steps; it
   ends at /draw when the server has that page (TOT.hasPage), with "Ask me yourself" (/socrates).
   It is the Plato's Chair site's tour: where /plato isn't served (the Lingua site, MLL_SITE=lingua) it does nothing. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  if (!T.hasPage('/plato')) return;
  var STEP_KEY = 'tot-tour-step', OFFER_KEY = 'tot-tour-offer-done', SEEN_KEY = 'tot-draw-seen';
  var PHONE = 640;
  var FACE = '/static/img/socrates/socrates-';
  var CREDIT = 'Socrates drawn by Meta’s Muse Image. His lines are written in advance: this tour makes no AI calls.';

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
  function still() { return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches; }
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
  function hasDraw() { return T.hasPage ? T.hasPage('/draw') : false; }
  function hasSocrates() { return T.hasPage ? T.hasPage('/socrates') : false; }

  // --- the blind draw on the landing page ----------------------------------------------------------
  function landingPad() { return T.landing && T.landing.draw && q('#hero-draw'); }
  function revealed() { return document.body.classList.contains('revealed') || !q('#reveal') || !q('#reveal').hidden; }
  function revealChairs() { if (T.landing && T.landing.reveal) T.landing.reveal('tour'); }
  // From the chairs on, a drawing in this tab isn't blind any more (draw.js reads the same flag).
  function markSeen() {
    store('session', SEEN_KEY, '1');
    if (window.TOTDraw && window.TOTDraw.markSeen) window.TOTDraw.markSeen();
  }

  // --- Plato page data ----------------------------------------------------------------------------
  function platoReady() { return T.plato ? T.plato.ready : Promise.resolve(); }
  function P() { return T.plato && T.plato.state().data; }
  function noPlato() { return !P(); }
  function chairOnPlato() {
    return platoReady().then(function () { if (T.plato) { T.plato.setConcept('chair'); T.plato.setWho('ai'); } });
  }

  // --- the steps: Socrates asks (q), then points (p) -----------------------------------------------
  var STEPS = [
    { page: '/', url: '/', id: 'ask', target: '#hero-draw', face: 'questioning',
      // on a phone the caption sheet covers the bottom of the screen: light up the pad and its buttons, not the whole hero
      phoneTarget: ['#canvas-wrap', '#hero-draw .dw-actions'], kicker: 'Is there one ideal chair?', blind: true,
      skip: function () { return !landingPad(); },
      q: 'Before I tell you anything: what is a chair? Draw one, and we’ll see.',
      p: function () {
        return revealed()
          ? 'You’ve seen the machine’s chairs, so yours won’t be blind. Draw anyway, or go on.'
          : 'You have 20 seconds, like the players of Google’s Quick, Draw! game. Or press Next to see the machine’s chairs.';
      },
      next: function () { return revealed() ? 'Next' : 'Show me the machine’s chairs'; } },

    { page: '/', url: '/', id: 'home', target: '#chairs', face: 'pointing', kicker: 'Sixteen chairs',
      before: function () { revealChairs(); },
      onShow: function () {
        var at = current;
        return wait(700).then(function () { if (current === at && T.landing) { T.landing.cancelAuto(); T.landing.stack(true); } });
      },
      q: 'The machine drew the same chair sixteen times. Is that wisdom, or habit?',
      p: 'Meta’s image AI, Muse Image, drew 16 chairs; 16 people drew theirs. Stacked, the machine’s make one chair, people’s a cloud.' },

    { page: '/plato', url: '/plato', id: 'plato', face: 'neutral', kicker: 'Measuring “varied”',
      target: function () { return phone() ? '.pc-frame' : '#hero-fig'; },
      before: chairOnPlato, skip: noPlato,
      onShow: function () {
        var at = current;
        return wait(2400).then(function () { if (current === at && T.plato) T.plato.setWho('people'); });
      },
      q: 'How would you measure how varied sixteen drawings are?',
      p: 'Another Meta AI, DINOv2, judged how different the drawings look (their spread). People’s chairs differed nearly three times as much: 0.36 against 0.13.' },

    { page: '/plato', url: '/plato#everything', face: 'questioning', kicker: 'Not just chairs', target: '#rank-chart', before: platoReady, skip: noPlato,
      q: 'Was it only the chair, or does the machine do this with everything?',
      p: 'We tried 35 things; left of the line, the machine drew one more alike than people. That’s 34 of 35, typically half as varied (0.49).' },

    { page: '/plato', url: '/plato#variety', face: 'pointing', kicker: 'Can you talk it out of the chair?', target: '#var-fig', before: platoReady,
      skip: function () { var d = P(); return !d || !d.variety || !d.variety.conditions || !d.variety.conditions.listed; },
      q: 'If you ask it for “any kind of chair”, will it draw you a different one?',
      p: 'No: the same chair again. But given a list of kinds (a rocking chair, a throne), it drew 1.30 times people’s variety. The one chair is a habit.' },

    { page: '/plato', url: '/plato#variety', face: 'questioning', kicker: 'People draw the plain chair too', target: '#var-kinds', before: platoReady,
      skip: function () { var d = P(); return !d || !d.variety || !d.variety.kinds || !d.variety.kinds.summary; },
      q: 'Most people draw a chair from the side. Did you? And who taught you that?',
      p: 'Meta’s open AI model, Muse Glimmer, sorted the drawings: 84% of people’s chairs are the plain, ordinary kind. People differ in how they draw, not what.' },

    { page: '/plato', url: '/plato#second-model', face: 'neutral', kicker: 'Do all image AIs do this?', target: '#sdxl-card', before: platoReady,
      skip: function () { var d = P(); return !d || !d.sdxl || !d.sdxl.n_concepts; },
      q: 'Is this a law of all machines, or the habit of one?',
      p: 'Mostly of one. Another image AI, Stable Diffusion XL, drew about 2.4 times the variety, for 34 of 35 things, though much of it is style.' },

    { page: '/plato', url: '/plato#inside', face: 'pointing', kicker: 'Inside Meta’s open AI model', target: '#inside .pc-card', before: platoReady, skip: noPlato,
      q: 'And inside a machine’s mind, do sixteen chairs stay sixteen?',
      p: 'Muse Glimmer reads a picture in 52 stages. By the last, the machine’s doodles of a thing are one (spread 0.09); people’s stay apart (0.54).' },

    { page: '/', url: '/#series', face: 'questioning', kicker: 'The Plato series', target: '#series .series-grid', id: 'series',
      // Only once another experiment of the series is on this server (decided before changing page).
      skipEarly: function () {
        var pages = (T.site && T.site.pages) || {};
        return !Object.keys(pages).some(function (p) { return p.indexOf('/plato/') === 0 && pages[p]; });
      },
      skip: function () { return document.querySelectorAll('#series .series-card').length < 2; },
      q: 'Plato had more questions than chairs. Which would you put to a machine?',
      p: 'Each card puts one question to an AI and to people. Failed predictions are shown too.' },

    { page: function () { return hasDraw() ? '/draw' : null; }, url: '/draw?thing=chair', id: 'draw', finish: true, face: 'neutral', kicker: 'Your turn',
      target: function () {  // the drawing pad if the page has one; otherwise a centered card
        if (!hasDraw() || location.pathname !== '/draw') return null;
        return q('#canvas-wrap') ? '#canvas-wrap' : q('canvas') ? 'canvas' : null;
      },
      q: function () {
        return hasDraw() ? 'Now that you’ve seen the machine’s chairs, will your next one be any different?'
          : 'What would you ask a machine?';
      },
      p: function () {
        return hasDraw()
          ? 'Draw a chair in 20 seconds and compare it with 200 people’s. Nothing is stored. Then come and talk.'
          : 'Everything you saw comes from Meta’s AIs: Muse Image drew, DINOv2 compared the pictures, Muse Spark listed kinds and Muse Glimmer sorted the drawings into them.';
      },
      links: function () {
        var out = [];
        if (hasDraw()) out.push(location.pathname === '/draw' ? ['Start drawing', null] : ['Draw a chair in 20 seconds', '/draw?thing=chair']);
        if (hasSocrates()) out.push(['Ask me yourself', '/socrates'], ['Let me examine you', '/socrates?mode=examine']);
        out.push(['See the whole experiment', '/plato'], ['Look inside the model', T.hasPage('/plato/inside') ? '/plato/inside' : '/plato#inside']);
        return out;
      } }
  ];

  function pageOf(step) { return typeof step.page === 'function' ? step.page() : step.page; }
  function val(x) { return typeof x === 'function' ? x() : x; }
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
    ui.face = h('img', { class: 'tour-face', alt: '', width: 72, height: 72, src: FACE + 'neutral.webp' });
    ui.kicker = h('span', { class: 'tour-kicker' });
    ui.title = h('h2', { id: 'tour-title', class: 'tour-q' });
    ui.body = h('p', { id: 'tour-body', class: 'tour-p' });
    ui.extra = h('div', { class: 'tour-extra' });
    ui.credit = h('p', { class: 'tour-credit', text: CREDIT });
    ui.back = h('button', { type: 'button', class: 'btn btn-small', onclick: function () { go(current - 1, -1); } }, 'Back');
    ui.next = h('button', { type: 'button', class: 'btn btn-primary btn-small', onclick: function () { go(current + 1, 1); } }, 'Next');
    ui.skip = h('button', { type: 'button', class: 'tour-skip', onclick: end }, 'Skip tour');
    ui.card = h('div', { class: 'tour-card tour-socrates', role: 'dialog', 'aria-modal': 'false', 'aria-labelledby': 'tour-title', 'aria-describedby': 'tour-body', tabindex: '-1' }, [
      h('div', { class: 'tour-top' }, [ui.progress, h('button', { type: 'button', class: 'tour-x', 'aria-label': 'Close the tour', onclick: end }, '×')]),
      ui.bar,
      h('div', { class: 'tour-say' }, [
        ui.face,
        h('div', { class: 'tour-bubble' }, [h('p', { class: 'tour-who' }, [h('b', { text: 'Socrates' }), ui.kicker]), ui.title, ui.body])
      ]),
      ui.extra, ui.credit,
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
    var t = phone() && step.phoneTarget ? val(step.phoneTarget) : val(step.target);
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
    r = { top: r.top, bottom: r.bottom, left: Math.max(r.left, pad + 2), right: Math.min(r.right, vw - pad - 2) };
    var cw = card.offsetWidth, ch = card.offsetHeight, gap = 14, top, left;
    if (!phone()) {
      // A target as wide as the page and too tall to leave room above or below (a whole section on a wide
      // window): light up the part on screen down to where the caption goes, and put the caption under it,
      // so it never covers what it talks about. scrollToTargets brings the target's top near the window's.
      var beside = r.right + pad + gap + cw < vw - 8 || r.left - pad - gap - cw > 8;
      var below = r.bottom + pad + gap + ch < vh - 8, above = r.top - pad - gap - ch > 8;
      var cut = vh - 12 - ch - gap - pad;
      if (!beside && !below && !above && cut - Math.max(r.top, 0) >= 160) r.bottom = cut;
    }
    ui.spot.style.display = 'block';
    ui.spot.style.top = (r.top - pad) + 'px';
    ui.spot.style.left = (r.left - pad) + 'px';
    ui.spot.style.width = Math.max(0, r.right - r.left + 2 * pad) + 'px';
    ui.spot.style.height = (r.bottom - r.top + 2 * pad) + 'px';
    if (phone()) { card.style.left = card.style.top = ''; return; }
    var clampX = function (x) { return Math.max(12, Math.min(vw - cw - 12, x)); };
    var clampY = function (y) { return Math.max(12, Math.min(vh - ch - 12, y)); };
    if (r.bottom + pad + gap + ch < vh - 8) { top = r.bottom + pad + gap; left = clampX(r.left); }
    else if (r.top - pad - gap - ch > 8) { top = r.top - pad - gap - ch; left = clampX(r.left); }
    else if (r.right + pad + gap + cw < vw - 8) { left = r.right + pad + gap; top = clampY(r.top); }
    else if (r.left - pad - gap - cw > 8) { left = r.left - pad - gap - cw; top = clampY(r.top); }
    else {
      var best = null;  // no free side: the corner that covers the least of the spotlight
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
    var r = unionRect(els), vh = window.innerHeight;
    var reserve = phone() ? ui.card.offsetHeight + 24 : 0;  // the caption sheet covers the bottom on phones
    var room = vh - reserve, height = r.bottom - r.top, wantTop;
    if (phone()) {
      wantTop = 12;
      if (r.top >= 8 && r.bottom <= room - 8) return;
    } else {
      var needed = height + 20 + ui.card.offsetHeight;  // room for the caption below the target when both fit
      var wide = (r.right - r.left) + ui.card.offsetWidth + 40 > window.innerWidth;  // no room beside it either
      // too tall for both: a wide target starts near the top (place() lights its top and puts the caption under it)
      wantTop = needed + 24 <= vh ? (vh - needed) / 2 : wide ? 16 : Math.max(12, (vh - height) / 2);
    }
    window.scrollBy(0, r.top - wantTop);
  }

  function render(step) {
    buildUI();
    ui.progress.textContent = 'Step ' + (current + 1) + ' of ' + STEPS.length;
    ui.bar.firstChild.style.width = (100 * (current + 1) / STEPS.length) + '%';
    var src = FACE + (step.face || 'neutral') + '.webp';
    if (ui.face.getAttribute('src') !== src) ui.face.setAttribute('src', src);
    ui.face.classList.remove('pop');
    if (!still()) { void ui.face.offsetWidth; ui.face.classList.add('pop'); }  // he pops up again at every step
    ui.kicker.textContent = step.kicker ? ' · ' + val(step.kicker) : '';
    ui.title.textContent = val(step.q);
    ui.body.textContent = val(step.p);
    ui.extra.innerHTML = '';
    ui.credit.hidden = !(current === 0 || step.finish || step.blind);
    ui.back.disabled = current === 0;
    ui.next.hidden = !!step.finish;
    ui.next.textContent = step.next ? val(step.next) : 'Next';
    ui.skip.textContent = step.finish ? 'Close' : 'Skip tour';
    if (step.finish && step.links) {
      step.links().forEach(function (b, k) {
        var cls = 'btn ' + (k === 0 ? 'btn-primary' : '');
        ui.extra.appendChild(b[1] ? h('a', { class: cls, href: b[1], onclick: function () { stop(); } }, b[0])
          : h('button', { type: 'button', class: cls, onclick: function () { end(); var pad = q('#pad'); if (pad) pad.focus(); } }, b[0]));
      });
    }
  }

  function go(i, dir) {
    if (busy || i < 0 || i >= STEPS.length) return Promise.resolve();
    var step = STEPS[i], page = pageOf(step);
    if (step.skipEarly && step.skipEarly()) {
      var on = i + (dir || 1);
      return on >= 0 && on < STEPS.length ? go(on, dir || 1) : Promise.resolve();
    }
    current = i;
    store('session', STEP_KEY, String(i));
    if (!step.blind) markSeen();
    if (page && location.pathname !== page) {
      location.href = step.url || page;
      return Promise.resolve();
    }
    busy = true;
    buildUI();
    ui.card.classList.add('loading');
    var prep = step.before ? Promise.resolve().then(step.before).catch(function () { /* show what we can */ }) : Promise.resolve();
    return prep.then(function () {
      if (step.skip && step.skip()) return 'skip';
      var sels = val(step.target);
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
      // Arriving on a new page, the browser may still scroll to the #anchor or shift the layout as pictures
      // load: fit the target and caption again once the page has settled.
      var refit = function () { if (current === i && ui) { scrollToTargets(targetsFor(step)); place(); } };
      if (document.readyState !== 'complete') window.addEventListener('load', function () { setTimeout(refit, 60); }, { once: true });
      else if (location.hash) setTimeout(refit, 350);
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
    if (/^\/(take|assess|challenge)\b/.test(location.pathname)) return;  // don't cover a test in progress
    var close = function () { store('local', OFFER_KEY, '1'); box.remove(); };
    var box = h('aside', { class: 'tour-offer', 'aria-label': 'Guided tour' }, [
      h('img', { class: 'tour-offer-face', src: FACE + 'questioning.webp', alt: '', width: 40, height: 40 }),
      h('p', null, [h('b', { text: 'New here?' }), ' Let Socrates show you around: 90 seconds.']),
      h('button', { type: 'button', class: 'btn btn-primary btn-small', 'data-tour-start': '' }, 'Take the tour'),
      h('button', { type: 'button', class: 'tour-x', 'aria-label': 'No thanks', onclick: close }, '×')
    ]);
    document.body.appendChild(box);
  }
  // Once a drawing is submitted or skipped (draw.js and landing.js send 'tot:revealed'), the results card is
  // what matters: the offer leaves this page view so it never covers the results. The header's Tour button
  // stays, and the offer comes back on the next page until the visitor closes it. If the tour is waiting at
  // the blind-draw step, Socrates moves on to the machine's chairs.
  document.addEventListener('tot:revealed', function () {
    var box = q('.tour-offer');
    if (box) box.remove();
    if (ui && current >= 0 && STEPS[current].blind) {
      var at = current;
      wait(900).then(function () { if (current === at) go(at + 1, 1); });
    }
  });

  T.tour = { start: start, end: end, go: go, steps: STEPS, current: function () { return current; } };

  // Carry on after the tour itself changed page; if the visitor went somewhere else, drop the tour.
  var saved = store('session', STEP_KEY), step = saved != null ? STEPS[+saved] : null;
  if (step && (!pageOf(step) || pageOf(step) === location.pathname)) {
    lastFocus = document.body;
    if (!step.blind && location.pathname === '/') revealChairs();  // past the blind draw: the chairs stay shown
    go(+saved, 1);
  } else {
    if (saved != null) store('session', STEP_KEY, null);
    offer();
  }
})();
