"""AgentVid Virality Scoring Engine: 15-dimension explicit weighted model + dashboard analytics."""
from __future__ import annotations

import math
import time
from typing import Any

from . import ai, projects

# Explicit, auditable weights summing to 1.00 across all 15 required dimensions
DIMENSION_WEIGHTS: dict[str, float] = {
    "opening_hook": 0.11,
    "emotional_impact": 0.09,
    "visual_engagement": 0.09,
    "human_presence": 0.07,
    "facial_expression": 0.07,
    "movement_action": 0.07,
    "information_value": 0.06,
    "storytelling": 0.07,
    "audio_clarity": 0.07,
    "speech_clarity": 0.06,
    "subject_visibility": 0.06,
    "composition": 0.05,
    "standalone_potential": 0.06,
    "pacing": 0.04,
    "ending_strength": 0.03,
}

DIMENSION_LABELS: dict[str, str] = {
    "opening_hook": "Opening Hook Strength",
    "emotional_impact": "Emotional Impact",
    "visual_engagement": "Visual Engagement",
    "human_presence": "Human Presence",
    "facial_expression": "Facial Expression Visibility",
    "movement_action": "Movement & Action",
    "information_value": "Information Value",
    "storytelling": "Storytelling Potential",
    "audio_clarity": "Audio Clarity",
    "speech_clarity": "Speech Clarity",
    "subject_visibility": "Subject Visibility",
    "composition": "Composition",
    "standalone_potential": "Standalone Clip Potential",
    "pacing": "Pacing",
    "ending_strength": "Ending Strength",
}


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> int:
    return int(round(max(lo, min(hi, v))))


def score_tier(score: int) -> str:
    if score >= 90:
        return "High Viral Potential"
    if score >= 75:
        return "Strong Potential"
    if score >= 60:
        return "Moderate Potential"
    if score >= 40:
        return "Needs Improvement"
    return "Low Predicted Potential"


def score_shot(shot: dict[str, Any], total_shots: int, video_duration: float) -> dict[str, Any]:
    """Deterministically compute all 15 virality dimensions from measured audiovisual + face metrics."""
    m = shot.get("metrics") or {}
    f = shot.get("face_info") or {}
    dur = max(0.2, float(shot.get("duration") or 1.0))
    idx = int(shot.get("number") or 1)
    transcript = (shot.get("transcript") or "").strip()
    word_count = len(transcript.split()) if transcript else 0
    wps = word_count / dur if word_count > 0 else 0.0

    motion = float(m.get("motion", 0.0))
    peak_motion = float(m.get("peak_motion", motion))
    contrast = float(m.get("contrast", 35.0))
    saturation = float(m.get("saturation", 30.0))
    sharpness = float(m.get("sharpness", 50.0))
    composition = float(m.get("composition", 55.0))
    audio_energy = float(m.get("audio_energy", 0.0))
    audio_peak = float(m.get("audio_peak", 0.0))
    audio_clarity = float(m.get("audio_clarity", 0.0))
    silence_ratio = float(m.get("silence_ratio", 0.0))
    speech_ratio = float(m.get("speech_ratio", 0.0))

    face_analyzed = bool(f.get("analyzed"))
    face_detected = bool(f.get("face_detected"))
    face_vis = float(f.get("visibility_ratio", 0.0))
    face_conf = float(f.get("avg_confidence", 0.0))
    eyes_vis = float(f.get("eyes_visibility_ratio", 0.0))
    closeup = bool(f.get("closeup"))
    obstruction = bool(f.get("obstruction_suspected"))

    # 1. Opening hook strength: strong motion/audio energy + immediate speech/face presence + ideal pace
    early_bonus = 8.0 if idx <= 2 else 0.0
    hook_energy = min(45.0, peak_motion * 0.45 + audio_peak * 0.35)
    hook_presence = 22.0 if face_detected else 8.0
    hook_dead_air_penalty = silence_ratio * 28.0
    opening_hook = _clamp(28.0 + hook_energy + hook_presence + early_bonus - hook_dead_air_penalty)

    # 2. Emotional impact: close-ups, audio dynamics, vocal energy, visual contrast
    emo = 30.0 + (22.0 if closeup else 10.0 if face_detected else 0.0) + audio_peak * 0.28 + min(22.0, contrast * 0.35) - silence_ratio * 20.0
    emotional_impact = _clamp(emo)

    # 3. Visual engagement: sharpness, color richness, contrast, motion balance
    vis_eng = sharpness * 0.34 + min(100.0, saturation * 1.45) * 0.24 + min(100.0, contrast * 1.35) * 0.22 + min(100.0, motion * 1.3) * 0.20
    visual_engagement = _clamp(vis_eng)

    # 4. Human presence
    if face_detected:
        human_presence = _clamp(52.0 + face_vis * 34.0 + (10.0 if closeup else 0.0) + min(8.0, (f.get("face_count", 1) - 1) * 4.0))
    elif face_analyzed:
        human_presence = _clamp(24.0 + speech_ratio * 26.0)
    else:
        human_presence = _clamp(35.0 + speech_ratio * 25.0)

    # 5. Facial expression visibility
    if face_detected:
        expr = 45.0 + face_conf * 28.0 + eyes_vis * 24.0 + (8.0 if closeup else 0.0) - (16.0 if obstruction else 0.0)
        facial_expression = _clamp(expr)
    else:
        facial_expression = 22 if face_analyzed else 35

    # 6. Movement & action
    movement_action = _clamp(22.0 + motion * 0.72 + peak_motion * 0.26)

    # 7. Information value (higher when dense speech/transcript or structured visual detail)
    if word_count > 0:
        info_val = 42.0 + min(42.0, wps * 15.0) + sharpness * 0.14
    else:
        info_val = 30.0 + speech_ratio * 38.0 + sharpness * 0.20
    information_value = _clamp(info_val)

    # 8. Storytelling potential (sweet-spot duration 4–22s + continuous speech/visual progression)
    dur_story = 1.0 if 4.5 <= dur <= 22.0 else max(0.35, 1.0 - abs(dur - 12.0) / 30.0)
    storytelling = _clamp(28.0 + dur_story * 32.0 + speech_ratio * 22.0 + (12.0 if face_detected else 4.0) - silence_ratio * 15.0)

    # 9. Audio clarity
    audio_clarity_score = _clamp(audio_clarity if audio_clarity > 0 else 25.0)

    # 10. Speech clarity
    if speech_ratio > 0.05:
        speech_clarity = _clamp(audio_clarity_score * 0.65 + speech_ratio * 35.0 - silence_ratio * 12.0)
    else:
        speech_clarity = _clamp(20.0 + audio_clarity_score * 0.25)

    # 11. Subject visibility
    if face_detected:
        subject_visibility = _clamp(42.0 + face_vis * 38.0 + face_conf * 18.0 - (14.0 if obstruction else 0.0))
    else:
        subject_visibility = _clamp(composition * 0.55 + sharpness * 0.35)

    # 12. Composition
    comp_score = _clamp(composition)

    # 13. Standalone clip potential (self-contained length 4–35s, low dead air, strong visual+audio)
    standalone_dur = 1.0 if 4.0 <= dur <= 35.0 else max(0.3, 1.0 - abs(dur - 15.0) / 40.0)
    standalone_potential = _clamp(24.0 + standalone_dur * 30.0 + (opening_hook * 0.24) + (audio_clarity_score * 0.16) - silence_ratio * 20.0)

    # 14. Pacing (sweet spot: active speech/motion with minimal silence)
    pace_ideal = 1.0 - min(0.8, silence_ratio * 1.1)
    pacing = _clamp(30.0 + pace_ideal * 36.0 + min(26.0, motion * 0.45 + speech_ratio * 20.0))

    # 15. Ending strength (clean resolution / energy sustain)
    end_bonus = 6.0 if idx == total_shots else 0.0
    ending_strength = _clamp(34.0 + (1.0 - silence_ratio) * 28.0 + audio_energy * 0.20 + (10.0 if face_detected else 0.0) + end_bonus)

    dims = {
        "opening_hook": opening_hook,
        "emotional_impact": emotional_impact,
        "visual_engagement": visual_engagement,
        "human_presence": human_presence,
        "facial_expression": facial_expression,
        "movement_action": movement_action,
        "information_value": information_value,
        "storytelling": storytelling,
        "audio_clarity": audio_clarity_score,
        "speech_clarity": speech_clarity,
        "subject_visibility": subject_visibility,
        "composition": comp_score,
        "standalone_potential": standalone_potential,
        "pacing": pacing,
        "ending_strength": ending_strength,
    }

    local_overall = _clamp(sum(dims[k] * w for k, w in DIMENSION_WEIGHTS.items()))
    ai_peak_score = int(shot.get("ai_score") or 0)
    is_ai_reel = shot.get("cut_kind") == "ai_peak_reel" and ai_peak_score > 0
    overall = _clamp(ai_peak_score * 0.55 + local_overall * 0.45) if is_ai_reel else local_overall

    # Confidence reflects how many real signals were available
    signals_present = 1  # visual always present
    if face_analyzed:
        signals_present += 1
    if audio_clarity > 0:
        signals_present += 1
    if word_count > 0:
        signals_present += 1
    if is_ai_reel:
        signals_present += 1
    confidence = "High" if signals_present >= 4 else "Medium-High" if signals_present == 3 else "Medium" if signals_present == 2 else "Low"

    # Build grounded, specific recommendation based on actual weakest/strongest dimensions
    recs: list[str] = []
    ai_reason = str(shot.get("ai_reason") or "").strip()
    if ai_reason:
        recs.append(ai_reason)
    if overall >= 80:
        recs.append("Strong candidate for opening clip or standalone short.")
    elif overall >= 65:
        recs.append("Solid retention signals; small pacing tweaks can lift engagement.")
    else:
        recs.append("Consider tightening this shot or pairing it as supporting B-roll.")

    if silence_ratio >= 0.35:
        trim_s = round(min(2.0, dur * silence_ratio * 0.6), 1)
        recs.append(f"Trim ~{trim_s}s of dead air ({int(silence_ratio * 100)}% silent) to sharpen pacing.")
    if face_detected and not closeup and dims["facial_expression"] < 72:
        recs.append("Apply a subtle 1.15x-1.25x zoom toward the primary subject to boost facial visibility.")
    if not face_detected and face_analyzed:
        recs.append("No face detected; consider adding kinetic captions or using as B-roll over voiceover.")
    if dims["opening_hook"] >= 80 and idx > 1:
        recs.append("High hook energy—test placing this shot first as a cold open.")
    if audio_clarity_score < 50:
        recs.append("Enable audio normalization during export to improve vocal presence.")

    # Actionable structured suggestions per automation switch
    zoom_sug = None
    if face_detected and not closeup and f.get("avg_box"):
        box = f["avg_box"]
        zoom_sug = {
            "recommended_zoom": 1.22,
            "pan_x": round(box["x"] + box["w"] * 0.5, 3),
            "pan_y": round(box["y"] + box["h"] * 0.45, 3),
            "reason": "Punch in slightly on detected face to increase emotional connection.",
        }
    elif motion < 10 and dur >= 4.0:
        zoom_sug = {
            "recommended_zoom": 1.12,
            "pan_x": 0.5,
            "pan_y": 0.5,
            "reason": "Static framing detected; subtle scale-in adds visual momentum.",
        }

    trans_sug = {
        "recommended_transition": "dissolve" if shot.get("scene_category") in ("Cinematic B-Roll", "Low-Light / Moody") else "fade" if idx == 1 else "none",
        "duration": 0.35,
        "reason": "Matches scene energy and maintains smooth cut rhythm.",
    }

    broll_sug = None
    if speech_ratio >= 0.55 and motion < 12 and dur >= 6.0:
        broll_sug = {
            "suggested": True,
            "at_offset": round(dur * 0.45, 1),
            "reason": "Long steady talking segment—insert 2-3s of visual B-roll mid-shot to reset viewer attention.",
        }

    return {
        "virality": {
            "score": overall,
            "tier": score_tier(overall),
            "confidence": confidence,
            "dimensions": dims,
            "dimension_labels": DIMENSION_LABELS,
            "recommendation": " ".join(recs),
            "source": "ai_peak_plus_local_model" if is_ai_reel else "local_weighted_model",
            "disclaimer": "Analytical prediction based on measurable audiovisual features; does not guarantee views.",
        },
        "suggestions": {
            "zoom": zoom_sug,
            "transition": trans_sug,
            "broll": broll_sug,
            "editing": recs,
        },
    }


def score_project_shots(
    shots: list[dict[str, Any]],
    video_duration: float,
    allow_ai_enhance: bool = False,
    switches: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Score every shot in a project and compute dashboard aggregates."""
    sw = switches or {}
    total = len(shots)
    updated_shots = []
    for sh in shots:
        res = score_shot(sh, total, video_duration)
        nxt = dict(sh)
        nxt["virality"] = res["virality"]
        sug = dict(nxt.get("suggestions") or {})
        if sw.get("zoom_suggestions", True):
            sug["zoom"] = res["suggestions"]["zoom"]
        if sw.get("transition_suggestions", True):
            sug["transition"] = res["suggestions"]["transition"]
        if sw.get("broll_suggestions", True):
            sug["broll"] = res["suggestions"]["broll"]
        if sw.get("editing_recommendations", True):
            sug["editing"] = res["suggestions"]["editing"]
        nxt["suggestions"] = sug
        updated_shots.append(nxt)

    ai_enhanced = False
    if allow_ai_enhance and ai.ready() and updated_shots:
        settings = projects.get_settings()
        if settings.get("privacy", {}).get("allow_cloud_ai"):
            try:
                _try_ai_refine_recommendations(updated_shots)
                ai_enhanced = True
            except Exception:
                ai_enhanced = False

    if not updated_shots:
        summary = {
            "status": "done",
            "overall_score": 0,
            "average_shot_score": 0,
            "highest_shot_id": None,
            "lowest_shot_id": None,
            "best_hook_shot_id": None,
            "best_emotional_shot_id": None,
            "best_standalone_shot_id": None,
            "recommended_sequence": [],
            "ai_enhanced": ai_enhanced,
            "disclaimer": "Virality scores are analytical predictions based on audiovisual signals and do not guarantee views or engagement.",
            "computed_at": time.time(),
        }
        return {"shots": updated_shots, "virality": summary}

    scores = [s["virality"]["score"] for s in updated_shots]
    avg_score = int(round(sum(scores) / len(scores)))
    top_scores = sorted(scores, reverse=True)[:max(1, min(3, len(scores)))]
    overall = int(round(avg_score * 0.55 + (sum(top_scores) / len(top_scores)) * 0.45))

    highest = max(updated_shots, key=lambda s: s["virality"]["score"])
    lowest = min(updated_shots, key=lambda s: s["virality"]["score"])
    best_hook = max(updated_shots, key=lambda s: s["virality"]["dimensions"].get("opening_hook", 0))
    best_emo = max(updated_shots, key=lambda s: s["virality"]["dimensions"].get("emotional_impact", 0))
    best_stand = max(updated_shots, key=lambda s: s["virality"]["dimensions"].get("standalone_potential", 0))

    # Recommended clip sequence: best hook first, then remaining top shots in chronological order
    ranked = sorted(updated_shots, key=lambda s: s["virality"]["score"], reverse=True)
    top_ids = {s["id"] for s in ranked[:max(1, min(5, len(ranked)))]}
    seq = [best_hook["id"]] + [
        s["id"] for s in updated_shots
        if s["id"] in top_ids and s["id"] != best_hook["id"]
    ]

    summary = {
        "status": "done",
        "overall_score": overall,
        "overall_tier": score_tier(overall),
        "average_shot_score": avg_score,
        "highest_shot_id": highest["id"],
        "lowest_shot_id": lowest["id"],
        "best_hook_shot_id": best_hook["id"],
        "best_emotional_shot_id": best_emo["id"],
        "best_standalone_shot_id": best_stand["id"],
        "recommended_sequence": seq,
        "ai_enhanced": ai_enhanced,
        "disclaimer": "Virality scores are analytical predictions based on audiovisual signals and do not guarantee views or engagement.",
        "computed_at": time.time(),
    }
    return {"shots": updated_shots, "virality": summary}


def _try_ai_refine_recommendations(shots: list[dict[str, Any]]) -> None:
    """Optionally enrich shot editing notes via configured AI provider using ONLY measured shot summaries."""
    compact = [
        {
            "number": s["number"],
            "duration": s["duration"],
            "category": s["scene_category"],
            "score": s["virality"]["score"],
            "hook": s["virality"]["dimensions"].get("opening_hook"),
            "face": s["face_info"].get("face_detected"),
            "silence_pct": int(s["metrics"].get("silence_ratio", 0) * 100),
            "transcript": (s.get("transcript") or "")[:160],
        }
        for s in shots[:16]
    ]
    schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "number": {"type": "INTEGER"},
                "recommendation": {"type": "STRING"},
            },
            "required": ["number", "recommendation"],
        },
    }
    prompt = (
        "You are an expert video editor. Given ONLY these measured shot summaries (do not invent transcript or visuals), "
        "write one concise, actionable editing recommendation per shot number.\n"
        f"Shots JSON: {compact}"
    )
    out, _, _ = ai.call(ai.models()[0], prompt, schema, timeout=30)
    if isinstance(out, list):
        by_num = {int(x["number"]): str(x["recommendation"])[:240] for x in out if isinstance(x, dict) and "number" in x and "recommendation" in x}
        for s in shots:
            if s["number"] in by_num and by_num[s["number"]]:
                s["virality"]["recommendation"] = by_num[s["number"]]
                s["virality"]["source"] = "local_weighted_model+ai_provider"
