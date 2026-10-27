/* Ask the Lab: send a question, show the agent's steps as they stream in (JSON lines), then the answer. */
(function () {
  'use strict';
  var T = window.TOT, h = T.h;
  var DOCS = 'https://github.com/rnorlund/MetaLesionLab/blob/main/docs/';
  var TOOLS = ['list_conditions', 'error_profile_by_site', 'get_condition', 'compare_conditions', 'find_responses',
    'word_lens', 'human_reference', 'plato_stats', 'cut_results', 'bilingual_results', 'language_support'];
  var PLACE = {
    list_conditions: 'Model Lab', error_profile_by_site: 'Model Lab', get_condition: 'Model Lab',
    compare_conditions: 'Model Lab', find_responses: 'Model Lab', word_lens: 'Word lens',
    human_reference: 'People with aphasia (published)', plato_stats: 'Plato’s Chair', cut_results: 'What can I cut?',
    bilingual_results: 'Bilingual test write-up', language_support: 'Language support'
  };
  var S = { busy: false, status: null };
  function $(id) { return document.getElementById(id); }

  // --- links ------------------------------------------------------------------------------
  var COND = /demo_\w+:[\w.\-]+/;
  function hrefFor(tool, arg) {
    var m = COND.exec(arg || '');
    if (m && tool !== 'plato_stats') return '/lab?c=' + encodeURIComponent(m[0]);
    if (tool === 'plato_stats') return '/plato#everything';
    if (tool === 'cut_results') return '/lab/cut';
    if (tool === 'bilingual_results') return DOCS + 'bilingual.md';
    if (tool === 'language_support') return DOCS + 'languages.md';
    return '/lab';
  }
  function safeHref(href) {
    href = String(href || '');
    if (/^\/(lab|plato|ask|challenge|take|studio|scorer|assess)(\/cut)?([?#][^\s"'<>]*)?$/.test(href)) return href;
    if (href.indexOf(DOCS) === 0 || /^https:\/\/(doi\.org|pmc\.ncbi\.nlm\.nih\.gov|arxiv\.org)\//.test(href)) return href;
    return null;
  }
  function external(href) { return /^https:/.test(href); }

  // --- answer text: a small, safe subset of Markdown ---------------------------------------------
  // A citation chip names the tool briefly, then what it looked up; trailing punctuation stays on its line.
  var SHORT = {
    list_conditions: 'conditions', error_profile_by_site: 'by damage site', get_condition: 'condition',
    compare_conditions: 'compare', find_responses: 'search', word_lens: 'word lens', human_reference: 'published data',
    plato_stats: 'Plato’s Chair', cut_results: 'What can I cut?', bilingual_results: 'bilingual test',
    language_support: 'languages'
  };
  var CITE = new RegExp('\\[(?:source:\\s*)?(' + TOOLS.join('|') + ')(?:\\s*[:,]\\s*([^\\]]*))?\\]([.,;:!?)]*)', 'g');
  function inline(text) {
    var out = T.esc(text);
    out = out.replace(CITE, function (_, tool, arg, punct) {
      arg = (arg || '').trim();
      var href = hrefFor(tool, arg);
      var label = SHORT[tool] + (arg ? ' · ' + arg.replace(/^demo_en:/, '') : '');
      return '<span class="cite-wrap"><a class="cite" href="' + href + '"' +
        (external(href) ? ' target="_blank" rel="noopener"' : '') + ' title="Source: ' + tool + (arg ? ' · ' + arg : '') +
        '">' + label + '</a>' + (punct || '') + '</span>';
    });
    out = out.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
    out = out.replace(/`([^`]+)`/g, '<code>$1</code>');
    out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, function (all, label, href) {
      var ok = safeHref(href.replace(/&amp;/g, '&'));
      return ok ? '<a href="' + T.esc(ok) + '"' + (external(ok) ? ' target="_blank" rel="noopener"' : '') + '>' + label + '</a>' : label;
    });
    return out;
  }
  function renderAnswer(text) {
    var box = h('div');
    var blocks = String(text || '').replace(/\r/g, '').split(/\n\s*\n/);
    blocks.forEach(function (block) {
      var lines = block.split('\n').filter(function (l) { return l.trim(); });
      if (!lines.length) return;
      var bullet = /^\s*(?:[-*•]|\d+[.)])\s+/;
      if (lines.every(function (l) { return bullet.test(l); })) {
        var ordered = /^\s*\d/.test(lines[0]);
        var list = h(ordered ? 'ol' : 'ul');
        lines.forEach(function (l) { list.appendChild(h('li', { html: inline(l.replace(bullet, '')) })); });
        box.appendChild(list);
      } else {
        box.appendChild(h('p', { html: lines.map(function (l) { return inline(l.replace(/^#+\s*/, '')); }).join('<br>') }));
      }
    });
    return box;
  }

  // --- one question ----------------------------------------------------------------------
  function argText(args) {
    return Object.keys(args || {}).map(function (k) {
      var v = args[k];
      return k + ': ' + (typeof v === 'string' ? '"' + v + '"' : JSON.stringify(v));
    }).join(', ');
  }
  function step(kind, label, body) {
    return h('li', { class: 'ask-step ' + kind }, [h('span', { class: 'ask-kind', text: label }), h('div', { class: 'ask-body' }, body)]);
  }
  function money(usd) {
    if (!usd) return '$0';
    return usd < 0.001 ? '<$0.001' : '$' + usd.toFixed(usd < 0.1 ? 3 : 2);
  }

  function Turn(question) {
    this.steps = h('ol', { class: 'ask-steps' });
    this.count = h('span', { text: 'Steps' });
    this.trace = h('details', { class: 'ask-trace', open: true }, [h('summary', null, [this.count]), this.steps]);
    this.state = h('span', { class: 'ask-state' }, [h('span', { class: 'spinner', 'aria-hidden': 'true' }), 'working']);
    this.answer = h('div', { class: 'ask-answer', 'aria-live': 'polite' });
    this.foot = h('div', { class: 'ask-foot' });
    this.calls = {};
    this.n = 0;
    this.el = h('article', { class: 'panel ask-turn', 'aria-label': 'Question and answer' }, [
      h('div', { class: 'ask-q' }, [h('h2', { text: question }), this.state]),
      this.trace, this.answer, this.foot
    ]);
  }
  Turn.prototype.add = function (li) {
    this.steps.appendChild(li);
    this.n += 1;
    this.count.textContent = 'Steps (' + this.n + ')';
  };
  Turn.prototype.finish = function (text) {
    this.state.innerHTML = '';
    this.state.appendChild(document.createTextNode(text));
  };
  Turn.prototype.handle = function (ev) {
    if (ev.type === 'thinking') {
      this.add(step('think', 'plan', [h('div', { text: ev.text })]));
    } else if (ev.type === 'tool_call') {
      var res = h('div', { class: 'ask-result' }, [h('span', { class: 'spinner', 'aria-hidden': 'true' }), ' running…']);
      var li = step('tool', 'tool', [h('div', { class: 'ask-call', text: ev.name + '(' + argText(ev.args) + ')' }), res]);
      this.calls[ev.step] = res;
      this.add(li);
    } else if (ev.type === 'tool_result') {
      var slot = this.calls[ev.step];
      if (!slot) return;
      slot.innerHTML = '';
      var failed = /^Error:/.test(ev.summary || '');
      slot.appendChild(h('span', { class: failed ? 'ask-error' : 'ok', text: failed ? '' : '✓' }));
      slot.appendChild(document.createTextNode(ev.summary || 'done'));
      var link = safeHref(ev.link);
      if (link) slot.appendChild(h('a', { href: link, target: external(link) ? '_blank' : null, rel: external(link) ? 'noopener' : null, text: 'open' }));
      var json = JSON.stringify(ev.result, null, 1);
      slot.parentNode.appendChild(h('details', { class: 'ask-data' }, [
        h('summary', { text: 'What the tool returned' }),
        h('pre', { text: json.length > 6000 ? json.slice(0, 6000) + '\n…' : json })
      ]));
    } else if (ev.type === 'checking') {
      this.add(step('check', 'check', [h('div', { text: ev.text })]));
    } else if (ev.type === 'guard') {
      this.add(step('check', 'guard', [h('div', { text: ev.text })]));
    } else if (ev.type === 'error') {
      this.add(step('error', 'error', [h('div', { text: ev.message })]));
      this.finish('stopped');
    } else if (ev.type === 'answer') {
      this.showAnswer(ev);
    } else if (ev.type === 'done') {
      if (!this.done) this.finish('done');
    }
  };
  Turn.prototype.showAnswer = function (ev) {
    var c = ev.check || {};
    this.done = true;
    if (!this.n) this.trace.hidden = true;  // answered without any step to show
    this.answer.innerHTML = '';
    this.answer.className = 'ask-answer' + (ev.refused ? ' refused' : '');
    this.answer.appendChild(renderAnswer(ev.text));
    if (!ev.refused) {
      var nums = c.numbers || 0;
      var good = !(c.unverified || []).length && !(c.banned_words || []).length;
      var parts = [];
      if (good) {
        parts.push(h('b', { text: nums ? '✓ Checked: ' : '✓ ' }));
        parts.push(nums ? 'all ' + nums + ' numbers match the tool results' +
          ((c.derived || []).length ? ' (' + c.derived.length + ' worked out from two of them)' : '') + '.' : 'No numbers to check.');
      } else {
        parts.push(h('b', { text: 'Check before you use this: ' }));
        if ((c.unverified || []).length) parts.push('these numbers weren’t found in the tool results: ' + c.unverified.join(', ') + '. ');
        if ((c.banned_words || []).length) parts.push('wording flagged: ' + c.banned_words.join(', ') + '.');
      }
      if (nums && !c.cited) parts.push(' Some numbers have no source tag.');
      if (c.repaired) parts.push(' The first draft was corrected once.');
      this.answer.parentNode.insertBefore(h('div', { class: 'ask-check ' + (good ? 'ok' : 'warn') }, parts), this.foot);
    }
    var src = h('div', { class: 'ask-sources' });
    (ev.sources || []).forEach(function (s) {
      var href = safeHref(s.href);
      if (!href) return;
      var arg = (s.args && (s.args.id || s.args.condition_id || s.args.condition || s.args.concept || s.args.language || s.args.lang || s.args.item || s.args.text)) || '';
      src.appendChild(h('a', { href: href, target: external(href) ? '_blank' : null, rel: external(href) ? 'noopener' : null },
        [(PLACE[s.tool] || 'Open') + (arg ? ' · ' + String(arg).replace(/^demo_en:/, '') : ''), external(href) ? ' ↗' : ' →']));
    });
    this.foot.innerHTML = '';
    if (src.childNodes.length) this.foot.appendChild(src);
    var stats = ev.refused ? 'answered without calling the model · $0' :
      money(ev.cost_usd) + ' · ' + ev.tool_calls + ' tool call' + (ev.tool_calls === 1 ? '' : 's') + ' · ' +
      ev.model_calls + ' Muse Spark call' + (ev.model_calls === 1 ? '' : 's') + ' · ' + ev.t.toFixed(1) + ' s';
    this.foot.appendChild(h('span', { class: 'ask-cost', text: stats }));
    this.finish(ev.refused ? 'declined' : 'answered');
  };

  // --- sending -----------------------------------------------------------------------------
  function setBusy(on) {
    S.busy = on;
    $('ask-btn').disabled = on;
    $('ask-btn').textContent = on ? 'Working…' : 'Ask';
    Array.prototype.forEach.call(document.querySelectorAll('.ask-chip'), function (b) { b.disabled = on; });
  }

  function ask(question) {
    question = String(question || '').trim();
    if (!question || S.busy) return;
    var thread = $('thread');
    Array.prototype.forEach.call(thread.querySelectorAll('details.ask-trace'), function (d) { d.open = false; });
    var turn = new Turn(question);
    thread.insertBefore(turn.el, thread.firstChild);
    setBusy(true);
    fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: question }) })
      .then(function (res) {
        if (!res.ok) {
          return res.json().catch(function () { return {}; }).then(function (d) {
            var msg = d && d.detail;
            if (Array.isArray(msg)) msg = msg.map(function (x) { return x.msg; }).join('; ');
            turn.handle({ type: 'error', message: msg || ('Request failed (' + res.status + ')') });
          });
        }
        var reader = res.body.getReader(), dec = new TextDecoder(), buf = '';
        function line(l) {
          if (!l.trim()) return;
          try { turn.handle(JSON.parse(l)); } catch (e) { /* a broken line is skipped */ }
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
      .catch(function (e) { turn.handle({ type: 'error', message: 'The connection dropped (' + e.message + '). Try again.' }); })
      .then(function () {
        if (!turn.done && turn.state.querySelector('.spinner')) turn.finish('stopped');
        setBusy(false);
        refreshStatus();
      });
  }

  function refreshStatus() {
    return T.api('/api/ask/status').then(function (s) {
      S.status = s;
      var meta = $('ask-meta'), off = $('ask-off');
      meta.textContent = 'Muse Spark 1.3 · reasoning ' + s.reasoning_effort + ' · up to ' + s.max_tool_calls +
        ' tool calls per question · ' + s.questions_left + ' of ' + s.per_session + ' questions left today';
      var why = !s.enabled ? 'Ask the Lab needs the Meta Model API, which isn’t set up on this server. Every other page works.'
        : !s.budget_left ? 'Ask the Lab has used today’s budget for questions. Every page of the lab still works; the agent will be back tomorrow.'
        : !s.questions_left ? 'You’ve used today’s questions on this demo. Every page of the lab still works.' : '';
      off.hidden = !why;
      off.textContent = why;
      $('tool-list').textContent = 'Tools: ' + s.tools.join(', ') + '. All read-only.';
      return s;
    }).catch(function () { return null; });
  }

  function init() {
    $('ask-form').addEventListener('submit', function (e) { e.preventDefault(); ask($('q').value); });
    $('q').addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); ask($('q').value); }
    });
    refreshStatus().then(function (s) {
      var box = $('suggest');
      ((s && s.suggested) || []).forEach(function (q) {
        box.appendChild(h('button', { type: 'button', class: 'ask-chip', text: q, onclick: function () { $('q').value = q; ask(q); } }));
      });
      var pre = T.param('q');
      if (pre) { $('q').value = pre; }
    });
  }
  init();
})();
