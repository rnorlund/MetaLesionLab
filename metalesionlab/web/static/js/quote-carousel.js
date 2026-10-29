/* Quote carousel: every .epigraph-band with two or more quotes (the landing page's quote band; epigraph.py renders
   the quotes and links this script and quote-carousel.css) shows one quote at a time, large, with the speaker's face
   beside it and the citation under it. Without this script the quotes stay as they are served: all of them, in a
   row that wraps (epigraph.css). Nothing here touches the words, which come verified from plato_passages.json.

   - The quotes cross-fade with a short slide, and every quote shares one grid cell, so the band is always as tall
     as its tallest quote and the page never shifts when the quote changes.
   - It moves on by itself every --qc-interval (8.5 s, quote-carousel.css): the current dot fills up, and the dot's
     animation ending is the cue to move on, so a pause keeps the time left. It holds while the mouse is over the
     band, while keyboard focus is inside it, while the tab is hidden and while the band is off screen. Pause/Play
     stops and starts it; pressing Play starts it at once, even with the mouse over the band.
   - Previous and next buttons, and a dot per quote (real buttons, "Quote 2 of 7"); the arrow keys move when the
     band or anything in it has focus (Home and End too, on a dot), and a sideways swipe moves on a touch screen.
   - WAI-ARIA carousel pattern: the band is a region with aria-roledescription="carousel", each quote a group with
     aria-roledescription="slide" and a label ("2 of 7"); the quotes are aria-live="polite" only while they are not
     moving by themselves, and the hidden quotes are inert.
   - prefers-reduced-motion: never moves by itself and never animates; no Pause/Play, the buttons and dots only. */
(function () {
  'use strict';

  var REDUCE = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  var made = 0;

  function svg(body, cls) {
    return '<svg' + (cls ? ' class="' + cls + '"' : '') + ' viewBox="0 0 10 10" aria-hidden="true" focusable="false">' + body + '</svg>';
  }
  var ICON = {
    prev: svg('<path d="M6.5 1.5L3 5l3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'),
    next: svg('<path d="M3.5 1.5L7 5 3.5 8.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'),
    pause: svg('<path d="M3.3 2v6M6.7 2v6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>', 'qc-i-pause'),
    play: svg('<path d="M3 1.8v6.4L8.2 5z" fill="currentColor" stroke="currentColor" stroke-width="0.8" stroke-linejoin="round"/>', 'qc-i-play')
  };

  function button(cls, html, label) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = cls;
    b.innerHTML = html;
    if (label) b.setAttribute('aria-label', label);
    return b;
  }

  function setup(root) {
    if (root.classList.contains('qc')) return;
    var slides = Array.prototype.filter.call(root.children, function (c) {
      return c.tagName === 'FIGURE' && c.classList.contains('epigraph');
    });
    var n = slides.length;
    if (n < 2) return;
    var id = 'qc' + (++made), cur = 0;
    var stopped = !!(REDUCE && REDUCE.matches);
    // why it is holding still: the mouse is over it, keyboard focus is in it, the tab is hidden, it is off screen
    var hold = { hover: false, focus: false, hidden: !!document.hidden, away: 'IntersectionObserver' in window };

    var view = document.createElement('div');
    view.className = 'qc-slides';
    view.id = id + '-slides';
    slides.forEach(function (s, i) {
      s.classList.add('qc-slide');
      s.setAttribute('role', 'group');
      s.setAttribute('aria-roledescription', 'slide');
      s.setAttribute('aria-label', (i + 1) + ' of ' + n);
      view.appendChild(s);
    });

    var ctrl = document.createElement('div');
    ctrl.className = 'qc-controls';
    var play = button('qc-btn qc-play', ICON.pause + ICON.play + '<span class="qc-play-text"></span>', '');
    var prev = button('qc-btn qc-step', ICON.prev, 'Previous quote');
    var next = button('qc-btn qc-step', ICON.next, 'Next quote');
    var dotRow = document.createElement('div');
    dotRow.className = 'qc-dots';
    dotRow.setAttribute('role', 'group');
    dotRow.setAttribute('aria-label', 'Choose a quote');
    var dots = slides.map(function (s, i) {
      var d = button('qc-dot', '<span class="qc-pip"><span class="qc-fill"></span></span>', 'Quote ' + (i + 1) + ' of ' + n);
      d.setAttribute('aria-controls', view.id);
      dotRow.appendChild(d);
      return d;
    });
    [play, prev, next].forEach(function (b) { b.setAttribute('aria-controls', view.id); });
    ctrl.appendChild(play);
    ctrl.appendChild(prev);
    ctrl.appendChild(dotRow);
    ctrl.appendChild(next);

    root.appendChild(view);
    root.appendChild(ctrl);
    root.classList.add('qc');
    root.setAttribute('role', 'region');
    root.setAttribute('aria-roledescription', 'carousel');
    root.setAttribute('aria-label', root.getAttribute('data-label') || 'Quotations');
    root.tabIndex = 0;

    function conceal(s, hidden) {
      if (hidden) { s.setAttribute('aria-hidden', 'true'); s.setAttribute('inert', ''); }
      else { s.removeAttribute('aria-hidden'); s.removeAttribute('inert'); }
    }

    function mark() {
      dots.forEach(function (d, k) {
        if (k === cur) { d.setAttribute('aria-current', 'true'); d.tabIndex = 0; }
        else { d.removeAttribute('aria-current'); d.tabIndex = -1; }
      });
    }

    function sync() {
      var held = hold.hover || hold.focus || hold.hidden || hold.away;
      root.classList.toggle('is-stopped', stopped);
      root.classList.toggle('is-held', held);
      view.setAttribute('aria-live', stopped || held ? 'polite' : 'off');
      play.hidden = !!(REDUCE && REDUCE.matches);
      // the button keeps its nodes (the stylesheet shows one icon): replacing what is under the pointer would lose
      // a click and make the browser report the mouse entering the band again
      if (play.getAttribute('data-shows') !== (stopped ? 'play' : 'pause')) {
        play.setAttribute('data-shows', stopped ? 'play' : 'pause');
        play.lastChild.textContent = stopped ? 'Play' : 'Pause';
        play.setAttribute('aria-label', stopped ? 'Play the quotes' : 'Pause the quotes');
      }
    }

    function show(to, dir) {
      to = (to + n) % n;
      if (to === cur) return;
      var old = slides[cur], now = slides[to];
      var hadFocus = old.contains(document.activeElement);
      root.style.setProperty('--qc-dir', dir < 0 ? '-1' : '1');
      slides.forEach(function (s) { s.classList.remove('is-leaving'); });
      // the new quote starts on the side it comes in from, without a transition, then slides in
      now.classList.add('qc-pre');
      void now.offsetWidth;
      now.classList.remove('qc-pre');
      old.classList.remove('is-active');
      old.classList.add('is-leaving');
      conceal(old, true);
      now.classList.add('is-active');
      conceal(now, false);
      cur = to;
      mark();
      if (hadFocus) root.focus();
    }

    slides.forEach(function (s, i) {
      if (i === 0) s.classList.add('is-active');
      else conceal(s, true);
    });
    mark();
    sync();

    play.addEventListener('click', function () {
      stopped = !stopped;
      if (!stopped) { hold.hover = false; hold.focus = false; }  // Play means now, even with the mouse over the band
      sync();
    });
    prev.addEventListener('click', function () { show(cur - 1, -1); });
    next.addEventListener('click', function () { show(cur + 1, 1); });
    dots.forEach(function (d, k) {
      d.addEventListener('click', function () { show(k, k < cur ? -1 : 1); });
    });

    root.addEventListener('keydown', function (e) {
      if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
      var onDot = dots.indexOf(document.activeElement) >= 0, to = null, dir = 1;
      if (e.key === 'ArrowRight') to = cur + 1;
      else if (e.key === 'ArrowLeft') { to = cur - 1; dir = -1; }
      else if (onDot && e.key === 'Home') { to = 0; dir = -1; }
      else if (onDot && e.key === 'End') to = n - 1;
      if (to === null) return;
      e.preventDefault();
      show(to, dir);
      if (onDot) dots[cur].focus();
    });

    // the current dot's fill running out is the cue to move on (quote-carousel.css times it)
    root.addEventListener('animationend', function (e) {
      if (e.animationName === 'qc-fill' && dots[cur].contains(e.target)) show(cur + 1, 1);
    });

    root.addEventListener('pointerenter', function (e) {
      if (e.pointerType === 'mouse' || e.pointerType === 'pen') { hold.hover = true; sync(); }
    });
    root.addEventListener('pointerleave', function () {
      if (hold.hover) { hold.hover = false; sync(); }
    });
    root.addEventListener('focusin', function (e) {
      var keyboard = true;
      try { keyboard = e.target.matches(':focus-visible'); } catch (x) { /* an older browser: any focus holds it */ }
      if (keyboard && !hold.focus) { hold.focus = true; sync(); }
    });
    root.addEventListener('focusout', function (e) {
      if (!root.contains(e.relatedTarget) && hold.focus) { hold.focus = false; sync(); }
    });
    document.addEventListener('visibilitychange', function () { hold.hidden = !!document.hidden; sync(); });
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (entries) {
        hold.away = !entries[entries.length - 1].isIntersecting;
        sync();
      }, { threshold: 0.35 }).observe(root);
    }
    if (REDUCE) {
      var motion = function () { if (REDUCE.matches) stopped = true; sync(); };
      if (REDUCE.addEventListener) REDUCE.addEventListener('change', motion);
      else if (REDUCE.addListener) REDUCE.addListener(motion);
    }

    // a sideways swipe on a touch screen
    var x0 = null, y0 = 0;
    view.addEventListener('touchstart', function (e) {
      if (e.touches.length === 1) { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; } else x0 = null;
    }, { passive: true });
    view.addEventListener('touchend', function (e) {
      if (x0 === null) return;
      var t = e.changedTouches[0], dx = t.clientX - x0, dy = t.clientY - y0;
      x0 = null;
      if (Math.abs(dx) > 48 && Math.abs(dx) > 1.5 * Math.abs(dy)) show(cur + (dx < 0 ? 1 : -1), dx < 0 ? 1 : -1);
    }, { passive: true });
  }

  function init() { Array.prototype.forEach.call(document.querySelectorAll('.epigraph-band'), setup); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
