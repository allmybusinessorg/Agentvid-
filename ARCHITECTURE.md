# AgentVid — System Architecture

**AgentVid — AI Video Creation & Editing Studio**
A product by **Creative Creature (WE.ARECC)** · Created by **i.sayak007**

---

## 1. High-Level Architecture

AgentVid uses a decoupled, local-first two-process desktop architecture designed for stability, responsiveness, and zero mandatory cloud dependencies:

```
┌──────────────────────────────────────────────────────────────────────┐
│                   Electron Desktop Shell (desktop/)                  │
│  main.js (Process Lifecycle, Native Dialogs, Menu, Logging, IPC)     │
│  preload.js (Context-Isolated window.agentvidDesktop Bridge)         │
│  splash.html (Branded Startup Splash)                                │
│  BrowserWindow (web/index.html + agentvid.css + agentvid-app.js)     │
└─────────────────────────┬────────────────────────────────────────────┘
                          │ Loopback HTTP (127.0.0.1:<port>)
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│            Standalone Local Engine (agentvid-engine.exe)             │
│  studio/agentvid_entry.py -> FastAPI + Uvicorn (studio/server.py)    │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  AgentVid Studio Modules (/api/v2/*)                           │  │
│  │  • projects.py        Local project store, settings, recovery  │  │
│  │  • automation.py      AUTO/MANUAL runner (14 switches, pause)  │  │
│  │  • video_analysis.py  Scene cuts, shots, audio/silence, thumbs │  │
│  │  • face_tracker.py    OpenCV YuNet ONNX face/landmark tracker  │  │
│  │  • virality.py        15-dimension weighted virality engine    │  │
│  │  • editor_engine.py   Non-destructive edits, ASS, FFmpeg export│  │
│  │  • assistant.py       Grounded studio intelligence assistant   │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │  Preserved Upstream PeakCut Core                               │  │
│  │  • ai.py (Multi-provider LLM adapter) · render.py · media.py   │  │
│  │  • transcribe.py (Optional local ASR) · tools.py · db.py       │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Local Project Storage Layout

All user data stays local under `%APPDATA%\AgentVid\data` (or `AGENTVID_DATA`):

```
data/
├── agentvid.db                 # SQLite WAL database
├── agentvid_settings.json      # Persistent AUTO/MANUAL, 14 switches, face, privacy, export defaults
├── ai.json                     # Optional local-only AI provider configuration (chmod 0600)
├── fonts/                      # Bundled SIL OFL caption fonts (Poppins, Anton, Archivo Black)
├── exports/                    # Default export output folder
└── projects/
    └── avp_<id>/
        ├── project.json        # Atomic project manifest (shots, timeline, virality, faces, logs)
        ├── autosave.json       # Periodic recovery snapshot (present only when dirty)
        ├── media/              # Validated imported video & background audio assets
        ├── thumbnails/         # Generated per-media & per-shot JPEG thumbnails
        └── exports/            # Rendered MP4 files + logs
```

All JSON persistence uses atomic temp-file writes followed by `os.replace()` to prevent project corruption if power or processes are interrupted.

---

## 3. Video Analysis, Face Tracking & Virality Pipeline

1. **Frame Sampling (`video_analysis.py`):** Streams frames sequentially via OpenCV `VideoCapture` at configurable `sample_fps` (default 1.5 fps) downscaled to `<= 384px` wide—never loading entire video files into memory.
2. **Scene & Shot Segmentation:** Computes HSV color histogram distances and grayscale frame deltas to find adaptive visual cuts, plus subdivides long continuous takes using detected silence boundaries. Generates real JPEG thumbnails per shot via FFmpeg.
3. **Audio & Silence Analysis:** Extracts 16kHz mono PCM to a short temp directory, computes 250ms RMS + zero-crossing windows for SNR audio clarity, silence segments, and speech activity. Runs local ASR only when a local speech model is present; never fabricates transcripts.
4. **AI Face Detection & Multi-Subject Tracking (`face_tracker.py`):** Uses the bundled 232KB OpenCV YuNet ONNX neural network (`cv2.FaceDetectorYN`) outputting calibrated confidence scores and 5 facial landmarks (eyes, nose, mouth corners). Tracks multiple subjects across frames via IoU + centroid proximity, detecting entries, exits, close-ups, and suspected obstructions, and computes headroom-protected `9:16`, `1:1`, and `16:9` crop boxes.
5. **15-Dimension Virality Model (`virality.py`):** Explicitly weights 15 measurable audiovisual and structural criteria (sum of weights = `1.00`) into a transparent 0–100 score per shot and video-level dashboard metrics.

---

## 4. Non-Destructive Editing & FFmpeg Export (`editor_engine.py`)

Source media is never overwritten. Every trim, split, merge, reorder, zoom, pan, speed, audio gain, transition, text overlay, and motion caption configuration is stored declaratively on the project timeline and compiled at export time into a multi-stage FFmpeg filter graph:
- Per-shot segment rendering with exact crop/zoom/pan, `lanczos` scaling, `setpts`/`atempo` speed chains, and uniform 48kHz stereo audio.
- Timeline assembly via FFmpeg `xfade` / `acrossfade` (when transitions are set) or lossless stream `concat`.
- Motion graphics & captions compiled to ASS v4.00+ inside a short temporary directory (bypassing Windows 260-char `libass` path limits) and burned in during final encoding.
- Encoder cascade: GPU hardware encoders (`h264_nvenc` / `hevc_nvenc`, `h264_qsv` / `hevc_qsv`) with automatic fallback to `libx264` / `libx265`.
