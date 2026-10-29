/* statviz: a headline number drawn as a small graphic, not just text.

   Usage. Link /static/css/statviz.css and /static/js/statviz.js, then write an element with data-sv set to one of
   four kinds; on load every [data-sv] element is drawn (call StatViz.renderAll(root) after adding new ones):
     <div data-sv="dots"   data-k="34" data-n="35" data-label="things Muse Image drew more alike than people"></div>
     <div data-sv="spread" data-a="0.09" data-b="0.54" data-a-label="Muse Image" data-b-label="People"
          data-label="as spread out: people’s doodles inside the model"></div>
     <div data-sv="layers" data-at="36" data-n="52" data-label="the layer where the model makes them one"></div>
     <div data-sv="bars"   data-values="0.13,0.36" data-labels="Muse Image,People" data-label="spread of 16 chairs"></div>
   dots is k of n as a dot grid (data-cols sets the columns); spread is two clusters of data-points dots (16) whose
   radii follow a and b, and its number is b ÷ a ("6×"); layers is an n-segment bar with a marker at layer at
   (data-mode="one" marks that layer only, the default fills it and everything after); bars are horizontal bars on
   one scale (data-max, data-digits, data-suffix such as "%"). The big number is worked out from the data; data-value and data-unit replace
   it ("34" and " of 35"), and data-value="" hides it. data-label is the caption under the graphic, data-alt the
   screen-reader sentence (one is built from the data otherwise). Colours are data-tone / data-a-tone / data-b-tone /
   data-tones: blue (Muse Image), orange (people), ink, green or muted. data-size="s" or "l" scales it, and
   class="sv-row" puts the number beside the graphic. From script: StatViz.render(el, opts) draws one element
   (opts override its data-*), StatViz.html(kind, opts) returns the markup as a string (it needs no DOM), and
   StatViz.kinds lists the kinds. The look lives in statviz.css, in the site's colour tokens only.

   Animate on view. A drawn graphic waits (class sv-wait, its entrance paused) until it scrolls into view, then plays
   (sv-play): the number counts up, a dot grid fills dot by dot, the two clusters drift in from one wide cloud into
   their tight and loose shapes, the layer marker slides from layer 1 to its layer and bars grow. render() does this
   for every graphic it draws; StatViz.watch(el) or StatViz.watchAll(root) does it for statviz markup drawn some other
   way (FirstLook.render calls it). The markup and its final values are the same either way: with
   prefers-reduced-motion, without IntersectionObserver or in print, the graphic is simply drawn, already complete.
*/
(function (root) {
  'use strict';

  var KINDS = ['dots', 'spread', 'layers', 'bars'];
  var TONES = ['blue', 'orange', 'ink', 'green', 'muted'];

  // ---------- small helpers (no DOM) ----------
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function num(v, fallback) { var x = parseFloat(v); return isFinite(x) ? x : fallback; }
  function int(v, fallback) { var x = parseInt(v, 10); return isFinite(x) ? x : fallback; }
  function list(v) {
    if (Array.isArray(v)) return v;
    return v == null || v === '' ? [] : String(v).split(',').map(function (s) { return s.trim(); });
  }
  function tone(t, fallback) { return TONES.indexOf(t) >= 0 ? t : fallback; }
  function r1(x) { return Math.round(x * 10) / 10; }
  function times(x) { return (x >= 10 ? String(Math.round(x)) : String(r1(x))) + '×'; }
  function fmt(x, digits) { return digits == null ? String(x) : Number(x).toFixed(digits); }
  function delay(i, n) { return ' style="--d:' + Math.round(i * Math.min(28, 900 / Math.max(1, n))) + 'ms"'; }  // the stagger, capped
  // A small seeded generator, so a cluster looks the same on every load and in every test.
  function rng(seed) {
    var s = seed >>> 0;
    return function () {
      s = (s + 0x6D2B79F5) >>> 0;
      var t = s;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // ---------- the four graphics: each returns {value, unit, alt, plot} ----------

  function dots(o) {
    var n = Math.max(1, Math.min(400, int(o.n, 10))), k = Math.max(0, Math.min(n, int(o.k, 0)));
    var cols = int(o.cols, 0) || (n <= 12 ? n : n === 100 ? 10 : Math.ceil(Math.sqrt(n * 2.2)));
    var rows = Math.ceil(n / cols), t = tone(o.tone, 'blue'), cell = 10, out = [];
    for (var i = 0; i < n; i++) {
      var cx = (i % cols) * cell + cell / 2, cy = Math.floor(i / cols) * cell + cell / 2;
      out.push(i < k
        ? '<circle class="sv-on sv-' + t + '" cx="' + cx + '" cy="' + cy + '" r="3.7"' + delay(i, k) + '/>'
        : '<circle class="sv-off" cx="' + cx + '" cy="' + cy + '" r="3.1"/>');
    }
    var alt = o.alt || (k + ' of ' + n + (o.label ? ' ' + o.label : ''));
    return {
      value: String(k), unit: ' of ' + n, alt: alt,
      plot: '<svg class="sv-svg" viewBox="0 0 ' + cols * cell + ' ' + rows * cell + '" style="--cols:' + cols + '" ' +
        'role="img" aria-label="' + esc(alt) + '"><title>' + esc(alt) + '</title>' + out.join('') + '</svg>'
    };
  }

  // Each dot also carries where its entrance starts (--dx, --dy): one wide cloud, the same for both clusters, so on
  // view Muse Image's dots visibly collapse into a knot while people's stay loose (statviz.css, sv-drift).
  function cluster(spread, max, seed, t, count, label) {
    var R = 44 * Math.max(0.06, spread / max), rand = rng(seed), from = rng(3), pts = [];
    for (var i = 0; i < count; i++) {
      var a = rand() * Math.PI * 2, d = R * Math.sqrt(0.08 + 0.92 * rand());
      var x = 50 + d * Math.cos(a), y = 50 + d * Math.sin(a);
      var fa = from() * Math.PI * 2, fd = 44 * Math.sqrt(0.15 + 0.85 * from());
      pts.push('<circle class="sv-on sv-' + t + '" cx="' + r1(x) + '" cy="' + r1(y) + '" r="3.4" style="--d:' + i * 22 + 'ms;--dx:' +
        r1(50 + fd * Math.cos(fa) - x) + 'px;--dy:' + r1(50 + fd * Math.sin(fa) - y) + 'px"/>');
    }
    return '<svg class="sv-svg" viewBox="0 0 100 100" aria-hidden="true">' +
      '<circle class="sv-ring" cx="50" cy="50" r="' + r1(R + 4) + '"/>' + pts.join('') + '</svg>';
  }
  function spread(o) {
    var a = num(o.a, 0.1), b = num(o.b, 0.5), max = Math.max(a, b) || 1, count = Math.max(3, Math.min(60, int(o.points, 16)));
    var ta = tone(o.aTone, 'blue'), tb = tone(o.bTone, 'orange');
    var la = o.aLabel || 'Muse Image', lb = o.bLabel || 'People', digits = o.digits == null ? 2 : int(o.digits, 2);
    var ratio = a > 0 ? b / a : 0;
    var alt = o.alt || (lb + ' ' + fmt(b, digits) + ', ' + la + ' ' + fmt(a, digits) + ': ' + times(ratio) +
      (b >= a ? ' as spread out' : ' as tight') + (o.label ? '. ' + o.label : ''));
    function side(v, t, lbl, seed) {
      return '<div class="sv-side">' + cluster(v, max, seed, t, count) +
        '<span class="sv-key"><i class="sv-sw sv-' + t + '" aria-hidden="true"></i>' + esc(lbl) +
        ' <b>' + esc(fmt(v, digits)) + '</b></span></div>';
    }
    return {
      value: ratio ? times(ratio) : '', unit: '', alt: alt,
      plot: '<div class="sv-pair" role="img" aria-label="' + esc(alt) + '" title="' + esc(alt) + '">' +
        side(a, ta, la, 7) + side(b, tb, lb, 11) + '</div>'
    };
  }

  function layers(o) {
    var n = Math.max(2, Math.min(400, int(o.n, 52))), at = Math.max(1, Math.min(n, int(o.at, 1)));
    var t = tone(o.tone, 'blue'), one = o.mode === 'one', w = 6, gap = 2, step = w + gap, top = 14, h = 26;
    var W = n * step - gap, segs = [];
    for (var i = 1; i <= n; i++) {
      var on = one ? i === at : i >= at;
      segs.push('<rect class="' + (on ? 'sv-on sv-' + t : 'sv-off-fill') + '" x="' + (i - 1) * step + '" y="' + top +
        '" width="' + w + '" height="' + h + '" rx="1.5"' + (on ? delay(i - at, n - at + 1) : '') + '/>');
    }
    var mx = (at - 1) * step + w / 2;
    var alt = o.alt || ('Layer ' + at + ' of ' + n + (o.label ? ': ' + o.label : ''));
    return {
      value: String(at), unit: ' of ' + n, alt: alt,
      plot: '<div class="sv-lay" style="--n:' + n + '"><svg class="sv-svg" viewBox="-4 0 ' + (W + 8) + ' ' + (top + h) +
        '" role="img" aria-label="' + esc(alt) + '"><title>' + esc(alt) + '</title>' + segs.join('') +
        '<path class="sv-mark" d="M' + (mx - 5) + ' 3h10l-5 8z" style="--mx:' + (1 - at) * step + 'px"/></svg>' +
        '<span class="sv-ticks" aria-hidden="true"><span>1</span><span>' + n + '</span></span></div>'
    };
  }

  function bars(o) {
    var values = list(o.values).map(function (v) { return num(v, 0); });
    var labels = list(o.labels), tones = list(o.tones), digits = o.digits == null ? null : int(o.digits, 2);
    var max = num(o.max, 0) || Math.max.apply(null, values.concat([0])) || 1, rows = [];
    var dflt = ['blue', 'orange', 'ink', 'green', 'muted'];
    values.forEach(function (v, i) {
      var pct = Math.max(0, Math.min(100, 100 * v / max));
      rows.push('<div class="sv-bar"><span class="sv-bar-l">' + esc(labels[i] || '') + '</span>' +
        '<span class="sv-track"><i class="sv-fill sv-' + tone(tones[i], dflt[i % dflt.length]) + '" style="width:' + r1(pct) +
        '%;--d:' + i * 120 + 'ms"></i></span><span class="sv-bar-v">' + esc(fmt(v, digits)) +
        (o.suffix ? '<span class="sv-bar-u">' + esc(o.suffix) + '</span>' : '') + '</span></div>');
    });
    var alt = o.alt || (values.map(function (v, i) { return (labels[i] || 'Bar ' + (i + 1)) + ' ' + fmt(v, digits) + (o.suffix || ''); }).join(', ') +
      (o.label ? ': ' + o.label : ''));
    // a comparison has no single headline number: each row carries its own value and units
    return { value: '', unit: '', alt: alt,
      plot: '<div class="sv-bars" role="img" aria-label="' + esc(alt) + '">' + rows.join('') + '</div>' };
  }

  var MAKERS = { dots: dots, spread: spread, layers: layers, bars: bars };

  // The whole graphic as a string: the number, the plot and the caption.
  function html(kind, o) {
    o = o || {};
    var make = MAKERS[kind];
    if (!make) throw new Error('statviz: unknown kind "' + kind + '" (one of ' + KINDS.join(', ') + ')');
    var g = make(o);
    var value = o.value != null ? String(o.value) : g.value, unit = o.unit != null ? String(o.unit) : (o.value != null ? '' : g.unit);
    var head = value ? '<p class="sv-val" aria-hidden="true"><span class="sv-num">' + esc(value) + '</span>' +
      (unit ? '<span class="sv-unit">' + esc(unit) + '</span>' : '') + '</p>' : '';
    var cap = o.label && !o.nocap ? '<p class="sv-cap">' + esc(o.label) + '</p>' : '';
    return cap + head + '<div class="sv-plot">' + g.plot + '</div>' + (o.take ? '<p class="sv-take">' + esc(o.take) + '</p>' : '');
  }

  // ---------- the DOM side ----------
  function optsFrom(el) {
    var d = el.dataset || {}, o = {};
    ['n', 'k', 'cols', 'tone', 'a', 'b', 'aLabel', 'bLabel', 'aTone', 'bTone', 'points', 'at', 'mode', 'values', 'labels',
      'tones', 'max', 'digits', 'suffix', 'value', 'unit', 'label', 'alt', 'nocap', 'take'].forEach(function (key) {
      if (d[key] != null) o[key] = d[key];
    });
    return o;
  }
  function render(el, opts) {
    var kind = (opts && opts.kind) || el.getAttribute('data-sv');
    var o = Object.assign(optsFrom(el), opts || {});
    el.innerHTML = html(kind, o);
    el.classList.add('sv', 'sv-' + kind);
    var size = el.getAttribute('data-size');
    if (size) el.classList.add('sv-' + size);
    el.setAttribute('data-sv-done', '1');
    watch(el);
    return el;
  }

  // ---------- animate on view ----------
  // A graphic waits (sv-wait: statviz.css holds its entrance at the first frame) until it is in view, then plays. Inside
  // a block the site's motion layer hasn't revealed yet (motion.js: .mo-r without .mo-in), it waits for that block's
  // "mo:in" so it plays where it can be seen. Nothing is hidden for good: the failsafe plays it after a few seconds.
  var io = null;
  function moving() {
    try {
      return !!(root.IntersectionObserver && root.matchMedia && !root.matchMedia('(prefers-reduced-motion: reduce)').matches);
    } catch (e) { return false; }
  }
  function play(el) {
    if (!el.classList.contains('sv-wait')) return;
    var held = el.closest && el.closest('.mo-r:not(.mo-in)');
    if (held && !el.__svHeld) {
      el.__svHeld = true;
      var go = function () { setTimeout(function () { play(el); }, 120); };
      held.addEventListener('mo:in', go, { once: true });
      setTimeout(go, 2500);
      return;
    }
    el.classList.remove('sv-wait');
    el.classList.add('sv-play');
    var nums = el.querySelectorAll('.sv-num, .sv-key b, .sv-bar-v');
    for (var i = 0; i < nums.length; i++) countUp(nums[i], 1600);
  }
  function watch(el) {
    if (!el || el.__svWatched || !moving()) return el;
    el.__svWatched = true;
    el.classList.add('sv-wait');
    if (!io) {
      io = new root.IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) { io.unobserve(e.target); play(e.target); }
        });
      }, { rootMargin: '0px 0px -10% 0px', threshold: 0.25 });
    }
    io.observe(el);
    return el;
  }
  function watchAll(scope) {
    var els = (scope || root.document).querySelectorAll('.sv');
    for (var i = 0; i < els.length; i++) watch(els[i]);
    return els.length;
  }
  // Every number in a label's own text counts up from 0 to its value, keeping its decimals and the text around it
  // ("2.7×", "33% → 4%"; child elements are left alone). The label keeps its final width meanwhile, so nothing beside
  // it moves, and its last frame is its own text again.
  var NUM = /\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?/g;
  function countUp(node, ms) {
    var jobs = [];
    for (var c = node.firstChild; c; c = c.nextSibling) {
      if (c.nodeType !== 3) continue;
      var text = c.nodeValue, parts = [], last = 0, m;
      NUM.lastIndex = 0;
      while ((m = NUM.exec(text))) { parts.push(text.slice(last, m.index), m[0]); last = m.index + m[0].length; }
      if (parts.length) jobs.push({ node: c, text: text, parts: parts.concat(text.slice(last)) });
    }
    if (!jobs.length || !root.requestAnimationFrame || node.__svCounting) return;
    node.__svCounting = true;
    node.style.minWidth = node.getBoundingClientRect().width + 'px';
    if (root.getComputedStyle(node).display === 'inline') node.style.display = 'inline-block';
    var t0 = null;
    function frame(t) {
      if (t0 == null) t0 = t;
      var k = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - k, 3);
      jobs.forEach(function (j) {
        j.node.nodeValue = k >= 1 ? j.text : j.parts.map(function (p, i) {
          if (i % 2 === 0) return p;
          var v = parseFloat(p.replace(/,/g, '')), dec = (p.split('.')[1] || '').length, x = v * e;
          return p.indexOf(',') >= 0 ? Math.round(x).toLocaleString('en-US') : x.toFixed(dec);
        }).join('');
      });
      if (k < 1) return root.requestAnimationFrame(frame);
      node.style.minWidth = node.style.display = '';
      node.__svCounting = false;
    }
    root.requestAnimationFrame(frame);
  }
  function renderAll(scope) {
    var els = (scope || document).querySelectorAll('[data-sv]:not([data-sv-done])');
    Array.prototype.forEach.call(els, function (el) {
      try { render(el); } catch (e) { if (root.console) root.console.warn(e.message); }
    });
    return els.length;
  }

  var api = { html: html, render: render, renderAll: renderAll, watch: watch, watchAll: watchAll, countUp: countUp,
    kinds: KINDS.slice(), tones: TONES.slice() };
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root && root.document) {
    root.StatViz = api;
    if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', function () { renderAll(); });
    else renderAll();
  }
})(typeof window !== 'undefined' ? window : this);
