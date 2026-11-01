/* glowskin: the glow of the glowing charts (glowchart.js) given to every other chart on a Plato page, in the dark
   theme. Each mark of an SVG chart drawn in a saturated colour (a dot, a line, a bar, a clock hand) gets class "gl",
   and the shared filter #pc-glow (the mark's own colour, blurred, under it) lights it; grid lines, axes, text, halos,
   faint bands, big panels and perfectly straight lines (reference lines, error bars) stay flat, and data lines thinner than 2 px are drawn at 2 (class "gl-w"). Charts drawn
   later (after a fetch, a resize or a filter) are caught by a MutationObserver. Icons and the intro are left alone.

   Motion (Roger: "give a sense of motion"). The first time a chart appears in its place, it makes an entrance when it
   scrolls into view: its lines draw themselves from left to right, its dots pop in from left to right, its bars grow
   from their base, and grid cells come in row by row. A chart redrawn in the same place later (a slider, a filter, a
   resize) doesn't replay it. While a chart is on screen, a short light runs along each long line every few seconds
   (dark theme only). Reduced motion: none of this. Charts that animate themselves (statviz, the glowing charts) are
   left alone.
   The look is in glowchart.css; site.py adds both files to every Plato page. */
(function () {
  'use strict';
  var FILTER = '<svg width="0" height="0" style="position:absolute;width:0;height:0" aria-hidden="true" focusable="false">' +
    '<filter id="pc-glow" x="-60%" y="-60%" width="220%" height="220%" color-interpolation-filters="sRGB">' +
    '<feGaussianBlur in="SourceGraphic" stdDeviation="2.6" result="b"/>' +
    '<feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></svg>';

  function saturated(c, alpha) {  // a series colour: saturated, neither near-black nor near-white, mostly opaque
    var m = /rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/.exec(c || '');
    if (!m || (m[4] !== undefined && +m[4] < 0.5) || alpha < 0.5) return false;
    var r = m[1] / 255, g = m[2] / 255, b = m[3] / 255, mx = Math.max(r, g, b), mn = Math.min(r, g, b);
    var l = (mx + mn) / 2, s = mx === mn ? 0 : (mx - mn) / (1 - Math.abs(2 * l - 1));
    return s > 0.4 && l > 0.25 && l < 0.88;
  }
  function width(svg) {
    var w = svg.getBoundingClientRect().width;
    if (!w && svg.viewBox && svg.viewBox.baseVal) w = svg.viewBox.baseVal.width;
    return w || parseFloat(svg.getAttribute('width')) || 0;
  }
  function skin(svg) {
    if (svg.id === 'pc-glow-defs' || svg.closest('header, nav, .sp-stage, .splash, .glow-chart, [data-no-glow]')) return;
    if (width(svg) < 160) return;  // icons and small glyphs
    var marks = svg.querySelectorAll('circle, ellipse, path, polyline, polygon, line, rect');
    if (marks.length > 1200) return;
    [].forEach.call(marks, function (el) {
      if (el.classList.contains('gl') || el.closest('defs, clipPath, mask, marker, pattern')) return;
      var cs = getComputedStyle(el);
      if (+cs.opacity < 0.5) return;
      var sw = parseFloat(cs.strokeWidth) || 0;
      var stroke = cs.stroke !== 'none' && sw >= 1 && saturated(cs.stroke, +cs.strokeOpacity);
      var fill = cs.fill !== 'none' && saturated(cs.fill, +cs.fillOpacity);
      if (!stroke && !fill) return;
      if (el.tagName !== 'circle' && el.tagName !== 'ellipse') {
        var bb = null;
        try { bb = el.getBBox(); } catch (e) { /* not rendered */ }
        // a perfectly straight line has a box with no height (or width), and a filter sized from that box draws
        // nothing: such lines (reference lines, error bars) stay flat. So does a big filled area (a band, a panel).
        if (!bb || bb.width < 1 || bb.height < 1) return;
        if (fill && !stroke && bb.width * bb.height > 40000) return;
      }
      el.classList.add('gl');
      if (stroke && !fill && /^(path|polyline|line)$/.test(el.tagName) && sw < 2 && !/\d/.test(cs.strokeDasharray)) el.classList.add('gl-w');
    });
  }


  // ---- motion ------------------------------------------------------------------------------------------
  var reduce = false;
  try { reduce = matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { /* old browser */ }
  var played = new WeakSet(), running = new WeakMap(), io = null;
  function isLine(el, cs) { return /^(path|polyline|line)$/.test(el.tagName) && cs.fill === 'none' || el.tagName === 'line' || el.tagName === 'polyline'; }
  function entrance(svg, marks) {
    var vb = svg.viewBox && svg.viewBox.baseVal, vw = (vb && vb.width) || svg.getBoundingClientRect().width || 1;
    var vh = (vb && vb.height) || svg.getBoundingClientRect().height || 1, anims = [];
    var cells = marks.filter(function (el) {
      if (el.tagName !== 'rect') return false;
      var b = el.getBBox(); return b.width > 6 && Math.abs(b.width - b.height) < Math.max(b.width, b.height) * 0.25;
    });
    var grid = cells.length >= 9;
    marks.forEach(function (el) {
      var bb, cs = getComputedStyle(el);
      try { bb = el.getBBox(); } catch (e) { return; }
      var fx = (bb.x + bb.width / 2) / vw, fy = (bb.y + bb.height / 2) / vh;
      if (isLine(el, cs) && !/\d/.test(cs.strokeDasharray) && el.getTotalLength) {
        var L = el.getTotalLength();
        if (L < 30) return;
        anims.push(el.animate([{ strokeDasharray: L + ' ' + L, strokeDashoffset: L }, { strokeDasharray: L + ' ' + L, strokeDashoffset: 0 }],
          { duration: 1500, delay: 120, easing: 'cubic-bezier(.3,.7,.3,1)', fill: 'backwards' }));
        return;
      }
      if (el.hasAttribute('transform')) {  // its own transform (a rotated diamond): a new transform box would move it, so it fades in
        anims.push(el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 500, delay: 150 + fx * 1100, fill: 'backwards' }));
        return;
      }
      el.style.transformBox = 'fill-box';
      if (el.tagName === 'rect' && !(grid && cells.indexOf(el) >= 0)) {
        var across = bb.width >= bb.height;  // a bar grows from its base
        el.style.transformOrigin = across ? 'left center' : 'center bottom';
        anims.push(el.animate([{ transform: across ? 'scaleX(0)' : 'scaleY(0)' }, { transform: 'none' }],
          { duration: 900, delay: 100 + (across ? fy : fx) * 700, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'backwards' }));
        return;
      }
      el.style.transformOrigin = 'center';
      var delay = grid ? 80 + fy * 1400 : 150 + fx * 1100;  // grid cells row by row, dots left to right
      anims.push(el.animate([{ transform: 'scale(0)', opacity: 0 }, { transform: 'scale(1.25)', opacity: 1, offset: 0.7 }, { transform: 'none', opacity: 1 }],
        { duration: 520, delay: delay, easing: 'ease-out', fill: 'backwards' }));
    });
    return anims;
  }
  function flows(svg, marks) {  // a short light that runs along each long line now and then
    var out = [];
    marks.forEach(function (el) {
      if (el.classList.contains('gl-flow') || el.hasAttribute('data-flow')) return;
      var cs = getComputedStyle(el);
      if (!isLine(el, cs) || /\d/.test(cs.strokeDasharray) || !el.getTotalLength) return;
      var L = el.getTotalLength();
      if (L < 150) return;
      el.setAttribute('data-flow', '');
      var f = el.cloneNode(false);
      f.removeAttribute('id'); f.removeAttribute('data-flow');
      f.setAttribute('class', 'gl gl-flow');
      f.setAttribute('aria-hidden', 'true');
      f.style.fill = 'none';  // the copy loses the line's own classes, and with them fill: none
      f.style.strokeWidth = (parseFloat(cs.strokeWidth) || 2) + 0.6 + 'px';
      f.style.strokeDasharray = '22 ' + (L + 30);
      el.parentNode.insertBefore(f, el.nextSibling);
      out.push(f.animate([{ strokeDashoffset: 22 }, { strokeDashoffset: -L, offset: 0.5 }, { strokeDashoffset: -L }],
        { duration: Math.max(3600, L * 6), delay: 1800 + Math.random() * 1800, iterations: Infinity, easing: 'ease-in-out' }));
    });
    return out;
  }
  function animate(svg) {
    if (reduce || !svg.animate || svg.closest('.sv, [data-sv], .glow-chart, [data-no-motion]')) return;
    var marks = [].slice.call(svg.querySelectorAll('.gl:not(.gl-flow)'));
    if (!marks.length) return;
    var box = svg.parentElement || svg, intro = [];
    var loop = flows(svg, marks);  // before the entrance, which rewrites the lines' dash pattern while it runs
    if (!played.has(box)) { played.add(box); intro = entrance(svg, marks); }
    if (!intro.length && !loop.length) return;
    intro.forEach(function (a) { a.pause(); });
    loop.forEach(function (a) { a.pause(); });
    running.set(svg, { intro: intro, loop: loop });
    if (!io) io = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        var r = running.get(e.target); if (!r) return;
        if (e.isIntersecting) { r.intro.forEach(function (a) { a.play(); }); r.intro = []; r.loop.forEach(function (a) { a.play(); }); }
        else r.loop.forEach(function (a) { a.pause(); });
      });
    }, { threshold: 0.25 });
    io.observe(svg);
  }

  var pending = new Set(), queued = false;
  function queue(svg) {
    pending.add(svg);
    if (queued) return;
    queued = true;
    (window.requestAnimationFrame || setTimeout)(function () {
      queued = false;
      var all = Array.from(pending);
      pending.clear();
      all.forEach(function (s) { if (s.isConnected) { skin(s); animate(s); } });
    });
  }
  function scan(root) {
    if (root.nodeType !== 1) return;
    if (root.tagName === 'svg' || root.tagName === 'SVG') { queue(root.ownerSVGElement || root); return; }
    var own = root.closest && root.closest('svg');
    if (own) { queue(own); return; }
    [].forEach.call(root.querySelectorAll('svg'), function (s) { if (!s.ownerSVGElement) queue(s); });
  }
  function init() {
    if (!document.body) return;
    if (!document.getElementById('pc-glow')) {
      var holder = document.createElement('div');
      holder.innerHTML = FILTER;
      var defs = holder.firstChild;
      if (defs) { defs.id = 'pc-glow-defs'; document.body.appendChild(defs); }
    }
    scan(document.body);
    if (!window.MutationObserver) return;
    new MutationObserver(function (ms) {
      ms.forEach(function (m) {
        [].forEach.call(m.addedNodes, scan);
        if (m.type === 'attributes' && m.target.nodeType === 1) scan(m.target);
      });
    }).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden', 'open'] });
    addEventListener('load', function () { scan(document.body); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
