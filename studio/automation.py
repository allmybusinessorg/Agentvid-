"""AgentVid AUTO / MANUAL Automation Engine with pause, resume, cancel, progress tracking, and activity logs."""
from __future__ import annotations

import copy
import threading
import time
import traceback
import uuid
from typing import Any

from . import ai_transcribe, face_tracker, projects, reel_selector, video_analysis, virality

_lock = threading.RLock()
_runs: dict[str, dict[str, Any]] = {}


class _RunControl:
    def __init__(self, pid: str):
        self.pid = pid
        self.cancel_event = threading.Event()
        self.pause_event = threading.Event()  # cleared = running, set = paused
        self.thread: threading.Thread | None = None

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def wait_if_paused(self) -> None:
        while self.pause_event.is_set() and not self.cancel_event.is_set():
            time.sleep(0.15)
        if self.cancel_event.is_set():
            raise InterruptedError("Operation cancelled by user.")


_controls: dict[str, _RunControl] = {}


def get_status(pid: str) -> dict[str, Any]:
    with _lock:
        settings = projects.get_settings()
        run = _runs.get(pid)
        if not run:
            return {
                "project_id": pid,
                "auto_mode": settings["auto_mode"],
                "switches": settings["automation"],
                "state": "idle",
                "operation": "",
                "progress": 0.0,
                "mode_used": "auto" if settings["auto_mode"] else "manual",
                "started_at": None,
                "finished_at": None,
                "error": "",
                "completed_steps": [],
            }
        out = copy.deepcopy(run)
        out["auto_mode"] = settings["auto_mode"]
        out["switches"] = settings["automation"]
        return out


def _set_run(pid: str, **fields):
    with _lock:
        if pid not in _runs:
            _runs[pid] = {
                "project_id": pid,
                "state": "idle",
                "operation": "",
                "progress": 0.0,
                "mode_used": "auto",
                "started_at": time.time(),
                "finished_at": None,
                "error": "",
                "completed_steps": [],
            }
        _runs[pid].update(fields)


def pause(pid: str) -> dict[str, Any]:
    with _lock:
        ctrl = _controls.get(pid)
        if ctrl and _runs.get(pid, {}).get("state") == "running":
            ctrl.pause_event.set()
            _set_run(pid, state="paused", operation="Paused by user")
            try:
                projects.append_activity(pid, "automation", "Automation pipeline paused by user.", "warn")
            except Exception:
                pass
    return get_status(pid)


def resume(pid: str) -> dict[str, Any]:
    with _lock:
        ctrl = _controls.get(pid)
        if ctrl and _runs.get(pid, {}).get("state") == "paused":
            ctrl.pause_event.clear()
            _set_run(pid, state="running", operation="Resuming pipeline...")
            try:
                projects.append_activity(pid, "automation", "Automation pipeline resumed.", "info")
            except Exception:
                pass
    return get_status(pid)


def stop(pid: str) -> dict[str, Any]:
    with _lock:
        ctrl = _controls.get(pid)
        if ctrl:
            ctrl.cancel_event.set()
            ctrl.pause_event.clear()
        if pid in _runs and _runs[pid].get("state") in ("running", "paused", "queued"):
            _set_run(pid, state="stopped", operation="Stopped by user", finished_at=time.time())
            try:
                projects.append_activity(pid, "automation", "Automation pipeline stopped by user.", "warn")
            except Exception:
                pass
    return get_status(pid)


def start_pipeline(
    pid: str,
    trigger: str = "auto",
    only_tasks: list[str] | None = None,
    sync: bool = False,
) -> dict[str, Any]:
    """Start AUTO or MANUAL tasks for a project.

    - When `trigger == "auto"`: checks `settings["auto_mode"]`; if False (MANUAL mode), does NOT auto-execute!
      When True, executes ONLY the enabled individual switches.
    - When `trigger == "manual"`: executes the explicitly requested `only_tasks` (or full manual run).
    """
    settings = projects.get_settings()
    if trigger == "auto" and not settings["auto_mode"]:
        projects.append_activity(
            pid,
            "automation",
            "MANUAL mode active: media imported without automatic processing. Trigger tasks manually when ready.",
            "info",
        )
        return get_status(pid)

    with _lock:
        existing = _runs.get(pid)
        if existing and existing.get("state") in ("running", "paused"):
            raise RuntimeError("An automation task is already running for this project. Pause or stop it first.")
        ctrl = _RunControl(pid)
        _controls[pid] = ctrl
        _set_run(
            pid,
            state="running",
            operation="Preparing analysis pipeline...",
            progress=0.02,
            mode_used=trigger,
            started_at=time.time(),
            finished_at=None,
            error="",
            completed_steps=[],
        )

    def _worker():
        try:
            _execute_pipeline(pid, ctrl, settings, trigger, only_tasks)
        except InterruptedError:
            _set_run(pid, state="stopped", operation="Processing stopped", finished_at=time.time())
            try:
                projects.append_activity(pid, "automation", "Processing cancelled.", "warn")
            except Exception:
                pass
        except Exception as e:
            err = f"{e}"
            traceback.print_exc()
            _set_run(pid, state="error", operation="Failed", error=err, finished_at=time.time())
            try:
                projects.append_activity(pid, "automation", f"Pipeline error: {err}", "error")
            except Exception:
                pass

    if sync:
        _worker()
        return get_status(pid)

    t = threading.Thread(target=_worker, name=f"agentvid-auto-{pid}", daemon=True)
    ctrl.thread = t
    t.start()
    return get_status(pid)


def _execute_pipeline(
    pid: str,
    ctrl: _RunControl,
    settings: dict[str, Any],
    trigger: str,
    only_tasks: list[str] | None,
) -> None:
    proj = projects.get_project(pid)
    media_meta, video_path = projects.get_active_media(proj)
    sw = copy.deepcopy(settings["automation"])
    perf = settings.get("performance") or {}
    sample_fps = float(perf.get("sample_fps", 1.5))
    max_width = int(perf.get("max_analysis_width", 480))

    # Determine which stages to execute
    if only_tasks is not None:
        task_set = set(only_tasks)
        run_scene = "scene_detection" in task_set or "shot_segmentation" in task_set or "analyze" in task_set or "reel_extraction" in task_set
        run_silence = "silence_detection" in task_set or "analyze" in task_set
        run_captions = "caption_generation" in task_set
        run_faces = "face_detection" in task_set or "subject_tracking" in task_set
        run_virality = "virality_scoring" in task_set or "highlight_detection" in task_set
        run_reframing = "reframing" in task_set or run_faces
        run_editing_plan = "editing_recommendations" in task_set or run_virality
    else:
        run_scene = bool(sw.get("scene_detection") or sw.get("shot_segmentation"))
        run_silence = bool(sw.get("silence_detection"))
        run_captions = bool(sw.get("caption_generation"))
        run_faces = bool(sw.get("face_detection"))
        run_virality = bool(sw.get("virality_scoring") or sw.get("highlight_detection"))
        run_reframing = bool(sw.get("reframing"))
        run_editing_plan = bool(sw.get("editing_recommendations") or sw.get("zoom_suggestions") or sw.get("transition_suggestions"))

    completed: list[str] = []
    projects.append_activity(
        pid,
        "automation",
        f"Started {'AUTO' if trigger == 'auto' else 'MANUAL'} pipeline on '{media_meta['name']}'.",
        "info",
    )

    # 1. Audio / Silence analysis (local English ASR only when no AI audio API is ready and language is English/Auto)
    cap_cfg = (proj.get("timeline") or {}).get("caption_config") or {}
    cap_lang = str(cap_cfg.get("language") or settings.get("caption_defaults", {}).get("language") or "auto")
    allow_cloud = bool(settings.get("privacy", {}).get("allow_cloud_ai", True))
    ai_audio_ready = allow_cloud and ai_transcribe._can_ai_transcribe_audio()
    want_local_asr_stage1 = (
        run_captions
        and not ai_audio_ready
        and cap_lang in ("auto", "en", "")
        and not (proj.get("analysis", {}).get("transcript_words"))
    )

    audio_info = {
        "rms_timeline": [],
        "silence_segments": proj.get("analysis", {}).get("silence_segments") or [],
        "speech_segments": proj.get("analysis", {}).get("speech_segments") or [],
        "audio_clarity": 0,
        "transcript_words": proj.get("analysis", {}).get("transcript_words") or [],
        "transcript_source": proj.get("analysis", {}).get("transcript_source") or "none",
    }
    if run_scene or run_silence or (run_captions and not (proj.get("shots"))):
        ctrl.wait_if_paused()
        _set_run(pid, operation="Analyzing audio, speech & silence...", progress=0.08)
        audio_info = video_analysis.extract_audio_features(
            video_path,
            duration=float(media_meta.get("duration") or 0.0),
            has_audio=bool(media_meta.get("has_audio")),
            silence_enabled=run_silence or bool(sw.get("silence_detection", True)),
            captions_enabled=want_local_asr_stage1,
            cancel_cb=ctrl.is_cancelled,
        )
        proj = projects.get_project(pid)
        proj["analysis"]["silence_segments"] = audio_info["silence_segments"]
        proj["analysis"]["speech_segments"] = audio_info["speech_segments"]
        # Preserve existing verified captions/transcript (e.g. from YouTube ingest) if local ASR returned empty
        if audio_info["transcript_words"]:
            proj["analysis"]["transcript_words"] = audio_info["transcript_words"]
            proj["analysis"]["transcript_source"] = audio_info["transcript_source"]
        elif proj["analysis"].get("transcript_words"):
            audio_info["transcript_words"] = proj["analysis"]["transcript_words"]
            audio_info["transcript_source"] = proj["analysis"].get("transcript_source") or "existing_captions"
        else:
            proj["analysis"]["transcript_source"] = audio_info["transcript_source"]
        if audio_info["transcript_words"]:
            proj["timeline"]["captions"] = ai_transcribe.words_to_cues(audio_info["transcript_words"])
        projects.save_project(pid, proj)
        if run_silence:
            completed.append("silence_detection")
        projects.append_activity(
            pid,
            "audio",
            f"Audio analyzed: {len(audio_info['silence_segments'])} silence segments, "
            f"{len(audio_info['speech_segments'])} speech segments, transcript={audio_info['transcript_source']}.",
            "info",
        )

    # 2. Peak-Moment Reel Extraction (AI transcript peak finder when API key configured, else local peak detector)
    if run_scene or not (proj.get("shots")):
        ctrl.wait_if_paused()
        reel_cfg = copy.deepcopy(settings.get("reels") or projects.DEFAULT_SETTINGS["reels"])
        req_count = int(reel_cfg.get("count") or 5)
        dur_mode = reel_cfg.get("duration_mode", "auto_ai")
        _set_run(
            pid,
            operation=f"Finding top {req_count} peak Reel moments across full video...",
            progress=0.22,
        )
        seg = reel_selector.build_peak_reels(
            pid=pid,
            video_path=video_path,
            media_meta=media_meta,
            audio_info=audio_info,
            reel_settings=reel_cfg,
            allow_ai=bool(settings.get("privacy", {}).get("allow_cloud_ai", True)),
            progress_cb=lambda p, msg: _set_run(pid, progress=round(0.22 + p * 0.28, 3), operation=msg),
            cancel_cb=ctrl.is_cancelled,
        )
        proj = projects.get_project(pid)
        proj["shots"] = seg["shots"]
        proj["analysis"]["status"] = "done"
        proj["analysis"]["scene_count"] = seg["scene_count"]
        proj["analysis"]["analyzed_at"] = seg["analyzed_at"]
        proj["analysis"]["reel_selection_mode"] = seg["selection_mode"]
        proj["analysis"]["reel_selection_note"] = seg["selection_note"]
        proj["analysis"]["ai_model"] = seg.get("ai_model")
        proj["analysis"]["requested_reels"] = req_count
        proj["analysis"]["duration_mode"] = dur_mode
        if reel_cfg.get("aspect") in ("9:16", "1:1", "16:9"):
            proj["timeline"]["aspect"] = reel_cfg["aspect"]
        projects.save_project(pid, proj)
        completed.extend(["scene_detection", "shot_segmentation", "reel_extraction"])
        mode_tag = f"AI ({seg['ai_model']})" if seg["selection_mode"] == "ai_peak_detection" else "Local Peak Detector"
        projects.append_activity(
            pid,
            "scenes",
            f"[{mode_tag}] Extracted {len(seg['shots'])} peak Reel(s) across full video ({dur_mode}). {seg['selection_note']}",
            "info",
        )

    # 2B. Voice-Synchronized Multi-Language Auto-Captions for All Extracted Reels
    proj = projects.get_project(pid)
    cur_shots = proj.get("shots") or []
    cur_cues = (proj.get("timeline") or {}).get("captions") or []
    explicit_cap_task = bool(only_tasks and "caption_generation" in only_tasks)
    cap_enabled_now = bool((proj.get("timeline") or {}).get("caption_config", {}).get("enabled", True))
    cues_in_shots = 0
    for sh in cur_shots:
        s0, s1 = float(sh.get("trim_start", sh["start"])), float(sh.get("trim_end", sh["end"]))
        cues_in_shots += sum(1 for c in cur_cues if float(c.get("end", 0)) > s0 and float(c.get("start", 0)) < s1)
    need_shot_captions = explicit_cap_task or (
        (run_captions or cap_enabled_now)
        and bool(media_meta.get("has_audio"))
        and (cues_in_shots < max(1, len(cur_shots)) or (ai_audio_ready and cap_lang not in ("auto", "en", "")))
    )
    if need_shot_captions and (explicit_cap_task or ai_audio_ready or not cur_cues):
        ctrl.wait_if_paused()
        ranges = [
            (float(sh.get("trim_start", sh["start"])), float(sh.get("trim_end", sh["end"])))
            for sh in cur_shots
        ] if cur_shots else [(0.0, float(media_meta.get("duration") or 0.0))]
        _set_run(pid, operation=f"Generating voice-synced captions ({ai_transcribe.language_label(cap_lang)})...", progress=0.46)
        cap_res = ai_transcribe.transcribe_video_ranges(
            video_path=video_path,
            ranges=ranges,
            language=cap_lang,
            allow_ai=allow_cloud,
            progress_cb=lambda p, msg: _set_run(pid, progress=round(0.46 + p * 0.06, 3), operation=msg),
            cancel_cb=ctrl.is_cancelled,
        )
        proj = projects.get_project(pid)
        if cap_res["cues"] or explicit_cap_task:
            if cap_res["words"]:
                proj["analysis"]["transcript_words"] = cap_res["words"]
            proj["analysis"]["transcript_source"] = cap_res["source"]
            proj["analysis"]["caption_language"] = cap_lang
            proj["analysis"]["caption_note"] = cap_res["note"]
            if cap_res["cues"]:
                proj["timeline"]["captions"] = cap_res["cues"]
                for sh in proj.get("shots") or []:
                    s0, s1 = float(sh.get("trim_start", sh["start"])), float(sh.get("trim_end", sh["end"]))
                    sh_cues = [c["text"] for c in cap_res["cues"] if float(c["end"]) > s0 and float(c["start"]) < s1]
                    if sh_cues:
                        sh["transcript"] = " ".join(sh_cues).strip()
            elif explicit_cap_task and cap_res["source"].startswith("ai_audio_silent"):
                proj["timeline"]["captions"] = []
            projects.save_project(pid, proj)
        completed.append("caption_generation")
        projects.append_activity(pid, "captions", cap_res["note"] or f"Caption pass complete ({cap_res['source']}).", "info")

    # 3. AI Face Detection & Subject Tracking
    if run_faces:
        ctrl.wait_if_paused()
        proj = projects.get_project(pid)
        fcfg = copy.deepcopy(proj.get("face_tracking", {}).get("config") or settings["face_detection"])
        if only_tasks and "face_detection" in only_tasks:
            fcfg["enabled"] = True
        _set_run(pid, operation="Running local AI face detection & tracking...", progress=0.52)
        fres = face_tracker.analyze_faces(
            video_path=video_path,
            media_meta=media_meta,
            shots=proj.get("shots") or [],
            face_config=fcfg,
            subject_tracking_enabled=bool(sw.get("subject_tracking", True)) if only_tasks is None else True,
            sample_fps=sample_fps,
            max_width=max_width,
            progress_cb=lambda p, msg: _set_run(pid, progress=round(0.52 + p * 0.28, 3), operation=msg),
            cancel_cb=ctrl.is_cancelled,
            pause_cb=ctrl.wait_if_paused,
        )
        proj = projects.get_project(pid)
        proj["face_tracking"] = {
            "config": fcfg,
            "status": fres["status"],
            "detected_faces_total": fres["detected_faces_total"],
            "subjects": fres["subjects"],
            "primary_subject_id": fres.get("primary_subject_id"),
            "frame_samples": fres["frame_samples"],
            "reframing_suggestions": fres["reframing_suggestions"],
            "model": fres["model"],
            "analyzed_at": fres["analyzed_at"],
        }
        shot_updates = fres.get("shot_updates") or {}
        target_aspect = fcfg.get("target_aspect", "9:16")
        for sh in proj.get("shots") or []:
            upd = shot_updates.get(sh["id"])
            if upd:
                sh["face_info"] = upd["face_info"]
                sh["detected_subjects"] = upd["detected_subjects"]
                if run_reframing:
                    sh.setdefault("suggestions", {})["reframing"] = upd["reframing"]
                    reframe_box = upd["reframing"].get(target_aspect)
                    if reframe_box and sh.get("edit", {}).get("crop_mode") in ("auto", "face"):
                        sh["edit"]["pan_x"] = reframe_box["pan_x"]
                        sh["edit"]["pan_y"] = reframe_box["pan_y"]
        projects.save_project(pid, proj)
        completed.append("face_detection")
        if sw.get("subject_tracking", True):
            completed.append("subject_tracking")
        if run_reframing:
            completed.append("reframing")
        projects.append_activity(
            pid,
            "faces",
            f"Face detection finished: {fres['detected_faces_total']} detections across {len(fres['subjects'])} tracked subject(s).",
            "info",
        )

    # 4. Virality Scoring & Editing Recommendations
    if run_virality or run_editing_plan:
        ctrl.wait_if_paused()
        _set_run(pid, operation="Computing 15-dimension virality scores & editing plan...", progress=0.84)
        proj = projects.get_project(pid)
        vres = virality.score_project_shots(
            shots=proj.get("shots") or [],
            video_duration=float(media_meta.get("duration") or 0.0),
            allow_ai_enhance=bool(settings.get("privacy", {}).get("allow_cloud_ai")),
            switches=sw,
        )
        proj["shots"] = vres["shots"]
        proj["virality"] = vres["virality"]

        # Build structured editing plan
        plan = []
        brolls = []
        for sh in proj["shots"]:
            sc = sh["virality"]["score"]
            if sc >= 75:
                plan.append({
                    "id": f"plan_{uuid.uuid4().hex[:6]}",
                    "shot_id": sh["id"],
                    "shot_number": sh["number"],
                    "action": "highlight_keep",
                    "priority": "high",
                    "summary": f"Keep Shot {sh['number']:02d} (Score {sc}/100) — {sh['virality']['tier']}.",
                    "approved": trigger == "auto",
                })
            elif sh["metrics"].get("silence_ratio", 0) >= 0.45:
                plan.append({
                    "id": f"plan_{uuid.uuid4().hex[:6]}",
                    "shot_id": sh["id"],
                    "shot_number": sh["number"],
                    "action": "trim_silence",
                    "priority": "medium",
                    "summary": f"Trim dead air in Shot {sh['number']:02d} ({int(sh['metrics']['silence_ratio'] * 100)}% silent).",
                    "approved": False,
                })
            if sh.get("suggestions", {}).get("zoom"):
                plan.append({
                    "id": f"plan_{uuid.uuid4().hex[:6]}",
                    "shot_id": sh["id"],
                    "shot_number": sh["number"],
                    "action": "apply_zoom",
                    "priority": "low",
                    "summary": f"Shot {sh['number']:02d}: {sh['suggestions']['zoom']['reason']}",
                    "approved": False,
                })
            if sh.get("suggestions", {}).get("broll"):
                brolls.append({
                    "shot_id": sh["id"],
                    "shot_number": sh["number"],
                    **sh["suggestions"]["broll"],
                })
        proj["analysis"]["editing_plan"] = plan
        proj["analysis"]["broll_suggestions"] = brolls
        projects.save_project(pid, proj)
        completed.append("virality_scoring")
        if sw.get("editing_recommendations", True):
            completed.append("editing_recommendations")
        projects.append_activity(
            pid,
            "virality",
            f"Virality analysis complete: overall video score {vres['virality']['overall_score']}/100 "
            f"(avg shot {vres['virality']['average_shot_score']}/100).",
            "info",
        )

    _set_run(
        pid,
        state="done",
        operation="Completed",
        progress=1.0,
        finished_at=time.time(),
        completed_steps=list(dict.fromkeys(completed)),
    )
    projects.append_activity(
        pid,
        "automation",
        f"Completed pipeline ({len(completed)} operations).",
        "info",
    )
