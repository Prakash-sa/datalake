import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import SettingsView from '@/app/components/SettingsView';

const SETTINGS = {
  ollama_url: 'http://127.0.0.1:11434',
  embedding_model: 'qwen3-embedding:0.6b',
  llm_model: 'qwen3:4b',
  temperature: 0.1,
  model_profiles: {
    light: { llm_model: 'qwen3:1.7b', embedding_model: 'qwen3-embedding:0.6b' },
    balanced: { llm_model: 'qwen3:4b', embedding_model: 'qwen3-embedding:0.6b' },
  },
};

function mockBackend({ missing = [] as string[] } = {}) {
  const calls: Array<{ url: string; body: unknown }> = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url: String(url), body: init?.body ? JSON.parse(String(init.body)) : null });
      if (String(url).includes('/models')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            status: 'ready',
            ollama_url: SETTINGS.ollama_url,
            models: [],
            required_models: ['qwen3:4b'],
            missing_models: missing,
          }),
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({ status: 'success', settings: SETTINGS }),
      };
    }),
  );
  return calls;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('SettingsView', () => {
  it('populates the form from saved settings', async () => {
    mockBackend();
    render(<SettingsView apiUrl="http://api" />);

    const url = (await screen.findByDisplayValue('http://127.0.0.1:11434')) as HTMLInputElement;
    expect(url.value).toBe('http://127.0.0.1:11434');
    expect(screen.getByDisplayValue('qwen3:4b')).toBeTruthy();
  });

  it('warns that changing the embedding model forces a reindex', async () => {
    mockBackend();
    render(<SettingsView apiUrl="http://api" />);

    expect(await screen.findByText(/requires reindexing every document/i)).toBeTruthy();
  });

  it('offers the configured profiles', async () => {
    mockBackend();
    render(<SettingsView apiUrl="http://api" />);

    expect(await screen.findByText('light')).toBeTruthy();
    expect(screen.getByText('balanced')).toBeTruthy();
  });

  it('lists missing models with a pull control', async () => {
    mockBackend({ missing: ['qwen3:4b'] });
    render(<SettingsView apiUrl="http://api" />);

    expect(await screen.findByText(/Pull qwen3:4b/)).toBeTruthy();
    expect(screen.getByText(/1 required model not installed/i)).toBeTruthy();
  });

  it('does not show the missing-model banner when nothing is missing', async () => {
    mockBackend();
    render(<SettingsView apiUrl="http://api" />);

    await screen.findByText('light');
    expect(screen.queryByText(/not installed/i)).toBeNull();
  });

  it('saves edited values and reports the restart requirement', async () => {
    const calls = mockBackend();
    render(<SettingsView apiUrl="http://api" />);

    const url = (await screen.findByDisplayValue('http://127.0.0.1:11434')) as HTMLInputElement;
    fireEvent.change(url, { target: { value: 'http://localhost:9999' } });
    fireEvent.click(screen.getByRole('button', { name: /Save settings/i }));

    await waitFor(() => expect(screen.getByText(/Restart the app/i)).toBeTruthy());
    const post = calls.find((c) => c.url.includes('/settings') && c.body);
    expect((post?.body as { ollama_url: string }).ollama_url).toBe('http://localhost:9999');
  });

  it('applying a profile fills the model fields without saving directly', async () => {
    mockBackend();
    render(<SettingsView apiUrl="http://api" />);

    fireEvent.click(await screen.findByText('light'));

    await waitFor(() => expect(screen.getByText(/review and save/i)).toBeTruthy());
  });

  it('surfaces a failed settings load', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        status: 503,
        json: async () => ({ detail: 'RAG service unavailable' }),
      })),
    );
    render(<SettingsView apiUrl="http://api" />);

    expect(await screen.findByText('RAG service unavailable')).toBeTruthy();
  });
});
