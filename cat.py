"""
ClaudeCat - Desktop pet whose running speed reflects Claude usage.
===================================================================

A borderless, always-on-top window showing a vector cat (vectorcat.py,
GDI+) rendered with true per-pixel alpha (winalpha.py,
UpdateLayeredWindow).  The cat's animation speed maps to the 5-hour
session utilization fetched from the Anthropic OAuth usage API (via
api.py, borrowed from jens-duttke/usage-monitor-for-claude, MIT).

Two independent loops:
- Animation loop: swaps frames every N ms (N depends on usage %).
- Poll loop:      fetches usage every POLL_INTERVAL seconds.

Run:  python cat.py        (Windows, Python 3.10+, `pip install requests`)
Quit: right-click the cat -> Quit
Move: left-drag the cat (or the % badge).

Success criteria (QA):
  QA_RESULT|STATUS:PASS|EXPECTED:cat speed changes with session usage
  within one poll cycle|ACTUAL:verify manually after running claude
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime

import api
import spritecat
import winalpha

# ---- Tunables (edit here, no config file by design) -----------------------
POLL_INTERVAL = 180          # seconds; do NOT go lower (endpoint 429s hard)
QUOTA_FIELD = 'five_hour'    # which quota drives the cat (session usage)
CAT_SIZE = 128               # startup size px; changeable from the right-click menu
SIZE_CHOICES = (64, 96, 128, 160, 192, 256)   # right-click menu size options
POLL_CHOICES = (60, 180, 300)                  # right-click menu poll interval options (seconds)

# usage % (upper bound, inclusive) -> frame interval in ms; None = frozen
SPEED_TABLE = [
    (25, 400),    # stroll
    (50, 250),    # trot
    (75, 150),    # run
    (95, 80),     # sprint
    (100, None),  # exhausted: cat freezes
]
# ---------------------------------------------------------------------------


class ClaudeCat:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.wm_attributes('-topmost', True)

        # User-toggleable options (right-click menu)
        self.topmost = tk.BooleanVar(value=True)
        self.show_pct = tk.BooleanVar(value=True)
        self.cat_size = tk.IntVar(value=CAT_SIZE)
        self.facing_right = tk.BooleanVar(value=False)
        self.poll_interval = tk.IntVar(value=POLL_INTERVAL)
        self.current_skin = tk.StringVar(value=spritecat.DEFAULT_SKIN)

        self.w = self.h = CAT_SIZE
        self._render_cat()

        # State shared between poll thread and UI loop
        self.usage_pct: float | None = None   # None = not fetched yet
        self.error: str | None = None
        self.resets_at: str | None = None
        self._frame_idx = 0
        self._refreshing_token = False

        # Bottom-right corner by default
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f'{self.w}x{self.h}+{sw - self.w - 40}+{sh - self.h - 140}')
        self.root.update()  # window must be mapped before we grab its hwnd
        self.canvas = winalpha.LayeredCanvas(self.root.winfo_id(), self.w, self.h)
        self.canvas.draw(self.idle_buffer)

        # % badge: a separate opaque mini-window below the cat (a layered
        # window's content comes only from UpdateLayeredWindow, so tkinter
        # widgets can't render inside the cat window itself)
        self.badge_win = tk.Toplevel(self.root)
        self.badge_win.overrideredirect(True)
        self.badge_win.wm_attributes('-topmost', True)
        self.badge = tk.Label(self.badge_win, text='...', bg='#222222',
                              fg='#ffffff', font=('Segoe UI', 9, 'bold'), padx=4)
        self.badge.pack()
        self._place_badge()

        self._bind_mouse()
        self._start_poll_thread()
        self._animate()

    # ---- UI wiring --------------------------------------------------------

    def _bind_mouse(self) -> None:
        for win in (self.root, self.badge_win):
            win.bind('<Button-1>', self._drag_start)
            win.bind('<B1-Motion>', self._drag_move)
            win.bind('<Button-3>', self._menu)

    def _drag_start(self, e: tk.Event) -> None:
        self._dx = e.x_root - self.root.winfo_x()
        self._dy = e.y_root - self.root.winfo_y()

    def _drag_move(self, e: tk.Event) -> None:
        self.root.geometry(f'+{e.x_root - self._dx}+{e.y_root - self._dy}')
        self._place_badge()

    def _place_badge(self) -> None:
        self.badge_win.update_idletasks()
        bw = self.badge_win.winfo_reqwidth()
        x = self.root.winfo_x() + (self.w - bw) // 2
        y = self.root.winfo_y() + self.h + 2
        self.badge_win.geometry(f'+{x}+{y}')

    def _set_topmost(self) -> None:
        on = self.topmost.get()
        self.root.wm_attributes('-topmost', on)
        self.badge_win.wm_attributes('-topmost', on)

    def _render_cat(self) -> None:
        self.idle_buffer, self.frame_buffers = spritecat.load_sprite_frames(
            self.cat_size.get(),
            facing='right' if self.facing_right.get() else 'left',
            skin=self.current_skin.get())

    def _apply_look(self) -> None:
        """Re-render after a size/direction change from the menu."""
        self._render_cat()
        size = self.cat_size.get()
        if size != self.w:
            # The DIB is fixed-size: replace canvas + window geometry
            self.w = self.h = size
            self.canvas.dispose()
            self.root.geometry(f'{size}x{size}')
            self.root.update_idletasks()
            self.canvas = winalpha.LayeredCanvas(self.root.winfo_id(), size, size)
        self.canvas.draw(self.idle_buffer)  # next animate tick takes over
        self._place_badge()

    def _menu(self, e: tk.Event) -> None:
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label=self._status_text(), state='disabled')
        m.add_command(label='Refresh now', command=self._poll_once_async)
        m.add_separator()
        m.add_checkbutton(label='Always on top', variable=self.topmost,
                          command=self._set_topmost)
        m.add_checkbutton(label='Show usage %', variable=self.show_pct)
        size_menu = tk.Menu(m, tearoff=0)
        for s in SIZE_CHOICES:
            size_menu.add_radiobutton(label=f'{s} px', variable=self.cat_size,
                                      value=s, command=self._apply_look)
        m.add_cascade(label='Size', menu=size_menu)
        poll_menu = tk.Menu(m, tearoff=0)
        for s in POLL_CHOICES:
            poll_menu.add_radiobutton(label=f'{s} sec', variable=self.poll_interval,
                                      value=s)
        m.add_cascade(label='Refresh', menu=poll_menu)
        skin_menu = tk.Menu(m, tearoff=0)
        for name in spritecat.list_skins():
            skin_menu.add_radiobutton(label=name, variable=self.current_skin,
                                      value=name, command=self._apply_look)
        m.add_cascade(label='Skin', menu=skin_menu)
        m.add_checkbutton(label='Face right', variable=self.facing_right,
                          command=self._apply_look)
        m.add_separator()
        m.add_command(label='Quit', command=self.root.destroy)
        m.tk_popup(e.x_root, e.y_root)

    def _status_text(self) -> str:
        if self.error:
            return f'! {self.error}'
        if self.usage_pct is None:
            return 'Fetching usage...'
        text = f'Session: {self.usage_pct:.0f}%'
        reset = self._reset_hhmm()
        if reset:
            text += f'  (resets {reset})'
        return text

    def _reset_hhmm(self) -> str | None:
        """Session reset time as local-timezone HH:MM, or None."""
        if not self.resets_at:
            return None
        try:
            return datetime.fromisoformat(self.resets_at).astimezone().strftime('%H:%M')
        except ValueError:
            return None

    def _update_badge(self) -> None:
        if not self.show_pct.get():
            self.badge_win.withdraw()
            return
        if self.error:
            self.badge.configure(text=' ! ', bg='#aa2222')
        elif self.usage_pct is None:
            self.badge.configure(text='...', bg='#222222')
        else:
            reset = self._reset_hhmm()
            text = f' {self.usage_pct:.0f}%' + (f' | {reset} ' if reset else ' ')
            if self.usage_pct > 90:
                self.badge.configure(text=text, bg='#3a1111', fg='#ff4444')
            else:
                self.badge.configure(text=text, bg='#222222', fg='#ffffff')
        if self.badge_win.state() == 'withdrawn':
            self.badge_win.deiconify()
        self._place_badge()

    # ---- Animation loop ---------------------------------------------------

    def _frame_interval(self) -> int | None:
        """Map current usage % to a frame interval (ms), or None if frozen."""
        if self.error or self.usage_pct is None:
            return 300  # API unavailable: gentle default animation
        for upper, interval in SPEED_TABLE:
            if self.usage_pct <= upper:
                return interval
        return None

    def _animate(self) -> None:
        self._update_badge()
        interval = self._frame_interval()
        if interval is None:
            # Frozen: show the standing pose and re-check twice a second
            self.canvas.draw(self.idle_buffer)
            self.root.after(500, self._animate)
            return
        self._frame_idx = (self._frame_idx + 1) % len(self.frame_buffers)
        self.canvas.draw(self.frame_buffers[self._frame_idx])
        self.root.after(interval, self._animate)

    # ---- Poll loop --------------------------------------------------------

    def _start_poll_thread(self) -> None:
        threading.Thread(target=self._poll_forever, daemon=True).start()

    def _poll_once_async(self) -> None:
        threading.Thread(target=self._poll_once, daemon=True).start()

    def _poll_forever(self) -> None:
        while True:
            wait = self._poll_once()
            time.sleep(wait)

    def _poll_once(self) -> float:
        """Fetch usage once; update shared state. Returns next wait (s)."""
        data = api.fetch_usage()

        if 'error' in data:
            self.error = data['error']
            print(f'[claude-cat] poll failed: {self.error}', file=sys.stderr)
            if data.get('auth_error'):
                self._try_refresh_token()
            if data.get('rate_limited'):
                # Back off beyond Retry-After; this endpoint punishes eagerness
                return max(data.get('retry_after', 0), self.poll_interval.get() * 2)
            return self.poll_interval.get()

        quota = data.get(QUOTA_FIELD)
        if not isinstance(quota, dict) or quota.get('utilization') is None:
            self.error = f'Quota field "{QUOTA_FIELD}" missing in API response'
            print(f'[claude-cat] {self.error}. Fields: {list(data)}', file=sys.stderr)
            return self.poll_interval.get()

        self.error = None
        self.usage_pct = float(quota['utilization'])
        self.resets_at = quota.get('resets_at')
        return self.poll_interval.get()

    def _try_refresh_token(self) -> None:
        """On auth expiry, run `claude update` once to refresh the token
        (same approach as usage-monitor-for-claude). Non-blocking, guarded."""
        if self._refreshing_token:
            return
        self._refreshing_token = True

        def run() -> None:
            try:
                subprocess.run(
                    ['claude', 'update'],
                    capture_output=True, timeout=120, shell=(sys.platform == 'win32'),
                )
            except Exception as exc:
                print(f'[claude-cat] token refresh failed: {exc}', file=sys.stderr)
            finally:
                self._refreshing_token = False

        threading.Thread(target=run, daemon=True).start()


if __name__ == '__main__':
    ClaudeCat().root.mainloop()
