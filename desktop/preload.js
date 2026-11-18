"use strict";
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("agentvidDesktop", {
  isDesktop: true,
  windowAction: (action) => ipcRenderer.send("agentvid:window", String(action || "")),
  pickMediaFile: (kind) => ipcRenderer.invoke("agentvid:pick-media", kind === "audio" ? "audio" : "video"),
  pickDirectory: () => ipcRenderer.invoke("agentvid:pick-dir"),
  revealPath: (targetPath) => ipcRenderer.invoke("agentvid:reveal-path", String(targetPath || "")),
  openPath: (targetPath) => ipcRenderer.invoke("agentvid:open-path", String(targetPath || "")),
  openExternal: (url) => ipcRenderer.invoke("agentvid:open-external", String(url || "")),
});
