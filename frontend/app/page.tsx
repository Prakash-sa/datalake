'use client';

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  Brain,
  CheckCircle2,
  FileText,
  Gauge,
  GitFork,
  Loader2,
  RefreshCw,
  Send,
  Sparkles,
  Upload,
  XCircle,
  Library,
  ListChecks,
  Search as SearchIcon,
  Settings as SettingsIcon,
  Stethoscope,
} from 'lucide-react';
import { streamQuery } from '@/lib/streamQuery';
import { apiRequest as callApi } from '@/lib/api';
import { dismissSetup, isSetupDismissed } from '@/lib/setup';
import type { ModelListResponse } from '@/lib/types';
import ActivityView from '@/app/components/ActivityView';
import DiagnosticsView from '@/app/components/DiagnosticsView';
import FirstRunSetup from '@/app/components/FirstRunSetup';
import LibraryView from '@/app/components/LibraryView';
import SettingsView from '@/app/components/SettingsView';
import type { CancelStream, CitationReport, StreamEvent } from '@/types/electron';

type RetrievedDocument = {
  id: string;
  content: string;
  relevance_score: number;
  metadata?: Record<string, unknown>;
};

type QueryResult = {
  status: 'success' | 'no_results' | 'error';
  query: string;
  answer?: string;
  retrieved_documents?: RetrievedDocument[];
  document_count?: number;
  processing_time_seconds?: number;
  error?: string;
};

type ApiResult<T> = {
  ok: boolean;
  status: number;
  data?: T;
  error?: string;
};

type Capability = {
  name: string;
  description: string;
  status: string;
  icon: React.ComponentType<{ className?: string }>;
};

const capabilities: Capability[] = [
  {
    name: 'Loop Engineering',
    description: 'Observe retrieval quality, latency, and errors so prompts and pipelines can be tightened continuously.',
    status: 'Instrumented',
    icon: RefreshCw,
  },
  {
    name: 'Memory',
    description: 'Persistent Chroma collections back document recall across API restarts and desktop sessions.',
    status: 'Persistent',
    icon: Brain,
  },
  {
    name: 'Eval',
    description: 'Use the eval endpoint and source-grounded answers to regression-test retrieval before releases.',
    status: 'API Ready',
    icon: Gauge,
  },
  {
    name: 'Open Source',
    description: 'Packaged desktop builds, docs, license, security policy, and contribution workflow are first-class.',
    status: 'Prepared',
    icon: GitFork,
  },
];

const examples = [
  'Summarize the pipeline architecture and key dependencies.',
  'Which documents mention production deployment risks?',
  'What should be monitored before a release?',
];

export default function DocumentRAGInterface() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [importStatus, setImportStatus] = useState<string | null>(null);
  const [isDesktop, setIsDesktop] = useState(false);
  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState<RetrievedDocument[]>([]);
  const [citations, setCitations] = useState<CitationReport | null>(null);
  const [truncatedCount, setTruncatedCount] = useState(0);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const cancelRef = useRef<CancelStream | null>(null);
  const [view, setView] = useState<
    'query' | 'library' | 'activity' | 'settings' | 'diagnostics'
  >('query');
  // Bumped after an import or delete so the library refetches.
  const [libraryVersion, setLibraryVersion] = useState(0);
  // null while the readiness probe is in flight, so the app does not flash
  // the query screen before setup is known to be needed.
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null);

  const apiUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    [],
  );

  useEffect(() => {
    setIsDesktop(Boolean(window.desktop?.isElectron));
  }, []);

  useEffect(() => {
    if (isSetupDismissed()) {
      setNeedsSetup(false);
      return;
    }
    // Setup is derived from the backend rather than a stored flag, so it
    // reappears if the required models are ever removed.
    void callApi<ModelListResponse>('/models', apiUrl).then((response) => {
      const missing = response.data?.missing_models ?? [];
      setNeedsSetup(!response.ok || response.data?.status === 'error' || missing.length > 0);
    });
  }, [apiUrl]);

  const apiRequest = <T,>(
    path: string,
    method: 'GET' | 'POST' | 'DELETE' = 'GET',
    body?: unknown,
  ): Promise<ApiResult<T>> => callApi<T>(path, apiUrl, method, body);

  const handleStreamEvent = useCallback((event: StreamEvent) => {
    switch (event.event) {
      case 'sources':
        setSources(event.documents ?? []);
        setTruncatedCount(event.truncated_document_count ?? 0);
        break;
      case 'token':
        // Appended per frame so the answer renders as it is generated.
        setAnswer((current) => current + event.text);
        break;
      case 'done':
        setLoading(false);
        cancelRef.current = null;
        setCitations(event.citations ?? null);
        setElapsed(event.processing_time_seconds ?? null);
        if (event.retrieved_documents) setSources(event.retrieved_documents);
        // A no-results run carries its message in `answer`.
        if (event.answer) setAnswer(event.answer);
        setResults({ status: event.status === 'no_results' ? 'no_results' : 'success', query });
        break;
      case 'error':
        setLoading(false);
        cancelRef.current = null;
        setErrorCode(event.code);
        setError(event.error);
        break;
    }
  }, [query]);

  const handleCancel = () => {
    cancelRef.current?.();
    cancelRef.current = null;
    setLoading(false);
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!query.trim()) return;

    // Abandon any in-flight generation before starting another.
    cancelRef.current?.();

    setLoading(true);
    setError(null);
    setErrorCode(null);
    setAnswer('');
    setSources([]);
    setCitations(null);
    setTruncatedCount(0);
    setElapsed(null);
    setResults(null);

    try {
      cancelRef.current = await streamQuery(
        { query, k: 5, minScore: 0 },
        handleStreamEvent,
        apiUrl,
      );
    } catch (err) {
      setLoading(false);
      setError(err instanceof Error ? err.message : 'Failed to process query');
    }
  };

  // Cancel an in-flight generation if the view unmounts.
  useEffect(() => () => cancelRef.current?.(), []);

  const handleImport = async () => {
    const selectDocuments = window.desktop?.selectDocuments;
    if (!selectDocuments) return;

    setImporting(true);
    setError(null);
    setImportStatus(null);

    try {
      const paths = await selectDocuments();
      if (!paths.length) return;

      // Queue the work instead of blocking on it; Activity shows progress and
      // surfaces per-file failures with retry.
      const response = await apiRequest<{ jobs: unknown[] }>('/jobs', 'POST', {
        paths,
        force_reindex: false,
      });
      if (!response.ok || !response.data) {
        throw new Error(response.error || 'Import failed');
      }

      const queued = response.data.jobs.length;
      setImportStatus(
        `${queued} file${queued === 1 ? '' : 's'} queued for indexing — see Activity for progress`,
      );
      setLibraryVersion((version) => version + 1);
      setView('activity');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to import documents');
    } finally {
      setImporting(false);
    }
  };

  const documents = sources;

  const views = [
    { id: 'query' as const, label: 'Query', icon: SearchIcon },
    { id: 'library' as const, label: 'Library', icon: Library },
    { id: 'activity' as const, label: 'Activity', icon: ListChecks },
    { id: 'settings' as const, label: 'Settings', icon: SettingsIcon },
    { id: 'diagnostics' as const, label: 'Diagnostics', icon: Stethoscope },
  ];

  if (needsSetup === null) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-zinc-950 text-zinc-100">
        <Loader2 className="h-6 w-6 animate-spin text-cyan-300" />
      </main>
    );
  }

  if (needsSetup) {
    return (
      <main className="min-h-screen bg-zinc-950 px-5 py-12 text-zinc-100 sm:px-8">
        <FirstRunSetup
          apiUrl={apiUrl}
          onComplete={() => setNeedsSetup(false)}
          onSkip={() => {
            dismissSetup();
            setNeedsSetup(false);
          }}
        />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <section className="border-b border-zinc-800 bg-zinc-950">
        <div className="mx-auto flex max-w-7xl flex-col gap-6 px-5 py-6 sm:px-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="mb-3 flex items-center gap-2 text-sm text-cyan-300">
                <Sparkles className="h-4 w-4" />
                <span>{isDesktop ? 'Desktop' : 'Web'} production console</span>
              </div>
              <h1 className="text-3xl font-semibold tracking-normal text-white sm:text-4xl">
                Document RAG Engine
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-400 sm:text-base">
                Query indexed documents, inspect source grounding, and validate the operating loop before shipping.
              </p>
            </div>
            {isDesktop && (
              <button
                type="button"
                onClick={handleImport}
                disabled={importing}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-zinc-700 px-4 py-2.5 text-sm font-medium text-zinc-200 transition hover:border-cyan-500 hover:text-white disabled:cursor-not-allowed disabled:text-zinc-500"
              >
                {importing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                Import
              </button>
            )}
            <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4 lg:min-w-[520px]">
              {capabilities.map((item) => (
                <div key={item.name} className="rounded-md border border-zinc-800 bg-zinc-900 p-3">
                  <item.icon className="mb-3 h-5 w-5 text-cyan-300" />
                  <div className="font-medium text-white">{item.name}</div>
                  <div className="mt-1 text-xs text-emerald-300">{item.status}</div>
                </div>
              ))}
            </div>
          </div>

          <nav className="flex gap-1 border-b border-zinc-800" aria-label="Views">
            {views.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setView(item.id)}
                aria-current={view === item.id ? 'page' : undefined}
                className={`inline-flex min-h-11 items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition ${
                  view === item.id
                    ? 'border-cyan-400 text-white'
                    : 'border-transparent text-zinc-400 hover:text-zinc-200'
                }`}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </button>
            ))}
          </nav>
        </div>
      </section>

      {view !== 'query' && (
        <section className="mx-auto max-w-7xl px-5 py-6 sm:px-8">
          {view === 'library' && (
            <LibraryView key={libraryVersion} apiUrl={apiUrl} />
          )}
          {view === 'activity' && <ActivityView apiUrl={apiUrl} />}
          {view === 'settings' && <SettingsView apiUrl={apiUrl} />}
          {view === 'diagnostics' && <DiagnosticsView apiUrl={apiUrl} />}
        </section>
      )}

      <section
        className={`mx-auto max-w-7xl gap-6 px-5 py-6 sm:px-8 lg:grid-cols-[minmax(0,1fr)_360px] ${
          view === 'query' ? 'grid' : 'hidden'
        }`}
      >
        <div className="space-y-6">
          <form onSubmit={handleSubmit} className="rounded-md border border-zinc-800 bg-zinc-900 p-5 shadow-2xl">
            <label className="block text-sm font-medium text-zinc-200" htmlFor="query">
              Ask a document-grounded question
            </label>
            <textarea
              id="query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="What should I know before deploying this pipeline?"
              className="mt-3 min-h-32 w-full resize-y rounded-md border border-zinc-700 bg-zinc-950 px-4 py-3 font-sans text-sm text-white outline-none transition focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/20"
              disabled={loading}
            />
            <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap gap-2">
                {examples.map((example) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => setQuery(example)}
                    className="rounded-md border border-zinc-700 px-3 py-2 text-left text-xs text-zinc-300 transition hover:border-cyan-500 hover:text-white"
                  >
                    {example}
                  </button>
                ))}
              </div>
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                Search
              </button>
              {loading && (
                <button
                  type="button"
                  onClick={handleCancel}
                  className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-zinc-700 px-4 py-2.5 text-sm font-semibold text-zinc-300 transition hover:border-zinc-600 hover:text-white"
                >
                  <XCircle className="h-4 w-4" />
                  Stop
                </button>
              )}
            </div>
          </form>

          {error && (
            <div className="flex gap-3 rounded-md border border-red-800 bg-red-950/70 p-4">
              <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-300" />
              <div className="text-sm text-red-100">
                <p>{error}</p>
                {errorCode && (
                  <p className="mt-1 text-xs text-red-300/80">
                    <code>{errorCode}</code>
                    {errorCode === 'model_unavailable' &&
                      ' — start Ollama, then pull the configured models.'}
                    {errorCode === 'generation_timeout' &&
                      ' — the model took too long; try a smaller profile.'}
                    {errorCode === 'cancelled' && ' — generation stopped.'}
                  </p>
                )}
              </div>
            </div>
          )}

          {importStatus && (
            <div className="flex gap-3 rounded-md border border-emerald-800 bg-emerald-950/50 p-4">
              <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-300" />
              <p className="text-sm text-emerald-100">{importStatus}</p>
            </div>
          )}

          {(answer || loading) && results?.status !== 'no_results' && (
            <div className="rounded-md border border-zinc-800 bg-zinc-900 p-5">
              <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
                  <Sparkles className="h-5 w-5 text-cyan-300" />
                  Answer
                  {loading && <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />}
                </h2>
                <div className="flex flex-wrap gap-2 text-xs text-zinc-400">
                  <span>{documents.length} sources</span>
                  {citations && <span>{citations.citation_count} citations</span>}
                  {truncatedCount > 0 && (
                    <span title="Dropped to fit the context token budget">
                      {truncatedCount} truncated
                    </span>
                  )}
                  {elapsed !== null && <span>{elapsed}s</span>}
                </div>
              </div>
              <p className="whitespace-pre-wrap rounded-md bg-zinc-950 p-4 text-sm leading-7 text-zinc-100">
                {answer}
                {loading && <span className="ml-0.5 animate-pulse text-cyan-300">▌</span>}
              </p>
              {citations && !citations.valid && (
                <p className="mt-3 flex items-start gap-2 rounded-md border border-amber-800 bg-amber-950/40 p-3 text-xs text-amber-100">
                  <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-300" />
                  This answer cited {citations.invalid_indices.length} source
                  {citations.invalid_indices.length === 1 ? '' : 's'} that were not
                  retrieved ([S{citations.invalid_indices.join('], [S')}]). Treat the
                  affected claims as unverified.
                </p>
              )}
            </div>
          )}

          {results?.status === 'no_results' && (
            <div className="rounded-md border border-zinc-800 bg-zinc-900 p-8 text-center">
              <FileText className="mx-auto mb-3 h-12 w-12 text-zinc-600" />
              <p className="font-medium text-zinc-200">No relevant documents found</p>
              <p className="mt-1 text-sm text-zinc-500">Index more documents or lower the minimum relevance threshold.</p>
            </div>
          )}

          {documents.length > 0 && (
            <div className="rounded-md border border-zinc-800 bg-zinc-900 p-5">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                <FileText className="h-5 w-5 text-zinc-400" />
                Source Documents
              </h2>
              <div className="space-y-3">
                {documents.map((doc, idx) => (
                  <article key={`${doc.id}-${idx}`} className="rounded-md border border-zinc-800 bg-zinc-950 p-4">
                    <div className="mb-2 flex items-start justify-between gap-3">
                      <span className="font-medium text-cyan-300">Document {idx + 1}</span>
                      <span className="rounded-md bg-emerald-950 px-2 py-1 text-xs text-emerald-300">
                        {(doc.relevance_score * 100).toFixed(1)}% match
                      </span>
                    </div>
                    <p className="line-clamp-4 text-sm leading-6 text-zinc-300">{doc.content}</p>
                    {doc.metadata && Object.keys(doc.metadata).length > 0 && (
                      <div className="mt-3 border-t border-zinc-800 pt-3 text-xs text-zinc-500">
                        {Object.entries(doc.metadata).map(([key, value]) => (
                          <span key={key} className="mr-3 inline-block">
                            <strong>{key}:</strong> {String(value)}
                          </span>
                        ))}
                      </div>
                    )}
                  </article>
                ))}
              </div>
            </div>
          )}
        </div>

        <aside className="space-y-4">
          {capabilities.map((item) => (
            <div key={item.name} className="rounded-md border border-zinc-800 bg-zinc-900 p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 font-medium text-white">
                  <item.icon className="h-5 w-5 text-cyan-300" />
                  {item.name}
                </div>
                <CheckCircle2 className="h-4 w-4 text-emerald-300" />
              </div>
              <p className="text-sm leading-6 text-zinc-400">{item.description}</p>
            </div>
          ))}
        </aside>
      </section>
    </main>
  );
}
