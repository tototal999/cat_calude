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


def apply_company_deployment(llm_defaults: dict) -> bool:
    """Force the packaged company endpoints while preserving an allowed model."""
    primary_fallbacks = list(llm_defaults['fallback_models'])
    # Models that share the flat base_url; these rotate so the dropdown never
    # loses one when a fallback is selected.
    primary_models = [llm_defaults['model'], *primary_fallbacks]
    endpoint_models = [e['model'] for e in llm_defaults.get('endpoints', [])]
    # Whitelist spans every endpoint's model; base_url is resolved per-model at
    # call time (llm_service.chat), so the flat base_url here is just the default.
    allowed_models = [*primary_models, *endpoint_models]

    global config
    with _config_lock:
        data = _read_config_unlocked()
        llm_config = data.get('llm')
        if not isinstance(llm_config, dict):
            llm_config = {}
            data['llm'] = llm_config
        selected = str(llm_config.get('model') or '').strip()
        if selected not in allowed_models:
            selected = allowed_models[0]
        if selected in primary_models:
            # Rotate within the primary host so every primary model stays listed.
            new_fallbacks = [m for m in primary_models if m != selected]
        else:
            # An extra-endpoint model is selected; leave the primary set intact.
            new_fallbacks = list(primary_fallbacks)
        enforced = {
            'provider': llm_defaults['provider'],
            'base_url': llm_defaults['base_url'],
            'model': selected,
            'fallback_models': new_fallbacks,
            'request_timeout': llm_defaults['request_timeout'],
            'endpoints': llm_defaults.get('endpoints', []),
        }
        for key in ('model_modes', 'task_models'):
            routes = llm_config.get(key)
            if isinstance(routes, dict):
                enforced[key] = {
                    name: model for name, model in routes.items()
                    if str(model).strip() in allowed_models}
        changed = any(llm_config.get(key) != value for key, value in enforced.items())
        if changed:
            llm_config.update(enforced)
        if not changed:
            return False
        temporary = CONFIG_FILE.with_suffix('.tmp')
        try:
            temporary.write_text(
                json.dumps(data, indent=1, ensure_ascii=False), encoding='utf-8')
            temporary.replace(CONFIG_FILE)
        except OSError:
            logger.exception('could not apply deployment defaults')
            temporary.unlink(missing_ok=True)
            raise
        config.clear()
        config.update(data)
        return True
