"""AgentVid local video analysis: scene detection, shot segmentation, audio/silence analysis, thumbnails."""
from __future__ import annotations

import math
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np
import soundfile as sf

from . import media, projects, transcribe


def _check_cancel(cancel_cb: Callable[[], bool] | None):
    if cancel_cb and cancel_cb():
        raise InterruptedError("Operation cancelled by user.")


def _check_pause(pause_cb: Callable[[], None] | None):
    if pause_cb:
        pause_cb()


def extract_audio_features(
    video_path: Path,
    duration: float,
    has_audio: bool,
    silence_enabled: bool = True,
    captions_enabled: bool = False,
    cancel_cb: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Extract real audio RMS envelope, silence intervals, speech activity, and optional local transcript."""
    if not has_audio or duration <= 0:
        return {
            "rms_timeline": [],
            "silence_segments": [],
            "speech_segments": [],
            "audio_clarity": 0,
            "transcript_words": [],
            "transcript_source": "no_audio",
        }

    _check_cancel(cancel_cb)
    with tempfile.TemporaryDirectory(prefix="av_aud_") as td:
        wav_path = Path(td) / "audio.wav"
        try:
            media.run([
                "ffmpeg", "-y", "-v", "error", "-i", str(video_path),
                "-vn", "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le", str(wav_path)
            ], timeout=300)
        except Exception:
            return {
                "rms_timeline": [],
                "silence_segments": [],
                "speech_segments": [],
                "audio_clarity": 0,
                "transcript_words": [],
                "transcript_source": "audio_extract_failed",
            }

        _check_cancel(cancel_cb)
        data, sr = sf.read(str(wav_path), dtype="float32")
        if data.ndim > 1:
            data = data.mean(axis=1)

        hop = max(1, int(sr * 0.25))  # 250ms windows
        n_win = max(1, len(data) // hop)
        rms_vals = []
        zcr_vals = []
        for i in range(n_win):
            seg = data[i * hop:(i + 1) * hop]
            if seg.size == 0:
                continue
            rms = float(np.sqrt(np.mean(seg * seg) + 1e-12))
            zcr = float(np.mean(np.abs(np.diff(np.signbit(seg))))) if seg.size > 1 else 0.0
            rms_vals.append(rms)
            zcr_vals.append(zcr)

        rms_arr = np.array(rms_vals, dtype=np.float32) if rms_vals else np.zeros(1, dtype=np.float32)
        p95 = float(np.percentile(rms_arr, 95)) if rms_arr.size else 0.0
        p10 = float(np.percentile(rms_arr, 10)) if rms_arr.size else 0.0
        peak = float(np.max(rms_arr)) if rms_arr.size else 0.0

        # Audio clarity: signal-to-noise ratio + non-clipping headroom
        snr_db = 20.0 * math.log10((p95 + 1e-6) / (p10 + 1e-6))
        clip_penalty = 15.0 if peak > 0.98 else 0.0
        audio_clarity = int(max(10, min(100, round(35 + snr_db * 2.2 - clip_penalty)))) if p95 > 0.002 else 15

        silence_thresh = max(0.006, p95 * 0.14)
        speech_thresh = max(0.015, p95 * 0.28)

        silence_segments = []
        speech_segments = []
        if silence_enabled:
            in_sil = False
            sil_s = 0.0
            for idx, v in enumerate(rms_vals):
                t = idx * 0.25
                if v < silence_thresh:
                    if not in_sil:
                        in_sil = True
                        sil_s = t
                else:
                    if in_sil:
                        if t - sil_s >= 0.75:
                            silence_segments.append({"start": round(sil_s, 2), "end": round(t, 2), "duration": round(t - sil_s, 2)})
                        in_sil = False
            if in_sil and (n_win * 0.25 - sil_s) >= 0.75:
                end_t = min(duration, n_win * 0.25)
                silence_segments.append({"start": round(sil_s, 2), "end": round(end_t, 2), "duration": round(end_t - sil_s, 2)})

        in_sp = False
        sp_s = 0.0
        for idx, (v, z) in enumerate(zip(rms_vals, zcr_vals)):
            t = idx * 0.25
            # Typical speech has moderate ZCR and energy above threshold
            is_speech = v >= speech_thresh and 0.01 <= z <= 0.45
            if is_speech:
                if not in_sp:
                    in_sp = True
                    sp_s = t
            else:
                if in_sp:
                    if t - sp_s >= 0.5:
                        speech_segments.append({"start": round(sp_s, 2), "end": round(t, 2), "duration": round(t - sp_s, 2)})
                    in_sp = False
        if in_sp and (n_win * 0.25 - sp_s) >= 0.5:
            end_t = min(duration, n_win * 0.25)
            speech_segments.append({"start": round(sp_s, 2), "end": round(end_t, 2), "duration": round(end_t - sp_s, 2)})

        rms_timeline = [
            {"t": round(i * 0.25, 2), "rms": round(float(v), 4)}
            for i, v in enumerate(rms_vals)
        ]

        transcript_words: list[dict[str, Any]] = []
        transcript_source = "audio_energy_only"
        if captions_enabled:
            _check_cancel(cancel_cb)
            # Only run local ASR if a local model is already installed; never fabricate text
            if transcribe.model_ready():
                try:
                    audio_i16 = media.load_audio(wav_path)
                    words = transcribe.transcribe(audio_i16)
                    if words:
                        transcript_words = words
                        transcript_source = "offline_speech_model"
                except Exception:
                    transcript_source = "asr_unavailable"
            else:
                transcript_source = "model_not_downloaded"

        return {
            "rms_timeline": rms_timeline,
            "silence_segments": silence_segments,
            "speech_segments": speech_segments,
            "audio_clarity": audio_clarity,
            "transcript_words": transcript_words,
            "transcript_source": transcript_source,
        }


def _composition_score(gray: np.ndarray) -> float:
    """Measure rule-of-thirds visual interest concentration using Sobel gradient energy."""
    h, w = gray.shape
    if h < 16 or w < 16:
        return 50.0
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    total = float(mag.mean()) + 1e-6

    # Rule-of-thirds interior zone (middle 60% weighted around thirds bands)
    y1, y2 = int(h * 0.2), int(h * 0.8)
    x1, x2 = int(w * 0.2), int(w * 0.8)
    thirds = float(mag[y1:y2, x1:x2].mean())
    ratio = thirds / total
    return float(max(25.0, min(98.0, 45.0 + ratio * 38.0)))


def _sharpness_score(gray: np.ndarray) -> float:
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    return float(max(15.0, min(100.0, 20.0 + math.log1p(lap_var) * 12.5)))


def detect_scenes_and_shots(
    pid: str,
    video_path: Path,
    media_meta: dict[str, Any],
    scene_detection_enabled: bool = True,
    shot_segmentation_enabled: bool = True,
    audio_info: dict[str, Any] | None = None,
    sample_fps: float = 1.5,
    max_width: int = 384,
    progress_cb: Callable[[float, str], None] | None = None,
    cancel_cb: Callable[[], bool] | None = None,
    pause_cb: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Perform real local scene change detection and shot segmentation with per-shot thumbnails and metrics."""
    duration = float(media_meta.get("duration") or 0.0)
    if duration <= 0:
        raise ValueError("Video duration must be greater than zero.")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video for analysis: {video_path.name}")

    native_fps = float(cap.get(cv2.CAP_PROP_FPS) or media_meta.get("fps") or 30.0)
    if native_fps <= 0 or native_fps > 240:
        native_fps = 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or round(duration * native_fps))
    # Cap total sampled frames on long videos (~240 samples max) for fast local responsiveness
    eff_sample_fps = min(max(0.5, sample_fps), max(0.25, 240.0 / max(1.0, duration)))
    step = max(1, int(round(native_fps / eff_sample_fps)))

    frame_metrics: list[dict[str, Any]] = []
    prev_hist = None
    prev_gray = None
    frame_idx = 0

    try:
        while True:
            _check_cancel(cancel_cb)
            _check_pause(pause_cb)
            if frame_idx % step != 0:
                if not cap.grab():
                    break
                frame_idx += 1
                continue
            ok, frame = cap.read()
            if not ok:
                break
            if True:
                t = round(frame_idx / native_fps, 3)
                h, w = frame.shape[:2]
                scale = min(1.0, max_width / max(1, w))
                small = cv2.resize(frame, (max(32, int(w * scale)), max(32, int(h * scale)))) if scale < 1.0 else frame
                hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

                hist = cv2.calcHist([hsv], [0, 1], None, [24, 16], [0, 180, 0, 256])
                cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)

                cut_dist = 0.0
                motion = 0.0
                if prev_hist is not None and prev_gray is not None:
                    corr = float(cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL))
                    hist_dist = max(0.0, 1.0 - corr)
                    diff = float(np.mean(cv2.absdiff(gray, prev_gray))) / 255.0
                    cut_dist = hist_dist * 0.68 + diff * 0.85
                    motion = min(100.0, diff * 420.0)

                brightness = float(np.mean(gray))
                contrast = float(np.std(gray))
                saturation = float(np.mean(hsv[:, :, 1])) / 255.0 * 100.0
                comp = _composition_score(gray)
                sharp = _sharpness_score(gray)

                frame_metrics.append({
                    "t": t,
                    "cut_dist": round(cut_dist, 4),
                    "motion": round(motion, 2),
                    "brightness": round(brightness, 2),
                    "contrast": round(contrast, 2),
                    "saturation": round(saturation, 2),
                    "composition": round(comp, 2),
                    "sharpness": round(sharp, 2),
                })
                prev_hist = hist
                prev_gray = gray

                if progress_cb and total_frames > 0:
                    progress_cb(min(0.7, frame_idx / total_frames * 0.7), f"Analyzing video frames ({t:.1f}s / {duration:.1f}s)")
            frame_idx += 1
    finally:
        cap.release()

    if not frame_metrics:
        raise RuntimeError("No readable video frames found during analysis.")

    # Detect visual scene boundaries
    cut_points: list[tuple[float, str]] = []
    if scene_detection_enabled and len(frame_metrics) >= 3:
        dists = np.array([m["cut_dist"] for m in frame_metrics[1:]], dtype=np.float32)
        mean_d = float(np.mean(dists))
        std_d = float(np.std(dists))
        threshold = max(0.32, mean_d + 1.65 * std_d)
        last_cut = 0.0
        for m in frame_metrics[1:]:
            if m["cut_dist"] >= threshold and (m["t"] - last_cut) >= 2.0 and (duration - m["t"]) >= 1.5:
                cut_points.append((m["t"], "visual_cut"))
                last_cut = m["t"]

    # Build shot ranges
    ranges: list[tuple[float, float, str]] = []
    if not shot_segmentation_enabled:
        ranges = [(0.0, round(duration, 2), "full_video")]
    else:
        boundaries = [0.0] + [t for t, _ in cut_points] + [round(duration, 2)]
        boundary_kinds = ["opening"] + [k for _, k in cut_points] + ["ending"]

        # If any segment is very long, subdivide cleanly using silence boundaries or pacing (capped reasonably for long videos)
        silences = (audio_info or {}).get("silence_segments") or []
        refined: list[tuple[float, float, str]] = []
        max_seg = 18.0 if duration <= 180 else 30.0
        target_len = 10.0 if duration <= 90 else (15.0 if duration <= 240 else 25.0)
        for idx in range(len(boundaries) - 1):
            s0, s1 = boundaries[idx], boundaries[idx + 1]
            kind = boundary_kinds[idx]
            seg_dur = s1 - s0
            if seg_dur <= max_seg:
                if seg_dur >= 0.8:
                    refined.append((round(s0, 2), round(s1, 2), kind))
                continue
            # Look for silence breaks inside long shot
            inner_cuts = []
            cur = s0
            while s1 - cur > target_len * 1.45:
                ideal = cur + target_len
                best_sil = None
                for sil in silences:
                    mid = (sil["start"] + sil["end"]) / 2.0
                    if cur + 4.0 <= mid <= s1 - 3.0 and abs(mid - ideal) <= 4.5:
                        if best_sil is None or abs(mid - ideal) < abs(best_sil - ideal):
                            best_sil = mid
                nxt = round(best_sil if best_sil is not None else ideal, 2)
                inner_cuts.append((nxt, "audio_pause" if best_sil is not None else "pacing_segment"))
                cur = nxt
            sub_bounds = [(s0, kind)] + inner_cuts + [(s1, "end")]
            for j in range(len(sub_bounds) - 1):
                a, k = sub_bounds[j]
                b, _ = sub_bounds[j + 1]
                if b - a >= 0.8:
                    refined.append((round(a, 2), round(b, 2), k))
        ranges = refined or [(0.0, round(duration, 2), "full_video")]

    # Generate thumbnails and assemble rich shot objects
    thumb_dir = projects.project_dir(pid) / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    rms_tl = (audio_info or {}).get("rms_timeline") or []
    sil_segs = (audio_info or {}).get("silence_segments") or []
    sp_segs = (audio_info or {}).get("speech_segments") or []
    words = (audio_info or {}).get("transcript_words") or []
    base_audio_clarity = int((audio_info or {}).get("audio_clarity") or 0)

    shots: list[dict[str, Any]] = []
    total_shots = len(ranges)
    for i, (s0, s1, cut_kind) in enumerate(ranges, start=1):
        _check_cancel(cancel_cb)
        _check_pause(pause_cb)
        dur = round(max(0.1, s1 - s0), 2)
        shot_id = f"shot_{i:02d}_{uuid.uuid4().hex[:6]}"
        mid = round(s0 + dur * 0.45, 2)
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

        # Aggregate frame metrics inside [s0, s1]
        in_frames = [m for m in frame_metrics if s0 <= m["t"] <= s1] or [frame_metrics[min(len(frame_metrics) - 1, i - 1)]]
        avg_motion = float(np.mean([m["motion"] for m in in_frames]))
        peak_motion = float(np.max([m["motion"] for m in in_frames]))
        avg_bright = float(np.mean([m["brightness"] for m in in_frames]))
        avg_contrast = float(np.mean([m["contrast"] for m in in_frames]))
        avg_sat = float(np.mean([m["saturation"] for m in in_frames]))
        avg_comp = float(np.mean([m["composition"] for m in in_frames]))
        avg_sharp = float(np.mean([m["sharpness"] for m in in_frames]))

        # Audio stats inside shot
        in_rms = [r["rms"] for r in rms_tl if s0 <= r["t"] <= s1]
        audio_energy = min(100.0, float(np.mean(in_rms)) * 380.0) if in_rms else 0.0
        audio_peak = min(100.0, float(np.max(in_rms)) * 260.0) if in_rms else 0.0

        def _overlap_ratio(segs):
            tot = 0.0
            for seg in segs:
                ov = max(0.0, min(s1, seg["end"]) - max(s0, seg["start"]))
                tot += ov
            return round(min(1.0, tot / max(0.1, dur)), 3)

        silence_ratio = _overlap_ratio(sil_segs)
        speech_ratio = _overlap_ratio(sp_segs)

        shot_words = [w for w in words if s0 - 0.1 <= w["s"] < s1]
        transcript_text = " ".join(w["w"] for w in shot_words).strip()

        # Scene category based on measurable visual + audio cues
        if avg_motion >= 32:
            scene_cat = "High Action"
        elif speech_ratio >= 0.45 and avg_motion < 18:
            scene_cat = "Dialogue / Presenter"
        elif avg_bright < 52:
            scene_cat = "Low-Light / Moody"
        elif avg_motion < 6 and silence_ratio > 0.6:
            scene_cat = "Static / Pause"
        elif avg_sat > 42 and avg_comp > 68:
            scene_cat = "Cinematic B-Roll"
        else:
            scene_cat = "General Scene"

        # Factual, non-fabricated observation summary
        obs_parts = []
        if avg_motion >= 30:
            obs_parts.append(f"dynamic movement (motion {avg_motion:.0f}/100)")
        elif avg_motion <= 8:
            obs_parts.append("steady camera framing")
        else:
            obs_parts.append(f"moderate motion ({avg_motion:.0f}/100)")

        if avg_bright < 55:
            obs_parts.append("low-key lighting")
        elif avg_bright > 185:
            obs_parts.append("bright high-key exposure")
        else:
            obs_parts.append("balanced exposure")

        if speech_ratio >= 0.45:
            audio_obs = f"Active speech/vocal energy ({int(speech_ratio * 100)}% of shot, clarity {base_audio_clarity}/100)"
        elif silence_ratio >= 0.65:
            audio_obs = f"Mostly quiet / dead air ({int(silence_ratio * 100)}% silent)"
        elif in_rms:
            audio_obs = f"Ambient audio activity (energy {audio_energy:.0f}/100, clarity {base_audio_clarity}/100)"
        else:
            audio_obs = "No audio track detected"

        desc = f"{scene_cat} shot ({dur:.1f}s) featuring {', '.join(obs_parts)}."
        if transcript_text:
            snippet = transcript_text[:110] + ("..." if len(transcript_text) > 110 else "")
            desc += f' Transcript: "{snippet}"'

        shots.append({
            "id": shot_id,
            "number": i,
            "media_id": media_meta["id"],
            "start": s0,
            "end": s1,
            "trim_start": s0,
            "trim_end": s1,
            "duration": dur,
            "cut_kind": cut_kind,
            "thumbnail_url": thumb_url,
            "description": desc,
            "scene_category": scene_cat,
            "transcript": transcript_text,
            "audio_observation": audio_obs,
            "emotional_visual_observation": (
                f"Visual contrast {avg_contrast:.0f}, sharpness {avg_sharp:.0f}/100, "
                f"color richness {avg_sat:.0f}/100, composition {avg_comp:.0f}/100."
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
                "motion": round(avg_motion, 2),
                "peak_motion": round(peak_motion, 2),
                "brightness": round(avg_bright, 2),
                "contrast": round(avg_contrast, 2),
                "saturation": round(avg_sat, 2),
                "composition": round(avg_comp, 2),
                "sharpness": round(avg_sharp, 2),
                "audio_energy": round(audio_energy, 2),
                "audio_peak": round(audio_peak, 2),
                "audio_clarity": base_audio_clarity,
                "silence_ratio": silence_ratio,
                "speech_ratio": speech_ratio,
            },
            "virality": {
                "score": 0,
                "tier": "Unscored",
                "confidence": "Pending",
                "dimensions": {},
                "recommendation": "",
                "source": "pending",
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
                "transition_duration": 0.4,
                "crop_mode": "auto",
                "crop_box": None,
                "text_overlay": "",
            },
            "suggestions": {
                "zoom": None,
                "transition": None,
                "reframing": None,
                "broll": None,
                "editing": [],
            },
            "status": "analyzed",
        })

        if progress_cb:
            progress_cb(0.7 + (i / max(1, total_shots)) * 0.3, f"Segmented shot {i}/{total_shots}")

    return {
        "shots": shots,
        "scene_count": len(cut_points) + 1,
        "cut_points": [{"t": t, "kind": k} for t, k in cut_points],
        "analyzed_at": time.time(),
    }
