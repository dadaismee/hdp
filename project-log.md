# Project Log — hdp (historical-document-processor)

## 2026-05-08 — Windows compat, CI/CD, API key injection

### Done

- **Windows SSL EOF fix** (`_ssl.c:1007`): added `certifi` + `SSL_CERT_FILE` env var in `extract_data.py`
- **Cross-platform `webbrowser.open()`** replaced macOS-only `subprocess.call(["open", …])` in `process_pipeline.py`
- **Cross-platform python command**: `process.platform === 'win32' ? 'python' : 'python3'` in `main.js`
- **Removed dead code**: duplicate `save_json`, `save_processed_md` in `extract_data.py`
- **Fixed `load_config()` deep merge**: nested `llm_settings` now preserves defaults
- **Added `certifi`** to `requirements.txt` and `pyinstaller.spec` (hidden imports + collect_all)
- **API key delivery**: two paths — `.env` for local builds (loaded in `main.js:loadDotEnv()`), GitHub Secret `API_KEY` for CI/CD
- **Persistent settings**: `output_path`, temperature, timeout restore on startup; toast feedback on save
- **Temperature/Timeout UI**: added fields in Cloud and Local settings tabs
- **`.env.example`** + **`scripts/inject_env.py`** for local production builds
- **`workflow_dispatch` inputs**: OS selection, API key override, custom branch
- **Updated deprecated Actions**: `checkout@v3→v4`, `setup-python@v4→v5`, `setup-node@v3→v4`
- **Windows Unicode fix**: `encoding='utf-8', errors='replace'` in `subprocess.run` + `sys.stdout.reconfigure(encoding='utf-8')` + `PYTHONIOENCODING=utf-8` + `PYTHONUTF8=1`
- **CI test step** (`scripts/test_pipeline.py`): creates test .docx, runs pipeline, validates md/json/html outputs
- **CI inject step fix**: `shell: bash` for cross-platform heredoc (step-level `env` not accessible in `if:` condition)
- **Refactored API key to single source**: removed `api_key` from `config.yml` — key lives only in `.env` (local) or env var `OPENROUTER_API_KEY` (CI/GitHub Secret). `extract_data.py` reads env var, falls back to `.env` via `python-dotenv`. CI creates `.env` from secret + PyInstaller bundles it. `main.js` passes key via spawn env.

### Current State

- **macOS build**: ✅ ALL CHECKS PASSED
- **Windows build**: ✅ ALL CHECKS PASSED (after Unicode fixes)
- **API key in CI**: ⏳ Нужно установить `API_KEY` GitHub Secret. После этого CI создаст `.env` из секрета → PyInstaller встроит в собранное приложение → LLM extraction будет работать.

### Known Issues

- **OpenRouter key was invalid** — replaced with new key (`sk-or-v1-2e42...075` ✅ работает). Key lives in `.env` (gitignored) locally, and in GitHub Secret for CI.
- **Model changed**: `google/gemini-2.0-pro-exp-02-05:free` removed from OpenRouter → replaced with `openrouter/free` (OpenRouter auto-selects free model).
- PyInstaller warning on Windows: `Failed to collect submodules for 'litellm.proxy.ui_crud_endpoints'` — non-blocking
- Node.js 20 deprecation warnings in Actions (migration to Node 24 by June 2026)

### TODO

- [ ] **HIGH** Установить `API_KEY` GitHub Secret с новым валидным ключом (`sk-or-v1-2e42...075`)
- [ ] **HIGH** Протестировать на CI после установки секрета — должен получить не `SKIP`, а `PASS` для LLM extraction
- [ ] MEDIUM Протестировать локально: `python3 scripts/process_pipeline.py --input-files <file>`
- [ ] LOW Скачать собранные артефакты и проверить локально
