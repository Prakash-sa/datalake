import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import DiagnosticsView from '@/app/components/DiagnosticsView';

const GB = 1024 ** 3;

function diagnostics(overrides: Record<string, unknown> = {}) {
  return {
    status: 'success',
    runtime: { python_version: '3.12.13', platform: 'macOS-26.5-arm64' },
    paths: {
      app_data_dir: '/data',
      app_db_path: '/data/app.db',
      chroma_path: '/data/chroma',
    },
    disk: { total_bytes: 100 * GB, used_bytes: 50 * GB, free_bytes: 50 * GB },
    models: {
      ollama_url: 'http://127.0.0.1:11434',
      embedding_model: 'qwen3-embedding:0.6b',
      llm_model: 'qwen3:4b',
    },
    storage: {
      status: 'ready',
      provider: 'chroma',
      persistent_path: '/data/chroma',
      writable: true,
    },
    stats: {
      documents_indexed: 3,
      queries_processed: 7,
      errors: 0,
      total_documents: 42,
      catalog_documents: 3,
      timestamp: '2026-01-01T00:00:00',
    },
    ...overrides,
  };
}

function mockBackend({
  diag = diagnostics(),
  modelsOk = true,
  missing = [] as string[],
} = {}) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (String(url).includes('/readiness')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            status: 'ready',
            capabilities: {
              embeddings: {
                status: 'ready',
                provider: 'local',
                model: 'all-MiniLM-L6-v2',
                dimensions: 384,
                requires_external_software: false,
              },
              ollama: { status: modelsOk ? 'ready' : 'error' },
            },
          }),
        };
      }
      if (String(url).includes('/models')) {
        return {
          ok: modelsOk,
          status: modelsOk ? 200 : 503,
          json: async () => ({
            status: modelsOk ? 'ready' : 'error',
            ollama_url: 'http://127.0.0.1:11434',
            models: [],
            required_models: ['qwen3:4b'],
            missing_models: missing,
          }),
        };
      }
      return { ok: true, status: 200, json: async () => diag };
    }),
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('DiagnosticsView', () => {
  it('reports index counts', async () => {
    mockBackend();
    render(<DiagnosticsView apiUrl="http://api" />);

    expect(await screen.findByText('42')).toBeTruthy();
    expect(screen.getByText('7')).toBeTruthy();
  });

  it('reports runtime and paths', async () => {
    mockBackend();
    render(<DiagnosticsView apiUrl="http://api" />);

    expect(await screen.findByText('3.12.13')).toBeTruthy();
    expect(screen.getByText('/data/app.db')).toBeTruthy();
  });

  it('warns when free disk space is low', async () => {
    mockBackend({
      diag: diagnostics({
        disk: { total_bytes: 100 * GB, used_bytes: 99.5 * GB, free_bytes: 0.5 * GB },
      }),
    });
    render(<DiagnosticsView apiUrl="http://api" />);

    expect(await screen.findByText(/Low free space/i)).toBeTruthy();
  });

  it('does not warn when disk space is adequate', async () => {
    mockBackend();
    render(<DiagnosticsView apiUrl="http://api" />);

    await screen.findByText('42');
    expect(screen.queryByText(/Low free space/i)).toBeNull();
  });

  it('reports missing models', async () => {
    mockBackend({ missing: ['qwen3:4b'] });
    render(<DiagnosticsView apiUrl="http://api" />);

    expect(await screen.findByText(/Missing: qwen3:4b/)).toBeTruthy();
  });

  it('reports an unreachable Ollama without implying search is broken', async () => {
    mockBackend({ modelsOk: false });
    render(<DiagnosticsView apiUrl="http://api" />);

    expect(await screen.findByText(/Search still works; written answers do not/i)).toBeTruthy();
  });

  it('reports the embedding provider and that it needs nothing external', async () => {
    mockBackend();
    render(<DiagnosticsView apiUrl="http://api" />);

    expect(await screen.findByText('all-MiniLM-L6-v2')).toBeTruthy();
    expect(screen.getByText('384')).toBeTruthy();
    expect(screen.getByText(/entirely on this machine/i)).toBeTruthy();
  });

  it('reports a non-writable vector store', async () => {
    mockBackend({
      diag: diagnostics({
        storage: {
          status: 'error',
          provider: 'chroma',
          persistent_path: '/data/chroma',
          writable: false,
          error: 'Read-only file system',
        },
      }),
    });
    render(<DiagnosticsView apiUrl="http://api" />);

    expect(await screen.findByText('Read-only file system')).toBeTruthy();
  });

  it('surfaces a failed diagnostics request', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        status: 503,
        json: async () => ({ detail: 'RAG service unavailable' }),
      })),
    );
    render(<DiagnosticsView apiUrl="http://api" />);

    expect(await screen.findByText('RAG service unavailable')).toBeTruthy();
  });
});
