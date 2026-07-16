"""
Sprite-based cat frames from PNG images (replaces vectorcat for photo cats).
============================================================================

Loads all *.png from a skin folder under skins/, removes white background
(makes it transparent), resizes to the requested square canvas, and outputs
premultiplied BGRA buffers for winalpha.LayeredCanvas.draw().

Skin pack structure:
    skins/
      bluecat/
        01.png, 02.png, ...
      blackcat/
        cat_0.png, cat_1.png, ...
"""
from __future__ import annotations

import sys
from pathlib import Path
from PIL import Image

# Support PyInstaller bundled exe: images are extracted to sys._MEIPASS
_BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))

# Legacy fallback: if skins/ doesn't exist, try frames/
LEGACY_FRAMES_DIR = _BASE_DIR / 'frames'


def _skin_roots() -> list[Path]:
    """Skin root directories in priority order.

    For a frozen exe, an external ``skins/`` folder next to ClaudeCat.exe
    wins over the skins bundled at build time (sys._MEIPASS), so new skins
    can be added by dropping a folder beside the exe - no rebuild needed.
    """
    roots = []
    if getattr(sys, 'frozen', False):
        roots.append(Path(sys.executable).parent / 'skins')
    roots.append(_BASE_DIR / 'skins')
    return [r for r in roots if r.is_dir()]

# Default skin name
DEFAULT_SKIN = 'bluecat'

# Threshold for "white" background removal (0-255).
# Pixels where R, G, B are all above this value are made transparent.
WHITE_THRESHOLD = 230


def list_skins() -> list[str]:
    """Return sorted list of available skin names across all skin roots."""
    names: set[str] = set()
    for root in _skin_roots():
        names.update(d.name for d in root.iterdir()
                     if d.is_dir() and any(d.glob('*.png')))
    if names:
        return sorted(names)
    # Fallback: no skins dir, treat legacy frames/ as a single skin
    if LEGACY_FRAMES_DIR.is_dir():
        return ['default']
    return []


def _get_skin_dir(skin_name: str) -> Path:
    """Resolve a skin name to its directory path (external root wins)."""
    roots = _skin_roots()
    for root in roots:
        skin_dir = root / skin_name
        if skin_dir.is_dir() and any(skin_dir.glob('*.png')):
            return skin_dir
    # Fallback to legacy frames/
    if LEGACY_FRAMES_DIR.is_dir():
        return LEGACY_FRAMES_DIR
    raise FileNotFoundError(f'Skin "{skin_name}" not found in {roots}')


def _pick_all(pngs: list[Path], marker: str) -> list[Path]:
    return [p for p in pngs if marker in p.stem.lower()]


def _pick_one(pngs: list[Path], marker: str) -> Path | None:
    matches = _pick_all(pngs, marker)
    return matches[0] if matches else None


def _collect_pngs(skin_dir: Path) -> tuple[list[Path], list[Path], Path | None]:
    """Collect run-cycle PNGs plus optional sleep/idle special-pose PNGs.

    Filenames containing "sleep" (any case, e.g. "cowcat_sleep_07.png") are
    the sleep pose - one or more frames, cycled like a mini run-cycle so a
    multi-frame sleep (e.g. a breathing loop) animates instead of freezing
    on a single image. A filename containing "_09" is the dedicated
    standby/idle pose (e.g. ragdollcat's ragdollcat_09.png). Both kinds are
    excluded from the main run cycle. If a marker isn't present in the
    skin, that special pose is simply empty/None and callers fall back to
    their default (e.g. run_frames[0] as idle, no sleep pose at all).
    """
    all_pngs = sorted(skin_dir.glob('*.png'))
    if not all_pngs:
        raise FileNotFoundError(f'No PNG files found in {skin_dir}')
    sleep_paths = _pick_all(all_pngs, 'sleep')
    idle_path = _pick_one(all_pngs, '_09')
    special = set(sleep_paths) | ({idle_path} if idle_path else set())
    frame_paths = [p for p in all_pngs if p not in special]
    if not frame_paths:
        # The special-pose file(s) were the only PNGs - use them as normal
        # frames too rather than leaving the skin with no run cycle.
        return all_pngs, [], None
    return frame_paths, sleep_paths, idle_path


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


def _load_one(path: Path, size: int, facing: str) -> bytes:
    img = Image.open(path)
    img = _remove_white_bg(img)
    img = _fit_to_square(img, size)
    if facing == 'right':
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    return _to_premultiplied_bgra(img)


def load_sprite_frames(size: int, facing: str = 'left', skin: str = DEFAULT_SKIN,
                       ) -> tuple[bytes, list[bytes], list[bytes]]:
    """Load sprite PNG files from a skin folder.

    size:   canvas width/height in px
    facing: 'left' or 'right'
    skin:   skin name (subdirectory under skins/)

    Returns (idle_frame, run_frames, sleep_frames). idle_frame is the
    skin's dedicated "_09" standby pose if it has one, else run_frames[0].
    sleep_frames is a (possibly multi-frame) cycle for the skin's "sleep"
    marked PNGs, or an empty list if the skin has none.
    """
    skin_dir = _get_skin_dir(skin)
    frame_paths, sleep_paths, idle_path = _collect_pngs(skin_dir)

    frames_bgra = [_load_one(p, size, facing) for p in frame_paths]
    sleep_bgra = [_load_one(p, size, facing) for p in sleep_paths]
    idle_bgra = _load_one(idle_path, size, facing) if idle_path else frames_bgra[0]

    return idle_bgra, frames_bgra, sleep_bgra
