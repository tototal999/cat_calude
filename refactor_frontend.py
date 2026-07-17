import os
import re

html_path = 'chat/chat.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Extract CSS
css_match = re.search(r'<style>([\s\S]*?)</style>', content)
if css_match:
    css_content = css_match.group(1)
    content = content.replace(f'<style>{css_content}</style>', '<link rel="stylesheet" href="style.css">')
else:
    css_content = ''

# Extract JS
js_match = re.search(r'<script>([\s\S]*?)</script>', content)
if js_match:
    js_content = js_match.group(1)
    content = content.replace(f'<script>{js_content}</script>', '<script src="chat.js"></script>')
else:
    js_content = ''

# Make frontend directory
os.makedirs('frontend', exist_ok=True)

# Write files
with open('frontend/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

with open('frontend/style.css', 'w', encoding='utf-8') as f:
    f.write(css_content.strip())

with open('frontend/chat.js', 'w', encoding='utf-8') as f:
    f.write(js_content.strip())

print("Frontend files split successfully!")
