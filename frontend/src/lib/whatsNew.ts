/**
 * "What's new" — a release note shown once, then never again.
 *
 * Deliberately client-side (localStorage), like the nav-tab preference: it's a
 * per-browser "you've read this", not account state, so it needs no table, no
 * migration and no request. The cost is that the same person on a second device
 * sees it once more there — acceptable for a note whose whole job is to be read.
 *
 * To announce the next release: bump `CURRENT_RELEASE` and rewrite the
 * `whatsNew.*` strings in both locales. Everyone sees the new note once.
 */

/** Bump this to show a fresh note. Anything else stored means "not seen yet". */
export const CURRENT_RELEASE = "2026-08-17-tests";

const KEY = "whats_new_seen";

export function seenRelease(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    // Private mode: treat as unseen. Showing twice beats never showing.
    return null;
  }
}

export function shouldShowWhatsNew(): boolean {
  return seenRelease() !== CURRENT_RELEASE;
}

export function markWhatsNewSeen(): void {
  try {
    localStorage.setItem(KEY, CURRENT_RELEASE);
  } catch {
    /* nothing to do — it'll just show again next time */
  }
}
