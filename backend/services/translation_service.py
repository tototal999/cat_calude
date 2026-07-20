"""Prompt construction for controlled English / Chinese translation."""
from __future__ import annotations

import re
from typing import Any

from backend.services import llm_service as llm

_SOURCES = {'auto': '自動偵測', 'zh-TW': '繁體中文', 'zh-CN': '簡體中文', 'en': '英文'}
_TARGETS = {'zh-TW': '繁體中文', 'zh-CN': '簡體中文', 'en': '英文'}
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
    source_code = str(options.get('source') or 'auto')
    target_code = str(options.get('target') or 'zh-TW')
    if source_code not in _SOURCES or target_code not in _TARGETS:
        return {'error': '不支援選擇的翻譯語言。'}
    if source_code != 'auto' and source_code == target_code:
        return {'error': '來源語言與目標語言不可相同。'}
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
    source_code = str(options.get('source') or 'auto')
    target_code = str(options.get('target') or 'zh-TW')
    source = _SOURCES.get(source_code, '自動偵測')
    target = _TARGETS.get(target_code, '繁體中文')
    mode = _MODES.get(str(options.get('mode') or ''), _MODES['general'])
    rules = [
        '你是企業文件翻譯助手。只輸出翻譯結果，不要補充說明或自行回答內容。',
        f'來源語言：{source}。目標語言：{target}。{mode}',
        '不得翻譯或修改程式碼、SQL 欄位名稱、單引號內常數、JSON Key、API path、檔名、錯誤碼、版本號與識別碼。',
    ]
    if target_code == 'zh-CN':
        rules.append('中文內容一律使用簡體中文字形，不得混入繁體中文字形。')
    if options.get('preserve_code', True):
        rules.append('保留 fenced code block 與 inline code 原樣。')
    if options.get('preserve_tables', True):
        rules.append('保留 Markdown 表格結構、欄位數與分隔列。')
    if options.get('use_glossary', True) and target_code != 'en':
        glossary = glossary_for_prompt(llm.translation_glossary())
        if glossary:
            glossary_rule = '固定術語表（需優先採用）'
            if target_code == 'zh-CN':
                glossary_rule += '；採用其語意，但輸出字形需轉為簡體中文'
            rules.append(f'{glossary_rule}：\n{glossary}')
    return [
        {'role': 'system', 'content': '\n'.join(rules)},
        {'role': 'user', 'content': text},
    ]


def glossary_for_prompt(glossary: dict[str, str] | None = None) -> str:
    entries = glossary if isinstance(glossary, dict) and glossary else _DEFAULT_GLOSSARY
    safe = [(str(source).strip(), str(target).strip()) for source, target in entries.items()]
    return '\n'.join(f'- {source} → {target}' for source, target in safe if source and target)
