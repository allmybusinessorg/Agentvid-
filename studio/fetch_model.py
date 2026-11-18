"""AgentVid Offline Speech-to-Text Model Manager (Parakeet 0.6B via sherpa-onnx).

Downloaded once on demand (~480 MB, 100% offline, no API key required). Unpacked atomically into a
staging folder and moved into place only when complete so interrupted downloads never leave broken files.
"""
from __future__ import annotations

import importlib.util
import shutil
import tarfile
import threading
import urllib.request
from typing import Any

from . import config

URL = f"https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{config.ASR_MODEL_NAME}.tar.bz2"
_lock = threading.Lock()
_cancel_event = threading.Event()
state: dict[str, Any] = {
    "doing": False,
    "percent": 0,
    "downloaded_mb": 0.0,
    "total_mb": 480.0,
    "items_done": 0,
    "items_total": 4,
    "stage": "idle",
    "error": "",
}


def library_installed() -> bool:
    return importlib.util.find_spec("sherpa_onnx") is not None


def ready() -> bool:
    """Is the complete offline speech model installed on this PC?"""
    d = config.ASR_MODEL_DIR
    if not (d / "tokens.txt").is_file():
        return False
    return all(any(d.glob(f"{part}*.onnx")) for part in ("encoder", "decoder", "joiner"))


def status() -> dict[str, Any]:
    is_ready = ready()
    return {
        "ready": is_ready,
        "library_installed": library_installed(),
        "doing": bool(state["doing"]),
        "percent": 100 if is_ready else int(state["percent"]),
        "downloaded_mb": round(float(state["downloaded_mb"]), 1),
        "total_mb": round(float(state["total_mb"]), 1),
        "items_done": int(state["items_total"]) if is_ready else int(state.get("items_done") or 0),
        "items_total": int(state.get("items_total") or 4),
        "stage": "ready" if is_ready and not state["doing"] else state["stage"],
        "error": "" if is_ready else str(state["error"] or ""),
        "model_name": config.ASR_MODEL_NAME,
        "size_hint": "~480 MB",
        "path": str(config.ASR_MODEL_DIR),
    }


def cancel() -> dict[str, Any]:
    _cancel_event.set()
    if state["doing"]:
        state["stage"] = "cancelling"
    return status()


def ensure() -> None:
    """Download and unpack the offline speech model once. Supports live progress and clean cancellation."""
    if ready():
        return
    with _lock:
        if ready():
            return
        _cancel_event.clear()
        state.update(doing=True, percent=0, downloaded_mb=0.0, total_mb=480.0, items_done=0, items_total=4, stage="downloading", error="")
        print("\n  AgentVid: Downloading offline speech model (one time, ~480 MB)...\n", flush=True)
        config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        tmp = config.MODELS_DIR / "speech-model.tar.bz2"
        part = config.MODELS_DIR / "speech-model.unpacking"
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "AgentVid-Studio/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                if total > 0:
                    state["total_mb"] = round(total / (1024 * 1024), 1)
                done = 0
                with tmp.open("wb") as out_f:
                    while True:
                        if _cancel_event.is_set():
                            raise InterruptedError("Download cancelled by user.")
                        chunk = resp.read(256 * 1024)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        done += len(chunk)
                        state["downloaded_mb"] = round(done / (1024 * 1024), 1)
                        if total > 0:
                            state["percent"] = min(88, int(done * 88 / total))

            if _cancel_event.is_set():
                raise InterruptedError("Download cancelled by user.")

            state.update(stage="extracting", percent=90)
            shutil.rmtree(part, ignore_errors=True)
            part.mkdir()
            with tarfile.open(tmp, "r:bz2") as t:
                members = [
                    m for m in t.getmembers()
                    if (m.isfile() or m.isdir()) and not m.name.startswith(("/", "..")) and ".." not in m.name.split("/")
                ]
                file_members = [m for m in members if m.isfile()]
                state["items_total"] = max(1, len(file_members))
                extracted_files = 0
                for idx, m in enumerate(members, start=1):
                    if _cancel_event.is_set():
                        raise InterruptedError("Download cancelled by user.")
                    t.extract(m, part)
                    if m.isfile():
                        extracted_files += 1
                        state["items_done"] = extracted_files
                    state["percent"] = min(99, 90 + int(idx * 9 / max(1, len(members))))

            got = part / config.ASR_MODEL_NAME
            if not got.is_dir():
                raise OSError("The downloaded archive did not contain the expected speech model folder.")
            shutil.rmtree(config.ASR_MODEL_DIR, ignore_errors=True)
            got.rename(config.ASR_MODEL_DIR)
            state.update(stage="ready", percent=100, error="")
            print("  AgentVid: Offline speech model ready.\n", flush=True)
        except InterruptedError:
            state.update(stage="cancelled", percent=0, error="Download cancelled.")
        except Exception as e:  # noqa: BLE001
            state.update(stage="error", error=str(e)[-240:])
            raise RuntimeError(
                "AgentVid couldn't download the offline speech model (~480 MB, one-time download). "
                "Check your internet connection and free disk space, then try again."
            ) from e
        finally:
            state["doing"] = False
            tmp.unlink(missing_ok=True)
            shutil.rmtree(part, ignore_errors=True)


def start_background() -> dict[str, Any]:
    if ready() or state["doing"]:
        return status()
    if not library_installed():
        state["error"] = "Offline speech runtime (sherpa-onnx) is not installed in this environment."
        state["stage"] = "error"
        return status()

    def _run():
        try:
            ensure()
        except Exception:
            pass

    threading.Thread(target=_run, name="agentvid-speech-dl", daemon=True).start()
    return status()


def main():
    if ready():
        print("Offline speech model already installed.")
        return
    ensure()


if __name__ == "__main__":
    main()
