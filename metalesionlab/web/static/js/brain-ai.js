/* Damage, in a brain and in an AI. One timeline (play/pause and a slider) drives, side by side, an ageing brain
   (nine AI-made scan frames crossfading from age 20 to 80, what was lost, the fluid spaces at 20, the language areas)
   and a network of artificial neurons switching off, with Meta's open AI (Muse Glimmer) answering "Describe a chair
   in one sentence" at each damage step. The answers come from /api/plato/glimmer; without them the brain and the
   network still play. Plays only while on screen (IntersectionObserver); reduced motion: no autoplay, the slider works.
   Usage: an element with class "ba" (see pages/damaged.html); BrainAI.init(el) is also called for every .ba. */
(function () {
  "use strict";
  var IMG = "/static/img/brain_ai/";
  var API = "/api/plato/glimmer";
  var LAYERS = [9, 11, 12, 11, 10, 9], MAXOFF = 0.7;
  var FWD = 8000, HOLD = 3000, BACK = 2500, REST = 1500, LANG = 2500, FADE = 700;
  var MAXSTEP = 0.2; // the answers stop at 20% of the neurons switched off
  var RM = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)");

  function $(s, r) { return (r || document).querySelector(s); }
  function rng(seed) {
    return function () {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      var t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  function ease(u) { return u * u * (3 - 2 * u); }
  function invEase(t) { var lo = 0, hi = 1; for (var i = 0; i < 24; i++) { var m = (lo + hi) / 2; if (ease(m) < t) lo = m; else hi = m; } return lo; }
  function pulse(t) { return 0.5 * (Math.exp(-Math.pow((t - 0.4167) / 0.045, 2)) + Math.exp(-Math.pow((t - 0.8333) / 0.045, 2))); }

  // The canvas needs real colours: resolve the site's tokens through a probe element (refreshed when the theme flips).
  var probe = null, palette = null;
  function colour(token) {
    if (!probe) { probe = document.createElement("i"); probe.style.cssText = "position:absolute;width:0;height:0;visibility:hidden"; document.body.appendChild(probe); }
    probe.style.color = "var(" + token + ")";
    return getComputedStyle(probe).color;
  }
  function getPalette() {
    if (!palette) palette = { blue: colour("--blue"), orange: colour("--orange"), panel: colour("--panel"), off: colour("--line-2"), offEdge: colour("--line-3"), edge: colour("--line-3") };
    return palette;
  }
  if (typeof MutationObserver === "function") new MutationObserver(function () { palette = null; }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  function makeNet(seed) {
    var R = rng(seed), nodes = [], layers = [], id = 0;
    LAYERS.forEach(function (n, l) {
      var a = [];
      for (var j = 0; j < n; j++) { var o = { l: l, j: j, id: id++, x: 0, y: 0, rank: 0, flash: 0, off: false }; nodes.push(o); a.push(o); }
      layers.push(a);
    });
    var ord = nodes.slice();
    for (var i = ord.length - 1; i > 0; i--) { var k = Math.floor(R() * (i + 1)); var tmp = ord[i]; ord[i] = ord[k]; ord[k] = tmp; }
    ord.forEach(function (n, i) { n.rank = (i + 0.5) / ord.length; });
    var edges = [];
    for (var l = 0; l < layers.length - 1; l++) layers[l].forEach(function (a) {
      layers[l + 1].forEach(function (b) {
        var dj = Math.abs(a.j / (layers[l].length - 1) - b.j / (layers[l + 1].length - 1));
        if (R() < 0.55 - dj * 0.4) edges.push({ a: a, b: b });
      });
    });
    var out = new Map();
    nodes.forEach(function (n) { out.set(n, []); });
    edges.forEach(function (e) { out.get(e.a).push(e); });
    return { nodes: nodes, layers: layers, edges: edges, out: out, pulses: [], R: R, spawn: 0 };
  }

  function fit(c) {
    var d = Math.min(window.devicePixelRatio || 1, 3), w = c.clientWidth, h = c.clientHeight;
    if (c.width !== Math.round(w * d) || c.height !== Math.round(h * d)) { c.width = Math.round(w * d); c.height = Math.round(h * d); }
    return { w: w, h: h, d: d };
  }

  function drawNet(c, net, t, dt, still) {
    var f = fit(c), w = f.w, h = f.h, x = c.getContext("2d"), P = getPalette();
    x.setTransform(f.d, 0, 0, f.d, 0, 0); x.clearRect(0, 0, w, h);
    var frac = t * MAXOFF, padx = w * 0.05, pady = h * 0.07, r = Math.max(3.5, Math.min(w, h) * 0.026);
    net.nodes.forEach(function (n) {
      n.x = padx + (w - 2 * padx) * n.l / (LAYERS.length - 1);
      n.y = pady + (h - 2 * pady) * (n.j + 0.5) / net.layers[n.l].length;
      var o = n.rank < frac;
      if (o && !n.off && !still) n.flash = 1;
      if (!o) n.flash = 0;
      n.off = o; n.flash = Math.max(0, n.flash - dt / 0.5);
    });
    x.lineWidth = 1;
    net.edges.forEach(function (e) {
      var on = !e.a.off && !e.b.off;
      x.globalAlpha = on ? 0.35 : 0.1; x.strokeStyle = on ? P.blue : P.edge;
      x.beginPath(); x.moveTo(e.a.x, e.a.y); x.lineTo(e.b.x, e.b.y); x.stroke();
    });
    x.globalAlpha = 1;
    if (!still) { // signals travelling through the neurons that are still on
      var act = net.layers[0].filter(function (n) { return !n.off; });
      net.spawn += dt * 9 * (act.length / LAYERS[0]);
      while (net.spawn > 1 && net.pulses.length < 70) {
        net.spawn--;
        var n0 = act[Math.floor(net.R() * act.length)]; if (!n0) break;
        var es = net.out.get(n0).filter(function (e) { return !e.b.off; });
        if (es.length) net.pulses.push({ e: es[Math.floor(net.R() * es.length)], p: 0 });
      }
      net.spawn = Math.min(net.spawn, 1.5);
      var keep = [];
      net.pulses.forEach(function (p) {
        p.p += dt * 0.9;
        if (p.e.a.off) return;
        if (p.p >= 1) {
          var nx = net.out.get(p.e.b).filter(function (e) { return !e.b.off; });
          if (p.e.b.off || !nx.length) return;
          p.e = nx[Math.floor(net.R() * nx.length)]; p.p -= 1;
        }
        if (p.e.b.off && p.p > 0.8) return;
        var px = p.e.a.x + (p.e.b.x - p.e.a.x) * p.p, py = p.e.a.y + (p.e.b.y - p.e.a.y) * p.p;
        x.globalAlpha = 0.85; x.fillStyle = P.blue; x.beginPath(); x.arc(px, py, r * 0.6, 0, 7); x.fill();
        x.globalAlpha = 0.25; x.beginPath(); x.arc(px, py, r * 1.5, 0, 7); x.fill();
        x.globalAlpha = 1; keep.push(p);
      });
      net.pulses = keep;
    }
    net.nodes.forEach(function (n) {
      if (n.off) { x.fillStyle = P.off; x.strokeStyle = P.offEdge; x.lineWidth = 1.2; x.beginPath(); x.arc(n.x, n.y, r, 0, 7); x.fill(); x.stroke(); }
      else {
        x.fillStyle = P.panel; x.strokeStyle = P.blue; x.lineWidth = 1.8; x.beginPath(); x.arc(n.x, n.y, r, 0, 7); x.fill(); x.stroke();
        x.globalAlpha = 0.4; x.fillStyle = P.blue; x.beginPath(); x.arc(n.x, n.y, r * 0.55, 0, 7); x.fill(); x.globalAlpha = 1;
      }
      if (n.flash > 0) {
        x.globalAlpha = n.flash; x.strokeStyle = P.orange; x.lineWidth = 3;
        x.beginPath(); x.arc(n.x, n.y, r * (1 + (1 - n.flash) * 1.8), 0, 7); x.stroke();
        x.globalAlpha = n.flash * 0.8; x.fillStyle = P.orange; x.beginPath(); x.arc(n.x, n.y, r, 0, 7); x.fill(); x.globalAlpha = 1;
      }
    });
  }

  function img(src, z, alt) {
    var im = new Image(); im.decoding = "async"; im.src = src; im.alt = alt || ""; im.style.zIndex = z;
    if (!alt) im.setAttribute("aria-hidden", "true");
    return im;
  }
  function blend(a, t) {
    var p = t * 8, i = Math.floor(p), f = p - i;
    a.forEach(function (im, k) { im.style.opacity = k === i ? 1 : (k === i + 1 ? f : 0); });
    if (i >= 8) a[8].style.opacity = 1;
  }

  function init(root) {
    if (root.__ba) return root.__ba;
    var stage = $(".ba-stage", root), canvas = $(".ba-net", root), ageEls = root.querySelectorAll(".ba-age-n");
    var sl = $(".ba-slider", root), pp = $(".ba-pp", root), ans = $(".ba-ans", root), mk = $(".ba-mk", root);
    var lines = $(".ba-lines", stage), lbls = [].slice.call(stage.querySelectorAll(".ba-lbl")), langcap = $(".ba-langcap", root);
    var brain = [], loss = [], first = lines;
    for (var i = 0; i < 9; i++) { var b = img(IMG + "brain_" + i + ".webp", 1, i === 0 ? "An AI-made illustration of an ageing brain scan" : ""); stage.insertBefore(b, first); brain.push(b); }
    for (i = 0; i < 9; i++) { var l = img(IMG + "loss_" + i + ".webp", 3); stage.insertBefore(l, first); loss.push(l); }
    var ghost = img(IMG + "ghost_vent.webp", 4), lang = img(IMG + "lang.webp", 5);
    stage.insertBefore(ghost, first); stage.insertBefore(lang, first);

    var net = makeNet(11), steps = [], stepI = -1, typeTimer = null;
    var T = 0, playing = false, wantPlay = false, visible = false, phase = "lang", ph0 = 0, last = 0, raf = 0, dragging = false;

    function reduced() { return !!(RM && RM.matches); }

    // Glimmer's real answers, damage step by step (stopping at 20% of the neurons off).
    (typeof fetch === "function" ? fetch(API) : Promise.reject(new Error("no fetch"))).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (d) {
      var s = d.damage[0].steps, ci = d.featured.chair, out = [];
      for (var k = 0; k < s.length; k++) {
        var cond = s[k].cond;
        var dose = cond === "intact" ? 0 : parseFloat(cond.split("@")[1]);
        if (dose > MAXSTEP + 1e-9) break;
        var txt = d.sentences[cond].chair[ci], ok = d.marks[cond].chair.correct[ci] === "1";
        if (typeof txt !== "string") throw new Error("no sentence");
        out.push({ text: txt, ok: ok });
      }
      if (!out.length) throw new Error("no steps");
      steps = out; stepI = -1; render(0);
    }).catch(function () { root.setAttribute("data-noai", "1"); });

    function setStep(i) {
      if (i === stepI || !steps.length) return;
      stepI = i; var s = steps[i];
      clearInterval(typeTimer);
      mk.innerHTML = "";
      var pill = document.createElement("span"); pill.className = "ba-pill " + (s.ok ? "ok" : "bad");
      pill.textContent = s.ok ? "describes it right" : "describes it wrong"; mk.appendChild(pill);
      if (reduced() || !visible) { ans.textContent = s.text; return; }
      var k = 0, cur = document.createElement("span"), t = document.createTextNode("");
      cur.className = "ba-cur"; ans.textContent = ""; ans.appendChild(t); ans.appendChild(cur);
      typeTimer = setInterval(function () {
        k = Math.min(s.text.length, k + 2); t.nodeValue = s.text.slice(0, k);
        if (k >= s.text.length) { clearInterval(typeTimer); cur.remove(); }
      }, 18);
    }

    var lblOp = 1, langOp = 1;
    function render(dt, now) {
      now = now || performance.now();
      if (playing) {
        var el = now - ph0;
        if (phase === "lang") { lblOp = 1; langOp = 1; }
        else if (phase === "fwd" && el < FADE) { lblOp = langOp = 1 - el / FADE; }
        else { lblOp = 0; langOp = 0; }
        langOp = Math.max(langOp, pulse(T));
      } else { lblOp = T < 0.02 ? 1 : 0; langOp = Math.max(lblOp, pulse(T)); }
      var ghostOp = Math.max(0, Math.min(1, (T * 60 - 8) / 8));
      var n = steps.length || 5, si = Math.round(T * (n - 1));
      blend(brain, T); blend(loss, T);
      ghost.style.opacity = ghostOp; lang.style.opacity = langOp;
      lines.style.opacity = lblOp; lbls.forEach(function (e) { e.style.opacity = lblOp; }); langcap.style.opacity = lblOp;
      drawNet(canvas, net, steps.length ? si / (n - 1) : T, dt, !playing && dt === 0);
      var age = Math.round(20 + 60 * T);
      ageEls.forEach(function (e) { e.textContent = age; });
      sl.setAttribute("aria-valuetext", "Age " + age);
      setStep(si);
    }

    function tick(now) {
      raf = 0;
      if (!visible || document.hidden) return;
      var dt = Math.min(0.1, (now - last) / 1000); last = now;
      if (playing && !dragging) {
        var el = now - ph0;
        if (phase === "lang") { T = 0; if (el >= LANG) { phase = "fwd"; ph0 = now; } }
        else if (phase === "fwd") { var u = Math.min(1, el / FWD); T = ease(u); if (el >= FWD) { phase = "hold"; ph0 = now; } }
        else if (phase === "hold") { T = 1; if (el >= HOLD) { phase = "back"; ph0 = now; } }
        else if (phase === "back") { var v = Math.min(1, el / BACK); T = 1 - ease(v); if (el >= BACK) { phase = "rest"; ph0 = now; T = 0; } }
        else { T = 0; if (el >= REST) { phase = "lang"; ph0 = now; } }
        sl.value = Math.round(T * 1000);
      }
      render(dt, now);
      raf = requestAnimationFrame(tick);
    }
    function loop() { if (!raf && visible && !document.hidden) { last = performance.now(); raf = requestAnimationFrame(tick); } }

    function setPlaying(p) {
      playing = p; wantPlay = p;
      root.setAttribute("data-state", p ? "playing" : "paused");
      pp.setAttribute("aria-label", p ? "Pause the animation" : "Play the animation");
      if (p) {
        var n = performance.now();
        if (T >= 1) { phase = "hold"; ph0 = n; } else if (T < 0.001) { phase = "lang"; ph0 = n; } else { phase = "fwd"; ph0 = n - invEase(T) * FWD; }
        loop();
      } else render(0.016);
    }
    pp.addEventListener("click", function () { setPlaying(!playing); });
    sl.addEventListener("input", function () { T = sl.value / 1000; if (playing) setPlaying(false); render(0.016); loop(); });

    // Plays only while on screen and while the tab is showing.
    var io = typeof IntersectionObserver !== "function" ? null : new IntersectionObserver(function (es) {
      visible = es[es.length - 1].isIntersecting;
      if (visible) {
        if (wantPlay && !playing) setPlaying(true);
        loop();
      } else {
        if (raf) { cancelAnimationFrame(raf); raf = 0; }
        clearInterval(typeTimer); if (steps.length && stepI >= 0) ans.textContent = steps[stepI].text;
        if (playing) { playing = false; root.setAttribute("data-state", "paused"); }
      }
    }, { threshold: 0.15 });
    if (io) io.observe(root); else { visible = true; loop(); }
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) { if (raf) { cancelAnimationFrame(raf); raf = 0; } if (playing) { playing = false; root.setAttribute("data-state", "paused"); } }
      else { if (wantPlay && visible && !playing) setPlaying(true); loop(); }
    });
    window.addEventListener("resize", function () { render(0, undefined); });

    // Reduced motion: no autoplay; the slider still works, the answers show at once.
    wantPlay = !reduced();
    root.setAttribute("data-state", "paused");
    pp.setAttribute("aria-label", "Play the animation");
    render(0);
    root.__ba = { setT: function (v) { setPlaying(false); T = v; sl.value = Math.round(v * 1000); render(0.016); } };
    return root.__ba;
  }

  window.BrainAI = { init: init };
  function boot() { [].forEach.call(document.querySelectorAll(".ba"), init); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
