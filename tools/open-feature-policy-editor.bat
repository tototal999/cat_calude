@echo off
cd /d "%~dp0.."
set "CLAUDECAT_PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if exist "%CLAUDECAT_PYTHON%" (
  "%CLAUDECAT_PYTHON%" tools\feature_policy_editor.py
) else (
  python tools\feature_policy_editor.py
)
if errorlevel 1 pause
