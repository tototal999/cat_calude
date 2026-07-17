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
        '你是 ClaudeCat，一隻住在桌面上的像素貓，平常負責監控主人的 Claude 用量。\n'
        '回覆簡短（50 字內），口語自然。'
    ),
    'max_history_turns': 20,
    'fallback_models': [],
    'export_dir': '',
    'debug_log': False,
}

_config: dict[str, Any] = {}
_config_file: Path | None = None
_debug_dir: Path | None = None


def init(config_file: Path) -> None:
    """Load LLM settings from the ``llm`` block in config.json."""
    global _config, _config_file, _debug_dir
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
        return
    try:
        data = json.loads(_config_file.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    llm = data.setdefault('llm', {})
    llm['model'] = model
    _config['model'] = model
    try:
        _config_file.write_text(json.dumps(data, indent=1, ensure_ascii=False),
                                encoding='utf-8')
    except OSError:
        logger.exception('could not save llm.model to config')


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
    return str(_get('model') or '')


def max_history_turns() -> int:
    n = _get('max_history_turns')
    return int(n) if isinstance(n, (int, float)) and n > 0 else 20


def system_prompt() -> str:
    return str(_get('system_prompt') or _DEFAULTS['system_prompt'])


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

    logger.info('llm ok in %.1fs model=%s tokens=%s',
                elapsed, used_model, data.get('usage', {}).get('total_tokens'))
    return {'content': content, 'model': used_model}


def probe(timeout: int = 15) -> str | None:
    """Quick connectivity check (max_tokens=1).  Returns None on success,
    or an error string on failure.  Used for the warm-up probe on window open."""
    model = current_model()
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
        pass
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
        pass


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
        pass
