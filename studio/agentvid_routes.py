"""AgentVid Studio REST API router (/api/v2/*)."""
from __future__ import annotations

import os
import platform
import re
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from . import (
    ai,
    ai_transcribe,
    assistant,
    automation,
    config,
    editor_engine,
    face_tracker,
    fetch_model,
    fonts_manager,
    projects,
    tools,
    url_ingest,
    virality,
)

router = APIRouter(prefix="/api/v2", tags=["agentvid"])

APP_VERSION = "1.0.0"
BUILD_CHANNEL = "Windows Standalone Studio"


def _safe_file_in(folder: Path, name: str) -> Path:
    if not name or "/" in name or "\\" in name or ".." in name or not re.fullmatch(r"[A-Za-z0-9._\- ]+", name):
        raise HTTPException(400, "Invalid file name.")
    target = (folder / name).resolve()
    if not str(target).startswith(str(folder.resolve())):
        raise HTTPException(403, "Access denied.")
    if not target.is_file():
        raise HTTPException(404, "File not found.")
    return target


# ------------------------------------------------------------------ System / Dashboard / About / Settings
@router.get("/dashboard")
def get_dashboard():
    return projects.dashboard_summary()


@router.get("/about")
def get_about():
    license_text = ""
    notices_text = ""
    for candidate in (config.ROOT / "LICENSE", Path(os.environ.get("AGENTVID_RESOURCES", "")) / "LICENSE"):
        if candidate.is_file():
            license_text = candidate.read_text(encoding="utf-8", errors="replace")
            break
    for candidate in (config.ROOT / "THIRD_PARTY_NOTICES.md", Path(os.environ.get("AGENTVID_RESOURCES", "")) / "THIRD_PARTY_NOTICES.md"):
        if candidate.is_file():
            notices_text = candidate.read_text(encoding="utf-8", errors="replace")
            break
    return {
        "product_name": "AgentVid",
        "subtitle": "AI Video Creation & Editing Studio",
        "agency": "Creative Creature",
        "agency_identity": "WE.ARECC",
        "creator": "i.sayak007",
        "creator_website": "https://isayak007.vercel.app/",
        "agency_instagram": "https://www.instagram.com/we.arecc/",
        "version": APP_VERSION,
        "build": BUILD_CHANNEL,
        "python": platform.python_version(),
        "os": f"{platform.system()} {platform.release()}",
        "ffmpeg_ready": len(tools.missing()) == 0,
        "missing_tools": tools.missing(),
        "data_dir": str(config.DATA_DIR),
        "license": license_text,
        "third_party_notices": notices_text,
    }


@router.get("/settings")
def get_settings():
    return {
        "settings": projects.get_settings(),
        "ai": ai.public(),
        "caption_styles": list(editor_engine.CAPTION_STYLES.values()),
        "caption_animations": list(editor_engine.CAPTION_ANIMATIONS.values()),
        "caption_languages": ai_transcribe.CAPTION_LANGUAGES,
        "ai_audio_ready": ai_transcribe._can_ai_transcribe_audio(),
        "fonts": fonts_manager.list_fonts(),
        "virality_weights": virality.DIMENSION_WEIGHTS,
        "virality_labels": virality.DIMENSION_LABELS,
        "speech_model": fetch_model.status(),
        "ffmpeg_ready": len(tools.missing()) == 0,
        "data_dir": str(config.DATA_DIR),
    }


# ------------------------------------------------------------------ Offline Speech Model (One-Time Download)
@router.get("/speech-model/status")
def get_speech_model_status():
    return {"speech_model": fetch_model.status()}


@router.post("/speech-model/download")
def download_speech_model():
    return {"speech_model": fetch_model.start_background()}


@router.post("/speech-model/cancel")
def cancel_speech_model_download():
    return {"speech_model": fetch_model.cancel()}


# ------------------------------------------------------------------ Custom Font Management (.ttf / .otf)
@router.get("/fonts")
def list_fonts():
    return {"fonts": fonts_manager.list_fonts()}


@router.post("/fonts/upload")
async def upload_custom_font(file: UploadFile = File(...)):
    raw = await file.read(26 * 1024 * 1024)
    try:
        installed = fonts_manager.install_custom_font(raw, file.filename or "custom.ttf")
        return {"font": installed, "fonts": fonts_manager.list_fonts()}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/fonts/file/{filename}")
def serve_font_file(filename: str):
    path = _safe_file_in(config.FONTS_DIR, filename)
    mtype = "font/otf" if filename.lower().endswith(".otf") else "font/ttf"
    return FileResponse(path, media_type=mtype, headers={"Cache-Control": "public, max-age=604800"})


@router.delete("/fonts/{filename}")
def remove_custom_font(filename: str):
    try:
        fonts_manager.delete_custom_font(filename)
        return {"ok": True, "fonts": fonts_manager.list_fonts()}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/settings")
def put_settings(body: dict = Body(...)):
    try:
        updated = projects.update_settings(body)
        return {"settings": updated}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/settings/ai")
def put_ai_settings(body: dict = Body(...)):
    try:
        res = ai.save(
            body.get("provider", ""),
            body.get("models", []),
            body.get("base_url", ""),
            body.get("key"),
        )
        return {"ai": res}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/settings/ai/test")
def test_ai_settings():
    try:
        return ai.test()
    except Exception as e:
        raise HTTPException(400, str(e))


# ------------------------------------------------------------------ Projects CRUD
@router.get("/projects")
def list_projects():
    return {"projects": projects.list_projects()}


@router.post("/projects")
def create_project(body: dict = Body(...)):
    name = str(body.get("name") or "Untitled Project").strip()
    desc = str(body.get("description") or "").strip()
    return {"project": projects.create_project(name, desc)}


@router.get("/projects/{pid}")
def get_project(pid: str):
    try:
        proj = projects.get_project(pid)
        return {
            "project": proj,
            "automation": automation.get_status(pid),
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, "Project not found.")


@router.put("/projects/{pid}/rename")
def rename_project(pid: str, body: dict = Body(...)):
    try:
        return {"project": projects.rename_project(pid, str(body.get("name") or ""))}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, "Project not found.")


@router.post("/projects/{pid}/duplicate")
def duplicate_project(pid: str, body: dict = Body(default={})):
    try:
        return {"project": projects.duplicate_project(pid, body.get("name"))}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, "Project not found.")


@router.delete("/projects/{pid}")
def delete_project(pid: str):
    try:
        automation.stop(pid)
        projects.delete_project(pid)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, "Project not found.")


@router.post("/projects/{pid}/save")
def save_project(pid: str, body: dict = Body(default={})):
    try:
        cur = projects.get_project(pid)
        for k in ("name", "description", "timeline", "shots", "active_media_id"):
            if k in body:
                cur[k] = body[k]
        saved = projects.save_project(pid, cur, clear_autosave=True)
        return {"project": saved}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, "Project not found.")


@router.post("/projects/{pid}/autosave")
def autosave_project(pid: str, body: dict = Body(default={})):
    try:
        return projects.autosave_project(pid, body)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, "Project not found.")


@router.post("/projects/{pid}/recover")
def recover_project(pid: str, body: dict = Body(default={"accept": True})):
    try:
        return {"project": projects.recover_project(pid, accept=bool(body.get("accept", True)))}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, "Project not found.")


# ------------------------------------------------------------------ Media Import & Static Serving
@router.post("/projects/{pid}/media/upload")
async def upload_media(
    pid: str,
    file: UploadFile = File(...),
    kind: str = Form("video"),
    trigger_auto: bool = Form(True),
):
    if kind not in ("video", "audio"):
        raise HTTPException(400, "Media kind must be 'video' or 'audio'.")
    try:
        pdir = projects.project_dir(pid)
        if not (pdir / "project.json").is_file():
            raise HTTPException(404, "Project not found.")
    except ValueError as e:
        raise HTTPException(400, str(e))

    orig_name = projects.sanitize_filename(file.filename or f"upload.{'mp4' if kind == 'video' else 'mp3'}")
    ext = Path(orig_name).suffix.lower()
    allowed = projects.ALLOWED_VIDEO_EXTS if kind == "video" else projects.ALLOWED_AUDIO_EXTS
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported {kind} format '{ext}'. Allowed: {', '.join(sorted(allowed))}")

    dst = pdir / "media" / f"{uuid.uuid4().hex[:8]}_{orig_name}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        with dst.open("wb") as out_f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                out_f.write(chunk)
        asset = projects.register_imported_media(pid, dst, orig_name, kind=kind)
    except Exception as e:
        try:
            dst.unlink()
        except OSError:
            pass
        raise HTTPException(400, str(e))

    auto_state = None
    if kind == "video" and trigger_auto:
        auto_state = automation.start_pipeline(pid, trigger="auto")

    return {
        "media": asset,
        "project": projects.get_project(pid),
        "automation": auto_state or automation.get_status(pid),
    }


@router.post("/projects/{pid}/media/import-local")
def import_local_media(pid: str, body: dict = Body(...)):
    """Desktop local file import (only permitted in single-user local desktop mode)."""
    if config.ACCOUNTS:
        raise HTTPException(403, "Direct local filesystem import is disabled in multi-user mode.")
    local_path = str(body.get("path") or "").strip()
    kind = str(body.get("kind") or "video")
    if kind not in ("video", "audio"):
        raise HTTPException(400, "Invalid media kind.")
    try:
        asset = projects.import_local_path(pid, local_path, kind=kind)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))

    auto_state = None
    if kind == "video" and bool(body.get("trigger_auto", True)):
        auto_state = automation.start_pipeline(pid, trigger="auto")

    return {
        "media": asset,
        "project": projects.get_project(pid),
        "automation": auto_state or automation.get_status(pid),
    }


@router.put("/projects/{pid}/media/active")
def set_active_media(pid: str, body: dict = Body(...)):
    try:
        proj = projects.get_project(pid)
        mid = str(body.get("media_id") or "")
        if not any(m["id"] == mid for m in (proj.get("media") or [])):
            raise HTTPException(404, "Media asset not found in project.")
        proj["active_media_id"] = mid
        projects.save_project(pid, proj)
        return {"project": proj}
    except FileNotFoundError:
        raise HTTPException(404, "Project not found.")


@router.get("/projects/{pid}/media/{filename}")
def serve_project_media(pid: str, filename: str):
    try:
        pdir = projects.project_dir(pid)
    except ValueError:
        raise HTTPException(400, "Invalid project id.")
    path = _safe_file_in(pdir / "media", filename)
    return FileResponse(path)


@router.get("/projects/{pid}/thumbnails/{filename}")
def serve_project_thumb(pid: str, filename: str):
    try:
        pdir = projects.project_dir(pid)
    except ValueError:
        raise HTTPException(400, "Invalid project id.")
    path = _safe_file_in(pdir / "thumbnails", filename)
    return FileResponse(path, media_type="image/jpeg")


@router.get("/projects/{pid}/exports/{filename}")
def serve_project_export(pid: str, filename: str):
    try:
        pdir = projects.project_dir(pid)
    except ValueError:
        raise HTTPException(400, "Invalid project id.")
    path = _safe_file_in(pdir / "exports", filename)
    return FileResponse(path, media_type="video/mp4", filename=filename)


# ------------------------------------------------------------------ Automation (AUTO / MANUAL)
@router.get("/projects/{pid}/automation")
def get_automation_status(pid: str):
    try:
        projects.validate_project_id(pid)
        return automation.get_status(pid)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/projects/{pid}/automation/run")
def run_automation(pid: str, body: dict = Body(default={})):
    try:
        trigger = str(body.get("trigger") or "manual")
        if trigger not in ("auto", "manual"):
            trigger = "manual"
        tasks = body.get("tasks")
        if tasks is not None and not isinstance(tasks, list):
            raise ValueError("tasks must be a list of task names.")
        state = automation.start_pipeline(pid, trigger=trigger, only_tasks=tasks, sync=bool(body.get("sync", False)))
        return {"automation": state, "project": projects.get_project(pid)}
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/projects/{pid}/automation/{action}")
def control_automation(pid: str, action: str):
    try:
        projects.validate_project_id(pid)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if action == "pause":
        return {"automation": automation.pause(pid)}
    if action == "resume":
        return {"automation": automation.resume(pid)}
    if action == "stop":
        return {"automation": automation.stop(pid)}
    raise HTTPException(404, "Unknown automation action.")


# ------------------------------------------------------------------ Face Detection & Subject Tracking
@router.put("/projects/{pid}/faces/config")
def update_face_config(pid: str, body: dict = Body(...)):
    try:
        proj = projects.get_project(pid)
        cfg = dict(proj.get("face_tracking", {}).get("config") or projects.get_settings()["face_detection"])
        for k in ("enabled", "mode", "sensitivity", "min_face_size", "multi_face", "primary_subject_id", "target_aspect"):
            if k in body:
                cfg[k] = body[k]
        # Recompute reframing suggestions if primary subject changed and subjects exist
        subjects = proj.get("face_tracking", {}).get("subjects") or []
        if "primary_subject_id" in body and subjects:
            chosen = next((s for s in subjects if s["subject_id"] == body["primary_subject_id"]), None)
            if chosen:
                media_meta, _ = projects.get_active_media(proj)
                src_w, src_h = int(media_meta.get("width") or 1920), int(media_meta.get("height") or 1080)
                proj["face_tracking"]["primary_subject_id"] = chosen["subject_id"]
                proj["face_tracking"]["reframing_suggestions"] = {
                    asp: face_tracker.compute_smart_reframe(src_w, src_h, asp, chosen["avg_box"])
                    for asp in ("9:16", "1:1", "16:9")
                }
        proj["face_tracking"]["config"] = cfg
        projects.save_project(pid, proj)
        projects.update_settings({"face_detection": cfg})
        return {"project": proj}
    except FileNotFoundError:
        raise HTTPException(404, "Project not found.")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/projects/{pid}/faces/reset")
def reset_face_tracking(pid: str):
    try:
        proj = projects.get_project(pid)
        cfg = proj.get("face_tracking", {}).get("config") or projects.get_settings()["face_detection"]
        cfg["primary_subject_id"] = None
        proj["face_tracking"] = {
            "config": cfg,
            "status": "idle",
            "detected_faces_total": 0,
            "subjects": [],
            "primary_subject_id": None,
            "frame_samples": [],
            "reframing_suggestions": {},
            "model": "OpenCV Local Multi-Pass Face + Eye Detector",
            "analyzed_at": None,
        }
        for sh in proj.get("shots") or []:
            sh["detected_subjects"] = []
            sh["face_info"] = {
                "analyzed": False,
                "face_detected": False,
                "face_count": 0,
                "primary_subject_id": None,
                "visibility_ratio": 0.0,
                "avg_confidence": 0.0,
                "closeup": False,
                "obstruction_suspected": False,
                "avg_box": None,
                "entries": 0,
                "exits": 0,
            }
        projects.save_project(pid, proj)
        projects.append_activity(pid, "faces", "Reset face detection and subject tracking state.")
        return {"project": projects.get_project(pid)}
    except FileNotFoundError:
        raise HTTPException(404, "Project not found.")


# ------------------------------------------------------------------ Timeline & Shot Editing
@router.put("/projects/{pid}/shots/{shot_id}")
def edit_shot(pid: str, shot_id: str, body: dict = Body(...)):
    try:
        proj = editor_engine.update_shot_edit(pid, shot_id, body)
        return {"project": proj}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/projects/{pid}/shots/{shot_id}/split")
def split_shot(pid: str, shot_id: str, body: dict = Body(...)):
    try:
        proj = editor_engine.split_shot(pid, shot_id, float(body.get("split_at")))
        return {"project": proj}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))


@router.post("/projects/{pid}/shots/merge")
def merge_shots(pid: str, body: dict = Body(...)):
    try:
        proj = editor_engine.merge_shots(pid, str(body.get("shot_a") or ""), str(body.get("shot_b") or ""))
        return {"project": proj}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/projects/{pid}/shots/reorder")
def reorder_shots(pid: str, body: dict = Body(...)):
    try:
        ids = body.get("ordered_ids") or []
        if not isinstance(ids, list):
            raise ValueError("ordered_ids must be a list.")
        return {"project": editor_engine.reorder_shots(pid, [str(x) for x in ids])}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/projects/{pid}/shots/{shot_id}/apply-suggestion")
def apply_suggestion(pid: str, shot_id: str, body: dict = Body(...)):
    try:
        proj = editor_engine.apply_suggestion(pid, shot_id, str(body.get("action") or ""))
        return {"project": proj}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/projects/{pid}/timeline")
def update_timeline(pid: str, body: dict = Body(...)):
    try:
        return {"project": editor_engine.update_timeline(pid, body)}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/projects/{pid}/captions/generate")
def generate_project_captions(pid: str, body: dict = Body(default={})):
    """Generate voice-synced captions in the chosen language (AI Audio API when configured, else offline speech model)."""
    try:
        proj = projects.get_project(pid)
        media_meta, video_path = projects.get_active_media(proj)
        settings = projects.get_settings()
        tl_cc = (proj.get("timeline") or {}).get("caption_config") or {}
        language = str(body.get("language") or tl_cc.get("language") or settings.get("caption_defaults", {}).get("language") or "auto")
        only_shots = bool(body.get("only_shots", True))
        shots = proj.get("shots") or []
        if only_shots and shots:
            ranges = [(float(sh.get("trim_start", sh["start"])), float(sh.get("trim_end", sh["end"]))) for sh in shots]
        else:
            ranges = [(0.0, float(media_meta.get("duration") or 0.0))]

        res = ai_transcribe.transcribe_video_ranges(
            video_path=video_path,
            ranges=ranges,
            language=language,
            allow_ai=bool(settings.get("privacy", {}).get("allow_cloud_ai", True)),
        )
        proj = projects.get_project(pid)
        proj["timeline"].setdefault("caption_config", {})["language"] = language
        proj["timeline"]["caption_config"]["enabled"] = True
        if res["words"]:
            proj["analysis"]["transcript_words"] = res["words"]
        proj["analysis"]["transcript_source"] = res["source"]
        proj["analysis"]["caption_language"] = language
        proj["analysis"]["caption_note"] = res["note"]
        if res["cues"]:
            proj["timeline"]["captions"] = res["cues"]
            for sh in proj.get("shots") or []:
                s0, s1 = float(sh.get("trim_start", sh["start"])), float(sh.get("trim_end", sh["end"]))
                sh_cues = [c["text"] for c in res["cues"] if float(c["end"]) > s0 and float(c["start"]) < s1]
                if sh_cues:
                    sh["transcript"] = " ".join(sh_cues).strip()
        elif res["source"].startswith("ai_audio_silent"):
            proj["timeline"]["captions"] = []
        projects.save_project(pid, proj)
        projects.append_activity(pid, "captions", res["note"] or f"Generated {len(res['cues'])} captions.")
        return {"project": proj, "cues_count": len(res["cues"]), "source": res["source"], "note": res["note"]}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


# ------------------------------------------------------------------ Virality Sorting & Filtering
@router.get("/projects/{pid}/virality/shots")
def query_virality_shots(
    pid: str,
    sort_by: str = Query("score_desc"),
    min_score: int = Query(0, ge=0, le=100),
    max_score: int = Query(100, ge=0, le=100),
):
    try:
        proj = projects.get_project(pid)
    except FileNotFoundError:
        raise HTTPException(404, "Project not found.")
    shots = [
        s for s in (proj.get("shots") or [])
        if min_score <= (s.get("virality") or {}).get("score", 0) <= max_score
    ]
    key_map = {
        "score_desc": (lambda s: (s.get("virality") or {}).get("score", 0), True),
        "score_asc": (lambda s: (s.get("virality") or {}).get("score", 0), False),
        "duration_desc": (lambda s: float(s.get("duration") or 0), True),
        "duration_asc": (lambda s: float(s.get("duration") or 0), False),
        "timestamp": (lambda s: float(s.get("start") or 0), False),
        "face_visibility": (lambda s: float((s.get("face_info") or {}).get("visibility_ratio", 0)), True),
        "hook_strength": (lambda s: ((s.get("virality") or {}).get("dimensions") or {}).get("opening_hook", 0), True),
    }
    fn, rev = key_map.get(sort_by, key_map["score_desc"])
    shots.sort(key=fn, reverse=rev)
    return {"shots": shots, "virality": proj.get("virality") or {}}


# ------------------------------------------------------------------ AI Assistant
@router.post("/projects/{pid}/assistant")
def ask_ai_assistant(pid: str, body: dict = Body(...)):
    try:
        prompt = str(body.get("prompt") or "").strip()
        action = str(body.get("action") or "chat").strip()
        return assistant.ask_assistant(pid, prompt, action=action)
    except FileNotFoundError:
        raise HTTPException(404, "Project not found.")
    except ValueError as e:
        raise HTTPException(400, str(e))


# ------------------------------------------------------------------ Video Link Ingestion (YouTube / Twitch / Kick)
@router.post("/ingest/preview")
def preview_ingest_url(body: dict = Body(...)):
    try:
        return {"preview": url_ingest.preview_link(str(body.get("url") or ""))}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.post("/ingest/url")
def start_ingest_url(body: dict = Body(...)):
    try:
        job = url_ingest.start_url_ingest(
            url=str(body.get("url") or ""),
            project_id=body.get("project_id") or None,
            project_name=str(body.get("project_name") or ""),
            height=int(body.get("height") or 1080),
            process_immediately=bool(body.get("process_immediately", True)),
            reel_count=int(body["reel_count"]) if body.get("reel_count") is not None else None,
            duration_mode=str(body["duration_mode"]) if body.get("duration_mode") else None,
            target_duration=int(body["target_duration"]) if body.get("target_duration") is not None else None,
            auto_captions=bool(body["auto_captions"]) if body.get("auto_captions") is not None else None,
            aspect=str(body["aspect"]) if body.get("aspect") else None,
            caption_language=str(body["caption_language"]) if body.get("caption_language") else None,
        )
        return {"ingest": job}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(400, str(e))


@router.get("/ingest/{ingest_id}")
def get_ingest(ingest_id: str):
    try:
        return {"ingest": url_ingest.get_ingest_status(ingest_id)}
    except FileNotFoundError:
        raise HTTPException(404, "Download task not found.")


# ------------------------------------------------------------------ Export Center
@router.post("/projects/{pid}/export/estimate")
def estimate_project_export(pid: str, body: dict = Body(default={})):
    try:
        proj = projects.get_project(pid)
        return editor_engine.estimate_export(proj, body)
    except FileNotFoundError:
        raise HTTPException(404, "Project not found.")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/projects/{pid}/export")
def start_project_export(pid: str, body: dict = Body(default={})):
    try:
        job = editor_engine.start_export(pid, body, sync=bool(body.get("sync", False)))
        return {"export": job}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/projects/{pid}/export/reels")
def start_project_reels_pack(pid: str, body: dict = Body(default={})):
    try:
        job = editor_engine.start_reels_pack(pid, body, sync=bool(body.get("sync", False)))
        return {"export": job}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/exports/{export_id}")
def get_export(export_id: str):
    try:
        return {"export": editor_engine.get_export_status(export_id)}
    except FileNotFoundError:
        raise HTTPException(404, "Export job not found.")


@router.post("/exports/{export_id}/cancel")
def cancel_export(export_id: str):
    return {"export": editor_engine.cancel_export(export_id)}
