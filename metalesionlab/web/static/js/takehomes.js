/* Take-homes: the stack toggle for the chairs (message 1), and the play buttons of message 3 (one voice at a time). */
(function () {
  'use strict';
  function $(id) { return document.getElementById(id); }

  var fig = $('chairs'), btn = $('stack-btn');
  if (fig && btn) btn.addEventListener('click', function () {
    var on = !fig.classList.contains('stacked');
    fig.classList.toggle('stacked', on);
    btn.setAttribute('aria-pressed', String(on));
  });

  var audioEl = null, current = null;
  function stop() {
    if (audioEl) { audioEl.pause(); audioEl = null; }
    if (current) current.setAttribute('aria-pressed', 'false');
    current = null;
  }
  document.querySelectorAll('.th-play').forEach(function (b) {
    b.addEventListener('click', function () {
      var was = current;
      stop();
      if (was === b) return;
      var a = new Audio(b.getAttribute('data-src'));
      audioEl = a;
      current = b;
      b.setAttribute('aria-pressed', 'true');
      a.addEventListener('ended', function () { if (current === b) stop(); });
      a.addEventListener('error', function () { if (current === b) stop(); });
      var p = a.play();
      if (p && p.catch) p.catch(function () { if (current === b) stop(); });
    });
  });
})();
