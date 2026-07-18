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
import logging
from pathlib import Path

import webview

from backend.services import llm_service as llm

logger = logging.getLogger('claudecat')

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
_history_generation = 0
_history_lock = threading.RLock()


def init(scheduler, on_chat_open=None, on_chat_close=None) -> None:
    global _scheduler, _on_chat_open, _on_chat_close, _current_model
    _scheduler = scheduler
    _on_chat_open = on_chat_open
    _on_chat_close = on_chat_close
    _current_model = llm.current_model()


def _build_system_prompt() -> str:
    """Return the chat prompt; optional limits never enter conversation context."""
    return llm.system_prompt()


def history_snapshot() -> tuple[int, list[dict[str, str]]]:
    """Return a stable history copy and its generation for an LLM request."""
    with _history_lock:
        return _history_generation, list(_history)


def append_history_if_current(generation: int, *messages: dict[str, str]) -> list[dict[str, str]] | None:
    """Append only when the chat was not cleared or replaced while LLM ran."""
    with _history_lock:
        if generation != _history_generation:
            return None
        _history.extend(messages)
        return list(_history)


def replace_history(history: list[dict[str, str]], session_id: str | None, model: str | None = None) -> None:
    """Load a session as a new history generation."""
    global _history, _current_session_id, _current_model, _history_generation
    with _history_lock:
        _history = list(history)
        _current_session_id = session_id
        if model:
            _current_model = model
        _history_generation += 1


def clear_history() -> None:
    """Clear the current conversation and invalidate all in-flight replies."""
    global _history, _current_session_id, _history_generation
    with _history_lock:
        _history = []
        _current_session_id = None
        _history_generation += 1


def ensure_session_id() -> str:
    global _current_session_id
    with _history_lock:
        if not _current_session_id:
            import uuid
            _current_session_id = str(uuid.uuid4())
        return _current_session_id


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
        logger.debug('chat geometry unavailable during window teardown', exc_info=True)
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
            logger.warning('could not show chat window', exc_info=True)
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
            logger.debug('could not destroy chat window during shutdown', exc_info=True)


def _on_closing():
    """User clicked X: hide instead of destroy, keeping the singleton
    (and the one-shot webview.start()) alive. Real close only on quit."""
    if _quitting:
        return True
    try:
        _window.hide()
    except Exception:
        logger.debug('could not hide chat window', exc_info=True)
    # Clear history on window close and invalidate replies still in flight.
    clear_history()
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
    from backend.routes.api import JsApi
    _window = webview.create_window(
        'ClaudeCat', str(HTML_PATH), js_api=JsApi(),
        width=560, height=560)
    _window.events.closing += _on_closing
    _icon = str(ICON_PATH) if ICON_PATH.exists() else None
    webview.start(icon=_icon)
