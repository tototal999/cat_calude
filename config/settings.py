import os
import json
import logging
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
logger = logging.getLogger('claudecat')


def _read_config_unlocked() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError) as exc:
        logger.warning('could not read config: %s', exc)
        return {}


def _merge(target: dict, patch: dict) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge(target[key], value)
        else:
            target[key] = value

def load_config() -> dict:
    """Reload config.json into the module-level ``config`` dict AND return
    a snapshot copy. Callers read this only for initial UI state; writes use
    ``merge_config`` so independent owners do not overwrite each other. Returning None here (the original
    refactor did) crashed the app on startup before the cat even appeared."""
    global config
    with _config_lock:
        config.clear()
        config.update(_read_config_unlocked())
        return dict(config)

def save_config():
    with _config_lock:
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except OSError:
            logger.exception('could not save config')


def merge_config(patch: dict) -> dict:
    """Atomically merge one owner's keys into config.json within this process."""
    global config
    if not isinstance(patch, dict):
        raise TypeError('config patch must be a dict')
    with _config_lock:
        data = _read_config_unlocked()
        _merge(data, patch)
        temporary = CONFIG_FILE.with_suffix('.tmp')
        try:
            temporary.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding='utf-8')
            temporary.replace(CONFIG_FILE)
        except OSError:
            logger.exception('could not merge config')
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                logger.warning('could not remove temporary config: %s', temporary)
            raise
        config.clear()
        config.update(data)
        return dict(data)
