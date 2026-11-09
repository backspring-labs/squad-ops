// The runtime API's error body, `{"detail": {"error": {code, message, details}}}` (built by
// `squadops.api.errors`; the standard is docs/architecture/api-route-lanes.md), read from a
// response's text. Shared by the plugins that say a refusal in the API's own words; each plugin's
// build bundles it.

/** `{code, message, details}` from the body's text, or the text itself when it isn't that shape. */
export function errorFromText(text, status) {
  try {
    const body = JSON.parse(text);
    const err = body?.detail?.error ?? body?.error;
    if (err && typeof err === 'object') {
      return { code: err.code ?? null, message: err.message ?? text, details: err.details ?? null };
    }
    if (typeof body?.detail === 'string') return { code: null, message: body.detail, details: null };
  } catch {
    // not JSON: the text is the message
  }
  return { code: null, message: text || `the API answered ${status}`, details: null };
}
