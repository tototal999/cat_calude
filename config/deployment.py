"""Company LLM deployment compiled into packaged builds."""
from __future__ import annotations

import sys
from typing import Any
from urllib.parse import urlparse


class DeploymentError(RuntimeError):
    pass


_llm: dict[str, Any] | None = None


def _check_url(base_url: str) -> str:
    base_url = str(base_url or '').strip().rstrip('/')
    parsed = urlparse(base_url)
    if (parsed.scheme not in {'http', 'https'} or not parsed.netloc
            or parsed.hostname in {'localhost', '127.0.0.1', '::1'}):
        raise DeploymentError('公司 LLM API URL 無效。')
    return base_url


def _check_model(item: object) -> str:
    model = str(item).strip()
    if not model or len(model) > 200:
        raise DeploymentError('公司 LLM 模型名稱無效。')
    return model


def _validate(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DeploymentError('公司 LLM 部署設定格式無效。')
    base_url = _check_url(value.get('base_url'))
    primary = str(value.get('model') or '').strip()
    fallbacks = value.get('fallback_models', [])
    if not primary or not isinstance(fallbacks, list):
        raise DeploymentError('公司 LLM 模型清單無效。')
    # model -> base_url map; the primary endpoint owns model + fallbacks.
    routes: dict[str, str] = {}
    for item in [primary, *fallbacks]:
        model = _check_model(item)
        routes.setdefault(model, base_url)
    # Optional extra endpoints, each its own base_url/model. Selecting one of
    # their models routes the call there instead of the primary host. No api
    # key is baked (the "no secrets in company-defaults" rule stays intact).
    endpoints_value = value.get('endpoints', [])
    if not isinstance(endpoints_value, list):
        raise DeploymentError('公司 LLM endpoints 必須是清單。')
    endpoints: list[dict[str, str]] = []
    for entry in endpoints_value:
        if not isinstance(entry, dict):
            raise DeploymentError('公司 LLM endpoint 格式無效。')
        if entry.get('api_key'):
            raise DeploymentError('endpoints 不得包含 api_key。')
        name = str(entry.get('name') or '').strip()
        ep_url = _check_url(entry.get('base_url'))
        ep_model = _check_model(entry.get('model'))
        if not name:
            raise DeploymentError('公司 LLM endpoint 需要 name。')
        if ep_model in routes:
            raise DeploymentError(f'模型 {ep_model} 重複出現在多個端點。')
        routes[ep_model] = ep_url
        endpoints.append({'name': name, 'base_url': ep_url, 'model': ep_model})
    timeout = value.get('request_timeout', 120)
    if not isinstance(timeout, int) or not 5 <= timeout <= 600:
        raise DeploymentError('公司 LLM Timeout 必須介於 5 到 600 秒。')
    fallback_models = [m for m in routes if routes[m] == base_url and m != primary]
    return {
        'provider': 'company',
        'base_url': base_url,
        'model': primary,
        'fallback_models': fallback_models,
        'request_timeout': timeout,
        'endpoints': endpoints,
        'routes': routes,
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
    """Every selectable model across all endpoints, primary first."""
    value = settings()
    result = [value['model'], *value['fallback_models']]
    for endpoint in value.get('endpoints', []):
        if endpoint['model'] not in result:
            result.append(endpoint['model'])
    return result


def base_url_for(model: str) -> str:
    """The endpoint base_url that serves ``model`` (primary host if unknown)."""
    value = settings()
    return value.get('routes', {}).get(str(model or '').strip(), value['base_url'])

