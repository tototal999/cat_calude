import os
import json
from pathlib import Path
import threading

LOG_DIR = Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'ClaudeCat'
LOG_FILE = LOG_DIR / 'claudecat.log'
CONFIG_FILE = LOG_DIR / 'config.json'
SCHEDULE_FILE = LOG_DIR / 'schedule.json'
SESSIONS_DIR = LOG_DIR / 'sessions'

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

config = {}
_config_lock = threading.Lock()
_usage_status = ''

def load_config():
    global config
    with _config_lock:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config.update(json.load(f))
            except Exception:
                pass

def save_config():
    with _config_lock:
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

def set_usage_status(status: str) -> None:
    global _usage_status
    _usage_status = status

def get_usage_status() -> str:
    return _usage_status
