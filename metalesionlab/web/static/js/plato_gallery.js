/* The gallery (/plato/gallery): every curated picture from /api/plato/gallery in a fluid grid, filtered by
   category or shuffled, and a large view (a <dialog>) with the full picture or the sequence playing frame by
   frame, its caption, a link to the experiment and a Share on X link. Deep links: /plato/gallery#<id>.
   Keys in the large view: left and right arrows step through the pictures shown, Esc closes. Card pictures and
   the order helpers come from gallery-strip.js (window.TOTGallery). With prefers-reduced-motion nothing plays
   by itself. */
(function () {
  'use strict';
  var G = window.TOTGallery, T = window.TOT || {};
  var h = G.h;
  var ALL = 'all';
  var D = null, items = [], filter = ALL, shown = [], cur = -1, opener = null;
  var timer = null, playing = !G.still, k = 0, hold = 0;

  var grid = document.getElementById('grid'), chips = document.getElementById('chips'), count = document.getElementById('count');
  var view = document.getElementById('view'), stage = document.getElementById('stage');
  var player = document.getElementById('player'), playBtn = document.getElementById('play'), framesEl = document.getElementById('frames');
  var $ = function (id) { return document.getElementById(id); };

  function origin() {
    var o = document.body.getAttribute('data-origin') || '';
    return /^https?:\/\//.test(o) ? o.replace(/\/$/, '') : window.location.origin;
  }
  function itemUrl(it) { return origin() + '/plato/gallery#' + encodeURIComponent(it.id); }

  // ---------- chips, grid ----------
  function renderChips() {
    chips.textContent = '';
    var cats = [ALL].concat(D.categories);
    cats.forEach(function (c) {
      var n = c === ALL ? items.length : items.filter(function (i) { return i.category === c; }).length;
      chips.appendChild(h('button', { type: 'button', class: 'gx-chip', 'aria-pressed': String(c === filter),
        onclick: function () { filter = c; renderChips(); renderGrid(); } },
        [c === ALL ? 'All' : c, h('span', { class: 'gx-chip-n', text: String(n) })]));
    });
  }

  function renderGrid() {
    shown = items.filter(function (i) { return filter === ALL || i.category === filter; });
    grid.textContent = '';
    shown.forEach(function (it) {
      var seq = it.sequence ? it.sequence.frames.length : 0;
      var a = h('a', { class: 'gx-card-link', href: '#' + it.id, 'data-id': it.id,
        onclick: function (e) { e.preventDefault(); open(it.id, a); } }, it.title);
      grid.appendChild(h('li', { class: 'gx-card' + (it.category === 'Watch it degrade' ? ' is-degrade' : ''), id: 'card-' + it.id }, [
        G.picture(it),
        h('div', { class: 'gx-card-body' }, [
          h('p', { class: 'gx-card-cat' }, [it.category, seq ? h('span', { class: 'gx-card-seq', text: ' · ' + seq + ' frames' }) : null]),
          h('h2', { class: 'gx-card-title' }, a),
          h('p', { class: 'gx-card-cap', text: it.caption })
        ])
      ]));
    });
    count.textContent = shown.length === items.length ? items.length + ' pictures'
      : shown.length + ' of ' + items.length + ' pictures: ' + filter;
  }

  // ---------- the large view ----------
  function stop() { clearInterval(timer); timer = null; }
  function setPlaying(on) {
    playing = on;
    playBtn.setAttribute('aria-pressed', String(on));
    playBtn.querySelector('span').textContent = on ? 'Pause' : 'Play';
    stop();
    var it = shown[cur];
    if (on && it && it.sequence) {
      timer = setInterval(function () {
        if (hold > 0) { hold--; return; }
        var n = it.sequence.frames.length;
        frame((k + 1) % n);
        hold = k === n - 1 ? 3 : k === 0 ? 1 : 0;
      }, 900);
    }
  }

  function pic(src, alt) { return h('img', { src: src, alt: alt || '', decoding: 'async' }); }

  function frame(n) {
    var it = shown[cur], seq = it.sequence, f = seq.frames[n];
    k = n;
    stage.textContent = '';
    var total = seq.frames.length;
    var alt = it.title + ', ' + f.label + ' (' + (n + 1) + ' of ' + total + ')';
    if (f.pair) {
      var labels = seq.pair_labels || ['', ''];
      stage.appendChild(h('div', { class: 'gx-pair' }, [
        h('figure', null, [h('figcaption', { text: labels[0] }), pic(f.src, alt + ', ' + labels[0])]),
        h('figure', null, [h('figcaption', { text: labels[1] }), pic(f.pair, alt + ', ' + labels[1])])
      ]));
    } else {
      stage.appendChild(h('div', { class: 'gx-single' }, pic(f.src, alt)));
    }
    stage.appendChild(h('figcaption', { class: 'gx-frame-label' }, [h('b', { text: f.label }),
      h('span', { text: '  ·  ' + (n + 1) + ' of ' + total })]));
    [].forEach.call(framesEl.children, function (li, i) {
      var b = li.firstChild;
      if (i === n) b.setAttribute('aria-current', 'step'); else b.removeAttribute('aria-current');
    });
  }

  function show(i) {
    if (!shown.length) return;
    cur = (i + shown.length) % shown.length;
    var it = shown[cur];
    stop();
    $('view-cat').textContent = it.category;
    $('view-title').textContent = it.title;
    $('view-cap').textContent = it.caption + (it.more ? ' ' + it.more : '');  // the card shows one sentence; the large view, the detail too
    $('view-credit').textContent = it.credit ? 'Credits: ' + it.credit : '';
    $('view-link').href = it.link;
    $('view-share').href = 'https://x.com/intent/post?text=' + encodeURIComponent(it.title + ' · ' + (T.BRAND || 'Plato’s Chair')) +
      '&url=' + encodeURIComponent(itemUrl(it));
    $('view-pos').textContent = (cur + 1) + ' of ' + shown.length + (filter === ALL ? '' : ' in ' + filter);
    framesEl.textContent = '';
    if (it.sequence) {
      player.hidden = false;
      it.sequence.frames.forEach(function (f, n) {  // warm the cache so playing doesn't stutter
        new Image().src = f.src;
        if (f.pair) new Image().src = f.pair;
        framesEl.appendChild(h('li', null, h('button', { type: 'button', class: 'gx-frame-btn' + (f.pair ? ' is-pair' : ''), 'aria-label': 'Frame ' + (n + 1) + ': ' + f.label,
          onclick: function () { setPlaying(false); frame(n); } }, G.cell(it, n, false))));
      });
      hold = 1;
      frame(0);
      setPlaying(playing);
    } else {
      player.hidden = true;
      stage.textContent = '';
      stage.appendChild(h('div', { class: 'gx-single gx-still' }, pic(it.image, it.alt)));
    }
    stage.setAttribute('aria-describedby', 'view-cap');
    history.replaceState(null, '', '#' + it.id);
  }

  function open(id, from) {
    var i = shown.findIndex(function (x) { return x.id === id; });
    if (i < 0) {  // not in the current filter: show everything
      filter = ALL; renderChips(); renderGrid();
      i = shown.findIndex(function (x) { return x.id === id; });
    }
    if (i < 0) return;
    opener = from || document.querySelector('[data-id="' + id + '"]');
    show(i);
    if (!view.open) {
      if (typeof view.showModal === 'function') view.showModal(); else view.setAttribute('open', '');
      document.documentElement.classList.add('gx-locked');
    }
    $('close').focus();
  }

  function close() {
    stop();
    if (view.open) view.close();
  }
  view.addEventListener('close', function () {
    stop();
    document.documentElement.classList.remove('gx-locked');
    history.replaceState(null, '', window.location.pathname + window.location.search);
    var card = shown[cur] && document.querySelector('[data-id="' + shown[cur].id + '"]');
    (card || opener || document.getElementById('main')).focus();
  });
  view.addEventListener('click', function (e) { if (e.target === view) close(); });  // the backdrop
  view.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowRight') { e.preventDefault(); show(cur + 1); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); show(cur - 1); }
  });
  $('close').addEventListener('click', close);
  $('prev').addEventListener('click', function () { show(cur - 1); });
  $('next').addEventListener('click', function () { show(cur + 1); });
  playBtn.addEventListener('click', function () { setPlaying(!playing); });

  function fromHash() {
    var id = decodeURIComponent((window.location.hash || '').slice(1));
    if (id && items.some(function (i) { return i.id === id; })) open(id);
    else if (!id && view.open) close();
  }
  window.addEventListener('hashchange', fromHash);

  $('shuffle').addEventListener('click', function () {
    items = G.order(items, 1);
    renderGrid();
  });

  G.load().then(function (d) {
    D = d;
    items = d.items.slice();  // curated order: the degradation sequences first
    var credits = $('credits');
    (d.credits || []).forEach(function (c) { credits.appendChild(h('li', { text: c })); });
    renderChips();
    renderGrid();
    fromHash();
  }).catch(function (err) {
    grid.textContent = '';
    var el = $('load-error');
    el.hidden = false;
    el.textContent = (err && err.message) || 'The gallery could not be loaded.';
  });
})();
