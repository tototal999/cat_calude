import re

with open('chat/window.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add _current_session_id
content = content.replace(
    "_history: list[dict[str, str]] = []\n_current_model: str = ''",
    "_history: list[dict[str, str]] = []\n_current_model: str = ''\n_current_session_id = None"
)

# Add session functions to JsApi
session_api = """
    def list_sessions(self):
        import json
        import cat
        sessions_dir = cat.LOG_DIR / 'sessions'
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
        global _history, _current_session_id, _current_model
        import json
        import cat
        path = cat.LOG_DIR / 'sessions' / f"{session_id}.json"
        if not path.exists():
            return {'error': 'Session not found'}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            _history = data.get('history', [])
            _current_session_id = session_id
            if data.get('model'):
                _current_model = data['model']
            return {'status': 'ok', 'history': _history, 'model': _current_model}
        except Exception as e:
            return {'error': str(e)}

    def delete_session(self, session_id):
        import cat
        path = cat.LOG_DIR / 'sessions' / f"{session_id}.json"
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass
        
        global _current_session_id
        if _current_session_id == session_id:
            self.clear_history()
        return {'status': 'ok'}

    def clear_history(self):
        global _history, _current_session_id
        _history = []
        _current_session_id = None
        return {'status': 'ok'}
"""

content = content.replace(
    """    def clear_history(self):
        global _history
        _history = []
        return {'status': 'ok'}""",
    session_api
)


# Add _save_session call in send_message
save_logic = """        # Success: append to history
        _history.append({'role': 'user', 'content': text})
        _history.append({'role': 'assistant', 'content': result['content']})

        # Save session
        try:
            import json, uuid, time, cat
            global _current_session_id
            sessions_dir = cat.LOG_DIR / 'sessions'
            sessions_dir.mkdir(exist_ok=True)
            if not _current_session_id:
                _current_session_id = str(uuid.uuid4())
            
            title = "New Chat"
            for msg in _history:
                if msg['role'] == 'user':
                    title = msg['content'][:20].replace('\\n', ' ')
                    break
                    
            session_data = {
                'id': _current_session_id,
                'title': title,
                'updated_at': time.time(),
                'history': _history,
                'model': _current_model
            }
            with open(sessions_dir / f"{_current_session_id}.json", "w", encoding="utf-8") as f:
                json.dump(session_data, f, ensure_ascii=False)
        except Exception:
            pass"""

content = content.replace(
    """        # Success: append to history
        _history.append({'role': 'user', 'content': text})
        _history.append({'role': 'assistant', 'content': result['content']})""",
    save_logic
)

with open('chat/window.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated window.py!")
