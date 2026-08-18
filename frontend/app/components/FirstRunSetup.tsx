'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Download,
  Loader2,
  RefreshCw,
  Sparkles,
  XCircle,
} from 'lucide-react';
import { apiRequest, formatBytes, streamModelPull, type PullEvent } from '@/lib/api';
import type {
  EmbeddingsCapability,
  ModelListResponse,
  Readiness,
  RuntimeSettings,
  SettingsResponse,
} from '@/lib/types';

type PullState = {
  status: string;
  percent: number | null;
  completed: number;
  total: number;
  done: boolean;
  error: string | null;
};

export default function FirstRunSetup({
  apiUrl,
  onComplete,
  onSkip,
}: {
  apiUrl: string;
  onComplete: () => void;
  onSkip: () => void;
}) {
  const [models, setModels] = useState<ModelListResponse | null>(null);
  const [settings, setSettings] = useState<RuntimeSettings | null>(null);
  const [profile, setProfile] = useState<string | null>(null);
  const [embeddings, setEmbeddings] = useState<EmbeddingsCapability | null>(null);
  const [checking, setChecking] = useState(true);
  const [pulls, setPulls] = useState<Record<string, PullState>>({});
  const abortRef = useRef<AbortController | null>(null);

  const check = useCallback(async () => {
    setChecking(true);
    const [modelList, settingsResponse, readiness] = await Promise.all([
      apiRequest<ModelListResponse>('/models', apiUrl),
      apiRequest<SettingsResponse>('/settings', apiUrl),
      apiRequest<Readiness>('/readiness', apiUrl),
    ]);
    setEmbeddings(readiness.data?.capabilities?.embeddings ?? null);
    // A failed listing means Ollama is unreachable, which is step one's whole
    // question — so it is state, not an error banner.
    setModels(modelList.ok ? (modelList.data ?? null) : null);
    if (settingsResponse.ok && settingsResponse.data) {
      setSettings(settingsResponse.data.settings);
    }
    setChecking(false);
  }, [apiUrl]);

  useEffect(() => {
    void check();
  }, [check]);

  // Abandon any in-flight download if the user leaves setup.
  useEffect(() => () => abortRef.current?.abort(), []);

  const ollamaReachable = models !== null && models.status !== 'error';
  const missing = models?.missing_models ?? [];
  // Embeddings are the only hard requirement. Ollama adds generated prose;
  // without it the app still imports, searches, and cites.
  const embeddingsReady = embeddings?.status === 'ready';
  const generationReady = ollamaReachable && missing.length === 0;
  const canContinue = embeddingsReady;

  const applyProfile = async (name: string) => {
    const chosen = settings?.model_profiles[name];
    if (!chosen) return;
    setProfile(name);
    await apiRequest('/settings', apiUrl, 'POST', {
      llm_model: chosen.llm_model,
      embedding_model: chosen.embedding_model,
    });
    await check();
  };

  const download = async (name: string) => {
    const controller = new AbortController();
    abortRef.current = controller;

    setPulls((current) => ({
      ...current,
      [name]: { status: 'starting', percent: null, completed: 0, total: 0, done: false, error: null },
    }));

    const onEvent = (event: PullEvent) => {
      setPulls((current) => {
        const existing = current[name];
        if (event.event === 'progress') {
          return {
            ...current,
            [name]: {
              status: event.status,
              percent: event.percent,
              completed: event.completed,
              total: event.total,
              done: false,
              error: null,
            },
          };
        }
        if (event.event === 'done') {
          return { ...current, [name]: { ...existing, status: 'complete', done: true } };
        }
        return { ...current, [name]: { ...existing, error: event.error, done: true } };
      });
    };

    await streamModelPull(name, apiUrl, onEvent, controller.signal);
    abortRef.current = null;
    await check();
  };

  const cancelDownloads = () => abortRef.current?.abort();

  const stepClass = (active: boolean) =>
    `rounded-md border p-5 ${active ? 'border-cyan-800 bg-zinc-900' : 'border-zinc-800 bg-zinc-900/60'}`;

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="text-center">
        <Sparkles className="mx-auto mb-3 h-8 w-8 text-cyan-300" />
        <h2 className="text-2xl font-semibold text-white">Set up your local RAG engine</h2>
        <p className="mt-2 text-sm text-zinc-400">
          Everything runs on this machine. Documents and answers never leave it.
        </p>
      </div>

      {/* Search engine — bundled, so this is normally already satisfied */}
      <div className={stepClass(!embeddingsReady)}>
        <h3 className="flex items-center gap-2 font-medium text-white">
          {checking ? (
            <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />
          ) : embeddingsReady ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-300" />
          ) : (
            <XCircle className="h-4 w-4 text-red-300" />
          )}
          Search engine
        </h3>
        <p className="mt-1 text-sm text-zinc-400">
          {checking
            ? 'Checking the bundled embedding model…'
            : embeddingsReady
              ? `Ready — ${embeddings?.model} runs on this machine, no install needed.`
              : 'The bundled embedding model could not be loaded.'}
        </p>
      </div>

      {/* Optional — Ollama, for generated answers */}
      <div className={stepClass(!ollamaReachable)}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="flex items-center gap-2 font-medium text-white">
              {checking ? (
                <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />
              ) : ollamaReachable ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-300" />
              ) : (
                <XCircle className="h-4 w-4 text-red-300" />
              )}
              Ollama <span className="text-xs font-normal text-zinc-500">optional</span>
            </h3>
            <p className="mt-1 text-sm text-zinc-400">
              {checking
                ? 'Checking for a local Ollama daemon…'
                : ollamaReachable
                  ? `Reachable at ${models?.ollama_url}`
                  : 'Not installed. Search works without it; add it for written answers.'}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void check()}
            className="inline-flex min-h-10 shrink-0 items-center gap-2 rounded-md border border-zinc-700 px-3 py-2 text-sm text-zinc-300 transition hover:border-zinc-600 hover:text-white"
          >
            <RefreshCw className="h-4 w-4" />
            Re-check
          </button>
        </div>
        {!checking && !ollamaReachable && (
          <p className="mt-3 rounded-md border border-zinc-800 bg-zinc-950 p-3 text-xs text-zinc-400">
            Download Ollama from ollama.com, then run <code className="text-zinc-300">ollama serve</code>.
          </p>
        )}
      </div>

      {/* Step 2 — profile */}
      <div className={stepClass(ollamaReachable && missing.length > 0)}>
        <h3 className="font-medium text-white">Choose a model profile</h3>
        <p className="mt-1 text-sm text-zinc-400">
          Larger models answer better but need more memory.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {Object.entries(settings?.model_profiles ?? {}).map(([name, option]) => (
            <button
              key={name}
              type="button"
              disabled={!ollamaReachable}
              onClick={() => void applyProfile(name)}
              className={`rounded-md border p-3 text-left transition disabled:opacity-50 ${
                profile === name ? 'border-cyan-500 bg-cyan-950/20' : 'border-zinc-700 hover:border-cyan-600'
              }`}
            >
              <div className="font-medium capitalize text-white">{name}</div>
              <div className="mt-1 text-xs text-zinc-400">{option.llm_model}</div>
              <div className="text-xs text-zinc-500">{option.embedding_model}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Step 3 — download */}
      <div className={stepClass(ollamaReachable && missing.length > 0)}>
        <h3 className="flex items-center gap-2 font-medium text-white">
          {generationReady && <CheckCircle2 className="h-4 w-4 text-emerald-300" />}
          Download models
        </h3>

        {!ollamaReachable && (
          <p className="mt-1 text-sm text-zinc-500">Start Ollama first.</p>
        )}

        {ollamaReachable && missing.length === 0 && (
          <p className="mt-1 text-sm text-emerald-300">All required models are installed.</p>
        )}

        {ollamaReachable && missing.length > 0 && (
          <div className="mt-3 space-y-3">
            {missing.map((name) => {
              const pull = pulls[name];
              return (
                <div key={name} className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <code className="text-sm text-zinc-200">{name}</code>
                    {!pull && (
                      <button
                        type="button"
                        onClick={() => void download(name)}
                        className="inline-flex items-center gap-1.5 rounded-md border border-cyan-800 px-2.5 py-1 text-xs text-cyan-300 transition hover:border-cyan-700"
                      >
                        <Download className="h-3.5 w-3.5" />
                        Download
                      </button>
                    )}
                    {pull && !pull.done && (
                      <button
                        type="button"
                        onClick={cancelDownloads}
                        className="inline-flex items-center gap-1.5 rounded-md border border-zinc-700 px-2.5 py-1 text-xs text-zinc-300 transition hover:border-zinc-600"
                      >
                        <XCircle className="h-3.5 w-3.5" />
                        Cancel
                      </button>
                    )}
                  </div>

                  {pull && (
                    <div className="mt-2">
                      {pull.percent !== null && (
                        <div className="h-1.5 overflow-hidden rounded-full bg-zinc-800">
                          <div
                            className="h-full rounded-full bg-cyan-500 transition-all"
                            style={{ width: `${pull.percent}%` }}
                          />
                        </div>
                      )}
                      <p className="mt-1.5 text-xs text-zinc-400">
                        {pull.error ? (
                          <span className="text-red-300">{pull.error}</span>
                        ) : (
                          <>
                            {pull.status}
                            {pull.total > 0 && (
                              <>
                                {' · '}
                                {formatBytes(pull.completed)} / {formatBytes(pull.total)}
                              </>
                            )}
                          </>
                        )}
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
            <p className="text-xs text-zinc-500">
              Models are several gigabytes. You can keep using the app once they finish.
            </p>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          onClick={onSkip}
          className="text-sm text-zinc-400 underline-offset-4 transition hover:text-zinc-200 hover:underline"
        >
          Skip for now
        </button>
        <button
          type="button"
          disabled={!canContinue}
          onClick={onComplete}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
        >
          {canContinue ? 'Start using the app' : 'Waiting for the search engine'}
        </button>
      </div>

      {!generationReady && !checking && canContinue && (
        <p className="flex items-start gap-2 text-xs text-zinc-500">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
          Without Ollama you can still import and search documents and read cited
          sources. Answers are written by the generation model, so they stay
          unavailable until it is installed.
        </p>
      )}
    </div>
  );
}
