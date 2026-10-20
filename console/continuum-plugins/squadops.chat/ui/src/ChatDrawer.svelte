<svelte:options customElement="squadops-chat-drawer" />

<script>
  import { onMount } from 'svelte';
  import { marked } from 'marked';
  import DOMPurify from 'dompurify';

  marked.setOptions({ breaks: true, gfm: true });

  // ── State ──────────────────────────────────────────────────────────────────

  let messages = $state([]);
  let inputText = $state('');
  let streaming = $state(false);
  let streamingText = $state('');
  let sessionId = $state(null);
  let sessions = $state([]);
  let agentId = $state(null);
  let agentName = $state('Agent');
  let agents = $state([]);
  let error = $state(null);
  let messagesEl = $state(null);
  let textareaEl = $state(null);
  let streamAbort = null; // AbortController for in-flight stream

  // SIP-0110 Appendix A (#2180): a new conversation is bound to a project server-side when it
  // opens; a capture the agent proposes is stored only when you confirm it on its card.
  let projects = $state([]);
  let projectId = $state('');        // the project a NEW conversation is bound to; '' = unbound
  let sessionProject = $state(null); // the open session's stored binding, read from the server
  let card = $state(null);           // { text, sourceMessageId, choices, choice } while confirming
  let cardBusy = $state(false);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  // ── Agent Discovery ────────────────────────────────────────────────────────

  async function discoverAgents() {
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/agents/messaging`);
      if (!resp.ok) {
        error = 'Failed to load messaging agents';
        return;
      }
      agents = await resp.json();
      if (agents.length > 0) {
        agentId = agents[0].agent_id;
        agentName = agents[0].display_name || agents[0].agent_id;
      }
    } catch (e) {
      error = 'Failed to connect to API';
      console.error('Agent discovery failed:', e);
    }
  }

  async function loadProjects() {
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/projects`);
      if (resp.ok) projects = await resp.json();
    } catch (e) {
      console.error('Failed to load projects:', e);
    }
  }

  // ── Session Management ─────────────────────────────────────────────────────

  async function loadSessions() {
    if (!agentId) return;
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/chat/${agentId}/sessions`);
      if (resp.ok) {
        sessions = await resp.json();
      }
    } catch (e) {
      console.error('Failed to load sessions:', e);
    }
  }

  async function loadSessionMessages(sid) {
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/chat/sessions/${sid}/messages`);
      if (resp.ok) {
        messages = await resp.json();
        sessionId = sid;
        const listed = sessions.find((s) => s.session_id === sid);
        if (listed) sessionProject = listed.project_id ?? null;
        scrollToBottom();
      }
    } catch (e) {
      console.error('Failed to load messages:', e);
    }
  }

  function startNewSession() {
    sessionId = null;
    sessionProject = null;
    messages = [];
    error = null;
    card = null;
  }

  // Q29: you delete your own conversations; a record already confirmed from one stays, marked.
  async function deleteSession() {
    if (!sessionId || !confirm('Delete this conversation? Its messages are removed for good.')) return;
    const resp = await apiFetch(`${apiBase}/api/v1/chat/sessions/${sessionId}`, { method: 'DELETE' });
    if (resp.status !== 204) {
      error = `Delete failed (${resp.status})`;
      return;
    }
    startNewSession();
    await loadSessions();
  }

  // ── Capture (confirmed, never automatic) ──────────────────────────────────

  const CAPTURE_BLOCK = /<memory-capture>[\s\S]*?(<\/memory-capture>|$)/g;

  function shown(text) {
    return (text || '').replace(CAPTURE_BLOCK, '').trimEnd();
  }

  function choiceKey(c) {
    return `${c.kind}:${c.scope}`;
  }

  // The proposal's own kind and scope when this session offers them; else the same kind, said so;
  // else nothing chosen, so the person picks: a proposal is never quietly made something else.
  // A project instruction's applicability, as comma-separated names the person can narrow; '*' is any.
  const APPLICABILITY_FIELDS = ['task_types', 'roles', 'stacks'];

  function openCard({ text, sourceMessageId, choices, kind, scope, suggestion = false, applicability = null,
                     target = null, lessonRevision = null }) {
    const exact = choices.find((c) => c.kind === kind && c.scope === scope);
    // A task instruction is never offered as a project one: widening it is a new record (§3.5).
    const sameKind = exact || (scope === 'task' ? null : choices.find((c) => c.kind === kind && c.scope !== 'task'));
    const changed = exact ? null : `Proposed as a ${scope} ${kind}, which this conversation doesn't offer you.`;
    const applies = Object.fromEntries(
      // A field the agent didn't name stays blank: '*' (any) is the person's to choose, never a default.
      APPLICABILITY_FIELDS.map((f) => [f, (applicability?.[f] || []).join(', ')])
    );
    // A task instruction's cycle and tasks (#2180): a cycle the agent didn't name stays blank.
    const aims = { cycle_id: target?.cycle_id || '', task_types: (target?.task_types || []).join(', ') };
    card = { text, sourceMessageId, choices, choice: sameKind ? choiceKey(sameKind) : null,
             suggestion, changed, applies, aims, lessonRevision };
  }

  function targetOf(aims) {
    return { cycle_id: aims.cycle_id.trim(),
             task_types: aims.task_types.split(',').map((v) => v.trim()).filter(Boolean) };
  }

  function applicabilityOf(applies) {
    return Object.fromEntries(
      APPLICABILITY_FIELDS.map((f) => [f, applies[f].split(',').map((v) => v.trim()).filter(Boolean)])
    );
  }

  // A console action: keep a message, through the same card and the same confirmation.
  async function keepMessage(msg) {
    if (!sessionId || !msg.message_id) return;
    const resp = await apiFetch(`${apiBase}/api/v1/chat/sessions/${sessionId}/capture-choices`);
    if (!resp.ok) {
      error = `Could not load what you may keep (${resp.status})`;
      return;
    }
    openCard({ text: shown(msg.content), sourceMessageId: msg.message_id, choices: await resp.json(),
               kind: 'note', scope: 'user' });
  }

  async function confirmCard() {
    if (!card || !card.choice || cardBusy) return;
    const chosen = card.choices.find((c) => choiceKey(c) === card.choice);
    cardBusy = true;
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/chat/sessions/${sessionId}/captures`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: card.sourceMessageId, text: card.text,
                               kind: chosen.kind, scope: chosen.scope,
                               suggestion: chosen.kind === 'note' && card.suggestion,
                               ...(chosen.kind === 'instruction' && chosen.scope === 'project'
                                 ? { applicability: applicabilityOf(card.applies) } : {}),
                               ...(chosen.scope === 'task'
                                 ? { target: targetOf(card.aims),
                                     ...(card.lessonRevision ? { lesson_revision: card.lessonRevision } : {}) }
                                 : {}) }),
      });
      const body = await resp.json().catch(() => ({}));
      if (resp.status === 201) {
        messages = [...messages, body.reply];
        card = null;
      } else {
        // §3.5: a failed save is shown, never swallowed; the server's reply says it too.
        error = body?.detail?.error?.message || `Not saved (${resp.status})`;
        await loadSessionMessages(sessionId);
      }
    } finally {
      cardBusy = false;
      scrollToBottom();
    }
  }

  async function selectSession(sid) {
    card = null; // a card belongs to the conversation its turn came from
    if (sid === '') {
      startNewSession();
    } else {
      await loadSessionMessages(sid);
    }
  }

  // ── Message Sending (SSE via fetch — P4-RC2) ──────────────────────────────

  function cancelStream() {
    if (streamAbort) {
      streamAbort.abort();
      streamAbort = null;
    }
  }

  async function sendMessage() {
    const text = inputText.trim();
    if (!text || streaming || !agentId) return;

    // Abort any lingering stream before starting a new one
    cancelStream();

    // Add user message to UI
    messages = [...messages, { role: 'user', content: text }];
    inputText = '';
    streaming = true;
    streamingText = '';
    error = null;
    scrollToBottom();

    // Reset textarea height
    if (textareaEl) textareaEl.style.height = 'auto';

    streamAbort = new AbortController();

    try {
      const body = { message: text };
      if (sessionId) body.session_id = sessionId;
      else if (projectId) body.project_id = projectId;

      const resp = await apiFetch(`${apiBase}/api/v1/chat/${agentId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: streamAbort.signal,
      });

      if (!resp.ok) {
        const failure = await resp.json().catch(() => ({}));
        error = failure?.detail?.error?.message || `Chat request failed (${resp.status})`;
        streaming = false;
        return;
      }

      // Capture session ID from response header
      const headerSessionId = resp.headers.get('X-Session-Id');
      if (headerSessionId && !sessionId) {
        sessionId = headerSessionId;
        sessionProject = projectId || null;
      }

      // Parse SSE stream via ReadableStream (P4-RC2)
      let streamFailed = false;
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        // Keep last incomplete line in buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const jsonStr = line.slice(6);
          try {
            const evt = JSON.parse(jsonStr);
            if (evt.error) {
              error = evt.error;
              streamFailed = true;
            } else if (evt.capture) {
              openCard({ text: evt.capture.text, sourceMessageId: evt.capture.source_message_id,
                         choices: evt.capture.choices, kind: evt.capture.kind,
                         scope: evt.capture.scope, suggestion: evt.capture.suggestion,
                         applicability: evt.capture.applicability, target: evt.capture.target,
                         lessonRevision: evt.capture.lesson_revision });
            } else if (evt.done) {
              // Stream complete
            } else if (evt.text) {
              streamingText += evt.text;
              scrollToBottom();
            }
            // Capture session ID from event payload too
            if (evt.session_id && !sessionId) {
              sessionId = evt.session_id;
            }
          } catch {
            // Skip malformed JSON
          }
        }
      }

      // Refresh session list if this was a new session, and re-read the turn as stored, so each
      // message carries its id (a capture names the turn it came from)
      await loadSessions();
      // A reply that failed partway isn't stored: keep what streamed (its notice included) on
      // screen, where the finally below puts it, rather than re-reading a transcript without it.
      if (!streamFailed && sessionId) {
        streamingText = '';
        await loadSessionMessages(sessionId);
      }
    } catch (e) {
      if (e.name === 'AbortError') {
        // User cancelled — not an error
      } else {
        error = 'Failed to send message';
        console.error('Chat send error:', e);
      }
    } finally {
      streamAbort = null;
      // Preserve partial response on cancel
      if (streamingText) {
        messages = [...messages, { role: 'assistant', content: streamingText }];
      }
      streaming = false;
      streamingText = '';
      scrollToBottom();
    }
  }

  // ── UI Helpers ─────────────────────────────────────────────────────────────

  function scrollToBottom() {
    // Defer to next tick so DOM updates first
    setTimeout(() => {
      if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
    }, 0);
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function autoResize(e) {
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 80) + 'px';
  }

  function renderMarkdown(text) {
    return DOMPurify.sanitize(marked.parse(text || ''));
  }

  function formatTime(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  onMount(async () => {
    await discoverAgents();
    await loadProjects();
    if (agentId) await loadSessions();
    setTimeout(() => textareaEl?.focus(), 100);
  });
</script>

<div class="chat-content">
  <!-- Session selector -->
  <div class="session-bar">
    <select
      class="session-select"
      value={sessionId || ''}
      onchange={(e) => selectSession(e.target.value)}
    >
      <option value="">New conversation</option>
      {#each sessions as s}
        <option value={s.session_id}>
          {formatTime(s.started_at)} — {s.session_id.slice(0, 8)}{s.project_id ? ` · ${s.project_id}` : ''}
        </option>
      {/each}
    </select>
    {#if !sessionId}
      <select class="session-select" bind:value={projectId} title="The project this conversation is bound to">
        <option value="">No project (your own notes only)</option>
        {#each projects as p}
          <option value={p.project_id}>{p.project_id}</option>
        {/each}
      </select>
    {:else}
      <span class="agent-label" title="Bound when it opened; it can't change">
        {sessionProject ? `Project: ${sessionProject}` : 'No project'}
      </span>
      <button class="link-btn" onclick={deleteSession} title="Delete this conversation">Delete</button>
    {/if}
    <span class="agent-label">{agentName}</span>
  </div>

  <!-- Messages -->
  <div class="messages" bind:this={messagesEl}>
    {#if !agentId}
      <div class="empty-state">
        <p>No messaging agents available.</p>
        <p class="hint">Ensure an agent has <code>a2a_messaging_enabled: true</code> in instances.yaml.</p>
      </div>
    {:else if messages.length === 0 && !streaming}
      <div class="empty-state">
        <p>Start a conversation with {agentName}.</p>
        <p class="hint">Messages are persisted across sessions.</p>
      </div>
    {:else}
      {#each messages as msg}
        <div class="message {msg.role}">
          <div class="bubble">
            {#if msg.role === 'assistant'}
              {@html renderMarkdown(shown(msg.content))}
            {:else}
              <p>{msg.content}</p>
            {/if}
          </div>
          {#if msg.message_id && !card}
            <button class="link-btn keep" onclick={() => keepMessage(msg)} title="Keep this as a note or preference">Keep</button>
          {/if}
        </div>
      {/each}
      {#if streaming && streamingText}
        <div class="message assistant">
          <div class="bubble streaming">
            {@html renderMarkdown(shown(streamingText))}
          </div>
        </div>
      {/if}
      {#if streaming && !streamingText}
        <div class="message assistant">
          <div class="bubble typing">
            <span class="dot"></span><span class="dot"></span><span class="dot"></span>
          </div>
        </div>
      {/if}
    {/if}
    {#if error}
      <div class="error-banner">{error}</div>
    {/if}
  </div>

  <!-- Capture card: nothing is kept until you confirm (SIP-0110 §A.3.5) -->
  {#if card}
    <div class="capture-card">
      <div class="capture-title">Keep this?</div>
      {#if card.changed}<div class="hint">{card.changed}</div>{/if}
      <textarea bind:value={card.text} rows="2"></textarea>
      {#each card.choices as c}
        <label class="capture-choice">
          <input type="radio" name="capture-choice" value={choiceKey(c)} bind:group={card.choice} />
          <span>{c.scope === 'task' ? `Task instruction for one cycle (${c.project_id})` : c.kind === 'instruction' ? `Project instruction (${c.project_id})` : c.scope === 'project' ? `Project note (${c.project_id})` : c.kind === 'preference' ? 'Your preference' : 'Your note'}</span>
          <span class="hint">takes effect {c.takes_effect}</span>
        </label>
      {/each}
      {#if card.choice === 'instruction:task'}
        <div class="hint">An intervention: it reaches this cycle's named tasks from their next dispatch, and is refused once they have dispatched.</div>
        <label class="capture-choice">
          <span>cycle</span>
          <input class="applies" bind:value={card.aims.cycle_id} placeholder="cyc_…" />
        </label>
        <label class="capture-choice">
          <span>task types</span>
          <input class="applies" bind:value={card.aims.task_types} />
        </label>
        {#if card.lessonRevision}
          <div class="hint">Applies lesson {card.lessonRevision}: refused for a cycle whose unit disables lessons.</div>
        {/if}
      {:else if card.choice?.startsWith('instruction:')}
        <div class="hint">It binds the squad's work in units admitted after you confirm it, on the tasks named here ('*' for any).</div>
        {#each APPLICABILITY_FIELDS as f}
          <label class="capture-choice">
            <span>{f.replace('_', ' ')}</span>
            <input class="applies" bind:value={card.applies[f]} />
          </label>
        {/each}
      {/if}
      {#if card.lessonRevision && card.choice && card.choice !== 'instruction:task'}
        <div class="hint">The agent proposed applying lesson {card.lessonRevision} to a cycle's task; only a task instruction carries it.</div>
      {/if}
      {#if card.choice?.startsWith('note:')}
        <label class="capture-choice" title="A claim to check, never a lesson's evidence">
          <input type="checkbox" bind:checked={card.suggestion} />
          <span>A suggestion: a claim about how the squad should work, kept to check</span>
        </label>
      {/if}
      <div class="capture-actions">
        <button class="link-btn" onclick={() => (card = null)} disabled={cardBusy}>Dismiss</button>
        <button class="send-btn wide" onclick={confirmCard} disabled={cardBusy || !card.text.trim() || !card.choice}>
          {cardBusy ? 'Saving…' : 'Confirm'}
        </button>
      </div>
    </div>
  {/if}

  <!-- Input -->
  <div class="input-area">
    {#if streaming}
      <button class="stop-btn" onclick={cancelStream} title="Stop generating">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <rect x="4" y="4" width="16" height="16" rx="2"/>
        </svg>
        Stop
      </button>
    {/if}
    <textarea
      bind:this={textareaEl}
      bind:value={inputText}
      placeholder={agentId ? `Message ${agentName}...` : 'No agent available'}
      disabled={streaming || !agentId}
      onkeydown={handleKeydown}
      oninput={autoResize}
      rows="1"
    ></textarea>
    <button
      class="send-btn"
      onclick={sendMessage}
      disabled={streaming || !inputText.trim() || !agentId}
      title="Send message"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="22" y1="2" x2="11" y2="13"/>
        <polygon points="22 2 15 22 11 13 2 9 22 2"/>
      </svg>
    </button>
  </div>
</div>

<style>
  .chat-content {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  /* ── Session Bar ──────────────────────────────────────────────────────── */
  .session-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    border-bottom: 1px solid var(--continuum-border, #2d2d44);
    flex-shrink: 0;
  }
  .session-select {
    background: var(--continuum-bg-secondary, #252540);
    color: var(--continuum-text-secondary, #a0a0b8);
    border: 1px solid var(--continuum-border, #2d2d44);
    border-radius: 4px;
    padding: 4px 6px;
    font-size: var(--continuum-font-size-xs, 11px);
    max-width: 200px;
    cursor: pointer;
  }
  .agent-label {
    font-size: var(--continuum-font-size-xs, 11px);
    color: var(--continuum-text-muted, #707088);
  }

  /* ── Messages ────────────────────────────────────────────────────────── */
  .messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .message {
    display: flex;
    max-width: 85%;
  }
  .message.user {
    align-self: flex-end;
  }
  .message.assistant {
    align-self: flex-start;
  }
  .bubble {
    padding: 8px 12px;
    border-radius: 12px;
    font-size: var(--continuum-font-size-sm, 13px);
    line-height: 1.5;
    word-wrap: break-word;
    overflow-wrap: break-word;
  }
  .message.user .bubble {
    background: var(--continuum-accent-primary, #6366f1);
    color: white;
    border-bottom-right-radius: 4px;
  }
  .message.assistant .bubble {
    background: var(--continuum-bg-secondary, #252540);
    color: var(--continuum-text-primary, #e0e0e8);
    border-bottom-left-radius: 4px;
  }
  /* Markdown reset inside bubbles */
  .bubble :global(p) {
    margin: 0 0 8px 0;
  }
  .bubble :global(p:last-child) {
    margin-bottom: 0;
  }
  .bubble :global(code) {
    background: rgba(0, 0, 0, 0.2);
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 0.9em;
  }
  .bubble :global(pre) {
    background: rgba(0, 0, 0, 0.3);
    padding: 8px;
    border-radius: 4px;
    overflow-x: auto;
    margin: 4px 0;
  }
  .bubble :global(pre code) {
    background: none;
    padding: 0;
  }

  /* Streaming indicator */
  .bubble.streaming {
    border-left: 2px solid var(--continuum-accent-primary, #6366f1);
  }
  .typing {
    display: flex;
    gap: 4px;
    padding: 12px 16px;
  }
  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--continuum-text-secondary, #a0a0b8);
    animation: bounce 1.2s infinite ease-in-out;
  }
  .dot:nth-child(2) { animation-delay: 0.2s; }
  .dot:nth-child(3) { animation-delay: 0.4s; }
  @keyframes bounce {
    0%, 60%, 100% { transform: translateY(0); }
    30% { transform: translateY(-6px); }
  }

  /* Empty state */
  .empty-state {
    text-align: center;
    padding: 40px 20px;
    color: var(--continuum-text-secondary, #a0a0b8);
  }
  .empty-state p {
    margin: 4px 0;
  }
  .hint {
    font-size: var(--continuum-font-size-xs, 11px);
    opacity: 0.7;
  }
  .hint code {
    background: var(--continuum-bg-secondary, #252540);
    padding: 1px 4px;
    border-radius: 3px;
  }

  /* Error */
  .error-banner {
    background: rgba(239, 68, 68, 0.15);
    color: #f87171;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: var(--continuum-font-size-xs, 11px);
    text-align: center;
  }

  /* ── Input Area ────────────────────────────────────────────────────────── */
  .input-area {
    display: flex;
    align-items: flex-end;
    gap: 8px;
    padding: 12px 16px;
    border-top: 1px solid var(--continuum-border, #2d2d44);
    flex-shrink: 0;
  }
  .input-area textarea {
    flex: 1;
    background: var(--continuum-bg-secondary, #252540);
    color: var(--continuum-text-primary, #e0e0e8);
    border: 1px solid var(--continuum-border, #2d2d44);
    border-radius: 8px;
    padding: 8px 12px;
    font-size: var(--continuum-font-size-sm, 13px);
    font-family: inherit;
    resize: none;
    overflow-y: hidden;
    line-height: 1.4;
  }
  .input-area textarea:focus {
    outline: none;
    border-color: var(--continuum-accent-primary, #6366f1);
  }
  .input-area textarea:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .input-area textarea::placeholder {
    color: var(--continuum-text-secondary, #a0a0b8);
    opacity: 0.6;
  }
  .stop-btn {
    background: var(--continuum-bg-secondary, #252540);
    border: 1px solid var(--continuum-border, #2d2d44);
    color: var(--continuum-text-secondary, #a0a0b8);
    border-radius: 6px;
    padding: 4px 10px;
    font-size: var(--continuum-font-size-xs, 11px);
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }
  .stop-btn:hover {
    color: #f87171;
    border-color: #f87171;
  }
  .send-btn {
    background: var(--continuum-accent-primary, #6366f1);
    border: none;
    color: white;
    width: 36px;
    height: 36px;
    border-radius: 8px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: opacity 0.1s ease;
  }
  .send-btn:hover:not(:disabled) {
    opacity: 0.85;
  }
  .send-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .send-btn.wide {
    width: auto;
    padding: 0 14px;
    font-size: var(--continuum-font-size-xs, 11px);
  }

  /* ── Memory: the capture card and its actions (#2180) ────────────────── */
  .link-btn {
    background: none;
    border: none;
    color: var(--continuum-text-secondary, #a0a0b8);
    font-size: var(--continuum-font-size-xs, 11px);
    cursor: pointer;
    padding: 2px 4px;
  }
  .link-btn:hover:not(:disabled) {
    color: var(--continuum-accent-primary, #6366f1);
  }
  .link-btn.keep {
    align-self: flex-end;
    opacity: 0.6;
  }
  .capture-card {
    margin: 0 16px 8px;
    padding: 10px 12px;
    border: 1px solid var(--continuum-accent-primary, #6366f1);
    border-radius: 8px;
    background: var(--continuum-bg-secondary, #252540);
    display: flex;
    flex-direction: column;
    gap: 6px;
    flex-shrink: 0;
  }
  .capture-title {
    font-size: var(--continuum-font-size-sm, 13px);
    color: var(--continuum-text-primary, #e0e0e8);
  }
  .capture-card textarea {
    background: var(--continuum-bg-primary, #1a1a2e);
    color: var(--continuum-text-primary, #e0e0e8);
    border: 1px solid var(--continuum-border, #2d2d44);
    border-radius: 6px;
    padding: 6px 8px;
    font-family: inherit;
    font-size: var(--continuum-font-size-sm, 13px);
    resize: vertical;
  }
  .capture-choice {
    display: flex;
    align-items: baseline;
    gap: 6px;
    font-size: var(--continuum-font-size-xs, 11px);
    color: var(--continuum-text-secondary, #a0a0b8);
  }
  .capture-choice .applies {
    flex: 1;
    background: var(--continuum-bg-primary, #1a1a2e);
    color: var(--continuum-text-primary, #e0e0e8);
    border: 1px solid var(--continuum-border, #2d2d44);
    border-radius: 4px;
    padding: 2px 6px;
  }
  .capture-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
</style>
