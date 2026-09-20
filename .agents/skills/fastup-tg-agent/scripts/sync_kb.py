#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Синхронизация базы знаний Алеси (tools.fastup.by) с локальными файлами в Git (bots/kb/).

Позволяет хранить базу знаний бота в версионируемом виде в Git, редактировать в Markdown
и обновлять на боевом сервере одной командой.

Использование:
    python scripts/sync_kb.py pull            # выгрузить все статьи с сервера в bots/kb/*.md
    python scripts/sync_kb.py status          # показать различия между локальными файлами и сервером
    python scripts/sync_kb.py push <id>       # отправить одну изменённую статью на сервер
    python scripts/sync_kb.py push --all      # отправить все локальные изменения на сервер
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "bots" / "kb"


def run_tool(action: str, args: dict = None) -> dict:
    cmd = [sys.executable, str(ROOT / "scripts" / "tools.py"), action]
    input_data = None
    if args:
        cmd.extend(["--json", "-"])
        input_data = json.dumps(args, ensure_ascii=False)
    res = subprocess.run(cmd, input=input_data, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        raise RuntimeError(f"tools.py {action} failed: {res.stderr or res.stdout}")
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return {"raw": res.stdout}


def parse_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---"):
        return {}, content.strip()
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content.strip()
    fm_raw, body = parts[1], parts[2]
    meta = {}
    for line in fm_raw.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    meta[k] = json.loads(v)
                except Exception:
                    meta[k] = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
            else:
                meta[k] = v.strip("'\"")
    return meta, body.strip()


def dump_markdown(item: dict) -> str:
    meta = {
        "id": item.get("id", ""),
        "topic": item.get("topic", ""),
        "question": item.get("question", ""),
    }
    if item.get("tags"):
        meta["tags"] = item["tags"]
    if item.get("source_ids"):
        meta["source_ids"] = item["source_ids"]

    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        else:
            # Escape newlines if any
            clean_v = str(v).replace("\n", " ")
            lines.append(f'{k}: "{clean_v}"')
    lines.append("---")
    lines.append("")
    lines.append(item.get("answer", "").strip())
    lines.append("")
    return "\n".join(lines)


def pull_kb():
    KB_DIR.mkdir(parents=True, exist_ok=True)
    print("📡 Получение списка статей с tools.fastup.by...")
    res = run_tool("kb_list")
    items = res.get("items", res if isinstance(res, list) else [])
    print(f"Всего статей на сервере: {len(items)}")

    count = 0
    for it in items:
        item_id = it.get("id")
        if not item_id:
            continue
        full_it = run_tool("kb_get", {"id": item_id})
        filepath = KB_DIR / f"{item_id}.md"
        content = dump_markdown(full_it)
        filepath.write_text(content, encoding="utf-8")
        count += 1
        print(f"  ✅ Загружено: {item_id} -> {filepath.name}")

    print(f"\n🎉 Успешно выгружено {count} статей в {KB_DIR.relative_to(ROOT)}/")


def status_kb(deep: bool = False):
    if not KB_DIR.exists():
        print(f"Папка {KB_DIR.relative_to(ROOT)} не найдена. Сначала выполните `python scripts/sync_kb.py pull`.")
        return

    print("📡 Сверка локальных файлов с сервером...")
    res = run_tool("kb_list")
    server_items = {it["id"]: it for it in res.get("items", res if isinstance(res, list) else [])}

    local_files = list(KB_DIR.glob("*.md"))
    print(f"Локальных файлов: {len(local_files)}, на сервере: {len(server_items)}\n")

    for f in local_files:
        content = f.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(content)
        item_id = meta.get("id", f.stem)
        if item_id not in server_items:
            print(f"  ➕ [НОВАЯ СТАТЬЯ] {f.name} (нет на сервере)")
        else:
            srv = server_items[item_id]
            changed = []
            if meta.get("question", "").strip() != srv.get("question", "").strip():
                changed.append("question")
            if meta.get("topic", "").strip() != srv.get("topic", "").strip():
                changed.append("topic")
            
            # Быстрая проверка превью ответа
            srv_preview = srv.get("answer_preview", "").strip()
            if srv_preview and not body.strip().startswith(srv_preview[:40]):
                changed.append("answer")
            elif deep:
                full_srv = run_tool("kb_get", {"id": item_id})
                if body.strip() != full_srv.get("answer", "").strip():
                    changed.append("answer")

            if changed:
                print(f"  📝 [ИЗМЕНЕНО: {', '.join(changed)}] {item_id}")
            else:
                print(f"  ✅ [СИНХРОНИЗИРОВАНО] {item_id}")


def push_kb(target_id: str = None, push_all: bool = False):
    if not KB_DIR.exists():
        print("Папка bots/kb/ не найдена.")
        return

    res = run_tool("kb_list")
    server_ids = {it["id"] for it in res.get("items", res if isinstance(res, list) else [])}

    files = list(KB_DIR.glob("*.md")) if push_all else [KB_DIR / f"{target_id}.md"]

    for f in files:
        if not f.exists():
            print(f"Файл {f} не найден.")
            continue
        meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        item_id = meta.get("id", f.stem)
        question = meta.get("question", "").strip()
        topic = meta.get("topic", "").strip() or question[:50]
        tags = meta.get("tags", [])
        answer = body.strip()

        if not question or not answer:
            print(f"⚠️ Пропущен {f.name}: нет вопроса или ответа")
            continue

        if item_id in server_ids:
            print(f"⚙️ Обновление статьи {item_id} на сервере...")
            run_tool("kb_update", {"id": item_id, "question": question, "answer": answer, "topic": topic, "tags": tags})
            print(f"  ✅ {item_id} успешно обновлена!")
        else:
            print(f"➕ Добавление новой статьи {item_id} на сервер...")
            run_tool("kb_add", {"question": question, "answer": answer, "topic": topic, "tags": tags, "force": True})
            print(f"  ✅ {item_id} успешно добавлена!")


def main():
    parser = argparse.ArgumentParser(description="Синхронизация базы знаний Алеси (bots/kb/ <-> tools.fastup.by)")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("pull", help="Выгрузить статьи с сервера в bots/kb/")
    subparsers.add_parser("status", help="Проверить статус изменений")

    push_parser = subparsers.add_parser("push", help="Отправить изменения на сервер")
    push_parser.add_argument("id", nargs="?", help="ID статьи для отправки")
    push_parser.add_argument("--all", action="store_true", help="Отправить все локальные статьи")

    args = parser.parse_args()

    if args.command == "pull":
        pull_kb()
    elif args.command == "status":
        status_kb()
    elif args.command == "push":
        if not args.id and not args.all:
            print("Укажите ID статьи или флаг --all.")
            return
        push_kb(args.id, args.all)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
