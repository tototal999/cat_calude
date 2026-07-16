"""
Vector cat frames rendered with GDI+ (Windows only, pure stdlib).
==================================================================

Replaces the bitmap frames/ sprites: the running cat is defined as
smooth curves (cardinal splines / ellipses / round-capped strokes) and
rasterized at any size with GDI+ anti-aliasing, via ctypes against the
built-in gdiplus.dll.  Output buffers are premultiplied BGRA, exactly
what winalpha.LayeredCanvas.draw() expects.

The run cycle is parametric: each frame's leg/tail/body positions are
functions of the cycle phase t in [0, 1), so the frame count can be
raised for smoother motion at no asset cost.  The cat is authored in
unit space facing left; ``facing='right'`` mirrors every x coordinate.
"""
from __future__ import annotations

import ctypes
import math
from ctypes import wintypes

_gdip = ctypes.windll.gdiplus

# GDI+ enums / constants
_PixelFormat32bppPARGB = 0x000E200B
_SmoothingModeAntiAlias = 4
_UnitPixel = 2
_LineCapRound = 2
_FillModeWinding = 1


class _GdiplusStartupInput(ctypes.Structure):
    _fields_ = [('GdiplusVersion', ctypes.c_uint32),
                ('DebugEventCallback', ctypes.c_void_p),
                ('SuppressBackgroundThread', wintypes.BOOL),
                ('SuppressExternalCodecs', wintypes.BOOL)]


class _PointF(ctypes.Structure):
    _fields_ = [('x', ctypes.c_float), ('y', ctypes.c_float)]


def _pts(seq) -> ctypes.Array:
    arr = (_PointF * len(seq))()
    for i, (x, y) in enumerate(seq):
        arr[i] = _PointF(x, y)
    return arr


class _Renderer:
    """One GDI+ bitmap/graphics pair drawing into a caller-owned buffer."""

    def __init__(self, size: int, argb: int) -> None:
        self.size = size
        self.stride = size * 4
        self.buf = ctypes.create_string_buffer(size * self.stride)
        self.bitmap = ctypes.c_void_p()
        _gdip.GdipCreateBitmapFromScan0(
            size, size, self.stride, _PixelFormat32bppPARGB,
            ctypes.cast(self.buf, ctypes.c_void_p), ctypes.byref(self.bitmap))
        self.g = ctypes.c_void_p()
        _gdip.GdipGetImageGraphicsContext(self.bitmap, ctypes.byref(self.g))
        _gdip.GdipSetSmoothingMode(self.g, _SmoothingModeAntiAlias)

        self.brush = ctypes.c_void_p()
        _gdip.GdipCreateSolidFill(ctypes.c_uint32(argb), ctypes.byref(self.brush))
        self.pen = ctypes.c_void_p()
        _gdip.GdipCreatePen1(ctypes.c_uint32(argb), ctypes.c_float(1.0),
                             _UnitPixel, ctypes.byref(self.pen))
        _gdip.GdipSetPenStartCap(self.pen, _LineCapRound)
        _gdip.GdipSetPenEndCap(self.pen, _LineCapRound)

    def set_color(self, argb: int) -> None:
        _gdip.GdipSetSolidFillColor(self.brush, ctypes.c_uint32(argb))
        _gdip.GdipSetPenColor(self.pen, ctypes.c_uint32(argb))

    def clear(self) -> None:
        _gdip.GdipGraphicsClear(self.g, ctypes.c_uint32(0))

    def fill_closed_curve(self, points, tension: float = 0.6) -> None:
        arr = _pts(points)
        _gdip.GdipFillClosedCurve2(self.g, self.brush, arr, len(arr),
                                   ctypes.c_float(tension), _FillModeWinding)

    def fill_polygon(self, points) -> None:
        arr = _pts(points)
        _gdip.GdipFillPolygon(self.g, self.brush, arr, len(arr), _FillModeWinding)

    def fill_ellipse(self, cx, cy, rx, ry) -> None:
        _gdip.GdipFillEllipse(self.g, self.brush,
                              ctypes.c_float(cx - rx), ctypes.c_float(cy - ry),
                              ctypes.c_float(rx * 2), ctypes.c_float(ry * 2))

    def stroke(self, points, width: float, tension: float = 0.5) -> None:
        _gdip.GdipSetPenWidth(self.pen, ctypes.c_float(width))
        arr = _pts(points)
        if len(arr) == 2:
            _gdip.GdipDrawLine(self.g, self.pen,
                               ctypes.c_float(points[0][0]), ctypes.c_float(points[0][1]),
                               ctypes.c_float(points[1][0]), ctypes.c_float(points[1][1]))
        else:
            _gdip.GdipDrawCurve2(self.g, self.pen, arr, len(arr),
                                 ctypes.c_float(tension))

    def snapshot(self) -> bytes:
        _gdip.GdipFlush(self.g, 1)  # FlushIntentionSync
        return self.buf.raw

    def dispose(self) -> None:
        _gdip.GdipDeletePen(self.pen)
        _gdip.GdipDeleteBrush(self.brush)
        _gdip.GdipDeleteGraphics(self.g)
        _gdip.GdipDisposeImage(self.bitmap)


def _draw_cat(r: _Renderer, t: float | None, flip: bool,
              cat_argb: int, eye_argb: int) -> None:
    """Draw one pose. t in [0,1) = run-cycle phase; None = standing idle.

    Authored in unit space (0..1, y down) facing left; flip mirrors x.
    """
    S = r.size
    X = (lambda x: 1.0 - x) if flip else (lambda x: x)

    def P(x: float, y: float) -> tuple[float, float]:
        return (X(x) * S, y * S)

    run = t is not None
    ph = t or 0.0
    bob = 0.018 * math.sin(2 * math.pi * ph * 2) if run else 0.0

    r.set_color(cat_argb)

    # Body: elongated blob, slightly arched back
    body = [(0.30, 0.46 + bob), (0.38, 0.375 + bob), (0.56, 0.345 + bob),
            (0.74, 0.365 + bob), (0.84, 0.44 + bob), (0.80, 0.545 + bob),
            (0.60, 0.575 + bob), (0.40, 0.555 + bob)]
    r.fill_closed_curve([P(x, y) for x, y in body], tension=0.55)

    # Head + ears
    hx, hy = 0.225, 0.375 + bob * 0.6
    hcx, hcy = P(hx, hy)
    r.fill_ellipse(hcx, hcy, 0.115 * S, 0.105 * S)
    r.fill_polygon([P(0.145, hy - 0.055), P(0.115, hy - 0.20), P(0.225, hy - 0.085)])
    r.fill_polygon([P(0.250, hy - 0.09), P(0.315, hy - 0.195), P(0.330, hy - 0.045)])

    # Whiskers: three strokes fanning forward from the muzzle
    wx, wy = 0.125, hy + 0.035
    for tip_x, tip_y in ((0.015, hy - 0.005), (0.005, hy + 0.035), (0.015, hy + 0.075)):
        r.stroke([P(wx, wy), P(tip_x, tip_y)], width=0.011 * S)

    # Tail: wavy stroke off the rump
    wag = 0.05 * math.sin(2 * math.pi * ph) if run else 0.0
    tail = [(0.815, 0.455 + bob), (0.90, 0.38 + bob + wag * 0.3),
            (0.955, 0.28 + wag), (0.985, 0.20 + wag * 1.5)]
    r.stroke([P(x, y) for x, y in tail], width=0.052 * S, tension=0.5)

    # Legs: round-capped strokes from shoulder/hip to parametric feet
    legs = [
        # (joint x, joint y, phase offset, reach)
        (0.375, 0.545, 0.00, 0.20),   # front near
        (0.415, 0.545, 0.15, 0.18),   # front far
        (0.735, 0.545, 0.50, 0.22),   # back near
        (0.775, 0.545, 0.65, 0.20),   # back far
    ]
    for jx, jy, off, reach in legs:
        jy += bob
        if run:
            theta = 0.72 * math.sin(2 * math.pi * (ph + off))
            fx = jx - reach * math.sin(theta)          # forward = toward the face
            fy = jy + reach * (0.92 * math.cos(theta) + 0.08)
        else:
            fx, fy = jx, jy + reach
        r.stroke([P(jx, jy), P(fx, fy)], width=0.055 * S)

    # Eye (side view -> one visible) + vertical slit pupil
    ex, ey = P(0.175, hy - 0.018)
    r.set_color(eye_argb)
    r.fill_ellipse(ex, ey, 0.026 * S, 0.030 * S)
    r.set_color(cat_argb)
    r.fill_ellipse(ex, ey, 0.010 * S, 0.024 * S)


def render_frames(size: int, color: str, frame_count: int,
                  facing: str = 'left',
                  eye_color: str = '#ffcc00') -> tuple[bytes, list[bytes]]:
    """Rasterize the cat. Returns (idle_frame, run_frames) as BGRA buffers.

    size:   canvas width/height in px
    color:  cat silhouette '#rrggbb'
    facing: 'left' or 'right'
    """
    cat_argb = 0xFF000000 | int(color.lstrip('#'), 16)
    eye_argb = 0xFF000000 | int(eye_color.lstrip('#'), 16)
    flip = facing == 'right'

    token = ctypes.c_void_p()
    startup = _GdiplusStartupInput(1, None, False, False)
    _gdip.GdiplusStartup(ctypes.byref(token), ctypes.byref(startup), None)
    try:
        r = _Renderer(size, cat_argb)
        r.clear()
        _draw_cat(r, None, flip, cat_argb, eye_argb)
        idle = r.snapshot()
        frames = []
        for i in range(frame_count):
            r.clear()
            _draw_cat(r, i / frame_count, flip, cat_argb, eye_argb)
            frames.append(r.snapshot())
        r.dispose()
    finally:
        _gdip.GdiplusShutdown(token)
    return idle, frames
