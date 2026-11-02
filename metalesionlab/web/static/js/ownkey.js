/* Your own Meta API key (for judges): More → "Use your own API key" opens a small dialog. The key stays in this tab's
   sessionStorage (gone when the tab closes) and is added, as the X-Meta-Key header, only to the paid requests: Ask
   Socrates (/api/socrates…), the voice test (/api/phaedrus/…), Draw it again (/api/plato/redraw) and telephone
   (/api/plato/telephone/…). The server uses it for that request and nothing
   else (web/own_key.py): those calls bill the visitor's account, so the demo's daily budget doesn't limit them.
   While a key is set, "More" and the phone menu show a small dot. site.py adds this file to every Plato page. */
(function () {
  'use strict';
  var STORE = 'pc-own-meta-key', PAID = /^\/api\/(socrates|phaedrus|plato\/redraw|plato\/telephone)(\/|$|\?)/;
  function get() { try { return sessionStorage.getItem(STORE) || ''; } catch (e) { return ''; } }
  function set(v) {
    try { if (v) sessionStorage.setItem(STORE, v); else sessionStorage.removeItem(STORE); } catch (e) { /* storage off */ }
    document.documentElement.classList.toggle('has-own-key', !!v);
  }

  // the key travels only with the paid requests to this site
  var native = window.fetch;
  if (native) {
    window.fetch = function (input, init) {
      var key = get(), url = typeof input === 'string' ? input : (input && input.url) || '';
      var path = url.indexOf(location.origin) === 0 ? url.slice(location.origin.length) : url;
      if (key && PAID.test(path)) {
        init = init || {};
        var headers = new Headers(init.headers || (typeof input !== 'string' && input.headers) || {});
        headers.set('X-Meta-Key', key);
        init.headers = headers;
      }
      return native.call(this, input, init);
    };
  }

  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === 'text') e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return e;
  }
  var dialog = null;
  function open() {
    if (!dialog) {
      var input = el('input', { type: 'password', id: 'ok-key', autocomplete: 'off', spellcheck: 'false', placeholder: 'Paste your Meta Model API key' });
      var status = el('p', { class: 'ok-status', role: 'status' });
      var save = el('button', { type: 'button', class: 'ok-save', text: 'Use this key' });
      var remove = el('button', { type: 'button', class: 'ok-remove', text: 'Remove key' });
      var close = el('button', { type: 'button', class: 'ok-close', 'aria-label': 'Close', text: '×' });
      dialog = el('dialog', { class: 'ok-dialog', 'aria-labelledby': 'ok-title' }, [
        close,
        el('h2', { id: 'ok-title', text: 'Use your own Meta API key' }),
        el('p', { text: 'The live demo shares a small daily budget. To try Ask Socrates, the voice test and Draw it again as much as you like, and to play telephone with your own drawing, use your own key from dev.meta.ai. Those calls then bill your account.' }),
        el('label', { for: 'ok-key', text: 'Your key' }), input,
        el('ul', { class: 'ok-facts' }, [
          el('li', { text: 'It stays in this browser tab only, and is gone when you close the tab.' }),
          el('li', { text: 'It is sent only with those requests, over HTTPS.' }),
          el('li', { text: 'Our server uses it for that request and never stores or logs it.' })
        ]),
        status,
        el('div', { class: 'ok-actions' }, [save, remove])
      ]);
      function show() {
        var on = !!get();
        status.textContent = on ? 'A key is in use for this tab.' : 'No key set: the demo’s shared budget is used.';
        remove.hidden = !on;
      }
      save.addEventListener('click', function () {
        var v = input.value.trim();
        if (!/^[A-Za-z0-9._:|+\/=\-]{20,400}$/.test(v)) { status.textContent = 'That doesn’t look like an API key: paste it without spaces or quotes.'; return; }
        set(v); input.value = ''; show();
        status.textContent = 'Saved for this tab. Ask Socrates and the voice test now use your key.';
        try { window.dispatchEvent(new CustomEvent('pc-own-key')); } catch (e) { /* old browser */ }
      });
      remove.addEventListener('click', function () {
        set(''); show();
        try { window.dispatchEvent(new CustomEvent('pc-own-key')); } catch (e) { /* old browser */ }
      });
      close.addEventListener('click', function () { dialog.close(); });
      dialog.addEventListener('click', function (e) { if (e.target === dialog) dialog.close(); });
      dialog._show = show;
      document.body.appendChild(dialog);
    }
    dialog._show();
    [].forEach.call(document.querySelectorAll('details.nav-more[open], details.nav-menu[open]'), function (d) { d.open = false; });
    if (dialog.showModal) dialog.showModal(); else dialog.setAttribute('open', '');
    var f = dialog.querySelector('input'); if (f) f.focus();
  }
  function addItems() {
    [].forEach.call(document.querySelectorAll('.nav-more .nav-panel, .nav-menu .nav-panel'), function (panel) {
      if (panel.querySelector('.ok-item')) return;
      panel.appendChild(el('p', { class: 'nav-group', text: 'For judges' }));
      var b = el('button', { type: 'button', class: 'ok-item' }, ['Use your own API key']);
      b.addEventListener('click', open);
      panel.appendChild(b);
    });
  }
  function init() {
    set(get());
    addItems();
    if (/[?&]ownkey=1(&|$)/.test(location.search)) open();
  }
  window.PCOwnKey = { open: open, active: function () { return !!get(); } };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
