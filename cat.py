"""
ClaudeCat - Desktop pet whose running speed reflects Claude usage.
===================================================================

A borderless, always-on-top window showing a vector cat (vectorcat.py,
GDI+) rendered with true per-pixel alpha (winalpha.py,
UpdateLayeredWindow).  The cat's animation speed maps to the 5-hour
session utilization fetched from the Anthropic OAuth usage API (via
api.py, borrowed from jens-duttke/usage-monitor-for-claude, MIT).

Loops:
- Animation loop: swaps frames every N ms (N depends on usage %).
- Poll loop:      fetches usage every POLL_INTERVAL seconds (可由選單真停).
- Schedule tick:  every 30s on the tk after() loop (scheduler.py, Part 1).

Threading (spec 1.2, verified by P1-0): the pywebview singleton window owns
the MAIN thread (chat/window.py); this tkinter cat runs in a background
thread started from __main__.

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
from config import settings
LOG_DIR = settings.LOG_DIR
LOG_FILE = settings.LOG_FILE
CONFIG_FILE = settings.CONFIG_FILE
SCHEDULE_FILE = settings.SCHEDULE_FILE
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
from backend.services import llm_service as llm
import scheduler as scheduler_mod
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
# Schedule data lives beside config (NOT the exe dir, which may be read-only);
# spec's file tree shows the source layout, this is the runtime location.
ALERT_BOOST_SECS = 3        # cat speeds up this long when a schedule fires
CARD_AUTOCLOSE_MS = 60_000  # popup cards self-dismiss after 60s


def _setup_logging() -> logging.Logger:
    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=512 * 1024, backupCount=2, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    log = logging.getLogger('claudecat')
    log.setLevel(logging.INFO)
    log.addHandler(handler)
    return log


logger = _setup_logging()




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
        cfg = settings.load_config()
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
        um = cfg.get('usage_monitor', {})
        self.monitor_enabled = tk.BooleanVar(
            value=bool(um.get('enabled', True)) if isinstance(um, dict) else True)
        # 'live' | 'error' | 'full': lets you preview the sleep/frozen poses
        # from the right-click menu instead of waiting for the real thing.
        # Deliberately not persisted - a forgotten forced state would look
        # like a permanently broken cat on the next start.
        self.debug_state = tk.StringVar(value='live')
        self._chat_open = False       # True while chat window is visible
        self._pre_chat_size: int | None = None  # size before shrink

        self.root.wm_attributes('-topmost', self.topmost.get())
        self.w = self.h = size
        self._render_cat()

        # Part 1.5 Interactive config
        self._sleep_min = int(cfg.get('sleep_min', 10))
        self._deep_sleep_min = int(cfg.get('deep_sleep_min', 12))
        self._last_interact = time.time()
        self._drag_start_x = 0
        self._drag_start_y = 0

        # State shared between poll thread and UI loop
        self.usage_pct: float | None = None   # None = not fetched yet
        self.weekly_pct: float | None = None
        self.error: str | None = None
        self.resets_at: str | None = None
        self.weekly_resets_at: str | None = None
        self._frame_idx = 0
        self._refreshing_token = False

        # Monitor availability (spec P1-6): unavailable = no credentials /
        # token unreadable / 3+ consecutive API failures. Popup fires once
        # per False->True transition only; recovery is silent.
        self._consec_failures = 0
        self.monitor_unavailable = False
        self._boost_until = 0.0

        # Popup cards may be requested from the poll thread; they are queued
        # here and materialized on the tk thread by the animation loop.
        self._pending_cards: list[str] = []
        self._cards_lock = threading.Lock()
        self._open_cards: list[tk.Toplevel] = []

        self.scheduler = scheduler_mod.Scheduler(SCHEDULE_FILE)
        if self.scheduler.errors:
            self._queue_card(f'排程檔有 {len(self.scheduler.errors)} 筆錯誤,'
                             f'詳見右鍵選單「排程」')

        # Last saved position, clamped on-screen; else bottom-right corner
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = cfg.get('x', sw - self.w - 40)
        y = cfg.get('y', sh - self.h - 140)
        if not (isinstance(x, int) and isinstance(y, int)
                and -self.w < x < sw and -self.h < y < sh):
            x, y = sw - self.w - 40, sh - self.h - 140
        self.root.geometry(f'{self.w}x{self.h}+{x}+{y}')
        self.root.update()  # window must be mapped before we grab its hwnd
        logger.info('screen=%dx%d requested=(%d,%d) actual=(%d,%d)',
                    sw, sh, x, y, self.root.winfo_x(), self.root.winfo_y())
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
        self.root.after(2000, self._schedule_tick)
        logger.info('started: skin=%s size=%d poll_interval=%d monitor=%s',
                    self.current_skin.get(), self.w, self.poll_interval.get(),
                    self.monitor_enabled.get())

    # ---- UI wiring --------------------------------------------------------

    def _bind_mouse(self) -> None:
        for win in (self.root, self.badge_win):
            win.bind('<Enter>', self._on_hover)
            win.bind('<Button-1>', self._drag_start)
            win.bind('<B1-Motion>', self._drag_move)
            win.bind('<ButtonRelease-1>', self._drag_release)
            win.bind('<Button-3>', self._menu)

    def _on_hover(self, e: tk.Event) -> None:
        self._last_interact = time.time()

    def _drag_start(self, e: tk.Event) -> None:
        self._dx = e.x_root - self.root.winfo_x()
        self._dy = e.y_root - self.root.winfo_y()
        self._drag_start_x = e.x_root
        self._drag_start_y = e.y_root
        self._last_interact = time.time()

    def _drag_move(self, e: tk.Event) -> None:
        self.root.geometry(f'+{e.x_root - self._dx}+{e.y_root - self._dy}')
        self._place_badge()
        self._last_interact = time.time()

    def _drag_release(self, e: tk.Event) -> None:
        self._last_interact = time.time()
        if abs(e.x_root - self._drag_start_x) <= 5 and abs(e.y_root - self._drag_start_y) <= 5:
            self._on_click()

    def _on_click(self) -> None:
        """P1.5-2: Click triggers a small random action (brief sprint here)"""
        self._boost_until = time.time() + 0.3

    def _place_badge(self) -> None:
        self.badge_win.update_idletasks()
        bw = self.badge_win.winfo_reqwidth()
        x = self.root.winfo_x() + (self.w - bw) // 2
        y = self.root.winfo_y() + self.h + 2
        self.badge_win.geometry(f'+{x}+{y}')

    def _save_config(self) -> None:
        """Merge cat-owned keys into config.json, preserving everything
        else (e.g. llm.py's ``llm`` block) - config.json has more than one
        writer, so this must never be a blind full-file overwrite."""
        cfg = settings.load_config()
        cfg.update({
            'skin': self.current_skin.get(),
            'size': self.cat_size.get(),
            'facing_right': self.facing_right.get(),
            'poll_interval': self.poll_interval.get(),
            'topmost': self.topmost.get(),
            'show_pct': self.show_pct.get(),
            'usage_monitor': {'enabled': self.monitor_enabled.get()},
            'x': self.root.winfo_x(),
            'y': self.root.winfo_y(),
        })
        try:
            CONFIG_FILE.write_text(json.dumps(cfg, indent=1, ensure_ascii=False),
                                   encoding='utf-8')
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
        m.add_command(label='排程...', command=self._open_schedule)
        m.add_command(label='交談...', command=self._open_chat)

        skin_menu = tk.Menu(m, tearoff=0)
        for name in spritecat.list_skins():
            skin_menu.add_radiobutton(label=name, variable=self.current_skin,
                                      value=name, command=self._apply_look)
        m.add_cascade(label='Skin', menu=skin_menu)

        m.add_cascade(label='設定', menu=self._build_settings_menu(m))

        test_menu = tk.Menu(m, tearoff=0)
        test_menu.add_radiobutton(label='Live (normal)', variable=self.debug_state, value='live')
        test_menu.add_radiobutton(label='Force error', variable=self.debug_state, value='error')
        test_menu.add_radiobutton(label='Force 100% (exhausted)', variable=self.debug_state, value='full')
        m.add_cascade(label='Test', menu=test_menu)

        m.add_separator()
        m.add_command(label='Show log', command=self._show_log)
        m.add_command(label='Quit', command=self._quit)
        m.tk_popup(e.x_root, e.y_root)

    def _build_settings_menu(self, parent: tk.Menu) -> tk.Menu:
        """Everything that isn't a top-level action lives here, so the
        main right-click menu stays short (spec-adjacent, user-reported:
        too many flat items)."""
        sm = tk.Menu(parent, tearoff=0)
        sm.add_checkbutton(label='Always on top', variable=self.topmost,
                           command=self._set_topmost)
        sm.add_checkbutton(label='Show usage %', variable=self.show_pct,
                           command=self._save_config)
        monitor_label = '用量監控（異常）' if (self.monitor_enabled.get()
                                              and self.monitor_unavailable) else '用量監控'
        sm.add_checkbutton(label=monitor_label, variable=self.monitor_enabled,
                           command=self._toggle_monitor)
        sm.add_checkbutton(label='Face right', variable=self.facing_right,
                           command=self._apply_look)
        sm.add_separator()
        size_menu = tk.Menu(sm, tearoff=0)
        for s in SIZE_CHOICES:
            size_menu.add_radiobutton(label=f'{s} px', variable=self.cat_size,
                                      value=s, command=self._apply_look)
        sm.add_cascade(label='Size', menu=size_menu)
        poll_menu = tk.Menu(sm, tearoff=0)
        for s in POLL_CHOICES:
            poll_menu.add_radiobutton(label=f'{s} sec', variable=self.poll_interval,
                                      value=s, command=self._save_config)
        sm.add_cascade(label='Refresh', menu=poll_menu)
        return sm

    # ---- Schedule + monitor toggle (Part 1) --------------------------------

    def _open_schedule(self) -> None:
        import backend.window_main as chatwin   # lazy: pulls in pywebview
        chatwin.request_open('schedule')

    def _open_chat(self) -> None:
        import backend.window_main as chatwin
        chatwin.request_open('chat')

    def _on_chat_open(self) -> None:
        """Shrink cat to 32px and dock beside the chat window (spec 2.1,
        user-requested: must stay attached to the window, not drift apart)."""
        if self._chat_open:
            return
        self._chat_open = True
        self._pre_chat_size = self.cat_size.get()
        self.cat_size.set(32)
        self._apply_look()
        self._sync_usage_status()
        self._dock_tick()
        logger.info('chat opened, cat shrunk to 32px and docking')

    def _on_chat_close(self) -> None:
        """Restore cat to original size when chat window closes."""
        if not self._chat_open:
            return
        self._chat_open = False
        if self._pre_chat_size and self._pre_chat_size in SIZE_CHOICES:
            self.cat_size.set(self._pre_chat_size)
        self._pre_chat_size = None
        self._apply_look()
        # Chatting doesn't touch the cat itself, so the idle-sleep timer
        # (P1.5-4) kept aging the whole time; _dock_tick() staved that off
        # while open, but reset explicitly too so closing never starts
        # already-idle. (User-reported: cat sprinted right as chat closed -
        # that was real usage% revealed after an idle-sleep freeze during
        # a long chat, not actually a bug in the speed logic itself.)
        self._last_interact = time.time()
        logger.info('chat closed, cat restored')

    def _dock_tick(self) -> None:
        """While chat is open, keep the cat glued to the chat window's
        current position (spec 2.1 originally pinned once and let the
        window drift away; re-scoped per user request to track it)."""
        if not self._chat_open:
            return
        import backend.window_main as chatwin
        geo = chatwin.get_geometry()
        if geo is not None:
            wx, wy, ww, _wh = geo
            sw = self.root.winfo_screenwidth()
            cx = wx - self.w - 4
            if cx < 0:   # window hugs the left edge - dock on the right instead
                cx = min(wx + ww + 4, sw - self.w)
            # 對齊視窗底部（大約是輸入區旁邊），預留一點邊距
            cy = max(0, wy + _wh - self.h - 15)
            if (cx, cy) != (self.root.winfo_x(), self.root.winfo_y()):
                self.root.geometry(f'+{cx}+{cy}')
                self._place_badge()
        # Chat counts as "attended" - don't let the idle-sleep timer
        # (P1.5-4) creep up just because no one is clicking the cat itself.
        self._last_interact = time.time()
        self.root.after(400, self._dock_tick)

    def _sync_usage_status(self) -> None:
        """Inject current usage into chat system prompt (spec 2.2)."""
        import backend.window_main as chatwin
        if not self._monitor_active():
            chatwin.set_usage_status('目前用量監控已關閉，無法提供用量數據。')
        elif self.error:
            chatwin.set_usage_status(f'目前用量監控異常：{self.error}')
        elif self.usage_pct is not None:
            parts = [f'目前狀態：session 用量 {self.usage_pct:.0f}%']
            if self.weekly_pct is not None:
                parts.append(f'weekly {self.weekly_pct:.0f}%')
            reset = self._to_local_hhmm(self.resets_at)
            if reset:
                parts.append(f'重置倒數 {reset}')
            chatwin.set_usage_status('，'.join(parts) + '。')
        else:
            chatwin.set_usage_status('用量數據尚未取得。')

    def _toggle_monitor(self) -> None:
        self._save_config()
        if self.monitor_enabled.get():
            self._poll_once_async()   # turn ON: refresh right away
        else:
            # OFF means truly off (spec): no polling, cat at leisure speed,
            # stale data cleared so nothing can lie on the badge/menu.
            self.usage_pct = None
            self.weekly_pct = None
            self.error = None
            self.monitor_unavailable = False
            self._consec_failures = 0
        logger.info('usage monitor %s', 'ON' if self.monitor_enabled.get() else 'OFF')

    def _schedule_tick(self) -> None:
        """30s tick on the tk after() loop (spec: no new thread)."""
        try:
            for item, kind in self.scheduler.tick(datetime.now()):
                self._queue_card(scheduler_mod.card_text(item, kind))
                self._boost_until = time.time() + ALERT_BOOST_SECS
                logger.info('schedule fired (%s): %s', kind, item.get('title'))
        except Exception:
            logger.exception('schedule tick failed')
        finally:
            self.root.after(30_000, self._schedule_tick)

    def _queue_card(self, text: str) -> None:
        """Thread-safe: cards can be requested from the poll thread; the
        animation loop (tk thread) materializes them."""
        with self._cards_lock:
            self._pending_cards.append(text)

    def _drain_cards(self) -> None:
        with self._cards_lock:
            pending, self._pending_cards = self._pending_cards, []
        for text in pending:
            self._show_card(text)

    def _show_card(self, text: str) -> None:
        """Popup card near the cat: topmost, click-to-close, 60s auto-close,
        stacks upward when several are open. tk thread only."""
        card = tk.Toplevel(self.root)
        card.overrideredirect(True)
        card.wm_attributes('-topmost', True)
        label = tk.Label(card, text=f'🐱 {text}', bg='#2a2a2a', fg='#ffffff',
                         font=('Segoe UI', 11), padx=14, pady=8,
                         bd=1, relief='solid')
        label.pack()

        idx = len(self._open_cards)
        card.update_idletasks()
        x = max(10, self.root.winfo_x() + self.w - card.winfo_reqwidth())
        y = max(10, self.root.winfo_y() - 46 - idx * (card.winfo_reqheight() + 6))
        card.geometry(f'+{x}+{y}')
        self._open_cards.append(card)

        def close(_e=None) -> None:
            if card in self._open_cards:
                self._open_cards.remove(card)
            try:
                card.destroy()
            except tk.TclError:
                pass   # already gone (auto-close raced the click)

        label.bind('<Button-1>', close)
        card.after(CARD_AUTOCLOSE_MS, close)

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
        """Short status line for the menu's top (disabled) entry - same
        compact format as the badge, so the menu window doesn't stretch
        wide with a long sentence (spec-adjacent, user-reported)."""
        if not self._monitor_active():
            return '用量監控:OFF'
        error = self._effective_error()
        usage = self._effective_usage()
        if error:
            return f'! {error}'
        if usage is None:
            return 'Fetching usage...'
        text = f'{usage:.0f}%'
        if self.weekly_pct is not None:
            text += f' | Week {self.weekly_pct:.0f}%'
        reset = self._to_local_hhmm(self.resets_at)
        if reset:
            text += f' ({reset})'
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
        if not self._monitor_active():
            state = (' OFF ', '#222222', '#888888')
        elif error:
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
            # Text width changed -> re-center under the cat. Rare (once per
            # poll at most), so no DWM-recomposite concern here.
            self._place_badge()
        if self.badge_win.state() == 'withdrawn':
            self.badge_win.deiconify()
            self._place_badge()

    # ---- Animation loop ---------------------------------------------------

    def _monitor_active(self) -> bool:
        """Monitor drives poses/speed only when ON - except the Test menu,
        which may preview any state regardless of the toggle."""
        return self.monitor_enabled.get() or self.debug_state.get() != 'live'

    def _should_sleep(self) -> bool:
        """Sleep pose wins over the run cycle when the session quota is fully used up (100%),
        or when idle for too long (P1.5-4)."""
        if not self.sleep_frames or not self._monitor_active():
            return False
        usage = self._effective_usage()
        if usage is not None and usage >= 100:
            return True
        idle_mins = (time.time() - self._last_interact) / 60
        if idle_mins >= self._sleep_min:
            # P1.5-4: currently using sleep frames for both want-to-sleep and deep-sleep stages.
            return True
        return False

    def _should_show_error_pose(self) -> bool:
        """Error pose (if the skin has one) replaces the gentle default
        animation when there's an error, or no usage data has come in yet."""
        if not self.error_frames or not self._monitor_active():
            return False
        return bool(self._effective_error()) or self._effective_usage() is None

    def _frame_interval(self) -> int | None:
        """Map current usage % to a frame interval (ms), or None if frozen."""
        if time.time() < self._boost_until:
            return 80   # schedule alert: brief sprint to catch the eye
        if not self._monitor_active():
            return 400  # monitor OFF: fixed leisure pace (spec P1-6)
        error = self._effective_error()
        usage = self._effective_usage()
        if error or usage is None:
            return 300  # API unavailable: gentle default animation
        for upper, interval in SPEED_TABLE:
            if usage <= upper:
                return interval
        return None

    def _animate(self) -> None:
        self._drain_cards()
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
            if not self.monitor_enabled.get():
                time.sleep(2)          # OFF = truly no API traffic (spec P1-6)
                continue
            wait = self._poll_once()
            deadline = time.time() + wait
            while time.time() < deadline:
                time.sleep(2)
                if not self.monitor_enabled.get():
                    break              # react to an OFF flip mid-wait

    def _set_unavailable(self, flag: bool, reason: str = '') -> None:
        """Popup exactly once per available->unavailable transition;
        recovery is silent (spec: 不洗版)."""
        if flag and not self.monitor_unavailable:
            self.monitor_unavailable = True
            self._queue_card(f'用量監控異常:{reason}')
            logger.warning('monitor unavailable: %s', reason)
        elif not flag and self.monitor_unavailable:
            self.monitor_unavailable = False
            logger.info('monitor recovered')

    def _poll_once(self) -> float:
        """Fetch usage once; update shared state. Returns next wait (s)."""
        data = api.fetch_usage()

        if 'error' in data:
            self.error = data['error']
            logger.error('poll failed: %s', self.error)
            self._consec_failures += 1
            no_token = data['error'] == api.T['no_token']
            if no_token or self._consec_failures >= 3:
                self._set_unavailable(True, data['error'])
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
            self._consec_failures += 1
            if self._consec_failures >= 3:
                self._set_unavailable(True, self.error)
            return self.poll_interval.get()

        was_error = self.error is not None
        self.error = None
        self._consec_failures = 0
        self._set_unavailable(False)
        
        new_usage = float(quota['utilization'])
        if self.usage_pct is not None and new_usage != self.usage_pct:
            self._last_interact = time.time()  # Usage jump wakes up cat (P1.5-4)
        self.usage_pct = new_usage
        
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
        self._sync_usage_status()
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
    import sys
    if len(sys.argv) > 2:
        if sys.argv[1] == '--worker':
            import worker
            worker.main(sys.argv[2])
            sys.exit(0)
        elif sys.argv[1] == '--ppt':
            import worker
            target = sys.argv[2]
            template = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None
            worker.generate_ppt(target, template)
            sys.exit(0)

    if not _acquire_single_instance_lock():
        # Silent exit: a withdrawn Tk root can't reliably host a modal
        # messagebox (it may not block/show at all on some setups), and
        # the user already has a cat on screen - no need to interrupt them.
        logger.info('another instance is already running; exiting')
        sys.exit(0)

    import backend.window_main as chatwin

    def _run_cat() -> None:
        try:
            app = ClaudeCat()
            llm.init(CONFIG_FILE)
            chatwin.init(app.scheduler, app._on_chat_open, app._on_chat_close)
            app.root.mainloop()
        except Exception:
            logger.exception('crashed')
        finally:
            # Unblock/close the webview side so the main thread can exit.
            chatwin.shutdown()

    threading.Thread(target=_run_cat, daemon=True).start()
    # Main thread parks here; opens the singleton webview window on demand
    # and returns only when the cat has quit (spec 1.2 threading model).
    chatwin.serve_main_thread()
