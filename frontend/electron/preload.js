const { contextBridge, ipcRenderer } = require('electron');

/**
 * Subscribe to a streaming endpoint.
 *
 * The renderer never sees a channel name or `ipcRenderer`; it passes a callback
 * and gets back a cancel function. The listener is removed on the terminal
 * frame, so an abandoned stream cannot leak a subscription.
 */
async function openStream(endpoint, body, onEvent) {
  if (typeof onEvent !== 'function') {
    throw new TypeError('a stream requires an event callback');
  }

  const result = await ipcRenderer.invoke('api:openStream', { endpoint, body });

  if (!result?.ok) {
    onEvent({ event: 'error', code: 'internal_error', error: result?.error || 'Stream failed' });
    return () => {};
  }

  const channel = `api:stream:${result.streamId}`;
  const listener = (_event, frame) => {
    if (frame?.event === 'closed') {
      ipcRenderer.removeListener(channel, listener);
      return;
    }
    onEvent(frame);
  };

  ipcRenderer.on(channel, listener);

  return () => {
    ipcRenderer.removeListener(channel, listener);
    ipcRenderer.invoke('api:cancelStream', result.streamId);
  };
}

/** One-shot document query. */
function streamQuery(request, onEvent) {
  // Only known fields are forwarded, so the renderer cannot smuggle arbitrary
  // properties into the main-process request.
  return openStream(
    'query',
    {
      query: String(request?.query ?? ''),
      k: Number(request?.k ?? 5),
      min_score: Number(request?.minScore ?? 0),
    },
    onEvent,
  );
}

/** One turn of a conversation. Omit conversationId to start a new one. */
function streamChat(request, onEvent) {
  const body = {
    message: String(request?.message ?? ''),
    k: Number(request?.k ?? 5),
    min_score: Number(request?.minScore ?? 0),
  };
  if (request?.conversationId) {
    body.conversation_id = String(request.conversationId);
  }
  return openStream('chat', body, onEvent);
}

contextBridge.exposeInMainWorld('desktop', {
  platform: process.platform,
  isElectron: true,
  apiRequest: (request) => ipcRenderer.invoke('api:request', request),
  selectDocuments: () => ipcRenderer.invoke('files:selectDocuments'),
  streamQuery,
  streamChat,
});
