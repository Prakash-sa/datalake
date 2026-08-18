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

/** One frame from a streaming model pull. */
export type PullEvent =
  | {
      event: 'progress';
      model: string;
      status: string;
      completed: number;
      total: number;
      percent: number | null;
    }
  | { event: 'done'; model: string }
  | { event: 'error'; code: string; error: string; actionable?: boolean };

/**
 * Pull a model, reporting progress as it downloads.
 *
 * Uses the streaming endpoint directly rather than IPC: a pull can take many
 * minutes, and a single buffered response would leave the user with no signal.
 */
export async function streamModelPull(
  name: string,
  apiUrl: string,
  onEvent: (event: PullEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const response = await fetch(`${apiUrl}/models/pull/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ name }),
      signal,
    });

    if (!response.ok || !response.body) {
      onEvent({
        event: 'error',
        code: 'model_unavailable',
        error: `Backend returned ${response.status}`,
      });
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf('\n\n');
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        for (const line of frame.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          try {
            onEvent(JSON.parse(line.slice(6)) as PullEvent);
          } catch {
            // Skip an unparseable frame rather than aborting the pull.
          }
        }
        boundary = buffer.indexOf('\n\n');
      }
    }
  } catch (error) {
    if ((error as Error).name === 'AbortError') {
      onEvent({ event: 'error', code: 'cancelled', error: 'Download cancelled' });
      return;
    }
    onEvent({
      event: 'error',
      code: 'internal_error',
      error: error instanceof Error ? error.message : 'Download failed',
    });
  }
}
