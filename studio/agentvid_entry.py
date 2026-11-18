"""Standalone entrypoint for AgentVid Desktop Engine (used by both Python dev run and PyInstaller executable)."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _configure_paths() -> None:
    # When frozen by PyInstaller, resolve web/ and fonts/ from resources or bundled folder
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        res_dir = Path(os.environ.get("AGENTVID_RESOURCES") or exe_dir)
        os.environ.setdefault("AGENTVID_RESOURCES", str(res_dir))
    # Default to offline-first desktop mode: no forced PeakCut update pings or mandatory ASR download on startup
    os.environ.setdefault("PEAKCUT_ACCOUNTS", "0")
    os.environ.setdefault("PEAKCUT_UPDATE_CHECK", "0")
    os.environ.setdefault("PEAKCUT_FETCH_MODEL", "0")
    os.environ.setdefault("PEAKCUT_HOST", "127.0.0.1")


def main() -> None:
    _configure_paths()
    import uvicorn
    from studio import config, server

    host = os.environ.get("AGENTVID_HOST") or config.HOST or "127.0.0.1"
    port = int(os.environ.get("AGENTVID_PORT") or os.environ.get("PEAKCUT_PORT") or config.PORT or 8765)
    print(f"AgentVid Studio Engine starting on http://{host}:{port}", flush=True)
    uvicorn.run(server.app, host=host, port=port, log_level="warning", backlog=1024)


if __name__ == "__main__":
    main()
