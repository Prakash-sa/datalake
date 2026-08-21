export {};

/** One frame from the backend's streaming query endpoint. */
export type StreamEvent =
  | {
      event: 'sources';
      documents: RetrievedDocument[];
      truncated_document_count: number;
    }
  | { event: 'token'; text: string }
  | {
      event: 'done';
      status: string;
      answer: string;
      retrieved_documents?: RetrievedDocument[];
      citations?: CitationReport;
      truncated_document_count?: number;
      processing_time_seconds?: number;
      code?: string;
    }
  | { event: 'error'; code: string; error: string; actionable?: boolean };

export interface RetrievedDocument {
  id: string;
  content: string;
  relevance_score: number;
  metadata?: Record<string, unknown>;
}

export interface CitationReport {
  valid: boolean;
  cited_indices: number[];
  cited_chunk_ids: string[];
  invalid_indices: number[];
  uncited_source_indices: number[];
  citation_count: number;
  supplied_source_count: number;
}

export interface StreamQueryRequest {
  query: string;
  k?: number;
  minScore?: number;
}

/** Called to cancel an in-flight stream. */
export type CancelStream = () => void;

declare global {
  interface Window {
    desktop?: {
      platform: string;
      isElectron: boolean;
      apiRequest: <T = unknown>(request: {
        path: string;
        method?: 'GET' | 'POST' | 'DELETE';
        body?: unknown;
      }) => Promise<{
        ok: boolean;
        status: number;
        data?: T;
        error?: string;
      }>;
      selectDocuments: () => Promise<string[]>;
      streamQuery: (
        request: StreamQueryRequest,
        onEvent: (event: StreamEvent) => void,
      ) => Promise<CancelStream>;
      streamChat: (
        request: { message: string; conversationId?: string | null; k?: number; minScore?: number },
        onEvent: (event: import('@/lib/chat').ChatStreamEvent) => void,
      ) => Promise<CancelStream>;
    };
  }
}
