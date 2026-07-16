"""
True per-pixel-alpha rendering for ClaudeCat (Windows only).
=============================================================

Replaces the tkinter chroma-key (``-transparentcolor``) approach, which
cannot key out anti-aliased sprite edges (semi-transparent pixels blend
with the key color and leave a magenta fringe).  Instead the cat window
is made WS_EX_LAYERED and each frame is pushed with UpdateLayeredWindow,
so the frame PNGs render with true smooth alpha.

Pure stdlib: PNG frames are decoded with zlib/struct (no Pillow, by
design — see README), and GDI is driven via ctypes.
"""
from __future__ import annotations

import ctypes
import struct
import zlib
from ctypes import wintypes
from pathlib import Path

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
ULW_ALPHA = 2
AC_SRC_OVER = 0
AC_SRC_ALPHA = 1
GA_ROOT = 2

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# 64-bit safety: handles/pointers must not go through the default c_int
user32.GetAncestor.restype = ctypes.c_void_p
user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
user32.GetDC.restype = ctypes.c_void_p
user32.GetDC.argtypes = [ctypes.c_void_p]
user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
gdi32.CreateDIBSection.restype = ctypes.c_void_p
gdi32.SelectObject.restype = ctypes.c_void_p
gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
_GetWindowLong = getattr(user32, 'GetWindowLongPtrW', user32.GetWindowLongW)
_SetWindowLong = getattr(user32, 'SetWindowLongPtrW', user32.SetWindowLongW)
_GetWindowLong.argtypes = [ctypes.c_void_p, ctypes.c_int]
_SetWindowLong.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]


class _BLENDFUNCTION(ctypes.Structure):
    _fields_ = [('BlendOp', ctypes.c_ubyte), ('BlendFlags', ctypes.c_ubyte),
                ('SourceConstantAlpha', ctypes.c_ubyte), ('AlphaFormat', ctypes.c_ubyte)]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', ctypes.c_long),
                ('biHeight', ctypes.c_long), ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long), ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)]


user32.UpdateLayeredWindow.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_void_p, ctypes.POINTER(wintypes.SIZE),
    ctypes.c_void_p, ctypes.POINTER(wintypes.POINT),
    wintypes.DWORD, ctypes.POINTER(_BLENDFUNCTION), wintypes.DWORD,
]


def load_rgba(path: Path | str) -> tuple[int, int, bytearray]:
    """Decode a non-interlaced 8-bit RGBA PNG. Returns (w, h, rgba bytes)."""
    data = Path(path).read_bytes()
    pos = 8
    idat = b''
    w = h = colortype = None
    while pos < len(data):
        ln, typ = struct.unpack('>I4s', data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + ln]
        if typ == b'IHDR':
            w, h, bitdepth, colortype = struct.unpack('>IIBB', chunk[:10])
        elif typ == b'IDAT':
            idat += chunk
        pos += 12 + ln
    if colortype != 6:
        raise ValueError(f'{path}: expected RGBA PNG (colortype 6), got {colortype}')

    raw = zlib.decompress(idat)
    bpp = 4
    stride = w * bpp
    out = bytearray()
    prev = bytearray(stride)
    i = 0
    for _ in range(h):
        f = raw[i]; i += 1
        line = bytearray(raw[i:i + stride]); i += stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        out += line
        prev = line
    return w, h, out


def to_premultiplied_bgra(w: int, h: int, rgba: bytearray) -> bytes:
    """RGBA -> premultiplied BGRA, as UpdateLayeredWindow requires."""
    buf = bytearray(len(rgba))
    for i in range(0, len(rgba), 4):
        r, g, b, a = rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3]
        buf[i] = b * a // 255
        buf[i + 1] = g * a // 255
        buf[i + 2] = r * a // 255
        buf[i + 3] = a
    return bytes(buf)


class LayeredCanvas:
    """Owns a memory DC + DIB section; pushes BGRA frames to a layered hwnd."""

    def __init__(self, tk_winfo_id: int, w: int, h: int) -> None:
        self.w, self.h = w, h
        self.hwnd = user32.GetAncestor(tk_winfo_id, GA_ROOT)
        style = _GetWindowLong(self.hwnd, GWL_EXSTYLE)
        _SetWindowLong(self.hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)

        bmi = _BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h  # negative = top-down rows, matching PNG order
        bmi.biPlanes = 1
        bmi.biBitCount = 32

        screen = user32.GetDC(None)
        self._memdc = gdi32.CreateCompatibleDC(screen)
        user32.ReleaseDC(None, screen)
        self._bits = ctypes.c_void_p()
        self._dib = gdi32.CreateDIBSection(None, ctypes.byref(bmi), 0,
                                           ctypes.byref(self._bits), None, 0)
        if not self._dib:
            raise OSError('CreateDIBSection failed')
        gdi32.SelectObject(self._memdc, self._dib)

    def dispose(self) -> None:
        """Release the memory DC and DIB (call before replacing the canvas)."""
        gdi32.DeleteDC(self._memdc)
        gdi32.DeleteObject(self._dib)

    def draw(self, bgra: bytes) -> None:
        ctypes.memmove(self._bits, bgra, len(bgra))
        size = wintypes.SIZE(self.w, self.h)
        src = wintypes.POINT(0, 0)
        blend = _BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(self.hwnd, None, None, ctypes.byref(size),
                                   self._memdc, ctypes.byref(src), 0,
                                   ctypes.byref(blend), ULW_ALPHA)
