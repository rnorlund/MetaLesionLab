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

  // --- second-language teaser: the numbers shipped with /lab/bilingual (the HTML holds a fallback) --
  if (document.getElementById('bilingual-teaser')) {
    T.api('/api/lab/bilingual').then(function (d) {
      var sm = d && d.summary, sw = d && d.switching;
      if (!sm || !sm.es) return;
      var acc = { en: sm.es.acc_en, es: sm.es.acc_lang, fr: (sm.fr || {}).acc_lang, pt: (sm.pt || {}).acc_lang };
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
        p.textContent = 'We gave Muse Glimmer the same pictures in English, Spanish, French and Portuguese, and damaged it the same way each time. Spanish lost ' +
          Math.round(sm.es.extra_drop * 100) + ' points more than English, ' + (sm.es.items_worse === sm.es.n_items ? 'every picture' : sm.es.items_worse + ' of ' + sm.es.n_items + ' pictures') +
          ' fared worse, and ' + Math.round(share * 100) + '% of damaged Spanish answers came out in English. Inside, the intact model finds the English word first and translates it at the end. It echoes bilingual aphasia, as an analogy only.';
      }
    }).catch(function () {});
  }

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
