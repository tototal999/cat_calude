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

import ctypes
import json
import logging
import logging.handlers
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path

import api
import spritecat
import winalpha

# Unique enough to not collide with an unrelated app's mutex on the same machine.
_SINGLE_INSTANCE_MUTEX_NAME = 'ClaudeCat_SingleInstance_5f3a9c1e'
_ERROR_ALREADY_EXISTS = 183
_mutex_handle = None


def _acquire_single_instance_lock() -> bool:
    """True if this is the only running instance (Windows named mutex).

    Multiple instances would each poll the usage API independently
    (multiplying load against an endpoint that already rate-limits hard),
    stack identical cats at the same default position, and fight over the
    same rotating log file - so only one instance should run at a time.
    """
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, _SINGLE_INSTANCE_MUTEX_NAME)
    if not handle:
        return True  # couldn't check (unexpected) - don't block the user over it
    if ctypes.windll.kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
        ctypes.windll.kernel32.CloseHandle(handle)
        return False
    global _mutex_handle
    _mutex_handle = handle  # keep alive for the process lifetime, released on exit
    return True

# ---- Tunables (edit here, no config file by design) -----------------------
POLL_INTERVAL = 180          # seconds; do NOT go lower (endpoint 429s hard)
QUOTA_FIELD = 'five_hour'    # which quota drives the cat (session usage)
WEEKLY_FIELD = 'seven_day'   # weekly quota, shown on the badge (often the real wall)
CAT_SIZE = 128               # startup size px; changeable from the right-click menu
SIZE_CHOICES = (64, 96, 128, 160, 192, 256)   # right-click menu size options
POLL_CHOICES = (180, 300)    # right-click menu poll interval options; the endpoint
                             # rate-limits hard below 180s, so no faster option

# The --windowed exe has no console, so print()/stderr vanish silently -
# everything worth diagnosing goes to this file instead (rotated, 3x512KB).
LOG_DIR = Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'ClaudeCat'
LOG_FILE = LOG_DIR / 'claudecat.log'
CONFIG_FILE = LOG_DIR / 'config.json'   # persisted user settings (skin/size/...)


def _setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=512 * 1024, backupCount=2, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    log = logging.getLogger('claudecat')
    log.setLevel(logging.INFO)
    log.addHandler(handler)
    return log


logger = _setup_logging()


def _load_config() -> dict:
    """Read persisted settings; missing/corrupt file just means defaults."""
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

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

        # User-toggleable options (right-click menu), seeded from config.json
        cfg = _load_config()
        skin = cfg.get('skin', spritecat.DEFAULT_SKIN)
        if skin not in spritecat.list_skins():
            skin = spritecat.DEFAULT_SKIN  # skin folder was renamed/removed
        size = cfg.get('size', CAT_SIZE)
        if size not in SIZE_CHOICES:
            size = CAT_SIZE
        poll = cfg.get('poll_interval', POLL_INTERVAL)
        if poll not in POLL_CHOICES:
            poll = POLL_INTERVAL  # also drops a stale 60s from older configs
        self.topmost = tk.BooleanVar(value=bool(cfg.get('topmost', True)))
        self.show_pct = tk.BooleanVar(value=bool(cfg.get('show_pct', True)))
        self.cat_size = tk.IntVar(value=size)
        self.facing_right = tk.BooleanVar(value=bool(cfg.get('facing_right', False)))
        self.poll_interval = tk.IntVar(value=poll)
        self.current_skin = tk.StringVar(value=skin)
        # 'live' | 'error' | 'full': lets you preview the sleep/frozen poses
        # from the right-click menu instead of waiting for the real thing.
        # Deliberately not persisted - a forgotten forced state would look
        # like a permanently broken cat on the next start.
        self.debug_state = tk.StringVar(value='live')

        self.root.wm_attributes('-topmost', self.topmost.get())
        self.w = self.h = size
        self._render_cat()

        # State shared between poll thread and UI loop
        self.usage_pct: float | None = None   # None = not fetched yet
        self.weekly_pct: float | None = None
        self.error: str | None = None
        self.resets_at: str | None = None
        self.weekly_resets_at: str | None = None
        self._frame_idx = 0
        self._refreshing_token = False

        # Last saved position, clamped on-screen; else bottom-right corner
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = cfg.get('x', sw - self.w - 40)
        y = cfg.get('y', sh - self.h - 140)
        if not (isinstance(x, int) and isinstance(y, int)
                and -self.w < x < sw and -self.h < y < sh):
            x, y = sw - self.w - 40, sh - self.h - 140
        self.root.geometry(f'{self.w}x{self.h}+{x}+{y}')
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
        self._last_badge_state: tuple[str, str, str] | None = None
        self._place_badge()

        self._bind_mouse()
        self._start_poll_thread()
        self._animate()
        logger.info('started: skin=%s size=%d poll_interval=%d',
                    self.current_skin.get(), self.w, self.poll_interval.get())

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

    def _save_config(self) -> None:
        cfg = {
            'skin': self.current_skin.get(),
            'size': self.cat_size.get(),
            'facing_right': self.facing_right.get(),
            'poll_interval': self.poll_interval.get(),
            'topmost': self.topmost.get(),
            'show_pct': self.show_pct.get(),
            'x': self.root.winfo_x(),
            'y': self.root.winfo_y(),
        }
        try:
            CONFIG_FILE.write_text(json.dumps(cfg, indent=1), encoding='utf-8')
        except OSError:
            logger.exception('could not save config')

    def _quit(self) -> None:
        self._save_config()  # position is only captured here, on clean exit
        self.root.destroy()

    def _set_topmost(self) -> None:
        on = self.topmost.get()
        self.root.wm_attributes('-topmost', on)
        self.badge_win.wm_attributes('-topmost', on)
        self._save_config()

    def _render_cat(self) -> None:
        (self.idle_buffer, self.frame_buffers, self.sleep_frames,
         self.error_frames) = spritecat.load_sprite_frames(
            self.cat_size.get(),
            facing='right' if self.facing_right.get() else 'left',
            skin=self.current_skin.get())
        self._error_frame_idx = 0

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
        self._save_config()

    def _menu(self, e: tk.Event) -> None:
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label=self._status_text(), state='disabled')
        m.add_command(label='Refresh now', command=self._poll_once_async)
        m.add_separator()
        m.add_checkbutton(label='Always on top', variable=self.topmost,
                          command=self._set_topmost)
        m.add_checkbutton(label='Show usage %', variable=self.show_pct,
                          command=self._save_config)
        size_menu = tk.Menu(m, tearoff=0)
        for s in SIZE_CHOICES:
            size_menu.add_radiobutton(label=f'{s} px', variable=self.cat_size,
                                      value=s, command=self._apply_look)
        m.add_cascade(label='Size', menu=size_menu)
        poll_menu = tk.Menu(m, tearoff=0)
        for s in POLL_CHOICES:
            poll_menu.add_radiobutton(label=f'{s} sec', variable=self.poll_interval,
                                      value=s, command=self._save_config)
        m.add_cascade(label='Refresh', menu=poll_menu)
        skin_menu = tk.Menu(m, tearoff=0)
        for name in spritecat.list_skins():
            skin_menu.add_radiobutton(label=name, variable=self.current_skin,
                                      value=name, command=self._apply_look)
        m.add_cascade(label='Skin', menu=skin_menu)
        m.add_checkbutton(label='Face right', variable=self.facing_right,
                          command=self._apply_look)
        test_menu = tk.Menu(m, tearoff=0)
        test_menu.add_radiobutton(label='Live (normal)', variable=self.debug_state, value='live')
        test_menu.add_radiobutton(label='Force error', variable=self.debug_state, value='error')
        test_menu.add_radiobutton(label='Force 100% (exhausted)', variable=self.debug_state, value='full')
        m.add_cascade(label='Test', menu=test_menu)
        m.add_separator()
        m.add_command(label='Show log', command=self._show_log)
        m.add_command(label='Quit', command=self._quit)
        m.tk_popup(e.x_root, e.y_root)

    def _show_log(self) -> None:
        """Show the log in-app: Explorer navigation to AppData\\Local can be
        blocked by endpoint-security policy on locked-down machines, so this
        doesn't rely on os.startfile - the text is just selectable/copyable."""
        try:
            content = LOG_FILE.read_text(encoding='utf-8') or '(log is empty)'
        except OSError as exc:
            content = f'(could not read log file: {exc})'

        win = tk.Toplevel(self.root)
        win.title(f'ClaudeCat log - {LOG_FILE}')
        win.geometry('700x400')
        text = tk.Text(win, wrap='none')
        text.insert('1.0', content)
        text.configure(state='disabled')
        text.pack(fill='both', expand=True)
        text.see('end')

    def _effective_error(self) -> str | None:
        """Real error, or a debug-menu override for previewing that state."""
        if self.debug_state.get() == 'error':
            return 'DEBUG: forced error'
        return self.error

    def _effective_usage(self) -> float | None:
        """Real usage %, or a debug-menu override for previewing that state."""
        ds = self.debug_state.get()
        if ds == 'error':
            return None
        if ds == 'full':
            return 100.0
        return self.usage_pct

    def _status_text(self) -> str:
        error = self._effective_error()
        usage = self._effective_usage()
        if error:
            return f'! {error}'
        if usage is None:
            return 'Fetching usage...'
        text = f'Session: {usage:.0f}%'
        reset = self._to_local_hhmm(self.resets_at)
        if reset:
            text += f'  (resets {reset})'
        if self.weekly_pct is not None:
            text += f'  |  Week: {self.weekly_pct:.0f}%'
            weekly_reset = self._to_local_hhmm(self.weekly_resets_at, with_date=True)
            if weekly_reset:
                text += f' (resets {weekly_reset})'
        return text

    @staticmethod
    def _to_local_hhmm(iso: str | None, with_date: bool = False) -> str | None:
        """ISO timestamp -> local-timezone 'HH:MM' (or 'M/D HH:MM'), or None."""
        if not iso:
            return None
        try:
            dt = datetime.fromisoformat(iso).astimezone()
            return dt.strftime('%m/%d %H:%M' if with_date else '%H:%M')
        except ValueError:
            return None

    def _update_badge(self) -> None:
        if not self.show_pct.get():
            self.badge_win.withdraw()
            return
        error = self._effective_error()
        usage = self._effective_usage()
        if error:
            state = (' ! ', '#aa2222', '#ffffff')
        elif usage is None:
            state = ('...', '#222222', '#ffffff')
        else:
            text = f' {usage:.0f}%'
            if self.weekly_pct is not None:
                text += f' W{self.weekly_pct:.0f}%'
            reset = self._to_local_hhmm(self.resets_at)
            text += f' | {reset} ' if reset else ' '
            # Red warning when either quota is nearly gone - the weekly cap
            # is often what actually locks you out, not the 5h session.
            hot = usage > 90 or (self.weekly_pct or 0) > 90
            state = (text, '#3a1111', '#ff4444') if hot \
                else (text, '#222222', '#ffffff')
        # Reposition/reconfigure only on real change - this runs every
        # animation tick (as often as every 80ms), and re-asserting a
        # -topmost window's geometry that often forces DWM to recomposite
        # the whole screen, which is what causes other apps to visibly lag.
        if state != self._last_badge_state:
            text, bg, fg = state
            self.badge.configure(text=text, bg=bg, fg=fg)
            self._last_badge_state = state
        if self.badge_win.state() == 'withdrawn':
            self.badge_win.deiconify()
            self._place_badge()

    # ---- Animation loop ---------------------------------------------------

    def _should_sleep(self) -> bool:
        """Sleep pose wins over the run cycle when the skin has one and the
        session quota is fully used up (100%). Errors / no data yet still
        play the normal gentle-default animation - sleep means 'quota is
        exhausted', not 'can't currently tell what the quota is'."""
        if not self.sleep_frames:
            return False
        usage = self._effective_usage()
        return usage is not None and usage >= 100

    def _should_show_error_pose(self) -> bool:
        """Error pose (if the skin has one) replaces the gentle default
        animation when there's an error, or no usage data has come in yet."""
        if not self.error_frames:
            return False
        return bool(self._effective_error()) or self._effective_usage() is None

    def _frame_interval(self) -> int | None:
        """Map current usage % to a frame interval (ms), or None if frozen."""
        error = self._effective_error()
        usage = self._effective_usage()
        if error or usage is None:
            return 300  # API unavailable: gentle default animation
        for upper, interval in SPEED_TABLE:
            if usage <= upper:
                return interval
        return None

    def _animate(self) -> None:
        self._update_badge()
        if self._should_sleep():
            # Static, not animated: one sleep frame (the first, by filename
            # sort - e.g. cowcat_sleep_07.png) is enough.
            self.canvas.draw(self.sleep_frames[0])
            self.root.after(500, self._animate)
            return
        if self._should_show_error_pose():
            self._error_frame_idx = (self._error_frame_idx + 1) % len(self.error_frames)
            self.canvas.draw(self.error_frames[self._error_frame_idx])
            self.root.after(500, self._animate)
            return
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
            logger.error('poll failed: %s', self.error)
            if data.get('auth_error'):
                self._try_refresh_token()
            if data.get('rate_limited'):
                # Back off beyond Retry-After; this endpoint punishes eagerness
                return max(data.get('retry_after', 0), self.poll_interval.get() * 2)
            return self.poll_interval.get()

        quota = data.get(QUOTA_FIELD)
        if not isinstance(quota, dict) or quota.get('utilization') is None:
            self.error = f'Quota field "{QUOTA_FIELD}" missing in API response'
            logger.error('%s. Fields: %s', self.error, list(data))
            return self.poll_interval.get()

        was_error = self.error is not None
        self.error = None
        self.usage_pct = float(quota['utilization'])
        self.resets_at = quota.get('resets_at')

        # Weekly quota is display-only (badge/menu): the session quota drives
        # the cat, but the weekly cap is often the wall you actually hit first.
        weekly = data.get(WEEKLY_FIELD)
        if isinstance(weekly, dict) and weekly.get('utilization') is not None:
            self.weekly_pct = float(weekly['utilization'])
            self.weekly_resets_at = weekly.get('resets_at')
        else:
            self.weekly_pct = None
            self.weekly_resets_at = None

        if was_error:
            logger.info('poll recovered: usage=%.0f%%', self.usage_pct)
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
            except Exception:
                logger.exception('token refresh failed')
            finally:
                self._refreshing_token = False

        threading.Thread(target=run, daemon=True).start()


if __name__ == '__main__':
    if not _acquire_single_instance_lock():
        # Silent exit: a withdrawn Tk root can't reliably host a modal
        # messagebox (it may not block/show at all on some setups), and
        # the user already has a cat on screen - no need to interrupt them.
        logger.info('another instance is already running; exiting')
        sys.exit(0)

    try:
        ClaudeCat().root.mainloop()
    except Exception:
        logger.exception('crashed')
        raise
