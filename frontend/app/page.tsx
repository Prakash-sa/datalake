'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  Brain,
  CheckCircle2,
  Gauge,
  GitFork,
  Library,
  ListChecks,
  Loader2,
  MessageSquare,
  RefreshCw,
  Settings as SettingsIcon,
  Sparkles,
  Stethoscope,
  Upload,
} from 'lucide-react';
import { apiRequest as callApi } from '@/lib/api';
import { dismissSetup, isSetupDismissed } from '@/lib/setup';
import type { Readiness } from '@/lib/types';
import ActivityView from '@/app/components/ActivityView';
import ChatView from '@/app/components/ChatView';
import DiagnosticsView from '@/app/components/DiagnosticsView';
import FirstRunSetup from '@/app/components/FirstRunSetup';
import LibraryView from '@/app/components/LibraryView';
import SettingsView from '@/app/components/SettingsView';

type View = 'chat' | 'library' | 'activity' | 'settings' | 'diagnostics';

const VIEWS: Array<{ id: View; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'library', label: 'Library', icon: Library },
  { id: 'activity', label: 'Activity', icon: ListChecks },
  { id: 'settings', label: 'Settings', icon: SettingsIcon },
  { id: 'diagnostics', label: 'Diagnostics', icon: Stethoscope },
];

const CAPABILITIES = [
  {
    name: 'Local',
    status: 'No cloud',
    description: 'Parsing, embedding, indexing, and retrieval all run on this machine.',
    icon: Brain,
  },
  {
    name: 'Grounded',
    status: 'Cited',
    description: 'Every answer cites the passages it used, validated against what was retrieved.',
    icon: GitFork,
  },
  {
    name: 'Hybrid search',
    status: 'Dense + FTS',
    description: 'Vector similarity fused with lexical search so exact terms are not lost.',
    icon: Gauge,
  },
  {
    name: 'Observable',
    status: 'Instrumented',
    description: 'Job progress, retrieval traces, and diagnostics for what the engine is doing.',
    icon: RefreshCw,
  },
];

export default function DocumentRAGInterface() {
  const [isDesktop, setIsDesktop] = useState(false);
  const [view, setView] = useState<View>('chat');
  const [importing, setImporting] = useState(false);
  const [importStatus, setImportStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Bumped after an import so the library refetches.
  const [libraryVersion, setLibraryVersion] = useState(0);
  // null while the readiness probe is in flight, so the app does not flash the
  // chat screen before setup is known to be needed.
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    setIsDesktop(Boolean(window.desktop?.isElectron));
  }, []);

  useEffect(() => {
    if (isSetupDismissed()) {
      setNeedsSetup(false);
      return;
    }
    // Derived from the backend rather than a stored flag, so setup reappears if
    // a dependency later goes missing. Embeddings are the only hard
    // requirement: without Ollama the app still imports and searches.
    void callApi<Readiness>('/readiness', apiUrl)
      .then((response) => {
        const capabilities = response.data?.capabilities;
        if (!response.ok || !capabilities) {
          setNeedsSetup(true);
          return;
        }
        setNeedsSetup(
          capabilities.embeddings?.status !== 'ready' ||
            capabilities.ollama?.status !== 'ready',
        );
      })
      .catch(() => setNeedsSetup(true));
  }, [apiUrl]);

  const handleImport = useCallback(async () => {
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
      const response = await callApi<{ jobs: unknown[] }>('/jobs', apiUrl, 'POST', {
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
  }, [apiUrl]);

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
                <span>{isDesktop ? 'Desktop' : 'Web'} · everything runs locally</span>
              </div>
              <h1 className="text-3xl font-semibold tracking-normal text-white sm:text-4xl">
                Document RAG Engine
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-400 sm:text-base">
                Ask questions about your own documents and get answers that cite the
                passages they came from.
              </p>
            </div>

            {isDesktop && (
              <button
                type="button"
                onClick={handleImport}
                disabled={importing}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-zinc-700 px-4 py-2.5 text-sm font-medium text-zinc-200 transition hover:border-cyan-500 hover:text-white disabled:cursor-not-allowed disabled:text-zinc-500"
              >
                {importing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="h-4 w-4" />
                )}
                Import documents
              </button>
            )}

            <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4 lg:min-w-[520px]">
              {CAPABILITIES.map((item) => (
                <div key={item.name} className="rounded-md border border-zinc-800 bg-zinc-900 p-3">
                  <item.icon className="mb-3 h-5 w-5 text-cyan-300" />
                  <div className="font-medium text-white">{item.name}</div>
                  <div className="mt-1 text-xs text-emerald-300">{item.status}</div>
                </div>
              ))}
            </div>
          </div>

          <nav className="flex gap-1 border-b border-zinc-800" aria-label="Views">
            {VIEWS.map((item) => (
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

      <section className="mx-auto max-w-7xl space-y-4 px-5 py-6 sm:px-8">
        {error && (
          <div className="flex gap-3 rounded-md border border-red-800 bg-red-950/70 p-4">
            <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-300" />
            <p className="text-sm text-red-100">{error}</p>
          </div>
        )}

        {importStatus && (
          <div className="flex gap-3 rounded-md border border-emerald-800 bg-emerald-950/50 p-4">
            <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-300" />
            <p className="text-sm text-emerald-100">{importStatus}</p>
          </div>
        )}

        {view === 'chat' && <ChatView apiUrl={apiUrl} />}
        {view === 'library' && <LibraryView key={libraryVersion} apiUrl={apiUrl} />}
        {view === 'activity' && <ActivityView apiUrl={apiUrl} />}
        {view === 'settings' && <SettingsView apiUrl={apiUrl} />}
        {view === 'diagnostics' && <DiagnosticsView apiUrl={apiUrl} />}
      </section>
    </main>
  );
}
