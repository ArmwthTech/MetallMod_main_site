import os
import re
import json
from pathlib import Path

# --- Конфиг ---
PROJECT_ROOT = Path(__file__).parent
TRANSLATIONS_DIR = PROJECT_ROOT / 'translations'
RU_JSON = TRANSLATIONS_DIR / 'ru.json'
EN_JSON = TRANSLATIONS_DIR / 'en.json'
SEARCH_EXTS = ['.py', '.html']

# --- Регулярки для поиска ключей ---
PY_KEY_RE = re.compile(r"_\(['\"](.+?)['\"]")
JINJA_KEY_RE = re.compile(r"\{\{\s*_\(['\"](.+?)['\"]\)\s*\}\}")


def find_translation_keys(root: Path):
    keys = set()
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if any(fname.endswith(ext) for ext in SEARCH_EXTS):
                fpath = Path(dirpath) / fname
                try:
                    with open(fpath, encoding='utf-8') as f:
                        text = f.read()
                        keys.update(PY_KEY_RE.findall(text))
                        keys.update(JINJA_KEY_RE.findall(text))
                except Exception as e:
                    print(f"[WARN] Не удалось прочитать {fpath}: {e}")
    return keys


def load_json(path: Path):
    if not path.exists():
        return {}
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save_json(path: Path, data: dict):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def sync_translations():
    print("[INFO] Поиск ключей переводов...")
    used_keys = find_translation_keys(PROJECT_ROOT)
    print(f"[INFO] Найдено ключей: {len(used_keys)}")

    ru = load_json(RU_JSON)
    en = load_json(EN_JSON)

    # Добавить новые ключи
    added = set()
    for key in used_keys:
        if key not in ru:
            ru[key] = key
            added.add(key)
        if key not in en:
            en[key] = ""
            added.add(key)

    # Удалить неиспользуемые ключи
    removed = set()
    for key in list(ru.keys()):
        if key not in used_keys:
            del ru[key]
            removed.add(key)
    for key in list(en.keys()):
        if key not in used_keys:
            del en[key]
            removed.add(key)

    save_json(RU_JSON, ru)
    save_json(EN_JSON, en)

    print(f"[INFO] Добавлено ключей: {len(added)}")
    print(f"[INFO] Удалено ключей: {len(removed)}")
    print("[OK] Синхронизация завершена.")


if __name__ == "__main__":
    sync_translations()
