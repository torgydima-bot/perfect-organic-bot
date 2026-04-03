#!/usr/bin/env python3
"""Генерация фавиконов с закруглёнными углами для дашборда. Запуск: python build_favicons.py"""
from __future__ import annotations

import json
import os

from PIL import Image, ImageDraw

_DIR = os.path.dirname(os.path.abspath(__file__))
_STATIC = os.path.join(_DIR, "static")

# Цвета как в админке
_BG_OUTER = (26, 29, 46, 255)  # #1a1d2e
_BG_INNER = (22, 101, 52, 255)  # #166534
_LEAF = (187, 247, 208, 255)  # #bbf7d0
_ACCENT = (124, 58, 237, 255)  # #7c3aed


def _render_icon(size: int) -> Image.Image:
    """RGBA, прозрачные углы за пределами скругления."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    rad = max(2, int(size * 0.24))
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=rad, fill=_BG_OUTER)
    pad = max(1, int(size * 0.09))
    rad2 = max(1, rad - pad)
    draw.rounded_rectangle(
        (pad, pad, size - 1 - pad, size - 1 - pad),
        radius=rad2,
        fill=_BG_INNER,
    )
    cx, cy = size // 2, int(size * 0.48)
    w = max(2, int(size * 0.20))
    h = max(3, int(size * 0.26))
    draw.polygon(
        [
            (cx, cy - h),
            (cx + w, cy),
            (cx, cy + h),
            (cx - w, cy),
        ],
        fill=_LEAF,
    )
    # Маленький акцент (читается с 32px+)
    if size >= 32:
        ar = max(1, size // 16)
        draw.ellipse(
            (size - pad - 2 * ar, pad, size - pad, pad + 2 * ar),
            fill=_ACCENT,
        )
    return img


def _save_png(img: Image.Image, path: str) -> None:
    img.save(path, "PNG", optimize=True)


def _save_ico(sizes_and_images: list[tuple[int, Image.Image]]) -> None:
    path = os.path.join(_STATIC, "favicon.ico")
    imgs = [im for _s, im in sizes_and_images]
    imgs[0].save(
        path,
        format="ICO",
        sizes=[(im.width, im.height) for im in imgs],
        append_images=imgs[1:],
    )


def main() -> None:
    os.makedirs(_STATIC, exist_ok=True)
    master = _render_icon(512)

    png_files = [
        (16, "favicon-16x16.png"),
        (32, "favicon-32x32.png"),
        (48, "favicon-48x48.png"),
        (180, "apple-touch-icon.png"),
        (192, "icon-192.png"),
        (512, "icon-512.png"),
    ]
    for s, fname in png_files:
        im = master.resize((s, s), Image.Resampling.LANCZOS)
        _save_png(im, os.path.join(_STATIC, fname))

    # ICO: нативные размеры для чёткости
    base16 = _render_icon(16)
    base32 = _render_icon(32)
    base48 = _render_icon(48)
    _save_ico([(16, base16), (32, base32), (48, base48)])

    # Web manifest (легковесный) для android/chrome
    manifest = {
        "name": "Perfect Organic Bot",
        "short_name": "PO Bot",
        "icons": [
            {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        ],
        "display": "standalone",
        "theme_color": "#1a1d2e",
        "background_color": "#0f1117",
    }
    with open(os.path.join(_STATIC, "site.webmanifest"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("OK:", _STATIC)


if __name__ == "__main__":
    main()
