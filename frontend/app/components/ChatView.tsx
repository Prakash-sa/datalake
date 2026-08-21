'use client';

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertCircle,
  FileText,
  Loader2,
  MessageSquarePlus,
  Send,
  Sparkles,
  Trash2,
  XCircle,
} from 'lucide-react';
import { apiRequest, formatRelative } from '@/lib/api';
import {
  type ChatMessage,
  type ChatStreamEvent,
  type ConversationSummary,
  explainChatError,
  streamChat,
} from '@/lib/chat';
import type { CancelStream, RetrievedDocument } from '@/types/electron';

const SUGGESTIONS = [
  'What are the main topics in my documents?',
  'Summarise the key points.',
  'What should I be aware of before deploying?',
];

function Sources({ documents }: { documents: RetrievedDocument[] }) {
  const [open, setOpen] = useState(false);
  if (!documents.length) return null;

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex items-center gap-1.5 text-xs text-zinc-400 transition hover:text-zinc-200"
      >
        <FileText className="h-3.5 w-3.5" />
        {open ? 'Hide' : 'Show'} {documents.length} source
        {documents.length === 1 ? '' : 's'}
      </button>

      {open && (
        <ol className="mt-2 space-y-2">
          {documents.map((doc, index) => (
            <li key={doc.id} className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-xs font-medium text-cyan-300">[S{index + 1}]</span>
                <span className="text-xs text-zinc-500">
                  {Math.round(doc.relevance_score * 100)}% match
                </span>
              </div>
              <p className="mt-1.5 line-clamp-4 text-xs leading-5 text-zinc-400">{doc.content}</p>
              {typeof doc.metadata?.source_name === 'string' && (
                <p className="mt-1.5 truncate text-[11px] text-zinc-600">
                  {doc.metadata.source_name as string}
                </p>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function Bubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  const hint = explainChatError(message.errorCode);

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[46rem] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-cyan-500 text-zinc-950'
            : 'border border-zinc-800 bg-zinc-900 text-zinc-100'
        }`}
      >
        <p className="whitespace-pre-wrap text-sm leading-6">
          {message.content}
          {message.streaming && (
            <span className="ml-0.5 animate-pulse text-cyan-300">▌</span>
          )}
        </p>

        {!isUser && hint && (
          <p className="mt-2 flex items-start gap-2 rounded-md border border-amber-900 bg-amber-950/40 p-2.5 text-xs text-amber-100">
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
            {hint}
          </p>
        )}

        {!isUser && message.citations && !message.citations.valid && (
          <p className="mt-2 rounded-md border border-amber-900 bg-amber-950/40 p-2.5 text-xs text-amber-100">
            This answer cited {message.citations.invalid_indices.length} source
            {message.citations.invalid_indices.length === 1 ? '' : 's'} that were not
            retrieved. Treat those claims as unverified.
          </p>
        )}

        {!isUser && <Sources documents={message.sources ?? []} />}
      </div>
    </div>
  );
}

export default function ChatView({ apiUrl }: { apiUrl: string }) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cancelRef = useRef<CancelStream | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const loadConversations = useCallback(async () => {
    const response = await apiRequest<{ conversations: ConversationSummary[] }>(
      '/conversations',
      apiUrl,
    );
    if (response.ok && response.data) setConversations(response.data.conversations);
  }, [apiUrl]);

  useEffect(() => {
    void loadConversations();
  }, [loadConversations]);

  // Abandon an in-flight reply if the view unmounts.
  useEffect(() => () => cancelRef.current?.(), []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const openConversation = async (id: string) => {
    cancelRef.current?.();
    setStreaming(false);
    setError(null);

    const response = await apiRequest<{
      conversation: { id: string; messages: ChatMessage[] };
    }>(`/conversations/${id}`, apiUrl);
    if (!response.ok || !response.data) {
      setError(response.error || 'Could not open that conversation');
      return;
    }

    setConversationId(id);
    setMessages(
      response.data.conversation.messages.map((m) => ({
        ...m,
        sources: [],
        errorCode: (m as { model?: { error_code?: string } }).model?.error_code ?? null,
      })),
    );
  };

  const startNew = () => {
    cancelRef.current?.();
    setStreaming(false);
    setConversationId(null);
    setMessages([]);
    setError(null);
  };

  const removeConversation = async (id: string) => {
    await apiRequest(`/conversations/${id}`, apiUrl, 'DELETE');
    if (id === conversationId) startNew();
    await loadConversations();
  };

  const handleEvent = useCallback((event: ChatStreamEvent) => {
    switch (event.event) {
      case 'conversation':
        setConversationId(event.conversation_id);
        break;
      case 'sources':
        // Attach to the assistant turn being written, so citations resolve
        // while the text is still arriving.
        setMessages((current) =>
          current.map((m, i) =>
            i === current.length - 1 && m.role === 'assistant'
              ? { ...m, sources: event.documents }
              : m,
          ),
        );
        break;
      case 'token':
        setMessages((current) =>
          current.map((m, i) =>
            i === current.length - 1 && m.role === 'assistant'
              ? { ...m, content: m.content + event.text }
              : m,
          ),
        );
        break;
      case 'done':
        setStreaming(false);
        cancelRef.current = null;
        setMessages((current) =>
          current.map((m, i) =>
            i === current.length - 1 && m.role === 'assistant'
              ? {
                  ...m,
                  id: event.message_id,
                  content: event.answer || m.content,
                  citations: event.citations,
                  sources: event.retrieved_documents ?? m.sources,
                  streaming: false,
                }
              : m,
          ),
        );
        break;
      case 'error':
        setStreaming(false);
        cancelRef.current = null;
        setMessages((current) =>
          current.map((m, i) =>
            i === current.length - 1 && m.role === 'assistant'
              ? {
                  ...m,
                  streaming: false,
                  errorCode: event.code,
                  content: m.content || '',
                }
              : m,
          ),
        );
        if (!explainChatError(event.code)) setError(event.error);
        break;
    }
  }, []);

  const send = async (e: FormEvent) => {
    e.preventDefault();
    const question = input.trim();
    if (!question || streaming) return;

    cancelRef.current?.();
    setInput('');
    setError(null);
    setStreaming(true);
    setMessages((current) => [
      ...current,
      { id: `local_${Date.now()}`, role: 'user', content: question },
      { id: `local_${Date.now()}_a`, role: 'assistant', content: '', streaming: true },
    ]);

    try {
      cancelRef.current = await streamChat(
        { message: question, conversationId, k: 5 },
        handleEvent,
        apiUrl,
      );
    } catch (err) {
      setStreaming(false);
      setError(err instanceof Error ? err.message : 'Could not send that message');
    }
    void loadConversations();
  };

  const stop = () => {
    cancelRef.current?.();
    cancelRef.current = null;
    setStreaming(false);
    setMessages((current) =>
      current.map((m, i) =>
        i === current.length - 1 ? { ...m, streaming: false } : m,
      ),
    );
  };

  return (
    <div className="grid gap-5 lg:grid-cols-[240px_minmax(0,1fr)]">
      {/* Conversations */}
      <aside className="space-y-2">
        <button
          type="button"
          onClick={startNew}
          className="inline-flex w-full min-h-10 items-center justify-center gap-2 rounded-md border border-zinc-700 px-3 py-2 text-sm text-zinc-200 transition hover:border-cyan-500 hover:text-white"
        >
          <MessageSquarePlus className="h-4 w-4" />
          New chat
        </button>

        <div className="space-y-1">
          {conversations.map((conversation) => (
            <div
              key={conversation.id}
              className={`group flex items-center gap-1 rounded-md border px-2.5 py-2 transition ${
                conversation.id === conversationId
                  ? 'border-cyan-800 bg-zinc-900'
                  : 'border-transparent hover:border-zinc-800 hover:bg-zinc-900/60'
              }`}
            >
              <button
                type="button"
                onClick={() => void openConversation(conversation.id)}
                className="min-w-0 flex-1 text-left"
              >
                <p className="truncate text-xs text-zinc-200">{conversation.title}</p>
                <p className="text-[11px] text-zinc-600">
                  {formatRelative(conversation.updated_at)}
                </p>
              </button>
              <button
                type="button"
                title="Delete conversation"
                onClick={() => void removeConversation(conversation.id)}
                className="opacity-0 transition group-hover:opacity-100"
              >
                <Trash2 className="h-3.5 w-3.5 text-zinc-500 hover:text-red-300" />
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* Thread */}
      <section className="flex min-h-[32rem] flex-col rounded-md border border-zinc-800 bg-zinc-950">
        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <Sparkles className="mb-3 h-8 w-8 text-cyan-300" />
              <p className="font-medium text-zinc-200">Ask about your documents</p>
              <p className="mt-1 text-sm text-zinc-500">
                Answers cite the passages they came from.
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => setInput(suggestion)}
                    className="rounded-md border border-zinc-700 px-3 py-2 text-xs text-zinc-300 transition hover:border-cyan-500 hover:text-white"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message) => (
            <Bubble key={message.id} message={message} />
          ))}
          <div ref={bottomRef} />
        </div>

        {error && (
          <div className="mx-5 mb-3 flex gap-3 rounded-md border border-red-800 bg-red-950/70 p-3">
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-300" />
            <p className="text-xs text-red-100">{error}</p>
          </div>
        )}

        <form onSubmit={send} className="border-t border-zinc-800 p-4">
          <div className="flex gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                // Enter sends; Shift+Enter adds a line, as in any chat client.
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  void send(e);
                }
              }}
              placeholder="Ask a question about your documents…"
              rows={2}
              className="min-h-12 flex-1 resize-y rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm text-white outline-none transition focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/20"
            />
            {streaming ? (
              <button
                type="button"
                onClick={stop}
                className="inline-flex min-h-11 items-center gap-2 self-end rounded-md border border-zinc-700 px-4 py-2.5 text-sm font-medium text-zinc-300 transition hover:border-zinc-600 hover:text-white"
              >
                <XCircle className="h-4 w-4" />
                Stop
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="inline-flex min-h-11 items-center gap-2 self-end rounded-md bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
              >
                <Send className="h-4 w-4" />
                Send
              </button>
            )}
          </div>
          {streaming && (
            <p className="mt-2 flex items-center gap-1.5 text-xs text-zinc-500">
              <Loader2 className="h-3 w-3 animate-spin" />
              Generating…
            </p>
          )}
        </form>
      </section>
    </div>
  );
}
