/* glowchart: charts drawn as light on the dark ground (Roger's pick, Oct 31): every mark glows, crowded stretches
   glow brighter, labels sit on the marks instead of in a legend, and the axes say what they mean in words.

   Kinds (markup, then GlowChart.renderAll() on load):
     <div class="glow-chart" data-glow="layers" data-src="/api/plato/inside/layers"></div>
       Muse Glimmer's 52 layers: per thing, how spread out Muse Image's and people's doodles look to it (faint
       threads), their means (bold, glowing) and the median layer where Muse Image's collapse to one.
   Colours are the --chart-muse / --chart-people / --chart-you tokens (app.css), checked for colour blindness on
   both themes; text is in ink tokens. Each chart draws itself in when it scrolls into view (reduced motion: drawn
   at once), redraws on resize and on a theme switch, and shows the values under the pointer. */
(function () {
  'use strict';
  var reduce = false;
  try { reduce = matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { /* old browser */ }

  function tok(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function colors() {
    return { muse: tok('--chart-muse'), people: tok('--chart-people'), you: tok('--chart-you'), ink: tok('--ink'),
             ink2: tok('--ink-2'), muted: tok('--muted'), line: tok('--line'), bg: tok('--chart-bg') };
  }
  function rgba(color, a) {  // a token colour (#RRGGBB) at alpha a
    var h = color.replace('#', '');
    if (h.length === 3) h = h.replace(/(.)/g, '$1$1');
    return 'rgba(' + parseInt(h.slice(0, 2), 16) + ',' + parseInt(h.slice(2, 4), 16) + ',' + parseInt(h.slice(4, 6), 16) + ',' + a + ')';
  }
  function ease(t) { return 1 - Math.pow(1 - t, 3); }

  function canvasFor(el, W, H) {
    var cv = el.querySelector('canvas');
    if (!cv) { cv = document.createElement('canvas'); el.appendChild(cv); }
    var dpr = window.devicePixelRatio || 1;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    cv.style.width = W + 'px'; cv.style.height = H + 'px';
    var g = cv.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { cv: cv, g: g };
  }
  function fonts(el) {
    var cs = getComputedStyle(el), base = parseFloat(cs.fontSize) || 16, fam = cs.fontFamily;
    return { base: base, label: function (k, w) { return (w || 500) + ' ' + Math.round(base * (k || 1)) + 'px ' + fam; } };
  }
  function text(g, s, x, y, o, C) {  // ink text with a halo of the chart's ground, so it reads over the marks
    g.font = o.font; g.textAlign = o.align || 'left'; g.textBaseline = o.base || 'middle';
    g.lineJoin = 'round'; g.lineWidth = 5; g.strokeStyle = C.bg; g.strokeText(s, x, y);
    g.fillStyle = o.color || C.ink; g.fillText(s, x, y);
  }
  function tipFor(el) {
    var t = el.querySelector('.glow-tip');
    if (!t) { t = document.createElement('div'); t.className = 'glow-tip'; t.hidden = true; el.appendChild(t); }
    return t;
  }
  function onView(el, start) {
    if (reduce || !('IntersectionObserver' in window)) { start(); return; }
    var io = new IntersectionObserver(function (es) {
      if (es[0].isIntersecting) { io.disconnect(); start(); }
    }, { threshold: 0.3 });
    io.observe(el);
  }

  // ---- layers: Muse Glimmer's 52 layers ------------------------------------------------------------
  function layers(el, d) {
    var t0 = null, raf = 0, hoverAt = null, n = d.n_layers;
    var top = Math.max.apply(0, d.things.map(function (t) { return Math.max(Math.max.apply(0, t.muse), Math.max.apply(0, t.people)); }));
    var yMax = Math.ceil(top * 10) / 10;
    var last = function (a) { return a[a.length - 1]; };

    function draw(now) {
      var C = colors(), F = fonts(el), W = Math.max(280, el.clientWidth);
      var H0 = Math.round(Math.max(280, Math.min(520, W * 0.5)));
      var cg = canvasFor(el, W, H0), g = cg.g;
      // the end labels need room on the right; without it they go inside the plot (narrow)
      g.font = F.label(1, 650);
      var labW = Math.max(g.measureText('People’s doodles').width, g.measureText('Meta AI’s doodles').width);
      g.font = F.label(0.9, 400);
      labW = Math.max(labW, g.measureText('look like one picture').width) + 34;
      var narrow = W < 620 || W - labW < W * 0.66;
      var H = narrow ? Math.round(Math.max(300, Math.min(520, W * 0.9))) : H0;
      if (H !== H0) { cg = canvasFor(el, W, H); g = cg.g; }
      var padL = 8, padR = narrow ? 12 : labW, padT = F.base * (narrow ? 3.8 : 2.2), padB = F.base * 3.6;
      var pw = W - padL - padR, ph = H - padT - padB;
      var X = function (i) { return padL + i / (n - 1) * pw; }, Y = function (v) { return padT + (1 - v / yMax) * ph; };
      var p = reduce ? 1 : t0 === null ? 0 : ease(Math.min(1, (now - t0) / 1800));
      var cut = padL + p * pw;
      // ground: three quiet guides, no numbers (the words on the left say what up and down mean)
      g.strokeStyle = C.line; g.lineWidth = 1;
      [0.25, 0.5, 0.75].forEach(function (f) { g.beginPath(); g.moveTo(padL, padT + f * ph); g.lineTo(padL + pw, padT + f * ph); g.stroke(); });
      g.beginPath(); g.moveTo(padL, padT + ph); g.lineTo(padL + pw, padT + ph); g.stroke();
      g.save(); g.beginPath(); g.rect(0, 0, cut + 2, H); g.clip();
      // each thing as a faint thread, then the two means, glowing
      function path(a) { g.beginPath(); a.forEach(function (v, i) { if (i) g.lineTo(X(i), Y(v)); else g.moveTo(X(i), Y(v)); }); }
      g.lineWidth = 1;
      d.things.forEach(function (t) {
        g.strokeStyle = rgba(C.people, 0.14); path(t.people); g.stroke();
        g.strokeStyle = rgba(C.muse, 0.16); path(t.muse); g.stroke();
      });
      [['people', d.mean.people], ['muse', d.mean.muse]].forEach(function (s) {
        g.save(); g.shadowColor = C[s[0]]; g.shadowBlur = 16; g.strokeStyle = C[s[0]]; g.lineWidth = 3.5; g.lineJoin = 'round';
        path(s[1]); g.stroke(); g.restore();
      });
      g.restore();
      // where Muse Image's doodles merge: a marker once the line has reached it
      var k = Math.round(d.collapse_layer) - 1, kx = X(k);
      if (cut >= kx) {
        var a = reduce ? 1 : Math.min(1, (cut - kx) / (pw * 0.08));
        g.globalAlpha = a;
        g.setLineDash([4, 5]); g.strokeStyle = C.muted; g.lineWidth = 1.2;
        g.beginPath(); g.moveTo(kx, padT - F.base * 0.4); g.lineTo(kx, padT + ph); g.stroke(); g.setLineDash([]);
        g.save(); g.shadowColor = C.muse; g.shadowBlur = 18; g.fillStyle = C.muse;
        g.beginPath(); g.arc(kx, Y(d.mean.muse[k]), 6, 0, 7); g.fill(); g.restore();
        g.font = F.label(0.9, 600);
        var say = 'Stage ' + (k + 1) + ': the AI’s doodles merge into one';
        if (g.measureText(say).width > Math.max(kx - 6, W - kx - 10)) say = 'Stage ' + (k + 1) + ': the AI’s merge';
        var fitsRight = kx + 10 + g.measureText(say).width <= W - 4;
        text(g, say, fitsRight ? kx + 10 : kx - 6, padT - F.base * 0.9, { font: F.label(0.9, 600), align: fitsRight ? 'left' : 'right' }, C);
        g.globalAlpha = 1;
      }
      // labels on the lines' ends, in words
      var ends = [['people', 'People’s doodles', 'still all different'], ['muse', 'Meta AI’s doodles', 'look like one picture']];
      ends.forEach(function (e) {
        var v = last(d.mean[e[0]]), x = padL + pw + 12, y = Y(v);
        g.globalAlpha = p;
        if (narrow) {
          text(g, e[1] + ': ' + e[2], padL + pw, y + (e[0] === 'muse' ? -F.base : -F.base), { font: F.label(0.85, 650), align: 'right' }, C);
        } else {
          g.fillStyle = C[e[0]]; g.beginPath(); g.arc(x + 4, y - F.base * 0.55, 5, 0, 7); g.fill();
          text(g, e[1], x + 14, y - F.base * 0.55, { font: F.label(1, 650) }, C);
          text(g, e[2], x + 14, y + F.base * 0.65, { font: F.label(0.9, 400), color: C.ink2 }, C);
        }
        g.globalAlpha = 1;
      });
      // what up and down mean, and the stages along the bottom
      text(g, '↑ drawings look different', padL, padT - F.base * (narrow ? 2.6 : 0.9), { font: F.label(0.85, 500), color: C.muted }, C);
      text(g, '↓ alike', padL, padT + ph - F.base * 0.7, { font: F.label(0.85, 500), color: C.muted }, C);
      [1, 13, 26, 39, 52].forEach(function (s) {
        text(g, String(s), X(s - 1), padT + ph + F.base * 0.9, { font: F.label(0.85, 500), color: C.muted, align: s === 1 ? 'left' : s === n ? 'right' : 'center' }, C);
      });
      text(g, 'Muse Glimmer’s 52 stages: seeing the picture → naming it', padL + pw / 2, padT + ph + F.base * 2.4,
           { font: F.label(0.9, 600), color: C.ink2, align: 'center' }, C);
      // the stage under the pointer
      if (hoverAt !== null && p === 1) {
        var hx = X(hoverAt);
        g.strokeStyle = C.ink2; g.lineWidth = 1; g.beginPath(); g.moveTo(hx, padT); g.lineTo(hx, padT + ph); g.stroke();
        [['people', d.mean.people], ['muse', d.mean.muse]].forEach(function (s) {
          g.fillStyle = C[s[0]]; g.strokeStyle = C.bg; g.lineWidth = 2;
          g.beginPath(); g.arc(hx, Y(s[1][hoverAt]), 5, 0, 7); g.fill(); g.stroke();
        });
      }
      el._geom = { X: X, padL: padL, pw: pw, W: W };
      if (!reduce && t0 !== null && p < 1) raf = requestAnimationFrame(draw);
    }

    var tip = tipFor(el);
    el.addEventListener('pointermove', function (e) {
      var gm = el._geom; if (!gm) return;
      var r = el.getBoundingClientRect(), x = e.clientX - r.left;
      var i = Math.round((x - gm.padL) / gm.pw * (n - 1));
      if (i < 0 || i >= n) { hoverAt = null; tip.hidden = true; draw(performance.now()); return; }
      hoverAt = i;
      tip.innerHTML = '<b>Stage ' + (i + 1) + ' of ' + n + '</b><span class="glow-k people">People’s: ' + d.mean.people[i].toFixed(2) +
        '</span><span class="glow-k muse">Meta AI’s: ' + d.mean.muse[i].toFixed(2) + '</span><span class="glow-note">how different the doodles look (higher = more varied)</span>';
      tip.hidden = false;
      var left = Math.min(gm.W - tip.offsetWidth - 4, Math.max(4, gm.X(i) + 14));
      tip.style.left = left + 'px'; tip.style.top = '8px';
      draw(performance.now());
    });
    el.addEventListener('pointerleave', function () { hoverAt = null; tip.hidden = true; draw(performance.now()); });
    el.setAttribute('role', 'img');
    if (!el.getAttribute('aria-label')) {
      el.setAttribute('aria-label', 'Line chart over Muse Glimmer’s ' + n + ' stages. People’s doodles stay different from each other ' +
        'throughout (' + last(d.mean.people).toFixed(2) + ' at the last stage). Meta AI’s doodles track them at first, then from stage ' +
        Math.round(d.collapse_layer) + ' fall until they look like one picture (' + last(d.mean.muse).toFixed(2) + ').');
    }
    draw(0);
    onView(el, function () { t0 = performance.now(); cancelAnimationFrame(raf); raf = requestAnimationFrame(draw); });
    return function () { draw(performance.now()); };
  }

  var KINDS = { layers: layers };
  var redraws = [];
  function render(el) {
    var kind = KINDS[el.getAttribute('data-glow')], src = el.getAttribute('data-src');
    if (!kind || el._glow) return;
    el._glow = true;
    fetch(src).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (d) {
      redraws.push(kind(el, d));
    }).catch(function () {
      el.classList.add('glow-failed');
      el.textContent = 'This chart couldn’t load. The numbers are in the text beside it.';
    });
  }
  function renderAll(root) { [].forEach.call((root || document).querySelectorAll('[data-glow]'), render); }
  var rt = 0;
  addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(function () { redraws.forEach(function (f) { f(); }); }, 120); });
  new MutationObserver(function () { redraws.forEach(function (f) { f(); }); })
    .observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  window.GlowChart = { render: render, renderAll: renderAll, rgba: rgba, colors: colors };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { renderAll(); }); else renderAll();
})();
