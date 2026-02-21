<svelte:options customElement="squadops-artifacts-viewer" />

<script>
  import { onMount, onDestroy } from 'svelte';
  import { marked } from 'marked';
  import hljs from 'highlight.js/lib/core';
  import json from 'highlight.js/lib/languages/json';
  import yaml from 'highlight.js/lib/languages/yaml';
  import python from 'highlight.js/lib/languages/python';
  import javascript from 'highlight.js/lib/languages/javascript';
  import bash from 'highlight.js/lib/languages/bash';
  import xml from 'highlight.js/lib/languages/xml';
  import css from 'highlight.js/lib/languages/css';

  hljs.registerLanguage('json', json);
  hljs.registerLanguage('yaml', yaml);
  hljs.registerLanguage('python', python);
  hljs.registerLanguage('javascript', javascript);
  hljs.registerLanguage('bash', bash);
  hljs.registerLanguage('xml', xml);
  hljs.registerLanguage('html', xml);
  hljs.registerLanguage('css', css);

  marked.setOptions({ breaks: true, gfm: true });

  let visible = $state(false);
  let artifact = $state(null);
  let loading = $state(false);
  let error = $state(null);
  let rawText = $state('');
  let renderedHtml = $state('');
  let renderMode = $state('plain'); // 'markdown' | 'highlighted' | 'plain' | 'binary'

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  /** Map media type to render mode and highlight.js language. */
  function classifyMedia(mediaType) {
    if (!mediaType) return { mode: 'plain', lang: null };
    const mt = mediaType.toLowerCase();
    if (mt === 'text/markdown') return { mode: 'markdown', lang: null };
    if (mt === 'application/json') return { mode: 'highlighted', lang: 'json' };
    if (mt === 'application/yaml' || mt === 'text/yaml') return { mode: 'highlighted', lang: 'yaml' };
    if (mt === 'text/x-python') return { mode: 'highlighted', lang: 'python' };
    if (mt === 'application/javascript' || mt === 'text/javascript') return { mode: 'highlighted', lang: 'javascript' };
    if (mt === 'text/html') return { mode: 'highlighted', lang: 'html' };
    if (mt === 'text/css') return { mode: 'highlighted', lang: 'css' };
    if (mt === 'text/x-shellscript') return { mode: 'highlighted', lang: 'bash' };
    if (mt.startsWith('text/')) return { mode: 'plain', lang: null };
    return { mode: 'binary', lang: null };
  }

  async function fetchAndRender(art) {
    loading = true;
    error = null;
    rawText = '';
    renderedHtml = '';
    renderMode = 'plain';

    const { mode, lang } = classifyMedia(art.media_type);

    if (mode === 'binary') {
      renderMode = 'binary';
      loading = false;
      return;
    }

    try {
      const resp = await apiFetch(`${apiBase}/api/v1/artifacts/${art.artifact_id}/download`);
      if (!resp.ok) {
        error = `Failed to fetch artifact (HTTP ${resp.status})`;
        loading = false;
        return;
      }
      const text = await resp.text();
      rawText = text;

      if (mode === 'markdown') {
        renderMode = 'markdown';
        renderedHtml = marked.parse(text);
      } else if (mode === 'highlighted') {
        renderMode = 'highlighted';
        if (lang === 'json') {
          try { rawText = JSON.stringify(JSON.parse(text), null, 2); } catch { /* keep raw */ }
        }
        const result = hljs.highlight(rawText, { language: lang });
        renderedHtml = result.value;
      } else {
        renderMode = 'plain';
      }
    } catch (e) {
      error = `Failed to load artifact: ${e.message}`;
    }
    loading = false;
  }

  function onViewEvent(e) {
    artifact = e.detail;
    visible = true;
    fetchAndRender(e.detail);
  }

  function close() {
    visible = false;
    artifact = null;
    rawText = '';
    renderedHtml = '';
    error = null;
  }

  function onKey(e) {
    if (e.key === 'Escape') close();
  }

  function onBackdropClick(e) {
    if (e.target === e.currentTarget) close();
  }

  async function download() {
    if (!artifact) return;
    const resp = await apiFetch(`${apiBase}/api/v1/artifacts/${artifact.artifact_id}/download`);
    if (resp.ok) {
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = artifact.filename;
      a.click();
      URL.revokeObjectURL(url);
    }
  }

  function formatSize(bytes) {
    if (!bytes) return '--';
    if (bytes < 1024) return `${bytes} B`;
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  onMount(() => {
    window.addEventListener('squadops:view-artifact', onViewEvent);
    window.addEventListener('keydown', onKey);
  });

  onDestroy(() => {
    window.removeEventListener('squadops:view-artifact', onViewEvent);
    window.removeEventListener('keydown', onKey);
  });
</script>

{#if visible}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div class="modal-backdrop" onclick={onBackdropClick}>
    <div class="modal-container">
      <header class="modal-header">
        <div class="header-left">
          <span class="filename">{artifact?.filename || ''}</span>
          {#if artifact?.artifact_type}
            <span class="type-badge">{artifact.artifact_type}</span>
          {/if}
        </div>
        <button class="close-btn" onclick={close} aria-label="Close viewer">&times;</button>
      </header>

      <div class="modal-body">
        {#if loading}
          <div class="loading">Loading artifact content...</div>
        {:else if error}
          <div class="error">{error}</div>
        {:else if renderMode === 'markdown'}
          <div class="markdown-content">{@html renderedHtml}</div>
        {:else if renderMode === 'highlighted'}
          <pre class="highlighted-content"><code>{@html renderedHtml}</code></pre>
        {:else if renderMode === 'binary'}
          <div class="binary-content">
            <p>Preview not available for this file type.</p>
            <button class="action-btn" onclick={download}>Download to view</button>
          </div>
        {:else}
          <pre class="plain-content">{rawText}</pre>
        {/if}
      </div>

      <footer class="modal-footer">
        <button class="action-btn" onclick={download}>Download</button>
        <span class="footer-meta">
          {formatSize(artifact?.size_bytes)}
          {#if artifact?.media_type}
            &middot; {artifact.media_type}
          {/if}
        </span>
      </footer>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    z-index: 9999;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .modal-container {
    width: 90vw;
    max-width: 1200px;
    height: 90vh;
    background: var(--continuum-bg-primary, #0f172a);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-md, 8px);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }

  /* Header */
  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--continuum-space-md, 16px) var(--continuum-space-lg, 24px);
    border-bottom: 1px solid var(--continuum-border, #334155);
    flex-shrink: 0;
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: var(--continuum-space-sm, 8px);
    min-width: 0;
  }
  .filename {
    font-weight: 600;
    font-size: var(--continuum-font-size-md, 1rem);
    word-break: break-all;
  }
  .type-badge {
    background: var(--continuum-bg-tertiary, #334155);
    padding: 2px 8px;
    border-radius: var(--continuum-radius-sm, 4px);
    font-size: var(--continuum-font-size-xs, 0.75rem);
    white-space: nowrap;
  }
  .close-btn {
    background: none;
    border: none;
    color: var(--continuum-text-muted, #94a3b8);
    font-size: 1.5rem;
    cursor: pointer;
    padding: 4px 8px;
    line-height: 1;
    border-radius: var(--continuum-radius-sm, 4px);
    flex-shrink: 0;
  }
  .close-btn:hover {
    color: var(--continuum-text-primary, #e2e8f0);
    background: var(--continuum-bg-hover, #334155);
  }

  /* Body */
  .modal-body {
    flex: 1;
    overflow-y: auto;
    padding: var(--continuum-space-lg, 24px);
  }
  .loading, .error {
    color: var(--continuum-text-muted, #94a3b8);
    padding: var(--continuum-space-lg, 24px);
  }
  .error { color: var(--continuum-danger, #ef4444); }

  .plain-content {
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    white-space: pre-wrap;
    word-break: break-word;
    margin: 0;
    line-height: 1.6;
  }
  .highlighted-content {
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    margin: 0;
    line-height: 1.6;
    white-space: pre;
    overflow-x: auto;
  }
  .highlighted-content code {
    font-family: inherit;
  }

  /* highlight.js token colors (dark theme) */
  .highlighted-content :global(.hljs-keyword) { color: #c678dd; }
  .highlighted-content :global(.hljs-string) { color: #98c379; }
  .highlighted-content :global(.hljs-number) { color: #d19a66; }
  .highlighted-content :global(.hljs-literal) { color: #56b6c2; }
  .highlighted-content :global(.hljs-built_in) { color: #e6c07b; }
  .highlighted-content :global(.hljs-comment) { color: #5c6370; font-style: italic; }
  .highlighted-content :global(.hljs-attr) { color: #d19a66; }
  .highlighted-content :global(.hljs-punctuation) { color: #abb2bf; }
  .highlighted-content :global(.hljs-tag) { color: #e06c75; }
  .highlighted-content :global(.hljs-name) { color: #e06c75; }
  .highlighted-content :global(.hljs-attribute) { color: #d19a66; }
  .highlighted-content :global(.hljs-selector-class) { color: #d19a66; }
  .highlighted-content :global(.hljs-selector-tag) { color: #e06c75; }
  .highlighted-content :global(.hljs-property) { color: #e06c75; }
  .highlighted-content :global(.hljs-title) { color: #61afef; }
  .highlighted-content :global(.hljs-params) { color: #abb2bf; }

  /* Markdown content styling */
  .markdown-content {
    line-height: 1.7;
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }
  .markdown-content :global(h1) { font-size: 1.5rem; font-weight: 700; margin: 1.5em 0 0.5em; }
  .markdown-content :global(h2) { font-size: 1.25rem; font-weight: 600; margin: 1.25em 0 0.5em; }
  .markdown-content :global(h3) { font-size: 1.1rem; font-weight: 600; margin: 1em 0 0.5em; }
  .markdown-content :global(p) { margin: 0.5em 0; }
  .markdown-content :global(ul), .markdown-content :global(ol) { padding-left: 1.5em; margin: 0.5em 0; }
  .markdown-content :global(li) { margin: 0.25em 0; }
  .markdown-content :global(code) {
    font-family: var(--continuum-font-mono, monospace);
    background: var(--continuum-bg-secondary, #1e293b);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.85em;
  }
  .markdown-content :global(pre) {
    background: var(--continuum-bg-secondary, #1e293b);
    padding: var(--continuum-space-md, 16px);
    border-radius: var(--continuum-radius-sm, 4px);
    overflow-x: auto;
    margin: 0.75em 0;
  }
  .markdown-content :global(pre code) { background: none; padding: 0; }
  .markdown-content :global(table) { width: 100%; border-collapse: collapse; margin: 0.75em 0; }
  .markdown-content :global(th), .markdown-content :global(td) {
    text-align: left;
    padding: var(--continuum-space-sm, 8px);
    border-bottom: 1px solid var(--continuum-border, #334155);
  }
  .markdown-content :global(th) { color: var(--continuum-text-muted, #94a3b8); font-weight: 500; }
  .markdown-content :global(blockquote) {
    border-left: 3px solid var(--continuum-border, #334155);
    padding-left: var(--continuum-space-md, 16px);
    color: var(--continuum-text-muted, #94a3b8);
    margin: 0.75em 0;
  }
  .markdown-content :global(a) { color: var(--continuum-accent-primary, #6366f1); text-decoration: none; }
  .markdown-content :global(a:hover) { text-decoration: underline; }
  .markdown-content :global(hr) { border: none; border-top: 1px solid var(--continuum-border, #334155); margin: 1em 0; }

  .binary-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--continuum-space-md, 16px);
    padding: var(--continuum-space-xl, 48px);
    color: var(--continuum-text-muted, #94a3b8);
  }

  /* Footer */
  .modal-footer {
    display: flex;
    align-items: center;
    gap: var(--continuum-space-md, 16px);
    padding: var(--continuum-space-sm, 8px) var(--continuum-space-lg, 24px);
    border-top: 1px solid var(--continuum-border, #334155);
    flex-shrink: 0;
  }
  .action-btn {
    background: var(--continuum-accent-primary, #6366f1);
    color: #fff;
    border: none;
    padding: 6px 16px;
    border-radius: var(--continuum-radius-sm, 4px);
    cursor: pointer;
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }
  .action-btn:hover { opacity: 0.9; }
  .footer-meta {
    color: var(--continuum-text-muted, #94a3b8);
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }
</style>
