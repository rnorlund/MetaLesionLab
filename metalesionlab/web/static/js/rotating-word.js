/* Rotating word: <span class="rw" data-rotating-word data-words="a chair|a rocking chair|God"><span class="rw-i">a thing</span></span>
   Without JS (or with reduced motion) the span keeps its written text. With JS every word is stacked in one inline-grid
   cell, so the slot is as wide as the longest word and nothing reflows; one shows at a time, every data-interval ms
   (default 1500), with a ~200 ms fade. Pauses on hover. aria-hidden: put the full text in an aria-label on the
   parent (the h1). CSS: rotating-word.css. */
(function () {
  'use strict';
  var RM = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  [].forEach.call(document.querySelectorAll('[data-rotating-word]'), function (el) {
    var words = (el.getAttribute('data-words') || '').split('|').map(function (w) { return w.trim(); }).filter(Boolean);
    if (RM || words.length < 2) return;
    var gap = +el.getAttribute('data-interval') || 1500, cur = 0, held = false;
    el.textContent = '';
    var items = words.map(function (w, i) {
      var s = document.createElement('span'); s.className = 'rw-i' + (i ? '' : ' is-on'); s.textContent = w; el.appendChild(s); return s;
    });
    el.setAttribute('aria-hidden', 'true');
    el.classList.add('rw-live');
    el.addEventListener('mouseenter', function () { held = true; });
    el.addEventListener('mouseleave', function () { held = false; });
    setInterval(function () {
      if (held || document.hidden) return;
      items[cur].classList.remove('is-on'); cur = (cur + 1) % items.length; items[cur].classList.add('is-on');
    }, gap);
  });
})();
