/**
 * NEXUS Desktop — Preload Script
 * Secure IPC bridge between renderer and main process.
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Window controls
  minimize:    () => ipcRenderer.send('window-minimize'),
  maximize:    () => ipcRenderer.send('window-maximize'),
  close:       () => ipcRenderer.send('window-close'),
  isMaximized: () => ipcRenderer.invoke('is-maximized'),

  // Platform info
  platform: process.platform,

  // Listen for events from main
  on: (channel, callback) => {
    const allowed = ['window-maximized', 'window-unmaximized'];
    if (allowed.includes(channel)) {
      ipcRenderer.on(channel, (_, ...args) => callback(...args));
    }
  },
});
