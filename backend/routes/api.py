from backend.services import llm_service as llm
from config import settings
import json
import uuid
import time
import sys
import subprocess
from pathlib import Path
import webview

import backend.window_main as wm

class JsApi:
    """Bridge for chat.html. Schedule edits are save-on-change.
    Chat methods run LLM calls in threads to avoid blocking the UI."""

    # ---- Schedule (Part 1, unchanged) ----

    def list_schedules(self):
        return {'items': wm._scheduler.list(), 'errors': wm._scheduler.errors}

    def upsert_schedule(self, item):
        err = wm._scheduler.upsert(item)
        return {'error': err, 'items': wm._scheduler.list()}

    def delete_schedule(self, sid):
        wm._scheduler.delete(sid)
        return {'error': None, 'items': wm._scheduler.list()}

    def get_tab(self):
        return wm._pending_tab

    # ---- Chat (Part 2) ----

    def list_models(self):
        return llm.list_models()

    def current_model(self):
        return wm._current_model or llm.current_model()

    def set_model(self, model):
        wm._current_model = model
        llm.save_config_model(model)

    def probe(self):
        """Warm-up connectivity check. Returns error string or None."""
        return llm.probe()

    def open_file_dialog(self):
        if wm._window is None:
            return None
        file_types = ('支援的資料檔 (*.txt;*.md;*.csv;*.sql;*.log;*.xlsx;*.xls)', '所有檔案 (*.*)')
        result = wm._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=file_types)
        if result and len(result) > 0:
            return result[0]
        return None


    def list_sessions(self):
        sessions_dir = settings.LOG_DIR / 'sessions'
        if not sessions_dir.exists():
            return []
        
        sessions = []
        for p in sessions_dir.glob('*.json'):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    sessions.append({
                        'id': data.get('id', p.stem),
                        'title': data.get('title', 'New Chat'),
                        'updated_at': data.get('updated_at', 0)
                    })
            except Exception:
                pass
        sessions.sort(key=lambda x: x['updated_at'], reverse=True)
        return sessions

    def load_session(self, session_id):
        path = settings.LOG_DIR / 'sessions' / f"{session_id}.json"
        if not path.exists():
            return {'error': 'Session not found'}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            wm._history = data.get('history', [])
            wm._current_session_id = session_id
            if data.get('model'):
                wm._current_model = data['model']
            return {'status': 'ok', 'history': wm._history, 'model': wm._current_model}
        except Exception as e:
            return {'error': str(e)}

    def delete_session(self, session_id):
        path = settings.LOG_DIR / 'sessions' / f"{session_id}.json"
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass
        
        if wm._current_session_id == session_id:
            self.clear_history()
        return {'status': 'ok'}

    def clear_history(self):
        wm._history = []
        wm._current_session_id = None
        return {'status': 'ok'}

    def export_ppt(self, text):
        if wm._window is None:
            return {'error': 'No window'}
        file_types = ('PowerPoint 簡報 (*.pptx)',)
        result = wm._window.create_file_dialog(webview.SAVE_DIALOG, save_filename='簡報.pptx', file_types=file_types)
        if not result or len(result) == 0:
            return {'status': 'cancelled'}
            
        target_path = result[0]
        
        try:
            cmd = [sys.executable]
            if not getattr(sys, 'frozen', False):
                import __main__
                main_file = getattr(__main__, '__file__', 'cat.py')
                cmd.append(main_file)
                
            if getattr(sys, 'frozen', False):
                exe_dir = Path(sys.executable).parent
            else:
                import __main__
                exe_dir = Path(getattr(__main__, '__file__', 'cat.py')).parent
                
            template_path = exe_dir / 'template.pptx'
            if not template_path.exists():
                template_path = settings.LOG_DIR / 'template.pptx'
                
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
        prompt_text = text
        if attached_file:
            try:
                p = Path(attached_file)
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
                
                prompt_text = f"{text}\\n\\n[附加檔案：{p.name}]\\n{file_content}"
            except Exception as e:
                return {'error': f'啟動 Worker 失敗: {e}'}

        sys_prompt = wm._build_system_prompt()
        max_turns = llm.max_history_turns()

        window = wm._history[-(max_turns * 2):] if len(wm._history) > max_turns * 2 else list(wm._history)
        truncated = len(wm._history) > max_turns * 2

        messages = [{'role': 'system', 'content': sys_prompt}]
        messages.extend(window)
        messages.append({'role': 'user', 'content': prompt_text})

        result = llm.chat(messages, model=wm._current_model, timeout=180)

        degraded = None
        if truncated:
            degraded = f'（已截斷較早的對話，保留最近 {max_turns} 輪）'

        if result.get('context_overflow'):
            half = max(len(window) // 2, 0)
            window = window[half:]
            messages = [{'role': 'system', 'content': sys_prompt}]
            messages.extend(window)
            messages.append({'role': 'user', 'content': prompt_text})
            result = llm.chat(messages, model=wm._current_model, timeout=180)
            if result.get('error'):
                return result
            degraded = '內容過長，已縮短貓的記憶重試'

        if result.get('error'):
            return result

        wm._history.append({'role': 'user', 'content': text})
        wm._history.append({'role': 'assistant', 'content': result['content']})

        try:
            sessions_dir = settings.LOG_DIR / 'sessions'
            sessions_dir.mkdir(exist_ok=True)
            if not wm._current_session_id:
                wm._current_session_id = str(uuid.uuid4())
            
            title = "New Chat"
            for msg in wm._history:
                if msg['role'] == 'user':
                    title = msg['content'][:20].replace('\\n', ' ')
                    break
                    
            session_data = {
                'id': wm._current_session_id,
                'title': title,
                'updated_at': time.time(),
                'history': wm._history,
                'model': wm._current_model
            }
            with open(sessions_dir / f"{wm._current_session_id}.json", "w", encoding="utf-8") as f:
                json.dump(session_data, f, ensure_ascii=False)
        except Exception:
            pass

        return {
            'content': result['content'],
            'model': result.get('model', wm._current_model),
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
            if not wm._history:
                return {'error': '沒有對話可匯出'}
            path = llm.export_chat(wm._history, wm._current_model)
            return {'error': None, 'path': str(path)}
        except Exception as exc:
            return {'error': str(exc)}