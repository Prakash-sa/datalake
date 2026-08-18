export type ApiResult<T> = {
  ok: boolean;
  status: number;
  data?: T;
  error?: string;
};

export type HttpMethod = 'GET' | 'POST' | 'DELETE';

/**
 * Call the backend.
 *
 * In the desktop shell this goes through typed IPC so the renderer never holds
 * the bearer token; in a browser it falls back to a direct fetch.
 */
export async function apiRequest<T>(
  path: string,
  apiUrl: string,
  method: HttpMethod = 'GET',
  body?: unknown,
): Promise<ApiResult<T>> {
  const desktopApi = typeof window !== 'undefined' ? window.desktop?.apiRequest : undefined;
  if (desktopApi) {
    return desktopApi<T>({ path, method, body });
  }

  try {
    const response = await fetch(`${apiUrl}${path}`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const payload = await response.json().catch(() => undefined);
    return {
      ok: response.ok,
      status: response.status,
      data: payload as T | undefined,
      error: response.ok ? undefined : payload?.detail || 'Request failed',
    };
  } catch (error) {
    // A dead backend must not throw past the caller; surface it as a result.
    return {
      ok: false,
      status: 0,
      error: error instanceof Error ? error.message : 'Network error',
    };
  }
}

/** Human-readable byte size. */
export function formatBytes(bytes: number): string {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exponent;
  return `${value >= 10 || exponent === 0 ? Math.round(value) : value.toFixed(1)} ${units[exponent]}`;
}

/** Short relative time, e.g. "3m ago". */
export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '—';

  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}
