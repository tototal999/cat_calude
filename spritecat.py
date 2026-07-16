"""
Sprite-based cat frames from PNG images (replaces vectorcat for photo cats).
============================================================================

Loads bluecat01..06.png from the frames/ directory, removes white background
(makes it transparent), resizes to the requested square canvas, and outputs
premultiplied BGRA buffers for winalpha.LayeredCanvas.draw().
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image
import struct


FRAMES_DIR = Path(__file__).parent / 'frames'
SPRITE_PATTERN = 'bluecat{:02d}.png'
SPRITE_COUNT = 6

# Threshold for "white" background removal (0-255).
# Pixels where R, G, B are all above this value are made transparent.
WHITE_THRESHOLD = 230


def _remove_white_bg(img: Image.Image, threshold: int = WHITE_THRESHOLD) -> Image.Image:
    """Convert near-white pixels to transparent."""
    img = img.convert('RGBA')
    data = img.getdata()
    new_data = []
    for r, g, b, a in data:
        if r > threshold and g > threshold and b > threshold:
            new_data.append((r, g, b, 0))
        else:
            new_data.append((r, g, b, a))
    img.putdata(new_data)
    return img


def _fit_to_square(img: Image.Image, size: int) -> Image.Image:
    """Resize image to fit within a square canvas, preserving aspect ratio,
    centered on transparent background."""
    # Calculate scale to fit
    w, h = img.size
    scale = min(size / w, size / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Center on transparent square canvas
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    offset_x = (size - new_w) // 2
    offset_y = (size - new_h) // 2
    canvas.paste(img, (offset_x, offset_y), img)
    return canvas


def _to_premultiplied_bgra(img: Image.Image) -> bytes:
    """Convert RGBA PIL Image to premultiplied BGRA bytes for UpdateLayeredWindow."""
    raw = img.tobytes()
    buf = bytearray(len(raw))
    for i in range(0, len(raw), 4):
        r, g, b, a = raw[i], raw[i + 1], raw[i + 2], raw[i + 3]
        buf[i] = b * a // 255      # B
        buf[i + 1] = g * a // 255  # G
        buf[i + 2] = r * a // 255  # R
        buf[i + 3] = a             # A
    return bytes(buf)


def load_sprite_frames(size: int, facing: str = 'left') -> tuple[bytes, list[bytes]]:
    """Load bluecat PNG sprites and return (idle_frame, run_frames) as BGRA buffers.

    size:   canvas width/height in px
    facing: 'left' or 'right'

    Returns the same format as vectorcat.render_frames() so it's a drop-in replacement.
    The first frame (bluecat01) is used as the idle frame.
    All 6 frames are used as the run cycle.
    """
    frames_bgra = []
    for i in range(1, SPRITE_COUNT + 1):
        path = FRAMES_DIR / SPRITE_PATTERN.format(i)
        img = Image.open(path)
        img = _remove_white_bg(img)
        img = _fit_to_square(img, size)

        if facing == 'right':
            img = img.transpose(Image.FLIP_LEFT_RIGHT)

        frames_bgra.append(_to_premultiplied_bgra(img))

    # idle = first frame; run cycle = all frames
    idle = frames_bgra[0]
    return idle, frames_bgra
