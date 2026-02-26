<!--
  ProfileParamRenderer — dynamic form fields from cycle request profile prompts (SIP-0074 §3.2).

  Type inference rules (§5.8):
  1. If meta.type is set explicitly, use it
  2. If meta.choices has entries, infer "choice"
  3. If the default value is boolean, infer "bool"
  4. Otherwise, infer "text"
-->
<script>
  let { prompts = {}, defaults = {}, values = {}, onChange = null } = $props();

  function inferType(key, meta) {
    if (meta.type) return meta.type;
    if (meta.choices?.length > 0) return 'choice';
    if (typeof defaults[key] === 'boolean') return 'bool';
    return 'text';
  }

  function handleChange(key, value) {
    onChange?.({ ...values, [key]: value });
  }
</script>

{#if Object.keys(prompts).length > 0}
  <div class="param-fields">
    {#each Object.entries(prompts) as [key, meta]}
      {@const fieldType = inferType(key, meta)}
      <div class="field-group">
        <label class="field-label" for="param-{key}">
          {meta.label}
          {#if meta.required}
            <span class="required-marker">*</span>
          {/if}
        </label>
        {#if meta.help_text}
          <span class="field-help">{meta.help_text}</span>
        {/if}

        {#if fieldType === 'choice'}
          <select
            id="param-{key}"
            class="field-select"
            value={values[key] ?? defaults[key] ?? ''}
            onchange={(e) => handleChange(key, e.target.value)}
          >
            {#each meta.choices as choice}
              <option value={choice}>{choice}</option>
            {/each}
          </select>
        {:else if fieldType === 'bool'}
          <label class="field-checkbox-label">
            <input
              id="param-{key}"
              type="checkbox"
              checked={values[key] ?? defaults[key] ?? false}
              onchange={(e) => handleChange(key, e.target.checked)}
            />
            <span class="checkbox-text">{values[key] ?? defaults[key] ? 'Yes' : 'No'}</span>
          </label>
        {:else if fieldType === 'text'}
          <input
            id="param-{key}"
            type="text"
            class="field-input"
            value={values[key] ?? defaults[key] ?? ''}
            oninput={(e) => handleChange(key, e.target.value)}
            placeholder={meta.help_text || ''}
          />
        {:else}
          <div class="field-readonly">
            <span class="readonly-icon">?</span>
            <span class="readonly-value">{values[key] ?? defaults[key] ?? '--'}</span>
            {#if meta.required}
              <span class="readonly-error">Unsupported prompt type for required field: {key}</span>
            {/if}
          </div>
        {/if}
      </div>
    {/each}
  </div>
{/if}

<style>
  .param-fields {
    display: flex;
    flex-direction: column;
    gap: var(--continuum-space-md, 16px);
  }

  .field-group {
    display: flex;
    flex-direction: column;
    gap: var(--continuum-space-xs, 4px);
  }

  .field-label {
    font-size: var(--continuum-font-size-sm, 0.875rem);
    font-weight: 600;
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .required-marker {
    color: var(--continuum-accent-danger, #ef4444);
    margin-left: 2px;
  }

  .field-help {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
  }

  .field-input,
  .field-select {
    padding: var(--continuum-space-sm, 8px);
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    color: var(--continuum-text-primary, #e2e8f0);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    outline: none;
  }

  .field-input:focus,
  .field-select:focus {
    border-color: var(--continuum-accent-primary, #6366f1);
  }

  .field-checkbox-label {
    display: flex;
    align-items: center;
    gap: var(--continuum-space-sm, 8px);
    cursor: pointer;
  }

  .checkbox-text {
    font-size: var(--continuum-font-size-sm, 0.875rem);
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .field-readonly {
    display: flex;
    align-items: center;
    gap: var(--continuum-space-sm, 8px);
    padding: var(--continuum-space-sm, 8px);
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  .readonly-icon {
    color: var(--continuum-accent-warning, #f59e0b);
    font-weight: 700;
  }

  .readonly-value {
    color: var(--continuum-text-muted, #94a3b8);
  }

  .readonly-error {
    color: var(--continuum-accent-danger, #ef4444);
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }
</style>
