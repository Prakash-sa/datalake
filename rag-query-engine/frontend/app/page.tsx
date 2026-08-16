'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
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
} from 'lucide-react';

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
  const [error, setError] = useState<string | null>(null);
  const [isDesktop, setIsDesktop] = useState(false);

  const apiUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    [],
  );

  useEffect(() => {
    setIsDesktop(Boolean(window.desktop?.isElectron));
  }, []);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${apiUrl}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, k: 5, min_score: 0 }),
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || 'Query failed');
      }

      const data = (await response.json()) as QueryResult;
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to process query');
    } finally {
      setLoading(false);
    }
  };

  const documents = results?.retrieved_documents ?? [];

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
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-5 py-6 sm:px-8 lg:grid-cols-[minmax(0,1fr)_360px]">
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
            </div>
          </form>

          {error && (
            <div className="flex gap-3 rounded-md border border-red-800 bg-red-950/70 p-4">
              <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-300" />
              <p className="text-sm text-red-100">{error}</p>
            </div>
          )}

          {results?.status === 'success' && (
            <div className="rounded-md border border-zinc-800 bg-zinc-900 p-5">
              <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
                  <Sparkles className="h-5 w-5 text-cyan-300" />
                  Answer
                </h2>
                <div className="flex gap-2 text-xs text-zinc-400">
                  <span>{results.document_count ?? documents.length} sources</span>
                  <span>{results.processing_time_seconds ?? 0}s</span>
                </div>
              </div>
              <p className="whitespace-pre-wrap rounded-md bg-zinc-950 p-4 text-sm leading-7 text-zinc-100">
                {results.answer}
              </p>
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
