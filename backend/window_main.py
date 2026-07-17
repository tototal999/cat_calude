"""
pywebview singleton window for ClaudeCat (Part 1+2: 排程 + 交談).
=================================================================

Threading model (spec 1.2, verified by P1-0): pywebview owns the MAIN
thread; the tkinter cat runs in a background thread. The main thread
parks in serve_main_thread() until the first open request, then lives
inside webview.start() forever. "Closing" the window actually hides it
(singleton survives), so webview.start() is only ever called once -
re-entering the GUI loop after it exits is not reliably supported.

cat.py calls: init(scheduler, on_chat_open, on_chat_close),
              request_open(tab), shutdown().
"""
from __future__ import annotations

import threading
from pathlib import Path

import webview

from backend.services import llm_service as llm

_window: webview.Window | None = None
_open_evt = threading.Event()
_pending_tab = 'schedule'
_quitting = False
_scheduler = None
_on_chat_open = None
_on_chat_close = None

_BASE_DIR = Path(__file__).parent
HTML_PATH = _BASE_DIR.parent / 'frontend' / 'index.html'

import sys as _sys
if getattr(_sys, 'frozen', False):
    _APP_DIR = Path(_sys.executable).parent
else:
    _APP_DIR = _BASE_DIR.parent
ICON_PATH = _APP_DIR / 'claudecat.ico'

# In-memory conversation history (关窗即清, spec 2.2)
_history: list[dict[str, str]] = []
_current_model: str = ''
_current_session_id = None


def init(scheduler, on_chat_open=None, on_chat_close=None) -> None:
    global _scheduler, _on_chat_open, _on_chat_close, _current_model
    _scheduler = scheduler
    _on_chat_open = on_chat_open
    _on_chat_close = on_chat_close
    _current_model = llm.current_model()


from backend.routes.api import JsApi

def _build_system_prompt() -> str:
    """Dynamic system prompt with usage status injection (spec 2.2)."""
    base = llm.system_prompt()
    # Usage status is injected by cat.py via set_usage_status()
    if _usage_status:
        return base + '\n' + _usage_status
    return base


_usage_status: str = ''


def set_usage_status(status: str) -> None:
    """Called by cat.py to inject current usage into the system prompt."""
    global _usage_status
    _usage_status = status


def get_geometry() -> tuple[int, int, int, int] | None:
    """Chat window's current (x, y, width, height), or None if it doesn't
    exist yet (e.g. the very first open, before serve_main_thread() creates
    it) or a read races window teardown. Cheap attribute read on
    pywebview's side - safe to poll from the tk thread."""
    if _window is None:
        return None
    try:
        return (_window.x, _window.y, _window.width, _window.height)
    except Exception:
        return None


def request_open(tab: str = 'schedule') -> None:
    """Open (or focus) the singleton window at the given tab.
    Safe to call from the tk thread."""
    global _pending_tab
    _pending_tab = tab
    if tab == 'chat' and _on_chat_open:
        _on_chat_open()
    if _window is not None:
        try:
            _window.show()
            _window.evaluate_js(f'showTab({tab!r})')
        except Exception:
            pass
    else:
        _open_evt.set()


def shutdown() -> None:
    """Called when the cat quits: unblock/close everything so the main
    thread (and thus the process) can exit."""
    global _quitting
    _quitting = True
    _open_evt.set()
    if _window is not None:
        try:
            _window.destroy()
        except Exception:
            pass


def _on_closing():
    """User clicked X: hide instead of destroy, keeping the singleton
    (and the one-shot webview.start()) alive. Real close only on quit."""
    global _history
    if _quitting:
        return True
    try:
        _window.hide()
    except Exception:
        pass
    # Clear history on window close (spec: 關窗即清)
    _history = []
    if _on_chat_close:
        _on_chat_close()
    return False


def serve_main_thread() -> None:
    """Park the main thread; on first open request, create the window and
    enter the webview GUI loop. Returns only when the app is quitting."""
    global _window
    _open_evt.wait()
    if _quitting:
        return
    _window = webview.create_window(
        'ClaudeCat', str(HTML_PATH), js_api=JsApi(),
        width=560, height=560)
    _window.events.closing += _on_closing
    _icon = str(ICON_PATH) if ICON_PATH.exists() else None
    webview.start(icon=_icon)
