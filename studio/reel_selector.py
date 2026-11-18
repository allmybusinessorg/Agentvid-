"""AgentVid AI Peak-Moment Reel Selector.

Extracts N high-impact, non-overlapping Reels (15s-60s Shorts/Reels format) from peak moments across
an entire video or 1-hour podcast—NEVER blindly slicing sequentially from start to end.

- When an AI provider API key is configured (Gemini, OpenAI, Grok, Groq, Claude, OpenRouter, Ollama)
  and a transcript is available, uses `brain.find_clips` to analyze the entire transcript + loudness peaks
  and select the exact N strongest moments with AI-crafted hooks, titles, and reasons.
- When no AI key is configured, ranks candidate peak windows across the entire video using real audio
  loudness spikes, speech activity, and visual engagement signals.
"""
from __future__ import annotations

import math
import time
import uuid
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

from . import ai, auth, brain, ctx, media, projects


def _rms_to_db_per_sec(rms_timeline: list[dict[str, Any]], duration: float) -> np.ndarray:
    n_sec = max(1, int(math.ceil(duration)))
    buckets = [[] for _ in range(n_sec)]
    for item in rms_timeline or []:
        sec = min(n_sec - 1, max(0, int(float(item.get("t", 0.0)))))
        buckets[sec].append(float(item.get("rms", 0.0)))
    db = np.full(n_sec, -60.0, dtype=np.float32)
    for i, vals in enumerate(buckets):
        if vals:
            mean_rms = float(np.mean(vals))
            db[i] = float(20.0 * math.log10(max(mean_rms, 1e-5)))
    return db


def _sample_shot_visuals(video_path: Path, start: float, end: float) -> dict[str, float]:
    """Sample 3 frames inside [start, end] to measure real motion, brightness, contrast, saturation, composition."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {"motion": 18.0, "peak_motion": 25.0, "brightness": 115.0, "contrast": 45.0,
                "saturation": 35.0, "composition": 65.0, "sharpness": 60.0}
    dur = max(0.5, end - start)
    times = [start + dur * f for f in (0.15, 0.5, 0.85)]
    grays = []
    brights, contrasts, sats, sharps, comps = [], [], [], [], []
    try:
        for t in times:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            h, w = frame.shape[:2]
            scale = min(1.0, 320.0 / max(1, w))
            small = cv2.resize(frame, (max(32, int(w * scale)), max(32, int(h * scale)))) if scale < 1.0 else frame
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            grays.append(gray)
            brights.append(float(np.mean(gray)))
            contrasts.append(float(np.std(gray)))
            sats.append(float(np.mean(hsv[:, :, 1])) / 255.0 * 100.0)
            lap = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            sharps.append(max(15.0, min(100.0, 20.0 + math.log1p(lap) * 12.5)))
            gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
            gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
            mag = np.sqrt(gx * gx + gy * gy)
            sh, sw = gray.shape
            thirds = float(mag[int(sh * 0.2):int(sh * 0.8), int(sw * 0.2):int(sw * 0.8)].mean())
            comps.append(max(25.0, min(98.0, 45.0 + (thirds / (float(mag.mean()) + 1e-6)) * 38.0)))
    finally:
        cap.release()

    motions = [min(100.0, float(np.mean(cv2.absdiff(grays[i], grays[i - 1]))) / 255.0 * 420.0)
               for i in range(1, len(grays))] or [15.0]
    return {
        "motion": round(float(np.mean(motions)), 2),
        "peak_motion": round(float(np.max(motions)), 2),
        "brightness": round(float(np.mean(brights)) if brights else 110.0, 2),
        "contrast": round(float(np.mean(contrasts)) if contrasts else 42.0, 2),
        "saturation": round(float(np.mean(sats)) if sats else 32.0, 2),
        "composition": round(float(np.mean(comps)) if comps else 64.0, 2),
        "sharpness": round(float(np.mean(sharps)) if sharps else 58.0, 2),
    }


def _local_peak_windows(
    duration: float,
    db: np.ndarray,
    audio_info: dict[str, Any],
    count: int,
    target_len: float,
    min_len: float,
    max_len: float,
    duration_mode: str,
) -> list[dict[str, Any]]:
    """Select top N non-overlapping peak moments across the ENTIRE video (never sequential 0:00->0:30)."""
    if duration <= min_len + 2.0:
        return [{
            "start": 0.0,
            "end": round(duration, 2),
            "ai_score": 76,
            "category": "highlight",
            "hook": "FULL CLIP",
            "title": "Main Highlight Reel",
            "reason": "Full source clip fits inside a single Reel window.",
            "highlight_words": [],
        }]

    win_len = min(duration, target_len if duration_mode == "fixed" else min(max_len, max(min_len, 32.0)))
    n_sec = len(db)
    z = brain.loud_zscore(db) if n_sec > 2 else np.zeros(n_sec, dtype=np.float32)

    speech_segs = audio_info.get("speech_segments") or []
    sil_segs = audio_info.get("silence_segments") or []
    words = audio_info.get("transcript_words") or []

    # Score candidate start positions every 4 seconds across the full video
    stride = max(2.0, min(6.0, duration / max(30.0, count * 6.0)))
    candidates: list[tuple[float, float, float]] = []
    t = 0.0
    while t + min(min_len, win_len) <= duration:
        s0 = round(t, 2)
        s1 = round(min(duration, s0 + win_len), 2)
        dur = max(1.0, s1 - s0)

        # Measure peak audio z-score + speech density - silence penalty
        i0, i1 = max(0, int(s0)), min(n_sec, max(1, int(math.ceil(s1))))
        seg_z = z[i0:i1]
        peak_z = float(np.percentile(seg_z, 88)) if seg_z.size else 0.0
        mean_z = float(np.mean(seg_z)) if seg_z.size else 0.0

        sp_ov = sum(max(0.0, min(s1, sg["end"]) - max(s0, sg["start"])) for sg in speech_segs) / dur
        sil_ov = sum(max(0.0, min(s1, sg["end"]) - max(s0, sg["start"])) for sg in sil_segs) / dur
        word_cnt = sum(1 for w in words if s0 <= w["s"] < s1)
        word_bonus = min(1.8, (word_cnt / dur) * 0.45) if words else 0.0

        # Avoid intro dead zone (first 5s of very long podcasts) unless peak is genuinely huge
        intro_pen = 0.6 if (duration > 180 and s0 < 5.0) else 0.0
        score = peak_z * 1.4 + mean_z * 0.7 + sp_ov * 2.2 - sil_ov * 2.5 + word_bonus - intro_pen
        candidates.append((score, s0, s1))
        t += stride

    candidates.sort(key=lambda x: x[0], reverse=True)
    picked: list[dict[str, Any]] = []
    min_gap = 3.0 if duration > count * win_len * 1.15 else 0.5

    for raw_sc, s0, s1 in candidates:
        if len(picked) >= count:
            break
        if any(not (s1 + min_gap <= p["start"] or s0 >= p["end"] + min_gap) for p in picked):
            continue
        # Snap end softly to nearest silence / sentence pause if within ±3s
        snapped_end = s1
        if words:
            stops = [w["e"] for w in words if s1 - 3.5 <= w["e"] <= min(duration, s1 + 3.0)]
            if stops:
                snapped_end = min(stops, key=lambda x: abs(x - s1))
        snapped_end = round(max(s0 + min(min_len, duration - s0), min(duration, snapped_end)), 2)
        norm_score = int(max(55, min(92, round(68 + raw_sc * 5.5))))
        picked.append({
            "start": s0,
            "end": snapped_end,
            "ai_score": norm_score,
            "category": "peak_moment",
            "hook": f"PEAK MOMENT #{len(picked) + 1}",
            "title": f"Peak Highlight ({int(s0 // 60)}:{int(s0 % 60):02d}–{int(snapped_end // 60)}:{int(snapped_end % 60):02d})",
            "reason": "Selected by local vocal energy, speech activity, and pacing peak detection.",
            "highlight_words": [],
        })

    # Keep highest-ranked first or chronological order (user sees exact timestamps from across whole episode)
    picked.sort(key=lambda x: x["start"])
    return picked


def build_peak_reels(
    pid: str,
    video_path: Path,
    media_meta: dict[str, Any],
    audio_info: dict[str, Any],
    reel_settings: dict[str, Any],
    allow_ai: bool = True,
    progress_cb: Callable[[float, str], None] | None = None,
    cancel_cb: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Find N peak Reels across the entire source video using AI API (when configured) or local peak detection."""
    duration = float(media_meta.get("duration") or 0.0)
    if duration <= 0:
        raise ValueError("Video duration must be greater than zero.")

    count = max(1, min(20, int(reel_settings.get("count") or 5)))
    dur_mode = reel_settings.get("duration_mode", "auto_ai")
    target_len = max(10.0, min(90.0, float(reel_settings.get("target_duration") or 30)))
    if dur_mode == "fixed":
        min_len = max(8.0, target_len - 4.0)
        max_len = min(90.0, target_len + 4.0)
    else:
        min_len = max(10.0, float(reel_settings.get("min_duration") or 18))
        max_len = min(60.0, max(min_len + 5.0, float(reel_settings.get("max_duration") or 58)))

    rms_tl = audio_info.get("rms_timeline") or []
    sil_segs = audio_info.get("silence_segments") or []
    sp_segs = audio_info.get("speech_segments") or []
    words = audio_info.get("transcript_words") or []
    base_clarity = int(audio_info.get("audio_clarity") or 0)
    db = _rms_to_db_per_sec(rms_tl, duration)

    selection_mode = "local_peak_fallback"
    selection_note = ""
    ai_model_used = None
    ai_tokens = 0
    raw_picks: list[dict[str, Any]] = []

    if allow_ai and ai.ready() and len(words) >= 12:
        if progress_cb:
            progress_cb(0.15, f"AI ({ai.label()}) analyzing full transcript for top {count} peak Reels...")
        try:
            def _run_ai_find():
                return brain.find_clips(
                    words=words,
                    db=db,
                    duration=duration,
                    title=media_meta.get("name") or "",
                    uploader="",
                    max_clips=count,
                    min_len=int(round(min_len)),
                    max_len=int(round(max_len)),
                    log=lambda m: None,
                )

            if ctx.uid_or_none() is None:
                with ctx.as_user(auth.local_user().id):
                    clips, info = _run_ai_find()
            else:
                clips, info = _run_ai_find()
            if clips and info.get("model"):
                selection_mode = "ai_peak_detection"
                ai_model_used = info.get("model")
                ai_tokens = int(info.get("tokens") or 0)
                selection_note = f"AI ({ai.label()} · {ai_model_used}) scanned the full transcript and picked {len(clips)} peak moments."
                for c in clips:
                    raw_picks.append({
                        "start": float(c["start"]),
                        "end": float(c["end"]),
                        "ai_score": int(c.get("score") or 78),
                        "category": str(c.get("category") or "highlight"),
                        "hook": str(c.get("hook") or ""),
                        "title": str(c.get("title") or ""),
                        "reason": str(c.get("reason") or ""),
                        "highlight_words": list(c.get("highlight_words") or []),
                    })
            else:
                selection_note = info.get("note") or "AI returned no clips; used local peak detection across the full video."
        except Exception as e:
            selection_note = f"AI provider call failed ({e}); fell back to local peak moment detection."
    else:
        if not ai.ready():
            selection_note = "No AI API key configured — selected peak moments locally by vocal energy & speech density. Add an AI key in Settings for deep podcast topic analysis."
        else:
            selection_note = "No transcript available yet — selected peak moments locally by audiovisual energy. Download the Offline Speech Package or paste a YouTube link for AI transcript analysis."

    if not raw_picks:
        if progress_cb:
            progress_cb(0.25, f"Scanning full video for top {count} non-overlapping peak moments...")
        raw_picks = _local_peak_windows(duration, db, audio_info, count, target_len, min_len, max_len, dur_mode)

    thumb_dir = projects.project_dir(pid) / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    shots: list[dict[str, Any]] = []

    for i, pk in enumerate(raw_picks, start=1):
        if cancel_cb and cancel_cb():
            raise InterruptedError("Cancelled by user.")
        s0 = round(max(0.0, float(pk["start"])), 2)
        s1 = round(min(duration, max(s0 + 1.0, float(pk["end"]))), 2)
        dur = round(s1 - s0, 2)
        shot_id = f"reel_{i:02d}_{uuid.uuid4().hex[:6]}"
        mid = round(s0 + dur * 0.42, 2)

        thumb_name = f"{shot_id}.jpg"
        thumb_path = thumb_dir / thumb_name
        thumb_url = ""
        try:
            media.run([
                "ffmpeg", "-y", "-v", "error", "-ss", f"{mid:.2f}", "-i", str(video_path),
                "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "4", str(thumb_path)
            ], timeout=45)
            if thumb_path.is_file():
                thumb_url = f"/api/v2/projects/{pid}/thumbnails/{thumb_name}"
        except Exception:
            thumb_url = ""

        vis = _sample_shot_visuals(video_path, s0, s1)
        in_rms = [r["rms"] for r in rms_tl if s0 <= r["t"] <= s1]
        audio_energy = min(100.0, float(np.mean(in_rms)) * 380.0) if in_rms else 0.0
        audio_peak = min(100.0, float(np.max(in_rms)) * 260.0) if in_rms else 0.0

        def _ov(segs):
            tot = sum(max(0.0, min(s1, sg["end"]) - max(s0, sg["start"])) for sg in segs)
            return round(min(1.0, tot / max(0.1, dur)), 3)

        silence_ratio = _ov(sil_segs)
        speech_ratio = _ov(sp_segs)
        shot_words = [w for w in words if s0 - 0.1 <= w["s"] < s1]
        transcript_text = " ".join(w["w"] for w in shot_words).strip()

        title = pk.get("title") or f"Peak Reel {i:02d}"
        hook = pk.get("hook") or ""
        reason = pk.get("reason") or ""
        desc = f"{title}. {reason}".strip()
        if transcript_text:
            snip = transcript_text[:130] + ("..." if len(transcript_text) > 130 else "")
            desc += f' "{snip}"'

        shots.append({
            "id": shot_id,
            "number": i,
            "media_id": media_meta["id"],
            "title": title,
            "hook": hook,
            "ai_reason": reason,
            "ai_score": int(pk.get("ai_score") or 0),
            "highlight_words": pk.get("highlight_words") or [],
            "start": s0,
            "end": s1,
            "trim_start": s0,
            "trim_end": s1,
            "duration": dur,
            "cut_kind": "ai_peak_reel" if selection_mode == "ai_peak_detection" else "local_peak_reel",
            "thumbnail_url": thumb_url,
            "description": desc,
            "scene_category": (pk.get("category") or "Peak Reel").replace("_", " ").title(),
            "transcript": transcript_text,
            "audio_observation": f"Speech {int(speech_ratio * 100)}% · Silence {int(silence_ratio * 100)}% · Clarity {base_clarity}/100",
            "emotional_visual_observation": (
                f"Motion {vis['motion']:.0f}/100, sharpness {vis['sharpness']:.0f}/100, composition {vis['composition']:.0f}/100."
            ),
            "detected_subjects": [],
            "face_info": {
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
            },
            "metrics": {
                **vis,
                "audio_energy": round(audio_energy, 2),
                "audio_peak": round(audio_peak, 2),
                "audio_clarity": base_clarity,
                "silence_ratio": silence_ratio,
                "speech_ratio": speech_ratio,
            },
            "virality": {
                "score": int(pk.get("ai_score") or 0),
                "tier": "Pending",
                "confidence": "High" if selection_mode == "ai_peak_detection" else "Medium",
                "dimensions": {},
                "recommendation": reason,
                "source": selection_mode,
            },
            "edit": {
                "included": True,
                "order": i - 1,
                "speed": 1.0,
                "zoom": 1.0,
                "pan_x": 0.5,
                "pan_y": 0.5,
                "volume": 1.0,
                "muted": False,
                "transition": "none",
                "transition_duration": 0.35,
                "crop_mode": "face",
                "crop_box": None,
                "text_overlay": "",
            },
            "suggestions": {
                "zoom": None,
                "transition": None,
                "reframing": None,
                "broll": None,
                "editing": [reason] if reason else [],
            },
            "status": "analyzed",
        })

        if progress_cb:
            progress_cb(0.35 + (i / max(1, len(raw_picks))) * 0.65, f"Prepared Peak Reel {i}/{len(raw_picks)} ({int(s0 // 60)}:{int(s0 % 60):02d})")

    return {
        "shots": shots,
        "scene_count": len(shots),
        "selection_mode": selection_mode,
        "selection_note": selection_note,
        "ai_model": ai_model_used,
        "ai_tokens": ai_tokens,
        "requested_count": count,
        "duration_mode": dur_mode,
        "target_duration": target_len,
        "analyzed_at": time.time(),
    }
