"""AgentVid Video Link Ingestion: preview & download YouTube/Twitch/Kick videos directly into a project."""
from __future__ import annotations

import copy
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from . import ai_transcribe, automation, media, projects

_lock = threading.RLock()
_jobs: dict[str, dict[str, Any]] = {}


def preview_link(url: str) -> dict[str, Any]:
    clean = str(url or "").strip()
    if not clean:
        raise ValueError("Please paste a video URL first.")
    if not media.site_allowed(clean):
        raise ValueError("Supported link sources: YouTube (youtube.com, youtu.be), Twitch (twitch.tv), and Kick (kick.com).")
    return media.preview(clean)


def get_ingest_status(ingest_id: str) -> dict[str, Any]:
    with _lock:
        job = _jobs.get(ingest_id)
        if not job:
            raise FileNotFoundError("Download task not found.")
        return copy.deepcopy(job)


def start_url_ingest(
    url: str,
    project_id: str | None = None,
    project_name: str = "",
    height: int = 1080,
    process_immediately: bool = True,
    reel_count: int | None = None,
    duration_mode: str | None = None,
    target_duration: int | None = None,
    auto_captions: bool | None = None,
    aspect: str | None = None,
    caption_language: str | None = None,
) -> dict[str, Any]:
    clean = str(url or "").strip()
    if not clean:
        raise ValueError("Please paste a video URL first.")
    if not media.site_allowed(clean):
        raise ValueError("Supported link sources: YouTube, Twitch, or Kick.")
    height = max(360, min(2160, int(height or 1080)))

    # Persist per-ingest Reel & Caption preferences so the automation pipeline honors them immediately
    settings_patch: dict[str, Any] = {}
    reel_patch: dict[str, Any] = {}
    if reel_count is not None:
        reel_patch["count"] = max(1, min(20, int(reel_count)))
    if duration_mode in ("auto_ai", "fixed"):
        reel_patch["duration_mode"] = duration_mode
    if target_duration is not None:
        reel_patch["target_duration"] = max(10, min(90, int(target_duration)))
    if auto_captions is not None:
        reel_patch["auto_captions"] = bool(auto_captions)
    if aspect in ("9:16", "1:1", "16:9"):
        reel_patch["aspect"] = aspect
    if reel_patch:
        settings_patch["reels"] = reel_patch
    if caption_language:
        settings_patch["caption_defaults"] = {"language": str(caption_language).strip()}
    if settings_patch:
        projects.update_settings(settings_patch)

    # Validate existing project if specified
    if project_id:
        projects.get_project(project_id)

    ingest_id = f"ing_{uuid.uuid4().hex[:10]}"
    state = {
        "id": ingest_id,
        "url": clean,
        "project_id": project_id or "",
        "status": "starting",
        "stage": "Fetching video metadata...",
        "progress": 0.04,
        "title": "",
        "uploader": "",
        "duration": 0.0,
        "error": "",
        "started_at": time.time(),
        "finished_at": None,
    }
    with _lock:
        _jobs[ingest_id] = state

    def _set(**kw):
        with _lock:
            _jobs[ingest_id].update(kw)

    def _worker():
        tmp_dir: Path | None = None
        try:
            meta = media.preview(clean)
            if meta.get("is_live"):
                raise ValueError("Live streams are currently broadcasting. Paste a completed video or VOD link.")
            title = meta.get("title") or "Imported Link Video"
            _set(
                status="downloading",
                stage=f"Downloading '{title[:60]}'...",
                progress=0.10,
                title=title,
                uploader=meta.get("uploader") or "",
                duration=float(meta.get("duration") or 0.0),
            )

            # Create project if not provided
            pid = project_id
            if not pid:
                pname = (project_name or title).strip()[:100] or "Link Project"
                created = projects.create_project(pname, f"Imported from {clean}")
                pid = created["id"]
                _set(project_id=pid)

            pdir = projects.project_dir(pid)
            tmp_dir = pdir / "media" / f"_dl_{ingest_id}"
            tmp_dir.mkdir(parents=True, exist_ok=True)

            def _hook(d: dict[str, Any]):
                st = d.get("status")
                if st == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    done = d.get("downloaded_bytes") or 0
                    if total > 0:
                        pct = min(0.75, 0.12 + (done / total) * 0.63)
                        spd = d.get("_speed_str") or ""
                        eta = d.get("_eta_str") or ""
                        extra = f" · {spd}" if spd else ""
                        if eta:
                            extra += f" · ETA {eta}"
                        _set(progress=round(pct, 3), stage=f"Downloading video ({int(done / total * 100)}%){extra}")
                elif st == "finished":
                    _set(progress=0.78, stage="Merging video & audio streams with FFmpeg...")

            with media._youtube_guard(clean), media._ydl({
                "format": media._video_format(height),
                "merge_output_format": "mp4",
                "outtmpl": str(tmp_dir / "source.%(ext)s"),
                "progress_hooks": [_hook],
            }) as ydl:
                ydl.download([clean])

            downloaded = media._biggest(tmp_dir, "source")
            safe_stem = projects.sanitize_filename(title, fallback="video")[:70]
            ext = downloaded.suffix.lower() if downloaded.suffix.lower() in projects.ALLOWED_VIDEO_EXTS else ".mp4"
            final_name = f"{uuid.uuid4().hex[:8]}_{safe_stem}{ext}"
            final_path = pdir / "media" / final_name
            shutil.move(str(downloaded), str(final_path))
            shutil.rmtree(tmp_dir, ignore_errors=True)
            tmp_dir = None

            _set(status="importing", progress=0.86, stage="Probing streams & generating thumbnail...")
            asset = projects.register_imported_media(pid, final_path, f"{safe_stem}{ext}", kind="video")

            # Fetch native YouTube captions if available (real transcript, pause-aware cues!)
            eff_settings = projects.get_settings()
            cap_defaults = eff_settings.get("caption_defaults") or {}
            chosen_lang = str(caption_language or cap_defaults.get("language") or "auto")
            if media.is_youtube(clean):
                _set(progress=0.92, stage="Checking video captions...")
                try:
                    yt_caps = media.youtube_words(clean)
                    if yt_caps and yt_caps[0]:
                        words, lang = yt_caps
                        words = ai_transcribe.translate_or_adapt_words(words, chosen_lang, title=title)
                        cues = ai_transcribe.words_to_cues(words)
                        proj = projects.get_project(pid)
                        proj["analysis"]["transcript_words"] = words
                        proj["analysis"]["transcript_source"] = f"youtube_captions ({lang})"
                        proj["analysis"]["caption_language"] = chosen_lang
                        proj["timeline"]["captions"] = cues
                        projects.save_project(pid, proj)
                        projects.append_activity(pid, "import", f"Imported {len(words)} timed caption words ({len(cues)} cues) from source link.")
                except Exception:
                    pass

            # Apply requested aspect, caption placement/size/language & auto_captions setting onto project timeline
            proj = projects.get_project(pid)
            eff_reels = eff_settings.get("reels") or {}
            proj.setdefault("timeline", {})["aspect"] = eff_reels.get("aspect", "9:16")
            cc = proj["timeline"].setdefault("caption_config", {})
            cc["enabled"] = bool(eff_reels.get("auto_captions", True))
            cc["language"] = chosen_lang
            cc["x_offset"] = int(cap_defaults.get("x_offset", cc.get("x_offset", 50)))
            cc["y_offset"] = int(cap_defaults.get("y_offset", cc.get("y_offset", 80)))
            cc["font_size"] = int(cap_defaults.get("font_size", cc.get("font_size", 64)))
            projects.save_project(pid, proj)

            if process_immediately:
                _set(progress=0.96, stage="Starting AI peak-moment & face tracking pipeline...")
                automation.start_pipeline(pid, trigger="manual")
            else:
                automation.start_pipeline(pid, trigger="auto")

            _set(
                status="done",
                progress=1.0,
                stage=f"Ready in project — '{asset['name']}'",
                finished_at=time.time(),
            )
        except Exception as e:
            if tmp_dir and tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)
            _set(status="error", stage="Download failed", error=str(e), finished_at=time.time())

    threading.Thread(target=_worker, name=f"agentvid-ingest-{ingest_id}", daemon=True).start()
    return get_ingest_status(ingest_id)
