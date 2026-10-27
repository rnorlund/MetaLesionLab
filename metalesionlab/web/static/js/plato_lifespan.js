/* The life of a chair (/plato/lifespan): children aged 2-10, adults, Muse Image, Stable Diffusion's training
   stages and a sketch model trained from scratch. Reads /api/plato/lifespan (public_data/plato_lifespan.json,
   group-level statistics only). No child's drawing is ever shown: children's stages are drawn as icon arrays. */
(function () {
  'use strict';
  var h = TOT.h;
  var SVGNS = 'http://www.w3.org/2000/svg';
  var C = { people: '#C2410C', sd: '#0D9488', muse: '#1D4ED8', ink: '#111827', ink2: '#374151', muted: '#6B7280',
            grid: '#E1E0D9', axis: '#C3C2B7', track: '#E5E3DC', chart: '#FCFCFB', sketch: '#374151' };
  var CK = ['v1.1', 'v1.2', 'v1.3', 'v1.4', 'v1.5'];
  var KSTEPS = { 'v1.1': 0.431, 'v1.2': 0.946, 'v1.3': 1.141, 'v1.4': 1.171, 'v1.5': 1.541 };
  var AGES = [2, 3, 4, 5, 6, 7, 8, 9, 10];
  var LABEL = { sailboat: 'boat (sailboat)', bicycle: 'bicycle' };
  var MEASURES = [
    { key: 'recog', name: 'Recognizable', fmt: pct, lo: 0, hi: 1,
      sub: 'How often a drawing sits closest to its own thing’s adult average, out of 21 things (chance 5%). Higher is more recognizable.' },
    { key: 'd_adult', name: 'Distance to the adult Form', fmt: f2, lo: 0.1, hi: 0.7,
      sub: 'How far a typical drawing is from the average of 200 adults’ drawings (cosine distance in Meta’s DINOv2). Lower is closer.' },
    { key: 'spread', name: 'Variety', fmt: f2, lo: 0.1, hi: 0.6,
      sub: 'How far apart drawings of the same thing are from each other, in sets of 16. Lower is more alike.' },
    { key: 'd_muse', name: 'Distance to Muse’s Form', fmt: f2, lo: 0.05, hi: 0.9,
      sub: 'How far a typical drawing is from the average of Muse Image’s doodles. Lower is closer to the AI’s chair.' }
  ];
  var D = null, thing = 'chair', stop = 0, measure = 'recog';
  var STOPS = AGES.map(function (a) { return { kind: 'kid', age: a, tick: String(a), cls: 'kid' }; })
    .concat([{ kind: 'adult', tick: 'adults', cls: 'adult' }, { kind: 'muse', tick: 'Muse', cls: 'muse' }])
    .concat(CK.map(function (c) { return { kind: 'sd', ck: c, tick: c, cls: 'sd' }; }))
    .concat([{ kind: 'damage', tick: 'damaged', cls: 'damage' }]);

  function pct(x) { return x == null || isNaN(x) ? '–' : Math.round(100 * x) + '%'; }
  function f2(x) { return x == null || isNaN(x) ? '–' : x.toFixed(2); }
  function f3(x) { return x == null || isNaN(x) ? '–' : x.toFixed(3); }
  function signed(x, fmt) { return (x > 0 ? '+' : x < 0 ? '−' : '') + fmt(Math.abs(x)); }
  function pts(x) { return (x > 0 ? '+' : x < 0 ? '−' : '') + Math.round(Math.abs(100 * x)) + ' points'; }
  function ciTxt(c, fmt) { return c ? '[' + fmt(c[0]) + ', ' + fmt(c[1]) + ']' : ''; }
  function ciPts(c) { return c ? '[' + signed(100 * c[0], function (v) { return v.toFixed(0); }) + ', ' +
    signed(100 * c[1], function (v) { return v.toFixed(0); }) + ']' : ''; }
  function svg(tag, attrs, parent) {
    var el = document.createElementNS(SVGNS, tag);
    Object.keys(attrs || {}).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(el);
    return el;
  }
  function text(parent, x, y, s, attrs) {
    var t = svg('text', Object.assign({ x: x, y: y, class: 'tick' }, attrs || {}), parent);
    t.textContent = s;
    return t;
  }
  function label(k) { return LABEL[k] || k; }
  function mean(xs) { var v = xs.filter(function (x) { return x != null && !isNaN(x); });
    return v.length ? v.reduce(function (a, b) { return a + b; }, 0) / v.length : NaN; }

  // ---------- data access: one value per stop, for one thing or the mean over the 20 things ----------
  function things() { return D.children.things; }
  function cellFor(s, k) {
    if (s.kind === 'kid') return D.children.cells[k][String(s.age)];
    if (s.kind === 'adult') return D.adults.cells[k];
    if (s.kind === 'muse') return D.muse.cells[k];
    if (s.kind === 'sd') return (D.ai.cells[k] || {})[s.ck];
    return null;
  }
  function value(s, m) {
    if (s.kind === 'damage') return NaN;
    if (thing !== 'mean') { var c = cellFor(s, thing); return c ? c[m] : NaN; }
    return mean(things().map(function (k) { var c = cellFor(s, k); return c ? c[m] : NaN; }));
  }
  function nFor(s) {
    if (thing === 'mean') return null;
    var c = cellFor(s, thing);
    return c ? c.n : null;
  }
  function color(s) { return s.kind === 'muse' ? C.muse : s.kind === 'sd' ? C.sd : s.kind === 'damage' ? C.muted : C.people; }

  // ---------- tooltip ----------
  function tipper(box) {
    var tip = h('div', { class: 'ls-tip', hidden: true });
    box.appendChild(tip);
    return {
      show: function (evt, html) {
        tip.innerHTML = html;
        tip.hidden = false;
        var r = box.getBoundingClientRect();
        var x = evt.clientX - r.left + 12, y = evt.clientY - r.top + 12;
        if (x + 240 > r.width) x = Math.max(0, evt.clientX - r.left - 252);
        tip.style.left = x + 'px';
        tip.style.top = y + 'px';
      },
      hide: function () { tip.hidden = true; }
    };
  }

  // ---------- icon array: ten little chairs, k of them solid ----------
  function iconArray(share, col, title) {
    var k = Math.round(10 * share);
    var s = svg('svg', { viewBox: '0 0 300 132', class: 'ls-icons', role: 'img', 'aria-label': title });
    for (var i = 0; i < 10; i++) {
      var x = 10 + (i % 5) * 58, y = 8 + Math.floor(i / 5) * 64;
      var c = i < k ? col : C.track;
      var g = svg('g', { fill: 'none', stroke: c, 'stroke-width': 4.5, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, s);
      svg('path', { d: 'M' + (x + 12) + ' ' + (y + 28) + 'V' + (y + 4) + 'H' + (x + 36) + 'V' + (y + 28) }, g);
      svg('path', { d: 'M' + (x + 6) + ' ' + (y + 30) + 'H' + (x + 42) }, g);
      svg('path', { d: 'M' + (x + 10) + ' ' + (y + 30) + 'V' + (y + 54) + 'M' + (x + 38) + ' ' + (y + 30) + 'V' + (y + 54) }, g);
    }
    return s;
  }

  // ---------- the timeline ----------
  function thingSelect() {
    var sel = document.getElementById('thing');
    sel.appendChild(h('option', { value: 'mean' }, 'All 20 things (mean)'));
    things().forEach(function (k) { sel.appendChild(h('option', { value: k }, label(k))); });
    sel.value = thing;
    sel.addEventListener('change', function () { thing = sel.value; renderAll(); });
  }

  function ticks() {
    var box = document.getElementById('ticks');
    box.innerHTML = '';
    STOPS.forEach(function (s, i) {
      // on phones only a few labels fit: ages 2, 4, 6, 8, 10 and the first and last Stable Diffusion stage
      var minor = (s.kind === 'kid' && s.age % 2 === 1) || s.kind === 'adult' || s.kind === 'muse' || s.kind === 'damage' ||
        (s.kind === 'sd' && s.ck !== 'v1.1' && s.ck !== 'v1.5') ? ' minor' : '';
      box.appendChild(h('span', { class: 'grp ' + s.cls + minor + (i === stop ? ' on' : '') }, s.tick));
    });
  }

  function stopName(s) {
    if (s.kind === 'kid') return 'Age ' + s.age;
    if (s.kind === 'adult') return 'Adults';
    if (s.kind === 'muse') return 'Muse Image';
    if (s.kind === 'sd') return 'Stable Diffusion ' + s.ck;
    return 'A damaged AI';
  }
  function stopWho(s) {
    var n = nFor(s);
    if (s.kind === 'kid') return (n ? n + ' drawings by ' : 'Drawings by ') + s.age + '-year-olds at a museum kiosk';
    if (s.kind === 'adult') return '200 Quick, Draw! players, 20 seconds each. Their average is the adult Form.';
    if (s.kind === 'muse') return 'Meta’s Muse Image, asked for a quick doodle';
    if (s.kind === 'sd') return '16 pictures from the same 16 seeds at every stage; ' + KSTEPS[s.ck].toFixed(2) +
      ' million training steps' + (s.ck === 'v1.1' ? '' : s.ck === 'v1.2' ? ', resumed from v1.1' : ', resumed from v1.2');
    return 'The end of the lifespan, by analogy only';
  }

  function meter(m, s) {
    var v = value(s, m.key);
    var W = 300, H = 34, pad = 6;
    var x = function (val) { return pad + (W - 2 * pad) * (val - m.lo) / (m.hi - m.lo); };
    var box = h('div', { class: 'ls-meter' });
    box.appendChild(h('div', { class: 'top' }, [h('span', null, m.name), h('b', null, isNaN(v) ? '–' : m.fmt(v))]));
    var g = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img',
                         'aria-label': m.name + ' at every stage; this one ' + m.fmt(v) });
    svg('line', { x1: pad, x2: W - pad, y1: 17, y2: 17, stroke: C.grid, 'stroke-width': 2, 'stroke-linecap': 'round' }, g);
    STOPS.forEach(function (o) {
      if (o.kind === 'damage' || o === s) return;
      var ov = value(o, m.key);
      if (isNaN(ov)) return;
      svg('circle', { cx: x(Math.max(m.lo, Math.min(m.hi, ov))), cy: 17, r: 3.5, fill: color(o), opacity: 0.28 }, g);
    });
    if (!isNaN(v)) svg('circle', { cx: x(Math.max(m.lo, Math.min(m.hi, v))), cy: 17, r: 8, fill: color(s), stroke: '#FFFFFF', 'stroke-width': 2.5 }, g);
    box.appendChild(g);
    box.appendChild(h('p', { class: 'hint ends' }, [h('span', null, m.fmt(m.lo)), h('span', null, m.fmt(m.hi))]));
    return box;
  }

  function renderStage() {
    var s = STOPS[stop];
    var pic = document.getElementById('pic'), read = document.getElementById('read');
    pic.innerHTML = '';
    read.innerHTML = '';
    var r = value(s, 'recog');
    if (s.kind === 'damage') {
      pic.appendChild(h('p', { class: 'ls-damage' }, ['Plato’s lifespan doesn’t end at the top. What happens to the chair when the AI is damaged? ',
        h('a', { href: '/plato/damage' }, 'Damage the painter'), ' shows it. Damage to the image model’s language part made the chair wander into other things (a room, a car, a person), never back to the plain chair; damage to its drawing part dissolved the lines but mostly kept the chair. This is an analogy, not a claim about people.']));
    } else {
      var src = null;
      if (thing === 'chair') {
        if (s.kind === 'adult') src = 'chair_adults';
        if (s.kind === 'muse') src = 'chair_muse';
        if (s.kind === 'sd') src = 'chair_sd_' + s.ck.replace('.', '');
      }
      if (src) {
        pic.appendChild(h('img', { src: '/static/img/plato_lifespan/' + src + '.webp', width: 812, height: 132,
          alt: s.kind === 'adult' ? 'Six adults’ chairs from Quick, Draw!, the most typical first' :
               s.kind === 'muse' ? 'Six of Muse Image’s chair doodles: the same slat-back chair' :
               'Six chairs drawn by Stable Diffusion ' + s.ck + ' from the same six seeds as every other stage' }));
      }
      pic.appendChild(iconArray(r, color(s), Math.round(10 * r) + ' in 10 drawings are recognizable'));
      var who = s.kind === 'kid' ? s.age + '-year-olds’' : s.kind === 'adult' ? 'adults’' : 'its';
      var noun = thing === 'mean' ? 'thing' : label(thing);
      var cap = [h('b', null, Math.round(10 * r) + ' in 10'), ' of ' + who + ' drawings ' +
        (thing === 'mean' ? 'are recognizable to the machine as what was asked for.' : 'look like a ' + noun + ' to the machine.')];
      if (s.kind === 'kid') cap.push(' Children’s drawings aren’t shown: they are licensed for non-commercial use, and they are children’s. These chairs stand for the numbers.');
      if (!src && s.kind !== 'kid' && thing !== 'chair') cap.push(' Pictures are shown for the chair only.');
      pic.appendChild(h('p', { class: 'ls-pic-cap' }, cap));
    }
    read.appendChild(h('h3', null, [h('span', { class: 'key', style: 'background:' + color(s) }), stopName(s)]));
    read.appendChild(h('p', { class: 'who' }, stopWho(s)));
    if (s.kind !== 'damage') {
      MEASURES.slice(0, 3).forEach(function (m) { read.appendChild(meter(m, s)); });
      read.appendChild(h('p', { class: 'hint' }, 'Faint dots: the other stages of life. Orange: people; blue: Muse Image; teal: Stable Diffusion.'));
    }
    document.getElementById('stop-label').textContent = stopName(s) + ' (' + (stop + 1) + ' of ' + STOPS.length + ')';
    var range = document.getElementById('stop');
    range.setAttribute('aria-valuetext', stopName(s));
    ticks();
  }

  // ---------- short answer ----------
  function renderAnswer() {
    var c = D.children, t = c.tests, ai = D.ai.all, at = ai.tests, cmp = D.comparison, sk = D.sketch;
    var ul = document.getElementById('answer-list');
    ul.innerHTML = '';
    var r = t.recog, da = t.d_adult, sp = t.spread;
    ul.appendChild(h('li', null, [h('b', null, 'Children walk toward the Form. '),
      'From age 2 to 10, drawings of 20 things become more recognizable (' + pct(c.curves.recog.mean[0]) + ' → ' +
      pct(c.curves.recog.mean[8]) + ', +' + (100 * r.linear.mean_slope).toFixed(1) + ' points a year [' +
      (100 * r.linear.ci95[0]).toFixed(1) + ', ' + (100 * r.linear.ci95[1]).toFixed(1) + ']' +
      ', for all 20 things) and closer to the adults’ average (' + f2(c.curves.d_adult.mean[0]) + ' → ' +
      f2(c.curves.d_adult.mean[8]) + '; adults ' + f2(D.adults.mean_over_children_things.d_adult) +
      '). Their variety narrows too, mostly before age 6. It doesn’t rise first, as we predicted.']));
    ul.appendChild(h('li', null, [h('b', null, 'They aren’t there at 10. '),
      '10-year-olds are still less recognizable than adults (' + pct(c.curves.recog.mean[8]) + ' vs ' +
      pct(D.adults.mean_over_children_things.recog) + ') and farther from the adult Form. By 10 they sit about as close to ' +
      'Muse Image’s chair as adults do.']));
    ul.appendChild(h('li', null, [h('b', null, 'Stable Diffusion doesn’t grow up the same way. '),
      'Its first public checkpoint, v1.1, is already as recognizable as a 10-year-old (' + pct(ai.curves.recog.mean[0]) +
      ' over 21 things). It gains ' + pts(at.recog.last_minus_first.mean) + ' by v1.5 ' +
      ciPts(at.recog.last_minus_first.ci95) + ', mostly at v1.2, and its variety narrows a little. But its pictures stay as far from people’s drawings at v1.5 as at v1.1 (' +
      f2(ai.curves.d_adult.mean[0]) + ' and ' + f2(ai.curves.d_adult.mean[4]) + '). For the 10 main things, and at a lower guidance setting, nothing changes clearly.']));
    if (sk) {
      var st = sk.steps['t1.0'], last = st[String(Math.max.apply(null, Object.keys(st).map(Number)))];
      ul.appendChild(h('li', null, [h('b', null, 'An AI that learns only from people’s chairs does grow up like a child. '),
        'A small sketch model trained from scratch starts at scribbles (' + pct(st['0'].recog) + ' recognizable), ' +
        'passes ' + pct(st['200'].recog) + ' after 200 steps, and ends at ' + pct(last.recog) + '. It ends ' +
        Math.round(100 * (1 - last.spread / sk.training_drawings.spread)) +
        '% less varied than the chairs it learned from (' + f2(last.spread) + ' vs ' + f2(sk.training_drawings.spread) +
        '): like Muse Image, it settles on the common chair.']));
    }
  }

  // ---------- two roads to the Form ----------
  function renderPaths() {
    var box = document.getElementById('paths-chart');
    box.innerHTML = '';
    var W = 760, H = 430, L = 56, R = 120, T = 16, B = 46;
    var xs = function (v) { return L + (W - L - R) * (v - 0.3) / 0.7; };
    var ys = function (v) { return T + (H - T - B) * (0.7 - v) / 0.55; };
    var s = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img',
      'aria-label': 'Recognizability against distance to the adult Form for children by age, adults, Muse Image and Stable Diffusion’s training stages' }, box);
    var tip = tipper(box);
    [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0].forEach(function (v) {
      svg('line', { x1: xs(v), x2: xs(v), y1: T, y2: H - B, stroke: C.grid }, s);
      text(s, xs(v), H - B + 18, pct(v), { 'text-anchor': 'middle' });
    });
    [0.2, 0.3, 0.4, 0.5, 0.6].forEach(function (v) {
      svg('line', { x1: L, x2: W - R, y1: ys(v), y2: ys(v), stroke: C.grid }, s);
      text(s, L - 8, ys(v) + 4, v.toFixed(1), { 'text-anchor': 'end' });
    });
    text(s, (L + W - R) / 2, H - 6, 'recognizable (share closest to its own thing, of 21)', { 'text-anchor': 'middle', class: 'lbl' });
    text(s, 14, (T + H - B) / 2, 'distance to the adult Form (lower = closer)', { transform: 'rotate(-90 14 ' + (T + H - B) / 2 + ')', 'text-anchor': 'middle', class: 'lbl' });
    function dot(st, shape, labelText, anchor, dx, dy) {
      var x = xs(value(st, 'recog')), y = ys(value(st, 'd_adult'));
      if (isNaN(x) || isNaN(y)) return;
      var col = color(st);
      if (shape === 'sq') svg('rect', { x: x - 6, y: y - 6, width: 12, height: 12, rx: 2, fill: col, stroke: '#FFFFFF', 'stroke-width': 2 }, s);
      else if (shape === 'dia') svg('path', { d: 'M' + x + ' ' + (y - 8) + 'L' + (x + 8) + ' ' + y + 'L' + x + ' ' + (y + 8) + 'L' + (x - 8) + ' ' + y + 'Z', fill: col, stroke: '#FFFFFF', 'stroke-width': 2 }, s);
      else svg('circle', { cx: x, cy: y, r: 5, fill: col, stroke: '#FFFFFF', 'stroke-width': 2 }, s);
      if (labelText) text(s, x + (dx || 8), y + (dy || 4), labelText, { class: 'lbl', 'text-anchor': anchor || 'start' });
      var hit = svg('circle', { cx: x, cy: y, r: 12, fill: 'transparent' }, s);
      hit.addEventListener('mousemove', function (e) {
        tip.show(e, '<b>' + stopName(st) + '</b><br>recognizable ' + pct(value(st, 'recog')) + '<br>distance to the adult Form ' +
          f3(value(st, 'd_adult')) + '<br>variety ' + f3(value(st, 'spread')));
      });
      hit.addEventListener('mouseleave', tip.hide);
    }
    var kid = STOPS.filter(function (o) { return o.kind === 'kid'; });
    var d = kid.map(function (o, i) { return (i ? 'L' : 'M') + xs(value(o, 'recog')) + ' ' + ys(value(o, 'd_adult')); }).join('');
    svg('path', { d: d, fill: 'none', stroke: C.people, 'stroke-width': 2, 'stroke-linejoin': 'round' }, s);
    var sd = STOPS.filter(function (o) { return o.kind === 'sd'; });
    function seg(a, b) { svg('line', { x1: xs(value(a, 'recog')), y1: ys(value(a, 'd_adult')), x2: xs(value(b, 'recog')), y2: ys(value(b, 'd_adult')), stroke: C.sd, 'stroke-width': 2 }, s); }
    seg(sd[0], sd[1]); seg(sd[1], sd[2]); seg(sd[1], sd[3]); seg(sd[1], sd[4]);
    kid.forEach(function (o) { dot(o, 'dot', [2, 6, 10].indexOf(o.age) >= 0 ? 'age ' + o.age : '', 'start', 6, -8); });
    sd.forEach(function (o, i) { dot(o, 'dot', i === 0 ? 'SD v1.1' : i === 4 ? 'SD v1.2–v1.5' : '', i === 0 ? 'end' : 'start', i === 0 ? -8 : 9, i === 0 ? 20 : -10); });
    dot(STOPS[9], 'sq', 'adults', 'start', 10, 4);
    dot(STOPS[10], 'dia', 'Muse Image', 'start', 11, 4);
    var leg = document.getElementById('paths-legend');
    leg.innerHTML = '';
    [['Children, ages 2–10', C.people, ''], ['Adults (Quick, Draw!)', C.people, 'sq'], ['Muse Image', C.muse, 'sq'],
     ['Stable Diffusion v1.1–v1.5', C.sd, '']].forEach(function (x) {
      leg.appendChild(h('span', null, [h('i', { class: x[2], style: 'background:' + x[1] }), x[0]]));
    });
    document.getElementById('paths-note').textContent = (thing === 'mean' ? 'Means over the 20 things both drew.' :
      'One thing: ' + label(thing) + '.') + ' Stable Diffusion v1.3, v1.4 and v1.5 each continue from v1.2. Its distance is mostly drawing style (it draws marker sketches on paper; people draw thin lines), so watch how it moves, not where it sits.';
  }

  // ---------- curves: children vs. Stable Diffusion, one measure at a time ----------
  function curveData(m) {
    if (thing === 'mean') {
      return { kid: AGES.map(function (a, i) { return { x: a, v: D.children.curves[m].mean[i], ci: D.children.curves[m].ci95[i] }; }),
               ai: CK.map(function (c, i) { return { x: KSTEPS[c], ck: c, v: D.ai.all.curves[m].mean[i], ci: D.ai.all.curves[m].ci95[i] }; }),
               adult: D.adults.mean_over_children_things[m], muse: D.muse.mean_over_children_things[m] };
    }
    return { kid: AGES.map(function (a) { var c = D.children.cells[thing][String(a)]; return { x: a, v: c[m], ci: c[m + '_ci95'] }; }),
             ai: CK.map(function (ck) { var c = D.ai.cells[thing][ck]; return { x: KSTEPS[ck], ck: ck, v: c[m], ci: c[m + '_ci95'] }; }),
             adult: D.adults.cells[thing][m], muse: D.muse.cells[thing][m] };
  }

  function panel(boxId, series, xdom, xticks, xfmt, yd, isAI, md, refs) {
    var box = document.getElementById(boxId);
    box.innerHTML = '';
    var W = 400, H = 280, L = 44, R = 54, T = 26, B = 34;
    var xs = function (v) { return L + (W - L - R) * (v - xdom[0]) / (xdom[1] - xdom[0]); };
    var ys = function (v) { return T + (H - T - B) * (yd[1] - v) / (yd[1] - yd[0]); };
    var s = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': md.name + (isAI ? ' by training stage' : ' by age') }, box);
    var tip = tipper(box);
    var yt = niceTicks(yd[0], yd[1], 5);
    yt.forEach(function (v) {
      svg('line', { x1: L, x2: W - R, y1: ys(v), y2: ys(v), stroke: C.grid }, s);
      text(s, L - 6, ys(v) + 4, md.key === 'recog' ? pct(v) : v.toFixed(2), { 'text-anchor': 'end' });
    });
    xticks.forEach(function (v) { text(s, xs(v), H - B + 16, xfmt(v), { 'text-anchor': 'middle' }); });
    text(s, (L + W - R) / 2, H - 4, isAI ? 'training steps (millions)' : 'age (years)', { 'text-anchor': 'middle', class: 'lbl' });
    [['adults', refs.adult, C.people], ['Muse', refs.muse, C.muse]].forEach(function (r) {
      if (r[1] == null || r[1] < yd[0] || r[1] > yd[1]) return;
      svg('line', { x1: L, x2: W - R, y1: ys(r[1]), y2: ys(r[1]), stroke: r[2], 'stroke-width': 1.2, opacity: 0.85 }, s);
      text(s, W - R + 4, ys(r[1]) + 4, r[0], { class: 'lbl' });
    });
    var col = isAI ? C.sd : C.people;
    if (!isAI) {
      var band = series.map(function (p, i) { return (i ? 'L' : 'M') + xs(p.x) + ' ' + ys(p.ci[1]); }).join('') +
        series.slice().reverse().map(function (p) { return 'L' + xs(p.x) + ' ' + ys(p.ci[0]); }).join('') + 'Z';
      svg('path', { d: band, fill: col, opacity: 0.1 }, s);
      svg('path', { d: series.map(function (p, i) { return (i ? 'L' : 'M') + xs(p.x) + ' ' + ys(p.v); }).join(''), fill: 'none', stroke: col, 'stroke-width': 2, 'stroke-linejoin': 'round' }, s);
    } else {
      series.forEach(function (p) { svg('line', { x1: xs(p.x), x2: xs(p.x), y1: ys(p.ci[0]), y2: ys(p.ci[1]), stroke: col, 'stroke-width': 2, opacity: 0.45, 'stroke-linecap': 'round' }, s); });
      var b = function (a, c) { svg('line', { x1: xs(series[a].x), y1: ys(series[a].v), x2: xs(series[c].x), y2: ys(series[c].v), stroke: col, 'stroke-width': 2 }, s); };
      b(0, 1); b(1, 2); b(1, 3); b(1, 4);
    }
    series.forEach(function (p, i) {
      svg('circle', { cx: xs(p.x), cy: ys(p.v), r: 4.5, fill: col, stroke: '#FFFFFF', 'stroke-width': 2 }, s);
      if (isAI && (i === 0 || i === 4)) text(s, xs(p.x), ys(p.v) - 10, p.ck, { 'text-anchor': 'middle', class: 'lbl' });
      var hit = svg('circle', { cx: xs(p.x), cy: ys(p.v), r: 12, fill: 'transparent' }, s);
      hit.addEventListener('mousemove', function (e) {
        tip.show(e, '<b>' + (isAI ? 'Stable Diffusion ' + p.ck : 'Age ' + p.x) + '</b><br>' + md.name + ': ' + md.fmt(p.v) +
          '<br>95% CI ' + ciTxt(p.ci, md.key === 'recog' ? pct : f2));
      });
      hit.addEventListener('mouseleave', tip.hide);
    });
  }

  function niceTicks(lo, hi, n) {
    var step = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(step)));
    var nice = [1, 2, 2.5, 5, 10].map(function (k) { return k * mag; }).filter(function (k) { return k >= step; })[0];
    var out = [];
    for (var v = Math.ceil(lo / nice) * nice; v <= hi + 1e-9; v += nice) out.push(+v.toFixed(6));
    return out;
  }

  function renderCurves() {
    var md = MEASURES.filter(function (m) { return m.key === measure; })[0];
    var tabs = document.getElementById('measure-tabs');
    tabs.innerHTML = '';
    MEASURES.forEach(function (m) {
      var b = h('button', { type: 'button', role: 'tab', 'aria-selected': m.key === measure ? 'true' : 'false' }, m.name);
      b.addEventListener('click', function () { measure = m.key; renderCurves(); });
      tabs.appendChild(b);
    });
    document.getElementById('measure-sub').textContent = md.sub;
    var cd = curveData(md.key);
    var all = [];
    cd.kid.concat(cd.ai).forEach(function (p) { all.push(p.v, p.ci[0], p.ci[1]); });
    all.push(cd.adult, cd.muse);
    var lo = Math.min.apply(null, all), hi = Math.max.apply(null, all), pad = (hi - lo) * 0.08;
    var yd = md.key === 'recog' ? [Math.max(0, lo - pad), Math.min(1, hi + pad)] : [Math.max(0, lo - pad), hi + pad];
    panel('kid-chart', cd.kid, [1.6, 10.4], AGES, String, yd, false, md, cd);
    panel('ai-chart', cd.ai, [0.3, 1.65], [0.5, 1.0, 1.5], function (v) { return v.toFixed(1); }, yd, true, md, cd);
    var t = D.children.tests[md.key].linear, a = D.ai.all.tests[md.key];
    var fmtS = md.key === 'recog' ? function (v) { return (100 * v).toFixed(1) + ' pts'; } : f3;
    document.getElementById('curves-note').textContent = (thing === 'mean' ? 'Means over 20 things (children) and 21 things (Stable Diffusion: the 20 and an umbrella). ' :
      'One thing: ' + label(thing) + '. ') + 'Children, all 20 things: ' + signed(t.mean_slope, fmtS) + ' a year, 95% CI ' +
      ciTxt(t.ci95, fmtS) + '. Stable Diffusion, 21 things, v1.5 minus v1.1: ' + signed(a.last_minus_first.mean, fmtS) +
      ', 95% CI ' + ciTxt(a.last_minus_first.ci95, fmtS) + '. Bands and bars are 95% bootstrap CIs.';
    // table view
    var rows = STOPS.filter(function (o) { return o.kind !== 'damage'; }).map(function (o) {
      return h('tr', null, [h('td', null, stopName(o))].concat(MEASURES.map(function (m) {
        return h('td', { class: 'num' }, m.fmt(value(o, m.key)));
      })));
    });
    var tb = document.getElementById('curves-table');
    tb.innerHTML = '';
    tb.appendChild(h('table', null, [h('thead', null, h('tr', null, [h('th', null, 'Stage (' + (thing === 'mean' ? 'mean of 20 things' : label(thing)) + ')')]
      .concat(MEASURES.map(function (m) { return h('th', { class: 'num' }, m.name); })))), h('tbody', null, rows)]));
  }

  // ---------- the sketch model ----------
  function renderGrow() {
    var sk = D.sketch;
    var strips = document.getElementById('grow-strips');
    strips.innerHTML = '';
    if (!sk) { document.getElementById('grow').hidden = true; return; }
    var st = sk.steps['t1.0'];
    [0, 100, 200, 800, 3200, 25600].forEach(function (n) {
      var r = st[String(n)];
      if (!r) return;
      strips.appendChild(h('figure', null, [h('figcaption', null, [h('b', null, n === 0 ? 'Untrained' : 'Step ' + n.toLocaleString('en-US')),
        pct(r.recog) + ' recognizable']), h('img', { src: '/static/img/plato_lifespan/sketch_step' + n + '.webp', width: 1080, height: 132, loading: 'lazy',
        alt: 'Six chairs the sketch model drew at training step ' + n }) ]));
    });
    // three small charts: one per measure, the sketch model as the only series, references labeled
    var box = document.getElementById('grow-chart');
    box.innerHTML = '';
    var steps = Object.keys(st).map(Number).sort(function (a, b) { return a - b; });
    var kidChair = D.children.cells.chair, tr = sk.training_drawings;
    var wrap = h('div', { class: 'ls-pair', style: 'grid-template-columns:repeat(3,minmax(0,1fr))' });
    box.appendChild(wrap);
    MEASURES.slice(0, 3).forEach(function (md) {
      var fig = h('figure', { class: 'ls-panel' }, h('figcaption', null, md.name));
      var inner = h('div', { class: 'ls-chart' });
      fig.appendChild(inner);
      wrap.appendChild(fig);
      var W = 300, H = 210, L = 40, R = 64, T = 10, B = 32;
      var lx = function (n) { return Math.log10(n + 25); };
      var xs = function (n) { return L + (W - L - R) * (lx(n) - lx(0)) / (lx(25600) - lx(0)); };
      var vals = steps.map(function (n) { return st[String(n)][md.key]; }).concat([tr[md.key], kidChair['2'][md.key], kidChair['10'][md.key]]);
      var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals), pad = (hi - lo) * 0.1;
      var yd = [Math.max(0, lo - pad), md.key === 'recog' ? Math.min(1, hi + pad) : hi + pad];
      var ys = function (v) { return T + (H - T - B) * (yd[1] - v) / (yd[1] - yd[0]); };
      var s = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': md.name + ' of the sketch model over training' }, inner);
      var tip = tipper(inner);
      niceTicks(yd[0], yd[1], 4).forEach(function (v) {
        svg('line', { x1: L, x2: W - R, y1: ys(v), y2: ys(v), stroke: C.grid }, s);
        text(s, L - 5, ys(v) + 4, md.key === 'recog' ? pct(v) : v.toFixed(2), { 'text-anchor': 'end' });
      });
      [0, 100, 1000, 10000].forEach(function (n) { text(s, xs(n), H - B + 15, n === 0 ? '0' : n >= 1000 ? (n / 1000) + 'k' : String(n), { 'text-anchor': 'middle' }); });
      text(s, (L + W - R) / 2, H - 3, 'training step', { 'text-anchor': 'middle', class: 'lbl' });
      var refs = [['learned from', tr[md.key], C.muted], ['age 2', kidChair['2'][md.key], C.people], ['age 10', kidChair['10'][md.key], C.people]]
        .map(function (r) { return { name: r[0], y: ys(r[1]), col: r[2], ly: ys(r[1]) }; })
        .sort(function (a, b) { return a.y - b.y; });
      refs.forEach(function (r, i) { if (i && r.ly - refs[i - 1].ly < 12) r.ly = refs[i - 1].ly + 12; });  // labels never overlap
      refs.forEach(function (r) {
        svg('line', { x1: L, x2: W - R, y1: r.y, y2: r.y, stroke: r.col, 'stroke-width': 1.2, opacity: 0.8 }, s);
        text(s, W - R + 4, r.ly + 4, r.name, { class: 'lbl', 'font-size': 11 });
      });
      svg('path', { d: steps.map(function (n, i) { return (i ? 'L' : 'M') + xs(n) + ' ' + ys(st[String(n)][md.key]); }).join(''), fill: 'none', stroke: C.sketch, 'stroke-width': 2, 'stroke-linejoin': 'round' }, s);
      steps.forEach(function (n) {
        var v = st[String(n)][md.key];
        svg('circle', { cx: xs(n), cy: ys(v), r: 4, fill: C.sketch, stroke: '#FFFFFF', 'stroke-width': 2 }, s);
        var hit = svg('circle', { cx: xs(n), cy: ys(v), r: 11, fill: 'transparent' }, s);
        hit.addEventListener('mousemove', function (e) {
          var r = st[String(n)];
          tip.show(e, '<b>Step ' + n.toLocaleString('en-US') + '</b><br>' + md.name + ': ' + md.fmt(v) + '<br>95% CI ' +
            ciTxt(r[md.key + '_ci95'], md.key === 'recog' ? pct : f2) + '<br>' + r.n + ' drawings');
        });
        hit.addEventListener('mouseleave', tip.hide);
      });
    });
    var last = st[String(steps[steps.length - 1])];
    document.getElementById('grow-note').textContent = 'Dark line: the sketch model (chairs only, 64 drawings per step, temperature 1; scribbles that are a single point don’t count). ' +
      'Lines: the 200 drawings it learned from (a random sample of its 20,000), and children’s chairs at 2 and at 10. ' +
      'At the last step its variety is ' + f2(last.spread) + ' against ' + f2(tr.spread) + ' for its teachers (difference ' +
      signed(last.spread_minus_training, f3) + ', 95% CI ' + ciTxt(last.spread_minus_training_ci95, f3) + '). One training run, one seed.';
  }

  function renderAll() {
    renderStage();
    renderPaths();
    renderCurves();
  }

  // a shareable starting point: #at=4 (age 4), #at=adults, #at=muse, #at=v1.3, #at=damaged; &thing=cat or mean
  function fromHash() {
    var q = {};
    location.hash.replace(/^#/, '').split('&').forEach(function (kv) { var p = kv.split('='); if (p[1]) q[p[0]] = decodeURIComponent(p[1]); });
    if (q.thing && (q.thing === 'mean' || things().indexOf(q.thing) >= 0)) thing = q.thing;
    if (q.at) {
      STOPS.forEach(function (s, i) {
        if (String(s.age) === q.at || s.ck === q.at || (s.kind === 'adult' && q.at === 'adults') ||
            (s.kind === 'muse' && q.at === 'muse') || (s.kind === 'damage' && q.at === 'damaged')) stop = i;
      });
    }
  }

  function init() {
    var range = document.getElementById('stop');
    range.max = String(STOPS.length - 1);
    fromHash();
    range.value = String(stop);
    range.addEventListener('input', function () { stop = +range.value; renderStage(); });
    thingSelect();
    renderAnswer();
    renderAll();
    renderGrow();
  }

  TOT.api('/api/plato/lifespan').then(function (data) { D = data; init(); }).catch(function (e) {
    var el = document.getElementById('load-error');
    el.textContent = 'The results didn’t load: ' + (e && e.message ? e.message : e);
    el.hidden = false;
  });
})();
