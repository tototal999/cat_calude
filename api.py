"""
API Client
===========

Reads Claude Code OAuth credentials and communicates with the
Anthropic API.  This is the only module that handles credentials.

Network communication exclusively with ``api.anthropic.com``.
Credentials used only in HTTP Authorization headers.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

# Surgical edit: replaced `from .i18n import T` with an inline string table
# so this module is standalone. Keys match the original i18n usage.
T = {
    'no_token': 'No OAuth token found (log in to Claude Code)',
    'connection_error': 'Connection error',
    'auth_expired': 'Auth token expired',
    'http_error': 'HTTP error {code}',
    'server_error': 'Server error {code}',
}

__all__ = ['API_URL_USAGE', 'API_URL_PROFILE', 'CLAUDE_CONFIG_DIR', 'CLAUDE_CREDENTIALS', 'read_access_token', 'api_headers', 'fetch_usage', 'fetch_profile']

# API endpoints & credentials
API_URL_USAGE = 'https://api.anthropic.com/api/oauth/usage'
API_URL_PROFILE = 'https://api.anthropic.com/api/oauth/profile'
CLAUDE_CONFIG_DIR = Path(os.environ.get('CLAUDE_CONFIG_DIR', '')) if os.environ.get('CLAUDE_CONFIG_DIR') else Path.home() / '.claude'
CLAUDE_CREDENTIALS = CLAUDE_CONFIG_DIR / '.credentials.json'
_FALLBACK_USER_AGENT = 'claude-code/2.1.204'
USAGE_API_ENABLED = False  # default OFF; controlled by the desktop menu


def set_usage_api_enabled(enabled: bool) -> None:
    """Allow the optional Claude-limits monitor to make requests."""
    global USAGE_API_ENABLED
    USAGE_API_ENABLED = bool(enabled)


def read_access_token() -> str | None:
    """Read the current access token from the Claude credentials file."""
    if not CLAUDE_CREDENTIALS.exists():
        return None

    try:
        creds = json.loads(CLAUDE_CREDENTIALS.read_text())
        return creds.get('claudeAiOauth', {}).get('accessToken') or None
    except (OSError, ValueError, KeyError):
        # OSError also covers a read racing a concurrent write (the file is
        # rewritten on token rotation/account switch); treat it as "no token
        # right now" rather than letting it crash a caller.
        return None


def api_headers() -> dict[str, str] | None:
    """Return auth headers for the Anthropic OAuth API, or None."""
    token = read_access_token()
    if not token:
        return None

    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'User-Agent': _user_agent(),
        'anthropic-beta': 'oauth-2025-04-20',
    }


def fetch_usage() -> dict[str, Any]:
    """Fetch usage data from the Anthropic OAuth usage API."""
    if not USAGE_API_ENABLED:
        return {'error': 'Claude usage monitor disabled'}
    headers = api_headers()
    if not headers:
        return {'error': T['no_token']}

    try:
        resp = requests.get(API_URL_USAGE, headers=headers, timeout=10)
        resp.raise_for_status()
        return _merge_scoped_limits(resp.json())
    except requests.ConnectionError:
        return {'error': T['connection_error']}
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        server_msg = _extract_server_message(e.response)
        extra: dict[str, Any] = {}
        if server_msg:
            extra['server_message'] = server_msg

        if code == 401:
            return {**extra, 'error': T['auth_expired'], 'auth_error': True}
        if code == 429:
            retry = _parse_retry_after(e.response)
            if retry is not None:
                extra['retry_after'] = retry
            return {**extra, 'error': T['http_error'].format(code=429), 'rate_limited': True}
        if 500 <= code < 600:
            return {**extra, 'error': T['server_error'].format(code=code)}
        return {**extra, 'error': T['http_error'].format(code=code or '?')}
    except Exception:
        return {'error': T['connection_error']}


def fetch_profile() -> dict[str, Any] | None:
    """Fetch account profile from the Anthropic OAuth profile API."""
    headers = api_headers()
    if not headers:
        return None

    try:
        resp = requests.get(API_URL_PROFILE, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


# Helpers


def _merge_scoped_limits(data: dict[str, Any]) -> dict[str, Any]:
    """Expose model-scoped limits from the ``limits`` array as quota fields.

    Newer usage responses carry per-model weekly limits only inside the
    ``limits`` array (via ``scope.model``), no longer as top-level fields
    like ``seven_day_sonnet``.  To keep them visible without hardcoding any
    field name, each active scoped limit is mapped onto a synthetic quota
    field that the existing field-name auto-detection understands.

    The period prefix is derived from the response, not assumed: the
    non-scoped limit of the same ``group`` shares its ``resets_at`` with an
    existing top-level quota field, whose name supplies the prefix (e.g. a
    weekly limit scoped to Fable becomes ``seven_day_fable``).  Inactive
    scoped limits (no reset window) are still surfaced at 0% so the model's
    limit is visible before it is first used; an existing top-level field is
    never overwritten (it carries higher-precision data).

    Parameters
    ----------
    data : dict
        Raw usage API response.

    Returns
    -------
    dict
        The response with synthetic quota fields added for any model-scoped
        limits not already present as top-level fields.
    """
    limits = data.get('limits')
    if not isinstance(limits, list):
        return data

    # resets_at -> existing top-level quota field name (the prefix source)
    reset_to_field: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, dict) and value.get('utilization') is not None:
            resets_at = value.get('resets_at')
            if resets_at:
                reset_to_field.setdefault(resets_at, key)

    # group -> period prefix, via the non-scoped limit's shared reset time
    group_prefix: dict[str, str] = {}
    for limit in limits:
        if not isinstance(limit, dict) or limit.get('scope'):
            continue
        group = limit.get('group')
        resets_at = limit.get('resets_at')
        if group and resets_at and resets_at in reset_to_field:
            group_prefix.setdefault(group, reset_to_field[resets_at])

    merged = dict(data)
    for limit in limits:
        if not isinstance(limit, dict):
            continue
        model = (limit.get('scope') or {}).get('model') or {}
        display_name = model.get('display_name')
        prefix = group_prefix.get(limit.get('group'))
        if not display_name or not prefix:
            continue

        field = f'{prefix}_{_model_slug(display_name)}'
        if merged.get(field) is not None:
            continue
        merged[field] = {'utilization': float(limit.get('percent') or 0), 'resets_at': limit.get('resets_at')}

    return merged


def _model_slug(display_name: str) -> str:
    """Convert a model display name into a field-name suffix (e.g. ``'Fable'`` -> ``'fable'``)."""
    cleaned = ''.join(char if char.isalnum() else ' ' for char in display_name.lower())
    return '_'.join(cleaned.split())


_cached_user_agent: str | None = None


def _user_agent() -> str:
    """Return the User-Agent string with the installed Claude Code version.

    Surgical edit: replaced the `.claude_cli` module dependency with a direct
    `claude --version` call, cached for the process lifetime.  The correct
    claude-code User-Agent is required to avoid the aggressive rate-limit
    bucket on the usage endpoint.
    """
    global _cached_user_agent
    if _cached_user_agent is not None:
        return _cached_user_agent

    import re
    import subprocess
    try:
        out = subprocess.run(
            ['claude', '--version'],
            capture_output=True, text=True, timeout=10, shell=(os.name == 'nt'),
        ).stdout
        match = re.search(r'(\d+\.\d+\.\d+)', out or '')
        _cached_user_agent = f'claude-code/{match.group(1)}' if match else _FALLBACK_USER_AGENT
    except Exception:
        _cached_user_agent = _FALLBACK_USER_AGENT
    return _cached_user_agent


def _extract_server_message(response: requests.Response | None) -> str | None:
    """Extract ``error.message`` from a JSON error response body.

    Strips the trailing "Please try again later." suffix that the API
    appends to some error messages - the app retries automatically, so
    the advice would be misleading.
    """
    if response is None:
        return None
    try:
        msg = response.json().get('error', {}).get('message') or None
        if msg:
            msg = msg.removesuffix(' Please try again later.').removesuffix(' Please try again later').strip()
        return msg or None
    except Exception:
        return None


def _parse_retry_after(response: requests.Response | None) -> int | None:
    """Parse the ``Retry-After`` header as an integer number of seconds."""
    if response is None:
        return None
    raw = response.headers.get('Retry-After')
    if raw is None:
        return None
    try:
        return max(int(raw), 0)
    except (ValueError, TypeError):
        return None
