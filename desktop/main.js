"use strict";

const { app, BrowserWindow, Menu, dialog, ipcMain, shell } = require("electron");
const { spawn, execFileSync } = require("child_process");
const fs = require("fs");
const http = require("http");
const net = require("net");
const path = require("path");

const ALLOWED_EXTERNAL_HOSTS = new Set([
  "isayak007.vercel.app",
  "www.instagram.com",
  "instagram.com",
  "github.com",
  "aistudio.google.com",
  "platform.openai.com",
  "console.anthropic.com",
  "openrouter.ai",
  "ollama.com",
]);

let mainWindow = null;
let splashWindow = null;
let backendProc = null;
let backendPort = 8765;
let isQuitting = false;

const userDataDir = app.getPath("userData");
const dataDir = path.join(userDataDir, "data");
const logsDir = path.join(userDataDir, "logs");
fs.mkdirSync(dataDir, { recursive: true });
fs.mkdirSync(logsDir, { recursive: true });
const logFile = path.join(logsDir, "desktop.log");

function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}\n`;
  try { fs.appendFileSync(logFile, line, "utf8"); } catch { /* ignore */ }
}

// Single-instance lock
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}

function findFreePort(preferred = 18765) {
  return new Promise((resolve) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", () => {
      const srv2 = net.createServer();
      srv2.listen(0, "127.0.0.1", () => {
        const port = srv2.address().port;
        srv2.close(() => resolve(port));
      });
    });
    srv.listen(preferred, "127.0.0.1", () => {
      srv.close(() => resolve(preferred));
    });
  });
}

function waitForHealth(port, timeoutMs = 45000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const req = http.get(`http://127.0.0.1:${port}/healthz`, (res) => {
        res.resume();
        if (res.statusCode === 200) return resolve(true);
        retry();
      });
      req.on("error", retry);
      req.setTimeout(1500, () => { req.destroy(); retry(); });
    };
    const retry = () => {
      if (Date.now() - start > timeoutMs) {
        return reject(new Error("AgentVid local engine did not respond in time."));
      }
      setTimeout(attempt, 350);
    };
    attempt();
  });
}

function startBackend(port) {
  const env = {
    ...process.env,
    AGENTVID_HOST: "127.0.0.1",
    AGENTVID_PORT: String(port),
    AGENTVID_DATA: dataDir,
    PEAKCUT_HOST: "127.0.0.1",
    PEAKCUT_PORT: String(port),
    PEAKCUT_DATA: dataDir,
    PEAKCUT_ACCOUNTS: "0",
    PEAKCUT_UPDATE_CHECK: "0",
    PEAKCUT_FETCH_MODEL: "0",
  };

  let cmd;
  let args;
  let cwd;

  if (app.isPackaged) {
    const engineExe = path.join(process.resourcesPath, "engine", "agentvid-engine.exe");
    env.AGENTVID_RESOURCES = process.resourcesPath;
    cmd = engineExe;
    args = [];
    cwd = path.join(process.resourcesPath, "engine");
  } else {
    const repoRoot = path.resolve(__dirname, "..");
    const venvPy = path.join(repoRoot, ".venv", "Scripts", "python.exe");
    cmd = fs.existsSync(venvPy) ? venvPy : "python";
    args = ["-m", "studio.agentvid_entry"];
    cwd = repoRoot;
  }

  log(`Spawning engine: ${cmd} ${args.join(" ")} on 127.0.0.1:${port}`);
  backendProc = spawn(cmd, args, {
    cwd,
    env,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });

  backendProc.stdout.on("data", (d) => log(`[engine:out] ${String(d).trim()}`));
  backendProc.stderr.on("data", (d) => log(`[engine:err] ${String(d).trim()}`));
  backendProc.on("exit", (code) => {
    log(`Engine exited with code ${code}`);
    backendProc = null;
    if (!isQuitting && mainWindow) {
      dialog.showErrorBox(
        "AgentVid Engine Stopped",
        `The local video processing engine exited unexpectedly (code ${code}).\nLogs: ${logFile}`
      );
    }
  });
}

function stopBackend() {
  if (!backendProc) return;
  const pid = backendProc.pid;
  log(`Stopping backend engine (PID ${pid})`);
  try {
    if (process.platform === "win32") {
      execFileSync("taskkill", ["/PID", String(pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" });
    } else {
      backendProc.kill("SIGTERM");
    }
  } catch {
    try { backendProc.kill(); } catch { /* ignore */ }
  }
  backendProc = null;
}

function createSplash() {
  splashWindow = new BrowserWindow({
    width: 440,
    height: 290,
    frame: false,
    transparent: true,
    resizable: false,
    alwaysOnTop: true,
    center: true,
    icon: path.join(__dirname, "assets", "icon.ico"),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  splashWindow.loadFile(path.join(__dirname, "splash.html"));
}

function createMainWindow(port) {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1080,
    minHeight: 700,
    show: false,
    frame: false,
    backgroundColor: "#06070b",
    title: "AgentVid — AI Video Creation & Editing Studio",
    icon: path.join(__dirname, "assets", "icon.ico"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      spellcheck: false,
    },
  });

  const allowedOrigin = `http://127.0.0.1:${port}`;
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    safeOpenExternal(url);
    return { action: "deny" };
  });
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith(allowedOrigin)) {
      event.preventDefault();
      safeOpenExternal(url);
    }
  });

  mainWindow.loadURL(`${allowedOrigin}/app`);
  mainWindow.once("ready-to-show", () => {
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.close();
      splashWindow = null;
    }
    mainWindow.show();
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  buildMenu();
}

function safeOpenExternal(rawUrl) {
  try {
    const parsed = new URL(rawUrl);
    if (parsed.protocol === "https:" && ALLOWED_EXTERNAL_HOSTS.has(parsed.hostname.toLowerCase())) {
      shell.openExternal(parsed.toString());
    }
  } catch {
    /* invalid URL ignored */
  }
}

function buildMenu() {
  const template = [
    {
      label: "AgentVid",
      submenu: [
        { label: "Reload Studio", accelerator: "CmdOrCtrl+R", click: () => mainWindow && mainWindow.reload() },
        { type: "separator" },
        { label: "Open Data Folder", click: () => shell.openPath(dataDir) },
        { label: "Open Logs Folder", click: () => shell.openPath(logsDir) },
        { type: "separator" },
        { role: "quit", label: "Exit AgentVid" },
      ],
    },
    {
      label: "Edit",
      submenu: [
        { role: "undo" },
        { role: "redo" },
        { type: "separator" },
        { role: "cut" },
        { role: "copy" },
        { role: "paste" },
        { role: "selectAll" },
      ],
    },
    {
      label: "View",
      submenu: [
        { role: "togglefullscreen" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { role: "resetZoom" },
      ],
    },
    {
      label: "About",
      submenu: [
        {
          label: "Creator Website (i.sayak007)",
          click: () => safeOpenExternal("https://isayak007.vercel.app/"),
        },
        {
          label: "Creative Creature Instagram (@we.arecc)",
          click: () => safeOpenExternal("https://www.instagram.com/we.arecc/"),
        },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// ------------------------------------------------------------------ Validated IPC Handlers
ipcMain.on("agentvid:window", (_ev, action) => {
  if (!mainWindow) return;
  if (action === "minimize") mainWindow.minimize();
  else if (action === "maximize") {
    if (mainWindow.isMaximized()) mainWindow.unmaximize();
    else mainWindow.maximize();
  } else if (action === "close") mainWindow.close();
});

ipcMain.handle("agentvid:pick-media", async (_ev, kind) => {
  if (!mainWindow) return null;
  const filters = kind === "audio"
    ? [{ name: "Audio Files", extensions: ["mp3", "wav", "aac", "m4a", "ogg", "flac"] }]
    : [{ name: "Video Files", extensions: ["mp4", "mov", "mkv", "webm", "m4v", "avi", "ts", "flv"] }];
  const res = await dialog.showOpenDialog(mainWindow, {
    title: kind === "audio" ? "Import Background Audio — AgentVid" : "Import Video — AgentVid",
    properties: ["openFile"],
    filters,
  });
  return res.canceled || !res.filePaths.length ? null : res.filePaths[0];
});

ipcMain.handle("agentvid:pick-dir", async () => {
  if (!mainWindow) return null;
  const res = await dialog.showOpenDialog(mainWindow, {
    title: "Select Export Folder — AgentVid",
    properties: ["openDirectory", "createDirectory"],
  });
  return res.canceled || !res.filePaths.length ? null : res.filePaths[0];
});

ipcMain.handle("agentvid:reveal-path", async (_ev, targetPath) => {
  if (!targetPath || !fs.existsSync(targetPath)) return false;
  shell.showItemInFolder(path.resolve(targetPath));
  return true;
});

ipcMain.handle("agentvid:open-path", async (_ev, targetPath) => {
  if (!targetPath || !fs.existsSync(targetPath)) return false;
  const resolved = path.resolve(targetPath);
  if (fs.statSync(resolved).isDirectory()) {
    await shell.openPath(resolved);
    return true;
  }
  return false;
});

ipcMain.handle("agentvid:open-external", async (_ev, url) => {
  safeOpenExternal(url);
  return true;
});

// ------------------------------------------------------------------ Lifecycle
app.whenReady().then(async () => {
  createSplash();
  try {
    backendPort = await findFreePort(18765);
    startBackend(backendPort);
    await waitForHealth(backendPort, 45000);
    createMainWindow(backendPort);
  } catch (err) {
    log(`Startup failed: ${err.stack || err.message}`);
    if (splashWindow && !splashWindow.isDestroyed()) splashWindow.close();
    dialog.showErrorBox(
      "AgentVid Failed to Start",
      `${err.message}\n\nCheck logs at:\n${logFile}`
    );
    app.quit();
  }
});

app.on("before-quit", () => {
  isQuitting = true;
  stopBackend();
});

app.on("window-all-closed", () => {
  isQuitting = true;
  stopBackend();
  app.quit();
});
