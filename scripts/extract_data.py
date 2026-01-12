import os
import sys
import json
import time
import requests
import glob
import yaml
import argparse
from pathlib import Path
from litellm import completion

# --- CONFIGURATION ---
# --- CONFIGURATION ---
# Paths
if getattr(sys, 'frozen', False):
    if hasattr(sys, '_MEIPASS'):
        BASE_DIR = sys._MEIPASS
    else:
        BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Note: INPUT_DIR usually needs to be writable, so we should NOT use MEIPASS for that if it's strictly for output. 
# But this script seems to imply INPUT_DIR is where MD files are provided. 
# If args are passed, this globals are overridden in main() anyway.
INPUT_DIR = os.path.join(BASE_DIR, "md")
JSON_OUTPUT_DIR = os.path.join(INPUT_DIR, "json")
PROCESSED_MD_DIR = os.path.join(INPUT_DIR, "Processed")
# Defaults for global access if needed, but better to pass around
DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "config.yml")
DEFAULT_PROMPT_PATH = os.path.join(BASE_DIR, "system_prompt.txt")

def load_config(config_path=None):
    use_path = config_path if config_path else DEFAULT_CONFIG_PATH
    
    # Defaults
    default_config = {
        "llm_settings": {
            "provider": "openrouter",
            "model": "google/gemini-2.0-flash-exp:free", 
            "temperature": 0.1,
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": ""
        }
    }
    
    try:
        if os.path.exists(use_path):
            with open(use_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    default_config.update(user_config)
        else:
            print(f"Config not found at {use_path}, using defaults.")
            
    except Exception as e:
        print(f"Warning: Could not load config.yml: {e}")
    
    return default_config


# Topics List
TOPICS_LIST = [
    "отношения Стельмашенко с Ванеком и Червинкой (Чешская православной община)",
    "отношения русского прихода в Праге с Савватием",
    "полномочия настоятеля (Стельмашенко)",
    "проблема ведения метрических книг",
    "история русского прихода в Праге",
    "история курортных церквей в ЧСР (Карлсбад, Мариенбад, Францесбад)",
    "проблема русского церковного имущества на курортах",
    "богослужения",
    "роль мирян",
    "виза для настоятеля (Ломако)",
    "отношения Стельмашенко с Досифеем",
    "роль Рафальского",
    "отношения Стельмашенко с эмигрантскими организациями в ЧСР",
    "собирание прихода",
    "Приходской устав 1917-1918",
    "финансовое положение прихода",
    "гонения на патриарха Тихона в России",
    "Приходской совет состав"
]

def load_system_prompt(prompt_path=None):
    use_path = prompt_path if prompt_path else DEFAULT_PROMPT_PATH
    
    if os.path.exists(use_path):
        with open(use_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        print(f"Warning: system_prompt.txt not found at {use_path}. Using default.")
        return """Ты — историк-архивист. Твоя задача — провести комплексный критический анализ исторического источника и извлечь из него структурированные данные.

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
"""

# Global variable will be initialized in main or via explicit call if needed, 
# but process_text_with_llm uses it. 
# We'll reload it in main if path is provided.
SYSTEM_PROMPT = load_system_prompt()

def normalize_name(name):
    if not name: return ""
    if "(" in name:
        return name.split("(")[0].strip()
    return name.strip()

def process_text_with_llm(text, config):
    llm_settings = config.get('llm_settings', {})
    provider = llm_settings.get('provider', 'openai')
    model = llm_settings.get('model', 'gpt-4o')
    temperature = llm_settings.get('temperature', 0.1)
    timeout = llm_settings.get('timeout', 600)
    
    # Construct model string for litellm
    if provider == 'ollama':
        model_name = f"ollama/{model}"
        api_base = llm_settings.get('base_url', "http://localhost:11434")
    elif provider == 'openrouter':
        model_name = f"openrouter/{model}"
        api_base = llm_settings.get('base_url', "https://openrouter.ai/api/v1")
    else:
        model_name = model
        api_base = None

    print(f"Calling LLM ({model_name})...")
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(topics_list=json.dumps(TOPICS_LIST, ensure_ascii=False, indent=2))},
        {"role": "user", "content": f"Текст документа:\n\n{text[:15000]}"}
    ]

    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = completion(
                model=model_name,
                messages=messages,
                temperature=temperature,
                api_base=api_base,
                api_key=llm_settings.get('api_key'),
                timeout=timeout,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            # Clean up potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            data = json.loads(content)
            
            # Normalize entities
            if 'metadata' in data:
                meta = data['metadata']
                if 'author' in meta: meta['author'] = normalize_name(meta['author'])
                
                # Normalize entities list
                if 'entities' in meta:
                    for ent in meta['entities']:
                        ent['name'] = normalize_name(ent['name'])
                
                # Normalize relationships
                if 'relationships' in meta:
                    for rel in meta['relationships']:
                        rel['source'] = normalize_name(rel['source'])
                        rel['target'] = normalize_name(rel['target'])
                
                # Normalize events
                if 'events' in meta:
                    for evt in meta['events']:
                        evt['actor'] = normalize_name(evt['actor'])
                        evt['target'] = normalize_name(evt['target'])
                        
            return data
        except Exception as e:
            print(f"Ошибка вызова LLM (Попытка {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                # Exponential backoff: 5, 10, 20, 40 seconds
                wait_time = 5 * (2 ** attempt)
                print(f"Повтор через {wait_time} сек...")
                time.sleep(wait_time)
            else:
                print("Не удалось получить ответ от LLM после всех попыток.")
                return None

def format_obsidian_link(name):
    return f"[[{name}]]"

def save_json(data, filename):
    path = os.path.join(JSON_OUTPUT_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2) # Save full data
    print(f"Saved JSON: {path}")

def save_processed_md(original_content, full_data, filename):
    path = os.path.join(PROCESSED_MD_DIR, filename)
    meta = full_data['metadata']
    analysis_text = full_data.get('analysis', '')
    
    # Generate ID from filename (remove extension)
    doc_id = os.path.splitext(filename)[0]
    if doc_id.endswith('.md') or doc_id.endswith('.docx') or doc_id.endswith('.rtf'): # Handle double extensions if any
         doc_id = os.path.splitext(doc_id)[0]

    # Collect mentions
    all_mentions = set()
    if meta.get('author'): all_mentions.add(meta['author'])
    if meta.get('location'): all_mentions.add(meta['location'])
    for ent in meta.get('entities', []): all_mentions.add(ent['name'])
    for rel in meta.get('relationships', []):
        all_mentions.add(rel['target'])
        all_mentions.add(rel['source'])

    yaml = "---\n"
    yaml += f"id: {doc_id}\n"
    yaml += f"title: \"{meta.get('title', doc_id)}\"\n"
    # Parse date for Dataview compatibility
    raw_date = meta.get('date', '')
    clean_date = ''
    begin_date = ''
    end_date = ''
    
    if raw_date:
        # Try to find the first YYYY-MM-DD pattern
        import re
        date_matches = re.findall(r'\d{4}-\d{2}-\d{2}', raw_date)
        if date_matches:
            clean_date = date_matches[0] # Use first date for sorting
            begin_date = date_matches[0]
            end_date = date_matches[-1] # Use last date for end
        else:
            # Fallback if no strict format found, just use raw string but it might break dataview sorting
            pass

    yaml += f"date: {clean_date}\n" # Standard field for Dataview
    yaml += f"begin: {begin_date}\n"
    yaml += f"end: {end_date}\n"
    # Type in YAML should probably be a string for Cosma, or [[Type]] for Obsidian? 
    # User wants Cosma graph. Cosma usually likes simple strings or lists.
    # But Obsidian needs [[Type]] to link to Type node.
    # Let's use [[Type]] for type as it acts as a tag/category often.
    yaml += f"type: {format_obsidian_link(meta.get('type', 'Doc'))}\n"
    
    yaml += f"location: {format_obsidian_link(meta.get('location', ''))}\n"
    yaml += f"summary: \"{meta.get('summary', '')}\"\n"
    
    # Topics
    if meta.get('topics'):
        yaml += "topics:\n"
        for topic in meta['topics']:
            yaml += f"  - \"{topic}\"\n"

    # Obsidian Typed Relationships (Extended Graph) - Translated to Russian
    # Mapping from English types to Russian
    rel_map = {
        "wrote_to": "написал",
        "conflict_with": "конфликт",
        "met_with": "встреча",
        "appointed": "назначил",
        "subordinate_to": "подчинение",
        "mentions": "упоминает",
        "elected_to": "избран",
        "member_of": "членство"
    }

    rels_by_type = {}
    for rel in meta.get('relationships', []):
        rtype = rel['type']
        target = rel['target']
        
        # Translate type if possible
        if rtype in rel_map:
            rtype = rel_map[rtype]
            
        if rtype == 'type': rtype = 'rel_type' # Avoid conflict with 'type' field
        
def save_json(data, filename, output_dir):
    path = os.path.join(output_dir, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Сохранен JSON: {path}")

def save_processed_md(original_content, data, filename, output_dir):
    # Construct YAML frontmatter
    yaml_front = "---\n"
    if 'metadata' in data:
        for k, v in data['metadata'].items():
            if k == 'entities': continue 
            if k == 'relationships': continue
            if k == 'events': continue
            yaml_front += f"{k}: {json.dumps(v, ensure_ascii=False)}\n"
    yaml_front += "---\n\n"
    
    # Construct Analysis Section
    analysis = data.get('analysis', '')
    
    # Construct Mentions Section
    mentions = "\n## Упоминания\n"
    if 'metadata' in data and 'entities' in data['metadata']:
        for e in data['metadata']['entities']:
            mentions += f"- [[{e['name']}]] ({e.get('group', 'Unknown')})\n"
            
    # Combine
    content = yaml_front + analysis + mentions + "\n\n# Оригинальный текст\n\n" + original_content
    
    path = os.path.join(output_dir, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Сохранен обработанный MD: {path}")

def main(args_list=None):
    parser = argparse.ArgumentParser(description="Extract data from Markdown files using LLM.")
    parser.add_argument("--base-dir", help="Base directory for input/output files. If provided, overrides default paths.")
    parser.add_argument("--config-path", help="Path to config.yml")
    parser.add_argument("--system-prompt-path", help="Path to system_prompt.txt")
    
    if args_list:
        args = parser.parse_args(args_list)
    else:
        args = parser.parse_args()

    # Reload Globals with args if provided
    global SYSTEM_PROMPT
    if args.system_prompt_path:
        SYSTEM_PROMPT = load_system_prompt(args.system_prompt_path)
    
    config_path = args.config_path
    
    if args.base_dir:
        # Custom paths
        input_dir = args.base_dir
        json_output_dir = os.path.join(input_dir, "json")
        processed_md_dir = os.path.join(input_dir, "Обработанные источники")
    else:
        # Default paths
        input_dir = INPUT_DIR
        json_output_dir = JSON_OUTPUT_DIR
        processed_md_dir = PROCESSED_MD_DIR

    # Ensure directories exist
    os.makedirs(json_output_dir, exist_ok=True)
    os.makedirs(processed_md_dir, exist_ok=True)

    # Get files
    files = glob.glob(os.path.join(input_dir, "*.md"))
    # Also support docx if converted in pipeline, but here we look for MDs usually.
    # If pipeline converts docx -> md in same folder, we find them.
    
    print(f"Найдено {len(files)} markdown файлов в {input_dir}")

    config = load_config(config_path)

    for file_path in files:
        filename = os.path.basename(file_path)
        
        # Skip already processed if needed, or just overwrite?
        # Logic: Check if json exists and has metadata
        json_filename = filename.replace('.md', '.json')
        json_path = os.path.join(json_output_dir, json_filename)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if os.path.exists(json_path):
            # Try to load full data from JSON
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                
                # Check if it is full data (has 'metadata' and 'analysis')
                if 'metadata' in existing_data and 'analysis' in existing_data:
                    print(f"Генерация Markdown из существующего JSON для {filename}...")
                    save_processed_md(content, existing_data, filename, processed_md_dir)
                    continue
                else:
                    pass
            except Exception as e:
                print(f"Ошибка чтения JSON {json_path}: {e}")

        print(f"Обработка {filename} с помощью ИИ...")
        full_data = process_text_with_llm(content, config)
            
        if full_data:
            save_json(full_data, json_filename, json_output_dir)
            save_processed_md(content, full_data, filename, processed_md_dir)
        else:
            print(f"Skipping {filename}")

if __name__ == "__main__":
    main()
