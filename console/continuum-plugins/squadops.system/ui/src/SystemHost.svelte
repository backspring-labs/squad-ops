<svelte:options customElement="squadops-system-host" />

<script>
  // The machine the deploy runs on (#2204b), from GET /health/host. The runtime API decides each
  // reading's state against the project's limits (`verdicts`); this panel only colours it. A
  // reading the API could not take shows as unknown, never as healthy, and so does every verdict
  // when the API is older than the console (the two images are rebuilt separately).
  import { onMount, onDestroy } from 'svelte';

  let reading = $state(null);
  let loading = $state(true);
  let pollTimer = $state(null);

  async function fetchHost() {
    try {
      const resp = await fetch('/api/health/host');
      reading = resp.ok ? await resp.json() : null;
    } catch {
      reading = null;
    }
    loading = false;
  }

  onMount(() => {
    fetchHost();
    pollTimer = setInterval(fetchHost, 15000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  const GIB = 2 ** 30;

  function gib(bytes) {
    return bytes == null ? 'unknown' : `${(bytes / GIB).toFixed(1)} GiB`;
  }

  function gb(bytes) {
    return bytes == null ? 'unknown' : `${Math.round(bytes / 1e9)} GB`;
  }

  function num(value, unit, digits = 0) {
    return value == null ? 'unknown' : `${Number(value).toFixed(digits)}${unit}`;
  }

  // The API's states, to the panel's colours: below a floor or past the critical limit is
  // critical, past the warning is a warning, and an unread value is unknown.
  function tone(state) {
    if (state === 'ok') return 'ok';
    if (state === 'warn') return 'warn';
    if (state === 'below_floor' || state === 'critical') return 'critical';
    return 'unknown';
  }

  function engineLine(engine) {
    if (engine.loaded == null) return `${engine.engine}: could not be read`;
    if (engine.loaded.length === 0) return `${engine.engine}: no model loaded`;
    return `${engine.engine}: ${engine.loaded.join(', ')}`;
  }

  function boxLine(box) {
    if (box == null) return 'could not be read';
    const holder = box.lease ? `held by ${box.lease.holder}` : 'not held';
    const until = box.lease?.expires_at ? ` until ${new Date(box.lease.expires_at).toLocaleString()}` : '';
    const models = box.quiet
      ? 'only the deploy’s models resident'
      : 'a model the deploy does not declare is resident';
    return `${holder}${until} · ${models}`;
  }

  // Grafana serves on the deploy's host at :3000; the Spark health dashboard has this panel's
  // readings over time, with the same limits drawn as lines.
  const grafanaUrl = `${location.protocol}//${location.hostname}:3000/d/spark-health?from=now-6h&to=now`;
</script>

<div class="system-host">
  <div class="header">
    <h3 class="title">Host</h3>
    <a class="grafana" href={grafanaUrl} target="_blank" rel="noopener">Open in Grafana</a>
  </div>

  {#if loading}
    <div class="muted">Reading the host...</div>
  {:else if !reading}
    <div class="muted">The host could not be read</div>
  {:else}
    {@const host = reading.host}
    {@const v = reading.verdicts ?? {}}
    {@const limits = reading.limits ?? {}}
    <div class="rows">
      <div class="row">
        <span class="key">Memory</span>
        <span class="val {tone(v.memory?.state)}">
          {gib(host.memory_available_bytes)} available of {gib(host.memory_total_bytes)}
        </span>
        <span class="limit">
          {#if v.memory}floor {gib(v.memory.floor_bytes)} {v.memory.floor === 'before_load' ? 'before an engine loads' : 'with an engine loaded'}{/if}
        </span>
      </div>
      <div class="row">
        <span class="key">Swap</span>
        <span class="val">{gib(host.swap_used_bytes)} used</span>
        <span class="limit">
          memory stalls {host.memory_pressure_stalled_ratio == null ? 'unknown' : `${(host.memory_pressure_stalled_ratio * 100).toFixed(2)}% of the last 5 min`}
        </span>
      </div>
      <div class="row">
        <span class="key">Disk /</span>
        <span class="val {tone(v.disk?.state)}">{gb(host.disk_root_available_bytes)} available</span>
        <span class="limit">{#if v.disk}floor {gb(v.disk.floor_bytes)}{/if}</span>
      </div>
      <div class="row">
        <span class="key">Board</span>
        <span class="val {tone(v.board_temperature?.state)}">{num(host.temperature_max_celsius, ' °C')} hottest zone</span>
        <span class="limit">
          {#if limits.board_temperature_critical_celsius != null}warning {limits.board_temperature_warn_celsius} °C · critical {limits.board_temperature_critical_celsius} °C{/if}
        </span>
      </div>
      <div class="row">
        <span class="key">GPU</span>
        <span class="val">
          {num(host.gpu_utilization_percent, '%')} · {num(host.gpu_power_watts, ' W', 1)} · {num(host.gpu_temperature_celsius, ' °C')}
        </span>
        <span class="limit">load {num(host.load_one_minute, '', 2)} (1 min)</span>
      </div>
      <div class="row">
        <span class="key">Engines</span>
        <span class="val">
          {#if reading.engines == null}
            could not be read
          {:else}
            {#each reading.engines as engine}
              <div>{engineLine(engine)}</div>
            {/each}
          {/if}
        </span>
      </div>
      <div class="row">
        <span class="key">Box</span>
        <span class="val">{boxLine(reading.box)}</span>
      </div>
    </div>
  {/if}
</div>

<style>
  .system-host {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: var(--continuum-space-md, 16px);
  }

  .title {
    font-size: var(--continuum-font-size-md, 1rem);
    font-weight: 600;
    margin: 0;
  }

  .grafana {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-accent-primary, #60a5fa);
  }

  .rows {
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-md, 8px);
    padding: var(--continuum-space-md, 16px);
  }

  .row {
    display: grid;
    grid-template-columns: 80px minmax(0, 1fr) minmax(0, 1fr);
    gap: var(--continuum-space-sm, 8px);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    padding: 4px 0;
  }

  .key {
    color: var(--continuum-text-muted, #94a3b8);
  }

  .val {
    font-family: var(--continuum-font-mono, monospace);
  }

  .limit {
    color: var(--continuum-text-muted, #94a3b8);
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }

  .ok {
    color: var(--continuum-accent-success, #22c55e);
  }

  .warn {
    color: var(--continuum-accent-warning, #f59e0b);
  }

  .critical {
    color: var(--continuum-accent-danger, #ef4444);
  }

  .unknown {
    color: var(--continuum-text-muted, #94a3b8);
    font-style: italic;
  }

  .muted {
    color: var(--continuum-text-muted, #94a3b8);
    padding: var(--continuum-space-md, 16px);
  }

  @media (max-width: 640px) {
    .row {
      grid-template-columns: 1fr;
    }
  }
</style>
