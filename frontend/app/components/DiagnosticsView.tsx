'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, HardDrive, Loader2, RefreshCw, XCircle } from 'lucide-react';
import { apiRequest, formatBytes } from '@/lib/api';
import type { Diagnostics, ModelListResponse } from '@/lib/types';

/** Free space below this makes indexing unreliable. */
const LOW_DISK_BYTES = 2 * 1024 ** 3;

function StatusDot({ ok, warn }: { ok: boolean; warn?: boolean }) {
  if (warn) return <AlertCircle className="h-4 w-4 text-amber-300" />;
  return ok ? (
    <CheckCircle2 className="h-4 w-4 text-emerald-300" />
  ) : (
    <XCircle className="h-4 w-4 text-red-300" />
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2 py-1.5">
      <span className="text-sm text-zinc-400">{label}</span>
      <code className="max-w-full truncate text-xs text-zinc-300" title={value}>
        {value}
      </code>
    </div>
  );
}

function Card({ title, children }: { title: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-900 p-5">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">{title}</h3>
      {children}
    </div>
  );
}

export default function DiagnosticsView({ apiUrl }: { apiUrl: string }) {
  const [data, setData] = useState<Diagnostics | null>(null);
  const [models, setModels] = useState<ModelListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const [diagnostics, modelList] = await Promise.all([
      apiRequest<Diagnostics>('/diagnostics', apiUrl),
      apiRequest<ModelListResponse>('/models', apiUrl),
    ]);

    if (!diagnostics.ok || !diagnostics.data) {
      setError(diagnostics.error || 'Could not load diagnostics');
      setLoading(false);
      return;
    }
    setError(null);
    setData(diagnostics.data);
    setModels(modelList.ok ? (modelList.data ?? null) : null);
    setLoading(false);
  }, [apiUrl]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900 p-8 text-sm text-zinc-400">
        <Loader2 className="h-4 w-4 animate-spin" />
        Collecting diagnostics…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex gap-3 rounded-md border border-red-800 bg-red-950/70 p-4">
        <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-300" />
        <p className="text-sm text-red-100">{error || 'Diagnostics unavailable'}</p>
      </div>
    );
  }

  const usedPercent = data.disk.total_bytes
    ? Math.round((data.disk.used_bytes / data.disk.total_bytes) * 100)
    : 0;
  const lowDisk = data.disk.free_bytes < LOW_DISK_BYTES;
  const ollamaReady = models !== null && models.missing_models.length === 0;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Diagnostics</h2>
          <p className="mt-1 text-sm text-zinc-400">
            Local only — no document text or prompts are included.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="inline-flex min-h-10 items-center gap-2 rounded-md border border-zinc-700 px-3 py-2 text-sm text-zinc-300 transition hover:border-zinc-600 hover:text-white"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card
          title={
            <>
              <StatusDot ok={ollamaReady} />
              Ollama
            </>
          }
        >
          <Row label="Endpoint" value={data.models.ollama_url} />
          <Row label="Generation model" value={data.models.llm_model} />
          <Row label="Embedding model" value={data.models.embedding_model} />
          {models && models.missing_models.length > 0 && (
            <p className="mt-2 rounded-md border border-amber-900 bg-amber-950/40 p-2.5 text-xs text-amber-100">
              Missing: {models.missing_models.join(', ')}. Pull them from Settings.
            </p>
          )}
          {models === null && (
            <p className="mt-2 rounded-md border border-red-900 bg-red-950/40 p-2.5 text-xs text-red-100">
              Could not reach Ollama. Start it, then refresh.
            </p>
          )}
        </Card>

        <Card
          title={
            <>
              <StatusDot ok={data.storage.writable} />
              Vector storage
            </>
          }
        >
          <Row label="Provider" value={data.storage.provider} />
          <Row label="Writable" value={data.storage.writable ? 'yes' : 'no'} />
          <Row label="Path" value={data.storage.persistent_path} />
          {data.storage.error && (
            <p className="mt-2 rounded-md border border-red-900 bg-red-950/40 p-2.5 text-xs text-red-100">
              {data.storage.error}
            </p>
          )}
        </Card>

        <Card
          title={
            <>
              <StatusDot ok={!lowDisk} warn={lowDisk} />
              <HardDrive className="h-4 w-4 text-zinc-400" />
              Disk
            </>
          }
        >
          <div className="mb-3 h-2 overflow-hidden rounded-full bg-zinc-800">
            <div
              className={`h-full rounded-full ${lowDisk ? 'bg-amber-400' : 'bg-cyan-500'}`}
              style={{ width: `${usedPercent}%` }}
            />
          </div>
          <Row label="Free" value={formatBytes(data.disk.free_bytes)} />
          <Row label="Used" value={`${formatBytes(data.disk.used_bytes)} (${usedPercent}%)`} />
          <Row label="Total" value={formatBytes(data.disk.total_bytes)} />
          {lowDisk && (
            <p className="mt-2 rounded-md border border-amber-900 bg-amber-950/40 p-2.5 text-xs text-amber-100">
              Low free space. Indexing large documents may fail.
            </p>
          )}
        </Card>

        <Card title="Index">
          <Row label="Documents in catalog" value={String(data.stats.catalog_documents)} />
          <Row label="Chunks indexed" value={String(data.stats.total_documents)} />
          <Row label="Queries processed" value={String(data.stats.queries_processed)} />
          <Row label="Errors" value={String(data.stats.errors)} />
        </Card>

        <Card title="Runtime">
          <Row label="Python" value={data.runtime.python_version} />
          <Row label="Platform" value={data.runtime.platform} />
        </Card>

        <Card title="Paths">
          <Row label="App data" value={data.paths.app_data_dir} />
          <Row label="Catalog" value={data.paths.app_db_path} />
          <Row label="Vectors" value={data.paths.chroma_path} />
        </Card>
      </div>
    </div>
  );
}
