'use client';

import { useState } from 'react';
import { Loader2, Send, AlertCircle } from 'lucide-react';

export default function RAGQueryInterface() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('http://localhost:8000/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, max_retries: 2 }),
      });

      if (!response.ok) throw new Error('Query failed');

      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError(err.message || 'Failed to process query');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">
            Data Lake RAG Query Engine
          </h1>
          <p className="text-slate-300">
            Ask natural language questions about your Iceberg data lake
          </p>
        </div>

        {/* Query Input */}
        <form onSubmit={handleSubmit} className="mb-8">
          <div className="bg-slate-800 rounded-lg p-6 shadow-xl border border-slate-700">
            <label className="block text-sm font-medium text-slate-300 mb-3">
              Natural Language Query
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g., Show me total sales by region for the last quarter"
                className="flex-1 bg-slate-700 text-white rounded px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white px-6 py-3 rounded font-medium flex items-center gap-2 transition"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
                Query
              </button>
            </div>
          </div>
        </form>

        {/* Error Message */}
        {error && (
          <div className="bg-red-900 border border-red-700 rounded-lg p-4 mb-8 flex gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <p className="text-red-100">{error}</p>
          </div>
        )}

        {/* Results */}
        {results && (
          <div className="space-y-6">
            {/* Generated SQL */}
            <div className="bg-slate-800 rounded-lg p-6 shadow-xl border border-slate-700">
              <h2 className="text-lg font-semibold text-white mb-3">Generated SQL</h2>
              <pre className="bg-slate-900 rounded p-4 text-slate-300 text-sm overflow-x-auto">
                {results.sql_query}
              </pre>
              <p className="text-xs text-slate-400 mt-2">
                Attempts: {results.attempts} | Generated at: {new Date(results.timestamp).toLocaleString()}
              </p>
            </div>

            {/* Query Results */}
            {results.results.status === 'success' && (
              <div className="bg-slate-800 rounded-lg p-6 shadow-xl border border-slate-700">
                <h2 className="text-lg font-semibold text-white mb-3">
                  Results ({results.results.row_count} rows)
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-slate-300">
                    <thead>
                      <tr className="border-b border-slate-700">
                        {results.results.columns.map((col, i) => (
                          <th key={i} className="text-left p-3 bg-slate-900 font-semibold">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {results.results.rows.slice(0, 20).map((row, i) => (
                        <tr key={i} className="border-b border-slate-700 hover:bg-slate-700">
                          {Array.isArray(row) ? (
                            row.map((cell, j) => (
                              <td key={j} className="p-3">
                                {cell?.toString() || 'NULL'}
                              </td>
                            ))
                          ) : (
                            <td colSpan={results.results.columns.length} className="p-3">
                              {JSON.stringify(row)}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {results.results.row_count > 20 && (
                  <p className="text-xs text-slate-400 mt-3">
                    Showing 20 of {results.results.row_count} rows
                  </p>
                )}
              </div>
            )}

            {/* Error Result */}
            {results.results.status === 'error' && (
              <div className="bg-red-900 border border-red-700 rounded-lg p-4">
                <p className="text-red-100 font-medium">Query Error:</p>
                <p className="text-red-200 text-sm mt-2">{results.results.error}</p>
              </div>
            )}
          </div>
        )}

        {/* Empty State */}
        {!results && !loading && (
          <div className="bg-slate-800 rounded-lg p-12 text-center border border-slate-700">
            <p className="text-slate-400 text-lg">
              Enter a query above to get started with semantic search on your data lake
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
