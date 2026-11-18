"""AgentVid Shader Caption Renderer: renders real Liquid Metal Silver, Molten Gold, Glossy Pink Chrome,
and Animated Moving Hyper-Gradients into a transparent FFmpeg overlay video band using Pillow + NumPy."""
from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import fonts_manager, media

SHADER_STYLES = {
    "liquid_silver",
    "molten_gold",
    "glossy_pink",
    "hyper_gradient",
    "cobalt_pulse",
    "solar_plasma",
}

# Multi-stop RGB palettes (periodic horizontally so scrolling gradients loop seamlessly!)
SHADER_PALETTES: dict[str, dict[str, Any]] = {
    "liquid_silver": {
        "stops": [
            (248, 250, 255),
            (165, 178, 196),
            (30, 38, 52),
            (230, 242, 255),
            (255, 255, 255),
            (110, 124, 145),
            (46, 56, 72),
            (215, 228, 244),
            (248, 250, 255),
        ],
        "rim": (255, 255, 255),
        "outline": (10, 12, 18),
        "angle": 0.42,
        "speed_px": 240.0,
        "metallic": True,
    },
    "molten_gold": {
        "stops": [
            (255, 248, 210),
            (250, 204, 21),
            (133, 77, 14),
            (254, 240, 138),
            (255, 251, 235),
            (202, 138, 4),
            (92, 52, 8),
            (253, 224, 71),
            (255, 248, 210),
        ],
        "rim": (255, 251, 220),
        "outline": (28, 16, 4),
        "angle": 0.38,
        "speed_px": 210.0,
        "metallic": True,
    },
    "glossy_pink": {
        "stops": [
            (255, 242, 249),
            (244, 114, 182),
            (131, 24, 67),
            (251, 207, 232),
            (255, 255, 255),
            (236, 72, 153),
            (110, 18, 58),
            (249, 168, 212),
            (255, 242, 249),
        ],
        "rim": (255, 236, 246),
        "outline": (34, 8, 22),
        "angle": 0.40,
        "speed_px": 230.0,
        "metallic": True,
    },
    "hyper_gradient": {
        "stops": [
            (0, 102, 255),
            (0, 229, 255),
            (255, 255, 255),
            (255, 46, 147),
            (255, 174, 0),
            (0, 102, 255),
        ],
        "rim": (255, 255, 255),
        "outline": (6, 8, 14),
        "angle": 0.18,
        "speed_px": 340.0,
        "metallic": False,
    },
    "cobalt_pulse": {
        "stops": [
            (255, 255, 255),
            (96, 165, 250),
            (0, 102, 255),
            (18, 52, 148),
            (59, 130, 246),
            (219, 234, 254),
            (255, 255, 255),
        ],
        "rim": (224, 242, 255),
        "outline": (5, 8, 16),
        "angle": 0.28,
        "speed_px": 280.0,
        "metallic": True,
    },
    "solar_plasma": {
        "stops": [
            (254, 240, 138),
            (251, 146, 60),
            (244, 63, 94),
            (192, 38, 211),
            (251, 191, 36),
            (254, 240, 138),
        ],
        "rim": (255, 247, 214),
        "outline": (20, 6, 12),
        "angle": 0.22,
        "speed_px": 310.0,
        "metallic": False,
    },
}


def is_shader_style(style_id: str) -> bool:
    return style_id in SHADER_STYLES


def _make_seamless_texture(style_id: str, width: int, height: int) -> np.ndarray:
    """Create a periodic (2*width x height x 3) uint8 gradient/liquid-metal texture strip."""
    spec = SHADER_PALETTES.get(style_id, SHADER_PALETTES["liquid_silver"])
    stops = np.array(spec["stops"], dtype=np.float32)
    n_seg = len(stops) - 1

    xs = np.linspace(0.0, 2.0, width * 2, endpoint=False, dtype=np.float32)
    ys = np.linspace(0.0, 1.0, height, dtype=np.float32)
    gx, gy = np.meshgrid(xs, ys)

    phase = (gx + gy * float(spec["angle"])) % 1.0
    if spec.get("metallic"):
        # Add subtle liquid ripple distortion for authentic molten metal reflections
        ripple = 0.045 * np.sin(gx * 2.0 * math.pi * 2.0 + gy * 4.5) * np.cos(gy * 3.14159)
        phase = (phase + ripple) % 1.0

    pos = phase * n_seg
    idx = np.clip(pos.astype(np.int32), 0, n_seg - 1)
    frac = (pos - idx)[..., None]
    rgb = stops[idx] * (1.0 - frac) + stops[idx + 1] * frac

    if spec.get("metallic"):
        # Crisp glossy specular horizon highlight band in the upper half of characters
        spec_band = np.exp(-((gy - 0.34) / 0.12) ** 2) * 52.0
        rgb = np.clip(rgb + spec_band[..., None], 0, 255)

    return rgb.astype(np.uint8)


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        test = f"{cur} {w}"
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines[:3]


def _render_cue_layers(
    text: str,
    font_path: Path,
    font_size: int,
    band_w: int,
    band_h: int,
    outline_rgb: tuple[int, int, int],
    rim_rgb: tuple[int, int, int],
    shadow: bool,
    x_pct: float = 50.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pre-render (fill_alpha_f32, rim_alpha_f32, backdrop_rgba_u8) for one caption cue."""
    font = ImageFont.truetype(str(font_path), font_size)
    dummy = Image.new("L", (band_w, band_h), 0)
    ddraw = ImageDraw.Draw(dummy)
    max_w = int(band_w * 0.84)
    lines = _wrap_text(ddraw, text, font, max_w)
    if not lines:
        empty_f = np.zeros((band_h, band_w), dtype=np.float32)
        return empty_f, empty_f, np.zeros((band_h, band_w, 4), dtype=np.uint8)

    line_gap = int(font_size * 1.16)
    total_h = line_gap * len(lines)
    start_y = max(8, (band_h - total_h) // 2)

    fill_mask = Image.new("L", (band_w, band_h), 0)
    fdraw = ImageDraw.Draw(fill_mask)
    stroke_w = max(3, int(round(font_size * 0.085)))

    outline_mask = Image.new("L", (band_w, band_h), 0)
    odraw = ImageDraw.Draw(outline_mask)

    target_cx = int(round(band_w * max(0.10, min(0.90, x_pct / 100.0))))
    pad_x = max(16, int(band_w * 0.04))

    for i, line in enumerate(lines):
        bbox = fdraw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        raw_x = target_cx - lw // 2
        clamped_x = max(pad_x, min(band_w - pad_x - lw, raw_x))
        x = clamped_x - bbox[0]
        y = start_y + i * line_gap - bbox[1]
        odraw.text((x, y), line, font=font, fill=255, stroke_width=stroke_w, stroke_fill=255)
        fdraw.text((x, y), line, font=font, fill=255)

    # Outer dark contour + soft drop shadow layer
    backdrop = Image.new("RGBA", (band_w, band_h), (0, 0, 0, 0))
    if shadow:
        sh_mask = outline_mask.filter(ImageFilter.GaussianBlur(radius=max(3, font_size // 16)))
        sh_img = Image.new("RGBA", (band_w, band_h), (0, 0, 0, 210))
        backdrop.paste(sh_img, (0, max(4, font_size // 14)), sh_mask)

    out_img = Image.new("RGBA", (band_w, band_h), (*outline_rgb, 245))
    backdrop.paste(out_img, (0, 0), outline_mask)

    # Specular top-edge inner bevel rim for liquid metal realism
    fill_arr = np.array(fill_mask, dtype=np.float32) / 255.0
    shifted = np.roll(fill_arr, shift=max(2, font_size // 28), axis=0)
    shifted[:max(2, font_size // 28), :] = 0.0
    rim_arr = np.clip(fill_arr - shifted, 0.0, 1.0) * 0.55

    return fill_arr, rim_arr, np.array(backdrop, dtype=np.uint8)


def build_shader_overlay_video(
    captions: list[dict[str, Any]],
    caption_cfg: dict[str, Any],
    out_w: int,
    out_h: int,
    total_duration: float,
    out_mov: Path,
    fps: int = 24,
) -> tuple[Path, int]:
    """Render an animated transparent MOV band containing liquid-metal / moving-gradient captions.

    Returns (out_mov_path, y_offset_pixels_from_top).
    """
    style_id = caption_cfg.get("style", "liquid_silver")
    spec = SHADER_PALETTES.get(style_id, SHADER_PALETTES["liquid_silver"])
    font_path = fonts_manager.resolve_font_path(caption_cfg.get("font") or "Poppins ExtraBold")

    vertical_boost = 1.30 if out_h > out_w else 1.0
    scale_factor = (min(out_w, out_h) / 1080.0) * vertical_boost
    font_size = max(32, int(round(float(caption_cfg.get("font_size") or 74) * scale_factor)))
    uppercase = bool(caption_cfg.get("uppercase", True))
    shadow = bool(caption_cfg.get("shadow", True))
    anim_speed = max(0.3, min(3.0, float(caption_cfg.get("animation_speed", 1.0))))
    dur_scale = max(0.5, min(2.0, float(caption_cfg.get("duration_scale", 1.0))))
    timing_off = float(caption_cfg.get("word_timing_offset", 0.0))

    band_w = out_w
    band_h = min(out_h, max(220, int(font_size * 4.2)) // 2 * 2)
    pos_mode = caption_cfg.get("position", "bottom")
    x_pct = float(caption_cfg.get("x_offset", 50))
    y_pct = float(caption_cfg.get("y_offset", 80 if pos_mode == "bottom" else 50 if pos_mode == "center" else 18))
    band_y = int(round(out_h * max(0.08, min(0.92, y_pct / 100.0)) - band_h / 2))
    band_y = max(0, min(out_h - band_h, band_y))

    tex = _make_seamless_texture(style_id, band_w, band_h)
    rim_col = np.array(spec["rim"], dtype=np.float32)

    prepared_cues = []
    for cue in captions:
        txt = str(cue.get("text") or "").strip()
        if not txt:
            continue
        if uppercase:
            txt = txt.upper()
        s = max(0.0, float(cue.get("start", 0.0)) + timing_off)
        raw_d = max(0.22, min(4.2, float(cue.get("end", s + 1.5)) - float(cue.get("start", 0.0))))
        e = s + raw_d * dur_scale
        if s >= total_duration:
            continue
        fill_a, rim_a, backdrop = _render_cue_layers(
            txt, font_path, font_size, band_w, band_h, spec["outline"], spec["rim"], shadow, x_pct=x_pct
        )
        prepared_cues.append({
            "s": s,
            "e": min(total_duration, e),
            "fill": fill_a,
            "rim": rim_a,
            "backdrop": backdrop,
            "bg_rgb": backdrop[:, :, :3].astype(np.float32),
            "bg_a": backdrop[:, :, 3:4].astype(np.float32) / 255.0,
        })

    n_frames = max(1, int(math.ceil(total_duration * fps)))
    blank_bytes = bytes(band_w * band_h * 4)
    speed_px = float(spec["speed_px"]) * anim_speed

    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgba",
        "-s", f"{band_w}x{band_h}", "-r", str(fps),
        "-i", "-",
        "-c:v", "qtrle", "-pix_fmt", "argb",
        str(out_mov),
    ]
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=media.NO_WINDOW,
    )
    assert proc.stdin is not None

    try:
        for fi in range(n_frames):
            t = fi / fps
            active = None
            for c in prepared_cues:
                if c["s"] <= t <= c["e"]:
                    active = c
                    break
            if active is None:
                proc.stdin.write(blank_bytes)
                continue

            # Fade-in / fade-out envelope for silky entrance & exit
            fade = 1.0
            dt_in = t - active["s"]
            dt_out = active["e"] - t
            if dt_in < 0.14:
                fade = max(0.0, dt_in / 0.14)
            elif dt_out < 0.12:
                fade = max(0.0, dt_out / 0.12)

            shift = int(round((t * speed_px) % band_w))
            grad_slice = tex[:, shift:shift + band_w, :].astype(np.float32)

            fill_a = active["fill"][..., None]
            rim_a = active["rim"][..., None]
            fg_rgb = np.clip(grad_slice * (1.0 - rim_a) + rim_col * rim_a, 0, 255)

            # Porter-Duff source-over: fg (gradient text) over backdrop (contour + shadow)
            bg_a = active["bg_a"]
            out_a = fill_a + bg_a * (1.0 - fill_a)
            safe_a = np.maximum(out_a, 1e-5)
            out_rgb = (fg_rgb * fill_a + active["bg_rgb"] * bg_a * (1.0 - fill_a)) / safe_a

            frame = np.empty((band_h, band_w, 4), dtype=np.uint8)
            frame[:, :, :3] = np.clip(out_rgb, 0, 255).astype(np.uint8)
            frame[:, :, 3] = np.clip(out_a[:, :, 0] * fade * 255.0, 0, 255).astype(np.uint8)
            proc.stdin.write(frame.tobytes())
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
    _, err = proc.communicate(timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(f"Shader caption render failed: {err.decode('utf-8', errors='replace')[-600:]}")
    return out_mov, band_y
