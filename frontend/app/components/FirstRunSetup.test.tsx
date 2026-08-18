import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import FirstRunSetup from '@/app/components/FirstRunSetup';

const PROFILES = {
  light: { llm_model: 'qwen3:1.7b', embedding_model: 'qwen3-embedding:0.6b' },
  balanced: { llm_model: 'qwen3:4b', embedding_model: 'qwen3-embedding:0.6b' },
};

/** Routes /models and /settings to canned payloads. */
function mockBackend({
  modelsOk = true,
  status = 'ready',
  missing = [] as string[],
} = {}) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (String(url).includes('/models')) {
        return {
          ok: modelsOk,
          status: modelsOk ? 200 : 503,
          json: async () => ({
            status,
            ollama_url: 'http://127.0.0.1:11434',
            models: [],
            required_models: ['qwen3:4b'],
            missing_models: missing,
          }),
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({
          status: 'success',
          settings: {
            ollama_url: 'http://127.0.0.1:11434',
            embedding_model: 'qwen3-embedding:0.6b',
            llm_model: 'qwen3:4b',
            temperature: 0.1,
            model_profiles: PROFILES,
          },
        }),
      };
    }),
  );
}

function renderSetup() {
  return render(
    <FirstRunSetup apiUrl="http://api" onComplete={() => {}} onSkip={() => {}} />,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('FirstRunSetup', () => {
  it('reports when Ollama cannot be reached', async () => {
    mockBackend({ modelsOk: false });
    renderSetup();

    expect(await screen.findByText(/Not reachable/i)).toBeTruthy();
    expect(screen.getByText(/ollama serve/)).toBeTruthy();
  });

  it('reports the endpoint once Ollama responds', async () => {
    mockBackend();
    renderSetup();

    expect(await screen.findByText(/Reachable at http:\/\/127\.0\.0\.1:11434/)).toBeTruthy();
  });

  it('offers the configured model profiles', async () => {
    mockBackend();
    renderSetup();

    expect(await screen.findByText('light')).toBeTruthy();
    expect(screen.getByText('balanced')).toBeTruthy();
  });

  it('lists missing models with a download control', async () => {
    mockBackend({ missing: ['qwen3:4b'] });
    renderSetup();

    // The model name also appears on the profile card, so target the
    // download row's <code> element specifically.
    const matches = await screen.findAllByText('qwen3:4b');
    expect(matches.some((el) => el.tagName === 'CODE')).toBe(true);
    expect(screen.getByText('Download')).toBeTruthy();
  });

  it('blocks continuing until every required model is present', async () => {
    mockBackend({ missing: ['qwen3:4b'] });
    renderSetup();

    const button = await screen.findByRole('button', { name: /Finish setup to continue/i });
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it('allows continuing once nothing is missing', async () => {
    mockBackend({ missing: [] });
    renderSetup();

    const button = await screen.findByRole('button', { name: /Start using the app/i });
    expect((button as HTMLButtonElement).disabled).toBe(false);
    expect(screen.getByText(/All required models are installed/i)).toBeTruthy();
  });

  it('always offers a way to skip', async () => {
    mockBackend({ missing: ['qwen3:4b'] });
    renderSetup();

    expect(await screen.findByText('Skip for now')).toBeTruthy();
  });
});
