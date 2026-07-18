"""Lifecycle manager for the packaged llama.cpp server.

No model is downloaded and no listener is exposed beyond 127.0.0.1.  The
runtime is opt-in until the company installer places the binary and GGUF file
next to the application and enables ``local_llm`` in config.json.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
from pathlib import Path

_process: subprocess.Popen | None = None
_status = '本機模型未啟用。'


def _wait_until_ready(process: subprocess.Popen, endpoint: str, timeout_seconds: float = 10.0) -> str | None:
    """Return an error message unless llama.cpp answers on its loopback health URL."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            return f'本機模型服務啟動後結束（exit {return_code}）。'
        try:
            with urlopen(f'{endpoint}/health', timeout=0.5) as response:
                if 200 <= response.status < 300:
                    return None
        except (OSError, URLError):
            time.sleep(0.2)
    return '本機模型服務未在 10 秒內就緒。'


def init(config_file: Path) -> dict:
    """Start the configured local server once and return its safe status."""
    global _status
    try:
        config = json.loads(config_file.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        config = {}
    options = config.get('local_llm', {}) if isinstance(config, dict) else {}
    if not isinstance(options, dict) or not options.get('enabled', False):
        _status = '本機模型未啟用。'
        return {'status': _status, 'endpoint': None}

    app_dir = config_file.parent
    binary = app_dir / str(options.get('server', 'llama-server.exe'))
    model = app_dir / str(options.get('model', 'model.gguf'))
    port = options.get('port', 8080)
    if not isinstance(port, int) or not 1024 <= port <= 65535:
        _status = '本機模型連接埠設定無效。'
        return {'status': _status, 'endpoint': None}
    if not binary.is_file():
        _status = f'找不到本機模型服務：{binary.name}'
        return {'status': _status, 'endpoint': None}
    if not model.is_file():
        _status = f'找不到本機 GGUF 模型：{model.name}'
        return {'status': _status, 'endpoint': None}

    global _process
    if _process is None or _process.poll() is not None:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        try:
            _process = subprocess.Popen(
                [str(binary), '-m', str(model), '--host', '127.0.0.1', '--port', str(port)],
                cwd=str(app_dir), creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            _status = f'無法啟動本機模型服務：{exc}'
            return {'status': _status, 'endpoint': None}
    endpoint = f'http://127.0.0.1:{port}/v1'
    error = _wait_until_ready(_process, endpoint)
    if error:
        if _process.poll() is None:
            _process.terminate()
            try:
                _process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _process.kill()
        _process = None
        _status = error
        return {'status': _status, 'endpoint': None}
    _status = f'本機模型服務已啟動（{endpoint}）。'
    return {'status': _status, 'endpoint': endpoint, 'model': options.get('model_id', '')}


def stop() -> None:
    global _process, _status
    if _process is not None and _process.poll() is None:
        _process.terminate()
        try:
            _process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _process.kill()
    _process = None
    _status = '本機模型服務已停止。'


def status() -> str:
    return _status
