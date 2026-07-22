"""Company LLM deployment compiled into packaged builds."""
from __future__ import annotations

import sys
from typing import Any
from urllib.parse import urlparse


class DeploymentError(RuntimeError):
    pass


_llm: dict[str, Any] | None = None


def _validate(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DeploymentError('公司 LLM 部署設定格式無效。')
    base_url = str(value.get('base_url') or '').strip().rstrip('/')
    parsed = urlparse(base_url)
    primary = str(value.get('model') or '').strip()
    fallbacks = value.get('fallback_models', [])
    if (parsed.scheme not in {'http', 'https'} or not parsed.netloc
            or parsed.hostname in {'localhost', '127.0.0.1', '::1'}):
        raise DeploymentError('公司 LLM API URL 無效。')
    if not primary or not isinstance(fallbacks, list):
        raise DeploymentError('公司 LLM 模型清單無效。')
    models: list[str] = []
    for item in [primary, *fallbacks]:
        model = str(item).strip()
        if not model or len(model) > 200:
            raise DeploymentError('公司 LLM 模型名稱無效。')
        if model not in models:
            models.append(model)
    timeout = value.get('request_timeout', 120)
    if not isinstance(timeout, int) or not 5 <= timeout <= 600:
        raise DeploymentError('公司 LLM Timeout 必須介於 5 到 600 秒。')
    return {
        'provider': 'company',
        'base_url': base_url,
        'model': models[0],
        'fallback_models': models[1:],
        'request_timeout': timeout,
    }


def load() -> dict[str, Any] | None:
    """Load the mandatory baked deployment in packaged builds."""
    global _llm
    if not getattr(sys, 'frozen', False):
        _llm = None
        return None
    try:
        from config import _baked_deployment
    except ImportError as exc:
        raise DeploymentError('找不到內嵌的公司 LLM 部署設定。') from exc
    _llm = _validate(getattr(_baked_deployment, 'LLM', None))
    return dict(_llm)


def managed() -> bool:
    return _llm is not None


def settings() -> dict[str, Any]:
    if _llm is None:
        raise DeploymentError('公司 LLM 部署設定尚未載入。')
    return dict(_llm)


def models() -> list[str]:
    value = settings()
    return [value['model'], *value['fallback_models']]

