/* motion: the Plato site's shared motion layer (static/css/motion.css has the looks). site.py adds both to every Plato
   page, after a tiny boot script that puts "mo" on <html> only when motion is welcome (no prefers-reduced-motion, an
   IntersectionObserver, no ?motion=0) and "mo-boot", which hides the first screen until this script has set it up.
   If this script never runs, the boot script takes both away again after 2.5 s; if it fails, it takes them away
   itself. Without either, nothing is hidden and nothing moves.

   What it does:
   - Scroll reveal. The first screen's parts (the question, the answer, the picture, the numbers) come in one after
     another; every later section's parts and every card rise into view once as they are scrolled to, a row of cards
     one card at a time. Which blocks: the AUTO selectors below (a block that holds other such blocks lets them move
     instead), plus any element with data-reveal (data-reveal="fade": no rise). data-reveal="none" on an element or
     an ancestor keeps it still. A revealed block gets .mo-in and a "mo:in" event (statviz.js waits for it, so its
     graphics play where they can be seen).
   - The chairs (home #chairs, /plato .pc-chairs): when they come into view, Muse Image's 16 are dealt from one point
     into the grid and people's 16 drift in from a cloud, while the spread under each counts up to 0.13 and 0.36.
     They settle spread out; stacking stays the visitor's button (landing.js, plato.js).
   - The home hero: Plato follows the pointer a little (a slow sway on a phone). Nothing else drifts: the site's look
     is big and quiet, so motion here is slow, smooth and only where it says something.
   - The draw pad: a wet-ink glow follows the pen (a canvas over the pad, colours from the tokens); motion.css adds
     the scan while the drawing is measured.
   - A Play button no one has pressed yet breathes a few times when it comes into view; [data-kenburns] frames drift
     closer while in view.
   Costs: one IntersectionObserver for the reveals, one for the rest, a MutationObserver on <main> for blocks drawn
   later (cards from a fetch), one pointermove listener while the home hero is on screen. Everything animates
   transform/translate/scale and opacity only. */
(function () {
  'use strict';
  var d = document, html = d.documentElement;
  if (!html.classList.contains('mo')) return;  // the boot script said no (reduced motion, no observer) or gave up
  var M = window.PCMotion = { countUp: countUp };

  function off() { html.classList.remove('mo', 'mo-boot'); }
  function $$(sel, root) { return Array.prototype.slice.call((root || d).querySelectorAll(sel)); }
  function rng(seed) {  // a small seeded generator: the same cloud on every load
    var s = seed >>> 0;
    return function () {
      s = (s + 0x6D2B79F5) >>> 0;
      var t = Math.imul(s ^ (s >>> 15), s | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // ---------- scroll reveal ----------
  var AUTO = [
    // the first screen's parts, and the parts of its inner columns
    'main > section:first-of-type > *', '.pc-top-text > *', '.gx-top-text > *', '.draw-grid > *', '.hero-ask > *',
    // every later section's parts: headings, figures, text, panels
    'main > section > *', '.wrap.section > *', '.split > *', '.plato-sec > *', '.socrates-row > *', '.reveal-band .hero-text > *',
    // cards, one at a time
    '.hub-grid > li', '.series-grid > *', '.finds > *', '.how > li', '.gx-grid > .gx-card', '.gx-films > *',
    // "From the lab", the band above the footer
    '.lab-strip > .lab-strip-head', '.lab-strip > .lab-strip-track',
    '[data-reveal]'
  ].join(', ');
  var CARDS = '.hub-grid > li, .series-grid > *, .gx-grid > .gx-card';
  // never: blocks with a moment of their own, the landing quote band (its own carousel), the tour's and the splash's
  var SKIP = '[data-reveal="none"], .chairs, .pc-chairs, .hero-plato, .quote-band, .splash, dialog, .pt-guide, .tour-card';
  var seen = typeof WeakSet === 'function' ? new WeakSet() : null;
  var firstSec = d.querySelector('main > section');
  var loadedAt = Date.now(), lastInput = 0;

  function wanted(el) {
    if (el.nodeType !== 1 || (seen && seen.has(el)) || el.classList.contains('mo-r')) return false;
    if (el.getAttribute('data-reveal') === 'none' || el.closest(SKIP)) return false;
    if (/^(SCRIPT|STYLE|LINK|TEMPLATE|META|BR)$/.test(el.tagName)) return false;
    if (!el.hasAttribute('data-reveal') && el.querySelector(AUTO)) return false;  // a container: its blocks move instead
    var cs = getComputedStyle(el);
    if (cs.display === 'contents' || cs.position === 'fixed' || cs.position === 'sticky') return false;
    if (cs.animationName && cs.animationName !== 'none') return false;  // it has an entrance of its own
    return true;
  }
  function inView(r) { return r.bottom > 0 && r.top < window.innerHeight && r.right > 0 && r.left < window.innerWidth; }
  function order(a, b) { return (a.r.top - b.r.top) || (a.r.left - b.r.left); }

  function show(list, step, cap) {
    list.forEach(function (it, i) {
      var wait = Math.min(cap, i * step);
      it.el.style.setProperty('--mo-delay', wait + 'ms');
      it.el.classList.add('mo-in');
      try { it.el.dispatchEvent(new CustomEvent('mo:in')); } catch (e) { /* old browser: statviz has its own timer */ }
      var nums = it.el.matches(COUNT) ? [it.el] : $$(COUNT, it.el);
      if (nums.length) setTimeout(function () { nums.forEach(function (n) { countUp(n, 1800); }); }, wait);
    });
  }
  var revealIO = new IntersectionObserver(function (entries) {
    var batch = [];
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      revealIO.unobserve(e.target);
      batch.push({ el: e.target, r: e.boundingClientRect });
    });
    show(batch.sort(order), 110, 660);
  }, { rootMargin: '0px 0px -6% 0px', threshold: 0 });

  // Tag the blocks. now: the ones on screen that should come in at once (the first screen, before it is seen).
  function tag(els, entrance) {
    var now = [];
    els.forEach(function (el) {
      if (seen) seen.add(el);
      var r = el.getBoundingClientRect();
      if (inView(r) && !entrance(el)) return;  // already on screen and already seen: leave it be
      el.classList.add('mo-r');
      if (el.getAttribute('data-reveal') === 'fade') el.classList.add('mo-fade');
      if (inView(r)) now.push({ el: el, r: r });
      else revealIO.observe(el);
    });
    return now;
  }

  function painted() {
    try { return performance.getEntriesByType('paint').some(function (p) { return p.name === 'first-contentful-paint'; }); }
    catch (e) { return true; }
  }

  // ---------- counting up a number (the chairs' spread, a finding's big number, [data-count]) ----------
  // Only the element's own text counts ("34" of "34<small> of 35</small>"); it keeps its final width meanwhile and
  // ends on its own text. Screen readers are not told about the frames: the text is right before and after.
  var NUM = /\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?/g;
  var COUNT = '.find-num, [data-count]';
  function countUp(node, ms) {
    var jobs = [];
    for (var c = node.firstChild; c; c = c.nextSibling) {
      if (c.nodeType !== 3) continue;
      var text = c.nodeValue, parts = [], last = 0, m;
      NUM.lastIndex = 0;
      while ((m = NUM.exec(text))) { parts.push(text.slice(last, m.index), m[0]); last = m.index + m[0].length; }
      if (parts.length) jobs.push({ node: c, text: text, parts: parts.concat(text.slice(last)) });
    }
    if (!jobs.length || node.__moCounting) return;
    node.__moCounting = true;
    node.style.minWidth = node.getBoundingClientRect().width + 'px';
    if (getComputedStyle(node).display === 'inline') node.style.display = 'inline-block';
    var t0 = null;
    requestAnimationFrame(function frame(t) {
      if (t0 == null) t0 = t;
      var k = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - k, 3);
      jobs.forEach(function (j) {
        j.node.nodeValue = k >= 1 ? j.text : j.parts.map(function (p, i) {
          if (i % 2 === 0) return p;
          var v = parseFloat(p.replace(/,/g, '')), dec = (p.split('.')[1] || '').length;
          return p.indexOf(',') >= 0 ? Math.round(v * e).toLocaleString('en-US') : (v * e).toFixed(dec);
        }).join('');
      });
      if (k < 1) return requestAnimationFrame(frame);
      node.style.minWidth = node.style.display = '';
      node.__moCounting = false;
    });
  }

  // ---------- one more observer for everything that plays when seen ----------
  var onView = new Map();
  var viewIO = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      var fn = onView.get(e.target);
      if (fn) fn(e.isIntersecting, e);
    });
  }, { threshold: [0, 0.2] });
  function whenSeen(el, fn) { onView.set(el, fn); viewIO.observe(el); }

  // ---------- the chairs: dealt from one point, and a cloud ----------
  function chairs(fig) {
    var people = $$('[data-side="people"] span', fig);
    if (!people.length) return;
    var rand = rng(16);
    people.forEach(function (s) {
      var c = +getComputedStyle(s).getPropertyValue('--c') || 0, r = +getComputedStyle(s).getPropertyValue('--r') || 0;
      // each starts somewhere else in its grid, turned, so the 16 settle out of a jumble (inside the grid: no scrolling)
      s.style.setProperty('--fx', Math.round((rand() * 3 - c) * 104) + '%');
      s.style.setProperty('--fy', Math.round((rand() * 3 - r) * 104) + '%');
      s.style.setProperty('--fr', Math.round((rand() - 0.5) * 80) + 'deg');
      s.style.setProperty('--fd', Math.round(1300 + rand() * 700) + 'ms');
      s.style.setProperty('--fw', Math.round(rand() * 650) + 'ms');
    });
    fig.classList.add('mo-prefly');
    var done = false, timer = null;
    function settle() { fig.classList.remove('mo-prefly', 'mo-fly'); }
    whenSeen(fig, function (on, e) {
      if (done || !on || e.intersectionRatio < 0.15) return;
      done = true;
      viewIO.unobserve(fig);
      fig.classList.add('mo-fly');
      fig.classList.remove('mo-prefly');
      $$('.when-grid b', fig).forEach(function (b) { countUp(b, 1800); });
      timer = setTimeout(settle, 2800);
    });
    // stacking is the visitor's: a press during the entrance ends it at once
    var btn = fig.querySelector('.stack-btn, .pc-stack-btn');
    if (btn) btn.addEventListener('click', function () { done = true; clearTimeout(timer); settle(); }, true);
  }

  // ---------- the home hero: Plato follows the pointer a little (on a phone, motion.css lets him sway) ----------
  function hero() {
    var ask = d.querySelector('.hero-ask');
    if (!ask || !ask.querySelector('.hero-plato')) return;
    ask.classList.add('mo-hero');
    if (!(window.matchMedia && matchMedia('(hover: hover) and (pointer: fine)').matches)) return;
    var x = 0, y = 0, queued = false, live = false;
    function apply() {
      queued = false;
      ask.style.setProperty('--mo-px', x.toFixed(3));
      ask.style.setProperty('--mo-py', y.toFixed(3));
    }
    function move(e) {
      if (!live || e.pointerType !== 'mouse') return;
      x = e.clientX / window.innerWidth - 0.5;
      y = e.clientY / window.innerHeight - 0.5;
      if (!queued) { queued = true; requestAnimationFrame(apply); }
    }
    whenSeen(ask, function (on) { live = on; });
    window.addEventListener('pointermove', move, { passive: true });
  }

  // ---------- the draw pad: a wet-ink glow behind the pen ----------
  function inkTrail() {
    var cv = null, ctx = null, pad = null, pts = [], down = false, raf = 0, colour = '', tip = '';
    function token(name, fallback) { return (getComputedStyle(pad).getPropertyValue(name) || '').trim() || fallback; }
    function size() {
      var r = pad.getBoundingClientRect(), dpr = Math.min(2, window.devicePixelRatio || 1);
      cv.width = Math.round(r.width * dpr);
      cv.height = Math.round(r.height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return r;
    }
    var rect = null;
    function start(e) {
      var target = e.target;
      if (!target || target.getAttribute('data-dw') !== 'pad' || (e.button != null && e.button > 0)) return;
      var panel = target.closest('.dw-panel');
      if (panel && panel.querySelector('.dw-status .spinner')) return;  // measuring: the pad isn't drawing
      if (pad !== target) {
        pad = target;
        if (cv) cv.remove();
        cv = d.createElement('canvas');
        cv.className = 'mo-ink';
        cv.setAttribute('aria-hidden', 'true');
        pad.parentNode.appendChild(cv);
        ctx = cv.getContext('2d');
      }
      rect = size();
      colour = token('--blue-fill', 'currentColor');
      tip = token('--orange-fill', colour);
      down = true;
      add(e);
      loop();
    }
    function add(e) {
      var evs = e.getCoalescedEvents ? e.getCoalescedEvents() : [];
      (evs.length ? evs : [e]).forEach(function (ev) {
        pts.push({ x: ev.clientX - rect.left, y: ev.clientY - rect.top, t: performance.now() });
      });
    }
    function moveIt(e) { if (down && e.target === pad) add(e); }
    function end() { down = false; }
    function loop() {
      if (raf) return;
      raf = requestAnimationFrame(function draw(now) {
        raf = 0;
        var life = 520, w = Math.max(5, rect.width / 46);
        while (pts.length && now - pts[0].t > life) pts.shift();
        ctx.clearRect(0, 0, rect.width, rect.height);
        ctx.lineCap = ctx.lineJoin = 'round';
        ctx.strokeStyle = colour;
        for (var i = 1; i < pts.length; i++) {
          var a = pts[i - 1], b = pts[i], k = 1 - (now - b.t) / life;
          if (k <= 0 || Math.abs(b.t - a.t) > 80) continue;  // a new stroke: no bridge between them
          ctx.globalAlpha = 0.34 * k * k;
          ctx.lineWidth = w * (0.5 + 0.5 * k);
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        }
        var p = pts[pts.length - 1];
        if (down && p) {  // the pen's tip
          ctx.globalAlpha = 0.5;
          ctx.fillStyle = tip;
          ctx.beginPath(); ctx.arc(p.x, p.y, w * 0.45, 0, Math.PI * 2); ctx.fill();
        }
        ctx.globalAlpha = 1;
        if (down || pts.length) loop();
        else ctx.clearRect(0, 0, rect.width, rect.height);
      });
    }
    d.addEventListener('pointerdown', start, { passive: true, capture: true });
    d.addEventListener('pointermove', moveIt, { passive: true, capture: true });
    d.addEventListener('pointerup', end, { passive: true, capture: true });
    d.addEventListener('pointercancel', end, { passive: true, capture: true });
  }

  // ---------- small ambient things ----------
  function ambient() {
    $$('.pi-play, .tp-play, #learn-play, [data-breathe]').forEach(function (b) {
      var once = false;
      whenSeen(b, function (on, e) {
        if (once || !on || e.intersectionRatio < 0.15) return;
        once = true;
        b.classList.add('mo-breathe');
      });
      b.addEventListener('click', function () { b.classList.remove('mo-breathe'); }, { once: true });
    });
    $$('[data-kenburns]').forEach(function (f) { whenSeen(f, function (on) { f.classList.toggle('mo-kb', on); }); });
  }

  // ---------- blocks drawn later: cards from a fetch, a section filled in by its script ----------
  function later() {
    var main = d.querySelector('main');
    if (!main || !window.MutationObserver) return;
    new MutationObserver(function (records) {
      var found = [];
      records.forEach(function (rec) {
        Array.prototype.forEach.call(rec.addedNodes, function (n) {
          if (n.nodeType !== 1 || n.namespaceURI !== 'http://www.w3.org/1999/xhtml') return;
          if (n.matches(AUTO)) found.push(n);
          if (n.firstElementChild) found.push.apply(found, $$(AUTO, n));
        });
      });
      if (!found.length) return;
      // Right after a click or a key, a block the page redraws in place stays still; cards and the first data stay lively.
      var calm = Date.now() - lastInput < 1200, early = Date.now() - loadedAt < 5000;
      found = found.filter(function (el) { return wanted(el) && !calm && (early || el.matches(CARDS)); });
      show(tag(found, function () { return true; }).sort(order), 90, 630);
    }).observe(main, { childList: true, subtree: true });
    ['pointerdown', 'keydown', 'input'].forEach(function (t) {
      d.addEventListener(t, function () { lastInput = Date.now(); }, { passive: true, capture: true });
    });
  }

  // ---------- start ----------
  function start() {
    var fresh = !painted();
    $$('#chairs, .pc-chairs').forEach(chairs);
    var els = $$(AUTO).filter(wanted);
    // the first screen comes in now, in reading order; anything else already on screen only if nothing was painted yet
    var now = tag(els, function (el) { return fresh || (firstSec && firstSec.contains(el)); });
    html.classList.remove('mo-boot');
    hero();
    inkTrail();
    ambient();
    later();
    var go = function () { show(now.sort(order), 130, 780); };
    if (html.classList.contains('splash-on')) {  // the opening animation first; the page comes in after it
      var mo = new MutationObserver(function () {
        if (!html.classList.contains('splash-on')) { mo.disconnect(); requestAnimationFrame(go); }
      });
      mo.observe(html, { attributes: true, attributeFilter: ['class'] });
    } else {
      requestAnimationFrame(go);
    }
  }

  try {
    if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', function () { try { start(); } catch (e) { fail(e); } });
    else start();
  } catch (e) { fail(e); }
  function fail(e) {
    off();
    $$('.mo-r').forEach(function (el) { el.classList.add('mo-in'); });
    if (window.console) console.warn('motion: ' + (e && e.message));
  }
})();
