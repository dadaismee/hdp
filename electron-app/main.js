const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const yaml = require('js-yaml');
const { spawn, exec } = require('child_process');

let mainWindow;

// Paths
const ROOT_DIR = path.resolve(__dirname, '..');
const CONFIG_PATH = path.join(ROOT_DIR, 'config.yml');
const SYSTEM_PROMPT_PATH = path.join(ROOT_DIR, 'system_prompt.txt');
const PROCESS_SCRIPT = path.join(ROOT_DIR, 'scripts', 'process_pipeline.py');
const VIZ_HTML = path.join(ROOT_DIR, 'md', 'tufte_timeline.html');

function createWindow() {
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

// 2. Get/Save Config
ipcMain.handle('get-config', async () => {
    try {
        if (fs.existsSync(CONFIG_PATH)) {
            const fileContents = fs.readFileSync(CONFIG_PATH, 'utf8');
            return yaml.load(fileContents);
        }
        return {};
    } catch (e) {
        console.error("Error reading config:", e);
        return {};
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
        return "";
    } catch (e) {
        return "";
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
    const inputDir = path.join(ROOT_DIR, 'input_docs');
    if (!fs.existsSync(inputDir)) fs.mkdirSync(inputDir, { recursive: true });

    let copiedCount = 0;
    filePaths.forEach(filePath => {
        if (filePath.endsWith('.docx')) {
            const dest = path.join(inputDir, path.basename(filePath));
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
        const pythonProcess = spawn(cmd, cmdArgs, { cwd: app.isPackaged ? path.dirname(cmd) : ROOT_DIR });

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
