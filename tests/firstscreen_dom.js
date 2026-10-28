/* A small stand-in for the browser, enough to run a series page's scripts under node and read what they drew on the
   first screen (tests/test_plato_firstscreen.py). It is permissive on purpose: anything a page asks for that isn't
   modelled here (a canvas, a layout measurement) answers with a harmless stand-in, so a chart further down the page
   can't stop the first screen from drawing.

   usage: node firstscreen_dom.js CONFIG.json
   CONFIG: {"html": page source, "scripts": [js files, in order], "api": {"/api/...": json file}, "ids": [ids to return]}
   The page's elements with an id are made flat, side by side (not nested), so ask for the innermost id you need.
   prints {"ids": {id: outerHTML}, "errors": [...]} */
'use strict';
const fs = require('fs');
const vm = require('vm');

const cfg = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const errors = [];

// Anything: callable, indexable, and 0 in arithmetic.
const ANY = new Proxy(function () {}, {
  get: (t, k) => (k === Symbol.toPrimitive ? () => 0 : k === 'length' ? 0 : k === 'then' ? undefined : ANY),
  apply: () => ANY,
  construct: () => ANY,
});

function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function escAttr(s) { return esc(s).replace(/"/g, '&quot;'); }

const byId = new Map();

class Node_ {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.nodeName = this.tagName;
    this.nodeType = 1;
    this.isFragment = false;
    this.attrs = {};
    this.children = [];
    this.parentNode = null;
    this._html = null;
    this._text = null;
    this.dataset = {};
    this.value = '';
    this.checked = false;
    this.disabled = false;
    this.clientWidth = 800;
    this.clientHeight = 400;
    this.offsetWidth = 800;
    this.offsetHeight = 400;
    const styles = {};
    this._styles = styles;
    this.style = new Proxy(styles, {
      get: (t, k) => (k === 'setProperty' ? (n, v) => { t[n] = v; } : k === 'removeProperty' ? (n) => { delete t[n]; } : (t[k] == null ? '' : t[k])),
      set: (t, k, v) => { t[k] = v; return true; },
    });
    const self = this;
    this.classList = {
      add: (...c) => { const s = new Set(self.className.split(/\s+/).filter(Boolean)); c.forEach((x) => s.add(x)); self.className = [...s].join(' '); },
      remove: (...c) => { self.className = self.className.split(/\s+/).filter((x) => x && !c.includes(x)).join(' '); },
      toggle: (c, on) => { const has = self.classList.contains(c); if (on === undefined ? !has : on) self.classList.add(c); else self.classList.remove(c); },
      contains: (c) => self.className.split(/\s+/).includes(c),
    };
  }
  get className() { return this.attrs.class || ''; }
  set className(v) { this.attrs.class = String(v); }
  get id() { return this.attrs.id || ''; }
  set id(v) { this.setAttribute('id', v); }
  get hidden() { return 'hidden' in this.attrs; }
  set hidden(v) { if (v) this.attrs.hidden = ''; else delete this.attrs.hidden; }
  get firstChild() { return this.children[0] || null; }
  get lastChild() { return this.children[this.children.length - 1] || null; }
  get childNodes() { return this.children; }
  get firstElementChild() { return this.firstChild; }
  get textContent() {
    if (this._text != null) return this._text;
    return (this._html ? this._html.replace(/<[^>]*>/g, '') : '') + this.children.map((c) => c.textContent).join('');
  }
  set textContent(v) { this._text = String(v == null ? '' : v); this._html = null; this.children = []; }
  get innerHTML() { return (this._text != null ? esc(this._text) : this._html || '') + this.children.map((c) => c.outerHTML).join(''); }
  set innerHTML(v) { this._html = String(v); this._text = null; this.children = []; }
  get outerHTML() {
    if (this.nodeType === 3) return esc(this._text);
    const tag = this.tagName.toLowerCase();
    let attrs = Object.keys(this.attrs).map((k) => ' ' + k + '="' + escAttr(this.attrs[k]) + '"').join('');
    const css = Object.keys(this._styles).map((k) => k + ': ' + this._styles[k]).join('; ');
    if (css) attrs += ' style="' + escAttr(css) + '"';
    return '<' + tag + attrs + '>' + this.innerHTML + '</' + tag + '>';
  }
  setAttribute(k, v) { this.attrs[k] = String(v); if (k === 'id') byId.set(String(v), this); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  hasAttribute(k) { return k in this.attrs; }
  removeAttribute(k) { delete this.attrs[k]; }
  appendChild(c) {
    if (c && c.isFragment) { c.children.slice().forEach((x) => this.appendChild(x)); c.children = []; return c; }
    if (c.parentNode) c.parentNode.removeChild(c);
    if (this._text != null) { this._html = esc(this._text); this._text = null; }  // text set earlier stays in front
    c.parentNode = this; this.children.push(c); return c;
  }
  append(...cs) { cs.forEach((c) => this.appendChild(typeof c === 'string' ? doc.createTextNode(c) : c)); }
  insertBefore(c, ref) {
    if (c.parentNode) c.parentNode.removeChild(c);
    const i = ref ? this.children.indexOf(ref) : -1;
    c.parentNode = this;
    if (i < 0) this.children.push(c); else this.children.splice(i, 0, c);
    return c;
  }
  removeChild(c) { const i = this.children.indexOf(c); if (i >= 0) this.children.splice(i, 1); c.parentNode = null; return c; }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  replaceChildren(...cs) { this.children = []; this._html = null; this._text = null; this.append(...cs); }
  cloneNode() { return new Node_(this.tagName); }
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() { return true; }
  focus() {}
  blur() {}
  click() {}
  scrollIntoView() {}
  closest() { return null; }
  matches() { return false; }
  getBoundingClientRect() { return { left: 0, top: 0, right: 800, bottom: 400, width: 800, height: 400, x: 0, y: 0 }; }
  getBBox() { return { x: 0, y: 0, width: 40, height: 12 }; }
  getComputedTextLength() { return 40; }
  walk(fn) { this.children.forEach((c) => { fn(c); c.walk(fn); }); }
  querySelectorAll(sel) {
    const out = [];
    const parts = String(sel).split(',').map((s) => s.trim().split(/\s+/).pop());
    const test = (el, p) => {
      const m = p.match(/^([a-z0-9]*)((?:[.#][\w-]+)*)$/i);
      if (!m) return false;
      if (m[1] && el.tagName !== m[1].toUpperCase()) return false;
      return (m[2].match(/[.#][\w-]+/g) || []).every((x) => (x[0] === '#' ? el.id === x.slice(1) : el.classList.contains(x.slice(1))));
    };
    this.walk((el) => { if (el.nodeType === 1 && parts.some((p) => test(el, p))) out.push(el); });
    return out;
  }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  getElementsByTagName(t) { return this.querySelectorAll(t); }
}
// Every element answers anything it doesn't model with ANY.
function wrap(n) {
  return new Proxy(n, {
    get: (t, k, r) => (k in t ? Reflect.get(t, k, r) : typeof k === 'symbol' ? undefined : ANY),
  });
}

const doc = {
  body: null,
  documentElement: null,
  readyState: 'complete',
  createElement: (t) => wrap(new Node_(t)),
  createElementNS: (ns, t) => wrap(new Node_(t)),
  createTextNode: (s) => { const n = new Node_('#text'); n.nodeType = 3; n._text = String(s); return wrap(n); },
  createDocumentFragment: () => { const f = wrap(new Node_('#fragment')); f.isFragment = true; return f; },
  getElementById: (id) => byId.get(id) || null,
  querySelectorAll: (s) => doc.body.querySelectorAll(s),
  querySelector: (s) => doc.body.querySelector(s),
  addEventListener: () => {},
  removeEventListener: () => {},
};
doc.body = doc.createElement('body');
doc.documentElement = doc.createElement('html');

// The page's elements that carry an id, from its source: enough for every getElementById.
const src = fs.readFileSync(cfg.html, 'utf8');
for (const m of src.matchAll(/<([a-zA-Z][\w-]*)\b([^>]*?)\bid="([^"]+)"([^>]*)>/g)) {
  if (m[1].toLowerCase() === 'script') continue;
  const el = doc.createElement(m[1]);
  el.setAttribute('id', m[3]);
  const rest = m[2] + m[4];
  const cls = rest.match(/\bclass="([^"]*)"/);
  if (cls) el.setAttribute('class', cls[1]);
  if (/\bhidden\b/.test(rest)) el.hidden = true;
  const val = rest.match(/\bvalue="([^"]*)"/);
  if (val) el.value = val[1];
  doc.body.appendChild(el);
}

const api = {};
for (const [path, file] of Object.entries(cfg.api)) api[path] = fs.readFileSync(file, 'utf8');
function fetch(path) {
  const key = String(path).split('?')[0];
  const body = api[key];
  const res = body == null
    ? { ok: false, status: 404, text: () => Promise.resolve('{"detail": "not found"}'), json: () => Promise.resolve({ detail: 'not found' }) }
    : { ok: true, status: 200, text: () => Promise.resolve(body), json: () => Promise.resolve(JSON.parse(body)) };
  return Promise.resolve(res);
}

const win = {
  document: doc,
  fetch,
  location: { hash: '', search: '', pathname: '/', href: 'http://localhost/' },
  history: { replaceState() {}, pushState() {} },
  navigator: { userAgent: 'node' },
  innerWidth: 1280,
  innerHeight: 800,
  devicePixelRatio: 1,
  matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }),
  getComputedStyle: () => new Proxy({}, { get: () => '' }),
  requestAnimationFrame: () => 0,
  cancelAnimationFrame: () => {},
  setTimeout: () => 0,  // nothing waits on a timer for the first screen
  clearTimeout: () => {},
  setInterval: () => 0,
  clearInterval: () => {},
  addEventListener: () => {},
  removeEventListener: () => {},
  localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  Image: function () { return doc.createElement('img'); },
  URLSearchParams,
  console: { log() {}, info() {}, warn() {}, error: (...a) => errors.push(a.join(' ')) },
  ResizeObserver: function () { return { observe() {}, disconnect() {} }; },
  IntersectionObserver: function () { return { observe() {}, disconnect() {} }; },
  CustomEvent: function (t, o) { this.type = t; this.detail = o && o.detail; },
};
win.window = win;
win.self = win;
win.globalThis = win;
const ctx = vm.createContext(win);

process.on('unhandledRejection', (e) => errors.push('rejection: ' + (e && e.stack ? e.stack.split('\n')[0] : e)));
for (const file of cfg.scripts) {
  try { vm.runInContext(fs.readFileSync(file, 'utf8'), ctx, { filename: file }); }
  catch (e) { errors.push(file + ': ' + e.message); }
}

// let the fetch promises and their .then chains settle
(async () => {
  for (let i = 0; i < 50; i++) await new Promise((r) => setImmediate(r));
  const ids = {};
  for (const id of cfg.ids) { const el = byId.get(id); ids[id] = el ? el.outerHTML : null; }
  process.stdout.write(JSON.stringify({ ids, errors }));
})();
