import type { CancelStream, CitationReport, RetrievedDocument } from '@/types/electron';

export type ChatStreamEvent =
  | { event: 'conversation'; conversation_id: string; title: string }
  | { event: 'sources'; documents: RetrievedDocument[]; truncated_document_count: number }
  | { event: 'token'; text: string }
  | {
      event: 'done';
      status: string;
      conversation_id: string;
      message_id: string;
      answer: string;
      retrieved_documents: RetrievedDocument[];
      citations: CitationReport;
      processing_time_seconds: number;
    }
  | { event: 'error'; code: string; error: string; actionable?: boolean };

export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: CitationReport;
  sources?: RetrievedDocument[];
  createdAt?: string;
  errorCode?: string | null;
  streaming?: boolean;
};

export type ConversationSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type ChatRequest = {
  message: string;
  conversationId?: string | null;
  k?: number;
  minScore?: number;
};

/**
 * Send one conversation turn and stream the reply.
 *
 * In the desktop shell this goes through typed IPC, so the renderer never holds
 * the backend token. In a browser it reads the SSE response directly, which
 * keeps `next dev` usable.
 */
export async function streamChat(
  request: ChatRequest,
  onEvent: (event: ChatStreamEvent) => void,
  apiUrl: string,
): Promise<CancelStream> {
  const desktop = typeof window !== 'undefined' ? window.desktop : undefined;
  if (desktop?.streamChat) {
    return desktop.streamChat(request, onEvent);
  }

  const controller = new AbortController();

  const run = async () => {
    try {
      const response = await fetch(`${apiUrl}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({
          message: request.message,
          conversation_id: request.conversationId ?? undefined,
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

        // A network chunk can split a frame, so only complete frames are sent on.
        let boundary = buffer.indexOf('\n\n');
        while (boundary !== -1) {
          const frame = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          for (const line of frame.split('\n')) {
            if (!line.startsWith('data: ')) continue;
            try {
              onEvent(JSON.parse(line.slice(6)) as ChatStreamEvent);
            } catch {
              // Skip a frame that will not parse rather than ending the turn.
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
        error: error instanceof Error ? error.message : 'Chat failed',
      });
    }
  };

  void run();
  return () => controller.abort();
}

/** Short, human explanation for a structured chat error. */
export function explainChatError(code: string | null | undefined): string | null {
  switch (code) {
    case 'model_unavailable':
      return 'No generation model is available. Add a local GGUF model or switch to Ollama in Settings; search still works without written answers.';
    case 'generation_timeout':
      return 'The model took too long. A smaller model such as qwen3:1.7b responds much faster on CPU.';
    case 'no_relevant_evidence':
      return 'Nothing in your library matched that question.';
    case 'cancelled':
      return 'Stopped.';
    case 'index_model_mismatch':
      return 'The index was built with a different embedding model. Rebuild it from Activity.';
    default:
      return null;
  }
}
