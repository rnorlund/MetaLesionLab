/* Plato's Chair's opening animation, "the cave", on the landing page (about 8 seconds).

   Firelight and drifting shadows, with Republic 515c. The chair's shadow slows to the centre and comes
   into focus, the wall turns to paper, and the chair comes closer while flipping through the 16 kinds
   Muse Spark named (drawn by Muse Image) and people's own chairs, with Republic 596a. It ends on the
   geometric "Form" chair, which draws itself and glides into the header's brand slot to become the logo,
   while the page fades in under it.

   When it plays is decided by a small script in the page's <head>, before the first paint, which adds
   html.splash-on: once per browser session (sessionStorage "pc-splash-seen"), never with reduced motion,
   during the guided tour, on a deep link (#…) or with ?nosplash=1; ?splash=1 plays it again. Skip it
   with the Skip button or any key. It never shows Muse Image's own chairs (the 16 alike ones), so the
   drawing that follows stays blind. Its pictures (static/img/splash/, about 110 KB) and stylesheet
   load only when it plays. The Form chair is the header's own logo (web/site.py FORM_CHAIR), cloned. */
(function () {
  'use strict';
  var root = document.documentElement;
  if (!root.classList.contains('splash-on')) return;
  try { window.sessionStorage.setItem('pc-splash-seen', '1'); } catch (e) { /* storage off: the head script won't play it */ }

  var IMG = '/static/img/splash/';
  var SHADOWS = ['umbrella', 'cup', 'cat', 'bicycle', 'tree', 'house', 'key'];
  var N_KINDS = 16, N_PEOPLE = 8;
  var Q515 = '“To them, I said, the truth would be literally nothing but the shadows of the images.”' +
    '<cite>Plato, Republic 515c · Jowett</cite>';
  var Q596 = '“Whenever a number of individuals have a common name, we assume them to have also a corresponding idea or form.”' +
    '<cite>Plato, Republic 596a · Jowett</cite>';
  var NAVY = '#141a26', WHITE = '#F9FAFB', ORANGE = '#C2410C';
  var MAX_MS = 14000;  // whatever happens, the page is back by then

  var run = 0, done = false, anims = [], timers = [];
  var stage, actor, shadowEl, caption, credit, skipBtn, form, frames = [], shadowPic, L = {};

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function img(src) { var i = new Image(); i.src = src; i.alt = ''; i.decoding = 'async'; return i; }
  function later(fn, ms) { timers.push(setTimeout(fn, ms)); }
  function wait(ms, id) {
    return new Promise(function (resolve, reject) {
      later(function () { if (id === run && !done) resolve(); else reject(new Error('stopped')); }, ms);
    });
  }
  function anim(target, frames_, opts) {
    var o = Object.assign({ fill: 'forwards' }, opts);
    var a = target.animate(frames_, o);
    anims.push(a);
    return a;
  }
  function say(html) {
    caption.classList.remove('on');
    later(function () { caption.innerHTML = html || ''; if (html) caption.classList.add('on'); }, 250);
  }

  // --- the stage --------------------------------------------------------------------------------
  function build() {
    stage = el('div', 'splash');
    var scene = el('div', 'sp-scene');
    scene.setAttribute('aria-hidden', 'true');
    scene.appendChild(el('div', 'sp-bg sp-wall'));
    scene.appendChild(el('div', 'sp-bg sp-paper'));
    scene.appendChild(el('div', 'sp-bg sp-fire'));
    scene.appendChild(el('div', 'sp-bg sp-fire b'));
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
    caption = scene.appendChild(el('p', 'sp-caption'));
    credit = scene.appendChild(el('p', 'sp-credit',
      'Chairs: 16 kinds named by Muse Spark and drawn by Muse Image, and people’s drawings (Google Quick, Draw!, CC BY 4.0)'));
    stage.appendChild(scene);
    skipBtn = el('button', 'sp-skip', 'Skip <small>· any key</small>');
    skipBtn.type = 'button';
    skipBtn.setAttribute('aria-label', 'Skip the opening animation');
    skipBtn.addEventListener('click', function () { finish(); });
    stage.appendChild(skipBtn);
    document.body.appendChild(stage);
  }

  // The chair's size and place follow the stage's height, so it never grows into the caption.
  function layout() {
    var W = window.innerWidth, H = window.innerHeight, portrait = W < H;
    L.W = W; L.H = H;
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

  // --- the cave ---------------------------------------------------------------------------------
  function play() {
    var id = ++run, W = L.W, H = L.H;
    SHADOWS.forEach(function (name, i) {
      var s = img(IMG + 'shadow_' + name + '.webp');
      shadowEl.appendChild(s);
      var scale = 0.65 + (i % 3) * 0.22, y = H * (0.14 + (i * 0.37 % 0.5)), dir = i % 2 ? -1 : 1;
      var from = dir > 0 ? -0.25 * W : 1.05 * W, to = dir > 0 ? 1.05 * W : -0.25 * W;
      anim(s, [{ transform: 'translate(' + from + 'px,' + y + 'px) skewX(-14deg) scale(' + scale + ')' },
               { transform: 'translate(' + to + 'px,' + (y + (i % 2 ? -10 : 10)) + 'px) skewX(-14deg) scale(' + scale + ')' }],
           { duration: 3600 + i * 420, delay: i * 260 - 300, easing: 'linear', fill: 'both' });
    });
    shadowPic.classList.add('on');
    shadowPic.style.filter = 'blur(3px)';
    anim(actor, [{ transform: 'translateX(-' + (0.62 * W) + 'px) skewX(-14deg) scale(.62)', opacity: 0.6 },
                 { transform: 'translateX(0) skewX(-14deg) scale(.62)', opacity: 0.6 }], { duration: 2600, easing: 'cubic-bezier(.2,.7,.25,1)' });
    return wait(400, id).then(function () {
      say(Q515);
      return wait(2200, id);
    }).then(function () {
      // the fire goes out, the wall turns to paper, the shadow comes into focus
      shadowEl.style.opacity = 0;
      stage.classList.add('lit');
      say('');
      anim(actor, [{ transform: 'translateX(0) skewX(-14deg) scale(.62)', opacity: 0.6 },
                   { transform: 'translateX(0) skewX(0deg) scale(.66)', opacity: 1 }], { duration: 600, easing: 'ease-out' });
      anim(shadowPic, [{ filter: 'blur(3px)' }, { filter: 'blur(0px)' }], { duration: 600 });
      return wait(600, id);
    }).then(function () {
      // it comes closer, flipping through the named kinds and people's chairs
      shadowPic.classList.remove('on');
      show(0);
      say(Q596);
      credit.classList.add('on');
      anim(actor, [{ transform: 'translateX(0) scale(.66)' }, { transform: 'translateX(0) scale(' + L.smax + ')' }],
           { duration: 2500, easing: 'cubic-bezier(.45,0,.3,1)' });
      var chain = Promise.resolve();
      frames.forEach(function (_, i) {
        if (!i) return;
        var t = i / frames.length, gap = 55 + Math.pow(t, 2.2) * 210;
        chain = chain.then(function () { return wait(gap, id); }).then(function () { show(i); });
      });
      return chain.then(function () { return wait(180, id); });
    }).then(function () {
      // the Form draws itself
      show(-1);
      credit.classList.remove('on');
      if (form) {
        form.style.opacity = 1;
        [].slice.call(form.querySelectorAll('path')).forEach(function (path, j) {
          var len = path.getTotalLength();
          path.style.strokeDasharray = len;
          anim(path, [{ strokeDashoffset: len }, { strokeDashoffset: 0 }], { duration: 420, delay: 90 * j, easing: 'ease-out', fill: 'both' });
        });
      }
      say('One ideal chair?');
      return wait(1250, id);
    }).then(function () {
      say('');
      return glide(id);
    });
  }

  // --- into the header --------------------------------------------------------------------------
  function glide(id) {
    var g = logoTarget();
    root.classList.remove('splash-on');
    root.classList.add('splash-fade');
    stage.classList.add('out');
    if (!g || !form) return wait(700, id).then(function () { finish(); });
    anim(actor, [{ transform: 'translateX(0) scale(' + L.smax + ')' }, { transform: 'translate(' + g.dx + 'px,' + g.dy + 'px) scale(' + g.s + ')' }],
         { duration: 950, easing: 'cubic-bezier(.65,0,.35,1)' });
    anim(form, [{ color: NAVY }, { color: WHITE }], { duration: 600, delay: 350 });
    var seat = form.querySelector('.seat');
    if (seat) anim(seat, [{ stroke: ORANGE }, { stroke: WHITE }], { duration: 600, delay: 350 });
    return wait(1000, id).then(function () { finish(); });
  }

  // --- the end, played or skipped ---------------------------------------------------------------
  function finish() {
    if (done) return;
    done = true;
    run++;
    timers.forEach(clearTimeout);
    anims.forEach(function (a) { try { a.cancel(); } catch (e) { /* already gone */ } });
    document.removeEventListener('keydown', onKey, true);
    window.removeEventListener('resize', finish);
    if (stage && stage.parentNode) stage.parentNode.removeChild(stage);
    root.classList.remove('splash-on', 'splash-fade');
  }
  function onKey(e) {
    if (e.repeat) return;
    if (e.key === ' ' || e.key === 'Enter') e.preventDefault();  // skipping shouldn't also scroll or click
    finish();
  }

  // --- start: once the stylesheet and pictures are in (or not at all) ----------------------------
  setTimeout(finish, MAX_MS);
  document.addEventListener('keydown', onKey, true);
  window.addEventListener('resize', finish);
  var sheet = document.createElement('link');
  sheet.rel = 'stylesheet';
  sheet.href = '/static/css/splash.css';
  var sheetReady = new Promise(function (resolve, reject) { sheet.onload = resolve; sheet.onerror = reject; });
  document.head.appendChild(sheet);
  var names = ['shadow_chair'].concat(SHADOWS.map(function (n) { return 'shadow_' + n; }));
  for (var k = 1; k <= N_KINDS; k++) names.push('kind_' + (k < 10 ? '0' : '') + k);
  for (var p = 1; p <= N_PEOPLE; p++) names.push('people_' + p);
  var picsReady = Promise.all(names.map(function (n) {
    return new Promise(function (resolve, reject) { var i = new Image(); i.onload = resolve; i.onerror = reject; i.src = IMG + n + '.webp'; });
  }));
  var slow = new Promise(function (_, reject) { setTimeout(function () { reject(new Error('slow')); }, 3500); });
  Promise.race([Promise.all([sheetReady, picsReady]), slow]).then(function () {
    if (done) return;
    build();
    layout();
    var go = function () { play().catch(function () { /* skipped */ }); };
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

  window.PCSplash = { skip: finish };
})();
