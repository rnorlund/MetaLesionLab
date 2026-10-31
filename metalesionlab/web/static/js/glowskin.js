/* glowskin: the glow of the glowing charts (glowchart.js) given to every other chart on a Plato page, in the dark
   theme. Each mark of an SVG chart drawn in a saturated colour (a dot, a line, a bar, a clock hand) gets class "gl",
   and the shared filter #pc-glow (the mark's own colour, blurred, under it) lights it; grid lines, axes, text, halos,
   faint bands, big panels and perfectly straight lines (reference lines, error bars) stay flat, and data lines thinner than 2 px are drawn at 2 (class "gl-w"). Charts drawn
   later (after a fetch, a resize or a filter) are caught by a MutationObserver. Icons and the intro are left alone.
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

  var pending = new Set(), queued = false;
  function queue(svg) {
    pending.add(svg);
    if (queued) return;
    queued = true;
    (window.requestAnimationFrame || setTimeout)(function () {
      queued = false;
      var all = Array.from(pending);
      pending.clear();
      all.forEach(function (s) { if (s.isConnected) skin(s); });
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
