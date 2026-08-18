'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertCircle, Ban, CheckCircle2, Loader2, RefreshCw, XCircle } from 'lucide-react';
import { apiRequest, formatRelative } from '@/lib/api';
import {
  type IngestionJob,
  type JobStatus,
  explainErrorCode,
  isTerminal,
  progressFraction,
} from '@/lib/jobs';

const POLL_INTERVAL_MS = 1500;

const STATUS_STYLES: Record<JobStatus, string> = {
  queued: 'border-zinc-700 text-zinc-300',
  parsing: 'border-cyan-800 text-cyan-300',
  chunking: 'border-cyan-800 text-cyan-300',
  embedding: 'border-cyan-800 text-cyan-300',
  committing: 'border-cyan-800 text-cyan-300',
  complete: 'border-emerald-800 text-emerald-300',
  failed: 'border-red-800 text-red-300',
  cancelled: 'border-zinc-700 text-zinc-400',
};

function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {!isTerminal(status) && <Loader2 className="h-3 w-3 animate-spin" />}
      {status === 'complete' && <CheckCircle2 className="h-3 w-3" />}
      {status === 'failed' && <AlertCircle className="h-3 w-3" />}
      {status === 'cancelled' && <Ban className="h-3 w-3" />}
      {status}
    </span>
  );
}

export default function ActivityView({ apiUrl }: { apiUrl: string }) {
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  // Held in a ref so the poll effect does not restart on every tick.
  const hasActiveRef = useRef(false);

  const load = useCallback(async () => {
    const response = await apiRequest<{ jobs: IngestionJob[] }>('/jobs', apiUrl);
    if (!response.ok || !response.data) {
      setError(response.error || 'Could not load jobs');
      setLoading(false);
      return;
    }
    setError(null);
    setJobs(response.data.jobs);
    hasActiveRef.current = response.data.jobs.some((job) => !isTerminal(job.status));
    setLoading(false);
  }, [apiUrl]);

  useEffect(() => {
    void load();
    // Poll only while something is in flight, so an idle queue costs nothing.
    const timer = setInterval(() => {
      if (hasActiveRef.current) void load();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [load]);

  const act = async (jobId: string, action: 'cancel' | 'retry') => {
    setBusyId(jobId);
    const response = await apiRequest(`/jobs/${jobId}/${action}`, apiUrl, 'POST');
    if (!response.ok) setError(response.error || `Could not ${action} job`);
    setBusyId(null);
    await load();
  };

  const active = jobs.filter((job) => !isTerminal(job.status));
  const finished = jobs.filter((job) => isTerminal(job.status));

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Activity</h2>
          <p className="mt-1 text-sm text-zinc-400">
            {active.length > 0
              ? `${active.length} job${active.length === 1 ? '' : 's'} in progress`
              : 'No jobs running'}
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

      {error && (
        <div className="flex gap-3 rounded-md border border-red-800 bg-red-950/70 p-4">
          <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-300" />
          <p className="text-sm text-red-100">{error}</p>
        </div>
      )}

      {loading && jobs.length === 0 && (
        <div className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900 p-8 text-sm text-zinc-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading jobs…
        </div>
      )}

      {!loading && jobs.length === 0 && !error && (
        <div className="rounded-md border border-zinc-800 bg-zinc-900 p-8 text-center">
          <p className="font-medium text-zinc-200">No ingestion jobs yet</p>
          <p className="mt-1 text-sm text-zinc-500">Import documents to queue indexing work.</p>
        </div>
      )}

      {[...active, ...finished].map((job) => {
        const hint = explainErrorCode(job.error_code);
        const percent = Math.round(progressFraction(job.status) * 100);

        return (
          <div key={job.id} className="rounded-md border border-zinc-800 bg-zinc-900 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate font-medium text-zinc-100" title={job.source_path}>
                  {job.source_path.split('/').pop() || job.source_path}
                </p>
                <p className="mt-1 truncate text-xs text-zinc-500" title={job.source_path}>
                  {job.source_path}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={job.status} />
                {!isTerminal(job.status) && (
                  <button
                    type="button"
                    disabled={busyId === job.id}
                    onClick={() => void act(job.id, 'cancel')}
                    className="inline-flex items-center gap-1.5 rounded-md border border-zinc-700 px-2.5 py-1 text-xs text-zinc-300 transition hover:border-zinc-600 hover:text-white disabled:opacity-50"
                  >
                    <XCircle className="h-3.5 w-3.5" />
                    Cancel
                  </button>
                )}
                {job.status === 'failed' && (
                  <button
                    type="button"
                    disabled={busyId === job.id}
                    onClick={() => void act(job.id, 'retry')}
                    className="inline-flex items-center gap-1.5 rounded-md border border-cyan-800 px-2.5 py-1 text-xs text-cyan-300 transition hover:border-cyan-700 hover:text-cyan-200 disabled:opacity-50"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    Retry
                  </button>
                )}
              </div>
            </div>

            {!isTerminal(job.status) && (
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-zinc-800">
                <div
                  className="h-full rounded-full bg-cyan-500 transition-all duration-500"
                  style={{ width: `${percent}%` }}
                />
              </div>
            )}

            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-500">
              {job.chunks_total > 0 && (
                <span>
                  {job.chunks_done}/{job.chunks_total} chunks
                </span>
              )}
              {job.attempts > 1 && <span>attempt {job.attempts}</span>}
              <span>updated {formatRelative(job.updated_at)}</span>
            </div>

            {job.error && (
              <div className="mt-3 rounded-md border border-red-900 bg-red-950/40 p-3">
                {/* The backend message is the fact; the hint is only guidance,
                    so it must not replace what the backend actually reported. */}
                <p className="text-xs text-red-100">{job.error}</p>
                {hint && <p className="mt-1.5 text-xs text-red-200/80">{hint}</p>}
                {job.error_code && (
                  <code className="mt-1.5 block text-[11px] text-red-300/70">{job.error_code}</code>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
