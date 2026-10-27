/* Ask Socrates: a short dialogue with an AI playing Socrates. The browser keeps the dialogue and sends it
   with each turn; the server streams the agent's steps as JSON lines (start, guard, thinking, tool_call,
   tool_result, checking, answer, done or error). Optional context from /draw arrives in the URL. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var MAX_TURNS = 8;
  var GUTENBERG = { republic: 1497, cratylus: 1616, phaedrus: 1636, meno: 1643 };
  var EXPERIMENTS = { forms: 'Forms', damage: 'damage', bird: 'name-a-bird', cave: 'Cave', cratylus: 'bouba/kiki' };
  var S = { history: [], busy: false, status: null, context: null, lastTurn: null };
  function $(id) { return document.getElementById(id); }

  // --- links and labels --------------------------------------------------------------------
  function passageHref(id) {
    var m = /^(republic|cratylus|phaedrus|meno)-/.exec(String(id || '').trim().toLowerCase());
    return m ? 'https://www.gutenberg.org/ebooks/' + GUTENBERG[m[1]] : null;
  }
  function passageLabel(id) {
    var m = /^(republic|cratylus|phaedrus|meno)-(\d+[a-e]?)/.exec(String(id || '').trim().toLowerCase());
    return m ? m[1].charAt(0).toUpperCase() + m[1].slice(1) + ' ' + m[2] : 'Plato';
  }
  function experimentKey(arg) {
    var k = String(arg || '').trim().toLowerCase().replace(/^name\s*[:=]\s*/, '').split(/[\s,]/)[0];
    return EXPERIMENTS[k] ? k : null;
  }
  function cite(tool, arg) {
    arg = String(arg || '').trim().replace(/^(concept|name|topic)\s*[:=]\s*/i, '');
    switch (tool) {
      case 'plato_stats': return { href: '/plato#everything', label: 'Plato’s Chair' + (arg ? ' · ' + arg : '') };
      case 'plato_variety': return { href: '/plato#variety', label: 'Any kind?' + (arg ? ' · ' + arg : '') };
      case 'glimmer_inside': return { href: '/plato#inside', label: 'Inside Glimmer' + (arg ? ' · ' + arg : '') };
      case 'plato_experiment':
        var k = experimentKey(arg);
        return { href: k ? '/plato/' + k : '/plato', label: k ? 'The ' + EXPERIMENTS[k] + ' experiment' : 'Plato experiments' };
      case 'plato_passage': return { href: passageHref(arg), label: passageLabel(arg), external: true };
      case 'your_drawing': return { href: '/draw', label: 'Your drawing' };
    }
    return { href: null, label: tool };
  }
  function safeHref(href) {
    href = String(href || '');
    if (/^\/(plato|draw|socrates|ask|lab|challenge)(\/[a-z]+)?([?#][^\s"'<>]*)?$/.test(href)) return href;
    if (/^https:\/\/www\.gutenberg\.org\/ebooks\/\d+$/.test(href)) return href;
    return null;
  }

  // --- answer text: a small, safe subset of Markdown, with citation chips ---------------------
  var CITE = /\[(?:source:\s*)?(plato_stats|plato_variety|glimmer_inside|plato_experiment|plato_passage|your_drawing)(?:\s*[:,]\s*([^\]]*))?\]([.,;:!?)]*)/g;
  function inline(text) {
    var out = T.esc(text);
    out = out.replace(CITE, function (_, tool, arg, punct) {
      var c = cite(tool, (arg || '').replace(/&#39;|&quot;/g, ''));
      var href = safeHref(c.href);
      var chip = href ? '<a class="so-cite" href="' + T.esc(href) + '"' + (c.external ? ' target="_blank" rel="noopener"' : '') +
        ' title="Source: ' + tool + '">' + T.esc(c.label) + '</a>' : '<span class="so-cite">' + T.esc(c.label) + '</span>';
      return '<span class="so-cite-wrap">' + chip + (punct || '') + '</span>';
    });
    out = out.replace(/(“|&quot;)([^”<]{3,600}?)(”|&quot;)/g, '<span class="so-quote">“$2”</span>');
    out = out.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
    out = out.replace(/(^|[\s(])\*([^*\s][^*]*?)\*(?=[\s.,;:!?)]|$)/g, '$1<i>$2</i>');
    return out;
  }
  function renderText(text) {
    var box = h('div', { class: 'so-text' });
    String(text || '').replace(/\r/g, '').split(/\n\s*\n/).forEach(function (block) {
      var lines = block.split('\n').filter(function (l) { return l.trim(); });
      if (!lines.length) return;
      var bullet = /^\s*(?:[-*•]|\d+[.)])\s+/;
      if (lines.every(function (l) { return bullet.test(l); })) {
        var list = h(/^\s*\d/.test(lines[0]) ? 'ol' : 'ul');
        lines.forEach(function (l) { list.appendChild(h('li', { html: inline(l.replace(bullet, '')) })); });
        box.appendChild(list);
      } else if (lines.every(function (l) { return /^\s*>/.test(l); })) {
        box.appendChild(h('blockquote', { html: lines.map(function (l) { return inline(l.replace(/^\s*>\s?/, '')); }).join('<br>') }));
      } else {
        box.appendChild(h('p', { html: lines.map(function (l) { return inline(l.replace(/^#+\s*/, '')); }).join('<br>') }));
      }
    });
    return box;
  }
  function money(usd) {
    if (!usd) return '$0';
    return usd < 0.001 ? '<$0.001' : '$' + usd.toFixed(usd < 0.1 ? 3 : 2);
  }

  // --- what Socrates is doing, in words -----------------------------------------------------
  function stepLabel(name, args) {
    args = args || {};
    var c = args.concept ? String(args.concept) : '';
    switch (name) {
      case 'plato_stats': return 'Socrates checks the ' + (c ? c + ' ' : 'chair ') + 'results' + (c ? '' : ' for all 35 things');
      case 'plato_variety': return 'Socrates checks what happens when you ask for variety' + (c ? ' (' + c + ')' : '');
      case 'glimmer_inside': return 'Socrates looks inside Muse Glimmer' + (c ? ' at the ' + c : '');
      case 'plato_experiment':
        var k = experimentKey(args.name);
        return 'Socrates checks the ' + (k ? EXPERIMENTS[k] + ' ' : '') + 'experiment' + (args.focus ? ' (' + args.focus + ')' : '');
      case 'plato_passage': return 'Socrates looks up Plato on “' + String(args.topic || '') + '”';
    }
    return 'Socrates runs ' + name;
  }

  // --- turns ------------------------------------------------------------------------------
  function speaker(who, extra) {
    return h('div', { class: 'so-speaker' }, [h('span', { class: 'so-name', text: who }), extra || null]);
  }
  function visitorTurn(text) {
    var li = h('li', { class: 'so-turn so-you' }, [speaker('You'), h('p', { class: 'so-said', text: text })]);
    $('thread').appendChild(li);
    return li;
  }

  function Reply() {
    this.state = h('span', { class: 'so-state' }, [h('span', { class: 'spinner', 'aria-hidden': 'true' }), ' thinking']);
    this.count = h('span', { text: 'Socrates is looking things up' });
    this.steps = h('ol', { class: 'so-steps' });
    this.trace = h('details', { class: 'so-trace', open: true }, [h('summary', null, [this.count]), this.steps]);
    this.trace.hidden = true;
    this.body = h('div', { class: 'so-body', 'aria-live': 'polite' });
    this.foot = h('div', { class: 'so-foot' });
    this.calls = {};
    this.n = 0;
    this.el = h('li', { class: 'so-turn so-socrates' }, [
      speaker('Socrates', h('span', { class: 'so-ai', text: 'AI', title: 'An AI (Muse Spark) playing Socrates' })),
      this.state, this.trace, this.body, this.foot
    ]);
    $('thread').appendChild(this.el);
  }
  Reply.prototype.add = function (li) {
    this.trace.hidden = false;
    this.steps.appendChild(li);
    this.n += 1;
  };
  Reply.prototype.finish = function (text) {
    this.state.innerHTML = '';
    this.state.hidden = !text;
    if (text) this.state.appendChild(document.createTextNode(text));
  };
  Reply.prototype.handle = function (ev) {
    if (ev.type === 'thinking') {
      this.add(h('li', { class: 'so-step so-plan', text: ev.text }));
    } else if (ev.type === 'tool_call') {
      var res = h('span', { class: 'so-step-res' }, [h('span', { class: 'spinner', 'aria-hidden': 'true' })]);
      var li = h('li', { class: 'so-step' }, [h('span', { class: 'so-step-what', text: stepLabel(ev.name, ev.args) + '…' }), res]);
      this.calls[ev.step] = { res: res, li: li, name: ev.name, args: ev.args };
      this.add(li);
      this.count.textContent = 'Socrates checks ' + this.n + ' source' + (this.n === 1 ? '' : 's');
    } else if (ev.type === 'tool_result') {
      var slot = this.calls[ev.step];
      if (!slot) return;
      slot.res.innerHTML = '';
      var failed = /^Error:/.test(ev.summary || '');
      slot.res.appendChild(h('span', { class: failed ? 'so-bad' : 'so-ok', text: failed ? '✕ ' : '✓ ' }));
      slot.res.appendChild(document.createTextNode(ev.summary || 'done'));
      var link = safeHref(ev.link);
      if (link) slot.res.appendChild(h('a', { href: link, target: /^https/.test(link) ? '_blank' : null, rel: /^https/.test(link) ? 'noopener' : null, text: 'open' }));
      var json = JSON.stringify(ev.result, null, 1);
      slot.li.appendChild(h('details', { class: 'so-data' }, [h('summary', { text: 'What the tool returned' }),
        h('pre', { text: json.length > 5000 ? json.slice(0, 5000) + '\n…' : json })]));
    } else if (ev.type === 'checking') {
      this.add(h('li', { class: 'so-step so-checkstep', text: ev.text }));
    } else if (ev.type === 'guard') {
      this.add(h('li', { class: 'so-step so-checkstep', text: ev.text }));
    } else if (ev.type === 'error') {
      this.failed = true;
      this.body.appendChild(h('p', { class: 'so-error', text: ev.message }));
      this.finish('');
    } else if (ev.type === 'answer') {
      this.answer(ev);
    }
  };
  Reply.prototype.answer = function (ev) {
    this.done = ev;
    this.finish('');
    if (this.n) { this.trace.open = false; this.count.textContent = 'Socrates checked ' + this.n + ' step' + (this.n === 1 ? '' : 's'); }
    var body = ev.body != null ? ev.body : ev.text;
    var question = ev.question_back || '';
    if (!body && !question) body = ev.text;
    this.body.innerHTML = '';
    this.body.className = 'so-body' + (ev.refused ? ' refused' : '');
    if (body) this.body.appendChild(renderText(body));
    if (question) {
      this.body.appendChild(h('div', { class: 'so-ask' }, [h('span', { class: 'so-ask-label', text: 'Socrates asks you' }),
        h('p', { html: inline(question) })]));
    }
    var c = ev.check || {};
    var foot = this.foot;
    foot.innerHTML = '';
    var src = h('div', { class: 'so-sources' });
    var seen = {};
    (ev.sources || []).forEach(function (s) {
      var passage = s.tool === 'plato_passage';
      var c2 = cite(s.tool, passage ? '' : s.args && (s.args.concept || s.args.name));
      var href = safeHref(s.href) || safeHref(c2.href);
      if (!href || seen[href]) return;
      seen[href] = 1;
      var ext = /^https/.test(href);
      src.appendChild(h('a', { href: href, target: ext ? '_blank' : null, rel: ext ? 'noopener' : null },
        [passage ? 'Plato’s text (Gutenberg)' : c2.label.split(' · ')[0], ext ? ' ↗' : ' →']));
    });
    if (S.context && /\[your_drawing\]/.test(ev.text || '') && !seen['/draw']) src.appendChild(h('a', { href: '/draw' }, ['Your drawing →']));
    if (src.childNodes.length) foot.appendChild(src);
    if (!ev.refused) {
      var nums = c.numbers || 0, quotes = c.quotes || 0;
      var good = !(c.unverified || []).length && !(c.banned_words || []).length && !(c.bad_quotes || []).length;
      var parts = [];
      if (good) {
        var what = [];
        if (nums) what.push(nums + ' number' + (nums === 1 ? '' : 's') + ' match the results');
        if (quotes) what.push(quotes + ' quotation' + (quotes === 1 ? '' : 's') + ' match Plato’s text');
        parts.push(h('b', { text: '✓ ' }), what.length ? 'Checked: ' + what.join('; ') + '.' : 'Nothing to check: no numbers or quotations.');
      } else {
        parts.push(h('b', { text: 'Check before you use this: ' }));
        if ((c.unverified || []).length) parts.push('these numbers weren’t found in the results: ' + c.unverified.join(', ') + '. ');
        if ((c.bad_quotes || []).length) parts.push('a quotation didn’t match the verified passages. ');
        if ((c.banned_words || []).length) parts.push('wording flagged: ' + c.banned_words.join(', ') + '.');
      }
      if (c.repaired) parts.push(' The first draft was corrected once.');
      foot.appendChild(h('p', { class: 'so-check ' + (good ? 'ok' : 'warn') }, parts));
    }
    var stats = ev.refused ? 'answered without calling the model · $0' :
      money(ev.cost_usd) + ' · ' + ev.tool_calls + ' tool call' + (ev.tool_calls === 1 ? '' : 's') + ' · ' +
      ev.model_calls + ' Muse Spark call' + (ev.model_calls === 1 ? '' : 's') + ' · ' + (ev.t || 0).toFixed(1) + ' s';
    foot.appendChild(h('span', { class: 'so-cost', text: stats }));
  };

  // --- the dialogue ---------------------------------------------------------------------------
  function turnsUsed() { return S.history.filter(function (x) { return x.role === 'visitor'; }).length; }
  function updateMeta() {
    var used = turnsUsed(), max = (S.status && S.status.max_turns) || MAX_TURNS;
    $('turns').textContent = used ? 'Turn ' + Math.min(used + (S.busy ? 0 : 1), max) + ' of ' + max : 'Up to ' + max + ' turns';
    var s = S.status;
    $('meta').textContent = s ? 'Muse Spark 1.3 · up to ' + s.max_tool_calls + ' tool calls a turn · ' + s.turns_left + ' turns left today' : '';
    var full = used >= max;
    $('msg').disabled = S.busy || full || !!(s && (!s.enabled || !s.budget_left || !s.turns_left));
    $('send').disabled = $('msg').disabled;
    $('send').textContent = S.busy ? 'Thinking…' : 'Send';
    $('msg').placeholder = full ? 'This dialogue has had its ' + max + ' turns. Start a new one.' :
      used ? 'Answer Socrates, or ask something else…' : 'Ask Socrates, or answer his question…';
    $('restart').disabled = S.busy || !used;
    $('share').disabled = S.busy || !S.lastTurn;
    $('empty').hidden = !!used || S.busy;
    Array.prototype.forEach.call(document.querySelectorAll('.so-starter'), function (b) { b.disabled = S.busy; });
  }

  function send(text) {
    text = String(text || '').trim();
    var max = (S.status && S.status.max_turns) || MAX_TURNS;
    if (!text || S.busy || turnsUsed() >= max) return;
    S.busy = true;
    $('msg').value = '';
    $('empty').hidden = true;
    var you = visitorTurn(text);
    var reply = new Reply();
    updateMeta();
    reply.el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    var body = { question: text, history: S.history.slice() };
    if (S.context) body.context = S.context;
    fetch('/api/socrates', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (res) {
        if (!res.ok) {
          return res.json().catch(function () { return {}; }).then(function (d) {
            var msg = d && d.detail;
            if (Array.isArray(msg)) msg = msg.map(function (x) { return x.msg; }).join('; ');
            reply.handle({ type: 'error', message: msg || ('Request failed (' + res.status + ')') });
          });
        }
        var reader = res.body.getReader(), dec = new TextDecoder(), buf = '';
        function line(l) {
          if (!l.trim()) return;
          try { reply.handle(JSON.parse(l)); } catch (e) { /* a broken line is skipped */ }
        }
        function pump() {
          return reader.read().then(function (r) {
            if (r.done) { line(buf); return; }
            buf += dec.decode(r.value, { stream: true });
            var i;
            while ((i = buf.indexOf('\n')) >= 0) { line(buf.slice(0, i)); buf = buf.slice(i + 1); }
            return pump();
          });
        }
        return pump();
      })
      .catch(function (e) { reply.handle({ type: 'error', message: 'The connection dropped (' + e.message + '). Try again.' }); })
      .then(function () {
        S.busy = false;
        var ev = reply.done;
        if (ev) {
          S.history.push({ role: 'visitor', text: text });
          S.history.push({ role: 'socrates', text: ev.text, tools: ev.tools_used || [] });
          S.lastTurn = { you: text, ev: ev };
        } else {
          you.remove();  // the message didn't go through; keep it in the box to try again
          if (!reply.failed) reply.el.remove();
          $('msg').value = text;
          reply.finish('');
        }
        updateMeta();
        refreshStatus();
        if (!$('msg').disabled) $('msg').focus({ preventScroll: true });
      });
  }

  function restart() {
    if (S.busy) return;
    S.history = [];
    S.lastTurn = null;
    $('thread').innerHTML = '';
    updateMeta();
    $('msg').focus();
  }

  // --- share: a short excerpt with a link --------------------------------------------------------
  function plain(text) {
    return String(text || '').replace(CITE, '$3').replace(/\*\*([^*]+)\*\*/g, '$1').replace(/\s+/g, ' ').trim();
  }
  function clip(text, n) {
    text = plain(text);
    if (text.length <= n) return text;
    var cut = text.slice(0, n), at = Math.max(cut.lastIndexOf('. '), cut.lastIndexOf('? '));
    return (at > n * 0.5 ? cut.slice(0, at + 1) : cut.replace(/\s+\S*$/, '') + '…');
  }
  function excerpt() {
    var t = S.lastTurn;
    if (!t) return '';
    var ev = t.ev, lines = ['I asked an AI playing Socrates: “' + clip(t.you, 140) + '”'];
    if (ev.body) lines.push('Socrates: ' + clip(ev.body, 260));
    if (ev.question_back) lines.push('And he asked me: “' + clip(ev.question_back, 200) + '”');
    lines.push(location.origin + '/socrates');
    return lines.join('\n');
  }
  function share() {
    var text = excerpt();
    if (!text) return;
    var done = function () { say('Copied an excerpt with a link. Paste it anywhere.'); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text) ? done() : say('Couldn’t copy; select the text yourself.'); });
    } else if (fallbackCopy(text)) {
      done();
    }
  }
  function fallbackCopy(text) {
    var ta = h('textarea', { class: 'sr-only', readonly: true });
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    ta.remove();
    return ok;
  }
  function say(msg) {
    var t = $('toast');
    t.textContent = msg;
    t.classList.add('on');
    clearTimeout(say.timer);
    say.timer = setTimeout(function () { t.classList.remove('on'); }, 3200);
  }

  // --- context from /draw -------------------------------------------------------------------------
  function readContext() {
    var p = new URLSearchParams(location.search);
    var concept = p.get('draw'), orig = parseFloat(p.get('originality'));
    if (!concept || !isFinite(orig)) return null;
    var ctx = { concept: concept.slice(0, 30), originality: Math.max(0, Math.min(100, orig)) };
    ['people_closer_to_muse', 'muse_closer', 'd_nearest_ai', 'd_nearest_human', 'n_people'].forEach(function (k) {
      var v = parseFloat(p.get(k));
      if (isFinite(v)) ctx[k] = v;
    });
    var looks = p.get('looks_like');
    if (looks) ctx.looks_like = looks.split(',').slice(0, 3).map(function (x) { return x.trim().slice(0, 24); });
    ctx.label = (p.get('label') || concept).slice(0, 30);
    return ctx;
  }
  function showContext() {
    var c = S.context;
    if (!c) { $('drawing').hidden = true; return; }
    var label = c.label || c.concept;
    $('drawing').hidden = false;
    document.querySelectorAll('[data-concept]').forEach(function (el) { el.textContent = label; });
    var n = c.n_people || 200, facts = 'More original than ' + Math.round(c.originality) + '% of ' + n + ' people’s drawings of a ' + label + '.';
    if (isFinite(c.d_nearest_ai) && isFinite(c.d_nearest_human)) {
      facts += ' Its closest match is ' + (c.d_nearest_ai < c.d_nearest_human ? 'one of Muse Image’s doodles.' : 'one of people’s drawings.');
    }
    $('drawing-facts').textContent = facts;
  }

  // --- status and start -----------------------------------------------------------------------------
  function refreshStatus() {
    return T.api('/api/socrates/status').then(function (s) {
      S.status = s;
      var why = !s.enabled ? 'Ask Socrates needs the Meta Model API, which isn’t set up on this server. Every other page works.'
        : !s.budget_left ? 'Socrates has used today’s budget for dialogues. Every page of the lab still works; he’ll be back tomorrow.'
        : !s.turns_left ? 'You’ve used today’s turns with Socrates on this demo. Every page of the lab still works.' : '';
      $('off').hidden = !why;
      $('off').textContent = why;
      $('tool-list').textContent = 'Tools: ' + s.tools.join(', ') + '. All read-only. Plato passages: Benjamin Jowett’s translation (1892), public domain, checked word for word against Project Gutenberg.';
      updateMeta();
      return s;
    }).catch(function () { return null; });
  }

  function init() {
    S.context = readContext();
    showContext();
    $('form').addEventListener('submit', function (e) { e.preventDefault(); send($('msg').value); });
    $('msg').addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send($('msg').value); }
    });
    $('restart').addEventListener('click', restart);
    $('share').addEventListener('click', share);
    $('drawing-drop').addEventListener('click', function () {
      S.context = null;
      showContext();
      var first = document.querySelector('.so-starter.mine');
      if (first) first.remove();
    });
    refreshStatus().then(function (s) {
      var box = $('starters');
      var list = ((s && s.starters) || []).slice();
      if (S.context) list.unshift({ text: 'What do you make of my ' + (S.context.label || S.context.concept) + '?', mine: true });
      list.forEach(function (q) {
        var text = typeof q === 'string' ? q : q.text;
        box.appendChild(h('button', { type: 'button', class: 'so-starter' + (q.mine ? ' mine' : ''), text: text,
          onclick: function () { send(text); } }));
      });
      var pre = T.param('q');
      if (pre) $('msg').value = pre.slice(0, 500);
      updateMeta();
    });
    updateMeta();
  }
  init();
})();
