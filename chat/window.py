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

import llm

_window: webview.Window | None = None
_open_evt = threading.Event()
_pending_tab = 'schedule'
_quitting = False
_scheduler = None
_on_chat_open = None
_on_chat_close = None

_BASE_DIR = Path(__file__).parent
HTML_PATH = _BASE_DIR / 'chat.html'

# In-memory conversation history (关窗即清, spec 2.2)
_history: list[dict[str, str]] = []
_current_model: str = ''


def init(scheduler, on_chat_open=None, on_chat_close=None) -> None:
    global _scheduler, _on_chat_open, _on_chat_close, _current_model
    _scheduler = scheduler
    _on_chat_open = on_chat_open
    _on_chat_close = on_chat_close
    _current_model = llm.current_model()


class JsApi:
    """Bridge for chat.html. Schedule edits are save-on-change.
    Chat methods run LLM calls in threads to avoid blocking the UI."""

    # ---- Schedule (Part 1, unchanged) ----

    def list_schedules(self):
        return {'items': _scheduler.list(), 'errors': _scheduler.errors}

    def upsert_schedule(self, item):
        err = _scheduler.upsert(item)
        return {'error': err, 'items': _scheduler.list()}

    def delete_schedule(self, sid):
        _scheduler.delete(sid)
        return {'error': None, 'items': _scheduler.list()}

    def get_tab(self):
        return _pending_tab

    # ---- Chat (Part 2) ----

    def list_models(self):
        return llm.list_models()

    def current_model(self):
        return _current_model or llm.current_model()

    def set_model(self, model):
        global _current_model
        _current_model = model
        llm.save_config_model(model)

    def probe(self):
        """Warm-up connectivity check. Returns error string or None."""
        return llm.probe()

    def open_file_dialog(self):
        if _window is None:
            return None
        file_types = ('支援的資料檔 (*.txt;*.md;*.csv;*.sql;*.log;*.xlsx;*.xls)', '所有檔案 (*.*)')
        result = _window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=file_types)
        if result and len(result) > 0:
            return result[0]
        return None

    def clear_history(self):
        global _history
        _history = []
        return {'status': 'ok'}

    def export_ppt(self, text):
        if _window is None:
            return {'error': 'No window'}
        file_types = ('PowerPoint 簡報 (*.pptx)',)
        result = _window.create_file_dialog(webview.SAVE_DIALOG, save_filename='簡報.pptx', file_types=file_types)
        if not result or len(result) == 0:
            return {'status': 'cancelled'}
            
        target_path = result[0]
        
        try:
            import sys, subprocess
            import cat
            
            cmd = [sys.executable]
            if not getattr(sys, 'frozen', False):
                import __main__
                main_file = getattr(__main__, '__file__', 'cat.py')
                cmd.append(main_file)
                
            from pathlib import Path
            if getattr(sys, 'frozen', False):
                exe_dir = Path(sys.executable).parent
            else:
                import __main__
                exe_dir = Path(getattr(__main__, '__file__', 'cat.py')).parent
                
            template_path = exe_dir / 'template.pptx'
            if not template_path.exists():
                template_path = cat.LOG_DIR / 'template.pptx'
                
            template_arg = str(template_path) if template_path.exists() else ""
            cmd.extend(['--ppt', target_path, template_arg])
            
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            proc = subprocess.run(cmd, input=text, capture_output=True, text=True, encoding='utf-8', creationflags=creationflags)
            
            if proc.returncode != 0:
                return {'error': f'PPT 轉檔失敗: {proc.stderr}'}
                
            return {'status': 'ok', 'path': target_path}
        except Exception as e:
            return {'error': f'啟動 Worker 失敗: {e}'}

    def send_message(self, text, attached_file=None):
        """Send a user message; manages history + context + overflow retry."""
        global _history

        prompt_text = text
        if attached_file:
            try:
                p = Path(attached_file)
                import sys, subprocess
                cmd = [sys.executable]
                if not getattr(sys, 'frozen', False):
                    import __main__
                    main_file = getattr(__main__, '__file__', 'cat.py')
                    cmd.append(main_file)
                cmd.extend(['--worker', str(p)])
                
                creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', creationflags=creationflags)
                
                if proc.returncode != 0:
                    return {'error': f'Worker 處理失敗: {proc.stderr}'}
                    
                file_content = proc.stdout
                
                max_chars = llm.max_file_chars()
                if len(file_content) > max_chars:
                    return {'error': f'檔案內容過長 ({len(file_content)} 字 / 上限 {max_chars} 字)，請先縮減資料或調整 config.json 再上傳。'}
                
                prompt_text = f"{text}\n\n[附加檔案：{p.name}]\n{file_content}"
            except Exception as e:
                return {'error': f'啟動 Worker 失敗: {e}'}

        # Build messages: system + history + new user input
        sys_prompt = _build_system_prompt()
        max_turns = llm.max_history_turns()

        # Sliding window: keep most recent N turns (spec: 從最舊丟)
        window = _history[-(max_turns * 2):] if len(_history) > max_turns * 2 else list(_history)
        truncated = len(_history) > max_turns * 2

        messages = [{'role': 'system', 'content': sys_prompt}]
        messages.extend(window)
        messages.append({'role': 'user', 'content': prompt_text})

        result = llm.chat(messages, model=_current_model, timeout=180)

        degraded = None
        if truncated:
            degraded = f'（已截斷較早的對話，保留最近 {max_turns} 輪）'

        # Context overflow retry (spec: 砍半 history 重試一次)
        if result.get('context_overflow'):
            half = max(len(window) // 2, 0)
            window = window[half:]
            messages = [{'role': 'system', 'content': sys_prompt}]
            messages.extend(window)
            messages.append({'role': 'user', 'content': prompt_text})
            result = llm.chat(messages, model=_current_model, timeout=180)
            if result.get('error'):
                return result
            degraded = '內容過長，已縮短貓的記憶重試'

        if result.get('error'):
            return result

        # Success: append to history
        _history.append({'role': 'user', 'content': text})
        _history.append({'role': 'assistant', 'content': result['content']})

        return {
            'content': result['content'],
            'model': result.get('model', _current_model),
            'degraded': degraded,
        }

    def save_note(self, content, model):
        try:
            path = llm.save_note(content, model)
            return {'error': None, 'path': str(path)}
        except Exception as exc:
            return {'error': str(exc)}

    def export_chat(self):
        try:
            if not _history:
                return {'error': '沒有對話可匯出'}
            path = llm.export_chat(_history, _current_model)
            return {'error': None, 'path': str(path)}
        except Exception as exc:
            return {'error': str(exc)}


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
    webview.start()
