'use client';

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertCircle,
  ChevronRight,
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
        className={`max-w-full rounded-2xl px-4 py-3 shadow-sm sm:max-w-[85%] xl:max-w-[54rem] ${
          isUser
            ? 'bg-cyan-400 text-zinc-950'
            : 'border border-zinc-800 bg-zinc-900/95 text-zinc-100'
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
    <div className="flex min-h-[calc(100dvh-14rem)] flex-1 flex-col gap-4 lg:grid lg:min-h-[34rem] lg:grid-cols-[280px_minmax(0,1fr)] xl:min-h-[calc(100dvh-13rem)]">
      {/* Conversations */}
      <aside className="min-w-0 rounded-md border border-zinc-800 bg-zinc-950/70 p-3 lg:flex lg:min-h-0 lg:flex-col">
        <button
          type="button"
          onClick={startNew}
          className="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-md border border-zinc-700 px-3 py-2 text-sm font-medium text-zinc-200 transition hover:border-cyan-500 hover:bg-zinc-900 hover:text-white"
        >
          <MessageSquarePlus className="h-4 w-4" />
          New chat
        </button>

        <div className="mt-3 flex gap-2 overflow-x-auto pb-1 lg:min-h-0 lg:flex-1 lg:flex-col lg:overflow-y-auto lg:overflow-x-hidden lg:pb-0">
          {conversations.length === 0 && (
            <div className="min-w-full rounded-md border border-dashed border-zinc-800 px-3 py-4 text-center text-xs text-zinc-500">
              New conversations appear here.
            </div>
          )}

          {conversations.map((conversation) => (
            <div
              key={conversation.id}
              className={`group flex min-w-56 items-center gap-1 rounded-md border px-2.5 py-2 transition lg:min-w-0 ${
                conversation.id === conversationId
                  ? 'border-cyan-800 bg-zinc-900'
                  : 'border-transparent bg-zinc-900/40 hover:border-zinc-800 hover:bg-zinc-900/70'
              }`}
            >
              <button
                type="button"
                onClick={() => void openConversation(conversation.id)}
                className="min-w-0 flex-1 text-left"
              >
                <p className="truncate text-xs font-medium text-zinc-200">{conversation.title}</p>
                <p className="text-[11px] text-zinc-600">
                  {formatRelative(conversation.updated_at)}
                </p>
              </button>
              <button
                type="button"
                title="Delete conversation"
                onClick={() => void removeConversation(conversation.id)}
                className="rounded p-1 opacity-100 transition hover:bg-red-950/50 lg:opacity-0 lg:group-hover:opacity-100"
              >
                <Trash2 className="h-3.5 w-3.5 text-zinc-500 hover:text-red-300" />
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* Thread */}
      <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-md border border-zinc-800 bg-zinc-950">
        <div className="flex min-h-14 items-center justify-between gap-3 border-b border-zinc-800 px-4 py-3">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-white">
              {conversationId ? 'Conversation' : 'New chat'}
            </h2>
            <p className="mt-0.5 truncate text-xs text-zinc-500">
              {messages.length
                ? `${messages.length} message${messages.length === 1 ? '' : 's'}`
                : 'Ask a question to start a cited answer'}
            </p>
          </div>
          {conversations.length > 0 && (
            <div className="hidden items-center gap-1 text-xs text-zinc-500 sm:flex">
              <span>{conversations.length} saved</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </div>
          )}
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4 sm:p-5">
          {messages.length === 0 && (
            <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center text-center">
              <Sparkles className="mb-3 h-8 w-8 text-cyan-300" />
              <p className="text-base font-medium text-zinc-200">Ask about your documents</p>
              <p className="mt-1 text-sm leading-6 text-zinc-500">
                Answers cite the passages they came from.
              </p>
              <div className="mt-4 grid w-full gap-2 sm:grid-cols-3">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => setInput(suggestion)}
                    className="min-h-11 rounded-md border border-zinc-800 bg-zinc-900/70 px-3 py-2 text-left text-xs leading-5 text-zinc-300 transition hover:border-cyan-500 hover:text-white"
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
          <div className="flex flex-col gap-3 sm:flex-row">
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
              className="min-h-12 flex-1 resize-none rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm text-white outline-none transition placeholder:text-zinc-500 focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/20"
            />
            {streaming ? (
              <button
                type="button"
                onClick={stop}
                className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md border border-zinc-700 px-4 py-2.5 text-sm font-medium text-zinc-300 transition hover:border-zinc-600 hover:text-white sm:w-auto sm:self-end"
              >
                <XCircle className="h-4 w-4" />
                Stop
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md bg-cyan-400 px-4 py-2.5 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400 sm:w-auto sm:self-end"
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
