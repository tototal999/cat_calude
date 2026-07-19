"""Prompt construction for controlled English / Traditional Chinese translation."""
from __future__ import annotations

import re
from typing import Any

from backend.services import llm_service as llm

_TARGETS = {'zh-TW': '繁體中文', 'en': '英文'}
_MODES = {
    'general': '一般翻譯，語意正確、自然易讀。',
    'technical': '技術翻譯，保留工程與 ERP 語境，避免任意意譯術語。',
    'business': '正式商務翻譯，語氣專業、禮貌且精準。',
    'bilingual': '中英對照：每段先列原文，再列譯文。',
}
_DEFAULT_GLOSSARY = {
    'Purchase Order': '採購單',
    'Receipt': '收料',
    'Reject': '剔退',
    'Organization': '庫存組織',
    'Concurrent Program': '並行程式',
}


def translate(text: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Translate through the task-routed LLM and surface its errors unchanged."""
    if not isinstance(text, str) or not text.strip():
        return {'error': '請先輸入要翻譯的內容。'}
    options = options if isinstance(options, dict) else {}
    protected_text, protected = protect_content(text, options)
    messages = build_messages(protected_text, options)
    result = llm.chat(
        messages,
        model=llm.model_for_task('translation'),
        timeout=llm.request_timeout(),
    )
    if result.get('error'):
        return result
    try:
        result['content'] = restore_content(result.get('content', ''), protected)
    except ValueError as exc:
        return {'error': str(exc)}
    return result


def protect_content(text: str, options: dict[str, Any]) -> tuple[str, dict[str, str]]:
    """Replace non-translatable fragments with stable placeholders before LLM use."""
    if not options.get('preserve_code', True):
        return text, {}
    patterns = (
        r'```[\s\S]*?```',                 # fenced code
        r'`[^`\n]+`',                      # inline code
        r"'(?:[^'\\]|\\.)*'",             # SQL/string constants
        r'"(?:[^"\\]|\\.)*"\s*:',       # JSON keys
        r'\b(?:[A-Z][A-Z0-9_]{1,}|[A-Za-z][A-Za-z0-9+.-]*://[^\s]+|/[A-Za-z0-9_./-]+|[\w.-]+\.(?:json|ya?ml|py|js|sql|md|csv|xlsx?|docx?|pptx?))\b',
    )
    protected: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        token = f'[[[CC_PROTECTED_{len(protected):04d}]]]'
        protected[token] = match.group(0)
        return token

    return re.sub('|'.join(f'(?:{pattern})' for pattern in patterns), replace, text), protected


def restore_content(text: str, protected: dict[str, str]) -> str:
    if not isinstance(text, str):
        raise ValueError('翻譯模型回傳格式無效。')
    missing = [token for token in protected if text.count(token) != 1]
    if missing:
        return_error = '翻譯結果未能完整保留程式碼或識別碼，請重試或關閉保護後人工確認。'
        raise ValueError(return_error)
    for token, original in protected.items():
        text = text.replace(token, original)
    return text


def build_messages(text: str, options: dict[str, Any]) -> list[dict[str, str]]:
    target = _TARGETS.get(str(options.get('target') or ''), '繁體中文')
    mode = _MODES.get(str(options.get('mode') or ''), _MODES['general'])
    rules = [
        '你是企業文件翻譯助手。只輸出翻譯結果，不要補充說明或自行回答內容。',
        f'目標語言：{target}。{mode}',
        '不得翻譯或修改程式碼、SQL 欄位名稱、單引號內常數、JSON Key、API path、檔名、錯誤碼、版本號與識別碼。',
    ]
    if options.get('preserve_code', True):
        rules.append('保留 fenced code block 與 inline code 原樣。')
    if options.get('preserve_tables', True):
        rules.append('保留 Markdown 表格結構、欄位數與分隔列。')
    if options.get('use_glossary', True):
        glossary = glossary_for_prompt(llm.translation_glossary())
        if glossary:
            rules.append(f'固定術語表（需優先採用）：\n{glossary}')
    return [
        {'role': 'system', 'content': '\n'.join(rules)},
        {'role': 'user', 'content': text},
    ]


def glossary_for_prompt(glossary: dict[str, str] | None = None) -> str:
    entries = glossary if isinstance(glossary, dict) and glossary else _DEFAULT_GLOSSARY
    safe = [(str(source).strip(), str(target).strip()) for source, target in entries.items()]
    return '\n'.join(f'- {source} → {target}' for source, target in safe if source and target)
