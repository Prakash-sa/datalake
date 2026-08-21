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
    icon: Brain,
  },
  {
    name: 'Grounded',
    status: 'Cited',
    icon: GitFork,
  },
  {
    name: 'Hybrid search',
    status: 'Dense + FTS',
    icon: Gauge,
  },
  {
    name: 'Observable',
    status: 'Instrumented',
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
            capabilities.generation?.status !== 'ready',
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
    <main className="flex min-h-screen flex-col bg-zinc-950 text-zinc-100">
      <section className="shrink-0 border-b border-zinc-800 bg-zinc-950/95">
        <div className="mx-auto flex w-full max-w-[96rem] flex-col gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div className="min-w-0">
              <div className="mb-2 flex flex-wrap items-center gap-2 text-xs font-medium">
                <span className="inline-flex items-center gap-1.5 rounded-md border border-cyan-900/70 bg-cyan-950/30 px-2 py-1 text-cyan-200">
                  <Sparkles className="h-3.5 w-3.5" />
                  {isDesktop ? 'Desktop' : 'Web'}
                </span>
                <span className="text-zinc-500">Everything runs locally</span>
              </div>
              <h1 className="truncate text-2xl font-semibold tracking-normal text-white sm:text-3xl">
                Document RAG Engine
              </h1>
              <p className="mt-1 max-w-3xl text-sm leading-6 text-zinc-400">
                Ask grounded questions, manage your index, and inspect retrieval behavior from one
                local workspace.
              </p>
            </div>

            <div className="flex flex-col gap-3 lg:flex-row lg:items-center xl:justify-end">
              <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4 lg:min-w-[520px]">
                {CAPABILITIES.map((item) => (
                  <div
                    key={item.name}
                    className="flex min-h-16 items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900/70 px-3 py-2"
                  >
                    <item.icon className="h-4 w-4 flex-shrink-0 text-cyan-300" />
                    <div className="min-w-0">
                      <div className="truncate font-medium text-white">{item.name}</div>
                      <div className="truncate text-emerald-300">{item.status}</div>
                    </div>
                  </div>
                ))}
              </div>

              {isDesktop && (
                <button
                  type="button"
                  onClick={handleImport}
                  disabled={importing}
                  className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md border border-zinc-700 px-4 py-2.5 text-sm font-medium text-zinc-100 transition hover:border-cyan-500 hover:bg-zinc-900 disabled:cursor-not-allowed disabled:text-zinc-500 lg:w-auto"
                >
                  {importing ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Upload className="h-4 w-4" />
                  )}
                  Import documents
                </button>
              )}
            </div>
          </div>

          <nav
            className="-mx-4 flex gap-1 overflow-x-auto border-t border-zinc-900 px-4 pt-3 sm:mx-0 sm:px-0"
            aria-label="Views"
          >
            {VIEWS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setView(item.id)}
                aria-current={view === item.id ? 'page' : undefined}
                className={`inline-flex min-h-10 shrink-0 items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition ${
                  view === item.id
                    ? 'bg-zinc-100 text-zinc-950'
                    : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100'
                }`}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </button>
            ))}
          </nav>
        </div>
      </section>

      <section className="mx-auto flex w-full max-w-[96rem] flex-1 flex-col space-y-4 px-4 py-4 sm:px-6 lg:min-h-0 lg:px-8">
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
