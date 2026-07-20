"""
LLM client for ClaudeCat (Part 2).
====================================

OpenAI-compatible chat completions client.  Talks to any endpoint that
speaks ``/v1/chat/completions`` (vLLM, Ollama, LM Studio, llama.cpp …).

Design decisions (spec 2.2):
- No streaming (SSE deferred to Part 3).
- Timeout 60s (cold model load can take 10-30s).
- Context overflow: caller detects HTTP 400 with context/length/token
  keywords and halves history once; this module just surfaces the error.
- Debug logging is opt-in (``llm.debug_log: true`` in config).

This module is stateless: no history, no config persistence.  Config is
read from cat.py's CONFIG_FILE; history lives in chat/window.py.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import requests
from config import settings

logger = logging.getLogger('claudecat')

# ---- Config defaults (overridden by config.json ``llm`` block) ------------
# No real endpoint is committed here - this repo is public. Your actual
# base_url/model/api_key go in the *runtime* config.json (never checked
# into git), e.g.:
#   "llm": {"base_url": "http://your-host:8000/v1", "model": "your-model"}

_DEFAULTS: dict[str, Any] = {
    'base_url': 'http://localhost:8000/v1',   # example only - set your own in config.json
    'model': '',
    'api_key': '',
    'system_prompt': (
        '你是專業的 AI 助手。\n'
        '請以詳盡、專業的繁體中文回答使用者的問題，協助分析資料與撰寫程式，無須限制字數。'
    ),
    'max_history_turns': 20,
    'fallback_models': [],
    'export_dir': '',
    'debug_log': False,
    'max_file_chars': 50000,
    'max_file_bytes': 10 * 1024 * 1024,
    'provider': 'company',
    'request_timeout': 120,
    'model_mode': 'auto',
    'model_modes': {},
    'task_models': {},
    'translation_glossary': {},
}

_config: dict[str, Any] = {}
_config_file: Path | None = None
_debug_dir: Path | None = None
_local_sidecar_active = False


def init(config_file: Path) -> None:
    """Load LLM settings from the ``llm`` block in config.json."""
    global _config, _config_file, _debug_dir, _local_sidecar_active
    _local_sidecar_active = False
    _config_file = config_file
    try:
        data = json.loads(config_file.read_text(encoding='utf-8'))
        _config = data.get('llm', {}) if isinstance(data, dict) else {}
    except (OSError, ValueError):
        _config = {}

    if _get('debug_log'):
        export = _export_dir()
        _debug_dir = export / 'debug'
        _debug_dir.mkdir(parents=True, exist_ok=True)
    else:
        _debug_dir = None


def _get(key: str) -> Any:
    return _config.get(key, _DEFAULTS.get(key))


def _export_dir() -> Path:
    d = _get('export_dir')
    if d:
        return Path(d)
    # Default: beside config.json (i.e. %LOCALAPPDATA%\ClaudeCat)
    if _config_file:
        return _config_file.parent
    return Path('.')


def save_config_model(model: str) -> None:
    """Persist the selected model back to config.json ``llm.model``."""
    if not _config_file:
        raise RuntimeError('LLM 設定尚未初始化。')
    model = str(model or '').strip()
    models = list_models()
    if model not in models:
        raise ValueError('選擇的模型不在可用清單中。')
    fallbacks = [item for item in models if item != model]
    settings.merge_config({'llm': {
        'model': model,
        'fallback_models': fallbacks,
    }})
    _config['model'] = model
    _config['fallback_models'] = fallbacks


# ---- Public API -----------------------------------------------------------

def list_models() -> list[str]:
    """Return available model names from config (no API call).

    The primary model is always first, followed by fallback_models.
    Duplicates are removed while preserving order.
    """
    primary = _get('model') or ''
    fallbacks = _get('fallback_models') or []
    seen: set[str] = set()
    result: list[str] = []
    for m in [primary, *fallbacks]:
        m = str(m).strip()
        if m and m not in seen:
            seen.add(m)
            result.append(m)
    return result


def current_model() -> str:
    return model_for_task('chat')


def request_timeout() -> int:
    value = _get('request_timeout')
    return int(value) if isinstance(value, (int, float)) and 5 <= value <= 600 else 120


def translation_glossary() -> dict[str, str]:
    glossary = _get('translation_glossary')
    if not isinstance(glossary, dict):
        return {}
    return {str(key): str(value) for key, value in glossary.items()
            if str(key).strip() and str(value).strip()}


_MODEL_MODES = (
    ('auto', '自動選擇'),
    ('fast', '快速'),
    ('quality', '高品質'),
    ('code', '程式分析'),
    ('translation', '翻譯'),
)
_TASKS = ('chat', 'translation', 'document', 'code', 'error_analysis')


def list_model_modes() -> list[dict[str, str]]:
    return [{'id': key, 'label': label} for key, label in _MODEL_MODES]


def model_mode() -> str:
    mode = str(_get('model_mode') or 'auto')
    return mode if mode in {key for key, _label in _MODEL_MODES} else 'auto'


def model_for_task(task: str, fallback: str = '') -> str:
    """Resolve a real model id without exposing routing details to normal users."""
    if _local_sidecar_active or _get('provider') == 'local':
        # A llama.cpp sidecar accepts its own alias, not company task-route ids.
        return str(_get('model') or 'local-model').strip()
    task = str(task or 'chat')
    task_models = _get('task_models')
    if isinstance(task_models, dict):
        selected = str(task_models.get(task) or '').strip()
        if selected:
            return selected
    modes = _get('model_modes')
    if isinstance(modes, dict):
        selected = str(modes.get(model_mode()) or '').strip()
        if selected:
            return selected
    return str(fallback or _get('model') or '').strip()


def public_settings() -> dict[str, Any]:
    """Return editable LLM settings; intentionally excludes the API key."""
    modes = _get('model_modes')
    routes = _get('task_models')
    return {
        'provider': str(_get('provider') or 'company'),
        'base_url': str(_get('base_url') or ''),
        'model': str(_get('model') or ''),
        'request_timeout': request_timeout(),
        'model_mode': model_mode(),
        'model_modes': modes if isinstance(modes, dict) else {},
        'task_models': routes if isinstance(routes, dict) else {},
        'api_key_managed_externally': True,
    }


def save_toolbox_settings(values: dict[str, Any]) -> dict[str, Any]:
    """Validate and merge non-secret advanced settings into runtime config."""
    if not isinstance(values, dict):
        raise ValueError('設定格式無效。')
    patch: dict[str, Any] = {}
    provider = str(values.get('provider') or '').strip()
    if provider:
        if provider not in {'company', 'ollama', 'openai-compatible', 'local'}:
            raise ValueError('Provider 設定無效。')
        patch['provider'] = provider
    base_url = str(values.get('base_url') or '').strip().rstrip('/')
    if base_url:
        if not re.match(r'^https?://[^\s/]+(?::\d+)?(?:/[^\s]*)?$', base_url):
            raise ValueError('API URL 必須是 http 或 https URL。')
        patch['base_url'] = base_url
    model = str(values.get('model') or '').strip()
    if model:
        patch['model'] = model[:200]
    timeout = values.get('request_timeout')
    if timeout not in (None, ''):
        try:
            timeout = int(timeout)
        except (TypeError, ValueError) as exc:
            raise ValueError('Timeout 必須是數字。') from exc
        if not 5 <= timeout <= 600:
            raise ValueError('Timeout 必須介於 5 到 600 秒。')
        patch['request_timeout'] = timeout
    mode = str(values.get('model_mode') or '').strip()
    if mode:
        if mode not in {key for key, _label in _MODEL_MODES}:
            raise ValueError('模型模式設定無效。')
        patch['model_mode'] = mode
    for key, allowed in (('model_modes', {item[0] for item in _MODEL_MODES}),
                         ('task_models', set(_TASKS))):
        value = values.get(key)
        if value is not None:
            if not isinstance(value, dict):
                raise ValueError(f'{key} 必須是物件。')
            patch[key] = {name: str(value.get(name) or '').strip()[:200]
                          for name in allowed if name in value}
    if patch:
        settings.merge_config({'llm': patch})
        _config.update(patch)
    return public_settings()


def use_local_endpoint(endpoint: str, model: str = '') -> None:
    """Use a loopback llama.cpp endpoint for this process only.

    This deliberately does not overwrite the user's configured remote endpoint.
    """
    if not endpoint.startswith('http://127.0.0.1:'):
        raise ValueError('本機模型端點必須使用 127.0.0.1。')
    global _local_sidecar_active
    _local_sidecar_active = True
    _config['base_url'] = endpoint
    _config['model'] = str(model or 'local-model').strip()


def is_local_endpoint() -> bool:
    """True only when this process is configured to call a loopback model."""
    base = str(_get('base_url') or '')
    return base.startswith('http://127.0.0.1:') or base.startswith('http://localhost:')


def max_history_turns() -> int:
    n = _get('max_history_turns')
    return int(n) if isinstance(n, (int, float)) and n > 0 else 20


def system_prompt() -> str:
    return str(_get('system_prompt') or _DEFAULTS['system_prompt'])


def max_file_chars() -> int:
    n = _get('max_file_chars')
    return int(n) if isinstance(n, (int, float)) and n > 0 else 50000


def max_file_bytes() -> int:
    n = _get('max_file_bytes')
    return int(n) if isinstance(n, (int, float)) and n > 0 else 10 * 1024 * 1024


def chat(messages: list[dict[str, str]],
         model: str | None = None,
         timeout: int = 60) -> dict[str, Any]:
    """Send a chat completion request.  Returns a dict with either:

    - ``{'content': str, 'model': str}`` on success, or
    - ``{'error': str, 'context_overflow': bool}`` on failure.

    ``context_overflow`` is True when the error looks like a context-length
    problem (HTTP 400 + keywords), signalling the caller to halve history
    and retry once.
    """
    model = model or current_model()
    base = str(_get('base_url') or _DEFAULTS['base_url']).rstrip('/')
    url = f'{base}/chat/completions'

    headers: dict[str, str] = {'Content-Type': 'application/json'}
    api_key = _get('api_key')
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    payload = {
        'model': model,
        'messages': messages,
    }

    _debug_log_request(payload)
    t0 = time.time()

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.ConnectionError:
        return {'error': f'無法連線 {base}（連線被拒或網路不通）',
                'context_overflow': False}
    except requests.Timeout:
        return {'error': f'請求逾時（{timeout} 秒）',
                'context_overflow': False}
    except Exception as exc:
        return {'error': f'請求失敗: {exc}',
                'context_overflow': False}

    elapsed = time.time() - t0

    if resp.status_code != 200:
        err_msg = _extract_error(resp)
        overflow = (resp.status_code == 400
                    and _looks_like_context_overflow(err_msg))
        logger.error('llm %d in %.1fs: %s', resp.status_code, elapsed, err_msg)
        return {'error': err_msg, 'context_overflow': overflow}

    try:
        data = resp.json()
    except ValueError:
        return {'error': '回應不是有效 JSON', 'context_overflow': False}

    _debug_log_response(data, elapsed)

    choice = (data.get('choices') or [{}])[0]
    content = (choice.get('message') or {}).get('content', '')
    used_model = data.get('model', model)
    if not isinstance(content, str) or not content.strip():
        return {'error': '模型回傳空白內容', 'context_overflow': False}

    logger.info('llm ok in %.1fs model=%s tokens=%s',
                elapsed, used_model, data.get('usage', {}).get('total_tokens'))
    return {'content': content, 'model': used_model}


def probe(timeout: int | None = None, model: str | None = None) -> str | None:
    """Quick connectivity check (max_tokens=1).  Returns None on success,
    or an error string on failure.  Used for the warm-up probe on window open."""
    timeout = timeout if isinstance(timeout, int) and timeout > 0 else min(request_timeout(), 30)
    model = model or current_model()
    base = str(_get('base_url') or _DEFAULTS['base_url']).rstrip('/')
    url = f'{base}/chat/completions'

    headers: dict[str, str] = {'Content-Type': 'application/json'}
    api_key = _get('api_key')
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': 'hi'}],
        'max_tokens': 1,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return None
        return _extract_error(resp)
    except requests.ConnectionError:
        return f'無法連線 {base}'
    except requests.Timeout:
        return f'探測逾時（{timeout} 秒）'
    except Exception as exc:
        return str(exc)


# ---- File I/O (spec 2.2: 寫檔永遠由使用者按鈕觸發) -----------------------

def export_chat(history: list[dict[str, str]], model: str) -> Path:
    """Write full conversation to chat_YYYYMMDD_HHMMSS.md.  Returns path."""
    ts = time.strftime('%Y%m%d_%H%M%S')
    path = _export_dir() / f'chat_{ts}.md'
    lines = [f'# ClaudeCat 對話匯出', f'', f'- 模型: {model}', f'- 時間: {ts}', '']
    for msg in history:
        role = '🐱' if msg['role'] == 'assistant' else '👤'
        lines.append(f'### {role} {msg["role"]}')
        lines.append('')
        lines.append(msg.get('content', ''))
        lines.append('')
    path.write_text('\n'.join(lines), encoding='utf-8')
    logger.info('exported chat to %s', path)
    return path


def save_note(content: str, model: str) -> Path:
    """Write a single assistant reply to note_YYYYMMDD_HHMMSS.md."""
    ts = time.strftime('%Y%m%d_%H%M%S')
    path = _export_dir() / f'note_{ts}.md'
    text = f'# ClaudeCat 筆記\n\n- 模型: {model}\n- 時間: {ts}\n\n{content}\n'
    path.write_text(text, encoding='utf-8')
    logger.info('saved note to %s', path)
    return path


# ---- Internals ------------------------------------------------------------

_CONTEXT_KEYWORDS = re.compile(
    r'context|length|token|too.long|maximum|exceed|limit', re.IGNORECASE)


def _looks_like_context_overflow(msg: str) -> bool:
    return bool(_CONTEXT_KEYWORDS.search(msg))


def _extract_error(resp: requests.Response) -> str:
    try:
        body = resp.json()
        msg = (body.get('error', {}) if isinstance(body.get('error'), dict)
               else {}).get('message')
        if not msg and isinstance(body.get('message'), str):
            msg = body['message']
        if msg:
            return f'HTTP {resp.status_code}: {msg}'
    except Exception:
        logger.debug('could not parse error response as JSON', exc_info=True)
    return f'HTTP {resp.status_code}'


def _debug_log_request(payload: dict) -> None:
    if not _debug_dir:
        return
    ts = time.strftime('%Y%m%d_%H%M%S')
    path = _debug_dir / f'req_{ts}.json'
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                        encoding='utf-8')
    except OSError:
        logger.warning('could not write debug request log: %s', path)


def _debug_log_response(data: dict, elapsed: float) -> None:
    if not _debug_dir:
        return
    ts = time.strftime('%Y%m%d_%H%M%S')
    path = _debug_dir / f'resp_{ts}.json'
    try:
        out = {'elapsed_sec': round(elapsed, 2), **data}
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                        encoding='utf-8')
    except OSError:
        logger.warning('could not write debug response log: %s', path)
