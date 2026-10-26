/* Landing page: plain-language definitions for jargon, and links to pages that may not exist yet. */
(function () {
  'use strict';
  var T = window.TOT;

  // --- definitions: show on hover or keyboard focus, toggle on click or tap, Escape closes -----
  var terms = [].slice.call(document.querySelectorAll('.term'));
  function wrapOf(btn) { return btn.closest('.term-wrap'); }
  function fit(btn) {
    var pop = document.getElementById(btn.getAttribute('aria-describedby'));
    if (!pop) return;
    pop.style.setProperty('--shift', '-50%');
    var r = pop.getBoundingClientRect(), margin = 12, dx = 0;
    if (r.left < margin) dx = margin - r.left;
    else if (r.right > window.innerWidth - margin) dx = window.innerWidth - margin - r.right;
    if (dx) pop.style.setProperty('--shift', 'calc(-50% + ' + Math.round(dx) + 'px)');
  }
  function close(btn, hush) {
    wrapOf(btn).classList.remove('open');
    if (hush) wrapOf(btn).classList.add('hush');  // also hide the hover/focus view until the pointer or focus leaves
    btn.setAttribute('aria-expanded', 'false');
  }
  function closeAll(except, hush) {
    terms.forEach(function (b) {
      if (b !== except) close(b, hush && (b === document.activeElement || wrapOf(b).matches(':hover')));
    });
  }
  terms.forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var open = !wrapOf(btn).classList.contains('open');
      closeAll(btn);
      wrapOf(btn).classList.remove('hush');
      wrapOf(btn).classList.toggle('open', open);
      btn.setAttribute('aria-expanded', String(open));
      if (open) fit(btn);
    });
    btn.addEventListener('mouseenter', function () { requestAnimationFrame(function () { fit(btn); }); });
    btn.addEventListener('focus', function () { requestAnimationFrame(function () { fit(btn); }); });
    btn.addEventListener('blur', function () { wrapOf(btn).classList.remove('hush'); });
    wrapOf(btn).addEventListener('mouseleave', function () { if (document.activeElement !== btn) wrapOf(btn).classList.remove('hush'); });
  });
  document.addEventListener('click', function () { closeAll(null); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeAll(null, true); });
  window.addEventListener('resize', function () { closeAll(null); });

  // --- links to the Naming Assessment, which ships separately -----------------------------------
  // Until /assess exists on this server, its buttons point at their fallback and its extra boxes stay hidden.
  T.api('/api/pages').then(function (pages) {
    var has = !!(pages && pages.assess);
    document.querySelectorAll('[data-assess-box]').forEach(function (el) { el.hidden = !has; });
    if (has) return;
    document.querySelectorAll('a[data-assess][data-fallback]').forEach(function (a) {
      a.setAttribute('href', a.getAttribute('data-fallback'));
      if (a.getAttribute('data-fallback-text')) a.textContent = a.getAttribute('data-fallback-text');
    });
  }).catch(function () {});
})();
