/** Mirrors `rag_backend.domain.jobs.JobStatus`. */
export const JOB_STATUSES = [
  'queued',
  'parsing',
  'chunking',
  'embedding',
  'committing',
  'complete',
  'failed',
  'cancelled',
] as const;

export type JobStatus = (typeof JOB_STATUSES)[number];

export type IngestionJob = {
  id: string;
  source_path: string;
  document_id: string | null;
  status: JobStatus;
  error_code: string | null;
  error: string | null;
  attempts: number;
  chunks_total: number;
  chunks_done: number;
  force_reindex: boolean;
  created_at: string;
  updated_at: string;
  finished_at: string | null;
};

const PIPELINE: JobStatus[] = [
  'queued',
  'parsing',
  'chunking',
  'embedding',
  'committing',
  'complete',
];

export const TERMINAL_STATUSES: JobStatus[] = ['complete', 'failed', 'cancelled'];

export function isTerminal(status: JobStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

/**
 * Completion fraction for the progress bar.
 *
 * Failed and cancelled report 0, matching the backend: a stalled bar is more
 * misleading than an empty one.
 */
export function progressFraction(status: JobStatus): number {
  if (status === 'complete') return 1;
  if (status === 'failed' || status === 'cancelled') return 0;
  const index = PIPELINE.indexOf(status);
  return index < 0 ? 0 : index / (PIPELINE.length - 1);
}

/** Short, human-facing explanation for a structured backend error code. */
export function explainErrorCode(code: string | null): string | null {
  switch (code) {
    case 'unsupported_format':
      return 'This file type or path cannot be read.';
    case 'embedding_failed':
      return 'Embedding failed — check that Ollama is running and the model is pulled.';
    case 'model_unavailable':
      return 'Ollama is unreachable. Start it, then retry.';
    case 'no_extractable_text':
      return 'No readable text was found in this document.';
    case 'cancelled':
      return 'Stopped before finishing.';
    case 'duplicate':
      return 'Already indexed; nothing was re-embedded.';
    default:
      return null;
  }
}
