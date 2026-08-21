export {};

export interface PerformanceMetrics {
  retrieval_time_seconds?: number | null;
  first_token_time_seconds?: number | null;
  generation_time_seconds?: number | null;
  total_time_seconds?: number | null;
  tokens_per_second?: number | null;
  generated_token_count?: number;
  context_document_count?: number;
  retrieved_document_count?: number;
  truncated_document_count?: number;
  answer_mode?: AnswerMode;
}

/** One frame from the backend's streaming query endpoint. */
export type StreamEvent =
  | {
      event: 'sources';
      documents: RetrievedDocument[];
      truncated_document_count: number;
      answer_mode?: AnswerMode;
      metrics?: PerformanceMetrics;
    }
  | { event: 'token'; text: string; first_token_time_seconds?: number }
  | {
      event: 'done';
      status: string;
      answer: string;
      retrieved_documents?: RetrievedDocument[];
      citations?: CitationReport;
      truncated_document_count?: number;
      processing_time_seconds?: number;
      code?: string;
      answer_mode?: AnswerMode;
      metrics?: PerformanceMetrics;
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
  answerMode?: AnswerMode;
}

export type AnswerMode = 'fast' | 'balanced' | 'deep';

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
        request: {
          message: string;
          conversationId?: string | null;
          k?: number;
          minScore?: number;
          answerMode?: AnswerMode;
        },
        onEvent: (event: import('@/lib/chat').ChatStreamEvent) => void,
      ) => Promise<CancelStream>;
    };
  }
}
