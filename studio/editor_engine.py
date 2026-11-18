"""AgentVid Non-Destructive Timeline Editor, Motion Graphics & Caption Renderer, and Real FFmpeg Export Engine."""
from __future__ import annotations

import copy
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from . import caption_fx, config, fonts_manager, media, projects, render as legacy_render

# ------------------------------------------------------------------ Motion Graphics & Caption Presets
CAPTION_STYLES: dict[str, dict[str, Any]] = {
    "liquid_silver": {
        "id": "liquid_silver",
        "category": "Liquid Metal",
        "label": "Liquid Metal Silver",
        "font": "Archivo Black",
        "font_size": 78,
        "color": "#F8FAFF",
        "highlight_color": "#CBD5E1",
        "outline": 5,
        "shadow": 4,
        "bg": "none",
        "uppercase": True,
        "spacing": 2.2,
        "animated_gradient": True,
        "desc": "Mirror-mercury liquid silver reflections with moving specular sweep.",
    },
    "molten_gold": {
        "id": "molten_gold",
        "category": "Liquid Metal",
        "label": "Molten Liquid Gold",
        "font": "Archivo Black",
        "font_size": 78,
        "color": "#FEF08A",
        "highlight_color": "#FACC15",
        "outline": 5,
        "shadow": 4,
        "bg": "none",
        "uppercase": True,
        "spacing": 2.0,
        "animated_gradient": True,
        "desc": "24K liquid bullion reflection with warm animated light sheen.",
    },
    "glossy_pink": {
        "id": "glossy_pink",
        "category": "Liquid Metal",
        "label": "Glossy Pink Chrome",
        "font": "Archivo Black",
        "font_size": 76,
        "color": "#FBCFE8",
        "highlight_color": "#EC4899",
        "outline": 5,
        "shadow": 4,
        "bg": "none",
        "uppercase": True,
        "spacing": 1.8,
        "animated_gradient": True,
        "desc": "High-gloss rose-pink liquid chrome with sweeping specular gleam.",
    },
    "hyper_gradient": {
        "id": "hyper_gradient",
        "category": "Moving Gradients",
        "label": "Hyper Moving Gradient",
        "font": "Anton",
        "font_size": 84,
        "color": "#FFFFFF",
        "highlight_color": "#0066FF",
        "outline": 5,
        "shadow": 3,
        "bg": "none",
        "uppercase": True,
        "spacing": 1.6,
        "animated_gradient": True,
        "desc": "Continuously flowing high-energy multi-stop creator gradient.",
    },
    "cobalt_pulse": {
        "id": "cobalt_pulse",
        "category": "Moving Gradients",
        "label": "Cobalt Wave",
        "font": "Poppins ExtraBold",
        "font_size": 74,
        "color": "#FFFFFF",
        "highlight_color": "#0066FF",
        "outline": 5,
        "shadow": 3,
        "bg": "none",
        "uppercase": True,
        "spacing": 1.4,
        "animated_gradient": True,
        "desc": "Animated electric cobalt & ice-white metallic sheen (Creative Creature signature).",
    },
    "solar_plasma": {
        "id": "solar_plasma",
        "category": "Moving Gradients",
        "label": "Solar Plasma Flow",
        "font": "Anton",
        "font_size": 82,
        "color": "#FDE68A",
        "highlight_color": "#FB923C",
        "outline": 5,
        "shadow": 3,
        "bg": "none",
        "uppercase": True,
        "spacing": 1.6,
        "animated_gradient": True,
        "desc": "Animated molten amber, coral, and magenta plasma flow.",
    },
    "swiss_minimal": {
        "id": "swiss_minimal",
        "category": "Ultra-Minimal",
        "label": "Swiss Ultra-Minimal",
        "font": "Poppins ExtraBold",
        "font_size": 44,
        "color": "#F8FAFC",
        "highlight_color": "#0066FF",
        "outline": 1,
        "shadow": 2,
        "bg": "none",
        "uppercase": False,
        "spacing": 0.6,
        "desc": "Editorial gallery typography with razor-clean negative space.",
    },
    "whisper_mono": {
        "id": "whisper_mono",
        "category": "Ultra-Minimal",
        "label": "Whisper Mono",
        "font": "Poppins ExtraBold",
        "font_size": 40,
        "color": "#E2E8F0",
        "highlight_color": "#FFFFFF",
        "outline": 1,
        "shadow": 2,
        "bg": "subtle",
        "uppercase": True,
        "spacing": 3.4,
        "desc": "Ultra-minimal tracked documentary subtitles with subtle obsidian frost.",
    },
    "minimal": {
        "id": "minimal",
        "category": "Ultra-Minimal",
        "label": "Minimal Subtitles",
        "font": "Poppins ExtraBold",
        "font_size": 52,
        "color": "#F8FAFC",
        "highlight_color": "#38BDF8",
        "outline": 2,
        "shadow": 1,
        "bg": "subtle",
        "uppercase": False,
        "spacing": 0.5,
        "desc": "Clean, legible studio subtitles with subtle dark backdrop.",
    },
    "kinetic": {
        "id": "kinetic",
        "label": "Kinetic Typography",
        "font": "Anton",
        "font_size": 88,
        "color": "#FFFFFF",
        "highlight_color": "#F472B6",
        "outline": 5,
        "shadow": 3,
        "bg": "none",
        "uppercase": True,
        "spacing": 2.0,
        "desc": "High-impact oversized display type built for fast-paced edits.",
    },
    "word_by_word": {
        "id": "word_by_word",
        "label": "Word-by-Word Captions",
        "font": "Poppins ExtraBold",
        "font_size": 76,
        "color": "#E2E8F0",
        "highlight_color": "#38BDF8",
        "outline": 5,
        "shadow": 2,
        "bg": "none",
        "uppercase": True,
        "spacing": 1.0,
        "desc": "Single-word and tight-phrase synchronized speech emphasis.",
    },
    "highlighted": {
        "id": "highlighted",
        "label": "Highlighted Keywords",
        "font": "Poppins ExtraBold",
        "font_size": 68,
        "color": "#FFFFFF",
        "highlight_color": "#FACC15",
        "outline": 4,
        "shadow": 2,
        "bg": "pill",
        "uppercase": False,
        "spacing": 0.5,
        "desc": "Active keyword highlight pill for explainer and creator videos.",
    },
    "liquid_glass": {
        "id": "liquid_glass",
        "label": "Liquid Glass",
        "font": "Poppins ExtraBold",
        "font_size": 64,
        "color": "#F8FAFC",
        "highlight_color": "#7DD3FC",
        "outline": 2,
        "shadow": 2,
        "bg": "glass",
        "uppercase": False,
        "spacing": 1.2,
        "desc": "Translucent frosted glass capsule inspired by spatial UI aesthetics.",
    },
    "glossy_metal": {
        "id": "glossy_metal",
        "label": "Glossy Metal",
        "font": "Archivo Black",
        "font_size": 74,
        "color": "#E2E8F0",
        "highlight_color": "#CBD5E1",
        "outline": 4,
        "shadow": 4,
        "bg": "none",
        "uppercase": True,
        "spacing": 1.8,
        "desc": "Brushed metallic sheen with deep specular drop shadow.",
    },
    "chrome": {
        "id": "chrome",
        "label": "Chrome Typography",
        "font": "Archivo Black",
        "font_size": 78,
        "color": "#F1F5F9",
        "highlight_color": "#A5F3FC",
        "outline": 5,
        "shadow": 4,
        "bg": "none",
        "uppercase": True,
        "spacing": 2.4,
        "desc": "High-contrast mirror chrome lettering for futuristic visuals.",
    },
    "bold_editorial": {
        "id": "bold_editorial",
        "label": "Bold Editorial",
        "font": "Anton",
        "font_size": 82,
        "color": "#FFFFFF",
        "highlight_color": "#818CF8",
        "outline": 4,
        "shadow": 2,
        "bg": "solid",
        "uppercase": True,
        "spacing": 1.4,
        "desc": "Magazine-grade display typography with crisp contrast framing.",
    },
    "cinematic": {
        "id": "cinematic",
        "label": "Cinematic Captions",
        "font": "Poppins ExtraBold",
        "font_size": 48,
        "color": "#F1F5F9",
        "highlight_color": "#FDE68A",
        "outline": 2,
        "shadow": 3,
        "bg": "none",
        "uppercase": True,
        "spacing": 4.0,
        "desc": "Wide-tracked film subtitles with soft shadow depth.",
    },
    "modern_creator": {
        "id": "modern_creator",
        "label": "Modern Creator",
        "font": "Poppins ExtraBold",
        "font_size": 74,
        "color": "#FFFFFF",
        "highlight_color": "#34D399",
        "outline": 6,
        "shadow": 2,
        "bg": "none",
        "uppercase": True,
        "spacing": 0.8,
        "desc": "High-retention creator captions tuned for vertical social feeds.",
    },
    "apple_minimal": {
        "id": "apple_minimal",
        "label": "Minimal Studio",
        "font": "Poppins ExtraBold",
        "font_size": 56,
        "color": "#FAFAFA",
        "highlight_color": "#A78BFA",
        "outline": 1,
        "shadow": 2,
        "bg": "glass",
        "uppercase": False,
        "spacing": 0.4,
        "desc": "Refined ultra-clean typography with balanced negative space.",
    },
}

CAPTION_ANIMATIONS: dict[str, dict[str, str]] = {
    "pop_in": {"id": "pop_in", "label": "Pop-In"},
    "scale_up": {"id": "scale_up", "label": "Scale-Up"},
    "blur_reveal": {"id": "blur_reveal", "label": "Blur Reveal"},
    "word_reveal": {"id": "word_reveal", "label": "Word-by-Word Reveal"},
    "slide_in": {"id": "slide_in", "label": "Slide-In"},
    "bounce": {"id": "bounce", "label": "Bounce"},
    "tracking": {"id": "tracking", "label": "Tracking Animation"},
    "highlight": {"id": "highlight", "label": "Highlight Animation"},
    "motion_blur": {"id": "motion_blur", "label": "Motion Blur"},
    "smooth_exit": {"id": "smooth_exit", "label": "Smooth Exit"},
}

RESOLUTION_DIMS: dict[tuple[str, str], tuple[int, int]] = {
    ("720p", "16:9"): (1280, 720),
    ("1080p", "16:9"): (1920, 1080),
    ("4k", "16:9"): (3840, 2160),
    ("720p", "9:16"): (720, 1280),
    ("1080p", "9:16"): (1080, 1920),
    ("4k", "9:16"): (2160, 3840),
    ("720p", "1:1"): (720, 720),
    ("1080p", "1:1"): (1080, 1080),
    ("4k", "1:1"): (2160, 2160),
}

QUALITY_CRF = {"draft": 26, "standard": 21, "high": 18, "master": 15}
QUALITY_MBPS = {"draft": 2.5, "standard": 5.5, "high": 9.5, "master": 16.0}

# ------------------------------------------------------------------ Non-destructive Timeline Edits
def _renumber_shots(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for idx, sh in enumerate(shots):
        nxt = copy.deepcopy(sh)
        nxt["number"] = idx + 1
        nxt.setdefault("edit", {})["order"] = idx
        out.append(nxt)
    return out


def update_shot_edit(pid: str, shot_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    proj = projects.get_project(pid)
    found = None
    for sh in proj.get("shots") or []:
        if sh["id"] == shot_id:
            found = sh
            break
    if not found:
        raise FileNotFoundError("Shot not found.")

    edit = dict(found.get("edit") or {})
    if "included" in patch:
        edit["included"] = bool(patch["included"])
    if "speed" in patch:
        edit["speed"] = round(max(0.25, min(4.0, float(patch["speed"]))), 2)
    if "zoom" in patch:
        edit["zoom"] = round(max(1.0, min(2.5, float(patch["zoom"]))), 2)
    if "pan_x" in patch:
        edit["pan_x"] = round(max(0.0, min(1.0, float(patch["pan_x"]))), 4)
    if "pan_y" in patch:
        edit["pan_y"] = round(max(0.0, min(1.0, float(patch["pan_y"]))), 4)
    if "volume" in patch:
        edit["volume"] = round(max(0.0, min(2.0, float(patch["volume"]))), 2)
    if "muted" in patch:
        edit["muted"] = bool(patch["muted"])
    if patch.get("transition") in ("none", "fade", "dissolve", "wipeleft", "wiperight", "slideup", "zoomin"):
        edit["transition"] = patch["transition"]
    if "transition_duration" in patch:
        edit["transition_duration"] = round(max(0.1, min(1.5, float(patch["transition_duration"]))), 2)
    if patch.get("crop_mode") in ("auto", "center", "custom", "face"):
        edit["crop_mode"] = patch["crop_mode"]
    if "text_overlay" in patch:
        edit["text_overlay"] = str(patch["text_overlay"] or "")[:140]

    if "trim_start" in patch or "trim_end" in patch:
        ts = float(patch.get("trim_start", found.get("trim_start", found["start"])))
        te = float(patch.get("trim_end", found.get("trim_end", found["end"])))
        ts = max(float(found["start"]), min(ts, float(found["end"]) - 0.2))
        te = max(ts + 0.2, min(te, float(found["end"])))
        found["trim_start"] = round(ts, 2)
        found["trim_end"] = round(te, 2)
        found["duration"] = round(te - ts, 2)

    found["edit"] = edit
    projects.save_project(pid, proj)
    return proj


def split_shot(pid: str, shot_id: str, split_at: float) -> dict[str, Any]:
    proj = projects.get_project(pid)
    shots = list(proj.get("shots") or [])
    idx = next((i for i, s in enumerate(shots) if s["id"] == shot_id), None)
    if idx is None:
        raise FileNotFoundError("Shot not found.")
    sh = shots[idx]
    s0 = float(sh.get("trim_start", sh["start"]))
    s1 = float(sh.get("trim_end", sh["end"]))
    split_t = round(float(split_at), 2)
    if split_t <= s0 + 0.3 or split_t >= s1 - 0.3:
        raise ValueError(f"Split timestamp must be between {s0 + 0.3:.2f}s and {s1 - 0.3:.2f}s.")

    left = copy.deepcopy(sh)
    left["end"] = split_t
    left["trim_end"] = split_t
    left["duration"] = round(split_t - s0, 2)

    right = copy.deepcopy(sh)
    right["id"] = f"shot_{uuid.uuid4().hex[:8]}"
    right["start"] = split_t
    right["trim_start"] = split_t
    right["end"] = s1
    right["trim_end"] = s1
    right["duration"] = round(s1 - split_t, 2)
    right["cut_kind"] = "manual_split"

    # Generate thumbnail for new right half
    try:
        _, video_path = projects.get_active_media(proj)
        tname = f"{right['id']}.jpg"
        tpath = projects.project_dir(pid) / "thumbnails" / tname
        mid = split_t + (s1 - split_t) * 0.45
        media.run([
            "ffmpeg", "-y", "-v", "error", "-ss", f"{mid:.2f}", "-i", str(video_path),
            "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "4", str(tpath)
        ], timeout=45)
        if tpath.is_file():
            right["thumbnail_url"] = f"/api/v2/projects/{pid}/thumbnails/{tname}"
    except Exception:
        pass

    new_shots = shots[:idx] + [left, right] + shots[idx + 1:]
    proj["shots"] = _renumber_shots(new_shots)
    projects.save_project(pid, proj)
    projects.append_activity(pid, "editor", f"Split Shot {sh['number']:02d} at {split_t:.2f}s.")
    return projects.get_project(pid)


def merge_shots(pid: str, shot_id_a: str, shot_id_b: str) -> dict[str, Any]:
    proj = projects.get_project(pid)
    shots = list(proj.get("shots") or [])
    ia = next((i for i, s in enumerate(shots) if s["id"] == shot_id_a), None)
    ib = next((i for i, s in enumerate(shots) if s["id"] == shot_id_b), None)
    if ia is None or ib is None or ia == ib:
        raise ValueError("Select two distinct shots to merge.")
    first_i, second_i = min(ia, ib), max(ia, ib)
    a, b = shots[first_i], shots[second_i]
    merged = copy.deepcopy(a)
    merged["start"] = min(float(a["start"]), float(b["start"]))
    merged["end"] = max(float(a["end"]), float(b["end"]))
    merged["trim_start"] = min(float(a.get("trim_start", a["start"])), float(b.get("trim_start", b["start"])))
    merged["trim_end"] = max(float(a.get("trim_end", a["end"])), float(b.get("trim_end", b["end"])))
    merged["duration"] = round(merged["trim_end"] - merged["trim_start"], 2)
    merged["transcript"] = (f"{a.get('transcript', '')} {b.get('transcript', '')}").strip()
    merged["cut_kind"] = "manual_merge"
    new_shots = [s for idx, s in enumerate(shots) if idx != second_i]
    new_shots[first_i] = merged
    proj["shots"] = _renumber_shots(new_shots)
    projects.save_project(pid, proj)
    projects.append_activity(pid, "editor", f"Merged Shot {a['number']:02d} and Shot {b['number']:02d}.")
    return projects.get_project(pid)


def reorder_shots(pid: str, ordered_ids: list[str]) -> dict[str, Any]:
    proj = projects.get_project(pid)
    by_id = {s["id"]: s for s in (proj.get("shots") or [])}
    reordered = [by_id[sid] for sid in ordered_ids if sid in by_id]
    remaining = [s for s in (proj.get("shots") or []) if s["id"] not in set(ordered_ids)]
    proj["shots"] = _renumber_shots(reordered + remaining)
    projects.save_project(pid, proj)
    projects.append_activity(pid, "editor", "Reordered timeline shots.")
    return projects.get_project(pid)


def update_timeline(pid: str, patch: dict[str, Any]) -> dict[str, Any]:
    proj = projects.get_project(pid)
    tl = copy.deepcopy(proj.get("timeline") or {})
    if patch.get("aspect") in ("16:9", "9:16", "1:1"):
        tl["aspect"] = patch["aspect"]
    if patch.get("fps") in (24, 30, 60):
        tl["fps"] = int(patch["fps"])
    if "background_music" in patch:
        tl["background_music"] = patch["background_music"]
    if "music_volume" in patch:
        tl["music_volume"] = round(max(0.0, min(1.0, float(patch["music_volume"]))), 2)
    if "master_volume" in patch:
        tl["master_volume"] = round(max(0.0, min(2.0, float(patch["master_volume"]))), 2)
    if "normalize_audio" in patch:
        tl["normalize_audio"] = bool(patch["normalize_audio"])
    if isinstance(patch.get("text_overlays"), list):
        tl["text_overlays"] = patch["text_overlays"][:50]
    if isinstance(patch.get("caption_config"), dict):
        cc = dict(tl.get("caption_config") or projects.DEFAULT_CAPTION_CONFIG)
        cc.update(patch["caption_config"])
        tl["caption_config"] = cc
    if isinstance(patch.get("captions"), list):
        tl["captions"] = patch["captions"][:500]
    proj["timeline"] = tl
    projects.save_project(pid, proj)
    return proj


def apply_suggestion(pid: str, shot_id: str, action: str) -> dict[str, Any]:
    proj = projects.get_project(pid)
    sh = next((s for s in (proj.get("shots") or []) if s["id"] == shot_id), None)
    if not sh:
        raise FileNotFoundError("Shot not found.")
    sug = sh.get("suggestions") or {}
    if action == "apply_zoom" and sug.get("zoom"):
        z = sug["zoom"]
        sh["edit"]["zoom"] = float(z.get("recommended_zoom", 1.18))
        sh["edit"]["pan_x"] = float(z.get("pan_x", 0.5))
        sh["edit"]["pan_y"] = float(z.get("pan_y", 0.5))
    elif action == "apply_transition" and sug.get("transition"):
        tr = sug["transition"]
        sh["edit"]["transition"] = tr.get("recommended_transition", "fade")
        sh["edit"]["transition_duration"] = float(tr.get("duration", 0.35))
    elif action == "apply_reframe" and sug.get("reframing"):
        aspect = proj.get("timeline", {}).get("aspect", "9:16")
        rf = sug["reframing"].get(aspect) or next(iter(sug["reframing"].values()), None)
        if rf:
            sh["edit"]["crop_mode"] = "face"
            sh["edit"]["pan_x"] = rf["pan_x"]
            sh["edit"]["pan_y"] = rf["pan_y"]
    elif action == "trim_silence":
        dur = float(sh.get("duration") or 1.0)
        trim_amt = min(1.5, dur * 0.2)
        if dur - trim_amt >= 1.0:
            sh["trim_start"] = round(float(sh.get("trim_start", sh["start"])) + trim_amt, 2)
            sh["duration"] = round(float(sh.get("trim_end", sh["end"])) - sh["trim_start"], 2)
    elif action == "highlight_keep":
        sh["edit"]["included"] = True

    for item in proj.get("analysis", {}).get("editing_plan") or []:
        if item.get("shot_id") == shot_id and item.get("action") == action:
            item["approved"] = True

    projects.save_project(pid, proj)
    projects.append_activity(pid, "editor", f"Applied AI suggestion '{action}' to Shot {sh['number']:02d}.")
    return projects.get_project(pid)


# ------------------------------------------------------------------ ASS Motion Graphics Generator
def _hex_to_ass_bgr(hex_color: str, alpha: int = 0) -> str:
    h = re.sub(r"[^0-9A-Fa-f]", "", str(hex_color or "FFFFFF"))
    if len(h) != 6:
        h = "FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    a = f"{max(0, min(255, alpha)):02X}"
    return f"&H{a}{b}{g}{r}"


def _ass_ts(t: float) -> str:
    t = max(0.0, float(t))
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _clean_ass_text(text: str) -> str:
    return re.sub(r"[\x00-\x1f\x7f]+", " ", re.sub(r"[{}\\]", "", str(text or ""))).strip()


def build_motion_ass(
    captions: list[dict[str, Any]],
    text_overlays: list[dict[str, Any]],
    caption_cfg: dict[str, Any],
    out_w: int,
    out_h: int,
) -> str:
    """Compile AgentVid captions and text overlays into a rich ASS subtitle script matching preview styles."""
    style_id = caption_cfg.get("style", "liquid_glass")
    preset = CAPTION_STYLES.get(style_id, CAPTION_STYLES["liquid_glass"])
    anim = caption_cfg.get("animation", "word_reveal")
    font_name = caption_cfg.get("font") or preset["font"]
    vertical_boost = 1.32 if out_h > out_w else 1.0
    scale_factor = (min(out_w, out_h) / 1080.0) * vertical_boost
    font_size = max(30, int(round(float(caption_cfg.get("font_size") or preset["font_size"]) * scale_factor)))
    margin_x = max(56, int(round(out_w * 0.08)))
    color = _hex_to_ass_bgr(caption_cfg.get("color") or preset["color"], 0)
    hi_color = _hex_to_ass_bgr(caption_cfg.get("highlight_color") or preset["highlight_color"], 0)
    outline_px = max(3, int(round(max(3, preset.get("outline", 4)) * scale_factor)))
    shadow_px = max(2, int(round(preset.get("shadow", 2) * scale_factor))) if caption_cfg.get("shadow", True) else 0
    spacing = float(preset.get("spacing", 0.5))
    uppercase = bool(caption_cfg.get("uppercase", preset.get("uppercase", False)))
    speed = max(0.3, min(3.0, float(caption_cfg.get("animation_speed", 1.0))))
    dur_scale = max(0.5, min(2.0, float(caption_cfg.get("duration_scale", 1.0))))
    timing_off = float(caption_cfg.get("word_timing_offset", 0.0))

    bg_mode = caption_cfg.get("background", preset.get("bg", "none"))
    bg_op = max(0.0, min(1.0, float(caption_cfg.get("background_opacity", 0.55))))
    bg_alpha = int(round((1.0 - bg_op) * 255))
    # Avoid BorderStyle=3 with per-word karaoke tags (libass draws vertical box seams between karaoke words)
    use_box_bg = bg_mode in ("solid", "pill", "subtle") and anim not in ("word_reveal", "highlight")
    border_style = 3 if use_box_bg else 1
    if use_box_bg:
        back_col = _hex_to_ass_bgr("#0A0D16", max(40, bg_alpha))
        out_col = _hex_to_ass_bgr("#0A0D16", max(40, bg_alpha))
    else:
        back_col = "&H68000000"
        out_col = "&H00000000"

    pos_mode = caption_cfg.get("position", "bottom")
    x_pct = float(caption_cfg.get("x_offset", 50))
    y_pct = float(caption_cfg.get("y_offset", 80 if pos_mode == "bottom" else 50 if pos_mode == "center" else 18))
    cy = int(round(out_h * max(0.08, min(0.92, y_pct / 100.0))))
    cx = int(round(out_w * max(0.10, min(0.90, x_pct / 100.0))))

    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {out_w}
PlayResY: {out_h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font_name},{font_size},{color},{hi_color},{out_col},{back_col},1,0,0,0,100,100,{spacing},0,{border_style},{outline_px},{shadow_px},5,{margin_x},{margin_x},40,1
Style: Overlay,Poppins ExtraBold,{max(32, int(font_size * 0.92))},&H00FFFFFF,&H0038BDF8,&H00000000,&H70090B10,1,0,0,0,100,100,1.0,0,3,{max(2, outline_px)},2,5,{margin_x},{margin_x},40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    t_in = max(60, int(round(180 / speed)))
    t_out = max(60, int(round(160 / speed)))
    events: list[str] = []

    def _anim_tags(cue_dur: float) -> str:
        if anim == "pop_in":
            return f"\\pos({cx},{cy})\\fscx78\\fscy78\\t(0,{t_in},\\fscx106\\fscy106)\\t({t_in},{t_in + 90},\\fscx100\\fscy100)"
        if anim == "scale_up":
            return f"\\pos({cx},{cy})\\fscx86\\fscy86\\t(0,{int(cue_dur * 900)},\\fscx105\\fscy105)"
        if anim == "blur_reveal":
            return f"\\pos({cx},{cy})\\blur8\\fad({t_in},80)\\t(0,{t_in + 80},\\blur0)"
        if anim == "slide_in":
            return f"\\move({cx},{cy + int(45 * scale_factor)},{cx},{cy},0,{t_in})\\fad({t_in},80)"
        if anim == "bounce":
            return f"\\pos({cx},{cy})\\fscx90\\fscy90\\t(0,{t_in},\\fscx114\\fscy114)\\t({t_in},{t_in + 120},\\fscx100\\fscy100)"
        if anim == "tracking":
            return f"\\pos({cx},{cy})\\fsp14\\t(0,{t_in + 120},\\fsp{spacing:.1f})"
        if anim == "motion_blur":
            return f"\\move({cx - int(35 * scale_factor)},{cy},{cx},{cy},0,{t_in})\\blur6\\t(0,{t_in},\\blur0)"
        if anim == "smooth_exit":
            return f"\\pos({cx},{cy})\\fad({t_in},{t_out + 120})"
        return f"\\pos({cx},{cy})\\fad({min(120, t_in)},80)"

    if caption_cfg.get("enabled", True):
        for cue in captions:
            s = max(0.0, float(cue.get("start", 0.0)) + timing_off)
            raw_dur = max(0.22, min(4.2, float(cue.get("end", s + 1.5)) - float(cue.get("start", 0.0))))
            e = s + raw_dur * dur_scale
            text = _clean_ass_text(cue.get("text", ""))
            if not text:
                continue
            if uppercase:
                text = text.upper()

            if anim in ("word_reveal", "highlight") and cue.get("words"):
                words = cue["words"]
                k_parts = []
                for idx, w in enumerate(words):
                    wt = _clean_ass_text(w.get("w", ""))
                    if not wt:
                        continue
                    if uppercase:
                        wt = wt.upper()
                    wdur_cs = max(8, int(round((float(w.get("e", s + 0.3)) - float(w.get("s", s))) * 100 * dur_scale)))
                    if anim == "highlight":
                        k_parts.append(f"{{\\kf{wdur_cs}}}{wt}")
                    else:
                        k_parts.append(f"{{\\k{wdur_cs}}}{wt}")
                body = " ".join(k_parts) if k_parts else text
                tags = f"\\an5\\pos({cx},{cy})\\c{hi_color}\\2c{color}\\fad(80,80)"
                events.append(f"Dialogue: 2,{_ass_ts(s)},{_ass_ts(e)},Cap,,0,0,0,,{{{tags}}}{body}")
            else:
                tags = "\\an5" + _anim_tags(e - s)
                if anim == "highlight":
                    tags += f"\\c{hi_color}"
                events.append(f"Dialogue: 2,{_ass_ts(s)},{_ass_ts(e)},Cap,,0,0,0,,{{{tags}}}{text}")

    # Shot-level or timeline text overlays
    for ov in text_overlays:
        txt = _clean_ass_text(ov.get("text", ""))
        if not txt:
            continue
        s = max(0.0, float(ov.get("start", 0.0)))
        e = max(s + 0.4, float(ov.get("end", s + 3.0)))
        ox = int(round(out_w * float(ov.get("x", 0.5))))
        oy = int(round(out_h * float(ov.get("y", 0.16))))
        events.append(
            f"Dialogue: 4,{_ass_ts(s)},{_ass_ts(e)},Overlay,,0,0,0,,{{\\an5\\pos({ox},{oy})\\fad(180,180)}}{txt}"
        )

    return head + "\n".join(events) + "\n"


# ------------------------------------------------------------------ Export Job Runner
_export_lock = threading.RLock()
_export_jobs: dict[str, dict[str, Any]] = {}
_export_cancels: dict[str, threading.Event] = {}


def get_export_status(export_id: str) -> dict[str, Any]:
    with _export_lock:
        job = _export_jobs.get(export_id)
        if not job:
            raise FileNotFoundError("Export job not found.")
        return copy.deepcopy(job)


def cancel_export(export_id: str) -> dict[str, Any]:
    with _export_lock:
        ev = _export_cancels.get(export_id)
        if ev:
            ev.set()
        if export_id in _export_jobs and _export_jobs[export_id]["status"] in ("queued", "running"):
            _export_jobs[export_id]["status"] = "cancelled"
            _export_jobs[export_id]["stage"] = "Cancelled by user"
            _export_jobs[export_id]["logs"].append("Export cancelled by user.")
        return copy.deepcopy(_export_jobs.get(export_id, {}))


def estimate_export(proj: dict[str, Any], opts: dict[str, Any]) -> dict[str, Any]:
    shots = _select_shots_for_export(proj, opts)
    total_dur = sum(
        max(0.1, (float(s.get("trim_end", s["end"])) - float(s.get("trim_start", s["start"]))) / max(0.25, float(s.get("edit", {}).get("speed", 1.0))))
        for s in shots
    )
    res = opts.get("resolution", "1080p")
    qual = opts.get("quality", "standard")
    codec = opts.get("codec", "h264")
    res_mult = {"720p": 0.55, "1080p": 1.0, "4k": 2.6}.get(res, 1.0)
    codec_mult = 0.72 if codec == "h265" else 1.0
    mbps = QUALITY_MBPS.get(qual, 5.5) * res_mult * codec_mult + 0.192
    est_bytes = int(total_dur * mbps * 1024 * 1024 / 8)
    w, h = RESOLUTION_DIMS.get((res, opts.get("aspect", "16:9")), (1920, 1080))
    return {
        "shot_count": len(shots),
        "duration_sec": round(total_dur, 2),
        "estimated_bytes": est_bytes,
        "estimated_mb": round(est_bytes / (1024 * 1024), 2),
        "width": w,
        "height": h,
    }


def _select_shots_for_export(proj: dict[str, Any], opts: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(opts.get("_custom_shots"), list):
        return list(opts["_custom_shots"])
    shots = list(proj.get("shots") or [])
    mode = opts.get("mode", "full")
    if mode == "shot":
        sid = opts.get("shot_id")
        return [s for s in shots if s["id"] == sid]
    if mode == "selected":
        wanted = set(opts.get("shot_ids") or [])
        return [s for s in shots if s["id"] in wanted]
    if mode in ("top_rated", "social_reels"):
        min_score = int(opts.get("min_score", 70))
        top = [s for s in shots if (s.get("virality") or {}).get("score", 0) >= min_score]
        if not top:
            top = sorted(shots, key=lambda s: (s.get("virality") or {}).get("score", 0), reverse=True)[:max(1, min(3, len(shots)))]
        return top
    # default: full edited timeline (included shots)
    inc = [s for s in shots if s.get("edit", {}).get("included", True)]
    return inc or shots


def _atempo_chain(speed: float) -> str:
    """Build valid FFmpeg atempo filter chain for speeds between 0.25x and 4.0x."""
    s = max(0.25, min(4.0, float(speed)))
    parts = []
    while s > 2.0:
        parts.append("atempo=2.0")
        s /= 2.0
    while s < 0.5:
        parts.append("atempo=0.5")
        s /= 0.5
    parts.append(f"atempo={s:.4f}")
    return ",".join(parts)


def start_export(pid: str, opts: dict[str, Any], sync: bool = False) -> dict[str, Any]:
    proj = projects.get_project(pid)
    media_meta, video_path = projects.get_active_media(proj)
    shots = _select_shots_for_export(proj, opts)
    if not shots:
        raise ValueError("No shots available to export. Analyze or include at least one shot first.")

    export_id = f"exp_{uuid.uuid4().hex[:10]}"
    est = estimate_export(proj, opts)
    settings = projects.get_settings()

    aspect = opts.get("aspect") or proj.get("timeline", {}).get("aspect") or "16:9"
    if opts.get("mode") == "social_reels":
        aspect = "9:16"
    resolution = opts.get("resolution") or "1080p"
    codec = opts.get("codec") or "h264"
    fps = int(opts.get("fps") or proj.get("timeline", {}).get("fps") or 30)
    quality = opts.get("quality") or "standard"
    audio_bitrate = opts.get("audio_bitrate") or "192k"
    out_w, out_h = RESOLUTION_DIMS.get((resolution, aspect), (1920, 1080))

    raw_name = projects.sanitize_filename(opts.get("filename") or f"{proj['name']}_{opts.get('mode', 'full')}_{aspect.replace(':', 'x')}.mp4")
    if not raw_name.lower().endswith(".mp4"):
        raw_name += ".mp4"

    # Output inside project exports dir AND optionally copy to user's chosen output folder
    proj_export_dir = projects.project_dir(pid) / "exports"
    proj_export_dir.mkdir(parents=True, exist_ok=True)
    proj_out_path = proj_export_dir / f"{export_id}_{raw_name}"

    custom_dir_str = str(opts.get("output_dir") or settings.get("export_defaults", {}).get("output_dir") or "").strip()
    custom_out_path = None
    if custom_dir_str:
        cdir = Path(custom_dir_str).expanduser()
        try:
            cdir.mkdir(parents=True, exist_ok=True)
            custom_out_path = cdir / raw_name
        except OSError:
            custom_out_path = None

    job_state = {
        "id": export_id,
        "project_id": pid,
        "status": "running",
        "progress": 0.02,
        "stage": "Preparing FFmpeg render graph...",
        "filename": raw_name,
        "file_url": f"/api/v2/projects/{pid}/exports/{proj_out_path.name}",
        "output_path": str(custom_out_path or proj_out_path),
        "internal_path": str(proj_out_path),
        "mode": opts.get("mode", "full"),
        "aspect": aspect,
        "resolution": resolution,
        "width": out_w,
        "height": out_h,
        "codec": codec,
        "fps": fps,
        "quality": quality,
        "audio_bitrate": audio_bitrate,
        "estimated_mb": est["estimated_mb"],
        "actual_mb": 0.0,
        "duration_sec": est["duration_sec"],
        "started_at": time.time(),
        "finished_at": None,
        "error": "",
        "logs": [f"Initialized export {export_id} ({out_w}x{out_h} @ {fps}fps, {codec.upper()}, {quality})."],
    }
    cancel_ev = threading.Event()
    with _export_lock:
        _export_jobs[export_id] = job_state
        _export_cancels[export_id] = cancel_ev

    def _log(msg: str, progress: float | None = None, stage: str | None = None):
        with _export_lock:
            j = _export_jobs[export_id]
            j["logs"].append(msg)
            if progress is not None:
                j["progress"] = round(max(0.0, min(1.0, progress)), 3)
            if stage is not None:
                j["stage"] = stage

    def _run():
        work = Path(tempfile.mkdtemp(prefix="avexp_"))
        try:
            legacy_render.install_fonts()
            (work / "f").mkdir()
            for tf in list(config.FONTS_DIR.glob("*.ttf")) + list(config.FONTS_DIR.glob("*.otf")):
                shutil.copyfile(tf, work / "f" / tf.name)

            tl = proj.get("timeline") or {}
            has_audio = bool(media_meta.get("has_audio"))
            src_w = int(media_meta.get("width") or 1920)
            src_h = int(media_meta.get("height") or 1080)
            master_vol = float(tl.get("master_volume", 1.0))

            seg_files: list[Path] = []
            seg_durs: list[float] = []
            seg_transitions: list[tuple[str, float]] = []
            timeline_overlays: list[dict[str, Any]] = list(tl.get("text_overlays") or [])
            remapped_captions: list[dict[str, Any]] = []
            raw_captions = list(tl.get("captions") or [])

            timeline_cursor = 0.0
            n_shots = len(shots)

            for idx, sh in enumerate(shots):
                if cancel_ev.is_set():
                    raise InterruptedError("Cancelled")

                s0 = float(sh.get("trim_start", sh["start"]))
                s1 = float(sh.get("trim_end", sh["end"]))
                raw_len = max(0.2, s1 - s0)
                ed = sh.get("edit") or {}
                speed = max(0.25, min(4.0, float(ed.get("speed", 1.0))))
                zoom = max(1.0, min(2.5, float(ed.get("zoom", 1.0))))
                pan_x = max(0.0, min(1.0, float(ed.get("pan_x", 0.5))))
                pan_y = max(0.0, min(1.0, float(ed.get("pan_y", 0.5))))
                if ed.get("crop_mode", "auto") in ("auto", "face") and aspect in ("9:16", "1:1"):
                    rf = ((sh.get("suggestions") or {}).get("reframing") or {}).get(aspect)
                    if rf:
                        pan_x = max(0.0, min(1.0, float(rf.get("pan_x", pan_x))))
                        pan_y = max(0.0, min(1.0, float(rf.get("pan_y", pan_y))))
                vol = 0.0 if ed.get("muted") else max(0.0, min(2.0, float(ed.get("volume", 1.0)) * master_vol))
                out_dur = raw_len / speed

                # Remap any captions falling inside [s0, s1] onto output timeline
                for cue in raw_captions:
                    cs = float(cue.get("start", 0.0))
                    ce = float(cue.get("end", 0.0))
                    if ce <= s0 or cs >= s1:
                        continue
                    ns = timeline_cursor + max(0.0, cs - s0) / speed
                    ne = timeline_cursor + min(raw_len, ce - s0) / speed
                    # Guard against any stale/corrupt cue spanning an entire clip
                    if ne - ns > 4.5:
                        ne = min(timeline_cursor + out_dur, ns + 3.4)
                    if ne - ns < 0.12:
                        continue
                    mapped_words = []
                    for w in cue.get("words") or []:
                        ws, we = float(w.get("s", cs)), float(w.get("e", ce))
                        if we > s0 and ws < s1:
                            mapped_words.append({
                                "w": w["w"],
                                "s": round(timeline_cursor + max(0.0, ws - s0) / speed, 3),
                                "e": round(timeline_cursor + min(raw_len, we - s0) / speed, 3),
                            })
                    remapped_captions.append({
                        "start": round(ns, 3),
                        "end": round(ne, 3),
                        "text": cue.get("text", ""),
                        "words": mapped_words,
                    })

                if ed.get("text_overlay"):
                    timeline_overlays.append({
                        "text": ed["text_overlay"],
                        "start": round(timeline_cursor, 2),
                        "end": round(timeline_cursor + out_dur, 2),
                        "x": 0.5,
                        "y": 0.16,
                    })

                # Compute real crop box honoring aspect ratio + smart pan + zoom
                target_ratio = out_w / out_h
                src_ratio = src_w / max(1, src_h)
                if src_ratio > target_ratio:
                    base_ch = src_h
                    base_cw = int(round(src_h * target_ratio))
                else:
                    base_cw = src_w
                    base_ch = int(round(src_w / target_ratio))

                crop_w = max(32, int(round(base_cw / zoom)) // 2 * 2)
                crop_h = max(32, int(round(base_ch / zoom)) // 2 * 2)
                cx0 = int(round(pan_x * src_w - crop_w / 2))
                cy0 = int(round(pan_y * src_h - crop_h / 2))
                cx0 = max(0, min(src_w - crop_w, cx0))
                cy0 = max(0, min(src_h - crop_h, cy0))

                vf_parts = [
                    f"crop={crop_w}:{crop_h}:{cx0}:{cy0}",
                    f"scale={out_w}:{out_h}:flags=lanczos",
                    f"setpts=PTS/{speed:.4f}",
                    f"fps={fps}",
                    "setsar=1",
                ]
                seg_path = work / f"seg_{idx:03d}.mp4"
                cmd = [
                    "ffmpeg", "-y", "-v", "error",
                    "-ss", f"{s0:.3f}", "-t", f"{raw_len:.3f}",
                    "-i", str(video_path),
                    "-vf", ",".join(vf_parts),
                ]
                if has_audio:
                    af_parts = [_atempo_chain(speed), f"volume={vol:.3f}"]
                    cmd += ["-af", ",".join(af_parts), "-c:a", "aac", "-b:a", audio_bitrate, "-ar", "48000", "-ac", "2"]
                else:
                    # Generate silent audio so concat/mixing is always uniform
                    cmd = [
                        "ffmpeg", "-y", "-v", "error",
                        "-ss", f"{s0:.3f}", "-t", f"{raw_len:.3f}", "-i", str(video_path),
                        "-f", "lavfi", "-t", f"{out_dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
                        "-vf", ",".join(vf_parts),
                        "-map", "0:v:0", "-map", "1:a:0",
                        "-c:a", "aac", "-b:a", audio_bitrate, "-ar", "48000", "-ac", "2", "-shortest",
                    ]

                cmd += ["-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(seg_path)]
                _log(
                    f"Rendering Shot {sh['number']:02d} ({s0:.2f}s-{s1:.2f}s, {speed}x, zoom {zoom}x)...",
                    progress=0.08 + (idx / max(1, n_shots)) * 0.50,
                    stage=f"Rendering shot {idx + 1}/{n_shots}",
                )
                p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   creationflags=media.NO_WINDOW, timeout=600)
                if p.returncode != 0:
                    raise RuntimeError(f"Shot {sh['number']} render failed: {p.stderr[-800:]}")

                seg_files.append(seg_path)
                seg_durs.append(out_dur)
                seg_transitions.append((ed.get("transition", "none"), float(ed.get("transition_duration", 0.35))))
                timeline_cursor += out_dur

            if cancel_ev.is_set():
                raise InterruptedError("Cancelled")

            # Assemble segments (with xfade transitions when configured, else lossless stream concat)
            _log("Assembling timeline & applying transitions...", progress=0.64, stage="Assembling timeline")
            assembled = work / "assembled.mp4"
            use_xfade = len(seg_files) > 1 and any(tr[0] != "none" for tr in seg_transitions[1:])

            if len(seg_files) == 1:
                shutil.copyfile(seg_files[0], assembled)
            elif use_xfade:
                xf_map = {
                    "fade": "fade",
                    "dissolve": "dissolve",
                    "wipeleft": "wipeleft",
                    "wiperight": "wiperight",
                    "slideup": "slideup",
                    "zoomin": "smoothup",
                }
                inputs = []
                for sf_path in seg_files:
                    inputs += ["-i", str(sf_path)]
                vf_lines = []
                af_lines = []
                cur_v = "[0:v]"
                cur_a = "[0:a]"
                offset = seg_durs[0]
                for i in range(1, len(seg_files)):
                    tr_name, tr_dur = seg_transitions[i]
                    td = min(tr_dur, seg_durs[i - 1] * 0.4, seg_durs[i] * 0.4) if tr_name != "none" else 0.05
                    td = max(0.05, round(td, 2))
                    xname = xf_map.get(tr_name, "fade")
                    out_v = f"[v{i}]"
                    out_a = f"[a{i}]"
                    off = max(0.0, round(offset - td, 3))
                    vf_lines.append(f"{cur_v}[{i}:v]xfade=transition={xname}:duration={td:.2f}:offset={off:.3f}{out_v}")
                    af_lines.append(f"{cur_a}[{i}:a]acrossfade=d={td:.2f}{out_a}")
                    cur_v, cur_a = out_v, out_a
                    offset = off + seg_durs[i]
                fc = ";".join(vf_lines + af_lines)
                p = subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc,
                     "-map", cur_v, "-map", cur_a, "-c:v", "libx264", "-crf", "17", "-preset", "veryfast",
                     "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", audio_bitrate, str(assembled)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    creationflags=media.NO_WINDOW, timeout=900,
                )
                if p.returncode != 0:
                    _log(f"Transition fallback to clean cut: {p.stderr[-250:]}")
                    use_xfade = False

            if len(seg_files) > 1 and not use_xfade:
                concat_txt = work / "concat.txt"
                concat_txt.write_text("\n".join(f"file '{sf_path.name}'" for sf_path in seg_files), encoding="utf-8")
                p = subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "concat.txt",
                     "-c", "copy", str(assembled)],
                    cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    creationflags=media.NO_WINDOW, timeout=600,
                )
                if p.returncode != 0:
                    raise RuntimeError(f"Concatenation failed: {p.stderr[-800:]}")

            if cancel_ev.is_set():
                raise InterruptedError("Cancelled")

            # Burn-in Motion Graphics Captions + Text Overlays + Optional Background Music + Final Encode
            _log("Rendering captions & final encoding...", progress=0.76, stage="Final encode & captions")
            caption_cfg = dict(tl.get("caption_config") or projects.DEFAULT_CAPTION_CONFIG)
            style_id = str(caption_cfg.get("style") or "liquid_glass")
            use_shader_fx = bool(caption_cfg.get("enabled", True) and remapped_captions and caption_fx.is_shader_style(style_id))
            shader_mov = None
            shader_y = 0
            if use_shader_fx:
                _log(f"Rendering animated '{style_id}' metallic/gradient caption overlay...", progress=0.78, stage="Rendering shader captions")
                shader_mov, shader_y = caption_fx.build_shader_overlay_video(
                    remapped_captions,
                    caption_cfg,
                    out_w,
                    out_h,
                    max(0.5, timeline_cursor),
                    work / "captions_fx.mov",
                    fps=min(24, fps),
                )

            has_ass = bool(((caption_cfg.get("enabled", True) and remapped_captions) and not use_shader_fx) or timeline_overlays)
            if has_ass:
                ass_cues = [] if use_shader_fx else remapped_captions
                ass_text = build_motion_ass(ass_cues, timeline_overlays, caption_cfg, out_w, out_h)
                (work / "captions.ass").write_text(ass_text, encoding="utf-8")

            bg_music_id = tl.get("background_music")
            bg_music_path = None
            if bg_music_id:
                track = next((a for a in (proj.get("audio_tracks") or []) if a["id"] == bg_music_id), None)
                if track:
                    cand = projects.project_dir(pid) / "media" / track["filename"]
                    if cand.is_file():
                        bg_music_path = cand

            crf = QUALITY_CRF.get(quality, 21)
            hw_mode = settings.get("performance", {}).get("hw_accel", "auto")
            encoders: list[tuple[str, list[str]]] = []
            if codec == "h265":
                if hw_mode == "auto":
                    encoders.append(("hevc_nvenc", ["-c:v", "hevc_nvenc", "-cq", str(crf + 2), "-preset", "p4", "-pix_fmt", "yuv420p"]))
                    encoders.append(("hevc_qsv", ["-c:v", "hevc_qsv", "-global_quality", str(crf + 2), "-pix_fmt", "nv12"]))
                encoders.append(("libx265", ["-c:v", "libx265", "-crf", str(crf + 2), "-preset", "fast", "-tag:v", "hvc1", "-pix_fmt", "yuv420p"]))
            else:
                if hw_mode == "auto":
                    encoders.append(("h264_nvenc", ["-c:v", "h264_nvenc", "-cq", str(crf), "-preset", "p4", "-pix_fmt", "yuv420p"]))
                    encoders.append(("h264_qsv", ["-c:v", "h264_qsv", "-global_quality", str(crf), "-preset", "fast", "-pix_fmt", "nv12"]))
                encoders.append(("libx264", ["-c:v", "libx264", "-crf", str(crf), "-preset", "medium" if quality in ("high", "master") else "fast", "-pix_fmt", "yuv420p"]))

            final_local = work / "final.mp4"
            base_cmd = ["ffmpeg", "-y", "-v", "error", "-i", "assembled.mp4"]
            next_in_idx = 1
            bgm_idx = None
            fx_idx = None
            if bg_music_path:
                base_cmd += ["-stream_loop", "-1", "-i", str(bg_music_path)]
                bgm_idx = next_in_idx
                next_in_idx += 1
            if shader_mov is not None:
                base_cmd += ["-i", shader_mov.name]
                fx_idx = next_in_idx
                next_in_idx += 1

            filter_parts = []
            v_map = "0:v:0"
            if fx_idx is not None and has_ass:
                filter_parts.append(f"[0:v][{fx_idx}:v]overlay=0:{shader_y}:shortest=1[vfx];[vfx]ass=captions.ass:fontsdir=f[vout]")
                v_map = "[vout]"
            elif fx_idx is not None:
                filter_parts.append(f"[0:v][{fx_idx}:v]overlay=0:{shader_y}:shortest=1[vout]")
                v_map = "[vout]"
            elif has_ass:
                filter_parts.append("[0:v]ass=captions.ass:fontsdir=f[vout]")
                v_map = "[vout]"

            a_map = "0:a:0"
            norm_str = ",loudnorm=I=-14:TP=-1.5:LRA=11" if tl.get("normalize_audio", True) else ""
            if bgm_idx is not None:
                mvol = max(0.0, min(1.0, float(tl.get("music_volume", 0.25))))
                filter_parts.append(f"[{bgm_idx}:a]volume={mvol:.3f}[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2{norm_str}[aout]")
                a_map = "[aout]"
            elif norm_str:
                filter_parts.append(f"[0:a]anull{norm_str}[aout]")
                a_map = "[aout]"

            if filter_parts:
                base_cmd += ["-filter_complex", ";".join(filter_parts), "-map", v_map, "-map", a_map]
            else:
                base_cmd += ["-map", "0:v:0", "-map", "0:a:0"]

            base_cmd += ["-c:a", "aac", "-b:a", audio_bitrate, "-ar", "48000", "-movflags", "+faststart"]

            last_err = ""
            used_encoder = ""
            for label, enc_args in encoders:
                if cancel_ev.is_set():
                    raise InterruptedError("Cancelled")
                _log(f"Encoding with {label}...", progress=0.82, stage=f"Encoding ({label})")
                p = subprocess.run(
                    base_cmd + enc_args + [str(final_local)],
                    cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    creationflags=media.NO_WINDOW, timeout=1200,
                )
                if p.returncode == 0 and final_local.is_file() and final_local.stat().st_size > 0:
                    used_encoder = label
                    break
                last_err = p.stderr[-800:]
                _log(f"Encoder {label} unavailable, trying fallback...")
            else:
                raise RuntimeError(f"Video export failed on all encoders: {last_err}")

            shutil.move(str(final_local), str(proj_out_path))
            if custom_out_path:
                try:
                    shutil.copy2(proj_out_path, custom_out_path)
                except OSError as e:
                    _log(f"Note: could not copy to custom output dir ({e}); kept inside project exports.")

            actual_bytes = proj_out_path.stat().st_size
            actual_mb = round(actual_bytes / (1024 * 1024), 2)
            _log(f"Export succeeded using {used_encoder} ({actual_mb} MB).", progress=1.0, stage="Export complete")

            with _export_lock:
                j = _export_jobs[export_id]
                j["status"] = "done"
                j["actual_mb"] = actual_mb
                j["encoder"] = used_encoder
                j["finished_at"] = time.time()
                summary_rec = copy.deepcopy(j)

            cur_proj = projects.get_project(pid)
            cur_proj["exports"] = (cur_proj.get("exports") or [])[-29:] + [summary_rec]
            projects.save_project(pid, cur_proj)
            projects.append_activity(pid, "export", f"Exported '{raw_name}' ({out_w}x{out_h}, {used_encoder}, {actual_mb} MB).")

        except InterruptedError:
            with _export_lock:
                _export_jobs[export_id]["status"] = "cancelled"
                _export_jobs[export_id]["stage"] = "Cancelled"
                _export_jobs[export_id]["finished_at"] = time.time()
        except Exception as e:
            with _export_lock:
                _export_jobs[export_id]["status"] = "error"
                _export_jobs[export_id]["stage"] = "Failed"
                _export_jobs[export_id]["error"] = str(e)
                _export_jobs[export_id]["logs"].append(f"ERROR: {e}")
                _export_jobs[export_id]["finished_at"] = time.time()
            try:
                projects.append_activity(pid, "export", f"Export failed: {e}", "error")
            except Exception:
                pass
        finally:
            shutil.rmtree(work, ignore_errors=True)

    if sync:
        _run()
        return get_export_status(export_id)

    threading.Thread(target=_run, name=f"agentvid-export-{export_id}", daemon=True).start()
    return get_export_status(export_id)


# ------------------------------------------------------------------ Multi-Reel Pack Generator (e.g. 3 x 30s Reels)
def plan_viral_reels(proj: dict[str, Any], count: int = 3, target_duration: float = 30.0) -> list[dict[str, Any]]:
    """Select up to `count` non-overlapping ~`target_duration`s highlight windows anchored on highest-virality shots."""
    shots = list(proj.get("shots") or [])
    if not shots:
        raise ValueError("No analyzed shots available yet. Analyze the video first.")
    media_meta, _ = projects.get_active_media(proj)
    total_dur = float(media_meta.get("duration") or max(float(s["end"]) for s in shots))
    target = max(10.0, min(90.0, float(target_duration or 30.0)))
    count = max(1, min(6, int(count or 3)))

    ranked = sorted(shots, key=lambda s: (s.get("virality") or {}).get("score", 0), reverse=True)
    used_ranges: list[tuple[float, float]] = []
    reels: list[dict[str, Any]] = []

    def _overlaps(a0: float, a1: float) -> bool:
        for b0, b1 in used_ranges:
            ov = min(a1, b1) - max(a0, b0)
            if ov > min(4.0, target * 0.2):
                return True
        return False

    for anchor in ranked:
        if len(reels) >= count:
            break
        s0 = float(anchor.get("trim_start", anchor["start"]))
        s1 = min(total_dur, s0 + target)
        if s1 - s0 < min(target, total_dur) - 0.5:
            s0 = max(0.0, total_dur - target)
            s1 = total_dur
        if _overlaps(s0, s1):
            continue
        used_ranges.append((s0, s1))
        score = int((anchor.get("virality") or {}).get("score", 0))
        reels.append({
            "index": len(reels) + 1,
            "anchor_shot_id": anchor["id"],
            "anchor_shot_number": anchor["number"],
            "score": score,
            "start": round(s0, 2),
            "end": round(s1, 2),
            "duration": round(s1 - s0, 2),
            "face_info": anchor.get("face_info") or {},
            "suggestions": anchor.get("suggestions") or {},
        })

    # Fallback evenly spaced windows if video had few/clustered high-scoring shots
    if len(reels) < count and total_dur >= target * 1.1:
        stride = max(target, (total_dur - target) / max(1, count - 1)) if count > 1 else 0.0
        for i in range(count * 2):
            if len(reels) >= count:
                break
            s0 = round(min(max(0.0, total_dur - target), i * stride * 0.5), 2)
            s1 = round(min(total_dur, s0 + target), 2)
            if s1 - s0 < 8.0 or _overlaps(s0, s1):
                continue
            used_ranges.append((s0, s1))
            near = min(shots, key=lambda sh: abs(float(sh["start"]) - s0))
            reels.append({
                "index": len(reels) + 1,
                "anchor_shot_id": near["id"],
                "anchor_shot_number": near["number"],
                "score": int((near.get("virality") or {}).get("score", 0)),
                "start": s0,
                "end": s1,
                "duration": round(s1 - s0, 2),
                "face_info": near.get("face_info") or {},
                "suggestions": near.get("suggestions") or {},
            })

    return reels


def start_reels_pack(pid: str, opts: dict[str, Any], sync: bool = False) -> dict[str, Any]:
    """Batch-generate individual vertical 9:16 Reels (1–20) from the project's extracted Peak Reels or top moments."""
    proj = projects.get_project(pid)
    shots = list(proj.get("shots") or [])
    included_shots = [s for s in shots if (s.get("edit") or {}).get("included", True)]
    is_peak_timeline = any(s.get("cut_kind") in ("ai_peak_reel", "local_peak_reel") for s in included_shots)
    use_timeline_reels = bool(opts.get("use_timeline_reels", is_peak_timeline))

    aspect = opts.get("aspect") or proj.get("timeline", {}).get("aspect") or "9:16"
    if aspect not in ("9:16", "1:1", "16:9"):
        aspect = "9:16"

    if use_timeline_reels and included_shots:
        max_n = int(opts.get("count") or len(included_shots))
        max_n = max(1, min(20, max_n))
        selected_shots = included_shots[:max_n]
        planned = []
        for idx, sh in enumerate(selected_shots, start=1):
            s0 = float(sh.get("trim_start", sh["start"]))
            s1 = float(sh.get("trim_end", sh["end"]))
            dur = round(max(1.0, s1 - s0), 2)
            planned.append({
                "index": idx,
                "anchor_shot_id": sh["id"],
                "anchor_shot_number": sh.get("number", idx),
                "title": sh.get("title") or f"Peak Reel {idx:02d}",
                "hook": sh.get("hook") or "",
                "score": int((sh.get("virality") or {}).get("score", 0)),
                "start": round(s0, 2),
                "end": round(s1, 2),
                "duration": dur,
                "face_info": sh.get("face_info") or {},
                "suggestions": sh.get("suggestions") or {},
                "edit": copy.deepcopy(sh.get("edit") or {}),
            })
        label_dur = "AI/Edited"
    else:
        count = max(1, min(20, int(opts.get("count") or 3)))
        target_dur = max(10.0, min(90.0, float(opts.get("target_duration") or 30.0)))
        planned = plan_viral_reels(proj, count=count, target_duration=target_dur)
        label_dur = f"{int(target_dur)}s"

    if not planned:
        raise ValueError("Could not build Reel windows from this project.")

    batch_id = f"exp_{uuid.uuid4().hex[:10]}"
    resolution = opts.get("resolution") or "1080p"
    codec = opts.get("codec") or "h264"
    fps = int(opts.get("fps") or 30)
    quality = opts.get("quality") or "standard"
    audio_bitrate = opts.get("audio_bitrate") or "192k"
    output_dir = opts.get("output_dir") or ""
    out_w, out_h = RESOLUTION_DIMS.get((resolution, aspect), (1080, 1920))

    caps_enabled = bool((proj.get("timeline") or {}).get("caption_config", {}).get("enabled", True))
    job_state = {
        "id": batch_id,
        "project_id": pid,
        "status": "running",
        "progress": 0.02,
        "stage": f"Exporting {len(planned)} Reels ({aspect}, Captions {'ON' if caps_enabled else 'OFF'})...",
        "filename": f"{len(planned)} Reels ({label_dur})",
        "file_url": "",
        "output_path": output_dir or str(projects.project_dir(pid) / "exports"),
        "mode": "reels_pack",
        "aspect": aspect,
        "resolution": resolution,
        "width": out_w,
        "height": out_h,
        "codec": codec,
        "fps": fps,
        "quality": quality,
        "captions_enabled": caps_enabled,
        "duration_sec": round(sum(r["duration"] for r in planned), 2),
        "actual_mb": 0.0,
        "reels": [],
        "started_at": time.time(),
        "finished_at": None,
        "error": "",
        "logs": [f"Initialized Reels Pack: {len(planned)} Reels ({out_w}x{out_h}, {codec.upper()}, Captions {'ON' if caps_enabled else 'OFF'})."],
    }
    cancel_ev = threading.Event()
    with _export_lock:
        _export_jobs[batch_id] = job_state
        _export_cancels[batch_id] = cancel_ev

    def _run_pack():
        rendered_reels = []
        total_mb = 0.0
        try:
            for idx, r in enumerate(planned, start=1):
                if cancel_ev.is_set():
                    raise InterruptedError("Cancelled")
                reel_label = r.get("title") or f"Shot {r['anchor_shot_number']:02d}"
                with _export_lock:
                    _export_jobs[batch_id]["progress"] = round((idx - 1) / len(planned), 3)
                    _export_jobs[batch_id]["stage"] = f"Rendering Reel {idx}/{len(planned)} ({r['start']:.1f}s-{r['end']:.1f}s, Score {r['score']})..."
                    _export_jobs[batch_id]["logs"].append(
                        f"Reel {idx}: {r['start']:.1f}s-{r['end']:.1f}s ({r['duration']:.1f}s) — {reel_label} (Score {r['score']}/100)"
                    )

                cur_proj = projects.get_project(pid)
                base_edit = {
                    "included": True,
                    "speed": 1.0,
                    "zoom": 1.0,
                    "pan_x": 0.5,
                    "pan_y": 0.5,
                    "volume": 1.0,
                    "muted": False,
                    "transition": "none",
                    "crop_mode": "face",
                    "text_overlay": "",
                }
                if r.get("edit"):
                    base_edit.update(r["edit"])
                    base_edit["included"] = True
                virtual_shot = {
                    "id": f"reel_{idx}",
                    "number": r["anchor_shot_number"],
                    "start": r["start"],
                    "end": r["end"],
                    "trim_start": r["start"],
                    "trim_end": r["end"],
                    "duration": r["duration"],
                    "face_info": r["face_info"],
                    "suggestions": r["suggestions"],
                    "edit": base_edit,
                }
                safe_base = projects.sanitize_filename(cur_proj["name"], fallback="AgentVid")[:36]
                r_fname = f"{safe_base}_Reel_{idx:02d}_{int(round(r['duration']))}s_Score{r['score']}.mp4"

                sub = _export_custom_shots(
                    pid=pid,
                    shots=[virtual_shot],
                    opts={
                        "mode": "reel",
                        "aspect": aspect,
                        "resolution": resolution,
                        "codec": codec,
                        "fps": fps,
                        "quality": quality,
                        "audio_bitrate": audio_bitrate,
                        "filename": r_fname,
                        "output_dir": output_dir,
                    },
                )
                if sub["status"] != "done":
                    raise RuntimeError(sub.get("error") or f"Reel {idx} render failed.")
                total_mb += float(sub.get("actual_mb") or 0.0)
                rendered_reels.append({
                    "index": idx,
                    "title": r.get("title") or f"Reel {idx:02d}",
                    "filename": sub["filename"],
                    "file_url": sub["file_url"],
                    "output_path": sub["output_path"],
                    "internal_path": sub["internal_path"],
                    "start": r["start"],
                    "end": r["end"],
                    "duration": r["duration"],
                    "score": r["score"],
                    "actual_mb": sub["actual_mb"],
                    "width": sub["width"],
                    "height": sub["height"],
                })
                with _export_lock:
                    _export_jobs[batch_id]["reels"] = list(rendered_reels)
                    _export_jobs[batch_id]["logs"].append(f"Reel {idx} complete: {sub['filename']} ({sub['actual_mb']} MB)")

            with _export_lock:
                j = _export_jobs[batch_id]
                j["status"] = "done"
                j["progress"] = 1.0
                j["stage"] = f"Generated {len(rendered_reels)} Reels"
                j["actual_mb"] = round(total_mb, 2)
                j["file_url"] = rendered_reels[0]["file_url"] if rendered_reels else ""
                j["finished_at"] = time.time()
        except InterruptedError:
            with _export_lock:
                _export_jobs[batch_id]["status"] = "cancelled"
                _export_jobs[batch_id]["stage"] = "Cancelled"
                _export_jobs[batch_id]["finished_at"] = time.time()
        except Exception as e:
            with _export_lock:
                _export_jobs[batch_id]["status"] = "error"
                _export_jobs[batch_id]["stage"] = "Failed"
                _export_jobs[batch_id]["error"] = str(e)
                _export_jobs[batch_id]["logs"].append(f"ERROR: {e}")
                _export_jobs[batch_id]["finished_at"] = time.time()

    if sync:
        _run_pack()
        return get_export_status(batch_id)

    threading.Thread(target=_run_pack, name=f"agentvid-reels-{batch_id}", daemon=True).start()
    return get_export_status(batch_id)


def _export_custom_shots(pid: str, shots: list[dict[str, Any]], opts: dict[str, Any]) -> dict[str, Any]:
    """Synchronously export an explicit list of virtual shots through the full FFmpeg + caption pipeline."""
    orig_select = _select_shots_for_export
    # Pass virtual shots via a thread-safe custom key supported by start_export
    opts_with_shots = dict(opts, _custom_shots=shots)
    return start_export(pid, opts_with_shots, sync=True)
