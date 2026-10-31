# Contributing

Issues and pull requests are welcome. Issues may be written in English or Chinese.

## Set up

1. Use Windows 10/11 and Python 3.11.
2. Install the dependencies: `pip install -r requirements.txt`
3. Start the app: `python cat.py`

## Before you open a pull request

Run the same checks as CI:

```
python -m unittest test_logic
node --check frontend/chat.js
node tools/test_frontend_policy.js
```

- Add or update a test in `test_logic.py` for every behavior change. For a bug fix, first add a test that fails without the fix.
- Keep each pull request to one change. Do not mix refactoring with a fix or a feature.
- If you add a dependency, pin its version in `requirements.txt`.
- Commit messages use a type prefix: `feat:`, `fix:`, `docs:`, `ci:` or `chore:`.

## Do not commit

- API keys, tokens, internal URLs, host names or document contents. Put endpoints and keys in the runtime `config.json`, not in code, tests or docs.
- Company deployment files: `company-defaults.json`, `config/_baked_policy.py`, `config/_baked_deployment.py`.
- Images or other assets without a known source. Add new assets to the source table in `README.md`.

Report security problems as described in `SECURITY.md`.
