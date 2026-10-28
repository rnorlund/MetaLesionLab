/* Live demo: today's AI budget, and what to do when it's used up.
   Added to every page by web/guard.py only when the server runs with PUBLIC_DEMO=1.
   - A slim note at the top says how much of today's budget for Meta API calls is left.
   - When the budget is used up, a banner at the top says so and offers recorded examples.
   - Any response the guard marks (X-Tippa-Guard: budget) brings up that banner; a guard note
     (X-Tippa-Guard-Note, e.g. fewer pictures per word) is shown as a toast. */
(function () {
  'use strict';
  if (window.__tippaGuard) return;
  window.__tippaGuard = true;
  var HIDE_KEY = 'tippa-guard-note-hidden';
  var state = { info: null, banner: null, note: null };

  function el(tag, attrs, children) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'text') e.textContent = attrs[k];
      else if (k.slice(0, 2) === 'on') e.addEventListener(k.slice(2), attrs[k]);
      else e.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return e;
  }
  function stored(key, value) {
    try {
      if (value === undefined) return window.sessionStorage.getItem(key);
      window.sessionStorage.setItem(key, value);
    } catch (e) { /* storage off */ }
    return null;
  }

  var css = '' +
    '.tg-note{position:relative;padding:5px 44px 5px 16px;text-align:center;background:var(--soft,#F9FAFB);' +
    'border-bottom:1px solid var(--line,#E5E7EB);color:var(--muted,#4B5563);font:13px/1.4 var(--sans,system-ui,sans-serif)}' +
    '.tg-note b{color:var(--ink,#111827);font-weight:600}' +
    '.tg-note button{position:absolute;right:8px;top:50%;transform:translateY(-50%);border:0;background:transparent;' +
    'color:var(--faint,#6B7280);font:16px/1 var(--sans,system-ui,sans-serif);cursor:pointer;padding:3px 8px;border-radius:6px}' +
    '.tg-note button:hover,.tg-note button:focus-visible{background:var(--ground,#F3F4F6);color:var(--ink,#111827)}' +
    '.tg-banner{background:var(--amber-soft,#FEF3C7);border-bottom:1px solid var(--amber,#FDE68A);color:var(--ink,#111827);' +
    'font:15px/1.45 var(--sans,system-ui,sans-serif);padding:12px 16px}' +
    '.tg-banner-in{max-width:1100px;margin:0 auto;display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px}' +
    '.tg-banner p{margin:0;flex:1 1 320px}' +
    '.tg-banner .tg-links{display:flex;flex-wrap:wrap;gap:8px}' +
    '.tg-banner a,.tg-banner button{display:inline-block;font:600 14px/1 var(--sans,system-ui,sans-serif);color:var(--ink,#111827);' +
    'background:#fff;border:1px solid var(--line-2,#D1D5DB);border-radius:8px;padding:9px 12px;text-decoration:none;cursor:pointer}' +
    '.tg-banner a:hover,.tg-banner button:hover,.tg-banner a:focus-visible,.tg-banner button:focus-visible{border-color:var(--ink,#111827)}' +
    '@media (max-width:640px){.tg-note{font-size:12px}}';

  function addStyle() {
    if (document.getElementById('tg-style')) return;
    document.head.appendChild(el('style', { id: 'tg-style', text: css }));
  }

  function money(x) { return '$' + Number(x || 0).toFixed(2); }
  function hours(s) { var h = s / 3600; return h < 1 ? 'less than an hour' : 'about ' + Math.round(h) + ' h'; }

  function showNote(info) {
    if (state.note) state.note.remove();
    if (stored(HIDE_KEY) === '1' || info.exhausted) return;
    var pct = info.daily_cap_usd > 0 ? Math.round(100 * info.left_today_usd / info.daily_cap_usd) : 0;
    var hide = el('button', { type: 'button', 'aria-label': 'Hide this note', title: 'Hide', text: '×', onclick: function () {
      stored(HIDE_KEY, '1'); state.note.remove();
    } });
    state.note = el('div', { class: 'tg-note', role: 'status' }, [
      el('span', {}, ['Live demo: calls to Meta’s models share a budget of ' + money(info.daily_cap_usd) + ' a day. ',
        el('b', { text: pct + '% left today.' }), ' ' + (info.free_note || 'Browsing, replays and exports are free.')]), hide
    ]);
    document.body.insertBefore(state.note, document.body.firstChild);
  }

  function exampleLink(ex) {
    var tourOnPage = ex.tour && document.querySelector('[data-tour-start]');
    if (tourOnPage) return el('button', { type: 'button', 'data-tour-start': ex.tour, text: ex.label });
    return el('a', { href: ex.href, text: ex.label });
  }

  function showExhausted(payload) {
    var info = payload || state.info || {};
    if (state.note) state.note.remove();
    if (state.banner) return;
    var wait = info.resets_in_s ? ' (' + hours(info.resets_in_s) + ' from now)' : '';
    var links = (info.examples || []).map(exampleLink);
    state.banner = el('div', { class: 'tg-banner', role: 'region', 'aria-label': 'Live demo budget' }, [
      el('div', { class: 'tg-banner-in' }, [
        el('p', {}, [el('b', { text: 'Today’s live demo budget is used up. ' }),
          (info.paused || 'New scoring and picture generation pause') + ' until 00:00 UTC' + wait +
          '. Here’s what still works:']),
        el('div', { class: 'tg-links' }, links)
      ])
    ]);
    document.body.insertBefore(state.banner, document.body.firstChild);
  }

  function toast(msg) {
    if (window.TOT && window.TOT.toast) window.TOT.toast(msg);
  }

  // Watch every response: the page's own code shows the error text; this adds the banner.
  if (window.fetch) {
    var plain = window.fetch.bind(window);
    window.fetch = function () {
      return plain.apply(null, arguments).then(function (res) {
        try {
          var kind = res.headers.get('x-tippa-guard');
          var note = res.headers.get('x-tippa-guard-note');
          if (kind === 'budget') res.clone().json().then(showExhausted, function () { showExhausted(); });
          if (note) toast(note);
        } catch (e) { /* never break the page's request */ }
        return res;
      });
    };
  }

  function start() {
    addStyle();
    plainFetchGuard().then(function (info) {
      if (!info || !info.public_demo) return;
      state.info = info;
      if (info.exhausted) showExhausted(info); else showNote(info);
    });
  }
  function plainFetchGuard() {
    return fetch('/api/guard', { headers: { Accept: 'application/json' } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
