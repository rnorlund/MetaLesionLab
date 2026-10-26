/* Test Studio: build a checked picture set, review each item, export. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var COST_PER_CANDIDATE = 0.0145;
  var state = { status: null, sets: [], current: null, data: null, poll: null, langs: [] };
  function $(id) { return document.getElementById(id); }

  function tokenFor(id) { try { return localStorage.getItem('tot-edit-' + id); } catch (e) { return null; } }
  function saveToken(id, tok) { try { localStorage.setItem('tot-edit-' + id, tok); } catch (e) { /* private mode */ } }
  function radio(name) { var el = document.querySelector('input[name="' + name + '"]:checked'); return el ? el.value : null; }
  function wordLines() {
    var seen = {};
    return $('words').value.split('\n').map(function (l) { return l.trim(); }).filter(function (l) {
      var w = l.split(':')[0].trim().toLowerCase();
      if (!w || seen[w]) return false;
      seen[w] = true;
      return true;
    });
  }

  // --- status, estimate and feature flags ------------------------------------------------
  function refreshStatus() {
    T.status.p = null;
    return T.status().then(function (st) {
      state.status = st;
      updateEstimate();
      return st;
    });
  }

  function updateEstimate() {
    var st = state.status, n = wordLines().length, c = +radio('cands');
    var btn = $('build-btn'), out = $('estimate');
    var max = st ? st.max_words : 24;
    var parts = [];
    if (n) parts.push(n + (n === 1 ? ' word' : ' words') + ' × ' + c + ' candidate' + (c > 1 ? 's' : '') +
      ' ≈ $' + (n * c * COST_PER_CANDIDATE).toFixed(2) + ' of Meta API calls, about a minute.');
    if (st && !st.features.builds) { parts = ['Building new sets is turned off on this demo; browse and export the sets below.']; btn.disabled = true; }
    else if (st && !st.features.meta_api) { parts = ['Live generation is off: this server has no Meta API key.']; btn.disabled = true; }
    else if (st) {
      var left = st.limits.build.remaining;
      parts.push(left + ' of ' + st.limits.build.per_day + ' builds left today on this demo.');
      btn.disabled = left <= 0 || n === 0 || n > max;
      if (n > max) parts.unshift('Up to ' + max + ' words per set.');
    }
    out.textContent = parts.join(' ');
  }

  function applyFeatures(st) {
    var langs = st ? st.languages : [{ code: 'en', name: 'English', verified: true }, { code: 'es', name: 'Spanish', verified: true }];
    state.langs = langs;
    T.fillLanguages($('lang'), langs, 'en');
    T.fillLanguages($('scene-lang'), langs, 'en');
    if (st) $('max-words').textContent = st.max_words;
    var sceneOk = st && st.features.scorer && st.features.builds && st.features.meta_api;
    $('scene-btn').disabled = !sceneOk;
    if (st && !st.features.scorer) {
      $('task').querySelector('option[value="scene"]').textContent = 'Picture description (scene) · coming soon';
      $('scene-note').textContent = 'Scene drawing turns on when the picture-description scorer is installed on this server.';
    } else if (st) {
      $('scene-note').textContent = st.limits.scene.remaining + ' of ' + st.limits.scene.per_day + ' scenes left today. About $0.02 per scene.';
    }
    updateEstimate();
  }

  // --- set list -------------------------------------------------------------------------
  var STATUS_LABEL = { queued: 'Queued', running: 'Building', done: null, error: 'Failed', incomplete: 'No results yet' };

  function loadSets() {
    return T.api('/api/sets').then(function (sets) {
      state.sets = sets;
      renderSetList();
      return sets;
    }).catch(function (e) { T.toast(e.message, 'error'); return []; });
  }

  function renderSetList() {
    var ul = $('set-list');
    ul.innerHTML = '';
    if (!state.sets.length) {
      ul.appendChild(h('li', { class: 'muted small', text: 'No sets yet.' }));
      return;
    }
    state.sets.forEach(function (s) {
      var sub = [s.lang, s.n_items + ' words'];
      if (s.status === 'done') sub.push(s.kept + ' kept' + (s.review ? ' · ' + s.review + ' review' : ''));
      var right = STATUS_LABEL[s.status] ? h('span', { class: 'pill ' + (s.status === 'error' ? 'pill-excluded' : 'pill-review'), text: STATUS_LABEL[s.status] }) : null;
      var btn = h('button', { type: 'button', 'aria-current': s.id === state.current ? 'true' : 'false', onclick: function () { openSet(s.id); } }, [
        h('span', null, [h('span', { class: 'name', text: s.name }), h('br'), h('span', { class: 'sub', text: sub.join(' · ') })]),
        right
      ]);
      ul.appendChild(h('li', null, btn));
    });
  }

  // --- one set ----------------------------------------------------------------------------
  function openSet(id) {
    if (state.poll) { clearTimeout(state.poll); state.poll = null; }
    state.current = id;
    renderSetList();
    history.replaceState(null, '', '/studio?set=' + encodeURIComponent(id));
    return fetchSet(id);
  }

  function fetchSet(id) {
    return T.api('/api/sets/' + encodeURIComponent(id)).then(function (data) {
      if (state.current !== id) return;
      var wasBuilding = state.data && state.data.id === id && (state.data.status === 'running' || state.data.status === 'queued');
      state.data = data;
      renderSet();
      if (data.status === 'running' || data.status === 'queued') {
        state.poll = setTimeout(function () { fetchSet(id); }, 2500);
      } else if (wasBuilding) {
        loadSets();
        refreshStatus();
        T.toast(data.status === 'done' ? 'Set "' + data.name + '" is ready.' : 'The build stopped.', data.status === 'done' ? null : 'error');
      }
    }).catch(function (e) { T.toast(e.message, 'error'); });
  }

  function reviewReason(it) {
    var c = it.candidates || [];
    if (!c.some(function (x) { return x.sam_ok; })) return 'no single clear object';
    var miss = c.filter(function (x) { return x.sam_ok && !x.spark_ok; })[0];
    if (miss) return 'Spark said "' + miss.spark_name + '"';
    return 'check the pictures';
  }

  function keptCandidate(it) {
    return (it.candidates || []).filter(function (c) { return c.file === it.image; })[0] || null;
  }

  function renderSet() {
    var d = state.data, m = d.manifest;
    $('set-h').textContent = d.name;
    var nCand = m ? m.items.reduce(function (a, it) { return a + (it.candidates || []).length; }, 0) : null;
    $('set-meta').textContent = m
      ? T.langName(state.langs, m.lang) + ' · ' + m.items.length + ' words · ' + nCand + ' candidates · ' + d.kept + ' kept' + (d.review ? ' · ' + d.review + ' need review' : '') + (d.excluded ? ' · ' + d.excluded + ' excluded' : '')
      : (d.lang ? T.langName(state.langs, d.lang) + ' · ' : '') + d.n_items + ' words';

    var statusBox = $('set-status');
    statusBox.innerHTML = '';
    var body = $('set-body');
    body.innerHTML = '';
    $('export-panel').hidden = !m;

    if (d.status === 'running' || d.status === 'queued' || d.status === 'incomplete' || d.status === 'error') {
      var drawn = d.progress.drawn, expected = d.progress.expected;
      var box = h('div', { class: 'build-status' });
      if (d.status === 'error') {
        box.appendChild(h('div', { class: 'note note-error' }, h('p', { text: d.error || 'The build stopped.' })));
      } else if (d.status === 'incomplete') {
        box.appendChild(h('div', { class: 'note note-warn' }, h('p', { text: 'This set has no results yet. It may still be building in another process, or its build was interrupted. ' + drawn + ' pictures drawn so far.' })));
      } else {
        var pct = expected ? Math.min(100, Math.round(100 * drawn / expected)) : 5;
        var label = d.status === 'queued' ? 'Waiting for a free slot…' : drawn === 0 ? 'Muse Spark is planning each picture…' : 'Drawing and checking pictures';
        box.appendChild(h('div', { class: 'line' }, [h('span', null, [h('span', { class: 'spinner', 'aria-hidden': 'true' }), ' ', label]),
          h('span', { class: 'mono muted', text: drawn + (expected ? ' of ' + expected : '') + ' pictures' })]));
        var bar = h('div', { class: 'progress', role: 'progressbar', 'aria-valuemin': '0', 'aria-valuemax': '100', 'aria-valuenow': String(pct), 'aria-label': 'Build progress' }, h('div'));
        bar.firstChild.style.width = pct + '%';
        box.appendChild(bar);
      }
      statusBox.appendChild(box);
      var files = (d.drawn_files || []).slice(-36);
      if (files.length) {
        var grid = h('div', { class: 'drawn' });
        files.forEach(function (f) {
          var name = f.split('/').pop().replace(/\.png$/, '');
          grid.appendChild(h('figure', null, [h('img', { src: T.mediaUrl(d.id, f, 160), alt: 'Candidate picture ' + name, loading: 'lazy' }), h('figcaption', { text: name })]));
        });
        body.appendChild(grid);
      } else if (d.status !== 'error') {
        body.appendChild(h('div', { class: 'empty', text: 'Pictures appear here as Muse Image draws them.' }));
      }
      return;
    }
    if (!m) return;

    var ambiguous = m.items.filter(function (it) { return it.ambiguous; });
    if (ambiguous.length) {
      statusBox.appendChild(h('div', { class: 'note note-warn', style: { marginBottom: '14px' } }, h('p', null, [
        h('b', { text: ambiguous.length === 1 ? '1 word has more than one meaning: ' : ambiguous.length + ' words have more than one meaning: ' }),
        ambiguous.map(function (it) { return it.word + ' (also ' + (it.other_meanings || []).join(', ') + ')'; }).join('; ') + '. ',
        'Check that the picture shows the meaning you want, or pin it with "word: meaning" and rebuild.'
      ])));
    }

    var cards = h('div', { class: 'cards' });
    m.items.forEach(function (it, i) { cards.appendChild(itemCard(it, i)); });
    body.appendChild(cards);
    updateExportLinks();
  }

  function itemCard(it, i) {
    var best = keptCandidate(it);
    var pic = it.image
      ? h('img', { src: T.mediaUrl(state.data.id, it.image, 320), alt: 'Muse Image drawing for "' + it.word + '"', loading: 'lazy' })
      : h('span', { text: 'No picture passed the checks' });
    var statusPill = it.status === 'kept' ? h('span', { class: 'pill pill-kept', text: 'Kept' })
      : it.status === 'excluded' ? h('span', { class: 'pill pill-excluded', text: 'Excluded' })
      : h('span', { class: 'pill pill-review', text: 'Review: ' + reviewReason(it) });
    var samText = best ? best.sam_objects + ' · ' + (best.sam_confidence == null ? '–' : best.sam_confidence.toFixed(2)) : '–';
    return h('button', { type: 'button', class: 'card', 'aria-label': it.word + ', ' + (it.status || '') + '. Open details', onclick: function () { openItem(i); } }, [
      h('div', { class: 'pic' }, pic),
      h('div', { class: 'body' }, [
        h('div', { class: 'kv' }, [h('span', { class: 'word', text: it.word }), h('span', { class: 'muted', text: 'Zipf ' + (it.zipf == null ? '–' : it.zipf) })]),
        h('div', { class: 'kv' }, [h('span', { text: 'SAM objects' }), h('span', { text: samText })]),
        h('div', { class: 'kv' }, [h('span', { text: 'Spark named' }), h('span', { text: best ? best.spark_name : '–' })]),
        it.ambiguous ? h('span', { class: 'flag', text: 'Also means: ' + (it.other_meanings || []).join(', ') }) : null,
        (it.alternates || []).length ? h('span', { class: 'xsmall muted', text: 'Also accepts: ' + it.alternates.join(', ') }) : null,
        h('span', { style: { alignSelf: 'flex-start' } }, statusPill)
      ])
    ]);
  }

  // --- item dialog ------------------------------------------------------------------------
  var dlg = $('item-dialog');
  $('dlg-close').addEventListener('click', function () { dlg.close(); });
  dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });

  function openItem(i) {
    renderItem(i);
    if (!dlg.open) dlg.showModal();
  }

  function renderItem(i) {
    var d = state.data, it = d.manifest.items[i], editable = d.editable || !!tokenFor(d.id);
    $('dlg-title').textContent = it.word + (it.hint ? ' (' + it.hint + ')' : '');
    var body = $('dlg-body');
    body.innerHTML = '';
    var facts = [['Shown to SAM as', it.gloss], ['Drawn as', it.depiction], ['Frequency (Zipf)', it.zipf], ['Length (phonemes)', it.phonemes],
      ['Other meanings', it.ambiguous ? (it.other_meanings || []).join(', ') : 'none flagged'], ['Status', it.status]];
    body.appendChild(h('dl', { class: 'facts' }, facts.map(function (f) { return h('div', null, [h('dt', { text: f[0] }), h('dd', { text: f[1] == null ? '–' : String(f[1]) })]); })));

    var grid = h('div', { class: 'cand-grid' });
    (it.candidates || []).forEach(function (c, k) {
      var current = c.file === it.image;
      var pass = c.sam_ok && c.spark_ok;
      var why = [];
      if (!c.sam_ok) why.push(c.sam_objects === 1 ? 'object too small or too large' : c.sam_objects + ' objects found');
      if (!c.spark_ok) why.push('named "' + c.spark_name + '"');
      grid.appendChild(h('div', { class: 'cand' + (current ? ' current' : '') }, [
        h('img', { src: T.mediaUrl(d.id, c.file, 640), alt: 'Candidate ' + (k + 1) + ' for "' + it.word + '"', loading: 'lazy' }),
        h('div', { class: 'body' }, [
          h('div', { class: 'kv' }, [h('span', { text: 'Candidate ' + (k + 1) }), current ? h('span', { class: 'pill pill-kept', text: 'In use' }) : h('span')]),
          h('div', { class: 'kv' }, [h('span', { text: 'SAM 3.1 objects' }), h('span', { text: String(c.sam_objects) })]),
          h('div', { class: 'kv' }, [h('span', { text: 'SAM confidence' }), h('span', { text: c.sam_confidence == null ? '–' : c.sam_confidence.toFixed(3) })]),
          h('div', { class: 'kv' }, [h('span', { text: 'Box covers' }), h('span', { text: c.sam_area == null ? '–' : Math.round(c.sam_area * 100) + '% of picture' })]),
          h('div', { class: 'kv' }, [h('span', { text: 'Muse Spark named' }), h('span', null, [c.spark_name + ' ', T.pill(c.spark_code)])]),
          h('span', { class: pass ? 'check-ok' : 'check-bad', text: pass ? 'Passes both checks' : 'Fails: ' + why.join('; ') }),
          h('button', { type: 'button', class: 'btn btn-small', disabled: current || !editable, onclick: function () { save(i, { image: c.file }); } }, current ? 'Chosen picture' : 'Use this picture')
        ])
      ]));
    });
    body.appendChild(h('div', null, [h('h3', { class: 'small', style: { margin: '0 0 10px' }, text: 'Candidates and their checks' }), grid]));

    var named = (it.candidates || []).filter(function (c) { return !c.spark_ok && c.spark_name; }).map(function (c) { return c.spark_name.toLowerCase(); });
    var altInput = h('input', { type: 'text', id: 'alt-input', value: (it.alternates || []).join(', '), placeholder: 'e.g. teapot, kettle pot', disabled: !editable, autocomplete: 'off' });
    var statusSel = h('select', { id: 'status-input', disabled: !editable }, [
      h('option', { value: 'kept', text: 'Kept', selected: it.status === 'kept' }),
      h('option', { value: 'review', text: 'Needs review', selected: it.status === 'review' }),
      h('option', { value: 'excluded', text: 'Excluded', selected: it.status === 'excluded' })
    ]);
    body.appendChild(h('div', { class: 'edit-row' }, [
      h('label', { class: 'field' }, ['Accepted alternate names', altInput, h('span', { class: 'hint', text: 'Comma-separated. The Scorer codes these as correct.' + (named.length ? ' Muse Spark also said: ' + named.join(', ') + '.' : '') })]),
      h('label', { class: 'field', style: { flex: '0 1 180px' } }, ['Status', statusSel]),
      h('button', { type: 'button', class: 'btn btn-primary', disabled: !editable, onclick: function () {
        save(i, { alternates: altInput.value.split(',').map(function (s) { return s.trim(); }).filter(Boolean), status: statusSel.value });
      } }, 'Save')
    ]));
    if (!editable) body.appendChild(h('p', { class: 'xsmall muted', style: { margin: 0 }, text: 'On this public demo you can edit only the sets you built in this browser.' }));
  }

  function save(i, change) {
    var d = state.data;
    var headers = {};
    var tok = tokenFor(d.id);
    if (tok) headers['X-Edit-Token'] = tok;
    T.api('/api/sets/' + encodeURIComponent(d.id) + '/items/' + i, { method: 'PATCH', json: change, headers: headers }).then(function (item) {
      d.manifest.items[i] = item;
      var statuses = d.manifest.items.map(function (x) { return x.status; });
      d.kept = statuses.filter(function (s) { return s === 'kept'; }).length;
      d.review = statuses.filter(function (s) { return s === 'review'; }).length;
      d.excluded = statuses.filter(function (s) { return s === 'excluded'; }).length;
      renderSet();
      renderItem(i);
      loadSets();
      T.toast('Saved "' + item.word + '".');
    }).catch(function (e) { T.toast(e.message, 'error'); });
  }

  // --- exports ----------------------------------------------------------------------------
  function updateExportLinks() {
    if (!state.data) return;
    var base = '/api/sets/' + encodeURIComponent(state.data.id);
    $('dl-pdf').href = base + '/cards.pdf?per_page=' + $('per-page').value + '&word=' + ($('show-word').checked ? 1 : 0) + '&page=' + $('paper').value;
    $('dl-csv').href = base + '/norms.csv';
    $('dl-zip').href = base + '/set.zip';
    $('use-scorer').href = '/scorer?set=' + encodeURIComponent(state.data.id);
  }
  ['per-page', 'paper', 'show-word'].forEach(function (id) { $(id).addEventListener('change', updateExportLinks); });

  // --- build ------------------------------------------------------------------------------
  $('naming-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var btn = $('build-btn');
    var lines = wordLines();
    if (!lines.length) { T.toast('Add at least one word, one per line.', 'error'); $('words').focus(); return; }
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner" aria-hidden="true"></span> Starting…';
    T.api('/api/sets', { method: 'POST', json: {
      name: $('set-name').value.trim(), lang: $('lang').value, words: lines.join('\n'), style: radio('style'), candidates: +radio('cands')
    } }).then(function (res) {
      saveToken(res.id, res.edit_token);
      T.toast('Building your set. This takes about a minute.');
      return loadSets().then(function () { return openSet(res.id); });
    }).catch(function (err) {
      T.toast(err.message, 'error');
    }).then(function () {
      btn.textContent = 'Generate set';
      refreshStatus();
    });
  });
  $('words').addEventListener('input', updateEstimate);
  document.querySelectorAll('input[name="cands"]').forEach(function (r) { r.addEventListener('change', updateEstimate); });

  $('task').addEventListener('change', function () {
    var t = $('task').value;
    $('naming-form').hidden = t !== 'naming';
    $('scene-form').hidden = t !== 'scene';
    $('fluency-info').hidden = t !== 'fluency';
  });
  $('refresh-sets').addEventListener('click', function () { loadSets(); if (state.current) fetchSet(state.current); });

  // --- scenes -----------------------------------------------------------------------------
  function loadScenes() {
    return T.api('/api/scenes').then(function (scenes) {
      state.scenes = scenes;
      var grid = $('scenes');
      grid.innerHTML = '';
      $('scenes-panel').hidden = !scenes.length;
      $('scenes-meta').textContent = scenes.length + (scenes.length === 1 ? ' scene' : ' scenes');
      scenes.forEach(function (s) {
        grid.appendChild(h('button', { type: 'button', class: 'card scene-card', 'aria-label': 'Scene ' + (s.theme || s.setting || s.id) + '. Open details', onclick: function () { openScene(s.id); } }, [
          h('div', { class: 'pic' }, s.image_url ? h('img', { src: s.image_url + '?w=320', alt: 'Scene: ' + (s.description || s.theme || s.id), loading: 'lazy' }) : h('span', { text: 'No picture' })),
          h('div', { class: 'body' }, [
            h('span', { class: 'word', text: s.theme || s.setting || ('Scene ' + s.id) }),
            h('p', { text: (s.content_units || []).length + ' content units · ' + T.langName(state.langs, s.lang || 'en') + (s.units_edited ? ' · reviewed' : '') })
          ])
        ]));
      });
    }).catch(function () { /* scenes are optional */ });
  }

  function openScene(id) {
    var s = (state.scenes || []).filter(function (x) { return x.id === id; })[0];
    if (!s) return;
    var editable = s.editable || !!tokenFor('scene-' + s.id);
    $('dlg-title').textContent = 'Scene · ' + (s.theme || s.setting || s.id);
    var body = $('dlg-body');
    body.innerHTML = '';
    if (s.image_url) body.appendChild(h('img', { src: s.image_url, alt: 'Scene: ' + (s.description || ''), style: { width: '100%', borderRadius: '10px', border: '1px solid #E5E7EB' } }));
    if (s.description) body.appendChild(h('p', { class: 'small', style: { margin: 0 } }, [h('span', { class: 'muted', text: 'Muse Spark sees: ' }), s.description]));
    var units = h('textarea', { id: 'units-input', rows: '10', class: 'mono', disabled: !editable, spellcheck: 'false' });
    units.value = (s.content_units || []).join('\n');
    body.appendChild(h('label', { class: 'field' }, ['Content units, one per line', units,
      h('span', { class: 'hint', text: 'What a full description should mention: key people, objects and actions. Listed by Muse Spark from the finished picture; correct anything that isn\'t really there.' })]));
    body.appendChild(h('div', { class: 'btn-row' }, [
      h('button', { type: 'button', class: 'btn btn-primary', disabled: !editable, onclick: function () {
        var headers = {}, tok = tokenFor('scene-' + s.id);
        if (tok) headers['X-Edit-Token'] = tok;
        T.api('/api/scenes/' + encodeURIComponent(s.id), { method: 'PATCH', headers: headers,
          json: { content_units: units.value.split('\n').map(function (u) { return u.trim(); }).filter(Boolean) } })
          .then(function () { T.toast('Content units saved.'); return loadScenes(); })
          .then(function () { openScene(s.id); })
          .catch(function (e) { T.toast(e.message, 'error'); });
      } }, 'Save content units'),
      h('a', { class: 'btn btn-dark', href: '/scorer?task=description&scene=' + encodeURIComponent(s.id) }, 'Use in Scorer')
    ]));
    if (!editable) body.appendChild(h('p', { class: 'xsmall muted', style: { margin: 0 }, text: 'On this public demo you can edit only the scenes you drew in this browser.' }));
    if (!dlg.open) dlg.showModal();
  }

  $('scene-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var btn = $('scene-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner" aria-hidden="true"></span> Drawing…';
    T.api('/api/scenes', { method: 'POST', json: { lang: $('scene-lang').value, theme: $('scene-theme').value.trim() || null } })
      .then(function (scene) {
        if (scene.edit_token) saveToken('scene-' + scene.id, scene.edit_token);
        T.toast('Scene ready. Check its content units.');
        return loadScenes().then(function () { openScene(scene.id); });
      })
      .catch(function (err) { T.toast(err.message, 'error'); })
      .then(function () { btn.disabled = false; btn.textContent = 'Draw a scene'; refreshStatus().then(applyFeatures); });
  });

  // --- start ------------------------------------------------------------------------------
  T.status().then(function (st) { state.status = st; applyFeatures(st); });
  loadSets().then(function (sets) {
    var want = T.param('set');
    var first = sets.filter(function (s) { return s.status === 'done'; })[0];
    if (want || first) openSet(want || first.id);
  });
  loadScenes();
})();
