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
  function num(x, fmt) { return (x < 0 ? '−' : '') + fmt(Math.abs(x)); }
  // a 95% interval in words: "probably between 3.7 and 5.3"
  function between(c, fmt) { return 'probably between ' + num(c[0], fmt) + ' and ' + num(c[1], fmt); }
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
    var ver = function (k) { return k.replace(/^v/, ''); };
    window.FirstLook.render(host, { stats: [
      // 1. children become recognizable; Stable Diffusion's first public version already is
      { kind: 'bars', verdict: verdict(cp.C1_recognizability_rises),
        o: { values: [r2, r10, rad, rsd], labels: ['age ' + ages[0], 'age ' + ages[last], 'adults', 'AI ' + ck[0]], tones: ['orange', 'orange', 'ink', 'green'],
          max: 100, value: r10 + '%', unit: 'at ' + ages[last] + ', from ' + r2 + '% at ' + ages[0],
          label: 'of children’s drawings that an AI could recognize as what was asked for',
          alt: 'Recognized: ' + r2 + '% of 2-year-olds’ drawings, ' + r10 + '% of 10-year-olds’, ' + rad + '% of adults’, and ' + rsd +
            '% of Stable Diffusion ' + ck[0] + '’s pictures.' },
        q: 'We predicted children’s drawings would get easier to recognize with age' +
          (slope ? ': ' + (slope.mean_slope < 0 ? 'down ' : 'up ') + one(Math.abs(slope.mean_slope)) + ' points a year (' + between(slope.ci95, one) + ')' : '') +
          '. For comparison: adults ' + rad + '%; Stable Diffusion’s first public version (AI ' + ck[0] + ') already ' + rsd + '%.' },
      // 2. distance to people's drawings: children close in, Stable Diffusion does not
      { kind: 'bars', verdict: verdict(ap.A3_d_adult_changes),
        o: { values: [c.d_adult.mean[0], c.d_adult.mean[last], sd0, sdN], labels: ['age ' + ages[0], 'age ' + ages[last], 'AI ' + ck[0], 'AI ' + ck[n]],
          tones: ['orange', 'orange', 'green', 'green'], digits: 2,
          value: excludesZero(t.ci95) ? (t.mean > 0 ? 'Farther' : 'Closer') : 'No closer', unit: '',
          label: (excludesZero(t.ci95) && t.mean > 0 ? 'from' : 'to') + ' the average adult drawing: Stable Diffusion’s pictures from version ' + ver(ck[0]) + ' to ' + ver(ck[n]) +
            '. Children’s drawings get closer with age.',
          alt: 'How far drawings are from the average adult drawing (0 = identical): children ' + f2(c.d_adult.mean[0]) + ' at age ' + ages[0] + ' and ' +
            f2(c.d_adult.mean[last]) + ' at ' + ages[last] + '; Stable Diffusion ' + f2(sd0) + ' at ' + ck[0] + ' and ' + f2(sdN) + ' at ' + ck[n] + '.' },
        q: 'We predicted more training would change how far its pictures are from people’s drawings' +
          (t.ci95 ? '. The change: ' + signed(t.mean, f2) + ' (' + between(t.ci95, f2) + ')' : '') +
          '. Distance is how different two pictures look to a Meta AI that compares pictures (DINOv2); 0 = identical. A typical adult drawing is ' +
          f2(ad.d_adult) + ' from the adults’ average.' }
    ] });
    var q = document.getElementById('hero-qual');
    if (q) {
      q.textContent = 'Averages over ' + ch.things.length + ' everyday things (' + ai.things.length + ' for Stable Diffusion). Children drew with a fingertip at a ' +
        'museum kiosk, adults in a 20-second online game, and the AI makes polished pictures. So most of the AI’s distance from people’s drawings is drawing style.';
    }
  }
})();
