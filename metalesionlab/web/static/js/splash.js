/* Plato's Chair's opening animation, "the cave", on the landing page, in three styles.

   It opens on the question, in the dark with only the fire: "If Plato were alive today…" and "What would he ask
   AI?" light up letter by letter like embers, cool, then turn into shadows thrown on the wall away from the fire.
   Then firelight and drifting shadows, with Republic 515c. The chair's shadow slows to the centre and comes
   into focus, the wall turns to paper, and the chair comes closer while flipping through the 16 kinds
   Muse Spark named (drawn by Muse Image) and people's own chairs, with Republic 596a. It ends on the
   geometric "Form" chair, which draws itself and glides into the header's brand slot to become the logo,
   while the page fades in under it.

   Styles (?splash=1&style=a|b|c; DEFAULT_STYLE below plays when there is no style param):
     a  Readable: the same sequence; every caption stays up for its reading time and the visuals wait for it.
     b  Words first: each caption alone, large and centred, held for its reading time, then it shrinks to
        the top while the scene plays beneath it.
     c  Short and bold: three short lines in big type, held 2.5-3 s each (the long quotes are dropped, not cut).
   Reading time = max(2.5 s, 0.4 s per word + 1.2 s). window.PCSplash.log lists every caption's on-screen time.

   When it plays is decided by a small script in the page's <head>, before the first paint: once per browser
   session (sessionStorage "pc-splash-seen"), never with reduced motion (Replay then shows a still page with
   the text), during the guided tour, on a deep link (#...) or with ?nosplash=1; ?splash=1 plays it again.
   Skip it with the Skip button, Esc or a click. It never shows Muse Image's own chairs (the 16 alike ones),
   so the drawing that follows stays blind. The Form chair is the header's own logo (web/site.py FORM_CHAIR). */
(function () {
  'use strict';
  var root = document.documentElement;
  if (!root.classList.contains('splash-on')) return;
  try { window.sessionStorage.setItem('pc-splash-seen', '1'); } catch (e) { /* storage off: the head script won't play it */ }

  var DEFAULT_STYLE = 'a';  // the style that plays without ?style= (a, b or c): the one place to change it
  var STYLE = (/[?&]style=([abc])(&|$)/.exec(location.search) || [0, DEFAULT_STYLE])[1];
  var STATIC = root.classList.contains('splash-static');  // reduced motion: a still page with the text

  var IMG = '/static/img/splash/';
  var SHADOWS = ['umbrella', 'cup', 'cat', 'bicycle', 'tree', 'house', 'key'];
  var N_KINDS = 16, N_PEOPLE = 8;
  var Q515 = '“To them, I said, the truth would be literally nothing but the shadows of the images.”' +
    '<cite>Plato, Republic 515c · Jowett</cite>';
  var Q596 = '“Whenever a number of individuals have a common name, we assume them to have also a corresponding idea or form.”' +
    '<cite>Plato, Republic 596a · Jowett</cite>';
  var T1 = 'If Plato were alive today…', T2 = 'What would he ask AI?';  // the opening title
  var ONE = 'Plato’s Chair';  // the closing caption: the site's name, under the Form chair
  var C1 = 'Plato said every chair is a copy of one ideal chair.', C2 = 'We only ever see the shadows.', C3 = 'What would Plato ask an AI?';
  var NAVY = '#141a26', WHITE = '#F9FAFB', ORANGE = '#C2410C';
  var MAX_MS = { a: 42000, b: 46000, c: 30000 }[STYLE];  // whatever happens, the page is back by then

  var raf = 0, run = 0, done = false, anims = [], timers = [], log = [], cur = null;
  var stage, actor, shadowEl, caption, title, skipBtn, form, frames = [], shadowPic, L = {};

  // Reading time of a caption (the citation line is not counted).
  function words(html) { var t = html.replace(/<cite>.*?<\/cite>/g, '').replace(/<[^>]+>/g, ' ').trim(); return t ? t.split(/\s+/).length : 0; }
  function readMs(html) { return Math.max(2500, 400 * words(html) + 1200); }

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  // A line of the opening title: one span per letter (--i staggers them), words kept whole so a line breaks only
  // between words.
  function embers(text, cls) {
    var line = el('span', cls), i = 0;
    text.split(' ').forEach(function (w, k) {
      if (k) line.appendChild(document.createTextNode(' '));
      var word = line.appendChild(el('span', 'w'));
      Array.from(w).forEach(function (c) { var ch = word.appendChild(el('span', 'ch')); ch.textContent = c; ch.style.setProperty('--i', i++); });
    });
    return line;
  }
  function img(src) { var i = new Image(); i.src = src; i.alt = ''; i.decoding = 'async'; return i; }
  function later(fn, ms) { timers.push(setTimeout(fn, ms)); }
  function wait(ms, id) {
    return new Promise(function (resolve, reject) {
      later(function () { if (id === run && !done) resolve(); else reject(new Error('stopped')); }, ms);
    });
  }
  function anim(target, frames_, opts) {
    var a = target.animate(frames_, Object.assign({ fill: 'forwards' }, opts));
    anims.push(a);
    return a;
  }

  // --- captions ---------------------------------------------------------------------------------
  // mode: '' (bottom, small), 'big' (large, centred), 'high' (large, near the top). veil: dim the scene behind it.
  function say(html, mode, veil) {
    unsay();
    caption.className = 'sp-caption' + (mode ? ' ' + mode : '') + (/<cite>/.test(html || '') ? ' q' : '');
    stage.classList.toggle('veil', !!veil);
    if (!html) return;
    later(function () {
      caption.innerHTML = html;
      caption.classList.add('on');
      cur = { text: caption.textContent, need: readMs(html), shown: performance.now() };
      log.push(cur);
    }, 250);
  }
  function endLog() { if (cur && cur.hidden == null) { cur.hidden = performance.now(); cur.held = Math.round(cur.hidden - cur.shown); } cur = null; }
  function unsay() { caption.classList.remove('on'); endLog(); }
  // Shows a caption and resolves once it has been fully up for `ms` (its reading time unless given).
  function hold(id, html, mode, veil, ms) { say(html, mode, veil); return wait(300 + (ms || readMs(html)), id); }
  // Words-first: the held caption shrinks to the top and the scene plays beneath it.
  function demote() { endLog(); caption.classList.remove('big', 'high'); caption.classList.add('top'); stage.classList.remove('veil'); }

  // The fire is at the front right, between us and the wall. An object at xo (px) crossing in front of it casts a
  // shadow that leans away from the fire (skew = -atan((xo - lightX) / depth), upright right under it), is bigger
  // and softer the nearer the fire, and moves faster than its object: x = lightX + (xo - lightX) * MAG.
  function projectShadow(xo, lightX, depth, W) {
    var dx = xo - lightX, MAG = 1.25;
    var skew = Math.max(-25, Math.min(25, -Math.atan(dx / depth) * 180 / Math.PI));
    var near = 1 - Math.min(1, Math.abs(dx) / W);  // 1 beside the fire, 0 across the wall
    return { x: lightX + dx * MAG, skew: skew, scale: 0.85 + 0.35 * near, blur: 1.5 + 2.5 * near, near: near };
  }

  // --- the stage --------------------------------------------------------------------------------
  function build() {
    stage = el('div', 'splash s-' + STYLE);
    var scene = el('div', 'sp-scene');
    scene.setAttribute('aria-hidden', 'true');
    scene.appendChild(el('div', 'sp-bg sp-wall'));
    scene.appendChild(el('div', 'sp-bg sp-paper'));
    scene.appendChild(el('div', 'sp-bg sp-fire'));
    scene.appendChild(el('div', 'sp-bg sp-fire b'));
    scene.appendChild(el('div', 'sp-lamp'));
    shadowEl = scene.appendChild(el('div', 'sp-shadows'));
    actor = scene.appendChild(el('div', 'sp-actor'));
    shadowPic = actor.appendChild(img(IMG + 'shadow_chair.webp'));
    var seq = [], k = 1, p = 1;
    while (k <= N_KINDS || p <= N_PEOPLE) {  // two named kinds, then one person's chair
      if (k <= N_KINDS) seq.push('kind_' + (k < 10 ? '0' : '') + k++ + '.webp');
      if (k <= N_KINDS) seq.push('kind_' + (k < 10 ? '0' : '') + k++ + '.webp');
      if (p <= N_PEOPLE) seq.push('people_' + p++ + '.webp');
    }
    frames = seq.map(function (name) { return actor.appendChild(img(IMG + name)); });
    var logo = document.querySelector('.site-head .brand-logo');
    if (logo) {
      form = logo.cloneNode(true);
      actor.appendChild(form);
    }
    scene.appendChild(el('div', 'sp-bg sp-veil'));
    caption = scene.appendChild(el('p', 'sp-caption'));
    title = scene.appendChild(el('div', 'sp-title'));
    [[T1, 'ln l1'], [T2, 'ln l2']].forEach(function (t) { title.appendChild(embers(t[0], t[1])); });
    stage.appendChild(scene);
    skipBtn = el('button', 'sp-skip', 'Skip intro <span aria-hidden="true">→</span>');
    skipBtn.type = 'button';
    skipBtn.setAttribute('aria-label', 'Skip the opening animation (Esc)');
    skipBtn.addEventListener('click', function (e) { e.stopPropagation(); finish(); });
    stage.appendChild(skipBtn);
    stage.addEventListener('click', function () { finish(); });
    document.body.appendChild(stage);
  }

  // Reduced motion: no animation at all; the words on one still page, and a button to go on.
  function buildStatic() {
    stage = el('div', 'splash static');
    var box = el('div', 'sp-still');
    box.appendChild(el('p', 'sp-still-h', 'Plato’s Chair'));
    box.appendChild(el('p', 'sp-still-big', T1 + '<br>' + T2));
    [Q515, Q596].forEach(function (q) { box.appendChild(el('p', 'sp-still-q', q)); });
    skipBtn = el('button', 'sp-continue', 'Continue to the page <span aria-hidden="true">→</span>');
    skipBtn.type = 'button';
    skipBtn.addEventListener('click', function () { finish(); });
    box.appendChild(skipBtn);
    stage.appendChild(box);
    document.body.appendChild(stage);
    skipBtn.focus({ preventScroll: true });
  }

  // The chair's size and place follow the stage's height, so it never grows into the caption.
  function layout() {
    var W = window.innerWidth, H = window.innerHeight, portrait = W < H;
    L.W = W; L.H = H; L.lightX = W * 0.92; L.depth = W * 0.6;
    L.base = Math.round(portrait ? Math.min(W * 0.42, H * 0.3) : Math.min(W * 0.22, H * 0.34));
    L.x = W / 2 - L.base / 2;
    L.y = H * 0.42 - L.base / 2;
    L.smax = Math.min(1.5, (H * 0.62) / L.base);
    actor.style.width = actor.style.height = L.base + 'px';
    actor.style.left = L.x + 'px';
    actor.style.top = L.y + 'px';
    stage.style.setProperty('--sp-shadow', (portrait ? 22 : 15) + '%');
  }

  // Where the logo sits once the page has settled. The page only fades in (opacity, no transforms), and
  // this is measured before the fade starts, so it is the logo's final place, not a mid-transition one.
  function logoTarget() {
    var logo = document.querySelector('.site-head .brand-logo');
    if (!logo) return null;
    var r = logo.getBoundingClientRect();
    if (!r.width) return null;
    return { dx: r.left + r.width / 2 - (L.x + L.base / 2), dy: r.top + r.height / 2 - (L.y + L.base / 2), s: r.height / L.base };
  }

  function show(i) {
    frames.forEach(function (f, j) { f.classList.toggle('on', j === i); });
  }

  // --- the scenes (each style strings them together with its own captions) ----------------------
  // The opening title, in the dark with only the fire: each line lights up letter by letter like embers and cools;
  // after its reading time the letters go dark and their shadows stretch away from the fire (up and to the left),
  // while onCast starts the cave behind them. Resolves once the title has gone.
  function opening(id, onCast) {
    var lines = title.children, both = T1 + ' ' + T2;
    stage.classList.add('dark');
    return wait(350, id).then(function () {
      lines[0].classList.add('on');
      cur = { text: both, need: readMs(both), shown: performance.now() };
      log.push(cur);
      return wait(1500, id);
    }).then(function () {
      lines[1].classList.add('on');
      return wait(readMs(both) - 1500, id);
    }).then(function () {
      endLog();
      title.classList.add('cast');
      stage.classList.remove('dark');
      onCast();
      return wait(1300, id);
    }).then(function () { title.classList.add('gone'); });
  }
  function cave(slide) {  // firelight, drifting shadows, the chair's shadow sliding in
    var W = L.W, H = L.H;
    var items = SHADOWS.map(function (name, i) {
      var s = img(IMG + 'shadow_' + name + '.webp');
      shadowEl.appendChild(s);
      var dir = i % 2 ? -1 : 1;
      return { el: s, scale: 0.65 + (i % 3) * 0.22, y: H * (0.14 + (i * 0.37 % 0.5)), dir: dir, period: 4500 + i * 520, delay: i * 320 - 400, blur: -1 };
    });
    var t0 = performance.now();
    (function tick(now) {  // one loop: each object's place gives its shadow's lean, size, softness and place
      if (done || stage.classList.contains('lit')) return;
      var w = shadowEl.firstChild ? shadowEl.firstChild.offsetWidth || W * 0.15 : W * 0.15;
      items.forEach(function (o) {
        var f = (((now - t0 - o.delay) / o.period) % 1 + 1) % 1;
        var xo = (o.dir > 0 ? -0.25 + 1.3 * f : 1.05 - 1.3 * f) * W;  // the object's centre, on its way across
        var p = projectShadow(xo, L.lightX, L.depth, W);
        var flick = 1 + 0.015 * Math.sin(now / 90 + o.period) + 0.01 * Math.sin(now / 37 + o.delay);
        var sc = o.scale * p.scale * flick;
        o.el.style.transform = 'translate(' + (p.x - w / 2) + 'px,' + (o.y + (o.dir > 0 ? 10 : -10) * f) + 'px) skewX(' + p.skew.toFixed(2) + 'deg) scale(' + sc.toFixed(3) + ')';
        var b = Math.round(p.blur * 2) / 2;
        if (b !== o.blur) { o.blur = b; o.el.style.filter = 'blur(' + b + 'px)'; }
        o.el.style.opacity = (0.5 + 0.08 * p.near + 0.02 * Math.sin(now / 53 + o.delay)).toFixed(3);
      });
      raf = requestAnimationFrame(tick);
    })(t0);
    shadowPic.classList.add('on');
    shadowPic.style.filter = 'blur(3px)';
    var lean = projectShadow(W / 2, L.lightX, L.depth, W).skew.toFixed(1);  // the chair stops at the centre, leaning away from the fire
    L.lean = lean;
    anim(actor, [{ transform: 'translateX(-' + (0.62 * W) + 'px) skewX(' + (+lean + 8) + 'deg) scale(.62)', opacity: 0.6 },
                 { transform: 'translateX(0) skewX(' + lean + 'deg) scale(.62)', opacity: 0.6 }], { duration: slide || 3200, easing: 'cubic-bezier(.2,.7,.25,1)' });
  }
  function focus(id) {  // the fire goes out, the wall turns to paper, the shadow comes into focus
    shadowEl.style.opacity = 0;
    stage.classList.add('lit');
    anim(actor, [{ transform: 'translateX(0) skewX(' + (L.lean || 0) + 'deg) scale(.62)', opacity: 0.6 },
                 { transform: 'translateX(0) skewX(0deg) scale(.66)', opacity: 1 }], { duration: 700, easing: 'ease-out' });
    anim(shadowPic, [{ filter: 'blur(3px)' }, { filter: 'blur(0px)' }], { duration: 700 });
    return wait(700, id);
  }
  function still(id) {  // the chair as a plain frame, ready to come closer
    shadowPic.classList.remove('on');
    show(0);
  }
  function flip(id, speed) {  // it comes closer, flipping through the named kinds and people's chairs
    var sp = speed || 1;
    anim(actor, [{ transform: 'translateX(0) scale(.66)' }, { transform: 'translateX(0) scale(' + L.smax + ')' }],
         { duration: 2500 * sp, easing: 'cubic-bezier(.45,0,.3,1)' });
    var chain = Promise.resolve();
    frames.forEach(function (_, i) {
      if (!i) return;
      var t = i / frames.length, gap = (55 + Math.pow(t, 2.2) * 210) * sp;
      chain = chain.then(function () { return wait(gap, id); }).then(function () { show(i); });
    });
    return chain.then(function () { return wait(180, id); });
  }
  // Under a long hold: step through the chairs (people's and the named kinds), cross-fading, one per ~0.9 s.
  function cycle(id, until) {
    actor.classList.add('fade');
    var i = frames.length - 1;
    function next() {
      var left = until - performance.now();
      if (left <= 0) return Promise.resolve();
      return wait(Math.min(900, left), id).then(function () {
        if (until - performance.now() > 150) show(i = (i + 5) % frames.length);
        return next();
      });
    }
    return next().then(function () { actor.classList.remove('fade'); });
  }
  function drawForm() {  // the Form draws itself
    show(-1);
    if (!form) return;
    form.style.opacity = 1;
    [].slice.call(form.querySelectorAll('path')).forEach(function (path, j) {
      var len = path.getTotalLength();
      path.style.strokeDasharray = len;
      anim(path, [{ strokeDashoffset: len }, { strokeDashoffset: 0 }], { duration: 420, delay: 90 * j, easing: 'ease-out', fill: 'both' });
    });
    later(function () { form.classList.add('glow'); }, 600);  // drawn: it glows like an ember while the name is up
  }
  function end(id) { unsay(); return glide(id); }

  // --- the three styles -------------------------------------------------------------------------
  function playA(id) {  // the same sequence, every caption held for its reading time
    return opening(id, function () { cave(); }).then(function () { return hold(id, Q515); })
      .then(function () { unsay(); return focus(id); })
      .then(function () { still(id); say(Q596); return wait(1000, id); })  // the caption is up first, then the chair moves
      .then(function () {
        var until = performance.now() + 300 + readMs(Q596) - 1000;  // the caption's reading time is unchanged
        return flip(id).then(function () { return cycle(id, until); });  // ...and the pictures keep changing under it
      }).then(function () { drawForm(); return hold(id, ONE, 'name'); })
      .then(function () { return end(id); });
  }
  function playB(id) {  // words first: each caption alone, big, then small at the top while the scene plays
    return opening(id, function () { cave(2400); }).then(function () { return hold(id, Q515, 'big', true); })
      .then(function () { demote(); return focus(id); })
      .then(function () { return wait(1500, id); })
      .then(function () { unsay(); still(id); return wait(500, id); })
      .then(function () { return hold(id, Q596, 'big', true); })
      .then(function () { demote(); return flip(id); })
      .then(function () { unsay(); drawForm(); return wait(900, id); })
      .then(function () { return hold(id, ONE, 'high name'); })
      .then(function () { return end(id); });
  }
  function playC(id) {  // short and bold: three lines
    return opening(id, function () { cave(2600); }).then(function () { return hold(id, C1, 'big', true, 3000); })
      .then(function () { return hold(id, C2, 'big', false, 2800); })
      .then(function () { unsay(); return focus(id); })
      .then(function () { still(id); return flip(id, 0.5); })
      .then(function () { drawForm(); return hold(id, C3, 'high', false, 3000); })
      .then(function () { return end(id); });
  }
  function play() {
    var id = ++run;
    return (STYLE === 'b' ? playB : STYLE === 'c' ? playC : playA)(id);
  }

  // --- into the header --------------------------------------------------------------------------
  function glide(id) {
    var g = logoTarget();
    root.classList.remove('splash-on');
    root.classList.add('splash-fade');
    stage.classList.add('out');
    if (!g || !form) return wait(700, id).then(function () { finish(); });
    // it swells for a beat, bursts into sparks, and flies up into the header trailing a few more
    var SWELL = 180, FLY = 950, cx = L.x + L.base / 2, cy = L.y + L.base / 2;
    anim(actor, [{ transform: 'translate(0,0) scale(' + L.smax + ')', easing: 'ease-out' },
                 { transform: 'translate(0,0) scale(' + (L.smax * 1.1) + ')', offset: SWELL / (SWELL + FLY), easing: 'cubic-bezier(.65,0,.35,1)' },
                 { transform: 'translate(' + g.dx + 'px,' + g.dy + 'px) scale(' + g.s + ')' }], { duration: SWELL + FLY });
    later(function () { ring(cx, cy, L.base * L.smax * 0.75); burst(cx, cy, 60, L.base * L.smax * 1.05, 1); }, SWELL - 40);
    for (var k = 1; k <= 8; k++) {
      (function (k) {
        var t = k / 9, e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;  // the flight's easing, roughly
        later(function () { burst(cx + g.dx * e, cy + g.dy * e, 6, L.base * 0.32, 0.6); }, SWELL + FLY * t);
      })(k);
    }
    later(function () { ring(cx + g.dx, cy + g.dy, L.base * g.s); }, SWELL + FLY - 60);
    form.classList.remove('glow');
    anim(form, [{ color: NAVY }, { color: WHITE }], { duration: 600, delay: SWELL + 350 });
    var seat = form.querySelector('.seat');
    if (seat) anim(seat, [{ stroke: ORANGE }, { stroke: WHITE }], { duration: 600, delay: SWELL + 350 });
    return wait(SWELL + FLY + 560, id).then(function () { finish(); });
  }
  // Sparks flying out from (x, y): n of them, up to `reach` px away, each fading as it goes.
  function burst(x, y, n, reach, life) {
    for (var i = 0; i < n; i++) {
      var sp = stage.appendChild(el('i', 'sp-spark' + (i % 3 ? (i % 3 === 1 ? ' b' : ' c') : ''), null));
      var a = Math.random() * Math.PI * 2, d = reach * (0.45 + Math.random() * 0.55), size = (5 + Math.random() * 11) * (0.6 + 0.4 * life);
      sp.style.left = x + 'px'; sp.style.top = y + 'px'; sp.style.width = sp.style.height = size + 'px';
      anim(sp, [{ transform: 'translate(-50%,-50%) translate(0,0) scale(1)', opacity: 1 },
                { transform: 'translate(-50%,-50%) translate(' + Math.cos(a) * d + 'px,' + (Math.sin(a) * d - reach * 0.15) + 'px) scale(0.2)', opacity: 0 }],
           { duration: (850 + Math.random() * 700) * life, easing: 'cubic-bezier(.15,.7,.3,1)' });
    }
  }
  // A ring of light where the chair lands in the header.
  function ring(x, y, size) {
    var r = stage.appendChild(el('i', 'sp-ring', null));
    r.style.left = x + 'px'; r.style.top = y + 'px'; r.style.width = r.style.height = Math.max(36, size * 2.2) + 'px';
    anim(r, [{ transform: 'translate(-50%,-50%) scale(0.4)', opacity: 0.95 }, { transform: 'translate(-50%,-50%) scale(2.6)', opacity: 0 }],
         { duration: 620, easing: 'ease-out' });
  }

  // --- the end, played or skipped ---------------------------------------------------------------
  function finish() {
    if (done) return;
    done = true;
    run++;
    endLog();
    cancelAnimationFrame(raf);
    timers.forEach(clearTimeout);
    anims.forEach(function (a) { try { a.cancel(); } catch (e) { /* already gone */ } });
    document.removeEventListener('keydown', onKey, true);
    window.removeEventListener('resize', finish);
    if (stage && stage.parentNode) stage.parentNode.removeChild(stage);
    root.classList.remove('splash-on', 'splash-fade', 'splash-static');
    window.PCSplash.done = true;
  }
  function onKey(e) { if (e.key === 'Escape') { e.preventDefault(); finish(); } }

  // --- start: once the stylesheet and pictures are in (or not at all) ----------------------------
  window.PCSplash = { skip: finish, log: log, style: STYLE, done: false, readMs: readMs };
  document.addEventListener('keydown', onKey, true);
  var sheet = document.createElement('link');
  sheet.rel = 'stylesheet';
  sheet.href = '/static/css/splash.css';
  var serif = document.createElement('link');  // the epigraphs' serif, for the quotes
  serif.rel = 'stylesheet';
  serif.href = 'https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:ital,wght@1,300;1,400&display=swap';
  document.head.appendChild(serif);
  var sheetReady = new Promise(function (resolve, reject) { sheet.onload = resolve; sheet.onerror = reject; });
  document.head.appendChild(sheet);
  if (STATIC) {  // no pictures, no timers, no resize listener: it stays until Continue or Esc
    sheetReady.then(function () { if (!done) buildStatic(); }).catch(finish);
    return;
  }
  setTimeout(finish, MAX_MS);
  window.addEventListener('resize', finish);
  var names = ['shadow_chair'].concat(SHADOWS.map(function (n) { return 'shadow_' + n; }));
  for (var k = 1; k <= N_KINDS; k++) names.push('kind_' + (k < 10 ? '0' : '') + k);
  for (var p = 1; p <= N_PEOPLE; p++) names.push('people_' + p);
  // Every picture gets 1.5 s at most; one that fails or is slow is simply left out, and the intro goes on without it.
  var picsReady = Promise.all(names.map(function (n) {
    return new Promise(function (resolve) { var i = new Image(); i.onload = i.onerror = resolve; i.src = IMG + n + '.webp'; setTimeout(resolve, 1500); });
  }));
  var slow = new Promise(function (_, reject) { setTimeout(function () { reject(new Error('slow')); }, 3500); });
  Promise.race([Promise.all([sheetReady.catch(function () {}), picsReady]), slow]).then(function () {
    if (done) return;
    build();
    layout();
    var go = function () { play().catch(function (e) { if (!done && !(e && e.message === 'stopped')) finish(); }); };  // a scene that fails never leaves the stage frozen: the page opens
    if (document.hidden) {  // opened in a background tab: start when it's looked at
      document.addEventListener('visibilitychange', function onVis() {
        if (document.hidden) return;
        document.removeEventListener('visibilitychange', onVis);
        go();
      });
    } else {
      go();
    }
  }).catch(finish);  // couldn't load in time: just show the page
})();
