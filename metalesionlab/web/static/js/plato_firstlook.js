/* First look: the headline numbers of /plato/inside, /plato/forms, /plato/atlas and /plato/scale (plato_firstlook.css
   lays them out). Each page's numbers are worked out here from the page's own data (the JSON its /api route
   returns), at most three, each drawn as a small graphic with its honest qualifier in a smaller line.

   The other six series pages (cave, cratylus, bird, damage, telephone, lifespan) build their own {stats, note} in their
   page scripts and draw them with FirstLook.render, so all ten first screens share one look (plato_firstscreen.css).
   The damage numbers live here too (FirstLook.damage), because the Damaged AI hub (/damaged) draws the same ones
   (FirstLook.damaged, with Stable Diffusion XL's God from /plato/ideas).

   FirstLook.inside(data), .forms(data), .atlas(data) and .scale(data) return {stats: [{kind, o, q}], note}: kind is a
   statviz kind (dots, spread, bars) or one drawn here, o its options, q the qualifier. FirstLook.html(spec) is one
   graphic's markup and FirstLook.render(box, page) puts a page's numbers in box. All of it but render is pure
   string work, so node can run it in the tests (tests/test_plato_firstlook.py).

   statviz.js draws dots, spread clusters and bars. The kinds it has no form for are drawn here in statviz's own
   classes, so statviz.css styles them too: lrange (an n-layer bar with a marker and a range band), fails (a strip of
   answers per model, the failures filled), ratio (dots on a line where people's spread is 1) and pbars (bars that
   read as percentages). Colours come from the site's tokens through those classes; nothing here names a colour. */
(function (root) {
  'use strict';

  var SV = root && root.StatViz ? root.StatViz : (typeof require === 'function' ? require('./statviz.js') : null);

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function f2(x) { return Number(x).toFixed(2); }
  function pct(x) { return Math.round(x * 100) + '%'; }
  function ci(c) { return f2(c[0]) + '–' + f2(c[1]); }
  function signed(v, digits) {
    var s = digits == null ? String(Math.abs(v)) : Math.abs(v).toFixed(digits);
    return (v > 0 ? '+' : v < 0 ? '−' : '') + s;
  }
  function quoted(list) { return list.map(function (t) { return '“' + t + '”'; }).join(', '); }
  function median(xs) {
    var s = xs.slice().sort(function (a, b) { return a - b; }), m = s.length >> 1;
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  }

  // The same frame statviz.html gives a graphic: the number, the plot, the caption.
  function frame(value, unit, plot, label) {
    return (value ? '<p class="sv-val" aria-hidden="true"><span class="sv-num">' + esc(value) + '</span>' +
      (unit ? '<span class="sv-unit">' + esc(unit) + '</span>' : '') + '</p>' : '') +
      '<div class="sv-plot">' + plot + '</div>' + (label ? '<p class="sv-cap">' + esc(label) + '</p>' : '');
  }

  // ---------- the graphics statviz has no kind for ----------

  // n segments, filled from layer `at` to the last; a band behind the segments lo..hi; a marker at `at`.
  function lrange(o) {
    var n = o.n, at = o.at, w = 6, gap = 2, step = w + gap, top = 14, hh = 26, W = n * step - gap, out = [];
    out.push('<rect class="fl-band" x="' + ((o.lo - 1) * step - 2) + '" y="' + (top - 4) + '" width="' + ((o.hi - o.lo) * step + w + 4) +
      '" height="' + (hh + 8) + '" rx="3"/>');
    for (var i = 1; i <= n; i++) {
      out.push('<rect class="' + (i >= at ? 'sv-on sv-blue' : 'sv-off-fill') + '" x="' + (i - 1) * step + '" y="' + top + '" width="' + w +
        '" height="' + hh + '" rx="1.5"' + (i >= at ? ' style="--d:' + (i - at) * 24 + 'ms"' : '') + '/>');
    }
    var mx = (at - 1) * step + w / 2, mid = ((o.lo + o.hi) / 2 - 1) * step + w / 2;
    var alt = o.alt || ('Layer ' + at + ' of ' + n + ', range ' + o.lo + ' to ' + o.hi);
    return frame(String(at), 'of ' + n + ' layers',
      '<div class="sv-lay" style="--n:' + n + '"><svg class="sv-svg" viewBox="-4 0 ' + (W + 8) + ' ' + (top + hh + 4) + '" role="img" aria-label="' +
      esc(alt) + '"><title>' + esc(alt) + '</title>' + out.join('') + '<path class="sv-mark" d="M' + (mx - 5) + ' 1h10l-5 8z"/></svg>' +
      '<span class="sv-ticks fl-lticks" aria-hidden="true"><span>1</span><span class="fl-lband" style="left:' + (100 * (mid + 4) / (W + 8)).toFixed(1) + '%">' +
      o.lo + '–' + o.hi + '</span><span>' + n + '</span></span></div>', o.label);
  }

  // One row of squares per model, one square per answer, filled where the answer failed.
  function fails(o) {
    var cell = 10, cols = Math.max.apply(null, o.rows.map(function (r) { return r.tiles.length; })), out = [];
    o.rows.forEach(function (r, ri) {
      r.tiles.forEach(function (fail, i) {
        out.push('<rect class="' + (fail ? 'sv-on sv-muted' : 'sv-off') + '" x="' + (i * cell + 1) + '" y="' + (ri * 16 + 1) +
          '" width="8" height="8" rx="1.5"' + (fail ? ' style="--d:' + i * 30 + 'ms"' : '') + '/>');
      });
    });
    var alt = o.rows.map(function (r) { return r.label + ': ' + r.tiles.filter(Boolean).length + ' of ' + r.tiles.length + ' failed'; }).join('; ');
    return frame(o.value, o.unit, '<div class="fl-fails">' + o.rows.map(function (r) { return '<span>' + esc(r.label) + '</span>'; }).join('') +
      '<svg class="sv-svg" viewBox="0 0 ' + cols * cell + ' ' + (o.rows.length * 16 - 6) + '" role="img" aria-label="' + esc(alt) + '"><title>' + esc(alt) +
      '</title>' + out.join('') + '</svg></div>', o.label);
  }

  // Dots on one line from 0 to hi, people's spread at 1; a point may be a ring (a reference) or big (the one that matters).
  function ratio(o) {
    var W = 300, H = 46, L = 6, R = 6, hi = o.hi, out = [];
    var X = function (v) { return (L + Math.min(v, hi) / hi * (W - L - R)).toFixed(1); };
    out.push('<line class="fl-rs-axis" x1="' + L + '" x2="' + (W - R) + '" y1="24" y2="24"/>');
    out.push('<line class="fl-rs-people" x1="' + X(1) + '" x2="' + X(1) + '" y1="8" y2="34"/>');
    out.push('<text class="fl-rs-lab" x="' + X(1) + '" y="5" text-anchor="middle">people 1×</text>');
    [0, 0.5, 1.5].filter(function (v) { return v <= hi; }).forEach(function (v) {
      out.push('<text class="fl-rs-tick" x="' + X(v) + '" y="45" text-anchor="middle">' + v + '</text>');
    });
    o.pts.forEach(function (p, i) {
      out.push(p.ring ? '<circle class="fl-rs-ring" cx="' + X(p.x) + '" cy="24" r="6"/>'
        : '<circle class="sv-on sv-' + p.tone + '" cx="' + X(p.x) + '" cy="24" r="' + (p.big ? 7 : 5) + '" style="--d:' + i * 80 + 'ms"/>');
    });
    var alt = o.pts.map(function (p) { return p.label + ' ' + f2(p.x) + '×'; }).join(', ') + ' people’s spread';
    var key = o.pts.filter(function (p) { return p.key; }).map(function (p) {
      return '<span><i class="' + (p.ring ? 'fl-ring' : 'sv-sw sv-' + p.tone) + '"></i>' + esc(p.key) + '</span>';
    }).join('');
    return frame(o.value, o.unit, '<svg class="sv-svg fl-rs" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + esc(alt) + '"><title>' +
      esc(alt) + '</title>' + out.join('') + '</svg><p class="fl-rs-key">' + key + '</p>', o.label);
  }

  // statviz's bars, with the values as percentages.
  function pbars(o) {
    var alt = o.rows.map(function (r) { return r.label + ' ' + pct(r.v); }).join(', ');
    return frame(o.value, o.unit, '<div class="sv-bars" role="img" aria-label="' + esc(alt) + '">' + o.rows.map(function (r, i) {
      return '<div class="sv-bar"><span class="sv-bar-l">' + esc(r.label) + '</span><span class="sv-track"><i class="sv-fill sv-' + r.tone +
        '" style="width:' + (100 * Math.max(0, Math.min(1, r.v))).toFixed(1) + '%;--d:' + i * 120 + 'ms"></i></span><span class="sv-bar-v">' +
        pct(r.v) + '</span></div>';
    }).join('') + '</div>', o.label);
  }

  var OWN = { lrange: lrange, fails: fails, ratio: ratio, pbars: pbars };

  function html(spec) {
    if (OWN[spec.kind]) return OWN[spec.kind](spec.o);
    if (SV) return SV.html(spec.kind, spec.o);
    // statviz didn't load: the number and its label as text
    var o = spec.o;
    return frame(o.value != null ? o.value : (o.k != null ? o.k + ' of ' + o.n : ''), '', '', o.label);
  }

  // spec.verdict (optional, {tone: 'yes' | 'no' | 'part', text}) leads the qualifier: how a planned prediction came out.
  function figure(spec) {
    var v = spec.verdict ? '<span class="fl-verdict ' + esc(spec.verdict.tone) + '">' + esc(spec.verdict.text) + '</span> ' : '';
    return '<figure class="fl-stat"><div class="sv sv-' + spec.kind + '" data-sv-done="1">' + html(spec) + '</div>' +
      '<figcaption class="fl-q">' + v + esc(spec.q) + '</figcaption></figure>';
  }

  function render(box, page) {
    box.innerHTML = page.stats.map(figure).join('');
    return box;
  }

  // ---------- each page's three numbers, from its data ----------

  function inside(d) {
    var sm = d.summary, ms = sm.mean_spread, n = d.n_layers || ms.muse.length, last = n - 1;
    var times = ms.people[last] / ms.muse[last], never = quoted(sm.never_collapse);
    var per = d.concepts.map(function (c) { return c.n.muse; });
    var lo = Math.min.apply(null, per), hi = Math.max.apply(null, per);
    return {
      stats: [
        { kind: 'lrange', o: { at: sm.median_collapse_layer, lo: sm.earliest_collapse, hi: sm.latest_collapse, n: n,
            label: 'the median layer where Muse’s doodles of a thing collapse',
            alt: 'Median layer ' + sm.median_collapse_layer + ' of ' + n + ' where Muse Image’s doodles of a thing collapse; the band is the range, ' +
              sm.earliest_collapse + ' to ' + sm.latest_collapse + ', over ' + sm.n_concepts + ' things.' },
          q: 'Range ' + sm.earliest_collapse + '–' + sm.latest_collapse + ' over ' + sm.n_concepts + ' things (the band). ' + never + ' never collapses.' },
        { kind: 'spread', o: { a: ms.muse[last], b: ms.people[last], aLabel: 'Muse Image', bLabel: 'People', value: Math.round(times) + '×',
            label: 'more spread out: people’s doodles of a thing against Muse’s, at the last layer' },
          q: f2(ms.people[last]) + ' against ' + f2(ms.muse[last]) + ' at layer ' + n + ', the mean of ' + sm.n_concepts + ' things. 0 would be one point.' },
        { kind: 'dots', o: { k: sm.collapse_at_or_before_name, n: sm.n_with_both, cols: Math.min(sm.n_with_both, 12), tone: 'blue',
            label: 'things whose doodles collapse at or before the layer where the word lens can read the name' },
          q: 'A median ' + sm.median_layers_between + ' layers earlier. ' + never + ' never collapses, so it isn’t counted.' }
      ],
      note: 'Exploratory: one model, one prompt, ' + sm.n_concepts + ' things, ' + (lo === hi ? lo : lo + '–' + hi) + ' doodles each. “Collapse” means ' +
        'Muse’s spread stays under half of people’s through the last layer, a line we chose after seeing the data.'
    };
  }

  function forms(d) {
    var c = d.clock, G = c.groups, p = G.people, m = G.muse_doodle_default, a = G.muse_doodle_asked;
    var e = (c.byeye_no_time || {}).muse_doodle_default, chance = Math.round(c.chance_ten_ten * 1000) / 10;
    var stats = [
      { kind: 'dots', o: { k: e ? e.sure : m.ten_ten.k, n: e ? e.n : m.n, cols: 8, tone: 'blue', label: 'of Muse Image’s clocks show 10:10 when no time is asked' },
        q: e ? 'Counted by eye. Our automatic reader, which often put the hour one too high, counted ' + m.ten_ten.k + ' and read most of the others as 11:10.'
          : 'Read by our automatic reader.' },
      { kind: 'dots', o: { k: p.ten_ten.k, n: p.n, cols: 40, tone: 'orange', value: pct(p.ten_ten.share), unit: '',
          label: 'of people’s clocks show about 10:10: ' + p.ten_ten.k + ' of ' + p.n },
        q: '“About 10:10”: within 10 minutes, hands either way round. If drawn times were random, ' + chance + '% would count.' }
    ];
    if (a) {
      stats.push({ kind: 'dots', o: { k: a.ten_ten.k, n: a.n, cols: 24, tone: 'blue', label: 'of Muse Image’s clocks show 10:10 when we ask for a time' },
        q: 'A default, not a limit: it draws the time asked. ' + pct(a.minute_correct) + ' have the minute hand right.' });
    }
    return { stats: stats, note: 'Pre-registered: the plan and its predictions were written before any picture was drawn. The count by eye came after.' };
  }

  function atlas(d) {
    var a = d.summary.all, n = d.summary.n_concepts, nw = d.summary.new, sd = d.summary.sdxl.all;
    return {
      stats: [
        { kind: 'dots', o: { k: a.below_1, n: n, cols: 45, tone: 'blue', label: 'things Muse Image draws more alike than people do' },
          q: 'Its 95% CI is entirely below 1 for ' + a.ci_entirely_below_1 + ' of them, and entirely above 1 for ' + a.ci_entirely_above_1 + '.' },
        { kind: 'bars', o: { values: [a.median, 1], labels: ['Muse Image', 'People'], tones: ['blue', 'orange'], max: 1, digits: 2, value: pct(a.median),
            label: 'as varied as people: Muse Image’s spread over people’s, the median of ' + n + ' things' },
          q: 'Median ratio ' + f2(a.median) + ' (95% CI ' + ci(a.median_ci95) + '); 1 would be as varied as people.' },
        { kind: 'dots', o: { k: nw.below_1, n: nw.n, cols: 33, tone: 'blue', label: 'of the ' + nw.n + ' new things, picked at random, below 1: the pre-registered test' },
          q: 'Their median ratio is ' + f2(nw.median) + ' (95% CI ' + ci(nw.median_ci95) + ').' }
      ],
      note: 'An open model, Stable Diffusion XL, given the same prompt: median ratio ' + f2(sd.median) + ', below 1 for ' + sd.below_1 + ' of ' + sd.n +
        '. One prompt and one drawing style; people’s extra spread is partly their wobbly 20-second lines.'
    };
  }

  function scale(d) {
    var rows = d.arm_b.rows.filter(function (r) { return r.temp === 1; }), by = {}, wall = {};
    rows.forEach(function (r) { by[r.key] = r; });
    d.wall.models.forEach(function (m) { wall[m.key] = m; });
    var P3 = d.predictions.P3.model_size, P2 = d.predictions.P2.model_size, P1 = d.predictions.P1.data_size;
    var of12 = function (v) { return signed(Math.round(v * 12)); };
    var checks = Object.keys(P3.checks), held = checks.filter(function (k) { return P3.checks[k] === 'supported'; }).length;
    var family = d.arm_b.family_tests['Qwen2.5|1.0'].failure_rate, small = wall[family.smallest], big = wall[family.largest];
    var top = rows.filter(function (r) { return r.kind === 'open' && r.family !== 'Muse' && r.params_b >= 30; });
    var spreads = top.map(function (r) { return r.spread_ratio; });
    var wonder = by.wonder, museImage = d.anchors.muse_image.spread / d.anchors.people.spread_n12;
    var arm = d.arm_a.rows.filter(function (r) { return r.temp === 1 && r.checkpoint === 'final'; }).sort(function (x, y) { return x.size - y.size; });
    var first = arm[0], last = arm[arm.length - 1], learned = arm.map(function (r) { return r.train_spread; });
    var size = function (r) { return r.size.toLocaleString('en-US'); };
    var params = function (m) { return m.label.split(' ').pop(); };
    return {
      stats: [
        { kind: 'fails', o: { value: small.failed + ' → ' + big.failed, unit: 'failures in 12',
            rows: [{ label: params(small), tiles: small.tiles }, { label: params(big), tiles: big.tiles }],
            label: 'drawings that failed, ' + small.family + ' at ' + params(small) + ' and at ' + params(big) + ' parameters' },
          q: 'Planned prediction P3, fewer failures: supported, ' + of12(P3.contrast) + ' of 12 [' + of12(P3.ci95[0]) + ', ' + of12(P3.ci95[1]) + '], and in ' +
            held + ' of ' + checks.length + ' checks across the three families.' },
        { kind: 'ratio', o: { value: f2(wonder.spread_ratio) + '×', unit: 'people’s spread', hi: 1.7,
            pts: top.map(function (r, i) { return { x: r.spread_ratio, label: r.label, tone: 'muted', key: i ? null : 'open models at 32B' }; }).concat([
              { x: museImage, label: 'Muse Image', ring: true, key: 'Muse Image' },
              { x: wonder.spread_ratio, label: wonder.label, tone: 'ink', big: true, key: 'Muse Wonder' }]),
            label: 'Muse Wonder’s chairs, as narrow as Muse Image’s; the open models at 32B: ' + f2(Math.min.apply(null, spreads)) + ' to ' +
              Math.max.apply(null, spreads).toFixed(1) + '×' },
          q: 'No convergence with size: P2 unclear, ' + signed(P2.contrast, 3) + ' [' + signed(P2.ci95[0], 3) + ', ' + signed(P2.ci95[1], 3) + '] for ' +
            small.family + '. Meta doesn’t publish Wonder’s size, so it says nothing about scale.' },
        { kind: 'pbars', o: { value: pct(first.recog.mean) + ' → ' + pct(last.recog.mean), unit: '',
            rows: [{ label: size(first) + ' chairs', v: first.recog.mean, tone: 'muted' }, { label: size(last) + ' chairs', v: last.recog.mean, tone: 'blue' }],
            label: 'of the sketch model’s chairs recognizable, as its training grows from ' + size(first) + ' to ' + size(last) + ' people’s chairs' },
          q: 'P1 supported: ' + signed(Math.round(P1.contrast * 100)) + ' points [' + signed(Math.round(P1.ci95[0] * 100)) + ', ' +
            signed(Math.round(P1.ci95[1] * 100)) + ']. Not more alike: their spread stays about ' + f2(median(arm.map(function (r) { return r.spread.mean; }))) +
            ', below the chairs it learned from (' + f2(Math.min.apply(null, learned)) + ' to ' + f2(Math.max.apply(null, learned)) + ').' }
      ],
      note: 'Every prediction was planned before any run and is reported whichever way it came out. 12 drawings per model, one prompt, and one vision ' +
        'model (DINOv2) to measure spread.'
    };
  }

  // ---------- damage: the first screens of /plato/damage and of the Damaged AI hub (/damaged) ----------
  // d is what /api/plato/damage returns, ideas what /api/plato/ideas returns (its "damage": Stable Diffusion XL's God
  // under damage). The numbers and each planned prediction's verdict are worked out once, here, from the data (never
  // typed in); /plato/damage words them for its own readers, the hub in plain words for anyone.

  function pts(x) { return (x < 0 ? '−' : '+') + Math.abs(Math.round(x * 100)) + ' pts'; }
  function ciPts(c) { return '95% CI ' + pts(c[0]) + ' to ' + pts(c[1]); }
  function excludesZero(c) { return !!c && (c[0] > 0 || c[1] < 0); }
  function plus(v) { return (v < 0 ? '−' : '+') + Math.abs(v); }
  // A matched test {difference, ci95, predicted_sign}: {tone, text} for figure()'s verdict.
  function verdictOf(t) {
    var held = excludesZero(t.ci95) && Math.sign(t.difference) === t.predicted_sign;
    var rev = excludesZero(t.ci95) && Math.sign(t.difference) === -t.predicted_sign;
    return held ? { tone: 'yes', text: 'As predicted' } : rev ? { tone: 'no', text: 'Prediction reversed' } : { tone: 'part', text: 'Not distinguishable at this n' };
  }
  function plainVerdict(v) { return v.tone === 'part' ? { tone: 'part', text: 'Too close to call' } : v; }
  function primary(d) { return (d.matched || {})['text-zero vs unet-zero'] || {}; }  // the pre-registered contrast

  // The numbers. What: the asked kind, lost faster after language damage (the pre-registered primary test).
  function kindNumbers(d) {
    var kc = primary(d).delta_correct;
    return kc ? { kc: kc, lang: Math.round(-kc.language * 100), draw: Math.round(-kc.drawing * 100) } : null;
  }
  // Back to the plain chair, as in semantic dementia? Farther from it, not closer.
  function protoNumbers(d) {
    var pooled = d.pooled || {}, pz = (pooled['text-zero'] || {}).delta_d_proto, pd = (pooled['unet-zero'] || {}).delta_d_proto;
    var h2 = primary(d).delta_d_proto;
    if (!pz || !pd) return null;
    return { pz: pz, pd: pd, farther: pz.ci95[0] > 0,
      verdict: h2 ? (verdictOf(h2).tone === 'yes' ? verdictOf(h2) : { tone: 'no', text: 'Prediction failed' }) : null };
  }
  // Clocks: the mildest drawing damage strips the numbers first.
  function clockNumbers(d) {
    var c = d.clocks, fi = c && c.feature_names ? c.feature_names.indexOf('12 numbers in order') : -1;
    if (fi < 0) return null;
    var intact = c.features.filter(function (r) { return r.cond === 'intact'; })[0];
    var mild = c.features.filter(function (r) { return r.cond.indexOf('unet-zero@') === 0; })
      .sort(function (x, y) { return parseFloat(x.cond.split('@')[1]) - parseFloat(y.cond.split('@')[1]); })[0];
    return intact && mild ? { a: Math.round(intact.values[fi] * 100), b: Math.round(mild.values[fi] * 100), mild: mild } : null;
  }
  // How the planned split ("what" vs "how") came out.
  function splitParts(d) {
    var m = primary(d), kc = m.delta_correct, clean = m.delta_p_clean, cn = ((d.matched || {})['text-noise vs unet-noise'] || {}).delta_p_clean;
    if (!kc || !clean || !cn) return null;
    var p = { what: verdictOf(kc).tone === 'yes', noise: verdictOf(cn).tone === 'yes', off: verdictOf(clean).tone === 'yes',
      offReversed: verdictOf(clean).tone === 'no' };
    p.head = p.what && p.noise && p.off ? 'Supported.' : p.what || p.noise || p.off ? 'Partly supported.' : 'Not supported.';
    return p;
  }
  // God: more of Stable Diffusion XL's drawings of God become an ordinary person (a person with neither beard nor halo)
  // under language damage than under drawing damage (the pre-registered D3, by Muse Glimmer; by eye as a check).
  function godNumbers(ideas) {
    var x = ideas && ideas.damage, t = x && x.tests, d3 = t && t.D3, n = x && x.n_seeds;
    if (!d3 || !n) return null;
    var eye = t.D3_eye;
    return { n: n, a: Math.round(d3.language_rise * n), b: Math.round(d3.drawing_rise * n),
      eye: eye ? [Math.round(eye.language_rise * n), Math.round(eye.drawing_rise * n)] : null,
      verdict: d3.passes ? { tone: 'yes', text: 'As predicted' } : { tone: 'no', text: 'Prediction failed' } };
  }

  // /plato/damage: the asked kind, the plain chair, the clocks; and how the split came out.
  function damage(d) {
    var k = kindNumbers(d), pr = protoNumbers(d), c = clockNumbers(d), sp = splitParts(d), stats = [];
    if (k) {
      stats.push({ kind: 'bars', verdict: verdictOf(k.kc),
        o: { values: [k.lang, k.draw], labels: ['language', 'drawing'], tones: ['blue', 'orange'], max: 100, value: k.lang + ' vs ' + k.draw, unit: ' pts',
          label: 'fewer chairs still the asked kind, at equal picture change',
          alt: 'Language part damaged: ' + k.lang + ' points fewer chairs still read as the asked kind; drawing part damaged: ' + k.draw +
            ' points fewer, at the same amount of picture change (neurons switched off).' },
        q: 'Pre-registered test: ' + pts(k.kc.difference) + ', ' + ciPts(k.kc.ci95) + '.' });
    }
    if (pr) {
      stats.push({ kind: 'bars', verdict: pr.verdict,
        o: { values: [pr.pz.mean, pr.pd.mean], labels: ['language', 'drawing'], tones: ['blue', 'orange'], digits: 2,
          value: pr.farther ? 'Farther' : 'No closer', unit: '', label: 'from the plain chair, not back to it (change in distance)',
          alt: 'Back to the plain chair? No. Distance to the plain chair grew by ' + pr.pz.mean.toFixed(2) + ' after language damage and by ' +
            pr.pd.mean.toFixed(2) + ' after drawing damage (neurons switched off, averaged over the damage levels).' },
        q: 'Predicted: back toward the plain chair, as in semantic dementia.' });
    }
    if (c) {
      stats.push({ kind: 'bars',
        o: { values: [c.a, c.b], labels: ['intact', 'drawing'], tones: ['ink', 'orange'], max: 100, value: c.a + '% → ' + c.b + '%', unit: '',
          label: 'clocks with all 12 numbers in order: drawing damage strips them first',
          alt: 'Clocks with all 12 numbers in order: ' + c.a + '% intact, ' + c.b + '% after the mildest drawing damage (' + c.mild.label + ').' },
        q: 'The mildest drawing damage. Language damage removes the whole clock instead.' });
    }
    return { stats: stats, split: sp && { head: sp.head, text: 'The “what” half ' + (sp.what ? 'held' : 'did not hold') + '; the “how” half ' +
      (sp.noise ? 'held for noise' : 'did not hold for noise') + (sp.offReversed ? ' but reversed for neurons switched off' : '') } };
  }

  // /damaged, in plain words: the asked kind, God, the clocks (either API may be missing), each number's meaning first;
  // then, for the note, how the planned split came out and whether the chairs went back to the plain chair.
  function damaged(d, ideas) {
    var k = d && kindNumbers(d), g = godNumbers(ideas), c = d && clockNumbers(d), stats = [];
    var parts = ['words part', 'drawing part'];
    if (k) {
      var kv = plainVerdict(verdictOf(k.kc));
      stats.push({ kind: 'bars', verdict: kv,
        o: { values: [k.lang, k.draw], labels: parts, tones: ['blue', 'orange'], max: 100, value: k.lang + ' vs ' + k.draw, unit: ' in 100',
          label: 'chairs stopped being the kind we asked for',
          alt: 'After damage to the part that reads the words, ' + k.lang + ' in every 100 chairs stopped being the kind asked for. After the same ' +
            'amount of damage to the part that paints the picture, ' + k.draw + ' in 100 did.' },
        q: 'Equal damage to each part' + (kv.tone === 'yes' ? '; too big a gap for chance.' : '.') });
    }
    if (g) {
      stats.push({ kind: 'bars', verdict: g.verdict,
        o: { values: [g.a, g.b], labels: parts, tones: ['blue', 'orange'], max: g.n, value: plus(g.a) + ' vs ' + plus(g.b), unit: ' of ' + g.n,
          label: 'more drawings of God became an ordinary person',
          alt: 'Of Stable Diffusion XL’s ' + g.n + ' drawings of God, ' + g.a + ' more showed an ordinary person, with no beard and no halo, after the ' +
            'most damage to the part that reads the words. After the most damage to the part that paints the picture, ' + g.b + ' more did.' },
        q: 'Heaviest damage.' + (g.eye ? ' Counted by eye instead: ' + plus(g.eye[0]) + ' vs ' + plus(g.eye[1]) + '.' : '') });
    }
    if (c) {
      stats.push({ kind: 'bars',
        o: { values: [c.a, c.b], labels: ['undamaged', 'drawing part'], tones: ['ink', 'orange'], max: 100, value: c.a + '% → ' + c.b + '%', unit: '',
          label: 'of clocks had all 12 numbers: undamaged, then lightly damaged',
          alt: 'Clocks with all 12 numbers in order: ' + c.a + '% undamaged, ' + c.b + '% after the lightest damage to the part that paints the picture.' },
        q: 'Words-part damage erases the whole clock instead.' });
    }
    var pr = d ? protoNumbers(d) : null;
    return { stats: stats, split: d ? splitParts(d) : null, proto: pr && pr.verdict ? { verdict: pr.verdict, farther: pr.farther } : null };
  }

  var api = { inside: inside, forms: forms, atlas: atlas, scale: scale, damage: damage, damaged: damaged,
    html: html, figure: figure, render: render };
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root && root.document) root.FirstLook = api;
})(typeof window !== 'undefined' ? window : this);
