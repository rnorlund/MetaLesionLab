/* Watch an AI forget what a chair is (/plato/lifespan#forget): the sketch model of #learn, fully trained, with a
   growing share of its artificial neurons switched off. Reads /api/plato/lifespan/forget (public_data/
   plato_sketch_forget.json, written by scripts/plato_sketch_forget.py analyze --public: group-level numbers only).
   The pictures are two sprites: the learning animation's (24 frames, 6 across and 4 down) and this one (one frame per
   damage level, 4 x 4). Colours are the site's tokens, so both themes work: blue is learning, orange is forgetting.
   Line art sits on paper in every theme. With reduced motion nothing plays by itself. */
(function () {
  'use strict';
  var app = document.getElementById('forget-app');
  if (!app || !window.TOT) return;
  var h = TOT.h, SVGNS = 'http://www.w3.org/2000/svg';
  var REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var SPRITE = { learn: '/static/img/plato_lifespan/sketch/learn_sprite.webp', forget: '/static/img/plato_forget/forget_sprite.webp' };
  var TEMPS = [['t0.4', 'Low randomness, as in the pictures'], ['t1.0', 'Normal randomness']];
  var F = null, temp = 't0.4', markers = [], lastFrame = null;  // markers: the charts' 'you are here' marks

  // ---------- small helpers ----------
  function pct(x) { return x == null || isNaN(x) ? '–' : Math.round(100 * x) + '%'; }
  function f2(x) { return x == null || isNaN(x) ? '–' : x.toFixed(2); }
  function f3(x) { return x == null || isNaN(x) ? '–' : x.toFixed(3); }
  function signed(x, fmt) { return (x > 0 ? '+' : x < 0 ? '−' : '') + (fmt || f2)(Math.abs(x)); }
  function steps(n) { return Number(n).toLocaleString('en-US'); }
  function offTxt(d) { return (d === 0 ? '0' : d < 0.1 ? (100 * d).toFixed(0) : String(Math.round(100 * d))) + '%'; }
  function likely(c, fmt) { return 'probably between ' + signed(c[0], fmt) + ' and ' + signed(c[1], fmt); }
  function svg(tag, attrs, parent) {
    var el = document.createElementNS(SVGNS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) el.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(el);
    return el;
  }
  function label(parent, x, y, s, attrs) {
    var t = svg('text', Object.assign({ x: x, y: y }, attrs || {}), parent);
    t.textContent = s;
    return t;
  }
  function paint(prop, token) { return prop + ':var(' + token + ')'; }
  function tipper(box) {
    var tip = h('div', { class: 'fg-tip', role: 'status' });
    tip.hidden = true;
    box.appendChild(tip);
    return {
      show: function (evt, html) {
        tip.innerHTML = html;
        tip.hidden = false;
        var r = box.getBoundingClientRect(), x = evt.clientX - r.left + 14, y = evt.clientY - r.top + 14;
        if (x + tip.offsetWidth > r.width) x = Math.max(0, evt.clientX - r.left - tip.offsetWidth - 14);
        tip.style.left = x + 'px';
        tip.style.top = y + 'px';
      },
      hide: function () { tip.hidden = true; }
    };
  }
  function T(tk) { return F.tests[tk || 'f'].silence.test_seeds; }
  function curve(tk) { return F.forget[tk].silence_display; }

  // ---------- the player: the same 16 chairs at every damage level, or its whole life ----------
  function frameList(mode) {
    var a = F.animation, out = [];
    if (mode === 'life') {
      a.learn_steps.forEach(function (st, k) { out.push({ kind: 'learn', k: k, step: st, recog: a.learn_recog[k], spread: a.learn_spread[k] }); });
    }
    a.doses.forEach(function (d, k) {
      if (mode === 'life' && k === 0) return;  // the fully trained model is learning's last frame
      out.push({ kind: 'forget', k: k, dose: d, recog: a.recog[k], spread: a.spread[k] });
    });
    return out;
  }

  function player() {
    var a = F.animation, nL = a.learn_steps.length, nF = a.doses.length;
    var grid = { learn: [Math.ceil(nL / 4), 4], forget: [4, Math.ceil(nF / 4)] };
    var looks = curve('t0.4').looks_like_step;
    var mode = 'forget', list = frameList(mode), i = 0, playing = false, timer = null, fadeTimer = null, touched = false;

    var base = h('div', { class: 'fg-frame' }), top = h('div', { class: 'fg-frame fg-top' });
    var pic = h('div', { class: 'fg-frames', role: 'img' }, [base, top]);
    var kicker = h('span'), big = h('b'), small = h('small');
    var recog = h('b'), spread = h('b');
    var range = h('input', { type: 'range', min: '0', max: String(list.length - 1), step: '1', value: '0', 'aria-label': 'How much damage' });
    var play = h('button', { type: 'button', class: 'ls-play', 'aria-pressed': 'false' }, 'Play');
    var life = h('button', { type: 'button', class: 'fg-life', 'aria-pressed': 'false' }, 'Play the life of an AI');
    var ends = h('div', { class: 'fg-ends', 'aria-hidden': 'true' }, [h('span', null, 'healthy'), h('span', null, 'all switched off')]);
    var lifebar = h('div', { class: 'fg-lifebar', 'aria-hidden': 'true' });
    var lbLearn = h('span', { class: 'fg-lb-learn' }), lbForget = h('span', { class: 'fg-lb-forget' }), lbDot = h('i');
    lifebar.appendChild(h('div', { class: 'fg-lb-track' }, [lbLearn, lbForget, lbDot]));
    lifebar.appendChild(h('div', { class: 'fg-lb-labels' }, [h('span', null, 'learning'), h('span', null, 'forgetting')]));
    var cap = h('p', { class: 'ls-note' }, '“Named as a chair” means a Meta AI that compares pictures (DINOv2) finds the drawing closest to people’s chairs, out of 21 things. ' +
      'One run of the model, drawing with low randomness (the randomness setting decides how boldly it draws). ' +
      'The 16 tiles are its first 16 drawings; the numbers come from all 200 of its drawings at each level. ' +
      'A blank tile is a drawing that was only a dot. The levels 2, 4, 6 and 8% were added after we saw that most of the change comes before 10%.');
    app.appendChild(h('div', { class: 'fg-player', id: 'forget-player' }, [
      h('div', { class: 'fg-pic' }, pic),
      h('div', { class: 'fg-read' }, [
        h('div', { class: 'fg-stage' }, [kicker, big, small]),
        h('div', { class: 'fg-row' }, [h('span', null, 'Drawings an AI could name as a chair'), recog]),
        h('div', { class: 'fg-row' }, [h('span', null, 'How different its drawings are from one another'), spread]),
        h('div', { class: 'fg-controls' }, [play, range]), ends, lifebar,
        h('div', { class: 'fg-life-row' }, [life, h('span', { class: 'ls-note' }, 'From scribbles to chairs as it learns, then back to scribbles as we damage it.')]),
        cap])]));

    lbLearn.style.flex = String(nL - 1);
    lbForget.style.flex = String(nF - 1);
    function sprite(el, f) {
      var g = grid[f.kind];
      el.style.backgroundImage = 'url("' + SPRITE[f.kind] + '")';
      el.style.backgroundSize = (g[0] * 100) + '% ' + (g[1] * 100) + '%';
      el.style.backgroundPosition = (f.k % g[0]) / (g[0] - 1) * 100 + '% ' + Math.floor(f.k / g[0]) / (g[1] - 1) * 100 + '%';
    }
    function readout(f) {
      if (f.kind === 'learn') {
        kicker.textContent = 'Learning: training step';
        big.textContent = steps(f.step);
        small.textContent = f.step ? steps(f.step * 100) + ' people’s chairs seen' : 'nothing learned yet';
      } else {
        kicker.textContent = 'Artificial neurons switched off';
        big.textContent = offTxt(f.dose);
        var st = looks[f.k];
        small.textContent = f.dose === 0 ? 'the fully trained model, before any damage'
          : st == null ? '' : 'looks most like step ' + steps(st) + ' of its training';
      }
      recog.textContent = pct(f.recog);
      spread.textContent = f2(f.spread);
      range.value = String(i);
      range.setAttribute('aria-valuetext', f.kind === 'learn' ? 'Training step ' + steps(f.step) : offTxt(f.dose) + ' of its neurons switched off');
      pic.setAttribute('aria-label', '16 chairs drawn by the sketch model, ' + (f.kind === 'learn' ? 'at training step ' + steps(f.step)
        : offTxt(f.dose) + ' of its artificial neurons switched off') + '; ' + pct(f.recog) + ' of its drawings can be named as chairs');
      // where it is in its life: learning fills the blue part, damage the orange
      var pos = f.kind === 'learn' ? f.k / (nL - 1) * (nL - 1) : (nL - 1) + f.k;
      lbDot.style.left = (100 * pos / (nL + nF - 2)) + '%';
      lastFrame = f;
      markers.forEach(function (m) { m(f); });
    }
    function show(k, fade) {
      i = k;
      var f = list[k];
      clearTimeout(fadeTimer);
      if (!fade || REDUCED) {
        sprite(base, f);
        top.classList.remove('fade');
      } else {
        sprite(top, f);
        top.classList.remove('fade');
        void top.offsetWidth;  // restart the cross-fade
        top.classList.add('fade');
        fadeTimer = setTimeout(function () { sprite(base, f); top.classList.remove('fade'); }, 380);
      }
      readout(f);
    }
    function setMode(m) {
      mode = m;
      list = frameList(m);
      range.max = String(list.length - 1);
      range.setAttribute('aria-label', m === 'life' ? 'Its life: learning, then damage' : 'How much damage');
      ends.firstChild.textContent = m === 'life' ? 'untrained' : 'healthy';
      app.classList.toggle('fg-in-life', m === 'life');
    }
    function tick() {
      var last = i === list.length - 1;
      if (last && mode === 'life') { stop(); return; }
      var f = list[last ? 0 : i + 1];
      show(last ? 0 : i + 1, true);
      var wait = f.kind === 'forget' && f.dose === 0 ? 1600 : i === list.length - 1 ? 2800 : i === 0 ? 1400 : 850;
      if (mode === 'life' && f.kind === 'learn' && f.k === nL - 1) wait = 1800;  // fully trained: a pause before the damage
      timer = setTimeout(tick, wait);
    }
    function stop() {
      playing = false;
      clearTimeout(timer);
      play.textContent = 'Play';
      play.setAttribute('aria-pressed', 'false');
      life.setAttribute('aria-pressed', 'false');
      life.textContent = 'Play the life of an AI';
    }
    function start(btn) {
      playing = true;
      clearTimeout(timer);
      btn.setAttribute('aria-pressed', 'true');
      if (btn === play) play.textContent = 'Pause';
      else life.textContent = 'Pause the life of an AI';
      timer = setTimeout(tick, i === list.length - 1 ? 300 : 700);
    }
    play.addEventListener('click', function () {
      touched = true;
      if (playing && mode === 'forget') { stop(); return; }
      stop();
      if (mode !== 'forget') { setMode('forget'); show(0, false); }
      else if (i === list.length - 1) show(0, false);
      start(play);
    });
    life.addEventListener('click', function () {
      touched = true;
      if (playing && mode === 'life') { stop(); return; }
      stop();
      if (mode !== 'life' || i === list.length - 1) { setMode('life'); show(0, false); }
      start(life);
    });
    range.addEventListener('input', function () { touched = true; stop(); show(+range.value, false); });
    setMode('forget');
    show(0, false);
    if (!REDUCED && 'IntersectionObserver' in window) {
      new IntersectionObserver(function (es) {
        es.forEach(function (e) {
          if (e.isIntersecting && !touched && !playing) start(play);
          else if (!e.isIntersecting && playing && !touched) stop();
        });
      }, { threshold: 0.5 }).observe(document.getElementById('forget-player'));
    }
  }

  // ---------- what we found ----------
  function findings() {
    var t1 = T('t1.0'), t4 = T('t0.4'), all1 = F.tests['t1.0'].silence.all_seeds;
    var q1 = t1.q1_distance_gap, q1a = all1 && all1.q1_distance_gap, half = t1.half_forgotten_dose;
    var cv1 = curve('t1.0'), cv4 = curve('t0.4'), dd = F.display_doses;
    var at = function (cv, m, d) { return cv[m].mean[dd.indexOf(d)]; };
    var lookStep = function (d) { return cv1.looks_like_step[dd.indexOf(d)]; };
    var learn4 = F.learn['t0.4'].recog.mean[0];
    var box = h('div', { class: 'fg-findings', role: 'list' });
    function card(cls, head, paras, numbers) {
      box.appendChild(h('div', { class: 'fg-card ' + cls, role: 'listitem' }, [h('h3', null, head)]
        .concat(paras.slice(0, 1).map(function (p) { return h('p', null, p); }))  // one short paragraph; the rest is under "How we know"
        .concat(paras.length > 1 || numbers ? [h('details', { class: 'how-we-know' }, [h('summary', null, 'How we know')]
          .concat(paras.slice(1).map(function (p) { return h('p', null, p); }))
          .concat(numbers ? [h('p', { class: 'fg-num' }, numbers)] : []))] : [])));
    }
    // Q1
    var lows = dd.filter(function (d) { return d >= 0.4 && d <= 0.8; }).map(function (d) { return at(cv4, 'recog', d); });
    var q1head = q1.verdict === 'retraces' ? 'Forgetting runs its training backwards'
      : q1.verdict === 'closer' || q1.verdict === 'further' ? 'It walks back toward scribbles, but off the road it came by'
        : 'It walks back toward scribbles, but not clearly along the road it came by';
    card('fg-q1', q1head, [
      'With more neurons switched off, its drawings look like earlier and earlier stages of its training. Drawing with normal randomness, with a tenth switched off they look most like step ' +
        steps(lookStep(0.1)) + ' of 102,400; with three tenths, like step ' + steps(lookStep(0.3)) + '.',
      'But it doesn’t pass through quite the same places. From about a fifth switched off, its scribbles look more like people’s typical chair than the learning model’s did when they were just as hard to name. ' +
        (q1.verdict === 'unclear' ? 'In the three runs we kept for the test, that gap is too close to call' : 'In the three runs we kept for the test, the gap is clear') +
        (q1a && q1a.verdict !== q1.verdict ? '; with the first run added, it is clear.' : '.'),
      'Drawing with low randomness it goes where training never went: with 40 to 80% switched off, only ' + pct(Math.min.apply(null, lows)) + ' to ' +
        pct(Math.max.apply(null, lows)) + ' of its drawings can be named as chairs, fewer than the untrained model’s scribbles (' + pct(learn4) + ').'],
      'How far it sits from the learning road, at the same share named as chairs (0 = on the road; measured as how different pictures look to DINOv2): ' +
        signed(q1.mean, f3) + ', ' + likely(q1.t_ci95, f3) + ' (' + q1.n_seeds + ' runs)' +
        (q1a ? '; with the first run, ' + signed(q1a.mean, f3) + ', ' + likely(q1a.t_ci95, f3) : '') + '.');
    // Q2
    var q2 = t1.q2_primary, q2g = t1.q2_variety_gap, v1 = cv1.spread.mean, v4 = cv4.spread.mean;
    var min4 = Math.min.apply(null, v4.filter(function (v) { return v != null; })), i4 = v4.indexOf(min4);
    var top1 = t1.q2_variety_change['0.90'];
    card('fg-q2', 'Its drawings first grow alike, then scatter', [
      'As the damage spreads, its chairs turn into the same kind of scribble. Drawing with low randomness, its 16 drawings become one diagonal staircase: with ' +
        offTxt(dd[i4]) + ' switched off, its drawings differ from one another only about ' + Math.round(100 * min4 / v4[0]) + '% as much as the healthy model’s do (' +
        f2(min4) + ' against ' + f2(v4[0]) + ').',
      'Once nearly every neuron is off, the scribbles scatter again' + (top1 && top1.verdict === 'more varied' ? ', and with 90% off they are more varied than the healthy model’s.' : '.'),
      'Our planned test looked at the point where it has lost about half of what it learned (' + offTxt(half) + ' switched off, normal randomness). There the change is ' +
        (q2.verdict === 'no clear change' ? 'too close to call.' : q2.verdict === 'less varied' ? 'clearly toward alike.' : 'clearly toward more varied.')],
      'Change in how different the drawings are from one another (we call this spread), at ' + offTxt(half) + ' off: ' + signed(q2.mean, f3) + ', ' +
        likely(q2.t_ci95, f3) + '. Against the learning model when just as hard to name: ' + signed(q2g.mean, f3) + ', ' + likely(q2g.t_ci95, f3) + '.');
    // Q3
    var q3 = t1.q3_primary, sk = q3.shape_kept.mean, dk = q3.detail_kept.mean;
    var ls = t1.q3_learning_share, ls4 = t4.q3_learning_share, k100 = F.learn_steps.indexOf(100);
    var q3head = q3.verdict === 'details go first' ? 'The details go before the overall shape'
      : q3.verdict === 'shape goes first' ? 'The overall shape goes before the details' : 'The details and the overall shape go together';
    card('fg-q3', q3head, [
      'With ' + offTxt(half) + ' of its neurons switched off, its drawings keep ' + Math.round(100 * sk) + '% of the overall shape training gave them, but only ' +
        Math.round(100 * dk) + '% of the details, such as a back’s slats or a seat’s edge.',
      'To tell them apart, we blurred each drawing until only its rough outline was left and compared it with the nearest of 1,000 people’s chairs. Then we did the same with its sharp lines.',
      'Learning did not simply build them in the opposite order. With normal randomness, the details came about as early as the shape (at step 100: ' +
        Math.round(100 * ls.detail[k100]) + '% of the details, ' + Math.round(100 * ls.shape[k100]) + '% of the shape). With low randomness the shape came first (' +
        Math.round(100 * ls4.shape[k100]) + '% against ' + Math.round(100 * ls4.detail[k100]) + '%), so there the last thing in was the first thing out.'],
      'Shape kept minus details kept, at ' + offTxt(half) + ' off: ' + signed(q3.mean) + ', ' + likely(q3.t_ci95) + ' (' + q3.n_seeds + ' runs, all three the same way).');
    // noise
    var n4 = F.tests['t0.4'].noise.test_seeds.q1_distance_gap, n1 = F.tests['t1.0'].noise.test_seeds.q1_distance_gap, nc = F.forget['t1.0'].noise;
    var kmax = F.arms.noise[F.arms.noise.length - 1];
    card('fg-noise', 'Noise makes it forget more like a film of its training run backwards', [
      'Instead of switching neurons off, we added random noise to every one of them. The model held up far better: with noise ' + kmax +
        ' times as large as each neuron’s usual swing, ' + pct(nc.recog.mean[nc.recog.mean.length - 1]) + ' of its drawings could still be named as chairs.',
      'And this kind of forgetting stays on the learning road. ' + (n4.verdict === 'retraces' ? 'Drawing with low randomness it passes through the same places as learning did. ' : '') +
        (n1.verdict === 'retraces' ? 'With normal randomness too.' : 'With normal randomness, whether it stays on the road is too close to call.')],
      'Distance from the learning road with noise: low randomness ' + signed(n4.mean, f3) + ', ' + likely(n4.t_ci95, f3) + '; normal randomness ' +
        signed(n1.mean, f3) + ', ' + likely(n1.t_ci95, f3) + '.');
    app.appendChild(box);
  }

  // ---------- charts ----------
  function chartBox(parent, title, sub) {
    var fig = h('figure', { class: 'fg-panel' }, [h('figcaption', null, [h('b', null, title), sub ? h('span', null, sub) : null])]);
    var inner = h('div', { class: 'fg-chart' });
    fig.appendChild(inner);
    parent.appendChild(fig);
    return inner;
  }
  function yTicks(lo, hi, n) {
    var step = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(step)));
    var nice = [1, 2, 2.5, 5, 10].map(function (k) { return k * mag; }).filter(function (k) { return k >= step; })[0];
    var out = [];
    for (var v = Math.ceil(lo / nice) * nice; v <= hi + 1e-9; v += nice) out.push(+v.toFixed(6));
    return out;
  }

  function pathChart(parent) {
    var L = F.learn[temp], cv = curve(temp), dd = F.display_doses, st = F.learn_steps;
    var box = chartBox(parent, 'The road in and the road out', 'Each dot is the model at one stage: how many of its drawings an AI can name as chairs, and how different they look from people’s typical chair.');
    var narrow = box.clientWidth < 560;  // phones: a squarer chart with larger type
    var W = narrow ? 460 : 860, H = narrow ? 440 : 470, Lm = narrow ? 58 : 64, R = narrow ? 18 : 28, Tm = 14, Bm = 56;
    var ys = [], all = L.d_adult.mean.concat(cv.d_adult.mean).filter(function (v) { return v != null; });
    var lo = Math.max(0, Math.min.apply(null, all) - 0.03), hi = Math.max.apply(null, all) + 0.03;
    var xs = function (r) { return Lm + (W - Lm - R) * r; };
    var yv = function (d) { return Tm + (H - Tm - Bm) * (hi - d) / (hi - lo); };
    var s = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'fg-road' + (narrow ? ' fg-narrow' : ''), role: 'img', 'aria-label': 'Learning (blue) and forgetting (orange) as paths: how many drawings can be named as chairs against how different they look from people’s typical chair' }, box);
    var tip = tipper(box);
    yTicks(lo, hi, 5).forEach(function (v) {
      svg('line', { x1: Lm, x2: W - R, y1: yv(v), y2: yv(v), style: paint('stroke', '--chart-grid') }, s);
      label(s, Lm - 6, yv(v) + 4, v.toFixed(2), { 'text-anchor': 'end', class: 'fg-tick' });
    });
    (narrow ? [0, 0.5, 1] : [0, 0.25, 0.5, 0.75, 1]).forEach(function (v) {
      svg('line', { x1: xs(v), x2: xs(v), y1: Tm, y2: H - Bm, style: paint('stroke', '--chart-grid') }, s);
      label(s, xs(v), H - Bm + 16, pct(v), { 'text-anchor': 'middle', class: 'fg-tick' });
    });
    label(s, (Lm + W - R) / 2, H - 12, narrow ? 'Named as a chair →' : 'Drawings an AI could name as a chair →', { 'text-anchor': 'middle', class: 'fg-lbl' });
    label(s, 14, (Tm + H - Bm) / 2, narrow ? 'Unlike people’s chair →' : 'More different from people’s typical chair →', { 'text-anchor': 'middle', class: 'fg-lbl', transform: 'rotate(-90 14 ' + (Tm + H - Bm) / 2 + ')' });
    function pts(rs, ds) {
      return rs.map(function (r, k) { return r == null || ds[k] == null ? null : [xs(r), yv(ds[k])]; });
    }
    function line(p, token, dash) {
      var d = p.filter(Boolean).map(function (q, k) { return (k ? 'L' : 'M') + q[0].toFixed(1) + ' ' + q[1].toFixed(1); }).join('');
      svg('path', { d: d, fill: 'none', 'stroke-width': 2.4, 'stroke-linejoin': 'round', 'stroke-dasharray': dash || 'none', style: paint('stroke', token) }, s);
    }
    var pl = pts(L.recog.mean, L.d_adult.mean), pf = pts(cv.recog.mean, cv.d_adult.mean);
    line(pl, '--blue');
    line(pf, '--orange');
    function dots(p, token, tipFor) {
      p.forEach(function (q, k) {
        if (!q) return;
        svg('circle', { cx: q[0], cy: q[1], r: 3.6, 'stroke-width': 1.5, style: paint('fill', token) + ';' + paint('stroke', '--chart-halo') }, s);
        var hit = svg('circle', { cx: q[0], cy: q[1], r: 9, fill: 'transparent' }, s);
        hit.addEventListener('mousemove', function (e) { tip.show(e, tipFor(k)); });
        hit.addEventListener('mouseleave', tip.hide);
      });
    }
    dots(pl, '--blue', function (k) {
      return '<b>Learning: step ' + steps(st[k]) + '</b><br>' + pct(L.recog.mean[k]) + ' named as chairs<br>Different from people’s chair: ' + f3(L.d_adult.mean[k]);
    });
    dots(pf, '--orange', function (k) {
      return '<b>' + offTxt(dd[k]) + ' of its neurons switched off</b><br>' + pct(cv.recog.mean[k]) + ' named as chairs<br>Different from people’s chair: ' +
        f3(cv.d_adult.mean[k]) + (dd[k] ? '<br>Looks most like step ' + steps(cv.looks_like_step[k]) + ' of training' : '');
    });
    function tag(q, s0, anchor, dx, dy, token) {
      if (!q) return;
      label(s, q[0] + dx, q[1] + dy, s0, { 'text-anchor': anchor, class: 'fg-lbl-strong', style: paint('fill', token) });
    }
    tag(pl[0], 'untrained', 'start', 8, -8, '--ink');
    tag(pl[pl.length - 1], 'fully trained', 'end', -8, 20, '--ink');
    [[0.1, '10% off'], [0.3, '30% off'], [1, '100% off']].forEach(function (x) {
      var k = dd.indexOf(x[0]);
      if (k >= 0) tag(pf[k], x[1], 'start', 8, 4, '--ink-2');
    });
    var mk = svg('circle', { r: 8, 'stroke-width': 3, fill: 'none', style: paint('stroke', '--ink') }, s);
    markers.push(function (f) {
      var q = f.kind === 'learn' ? pl[f.k] : pf[f.k];
      if (!q) { mk.setAttribute('opacity', 0); return; }
      mk.setAttribute('cx', q[0]);
      mk.setAttribute('cy', q[1]);
      mk.setAttribute('opacity', 1);
    });
  }

  function doseChart(parent, title, sub, series, yfmt, refs, yd) {
    var dd = F.display_doses, box = chartBox(parent, title, sub);
    var narrow = box.clientWidth < 420;
    var W = 420, H = narrow ? 330 : 300, Lm = 48, R = 96, Tm = 12, Bm = 46;
    var vals = [];
    series.forEach(function (sr) { sr.v.forEach(function (v, k) { if (v != null) vals.push(v); if (sr.ci && sr.ci[k] && sr.ci[k][0] != null) vals.push(sr.ci[k][0], sr.ci[k][1]); }); });
    refs.forEach(function (r) { vals.push(r[1]); });
    var lo = yd ? yd[0] : Math.min.apply(null, vals), hi = yd ? yd[1] : Math.max.apply(null, vals), pad = yd ? 0 : (hi - lo) * 0.08;
    lo -= pad; hi += pad;
    var xs = function (d) { return Lm + (W - Lm - R) * d; }, yv = function (v) { return Tm + (H - Tm - Bm) * (hi - v) / (hi - lo); };
    var s = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, class: narrow ? 'fg-narrow' : null, role: 'img', 'aria-label': title + ', by the share of neurons switched off' }, box);
    var tip = tipper(box);
    yTicks(lo, hi, 4).forEach(function (v) {
      svg('line', { x1: Lm, x2: W - R, y1: yv(v), y2: yv(v), style: paint('stroke', '--chart-grid') }, s);
      label(s, Lm - 6, yv(v) + 4, yfmt(v), { 'text-anchor': 'end', class: 'fg-tick' });
    });
    [0, 0.25, 0.5, 0.75, 1].forEach(function (v) { label(s, xs(v), H - Bm + 16, pct(v), { 'text-anchor': 'middle', class: 'fg-tick' }); });
    label(s, (Lm + W - R) / 2, H - 10, 'Neurons switched off', { 'text-anchor': 'middle', class: 'fg-lbl' });
    var rl = refs.map(function (r) { return { name: r[0], y: yv(r[1]), ly: yv(r[1]) + 4, dash: r[2] }; }).sort(function (a, b) { return a.y - b.y; });
    rl.forEach(function (r, k) { if (k && r.ly - rl[k - 1].ly < 13) r.ly = rl[k - 1].ly + 13; });
    rl.forEach(function (r) {
      svg('line', { x1: Lm, x2: W - R, y1: r.y, y2: r.y, 'stroke-width': 1.3, 'stroke-dasharray': r.dash, style: paint('stroke', '--faint') }, s);
      label(s, W - R + 5, r.ly, r.name, { class: 'fg-lbl', 'font-size': 11 });
    });
    series.forEach(function (sr) {
      var idx = sr.x.map(function (d, k) { return k; }).filter(function (k) { return sr.v[k] != null; });
      if (sr.ci) {
        var ok = idx.filter(function (k) { return sr.ci[k] && sr.ci[k][0] != null; });
        if (ok.length > 1) {
          var band = ok.map(function (k, j) { return (j ? 'L' : 'M') + xs(sr.x[k]) + ' ' + yv(sr.ci[k][1]); }).join('') +
            ok.slice().reverse().map(function (k) { return 'L' + xs(sr.x[k]) + ' ' + yv(sr.ci[k][0]); }).join('') + 'Z';
          svg('path', { d: band, opacity: 0.16, style: paint('fill', sr.token) }, s);
        }
      }
      svg('path', { d: idx.map(function (k, j) { return (j ? 'L' : 'M') + xs(sr.x[k]) + ' ' + yv(sr.v[k]); }).join(''), fill: 'none', 'stroke-width': 2.2,
        'stroke-linejoin': 'round', 'stroke-dasharray': sr.dash || 'none', style: paint('stroke', sr.token) }, s);
      idx.forEach(function (k) { svg('circle', { cx: xs(sr.x[k]), cy: yv(sr.v[k]), r: 3, 'stroke-width': 1.2, style: paint('fill', sr.token) + ';' + paint('stroke', '--chart-halo') }, s); });
      if (sr.name) {
        var kl = idx[idx.length - 1];
        label(s, xs(sr.x[kl]) + 6, yv(sr.v[kl]) + (sr.dy || 4), sr.name, { class: 'fg-lbl-strong', 'font-size': 11 });
      }
    });
    var cross = svg('line', { x1: 0, x2: 0, y1: Tm, y2: H - Bm, opacity: 0, style: paint('stroke', '--ink-2') }, s);
    dd.forEach(function (d, k) {
      var x0 = k ? (xs(dd[k - 1]) + xs(d)) / 2 : Lm, x1 = k < dd.length - 1 ? (xs(d) + xs(dd[k + 1])) / 2 : W - R;
      var hit = svg('rect', { x: x0, y: Tm, width: Math.max(1, x1 - x0), height: H - Tm - Bm, fill: 'transparent' }, s);
      hit.addEventListener('mousemove', function (e) {
        cross.setAttribute('x1', xs(d)); cross.setAttribute('x2', xs(d)); cross.setAttribute('opacity', 0.5);
        tip.show(e, '<b>' + offTxt(d) + ' switched off</b>' + series.map(function (sr) {
          var j = sr.x.indexOf(d);
          return j < 0 || sr.v[j] == null ? '' : '<br>' + (sr.label || sr.name) + ': ' + yfmt(sr.v[j]) +
            (sr.ci && sr.ci[j] && sr.ci[j][0] != null ? ' (probably ' + yfmt(sr.ci[j][0]) + ' to ' + yfmt(sr.ci[j][1]) + ')' : '');
        }).join(''));
      });
      hit.addEventListener('mouseleave', function () { tip.hide(); cross.setAttribute('opacity', 0); });
    });
    var mk = svg('line', { y1: Tm, y2: H - Bm, 'stroke-width': 2, opacity: 0, style: paint('stroke', '--orange') }, s);
    markers.push(function (f) {
      if (f.kind !== 'forget') { mk.setAttribute('opacity', 0); return; }
      mk.setAttribute('x1', xs(f.dose)); mk.setAttribute('x2', xs(f.dose)); mk.setAttribute('opacity', 0.55);
    });
  }

  function charts(wrap) {
    wrap.innerHTML = '';
    markers = [];
    var grid = h('div', { class: 'fg-charts' });
    wrap.appendChild(grid);
    pathChart(grid);
    var cv = curve(temp), dd = F.display_doses;
    doseChart(grid, 'How different its drawings are from one another', 'Average of the four runs, with a band where the true value probably lies.',
      [{ x: dd, v: cv.spread.mean, ci: cv.spread.ci95, token: '--orange', label: 'Its drawings' }], f2,
      [['people’s chairs', F.reference.spread, '5 4'], ['untrained', F.learn[temp].spread.mean[0], '2 3']]);
    var q3 = T(temp).q3_shape_minus_detail, qd = [0].concat(Object.keys(q3).map(Number));
    var get = function (key) { return [1].concat(Object.keys(q3).map(function (d) { return q3[d][key].mean; })); };
    doseChart(grid, 'What is left of what training built', 'The overall shape, and the details. 100% = the healthy model; 0% = the untrained model. Average of the three test runs.',
      [{ x: qd, v: get('shape_kept'), token: '--ink', name: 'overall shape', label: 'Overall shape', dy: -4 },
       { x: qd, v: get('detail_kept'), token: '--orange', dash: '6 4', name: 'details', label: 'Details', dy: 12 }],
      function (v) { return Math.round(100 * v) + '%'; }, [], [-0.05, 1.05]);
  }

  function chartsSection() {
    var tabs = h('div', { class: 'ls-tabs', role: 'tablist', 'aria-label': 'Randomness setting' });
    var wrap = h('div');
    function draw() {
      tabs.innerHTML = '';
      TEMPS.forEach(function (t) {
        var b = h('button', { type: 'button', role: 'tab', 'aria-selected': t[0] === temp ? 'true' : 'false' }, t[1]);
        b.addEventListener('click', function () { temp = t[0]; draw(); });
        tabs.appendChild(b);
      });
      charts(wrap);
      table();
      if (lastFrame) markers.forEach(function (m) { m(lastFrame); });
    }
    app.appendChild(h('h3', { class: 'fg-h3' }, 'The road in and the road out, measure by measure'));
    app.appendChild(h('p', { class: 'ls-sub' }, 'Blue is the model learning, from its untrained start to step 102,400. Orange is the same model, fully trained, as we switch off more of its neurons. ' +
      'The randomness setting decides how boldly it draws; the pictures above use low randomness. The circle follows the player.'));
    app.appendChild(tabs);
    app.appendChild(wrap);
    var tbl = h('details', { class: 'ls-numbers fg-numbers' }, [h('summary', null, 'The numbers, level by level')]);
    var tbox = h('div');
    tbl.appendChild(tbox);
    app.appendChild(tbl);
    function table() {
      var cv = curve(temp), dd = F.display_doses;
      tbox.innerHTML = '';
      var rows = dd.map(function (d, k) {
        return h('tr', null, [h('td', { class: 'num' }, offTxt(d)), h('td', { class: 'num' }, pct(cv.recog.mean[k])), h('td', { class: 'num' }, f3(cv.d_adult.mean[k])),
          h('td', { class: 'num' }, f3(cv.spread.mean[k])), h('td', { class: 'num' }, cv.n.mean[k] == null ? '–' : String(Math.round(200 - cv.n.mean[k]))),
          h('td', { class: 'num' }, cv.looks_like_step[k] == null ? '–' : steps(cv.looks_like_step[k]))]);
      });
      tbox.appendChild(h('div', null, h('table', null, [h('thead', null, h('tr', null, ['Neurons switched off', 'Named as chairs', 'Different from people’s typical chair',
        'Different from one another', 'Only a dot (of 200)', 'Looks most like training step'].map(function (x) { return h('th', { class: 'num' }, x); }))),
        h('tbody', null, rows)])));
      tbox.appendChild(h('p', { class: 'ls-note' }, (temp === 't0.4' ? 'Low' : 'Normal') + ' randomness. Each number is the average of the four runs, 200 drawings each. ' +
        'Distances are how different pictures look to a Meta AI that compares pictures (DINOv2): 0 means identical.'));
      var trows = [];
      TEMPS.forEach(function (t) {
        ['silence', 'noise', 'readout'].forEach(function (arm) {
          var b = F.tests[t[0]][arm].test_seeds;
          if (!b) return;
          var what = { silence: 'switched off', noise: 'noise added', readout: 'cut off from the pen' }[arm];
          [['Q1 off the learning road', b.q1_distance_gap, f3], ['Q2 change in variety', b.q2_primary, f3], ['Q3 shape kept minus details kept', b.q3_primary, f2]].forEach(function (q) {
            var r = q[1];
            if (!r) return;
            var sg = function (v) { return signed(v, q[2]); };
            trows.push(h('tr', null, [h('td', null, q[0]), h('td', null, t[0] === 't0.4' ? 'low' : 'normal'), h('td', null, what),
              h('td', { class: 'num' }, sg(r.mean)), h('td', { class: 'num' }, '[' + sg(r.t_ci95[0]) + ', ' + sg(r.t_ci95[1]) + ']'),
              h('td', { class: 'num' }, '[' + sg(r.boot_ci95[0]) + ', ' + sg(r.boot_ci95[1]) + ']'), h('td', null, r.verdict)]));
          });
        });
      });
      tbox.appendChild(h('div', null, h('table', null, [h('thead', null, h('tr', null, ['Question', 'Randomness', 'Damage', 'Result', 'Likely range (runs)',
        'Likely range (runs and drawings)', 'Verdict'].map(function (x, k) { return h('th', { class: k >= 3 && k <= 5 ? 'num' : null }, x); }))), h('tbody', null, trows)])));
      tbox.appendChild(h('p', { class: 'ls-note' }, 'The three runs kept for the test (the first run, shown in the pictures, is left out, as in the learning test). ' +
        'Likely ranges are 95% intervals: across runs, and resampling runs and drawings. A verdict needs both. Q2 and Q3 are measured where it has lost about half of what it learned, by how many drawings can be named as chairs. ' +
        'Q1 counts as “retraces” only if both ranges stay within ±0.03.'));
    }
    draw();
    var lastW = window.innerWidth, rt = 0;
    window.addEventListener('resize', function () {  // the charts pick their shape from their width
      clearTimeout(rt);
      rt = setTimeout(function () { if (window.innerWidth !== lastW) { lastW = window.innerWidth; charts(wrap); if (lastFrame) markers.forEach(function (m) { m(lastFrame); }); } }, 200);
    });
  }

  function method() {
    app.appendChild(h('details', { class: 'ls-numbers fg-method' }, [h('summary', null, 'How we did it'), h('ul', null, [
      h('li', null, 'The model is the larger sketch model above, at the end of its training, in all four of its runs. We wrote down the three questions and how we would answer them before it drew anything damaged.'),
      h('li', null, 'Switching off a neuron means its output is set to zero every time the model takes a step with its pen, so it can no longer affect the next stroke. The neurons go in a random order that is fixed for each run, so every neuron off at 20% is also off at 30%. Nothing in the model is changed for good: the damage is removed after each set of drawings, and the model then draws exactly what it drew before.'),
      h('li', null, 'Each run drew 200 chairs at each level of damage, from the same random starting points as when it learned. A Meta AI that compares pictures (DINOv2) judged them, exactly as in “Watch an AI learn”.'),
      h('li', null, 'Two other kinds of damage: random noise added to every neuron, scaled to how much that neuron usually varies; and cutting the neurons off only from the pen, while they still pass messages to each other. Cut off from the pen only, it holds up a little longer at first.'),
      h('li', null, 'Comparisons with people are analogies, not claims about brains. In semantic dementia, people’s drawings also lose the details that set a thing apart before its overall shape; that is a different kind of damage in a different kind of mind.'),
      h('li', null, [document.createTextNode('Plan: '), h('a', { href: 'https://github.com/rnorlund/MetaLesionLab/blob/main/docs/plato_sketch_forget_plan.md' }, 'docs/plato_sketch_forget_plan.md'),
        document.createTextNode('. Write-up: '), h('a', { href: 'https://github.com/rnorlund/MetaLesionLab/blob/main/docs/plato_sketch_forget.md' }, 'docs/plato_sketch_forget.md'),
        document.createTextNode('. Data: '), h('a', { href: '/api/plato/lifespan/forget' }, 'the statistics behind this section'), document.createTextNode('.')])])]));
  }

  TOT.api('/api/plato/lifespan/forget').then(function (data) {
    F = data;
    app.innerHTML = '';
    player();
    findings();
    chartsSection();
    method();
  }).catch(function (e) {
    app.innerHTML = '';
    app.appendChild(h('p', { class: 'ls-note' }, 'The forgetting results didn’t load: ' + (e && e.message ? e.message : e)));
  });
})();
