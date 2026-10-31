/* glowchart: charts drawn as light on the dark ground (Roger's pick, Oct 31): every mark glows, crowded stretches
   glow brighter, labels sit on the marks instead of in a legend, and the axes say what they mean in words.

   Kinds (markup, then GlowChart.renderAll() on load):
     <div class="glow-chart" data-glow="layers" data-src="/api/plato/inside/layers"></div>
       Muse Glimmer's 52 layers: per thing, how spread out Muse Image's and people's doodles look to it (faint
       threads), their means (bold, glowing) and the median layer where Muse Image's collapse to one.
   From script:
     GlowChart.swarm(el, { rows: [{ who: 'muse' | 'people', label, values, sprite: { src, cell, cols } }], you: value,
                           youImage: canvas (dark ink on white) or null, youPhoto: true for a photo (drawn as it is),
                           anchor: { row: 0, label: 'The AI’s usual chair' }, ends: ['Just like it', 'Nothing like it'] })
       One line (Roger's pick): every drawing a glowing dot placed by its distance, the anchor row's closest drawing
       pinned at the start and the visitor's drawing pinned where it lands.
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

  var redraws = [];

  // ---- swarm: one line, every drawing a glowing dot -------------------------------------------------
  var sheets = {};
  function tinted(src, color) {  // a sprite sheet of dark ink on white, as ink of `color` on nothing
    var key = src + '|' + color;
    if (!sheets[key]) sheets[key] = new Promise(function (ok) {
      var im = new Image();
      im.onload = function () { ok(tint(im, color)); };
      im.onerror = function () { ok(null); };
      im.src = src;
    });
    return sheets[key];
  }
  function tint(im, color) {
    var cv = document.createElement('canvas');
    cv.width = im.naturalWidth || im.width; cv.height = im.naturalHeight || im.height;
    var g = cv.getContext('2d');
    g.drawImage(im, 0, 0);
    var d = g.getImageData(0, 0, cv.width, cv.height), px = d.data, h = color.replace('#', '');
    var r = parseInt(h.slice(0, 2), 16), gg = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
    for (var k = 0; k < px.length; k += 4) {
      var a = 255 - (px[k] + px[k + 1] + px[k + 2]) / 3;
      px[k] = r; px[k + 1] = gg; px[k + 2] = b; px[k + 3] = Math.min(255, a * 1.5);
    }
    g.putImageData(d, 0, 0);
    return cv;
  }
  function swarm(el, o) {
    if (el._glowStop) el._glowStop();
    el.textContent = '';
    el.classList.add('glow-chart', 'glow-swarm');
    var C = colors(), stage = document.createElement('div'), t0 = null, raf = 0, alive = true, L = null;
    stage.className = 'glow-stage';
    var key = document.createElement('div');
    key.className = 'glow-key';
    o.rows.forEach(function (row) {
      key.insertAdjacentHTML('beforeend', '<span><i class="' + row.who + '"></i>' + row.label + '</span>');
    });
    key.insertAdjacentHTML('beforeend', '<span><i class="you"></i>Yours</span>');
    var ends = document.createElement('div');
    ends.className = 'glow-ends';
    ends.innerHTML = '<span>← <b></b></span><span><b></b> →</span>';
    ends.querySelectorAll('b')[0].textContent = o.ends[0];
    ends.querySelectorAll('b')[1].textContent = o.ends[1];
    el.appendChild(key); el.appendChild(stage); el.appendChild(ends);
    var tip = tipFor(el);

    var dots = [];
    o.rows.forEach(function (row) { row.values.forEach(function (v, i) { dots.push({ who: row.who, row: row, i: i, v: v }); }); });
    var anchorRow = o.rows[o.anchor.row], anchorI = anchorRow.values.indexOf(Math.min.apply(0, anchorRow.values));
    var ink = {};

    function layout() {
      var W = Math.max(260, stage.clientWidth), F = fonts(el), r = Math.max(3.2, Math.min(6, W / 200)), pad = 12;
      var vmax = Math.max(o.you, Math.max.apply(0, dots.map(function (d) { return d.v; }))) * 1.03;
      var X = function (v) { return pad + v / vmax * (W - 2 * pad); };
      var placed = [];
      dots.slice().sort(function (a, b) { return a.v - b.v; }).forEach(function (d) {
        var sx = X(d.v), best = 0;
        for (var k = 0; k < 600; k++) {
          var y = (k % 2 ? 1 : -1) * Math.ceil(k / 2) * r * 0.9, ok = true;
          for (var j = placed.length - 1; j >= 0; j--) {
            var q = placed[j]; if (sx - q.sx > 2 * r + 1.5) break;
            var dx = sx - q.sx, dy = y - q.sy; if (dx * dx + dy * dy < (2 * r + 1.5) * (2 * r + 1.5)) { ok = false; break; }
          }
          if (ok) { best = y; break; }
        }
        d.sx = sx; d.sy = best; placed.push(d);
      });
      var spread = Math.max.apply(0, placed.map(function (d) { return Math.abs(d.sy); }));
      var narrow = W < 520, thumb = Math.max(64, Math.min(132, W / 6)), lab = F.base * (narrow ? 1.05 : 1.25);
      var top = thumb + (narrow ? 2 * lab + 26 : lab + 22), mid = top + spread + r + 14;
      L = { W: W, H: mid + spread + r + 10, r: r, X: X, pad: pad, top: top, mid: mid, thumb: thumb, lab: lab, narrow: narrow, F: F,
            order: placed };
    }
    function box(g, cx, color, glow, drawInk) {
      var th = L.thumb, y = L.top - th - 8;
      g.save(); g.shadowColor = color; g.shadowBlur = glow; g.fillStyle = C.bg; g.beginPath(); g.roundRect(cx - th / 2, y, th, th, 14); g.fill(); g.restore();
      g.strokeStyle = color; g.lineWidth = 2.5; g.beginPath(); g.roundRect(cx - th / 2, y, th, th, 14); g.stroke();
      g.save(); g.beginPath(); g.roundRect(cx - th / 2 + 3, y + 3, th - 6, th - 6, 11); g.clip(); drawInk(cx - th / 2 + 5, y + 5, th - 10); g.restore();
    }
    function sprite(g, d, x, y, size) {
      var sh = ink[d.who], sp = d.row.sprite;
      if (!sh || !sp) return;
      g.drawImage(sh, (d.i % sp.cols) * sp.cell, Math.floor(d.i / sp.cols) * sp.cell, sp.cell, sp.cell, x, y, size, size);
    }
    function draw(now) {
      if (!alive || !L) return;
      C = colors();
      var cg = canvasFor(stage, L.W, L.H), g = cg.g, r = L.r, n = L.order.length;
      var el0 = reduce ? 1e9 : t0 === null ? 0 : now - t0;
      function prog(k) { return reduce ? 1 : Math.max(0, Math.min(1, (el0 - k / n * 900) / 700)); }
      g.strokeStyle = C.line; g.lineWidth = 1.5; g.beginPath(); g.moveTo(L.pad, L.mid); g.lineTo(L.W - L.pad, L.mid); g.stroke();
      g.globalCompositeOperation = 'lighter';
      L.order.forEach(function (d, k) {
        var e = ease(prog(k)); if (!e) return;
        var x = L.pad + (d.sx - L.pad) * e, y = L.mid + d.sy * e, R = r * (d.who === 'muse' ? 8 : 7.5);
        var gr = g.createRadialGradient(x, y, 0, x, y, R);
        gr.addColorStop(0, rgba(C[d.who], d.who === 'muse' ? 0.30 : 0.17)); gr.addColorStop(1, rgba(C[d.who], 0));
        g.fillStyle = gr; g.beginPath(); g.arc(x, y, R, 0, 7); g.fill();
      });
      g.globalCompositeOperation = 'source-over';
      L.order.forEach(function (d, k) {
        var e = ease(prog(k)); if (!e) return;
        d.hx = L.pad + (d.sx - L.pad) * e; d.hy = L.mid + d.sy * e;
        g.save(); g.shadowColor = C[d.who]; g.shadowBlur = 10; g.globalAlpha = e; g.fillStyle = C[d.who];
        g.beginPath(); g.arc(d.hx, d.hy, d.who === 'muse' ? r + 0.5 : r, 0, 7); g.fill(); g.restore();
      });
      // the anchor's drawing at the start of the line, and yours where it lands
      var ax = L.pad + L.thumb / 2, labFont = L.F.label(L.lab / L.F.base, 700);
      box(g, ax, C[anchorRow.who], 18, function (x, y, s) { sprite(g, { who: anchorRow.who, row: anchorRow, i: anchorI }, x, y, s); });
      var words = o.anchor.label.split(' ');
      if (L.narrow) {
        var half = Math.ceil(words.length / 2);
        text(g, words.slice(0, half).join(' '), ax - L.thumb / 2, L.top - L.thumb - 8 - L.lab * 1.9, { font: labFont }, C);
        text(g, words.slice(half).join(' '), ax - L.thumb / 2, L.top - L.thumb - 8 - L.lab * 0.75, { font: labFont }, C);
      } else {
        text(g, o.anchor.label, ax + L.thumb / 2 + 14, L.top - L.thumb / 2 - 8, { font: labFont }, C);
      }
      var ty = reduce ? 1 : ease(Math.max(0, Math.min(1, (el0 - 1300) / 600)));
      if (ty > 0) {
        var ux = L.X(o.you), bx = Math.min(L.W - L.thumb / 2 - 4, Math.max(L.thumb * 1.5 + 24, ux));
        g.globalAlpha = ty;
        g.strokeStyle = C.you; g.lineWidth = 2.5; g.beginPath(); g.moveTo(ux, L.mid); g.lineTo(ux, L.top - 8); g.stroke();
        if (Math.abs(bx - ux) > 1) { g.beginPath(); g.moveTo(ux, L.top - 8); g.lineTo(bx, L.top - 8); g.stroke(); }
        var pulse = reduce ? 0 : (now / 1500) % 1;
        g.beginPath(); g.arc(ux, L.mid, r + 4 + pulse * 22, 0, 7); g.strokeStyle = rgba(C.you, 0.6 * (1 - pulse)); g.lineWidth = 2; g.stroke();
        g.save(); g.shadowColor = C.you; g.shadowBlur = 16; g.fillStyle = C.you; g.beginPath(); g.arc(ux, L.mid, r + 4, 0, 7); g.fill(); g.restore();
        box(g, bx, C.you, 22, function (x, y, s) {
          if (ink.you) { var k = Math.min(s / ink.you.width, s / ink.you.height); g.drawImage(ink.you, x + (s - ink.you.width * k) / 2, y + (s - ink.you.height * k) / 2, ink.you.width * k, ink.you.height * k); }
        });
        if (L.narrow) text(g, 'Yours', bx, L.top - L.thumb - 8 - L.lab * 0.75, { font: labFont, align: 'center' }, C);
        else if (bx - L.thumb / 2 - 14 - g.measureText('Yours').width > ax + L.thumb / 2 + 14 + g.measureText(o.anchor.label).width + 20)
          text(g, 'Yours', bx - L.thumb / 2 - 14, L.top - L.thumb / 2 - 8, { font: labFont, align: 'right' }, C);
        else text(g, 'Yours', bx, L.top - L.thumb - 8 - L.lab * 0.75, { font: labFont, align: 'center' }, C);
        g.globalAlpha = 1;
      }
      if (!reduce && t0 !== null) raf = requestAnimationFrame(draw);
    }
    // the drawings, in the chart's colours
    var jobs = o.rows.map(function (row) { return row.sprite ? tinted(row.sprite.src, C[row.who]).then(function (cv) { ink[row.who] = cv; }) : null; });
    if (o.youImage) {
      ink.you = o.youPhoto ? o.youImage : null;
      if (!o.youPhoto) jobs.push(Promise.resolve().then(function () { ink.you = tint(o.youImage, C.you); }));
    }
    layout();
    draw(0);
    Promise.all(jobs).then(function () { draw(performance.now()); });
    onView(el, function () { t0 = performance.now(); cancelAnimationFrame(raf); raf = requestAnimationFrame(draw); });
    // the drawing under the pointer, bigger
    var tcv = document.createElement('canvas');
    stage.addEventListener('pointermove', function (e) {
      if (!L) return;
      var rc = stage.getBoundingClientRect(), mx = e.clientX - rc.left, my = e.clientY - rc.top, best = null, bd = 144;
      L.order.forEach(function (d) { var dx = d.hx - mx, dy = d.hy - my, q = dx * dx + dy * dy; if (q < bd) { bd = q; best = d; } });
      if (!best) { tip.hidden = true; return; }
      tip.innerHTML = '';
      if (ink[best.who] && best.row.sprite) {
        tcv.width = tcv.height = 96; var tg = tcv.getContext('2d'); tg.clearRect(0, 0, 96, 96);
        sprite(tg, best, 0, 0, 96); tip.appendChild(tcv);
      }
      var b = document.createElement('b'); b.textContent = best.who === 'muse' ? 'Meta’s AI (Muse Image)' : 'A person’s drawing';
      tip.appendChild(b);
      tip.hidden = false;
      tip.style.left = Math.min(L.W - tip.offsetWidth, Math.max(0, best.hx + 14)) + 'px';
      tip.style.top = Math.max(0, best.hy + stage.offsetTop - tip.offsetHeight - 10) + 'px';
    });
    stage.addEventListener('pointerleave', function () { tip.hidden = true; });
    el.setAttribute('role', 'img');
    el._glowStop = function () { alive = false; cancelAnimationFrame(raf); };
    var redraw = function () { if (!alive) return; C = colors(); layout(); jobs = []; o.rows.forEach(function (row) {
      if (row.sprite) tinted(row.sprite.src, C[row.who]).then(function (cv) { ink[row.who] = cv; draw(performance.now()); }); });
      if (o.youImage && !o.youPhoto) ink.you = tint(o.youImage, C.you); draw(performance.now()); };
    redraws.push(redraw);
    return redraw;
  }

  var KINDS = { layers: layers };
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
  window.GlowChart = { render: render, renderAll: renderAll, swarm: swarm, rgba: rgba, colors: colors };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { renderAll(); }); else renderAll();
})();
