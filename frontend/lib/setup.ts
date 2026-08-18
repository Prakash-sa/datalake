const DISMISS_KEY = 'rag.setupDismissed';

/**
 * Whether the user chose to skip first-run setup.
 *
 * Stored in localStorage rather than backend settings: this is a UI preference
 * about what to show, not part of the engine's configuration. Readiness itself
 * is always derived from the backend, so a dismissed setup still reappears if
 * models are later removed and the user clears the flag.
 */
export function isSetupDismissed(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return window.localStorage.getItem(DISMISS_KEY) === 'true';
  } catch {
    // Private mode or a blocked store; treat as not dismissed.
    return false;
  }
}

export function dismissSetup(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(DISMISS_KEY, 'true');
  } catch {
    // Nothing to do; setup will simply show again next launch.
  }
}

export function resetSetupDismissal(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(DISMISS_KEY);
  } catch {
    // Ignore.
  }
}
