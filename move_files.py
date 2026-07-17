import os

os.makedirs('config', exist_ok=True)
os.makedirs('backend/routes', exist_ok=True)
os.makedirs('backend/services', exist_ok=True)
os.makedirs('backend/prompts', exist_ok=True)
os.makedirs('backend/models', exist_ok=True)

if os.path.exists('llm.py'):
    os.rename('llm.py', 'backend/services/llm_service.py')

if os.path.exists('chat/window.py'):
    os.rename('chat/window.py', 'backend/window_main.py')

print("Directories created and files moved.")
