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
from config import settings
LOG_DIR = settings.LOG_DIR
LOG_FILE = settings.LOG_FILE
CONFIG_FILE = settings.CONFIG_FILE
SCHEDULE_FILE = settings.SCHEDULE_FILE
import logging
import logging.handlers
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

if getattr(sys, 'frozen', False):
    _bundle_dir = Path(sys._MEIPASS)
    os.environ['TCL_LIBRARY'] = str(_bundle_dir / 'tcl' / 'tcl8.6')
    os.environ['TK_LIBRARY'] = str(_bundle_dir / 'tcl' / 'tk8.6')

import tkinter as tk
from tkinter import messagebox
from datetime import datetime

import api
from backend.services import llm_service as llm
from backend.services import local_llm
from backend.services import codex_limits
from backend.services.tray_service import TrayService
from pet.state_machine import PetState, PetStateMachine
from plugins import builtin as builtin_plugins
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
        self.root.title('ClaudeCat')
        self.root.overrideredirect(True)
        self.root.wm_attributes('-topmost', True)
        self.root.protocol('WM_DELETE_WINDOW', self._quit)

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
        self.claude_consent_accepted = bool(um.get('consent_accepted', False)) \
            if isinstance(um, dict) else False
        self.claude_limits_available = api.CLAUDE_CREDENTIALS.exists()
        self.monitor_enabled = tk.BooleanVar(
            value=bool(um.get('enabled', False)) and self.claude_consent_accepted
            if isinstance(um, dict) else False)
        codex = cfg.get('codex_limits', {})
        self.codex_consent_accepted = bool(codex.get('consent_accepted', False)) \
            if isinstance(codex, dict) else False
        self.codex_limits_available = codex_limits.find_executable() is not None
        self.codex_limits_enabled = tk.BooleanVar(
            value=bool(codex.get('enabled', False)) and self.codex_consent_accepted
            if isinstance(codex, dict) else False)
        api.set_usage_api_enabled(self.monitor_enabled.get())
        # 'live' | 'error' | 'full': lets you preview the sleep/frozen poses
        # from the right-click menu instead of waiting for the real thing.
        # Deliberately not persisted - a forgotten forced state would look
        # like a permanently broken cat on the next start.
        self.debug_state = tk.StringVar(value='live')
        self._chat_open = False       # True while chat window is visible
        self._pre_chat_size: int | None = None  # size before shrink
        self._quick_window: tk.Toplevel | None = None
        self._quick_entry: tk.Entry | None = None
        self.pet_state = PetStateMachine()
        self._tray_actions: queue.SimpleQueue[str] = queue.SimpleQueue()

        self.root.wm_attributes('-topmost', self.topmost.get())
        self.w = self.h = size
        self._render_cat()

        # Part 1.5 Interactive config
        self._sleep_min = int(cfg.get('sleep_min', 10))
        self._last_interact = time.time()
        self._drag_start_x = 0
        self._drag_start_y = 0

        # State shared between poll thread and UI loop
        self.usage_pct: float | None = None   # None = not fetched yet
        self.weekly_pct: float | None = None
        self.error: str | None = None
        self.resets_at: str | None = None
        self.weekly_resets_at: str | None = None
        self.codex_usage_pct: float | None = None
        self.codex_weekly_pct: float | None = None
        self.codex_resets_at: str | None = None
        self.codex_error: str | None = None
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
        # Keep the transparent, borderless pet while exposing a normal
        # taskbar item.  Its Close button follows _quit() and saves position.
        winalpha.show_in_taskbar(self.root.winfo_id())

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
        icon_path = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'claudecat.ico'
        self.tray = TrayService(icon_path, self._on_tray_action)
        self.tray_available = self.tray.start()
        if not self.tray_available:
            logger.warning('system tray is unavailable')
        self.root.after(150, self._drain_tray_actions)

        self._bind_mouse()
        # v6.1 intentionally does not call Claude or Codex for usage data.
        self._start_poll_thread()
        self._start_codex_poll_thread()
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
        """Open a compact question bubble; dragging keeps its normal behavior."""
        self._boost_until = time.time() + 0.3
        self._open_quick_question()

    def _open_quick_question(self) -> None:
        """Show the small, cat-adjacent Qwen question bubble (no webview)."""
        self._set_pet_state(PetState.LISTENING)
        if self._quick_window is not None and self._quick_window.winfo_exists():
            self._quick_window.deiconify()
            self._quick_window.lift()
            if self._quick_entry is not None:
                self._quick_entry.focus_set()
            return

        win = tk.Toplevel(self.root)
        self._quick_window = win
        win.overrideredirect(True)
        win.wm_attributes('-topmost', True)
        win.configure(bg='#202225')
        x = min(self.root.winfo_x() + self.w + 8, self.root.winfo_screenwidth() - 360)
        y = max(0, self.root.winfo_y())
        win.geometry(f'350x118+{x}+{y}')

        outer = tk.Frame(win, bg='#202225', highlightbackground='#4f8cff', highlightthickness=1)
        outer.pack(fill='both', expand=True)
        header = tk.Frame(outer, bg='#202225')
        header.pack(fill='x', padx=8, pady=(7, 2))
        tk.Label(header, text='🐱 問我一句', bg='#202225', fg='#f1f3f4',
                 font=('Segoe UI', 10, 'bold')).pack(side='left')
        tk.Button(header, text='×', command=win.destroy, relief='flat', bd=0,
                  bg='#202225', fg='#9aa0a6', activebackground='#303236',
                  activeforeground='#ffffff').pack(side='right')
        entry = tk.Entry(outer, bg='#303236', fg='#f1f3f4', insertbackground='#ffffff',
                         relief='flat', font=('Segoe UI', 10))
        self._quick_entry = entry
        entry.pack(fill='x', padx=8, pady=4, ipady=5)
        answer = tk.Label(outer, text='輸入問題後按 Enter', justify='left', anchor='w',
                          wraplength=328, bg='#202225', fg='#aab0b7', font=('Segoe UI', 9))
        answer.pack(fill='both', expand=True, padx=9, pady=(1, 6))

        def ask(_event=None):
            question = entry.get().strip()
            if not question:
                return 'break'
            entry.configure(state='disabled')
            self._set_pet_state(PetState.THINKING)
            answer.configure(text='思考中…', fg='#aab0b7')

            def work():
                result = llm.chat([
                    {'role': 'system', 'content': '你是桌面貓咪助手。請用繁體中文簡短直接回答。'},
                    {'role': 'user', 'content': question},
                ], timeout=60)

                def done():
                    if not win.winfo_exists():
                        return
                    self._set_pet_state(PetState.STREAMING)
                    text = result.get('content') or f'無法回答：{result.get("error", "未知錯誤")}'
                    answer.configure(text=text, fg='#f1f3f4')
                    entry.configure(state='normal')
                    entry.delete(0, 'end')
                    self._last_interact = time.time()
                    final_state = PetState.SUCCESS if result.get('content') else PetState.ERROR
                    self._set_pet_state(final_state)
                    self.root.after(1500, lambda: self._reset_pet_state_if(final_state))
                    if self._is_long_answer(text):
                        win.withdraw()
                        self._show_answer_panel(text)
                self.root.after(0, done)

            threading.Thread(target=work, daemon=True).start()
            return 'break'

        entry.bind('<Return>', ask)
        win.bind('<Escape>', lambda _event: win.destroy())
        win.bind('<Destroy>', lambda _event: (setattr(self, '_quick_window', None),
                                               setattr(self, '_quick_entry', None)))
        win.bind('<Destroy>', lambda _event: self._set_pet_state(PetState.IDLE), add='+')
        entry.focus_set()

    def _set_pet_state(self, state: PetState) -> None:
        """Apply a valid visual-state transition without blocking the UI."""
        previous = self.pet_state.current
        if not self.pet_state.transition(state):
            logger.debug('ignored pet state transition: %s -> %s', previous, state)
            return
        if previous != state:
            logger.info('pet state: %s -> %s', previous.value, state.value)
            self._last_interact = time.time()

    def _reset_pet_state_if(self, state: PetState) -> None:
        """Return to normal only if no later interaction changed state."""
        if self.pet_state.current == state:
            self._set_pet_state(PetState.IDLE)

    @staticmethod
    def _is_long_answer(text: str) -> bool:
        return len(text) > 180 or text.count('\n') >= 4

    def _show_answer_panel(self, text: str) -> None:
        """Show a dismissible, cat-adjacent card for a long Qwen answer."""
        panel = tk.Toplevel(self.root)
        panel.overrideredirect(True)
        panel.wm_attributes('-topmost', True)
        panel.configure(bg='#202225')
        x = min(self.root.winfo_x() + self.w + 8, self.root.winfo_screenwidth() - 430)
        y = max(0, self.root.winfo_y() - 80)
        panel.geometry(f'420x300+{x}+{y}')

        outer = tk.Frame(panel, bg='#202225', highlightbackground='#4f8cff', highlightthickness=1)
        outer.pack(fill='both', expand=True)
        tk.Label(outer, text='回答', bg='#202225', fg='#f1f3f4',
                 font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=10, pady=(8, 3))
        body = tk.Text(outer, wrap='word', bg='#303236', fg='#f1f3f4',
                       insertbackground='#ffffff', relief='flat', font=('Segoe UI', 10),
                       padx=8, pady=7)
        body.insert('1.0', text)
        body.configure(state='disabled')
        body.pack(fill='both', expand=True, padx=9, pady=(0, 7))
        buttons = tk.Frame(outer, bg='#202225')
        buttons.pack(fill='x', padx=8, pady=(0, 8))

        def close() -> None:
            panel.destroy()
            self._set_pet_state(PetState.IDLE)

        def copy() -> None:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)

        tk.Button(buttons, text='複製', command=copy, relief='flat', bd=0,
                  bg='#303236', fg='#f1f3f4').pack(side='left', padx=(0, 5))
        tk.Button(buttons, text='繼續問', command=lambda: (close(), self._open_quick_question()),
                  relief='flat', bd=0, bg='#303236', fg='#f1f3f4').pack(side='left')
        tk.Button(buttons, text='收合', command=close, relief='flat', bd=0,
                  bg='#303236', fg='#f1f3f4').pack(side='right')
        panel.bind('<Escape>', lambda _event: close())

    def _place_badge(self) -> None:
        self.badge_win.update_idletasks()
        bw = self.badge_win.winfo_reqwidth()
        x = self.root.winfo_x() + (self.w - bw) // 2
        y = self.root.winfo_y() + self.h + 2
        self.badge_win.geometry(f'+{x}+{y}')

    def _save_config(self) -> None:
        """Merge cat-owned keys without overwriting the LLM owner's settings."""
        patch = {
            'skin': self.current_skin.get(),
            'size': self.cat_size.get(),
            'facing_right': self.facing_right.get(),
            'poll_interval': self.poll_interval.get(),
            'topmost': self.topmost.get(),
            'show_pct': self.show_pct.get(),
            'usage_monitor': {
                'enabled': self.monitor_enabled.get(),
                'consent_accepted': self.claude_consent_accepted,
            },
            'codex_limits': {
                'enabled': self.codex_limits_enabled.get(),
                'consent_accepted': self.codex_consent_accepted,
            },
            'x': self.root.winfo_x(),
            'y': self.root.winfo_y(),
        }
        try:
            settings.merge_config(patch)
        except OSError:
            logger.exception('could not save config')

    def _quit(self) -> None:
        self._save_config()  # position is only captured here, on clean exit
        self.tray.stop()
        self.root.destroy()

    def _set_topmost(self) -> None:
        on = self.topmost.get()
        self.root.wm_attributes('-topmost', on)
        self.badge_win.wm_attributes('-topmost', on)
        self._save_config()

    def _render_cat(self) -> None:
        try:
            self.state_frames = spritecat.load_state_frames(
                self.cat_size.get(),
                facing='right' if self.facing_right.get() else 'left',
                skin=self.current_skin.get())
        except (FileNotFoundError, OSError) as exc:
            logger.exception('could not load skin: %s', self.current_skin.get())
            messagebox.showerror(
                'ClaudeCat 無法載入素材',
                f'找不到或無法讀取皮膚素材：{exc}\n\n請重新安裝 skins 資料夾後再啟動。',
                parent=self.root,
            )
            raise RuntimeError('required skin assets are unavailable') from exc
        self.idle_buffer = self.state_frames['idle'][0]
        self.frame_buffers = self.state_frames['run']
        self.sleep_frames = self.state_frames['sleep']
        self.error_frames = self.state_frames['error']
        self._action_frame_indices: dict[str, int] = {}
        self._error_frame_idx = 0

    def _draw_state_frame(self, action: str) -> None:
        frames = self.state_frames[action]
        index = self._action_frame_indices.get(action, 0) % len(frames)
        self.canvas.draw(frames[index])
        self._action_frame_indices[action] = index + 1

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
        m.add_separator()
        m.add_command(label='排程...', command=self._open_schedule)
        m.add_command(label='交談...', command=self._open_chat)
        m.add_command(label='文件助手...', command=self._open_documents)

        plugin_menu = tk.Menu(m, tearoff=0)
        for action in builtin_plugins.actions():
            plugin_menu.add_command(label=action.label,
                                    command=lambda action_id=action.action_id:
                                    self._run_plugin_action(action_id))
        m.add_cascade(label='Plugins', menu=plugin_menu)

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
        monitor_label = 'Claude limits（異常）' if (self.monitor_enabled.get()
                                                    and self.monitor_unavailable) else 'Claude limits'
        sm.add_checkbutton(label=monitor_label, variable=self.monitor_enabled,
                           command=self._toggle_monitor)
        sm.add_checkbutton(label='Codex limits（非官方）',
                           variable=self.codex_limits_enabled, command=self._toggle_codex_limits)
        sm.add_checkbutton(label='Face right', variable=self.facing_right,
                           command=self._apply_look)
        sm.add_checkbutton(label='Show usage badge', variable=self.show_pct,
                           command=self._toggle_badge)
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

    def _toggle_badge(self) -> None:
        if self.show_pct.get():
            self._show_cat()
        else:
            self.badge_win.withdraw()
        self._save_config()

    # ---- Schedule + monitor toggle (Part 1) --------------------------------

    def _open_schedule(self) -> None:
        import backend.window_main as chatwin   # lazy: pulls in pywebview
        chatwin.request_open('schedule')

    def _open_chat(self) -> None:
        import backend.window_main as chatwin
        chatwin.request_open('chat')

    def _open_documents(self) -> None:
        import backend.window_main as chatwin
        chatwin.request_open('documents')

    def _run_plugin_action(self, action_id: str) -> None:
        """Dispatch only declared built-in actions; plugins cannot run code."""
        actions = {
            'quick_question': self._open_quick_question,
            'documents': self._open_documents,
        }
        action = actions.get(action_id)
        if action is None:
            logger.warning('rejected unknown plugin action: %s', action_id)
            return
        action()

    def _on_tray_action(self, action_id: str) -> None:
        """pystray runs on its own thread; enqueue work for Tk's main loop."""
        self._tray_actions.put(action_id)

    def _drain_tray_actions(self) -> None:
        """Run queued tray actions on the Tk thread; never call Tk from pystray."""
        actions = {
            'show': self._show_cat,
            'hide': self._hide_cat,
            'quick_question': lambda: self._run_plugin_action('quick_question'),
            'documents': lambda: self._run_plugin_action('documents'),
            'quit': self._quit,
        }
        while True:
            try:
                action_id = self._tray_actions.get_nowait()
            except queue.Empty:
                break
            action = actions.get(action_id)
            if action is None:
                logger.warning('rejected unknown tray action: %s', action_id)
            else:
                action()
                if action_id == 'quit':
                    return
        if self.root.winfo_exists():
            self.root.after(150, self._drain_tray_actions)

    def _show_cat(self) -> None:
        self.root.deiconify()
        self.root.lift()
        if self.show_pct.get():
            self.badge_win.deiconify()
            self._place_badge()

    def _hide_cat(self) -> None:
        self.root.withdraw()
        self.badge_win.withdraw()
        if self._quick_window is not None and self._quick_window.winfo_exists():
            self._quick_window.withdraw()

    def _on_chat_open(self) -> None:
        """Shrink cat to 32px and dock beside the chat window (spec 2.1,
        user-requested: must stay attached to the window, not drift apart)."""
        if self._chat_open:
            return
        self._chat_open = True
        self._pre_chat_size = self.cat_size.get()
        self.cat_size.set(32)
        self._apply_look()
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

    def _toggle_monitor(self) -> None:
        if self.monitor_enabled.get() and not self.claude_limits_available:
            self.monitor_enabled.set(False)
            messagebox.showinfo('Claude limits', 'No use：找不到本機 Claude 登入資料。', parent=self.root)
            self._save_config()
            return
        if self.monitor_enabled.get() and not self.claude_consent_accepted:
            approved = messagebox.askyesno(
                '啟用 Claude limits',
                '此功能會讀取本機 Claude 登入資料，向 Claude 用量 API 查詢目前用量與重置時間。\n\n'
                '不會顯示、保存或上傳 token；Qwen 聊天與文件助手不受影響。\n'
                '是否同意啟用？', parent=self.root,
            )
            if not approved:
                self.monitor_enabled.set(False)
                self._save_config()
                return
            self.claude_consent_accepted = True
        api.set_usage_api_enabled(self.monitor_enabled.get())
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

    def _toggle_codex_limits(self) -> None:
        """Require per-user consent before the unofficial reader can run."""
        if self.codex_limits_enabled.get() and not self.codex_limits_available:
            self.codex_limits_enabled.set(False)
            messagebox.showinfo('Codex limits', 'No use：找不到本機 Codex Desktop。', parent=self.root)
            self._save_config()
            return
        if self.codex_limits_enabled.get() and not self.codex_consent_accepted:
            approved = messagebox.askyesno(
                '啟用 Codex limits（非官方）',
                '此功能會透過本機 Codex app-server 讀取目前登入帳號的用量與重置時間。\n\n'
                '不會顯示、保存或上傳 token；Qwen 聊天與文件助手不受影響。\n'
                '此為非官方相容方式，Codex 更新後可能失效。是否同意啟用？',
                parent=self.root,
            )
            if not approved:
                self.codex_limits_enabled.set(False)
                self._save_config()
                return
            self.codex_consent_accepted = True
        self._save_config()
        if self.codex_limits_enabled.get():
            self._poll_codex_once_async()
        else:
            self.codex_usage_pct = None
            self.codex_weekly_pct = None
            self.codex_resets_at = None
            self.codex_error = None
        logger.info('codex limits %s', 'ON' if self.codex_limits_enabled.get() else 'OFF')

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
        if self._effective_usage() is not None:
            return None
        if self.monitor_enabled.get() and self.error:
            return self.error
        if self.codex_limits_enabled.get() and self.codex_error:
            return self.codex_error
        return None

    def _effective_usage(self) -> float | None:
        """Real usage %, or a debug-menu override for previewing that state."""
        ds = self.debug_state.get()
        if ds == 'error':
            return None
        if ds == 'full':
            return 100.0
        values = []
        if self.monitor_enabled.get() and self.usage_pct is not None:
            values.append(self.usage_pct)
        if self.codex_limits_enabled.get() and self.codex_usage_pct is not None:
            values.append(self.codex_usage_pct)
        return max(values) if values else None

    def _status_text(self) -> str:
        """Short status line for the menu's top (disabled) entry - same
        compact format as the badge, so the menu window doesn't stretch
        wide with a long sentence (spec-adjacent, user-reported)."""
        if not self.claude_limits_available and not self.codex_limits_available:
            return 'No use'
        if not self._monitor_active():
            return '用量監控:OFF'
        error = self._effective_error()
        usage = self._effective_usage()
        if error:
            return f'! {error}'
        if usage is None:
            return 'Fetching usage...'
        parts = []
        if self.monitor_enabled.get() and self.usage_pct is not None:
            parts.append(f'Claude {self.usage_pct:.0f}%')
        if self.codex_limits_enabled.get() and self.codex_usage_pct is not None:
            parts.append(f'Codex {self.codex_usage_pct:.0f}%')
        return ' | '.join(parts) or 'Fetching usage...'

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
        if not self.claude_limits_available and not self.codex_limits_available:
            state = (' No use ', '#222222', '#888888')
        elif not self._monitor_active():
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
        return self.monitor_enabled.get() or self.codex_limits_enabled.get() \
            or self.debug_state.get() != 'live'

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
        if self.pet_state.current == PetState.ERROR and self.error_frames:
            return True
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
        state = self.pet_state.current
        if state in (PetState.THINKING, PetState.STREAMING):
            self._draw_state_frame('thinking' if state == PetState.THINKING else 'streaming')
            self.root.after(120, self._animate)
            return
        if state in (PetState.LISTENING, PetState.SUCCESS):
            self._draw_state_frame('listening' if state == PetState.LISTENING else 'success')
            self.root.after(250, self._animate)
            return
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

    def _start_codex_poll_thread(self) -> None:
        threading.Thread(target=self._poll_codex_forever, daemon=True).start()

    def _poll_once_async(self) -> None:
        if not self.monitor_enabled.get():
            return
        threading.Thread(target=self._poll_once, daemon=True).start()

    def _poll_codex_once_async(self) -> None:
        if self.codex_limits_enabled.get():
            threading.Thread(target=self._poll_codex_once, daemon=True).start()

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

    def _poll_codex_forever(self) -> None:
        while True:
            if not self.codex_limits_enabled.get():
                time.sleep(2)
                continue
            self._poll_codex_once()
            deadline = time.time() + self.poll_interval.get()
            while time.time() < deadline:
                time.sleep(2)
                if not self.codex_limits_enabled.get():
                    break

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
        return self.poll_interval.get()

    def _poll_codex_once(self) -> None:
        """Read Codex limits through its local app-server only when enabled."""
        data = codex_limits.fetch_usage()
        if 'error' in data:
            self.codex_error = data['error']
            logger.warning('codex limits poll failed: %s', self.codex_error)
            return
        previous = self.codex_usage_pct
        self.codex_usage_pct = data['usage_pct']
        self.codex_weekly_pct = data.get('weekly_pct')
        self.codex_resets_at = data.get('resets_at')
        self.codex_error = None
        if previous is not None and previous != self.codex_usage_pct:
            self._last_interact = time.time()
        logger.info('codex limits updated: usage=%.0f%% plan=%s',
                    self.codex_usage_pct, data.get('plan'))

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
            max_chars = int(sys.argv[3]) if len(sys.argv) > 3 else 50000
            worker.main(sys.argv[2], max_chars)
            sys.exit(0)
        elif sys.argv[1] == '--document-check':
            if len(sys.argv) < 5:
                sys.exit(2)
            from backend.services import document_service
            result = document_service.ingest(sys.argv[2])
            if result.get('error'):
                sys.exit(1)
            evidence = document_service.query(result['document']['id'], sys.argv[3])
            sources = evidence.get('sources', [])
            if not sources or sources[0]['source'].get('locator') != sys.argv[4]:
                sys.exit(1)
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
            runtime = local_llm.init(CONFIG_FILE)
            if runtime.get('endpoint'):
                llm.use_local_endpoint(runtime['endpoint'], runtime.get('model', ''))
            logger.info('local llm: %s', runtime['status'])
            chatwin.init(app.scheduler, app._on_chat_open, app._on_chat_close)
            app.root.mainloop()
        except Exception:
            logger.exception('crashed')
        finally:
            local_llm.stop()
            # Unblock/close the webview side so the main thread can exit.
            chatwin.shutdown()

    threading.Thread(target=_run_cat, daemon=True).start()
    # Main thread parks here; opens the singleton webview window on demand
    # and returns only when the cat has quit (spec 1.2 threading model).
    chatwin.serve_main_thread()
