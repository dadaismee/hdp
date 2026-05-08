"""Inject API key from .env into config.yml before building."""
import os
import yaml

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.yml')

if not os.path.exists(env_path):
    print(".env not found — skipping injection")
    exit(0)

# Parse .env manually (no python-dotenv dependency)
api_key = None
with open(env_path, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line.startswith('#') or '=' not in line:
            continue
        k, _, v = line.partition('=')
        if k.strip() == 'OPENROUTER_API_KEY':
            api_key = v.strip()
            break

if not api_key:
    print("OPENROUTER_API_KEY not found in .env — skipping injection")
    exit(0)

with open(config_path, 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

cfg.setdefault('llm_settings', {})['api_key'] = api_key

with open(config_path, 'w', encoding='utf-8') as f:
    yaml.dump(cfg, f, allow_unicode=True)

print(f"API key injected into {config_path}")
