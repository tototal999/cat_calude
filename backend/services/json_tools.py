"""Deterministic JSON utilities for the desktop AI toolbox.

These operations intentionally never call an LLM.  They are suitable for
offline use and preserve object-key order unless the caller explicitly asks
for another operation (which the MVP does not expose).
"""
from __future__ import annotations

import json
from typing import Any

MAX_INPUT_CHARS = 1_000_000
MAX_DEPTH = 100
MAX_NODES = 100_000


def process(text: str, action: str = 'format', query: str = '') -> dict[str, Any]:
    """Validate JSON and return a deterministic view for the requested action."""
    if not isinstance(text, str) or not text.strip():
        return {'error': '請先貼上 JSON 內容。', 'valid': False}
    if len(text) > MAX_INPUT_CHARS:
        return {'error': f'JSON 超過 {MAX_INPUT_CHARS:,} 字元上限。', 'valid': False}
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        return {
            'error': f'JSON 格式錯誤：第 {exc.lineno} 行、第 {exc.colno} 欄：{exc.msg}',
            'valid': False,
            'line': exc.lineno,
            'column': exc.colno,
        }

    structure_error = _structure_error(value)
    if structure_error:
        return {'error': structure_error, 'valid': False}
    result: dict[str, Any] = {'valid': True, 'data': value}
    if action == 'minify':
        result['text'] = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    elif action == 'format':
        result['text'] = json.dumps(value, ensure_ascii=False, indent=2)
    elif action == 'validate':
        result['text'] = 'JSON 格式正確。'
    elif action == 'search':
        result['matches'] = search(value, query)
    else:
        return {'error': '不支援的 JSON 操作。', 'valid': True}
    return result


def _structure_error(value: Any) -> str | None:
    """Bound tree traversal before rendering/searching it in the WebView."""
    nodes = 0
    pending = [(value, 1)]
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if nodes > MAX_NODES:
            return f'JSON 節點超過 {MAX_NODES:,} 個上限。'
        if depth > MAX_DEPTH:
            return f'JSON 巢狀層級超過 {MAX_DEPTH} 層上限。'
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
    return None


def search(value: Any, query: str, limit: int = 100) -> list[dict[str, str]]:
    """Find matching keys or scalar values and report stable JSONPath values."""
    needle = str(query or '').casefold().strip()
    if not needle:
        return []
    matches: list[dict[str, str]] = []

    def visit(item: Any, path: str) -> None:
        if len(matches) >= limit:
            return
        if isinstance(item, dict):
            for key, child in item.items():
                key_text = str(key)
                child_path = f'{path}[{json.dumps(key_text, ensure_ascii=False)}]'
                if needle in key_text.casefold():
                    matches.append({'path': child_path, 'kind': 'key', 'preview': key_text})
                visit(child, child_path)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, f'{path}[{index}]')
        else:
            preview = str(item)
            if needle in preview.casefold():
                matches.append({'path': path, 'kind': 'value', 'preview': preview[:200]})

    visit(value, '$')
    return matches[:limit]
