"""Optional, unofficial reader for the locally installed Codex app-server.

It never reads, logs, or transports an OAuth token itself.  Codex owns its
own authenticated app-server session; this module sends only JSON-RPC
``initialize`` and ``account/rateLimits/read`` requests over that process's
standard input.  The protocol is experimental and may change with Codex.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUEST_TIMEOUT_SECONDS = 12


def find_executable() -> Path | None:
    """Find the user-writable Codex runtime, avoiding protected WindowsApps."""
    local_app_data = os.environ.get('LOCALAPPDATA')
    if not local_app_data:
        return None
    bin_dir = Path(local_app_data) / 'OpenAI' / 'Codex' / 'bin'
    candidates = []
    for path in bin_dir.glob('*/codex.exe'):
        try:
            candidates.append((path.stat().st_mtime, path))
        except OSError:
            continue
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1] if candidates else None


def fetch_usage() -> dict[str, Any]:
    """Return normalized Codex limits, or a safe user-facing error message."""
    executable = find_executable()
    if executable is None:
        return {'error': '找不到本機 Codex app-server；請先安裝並登入 Codex Desktop。'}
    try:
        response = _request_rate_limits(executable)
        limits = response.get('rateLimits')
        if not isinstance(limits, dict):
            return {'error': 'Codex 沒有回傳可用的用量資料。'}
        primary = limits.get('primary') if isinstance(limits.get('primary'), dict) else {}
        secondary = limits.get('secondary') if isinstance(limits.get('secondary'), dict) else {}
        if primary.get('usedPercent') is None:
            return {'error': 'Codex 沒有回傳主要用量窗口。'}
        return {
            'usage_pct': float(primary['usedPercent']),
            'weekly_pct': _number_or_none(secondary.get('usedPercent')),
            'resets_at': _unix_to_iso(primary.get('resetsAt')),
            'weekly_resets_at': _unix_to_iso(secondary.get('resetsAt')),
            'plan': limits.get('planType'),
        }
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        detail = str(exc).strip()
        message = 'Codex 用量暫時無法讀取。'
        if detail:
            message += f' {detail}'
        return {'error': message}


def _request_rate_limits(executable: Path) -> dict[str, Any]:
    # codex.exe is a console app; without this flag the windowed build pops a
    # console window on every poll (user-reported: "a cmd window opens and
    # closes every few minutes").
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    process = subprocess.Popen(
        [str(executable), 'app-server', '--stdio'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding='utf-8', bufsize=1, creationflags=creationflags,
    )
    assert process.stdin is not None and process.stdout is not None
    lines: queue.Queue[str | None] = queue.Queue()

    def read_stdout() -> None:
        for line in process.stdout:
            lines.put(line)
        lines.put(None)

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()
    try:
        _send(process, 1, 'initialize', {
            'clientInfo': {'name': 'ClaudeCat', 'version': '1.0'}, 'capabilities': {},
        })
        _receive(lines, 1)
        _send(process, 2, 'account/rateLimits/read', None)
        result = _receive(lines, 2)
        if 'error' in result:
            raise ValueError(_rpc_error_message(result['error']))
        payload = result.get('result')
        if not isinstance(payload, dict):
            raise ValueError('Codex app-server returned an invalid payload')
        return payload
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def _send(process: subprocess.Popen[str], request_id: int, method: str,
          params: dict[str, Any] | None) -> None:
    assert process.stdin is not None
    process.stdin.write(json.dumps({'id': request_id, 'method': method, 'params': params}) + '\n')
    process.stdin.flush()


def _receive(lines: queue.Queue[str | None], request_id: int) -> dict[str, Any]:
    for _ in range(12):
        try:
            line = lines.get(timeout=REQUEST_TIMEOUT_SECONDS)
        except queue.Empty as exc:
            raise TimeoutError('Codex app-server timed out') from exc
        if line is None:
            raise OSError('Codex app-server closed before responding')
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get('id') == request_id:
            return message
    raise ValueError('Codex app-server did not return the requested response')


def _rpc_error_message(error: Any) -> str:
    """Return the JSON-RPC server's safe diagnostic without exposing secrets."""
    if isinstance(error, dict):
        message = str(error.get('message') or '').strip()
        code = error.get('code')
        if message and code is not None:
            return f'Codex app-server 拒絕用量請求（{code}）：{message}'
        if message:
            return f'Codex app-server 拒絕用量請求：{message}'
        if code is not None:
            return f'Codex app-server 拒絕用量請求（{code}）。'
    return 'Codex app-server 拒絕用量請求。'


def _number_or_none(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _unix_to_iso(value: Any) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    # JSON-RPC providers commonly use Unix milliseconds; normalize both forms.
    seconds = value / 1000 if value > 100_000_000_000 else value
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
