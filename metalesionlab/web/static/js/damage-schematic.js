/* Damage schematic: the figure is written into the page as static HTML (works without JS); see damage-schematic.css.
     <figure class="ds" data-damage-schematic> ... </figure>
   This script only adds a small convenience: pointing at one of the three small versions marks the matching part in
   the big flow above it (class ds-hot on .ds-p1 / .ds-p2). It needs nothing else. */
(function () {
  'use strict';
  [].forEach.call(document.querySelectorAll('[data-damage-schematic]'), function (fig) {
    var flow = fig.querySelector('.ds-flow');
    if (!flow) return;
    [].forEach.call(fig.querySelectorAll('.ds-ver'), function (v) {
      var bad = v.querySelector('.ds-part.is-cracked'), which = bad ? (bad.classList.contains('ds-p1') ? '.ds-p1' : '.ds-p2') : null;
      function on(e) { if (which) { var t = flow.querySelector(which); if (t) t.classList.toggle('ds-hot', e); } }
      v.addEventListener('mouseenter', function () { on(true); });
      v.addEventListener('mouseleave', function () { on(false); });
    });
  });
})();
