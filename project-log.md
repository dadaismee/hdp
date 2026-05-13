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

### Current State

- **macOS build**: ✅ ALL CHECKS PASSED
- **Windows build**: ✅ ALL CHECKS PASSED (after Unicode fixes)
- **API key injection in CI**: ❌ `API_KEY` GitHub Secret not set in repo (`gh secret list` returns empty)
- **LLM extraction in CI**: SKIPPED — `API key не найден для провайдера openrouter`

### Known Issues

- **OpenRouter 401 `User not found`** — API key was invalid/expired. Replaced with new key (`sk-or-v1-2e42...075`). Key is set locally in `.env` (gitignored), not committed to repo.
- **Model `google/gemini-2.0-pro-exp-02-05:free`** — removed from OpenRouter. Replaced with `openrouter/free`.
- PyInstaller warning on Windows: `Failed to collect submodules for 'litellm.proxy.ui_crud_endpoints'` — non-blocking
- Node.js 20 deprecation warnings in Actions (migration to Node 24 by June 2026)

### TODO

- [ ] **HIGH** Протестировать с другим API-ключом openrouter/cerebras — текущий ключ выдаёт 401 `User not found`
- [ ] MEDIUM Set `API_KEY` GitHub Secret (`Settings → Secrets → Actions`) чтобы LLM extraction работал в CI
- [ ] LOW Скачать собранные артефакты и проверить локально
