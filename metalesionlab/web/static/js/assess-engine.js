/* Naming Assessment engine, shared by /assess (clinicians and researchers) and /take (anyone).

   Timing. The microphone is captured continuously through an AudioWorklet; every block of samples
   carries the audio clock frame of its first sample. When a picture is drawn, its onset (the
   second animation frame after the picture is revealed) is converted from the page clock to the
   audio clock with AudioContext.getOutputTimestamp(), allowing for the output and input latencies
   the browser reports. Each clip starts LEAD_IN_MS before the onset (the server takes its noise
   floor from that stretch) and ends at "next" or at the time limit. Clips are resampled to 16 kHz
   and sent as WAV with the onset's position in the clip; the server finds the speech onset.
   Device delays the browser doesn't report (typically 10-50 ms) are not corrected.

   Storage. Sessions and private sets live in this browser's IndexedDB, never on the server. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var LEAD_IN_MS = 300, CLIP_RATE = 16000, KEEP_S = 120;

  // --- continuous capture ------------------------------------------------------------------
  function Capture() {
    this.ctx = null; this.stream = null; this.node = null; this.chunks = []; this.total = 0; this.rate = 48000;
    this.inputLatency = 0; this.onlevel = null;
  }
  Capture.supported = function () {
    return !!(window.AudioContext && window.AudioWorkletNode && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  };
  Capture.prototype.start = function () {
    var self = this;
    var constraints = { audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 } };
    return navigator.mediaDevices.getUserMedia(constraints).then(function (stream) {
      self.stream = stream;
      self.ctx = new AudioContext();
      self.rate = self.ctx.sampleRate;
      var settings = stream.getAudioTracks()[0].getSettings ? stream.getAudioTracks()[0].getSettings() : {};
      self.inputLatency = typeof settings.latency === 'number' ? settings.latency : 0;
      return self.ctx.audioWorklet.addModule('/static/js/assess-worklet.js');
    }).then(function () {
      var ctx = self.ctx;
      var src = ctx.createMediaStreamSource(self.stream);
      self.node = new AudioWorkletNode(ctx, 'tl-capture', { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1] });
      self.node.port.onmessage = function (e) { self._push(e.data.frame, e.data.samples); };
      var mute = ctx.createGain();
      mute.gain.value = 0;
      src.connect(self.node);
      self.node.connect(mute).connect(ctx.destination);  // keeps the worklet running; silent
      return ctx.state === 'suspended' ? ctx.resume() : null;
    }).then(function () { return self; });
  };
  Capture.prototype._push = function (frame, samples) {
    this.chunks.push({ start: frame, data: samples });
    this.total = frame + samples.length;
    var keepFrom = this.total - KEEP_S * this.rate;
    while (this.chunks.length && this.chunks[0].start + this.chunks[0].data.length < keepFrom) this.chunks.shift();
    if (this.onlevel) {
      var s = 0;
      for (var i = 0; i < samples.length; i++) s += samples[i] * samples[i];
      this.onlevel(10 * Math.log10(s / samples.length + 1e-12));
    }
  };
  /* The audio-clock frame holding sound captured at page time perfMs (performance.now() units). */
  Capture.prototype.frameAt = function (perfMs) {
    var ctx = this.ctx, t = null;
    var ts = ctx.getOutputTimestamp ? ctx.getOutputTimestamp() : null;
    if (ts && ts.performanceTime > 0) {
      t = ts.contextTime + (perfMs - ts.performanceTime) / 1000 + (ctx.outputLatency || ctx.baseLatency || 0) + this.inputLatency;
    }
    var fallback = ctx.currentTime + (ctx.baseLatency || 0) + this.inputLatency - (performance.now() - perfMs) / 1000;
    if (t == null || Math.abs(t - fallback) > 0.5) t = fallback;  // a clock we can't trust: use the simpler estimate
    return Math.round(t * this.rate);
  };
  Capture.prototype.waitFor = function (frame) {
    var self = this, t0 = performance.now();
    return new Promise(function (resolve) {
      (function poll() {
        if (self.total >= frame || performance.now() - t0 > 1500) resolve();
        else setTimeout(poll, 20);
      })();
    });
  };
  Capture.prototype.extract = function (from, to) {
    var out = new Float32Array(Math.max(0, to - from));
    this.chunks.forEach(function (c) {
      var a = Math.max(from, c.start), b = Math.min(to, c.start + c.data.length);
      if (b > a) out.set(c.data.subarray(a - c.start, b - c.start), a - from);
    });
    return out;
  };
  /* A 16 kHz WAV of [fromFrame, toFrame). */
  Capture.prototype.clip = function (fromFrame, toFrame) {
    var self = this;
    return this.waitFor(toFrame).then(function () { return toRate(self.extract(fromFrame, toFrame), self.rate, CLIP_RATE); })
      .then(function (pcm) { return wavBlob(pcm, CLIP_RATE); });
  };
  Capture.prototype.stop = function () {
    if (this.stream) this.stream.getTracks().forEach(function (t) { t.stop(); });
    if (this.ctx) this.ctx.close();
    this.stream = this.ctx = this.node = null;
    this.chunks = [];
  };

  function toRate(samples, from, to) {
    if (from === to || !samples.length) return Promise.resolve(samples);
    var n = Math.max(1, Math.round(samples.length * to / from));
    var off = new OfflineAudioContext(1, n, to);
    var buf = off.createBuffer(1, samples.length, from);
    buf.copyToChannel(samples, 0);
    var src = off.createBufferSource();
    src.buffer = buf;
    src.connect(off.destination);
    src.start();
    return off.startRendering().then(function (r) { return r.getChannelData(0); });
  }

  function wavBlob(samples, rate) {
    var buf = new ArrayBuffer(44 + samples.length * 2), v = new DataView(buf);
    function str(o, s) { for (var i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); }
    str(0, 'RIFF'); v.setUint32(4, 36 + samples.length * 2, true); str(8, 'WAVE'); str(12, 'fmt ');
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, rate, true);
    v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); str(36, 'data');
    v.setUint32(40, samples.length * 2, true);
    for (var i = 0; i < samples.length; i++) {
      var s = Math.max(-1, Math.min(1, samples[i]));
      v.setInt16(44 + i * 2, s < 0 ? s * 32768 : s * 32767, true);
    }
    return new Blob([buf], { type: 'audio/wav' });
  }

  /* Show a picture and resolve with its onset in page time: the picture is decoded first, then
     revealed, and the onset is taken at the second animation frame, when it has been painted. */
  function reveal(img, url) {
    img.hidden = true;
    img.src = url;
    var ready = img.decode ? img.decode().catch(function () {}) : new Promise(function (r) { img.onload = r; img.onerror = r; });
    return ready.then(function () {
      return new Promise(function (resolve) {
        img.hidden = false;
        requestAnimationFrame(function () { requestAnimationFrame(function () { resolve(performance.now()); }); });
      });
    });
  }

  // --- scoring requests -----------------------------------------------------------------------
  function scoreClip(blob, meta) {
    var fd = new FormData();
    fd.append('audio', blob, 'clip.wav');
    fd.append('target', meta.target);
    fd.append('lang', meta.lang);
    fd.append('picture_onset_ms', String(meta.onsetMs));
    fd.append('time_limit_s', String(meta.limitS));
    if (meta.setId) { fd.append('set_id', meta.setId); fd.append('item', String(meta.index)); }
    if (meta.alternates && meta.alternates.length) fd.append('alternates', JSON.stringify(meta.alternates));
    fd.append('second_rater', meta.secondRater ? 'true' : 'false');
    var attempt = 0;
    function go() {
      return T.api('/api/assess/naming', { method: 'POST', body: fd }).catch(function (e) {
        // Network drops (no status) and 5xx retry with backoff; limits and bad input don't.
        if (attempt < 3 && (!e.status || e.status >= 500) && e.status !== 503) {
          attempt++;
          return new Promise(function (r) { setTimeout(r, 600 * Math.pow(2, attempt)); }).then(go);
        }
        throw e;
      });
    }
    return go();
  }

  // --- measures (same definitions as metalesionlab/assessment.py) -------------------------------
  function pct(values, q) {
    if (!values.length) return null;
    var a = values.slice().sort(function (x, y) { return x - y; }), pos = (a.length - 1) * q / 100;
    var lo = Math.floor(pos), hi = Math.ceil(pos);
    return a[lo] + (a[hi] - a[lo]) * (pos - lo);
  }
  function finalCode(it) { return T.normCode(it.reviewer || it.code); }
  function finalLatency(it) {
    return it.reviewer_latency_ms != null ? +it.reviewer_latency_ms : (it.latency_ms == null ? null : it.latency_ms);
  }
  function summarize(items) {
    var scored = items.filter(function (it) { return !it.practice && it.status === 'done' && finalCode(it); });
    var counts = {};
    scored.forEach(function (it) { var c = finalCode(it); counts[c] = (counts[c] || 0) + 1; });
    var lat = scored.filter(function (it) { return finalCode(it) === 'Correct' && finalLatency(it) != null; }).map(finalLatency);
    var n = scored.length, correct = counts.Correct || 0;
    function r(v) { return v == null ? null : Math.round(v); }
    return {
      n: n, correct: correct, accuracy_pct: n ? Math.round(1000 * correct / n) / 10 : null, counts: counts,
      latency_n: lat.length, latency_median_ms: r(pct(lat, 50)), latency_q1_ms: r(pct(lat, 25)), latency_q3_ms: r(pct(lat, 75)),
      timeouts: scored.filter(function (it) { return it.timeout; }).map(function (it) { return it.target; }),
      flagged: scored.filter(function (it) { return (it.flags || []).length; }).map(function (it) { return it.target; })
    };
  }
  function seconds(ms, digits) { return ms == null ? '–' : (ms / 1000).toFixed(digits == null ? 2 : digits) + ' s'; }

  // --- IndexedDB: sessions and private sets, in this browser only --------------------------------
  var DB_NAME = 'tippa-lingua-assess', memory = { sessions: {}, sets: {} }, dbp = null;
  function db() {
    if (dbp) return dbp;
    dbp = new Promise(function (resolve) {
      try {
        var req = indexedDB.open(DB_NAME, 1);
        req.onupgradeneeded = function () {
          var d = req.result;
          if (!d.objectStoreNames.contains('sessions')) d.createObjectStore('sessions', { keyPath: 'id' }).createIndex('speaker', 'speaker');
          if (!d.objectStoreNames.contains('sets')) d.createObjectStore('sets', { keyPath: 'id' });
        };
        req.onsuccess = function () { resolve(req.result); };
        req.onerror = function () { resolve(null); };
      } catch (e) { resolve(null); }
    });
    return dbp;
  }
  function tx(store, mode, fn) {
    return db().then(function (d) {
      if (!d) return fn(null);
      return new Promise(function (resolve, reject) {
        var t = d.transaction(store, mode), s = t.objectStore(store), out = fn(s);
        t.oncomplete = function () { resolve(out && out.result !== undefined ? out.result : out); };
        t.onerror = function () { reject(t.error); };
        t.onabort = function () { reject(t.error || new Error('Storage was refused (the browser may be out of space).')); };
      });
    });
  }
  var store = {
    persistent: function () { return db().then(function (d) { return !!d; }); },
    put: function (name, obj) {
      return tx(name, 'readwrite', function (s) { if (!s) { memory[name][obj.id] = obj; return obj; } s.put(obj); return obj; });
    },
    all: function (name) {
      return tx(name, 'readonly', function (s) {
        if (!s) return Object.keys(memory[name]).map(function (k) { return memory[name][k]; });
        return s.getAll();
      });
    },
    get: function (name, id) { return tx(name, 'readonly', function (s) { return s ? s.get(id) : memory[name][id]; }); },
    del: function (name, id) { return tx(name, 'readwrite', function (s) { if (!s) delete memory[name][id]; else s.delete(id); return true; }); }
  };

  // --- bring your own test: ZIP or folder of pictures plus a CSV -------------------------------------
  function readZip(file) {
    return file.arrayBuffer().then(function (buf) {
      var v = new DataView(buf), bytes = new Uint8Array(buf), eocd = -1;
      for (var i = buf.byteLength - 22; i >= Math.max(0, buf.byteLength - 65557); i--) {
        if (v.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
      }
      if (eocd < 0) throw new Error('That file isn\'t a ZIP archive.');
      var count = v.getUint16(eocd + 10, true), p = v.getUint32(eocd + 16, true), utf8 = new TextDecoder();
      var jobs = [];
      for (var k = 0; k < count; k++) {
        if (v.getUint32(p, true) !== 0x02014b50) throw new Error('The ZIP archive is damaged or uses ZIP64, which isn\'t supported.');
        var method = v.getUint16(p + 10, true), size = v.getUint32(p + 20, true), nameLen = v.getUint16(p + 28, true);
        var extra = v.getUint16(p + 30, true), comment = v.getUint16(p + 32, true), local = v.getUint32(p + 42, true);
        var name = utf8.decode(bytes.subarray(p + 46, p + 46 + nameLen));
        p += 46 + nameLen + extra + comment;
        if (/\/$/.test(name) || /(^|\/)(__MACOSX|\.)/.test(name)) continue;
        var start = local + 30 + v.getUint16(local + 26, true) + v.getUint16(local + 28, true);
        var data = bytes.slice(start, start + size);
        jobs.push((function (name, method, data) {
          if (method === 0) return Promise.resolve({ name: name, blob: new Blob([data]) });
          if (method !== 8) return Promise.resolve(null);
          if (!window.DecompressionStream) throw new Error('This browser can\'t unpack ZIP files; choose the folder instead.');
          var stream = new Blob([data]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
          return new Response(stream).blob().then(function (b) { return { name: name, blob: b }; });
        })(name, method, data));
      }
      return Promise.all(jobs).then(function (list) { return list.filter(Boolean); });
    });
  }

  function parseCSV(text) {
    text = text.replace(/^\ufeff/, '');
    var first = text.split(/\r?\n/)[0] || '';
    var sep = (first.match(/;/g) || []).length > (first.match(/,/g) || []).length ? ';' : ',';  // Excel in many locales
    var rows = [], row = [], cell = '', q = false;
    for (var i = 0; i < text.length; i++) {
      var c = text[i];
      if (q) {
        if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; } else if (c === '"') q = false; else cell += c;
      } else if (c === '"') q = true;
      else if (c === sep) { row.push(cell); cell = ''; }
      else if (c === '\n' || c === '\r') {
        if (c === '\r' && text[i + 1] === '\n') i++;
        row.push(cell); cell = '';
        if (row.some(function (x) { return x.trim(); })) rows.push(row);
        row = [];
      } else cell += c;
    }
    row.push(cell);
    if (row.some(function (x) { return x.trim(); })) rows.push(row);
    return rows;
  }

  var IMAGE_RE = /\.(png|jpe?g|webp|gif)$/i;
  function base(name) { return String(name).split('/').pop().toLowerCase(); }
  function truthy(s) { return /^(1|y|yes|true|x|practice|p)$/i.test(String(s || '').trim()); }

  /* files: [{name, blob}] from a ZIP or a folder. Returns {items, problems, csvName}. */
  function buildTest(files) {
    var csv = files.filter(function (f) { return /\.csv$/i.test(f.name); }).sort(function (a, b) { return a.name.length - b.name.length; })[0];
    if (!csv) return Promise.reject(new Error('Add a CSV with the columns file, target, alternates and practice (see the help).'));
    var images = {};
    files.forEach(function (f) { if (IMAGE_RE.test(f.name)) images[base(f.name)] = f; });
    return csv.blob.text().then(function (text) {
      var rows = parseCSV(text);
      if (!rows.length) throw new Error('The CSV is empty.');
      var head = rows[0].map(function (x) { return x.trim().toLowerCase(); });
      var col = function (names) { for (var i = 0; i < names.length; i++) { var k = head.indexOf(names[i]); if (k >= 0) return k; } return -1; };
      var cFile = col(['file', 'image', 'picture', 'filename']), cTarget = col(['target', 'word', 'name']);
      var cAlt = col(['alternates', 'alternatives', 'accepted', 'alternate']), cPrac = col(['practice', 'practise']);
      if (cFile < 0 || cTarget < 0) throw new Error('The CSV needs a header row with at least "file" and "target".');
      var items = [], problems = [];
      rows.slice(1).forEach(function (r, k) {
        var file = (r[cFile] || '').trim(), target = (r[cTarget] || '').trim().toLowerCase();
        if (!file && !target) return;
        if (!target) { problems.push('Row ' + (k + 2) + ': no target word.'); return; }
        var img = images[base(file)];
        if (!img) { problems.push('Row ' + (k + 2) + ': picture "' + file + '" wasn\'t found.'); return; }
        var alts = cAlt >= 0 ? String(r[cAlt] || '').split(/[;|]/).map(function (a) { return a.trim().toLowerCase(); }).filter(Boolean) : [];
        items.push({ target: target, alternates: alts, practice: cPrac >= 0 && truthy(r[cPrac]), file: base(file), image: img.blob });
      });
      if (!items.length) throw new Error('No usable rows: ' + (problems[0] || 'check the CSV.'));
      return { items: items, problems: problems, csvName: csv.name };
    });
  }

  // --- small SVG charts ------------------------------------------------------------------------
  var NS = 'http://www.w3.org/2000/svg';
  function svg(tag, attrs, kids) {
    var el = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) el.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { if (c) el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return el;
  }
  function niceStep(max, ticks) {
    var raw = max / ticks, mag = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / mag;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * mag;
  }
  function tooltip(box) {
    var tip = box.querySelector('.chart-tip');
    if (!tip) { tip = h('div', { class: 'chart-tip', role: 'status', hidden: true }); box.appendChild(tip); }
    return {
      show: function (html, x, y) { tip.innerHTML = html; tip.hidden = false; tip.style.left = Math.min(x, box.clientWidth - 170) + 'px'; tip.style.top = Math.max(0, y - 46) + 'px'; },
      hide: function () { tip.hidden = true; }
    };
  }

  /* Latency per item: one bar per scored item, colored by final code; × marks no latency. */
  function latencyChart(box, items, limitS) {
    box.innerHTML = '';
    box.classList.add('chart');
    var list = items.filter(function (it) { return !it.practice && it.status === 'done'; });
    if (!list.length) { box.appendChild(h('p', { class: 'small muted', text: 'No scored items yet.' })); return; }
    var W = Math.max(320, box.clientWidth || 640), H = 200, L = 40, R = 8, Tp = 10, B = 26;
    var vals = list.map(finalLatency);
    var max = Math.max.apply(null, vals.filter(function (v) { return v != null; }).concat([1000])) * 1.1;
    var step = niceStep(max, 4), top = Math.ceil(max / step) * step;
    var plotW = W - L - R, plotH = H - Tp - B, bw = plotW / list.length;
    var s = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, width: '100%', role: 'img',
      'aria-label': 'Naming latency per item, in seconds; ' + list.length + ' items. The table below lists every value.' });
    for (var t = 0; t <= top + 1e-9; t += step) {
      var y = Tp + plotH - plotH * t / top;
      s.appendChild(svg('line', { x1: L, x2: W - R, y1: y, y2: y, class: 'grid' }));
      s.appendChild(svg('text', { x: L - 6, y: y + 4, 'text-anchor': 'end', class: 'tick' }, [(t / 1000).toFixed(step < 1000 ? 1 : 0) + ' s']));
    }
    var tip = tooltip(box);
    list.forEach(function (it, k) {
      var v = vals[k], code = finalCode(it), color = T.codeInfo(code).color, x = L + k * bw;
      var g = svg('g', { class: 'mark', tabindex: '0' });
      var label = '#' + (it.n || k + 1) + ' ' + it.target + ': ' + T.codeInfo(code).label + ', ' + (v == null ? 'no latency' : seconds(v));
      g.setAttribute('aria-label', label);
      if (v == null) {
        g.appendChild(svg('text', { x: x + bw / 2, y: Tp + plotH - 3, 'text-anchor': 'middle', class: 'miss', fill: color }, ['×']));
      } else {
        var bh = Math.max(2, plotH * v / top), bwid = Math.max(2, Math.min(28, bw - 2));
        g.appendChild(svg('path', { d: roundTop(x + (bw - bwid) / 2, Tp + plotH - bh, bwid, bh, Math.min(4, bwid / 2)), fill: color }));
      }
      g.appendChild(svg('rect', { x: x, y: Tp, width: bw, height: plotH, fill: 'transparent' }));  // hit area
      var showTip = function (ev) {
        var r = box.getBoundingClientRect();
        tip.show('<b>' + T.esc(it.target) + '</b> · ' + T.esc(T.codeInfo(code).label) + '<br>' + (v == null ? 'no latency' : seconds(v)) +
          (it.timeout ? ' · time limit' : ''), (ev.clientX || r.left + x) - r.left + 8, (ev.clientY || r.top + Tp) - r.top);
      };
      g.addEventListener('mousemove', showTip);
      g.addEventListener('focus', showTip);
      g.addEventListener('mouseleave', tip.hide);
      g.addEventListener('blur', tip.hide);
      s.appendChild(g);
      if (list.length <= 30 || (k + 1) % 5 === 0) {
        s.appendChild(svg('text', { x: x + bw / 2, y: H - B + 16, 'text-anchor': 'middle', class: 'tick' }, [String(it.n || k + 1)]));
      }
    });
    s.appendChild(svg('line', { x1: L, x2: W - R, y1: Tp + plotH, y2: Tp + plotH, class: 'axis' }));
    box.appendChild(s);
    var used = T.ORDER.filter(function (c) { return list.some(function (it) { return finalCode(it) === c; }); });
    var leg = T.legend(used);
    leg.appendChild(h('span', { class: 'muted', text: '× no response (limit ' + limitS + ' s)' }));
    box.appendChild(leg);
  }
  function roundTop(x, y, w, hgt, r) {
    return 'M' + x + ',' + (y + hgt) + 'V' + (y + r) + 'Q' + x + ',' + y + ' ' + (x + r) + ',' + y + 'H' + (x + w - r) +
      'Q' + (x + w) + ',' + y + ' ' + (x + w) + ',' + (y + r) + 'V' + (y + hgt) + 'Z';
  }

  /* One measure across sessions: points joined by a line, nothing extrapolated. */
  function trendChart(box, points, opts) {
    box.innerHTML = '';
    box.classList.add('chart');
    if (!points.length) { box.appendChild(h('p', { class: 'small muted', text: 'No sessions yet.' })); return; }
    var W = Math.max(280, box.clientWidth || 420), H = 170, L = 46, R = 14, Tp = 12, B = 28;
    var vals = points.map(function (p) { return p.value; }).filter(function (v) { return v != null; });
    var lo = opts.min != null ? opts.min : 0, hi = opts.max != null ? opts.max : Math.max.apply(null, vals.concat([1])) * 1.15;
    var step = niceStep(hi - lo, 4); hi = lo + Math.ceil((hi - lo) / step) * step;
    var plotW = W - L - R, plotH = H - Tp - B;
    var xAt = function (k) { return L + (points.length === 1 ? plotW / 2 : plotW * k / (points.length - 1)); };
    var yAt = function (v) { return Tp + plotH - plotH * (v - lo) / (hi - lo); };
    var s = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, width: '100%', role: 'img', 'aria-label': opts.label + ' across ' + points.length + ' sessions; the sessions table lists every value.' });
    for (var t = lo; t <= hi + 1e-9; t += step) {
      s.appendChild(svg('line', { x1: L, x2: W - R, y1: yAt(t), y2: yAt(t), class: 'grid' }));
      s.appendChild(svg('text', { x: L - 6, y: yAt(t) + 4, 'text-anchor': 'end', class: 'tick' }, [opts.fmt(t)]));
    }
    s.appendChild(svg('line', { x1: L, x2: W - R, y1: Tp + plotH, y2: Tp + plotH, class: 'axis' }));
    var d = '', tip = tooltip(box);
    points.forEach(function (p, k) { if (p.value != null) d += (d ? 'L' : 'M') + xAt(k) + ',' + yAt(p.value); });
    if (d) s.appendChild(svg('path', { d: d, class: 'trend-line' }));
    points.forEach(function (p, k) {
      if (p.value == null) return;
      var g = svg('g', { class: 'mark', tabindex: '0', 'aria-label': p.label + ': ' + opts.fmt(p.value) });
      g.appendChild(svg('circle', { cx: xAt(k), cy: yAt(p.value), r: 12, fill: 'transparent' }));
      g.appendChild(svg('circle', { cx: xAt(k), cy: yAt(p.value), r: 4.5, class: 'trend-dot' }));
      var showTip = function () { tip.show('<b>' + T.esc(p.label) + '</b><br>' + T.esc(opts.fmt(p.value, true)) + (p.note ? '<br>' + T.esc(p.note) : ''), xAt(k) * box.clientWidth / W, yAt(p.value) * box.clientWidth / W); };
      g.addEventListener('mouseenter', showTip);
      g.addEventListener('focus', showTip);
      g.addEventListener('mouseleave', tip.hide);
      g.addEventListener('blur', tip.hide);
      s.appendChild(g);
      if (points.length <= 8 || k === 0 || k === points.length - 1) {
        s.appendChild(svg('text', { x: xAt(k), y: H - 8, 'text-anchor': k === 0 && points.length > 1 ? 'start' : k === points.length - 1 && points.length > 1 ? 'end' : 'middle', class: 'tick' }, [p.short]));
      }
    });
    box.appendChild(s);
  }

  /* Where one score sits beside a reference range (5th to 95th percentile), on a 0..max scale. */
  function rangeStrip(box, value, range, max, fmt) {
    box.innerHTML = '';
    var W = 320, H = 54, L = 10, R = 10;
    var x = function (v) { return L + (W - L - R) * Math.max(0, Math.min(1, v / max)); };
    var s = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, width: '100%', role: 'img',
      'aria-label': 'Your result ' + fmt(value) + '; reference range ' + fmt(range[0]) + ' to ' + fmt(range[1]) });
    s.appendChild(svg('line', { x1: L, x2: W - R, y1: 26, y2: 26, class: 'axis' }));
    s.appendChild(svg('rect', { x: x(range[0]), y: 18, width: Math.max(3, x(range[1]) - x(range[0])), height: 16, rx: 4, class: 'range-band' }));
    s.appendChild(svg('circle', { cx: x(value), cy: 26, r: 7, class: 'range-dot' }));
    s.appendChild(svg('text', { x: L, y: 50, class: 'tick' }, [fmt(0)]));
    s.appendChild(svg('text', { x: W - R, y: 50, 'text-anchor': 'end', class: 'tick' }, [fmt(max)]));
    s.appendChild(svg('text', { x: x(value), y: 11, 'text-anchor': 'middle', class: 'tick strong' }, ['you']));
    box.appendChild(s);
  }

  function download(name, blob) {
    var a = h('a', { href: URL.createObjectURL(blob), download: name });
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
  }
  function uid(prefix) {
    var a = new Uint8Array(6);
    crypto.getRandomValues(a);
    return prefix + Array.prototype.map.call(a, function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
  }

  window.TLA = {
    LEAD_IN_MS: LEAD_IN_MS, Capture: Capture, reveal: reveal, scoreClip: scoreClip, summarize: summarize, pct: pct,
    finalCode: finalCode, finalLatency: finalLatency, seconds: seconds, store: store, readZip: readZip, parseCSV: parseCSV,
    buildTest: buildTest, IMAGE_RE: IMAGE_RE, latencyChart: latencyChart, trendChart: trendChart, rangeStrip: rangeStrip,
    download: download, uid: uid
  };
})();
