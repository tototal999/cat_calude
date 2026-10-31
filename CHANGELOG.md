# Changelog

Versions match `__version__` in `cat.py`. Only `v2` and `v7.3.1` are published as Git tags.

## v7.3.1 - 2026-10-31

First public release since v2.

### Added
- MIT `LICENSE` and `THIRD_PARTY_NOTICES.md` for `api.py` (derived from usage-monitor-for-claude).
- Pinned `requirements.txt` and a GitHub Actions workflow that runs the Python and frontend tests on Windows with Python 3.11.
- English summary and an asset source table in `README.md`.

### Fixed
- Clearing the log now also deletes rotated backups when the log path contains Windows 8.3 short names.
- `latest_run` returns the newer workflow run when two run files share the same modification time.

### Removed
- Personal work logs from the repository.
- Unused RunCat365 frames (`frames/cat_0.png` to `cat_4.png`).

### Changed (2026-07-28)
- Document de-duplication with timestamp IDs, full PDF analysis, and removal of the flow / SOP action.

## 7.2.2 - 2026-07-28
- Document analysis results are saved to disk. Drag and drop is disabled. MarkItDown is removed.

## 7.1.1 - 2026-07-28
- Schedules stop when the feature policy disables them, so a leftover `schedule.json` no longer fires.

## 7.1.0 - 2026-07-28
- Single version source and a smoke test that starts Tk for real.

## Unversioned changes, 2026-07-18 to 2026-07-27
- Local document assistant; documents and index stay on the computer.
- Optional Codex usage limits monitoring, off until the user consents.
- Stateful pet interactions and a tray icon.
- Desktop AI toolbox with a unified tool menu, model controls and task routing.
- Document meeting pack workflow with bounded retries, retention and recovery of interrupted runs.
- Managed feature policy and release workflow for company deployments.
- Multiple LLM endpoints that switch with the selected model.
- Pet animation no longer depends on Codex usage. New `wuma` skin.
- Full PPTX slide analysis and a copy button in the document assistant.

## v2 - 2026-07-17
- Desktop pet that runs faster as the Claude 5-hour usage grows; bluecat sprites and a skin system.
- Sleep and idle poses, weekly quota display, persistent settings and logging.
- Schedule reminders and an LLM chat window with the endpoint in the runtime `config.json`.
- File attachments, Excel conversion and PPTX export in chat.
- Chat UI refactored to an MVC structure with an Open WebUI style layout.
- Windows EXE build that bundles the Tk runtime.
