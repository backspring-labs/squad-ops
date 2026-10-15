// The runtime API pages its lists (#1891, #1976): `limit` (at most 500) and `offset`, and a full
// page means there may be more. A view that needs the whole list asks page by page until a short
// page ends it. Shared by the plugins that read paged lists; each plugin's build bundles it, and
// the console image installs only the `squadops.*` plugins.

export const PAGE_LIMIT = 500;

// Every item of the list at `url`, or the first refusal: `{ ok, status, items }`.
export async function fetchAllPages(apiFetch, url) {
  const items = [];
  const join = url.includes('?') ? '&' : '?';
  for (let offset = 0; ; offset += PAGE_LIMIT) {
    const resp = await apiFetch(`${url}${join}limit=${PAGE_LIMIT}&offset=${offset}`);
    if (!resp.ok) return { ok: false, status: resp.status, items };
    const page = await resp.json();
    items.push(...page);
    if (page.length < PAGE_LIMIT) return { ok: true, status: resp.status, items };
  }
}
