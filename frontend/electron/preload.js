const { contextBridge, ipcRenderer } = require('electron');

/**
 * Subscribe to a streaming query.
 *
 * The renderer never sees a channel name or `ipcRenderer`; it passes a callback
 * and gets back a cancel function. The listener is removed on the terminal
 * frame, so an abandoned stream cannot leak a subscription.
 */
async function streamQuery(request, onEvent) {
  if (typeof onEvent !== 'function') {
    throw new TypeError('streamQuery requires an event callback');
  }

  // Forward only known fields, so the renderer cannot smuggle arbitrary
  // properties into the main-process fetch.
  const result = await ipcRenderer.invoke('api:streamQuery', {
    query: String(request?.query ?? ''),
    k: Number(request?.k ?? 5),
    minScore: Number(request?.minScore ?? 0),
  });

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

contextBridge.exposeInMainWorld('desktop', {
  platform: process.platform,
  isElectron: true,
  apiRequest: (request) => ipcRenderer.invoke('api:request', request),
  selectDocuments: () => ipcRenderer.invoke('files:selectDocuments'),
  streamQuery,
});
