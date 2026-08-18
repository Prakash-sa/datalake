import type {
  CancelStream,
  StreamEvent,
  StreamQueryRequest,
} from '@/types/electron';

/**
 * Start a streaming query and return a function that cancels it.
 *
 * In the desktop shell this goes through typed IPC, so the renderer never holds
 * the backend token or a general-purpose HTTP client. In a browser it falls
 * back to reading the SSE response directly, which keeps `next dev` usable.
 */
export async function streamQuery(
  request: StreamQueryRequest,
  onEvent: (event: StreamEvent) => void,
  apiUrl: string,
): Promise<CancelStream> {
  const desktop = typeof window !== 'undefined' ? window.desktop : undefined;
  if (desktop?.streamQuery) {
    return desktop.streamQuery(request, onEvent);
  }
  return browserStreamQuery(request, onEvent, apiUrl);
}

async function browserStreamQuery(
  request: StreamQueryRequest,
  onEvent: (event: StreamEvent) => void,
  apiUrl: string,
): Promise<CancelStream> {
  const controller = new AbortController();

  const run = async () => {
    try {
      const response = await fetch(`${apiUrl}/query/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          query: request.query,
          k: request.k ?? 5,
          min_score: request.minScore ?? 0,
        }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        onEvent({
          event: 'error',
          code: 'retrieval_failed',
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

        // A network chunk can split an SSE frame, so only complete frames
        // (terminated by a blank line) are dispatched.
        let boundary = buffer.indexOf('\n\n');
        while (boundary !== -1) {
          const frame = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          for (const line of frame.split('\n')) {
            if (!line.startsWith('data: ')) continue;
            try {
              onEvent(JSON.parse(line.slice(6)) as StreamEvent);
            } catch {
              // Skip an unparseable frame rather than ending the stream.
            }
          }
          boundary = buffer.indexOf('\n\n');
        }
      }
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        onEvent({ event: 'error', code: 'cancelled', error: 'Generation cancelled' });
        return;
      }
      onEvent({
        event: 'error',
        code: 'internal_error',
        error: error instanceof Error ? error.message : 'Stream failed',
      });
    }
  };

  void run();
  return () => controller.abort();
}
