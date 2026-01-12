import os
import subprocess
import sys
import glob
import traceback
import time
import argparse
import shutil

# Paths relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_INPUT_DOCS_DIR = os.path.join(PROJECT_ROOT, "input_docs")
DEFAULT_MD_INBOX_DIR = os.path.join(PROJECT_ROOT, "md")
DEFAULT_OUTPUT_HTML = os.path.join(PROJECT_ROOT, "md", "tufte_timeline.html")

EXTRACT_SCRIPT = os.path.join(SCRIPT_DIR, "extract_data.py")
VIZ_SCRIPT = os.path.join(SCRIPT_DIR, "generate_tufte_viz.py")

def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}")
    sys.stdout.flush()

def run_command(command):
    try:
        subprocess.check_call(command)
    except subprocess.CalledProcessError as e:
        log(f"Ошибка при выполнении команды: {e}")
        pass

def main():
    parser = argparse.ArgumentParser(description="Process document pipeline.")
    parser.add_argument("--output-dir", help="Directory to save processed files.")
    parser.add_argument("--input-files", nargs="*", help="List of specific input files to process.")
    parser.add_argument("--config-path", help="Path to config.yml")
    parser.add_argument("--system-prompt-path", help="Path to system_prompt.txt")
    args = parser.parse_args()

    # Force UTF-8 for Windows console
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

    log("--- Запуск конвейера обработки документов ---")
    
    # Determine Working Directories
    if args.output_dir:
        # Custom Mode
        working_dir = args.output_dir
        if not os.path.exists(working_dir):
            os.makedirs(working_dir)
        
        # Copy input files if provided
        if args.input_files:
            log(f"Копирование {len(args.input_files)} файлов в {working_dir}...")
            for f in args.input_files:
                if os.path.exists(f):
                    # Check if source and destination are the same
                    src = os.path.abspath(f)
                    dst = os.path.abspath(os.path.join(working_dir, os.path.basename(f)))
                    
                    if src != dst:
                        shutil.copy2(f, working_dir)
                    else:
                        log(f"Файл уже в целевой папке, копирование не требуется: {f}")
                else:
                    log(f"Внимание: Файл не найден: {f}")
        
        docx_source_dir = working_dir
        md_output_dir = working_dir 
        extract_base_dir = working_dir 
        
    else:
        # Default Mode
        docx_source_dir = DEFAULT_INPUT_DOCS_DIR
        md_output_dir = DEFAULT_MD_INBOX_DIR
        extract_base_dir = None 
        
        if not os.path.exists(docx_source_dir):
            os.makedirs(docx_source_dir)
            log(f"Создана папка для входящих файлов: {docx_source_dir}")
            return

        if not os.path.exists(md_output_dir):
            os.makedirs(md_output_dir)

    # 1. Convert DOCX to MD
    docx_files = glob.glob(os.path.join(docx_source_dir, "*.docx"))
    if not docx_files:
        log(f"Файлы .docx не найдены в {docx_source_dir}")
    else:
        # Estimate time: ~2 sec per conversion
        est_time = len(docx_files) * 2
        log(f"Найдено {len(docx_files)} файлов. Конвертация в Markdown... (Оценка: ~{est_time} сек)")
        
        for i, docx_path in enumerate(docx_files):
            filename = os.path.basename(docx_path)
            name_no_ext = os.path.splitext(filename)[0]
            md_path = os.path.join(md_output_dir, name_no_ext + ".md")
            
            if os.path.exists(md_path):
                src_mtime = os.path.getmtime(docx_path)
                dst_mtime = os.path.getmtime(md_path)
                if src_mtime <= dst_mtime:
                    log(f"[{i+1}/{len(docx_files)}] Пропуск {filename} (уже обработан)")
                    continue
            
            log(f"[{i+1}/{len(docx_files)}] Конвертация {filename}...")
            
            # Check for bundled pandoc
            if getattr(sys, 'frozen', False):
                # Determine executable name based on OS
                pandoc_name = "pandoc.exe" if sys.platform == "win32" else "pandoc"
                
                # Look in _MEIxxxx folder (OneFile)
                if hasattr(sys, '_MEIPASS'):
                     mei_pandoc = os.path.join(sys._MEIPASS, pandoc_name)
                else:
                     mei_pandoc = None

                # Look alongside exe (OneDir or fallback)
                exe_pandoc = os.path.join(os.path.dirname(sys.executable), pandoc_name)
                
                if mei_pandoc and os.path.exists(mei_pandoc):
                    pandoc_path = mei_pandoc
                    log(f"Используется встроенный Pandoc (OneFile): {pandoc_path}")
                elif os.path.exists(exe_pandoc):
                    pandoc_path = exe_pandoc
                    log(f"Используется встроенный Pandoc (OneDir): {pandoc_path}")
                else:
                    pandoc_path = "pandoc" # Fallback to system path
                    log(f"Встроенный Pandoc ({pandoc_name}) не найден в {exe_pandoc}, попытка использовать системный...")
            else:
                pandoc_path = "pandoc"

            cmd = [pandoc_path, docx_path, "-f", "docx", "-t", "markdown", "--wrap=none", "-o", md_path]
            run_command(cmd)

    # 2. Extract Data
    # Estimate time: ~30 sec per file for LLM
    # We count .md files in the target dir
    md_files = glob.glob(os.path.join(md_output_dir, "*.md"))
    # Exclude processed
    files_to_process = []
    processed_dir = os.path.join(md_output_dir, "Обработанные источники" if args.output_dir else "Processed")
    
    for f in md_files:
        if "Processed" in f or "Обработанные" in f: continue
        # Check if already in processed dir
        fname = os.path.basename(f)
        if os.path.exists(os.path.join(processed_dir, fname)):
             # Check timestamps (simplified logic here, extract_data does real check)
             pass
        files_to_process.append(f)

    # 2. Extract Data & AI Analysis
    est_llm_time = len(files_to_process) * 30
    log(f"\n--- Запуск извлечения данных и AI-анализа ---")
    log(f"Это может занять время (Оценка: ~{est_llm_time // 60} мин {est_llm_time % 60} сек)...")
    
    # Prepare args for extract_data
    extract_args = []
    if extract_base_dir:
        extract_args.extend(["--base-dir", extract_base_dir])
    
    if args.config_path:
        extract_args.extend(["--config-path", args.config_path])
    
    if args.system_prompt_path:
         extract_args.extend(["--system-prompt-path", args.system_prompt_path])
        
    try:
        # Import and call directly
        import extract_data
        extract_data.main(extract_args)
    except Exception as e:
        log(f"Ошибка при извлечении данных: {e}")
        traceback.print_exc()
        sys.exit(1)

    # 3. Generate Visualization
    log("\n--- Генерация визуализации ---")
    
    viz_args = []
    if extract_base_dir:
        json_dir = os.path.join(extract_base_dir, "json")
        viz_args.append(json_dir)
        # Explicitly set output file
        viz_output = os.path.join(extract_base_dir, "tufte_timeline.html")
        viz_args.extend(["--output-file", viz_output])
        
    try:
        import generate_tufte_viz
        generate_tufte_viz.main(viz_args)
    except Exception as e:
        log(f"Ошибка при генерации визуализации: {e}")
        traceback.print_exc()
        sys.exit(1)
        
    # 4. Open Result
    target_html = DEFAULT_OUTPUT_HTML
    if extract_base_dir:
        target_html = os.path.join(extract_base_dir, "tufte_timeline.html")
        
    log(f"\n--- Готово! Открываю {os.path.basename(target_html)} ---")
    if os.path.exists(target_html):
        subprocess.call(["open", target_html])
    else:
        log(f"Файл визуализации не найден: {target_html}")

if __name__ == "__main__":
    main()
