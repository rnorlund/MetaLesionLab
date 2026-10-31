/* Next question: a button between two sections that asks the next section's question. Clicking it scrolls the page
   until that section, its answer, comes up to the top, the way "See where it lands" does on the landing page, so a
   page reads as question, answer, question, answer…

   Mark a section with data-ask="Is it just chairs?" (a short question, ending in "?"). The button goes just above it,
   after whatever came before. Scrolling is smooth (instant with reduced motion), and focus moves to the section's
   heading, so keyboard and screen-reader users land on the answer too. While a section is hidden (the landing page's
   reveal before a drawing, a section a page shows later), its button is hidden with it (next-question.css).
   Added to every Plato page by site.py (add_next); a page with no data-ask is left as it is. */
(function () {
  'use strict';
  var reduce = false;
  try { reduce = matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { /* old browser: animate */ }

  function go(target) {
    target.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
    var h = target.querySelector('h1, h2, h3') || target;
    if (!h.hasAttribute('tabindex')) h.setAttribute('tabindex', '-1');
    try { h.focus({ preventScroll: true }); } catch (e) { h.focus(); }
  }

  function add(sec) {
    var q = (sec.getAttribute('data-ask') || '').trim(), prev = sec.previousElementSibling;
    if (!q || (prev && prev.classList.contains('nq'))) return;
    var box = document.createElement('p'), btn = document.createElement('button'), text = document.createElement('span');
    box.className = 'nq';
    btn.type = 'button';
    btn.className = 'nq-btn';
    text.className = 'nq-q';
    text.textContent = q;
    btn.appendChild(text);
    btn.insertAdjacentHTML('beforeend', '<span class="nq-arrow" aria-hidden="true">↓</span>');
    btn.addEventListener('click', function () { go(sec); });
    box.appendChild(btn);
    sec.parentNode.insertBefore(box, sec);
  }

  function init() { [].forEach.call(document.querySelectorAll('[data-ask]'), add); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
