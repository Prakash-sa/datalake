import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import type { IngestionJob } from '@/lib/jobs';
import ActivityView from '@/app/components/ActivityView';

function job(overrides: Partial<IngestionJob> = {}): IngestionJob {
  return {
    id: 'job_1',
    source_path: '/docs/report.pdf',
    document_id: null,
    status: 'queued',
    error_code: null,
    error: null,
    attempts: 0,
    chunks_total: 0,
    chunks_done: 0,
    force_reindex: false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    finished_at: null,
    ...overrides,
  };
}

function mockJobs(jobs: IngestionJob[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ status: 'success', jobs }),
    })),
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('ActivityView', () => {
  it('shows an empty state when no jobs exist', async () => {
    mockJobs([]);
    render(<ActivityView apiUrl="http://api" />);

    expect(await screen.findByText('No ingestion jobs yet')).toBeTruthy();
  });

  it('renders the file name and status of a running job', async () => {
    mockJobs([job({ status: 'embedding', chunks_total: 10, chunks_done: 4 })]);
    render(<ActivityView apiUrl="http://api" />);

    expect(await screen.findByText('report.pdf')).toBeTruthy();
    expect(screen.getByText('embedding')).toBeTruthy();
    expect(screen.getByText('4/10 chunks')).toBeTruthy();
  });

  it('offers cancel for a running job and not retry', async () => {
    mockJobs([job({ status: 'parsing' })]);
    render(<ActivityView apiUrl="http://api" />);

    expect(await screen.findByText('Cancel')).toBeTruthy();
    expect(screen.queryByText('Retry')).toBeNull();
  });

  it('offers retry for a failed job and not cancel', async () => {
    mockJobs([job({ status: 'failed', error_code: 'embedding_failed', error: 'boom' })]);
    render(<ActivityView apiUrl="http://api" />);

    expect(await screen.findByText('Retry')).toBeTruthy();
    expect(screen.queryByText('Cancel')).toBeNull();
  });

  it('translates a structured error code into an actionable sentence', async () => {
    mockJobs([job({ status: 'failed', error_code: 'embedding_failed', error: 'raw backend text' })]);
    render(<ActivityView apiUrl="http://api" />);

    // The hint replaces the raw message, but the code stays for support.
    expect(await screen.findByText(/check that Ollama is running/i)).toBeTruthy();
    expect(screen.getByText('embedding_failed')).toBeTruthy();
    expect(screen.queryByText('raw backend text')).toBeNull();
  });

  it('surfaces a backend failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        status: 503,
        json: async () => ({ detail: 'RAG service unavailable' }),
      })),
    );
    render(<ActivityView apiUrl="http://api" />);

    await waitFor(() => expect(screen.getByText('RAG service unavailable')).toBeTruthy());
  });
});
