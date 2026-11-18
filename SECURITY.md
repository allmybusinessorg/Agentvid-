# AgentVid — Security & Privacy Architecture

**AgentVid — AI Video Creation & Editing Studio**
A product by **Creative Creature (WE.ARECC)** · Created by **i.sayak007**

---

## 1. Local-First Privacy Guarantees

- **Media Never Leaves Your Computer by Default:** Video decoding, scene detection, shot segmentation, thumbnail generation, OpenCV YuNet face detection, subject tracking, audio/silence analysis, 15-dimension virality scoring, motion captions, and FFmpeg video export run **100% locally**.
- **Explicit Cloud AI Opt-In:** External LLM requests occur only when both (a) the user configures an AI provider key in Settings and (b) `Enable Cloud AI Enrichment` is explicitly turned ON in Privacy settings.
- **Zero Telemetry:** No analytics, crash-upload beacons, or forced upstream update pings are sent.
- **No Fabricated AI Outputs:** If a speech model or external AI provider is not configured, AgentVid clearly reports the status instead of fabricating transcripts or observations.

---

## 2. Electron Desktop Security Controls (`desktop/main.js`, `desktop/preload.js`)

- **Strict Renderer Isolation:** `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`, `webSecurity: true`.
- **Minimal Preload Surface:** Only six explicitly scoped IPC methods are exposed via `contextBridge`: `windowAction`, `pickMediaFile`, `pickDirectory`, `revealPath`, `openPath`, and `openExternal`.
- **Navigation & Popup Containment:** `will-navigate` restricts the main window strictly to its own `http://127.0.0.1:<port>` origin. `setWindowOpenHandler` denies all arbitrary popups.
- **External URL Allowlist:** `openExternal` only opens `https://` links matching an explicit host allowlist (such as `isayak007.vercel.app` and `www.instagram.com`).
- **Localhost-Only Backend:** The embedded engine binds strictly to `127.0.0.1` on an ephemeral local port and is terminated cleanly on application exit.

---

## 3. Backend Validation & Process Safety (`studio/`)

- **Input & Filename Sanitization:** Project IDs are validated against `^avp_[a-f0-9]{10}$`. All imported and exported filenames are sanitized against a strict allowlist regex and resolved with directory-containment checks to prevent path traversal (`..`, absolute paths, symlinks escaping project storage).
- **Media Validation:** Imported files are checked against explicit video/audio extension allowlists AND verified with `ffprobe` for valid streams before registration.
- **Safe Subprocess Execution:** FFmpeg/FFprobe commands are executed via argument lists (`subprocess.run([...])`, never `shell=True`), with strict timeouts and hidden console windows (`CREATE_NO_WINDOW`).
- **Request & Security Headers (`Gate` Middleware):** Enforces same-origin checks on mutating requests, per-route body size limits, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, and a strict Content Security Policy (CSP).
- **Secret Handling:** Optional AI provider keys are stored exclusively in local user data (`ai.json`, never in source code) and are never returned back to the UI (only a boolean `has_key` and 4-character hint).
