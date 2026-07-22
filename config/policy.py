"""Read-only company feature policy, compiled into the exe at build time.

``ClaudeCat.spec`` reads ``feature-policy.json`` during the build and writes it
out as ``config/_baked_policy.py``, which is then compiled into the PYZ archive;
the generated source is removed once the build finishes.  Packaged builds import
that module - they never read a policy file from disk.  That is deliberate: a
policy shipped as data (beside the exe, or under ``_internal/`` in an onedir
build) is an ordinary file that can be edited or deleted, and deleting it would
turn every feature back on.  Changing the policy therefore means rebuilding.

The company LLM endpoint and model whitelist are compiled in the same way, so a
released build needs no ``company-defaults.json`` beside the exe.  That file is
a *build input* (kept out of Git); this module is a *policy* and is never
written to config.json, so the user cannot flip a disabled feature back on.

Packaged builds fail closed: a missing, malformed, incomplete or
mandatory-disabling policy raises PolicyError rather than enabling everything.
Development runs have no baked module and stay unrestricted on purpose.

Nothing here writes to disk.

This is a deployment control, not a security boundary.  Someone who unpacks the
PyInstaller archive and recompiles the module can still reach it - the point is
that editing a JSON in Notepad no longer does.
"""
from __future__ import annotations

import json
import logging
import sys
import threading
from pathlib import Path

logger = logging.getLogger('claudecat')

POLICY_SOURCE = 'feature-policy.json'   # edited by tools/feature-policy-editor.html

# Canonical feature ids.  Keep in sync with tools/feature-policy-editor.html.
# Sub-features use "parent.child" and are implicitly off when the parent is off.
MAIN_FEATURES = (
    ('quick_question', '快速提問'),
    ('chat', '交談（LLM 介面）'),
    ('documents', '文件助手'),
    ('json', 'JSON 工具'),
    ('translate', '翻譯'),
    ('settings', '模型設定'),
    ('schedule', '排程'),
)
SUB_FEATURES = (
    ('documents.meeting_pack', '文件會議包'),
    ('documents.compare', '比較文件'),
    ('chat.attachments', '附件分析'),
    ('chat.export_pptx', '簡報匯出 PPTX'),
    ('usage.claude', 'Claude 用量顯示'),
    ('usage.codex', 'Codex 用量顯示'),
)
FEATURE_IDS = tuple(fid for fid, _label in MAIN_FEATURES + SUB_FEATURES)

# Both entry points that put a question to the company LLM.  Asking the model is
# what the product is for; an install without it is not a usable ClaudeCat.
# Enforced here rather than only hidden in the editor, so a hand-edited policy
# file cannot switch them off either.
MANDATORY_FEATURES = frozenset({'chat', 'quick_question'})

DISABLED_MESSAGE = '此功能已由公司政策停用。'


class PolicyError(RuntimeError):
    pass

_lock = threading.Lock()
_policy: dict[str, bool] = {}
_loaded = False


def _baked_features() -> dict | None:
    """The policy compiled into the PYZ archive by ClaudeCat.spec.

    Deliberately *not* a data file: in onedir builds ``_internal/`` is a normal
    folder, so a bundled .json could still be edited in Notepad.  Development
    runs have no baked module and stay unrestricted.
    """
    if not getattr(sys, 'frozen', False):
        return None
    try:
        from config import _baked_policy
    except ImportError as exc:
        raise PolicyError('找不到內嵌的公司功能政策。') from exc
    features = getattr(_baked_policy, 'FEATURES', None)
    if not isinstance(features, dict):
        raise PolicyError('內嵌的公司功能政策格式無效。')
    return features


def _validate_features(features: object) -> dict[str, bool]:
    if not isinstance(features, dict):
        raise PolicyError('公司功能政策必須包含 features 物件。')
    unknown = set(features) - set(FEATURE_IDS)
    missing = set(FEATURE_IDS) - set(features)
    non_boolean = sorted(key for key, value in features.items()
                         if not isinstance(value, bool))
    disabled_mandatory = sorted(
        key for key in MANDATORY_FEATURES if features.get(key) is False)
    if unknown or missing or non_boolean or disabled_mandatory:
        raise PolicyError(
            '公司功能政策無效：'
            f'未知={sorted(unknown)}、缺少={sorted(missing)}、'
            f'非布林={non_boolean}、必要功能關閉={disabled_mandatory}')
    return {key: features[key] for key in FEATURE_IDS}


def load(path: Path | None = None) -> dict[str, bool]:
    """Load a strict policy; packaged builds must never fail open."""
    global _loaded
    with _lock:
        _policy.clear()
        _loaded = True
        if path is not None:                      # explicit file: tests and tooling
            try:
                data = json.loads(path.read_text(encoding='utf-8-sig'))
            except (OSError, ValueError) as exc:
                raise PolicyError(f'無法讀取公司功能政策：{exc}') from exc
            features = data.get('features') if isinstance(data, dict) else None
        else:
            features = _baked_features()
        if features is None:  # Development runs are intentionally unrestricted.
            return dict(_policy)
        _policy.update(_validate_features(features))
        disabled = sorted(k for k, v in _policy.items() if not v)
        logger.info('feature policy loaded; disabled=%s', ', '.join(disabled) or '(none)')
        return dict(_policy)


def is_enabled(feature_id: str) -> bool:
    """True unless the policy explicitly disables this feature or its parent."""
    if not _loaded:
        load()
    feature_id = str(feature_id or '').strip()
    if not feature_id:
        return True
    if feature_id in MANDATORY_FEATURES:
        return True
    with _lock:
        parent = feature_id.split('.', 1)[0]
        if parent != feature_id and _policy.get(parent, True) is False:
            return False
        return _policy.get(feature_id, True)


def snapshot() -> dict[str, bool]:
    """Every known feature with its effective state, for the UI to hide entries."""
    if not _loaded:
        load()
    return {fid: is_enabled(fid) for fid in FEATURE_IDS}
