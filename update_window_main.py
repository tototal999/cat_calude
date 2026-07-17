import re

with open('backend/window_main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace class JsApi ... to def _build_system_prompt
match = re.search(r'class JsApi:([\s\S]*?)def _build_system_prompt', content)
if match:
    content = content.replace(match.group(0), 'from backend.routes.api import JsApi\n\ndef _build_system_prompt')
    with open('backend/window_main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("JsApi removed from window_main.py")
else:
    print("JsApi not found")
