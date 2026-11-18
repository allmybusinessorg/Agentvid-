"""AgentVid local project management, persistent settings, autosave, and session recovery."""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from . import config, media

_lock = threading.RLock()

ALLOWED_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".ts", ".flv"}
ALLOWED_AUDIO_EXTS = {".mp3", ".wav", ".aac", ".m4a", ".ogg", ".flac"}
PROJECT_ID_RE = re.compile(r"^avp_[a-f0-9]{10}$")
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._\- ]+")

AUTOMATION_SWITCH_KEYS = (
    "scene_detection",
    "shot_segmentation",
    "face_detection",
    "subject_tracking",
    "silence_detection",
    "caption_generation",
    "highlight_detection",
    "virality_scoring",
    "reframing",
    "zoom_suggestions",
    "transition_suggestions",
    "broll_suggestions",
    "editing_recommendations",
    "export_preparation",
)

DEFAULT_AUTOMATION_SWITCHES: dict[str, bool] = {
    "scene_detection": True,
    "shot_segmentation": True,
    "face_detection": True,
    "subject_tracking": True,
    "silence_detection": True,
    "caption_generation": True,
    "highlight_detection": True,
    "virality_scoring": True,
    "reframing": True,
    "zoom_suggestions": True,
    "transition_suggestions": True,
    "broll_suggestions": True,
    "editing_recommendations": True,
    "export_preparation": False,
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "auto_mode": True,
    "automation": dict(DEFAULT_AUTOMATION_SWITCHES),
    "face_detection": {
        "enabled": True,
        "mode": "auto",
        "sensitivity": 0.65,
        "min_face_size": 36,
        "multi_face": True,
        "primary_subject_id": None,
        "target_aspect": "9:16",
    },
    "privacy": {
        "local_only": True,
        "allow_cloud_ai": True,
        "telemetry": False,
    },
    "reels": {
        "count": 5,
        "duration_mode": "auto_ai",
        "target_duration": 30,
        "min_duration": 18,
        "max_duration": 58,
        "aspect": "9:16",
        "auto_captions": True,
    },
    "caption_defaults": {
        "language": "auto",
        "x_offset": 50,
        "y_offset": 80,
        "font_size": 64,
        "position": "bottom",
        "enabled": True,
    },
    "performance": {
        "hw_accel": "auto",
        "sample_fps": 1.5,
        "max_analysis_width": 480,
    },
    "export_defaults": {
        "format": "mp4",
        "codec": "h264",
        "resolution": "1080p",
        "aspect": "16:9",
        "fps": 30,
        "audio_bitrate": "192k",
        "output_dir": "",
    },
    "onboarding": {
        "completed": False,
        "completed_at": None,
        "instagram_clicked": False,
        "newsletter_subscribed": False,
    },
}

DEFAULT_CAPTION_CONFIG: dict[str, Any] = {
    "enabled": True,
    "language": "auto",
    "style": "liquid_glass",
    "animation": "word_reveal",
    "font": "Poppins ExtraBold",
    "font_weight": 800,
    "font_size": 64,
    "color": "#FFFFFF",
    "highlight_color": "#0066FF",
    "position": "bottom",
    "x_offset": 50,
    "y_offset": 80,
    "background": "glass",
    "background_opacity": 0.55,
    "shadow": True,
    "animation_speed": 1.0,
    "duration_scale": 1.0,
    "word_timing_offset": 0.0,
    "uppercase": False,
    "words_per_line": 4,
}


def projects_root() -> Path:
    d = config.DATA_DIR / "projects"
    d.mkdir(parents=True, exist_ok=True)
    return d


def exports_root() -> Path:
    d = config.DATA_DIR / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _settings_path() -> Path:
    return config.DATA_DIR / "agentvid_settings.json"


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def sanitize_filename(name: str, fallback: str = "media") -> str:
    base = Path(str(name or fallback)).name
    cleaned = SAFE_FILENAME_RE.sub("_", base).strip(" .")
    if not cleaned:
        cleaned = fallback
    return cleaned[:120]


def validate_project_id(pid: str) -> str:
    if not isinstance(pid, str) or not PROJECT_ID_RE.fullmatch(pid):
        raise ValueError("Invalid project identifier.")
    return pid


def project_dir(pid: str) -> Path:
    return projects_root() / validate_project_id(pid)


def _project_json(pid: str) -> Path:
    return project_dir(pid) / "project.json"


def _autosave_json(pid: str) -> Path:
    return project_dir(pid) / "autosave.json"


# ------------------------------------------------------------------ Settings
def get_settings() -> dict[str, Any]:
    with _lock:
        path = _settings_path()
        raw: dict[str, Any] = {}
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    raw = loaded
            except (OSError, ValueError):
                raw = {}
        merged = _deep_merge(DEFAULT_SETTINGS, raw)
        if not merged["export_defaults"].get("output_dir"):
            merged["export_defaults"]["output_dir"] = str(exports_root())
        return merged


def update_settings(patch: dict[str, Any]) -> dict[str, Any]:
    """Update persistent user settings. Toggling auto_mode NEVER alters saved individual switches."""
    if not isinstance(patch, dict):
        raise ValueError("Settings update must be a JSON object.")
    with _lock:
        cur = get_settings()
        nxt = copy.deepcopy(cur)

        if "auto_mode" in patch:
            nxt["auto_mode"] = bool(patch["auto_mode"])

        if isinstance(patch.get("automation"), dict):
            for k in AUTOMATION_SWITCH_KEYS:
                if k in patch["automation"]:
                    nxt["automation"][k] = bool(patch["automation"][k])

        if isinstance(patch.get("face_detection"), dict):
            fd = patch["face_detection"]
            if "enabled" in fd:
                nxt["face_detection"]["enabled"] = bool(fd["enabled"])
            if fd.get("mode") in ("auto", "manual"):
                nxt["face_detection"]["mode"] = fd["mode"]
            if "sensitivity" in fd:
                nxt["face_detection"]["sensitivity"] = max(0.1, min(1.0, float(fd["sensitivity"])))
            if "min_face_size" in fd:
                nxt["face_detection"]["min_face_size"] = max(16, min(240, int(fd["min_face_size"])))
            if "multi_face" in fd:
                nxt["face_detection"]["multi_face"] = bool(fd["multi_face"])
            if "primary_subject_id" in fd:
                val = fd["primary_subject_id"]
                nxt["face_detection"]["primary_subject_id"] = None if val in (None, "") else int(val)
            if fd.get("target_aspect") in ("9:16", "1:1", "16:9"):
                nxt["face_detection"]["target_aspect"] = fd["target_aspect"]

        if isinstance(patch.get("privacy"), dict):
            pr = patch["privacy"]
            for k in ("local_only", "allow_cloud_ai", "telemetry"):
                if k in pr:
                    nxt["privacy"][k] = bool(pr[k])

        if isinstance(patch.get("reels"), dict):
            rl = patch["reels"]
            if "count" in rl:
                nxt["reels"]["count"] = max(1, min(20, int(rl["count"])))
            if rl.get("duration_mode") in ("auto_ai", "fixed"):
                nxt["reels"]["duration_mode"] = rl["duration_mode"]
            if "target_duration" in rl:
                nxt["reels"]["target_duration"] = max(10, min(90, int(rl["target_duration"])))
            if "min_duration" in rl:
                nxt["reels"]["min_duration"] = max(10, min(55, int(rl["min_duration"])))
            if "max_duration" in rl:
                nxt["reels"]["max_duration"] = max(15, min(90, int(rl["max_duration"])))
            if rl.get("aspect") in ("9:16", "1:1", "16:9"):
                nxt["reels"]["aspect"] = rl["aspect"]
            if "auto_captions" in rl:
                nxt["reels"]["auto_captions"] = bool(rl["auto_captions"])
                nxt["caption_defaults"]["enabled"] = bool(rl["auto_captions"])

        if isinstance(patch.get("caption_defaults"), dict):
            cd = patch["caption_defaults"]
            if isinstance(cd.get("language"), str) and cd["language"].strip():
                nxt["caption_defaults"]["language"] = cd["language"].strip()[:24]
            if "x_offset" in cd:
                nxt["caption_defaults"]["x_offset"] = max(10, min(90, int(round(float(cd["x_offset"])))))
            if "y_offset" in cd:
                nxt["caption_defaults"]["y_offset"] = max(10, min(90, int(round(float(cd["y_offset"])))))
            if "font_size" in cd:
                nxt["caption_defaults"]["font_size"] = max(28, min(120, int(round(float(cd["font_size"])))))
            if cd.get("position") in ("top", "center", "bottom"):
                nxt["caption_defaults"]["position"] = cd["position"]
            if "enabled" in cd:
                nxt["caption_defaults"]["enabled"] = bool(cd["enabled"])
                nxt["reels"]["auto_captions"] = bool(cd["enabled"])

        if isinstance(patch.get("performance"), dict):
            pf = patch["performance"]
            if pf.get("hw_accel") in ("auto", "cpu"):
                nxt["performance"]["hw_accel"] = pf["hw_accel"]
            if "sample_fps" in pf:
                nxt["performance"]["sample_fps"] = max(0.5, min(5.0, float(pf["sample_fps"])))
            if "max_analysis_width" in pf:
                nxt["performance"]["max_analysis_width"] = max(240, min(960, int(pf["max_analysis_width"])))

        if isinstance(patch.get("export_defaults"), dict):
            ex = patch["export_defaults"]
            if ex.get("format") in ("mp4",):
                nxt["export_defaults"]["format"] = ex["format"]
            if ex.get("codec") in ("h264", "h265"):
                nxt["export_defaults"]["codec"] = ex["codec"]
            if ex.get("resolution") in ("720p", "1080p", "4k"):
                nxt["export_defaults"]["resolution"] = ex["resolution"]
            if ex.get("aspect") in ("16:9", "9:16", "1:1"):
                nxt["export_defaults"]["aspect"] = ex["aspect"]
            if ex.get("fps") in (24, 30, 60):
                nxt["export_defaults"]["fps"] = int(ex["fps"])
            if ex.get("audio_bitrate") in ("128k", "160k", "192k", "256k", "320k"):
                nxt["export_defaults"]["audio_bitrate"] = ex["audio_bitrate"]
            if isinstance(ex.get("output_dir"), str) and ex["output_dir"].strip():
                out_p = Path(ex["output_dir"].strip()).resolve()
                out_p.mkdir(parents=True, exist_ok=True)
                nxt["export_defaults"]["output_dir"] = str(out_p)

        if isinstance(patch.get("onboarding"), dict):
            ob = patch["onboarding"]
            if "completed" in ob:
                nxt["onboarding"]["completed"] = bool(ob["completed"])
                if ob["completed"] and not nxt["onboarding"].get("completed_at"):
                    nxt["onboarding"]["completed_at"] = time.time()
            if "instagram_clicked" in ob:
                nxt["onboarding"]["instagram_clicked"] = bool(ob["instagram_clicked"])
            if "newsletter_subscribed" in ob:
                nxt["onboarding"]["newsletter_subscribed"] = bool(ob["newsletter_subscribed"])

        _atomic_write_json(_settings_path(), nxt)
        return nxt


# ------------------------------------------------------------------ Projects
def _new_project_payload(pid: str, name: str, description: str = "") -> dict[str, Any]:
    now = time.time()
    settings = get_settings()
    return {
        "id": pid,
        "name": (name or "Untitled Project").strip()[:120] or "Untitled Project",
        "description": (description or "").strip()[:500],
        "created_at": now,
        "updated_at": now,
        "last_saved_at": now,
        "autosave_at": None,
        "session_state": "clean",
        "active_media_id": None,
        "media": [],
        "audio_tracks": [],
        "shots": [],
        "timeline": {
            "aspect": settings.get("reels", {}).get("aspect", "9:16"),
            "fps": 30,
            "background_music": None,
            "music_volume": 0.25,
            "master_volume": 1.0,
            "normalize_audio": True,
            "text_overlays": [],
            "caption_config": {
                **copy.deepcopy(DEFAULT_CAPTION_CONFIG),
                "enabled": bool(settings.get("caption_defaults", {}).get("enabled", settings.get("reels", {}).get("auto_captions", True))),
                "language": str(settings.get("caption_defaults", {}).get("language") or "auto"),
                "x_offset": int(settings.get("caption_defaults", {}).get("x_offset") or 50),
                "y_offset": int(settings.get("caption_defaults", {}).get("y_offset") or 80),
                "font_size": int(settings.get("caption_defaults", {}).get("font_size") or 64),
                "position": str(settings.get("caption_defaults", {}).get("position") or "bottom"),
            },
            "captions": [],
            "history_count": 0,
        },
        "face_tracking": {
            "config": copy.deepcopy(settings["face_detection"]),
            "status": "idle",
            "detected_faces_total": 0,
            "subjects": [],
            "frame_samples": [],
            "reframing_suggestions": {},
            "model": "OpenCV Haar/DNN Local Face Detector",
            "analyzed_at": None,
        },
        "virality": {
            "status": "idle",
            "overall_score": 0,
            "average_shot_score": 0,
            "highest_shot_id": None,
            "lowest_shot_id": None,
            "best_hook_shot_id": None,
            "best_emotional_shot_id": None,
            "best_standalone_shot_id": None,
            "recommended_sequence": [],
            "ai_enhanced": False,
            "disclaimer": "Virality scores are analytical predictions based on audiovisual signals and do not guarantee views or engagement.",
            "computed_at": None,
        },
        "analysis": {
            "status": "idle",
            "scene_count": 0,
            "silence_segments": [],
            "speech_segments": [],
            "transcript_words": [],
            "transcript_source": "none",
            "editing_plan": [],
            "broll_suggestions": [],
            "analyzed_at": None,
        },
        "exports": [],
        "activity_log": [
            {
                "id": uuid.uuid4().hex[:8],
                "ts": now,
                "level": "info",
                "stage": "project",
                "message": f"Created project '{(name or 'Untitled Project').strip()[:80]}'.",
            }
        ],
    }


def create_project(name: str, description: str = "") -> dict[str, Any]:
    with _lock:
        pid = f"avp_{uuid.uuid4().hex[:10]}"
        pdir = project_dir(pid)
        for sub in ("media", "thumbnails", "exports"):
            (pdir / sub).mkdir(parents=True, exist_ok=True)
        data = _new_project_payload(pid, name, description)
        _atomic_write_json(_project_json(pid), data)
        return copy.deepcopy(data)


def list_projects() -> list[dict[str, Any]]:
    with _lock:
        out = []
        for pdir in projects_root().iterdir():
            if not pdir.is_dir() or not PROJECT_ID_RE.fullmatch(pdir.name):
                continue
            jf = pdir / "project.json"
            if not jf.is_file():
                continue
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            shots = data.get("shots") or []
            high_potential = sum(1 for s in shots if (s.get("virality") or {}).get("score", 0) >= 75)
            has_autosave = (pdir / "autosave.json").is_file()
            thumb = ""
            if shots and shots[0].get("thumbnail_url"):
                thumb = shots[0]["thumbnail_url"]
            elif data.get("media") and data["media"][0].get("thumbnail_url"):
                thumb = data["media"][0]["thumbnail_url"]
            out.append({
                "id": data["id"],
                "name": data.get("name", "Untitled"),
                "description": data.get("description", ""),
                "created_at": data.get("created_at", 0),
                "updated_at": data.get("updated_at", 0),
                "media_count": len(data.get("media") or []),
                "shot_count": len(shots),
                "high_potential_shots": high_potential,
                "overall_virality": (data.get("virality") or {}).get("overall_score", 0),
                "analysis_status": (data.get("analysis") or {}).get("status", "idle"),
                "session_state": data.get("session_state", "clean"),
                "has_recovery": has_autosave,
                "thumbnail_url": thumb,
            })
        return sorted(out, key=lambda x: x.get("updated_at", 0), reverse=True)


def get_project(pid: str) -> dict[str, Any]:
    with _lock:
        jf = _project_json(pid)
        if not jf.is_file():
            raise FileNotFoundError(f"Project {pid} not found.")
        data = json.loads(jf.read_text(encoding="utf-8"))
        data["has_recovery"] = _autosave_json(pid).is_file()
        return data


def save_project(pid: str, data: dict[str, Any], clear_autosave: bool = False) -> dict[str, Any]:
    with _lock:
        validate_project_id(pid)
        now = time.time()
        nxt = copy.deepcopy(data)
        nxt["id"] = pid
        nxt["updated_at"] = now
        nxt["last_saved_at"] = now
        nxt["session_state"] = "clean"
        nxt.pop("has_recovery", None)
        _atomic_write_json(_project_json(pid), nxt)
        if clear_autosave:
            af = _autosave_json(pid)
            if af.is_file():
                try:
                    af.unlink()
                except OSError:
                    pass
        nxt["has_recovery"] = _autosave_json(pid).is_file()
        return nxt


def autosave_project(pid: str, patch: dict[str, Any] | None = None) -> dict[str, Any]:
    with _lock:
        cur = get_project(pid)
        now = time.time()
        nxt = copy.deepcopy(cur)
        if isinstance(patch, dict):
            for key in ("name", "description", "timeline", "shots", "active_media_id"):
                if key in patch:
                    nxt[key] = copy.deepcopy(patch[key])
        nxt["autosave_at"] = now
        nxt["updated_at"] = now
        nxt["session_state"] = "autosaved"
        nxt.pop("has_recovery", None)
        _atomic_write_json(_autosave_json(pid), nxt)
        return {"ok": True, "autosave_at": now}


def recover_project(pid: str, accept: bool = True) -> dict[str, Any]:
    with _lock:
        af = _autosave_json(pid)
        if not af.is_file():
            return get_project(pid)
        if accept:
            recovered = json.loads(af.read_text(encoding="utf-8"))
            recovered["activity_log"] = (recovered.get("activity_log") or [])[-199:] + [{
                "id": uuid.uuid4().hex[:8],
                "ts": time.time(),
                "level": "info",
                "stage": "recovery",
                "message": "Recovered autosaved session state.",
            }]
            return save_project(pid, recovered, clear_autosave=True)
        try:
            af.unlink()
        except OSError:
            pass
        return get_project(pid)


def rename_project(pid: str, new_name: str) -> dict[str, Any]:
    clean = (new_name or "").strip()[:120]
    if not clean:
        raise ValueError("Project name cannot be empty.")
    with _lock:
        cur = get_project(pid)
        cur["name"] = clean
        cur["activity_log"] = (cur.get("activity_log") or [])[-199:] + [{
            "id": uuid.uuid4().hex[:8],
            "ts": time.time(),
            "level": "info",
            "stage": "project",
            "message": f"Renamed project to '{clean}'.",
        }]
        return save_project(pid, cur)


def duplicate_project(pid: str, new_name: str | None = None) -> dict[str, Any]:
    with _lock:
        src = get_project(pid)
        src_dir = project_dir(pid)
        new_id = f"avp_{uuid.uuid4().hex[:10]}"
        dst_dir = project_dir(new_id)
        shutil.copytree(src_dir, dst_dir)
        af = dst_dir / "autosave.json"
        if af.is_file():
            af.unlink()
        now = time.time()
        dup = copy.deepcopy(src)
        dup["id"] = new_id
        dup["name"] = (new_name or f"{src.get('name', 'Project')} (Copy)").strip()[:120]
        dup["created_at"] = now
        dup["updated_at"] = now
        dup["last_saved_at"] = now
        # Update relative API URLs pointing to project id
        old_prefix = f"/api/v2/projects/{pid}/"
        new_prefix = f"/api/v2/projects/{new_id}/"
        serialized = json.dumps(dup, ensure_ascii=False).replace(old_prefix, new_prefix)
        dup = json.loads(serialized)
        dup["activity_log"] = (dup.get("activity_log") or [])[-199:] + [{
            "id": uuid.uuid4().hex[:8],
            "ts": now,
            "level": "info",
            "stage": "project",
            "message": f"Duplicated from project '{src.get('name', pid)}'.",
        }]
        return save_project(new_id, dup, clear_autosave=True)


def delete_project(pid: str) -> None:
    with _lock:
        pdir = project_dir(pid)
        if not pdir.is_dir():
            raise FileNotFoundError(f"Project {pid} not found.")
        shutil.rmtree(pdir)


def append_activity(pid: str, stage: str, message: str, level: str = "info") -> dict[str, Any]:
    with _lock:
        cur = get_project(pid)
        entry = {
            "id": uuid.uuid4().hex[:8],
            "ts": time.time(),
            "level": level,
            "stage": stage,
            "message": str(message)[:400],
        }
        log = list(cur.get("activity_log") or [])
        log.append(entry)
        cur["activity_log"] = log[-250:]
        save_project(pid, cur)
        return entry


# ------------------------------------------------------------------ Media Import
def probe_media_file(path: Path) -> dict[str, Any]:
    """Probe video/audio file metadata safely via ffprobe."""
    out = media.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,size,bit_rate:stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,sample_rate,channels",
        "-of", "json", str(path)
    ], timeout=60)
    raw = json.loads(out or "{}")
    fmt = raw.get("format") or {}
    streams = raw.get("streams") or []
    vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
    astream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    fps = 30.0
    if vstream:
        rate = vstream.get("avg_frame_rate") or vstream.get("r_frame_rate") or "30/1"
        if "/" in str(rate):
            num, den = str(rate).split("/", 1)
            try:
                if float(den) > 0:
                    fps = round(float(num) / float(den), 3)
            except ValueError:
                fps = 30.0
        else:
            try:
                fps = float(rate)
            except ValueError:
                fps = 30.0
    if fps <= 0 or fps > 240:
        fps = 30.0

    return {
        "duration": round(float(fmt.get("duration") or 0.0), 3),
        "size_bytes": int(fmt.get("size") or path.stat().st_size),
        "bitrate": int(fmt.get("bit_rate") or 0),
        "has_video": vstream is not None,
        "has_audio": astream is not None,
        "width": int((vstream or {}).get("width") or 0),
        "height": int((vstream or {}).get("height") or 0),
        "video_codec": (vstream or {}).get("codec_name") or "",
        "audio_codec": (astream or {}).get("codec_name") or "",
        "fps": fps,
        "sample_rate": int((astream or {}).get("sample_rate") or 0),
        "channels": int((astream or {}).get("channels") or 0),
    }


def _generate_media_thumb(src: Path, dst: Path, duration: float) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    seek = min(2.0, max(0.0, duration * 0.15))
    try:
        media.run([
            "ffmpeg", "-y", "-v", "error", "-ss", f"{seek:.2f}", "-i", str(src),
            "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "4", str(dst)
        ], timeout=60)
        return dst.is_file()
    except Exception:
        return False


def register_imported_media(pid: str, stored_path: Path, original_name: str, kind: str = "video") -> dict[str, Any]:
    """Validate an already-stored file inside project's media/ folder, probe it, generate thumbnail, and register it."""
    pdir = project_dir(pid)
    media_dir = (pdir / "media").resolve()
    resolved = stored_path.resolve()
    if not str(resolved).startswith(str(media_dir)):
        raise ValueError("Media file must reside inside project media storage.")
    ext = resolved.suffix.lower()
    if kind == "video" and ext not in ALLOWED_VIDEO_EXTS:
        raise ValueError(f"Unsupported video format: {ext}")
    if kind == "audio" and ext not in ALLOWED_AUDIO_EXTS:
        raise ValueError(f"Unsupported audio format: {ext}")

    meta = probe_media_file(resolved)
    if kind == "video" and (not meta["has_video"] or meta["duration"] <= 0):
        raise ValueError("The imported file does not contain a valid video stream.")
    if kind == "audio" and (not meta["has_audio"] or meta["duration"] <= 0):
        raise ValueError("The imported file does not contain a valid audio stream.")

    mid = f"med_{uuid.uuid4().hex[:10]}"
    thumb_name = ""
    thumb_url = ""
    if kind == "video":
        thumb_name = f"{mid}.jpg"
        if _generate_media_thumb(resolved, pdir / "thumbnails" / thumb_name, meta["duration"]):
            thumb_url = f"/api/v2/projects/{pid}/thumbnails/{thumb_name}"

    asset = {
        "id": mid,
        "kind": kind,
        "name": sanitize_filename(original_name, fallback=resolved.name),
        "filename": resolved.name,
        "stream_url": f"/api/v2/projects/{pid}/media/{resolved.name}",
        "thumbnail_url": thumb_url,
        "imported_at": time.time(),
        **meta,
    }

    with _lock:
        cur = get_project(pid)
        if kind == "audio":
            cur["audio_tracks"] = list(cur.get("audio_tracks") or []) + [asset]
        else:
            cur["media"] = list(cur.get("media") or []) + [asset]
            if not cur.get("active_media_id"):
                cur["active_media_id"] = mid
                # Match timeline aspect ratio to source orientation if fresh
                if meta["width"] and meta["height"]:
                    ratio = meta["width"] / meta["height"]
                    if ratio < 0.8:
                        cur["timeline"]["aspect"] = "9:16"
                    elif ratio < 1.2:
                        cur["timeline"]["aspect"] = "1:1"
                    else:
                        cur["timeline"]["aspect"] = "16:9"
        cur["activity_log"] = (cur.get("activity_log") or [])[-199:] + [{
            "id": uuid.uuid4().hex[:8],
            "ts": time.time(),
            "level": "info",
            "stage": "import",
            "message": f"Imported {kind} '{asset['name']}' ({meta['width']}x{meta['height']}, {meta['duration']:.1f}s).",
        }]
        save_project(pid, cur)
    return asset


def import_local_path(pid: str, local_path: str, kind: str = "video") -> dict[str, Any]:
    """Copy a validated local file from the user's computer into the project media folder (desktop mode)."""
    src = Path(str(local_path or "")).expanduser()
    if not src.is_file():
        raise FileNotFoundError("Selected file does not exist.")
    ext = src.suffix.lower()
    allowed = ALLOWED_VIDEO_EXTS if kind == "video" else ALLOWED_AUDIO_EXTS
    if ext not in allowed:
        raise ValueError(f"Unsupported file extension '{ext}'. Allowed: {', '.join(sorted(allowed))}")
    pdir = project_dir(pid)
    safe_name = f"{uuid.uuid4().hex[:8]}_{sanitize_filename(src.name)}"
    dst = pdir / "media" / safe_name
    shutil.copy2(src, dst)
    try:
        return register_imported_media(pid, dst, src.name, kind=kind)
    except Exception:
        try:
            dst.unlink()
        except OSError:
            pass
        raise


def get_active_media(proj: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    media_list = proj.get("media") or []
    if not media_list:
        raise ValueError("No video media imported in this project yet.")
    active_id = proj.get("active_media_id")
    chosen = next((m for m in media_list if m["id"] == active_id), media_list[0])
    path = project_dir(proj["id"]) / "media" / chosen["filename"]
    if not path.is_file():
        raise FileNotFoundError("Source media file is missing from local project storage.")
    return chosen, path


def dashboard_summary() -> dict[str, Any]:
    projs = list_projects()
    total_shots = sum(p["shot_count"] for p in projs)
    high_potential = sum(p["high_potential_shots"] for p in projs)
    recent_activity = []
    for p in projs[:6]:
        try:
            full = get_project(p["id"])
            for ev in (full.get("activity_log") or [])[-5:]:
                recent_activity.append({**ev, "project_id": p["id"], "project_name": p["name"]})
        except Exception:
            continue
    recent_activity.sort(key=lambda x: x.get("ts", 0), reverse=True)
    return {
        "project_count": len(projs),
        "total_analyzed_shots": total_shots,
        "high_potential_shots": high_potential,
        "recent_projects": projs[:8],
        "recent_activity": recent_activity[:15],
        "settings": get_settings(),
    }
