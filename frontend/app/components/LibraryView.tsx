'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, FileText, Loader2, RefreshCw, Trash2 } from 'lucide-react';
import { apiRequest, formatBytes, formatRelative } from '@/lib/api';

export type CatalogDocument = {
  id: string;
  source_path: string;
  title: string;
  source_hash: string;
  content_type: string;
  parser_version: string;
  chunker_version: string;
  embedding_model: string;
  llm_model: string;
  indexed_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
  chunk_count: number;
};

/** Short label for a MIME type, so the table stays readable. */
function contentTypeLabel(contentType: string): string {
  if (contentType.includes('wordprocessingml')) return 'DOCX';
  if (contentType.includes('pdf')) return 'PDF';
  if (contentType.includes('markdown')) return 'MD';
  if (contentType.includes('html')) return 'HTML';
  if (contentType.includes('plain')) return 'TXT';
  return contentType.split('/').pop()?.toUpperCase() || 'FILE';
}

export default function LibraryView({
  apiUrl,
  onChanged,
}: {
  apiUrl: string;
  onChanged?: () => void;
}) {
  const [documents, setDocuments] = useState<CatalogDocument[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const response = await apiRequest<{ documents: CatalogDocument[] }>('/documents', apiUrl);
    if (!response.ok || !response.data) {
      setError(response.error || 'Could not load the document library');
      setLoading(false);
      return;
    }
    setError(null);
    setDocuments(response.data.documents);
    setLoading(false);
  }, [apiUrl]);

  useEffect(() => {
    void load();
  }, [load]);

  const remove = async (documentId: string) => {
    setBusyId(documentId);
    const response = await apiRequest(`/documents/${documentId}`, apiUrl, 'DELETE');
    if (!response.ok) setError(response.error || 'Could not delete the document');
    setBusyId(null);
    setConfirmId(null);
    await load();
    onChanged?.();
  };

  const totalChunks = documents.reduce((sum, doc) => sum + (doc.chunk_count ?? 0), 0);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Library</h2>
          <p className="mt-1 text-sm text-zinc-400">
            {documents.length} document{documents.length === 1 ? '' : 's'} · {totalChunks} chunks
            indexed
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

      {loading && documents.length === 0 && (
        <div className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900 p-8 text-sm text-zinc-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading library…
        </div>
      )}

      {!loading && documents.length === 0 && !error && (
        <div className="rounded-md border border-zinc-800 bg-zinc-900 p-8 text-center">
          <FileText className="mx-auto mb-3 h-12 w-12 text-zinc-600" />
          <p className="font-medium text-zinc-200">No documents indexed</p>
          <p className="mt-1 text-sm text-zinc-500">
            Import PDF, DOCX, Markdown, HTML, or text files to build the index.
          </p>
        </div>
      )}

      {documents.length > 0 && (
        <div className="grid gap-3 md:hidden">
          {documents.map((doc) => {
            const size = Number(doc.metadata?.source_size_bytes ?? 0);
            return (
              <article key={doc.id} className="rounded-md border border-zinc-800 bg-zinc-900 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-zinc-100" title={doc.title}>
                      {doc.title}
                    </p>
                    <p className="mt-1 truncate text-xs text-zinc-500" title={doc.source_path}>
                      {doc.source_path}
                    </p>
                  </div>
                  <span className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-300">
                    {contentTypeLabel(doc.content_type)}
                  </span>
                </div>

                <dl className="mt-3 grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <dt className="text-zinc-500">Size</dt>
                    <dd className="mt-0.5 text-zinc-300">{size ? formatBytes(size) : '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-zinc-500">Chunks</dt>
                    <dd className="mt-0.5 text-zinc-300">{doc.chunk_count}</dd>
                  </div>
                  <div>
                    <dt className="text-zinc-500">Indexed</dt>
                    <dd className="mt-0.5 text-zinc-300">{formatRelative(doc.indexed_at)}</dd>
                  </div>
                </dl>

                <div className="mt-3 flex items-center justify-between gap-3">
                  <code className="min-w-0 truncate text-xs text-zinc-500">{doc.embedding_model}</code>
                  {confirmId === doc.id ? (
                    <div className="flex shrink-0 gap-2">
                      <button
                        type="button"
                        disabled={busyId === doc.id}
                        onClick={() => void remove(doc.id)}
                        className="rounded-md border border-red-800 px-2.5 py-1 text-xs text-red-200 transition hover:bg-red-950 disabled:opacity-50"
                      >
                        {busyId === doc.id ? 'Deleting…' : 'Confirm'}
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmId(null)}
                        className="rounded-md border border-zinc-700 px-2.5 py-1 text-xs text-zinc-300 transition hover:border-zinc-600"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setConfirmId(doc.id)}
                      title="Delete document, chunks, and vectors"
                      className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-zinc-700 px-2.5 py-1 text-xs text-zinc-300 transition hover:border-red-800 hover:text-red-200"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}

      {documents.length > 0 && (
        <div className="hidden overflow-x-auto rounded-md border border-zinc-800 bg-zinc-900 md:block">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-zinc-800 text-xs uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-4 py-3 font-medium">Document</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Size</th>
                <th className="px-4 py-3 font-medium">Chunks</th>
                <th className="px-4 py-3 font-medium">Indexed</th>
                <th className="px-4 py-3 font-medium">Embedding model</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {documents.map((doc) => {
                const size = Number(doc.metadata?.source_size_bytes ?? 0);
                return (
                  <tr key={doc.id} className="align-top">
                    <td className="max-w-xs px-4 py-3">
                      <p className="truncate font-medium text-zinc-100" title={doc.title}>
                        {doc.title}
                      </p>
                      <p className="truncate text-xs text-zinc-500" title={doc.source_path}>
                        {doc.source_path}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-zinc-400">{contentTypeLabel(doc.content_type)}</td>
                    <td className="px-4 py-3 text-zinc-400">{size ? formatBytes(size) : '—'}</td>
                    <td className="px-4 py-3 text-zinc-400">{doc.chunk_count}</td>
                    <td className="px-4 py-3 text-zinc-400">{formatRelative(doc.indexed_at)}</td>
                    <td className="px-4 py-3">
                      <code className="text-xs text-zinc-500">{doc.embedding_model}</code>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {confirmId === doc.id ? (
                        <div className="flex justify-end gap-2">
                          <button
                            type="button"
                            disabled={busyId === doc.id}
                            onClick={() => void remove(doc.id)}
                            className="rounded-md border border-red-800 px-2.5 py-1 text-xs text-red-200 transition hover:bg-red-950 disabled:opacity-50"
                          >
                            {busyId === doc.id ? 'Deleting…' : 'Confirm'}
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmId(null)}
                            className="rounded-md border border-zinc-700 px-2.5 py-1 text-xs text-zinc-300 transition hover:border-zinc-600"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setConfirmId(doc.id)}
                          title="Delete document, chunks, and vectors"
                          className="inline-flex items-center gap-1.5 rounded-md border border-zinc-700 px-2.5 py-1 text-xs text-zinc-300 transition hover:border-red-800 hover:text-red-200"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                          Delete
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
