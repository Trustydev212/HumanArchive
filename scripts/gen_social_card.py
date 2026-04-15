#!/usr/bin/env python3
"""Sinh social card PNG (1200x630) cho OpenGraph / Twitter preview.

Dùng Pillow để vẽ. Không dùng SVG-to-PNG (cần librsvg).
Output PNG embed vào <meta property="og:image"> trong landing page.

Sử dụng:
    python scripts/gen_social_card.py assets/social-card.png

Cần: pip install Pillow
"""

from __future__ import annotations

import sys
from pathlib import Path


def _has_pillow() -> bool:
    try:
        import PIL  # noqa
        return True
    except ImportError:
        return False


def generate(out_path: Path) -> bool:
    """Tạo social card 1200x630 PNG. Trả về False nếu thiếu Pillow."""
    if not _has_pillow():
        return False

    from PIL import Image, ImageDraw, ImageFont  # type: ignore

    W, H = 1200, 630
    BG_TOP = (250, 247, 240)
    BG_BOTTOM = (240, 232, 212)
    FG = (42, 26, 10)
    MUTED = (90, 74, 53)
    ACCENT = (139, 69, 19)

    img = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(img)

    # Gradient background (top → bottom)
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] * (1 - t) + BG_BOTTOM[0] * t)
        g = int(BG_TOP[1] * (1 - t) + BG_BOTTOM[1] * t)
        b = int(BG_TOP[2] * (1 - t) + BG_BOTTOM[2] * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Constellation of voices bên phải
    cx, cy = 920, 315
    for dx, dy in [(-100, -80), (110, -100), (140, 30), (60, 130),
                    (-80, 110), (-150, 20), (-60, -130)]:
        draw.line([(cx, cy), (cx + dx, cy + dy)], fill=ACCENT + (100,) if False else ACCENT, width=2)
        draw.ellipse(
            (cx + dx - 14, cy + dy - 14, cx + dx + 14, cy + dy + 14),
            fill=ACCENT,
        )
    draw.ellipse((cx - 26, cy - 26, cx + 26, cy + 26), fill=ACCENT)
    draw.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), fill=BG_TOP)

    # Text
    # Try nice fonts; fallback to PIL default
    def load_font(size: int):
        for name in ["DejaVuSans-Bold.ttf", "Arial.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                      "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]:
            try:
                return ImageFont.truetype(name, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default()

    def load_font_regular(size: int):
        for name in ["DejaVuSans.ttf", "Arial.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                      "/System/Library/Fonts/Supplemental/Arial.ttf"]:
            try:
                return ImageFont.truetype(name, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default()

    title_font = load_font(72)
    tag_font = load_font_regular(30)
    small_font = load_font_regular(22)

    draw.text((80, 180), "HumanArchive", fill=FG, font=title_font)
    draw.text((80, 275),
              "Lưu trữ ký ức tập thể phi tập trung",
              fill=MUTED, font=tag_font)
    draw.text((80, 315),
              "Decentralized collective memory — without judgment.",
              fill=MUTED, font=tag_font)

    # 5 nguyên tắc mini
    principles = [
        "1.  No verdicts     2.  No identification",
        "3.  Empathy first   4.  Motivation > action",
        "5.  Raw data immutable — content-addressed",
    ]
    y = 420
    for line in principles:
        draw.text((80, y), line, fill=MUTED, font=small_font)
        y += 32

    # Footer URL
    draw.text((80, H - 60),
              "github.com/Trustydev212/HumanArchive",
              fill=ACCENT, font=small_font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")
    return True


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "assets/social-card.png")
    if generate(out):
        return 0
    print("Pillow not installed — install with: pip install Pillow", file=sys.stderr)
    print("Social card generation skipped (SVG banner will be used as fallback)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
