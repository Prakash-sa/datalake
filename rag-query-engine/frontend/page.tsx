'use client';

import { useState } from 'react';
import { Loader2, Send, AlertCircle, FileText, Zap } from 'lucide-react';

export default function DocumentRAGInterface() {
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
        body: JSON.stringify({ query: query, k: 5 }),
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
          <h1 className="text-4xl font-bold text-white mb-2 flex items-center gap-3">
            <Zap className="w-8 h-8 text-blue-400" />
            Document RAG Engine
          </h1>
          <p className="text-slate-300">
            Ask questions about your enterprise documents using semantic search and LLM analysis
          </p>
        </div>

        {/* Query Input */}
        <form onSubmit={handleSubmit} className="mb-8">
          <div className="bg-slate-800 rounded-lg p-6 shadow-xl border border-slate-700">
            <label className="block text-sm font-medium text-slate-300 mb-3">
              What would you like to know about your documents?
            </label>
            <div className="flex flex-col gap-2">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g., What is Apache Airflow and how does it work? or Explain the document processing pipeline..."
                className="flex-1 bg-slate-700 text-white rounded px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 font-sans text-sm min-h-24"
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
                Search & Analyze
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
            {/* LLM Response */}
            {results.status === 'success' && results.answer && (
              <div className="bg-slate-800 rounded-lg p-6 shadow-xl border border-slate-700">
                <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                  <Zap className="w-5 h-5 text-blue-400" />
                  Answer
                </h2>
                <div className="bg-slate-700 rounded p-4 text-slate-100 leading-relaxed">
                  {results.answer}
                </div>
              </div>
            )}

            {/* Retrieved Documents */}
            {results.retrieved_documents && results.retrieved_documents.length > 0 && (
              <div className="bg-slate-800 rounded-lg p-6 shadow-xl border border-slate-700">
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <FileText className="w-5 h-5 text-slate-400" />
                  Source Documents ({results.document_count})
                </h2>
                <div className="space-y-4">
                  {results.retrieved_documents.map((doc, idx) => (
                    <div key={idx} className="bg-slate-700 rounded-lg p-4 border border-slate-600">
                      <div className="flex items-start justify-between mb-2">
                        <span className="font-medium text-blue-400">
                          Document {idx + 1}
                        </span>
                        <span className="bg-blue-900 text-blue-200 text-xs px-2 py-1 rounded">
                          {(doc.relevance_score * 100).toFixed(1)}% match
                        </span>
                      </div>
                      <p className="text-slate-300 text-sm line-clamp-3">
                        {doc.content}
                      </p>
                      {doc.metadata && Object.keys(doc.metadata).length > 0 && (
                        <div className="mt-3 pt-3 border-t border-slate-600">
                          <p className="text-xs text-slate-400">
                            {Object.entries(doc.metadata).map(([key, value]) => (
                              <span key={key} className="inline-block mr-3">
                                <strong>{key}:</strong> {String(value)}
                              </span>
                            ))}
                          </p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* No Results State */}
            {results.status === 'no_results' && (
              <div className="bg-slate-700 border border-slate-600 rounded-lg p-6 text-center">
                <FileText className="w-12 h-12 text-slate-500 mx-auto mb-3" />
                <p className="text-slate-300 font-medium">No documents found</p>
                <p className="text-slate-400 text-sm mt-1">
                  Try a different query or index more documents
                </p>
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
            <FileText className="w-16 h-16 text-slate-600 mx-auto mb-4" />
            <p className="text-slate-400 text-lg">
              Enter a question about your documents to get started
            </p>
            <p className="text-slate-500 text-sm mt-2">
              The engine will search through indexed documents and provide an AI-powered answer
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
