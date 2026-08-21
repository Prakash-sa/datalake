'use client';

import { FormEvent, useCallback, useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, Download, Loader2, RefreshCw } from 'lucide-react';
import { apiRequest } from '@/lib/api';
import type { ModelListResponse, RuntimeSettings, SettingsResponse } from '@/lib/types';

export default function SettingsView({ apiUrl }: { apiUrl: string }) {
  const [settings, setSettings] = useState<RuntimeSettings | null>(null);
  const [models, setModels] = useState<ModelListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pulling, setPulling] = useState<string | null>(null);

  // Draft values, so editing does not mutate saved state until submit.
  const [ollamaUrl, setOllamaUrl] = useState('');
  const [generationProvider, setGenerationProvider] = useState<'local' | 'ollama'>('local');
  const [localLlmModelPath, setLocalLlmModelPath] = useState('');
  const [localLlmGpuLayers, setLocalLlmGpuLayers] = useState(12);
  const [localLlmMaxTokens, setLocalLlmMaxTokens] = useState(256);
  const [embeddingModel, setEmbeddingModel] = useState('');
  const [llmModel, setLlmModel] = useState('');
  const [temperature, setTemperature] = useState(0.1);

  const applySettings = (next: RuntimeSettings) => {
    setSettings(next);
    setOllamaUrl(next.ollama_url);
    setGenerationProvider(next.generation_provider);
    setLocalLlmModelPath(next.local_llm_model_path);
    setLocalLlmGpuLayers(next.local_llm_gpu_layers);
    setLocalLlmMaxTokens(next.local_llm_max_tokens);
    setEmbeddingModel(next.embedding_model);
    setLlmModel(next.llm_model);
    setTemperature(next.temperature);
  };

  const load = useCallback(async () => {
    const [settingsResponse, modelsResponse] = await Promise.all([
      apiRequest<SettingsResponse>('/settings', apiUrl),
      apiRequest<ModelListResponse>('/models', apiUrl),
    ]);

    if (!settingsResponse.ok || !settingsResponse.data) {
      setError(settingsResponse.error || 'Could not load settings');
      setLoading(false);
      return;
    }
    setError(null);
    applySettings(settingsResponse.data.settings);
    // A failed model listing is not fatal; Ollama may simply be stopped.
    setModels(modelsResponse.ok ? (modelsResponse.data ?? null) : null);
    setLoading(false);
  }, [apiUrl]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setNotice(null);

    const response = await apiRequest<SettingsResponse>('/settings', apiUrl, 'POST', {
      ollama_url: ollamaUrl,
      generation_provider: generationProvider,
      local_llm_model_path: localLlmModelPath,
      local_llm_gpu_layers: localLlmGpuLayers,
      local_llm_max_tokens: localLlmMaxTokens,
      embedding_model: embeddingModel,
      llm_model: llmModel,
      temperature,
    });

    setSaving(false);
    if (!response.ok || !response.data) {
      setError(response.error || 'Could not save settings');
      return;
    }
    setError(null);
    applySettings(response.data.settings);
    // Models are constructed at startup, so a change needs a restart.
    setNotice('Saved. Restart the app for model changes to take effect.');
  };

  const applyProfile = (profile: { llm_model: string; embedding_model: string }) => {
    setLlmModel(profile.llm_model);
    setEmbeddingModel(profile.embedding_model);
    setNotice('Profile applied — review and save.');
  };

  const pull = async (name: string) => {
    setPulling(name);
    setNotice(null);
    const response = await apiRequest(`/models/pull`, apiUrl, 'POST', { name });
    setPulling(null);
    if (!response.ok) {
      setError(response.error || `Could not pull ${name}`);
      return;
    }
    setNotice(`Pulled ${name}.`);
    await load();
  };

  const field =
    'mt-2 w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm text-white outline-none transition focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/20';

  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900 p-8 text-sm text-zinc-400">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading settings…
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Settings</h2>
          <p className="mt-1 text-sm text-zinc-400">
            Stored locally. Model changes apply after a restart.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="inline-flex min-h-10 items-center gap-2 rounded-md border border-zinc-700 px-3 py-2 text-sm text-zinc-300 transition hover:border-zinc-600 hover:text-white"
        >
          <RefreshCw className="h-4 w-4" />
          Reload
        </button>
      </div>

      {error && (
        <div className="flex gap-3 rounded-md border border-red-800 bg-red-950/70 p-4">
          <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-300" />
          <p className="text-sm text-red-100">{error}</p>
        </div>
      )}

      {notice && (
        <div className="flex gap-3 rounded-md border border-emerald-800 bg-emerald-950/50 p-4">
          <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-300" />
          <p className="text-sm text-emerald-100">{notice}</p>
        </div>
      )}

      {models && models.missing_models.length > 0 && (
        <div className="rounded-md border border-amber-800 bg-amber-950/40 p-4">
          <p className="flex items-center gap-2 text-sm font-medium text-amber-100">
            <AlertCircle className="h-4 w-4" />
            {models.missing_models.length} required model
            {models.missing_models.length === 1 ? '' : 's'} not installed
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {models.missing_models.map((name) => (
              <button
                key={name}
                type="button"
                disabled={pulling !== null}
                onClick={() => void pull(name)}
                className="inline-flex items-center gap-1.5 rounded-md border border-amber-700 px-2.5 py-1.5 text-xs text-amber-100 transition hover:bg-amber-900/40 disabled:opacity-50"
              >
                {pulling === name ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Download className="h-3.5 w-3.5" />
                )}
                Pull {name}
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-amber-200/70">
            Pulling downloads several gigabytes and can take a while.
          </p>
        </div>
      )}

      {settings && Object.keys(settings.model_profiles).length > 0 && (
        <div className="rounded-md border border-zinc-800 bg-zinc-900 p-5">
          <h3 className="text-sm font-medium text-zinc-200">Model profiles</h3>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {Object.entries(settings.model_profiles).map(([name, profile]) => (
              <button
                key={name}
                type="button"
                onClick={() => applyProfile(profile)}
                className="rounded-md border border-zinc-700 p-3 text-left transition hover:border-cyan-500"
              >
                <div className="font-medium capitalize text-white">{name}</div>
                <div className="mt-1 text-xs text-zinc-400">{profile.llm_model}</div>
                <div className="text-xs text-zinc-500">{profile.embedding_model}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      <form onSubmit={save} className="rounded-md border border-zinc-800 bg-zinc-900 p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm sm:col-span-2">
            <span className="font-medium text-zinc-200">Generation provider</span>
            <select
              value={generationProvider}
              onChange={(e) => setGenerationProvider(e.target.value as 'local' | 'ollama')}
              className={field}
            >
              <option value="local">Local GGUF (no Ollama)</option>
              <option value="ollama">Ollama daemon</option>
            </select>
          </label>
          <label className="block text-sm sm:col-span-2">
            <span className="font-medium text-zinc-200">Local GGUF model path</span>
            <input
              value={localLlmModelPath}
              onChange={(e) => setLocalLlmModelPath(e.target.value)}
              className={field}
              disabled={generationProvider !== 'local'}
            />
          </label>
          <label className="block text-sm">
            <span className="font-medium text-zinc-200">Local GPU layers</span>
            <input
              type="number"
              min={0}
              max={999}
              value={localLlmGpuLayers}
              onChange={(e) => setLocalLlmGpuLayers(Number(e.target.value))}
              className={field}
              disabled={generationProvider !== 'local'}
            />
            <span className="mt-1 block text-xs text-zinc-500">Use 0 for CPU-only.</span>
          </label>
          <label className="block text-sm">
            <span className="font-medium text-zinc-200">Max answer tokens</span>
            <input
              type="number"
              min={32}
              max={4096}
              value={localLlmMaxTokens}
              onChange={(e) => setLocalLlmMaxTokens(Number(e.target.value))}
              className={field}
              disabled={generationProvider !== 'local'}
            />
            <span className="mt-1 block text-xs text-zinc-500">Lower values answer faster.</span>
          </label>
          <label className="block text-sm sm:col-span-2">
            <span className="font-medium text-zinc-200">Ollama URL</span>
            <input
              value={ollamaUrl}
              onChange={(e) => setOllamaUrl(e.target.value)}
              className={field}
              disabled={generationProvider !== 'ollama'}
              placeholder="http://127.0.0.1:11434"
            />
          </label>
          <label className="block text-sm">
            <span className="font-medium text-zinc-200">Generation model</span>
            <input value={llmModel} onChange={(e) => setLlmModel(e.target.value)} className={field} />
          </label>
          <label className="block text-sm">
            <span className="font-medium text-zinc-200">Embedding model</span>
            <input
              value={embeddingModel}
              onChange={(e) => setEmbeddingModel(e.target.value)}
              className={field}
            />
            <span className="mt-1 block text-xs text-amber-300/80">
              Changing this requires reindexing every document.
            </span>
          </label>
          <label className="block text-sm sm:col-span-2">
            <span className="font-medium text-zinc-200">
              Temperature <span className="text-zinc-500">({temperature.toFixed(2)})</span>
            </span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={temperature}
              onChange={(e) => setTemperature(Number(e.target.value))}
              className="mt-3 w-full accent-cyan-400"
            />
            <span className="mt-1 block text-xs text-zinc-500">
              Low values keep grounded answers close to the source text.
            </span>
          </label>
        </div>

        <button
          type="submit"
          disabled={saving}
          className="mt-5 inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
        >
          {saving && <Loader2 className="h-4 w-4 animate-spin" />}
          Save settings
        </button>
      </form>
    </div>
  );
}
