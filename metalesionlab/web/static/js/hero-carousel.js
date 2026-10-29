/* Hero carousel: the picture area of a first screen as a slideshow of pictures (or strips of pictures), each with a
   caption of ten words or fewer ("rocking chair → car"). Modelled on quote-carousel.js (WAI-ARIA carousel pattern).

   USAGE
   1. Link /static/css/hero-carousel.css and /static/js/hero-carousel.js. Put this where the picture goes:
        <figure class="fl-visual" data-hero-carousel aria-label="Damaged AI, in pictures">
          <script type="application/json">{"slides":[
            {"caption":"rocking chair → car",
             "images":[{"src":"/static/img/a.webp","alt":"…","label":"undamaged"},{"src":"/static/img/b.webp","alt":"…","label":"car"}]}
          ]}</script>
          <!-- no-JS fallback: the first slide, written out (what the script renders for it): -->
          <div class="hc-static"> <div class="hc-strip" style="--n:2"><figure class="hc-pic">…</figure>…</div>
            <p class="hc-cap">rocking chair → car</p></div>
        </figure>
      The script replaces the contents of every [data-hero-carousel] it finds on load.
   2. Or from code:  HeroCarousel.mount(element, {slides:[…], label:'…', interval:7000})  -> {go(i), play(), pause(), destroy()}
      Slide: {caption, images:[{src, alt, label?}], href? (the caption becomes a link)}. Keep every slide to the same
      number of pictures so the area never changes height (the area is always as tall as the tallest slide anyway).
   3. Pictures sit on paper (--paper). Colours are the site's tokens. Timing: --hc-interval (7 s) is set from `interval`.

   BEHAVIOUR
   - Moves on by itself every 7 s (the current dot fills over that time; the fill ending is the cue to move on, so a
     pause keeps the time left). Holds while the mouse is over it, keyboard focus is inside it, the tab is hidden or it
     is off screen. Pause/Play stops and starts it for good.
   - Previous, next, one dot per slide (real buttons, aria-label "Slide 2 of 4"); arrow keys, Home and End when it has focus.
   - ARIA: region with aria-roledescription="carousel"; each slide a group with aria-roledescription="slide"; the slides
     are aria-live="polite" only when not moving by themselves; hidden slides are inert and aria-hidden.
   - prefers-reduced-motion: never moves by itself, never animates, no Pause/Play.
   - No layout jump: all slides share one grid cell. No JS: the first slide shows statically (.hc-static). */
(function () {
  'use strict';
  var REDUCE = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  var made = 0;

  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function svg(body, cls) {
    return '<svg' + (cls ? ' class="' + cls + '"' : '') + ' viewBox="0 0 10 10" aria-hidden="true" focusable="false">' + body + '</svg>';
  }
  var ICON = {
    prev: svg('<path d="M6.5 1.5L3 5l3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'),
    next: svg('<path d="M3.5 1.5L7 5 3.5 8.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'),
    pause: svg('<path d="M3.3 2v6M6.7 2v6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>', 'hc-i-pause'),
    play: svg('<path d="M3 1.8v6.4L8.2 5z" fill="currentColor" stroke="currentColor" stroke-width="0.8" stroke-linejoin="round"/>', 'hc-i-play')
  };

  // The markup of one slide (pure: tests read it).
  function slideHtml(s, i, n) {
    var imgs = (s.images || []).map(function (im) {
      return '<figure class="hc-pic"><span class="hc-paper"><img src="' + esc(im.src) + '" alt="' + esc(im.alt || '') +
        '" width="512" height="512" decoding="async"' + (i ? ' loading="lazy"' : '') + '></span>' +
        (im.label ? '<figcaption class="hc-lab">' + esc(im.label) + '</figcaption>' : '') + '</figure>';
    }).join('');
    var cap = s.href ? '<a href="' + esc(s.href) + '">' + esc(s.caption) + '</a>' : esc(s.caption);
    return '<figure class="hc-slide' + (i ? '' : ' is-active') + '" role="group" aria-roledescription="slide" aria-label="' + (i + 1) +
      ' of ' + n + '"><div class="hc-strip" style="--n:' + (s.images || []).length + '">' + imgs + '</div><figcaption class="hc-cap">' + cap + '</figcaption></figure>';
  }

  function mount(root, cfg) {
    var slides = (cfg && cfg.slides) || [], n = slides.length;
    if (!n) return null;
    var id = 'hc' + (++made), cur = 0, interval = cfg.interval || 7000;
    var stopped = !!(REDUCE && REDUCE.matches);
    var hold = { hover: false, focus: false, hidden: !!document.hidden, away: false };
    root.classList.add('hc');
    root.setAttribute('role', 'region');
    root.setAttribute('aria-roledescription', 'carousel');
    root.setAttribute('aria-label', cfg.label || root.getAttribute('aria-label') || 'Pictures');
    root.style.setProperty('--hc-interval', interval + 'ms');
    root.innerHTML = '<div class="hc-slides" id="' + id + '-slides">' + slides.map(function (s, i) { return slideHtml(s, i, n); }).join('') + '</div>' +
      '<div class="hc-controls"></div>';
    var view = root.querySelector('.hc-slides'), ctl = root.querySelector('.hc-controls');
    var els = [].slice.call(view.children), dots = [];
    function btn(cls, html, label) {
      var b = document.createElement('button'); b.type = 'button'; b.className = cls; b.innerHTML = html; b.setAttribute('aria-label', label); return b;
    }
    var toggle = btn('hc-btn hc-toggle', ICON.pause + ICON.play, 'Pause');
    toggle.setAttribute('aria-controls', view.id);
    var prev = btn('hc-btn hc-prev', ICON.prev, 'Previous slide'), next = btn('hc-btn hc-next', ICON.next, 'Next slide');
    prev.setAttribute('aria-controls', view.id); next.setAttribute('aria-controls', view.id);
    var dotBox = document.createElement('div'); dotBox.className = 'hc-dots';
    function paused() { return stopped || hold.hover || hold.focus || hold.hidden || hold.away; }
    slides.forEach(function (s, i) {
      var d = btn('hc-dot', '<span class="hc-pip"><span class="hc-fill"></span></span>', 'Slide ' + (i + 1) + ' of ' + n);
      d.addEventListener('click', function () { go(i); });
      d.addEventListener('animationend', function (e) { if (e.animationName === 'hc-fill' && !paused()) go(cur + 1); }, true);
      dots.push(d); dotBox.appendChild(d);
    });
    if (!(REDUCE && REDUCE.matches)) ctl.appendChild(toggle);
    if (n > 1) { ctl.appendChild(prev); ctl.appendChild(dotBox); ctl.appendChild(next); }

    function sync() {
      root.classList.toggle('is-stopped', stopped);
      root.classList.toggle('is-held', !stopped && paused());
      view.setAttribute('aria-live', stopped ? 'polite' : 'off');
      toggle.setAttribute('aria-label', stopped ? 'Play' : 'Pause');
      toggle.classList.toggle('is-stopped', stopped);
    }
    function go(i) {
      cur = ((i % n) + n) % n;
      els.forEach(function (e, k) {
        var on = k === cur;
        e.classList.toggle('is-active', on);
        e.setAttribute('aria-hidden', on ? 'false' : 'true');
        if ('inert' in e) e.inert = !on;
      });
      dots.forEach(function (d, k) {
        if (k === cur) d.setAttribute('aria-current', 'true'); else d.removeAttribute('aria-current');
        var f = d.querySelector('.hc-fill'); f.style.animation = 'none'; void f.offsetWidth; f.style.animation = '';  // restart the fill
      });
    }
    toggle.addEventListener('click', function () { stopped = !stopped; hold.hover = false; sync(); });
    prev.addEventListener('click', function () { go(cur - 1); });
    next.addEventListener('click', function () { go(cur + 1); });
    root.addEventListener('mouseenter', function () { hold.hover = true; sync(); });
    root.addEventListener('mouseleave', function () { hold.hover = false; sync(); });
    root.addEventListener('focusin', function () { hold.focus = true; sync(); });
    root.addEventListener('focusout', function (e) { if (!root.contains(e.relatedTarget)) { hold.focus = false; sync(); } });
    function onVis() { hold.hidden = !!document.hidden; sync(); }
    document.addEventListener('visibilitychange', onVis);
    var io = null;
    if ('IntersectionObserver' in window) {
      hold.away = true;  // until it is seen
      io = new IntersectionObserver(function (es) { hold.away = !es[es.length - 1].isIntersecting; sync(); });
      io.observe(root);
    }
    root.tabIndex = 0;
    root.addEventListener('keydown', function (e) {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      var onDot = e.target && e.target.classList && e.target.classList.contains('hc-dot');
      if (e.key === 'ArrowRight') { go(cur + 1); e.preventDefault(); }
      else if (e.key === 'ArrowLeft') { go(cur - 1); e.preventDefault(); }
      else if (onDot && e.key === 'Home') { go(0); e.preventDefault(); }
      else if (onDot && e.key === 'End') { go(n - 1); e.preventDefault(); }
    });
    if (REDUCE && REDUCE.addEventListener) REDUCE.addEventListener('change', function () { if (REDUCE.matches) stopped = true; sync(); });
    go(0); sync();
    return {
      go: go,
      play: function () { stopped = false; sync(); },
      pause: function () { stopped = true; sync(); },
      destroy: function () { document.removeEventListener('visibilitychange', onVis); if (io) io.disconnect(); }
    };
  }

  function auto() {
    [].forEach.call(document.querySelectorAll('[data-hero-carousel]'), function (root) {
      if (root.classList.contains('hc')) return;
      var js = root.querySelector('script[type="application/json"]'), cfg;
      try { cfg = JSON.parse(js.textContent); } catch (e) { return; }
      if (!cfg.label) cfg.label = root.getAttribute('aria-label') || '';
      mount(root, cfg);
    });
  }
  window.HeroCarousel = { mount: mount, slideHtml: slideHtml, auto: auto };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', auto); else auto();
})();
