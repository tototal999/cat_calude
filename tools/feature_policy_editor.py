"""Local admin launcher for editing the build-time feature policy."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = PROJECT_ROOT / 'feature-policy.json'
HTML_PATH = PROJECT_ROOT / 'tools' / 'feature-policy-editor.html'

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import policy  # noqa: E402


class PolicyEditorApi:
    def __init__(self, policy_path: Path = POLICY_PATH):
        self.policy_path = Path(policy_path)

    def load_policy(self) -> dict:
        try:
            document = json.loads(self.policy_path.read_text(encoding='utf-8-sig'))
            features = document.get('features') if isinstance(document, dict) else None
            policy._validate_features(features)
            return {'ok': True, 'document': document, 'path': str(self.policy_path)}
        except (OSError, ValueError, policy.PolicyError) as exc:
            return {'ok': False, 'error': str(exc), 'path': str(self.policy_path)}

    def save_policy(self, document: object) -> dict:
        try:
            if not isinstance(document, dict):
                raise policy.PolicyError('政策最外層必須是物件。')
            policy._validate_features(document.get('features'))
            content = json.dumps(document, ensure_ascii=False, indent=1) + '\n'
            temp_path = self.policy_path.with_suffix('.json.tmp')
            temp_path.write_text(content, encoding='utf-8')
            temp_path.replace(self.policy_path)
            return {'ok': True, 'path': str(self.policy_path)}
        except (OSError, ValueError, policy.PolicyError) as exc:
            return {'ok': False, 'error': str(exc), 'path': str(self.policy_path)}


def main() -> None:
    import webview

    webview.create_window(
        'ClaudeCat 功能政策管理',
        str(HTML_PATH),
        js_api=PolicyEditorApi(),
        width=1040,
        height=820,
        min_size=(760, 600),
    )
    webview.start(debug=False)


if __name__ == '__main__':
    main()
