const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const yaml = require('js-yaml');
const { spawn, exec } = require('child_process');

let mainWindow;

// Paths
const ROOT_DIR = path.resolve(__dirname, '..');

// --- USER DATA PATHS (For Persistence & Permissions) ---
// app.getPath('userData') returns:
// macOS: ~/Library/Application Support/Konspekt HDP
// Windows: %APPDATA%/Konspekt HDP
const USER_DATA_PATH = app.getPath('userData');
const CONFIG_PATH = path.join(USER_DATA_PATH, 'config.yml');
const SYSTEM_PROMPT_PATH = path.join(USER_DATA_PATH, 'system_prompt.txt');
const INPUT_DOCS_DIR = path.join(USER_DATA_PATH, 'input_docs');

// Bundled Paths (Read-only source for defaults)
const BUNDLED_CONFIG = path.join(ROOT_DIR, 'config.yml');
const BUNDLED_PROMPT = path.join(ROOT_DIR, 'system_prompt.txt');
const PROCESS_SCRIPT = path.join(ROOT_DIR, 'scripts', 'process_pipeline.py');
const VIZ_HTML = path.join(ROOT_DIR, 'md', 'tufte_timeline.html');

// Helper: Ensure config exists in UserData
function initUserData() {
    if (!fs.existsSync(USER_DATA_PATH)) {
        fs.mkdirSync(USER_DATA_PATH, { recursive: true });
    }

    if (!fs.existsSync(CONFIG_PATH) && fs.existsSync(BUNDLED_CONFIG)) {
        fs.copyFileSync(BUNDLED_CONFIG, CONFIG_PATH);
    }

    if (!fs.existsSync(SYSTEM_PROMPT_PATH) && fs.existsSync(BUNDLED_PROMPT)) {
        fs.copyFileSync(BUNDLED_PROMPT, SYSTEM_PROMPT_PATH);
    }
}

function createWindow() {
    initUserData(); // Ensure files exist

    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false // For simplicity in this local tool
        },
        titleBarStyle: 'hiddenInset',
        backgroundColor: '#f5f5f7'
    });

    mainWindow.loadFile('index.html');
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

// --- IPC HANDLERS ---

// 1. Select Folder
ipcMain.handle('select-folder', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openDirectory']
    });
    if (result.canceled) return null;
    return result.filePaths[0];
});

// --- DEFAULTS ---
const DEFAULT_SYS_PROMPT = `Ты — историк-архивист. Твоя задача — провести комплексный критический анализ исторического источника и извлечь из него структурированные данные.

1. ВЕРНИ ОТВЕТ В ФОРМАТЕ JSON.
2. JSON должен содержать два основных блока: "metadata" (структурированные данные для графа) и "analysis" (текст критического анализа).
3. В поле "topics" выбери наиболее подходящие темы из предложенного списка. Если ни одна не подходит, оставь список пустым.

СПИСОК ТЕМ:
{topics_list}

СТРУКТУРА JSON:
{{
  "metadata": {{
    "date": "YYYY-MM-DD",
    "type": "Тип документа (Письмо, Протокол, Отчет)",
    "title": "Заголовок документа",
    "summary": "Краткое содержание (1-2 предложения)",
    "author": "Имя Фамилия",
    "location": "Город",
    "topics": ["Тема 1", "Тема 2"],
    "entities": [
      {{"name": "Имя Фамилия", "type": "Person", "group": "Clergy/Diplomats/Laypeople/Organizations"}},
      {{"name": "Название Организации", "type": "Organization", "group": "Organizations"}}
    ],
    "relationships": [
      {{"source": "Субъект", "target": "Объект", "type": "тип_связи (wrote_to, conflict_with, met_with, appointed, subordinate_to, mentions, elected_to, member_of)", "desc": "описание"}}
    ],
    "events": [
      {{"date": "YYYY-MM-DD", "desc": "Описание события", "actor": "Главное действующее лицо", "target": "Второе лицо", "type": "Тип события"}}
    ]
  }},
  "analysis": "Текст критического анализа в формате Markdown."
}}
`;

const DEFAULT_CONFIG = {
    llm_settings: {
        provider: "openrouter",
        api_key: "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",
        model: "google/gemini-2.0-flash-exp:free"
    }
};

// 2. Get/Save Config
ipcMain.handle('get-config', async () => {
    try {
        let finalConfig = { ...DEFAULT_CONFIG }; // Start with defaults

        if (fs.existsSync(CONFIG_PATH)) {
            const fileContents = fs.readFileSync(CONFIG_PATH, 'utf8');
            const userConfig = yaml.load(fileContents);
            // Deep merge or just shallow merge top keys for now
            if (userConfig) {
                if (userConfig.llm_settings) {
                    finalConfig.llm_settings = { ...finalConfig.llm_settings, ...userConfig.llm_settings };
                }
                if (userConfig.output_path) {
                    finalConfig.output_path = userConfig.output_path;
                }
            }
        }
        return finalConfig;
    } catch (e) {
        console.error("Error reading config:", e);
        return DEFAULT_CONFIG;
    }
});

ipcMain.handle('save-config', async (event, newConfig) => {
    try {
        const yamlStr = yaml.dump(newConfig);
        fs.writeFileSync(CONFIG_PATH, yamlStr, 'utf8');
        return { success: true };
    } catch (e) {
        return { success: false, error: e.message };
    }
});

// 3. Get/Save Prompt
ipcMain.handle('get-prompt', async () => {
    try {
        if (fs.existsSync(SYSTEM_PROMPT_PATH)) {
            return fs.readFileSync(SYSTEM_PROMPT_PATH, 'utf8');
        }
        return DEFAULT_SYS_PROMPT;
    } catch (e) {
        return DEFAULT_SYS_PROMPT;
    }
});

ipcMain.handle('save-prompt', async (event, content) => {
    try {
        fs.writeFileSync(SYSTEM_PROMPT_PATH, content, 'utf8');
        return { success: true };
    } catch (e) {
        return { success: false, error: e.message };
    }
});

// 4. Run Process Pipeline
ipcMain.on('run-process', (event, filePaths) => {
    // 1. Copy files to input_docs
    if (!fs.existsSync(INPUT_DOCS_DIR)) fs.mkdirSync(INPUT_DOCS_DIR, { recursive: true });

    let copiedCount = 0;
    filePaths.forEach(filePath => {
        if (filePath.endsWith('.docx')) {
            const dest = path.join(INPUT_DOCS_DIR, path.basename(filePath));
            fs.copyFileSync(filePath, dest);
            copiedCount++;
        }
    });

    if (copiedCount === 0) {
        event.reply('process-log', "No .docx files found to process.");
        event.reply('process-done', false);
        return;
    }

    event.reply('process-log', `Copied ${copiedCount} files. Starting pipeline...`);

    // Prepare Args
    let outputPath = null;
    try {
        if (fs.existsSync(CONFIG_PATH)) {
            const conf = yaml.load(fs.readFileSync(CONFIG_PATH, 'utf8'));
            if (conf.output_path) outputPath = conf.output_path;
        }
    } catch (e) { console.error("Config read error", e); }

    const args = [PROCESS_SCRIPT];

    // Pass Config and Prompt Paths
    args.push('--config-path', CONFIG_PATH);
    args.push('--system-prompt-path', SYSTEM_PROMPT_PATH);

    if (outputPath) {
        args.push('--output-dir', outputPath);
        event.reply('process-log', `Using Output Directory: ${outputPath}`);
    }

    if (filePaths && filePaths.length > 0) {
        args.push('--input-files', ...filePaths);
    }

    // 2. Spawn Python Script
    const spawnPython = (retries = 3) => {
        let cmd, cmdArgs;

        if (app.isPackaged) {
            // In production, use the bundled executable
            // It should be in resources/python/process_pipeline (or .exe)
            const ext = process.platform === 'win32' ? '.exe' : '';
            cmd = path.join(process.resourcesPath, 'python', 'process_pipeline' + ext);
            // Remove the first argument (script path) because the executable IS the script
            cmdArgs = args.slice(1);
        } else {
            // In dev, use python3
            cmd = 'python3';
            cmdArgs = args; // args includes the script path as first arg
        }

        console.log(`Spawning: ${cmd} with args: ${cmdArgs}`);
        const pythonProcess = spawn(cmd, cmdArgs, {
            cwd: app.isPackaged ? path.dirname(cmd) : ROOT_DIR,
            env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
        });

        pythonProcess.stdout.on('data', (data) => {
            event.reply('process-log', data.toString());
        });

        pythonProcess.stderr.on('data', (data) => {
            event.reply('process-log', `ERROR: ${data.toString()}`);
        });

        pythonProcess.on('error', (err) => {
            console.error("Spawn error:", err);
            if (err.code === 'EAGAIN' && retries > 0) {
                event.reply('process-log', `System busy (EAGAIN), retrying in 1s... (${retries} left)`);
                setTimeout(() => spawnPython(retries - 1), 1000);
            } else {
                event.reply('process-log', `CRITICAL ERROR: Failed to start Python process. ${err.message}`);
                event.reply('process-done', false);
            }
        });

        pythonProcess.on('close', (code) => {
            if (code === 0) {
                event.reply('process-log', "Processing Complete!");
                event.reply('process-done', true);
            } else {
                // If code is null, it might be due to error handled above, but close still fires?
                if (code !== null) {
                    event.reply('process-log', `Process exited with code ${code}`);
                    event.reply('process-done', false);
                }
            }
        });
    };

    spawnPython();
});

// 5. Open Visualization
// 5. Open Visualization
ipcMain.on('open-viz', () => {
    let vizPath = VIZ_HTML; // Default

    try {
        if (fs.existsSync(CONFIG_PATH)) {
            const conf = yaml.load(fs.readFileSync(CONFIG_PATH, 'utf8'));
            if (conf.output_path) {
                vizPath = path.join(conf.output_path, 'tufte_timeline.html');
            }
        }
    } catch (e) {
        console.error("Config read error in open-viz", e);
    }

    if (fs.existsSync(vizPath)) {
        shell.openPath(vizPath);
    } else {
        dialog.showErrorBox(
            "Файл не найден",
            `Не удалось найти файл визуализации по пути:\n${vizPath}\n\nВозможно, обработка еще не завершена или файл был удален.`
        );
    }
});

// 6. Check Updates (Git Pull)
ipcMain.handle('check-update', async () => {
    return new Promise((resolve) => {
        exec('git pull origin main', { cwd: ROOT_DIR }, (error, stdout, stderr) => {
            if (error) {
                resolve({ success: false, message: error.message });
                return;
            }
            resolve({ success: true, message: stdout || stderr });
        });
    });
});

// 7. Check Ollama
ipcMain.handle('check-ollama', async () => {
    return new Promise((resolve) => {
        exec('ollama list', (error, stdout, stderr) => {
            if (error) {
                resolve({ installed: false });
            } else {
                // Parse models
                const lines = stdout.split('\n').slice(1); // Skip header
                const models = lines.map(l => l.split(/\s+/)[0]).filter(Boolean);
                resolve({ installed: true, models });
            }
        });
    });
});
