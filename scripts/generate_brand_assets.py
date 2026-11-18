"""Generate crisp AgentVid desktop icons (.ico, .png) and Windows installer brand bitmaps
in the Creative Creature Obsidian + Pure White + Signature Cobalt (#0066FF) theme."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT_DESKTOP = ROOT / "desktop" / "assets"
OUT_WEB = ROOT / "web" / "brand"
OUT_DESKTOP.mkdir(parents=True, exist_ok=True)
OUT_WEB.mkdir(parents=True, exist_ok=True)


def lerp(a, b, t):
    return int(a + (b - a) * t)


def make_icon(size: int = 512) -> Image.Image:
    s = size * 2
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    pad = int(s * 0.04)
    r = int(s * 0.22)

    bg = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(bg).rounded_rectangle([pad, pad, s - pad, s - pad], radius=r, fill=(9, 10, 14, 255))

    # Restrained signature Cobalt glow from top-center
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([int(s * 0.18), int(s * 0.05), int(s * 0.82), int(s * 0.65)], fill=(0, 102, 255, 52))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=int(s * 0.12)))

    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([pad, pad, s - pad, s - pad], radius=r, fill=255)
    img.paste(bg, (0, 0), mask)
    img = Image.alpha_composite(img, Image.composite(glow, Image.new("RGBA", (s, s), (0, 0, 0, 0)), mask))

    # Crisp architectural hairline border
    draw = ImageDraw.Draw(img)
    bw = max(4, int(s * 0.018))
    draw.rounded_rectangle([pad, pad, s - pad, s - pad], radius=r, outline=(255, 255, 255, 42), width=bw)

    # Stark pure white geometric 'A' mark
    cx = s * 0.5
    top_y = s * 0.20
    bot_y = s * 0.77
    half_w = s * 0.275
    leg_w = s * 0.125
    bar_y1 = s * 0.61
    bar_y2 = s * 0.695

    outer_a = [
        (cx, top_y),
        (cx + half_w, bot_y),
        (cx + half_w - leg_w, bot_y),
        (cx + half_w * 0.43, bar_y2),
        (cx - half_w * 0.43, bar_y2),
        (cx - half_w + leg_w, bot_y),
        (cx - half_w, bot_y),
    ]
    draw.polygon(outer_a, fill=(255, 255, 255, 255))

    inner_tri = [
        (cx, top_y + s * 0.20),
        (cx + half_w * 0.28, bar_y1),
        (cx - half_w * 0.28, bar_y1),
    ]
    draw.polygon(inner_tri, fill=(9, 10, 14, 255))

    # Creative Creature Cobalt Blue (#0066FF) play aperture + signature corner dot
    play_tri = [
        (cx - s * 0.042, s * 0.455),
        (cx + s * 0.068, s * 0.515),
        (cx - s * 0.042, s * 0.575),
    ]
    draw.polygon(play_tri, fill=(0, 102, 255, 255))

    dot_r = s * 0.042
    dot_cx, dot_cy = s * 0.76, s * 0.735
    draw.ellipse([dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r], fill=(0, 102, 255, 255))

    return img.resize((size, size), Image.Resampling.LANCZOS)


def make_installer_sidebar() -> Image.Image:
    w, h = 164, 314
    img = Image.new("RGB", (w, h), (7, 8, 11))
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = y / h
            px[x, y] = (lerp(8, 12, t), lerp(9, 14, t), lerp(13, 22, t))
    icon = make_icon(92)
    img.paste(icon, ((w - 92) // 2, 54), icon)
    return img


def make_installer_header() -> Image.Image:
    w, h = 150, 57
    img = Image.new("RGB", (w, h), (8, 9, 13))
    icon = make_icon(38)
    img.paste(icon, (w - 46, (h - 38) // 2), icon)
    return img


def main():
    icon512 = make_icon(512)
    icon512.save(OUT_DESKTOP / "icon.png", format="PNG")
    icon512.resize((256, 256), Image.Resampling.LANCZOS).save(OUT_WEB / "agentvid-icon.png", format="PNG")
    icon512.save(
        OUT_DESKTOP / "icon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    make_installer_sidebar().save(OUT_DESKTOP / "installer-sidebar.bmp", format="BMP")
    make_installer_header().save(OUT_DESKTOP / "installer-header.bmp", format="BMP")
    print("Generated Creative Creature themed AgentVid icons and installer bitmaps.")


if __name__ == "__main__":
    main()
