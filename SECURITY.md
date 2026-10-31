# Security Policy

## Supported versions

Only the latest release receives security fixes.

## Reporting a vulnerability

Report vulnerabilities privately through GitHub: open the **Security** tab of this repository and choose **Report a vulnerability**. Do not open a public issue for a security problem.

Include the affected version, steps to reproduce, and the impact you expect. Do not include real API keys, internal URLs or document contents in the report.

## How ClaudeCat handles credentials

- `api.py` is the only module that reads Claude credentials. It reads the local Claude Code OAuth token from `~/.claude/.credentials.json` (or `$CLAUDE_CONFIG_DIR/.credentials.json`) and sends it only in the `Authorization` header to `api.anthropic.com`.
- `backend/services/codex_limits.py` never reads, logs or sends a Codex OAuth token. It talks to the local Codex app-server, which keeps its own session.
- The LLM endpoint, model and API key live in the runtime `%LOCALAPPDATA%\ClaudeCat\config.json`. They are never stored in this repository, and the UI has no field to type an API key.
- Company deployment files (`company-defaults.json`, `config/_baked_policy.py`, `config/_baked_deployment.py`) are ignored by Git.
