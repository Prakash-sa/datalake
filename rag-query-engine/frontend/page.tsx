'use client';

import { useState } from 'react';
import { Loader2, Send, AlertCircle } from 'lucide-react';

export default function QueryInterface() {
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
        body: JSON.stringify({ sql: query }),
      });

      if (!response.ok) throw new Error('Query failed');

      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError(err.message || 'Failed to execute query');
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
            Data Lake Query Engine
          </h1>
          <p className="text-slate-300">
            Execute SQL queries on your Iceberg data lake
          </p>
        </div>

        {/* Query Input */}
        <form onSubmit={handleSubmit} className="mb-8">
          <div className="bg-slate-800 rounded-lg p-6 shadow-xl border border-slate-700">
            <label className="block text-sm font-medium text-slate-300 mb-3">
              SQL Query
            </label>
            <div className="flex flex-col gap-2">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g., SELECT * FROM iceberg.raw.sales LIMIT 10"
                className="flex-1 bg-slate-700 text-white rounded px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm min-h-20"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white px-6 py-3 rounded font-medium flex items-center gap-2 transition w-fit"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
                Execute
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
            {/* Query Results */}
            {results.status === 'success' && (
              <div className="bg-slate-800 rounded-lg p-6 shadow-xl border border-slate-700">
                <h2 className="text-lg font-semibold text-white mb-3">
                  Results ({results.row_count} rows)
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-slate-300">
                    <thead>
                      <tr className="border-b border-slate-700">
                        {results.columns.map((col, i) => (
                          <th key={i} className="text-left p-3 bg-slate-900 font-semibold">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {results.rows.slice(0, 20).map((row, i) => (
                        <tr key={i} className="border-b border-slate-700 hover:bg-slate-700">
                          {Array.isArray(row) ? (
                            row.map((cell, j) => (
                              <td key={j} className="p-3">
                                {cell?.toString() || 'NULL'}
                              </td>
                            ))
                          ) : (
                            <td colSpan={results.columns.length} className="p-3">
                              {JSON.stringify(row)}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {results.row_count > 20 && (
                  <p className="text-xs text-slate-400 mt-3">
                    Showing 20 of {results.row_count} rows
                  </p>
                )}
              </div>
            )}

            {/* Error Result */}
            {results.status === 'error' && (
              <div className="bg-red-900 border border-red-700 rounded-lg p-4">
                <p className="text-red-100 font-medium">Query Error:</p>
                <p className="text-red-200 text-sm mt-2">{results.error}</p>
              </div>
            )}
          </div>
        )}

        {/* Empty State */}
        {!results && !loading && (
          <div className="bg-slate-800 rounded-lg p-12 text-center border border-slate-700">
            <p className="text-slate-400 text-lg">
              Enter a SQL query above to get started
}
