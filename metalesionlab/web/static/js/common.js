/* Helpers shared by every page, plus the site header's menus. */
(function () {
  'use strict';

  var CODES = {
    Correct: { label: 'Correct', color: '#111827' },
    Semantic: { label: 'Semantic', color: '#2563EB' },
    Formal: { label: 'Formal', color: '#C2410C' },
    Mixed: { label: 'Mixed', color: '#7C3AED' },
    Nonword: { label: 'Nonword', color: '#0F766E' },
    Neologism: { label: 'Neologism', color: '#BE185D' },
    Unrelated: { label: 'Unrelated', color: '#92400E' },
    Description: { label: 'Description', color: '#A21CAF' },
    Visual: { label: 'Visual', color: '#15803D' },
    NoResponse: { label: 'No response', color: '#6B7280' }
  };
  var ORDER = ['Correct', 'Semantic', 'Formal', 'Mixed', 'Nonword', 'Neologism', 'Unrelated', 'Description', 'Visual', 'NoResponse'];

  function normCode(code) {
    if (!code) return null;
    var key = String(code).toLowerCase().replace(/[^a-z]/g, '');
    for (var i = 0; i < ORDER.length; i++) if (ORDER[i].toLowerCase() === key) return ORDER[i];
    return String(code);
  }
  function codeInfo(code) {
    var c = normCode(code);
    return CODES[c] || { label: c || '?', color: '#4B5563' };
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (ch) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
    });
  }

  /* Tiny element builder: h('div', {class: 'x', onclick: fn}, [children or text]) */
  function h(tag, attrs, children) {
    var el = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v == null || v === false) return;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k === 'html') el.innerHTML = v;
      else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
      else if (k.slice(0, 2) === 'on' && typeof v === 'function') el.addEventListener(k.slice(2), v);
      else if (v === true) el.setAttribute(k, '');
      else el.setAttribute(k, v);
    });
    [].concat(children == null ? [] : children).forEach(function (c) {
      if (c == null || c === false) return;
      el.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return el;
  }

  function pill(code) {
    var info = codeInfo(code);
    var el = h('span', { class: 'pill', text: info.label });
    el.style.background = info.color;
    return el;
  }

  /* fetch JSON; throws an Error whose message is the server's friendly "detail". */
  function api(path, opts) {
    opts = opts || {};
    var init = { method: opts.method || 'GET', headers: opts.headers || {} };
    if (opts.json !== undefined) {
      init.body = JSON.stringify(opts.json);
      init.headers['Content-Type'] = 'application/json';
    } else if (opts.body) {
      init.body = opts.body;
    }
    return fetch(path, init).then(function (res) {
      return res.text().then(function (text) {
        var data = null;
        try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
        if (!res.ok) {
          var detail = data && data.detail;
          if (Array.isArray(detail)) detail = detail.map(function (d) { return d.msg; }).join('; ');
          var err = new Error(detail || ('Request failed (' + res.status + ')'));
          err.status = res.status;
          throw err;
        }
        return data;
      });
    });
  }

  function mediaUrl(setId, file, width) {
    var path = String(file).split('/').map(encodeURIComponent).join('/');
    return '/media/sets/' + encodeURIComponent(setId) + '/' + path + (width ? '?w=' + width : '');
  }

  var toastZone = null;
  function toast(msg, kind) {
    if (!toastZone) {
      toastZone = h('div', { class: 'toast-zone', role: 'status', 'aria-live': 'polite' });
      document.body.appendChild(toastZone);
    }
    var t = h('div', { class: 'toast' + (kind === 'error' ? ' error' : ''), text: msg });
    toastZone.appendChild(t);
    setTimeout(function () { t.remove(); }, kind === 'error' ? 7000 : 4000);
  }

  function csvCell(v) {
    var s = v == null ? '' : String(v);
    return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  function downloadCSV(filename, columns, rows) {
    var lines = [columns.map(csvCell).join(',')];
    rows.forEach(function (r) { lines.push(columns.map(function (c) { return csvCell(r[c]); }).join(',')); });
    var blob = new Blob(['﻿' + lines.join('\r\n') + '\r\n'], { type: 'text/csv;charset=utf-8' });
    var a = h('a', { href: URL.createObjectURL(blob), download: filename });
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }

  function stackBar(counts, total, label) {
    var bar = h('div', { class: 'stack-bar', role: 'img', 'aria-label': label || '' });
    ORDER.forEach(function (c) {
      var n = counts[c] || 0;
      if (!n) return;
      var seg = h('div', { title: codeInfo(c).label + ' ' + n + ' (' + Math.round(100 * n / total) + '%)' });
      seg.style.flex = n + ' 1 0';
      seg.style.background = codeInfo(c).color;
      bar.appendChild(seg);
    });
    return bar;
  }
  function legend(codes) {
    var el = h('div', { class: 'legend' });
    codes.forEach(function (c) {
      var sw = h('span', { class: 'swatch' });
      sw.style.background = codeInfo(c).color;
      el.appendChild(h('span', null, [sw, typeof c === 'string' ? codeInfo(c).label : c]));
    });
    return el;
  }
  function describeCounts(counts, total) {
    return ORDER.filter(function (c) { return counts[c]; }).map(function (c) {
      return codeInfo(c).label + ' ' + counts[c] + ' of ' + total;
    }).join(', ');
  }

  function status() {
    if (!status.p) status.p = api('/api/status').catch(function () { return null; });
    return status.p;
  }

  function langName(langs, code) {
    var l = (langs || []).filter(function (x) { return x.code === code; })[0];
    return l ? l.name : code;
  }
  function fillLanguages(select, langs, selected) {
    select.innerHTML = '';
    langs.forEach(function (l) {
      select.appendChild(h('option', { value: l.code, text: l.name + (l.verified ? '' : ' (experimental)') }));
    });
    if (selected) select.value = selected;
  }

  function param(name) { return new URLSearchParams(location.search).get(name); }

  // The product name and which optional pages this server has: web/site.py puts them in every page.
  var site = { brand: '', tagline: '', pages: {} };
  try {
    var blob = document.getElementById('site-data');
    if (blob) site = JSON.parse(blob.textContent);
  } catch (e) { /* keep the defaults */ }
  function hasPage(path) { return !!(site.pages && site.pages[path]); }

  // Site header: close the More and Menu panels on Escape or a click elsewhere.
  function closeMenus(except) {
    document.querySelectorAll('.nav-more[open], .nav-menu[open]').forEach(function (d) { if (d !== except) d.open = false; });
  }
  document.addEventListener('click', function (e) {
    closeMenus(e.target.closest ? e.target.closest('.nav-more, .nav-menu') : null);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var open = document.querySelector('.nav-more[open], .nav-menu[open]');
    if (!open) return;
    open.open = false;
    open.querySelector('summary').focus();
  });

  window.TOT = {
    BRAND: site.brand, site: site, hasPage: hasPage,
    CODES: CODES, ORDER: ORDER, normCode: normCode, codeInfo: codeInfo, esc: esc, h: h, pill: pill, api: api,
    mediaUrl: mediaUrl, toast: toast, downloadCSV: downloadCSV, stackBar: stackBar, legend: legend,
    describeCounts: describeCounts, status: status, langName: langName, fillLanguages: fillLanguages, param: param
  };
})();
