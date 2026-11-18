"""AgentVid Font Manager: bundled SIL OFL fonts + user-uploaded custom .ttf/.otf fonts."""
from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from PIL import ImageFont

from . import config, render as legacy_render

ALLOWED_FONT_EXTS = {".ttf", ".otf"}
SAFE_FONT_RE = re.compile(r"[^A-Za-z0-9._\- ]+")

BUNDLED_FONTS = {
    "Poppins-ExtraBold.ttf": "Poppins ExtraBold",
    "Anton-Regular.ttf": "Anton",
    "ArchivoBlack-Regular.ttf": "Archivo Black",
}


def _meta_file() -> Path:
    return config.FONTS_DIR / "custom_fonts.json"


def _load_meta() -> dict[str, dict[str, Any]]:
    f = _meta_file()
    if not f.is_file():
        return {}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_meta(data: dict[str, dict[str, Any]]) -> None:
    config.FONTS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _meta_file().with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_meta_file())


def list_fonts() -> list[dict[str, Any]]:
    """Return all bundled + custom uploaded fonts ready for live UI preview and FFmpeg rendering."""
    legacy_render.install_fonts()
    out: list[dict[str, Any]] = []
    for fname, family in BUNDLED_FONTS.items():
        if (config.FONTS_DIR / fname).is_file():
            out.append({
                "id": fname,
                "family": family,
                "filename": fname,
                "url": f"/api/v2/fonts/file/{fname}",
                "custom": False,
            })

    meta = _load_meta()
    for fname, info in meta.items():
        fpath = config.FONTS_DIR / fname
        if not fpath.is_file():
            continue
        out.append({
            "id": fname,
            "family": info.get("family") or fpath.stem,
            "filename": fname,
            "url": f"/api/v2/fonts/file/{fname}",
            "custom": True,
        })
    return out


def resolve_font_path(family_or_file: str) -> Path:
    """Resolve a font family name or filename to its actual .ttf/.otf path on disk."""
    legacy_render.install_fonts()
    wanted = str(family_or_file or "").strip()
    if wanted:
        direct = config.FONTS_DIR / wanted
        if direct.is_file():
            return direct
        for item in list_fonts():
            if item["family"].lower() == wanted.lower() or item["filename"].lower() == wanted.lower():
                p = config.FONTS_DIR / item["filename"]
                if p.is_file():
                    return p
    return config.FONTS_DIR / "Poppins-ExtraBold.ttf"


def install_custom_font(raw_bytes: bytes, original_filename: str) -> dict[str, Any]:
    """Validate and save a user-uploaded .ttf or .otf font for both live preview and FFmpeg export."""
    if not raw_bytes or len(raw_bytes) > 25 * 1024 * 1024:
        raise ValueError("Font file must be non-empty and under 25 MB.")

    orig = Path(str(original_filename or "custom.ttf")).name
    ext = Path(orig).suffix.lower()
    if ext not in ALLOWED_FONT_EXTS:
        raise ValueError("Only .ttf and .otf font files are supported.")

    stem = SAFE_FONT_RE.sub("_", Path(orig).stem).strip(" ._")[:48] or "CustomFont"
    stored_name = f"custom_{uuid.uuid4().hex[:6]}_{stem}{ext}"
    config.FONTS_DIR.mkdir(parents=True, exist_ok=True)
    dst = config.FONTS_DIR / stored_name
    dst.write_bytes(raw_bytes)

    try:
        pil_font = ImageFont.truetype(str(dst), 48)
        fam, style = pil_font.getname()
        # Verify it can actually render characters
        pil_font.getbbox("AGENTVID")
        display_family = (fam or stem).strip()
        if style and style.lower() not in ("regular", "normal") and style.lower() not in display_family.lower():
            display_family = f"{display_family} {style}".strip()
    except Exception as e:
        dst.unlink(missing_ok=True)
        raise ValueError(f"Invalid or corrupted font file: {e}") from e

    meta = _load_meta()
    # Ensure unique display family name if user uploads a duplicate
    existing_fams = {f["family"].lower() for f in list_fonts()}
    final_family = display_family
    if final_family.lower() in existing_fams:
        final_family = f"{display_family} ({stem[:10]})"

    meta[stored_name] = {"family": final_family, "original": orig}
    _save_meta(meta)

    return {
        "id": stored_name,
        "family": final_family,
        "filename": stored_name,
        "url": f"/api/v2/fonts/file/{stored_name}",
        "custom": True,
    }


def delete_custom_font(filename: str) -> None:
    if filename in BUNDLED_FONTS:
        raise ValueError("Bundled studio fonts cannot be deleted.")
    if not re.fullmatch(r"custom_[A-Za-z0-9._\-]+\.(ttf|otf)", filename or ""):
        raise ValueError("Invalid custom font identifier.")
    meta = _load_meta()
    meta.pop(filename, None)
    _save_meta(meta)
    p = config.FONTS_DIR / filename
    if p.is_file():
        p.unlink()
