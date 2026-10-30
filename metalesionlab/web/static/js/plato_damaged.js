/* Damaged AI (/damaged): the hub's first screen. The rocking chair that damage to Stable Diffusion XL's language part
   turns into a car, step by step beside the same steps of damage to its drawing part, and three numbers drawn by
   FirstLook.damaged (plato_firstlook.js), the code that draws /plato/damage's first screen. Everything comes from
   /api/plato/damage and /api/plato/ideas (statistics and precomputed pictures); no API calls. The cards below are
   served with the page (damaged_routes.py). */
(function () {
  'use strict';
  var KIND = /rocking/, METHOD = 'noise', STEPS = 4;  // the slider's opening picture on /plato/damage: noise, up to level 3

  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'text') e.textContent = attrs[k]; else if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c != null) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return e;
  }
  function get(url) {
    return fetch(url).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
  }

  // Glimmer's one-word answer, spaced like the kind when it is the kind ("rockingchair" is the rocking chair).
  function say(name, label) {
    if (!name) return '';
    return name.replace(/\s+/g, '') === label.replace(/\s+/g, '') ? label : name;
  }

  // Two rows of the same steps: language part damaged, drawing part damaged; the last language step is the striking one.
  function renderFilm(d) {
    var host = $('film-rows'), sl = d && d.slider;
    if (!host || !sl) return;
    var kind = sl.kinds.filter(function (k) { return KIND.test(k.key); })[0] || sl.kinds[0];
    var m = sl.methods[METHOD], pics = sl.pictures[kind.key];
    host.innerHTML = '';
    // the glossary's plain names (docs/style_plain_language.md): the part that reads the words, the part that paints
    [[m.lang, 'lang', 'Words part damaged', 'the part that reads the words'],
     [m.draw, 'draw', 'Drawing part damaged', 'the part that paints the picture']]
      .forEach(function (row) {
        var frames = (pics[row[0]] || []).slice(0, STEPS);
        var list = el('ol', { class: 'dm-frames' });
        frames.forEach(function (p, i) {
          var name = say(p.name, kind.label), step = i ? 'step ' + i + ' of ' + (pics[row[0]] || []).slice(1).length : 'undamaged';
          list.appendChild(el('li', { class: 'dm-frame' + (i === frames.length - 1 ? ' last' : '') }, [
            el('img', { src: p.img, width: 256, height: 256, loading: i ? 'lazy' : null, decoding: 'async',
              alt: 'Stable Diffusion XL asked for a ' + kind.label + (i ? ', ' + row[2].toLowerCase() + ', ' + step : ', undamaged') +
                (name ? '; Muse Glimmer calls it ' + name : '') }),
            el('span', { class: 'dm-said' }, name ? '“' + name + '”' : '–'),
            el('span', { class: 'dm-step', text: step })]));
        });
        host.appendChild(el('div', { class: 'dm-row ' + row[1], role: 'group', 'aria-label': row[2] }, [
          el('p', { class: 'dm-row-h' }, [el('b', { text: row[2] }), el('span', { text: row[3] })]), list]));
      });
  }

  function renderLead(d, ideas) {
    var host = $('hero-stats'), q = $('hero-qual');
    if (!host || !window.FirstLook) return;
    var lead = window.FirstLook.damaged(d, ideas);
    if (lead.stats.length) window.FirstLook.render(host, lead);
    if (!q || !lead.split) return;
    // how the planned predictions came out, in plain words, from the same data: the split, then the plain chair
    var sp = lead.split, t = function (x) { q.appendChild(document.createTextNode(x)); };
    q.innerHTML = '';
    q.appendChild(el('b', { text: sp.head + ' ' }));
    t('We wrote down two predictions before we made any pictures. Damage to the words part would make the AI forget what it draws, ' +
      (sp.what ? 'and it did. ' : 'but it did not. ') +
      'Damage to the drawing part would cost more of its clean line style: ' + (sp.noise ? 'true when we added noise' : 'not true when we added noise') +
      (sp.offReversed ? ', but the opposite when we switched neurons off' : sp.off ? ' and when we switched neurons off' : '') + ' (');
    q.appendChild(el('a', { href: '/plato/damage#diss-h', text: 'details' }));
    t(').');
    if (lead.proto) {
      var v = lead.proto.verdict;
      t(' We also predicted that damaged chairs would drift back toward a plain, ordinary chair, as drawings do in semantic dementia, ' +
        'a brain disease that wears away what words and things mean. ');
      q.appendChild(el('b', { text: v.text + '.' }));
      t((v.tone === 'yes' ? '' : lead.proto.farther ? ' The chairs wandered farther from the plain chair instead' : ' The chairs came no closer to it') + ' (');
      q.appendChild(el('a', { href: '/plato/damage#proto-h', text: 'details' }));
      t(').');
    }
    t(' Other AIs, not people, judged the pictures. The damage is to an AI, so this is a comparison, not a claim about people.');
  }

  Promise.all([get('/api/plato/damage'), get('/api/plato/ideas')]).then(function (r) {
    var d = r[0], ideas = r[1];
    if (!d && !ideas) {
      var n = $('load-error');
      if (n) { n.hidden = false; n.textContent = 'Could not load the results of the damage experiments.'; }
      return;
    }
    renderFilm(d);
    renderLead(d, ideas);
  });
})();
