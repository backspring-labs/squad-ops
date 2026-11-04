// A selection one view hands to another in a different perspective.
//
// The plugins talk through window `CustomEvent`s (`squadops:select-project`,
// `squadops:select-campaign`), and the pinned shell (Continuum v1.0.2) mounts only the open
// perspective's panels (docs/architecture/console-fit-check-2-6.md §1). So an event dispatched
// for a panel in another perspective reaches no listener: the panel isn't mounted yet. Two parts
// close that, with no shell change:
//   - `announce` records the selection on `window` before dispatching it, and the receiving
//     panel takes it on mount (`takeAnnounced`), as well as listening for the event while mounted;
//   - `openNav` opens the other perspective the way the person would, by clicking the shell's own
//     left-nav entry. The shell has no API for this (it has no router: the fit check's §1 row 3),
//     so this reads the shell's rendered nav (`.nav-item` buttons, labelled by their plugin's nav
//     contribution) and answers false when it finds none, for the caller to say so.

const STORE = '__SQUADOPS_SELECTIONS__';

/** Records `detail` as the latest `name` selection, then dispatches it. */
export function announce(name, detail, win = globalThis) {
  win[STORE] = { ...(win[STORE] ?? {}), [name]: detail };
  if (typeof win.dispatchEvent === 'function' && typeof win.CustomEvent === 'function') {
    win.dispatchEvent(new win.CustomEvent(name, { detail }));
  }
}

/** The latest `name` selection not yet taken, or null; taking it clears it. */
export function takeAnnounced(name, win = globalThis) {
  const held = win[STORE]?.[name];
  if (held === undefined) return null;
  const { [name]: _taken, ...rest } = win[STORE];
  win[STORE] = rest;
  return held;
}

/** Clicks the shell's left-nav entry labelled `label`; false when the shell shows none. */
export function openNav(label, doc = globalThis.document) {
  if (!doc?.querySelectorAll) return false;
  const entry = [...doc.querySelectorAll('.nav-item')].find((el) => el.textContent.trim() === label);
  if (!entry) return false;
  entry.click();
  return true;
}
