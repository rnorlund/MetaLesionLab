/* The header on one line at every width (Roger, Nov 2: the theme button kept dropping to a second line). Above the
   phone breakpoint (861 px), links that don't fit move into the More menu, from the right, keeping the starred
   Take-homes and the Ask Socrates accent until last; they come back as the window widens. Below it, the Menu button
   already holds everything. site.py adds this file to every Plato page; app.css keeps the row from wrapping. */
(function () {
  'use strict';
  var head = document.querySelector('header.site-head'), nav = head && head.querySelector('.topnav');
  var more = nav && nav.querySelector('.nav-more'), panel = more && more.querySelector('.nav-panel');
  if (!nav || !more || !panel) return;
  var slot = document.createElement('div');
  slot.className = 'navfit-moved';
  panel.insertBefore(slot, panel.firstChild);
  var home = [];  // each moved link and the node it sat before, so it goes back where it was
  [].forEach.call(nav.querySelectorAll(':scope > a'), function (a, i) { a.setAttribute('data-navfit', i); });
  var current = more.classList.contains('is-current');

  function over() { return nav.scrollWidth > nav.clientWidth + 1 || head.scrollWidth > head.clientWidth + 1; }
  function restore() {
    while (home.length) { var h = home.pop(); nav.insertBefore(h.link, h.before); }
    more.classList.toggle('is-current', current);
  }
  function candidates() {
    var links = [].slice.call(nav.querySelectorAll(':scope > a'));
    var plain = links.filter(function (a) { return !a.classList.contains('nav-accent') && !a.classList.contains('nav-star'); });
    // popped from the end: the plain links go first, from the right; the starred and accent links last
    return links.filter(function (a) { return plain.indexOf(a) < 0; }).concat(plain);
  }
  function fit() {
    restore();
    if (window.innerWidth <= 860) return;  // the phone menu takes over
    var queue = candidates();
    while (over() && queue.length) {
      var link = queue.pop();
      home.push({ link: link, before: link.nextSibling });
      slot.insertBefore(link, slot.firstChild);
      if (link.getAttribute('aria-current') === 'page') more.classList.add('is-current');
    }
    [].slice.call(slot.children).sort(function (a, b) {  // in More, in their header order
      return +a.getAttribute('data-navfit') - +b.getAttribute('data-navfit');
    }).forEach(function (a) { slot.appendChild(a); });
  }
  var raf = 0;
  function later() { cancelAnimationFrame(raf); raf = requestAnimationFrame(fit); }
  window.addEventListener('resize', later);
  window.addEventListener('load', later);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(later);
  fit();
})();
