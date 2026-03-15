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

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  // ── Agent Discovery ────────────────────────────────────────────────────────

  async function discoverAgents() {
    try {
      const resp = await apiFetch(`${apiBase}/api/agents/messaging`);
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

  // ── Session Management ─────────────────────────────────────────────────────

  async function loadSessions() {
    if (!agentId) return;
    try {
      const resp = await apiFetch(`${apiBase}/api/chat/${agentId}/sessions`);
      if (resp.ok) {
        sessions = await resp.json();
      }
    } catch (e) {
      console.error('Failed to load sessions:', e);
    }
  }

  async function loadSessionMessages(sid) {
    try {
      const resp = await apiFetch(`${apiBase}/api/chat/sessions/${sid}/messages`);
      if (resp.ok) {
        messages = await resp.json();
        sessionId = sid;
        scrollToBottom();
      }
    } catch (e) {
      console.error('Failed to load messages:', e);
    }
  }

  function startNewSession() {
    sessionId = null;
    messages = [];
    error = null;
  }

  async function selectSession(sid) {
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

      const resp = await apiFetch(`${apiBase}/api/chat/${agentId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: streamAbort.signal,
      });

      if (!resp.ok) {
        error = `Chat request failed (${resp.status})`;
        streaming = false;
        return;
      }

      // Capture session ID from response header
      const headerSessionId = resp.headers.get('X-Session-Id');
      if (headerSessionId) sessionId = headerSessionId;

      // Parse SSE stream via ReadableStream (P4-RC2)
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

      // Refresh session list if this was a new session
      await loadSessions();
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
          {formatTime(s.started_at)} — {s.session_id.slice(0, 8)}
        </option>
      {/each}
    </select>
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
              {@html renderMarkdown(msg.content)}
            {:else}
              <p>{msg.content}</p>
            {/if}
          </div>
        </div>
      {/each}
      {#if streaming && streamingText}
        <div class="message assistant">
          <div class="bubble streaming">
            {@html renderMarkdown(streamingText)}
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
</style>
