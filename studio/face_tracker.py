"""AgentVid local AI face detection, multi-subject tracking, and smart reframing engine (OpenCV YuNet DNN)."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np


def _yunet_model_path() -> Path:
    res = os.environ.get("AGENTVID_RESOURCES")
    if res:
        cand = Path(res) / "models" / "face_detection_yunet_2023mar.onnx"
        if cand.is_file():
            return cand
    local = Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx"
    if local.is_file():
        return local
    raise FileNotFoundError("Bundled YuNet face detection model (face_detection_yunet_2023mar.onnx) not found.")


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax0, ay0, aw, ah = a
    bx0, by0, bw, bh = b
    ax1, ay1 = ax0 + aw, ay0 + ah
    bx1, by1 = bx0 + bw, by0 + bh
    ix = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    iy = max(0.0, min(ay1, by1) - max(ay0, by0))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def compute_smart_reframe(
    src_w: int,
    src_h: int,
    target_aspect: str,
    face_box: dict[str, float] | None,
) -> dict[str, Any]:
    """Compute optimal normalized crop rectangle [0..1] for 9:16, 1:1, or 16:9 without clipping the face."""
    aspect_map = {"9:16": 9.0 / 16.0, "1:1": 1.0, "16:9": 16.0 / 9.0}
    target_ratio = aspect_map.get(target_aspect, 9.0 / 16.0)
    src_ratio = max(0.1, src_w / max(1, src_h))

    if src_ratio > target_ratio:
        crop_h = 1.0
        crop_w = min(1.0, target_ratio / src_ratio)
    else:
        crop_w = 1.0
        crop_h = min(1.0, src_ratio / target_ratio)

    if face_box:
        fx = float(face_box["x"])
        fy = float(face_box["y"])
        fw = float(face_box["w"])
        fh = float(face_box["h"])
        fcx = fx + fw * 0.5
        fcy = fy + fh * 0.5

        x = fcx - crop_w * 0.5
        y = fcy - crop_h * 0.38

        margin_x = min(0.03, fw * 0.25)
        margin_y = min(0.04, fh * 0.3)
        if x > fx - margin_x:
            x = fx - margin_x
        if x + crop_w < fx + fw + margin_x:
            x = fx + fw + margin_x - crop_w
        if y > fy - margin_y:
            y = fy - margin_y
        if y + crop_h < fy + fh + margin_y:
            y = fy + fh + margin_y - crop_h

        x = max(0.0, min(1.0 - crop_w, x))
        y = max(0.0, min(1.0 - crop_h, y))
        reason = "Centered on tracked primary subject with headroom protection."
    else:
        x = (1.0 - crop_w) * 0.5
        y = (1.0 - crop_h) * 0.5
        reason = "No face detected; using balanced center framing."

    return {
        "aspect": target_aspect,
        "x": round(x, 4),
        "y": round(y, 4),
        "w": round(crop_w, 4),
        "h": round(crop_h, 4),
        "pan_x": round(x + crop_w * 0.5, 4),
        "pan_y": round(y + crop_h * 0.5, 4),
        "reason": reason,
    }


def analyze_faces(
    video_path: Path,
    media_meta: dict[str, Any],
    shots: list[dict[str, Any]],
    face_config: dict[str, Any],
    subject_tracking_enabled: bool = True,
    sample_fps: float = 1.5,
    max_width: int = 480,
    progress_cb: Callable[[float, str], None] | None = None,
    cancel_cb: Callable[[], bool] | None = None,
    pause_cb: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Run local OpenCV YuNet neural face detection, 5-landmark visibility, multi-subject tracking & smart reframing."""
    if not face_config.get("enabled", True):
        return {
            "status": "disabled",
            "detected_faces_total": 0,
            "subjects": [],
            "frame_samples": [],
            "reframing_suggestions": {},
            "shot_updates": {},
            "model": "OpenCV YuNet Neural Face Detector (Disabled)",
            "analyzed_at": time.time(),
        }

    model_path = _yunet_model_path()
    sensitivity = max(0.1, min(1.0, float(face_config.get("sensitivity", 0.65))))
    min_face_px = max(16, min(240, int(face_config.get("min_face_size", 36))))
    multi_face = bool(face_config.get("multi_face", True))
    preferred_primary = face_config.get("primary_subject_id")

    # Map sensitivity (0.1..1.0) to YuNet score threshold: higher sensitivity -> lower threshold
    score_thresh = round(max(0.35, min(0.90, 0.92 - sensitivity * 0.48)), 3)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video for face tracking: {video_path.name}")

    native_fps = float(cap.get(cv2.CAP_PROP_FPS) or media_meta.get("fps") or 30.0)
    if native_fps <= 0 or native_fps > 240:
        native_fps = 30.0
    duration = float(media_meta.get("duration") or 0.0)
    src_w = int(media_meta.get("width") or cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    src_h = int(media_meta.get("height") or cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or round(duration * native_fps))
    eff_sample_fps = min(max(0.5, sample_fps), max(0.25, 220.0 / max(1.0, duration)))
    step = max(1, int(round(native_fps / eff_sample_fps)))
    sample_interval = step / native_fps
    track_timeout = max(3.5, sample_interval * 2.6)

    # Build targeted sample timestamps inside selected Peak Reels (much faster & higher precision on 1-hr podcasts!)
    targeted_times: list[float] | None = None
    if shots:
        shot_span = sum(max(0.2, float(sh.get("trim_end", sh["end"])) - float(sh.get("trim_start", sh["start"]))) for sh in shots)
        is_peak_reels = any(sh.get("cut_kind") in ("ai_peak_reel", "local_peak_reel") for sh in shots)
        if is_peak_reels or (duration > 180.0 and shot_span < duration * 0.85):
            per_shot = max(6, min(18, int(220 / max(1, len(shots)))))
            ts_list: list[float] = []
            for sh in sorted(shots, key=lambda x: float(x.get("trim_start", x["start"]))):
                s0 = max(0.0, float(sh.get("trim_start", sh["start"])))
                s1 = min(duration, float(sh.get("trim_end", sh["end"])))
                sdur = max(0.2, s1 - s0)
                n_pts = max(3, min(per_shot, int(round(sdur * max(0.5, min(1.5, sample_fps)))) + 1))
                for k in range(n_pts):
                    frac = (k + 0.5) / n_pts
                    ts_list.append(round(s0 + sdur * frac, 2))
            if ts_list:
                targeted_times = sorted(set(ts_list))
                if len(targeted_times) >= 2:
                    sample_interval = max(0.5, (shot_span / max(1, len(targeted_times))))
                    track_timeout = max(3.5, sample_interval * 2.6)

    detector = None
    det_size = (0, 0)

    active_tracks: dict[int, dict[str, Any]] = {}
    all_tracks: dict[int, dict[str, Any]] = {}
    next_track_id = 1
    frame_samples: list[dict[str, Any]] = []
    total_detections = 0
    frame_idx = 0
    t_ptr = 0

    try:
        while True:
            if cancel_cb and cancel_cb():
                raise InterruptedError("Face tracking cancelled by user.")
            if pause_cb:
                pause_cb()

            if targeted_times is not None:
                if t_ptr >= len(targeted_times):
                    break
                t = targeted_times[t_ptr]
                t_ptr += 1
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
            else:
                if frame_idx % step != 0:
                    if not cap.grab():
                        break
                    frame_idx += 1
                    continue
                ok, frame = cap.read()
                if not ok:
                    break
                t = round(frame_idx / native_fps, 2)

            if True:
                fh, fw = frame.shape[:2]
                scale = min(1.0, max_width / max(1, fw))
                sw = max(64, int(round(fw * scale)))
                sh = max(64, int(round(fh * scale)))
                small = cv2.resize(frame, (sw, sh)) if scale < 1.0 else frame

                if detector is None:
                    detector = cv2.FaceDetectorYN.create(
                        str(model_path), "", (sw, sh), score_thresh, 0.3, 50
                    )
                    det_size = (sw, sh)
                elif det_size != (sw, sh):
                    detector.setInputSize((sw, sh))
                    det_size = (sw, sh)

                eff_min = max(12.0, min_face_px * scale)
                _, faces = detector.detect(small)

                dets: list[dict[str, Any]] = []
                if faces is not None and len(faces) > 0:
                    for row in faces:
                        rx, ry, rw, rh = float(row[0]), float(row[1]), float(row[2]), float(row[3])
                        conf = float(row[14])
                        if rw < eff_min or rh < eff_min or conf < score_thresh:
                            continue
                        # Clamp normalized box inside [0..1]
                        nx = max(0.0, min(1.0, rx / sw))
                        ny = max(0.0, min(1.0, ry / sh))
                        nw = max(0.01, min(1.0 - nx, rw / sw))
                        nh = max(0.01, min(1.0 - ny, rh / sh))

                        # YuNet landmarks: right_eye (4,5), left_eye (6,7), nose (8,9), mouth (10..13)
                        re_x, re_y = float(row[4]), float(row[5])
                        le_x, le_y = float(row[6]), float(row[7])
                        eyes_inside = (
                            rx <= re_x <= rx + rw and ry <= re_y <= ry + rh * 0.7
                            and rx <= le_x <= rx + rw and ry <= le_y <= ry + rh * 0.7
                            and abs(le_x - re_x) >= rw * 0.14
                        )
                        area_ratio = round(nw * nh, 4)
                        dets.append({
                            "x": round(nx, 4),
                            "y": round(ny, 4),
                            "w": round(nw, 4),
                            "h": round(nh, 4),
                            "confidence": round(max(0.0, min(1.0, conf)), 3),
                            "eyes_visible": bool(eyes_inside),
                            "area_ratio": area_ratio,
                            "closeup": area_ratio >= 0.065,
                        })

                dets.sort(key=lambda d: d["confidence"], reverse=True)
                if not multi_face and len(dets) > 1:
                    dets = dets[:1]

                total_detections += len(dets)

                # Multi-subject tracking association across frames
                assigned_ids: set[int] = set()
                sample_faces = []
                for det in dets:
                    dbox = (det["x"], det["y"], det["w"], det["h"])
                    dcx, dcy = det["x"] + det["w"] * 0.5, det["y"] + det["h"] * 0.5
                    best_tid = None
                    best_score = 0.0

                    if subject_tracking_enabled:
                        for tid, tr in active_tracks.items():
                            if tid in assigned_ids or (t - tr["last_t"]) > track_timeout:
                                continue
                            tbox = (tr["last_box"]["x"], tr["last_box"]["y"], tr["last_box"]["w"], tr["last_box"]["h"])
                            iou_val = _iou(dbox, tbox)
                            tcx = tbox[0] + tbox[2] * 0.5
                            tcy = tbox[1] + tbox[3] * 0.5
                            dist = float(np.hypot(dcx - tcx, dcy - tcy))
                            sim = iou_val * 0.65 + max(0.0, 1.0 - dist * 2.2) * 0.35
                            if sim > 0.28 and sim > best_score:
                                best_score = sim
                                best_tid = tid

                    if best_tid is None:
                        tid = next_track_id
                        next_track_id += 1
                        tr = {
                            "subject_id": tid,
                            "label": f"Subject {tid}",
                            "first_seen": t,
                            "last_t": t,
                            "frames_seen": 0,
                            "conf_sum": 0.0,
                            "area_sum": 0.0,
                            "eyes_visible_frames": 0,
                            "closeup_frames": 0,
                            "obstruction_events": 0,
                            "entries": 1,
                            "exits": 0,
                            "box_x_sum": 0.0,
                            "box_y_sum": 0.0,
                            "box_w_sum": 0.0,
                            "box_h_sum": 0.0,
                            "last_box": det,
                        }
                        all_tracks[tid] = tr
                        active_tracks[tid] = tr
                    else:
                        tid = best_tid
                        tr = active_tracks[tid]
                        gap = t - tr["last_t"]
                        if gap > max(1.6, sample_interval * 1.8):
                            tr["obstruction_events"] += 1
                        tr["last_t"] = t
                        tr["last_box"] = det

                    assigned_ids.add(tid)
                    tr["frames_seen"] += 1
                    tr["conf_sum"] += det["confidence"]
                    tr["area_sum"] += det["area_ratio"]
                    if det["eyes_visible"]:
                        tr["eyes_visible_frames"] += 1
                    if det["closeup"]:
                        tr["closeup_frames"] += 1
                    tr["box_x_sum"] += det["x"]
                    tr["box_y_sum"] += det["y"]
                    tr["box_w_sum"] += det["w"]
                    tr["box_h_sum"] += det["h"]

                    sample_faces.append({
                        "subject_id": tid,
                        "x": det["x"],
                        "y": det["y"],
                        "w": det["w"],
                        "h": det["h"],
                        "confidence": det["confidence"],
                        "closeup": det["closeup"],
                        "eyes_visible": det["eyes_visible"],
                    })

                for tid in list(active_tracks.keys()):
                    if tid not in assigned_ids and (t - active_tracks[tid]["last_t"]) > track_timeout:
                        active_tracks[tid]["exits"] += 1
                        del active_tracks[tid]

                frame_samples.append({
                    "t": t,
                    "face_count": len(sample_faces),
                    "faces": sample_faces,
                })

                if progress_cb:
                    if targeted_times is not None:
                        pct = min(0.92, (t_ptr / max(1, len(targeted_times))) * 0.92)
                        progress_cb(pct, f"Face tracking Peak Reels ({t_ptr}/{len(targeted_times)} samples · {t:.1f}s)")
                    elif total_frames > 0:
                        progress_cb(min(0.92, frame_idx / total_frames * 0.92), f"Detecting & tracking faces ({t:.1f}s / {duration:.1f}s)")
            frame_idx += 1
    finally:
        cap.release()

    total_samples = max(1, len(frame_samples))
    subjects = []
    for tid, tr in sorted(all_tracks.items(), key=lambda kv: kv[1]["frames_seen"], reverse=True):
        n = max(1, tr["frames_seen"])
        avg_box = {
            "x": round(tr["box_x_sum"] / n, 4),
            "y": round(tr["box_y_sum"] / n, 4),
            "w": round(tr["box_w_sum"] / n, 4),
            "h": round(tr["box_h_sum"] / n, 4),
        }
        subjects.append({
            "subject_id": tid,
            "label": tr["label"],
            "first_seen": tr["first_seen"],
            "last_seen": tr["last_t"],
            "frames_seen": n,
            "visibility_ratio": round(min(1.0, n / total_samples), 3),
            "avg_confidence": round(tr["conf_sum"] / n, 3),
            "avg_area_ratio": round(tr["area_sum"] / n, 4),
            "eyes_visibility_ratio": round(tr["eyes_visible_frames"] / n, 3),
            "closeup_ratio": round(tr["closeup_frames"] / n, 3),
            "obstruction_events": tr["obstruction_events"],
            "entries": tr["entries"],
            "exits": tr["exits"],
            "avg_box": avg_box,
            "source": "local_yunet_dnn",
        })

    primary_subject = None
    if subjects:
        if preferred_primary is not None:
            primary_subject = next((s for s in subjects if s["subject_id"] == int(preferred_primary)), None)
        if primary_subject is None:
            primary_subject = max(
                subjects,
                key=lambda s: s["visibility_ratio"] * (0.5 + s["avg_area_ratio"] * 4.0) * s["avg_confidence"],
            )

    primary_box = primary_subject["avg_box"] if primary_subject else None
    reframing_suggestions = {
        aspect: compute_smart_reframe(src_w, src_h, aspect, primary_box)
        for aspect in ("9:16", "1:1", "16:9")
    }

    shot_updates: dict[str, dict[str, Any]] = {}
    for sh in shots:
        s0, s1 = float(sh["start"]), float(sh["end"])
        in_s = [fs for fs in frame_samples if s0 <= fs["t"] <= s1]
        if not in_s:
            shot_updates[sh["id"]] = {
                "face_info": {
                    "analyzed": True,
                    "face_detected": False,
                    "face_count": 0,
                    "primary_subject_id": None,
                    "visibility_ratio": 0.0,
                    "avg_confidence": 0.0,
                    "eyes_visibility_ratio": 0.0,
                    "closeup": False,
                    "obstruction_suspected": False,
                    "avg_box": None,
                    "entries": 0,
                    "exits": 0,
                    "source": "local_yunet_dnn",
                },
                "detected_subjects": [],
                "reframing": {
                    aspect: compute_smart_reframe(src_w, src_h, aspect, None)
                    for aspect in ("9:16", "1:1", "16:9")
                },
            }
            continue

        faces_flat = [f for fs in in_s for f in fs["faces"]]
        frames_with_face = sum(1 for fs in in_s if fs["face_count"] > 0)
        vis_ratio = round(frames_with_face / len(in_s), 3)
        shot_subj_ids = sorted({f["subject_id"] for f in faces_flat})

        shot_primary_id = None
        if preferred_primary in shot_subj_ids:
            shot_primary_id = int(preferred_primary)
        elif primary_subject and primary_subject["subject_id"] in shot_subj_ids:
            shot_primary_id = primary_subject["subject_id"]
        elif shot_subj_ids:
            # Prefer largest foreground speaker (area * confidence summed across frames in shot)
            shot_primary_id = max(
                shot_subj_ids,
                key=lambda sid: sum(f["w"] * f["h"] * f["confidence"] for f in faces_flat if f["subject_id"] == sid),
            )

        pf = [f for f in faces_flat if f["subject_id"] == shot_primary_id] if shot_primary_id is not None else faces_flat
        avg_box = None
        if pf:
            avg_box = {
                "x": round(float(np.mean([f["x"] for f in pf])), 4),
                "y": round(float(np.mean([f["y"] for f in pf])), 4),
                "w": round(float(np.mean([f["w"] for f in pf])), 4),
                "h": round(float(np.mean([f["h"] for f in pf])), 4),
            }

        entries = 0
        exits = 0
        prev_present = False
        for fs in in_s:
            pres = fs["face_count"] > 0
            if pres and not prev_present:
                entries += 1
            elif not pres and prev_present:
                exits += 1
            prev_present = pres

        eyes_ok = sum(1 for f in pf if f.get("eyes_visible")) / max(1, len(pf)) if pf else 0.0
        obstruction = bool(pf and (eyes_ok < 0.25 or (entries > 1 and vis_ratio < 0.75)))
        closeup = bool(pf and any(f.get("closeup") for f in pf))
        avg_conf = round(float(np.mean([f["confidence"] for f in pf])), 3) if pf else 0.0

        shot_updates[sh["id"]] = {
            "face_info": {
                "analyzed": True,
                "face_detected": len(faces_flat) > 0,
                "face_count": len(shot_subj_ids),
                "primary_subject_id": shot_primary_id,
                "visibility_ratio": vis_ratio,
                "avg_confidence": avg_conf,
                "eyes_visibility_ratio": round(eyes_ok, 3),
                "closeup": closeup,
                "obstruction_suspected": obstruction,
                "avg_box": avg_box,
                "entries": entries,
                "exits": exits,
                "source": "local_yunet_dnn",
            },
            "detected_subjects": [f"Subject {sid}" for sid in shot_subj_ids],
            "reframing": {
                aspect: compute_smart_reframe(src_w, src_h, aspect, avg_box)
                for aspect in ("9:16", "1:1", "16:9")
            },
        }

    if len(frame_samples) > 180:
        idx_step = len(frame_samples) / 180.0
        compact_samples = [frame_samples[int(i * idx_step)] for i in range(180)]
    else:
        compact_samples = frame_samples

    if progress_cb:
        progress_cb(1.0, f"Face tracking complete: {len(subjects)} subject(s) tracked")

    return {
        "status": "done",
        "detected_faces_total": total_detections,
        "subjects": subjects,
        "primary_subject_id": primary_subject["subject_id"] if primary_subject else None,
        "frame_samples": compact_samples,
        "reframing_suggestions": reframing_suggestions,
        "shot_updates": shot_updates,
        "model": "OpenCV YuNet Neural Face & Landmark Detector (Local ONNX)",
        "analyzed_at": time.time(),
    }
