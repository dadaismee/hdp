const { ipcRenderer, shell } = require('electron');

// --- TABS ---
const tabs = document.querySelectorAll('.nav-btn');
const contents = document.querySelectorAll('.tab-content');

tabs.forEach(tab => {
    tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        contents.forEach(c => c.classList.remove('active'));

        tab.classList.add('active');
        document.getElementById(tab.dataset.tab).classList.add('active');
    });
});

// --- DASHBOARD ---
const dropZone = document.getElementById('drop-zone');
const statusArea = document.getElementById('status-area');
const logOutput = document.getElementById('log-output');
const spinner = document.getElementById('spinner');

// Drag & Drop
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');

    const files = Array.from(e.dataTransfer.files).map(f => f.path);
    const docxFiles = files.filter(f => f.endsWith('.docx'));

    if (docxFiles.length === 0) {
        alert("Пожалуйста, используйте только файлы .docx");
        return;
    }

    startProcessing(files);
});

// Click to browse
dropZone.addEventListener('click', async () => {
    const files = await ipcRenderer.invoke('select-files');
    if (files && files.length > 0) {
        startProcessing(files);
    }
});

function startProcessing(files) {
    statusArea.classList.remove('hidden');
    spinner.classList.remove('hidden');
    logOutput.textContent = "Запуск обработки...\n";

    ipcRenderer.send('run-process', files);
}

ipcRenderer.on('process-log', (event, msg) => {
    logOutput.textContent += msg + "\n";
    logOutput.scrollTop = logOutput.scrollHeight;
});

ipcRenderer.on('process-done', (event, success) => {
    spinner.classList.add('hidden');
    if (success) {
        logOutput.textContent += "\nГОТОВО! Теперь вы можете открыть визуализацию.";
    } else {
        logOutput.textContent += "\nОШИБКА. Проверьте логи.";
    }
});

document.getElementById('open-viz-btn').addEventListener('click', () => {
    ipcRenderer.send('open-viz');
});

// --- SETTINGS ---
const outputPathInput = document.getElementById('output-path');
const cloudSettings = document.getElementById('cloud-settings');
const localSettings = document.getElementById('local-settings');
const toggleBtns = document.querySelectorAll('.toggle-btn');
let currentMode = 'cloud';

// Load Config
async function loadConfig() {
    const config = await ipcRenderer.invoke('get-config');

    // Output Path (Assuming config has this, or we default)
    // Actually config.yml usually has LLM settings. 
    // We might need to store output path there or separate.
    // For now let's assume config.yml structure.

    if (config.llm_settings) {
        if (config.llm_settings.provider === 'ollama') {
            setMode('local');
            document.getElementById('local-model-select').value = config.llm_settings.model;
        } else {
            setMode('cloud');
            document.getElementById('cloud-provider').value = config.llm_settings.provider || 'openai';
            document.getElementById('api-key').value = config.llm_settings.api_key || '';
            document.getElementById('cloud-model').value = config.llm_settings.model || '';
        }
    }
}

// Toggle Mode
toggleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        setMode(btn.dataset.mode);
    });
});

function setMode(mode) {
    currentMode = mode;
    toggleBtns.forEach(b => b.classList.toggle('active', b.dataset.mode === mode));

    if (mode === 'cloud') {
        cloudSettings.classList.remove('hidden');
        localSettings.classList.add('hidden');
    } else {
        cloudSettings.classList.add('hidden');
        localSettings.classList.remove('hidden');
        checkOllama();
    }
    // Trigger save when mode changes (but wait for UI to update if needed)
    // We can just call saveSettings() here, but we need to ensure it's defined or hoisted.
    // Since saveSettings is defined below in original code, we might need to move it up or use function declaration.
    // However, in this replace block, I can't easily move code. 
    // Let's assume saveSettings is available or I will move it in next step if needed.
    // Actually, `const saveSettings` is not hoisted. I should have used `function saveSettings`.
    // I will fix this by changing the previous tool call to use `function saveSettings` or just calling it if it's defined.
    // Wait, I defined it as `const saveSettings` in the previous step.
    // I will just dispatch an event or call it if I can.
    // Better: I will update this function to just call saveSettings() assuming it will be available at runtime (JS hoisting doesn't work for const, but if setMode is called AFTER definition it works).
    // setMode is called on click, which is after definition.
    if (typeof saveSettings === 'function') saveSettings();
}

// Auto-fill defaults
document.getElementById('cloud-provider').addEventListener('change', (e) => {
    const provider = e.target.value;
    const modelInput = document.getElementById('cloud-model');

    if (provider === 'openrouter' && !modelInput.value) {
        modelInput.value = 'x-ai/grok-4.1-fast:free';
        saveSettings();
    } else if (provider === 'openai' && !modelInput.value) {
        modelInput.value = 'gpt-4o';
    } else if (provider === 'anthropic' && !modelInput.value) {
        modelInput.value = 'claude-3-5-sonnet-20240620';
    }
});

// Check Ollama
async function checkOllama() {
    const res = await ipcRenderer.invoke('check-ollama');
    const warning = document.getElementById('ollama-warning');
    const select = document.getElementById('local-model-select');

    if (!res.installed) {
        warning.classList.remove('hidden');
        select.innerHTML = '<option disabled>Ollama not found</option>';
    } else {
        warning.classList.add('hidden');
        select.innerHTML = res.models.map(m => `<option value="${m}">${m}</option>`).join('');
    }
}

document.getElementById('refresh-ollama').addEventListener('click', checkOllama);

// Auto-Save Logic
const saveSettings = async () => {
    // First get existing config to preserve other fields if any
    const existingConfig = await ipcRenderer.invoke('get-config') || {};

    const newConfig = {
        ...existingConfig,
        output_path: document.getElementById('output-path').value,
        llm_settings: {}
    };

    if (currentMode === 'cloud') {
        newConfig.llm_settings = {
            provider: document.getElementById('cloud-provider').value,
            api_key: document.getElementById('api-key').value,
            model: document.getElementById('cloud-model').value
        };
    } else {
        newConfig.llm_settings = {
            provider: 'ollama',
            model: document.getElementById('local-model-select').value,
            api_base: 'http://localhost:11434'
        };
    }

    const res = await ipcRenderer.invoke('save-config', newConfig);
    if (res.success) {
        // Optional: show subtle indicator instead of toast for every keystroke
        // showToast("Saved"); 
    } else {
        console.error("Error saving settings:", res.error);
    }
};

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

const debouncedSave = debounce(saveSettings, 1000);

// Attach Listeners
document.getElementById('cloud-provider').addEventListener('change', saveSettings);
document.getElementById('api-key').addEventListener('input', debouncedSave);
document.getElementById('cloud-model').addEventListener('input', debouncedSave);
document.getElementById('local-model-select').addEventListener('change', saveSettings);

// Select Folder
document.getElementById('select-folder-btn').addEventListener('click', async () => {
    const path = await ipcRenderer.invoke('select-folder');
    if (path) {
        outputPathInput.value = path;
        saveSettings(); // Save immediately after selection
    }
});

// --- PROMPT ---
const promptEditor = document.getElementById('prompt-editor');

async function loadPrompt() {
    const text = await ipcRenderer.invoke('get-prompt');
    promptEditor.value = text;
}

document.getElementById('save-prompt-btn').addEventListener('click', async () => {
    const res = await ipcRenderer.invoke('save-prompt', promptEditor.value);
    if (res.success) showToast("Prompt Saved");
    else alert("Error saving prompt");
});

// --- UPDATE ---
document.getElementById('update-btn').addEventListener('click', async () => {
    const btn = document.getElementById('update-btn');
    btn.textContent = "Checking...";
    const res = await ipcRenderer.invoke('check-update');
    alert(res.message);
    btn.textContent = "Check Updates";
});

// --- UTILS ---
function showToast(msg) {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

window.openUrl = (url) => shell.openExternal(url);

// Init
loadConfig();
loadPrompt();
