/* Guided tour: about 90 seconds of Plato's Chair, from the stacked chairs to "draw your own".
   Every number comes from the page's own data (/api/plato); no AI calls. The current step lives in
   sessionStorage, so the tour carries on across page loads. At most 10 steps; it ends at /draw when the
   server has that page (TOT.hasPage), and otherwise with the same closing card wherever it is.
   It is the Plato's Chair site's tour: where /plato isn't served (the Lingua site, MLL_SITE=lingua) it does nothing. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  if (!T.hasPage('/plato')) return;
  var STEP_KEY = 'tot-tour-step', OFFER_KEY = 'tot-tour-offer-done';
  var PHONE = 640;

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
  function pct(x) { return Math.round(x * 100); }
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

  // --- Plato page data ----------------------------------------------------------------------------
  function platoReady() { return T.plato ? T.plato.ready : Promise.resolve(); }
  function P() { return T.plato && T.plato.state().data; }
  function noPlato() { return !P(); }
  function chair() { var d = P(); return ((d && d.hero) || []).filter(function (c) { return c.key === 'chair'; })[0] || {}; }
  function chairOnPlato() {
    return platoReady().then(function () { if (T.plato) { T.plato.setConcept('chair'); T.plato.setWho('ai'); } });
  }

  // --- the steps ----------------------------------------------------------------------------------
  var STEPS = [
    { page: '/', url: '/', id: 'home', target: '#chairs', title: 'What would Plato ask an AI?',
      onShow: function () {
        var at = current;
        return wait(700).then(function () { if (current === at && T.landing) { T.landing.cancelAuto(); T.landing.stack(true); } });
      },
      body: 'Plato asked whether there is one ideal chair. We asked Meta’s image model, Muse Image, for a chair 16 times, and set its drawings beside 16 people’s from Google’s Quick, Draw!. Watch: stacked on top of each other, Muse Image’s 16 chairs make one chair. People’s make a cloud.' },

    { page: '/plato', url: '/plato', id: 'plato', title: 'Measuring “varied”',
      target: function () { return phone() ? '.pc-frame' : '#hero-fig'; },
      before: chairOnPlato, skip: noPlato,
      onShow: function () {
        var at = current;
        return wait(2400).then(function () { if (current === at && T.plato) T.plato.setWho('people'); });
      },
      body: function () {
        var c = chair();
        return 'Meta’s DINOv2 vision model turns each drawing into numbers, and the spread is how different two drawings look on average. Muse Image’s chairs: ' +
          (c.ai_spread != null ? c.ai_spread.toFixed(2) : '0.13') + '. People’s: ' + (c.human_spread != null ? c.human_spread.toFixed(2) : '0.36') +
          '. So its chairs are ' + (c.index != null ? pct(1 - c.index) : 63) + '% less varied. In a moment the picture switches to people’s chairs.';
      } },

    { page: '/plato', url: '/plato#everything', title: 'Not just chairs', target: '#rank-chart', before: platoReady, skip: noPlato,
      body: function () {
        var core = P().core;
        return 'We did the same for ' + core.n_concepts + ' things. Each dot is one thing; left of the line means Muse Image drew it more alike than people do. That’s ' +
          core.below_1 + ' of ' + core.n_concepts + ', with a typical ratio of ' + core.median_index.toFixed(2) +
          ': about half as varied. Umbrellas are the most uniform. Books are the one exception.';
      } },

    { page: '/plato', url: '/plato#variety', title: 'Can you prompt it out of the Platonic chair?', target: '#var-fig', before: platoReady,
      skip: function () { var d = P(); return !d || !d.variety || !d.variety.conditions || !d.variety.conditions.listed; },
      body: function () {
        var C = P().variety.conditions;
        return 'Asking for “any kind of chair” gives the same slat-back chair again (typical ratio ' + C.any.median_ratio.toFixed(2) +
          '). But when Meta’s Muse Spark lists 16 kinds and Muse Image draws one of each, the drawings are ' + C.listed.median_ratio.toFixed(2) +
          ' times as varied as people’s. Muse knows the variety; the narrow chair is its default.';
      } },

    { page: '/plato', url: '/plato#variety', title: 'People draw the plain chair too', target: '#var-kinds', before: platoReady,
      skip: function () { var d = P(); return !d || !d.variety || !d.variety.kinds || !d.variety.kinds.summary; },
      body: function () {
        var k = P().variety.kinds, S = k.summary;
        return 'Muse Glimmer labeled which kind of thing every drawing shows. On the ' + k.reliable + ' things it labels reliably, ' + pct(S.people.mean_share_plain) +
          '% of people’s recognizable drawings are the plain, ordinary kind, about the same as Muse Image’s usual prompt (' + pct(S.default.mean_share_plain) +
          '%). People vary in how they draw a thing far more than in which one they draw.';
      } },

    { page: '/plato', url: '/plato#second-model', title: 'Is it just Meta’s model?', target: '#sdxl-card', before: platoReady,
      skip: function () { var d = P(); return !d || !d.sdxl || !d.sdxl.n_concepts; },
      body: function () {
        var s = P().sdxl, times = s.median_muse_over_sdxl ? (1 / s.median_muse_over_sdxl).toFixed(1) : null;
        return 'Mostly, it’s Meta’s model. From the same prompt, Stable Diffusion XL drew more varied pictures for ' + s.muse_more_uniform + ' of ' + s.n_concepts + ' things' +
          (times ? ', about ' + times + ' times Muse Image’s spread' : '') + ', though much of that is drawing style. So Plato’s Chair measures a model, not all AI.';
      } },

    { page: '/plato', url: '/plato#inside', title: 'Inside Meta’s open model', target: '#inside .pc-card', before: platoReady, skip: noPlato,
      body: function () {
        var L = (P().inside.layer_spread || {}).L52;
        return 'We showed both sets of doodles to Muse Glimmer, Meta’s open-weight model, and measured their spread after each of its 52 layers. By the last layers, Glimmer files all of Muse Image’s doodles of a thing in one place' +
          (L ? ' (spread ' + L.ai.toFixed(2) + ', against ' + L.human.toFixed(2) + ' for people’s, in ' + L.human_wider + ' of ' + L.n + ' things)' : '') + '.';
      } },

    { page: '/', url: '/#series', title: 'The Plato series', target: '#series .series-grid', id: 'series',
      // Only once another experiment of the series is on this server (decided before changing page).
      skipEarly: function () {
        var pages = (T.site && T.site.pages) || {};
        return !Object.keys(pages).some(function (p) { return p.indexOf('/plato/') === 0 && pages[p]; });
      },
      skip: function () { return document.querySelectorAll('#series .series-card').length < 2; },
      body: function () {
        var qs = [].slice.call(document.querySelectorAll('#series .series-q')).map(function (el) { return '“' + el.textContent + '”'; });
        return 'Each experiment puts one of Plato’s questions to an AI and to people: ' + qs.join(', ') + '. Each card opens its results, including the predictions that failed.';
      } },

    { page: function () { return hasDraw() ? '/draw' : null; }, url: '/draw', id: 'draw', finish: true,
      target: function () {  // the drawing pad if the page has one; otherwise a centered card
        if (!hasDraw() || location.pathname !== '/draw') return null;
        return q('#canvas-wrap') ? '#canvas-wrap' : q('canvas') ? 'canvas' : null;
      },
      title: function () { return hasDraw() ? 'Your turn: draw a chair' : 'Now try it yourself'; },
      body: function () {
        return hasDraw()
          ? 'Draw a chair in 20 seconds, with a mouse or a finger, like the Quick, Draw! players did. Then see what Meta’s AI drew, and where your chair lands among 200 people’s, measured the same way. Nothing you draw is stored.'
          : 'Everything you saw comes from Meta’s models: Muse Image drew, DINOv2 measured, Muse Spark listed kinds and Muse Glimmer labeled them. Pick a starting point:';
      },
      links: function () {
        var out = [];
        if (hasDraw()) out.push(location.pathname === '/draw' ? ['Start drawing', null] : ['Draw a chair in 20 seconds', '/draw']);
        if (hasSocrates()) out.push(['Ask Socrates', '/socrates']);
        out.push(['See the whole experiment', '/plato'], ['Look inside the model', '/plato#inside']);
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
    var t = val(step.target);
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
      wantTop = needed + 24 <= vh ? (vh - needed) / 2 : Math.max(12, (vh - height) / 2);
    }
    window.scrollBy(0, r.top - wantTop);
  }

  function render(step) {
    buildUI();
    ui.progress.textContent = 'Step ' + (current + 1) + ' of ' + STEPS.length;
    ui.bar.firstChild.style.width = (100 * (current + 1) / STEPS.length) + '%';
    ui.title.textContent = val(step.title);
    ui.body.textContent = val(step.body);
    ui.extra.innerHTML = '';
    ui.back.disabled = current === 0;
    ui.next.hidden = !!step.finish;
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
      h('p', null, [h('b', { text: 'New here?' }), ' Take the 90-second tour.']),
      h('button', { type: 'button', class: 'btn btn-primary btn-small', 'data-tour-start': '' }, 'Take the tour'),
      h('button', { type: 'button', class: 'tour-x', 'aria-label': 'No thanks', onclick: close }, '×')
    ]);
    document.body.appendChild(box);
  }
  // Once a drawing is submitted or skipped (draw.js and landing.js send 'tot:revealed'), the results card is
  // what matters: the offer leaves this page view so it never covers the results. The header's Tour button
  // stays, and the offer comes back on the next page until the visitor closes it.
  document.addEventListener('tot:revealed', function () {
    var box = q('.tour-offer');
    if (box) box.remove();
  });

  T.tour = { start: start, end: end, go: go, steps: STEPS, current: function () { return current; } };

  // Carry on after the tour itself changed page; if the visitor went somewhere else, drop the tour.
  var saved = store('session', STEP_KEY), step = saved != null ? STEPS[+saved] : null;
  if (step && (!pageOf(step) || pageOf(step) === location.pathname)) {
    lastFocus = document.body;
    go(+saved, 1);
  } else {
    if (saved != null) store('session', STEP_KEY, null);
    offer();
  }
})();
