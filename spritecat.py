"""
Sprite-based cat frames from PNG images (replaces vectorcat for photo cats).
============================================================================

Loads all *.png from a skin folder under skins/, removes white background
(makes it transparent), resizes to the requested square canvas, and outputs
premultiplied BGRA buffers for winalpha.LayeredCanvas.draw().

Skin pack structure - {skin}_{action}_{order}.png, see _collect_pngs:
    skins/
      cowcat/
        cowcat_run_01.png, cowcat_run_02.png, ...
        cowcat_sleep_01.png, ...
        cowcat_error_01.png, ...
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


def _collect_pngs(skin_dir: Path) -> tuple[list[Path], list[Path], Path | None, list[Path]]:
    """Collect run-cycle PNGs plus optional sleep/idle/error special-pose PNGs.

    Naming convention: {skin}_{action}_{order}.png, e.g. "cowcat_run_01.png",
    "cowcat_sleep_01.png", "cowcat_error_01.png". The action word is matched
    as a case-insensitive substring:
      - "sleep" -> sleep pose (one or more frames, cycled like a mini run-cycle)
      - "error" -> error pose (same, cycled)
      - "idle"  -> the dedicated standby pose (single frame)
    Anything not matching one of those is a run-cycle frame (so "run" isn't
    a strictly required marker, but is the documented convention). If a
    marker isn't present in the skin, that special pose is simply
    empty/None and callers fall back to their default (e.g. run_frames[0]
    as idle, plain default animation with no error pose).
    """
    all_pngs = sorted(skin_dir.glob('*.png'))
    if not all_pngs:
        raise FileNotFoundError(f'No PNG files found in {skin_dir}')
    sleep_paths = _pick_all(all_pngs, 'sleep')
    error_paths = _pick_all(all_pngs, 'error')
    listening_paths = _pick_all(all_pngs, 'listening')
    thinking_paths = _pick_all(all_pngs, 'thinking')
    success_paths = _pick_all(all_pngs, 'success')
    non_special = [p for p in all_pngs if p not in sleep_paths and p not in error_paths
                   and p not in listening_paths and p not in thinking_paths
                   and p not in success_paths]
    idle_path = _pick_one(non_special, 'idle')
    special = (set(sleep_paths) | set(error_paths) | set(listening_paths)
               | set(thinking_paths) | set(success_paths)
               | ({idle_path} if idle_path else set()))
    frame_paths = [p for p in all_pngs if p not in special]
    if not frame_paths:
        # The special-pose file(s) were the only PNGs - use them as normal
        # frames too rather than leaving the skin with no run cycle.
        return all_pngs, [], None, []
    return frame_paths, sleep_paths, idle_path, error_paths


def _action_paths(skin_dir: Path) -> dict[str, list[Path]]:
    """Return every supported action, keeping named states out of run frames."""
    run_paths, sleep_paths, idle_path, error_paths = _collect_pngs(skin_dir)
    all_pngs = sorted(skin_dir.glob('*.png'))
    return {
        'run': run_paths,
        'idle': [idle_path] if idle_path else [run_paths[0]],
        'sleep': sleep_paths,
        'error': error_paths,
        'listening': _pick_all(all_pngs, 'listening'),
        'thinking': _pick_all(all_pngs, 'thinking'),
        'success': _pick_all(all_pngs, 'success'),
    }


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
                       ) -> tuple[bytes, list[bytes], list[bytes], list[bytes]]:
    """Load sprite PNG files from a skin folder.

    size:   canvas width/height in px
    facing: 'left' or 'right'
    skin:   skin name (subdirectory under skins/)

    Returns (idle_frame, run_frames, sleep_frames, error_frames). idle_frame
    is the skin's dedicated "_09" standby pose if it has one, else
    run_frames[0]. sleep_frames/error_frames are each a (possibly
    multi-frame) cycle for the skin's "sleep"/"error" marked PNGs, or an
    empty list if the skin has none.
    """
    skin_dir = _get_skin_dir(skin)
    frame_paths, sleep_paths, idle_path, error_paths = _collect_pngs(skin_dir)

    frames_bgra = [_load_one(p, size, facing) for p in frame_paths]
    sleep_bgra = [_load_one(p, size, facing) for p in sleep_paths]
    error_bgra = [_load_one(p, size, facing) for p in error_paths]
    idle_bgra = _load_one(idle_path, size, facing) if idle_path else frames_bgra[0]

    return idle_bgra, frames_bgra, sleep_bgra, error_bgra


def load_state_frames(size: int, facing: str = 'left', skin: str = DEFAULT_SKIN,
                      ) -> dict[str, list[bytes]]:
    """Load named visual states with safe fallbacks for incomplete skin packs."""
    paths = _action_paths(_get_skin_dir(skin))
    frames = {name: [_load_one(path, size, facing) for path in action_paths]
              for name, action_paths in paths.items()}
    frames['listening'] = frames['listening'] or frames['idle']
    frames['thinking'] = frames['thinking'] or frames['run']
    frames['success'] = frames['success'] or frames['idle']
    frames['streaming'] = frames['thinking']
    return frames
