/* Plato's Chair's landing page: draw first (the pad from draw.js, blind: nothing of Muse Image's chairs
   until the visitor draws or skips), then the reveal with the one motion moment (stack the 16 chairs on top
   of each other) and the visitor's results. The opening animation is splash.js. */
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
      // The chairs show the moment the visitor submits; the score follows a moment later, just below them.
      onSubmit: function (e) {
        reveal('drawn');
        invite('Measuring where your ' + e.concept.label + ' lands. Your results will appear just below.', true);
        revealEl.scrollIntoView({ behavior: still ? 'auto' : 'smooth', block: 'start' });
      },
      onReveal: function () { reveal('drawn'); invite('Your chair’s results are just below.', false); },
      onError: function (e) { invite('We couldn’t measure your drawing: ' + (e.message || 'please try again') + ' Scroll up to try again.', false); }
    });
  } else if (revealEl) {
    revealEl.hidden = false;
  }
  function invite(text, busy) {
    var el = document.getElementById('reveal-invite');
    if (!el) return;
    el.hidden = false;
    el.textContent = text;
    el.classList.toggle('busy', !!busy);
  }
  if (skip) {
    skip.addEventListener('click', function (e) {
      e.preventDefault();
      reveal('skip');
      revealEl.scrollIntoView({ behavior: still ? 'auto' : 'smooth', block: 'start' });
    });
  }
  // The guided tour keeps the blind draw: Socrates asks for a chair first, and tour.js calls
  // T.landing.reveal('tour') when it moves on to the chairs.

  // --- stack the drawings: Muse Image's 16 make one chair, people's 16 make a cloud ----------------
  function stack(on) {
    if (!fig) return;
    on = on == null ? !fig.classList.contains('stacked') : !!on;
    fig.classList.toggle('stacked', on);
    btn.setAttribute('aria-pressed', String(on));
  }
  function cancelAuto() { clearTimeout(autoTimer); autoTimer = null; autoDone = true; }
  if (btn) btn.addEventListener('click', function () { cancelAuto(); stack(); });

  // The chairs start spread out and stack only when the visitor presses the button (or the tour's first step
  // does it).

  T.landing = { stack: stack, cancelAuto: cancelAuto, reveal: reveal, draw: drawApp };
})();
