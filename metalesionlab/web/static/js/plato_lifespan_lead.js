/* The life of a chair (/plato/lifespan), first screen: the answer's headline numbers drawn as small graphics
   (FirstLook.render and statviz.js, as on the other series pages). Group-level statistics only, from the same
   /api/plato/lifespan response plato_lifespan.js loads: this file is linked just before it and watches TOT.api for
   that one path, so the page still fetches it once. No child's drawing is ever shown. */
(function () {
  'use strict';
  var T = window.TOT, PATH = '/api/plato/lifespan';
  if (!T || !T.api) return;
  var api = T.api;
  T.api = function (path) {
    var p = api.apply(this, arguments);
    if (path === PATH) p.then(render, function () { /* plato_lifespan.js reports the error */ });
    return p;
  };

  function pct(x) { return Math.round(100 * x); }
  function f2(x) { return x.toFixed(2); }
  function signed(x, fmt) { return (x > 0 ? '+' : x < 0 ? '−' : '') + fmt(Math.abs(x)); }
  function ci(c, fmt) { return '[' + (c[0] < 0 ? '−' : '') + fmt(Math.abs(c[0])) + ', ' + (c[1] < 0 ? '−' : '') + fmt(Math.abs(c[1])) + ']'; }
  function excludesZero(c) { return c && (c[0] > 0 || c[1] < 0); }
  function verdict(held) { return held == null ? null : held ? { tone: 'yes', text: 'As predicted' } : { tone: 'no', text: 'Prediction failed' }; }

  function render(D) {
    var host = document.getElementById('hero-stats');
    if (!host || !window.FirstLook || !D || !D.children || !D.ai || !D.ai.all) return;
    var ch = D.children, c = ch.curves, ages = ch.ages, last = ages.length - 1, cp = ch.predictions || {};
    var ad = D.adults.mean_over_children_things, ai = D.ai.all, ck = ai.checkpoints, n = ck.length - 1, ap = ai.predictions || {};
    var r2 = pct(c.recog.mean[0]), r10 = pct(c.recog.mean[last]), rad = pct(ad.recog), rsd = pct(ai.curves.recog.mean[0]);
    var slope = (ch.tests.recog || {}).linear;
    var t = (ai.tests.d_adult || {}).last_minus_first || {}, sd0 = ai.curves.d_adult.mean[0], sdN = ai.curves.d_adult.mean[n];
    var one = function (v) { return (100 * v).toFixed(1); };
    window.FirstLook.render(host, { stats: [
      // 1. children become recognizable; Stable Diffusion's first public stage already is
      { kind: 'bars', verdict: verdict(cp.C1_recognizability_rises),
        o: { values: [r2, r10, rad, rsd], labels: ['age ' + ages[0], 'age ' + ages[last], 'adults', 'SD ' + ck[0]], tones: ['orange', 'orange', 'ink', 'green'],
          max: 100, value: r10 + '%', unit: 'at ' + ages[last] + ', from ' + r2 + '% at ' + ages[0],
          label: 'of children’s drawings recognizable as what was asked',
          alt: 'Recognizable: ' + r2 + '% of 2-year-olds’ drawings, ' + r10 + '% of 10-year-olds’, ' + rad + '% of adults’, and ' + rsd +
            '% of Stable Diffusion ' + ck[0] + '’s pictures.' },
        q: (slope ? signed(slope.mean_slope, one) + ' points a year ' + ci(slope.ci95, one) + '; ' : '') + 'adults ' + rad + '%, Stable Diffusion ' + ck[0] +
          ' already ' + rsd + '%.' },
      // 2. distance to people's drawings: children close in, Stable Diffusion does not
      { kind: 'bars', verdict: verdict(ap.A3_d_adult_changes),
        o: { values: [c.d_adult.mean[0], c.d_adult.mean[last], sd0, sdN], labels: ['age ' + ages[0], 'age ' + ages[last], 'SD ' + ck[0], 'SD ' + ck[n]],
          tones: ['orange', 'orange', 'green', 'green'], digits: 2,
          value: excludesZero(t.ci95) ? (t.mean > 0 ? 'Farther' : 'Closer') : 'No closer', unit: '',
          label: 'Stable Diffusion to people’s drawings, ' + ck[0] + ' → ' + ck[n] + ' (distance; children close in)',
          alt: 'Distance to the average adult drawing: children ' + f2(c.d_adult.mean[0]) + ' at age ' + ages[0] + ' and ' + f2(c.d_adult.mean[last]) +
            ' at ' + ages[last] + '; Stable Diffusion ' + f2(sd0) + ' at ' + ck[0] + ' and ' + f2(sdN) + ' at ' + ck[n] + '.' },
        q: (t.ci95 ? 'Change ' + signed(t.mean, f2) + ' ' + ci(t.ci95, f2) + ' over training; ' : '') + 'we predicted a change. Adults: ' + f2(ad.d_adult) + '.' }
    ] });
    var q = document.getElementById('hero-qual');
    if (q) {
      q.textContent = 'Means over ' + ch.things.length + ' things (Stable Diffusion: ' + ai.things.length + '). The conditions differ (a fingertip at a museum kiosk, ' +
        'a 20-second online game, generated pictures), so the AI’s distance to people’s drawings is largely drawing style.';
    }
  }
})();
