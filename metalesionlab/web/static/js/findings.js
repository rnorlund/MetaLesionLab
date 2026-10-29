/* Findings: expandable picture cards below a first screen. A row of cards (picture 4:3 on paper, a title of six words or
   fewer, one muted line of ten words or fewer, an "Open" cue). One card opens at a time, into a full-width panel under
   the row: a picture or strip on the left; on the right an h3, two plain sentences, an optional big number with its
   label and verdict; then any HTML (charts, sliders, figures); then a nested "More detail" disclosure with Aristotle's
   badge for method and caveats.

   USAGE (HTML first, so with no JavaScript every panel simply shows, expanded, under its own h3)
   1. Link /static/css/findings.css and /static/js/findings.js. Write:
        <section class="fd" data-findings aria-label="Findings">
          <article class="fd-item" id="finding-words" data-title="Words part or painting part?"
                   data-line="Each part forgets in its own way." data-img="/static/img/a.webp" data-alt="">
            <div class="fd-main">
              <div class="fd-media"> <img …> or a strip of images </div>
              <div class="fd-text">
                <h3>Words part or painting part?</h3>
                <p>Sentence one.</p> <p>Sentence two.</p>
                <div class="fd-number"><p class="fd-num-v">29 pts</p><p class="fd-num-l">what it measures</p>
                  <p class="fd-verdict yes">As predicted</p></div>          <!-- optional; tone: yes | no | part -->
              </div>
            </div>
            <div class="fd-extra"> any HTML: existing charts, sliders, figures (keep their ids) </div>
            <details class="how-we-know fd-more"><summary>More detail</summary> method and caveats </details>
          </article>
          …
        </section>
      The card's title and line come from data-title / data-line (the picture from data-img, data-alt for its alt text,
      empty by default since the title says it). The panel's id is "finding-<id>": the URL hash #finding-<id> opens it,
      and so does a hash that points at anything inside a panel (a link to a chart's heading opens its card).
   2. Or from data:  Findings.render(hostElement, [{id, title, line, img, alt, media:'<html>', h3, text:['one','two'],
        number:{value,label,verdict:{tone,text}}, extra:'<html>', more:'<html>'}])  (it builds the same markup, then mounts).
      Findings.mount(hostElement) enhances markup already in the page and returns {open(id), close(), current()}.
      Findings.itemHtml(item) is the pure markup of one panel (tests read it).
   3. "More detail" always gets the Aristotle badge in its summary (portraits.ARISTOTLE_BADGE's markup); write only the words.

   BEHAVIOUR
   - Cards are real <button>s with aria-expanded and aria-controls (the panel); each panel is a region labelled by its card.
     Pressing the open card again closes it. Only one panel is open; the open card gets an orange underline.
   - The panel opens with a smooth height change (none with prefers-reduced-motion). Closed panels are hidden and inert,
     but laid out at full width, so charts inside them draw at the right size.
   - Colours are the site's tokens; pictures sit on paper (--paper). */
(function () {
  'use strict';
  var made = 0;
  var BADGE = '<span class="pt-badge pt-aristotle"><img class="pt-badge-face" src="/static/img/portraits/aristotle-neutral.webp" ' +
    'width="256" height="256" alt="" loading="lazy"><span class="pt-badge-text">Aristotle checks the evidence</span></span>';

  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

  // The markup of one panel from data (pure).
  function itemHtml(it) {
    var n = it.number;
    return '<article class="fd-item" id="finding-' + esc(it.id) + '" data-title="' + esc(it.title) + '" data-line="' + esc(it.line) +
      '" data-img="' + esc(it.img) + '" data-alt="' + esc(it.alt || '') + '"><div class="fd-main">' +
      (it.media ? '<div class="fd-media">' + it.media + '</div>' : '') +
      '<div class="fd-text"><h3>' + esc(it.h3 || it.title) + '</h3>' + (it.text || []).map(function (t) { return '<p>' + esc(t) + '</p>'; }).join('') +
      (n ? '<div class="fd-number"><p class="fd-num-v">' + esc(n.value) + '</p><p class="fd-num-l">' + esc(n.label) + '</p>' +
        (n.verdict ? '<p class="fd-verdict ' + esc(n.verdict.tone || '') + '">' + esc(n.verdict.text) + '</p>' : '') + '</div>' : '') +
      '</div></div>' + (it.extra ? '<div class="fd-extra">' + it.extra + '</div>' : '') +
      (it.more ? '<details class="how-we-know fd-more"><summary>More detail</summary>' + it.more + '</details>' : '') + '</article>';
  }

  function mount(host) {
    if (host.classList.contains('fd-js')) return host.__fd;
    var items = [].slice.call(host.querySelectorAll('.fd-item'));
    if (!items.length) return null;
    var uid = 'fd' + (++made), cur = null, cards = {};
    var row = document.createElement('div');
    row.className = 'fd-row';
    host.classList.add('fd-js');
    host.insertBefore(row, items[0]);

    items.forEach(function (it, i) {
      var pid = it.id || (uid + '-' + i), key = pid.replace(/^finding-/, ''), cid = uid + '-card-' + i;
      it.id = pid;
      var inner = document.createElement('div');
      inner.className = 'fd-inner';
      while (it.firstChild) inner.appendChild(it.firstChild);
      it.appendChild(inner);
      it.setAttribute('role', 'region');
      it.setAttribute('aria-labelledby', cid);
      it.setAttribute('aria-hidden', 'true');
      if ('inert' in it) it.inert = true;
      var sum = inner.querySelector('details.how-we-know > summary');
      if (sum && !sum.querySelector('.pt-badge')) sum.innerHTML = '<span class="fd-more-t">' + sum.innerHTML + '</span> ' + BADGE;
      var b = document.createElement('button');
      b.type = 'button'; b.id = cid; b.className = 'fd-card';
      b.setAttribute('aria-expanded', 'false'); b.setAttribute('aria-controls', pid);
      b.innerHTML = '<span class="fd-img">' + (it.getAttribute('data-img') ? '<img src="' + esc(it.getAttribute('data-img')) + '" alt="' +
        esc(it.getAttribute('data-alt')) + '" width="256" height="256" loading="lazy" decoding="async">' : '') + '</span>' +
        '<span class="fd-t">' + esc(it.getAttribute('data-title')) + '</span><span class="fd-l">' + esc(it.getAttribute('data-line')) +
        '</span><span class="fd-open" aria-hidden="true"><span class="fd-open-t">Open</span><span class="fd-open-x">Close</span></span>';
      b.addEventListener('click', function () { if (cur === key) close(); else open(key, true); });
      row.appendChild(b);
      cards[key] = { btn: b, panel: it };
    });

    function close(keepHash) {
      if (cur == null) return;
      var c = cards[cur];
      c.btn.setAttribute('aria-expanded', 'false'); c.panel.classList.remove('is-open');
      c.panel.setAttribute('aria-hidden', 'true'); if ('inert' in c.panel) c.panel.inert = true;
      cur = null;
      if (!keepHash && /^#finding-/.test(location.hash) && history.replaceState) history.replaceState(null, '', location.pathname + location.search);
    }
    function open(key, fromClick, scrollTo) {
      var c = cards[key];
      if (!c) return false;
      if (cur != null && cur !== key) close(true);
      cur = key;
      c.btn.setAttribute('aria-expanded', 'true'); c.panel.classList.add('is-open');
      c.panel.setAttribute('aria-hidden', 'false'); if ('inert' in c.panel) c.panel.inert = false;
      if (fromClick && history.replaceState) history.replaceState(null, '', '#finding-' + key);
      if (scrollTo) {
        var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        row.scrollIntoView({ block: 'start', behavior: reduce ? 'auto' : 'smooth' });
      }
      return true;
    }
    // a hash that is a panel, or something inside one, opens its card
    function fromHash() {
      var h = decodeURIComponent((location.hash || '').slice(1));
      if (!h) return;
      var t = document.getElementById(h);
      if (!t) return;
      var keys = Object.keys(cards);
      for (var i = 0; i < keys.length; i++) {
        if (cards[keys[i]].panel === t || cards[keys[i]].panel.contains(t)) {
          open(keys[i], false, false);
          var go = function () { (cards[keys[i]].panel === t ? row : t).scrollIntoView({ block: 'start' }); };
          setTimeout(go, 60);
          return;
        }
      }
    }
    window.addEventListener('hashchange', fromHash);
    var api = { open: function (id) { return open(String(id).replace(/^finding-/, ''), true); }, close: function () { close(); },
                current: function () { return cur; } };
    host.__fd = api;
    fromHash();
    return api;
  }

  function render(host, list) {
    host.classList.add('fd');
    host.setAttribute('data-findings', '');
    host.innerHTML = list.map(itemHtml).join('');
    return mount(host);
  }

  function auto() { [].forEach.call(document.querySelectorAll('[data-findings]'), mount); }
  window.Findings = { mount: mount, render: render, itemHtml: itemHtml, auto: auto };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', auto); else auto();
})();
