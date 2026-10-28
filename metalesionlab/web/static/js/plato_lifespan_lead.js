/* The life of a chair (/plato/lifespan), first screen: the answer's headline numbers drawn as small graphics
   (statviz.js). Group-level statistics only, from the same /api/plato/lifespan response plato_lifespan.js loads:
   this file is linked just before it and watches TOT.api for that one path, so the page still fetches it once.
   No child's drawing is ever shown. */
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
  function excludesZero(c) { return c && (c[0] > 0 || c[1] < 0); }

  function stat(host, opts) {
    var li = document.createElement('li'), g = document.createElement('div');
    li.className = 'fs-stat';
    li.appendChild(g);
    host.appendChild(li);
    window.StatViz.render(g, opts);
  }

  function render(D) {
    var host = document.getElementById('hero-stats');
    if (!host || !window.StatViz || !D || !D.children || !D.ai || !D.ai.all) return;
    var ch = D.children, c = ch.curves, ages = ch.ages, last = ages.length - 1;
    var ad = D.adults.mean_over_children_things, ai = D.ai.all, ck = ai.checkpoints, n = ck.length - 1;
    host.innerHTML = '';

    // 1. children become recognizable; Stable Diffusion's first public stage already is
    var r2 = pct(c.recog.mean[0]), r10 = pct(c.recog.mean[last]), rad = pct(ad.recog), rsd = pct(ai.curves.recog.mean[0]);
    stat(host, { kind: 'bars', values: [r2, r10, rad, rsd],
      labels: ['age ' + ages[0], 'age ' + ages[last], 'adults', 'SD ' + ck[0]], tones: ['orange', 'orange', 'ink', 'green'], max: 100,
      value: r10 + '%', unit: 'at ' + ages[last] + ', from ' + r2 + '% at ' + ages[0],
      label: 'of children’s drawings recognizable as what was asked',
      alt: 'Recognizable: ' + r2 + '% of 2-year-olds’ drawings, ' + r10 + '% of 10-year-olds’, ' + rad + '% of adults’, and ' + rsd +
        '% of Stable Diffusion ' + ck[0] + '’s pictures.' });

    // 2. distance to people's chairs: children close in, Stable Diffusion does not
    var t = (ai.tests.d_adult || {}).last_minus_first || {}, sd0 = ai.curves.d_adult.mean[0], sdN = ai.curves.d_adult.mean[n];
    var word = excludesZero(t.ci95) ? (t.mean > 0 ? 'Farther' : 'Closer') : 'No closer';
    stat(host, { kind: 'bars', values: [c.d_adult.mean[0], c.d_adult.mean[last], sd0, sdN],
      labels: ['age ' + ages[0], 'age ' + ages[last], 'SD ' + ck[0], 'SD ' + ck[n]], tones: ['orange', 'orange', 'green', 'green'], digits: 2,
      value: word, unit: '',
      label: 'Stable Diffusion to people’s drawings, ' + ck[0] + ' → ' + ck[n] + ' (distance; children close in)',
      alt: 'Distance to the average adult drawing: children ' + f2(c.d_adult.mean[0]) + ' at age ' + ages[0] + ' and ' + f2(c.d_adult.mean[last]) +
        ' at ' + ages[last] + '; Stable Diffusion ' + f2(sd0) + ' at ' + ck[0] + ' and ' + f2(sdN) + ' at ' + ck[n] + '.' });

    var q = document.getElementById('hero-qual');
    if (q) {
      q.textContent = 'Means over ' + ch.things.length + ' things (Stable Diffusion: ' + ai.things.length + '). Children aren’t there at ' + ages[last] +
        ': ' + r10 + '% against adults’ ' + rad + '%. The conditions differ (a fingertip at a museum kiosk, a 20-second online game, generated pictures), ' +
        'so the AI’s distance to people’s drawings is largely drawing style.';
    }
  }
})();
