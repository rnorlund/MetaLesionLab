/* "From the lab": a band of striking pictures from the experiments at the foot of every Plato page (site.py adds
   the empty band, #lab-strip, after </main>), and the shared helpers the gallery page (/plato/gallery) uses.

   The band shows a random selection on each visit, degradation sequences weighted first, as cards that link to
   the gallery at that item. It drifts slowly in a seamless loop and stops on hover, focus, touch or Pause; it can
   be dragged, swiped or stepped with the arrows. A sequence's card plays its frames as a mini filmstrip (one
   sprite image per item). With prefers-reduced-motion: no drift, no filmstrip playing (first and last frame side
   by side), just a scrollable row.

   On the landing page and Draw, the band waits until the visitor has drawn or skipped, so the drawing stays blind
   (draw.js: sessionStorage tot-draw-seen, the tot:revealed event). Pictures load lazily. */
(function () {
  'use strict';

  var API = '/api/plato/gallery';
  var DEGRADE = 'Watch it degrade';
  var STILL = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  var TICK_MS = 850, HOLD_END = 3, HOLD_START = 1;

  function h(tag, attrs, kids) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      var v = attrs[k];
      if (v == null || v === false) return;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k === 'style') el.setAttribute('style', v);
      else if (k.slice(0, 2) === 'on' && typeof v === 'function') el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c != null && c !== false) el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return el;
  }

  var dataPromise = null;
  function load() {
    if (!dataPromise) {
      dataPromise = fetch(API).then(function (r) {
        if (!r.ok) throw new Error('No gallery here (' + r.status + ')');
        return r.json();
      });
      dataPromise.catch(function () { dataPromise = null; });
    }
    return dataPromise;
  }

  /* A random order, degradation items weighted first (weighted sampling without replacement), with no two
     neighbours from the same experiment family (telephone-, damage-, draw-damage-, ...) where that can be helped. */
  function family(item) { var p = item.id.split('-'); return p[0] === 'draw' ? 'draw-damage' : p[0]; }
  function order(items, degradeWeight) {
    var w = degradeWeight == null ? 4 : degradeWeight;
    var keyed = items.map(function (it) {
      return { it: it, k: Math.pow(Math.random(), 1 / (it.category === DEGRADE ? w : 1)) };
    }).sort(function (a, b) { return b.k - a.k; }).map(function (x) { return x.it; });
    for (var i = 1; i < keyed.length; i++) {
      if (family(keyed[i]) !== family(keyed[i - 1])) continue;
      for (var j = i + 1; j < keyed.length; j++) {
        if (family(keyed[j]) !== family(keyed[i - 1])) {
          var t = keyed.splice(j, 1)[0];
          keyed.splice(i, 0, t);
          break;
        }
      }
    }
    return keyed;
  }

  /* ---------- the mini filmstrip: one sprite, one cell shown at a time ---------- */
  var flips = [];
  var visible = typeof IntersectionObserver === 'function' ? new IntersectionObserver(function (entries) {
    entries.forEach(function (e) { e.target._flipOn = e.isIntersecting; });
  }, { rootMargin: '80px' }) : null;

  function nFrames(item) { return item.sequence ? item.sequence.frames.length : 1; }
  function cellAspect(item) {
    var s = item.thumb_size, n = nFrames(item);
    return s && s[0] && s[1] ? (s[0] / n) / s[1] : 1;
  }

  // One window onto the sprite showing cell k (half: only its left half, the first panel of a pair).
  function cell(item, k, lazy, half) {
    var n = nFrames(item), m = half ? 2 : 1;
    var img = h('img', { src: item.thumb, alt: '', loading: lazy === false ? null : 'lazy', decoding: 'async',
                         draggable: 'false', style: 'width:' + (n * 100 * m) + '%' });
    var r = (cellAspect(item) / m).toFixed(4);
    var box = h('span', { class: 'lab-cell' + (half ? ' is-half' : ''), style: '--r:' + r + ';aspect-ratio:' + r }, img);
    box._img = img;
    show(box, k, n);
    return box;
  }
  function show(box, k, n) { box._img.style.transform = 'translateX(' + (-100 * k / n).toFixed(4) + '%)'; }

  /* The card picture: a still, a playing filmstrip, or (reduced motion) first and last frames side by side. */
  function picture(item, opts) {
    opts = opts || {};
    if (!item.sequence) {
      var s = item.thumb_size || [];
      return h('span', { class: 'lab-pic' }, h('img', { src: item.thumb, alt: item.alt, loading: opts.lazy === false ? null : 'lazy',
        decoding: 'async', draggable: 'false', width: s[0] || null, height: s[1] || null }));
    }
    var frames = item.sequence.frames, n = frames.length;
    if (STILL || opts.still) {  // a pair's first frame is the intact picture twice: show it once
      var pair = !!frames[0].pair;
      return h('span', { class: 'lab-pic lab-pic-pair' + (pair ? ' is-pair' : ''), role: 'img', 'aria-label': item.alt }, [
        cell(item, 0, opts.lazy, pair), h('span', { class: 'lab-arrow', 'aria-hidden': 'true', text: '→' }), cell(item, n - 1, opts.lazy)]);
    }
    var box = cell(item, 0, opts.lazy);
    var label = h('span', { class: 'lab-frame', 'aria-hidden': 'true', text: frames[0].label });
    var bar = h('span', { class: 'lab-bar', 'aria-hidden': 'true' }, h('i', { style: 'width:' + (100 / n).toFixed(2) + '%' }));
    var wrap = h('span', { class: 'lab-pic lab-flip', role: 'img', 'aria-label': item.alt }, [box, label, bar]);
    // a random first pause, so neighbouring filmstrips don't flip in step
    var f = { el: wrap, box: box, label: label, bar: bar.firstChild, item: item, k: 0, hold: HOLD_START + Math.floor(Math.random() * 4) };
    wrap._flipOn = !visible;
    if (visible) visible.observe(wrap);
    flips.push(f);
    return wrap;
  }

  function tick() {
    if (document.hidden) return;
    flips = flips.filter(function (f) { return f.el.isConnected; });
    flips.forEach(function (f) {
      if (!f.el._flipOn || f.el._paused) return;
      if (f.hold > 0) { f.hold--; return; }
      var n = nFrames(f.item);
      f.k = (f.k + 1) % n;
      f.hold = f.k === n - 1 ? HOLD_END : f.k === 0 ? HOLD_START : 0;
      show(f.box, f.k, n);
      f.label.textContent = f.item.sequence.frames[f.k].label;
      f.bar.style.width = (100 * (f.k + 1) / n).toFixed(2) + '%';
    });
  }
  if (!STILL) setInterval(tick, TICK_MS);

  /* ---------- the band ---------- */
  function card(item, clone) {
    var href = '/plato/gallery#' + encodeURIComponent(item.id);
    var tab = clone ? '-1' : null;
    return h('li', { class: 'lab-card' + (item.category === DEGRADE ? ' is-degrade' : ''), 'aria-hidden': clone ? 'true' : null }, [
      picture(item),
      h('span', { class: 'lab-card-body' }, [
        h('span', { class: 'lab-card-cat', text: item.category }),
        h('a', { class: 'lab-card-title', href: href, tabindex: tab, draggable: 'false' }, item.title),
        h('span', { class: 'lab-card-cap', title: item.caption, text: item.caption }),
        item.credit ? h('span', { class: 'lab-card-credit', title: item.credit, text: item.credit }) : null,  // e.g. Quick, Draw! (CC BY 4.0)
        h('a', { class: 'lab-card-go', href: item.link, tabindex: tab, draggable: 'false' }, ['See the experiment', h('span', { 'aria-hidden': 'true', text: ' →' })])
      ])
    ]);
  }

  function mount(root, data) {
    var items = order(data.items).slice(0, 18);
    if (!items.length) return;
    var track = root.querySelector('.lab-strip-track');
    var list = h('ul', { class: 'lab-strip-list', role: 'list' });
    items.forEach(function (it) { list.appendChild(card(it)); });
    list.appendChild(h('li', { class: 'lab-card lab-card-all' }, h('a', { href: '/plato/gallery', class: 'lab-card-title' },
      ['See all ' + data.items.length + ' in the gallery', h('span', { 'aria-hidden': 'true', text: ' →' })])));
    var loop = !STILL;
    if (loop) {  // a second copy for the seamless loop: hidden from screen readers and the tab order
      items.forEach(function (it) { list.appendChild(card(it, true)); });
      list.appendChild(h('li', { class: 'lab-card lab-card-all', 'aria-hidden': 'true' },
        h('a', { href: '/plato/gallery', class: 'lab-card-title', tabindex: '-1' }, 'See all ' + data.items.length + ' in the gallery →')));
    }
    track.appendChild(list);
    root.hidden = false;
    fitWidth(root);

    var setW = 0;
    function measure() {
      var first = list.children[0], copy = list.children[items.length + 1];
      setW = loop && first && copy ? copy.offsetLeft - first.offsetLeft : 0;
    }
    measure();
    window.addEventListener('resize', function () { fitWidth(root); measure(); });
    window.addEventListener('load', measure);

    // --- drift ---
    var pos = 0, last = 0, userPaused = false, hover = false, focus = false, touchUntil = 0, onScreen = true, dragging = false;
    var pauseBtn = root.querySelector('[data-lab-pause]');
    function wrap() {
      if (!setW) return;
      if (track.scrollLeft >= setW) track.scrollLeft -= setW;
      else if (track.scrollLeft <= 0 && pos < 0) track.scrollLeft += setW;
    }
    function running() {
      return loop && !userPaused && !hover && !focus && !dragging && onScreen && !document.hidden && Date.now() > touchUntil;
    }
    function frame(t) {
      var dt = last ? Math.min(t - last, 64) : 0;
      last = t;
      if (running() && setW) {
        if (Math.abs(track.scrollLeft - pos) > 2) pos = track.scrollLeft;  // the visitor scrolled: carry on from there
        pos += dt * speed() / 1000;
        if (pos >= setW) pos -= setW;
        track.scrollLeft = pos;
      } else {
        pos = track.scrollLeft;
      }
      requestAnimationFrame(frame);
    }
    function speed() { return Math.max(22, Math.min(46, window.innerWidth / 48)); }  // px per second
    if (loop) requestAnimationFrame(frame);
    track.addEventListener('scroll', function () { if (loop && !running()) wrap(); }, { passive: true });

    root.addEventListener('mouseenter', function () { hover = true; });
    root.addEventListener('mouseleave', function () { hover = false; });
    root.addEventListener('focusin', function () { focus = true; });
    root.addEventListener('focusout', function (e) { if (!root.contains(e.relatedTarget)) focus = false; });
    track.addEventListener('touchstart', function () { touchUntil = Date.now() + 1e9; }, { passive: true });
    track.addEventListener('touchend', function () { touchUntil = Date.now() + 2500; }, { passive: true });
    if (typeof IntersectionObserver === 'function') {
      new IntersectionObserver(function (e) { onScreen = e[0].isIntersecting; }).observe(root);
    }
    if (pauseBtn) {
      if (!loop) pauseBtn.hidden = true;
      pauseBtn.addEventListener('click', function () {
        userPaused = !userPaused;
        pauseBtn.setAttribute('aria-pressed', String(userPaused));
        pauseBtn.querySelector('span').textContent = userPaused ? 'Play' : 'Pause';
        flips.forEach(function (f) { if (root.contains(f.el)) f.el._paused = userPaused; });
      });
    }

    // --- drag with a mouse (touch scrolls natively); a drag is not a click ---
    var down = null, moved = false;
    track.addEventListener('pointerdown', function (e) {
      if (e.pointerType !== 'mouse' || e.button !== 0) return;
      down = { x: e.clientX, left: track.scrollLeft };
      moved = false;
    });
    window.addEventListener('pointermove', function (e) {
      if (!down) return;
      var dx = e.clientX - down.x;
      if (!moved && Math.abs(dx) > 5) { moved = true; dragging = true; root.classList.add('is-dragging'); }
      if (moved) {
        track.scrollLeft = down.left - dx;
        if (setW && track.scrollLeft >= setW) { track.scrollLeft -= setW; down.left -= setW; }
        if (setW && track.scrollLeft <= 0 && dx > 0) { track.scrollLeft += setW; down.left += setW; }
      }
    });
    window.addEventListener('pointerup', function () {
      if (!down) return;
      down = null;
      setTimeout(function () { dragging = false; root.classList.remove('is-dragging'); }, 0);
    });
    track.addEventListener('click', function (e) { if (moved) { e.preventDefault(); e.stopPropagation(); moved = false; } }, true);
    track.addEventListener('dragstart', function (e) { e.preventDefault(); });

    // --- previous and next ---
    root.querySelectorAll('[data-lab-step]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var dir = Number(btn.getAttribute('data-lab-step'));
        var c = list.children[0];
        var step = c ? c.getBoundingClientRect().width + 16 : 300;
        var n = Math.max(1, Math.floor(track.clientWidth / step) - 1);
        if (loop && dir < 0 && track.scrollLeft < n * step + 4 && setW) track.scrollLeft += setW;
        touchUntil = Date.now() + 4000;  // let the visitor look before the drift goes on
        track.scrollBy({ left: dir * n * step, behavior: STILL ? 'auto' : 'smooth' });
      });
    });
  }

  // Full width of the window, whatever column the page puts the band in (no horizontal page scroll).
  function fitWidth(root) {
    var vw = document.documentElement.clientWidth;
    root.style.setProperty('--lab-vw', vw + 'px');
    root.style.marginLeft = '0px';
    var left = root.getBoundingClientRect().left + window.scrollX;
    root.style.marginLeft = (-left) + 'px';
  }

  function start() {
    var root = document.getElementById('lab-strip');
    if (!root) return;
    var blind = document.getElementById('hero-draw') || document.getElementById('draw-app');
    var seen = false;
    try { seen = window.sessionStorage.getItem('tot-draw-seen') === '1'; } catch (e) { seen = false; }
    var go = function () { load().then(function (d) { mount(root, d); }).catch(function () { /* no band */ }); };
    if (blind && !seen) document.addEventListener('tot:revealed', go, { once: true });
    else go();
  }

  window.TOTGallery = { load: load, order: order, picture: picture, cell: cell, show: show, nFrames: nFrames,
                        cellAspect: cellAspect, still: STILL, h: h };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
