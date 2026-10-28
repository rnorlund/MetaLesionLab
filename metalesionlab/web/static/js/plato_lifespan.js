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
    // drawn at the reading column's own width, so the dots and the track keep their size on a wide window
    var col = document.getElementById('read');
    var W = Math.max(200, Math.round((col && col.clientWidth) || 300)), H = 34, pad = 10;
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
        h('a', { href: '/plato/damage' }, 'Damage the painter'), ' shows it. Damage to the image model’s language part made the chair wander into other things (a room, a car, a person), never back to the plain chair; damage to its drawing part dissolved the lines and kept the asked kind of chair more often. This is an analogy, not a claim about people.']));
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
    var ssd = D.sketch_seeds, sbd = D.sketch_big;
    if (sbd && sbd.concepts && sbd.concepts.chair) {
      var bc = sbd.concepts.chair, b1 = bc.tests['t1.0'].last, brc = bc.curves['t1.0'].recog.mean;
      var sm1 = ssd && ssd.concepts && ssd.concepts.chair ? ssd.concepts.chair.tests['t1.0'].last : null;
      var smallTxt = sm1 ? 'A smaller model we trained first (' + ssd.concepts.chair.seeds.length + ' runs on 20,000 chairs) ' +
        (sm1.verdict === 'narrower' ? 'ended ' + lessPct(sm1) + ' less varied.' : sm1.verdict === 'wider' ? 'ended more varied.' : 'showed no clear difference.') : '';
      var at = sbd.animation.temp, ta = bc.tests['t' + tName(at)] && bc.tests['t' + tName(at)].last;
      var animTxt = ta && at !== 1 && ta.verdict !== b1.verdict ? ' At the cautious temperature the animation uses (' + tName(at) + '), the difference is not clear (' +
        deltaTxt(ta) + ').' : '';
      ul.appendChild(h('li', null, [h('b', null, 'An AI that learns only from people’s chairs does grow up like a child. '),
        'A sketch model trained from scratch on ' + nTrain(bc) + ' people’s chairs starts at scribbles (' + pct(brc[0]) + ' recognizable) and ends at ' +
        pct(brc[brc.length - 1]) + ' (mean of ' + bc.seeds.length + ' runs, temperature 1). ' +
        (b1.verdict === 'narrower'
          ? 'In ' + (b1.n_below_0 === b1.n_seeds ? 'all ' + runsWord(b1, bc) : b1.n_below_0 + ' of ' + runsWord(b1, bc)) + ' it ends less varied than the chairs it learned from (' +
            lessPct(b1) + ' less, ' + deltaTxt(b1) + '): like Muse Image, it narrows toward the typical chair.'
          : b1.verdict === 'wider'
            ? 'It ends more varied than the chairs it learned from (' + deltaTxt(b1) + ').'
            : 'Whether it ends narrower than the chairs it learned from is not clear (' + deltaTxt(b1) + ', ' + runsWord(b1, bc) + ').') +
        animTxt + (smallTxt ? ' ' + smallTxt : '')]));
    } else if (ssd && ssd.concepts && ssd.concepts.chair) {
      var sc = ssd.concepts.chair, t1 = sc.tests['t1.0'].last, rc = sc.curves['t1.0'].recog.mean, nr = sc.seeds.length;
      var allTemps = ssd.temps.every(function (tp) { return sc.tests['t' + tp.toFixed(1)].last.verdict === 'narrower'; });
      ul.appendChild(h('li', null, [h('b', null, 'An AI that learns only from people’s chairs does grow up like a child. '),
        'A small sketch model trained from scratch ' + nr + ' times starts at scribbles (' + pct(rc[0]) + ' recognizable) and ends at ' +
        pct(rc[rc.length - 1]) + ' (mean of ' + nr + ' runs). ' +
        (t1.verdict === 'narrower'
          ? 'In ' + (t1.n_below_0 === t1.n_seeds ? 'all ' + nr : t1.n_below_0 + ' of ' + nr) + ' runs it ends less varied than the chairs it learned from (' +
            lessPct(t1) + ' less, ' + deltaTxt(t1) + ')' + (allTemps ? ', at every sampling temperature we tried' : '') + ': like Muse Image, it narrows toward the typical chair.'
          : 'Whether it ends narrower than the chairs it learned from does not hold up across runs (' + deltaTxt(t1) + ').') +
        (ssd.concepts.cat && ssd.concepts.cat.tests['t1.0'].last.verdict !== 'narrower'
          ? ' Not so for cats, which the same model learns much less well: its cats end ' +
            (ssd.concepts.cat.tests['t1.0'].last.verdict === 'wider' ? 'more varied than the ones it learned from.' : 'neither clearly narrower nor wider.')
          : '')]));
    } else if (sk) {
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

  // ---------- watch an AI learn: the sketch models. The player shows the larger model (sketch_big) when its results
  // are in, otherwise the small one (sketch_seeds); the charts and the table show every model's runs. ----------
  var REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var SKETCH = [['sketch_big', 'Larger model'], ['sketch_seeds', 'Small model']];
  var LEARN = { key: null, thing: 'chair', temp: 't1.0' };
  function shownKey() { return D.sketch_big && D.sketch_big.concepts && D.sketch_big.concepts.chair ? 'sketch_big' : 'sketch_seeds'; }
  function ss() { return D[shownKey()]; }
  function isBig() { return shownKey() === 'sketch_big'; }
  function fmtStep(n) { return n.toLocaleString('en-US'); }
  function lessPct(t) { return Math.round(-100 * t.mean_delta / t.ref_spread) + '%'; }
  function tName(tp) { return (+tp).toFixed(1); }
  function nTrain(b) { var k = b.n_train && Object.keys(b.n_train)[0]; return k ? fmtStep(b.n_train[k]) : ''; }
  function freshRuns(b) { return b.test_seeds && b.test_seeds.length < b.seeds.length; }
  function runsWord(t, b) { return t.n_seeds + (freshRuns(b) ? ' new runs' : ' runs'); }
  // #learn paints with the page's CSS variables (as styles, not attributes), so it follows the light and dark themes
  function paint(prop, token) { return prop + ':var(' + token + ')'; }

  function renderPlayer() {
    var B = ss(), a = B.animation, steps = a.steps, i = 0, playing = false, timer = null, fadeTimer = null, touched = false;
    var cols = Math.ceil(steps.length / 4), batch = B.batch || 100;  // the sprite: 4 rows of checkpoints
    var base = document.getElementById('learn-base'), top = document.getElementById('learn-top');
    var range = document.getElementById('learn-range'), btn = document.getElementById('learn-play');
    [base, top].forEach(function (e) { e.style.backgroundSize = (cols * 100) + '% 400%'; });
    range.max = String(steps.length - 1);
    document.getElementById('learn-end').textContent = 'step ' + fmtStep(steps[steps.length - 1]);
    function pos(k) { return (k % cols) / (cols - 1) * 100 + '% ' + Math.floor(k / cols) / 3 * 100 + '%'; }
    function bar(v) {
      var box = document.getElementById('learn-bar'), W = 360, lo = 0.2, hi = 0.55;
      var x = function (s) { return 6 + (W - 12) * (Math.max(lo, Math.min(hi, s)) - lo) / (hi - lo); };
      box.innerHTML = '';
      var s = svg('svg', { viewBox: '0 0 ' + W + ' 50', preserveAspectRatio: 'xMinYMid meet', role: 'img', 'aria-label': 'How varied its chairs are: ' + f2(v) + ', against ' + f2(a.ref_spread) + ' for the people’s chairs it learned from' }, box);
      svg('rect', { x: 6, y: 6, width: W - 12, height: 16, rx: 8, style: paint('fill', '--track') }, s);
      if (v != null) svg('rect', { x: 6, y: 6, width: Math.max(16, x(v) - 6), height: 16, rx: 8, style: paint('fill', '--ink-2') }, s);
      var rx = x(a.ref_spread);
      svg('line', { x1: rx, x2: rx, y1: 1, y2: 27, 'stroke-width': 3, style: paint('stroke', '--people') }, s);
      text(s, Math.min(W - 6, Math.max(6, rx)), 44, 'people’s chairs it learned from: ' + f2(a.ref_spread),
        { 'text-anchor': rx > W * 0.6 ? 'end' : rx < W * 0.4 ? 'start' : 'middle', 'font-size': 12, style: paint('fill', '--people') });
    }
    function readout(k) {
      document.getElementById('learn-step').textContent = fmtStep(steps[k]);
      document.getElementById('learn-seen').textContent = steps[k] ? fmtStep(steps[k] * batch) + ' chairs seen' : 'nothing seen yet';
      document.getElementById('learn-recog').textContent = pct(a.recog[k]);
      document.getElementById('learn-spread').textContent = f2(a.spread[k]);
      bar(a.spread[k]);
      range.value = String(k);
      range.setAttribute('aria-valuetext', 'Step ' + fmtStep(steps[k]));
      document.getElementById('learn-frames').setAttribute('aria-label', '16 chairs drawn by the sketch model at training step ' +
        fmtStep(steps[k]) + '; ' + pct(a.recog[k]) + ' of its drawings are recognizable as chairs');
    }
    function show(k, fade) {
      i = k;
      clearTimeout(fadeTimer);
      if (!fade || REDUCED) {
        base.style.backgroundPosition = pos(k);
        top.classList.remove('fade');
      } else {
        top.style.backgroundPosition = pos(k);
        top.classList.remove('fade');
        void top.offsetWidth;  // restart the cross-fade
        top.classList.add('fade');
        fadeTimer = setTimeout(function () { base.style.backgroundPosition = pos(k); top.classList.remove('fade'); }, 380);
      }
      readout(k);
    }
    function tick() {
      var last = i === steps.length - 1;
      show(last ? 0 : i + 1, true);
      timer = setTimeout(tick, i === steps.length - 1 ? 2600 : i === 0 ? 1400 : 900);
    }
    function play(on) {
      playing = on;
      clearTimeout(timer);
      btn.textContent = on ? 'Pause' : 'Play';
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      if (on) timer = setTimeout(tick, i === steps.length - 1 ? 300 : 700);
    }
    btn.addEventListener('click', function () { touched = true; if (!playing && i === steps.length - 1) show(0, false); play(!playing); });
    range.addEventListener('input', function () { touched = true; play(false); show(+range.value, false); });
    show(REDUCED ? steps.length - 1 : 0, false);
    var nr = B.concepts.chair.seeds.length;
    document.getElementById('learn-cap').textContent = 'One run (seed ' + a.seed + ' of ' + nr + ') at sampling temperature ' + tName(a.temp) + '. ' +
      (isBig() ? 'We chose the temperature by eye from this first run, before the other ' + (nr - 1) + ' runs were trained: at lower temperatures it draws cleaner chairs. '
        : 'Chosen in the plan before any training. ') +
      'A blank tile is a drawing that was only a dot. The numbers come from all 200 of this run’s drawings at each step; the 16 tiles are its first 16.';
    if (!REDUCED && 'IntersectionObserver' in window) {
      new IntersectionObserver(function (es) {
        es.forEach(function (e) {
          if (e.isIntersecting && !touched && !playing) play(true);
          else if (!e.isIntersecting && playing && !touched) play(false);
        });
      }, { threshold: 0.5 }).observe(document.getElementById('learn-player'));
    }
  }

  function renderStroke() {
    var box = document.getElementById('stroke-svg');
    TOT.api('/static/img/plato_lifespan/sketch/stroke_order.json').then(function (d) {
      var strokes = d.strokes, css = getComputedStyle(box);  // line art on its light card (--art-* in plato_lifespan.css)
      var ink = css.getPropertyValue('--art-ink').trim(), pen = css.getPropertyValue('--art-pen').trim();
      var xs = [], ys = [];
      strokes.forEach(function (st) { xs = xs.concat(st[0]); ys = ys.concat(st[1]); });
      var dx = (255 - Math.max.apply(null, xs)) / 2, dy = (255 - Math.max.apply(null, ys)) / 2;
      var paths = strokes.map(function (st) {
        var pts = st[0].map(function (x, k) { return [x + dx, st[1][k] + dy]; });
        if (pts.length === 1) pts.push(pts[0]);
        var len = 0;
        for (var k = 1; k < pts.length; k++) len += Math.hypot(pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1]);
        var p = svg('path', { d: pts.map(function (q, k) { return (k ? 'L' : 'M') + q[0] + ' ' + q[1]; }).join(''), fill: 'none', stroke: ink,
          'stroke-width': 6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', pathLength: 1, 'stroke-dasharray': 1 }, box);
        return { el: p, len: len };
      });
      function draw() {
        var t = 250;
        paths.forEach(function (p) {
          if (!p.el.animate) return;
          p.el.getAnimations().forEach(function (an) { an.cancel(); });
          var dur = Math.max(250, p.len / 120 * 1000);
          p.el.animate([{ strokeDashoffset: 1, stroke: pen }, { strokeDashoffset: 0, stroke: pen }], { duration: dur, delay: t, fill: 'both' });
          p.el.animate([{ stroke: pen }, { stroke: ink }], { duration: 250, delay: t + dur, fill: 'forwards' });
          t += dur + 300;
        });
      }
      document.getElementById('stroke-replay').addEventListener('click', draw);
      document.getElementById('stroke-note').textContent = 'Seed ' + d.seed + ' at step ' + fmtStep(d.step) +
        (d.temp !== 1 ? ', temperature ' + tName(d.temp) : '') + ': tile ' + (d.index + 1) +
        ' of the 16 above, the first one that the measure calls a chair (the rule was set in the plan). ' +
        strokes.length + (strokes.length === 1 ? ' stroke.' : ' strokes.');
      if (REDUCED || !('IntersectionObserver' in window)) return;
      var seen = false;
      new IntersectionObserver(function (es) {
        es.forEach(function (e) { if (e.isIntersecting && !seen) { seen = true; draw(); } });
      }, { threshold: 0.6 }).observe(box);
    }).catch(function () { box.closest('.ls-stroke').hidden = true; });
  }

  function verdictWords(t) {
    return t.verdict === 'narrower' ? 'narrower' : t.verdict === 'wider' ? 'wider' : 'no clear difference';
  }
  function deltaTxt(t) { return signed(t.mean_delta, f3) + ' ' + ciTxt(t.t_ci95, function (v) { return signed(v, f3); }); }
  function moreLess(t) { return t.mean_delta < 0 ? lessPct(t) + ' less varied' : Math.round(100 * t.mean_delta / t.ref_spread) + '% more varied'; }

  // The test's headline for one model's chairs at temperature 1, in each of the plan's three outcomes.
  function verdictHead(b, t1, who) {
    var all = t1.n_below_0 === t1.n_seeds, runs = runsWord(t1, b);
    if (t1.verdict === 'narrower') {
      return [h('b', null, who + ' ends narrower than the chairs it learned from' + (all ? ', in all ' + runs + '. ' : ' (' + t1.n_below_0 + ' of ' + runs + '). ')),
        'At its own temperature (1.0) its chairs are ' + lessPct(t1) + ' less varied than the people’s chairs it learned from (' + f2(t1.model_spread) + ' vs ' +
        f2(t1.ref_spread) + '; difference ' + deltaTxt(t1) + ', 95% CI across runs). Like Muse Image, it narrows toward the typical chair.'];
    }
    if (t1.verdict === 'wider') {
      return [h('b', null, who + ' ends more varied than the chairs it learned from. '), 'At its own temperature (1.0) the difference is ' + deltaTxt(t1) +
        ' (95% CI across ' + runs + '), and ' + t1.n_below_0 + ' of ' + runs + ' end narrower.'];
    }
    return [h('b', null, who + ' does not clearly end narrower than the chairs it learned from. '), 'At its own temperature (1.0) the difference is ' +
      deltaTxt(t1) + ' (95% CI across ' + runs + '), and ' + t1.n_below_0 + ' of ' + runs + ' end narrower.'];
  }

  function renderVerdict() {
    var box = document.getElementById('learn-verdict'), B = ss(), ch = B.concepts.chair, t1 = ch.tests['t1.0'].last;
    box.innerHTML = '';
    var head = verdictHead(ch, t1, isBig() ? 'The larger model' : 'It');
    if (freshRuns(ch) && ch.tests_all_seeds) {
      head.push(' The test uses the ' + t1.n_seeds + ' runs trained after we wrote down the test; with the first run too, the difference is ' +
        deltaTxt(ch.tests_all_seeds['t1.0'].last) + '.');
    }
    box.appendChild(h('p', null, head));
    var tiles = h('div', { class: 'ls-tiles' });
    B.temps.forEach(function (tp) {
      var t = ch.tests['t' + tName(tp)].last;
      var tag = tp === 1 ? ' (its own)' : tp === B.animation.temp ? ' (the animation’s)' : '';
      tiles.appendChild(h('div', { class: 'ls-tile' }, [h('span', null, 'Temperature ' + tName(tp) + tag),
        h('b', null, t.verdict === 'null' ? 'No clear difference' : moreLess(t)),
        h('small', null, (t.verdict === 'null' ? moreLess(t) + ' on average; ' : '') + 'difference ' + deltaTxt(t) + '; ' + t.n_below_0 + ' of ' + t.n_seeds + ' runs narrower')]));
    });
    box.appendChild(tiles);
    var allT = B.temps.every(function (tp) { return ch.tests['t' + tName(tp)].last.verdict === 'narrower'; });
    var ta = ch.tests['t' + tName(B.animation.temp)].last;
    box.appendChild(h('p', null, allT ? 'It holds at every sampling temperature we tried.' : [
      'By temperature: ' + B.temps.map(function (tp) { return tName(tp) + ': ' + verdictWords(ch.tests['t' + tName(tp)].last); }).join('; ') + '. ',
      B.animation.temp !== 1 && ta.verdict !== t1.verdict
        ? h('b', null, 'At the animation’s temperature (' + tName(B.animation.temp) + ') it is not clearly narrower: ') : '',
      B.animation.temp !== 1 && ta.verdict !== t1.verdict
        ? deltaTxt(ta) + ', ' + ta.n_below_0 + ' of ' + runsWord(ta, ch) + ' narrower. When it draws cautiously its runs disagree more, so the cleaner chairs above are not clearly less varied than people’s.'
        : '']));
    var sm = D.sketch_seeds;
    if (isBig() && sm && sm.concepts && sm.concepts.chair) {
      var s1 = sm.concepts.chair.tests['t1.0'].last, sr = sm.concepts.chair.curves['t1.0'].recog.mean;
      box.appendChild(h('p', null, [h('b', null, 'The first, smaller model. '), 'Before this one we trained a small sketch model (512 units instead of 2,048) on 20,000 chairs, ' +
        sm.concepts.chair.seeds.length + ' times. Its chairs were recognizable to the measure (' + pct(sr[sr.length - 1]) + ') but rough to the eye. ' +
        (s1.verdict === 'narrower' ? 'It ended narrower than the chairs it learned from in ' + (s1.n_below_0 === s1.n_seeds ? 'all ' + s1.n_seeds : s1.n_below_0 + ' of ' + s1.n_seeds) +
          ' runs (' + lessPct(s1) + ' less varied, ' + deltaTxt(s1) + ').'
          : 'Whether it ended narrower did not hold up (' + deltaTxt(s1) + ').') + ' Its first run, on a Mac, found −0.048 [−0.076, −0.022].']));
    } else {
      box.appendChild(h('p', null, 'The first run, on a Mac, found −0.048 [−0.076, −0.022].'));
    }
    var cat = sm && sm.concepts.cat;
    if (cat) {
      var c1 = cat.tests['t1.0'].last, cr = cat.curves['t1.0'].recog.mean, crl = cr[cr.length - 1];
      var how = 'Trained the same way on 20,000 cats (' + c1.n_seeds + ' runs), the ' + (isBig() ? 'small' : 'same small') + ' model ';
      var learned = 'learns them much less well (' + pct(crl) + ' of its cats are recognizable at the end, against ' + pct(cat.reference.recog) +
        ' of the cats it learned from)';
      box.appendChild(h('p', null, c1.verdict === 'narrower'
        ? [h('b', null, 'Cats too. '), how + 'also ends narrower than what it learned from (' + lessPct(c1) + ' less varied, ' + deltaTxt(c1) + ').']
        : c1.verdict === 'wider'
          ? [h('b', null, 'But not for cats. '), how + learned + ', and its cats end more varied than theirs, not less (' + deltaTxt(c1) +
            '). The narrowing shows up once a model has learned a thing well; before that, its drawings are still scattered.']
          : [h('b', null, 'Not clearly for cats. '), how + learned + ', and its cats end neither clearly narrower nor wider (' + deltaTxt(c1) + ').']));
    }
  }

  function learnOptions() {  // [model key, thing, tab label]
    var out = [], two = SKETCH.filter(function (m) { return D[m[0]] && D[m[0]].concepts; }).length > 1;
    SKETCH.forEach(function (m) {
      var B = D[m[0]];
      if (!B || !B.concepts) return;
      Object.keys(B.concepts).forEach(function (c) {
        out.push([m[0], c, (two ? m[1] + ': ' : '') + c + 's (' + B.concepts[c].seeds.length + ' runs)']);
      });
    });
    return out;
  }

  function learnTabs() {
    function tabs(box, items, cur, onPick) {
      box.innerHTML = '';
      items.forEach(function (it) {
        var b = h('button', { type: 'button', role: 'tab', 'aria-selected': it[0] === cur ? 'true' : 'false' }, it[1]);
        b.addEventListener('click', function () { onPick(it[0]); });
        box.appendChild(b);
      });
    }
    tabs(document.getElementById('learn-thing'), learnOptions().map(function (o) { return [o[0] + ':' + o[1], o[2][0].toUpperCase() + o[2].slice(1)]; }),
      LEARN.key + ':' + LEARN.thing, function (v) {
        var p = v.split(':');
        LEARN.key = p[0];
        LEARN.thing = p[1];
        if (!D[LEARN.key].temps.some(function (tp) { return 't' + tName(tp) === LEARN.temp; })) LEARN.temp = 't1.0';
        renderLearnCurves();
      });
    tabs(document.getElementById('learn-temp'), D[LEARN.key].temps.map(function (tp) { var k = 't' + tName(tp); return [k, 'Temperature ' + tName(tp)]; }),
      LEARN.temp, function (v) { LEARN.temp = v; renderLearnCurves(); });
  }

  function renderLearnCurves() {
    LEARN.key = LEARN.key || shownKey();
    learnTabs();
    var B = D[LEARN.key], b = B.concepts[LEARN.thing], cv = b.curves[LEARN.temp], steps = B.steps, ref = b.reference, kids = b.children || {};
    var box = document.getElementById('learn-chart');
    box.innerHTML = '';
    var wrap = h('div', { class: 'ls-pair ls-three' });
    box.appendChild(wrap);
    var lx = function (n) { return Math.log10(n + 25); };
    var ticks = [0, 100, 1000, 10000, 100000].filter(function (n) { return n <= steps[steps.length - 1]; });
    MEASURES.slice(0, 3).forEach(function (md) {
      var fig = h('figure', { class: 'ls-panel' }, h('figcaption', null, md.name));
      var inner = h('div', { class: 'ls-chart' });
      fig.appendChild(inner);
      wrap.appendChild(fig);
      var W = 300, H = 214, L = 40, R = 66, T = 10, Bm = 32;
      var xs = function (n) { return L + (W - L - R) * (lx(n) - lx(0)) / (lx(steps[steps.length - 1]) - lx(0)); };
      var c = cv[md.key];
      var refs = [['learned from', ref[md.key], '--faint']];  // [label, value, colour token]
      if (kids['2']) refs.push(['age 2', kids['2'][md.key], '--people'], ['age 10', kids['10'][md.key], '--people']);
      var vals = [];
      c.ci95.forEach(function (q) { vals.push(q[0], q[1]); });
      Object.keys(c.per_seed).forEach(function (sd) { c.per_seed[sd].forEach(function (v) { vals.push(v); }); });
      refs.forEach(function (r) { vals.push(r[1]); });
      vals = vals.filter(function (v) { return v != null && !isNaN(v); });
      var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals), pad = (hi - lo) * 0.08;
      var yd = [Math.max(0, lo - pad), md.key === 'recog' ? Math.min(1, hi + pad) : hi + pad];
      var ys = function (v) { return T + (H - T - Bm) * (yd[1] - v) / (yd[1] - yd[0]); };
      var s = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': md.name + ' of the ' + LEARN.thing + ' sketch model over training, mean of ' + b.seeds.length + ' runs with a 95% band' }, inner);
      var tip = tipper(inner);
      niceTicks(yd[0], yd[1], 4).forEach(function (v) {
        svg('line', { x1: L, x2: W - R, y1: ys(v), y2: ys(v), style: paint('stroke', '--gridline') }, s);
        text(s, L - 5, ys(v) + 4, md.key === 'recog' ? pct(v) : v.toFixed(2), { 'text-anchor': 'end' });
      });
      ticks.forEach(function (n) { text(s, xs(n), H - Bm + 15, n === 0 ? '0' : n >= 1000 ? (n / 1000) + 'k' : String(n), { 'text-anchor': 'middle' }); });
      text(s, (L + W - R) / 2, H - 3, 'training step', { 'text-anchor': 'middle', class: 'lbl' });
      var rl = refs.filter(function (r) { return r[1] != null; }).map(function (r) { return { name: r[0], y: ys(r[1]), ly: ys(r[1]), col: r[2] }; })
        .sort(function (p, q) { return p.y - q.y; });
      rl.forEach(function (r, k) { if (k && r.ly - rl[k - 1].ly < 12) r.ly = rl[k - 1].ly + 12; });
      rl.forEach(function (r) {
        svg('line', { x1: L, x2: W - R, y1: r.y, y2: r.y, 'stroke-width': 1.2, opacity: 0.85, 'stroke-dasharray': r.name === 'learned from' ? '4 3' : 'none',
          style: paint('stroke', r.col) }, s);
        text(s, W - R + 4, r.ly + 4, r.name, { class: 'lbl', 'font-size': 11 });
      });
      var idx = steps.map(function (n, k) { return k; }).filter(function (k) { return c.mean[k] != null && !isNaN(c.mean[k]); });
      var withCi = idx.filter(function (k) { return c.ci95[k][0] != null && !isNaN(c.ci95[k][0]); });
      if (withCi.length) {  // a band needs at least two runs
        var band = withCi.map(function (k, j) { return (j ? 'L' : 'M') + xs(steps[k]) + ' ' + ys(c.ci95[k][1]); }).join('') +
          withCi.slice().reverse().map(function (k) { return 'L' + xs(steps[k]) + ' ' + ys(c.ci95[k][0]); }).join('') + 'Z';
        svg('path', { d: band, opacity: 0.14, style: paint('fill', '--ink-2') }, s);
      }
      Object.keys(c.per_seed).forEach(function (sd) {
        var d = '';
        c.per_seed[sd].forEach(function (v, k) { if (v != null) d += (d ? 'L' : 'M') + xs(steps[k]) + ' ' + ys(v); });
        svg('path', { d: d, fill: 'none', 'stroke-width': 1, opacity: 0.28, style: paint('stroke', '--ink-2') }, s);
      });
      svg('path', { d: idx.map(function (k, j) { return (j ? 'L' : 'M') + xs(steps[k]) + ' ' + ys(c.mean[k]); }).join(''), fill: 'none', 'stroke-width': 2.2,
        'stroke-linejoin': 'round', style: paint('stroke', '--ink') }, s);
      // hover: one column per checkpoint, with a crosshair
      var cross = svg('line', { x1: 0, x2: 0, y1: T, y2: H - Bm, 'stroke-width': 1, opacity: 0, style: paint('stroke', '--ink-2') }, s);
      idx.forEach(function (k, j) {
        var x0 = j ? (xs(steps[idx[j - 1]]) + xs(steps[k])) / 2 : L, x1 = j < idx.length - 1 ? (xs(steps[k]) + xs(steps[idx[j + 1]])) / 2 : W - R;
        var hit = svg('rect', { x: x0, y: T, width: Math.max(1, x1 - x0), height: H - T - Bm, fill: 'transparent' }, s);
        hit.addEventListener('mousemove', function (e) {
          cross.setAttribute('x1', xs(steps[k])); cross.setAttribute('x2', xs(steps[k])); cross.setAttribute('opacity', 0.5);
          var fm = md.key === 'recog' ? pct : f3;
          tip.show(e, '<b>Step ' + fmtStep(steps[k]) + '</b><br>' + md.name + ': ' + fm(c.mean[k]) + ' (mean of ' + c.n_seeds[k] + ' runs)<br>95% CI ' +
            ciTxt(c.ci95[k], fm) + '<br>What it learned from: ' + fm(ref[md.key]));
        });
        hit.addEventListener('mouseleave', function () { tip.hide(); cross.setAttribute('opacity', 0); });
      });
    });
    var nm = LEARN.thing, tl = b.tests[LEARN.temp].last;
    document.getElementById('learn-curves-sub').textContent = (LEARN.key === 'sketch_big' ? 'The larger model (2,048 units). ' : D.sketch_big ? 'The first, smaller model (512 units). ' : '') +
      'Each panel: the mean of the ' + b.seeds.length + ' runs (dark line), a 95% band across runs, and each run on its own (thin lines). ' +
      '200 drawings per run and step, at temperature ' + LEARN.temp.slice(1) + '. Dashed: the 1,000 ' + nm + 's it learned from (a random sample of its ' + nTrain(b) + ').' +
      (kids['2'] ? ' Orange: children’s ' + nm + 's at 2 and at 10.' : '');
    document.getElementById('learn-curves-note').textContent = 'At the last step its variety is ' + f2(tl.model_spread) + ' against ' + f2(tl.ref_spread) +
      ' for what it learned from: difference ' + deltaTxt(tl) + ' (95% CI across ' + runsWord(tl, b) + '; resampling runs and drawings gives ' +
      ciTxt(tl.boot_ci95, function (v) { return signed(v, f3); }) + '). ' + tl.n_below_0 + ' of ' + runsWord(tl, b) + ' end narrower.' +
      (freshRuns(b) ? ' The test leaves out the first run, which we had seen before writing it down; the curves include it.' : '') +
      ' Single-dot drawings don’t count, so the first steps have fewer drawings.';
    renderLearnTable();
  }

  function renderLearnTable() {
    var rows = [], two = !!D.sketch_big;
    learnOptions().forEach(function (o) {
      var B = D[o[0]], b = B.concepts[o[1]];
      B.temps.forEach(function (tp) {
        var t = b.tests['t' + tName(tp)].last;
        var sg = function (v) { return signed(v, f3); };
        rows.push(h('tr', null, [h('td', null, two ? o[2] : o[1]), h('td', { class: 'num' }, fmtStep(B.steps[B.steps.length - 1])), h('td', { class: 'num' }, tName(tp)),
          h('td', { class: 'num' }, f3(t.model_spread)), h('td', { class: 'num' }, f3(t.ref_spread)),
          h('td', { class: 'num' }, sg(t.mean_delta)), h('td', { class: 'num' }, ciTxt(t.t_ci95, sg)), h('td', { class: 'num' }, ciTxt(t.boot_ci95, sg)),
          h('td', { class: 'num' }, t.n_below_0 + ' of ' + t.n_seeds), h('td', null, verdictWords(t))]));
      });
    });
    var tb = document.getElementById('learn-table');
    tb.innerHTML = '';
    tb.appendChild(h('table', null, [h('thead', null, h('tr', null, [two ? 'Model and thing' : 'Thing', 'Last step', 'Temperature', 'Its variety', 'Learned from', 'Difference',
      '95% CI across runs', '95% CI, runs and drawings', 'Runs narrower', 'Verdict'].map(function (x, k) { return h('th', { class: k && k < 9 ? 'num' : null }, x); }))),
      h('tbody', null, rows)]));
    tb.appendChild(h('p', { class: 'ls-note' }, 'At the last step. Variety: mean pairwise distance in sets of 16. The plan’s rule: narrower only if both CIs lie below 0.' +
      (two ? ' For the larger model, the runs trained after the test was written down (the first run is left out).' : '')));
  }

  function renderLearn() {
    if (!ss() || !ss().concepts || !ss().concepts.chair) { document.getElementById('learn').hidden = true; return; }
    renderPlayer();
    renderStroke();
    renderVerdict();
    renderLearnCurves();
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
    var lastW = window.innerWidth, resizeTimer = 0;
    window.addEventListener('resize', function () {  // the meters are drawn at the column's width
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        if (window.innerWidth === lastW) return;
        lastW = window.innerWidth;
        renderStage();
      }, 150);
    });
    thingSelect();
    renderAnswer();
    renderAll();
    renderLearn();
  }

  TOT.api('/api/plato/lifespan').then(function (data) { D = data; init(); }).catch(function (e) {
    var el = document.getElementById('load-error');
    el.textContent = 'The results didn’t load: ' + (e && e.message ? e.message : e);
    el.hidden = false;
  });
})();
