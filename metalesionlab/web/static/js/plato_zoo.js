/* The damage zoo (/plato/zoo)

   Everything comes from /api/plato/zoo (the models, each part's 11 damage steps, a caption per part) and one strip of
   11 pictures per model, part and thing in /static/img/zoo/. No API calls.

   Pick a thing and where the damage is, then play or drag the slider: every AI's card shows step k of its own range
   (intact to where its pictures stop meaning anything), with its own share of neurons switched off under it. The zoo
   plays once by itself when it first comes into view (not with reduced motion). ?thing=god&part=drawing opens a
   given view, for links. Colours come from the site's tokens through classes (plato_zoo.css). */
(function () {
  'use strict';

  var T = window.TOT, h = T.h;
  var PART_LABEL = { language: 'Words damaged', drawing: 'Drawing damaged' };
  var PART_WHAT = { language: 'neurons that read the words', drawing: 'neurons that draw' };
  var STEP_MS = 520, HOLD_MS = 1600;
  var S = { data: null, thing: 'chair', part: 'language', step: 0, timer: null, cards: [] };
  var $ = function (id) { return document.getElementById(id); };

  function label(phrase) { var p = phrase.replace(/^(a|an) /, ''); return p.charAt(0).toUpperCase() + p.slice(1); }
  function pct(dose) { return dose === 0 ? 'intact' : Math.round(dose * 100) + '% off'; }
  function last() { return S.data.steps - 1; }

  function seg(id, items, current, pick) {
    var box = $(id);
    box.textContent = '';
    items.forEach(function (it) {
      box.appendChild(h('button', { type: 'button', 'aria-pressed': String(it.key === current), text: it.text,
        onclick: function () { pick(it.key); } }));
    });
  }

  function remember() {
    try { history.replaceState(null, '', '?thing=' + S.thing + '&part=' + S.part); } catch (e) { /* file:// or old browser */ }
  }

  function controls() {
    seg('thing-seg', Object.keys(S.data.things).map(function (k) { return { key: k, text: label(S.data.things[k]) }; }),
      S.thing, function (k) { S.thing = k; build(); });
    seg('part-seg', S.data.parts.map(function (p) { return { key: p, text: PART_LABEL[p] || p }; }),
      S.part, function (p) { S.part = p; build(); });
  }

  function build() {
    stop();
    controls();
    remember();
    var grid = $('grid');
    grid.textContent = '';
    S.cards = S.data.models.map(function (m) {
      var img = h('img', { src: '/static/img/zoo/' + m.key + '-' + S.part + '-' + S.thing + '.webp', alt: '',
        width: S.data.frame * S.data.steps, height: S.data.frame, decoding: 'async' });
      img.style.width = (S.data.steps * 100) + '%';
      var dose = h('span', { class: 'zoo-dose' });
      var cap = m.captions && m.captions[S.part];
      var card = h('figure', { class: 'zoo-card' }, [
        h('div', { class: 'zoo-pic', role: 'img' }, [img]),
        h('figcaption', {}, [
          h('span', { class: 'zoo-name' }, [h('b', { text: m.name }), dose]),
          h('span', { class: 'zoo-maker', text: m.maker }),
          cap ? h('span', { class: 'zoo-capt', text: cap }) : null
        ])
      ]);
      grid.appendChild(card);
      return { m: m, img: img, dose: dose, pic: card.firstChild };
    });
    show(S.step);
  }

  function show(k) {
    S.step = k;
    var thing = S.data.things[S.thing];
    S.cards.forEach(function (c) {
      var d = c.m.doses[S.part][k];
      c.img.style.transform = 'translateX(' + (-100 * k / S.data.steps) + '%)';
      c.dose.textContent = pct(d);
      c.pic.setAttribute('aria-label', c.m.name + '’s drawing of ' + thing + (d === 0 ? ', undamaged' :
        ', with ' + Math.round(d * 100) + '% of its ' + PART_WHAT[S.part] + ' switched off'));
    });
    var range = $('step');
    range.value = String(k);
    var text = k === 0 ? 'intact' : 'step ' + k + ' of ' + last();
    range.setAttribute('aria-valuetext', text);
    $('step-out').textContent = text;
  }

  function stop() {
    if (S.timer) clearTimeout(S.timer);
    S.timer = null;
    $('play').setAttribute('aria-pressed', 'false');
    $('play').textContent = 'Play';
  }

  function play() {
    if (S.timer) { stop(); return; }
    $('play').setAttribute('aria-pressed', 'true');
    $('play').textContent = 'Pause';
    if (S.step >= last()) show(0);
    (function tick() {
      S.timer = setTimeout(function () {
        if (S.step < last()) { show(S.step + 1); tick(); return; }
        S.timer = setTimeout(function () { stop(); show(0); }, HOLD_MS);
      }, S.step === 0 ? STEP_MS * 1.5 : STEP_MS);
    })();
  }

  function playOnceInView() {
    var calm = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (calm || !('IntersectionObserver' in window)) return;
    var io = new IntersectionObserver(function (es) {
      if (es.some(function (e) { return e.isIntersecting; })) { io.disconnect(); if (!S.timer && S.step === 0) play(); }
    }, { threshold: 0.35 });
    io.observe($('grid'));
  }

  function table() {
    var t = $('models');
    t.appendChild(h('thead', {}, [h('tr', {}, ['AI', 'Made by', 'Reads the words with', 'Words damaged', 'Drawing damaged', 'License']
      .map(function (x) { return h('th', { scope: 'col', text: x }); }))]));
    t.appendChild(h('tbody', {}, S.data.models.map(function (m) {
      var top = function (p) { return '0 to ' + Math.round(m.doses[p][last()] * 100) + '% off'; };
      return h('tr', {}, [h('th', { scope: 'row', text: m.name }), h('td', { text: m.maker }), h('td', { text: m.reads_with }),
        h('td', { text: top('language') }), h('td', { text: top('drawing') }), h('td', { text: m.license })]);
    })));
  }

  function init() {
    var q = new URLSearchParams(location.search);
    T.api('/api/plato/zoo').then(function (data) {
      S.data = data;
      if (data.things[q.get('thing')]) S.thing = q.get('thing');
      if (data.parts.indexOf(q.get('part')) >= 0) S.part = q.get('part');
      $('prompt').textContent = '“' + data.prompt.replace('{phrase}', data.things[S.thing]) + '”';
      $('step').max = String(last());
      $('step').addEventListener('input', function () { stop(); show(+this.value); });
      $('play').addEventListener('click', play);
      build();
      table();
      playOnceInView();
    }).catch(function (err) {
      $('grid').textContent = '';
      var box = $('load-error');
      box.textContent = err.message;
      box.hidden = false;
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
