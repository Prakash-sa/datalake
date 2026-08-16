const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('desktop', {
  platform: process.platform,
  isElectron: true,
  apiRequest: (request) => ipcRenderer.invoke('api:request', request),
});
