/* The clock test (/plato/clock). Reads /api/plato/clock (web/data/plato_clock.json, written by scripts/plato_clock.py):
   Muse Image's clocks for the MoCA's words with their eye and Muse Spark scores, the age personas, the clocks drawn in
   code, /plato/damage's SDXL clocks with their checklist score, and the people's side, which is group averages of at
   least 20 adults and aggregate numbers only. Nothing per person exists in the data, so nothing here can show it.

   Visible text follows the plain-language rule: each sentence stands alone, things are named in full the first time,
   no unexplained jargon (no "rho", "CI", "spread" or "embedding" on the page), meaning first and exact numbers second.

   ClockPage.firstLook(data) returns the first screen's {answer, stats, note} (drawn by FirstLook.render): pure string
   work, so node runs it in the tests against the real data (tests/test_plato_clock.py). Everything else is DOM.
   Colours come from the site's tokens (plato_clock.css); line art sits on paper. */
(function (root) {
  'use strict';

  function pct(x) { return Math.round(100 * x) + '%'; }
  function f2(x) { return Number(x).toFixed(2); }
  function signed(x, d) { var s = Math.abs(x).toFixed(d == null ? 2 : d); return (x > 0 ? '+' : x < 0 ? '−' : '') + s; }
  function range(ci, d) { return '(probably between ' + signed(ci[0], d) + ' and ' + signed(ci[1], d) + ')'; }
  function count(times, k) { return (times && times[k]) || 0; }
  function words(n) { return ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'][n] || String(n); }
  function cap(s) { return s.replace(/^./, function (c) { return c.toUpperCase(); }); }
  function clear(r) { return r.ci95[0] > 0 || r.ci95[1] < 0; }  // a range for a link that leaves out zero
  var TIME = { '11:10': '10 past 11', '10:10': '10:10, the advert time', swapped: 'hands the wrong way round', other: 'another time', none: 'no time' };

  // ---------- the first screen: pure, from the data ----------
  function firstLook(d) {
    var P = d.people, M = d.muse, e = M.eye, s = M.spark, full = P.full_points;
    var at = count(e.times, '11:10'), ten = count(e.times, '10:10'), sw = count(e.times, 'swapped'), oth = count(e.times, 'other');
    var p1 = d.predictions && d.predictions.P1;
    var agree = M.agreement;
    return {
      answer: (at > 8 ? 'Yes: ' : 'Not on the hands: ') + 'Meta’s image AI drew 10 past 11, with all 12 numbers, on ' + e.all_three +
        ' of its ' + M.n + ' clocks.',
      stats: [
        { kind: 'dots', ask: 'Adults who got all three points', o: { k: full.k, n: full.n, cols: 35, tone: 'orange', value: pct(full.k / full.n), unit: '',
            label: 'of adults got all three points' },
          q: full.k + ' of ' + full.n + ' adults got all three points for their clock. Marked by the study’s own raters. ' + P.two_points.k + ' more got two of the three points: a circle, all 12 numbers, and the hands at 10 past 11.' },
        { kind: 'dots', ask: 'AI clocks that show 10 past 11', o: { k: at, n: M.n, cols: 8, tone: 'blue', label: 'of the AI’s clocks show 10 past 11, by our count' },
          verdict: p1 ? { tone: p1.supported ? 'yes' : 'no', text: 'We expected 7 or fewer' } : null,
          q: 'Counted by us, not by software. ' + (ten ? ten + ' show 10:10, the watch-advert time. ' : 'None shows 10:10. ') + (sw ? cap(words(sw)) + ' have the long and short hands the wrong way round' : '') +
            (oth ? (sw ? ', and ' : '') + words(oth) + ' has a third hand' : '') + '. Meta’s chat AI, Muse Spark, marking the same clocks, counted only ' +
            count(s.times, '11:10') + ': it mixed up which hand was which.' },
        { kind: 'pbars', ask: 'AI clocks that get each point', o: {
            rows: [{ label: 'Circle', v: e.contour.k / M.n, k: e.contour.k, n: M.n, tone: 'blue' }, { label: '12 numbers', v: e.numbers.k / M.n, k: e.numbers.k, n: M.n, tone: 'blue' },
                   { label: 'Hands', v: e.hands.k / M.n, k: e.hands.k, n: M.n, tone: 'blue' }],
            label: 'of the AI’s clocks get each point, by our count' },
          q: 'Muse Spark agreed with us on the circle and the numbers for all ' + M.n + ', but on the hands for only ' + agree.hands.agree + '.' }
      ],
      note: 'Before the AI drew anything, we wrote down that we expected it to get the hands wrong on most clocks. It didn’t. One AI drew 16 clocks for ' +
        'the same words; ' + full.n + ' people drew one each, on paper. This compares an AI with a test, and is not a diagnosis of anyone.'
    };
  }

  var api = { firstLook: firstLook };
  if (typeof module === 'object' && module.exports) { module.exports = api; return; }
  root.ClockPage = api;
  if (!root.document) return;

  // ---------- the page ----------
  var T = root.TOT, h = T.h, D = null;
  function $(id) { return document.getElementById(id); }
  function reduced() { return root.matchMedia && root.matchMedia('(prefers-reduced-motion: reduce)').matches; }
  function seg(box, items, current, onPick) {
    box.textContent = '';
    items.forEach(function (it) {
      box.appendChild(h('button', { type: 'button', 'aria-pressed': String(it.v === current), text: it.label,
        onclick: function () {
          box.querySelectorAll('button').forEach(function (b) { b.setAttribute('aria-pressed', String(b === this)); }, this);
          onPick(it.v);
        } }));
    });
  }
  function chips(sc) {  // the three points as small labelled marks
    return h('span', { class: 'pk-chips', 'aria-label': 'Circle ' + (sc.contour ? 'yes' : 'no') + ', numbers ' + (sc.numbers ? 'yes' : 'no') +
      ', hands ' + (sc.hands ? 'yes' : 'no') }, [['C', sc.contour], ['N', sc.numbers], ['H', sc.hands]].map(function (x) {
      return h('i', { class: x[1] ? 'on' : 'off', 'aria-hidden': 'true', title: { C: 'Circle', N: 'All 12 numbers', H: 'Hands at 10 past 11' }[x[0]] }, x[0]);
    }));
  }
  function timeOf(c) { return c.eye.time === 'other' && c.hands_n > 2 ? 'three hands' : TIME[c.eye.time] || c.eye.time; }
  function sparkTime(c) { return c.spark.time === 'swapped' ? 'hands mixed up' : TIME[c.spark.time] || c.spark.time; }
  function clockFig(c, opts) {
    opts = opts || {};
    var cap = [h('span', { class: 'pk-time' }, [timeOf(c)]), chips(c.eye)];
    if (opts.spark && c.spark) cap.push(h('span', { class: 'pk-spark', text: 'Muse Spark: ' + sparkTime(c) + ', ' + c.spark.total + ' of 3' }));
    return h('figure', { class: 'pk-clock' }, [
      h('img', { src: c.src, width: opts.size || 320, height: opts.size || 320, loading: 'lazy',
        alt: 'A clock by Meta’s image AI: ' + timeOf(c) + ', ' + c.eye.total + ' of 3 points by our count.' }),
      h('figcaption', null, cap)]);
  }

  function hero() {
    var fl = firstLook(D);
    $('hero-answer').textContent = fl.answer;
    root.FirstLook.render($('hero-stats'), fl);
    $('hero-note').textContent = fl.note;
    document.querySelectorAll('[data-k="n_analysed"]').forEach(function (n) { n.textContent = D.people.n_analysed; });
    $('hero-people').src = D.people.avg_all;
    var wall = $('hero-wall'), img = $('hero-ai');
    D.muse.clocks.forEach(function (c) { wall.appendChild(h('img', { src: c.src, alt: '', loading: 'lazy', width: 160, height: 160 })); });
    wall.setAttribute('role', 'img');
    wall.setAttribute('aria-label', 'Meta’s image AI’s 16 clocks: ' + D.muse.eye.all_three + ' show 10 past 11 with all 12 numbers.');
    seg($('ai-seg'), [{ v: 'avg', label: 'Combined' }, { v: 'all', label: 'All 16' }], 'avg', function (v) {
      wall.hidden = v !== 'all';
      img.hidden = v === 'all';
      $('hero-ai-cap').textContent = v === 'all' ? 'Its 16 clocks, one by one.' : 'Its 16 clocks, laid on top of each other the same way.';
    });
  }

  function points() {
    var M = D.muse, grid = $('muse-grid');
    M.clocks.forEach(function (c) { grid.appendChild(clockFig(c, { spark: true })); });
    var a = M.agreement, e = M.eye, s = M.spark;
    var withHands = M.clocks.filter(function (c) { return c.eye.hands; }).map(function (c) { return c.ratio; });
    $('agree-facts').appendChild(h('div', { class: 'pk-fact muse' }, [h('b', { text: 'Agreed on ' + a.hands.agree + ' of ' + M.n }),
      h('span', { text: 'We and Muse Spark agreed on every circle and every set of numbers, but on the hands for only ' + a.hands.agree +
        ' of the ' + M.n + ' clocks. The image AI draws its two hands nearly the same length: the hour hand is ' + Math.round(100 * Math.min.apply(null, withHands)) +
        '–' + Math.round(100 * Math.max.apply(null, withHands)) + '% as long as the minute hand. On ' + count(s.times, 'swapped') +
        ' clocks Muse Spark took the longer hand for the hour hand, and so read the time as 2:55.' })]));
    var strict = M.clocks.filter(function (c) { return c.eye.time === '11:10' && c.ratio != null; });
    var at = function (t) { return strict.filter(function (c) { return c.ratio <= t; }).length; };
    $('agree-facts').appendChild(h('div', { class: 'pk-fact' }, [h('b', { text: at(0.9) + ', ' + at(0.85) + ' or ' + at(0.8) + ' clocks' }),
      h('span', { text: 'get the hands point, depending on how much shorter the hour hand must be: at most 90%, 85% or 80% of the minute hand. ' +
        'The test doesn’t say, and neither did our plan; we chose 90% as we started marking, before Muse Spark saw any clock.' })]));
    var P = D.persona;
    $('time-facts').appendChild(h('div', { class: 'pk-fact muse' }, [h('b', { text: count(e.times, '11:10') + ' of ' + M.n + ' at 10 past 11' }),
      h('span', { text: 'and ' + (count(e.times, '10:10') ? count(e.times, '10:10') : 'none') + ' at 10:10. In an earlier experiment (The Platonic clock), asked only for “a clock”, the same AI drew ' +
        'the 10:10 of watch adverts on 13 of 16. Given the test’s words, it moved the hour hand to the 11.' })]));
    $('time-facts').appendChild(h('div', { class: 'pk-fact' }, [h('b', { text: count(P.eye.times, '11:10') + ' of ' + P.n + ' at 10 past 11' }),
      h('span', { text: 'when we told it the age of the person drawing (20 to 80), a different age each time, as in “Drawn by a 34-year-old: …”. ' + P.eye.hands.k + ' of those get the hands point; the other ' +
        (P.n - P.eye.hands.k) + ' have hands of almost equal length. Some also wrote “10 past 11” under the clock.' })]));
    var S = D.svg;
    $('svg-lede').textContent = 'Muse Spark and Meta’s Muse Wonder, an AI that writes drawing code, can’t paint pictures, but they can write one as drawing code (SVG). ' +
      'We gave each the same words, 16 times. Writing code, an AI has to work out where each hand points, and they did: by our count Muse Spark’s clocks got all ' +
      'three points ' + S.spark.eye.all_three + ' times in 16, and Muse Wonder’s ' + S.wonder.eye.all_three + ' times. Muse Spark’s checklist agreed with us on every one.';
    [['spark', 'Muse Spark'], ['wonder', 'Muse Wonder']].forEach(function (m) {
      var b = S[m[0]], row = h('div', { class: 'pk-svg-row', role: 'group', 'aria-label': m[1] + ', clocks written as code' });
      b.clocks.forEach(function (c) {
        row.appendChild(h('figure', { class: 'pk-svgc' + (c.eye.total < 3 ? ' miss' : '') }, [
          h('img', { src: c.src, width: 256, height: 256, loading: 'lazy', alt: m[1] + ', a clock written as code: ' +
            (c.eye.total < 3 && c.eye.time === 'other' ? 'the minute hand at the 1' : timeOf(c)) + ', ' + c.eye.total + ' of 3 points.' })]));
      });
      $('svg-rows').appendChild(h('div', { class: 'pk-svg-block' }, [h('p', { class: 'pk-svg-h' }, [h('b', { text: m[1] }), ': ' + b.eye.all_three +
        ' of 16 with all three points' + (b.failed ? ', ' + b.failed + ' didn’t draw' : '') + (b.eye.all_three < 16 ? ' (the outlined one has its minute hand at the 1)' : '')]), row]));
    });
  }

  function form() {
    var F = D.people.form, img = $('form-img'), i = 0, timer = 0;
    function show(k) {
      i = k;
      img.src = F[k].src;
      img.alt = F[k].n + ' adults’ clocks laid on top of each other' + (k === F.length - 1 ? ': all of them, a ghostly clock with its hands at 11 and 2.' : '.');
      $('form-cap').textContent = (k === F.length - 1 ? 'All ' + F[k].n + ' adults’ clocks.' : F[k].n + ' adults’ clocks, picked in a fixed random order.') +
        (k === 0 ? ' Even 20 already show a dent at the 11 and the 2.' : k === F.length - 1 ? ' No one drew this clock: it is what all of them share.' : '');
      $('form-seg').querySelectorAll('button').forEach(function (b, j) { b.setAttribute('aria-pressed', String(j === k)); });
    }
    seg($('form-seg'), F.map(function (f, k) { return { v: k, label: String(f.n) }; }), 0, function (k) { stop(); show(k); });
    function stop() { clearInterval(timer); timer = 0; $('form-play').textContent = 'Play'; }
    $('form-play').addEventListener('click', function () {
      if (timer) { stop(); return; }
      if (i === F.length - 1) show(0);
      $('form-play').textContent = 'Pause';
      timer = setInterval(function () { if (i >= F.length - 1) { stop(); return; } show(i + 1); }, reduced() ? 2200 : 1400);
    });
    show(0);
    var M = D.muse, ref = D.references.muse_doodle, ratio = D.people.spread / M.spread.value;
    $('form-ai-cap').textContent = 'Its 16 clocks for the same words lay on top of each other as one sharp clock, because they are nearly alike: ' +
      'they differ from one another about half as much as people’s clocks do (we call this spread: ' + f2(M.spread.value) + ' against ' + f2(D.people.spread) +
      '; 0 would mean identical copies). ' +
      'That isn’t always so: in an earlier experiment, asked only for “a quick doodle of a clock”, its 16 doodles varied about as much as people’s (' + f2(ref.spread) + ').';
    if (ratio < 1.5) $('form-ai-cap').textContent = $('form-ai-cap').textContent.replace('about half as much', 'less');
    var lv = $('levels');
    D.people.levels.forEach(function (l) {
      lv.appendChild(h('figure', { class: 'pk-level' }, [h('div', { class: 'pk-paper' }, [h('img', { src: l.src, width: 512, height: 512, loading: 'lazy',
        alt: l.n + ' adults’ clocks with ' + l.points + ' of 3 points, laid on top of each other.' })]),
        h('figcaption', { class: 'fl-cap' }, [h('b', { text: l.points === 3 ? 'All three points' : 'Two of three points' }), ': ' + l.n + ' adults’ clocks'])]));
    });
    lv.appendChild(h('p', { class: 'fl-cap pk-levels-note', text: 'The same, split by the points the study’s raters gave. ' +
      (D.people.n_analysed - D.people.full_points.k - D.people.two_points.k) + ' clocks got one point or none; they are too few (under 20) to show without ' +
      'someone’s own drawing showing through.' }));
  }

  function life() {
    var P = D.people, ages = D.persona, A = P.age_trend;
    var hands = P.decades.map(function (d) { return d.hands; });
    var lo11 = Math.min.apply(null, hands.map(function (x) { return x.to_11; })), hi11 = Math.max.apply(null, hands.map(function (x) { return x.to_11; }));
    var lo10 = Math.min.apply(null, hands.map(function (x) { return x.to_10; })), hi10 = Math.max.apply(null, hands.map(function (x) { return x.to_10; }));
    $('life-lede').textContent = 'People keep the ideal clock for life. Laid on top of each other, every age group’s clocks show the hands at 11 and 2, ' +
      'and the groups barely differ. The older groups’ clocks look a little busier around the edge and the numbers, but the hands are never lost. ' +
      'Each picture combines at least 20 people.';
    var box = $('decades'), pbox = $('personas');
    P.decades.forEach(function (d) {
      var r = d.age_range_years.replace('-', '–');
      box.appendChild(h('figure', { class: 'pk-decade' }, [
        h('div', { class: 'pk-paper' }, [h('img', { src: d.src, width: 512, height: 512, loading: 'lazy', alt: 'The clocks of ' + d.n + ' adults aged ' + r + ', laid on top of each other.' })]),
        h('figcaption', null, [h('b', { class: 'pk-age', text: 'Aged ' + r }), h('span', { class: 'pk-n', text: d.n + ' people' }),
          h('dl', { class: 'pk-dl' }, [
            h('dt', { text: 'All three points' }), h('dd', { text: pct(d.share_full) }),
            h('dt', { text: 'Average points' }), h('dd', { text: d.mean_points.toFixed(1) + ' of 3' }),
            h('dt', { text: 'How varied' }), h('dd', { text: f2(d.spread) }),
            h('dt', { text: 'Far from typical' }), h('dd', { text: f2(d.distance) })])])]));
      var col = h('div', { class: 'pk-pcol', role: 'group', 'aria-label': 'Meta’s image AI told the drawer was ' + r });
      d.personas.forEach(function (j) {
        var c = ages.clocks[j];
        col.appendChild(h('figure', { class: 'pk-pclock' }, [h('img', { src: c.src, width: 320, height: 320, loading: 'lazy',
          alt: 'Meta’s image AI, told “Drawn by a ' + c.age + '-year-old”: ' + timeOf(c) + ', ' + c.eye.total + ' of 3 points by our count.' }),
          h('figcaption', null, [h('b', { text: c.age }), chips(c.eye)])]));
      });
      pbox.appendChild(col);
    });
    var wrap = box.parentNode;
    wrap.parentNode.insertBefore(h('p', { class: 'fl-cap pk-dl-note', text: '“How varied”: how different the age group’s clocks are from one another (spread). ' +
      '“Far from typical”: how different its clocks look from all the full-marks clocks laid on top of each other. Both measure shape only, on a scale where 0 ' +
      'means identical.' }), wrap.nextSibling);
    $('persona-h').textContent = 'Meta’s image AI, told “Drawn by a ' + ages.ages[0] + '-year-old”, “… a ' + ages.ages[1] + '-year-old” and so on up to ' +
      ages.ages[ages.ages.length - 1];
    var lf = $('life-facts');
    var pts = A.rho_age_vs_clock_points, dist = A.rho_age_vs_distance, moca = A.rho_age_vs_moca_total;
    lf.appendChild(h('div', { class: 'pk-fact people' }, [h('b', { text: clear(pts) || clear(dist) ? 'A small change with age' : 'No clear change with age' }),
      h('span', { text: 'Across all ' + P.n_analysed + ' adults, older people’s clocks got about the same points as younger people’s, and looked just as typical. ' +
        'The link between age and points is ' + signed(pts.rho) + ' on a scale from −1 to +1 ' + range(pts.ci95) + '; between age and typical shape, ' +
        signed(dist.rho) + ' ' + range(dist.ci95) + '. Both are close to 0, no link.' })]));
    lf.appendChild(h('div', { class: 'pk-fact people' }, [h('b', { text: 'The hands survive at every age' }),
      h('span', { text: 'In each age group’s combined clock, the ink points toward the 11 between ' + Math.round(lo11) + ' and ' + Math.round(hi11) +
        ' times as strongly as toward an ordinary direction. Toward the 10, a common slip, it is only ' + lo10.toFixed(1) + ' to ' + hi10.toFixed(1) +
        ' times as strong. The whole memory test’s score does fall a little with age in this group, but the clock’s doesn’t (a link of ' + signed(moca.rho) +
        ', probably between ' + signed(moca.ci95[0]) + ' and ' + signed(moca.ci95[1]) + ').' })]));
    var V = ages.vs_people, T2 = ages.trend, sv = ages.spread_vs_default;
    var pf = $('persona-facts');
    pf.appendChild(h('div', { class: 'pk-fact muse' }, [h('b', { text: 'The AI’s idea of aging: the same clock' }),
      h('span', { text: 'Told only the age of the person drawing, Meta’s image AI drew ' + count(ages.eye.times, '11:10') + ' of ' + ages.n + ' clocks at 10 past 11. ' +
        'Its clocks for the 16 ages differed from one another no more than its 16 clocks with no age (spread ' + f2(ages.spread.value) + ' against ' +
        f2(D.muse.spread.value) + '). We had expected more variety. That didn’t happen.' })]));
    pf.appendChild(h('div', { class: 'pk-fact muse' }, [h('b', { text: 'No clear change with the age it was given' }),
      h('span', { text: 'The AI’s clocks for older ages didn’t get fewer points or look less typical. From the ' + V.young + ' group to the ' + V.old +
        ' group, people’s average points change by ' + signed(V.eye_points.people_change) + ' and the AI’s by ' + signed(V.eye_points.ai_change) +
        ' ' + range(V.eye_points.ai_ci95) + ': too close to call. We had expected the AI’s clocks for older ages to get worse. That didn’t happen: ' +
        'it did not draw older people’s clocks as shaky, and real older adults’ clocks aren’t shaky either.' })]));
    var rows = D.damage, dbox = $('dmg-row');
    var PART = { 'text-noise': 'Words part, noise added', 'text-zero': 'Words part, neurons off', 'unet-noise': 'Drawing part, noise added',
      'unet-zero': 'Drawing part, neurons off' };
    function showDmg(k) {
      var r = rows[k];
      dbox.textContent = '';
      r.levels.forEach(function (lv, j) {
        dbox.appendChild(h('figure', { class: 'pk-dmgc' }, [h('img', { src: lv.src, width: 512, height: 512, loading: 'lazy',
          alt: 'The open image AI’s clock, asked to show 8:45, ' + (j ? PART[r.method].toLowerCase() + ', step ' + j : 'undamaged') + '.' }),
          h('figcaption', null, [h('b', { text: j ? 'Step ' + j + ' of ' + (r.levels.length - 1) + (j === 1 ? ' (lightest)' : j === r.levels.length - 1 ? ' (heaviest)' : '') : 'Undamaged' }),
            h('span', { class: 'pk-score', text: 'checklist ' + lv.checklist.toFixed(1) + ' of 3' })])]));
      });
    }
    seg($('dmg-seg'), rows.map(function (r, k) { return { v: k, label: PART[r.method] }; }), 0, showDmg);
    showDmg(0);
  }

  function methods() {
    var M = D.muse, P = D.people, V = P.validation.rho_distance_vs_points;
    $('m-prompt').textContent = D.prompt;
    $('m-persona').textContent = D.persona_prompt.replace('{age}', '34');
    $('m-ages').textContent = D.persona.age_rule === 'even' ? 'The 16 ages were evenly spaced from 20 to 80, because the study’s age groups weren’t published yet when we ran this.'
      : 'The 16 ages were spread over the study’s age groups in proportion to their size.';
    $('m-people').textContent = 'We used ' + P.n_analysed + ' first-visit clocks; ' + P.n_excluded + ' of the ' + P.n_images +
      ' drawings couldn’t be cleaned up for the computer (lined paper, printed forms, or too faint).';
    $('m-valid').textContent = 'a link of ' + signed(V.rho) + ' on a scale from −1 to +1, where 0 is no link; clocks with three points and with two looked equally typical';
    var s = M.clocks.filter(function (c) { return c.eye.time === '11:10' && c.ratio != null; });
    $('m-strict').textContent = 'With a stricter line, fewer get the point: ' + s.filter(function (c) { return c.ratio <= 0.85; }).length + ' at 85%, ' +
      s.filter(function (c) { return c.ratio <= 0.8; }).length + ' at 80%.';
  }

  function pad() {
    if (!root.TOTDraw) return;
    root.TOTDraw.mount($('clock-pad'), {
      concept: 'clock', conceptLabel: 'clock', conceptMode: 'group', picker: false, deepLink: false, heading: 'h3',
      title: 'Draw a clock.', instruction: 'Put in all the numbers and set the time to 10 past 11.', results: $('clock-results')
    });
  }

  function start() {
    pad();
    T.api('/api/plato/clock').then(function (d) {
      D = d;
      [hero, points, form, life, methods].forEach(function (fn) {
        try { fn(); } catch (e) { if (root.console) root.console.error(e); }
      });
    }).catch(function (e) {
      var n = $('load-error');
      n.textContent = 'Couldn’t load the results: ' + e.message;
      n.hidden = false;
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})(typeof window !== 'undefined' ? window : this);
