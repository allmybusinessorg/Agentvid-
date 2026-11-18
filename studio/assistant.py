"""AgentVid AI Content Intelligence Assistant.

Grounded strictly in real analyzed project shots, face tracking, virality dimensions, and verified transcripts.
Never fabricates transcript text or visual observations. Clearly distinguishes local analytical responses from
optional external AI provider enhancements.
"""
from __future__ import annotations

import time
from typing import Any

from . import ai, projects


def _build_grounded_context(proj: dict[str, Any]) -> dict[str, Any]:
    shots = proj.get("shots") or []
    vir = proj.get("virality") or {}
    faces = proj.get("face_tracking") or {}
    analysis = proj.get("analysis") or {}
    return {
        "project_name": proj.get("name"),
        "shot_count": len(shots),
        "overall_virality": vir.get("overall_score", 0),
        "average_shot_score": vir.get("average_shot_score", 0),
        "transcript_source": analysis.get("transcript_source", "none"),
        "subjects_tracked": len(faces.get("subjects") or []),
        "shots": [
            {
                "id": s["id"],
                "number": s["number"],
                "start": s["start"],
                "end": s["end"],
                "duration": s["duration"],
                "category": s.get("scene_category"),
                "score": (s.get("virality") or {}).get("score", 0),
                "hook": ((s.get("virality") or {}).get("dimensions") or {}).get("opening_hook", 0),
                "emotional": ((s.get("virality") or {}).get("dimensions") or {}).get("emotional_impact", 0),
                "standalone": ((s.get("virality") or {}).get("dimensions") or {}).get("standalone_potential", 0),
                "face_detected": (s.get("face_info") or {}).get("face_detected", False),
                "closeup": (s.get("face_info") or {}).get("closeup", False),
                "silence_pct": int((s.get("metrics") or {}).get("silence_ratio", 0) * 100),
                "speech_pct": int((s.get("metrics") or {}).get("speech_ratio", 0) * 100),
                "motion": (s.get("metrics") or {}).get("motion", 0),
                "transcript": (s.get("transcript") or "")[:180],
                "recommendation": (s.get("virality") or {}).get("recommendation", ""),
            }
            for s in shots
        ],
    }


def _local_intelligence(proj: dict[str, Any], prompt: str, action: str = "chat") -> dict[str, Any]:
    ctx = _build_grounded_context(proj)
    shots = ctx["shots"]
    if not shots:
        return {
            "mode": "local_analytics",
            "external_ai_available": ai.ready(),
            "reply": (
                "No analyzed shots are available yet for this project. Import a video and run scene/shot analysis "
                "(or enable AUTO mode) so AgentVid can inspect real shots, face presence, audio dynamics, and virality scores."
            ),
            "recommended_shots": [],
            "actions": [],
            "ts": time.time(),
        }

    ranked = sorted(shots, key=lambda s: s["score"], reverse=True)
    top3 = ranked[:3]
    best_hook = max(shots, key=lambda s: s["hook"])
    weak_shots = [s for s in shots if s["silence_pct"] >= 45 or s["score"] < 50]
    broll_targets = [s for s in shots if s["speech_pct"] >= 50 and s["motion"] < 14 and s["duration"] >= 5.0]
    low = prompt.lower()

    if action == "strongest_moments" or "strongest" in low or "best" in low or "short" in low or "clip" in low:
        lines = [
            f"Based on measured audiovisual analysis across {len(shots)} shots (overall score {ctx['overall_virality']}/100):",
            "",
            "**Top Recommended Shots:**",
        ]
        for s in top3:
            face_note = "face visible" + (" (close-up)" if s["closeup"] else "") if s["face_detected"] else "no face detected"
            lines.append(
                f"- **Shot {s['number']:02d}** ({s['start']:.1f}s–{s['end']:.1f}s, {s['duration']:.1f}s) — "
                f"Virality **{s['score']}/100**, Hook **{s['hook']}**, {face_note}, {s['category']}. {s['recommendation']}"
            )
        lines.append(
            f"\n**Recommended Short-Form Sequence:** Open with **Shot {best_hook['number']:02d}** (strongest opening hook: {best_hook['hook']}/100), "
            f"then follow with " + ", ".join(f"Shot {s['number']:02d}" for s in top3 if s["id"] != best_hook["id"]) + "."
        )
        reply = "\n".join(lines)

    elif action == "improve_hooks" or "hook" in low:
        first = shots[0]
        reply = (
            f"**Opening Hook Audit:**\n"
            f"- Current opening (Shot {first['number']:02d}): Hook score **{first['hook']}/100**, "
            f"silence {first['silence_pct']}%, motion {first['motion']:.0f}/100.\n"
            f"- Strongest hook in project: **Shot {best_hook['number']:02d}** (Hook **{best_hook['hook']}/100**, "
            f"{best_hook['start']:.1f}s–{best_hook['end']:.1f}s).\n"
            f"- **Actionable Tip:** "
            + (
                f"Move Shot {best_hook['number']:02d} to position 1 as a cold open, or trim the first 1.2s of dead air in Shot {first['number']:02d}."
                if best_hook["id"] != first["id"]
                else f"Shot 01 is already your strongest hook. Add a bold Liquid Glass or Kinetic title overlay in the first 2 seconds."
            )
        )

    elif action == "trim_unnecessary" or "cut" in low or "unnecessary" in low or "dead" in low or "pacing" in low:
        if weak_shots:
            items = "\n".join(
                f"- **Shot {s['number']:02d}** ({s['duration']:.1f}s): Score {s['score']}/100, {s['silence_pct']}% silent, motion {s['motion']:.0f}/100."
                for s in weak_shots[:6]
            )
            reply = (
                f"**Pacing & Unnecessary Footage Review:**\n"
                f"Found {len(weak_shots)} shot(s) that slow down retention:\n{items}\n\n"
                "Consider excluding these shots from the timeline or trimming their silent tails."
            )
        else:
            reply = (
                "All analyzed shots maintain steady energy with low dead air. "
                "You can tighten overall rhythm further by applying 1.05x–1.10x speed on lower-motion segments."
            )

    elif action == "titles_captions" or "title" in low or "caption" in low:
        has_tr = ctx["transcript_source"] not in ("none", "audio_energy_only", "model_not_downloaded", "no_audio")
        if has_tr:
            reply = (
                f"**Caption & Title Suggestions (Transcript Verified: {ctx['transcript_source']}):**\n"
                f"- Recommended caption style: **Liquid Glass** or **Modern Creator** with **Word-by-Word Reveal**.\n"
                f"- Highlight Shot {top3[0]['number']:02d} as the hero cover frame.\n"
                + ("- Configure an external AI provider in Settings → AI to generate creative platform-specific title variants from your transcript." if not ai.ready() else "")
            )
        else:
            reply = (
                "**Caption & Title Status:**\n"
                f"- Local transcript status: `{ctx['transcript_source']}` (no fabricated captions generated).\n"
                "- You can manually add or edit caption cues in **Captions & Motion**, or enable the local speech model / external AI provider in Settings.\n"
                f"- Visually, **Shot {top3[0]['number']:02d}** ({top3[0]['category']}, score {top3[0]['score']}/100) is the strongest thumbnail/title anchor."
            )

    elif action == "broll_style" or "b-roll" in low or "broll" in low or "style" in low or "platform" in low:
        broll_lines = (
            "\n".join(f"- **Shot {s['number']:02d}** ({s['duration']:.1f}s): high speech ({s['speech_pct']}%), low motion ({s['motion']:.0f}) — insert 2–3s B-roll cutaway." for s in broll_targets[:4])
            if broll_targets else "- Shot pacing already has strong visual movement; B-roll inserts are optional."
        )
        reply = (
            f"**Style, B-Roll & Platform Versions:**\n"
            f"- **TikTok / Reels / Shorts (9:16):** Export Top-Rated preset with Smart Face Reframing + Kinetic or Modern Creator captions.\n"
            f"- **YouTube Landscape (16:9):** Keep full timeline with Minimal Studio captions and 0.35s dissolve transitions.\n"
            f"- **Square Feed (1:1):** Apply face-centered smart reframing.\n\n"
            f"**B-Roll Cutaway Candidates:**\n{broll_lines}"
        )

    else:
        reply = (
            f"**AgentVid Studio Analysis for '{ctx['project_name']}':**\n"
            f"- **Overall Predicted Virality:** {ctx['overall_virality']}/100 across {len(shots)} shots.\n"
            f"- **Top Shot:** Shot {top3[0]['number']:02d} ({top3[0]['score']}/100 — {top3[0]['category']}).\n"
            f"- **Best Opening Hook:** Shot {best_hook['number']:02d} (Hook {best_hook['hook']}/100).\n"
            f"- **Subjects Tracked:** {ctx['subjects_tracked']} detected via local OpenCV tracking.\n"
            f"- **Footage to Tighten:** {len(weak_shots)} shot(s) flagged with high silence or lower engagement.\n\n"
            "Ask me to find strongest moments, improve your opening hook, suggest B-roll/styles, flag unnecessary footage, or generate platform versions."
        )

    return {
        "mode": "local_analytics",
        "external_ai_available": ai.ready(),
        "external_ai_enabled": bool(projects.get_settings().get("privacy", {}).get("allow_cloud_ai")),
        "reply": reply,
        "recommended_shots": [s["id"] for s in top3],
        "ts": time.time(),
    }


def ask_assistant(pid: str, prompt: str, action: str = "chat") -> dict[str, Any]:
    """Answer user's editing question using local analytics, enhanced by configured LLM only when explicitly allowed."""
    proj = projects.get_project(pid)
    settings = projects.get_settings()
    allow_cloud = bool(settings.get("privacy", {}).get("allow_cloud_ai"))

    if allow_cloud and ai.ready():
        ctx = _build_grounded_context(proj)
        schema = {
            "type": "OBJECT",
            "properties": {
                "reply": {"type": "STRING"},
                "recommended_shot_numbers": {"type": "ARRAY", "items": {"type": "INTEGER"}},
            },
            "required": ["reply"],
        }
        sys_prompt = (
            "You are AgentVid AI Studio Assistant (by Creative Creature). "
            "Answer the creator's question using ONLY the verified project metrics below. "
            "CRITICAL: Never invent transcript lines, visual objects, or people that are not in the data. "
            "If transcript is empty, explicitly state transcript is unavailable. Never guarantee viral views.\n\n"
            f"Project Data: {ctx}\n\n"
            f"Action: {action}\nUser request: {str(prompt or '')[:600]}"
        )
        try:
            res, _, _ = ai.call(ai.models()[0], sys_prompt, schema, timeout=45)
            if isinstance(res, dict) and res.get("reply"):
                nums = set(res.get("recommended_shot_numbers") or [])
                rec_ids = [s["id"] for s in (proj.get("shots") or []) if s["number"] in nums]
                return {
                    "mode": f"ai_provider:{ai.label()}",
                    "external_ai_available": True,
                    "external_ai_enabled": True,
                    "reply": str(res["reply"])[:2500],
                    "recommended_shots": rec_ids,
                    "ts": time.time(),
                }
        except Exception as e:
            local = _local_intelligence(proj, prompt, action)
            local["note"] = f"External AI provider ({ai.label()}) unavailable: {e}. Showing verified local studio analysis."
            return local

    return _local_intelligence(proj, prompt, action)
