/* Ask Socrates: a short dialogue with an AI playing Socrates. The browser keeps the dialogue and sends it
   with each turn; the server streams the agent's steps as JSON lines (start, guard, thinking, tool_call,
   tool_result, checking, answer, done or error). Optional context from /draw arrives in the URL.

   Two modes. "Ask him": the visitor asks, Socrates answers from the results and asks one question back.
   "Let him examine you": Socrates opens with a question written in advance ("What is a chair?"), tests each
   definition with one counterexample from the experiments, and after three to five exchanges ends in aporia
   with what held and what broke. Each mode keeps its own thread; ?mode=examine&concept=clock opens one. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var MAX_TURNS = 8, EXAMINE_MAX = 5;
  var GUTENBERG = { republic: 1497, cratylus: 1616, phaedrus: 1636, meno: 1643, theaetetus: 1726, apology: 1656, timaeus: 1572 };
  var ARISTOTLE = { metaphysics: ['Metaphysics', 'metaphysics'], ethics: ['Ethics', 'nicomachaen'] };  // Ross's translation at MIT
  var PASSAGE_ID = /^(republic|cratylus|phaedrus|meno|theaetetus|apology|timaeus|metaphysics|ethics)-(\d+[a-e](?:\d+)?)/;
  var EXPERIMENTS = { forms: 'Forms', damage: 'damage', bird: 'name-a-bird', cave: 'Cave', cratylus: 'bouba/kiki', lifespan: 'life-of-a-chair' };
  var CASES = { chair: '/plato#variety', clock: '/plato/forms', bird: '/plato/bird', game: '/plato/bird' };
  var FACE = '/static/img/socrates/socrates-';
  var S = {
    mode: 'ask', busy: false, status: null, context: null,
    ask: { history: [], lastTurn: null },
    examine: { concept: 'chair', history: [], lastTurn: null, over: false }
  };
  function $(id) { return document.getElementById(id); }
  function D() { return S[S.mode]; }
  function thread() { return $(S.mode === 'examine' ? 'thread-examine' : 'thread'); }
  function examineInfo() { return (S.status && S.status.examine) || { concepts: [], max_exchanges: EXAMINE_MAX }; }
  function conceptInfo(key) {
    return examineInfo().concepts.filter(function (c) { return c.key === key; })[0] || null;
  }

  // --- links and labels --------------------------------------------------------------------
  function passageHref(id) {
    var m = PASSAGE_ID.exec(String(id || '').trim().toLowerCase());
    if (!m) return null;
    if (ARISTOTLE[m[1]]) return 'https://classics.mit.edu/Aristotle/' + ARISTOTLE[m[1]][1] + '.html';
    return 'https://www.gutenberg.org/ebooks/' + GUTENBERG[m[1]];
  }
  function passageLabel(id) {
    var m = PASSAGE_ID.exec(String(id || '').trim().toLowerCase());
    if (!m) return 'Plato';
    if (ARISTOTLE[m[1]]) return 'Aristotle, ' + ARISTOTLE[m[1]][0] + ' ' + m[2];
    return m[1].charAt(0).toUpperCase() + m[1].slice(1) + ' ' + m[2];
  }
  function isAristotleHref(href) { return /^https:\/\/classics\.mit\.edu\/Aristotle\//.test(href); }
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
      case 'counterexamples':
        var c = String(arg || '').toLowerCase().replace(/s$/, '');
        return { href: CASES[c] || '/plato#variety', label: 'Hard cases' + (CASES[c] ? ' · ' + c : '') };
      case 'your_drawing': return { href: '/draw', label: 'Your drawing' };
    }
    return { href: null, label: tool };
  }
  function safeHref(href) {
    href = String(href || '');
    if (/^\/(plato|draw|socrates|ask|lab|challenge)(\/[a-z]+)?([?#][^\s"'<>]*)?$/.test(href)) return href;
    if (/^https:\/\/www\.gutenberg\.org\/ebooks\/\d+$/.test(href)) return href;
    if (/^https:\/\/classics\.mit\.edu\/Aristotle\/[a-z]+(\.\d+\.[ivx]+)?\.html$/.test(href)) return href;
    return null;
  }

  // --- answer text: a small, safe subset of Markdown, with citation chips ---------------------
  var CITE = /\[(?:source:\s*)?(plato_stats|plato_variety|glimmer_inside|plato_experiment|plato_passage|counterexamples|your_drawing)(?:\s*[:,]\s*([^\]]*))?\]([.,;:!?)]*)/g;
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
      case 'counterexamples': return 'Socrates gathers hard cases for a ' + (c || 'chair') + ' from the experiments';
    }
    return 'Socrates runs ' + name;
  }

  // --- turns ------------------------------------------------------------------------------
  function face(kind) {
    return h('img', { class: 'so-face', src: FACE + kind + '.webp', width: 40, height: 40, alt: '', loading: 'lazy' });
  }
  function speaker(who, extra, faceKind) {
    return h('div', { class: 'so-speaker' }, [faceKind ? face(faceKind) : null, h('span', { class: 'so-name', text: who }), extra || null]);
  }
  function aiBadge() { return h('span', { class: 'so-ai', text: 'AI', title: 'An AI (Muse Spark) playing Socrates' }); }
  function visitorTurn(text) {
    var li = h('li', { class: 'so-turn so-you' }, [speaker('You'), h('p', { class: 'so-said', text: text })]);
    thread().appendChild(li);
    return li;
  }
  // Socrates' opening question in the examination: written in advance, no model call.
  function openingTurn(info) {
    var li = h('li', { class: 'so-turn so-socrates so-opening' }, [
      speaker('Socrates', aiBadge(), 'questioning'),
      h('div', { class: 'so-body' }, [
        h('div', { class: 'so-ask' }, [h('span', { class: 'so-ask-label', text: 'Socrates asks you' }), h('p', { text: info.opening })])
      ]),
      h('div', { class: 'so-foot' }, [h('span', { class: 'so-cost', text: 'Written in advance · $0' })])
    ]);
    $('thread-examine').appendChild(li);
    return li;
  }

  function Reply() {
    this.state = h('span', { class: 'so-state' }, [h('span', { class: 'spinner', 'aria-hidden': 'true' }), S.mode === 'examine' ? ' weighing your definition' : ' thinking']);
    this.count = h('span', { text: 'Socrates is looking things up' });
    this.steps = h('ol', { class: 'so-steps' });
    this.trace = h('details', { class: 'so-trace', open: true }, [h('summary', null, [this.count]), this.steps]);
    this.trace.hidden = true;
    this.body = h('div', { class: 'so-body', 'aria-live': 'polite' });
    this.foot = h('div', { class: 'so-foot' });
    this.calls = {};
    this.n = 0;
    this.mode = S.mode;
    this.who = speaker('Socrates', aiBadge(), S.mode === 'examine' ? 'pointing' : 'neutral');
    this.el = h('li', { class: 'so-turn so-socrates' }, [this.who, this.state, this.trace, this.body, this.foot]);
    thread().appendChild(this.el);
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
    var ex = ev.examine || null, final = !!(ex && ex.final);
    if (final) { var img = this.who.querySelector('.so-face'); if (img) img.src = FACE + 'questioning.webp'; }
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
    if (final && !ev.refused) this.body.appendChild(summaryCard(ex));
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
        [passage ? (isAristotleHref(href) ? 'Aristotle’s text (MIT Classics)' : 'Plato’s text (Gutenberg)')
          : c2.label.split(' · ')[0], ext ? ' ↗' : ' →']));
    });
    if (S.context && /\[your_drawing\]/.test(ev.text || '') && !seen['/draw']) src.appendChild(h('a', { href: '/draw' }, ['Your drawing →']));
    if (src.childNodes.length && !final) foot.appendChild(src);
    if (!ev.refused) {
      var nums = c.numbers || 0, quotes = c.quotes || 0;
      var good = !(c.unverified || []).length && !(c.banned_words || []).length && !(c.bad_quotes || []).length;
      var parts = [];
      if (good) {
        var what = [];
        if (nums) what.push(nums + (nums === 1 ? ' number matches' : ' numbers match') + ' the results');
        if (quotes) what.push(quotes + (quotes === 1 ? ' quotation matches' : ' quotations match') + ' Plato’s text');
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

  // The end of an examination: what held, what broke, where to look, and what next.
  function summaryCard(ex) {
    var rows = h('dl', { class: 'so-verdict' });
    if (ex.held) { rows.appendChild(h('dt', { text: 'What held' })); rows.appendChild(h('dd', { html: inline(ex.held) })); }
    if (ex.broke) { rows.appendChild(h('dt', { class: 'broke', text: 'What broke' })); rows.appendChild(h('dd', { html: inline(ex.broke) })); }
    var link = ex.link && safeHref(ex.link.href);
    var next = h('div', { class: 'so-next' });
    if (link) next.appendChild(h('a', { class: 'btn btn-primary', href: link }, ['See the experiment: ' + ex.link.label + ' →']));
    examineInfo().concepts.forEach(function (c) {
      if (c.key === ex.concept) return;
      next.appendChild(h('button', { type: 'button', class: 'btn btn-ghost', onclick: function () { pickConcept(c.key, true); } }, ['Examine me on a ' + c.label]));
    });
    next.appendChild(h('button', { type: 'button', class: 'btn btn-ghost', onclick: function () { setMode('ask', true); } }, ['Ask him instead']));
    return h('section', { class: 'so-aporia', 'aria-label': 'Where the examination got to' }, [
      h('span', { class: 'so-ask-label', text: 'Aporia: where we got to' }),
      rows.childNodes.length ? rows : h('p', { text: 'We stopped without a summary; the dialogue above is what we found.' }),
      next
    ]);
  }

  // --- the dialogue ---------------------------------------------------------------------------
  function turnsUsed(d) { return (d || D()).history.filter(function (x) { return x.role === 'visitor'; }).length; }
  function maxTurns() {
    return S.mode === 'examine' ? (examineInfo().max_exchanges || EXAMINE_MAX) : ((S.status && S.status.max_turns) || MAX_TURNS);
  }
  function updateMeta() {
    var d = D(), used = turnsUsed(d), max = maxTurns(), ex = S.mode === 'examine';
    var info = ex ? conceptInfo(S.examine.concept) : null;
    if (ex) {
      $('turns').textContent = d.over ? 'Examination over after ' + used + ' exchange' + (used === 1 ? '' : 's')
        : 'Exchange ' + Math.min(used + (S.busy ? 0 : 1), max) + ' of up to ' + max;
    } else {
      $('turns').textContent = used ? 'Turn ' + Math.min(used + (S.busy ? 0 : 1), max) + ' of ' + max : 'Up to ' + max + ' turns';
    }
    var s = S.status;
    $('meta').textContent = s ? 'Muse Spark 1.3 · up to ' + s.max_tool_calls + ' tool calls a turn · ' + s.turns_left + ' turns left today' : '';
    var full = used >= max || (ex && d.over);
    $('msg').disabled = S.busy || full || !!(s && (!s.enabled || !s.budget_left || !s.turns_left)) || (ex && !info);
    $('send').disabled = $('msg').disabled;
    $('send').textContent = S.busy ? 'Thinking…' : 'Send';
    if (ex) {
      $('msg').placeholder = d.over ? 'The examination is over. Pick another thing above, or ask him instead.'
        : used ? 'Mend your definition, or defend it…' : 'In a sentence: what is a ' + S.examine.concept + '?';
    } else {
      $('msg').placeholder = full ? 'This dialogue has had its ' + max + ' turns. Start a new one.' :
        used ? 'Answer Socrates, or ask something else…' : 'Ask Socrates, or answer his question…';
    }
    $('msg').setAttribute('aria-label', ex ? 'Your definition, for Socrates to examine' : 'Your message to Socrates');
    $('restart').textContent = ex ? 'New examination' : 'New dialogue';
    $('restart').disabled = S.busy || !used;
    $('share').disabled = S.busy || !d.lastTurn;
    $('empty').hidden = ex || !!used || S.busy;
    $('examine-intro').hidden = !ex;
    $('thread').hidden = ex;
    $('thread-examine').hidden = !ex;
    Array.prototype.forEach.call(document.querySelectorAll('.so-starter, .so-concepts input, .so-modes input'), function (b) { b.disabled = S.busy; });
  }

  function send(text) {
    text = String(text || '').trim();
    var d = D(), mode = S.mode;
    if (!text || S.busy || turnsUsed(d) >= maxTurns() || (mode === 'examine' && d.over)) return;
    S.busy = true;
    $('msg').value = '';
    $('empty').hidden = true;
    var you = visitorTurn(text);
    var reply = new Reply();
    updateMeta();
    reply.el.scrollIntoView({ behavior: still() ? 'auto' : 'smooth', block: 'nearest' });
    var body = { question: text, history: d.history.slice() };
    if (S.context) body.context = S.context;
    if (mode === 'examine') { body.mode = 'examine'; body.concept = d.concept; }
    fetch('/api/socrates', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (res) {
        if (!res.ok) {
          return res.json().catch(function () { return {}; }).then(function (x) {
            var msg = x && x.detail;
            if (Array.isArray(msg)) msg = msg.map(function (y) { return y.msg; }).join('; ');
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
          d.history.push({ role: 'visitor', text: text });
          d.history.push({ role: 'socrates', text: ev.text, tools: ev.tools_used || [] });
          d.lastTurn = { you: text, ev: ev };
          if (mode === 'examine' && ev.examine && ev.examine.final) d.over = true;
        } else {
          you.remove();  // the message didn't go through; keep it in the box to try again
          if (!reply.failed) reply.el.remove();
          $('msg').value = text;
          reply.finish('');
        }
        updateMeta();
        refreshStatus();
        if (S.mode === mode && !$('msg').disabled) $('msg').focus({ preventScroll: true });
        else if (d.over) { var first = reply.el.querySelector('.so-next a, .so-next button'); if (first) first.focus({ preventScroll: true }); }
      });
  }

  function restart() {
    if (S.busy) return;
    var d = D();
    d.history = [];
    d.lastTurn = null;
    if (S.mode === 'examine') { d.over = false; $('thread-examine').innerHTML = ''; startExamination(); }
    else $('thread').innerHTML = '';
    updateMeta();
    $('msg').focus();
  }

  // --- modes ------------------------------------------------------------------------------------
  function still() { return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches; }
  function startExamination() {
    var info = conceptInfo(S.examine.concept);
    if (info && !$('thread-examine').childNodes.length) openingTurn(info);
  }
  function setMode(mode, focus) {
    if (S.busy) return;
    S.mode = mode === 'examine' ? 'examine' : 'ask';
    var radio = document.querySelector('.so-modes input[value="' + S.mode + '"]');
    if (radio) radio.checked = true;
    if (S.mode === 'examine') startExamination();
    updateMeta();
    syncUrl();
    if (focus) $('msg').focus({ preventScroll: false });
  }
  function pickConcept(key, focus) {
    if (S.busy || !conceptInfo(key)) return;
    var d = S.examine;
    var changed = key !== d.concept;
    d.concept = key;
    var radio = document.querySelector('.so-concepts input[value="' + key + '"]');
    if (radio) radio.checked = true;
    if (changed || d.over || S.mode !== 'examine') {
      if (changed || d.over) { d.history = []; d.lastTurn = null; d.over = false; $('thread-examine').innerHTML = ''; }
      S.mode = 'examine';
      var m = document.querySelector('.so-modes input[value="examine"]');
      if (m) m.checked = true;
    }
    startExamination();
    updateMeta();
    syncUrl();
    if (focus) {
      $('examine-intro').scrollIntoView({ behavior: still() ? 'auto' : 'smooth', block: 'start' });
      $('msg').focus({ preventScroll: true });
    }
  }
  function syncUrl() {
    try {
      var u = new URL(location.href);
      if (S.mode === 'examine') { u.searchParams.set('mode', 'examine'); u.searchParams.set('concept', S.examine.concept); }
      else { u.searchParams.delete('mode'); u.searchParams.delete('concept'); }
      history.replaceState(null, '', u.pathname + (u.search || '') + u.hash);
    } catch (e) { /* an old browser keeps its URL */ }
  }
  function buildConcepts() {
    var box = $('concepts');
    examineInfo().concepts.forEach(function (c) {
      box.appendChild(h('label', { class: 'so-concept' }, [
        h('input', { type: 'radio', name: 'concept', value: c.key, checked: c.key === S.examine.concept ? true : null,
          onchange: function () { pickConcept(c.key, false); } }),
        h('span', { text: 'a ' + c.label })
      ]));
    });
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
    var d = D(), t = d.lastTurn;
    if (!t) return '';
    var ev = t.ev, ex = S.mode === 'examine', lines;
    if (ex) {
      var info = conceptInfo(d.concept);
      lines = ['An AI playing Socrates examined me: “' + (info ? info.question : 'What is a chair?') + '”', 'I said: “' + clip(t.you, 140) + '”'];
      if (ev.body) lines.push('Socrates: ' + clip(ev.body, 260));
      if (ev.examine && ev.examine.broke) lines.push('What broke: ' + clip(ev.examine.broke, 160));
      lines.push(location.origin + '/socrates?mode=examine&concept=' + d.concept);
      return lines.join('\n');
    }
    lines = ['I asked an AI playing Socrates: “' + clip(t.you, 140) + '”'];
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
      $('tool-list').textContent = 'Tools: ' + s.tools.join(', ') + '. All read-only. Passages: Plato in Benjamin Jowett’s translation (1892) and Aristotle in W. D. Ross’s (1925, 1928), public domain, checked word for word against Project Gutenberg.';
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
    Array.prototype.forEach.call(document.querySelectorAll('.so-modes input'), function (r) {
      r.addEventListener('change', function () { if (r.checked) setMode(r.value, false); });
    });
    var wanted = T.param('mode') === 'examine' ? 'examine' : 'ask', wantedConcept = String(T.param('concept') || '').toLowerCase();
    refreshStatus().then(function (s) {
      var box = $('starters');
      var list = ((s && s.starters) || []).slice();
      if (S.context) list.unshift({ text: 'What do you make of my ' + (S.context.label || S.context.concept) + '?', mine: true });
      list.forEach(function (q) {
        var text = typeof q === 'string' ? q : q.text;
        box.appendChild(h('button', { type: 'button', class: 'so-starter' + (q.mine ? ' mine' : ''), text: text,
          onclick: function () { send(text); } }));
      });
      if (conceptInfo(wantedConcept)) S.examine.concept = wantedConcept;
      buildConcepts();
      var pre = T.param('q');
      if (pre) $('msg').value = pre.slice(0, 500);
      setMode(wanted, false);
    });
    updateMeta();
  }
  init();
})();
