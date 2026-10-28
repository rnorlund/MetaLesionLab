/* Landing page: draw first (the pad from draw.js, blind: nothing of Muse Image's chairs until the visitor
   draws or skips), then the reveal with the one motion moment (stack the 16 chairs on top of each other),
   the visitor's results, and the second-language card's numbers. */
(function () {
  'use strict';
  var T = window.TOT;
  var fig = document.getElementById('chairs'), btn = document.getElementById('stack-btn');
  var still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var autoTimer = null, autoDone = false;

  // --- draw first, then the reveal ------------------------------------------------------------------
  var padEl = document.getElementById('hero-draw'), revealEl = document.getElementById('reveal');
  var skip = document.getElementById('skip-link'), drawApp = null;
  function reveal(how) {
    if (!revealEl || !revealEl.hidden) return;
    revealEl.hidden = false;
    if (drawApp) drawApp.markSeen();  // a drawing from now on is no longer blind
    if (skip) skip.hidden = true;
    var invite = document.getElementById('reveal-invite');
    if (invite) invite.hidden = how !== 'drawn';
    document.body.classList.add('revealed');
    document.dispatchEvent(new CustomEvent('tot:revealed'));  // drawn or skipped: the tour offer steps aside
  }
  if (padEl && window.TOTDraw) {
    drawApp = window.TOTDraw.mount(padEl, {
      title: 'Before we tell you anything: draw {a thing}.', instruction: 'You have 20 seconds.', heading: 'h2',
      concept: 'chair', picker: false, deepLink: false, revealStrip: false,
      results: document.getElementById('hero-results'), scrollTo: revealEl,
      onReveal: function () { reveal('drawn'); }
    });
  } else if (revealEl) {
    revealEl.hidden = false;
  }
  if (skip) {
    skip.addEventListener('click', function (e) {
      e.preventDefault();
      reveal('skip');
      revealEl.scrollIntoView({ behavior: still ? 'auto' : 'smooth', block: 'start' });
    });
  }
  // The guided tour starts at the chairs: show them first (capture phase, before the tour finds its target).
  document.addEventListener('click', function (e) {
    if (e.target.closest && e.target.closest('[data-tour-start]')) reveal('tour');
  }, true);

  // --- stack the drawings: Muse Image's 16 make one chair, people's 16 make a cloud ----------------
  function stack(on) {
    if (!fig) return;
    on = on == null ? !fig.classList.contains('stacked') : !!on;
    fig.classList.toggle('stacked', on);
    btn.setAttribute('aria-pressed', String(on));
  }
  function cancelAuto() { clearTimeout(autoTimer); autoTimer = null; autoDone = true; }
  if (btn) btn.addEventListener('click', function () { cancelAuto(); stack(); });

  // Once per visit, when the grids are on screen: stack, hold, and spread out again. Not with reduced
  // motion, and not while the guided tour is running (its first step does this itself).
  function touring() { try { return window.sessionStorage.getItem('tot-tour-step') != null; } catch (e) { return false; } }
  if (touring()) reveal('tour');
  function autoplay() {
    if (autoDone || still || touring()) return;
    autoDone = true;
    autoTimer = setTimeout(function () {
      stack(true);
      autoTimer = setTimeout(function () { stack(false); autoTimer = null; }, 3600);
    }, 1400);
  }
  if (fig && 'IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      if (entries.some(function (e) { return e.isIntersecting && e.intersectionRatio > 0.55; })) { io.disconnect(); autoplay(); }
    }, { threshold: [0.55] });
    io.observe(fig);
  }

  // --- second-language card: the numbers shipped with /lab/bilingual (the HTML holds a fallback) ----
  if (document.getElementById('bilingual-teaser')) {
    T.api('/api/lab/bilingual').then(function (d) {
      var sm = d && d.summary, sw = d && d.switching;
      if (!sm || !sm.es) return;
      var acc = { en: sm.es.acc_en, es: sm.es.acc_lang };
      Object.keys(acc).forEach(function (v) {
        if (acc[v] == null) return;
        var bar = document.querySelector('[data-bl-bar="' + v + '"]'), val = document.querySelector('[data-bl-val="' + v + '"]');
        if (bar) bar.style.width = Math.round(acc[v] * 100) + '%';
        if (val) val.textContent = Math.round(acc[v] * 100) + '%';
      });
      var kinds = document.querySelector('[data-bl-kinds]');
      if (kinds && sm.es.n_conditions) kinds.textContent = String(sm.es.n_conditions);
      var p = document.querySelector('[data-bl-teaser-text]'), share = sw && sw.es && sw.es.english_answers.mean;
      if (p && share != null) {
        p.textContent = 'Under the same damage, Muse Glimmer named ' + Math.round(sm.es.extra_drop * 100) +
          ' points fewer pictures in Spanish than in English, and ' + Math.round(share * 100) +
          '% of its damaged Spanish answers came out in English. It echoes bilingual aphasia, as an analogy only.';
      }
    }).catch(function () {});
  }

  T.landing = { stack: stack, cancelAuto: cancelAuto, reveal: reveal, draw: drawApp };
})();
