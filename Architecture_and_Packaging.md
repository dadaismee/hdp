# Architecture and Packaging Guide

## Project Architecture

This application is a hybrid system combining a modern **Electron** frontend with a powerful **Python** backend.

### Components

1.  **Electron App (`electron-app/`)**:
    -   **Frontend**: HTML/CSS/JS (Renderer process). Handles user interaction (Drag & Drop, Settings).
    -   **Backend**: Node.js (Main process). Handles system operations (File dialogs, Git updates) and spawns the Python pipeline.
    -   **Communication**: Uses IPC (Inter-Process Communication) to send commands from UI to Main, and then to Python.

2.  **Python Pipeline (`scripts/`)**:
    -   **`process_pipeline.py`**: The orchestrator.
        -   Copies input `.docx` files to the target folder.
        -   Runs `pandoc` to convert them to Markdown.
        -   Calls `extract_data.py`.
    -   **`extract_data.py`**: The core logic.
        -   Reads Markdown files.
        -   Sends text to LLM (OpenAI/Claude/Ollama).
        -   Extracts structured JSON.
        -   Saves processed Markdown to `[Folder]/Обработанные источники`.
        -   Saves JSON to `[Folder]/json`.
    -   **`generate_tufte_viz.py`**:
        -   Reads JSON data.
        -   Generates interactive HTML visualization.

### Data Flow
1.  User drops file -> Electron UI.
2.  Electron Main spawns `python3 scripts/process_pipeline.py --output-dir [Path] --input-files [Files]`.
3.  Python script executes conversion and extraction.
4.  Electron captures stdout/stderr and displays logs in UI.

---

## Packaging for Windows (Standalone)

To create a standalone Windows application that works without requiring the user to install Python, Node.js, or Pandoc manually, you need to **bundle** these dependencies.

### Strategy: Portable Distribution

The goal is to create a folder (or installer) containing:
1.  The Electron App executable.
2.  A portable Python environment (with required libraries).
3.  A portable Pandoc executable.
4.  (Optional) Portable Git.

### Step-by-Step Packaging Guide

#### 1. Bundle Python (PyInstaller)
Instead of asking users to install Python, compile your scripts into an executable.
1.  Install PyInstaller: `pip install pyinstaller`
2.  Compile the pipeline:
    ```bash
    pyinstaller --onefile --name process_pipeline scripts/process_pipeline.py
    ```
    *Note: You might need to adjust imports or hidden imports if PyInstaller misses them.*
3.  This creates a `dist/process_pipeline.exe`.
4.  **Update Electron**: Modify `main.js` to spawn `process_pipeline.exe` instead of `python3 scripts/process_pipeline.py` when running on Windows.

#### 2. Bundle Pandoc
1.  Download **Pandoc for Windows (zip)** (not installer).
2.  Extract `pandoc.exe`.
3.  Place it in a `resources/bin` folder in your Electron app.
4.  **Update Python Script**: Modify `process_pipeline.py` to look for `pandoc.exe` in the adjacent `bin` folder if not found in PATH.

#### 3. Build Electron App (electron-builder)
1.  Install builder: `npm install --save-dev electron-builder`
2.  Update `package.json`:
    ```json
    "build": {
      "appId": "com.antigravity.hdp",
      "win": {
        "target": "nsis",
        "extraResources": [
          "./resources/**",
          "./dist/process_pipeline.exe" 
        ]
      }
    }
    ```
3.  Run build: `npm run build`

### Result
You will get an installer (`.exe`). When installed, it will contain your Electron app and the bundled Python/Pandoc executables. The app will run completely offline (if using local LLM) and without external dependencies.
