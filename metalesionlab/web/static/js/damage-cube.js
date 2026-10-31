/* Damage cube: one AI picture turning on a cube, a quarter-turn per step of damage, from undamaged to the most damage,
   so the change reads as gradual (Damaged AI's first screen: God becoming an ordinary person). Each of the four faces
   is re-used for the step about to come into view, and faces darken as they turn away from the viewer.

   It plays by itself while it is on screen: one step about every 1.8 s, a longer hold on the last step, then a fast
   spin back to the start. The button pauses it; a step on the track turns straight to that step (and pauses).
   Reduced motion: it never plays by itself, and the track jumps without turning.

   Markup: <figure data-damage-cube data-pattern="/static/…/god_{i}.webp" data-labels="undamaged|noise × 0.2|…">
   containing .dcube-scene > .dcube-cube, .dcube-step, .dcube-track and .dcube-play (damage-cube.css). */
(function () {
  'use strict';
  var reduce = false;
  try { reduce = matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { /* old browser */ }
  function ease(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }

  function mount(root) {
    var labels = (root.getAttribute('data-labels') || '').split('|'), n = labels.length, pattern = root.getAttribute('data-pattern');
    var scene = root.querySelector('.dcube-scene'), cube = root.querySelector('.dcube-cube');
    var stepEl = root.querySelector('.dcube-step'), trackEl = root.querySelector('.dcube-track'), play = root.querySelector('.dcube-play');
    if (!scene || !cube || !pattern || n < 2) return;
    var src = function (i) { return pattern.replace('{i}', i); };
    for (var k = 0; k < n; k++) { var pre = new Image(); pre.src = src(k); }  // every step ready before it turns into view

    cube.innerHTML = '';
    var faces = [];
    for (var f = 0; f < 4; f++) {
      var face = document.createElement('div');
      face.className = 'dcube-face';
      face.innerHTML = '<img alt="" decoding="async"><span class="dcube-shade"></span>';
      cube.appendChild(face);
      faces.push({ el: face, img: face.querySelector('img'), shade: face.querySelector('.dcube-shade'), lvl: -1 });
    }
    var x = 0, step = 0, paused = reduce, visible = false, timer = 0, raf = 0;

    function set(v) {  // v: how far along, 0 = undamaged, n - 1 = the most damage
      x = v;
      var s = scene.getBoundingClientRect().width / 2, base = Math.floor(v + 1e-6);
      cube.style.transform = 'translateZ(' + (-s) + 'px) rotateY(' + (-90 * v) + 'deg)';
      faces.forEach(function (fc, i) {
        fc.el.style.transform = 'rotateY(' + (90 * i) + 'deg) translateZ(' + s + 'px)';
        var d = ((i - base) % 4 + 4) % 4, lvl = Math.max(0, Math.min(n - 1, base + (d === 3 ? -1 : d)));
        if (fc.lvl !== lvl) { fc.img.src = src(lvl); fc.lvl = lvl; }
        var a = (90 * i - 90 * v) * Math.PI / 180;
        fc.shade.style.opacity = (0.62 * (1 - Math.max(0, Math.cos(a)))).toFixed(3);
      });
    }
    function show(i) {
      step = i;
      if (stepEl) stepEl.textContent = labels[i] + ' · step ' + (i + 1) + ' of ' + n;
      if (trackEl) [].forEach.call(trackEl.children, function (b, j) {
        b.classList.toggle('on', j <= i);
        b.setAttribute('aria-current', j === i ? 'step' : 'false');
      });
    }
    function turn(to, ms, done) {
      cancelAnimationFrame(raf);
      if (reduce || ms <= 0) { set(to); show(to); if (done) done(); return; }
      var from = x, t0 = performance.now();
      (function tick(now) {
        var t = Math.min(1, (now - t0) / ms);
        set(from + (to - from) * ease(t));
        if (t < 1) raf = requestAnimationFrame(tick); else { show(to); if (done) done(); }
      })(t0);
    }
    function next() {
      clearTimeout(timer);
      if (paused || !visible) return;
      if (step < n - 1) turn(step + 1, 900, function () { timer = setTimeout(next, step === n - 1 ? 2600 : 900); });
      else turn(0, 1600, function () { timer = setTimeout(next, 1400); });
    }
    function setPaused(p) {
      paused = p;
      if (play) { play.textContent = p ? 'Play' : 'Pause'; play.setAttribute('aria-pressed', String(p)); }
      clearTimeout(timer);
      if (!p) timer = setTimeout(next, 600);
    }

    if (trackEl) {
      trackEl.innerHTML = '';
      labels.forEach(function (lab, i) {
        var b = document.createElement('button');
        b.type = 'button';
        b.setAttribute('aria-label', 'Step ' + (i + 1) + ' of ' + n + ': ' + lab);
        b.addEventListener('click', function () { setPaused(true); turn(i, 650); });
        trackEl.appendChild(b);
      });
    }
    if (play) {
      if (reduce) play.hidden = true;
      play.addEventListener('click', function () { setPaused(!paused); });
    }
    scene.addEventListener('click', function () { if (!reduce) setPaused(!paused); });
    window.addEventListener('resize', function () { set(x); });
    set(0);
    show(0);
    root.classList.add('ready');
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (es) {
        visible = es[0].isIntersecting;
        clearTimeout(timer);
        if (visible && !paused) timer = setTimeout(next, 1100);
      }, { threshold: 0.4 }).observe(scene);
    } else {
      visible = true;
      if (!paused) timer = setTimeout(next, 1100);
    }
  }

  function init() { [].forEach.call(document.querySelectorAll('[data-damage-cube]'), mount); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
