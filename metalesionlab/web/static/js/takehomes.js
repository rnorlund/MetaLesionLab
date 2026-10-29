/* Take-homes: the stack toggle for the chairs, and the God panel, covered until the visitor has drawn.
   The draw pad's flag (sessionStorage "tot-draw-seen", draw.js SEEN_KEY) means this tab has already shown
   Muse Image's drawings, so a seen visitor gets the panel uncovered; "Show me now" sets the same flag. */
(function () {
  'use strict';
  var SEEN_KEY = 'tot-draw-seen';
  function $(id) { return document.getElementById(id); }

  var fig = $('chairs'), btn = $('stack-btn');
  if (fig && btn) btn.addEventListener('click', function () {
    var on = !fig.classList.contains('stacked');
    fig.classList.toggle('stacked', on);
    btn.setAttribute('aria-pressed', String(on));
  });

  var god = $('god');
  function reveal() {
    $('god-cover').hidden = true;
    $('god-grid').hidden = false;
    god.setAttribute('data-state', 'open');
    god.querySelectorAll('.th-god-after').forEach(function (e) { e.hidden = false; });
  }
  var seen = false;
  try { seen = window.sessionStorage.getItem(SEEN_KEY) === '1'; } catch (e) { /* storage off */ }
  if (seen) reveal();
  $('god-show').addEventListener('click', function () {
    try { window.sessionStorage.setItem(SEEN_KEY, '1'); } catch (e) { /* storage off */ }
    reveal();
  });
})();
