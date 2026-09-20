#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Управление корпоративными документами Google Docs и Google Drive FastUp.by.

Работает напрямую через Google Apps Script шлюз компании под аккаунтом фирмы
в корпоративной папке «Акты/Договоры FastUp». Не зависит от личного Google-аккаунта
и не требует авторизации в браузере.

Команды:
    python scripts/gdocs.py list [--query "поиск"] [--folder "Акты"] [--json]
    python scripts/gdocs.py folders [--json]
    python scripts/gdocs.py read <FILE_ID>
    python scripts/gdocs.py create --title "..." [--content "..." | --file path.md] [--folder "Акты"]
    python scripts/gdocs.py copy --template-id <ID> --title "..." [--folder "Договоры"]
    python scripts/gdocs.py replace <FILE_ID> --pairs find1=replace1 find2=replace2
    python scripts/gdocs.py move <FILE_ID> --to <TARGET_FOLDER_ID>
    python scripts/gdocs.py trash <FILE_ID> [<FILE_ID_2> ...]
"""
import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

# Гарантируем UTF-8 вывод на любой консоли
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Подхват .env
try:
    from env_load import load_env
    load_env()
except ImportError:
    pass

# Адрес шлюза и его секрет — только из .env: код лежит в общем репозитории.
DEFAULT_GAS_URL = os.environ.get("GDOCS_GAS_URL", "").strip()
DEFAULT_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID") or "1YIvypoZFWwxmpQby2LOOXhI4LoeHFUDl"
GAS_SECRET = os.environ.get("GDOCS_GAS_SECRET", "").strip()
if not DEFAULT_GAS_URL or not GAS_SECRET:
    sys.stderr.write("Нет GDOCS_GAS_URL или GDOCS_GAS_SECRET в .env — доступ к документам выдаёт Егор\n")
    sys.exit(2)


import time

def gas_request(payload: dict, timeout: int = 60, retries: int = 2) -> dict:
    """Сырой вызов шлюза: {"ok": bool, "data": ..., "error": ...}. Адрес и секрет — из .env.

    Единственное место, где собирается запрос к шлюзу. Остальные скрипты (раскладка Диска,
    загрузка сканов) зовут его, а не держат свою копию адреса: без секрета шлюз отказывает.
    """
    body = {"folderId": DEFAULT_FOLDER_ID, **payload, "secret": GAS_SECRET}
    req_data = json.dumps(body).encode("utf-8")
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                DEFAULT_GAS_URL,
                data=req_data,
                headers={"Content-Type": "text/plain;charset=utf-8"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8")
            break
        except Exception as e:
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            return {"ok": False, "error": f"запрос к шлюзу не прошёл: {e}"}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"ok": False, "error": f"некорректный JSON ответа шлюза: {text[:300]}"}


def call_gas(action: str, payload: dict = None, retries: int = 2) -> dict:
    """Вызов действия шлюза для CLI: ошибка — сообщение и выход, успех — поле data."""
    data = gas_request({"action": action, **(payload or {})}, retries=retries)
    if not data.get("ok"):
        sys.stderr.write(f"Ошибка Google Apps Script: {data.get('error', 'неизвестная ошибка')}\n")
        sys.exit(1)

    return data.get("data")


def cmd_list(args):
    payload = {}
    if args.query:
        payload["query"] = args.query
    if args.folder:
        payload["folderName"] = args.folder

    files = call_gas("gdrive_list", payload)
    if args.json:
        print(json.dumps(files, ensure_ascii=False, indent=2))
        return

    if not files:
        print("Документы не найдены.")
        return

    print(f"Найдено документов: {len(files)}\n")
    for f in files:
        fid = f.get("id", "")
        name = f.get("name", "")
        folder = f.get("folder", "")
        mod = f.get("modifiedTime", "")[:10]
        url = f.get("webViewLink", "")
        print(f"[{fid}] {name}")
        print(f"  Папка: {folder} | Изменён: {mod}")
        print(f"  Ссылка: {url}\n")


def cmd_folders(args):
    folders = call_gas("gdrive_list_folders")
    if args.json:
        print(json.dumps(folders, ensure_ascii=False, indent=2))
        return

    if not folders:
        print("Папки не найдены.")
        return

    print(f"Папки верхнего уровня ({len(folders)}):\n")
    for f in folders:
        fid = f.get("id", "")
        name = f.get("name", "")
        url = f.get("url", "")
        print(f"[{fid}] {name} -> {url}")


def cmd_read(args):
    text = call_gas("gdrive_read_doc", {"fileId": args.file_id})
    print(text)


def cmd_create(args):
    content = args.content or ""
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            sys.stderr.write(f"Файл контента не найден: {args.file}\n")
            sys.exit(1)
        content = file_path.read_text(encoding="utf-8")

    payload = {
        "title": args.title,
        "content": content,
    }
    if args.folder:
        payload["folderName"] = args.folder

    res = call_gas("gdocs_create", payload)
    fid = res.get("id")
    folder_name = res.get("folder", "")
    url = f"https://docs.google.com/document/d/{fid}/edit"

    print(f"Создан документ:")
    print(f"  ID:     {fid}")
    print(f"  Папка:  {folder_name}")
    print(f"  Ссылка: {url}")


def cmd_copy(args):
    payload = {
        "templateFileId": args.template_id,
        "title": args.title,
    }
    if args.folder:
        payload["folderName"] = args.folder

    res = call_gas("gdocs_copy_template", payload)
    fid = res.get("id")
    folder_name = res.get("folder", "")
    url = f"https://docs.google.com/document/d/{fid}/edit"

    print(f"Скопирован шаблон:")
    print(f"  ID:     {fid}")
    print(f"  Папка:  {folder_name}")
    print(f"  Ссылка: {url}")


def cmd_replace(args):
    pairs = []
    for p in args.pairs:
        if "=" not in p:
            sys.stderr.write(f"Пара должна быть в формате find=replace, получено: {p}\n")
            sys.exit(1)
        k, _, v = p.partition("=")
        pairs.append({"find": k, "replace": v})

    res = call_gas("gdocs_replace", {"fileId": args.file_id, "pairs": pairs})
    print(f"Замены выполнены в файле {args.file_id}: {len(pairs)} замен.")


def cmd_move(args):
    res = call_gas("gdrive_move_file", {"fileId": args.file_id, "targetFolderId": args.to})
    print(f"Файл {args.file_id} перемещён в папку {args.to}")


def cmd_trash(args):
    res = call_gas("gdrive_trash", {"fileIds": args.file_ids})
    trashed = res.get("trashed", [])
    errors = res.get("errors", [])
    if trashed:
        print(f"Удалено в корзину ({len(trashed)}):")
        for item in trashed:
            print(f"  - [{item.get('id')}] {item.get('name')}")
    if errors:
        print(f"Ошибки при удалении ({len(errors)}):")
        for err in errors:
            print(f"  ! [{err.get('id')}] {err.get('error')}")


def cmd_upload(args):
    import base64
    import mimetypes

    file_path = Path(args.file)
    if not file_path.exists():
        sys.stderr.write(f"Файл не найден: {args.file}\n")
        sys.exit(1)

    filename = args.name or file_path.name
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if not mime_type:
        mime_type = "application/pdf" if file_path.suffix.lower() == ".pdf" else "application/octet-stream"

    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "fileName": filename,
        "mimeType": mime_type,
        "base64Data": b64,
    }
    if args.folder:
        payload["folderName"] = args.folder
    if args.folder_id:
        payload["folderId"] = args.folder_id

    res = call_gas("gdrive_upload_file", payload)
    fid = res.get("id")
    folder_name = res.get("folder", "")
    url = res.get("url", f"https://drive.google.com/file/d/{fid}/view")
    print(f"Загружен файл:")
    print(f"  Имя:    {filename}")
    print(f"  ID:     {fid}")
    print(f"  Папка:  {folder_name}")
    print(f"  Ссылка: {url}")


def cmd_cleanup(args):
    res = call_gas("gdrive_cleanup")
    moved = res.get("movedFiles", [])
    trashed_folds = res.get("trashedFolders", [])
    trashed_files = res.get("trashedFiles", [])

    print("=== ИТОГИ ОЧИСТКИ КРИВЫХ ПАПОК И МУСОРА ===")
    if moved:
        print(f"Перемещено файлов из кривых папок: {len(moved)}")
        for m in moved:
            print(f"  - {m.get('file')}: {m.get('from')} -> {m.get('to')}")
    if trashed_folds:
        print(f"Удалено кривых папок: {len(trashed_folds)}")
        for tf in trashed_folds:
            print(f"  - [{tf.get('id')}] {tf.get('name')} ({tf.get('reason')})")
    if trashed_files:
        print(f"Удалено черновых файлов/дубликатов: {len(trashed_files)}")
        for tf in trashed_files:
            print(f"  - [{tf.get('id')}] {tf.get('name')} ({tf.get('reason')})")
    if not moved and not trashed_folds and not trashed_files:
        print("Кривых папок и мусора не обнаружено. Всё чисто!")


def cmd_organize(args):
    res = call_gas("gdrive_organize", {"trashJunk": args.trash})
    moved = res.get("moved", [])
    trashed = res.get("trashed", [])
    print("=== ИТОГИ РАСКЛАДКИ ПО ПАПКАМ ===")
    print(f"Перемещено по категориям: {len(moved)}")
    for m in moved:
        print(f"  - {m.get('name')} -> {m.get('to')}")
    if trashed:
        print(f"Удалено мусора: {len(trashed)}")
        for t in trashed:
            print(f"  - {t.get('name')}")


def cmd_rename(args):
    res = call_gas("gdrive_rename", {"id": args.id, "name": args.name})
    print(f"Переименовано: [{res.get('id')}] -> {res.get('name')}")


def cmd_export_pdf(args):
    payload = {"fileId": args.file_id}
    if args.name:
        payload["fileName"] = args.name
    if args.folder:
        payload["folderName"] = args.folder
    res = call_gas("gdocs_export_pdf", payload)
    print(f"Экспортирован PDF:")
    print(f"  Имя:    {res.get('name')}")
    print(f"  ID:     {res.get('id')}")
    print(f"  Папка:  {res.get('folder')}")
    print(f"  Ссылка: {res.get('url')}")


def cmd_audit(args):
    res = call_gas("gdrive_audit")
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return
    print(f"=== АУДИТ ДОКУМЕНТОВ НА ДИСКЕ ({len(res)} шт.) ===")
    for item in res:
        print(f"[{item.get('id')}] {item.get('name')} | Папка: {item.get('folder')} | {item.get('modifiedTime', '')[:10]}")


def main():
    parser = argparse.ArgumentParser(
        description="Управление документами Google Docs/Drive компании FastUp"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # upload
    p_upload = sub.add_parser("upload", help="Загрузить бинарный файл (PDF, скан, чек) в Google Диск")
    p_upload.add_argument("file", help="Путь к локальному файлу")
    p_upload.add_argument("--name", "-n", help="Имя файла на Диске (по умолчанию имя локального файла)")
    p_upload.add_argument("--folder", "-f", help="Имя целевой папки на Google Диске")
    p_upload.add_argument("--folder-id", help="ID целевой папки на Google Диске")
    p_upload.set_defaults(func=cmd_upload)

    # list
    p_list = sub.add_parser("list", help="Поиск и список файлов в Google Диске")
    p_list.add_argument("--query", "-q", help="Поисковый запрос по названию")
    p_list.add_argument("--folder", "-f", help="Ограничить подпапкой (напр. «Акты», «Договоры»)")
    p_list.add_argument("--json", action="store_true", help="Вывод в сыром JSON")
    p_list.set_defaults(func=cmd_list)

    # folders
    p_folders = sub.add_parser("folders", help="Список папок верхнего уровня")
    p_folders.add_argument("--json", action="store_true", help="Вывод в сыром JSON")
    p_folders.set_defaults(func=cmd_folders)

    # read
    p_read = sub.add_parser("read", help="Прочитать текст Google Документа")
    p_read.add_argument("file_id", help="ID Google Документа")
    p_read.set_defaults(func=cmd_read)

    # create
    p_create = sub.add_parser("create", help="Создать Google Документ с Markdown-содержимым")
    p_create.add_argument("--title", "-t", required=True, help="Название документа")
    p_create.add_argument("--content", "-c", help="Markdown-текст документа")
    p_create.add_argument("--file", help="Путь к markdown-файлу с текстом документа")
    p_create.add_argument("--folder", "-f", help="Подпапка для сохранения (напр. «Акты», «Договоры»)")
    p_create.set_defaults(func=cmd_create)

    # copy
    p_copy = sub.add_parser("copy", help="Скопировать шаблон Google Документа")
    p_copy.add_argument("--template-id", required=True, help="ID файла-шаблона")
    p_copy.add_argument("--title", "-t", required=True, help="Название нового документа")
    p_copy.add_argument("--folder", "-f", help="Подпапка для сохранения")
    p_copy.set_defaults(func=cmd_copy)

    # replace
    p_replace = sub.add_parser("replace", help="Заменить плейсхолдеры в документе")
    p_replace.add_argument("file_id", help="ID Google Документа")
    p_replace.add_argument(
        "--pairs",
        nargs="+",
        required=True,
        help="Пары поиска-замены через знак = (напр. client=ИП_Иванов sum=500)",
    )
    p_replace.set_defaults(func=cmd_replace)

    # move
    p_move = sub.add_parser("move", help="Переместить файл в другую папку")
    p_move.add_argument("file_id", help="ID Google Документа")
    p_move.add_argument("--to", required=True, help="ID целевой папки")
    p_move.set_defaults(func=cmd_move)

    # trash
    p_trash = sub.add_parser("trash", help="Переместить документ(ы) в корзину")
    p_trash.add_argument("file_ids", nargs="+", help="Один или несколько ID файлов")
    p_trash.set_defaults(func=cmd_trash)

    # cleanup
    p_clean = sub.add_parser("cleanup", help="Очистить кривые папки (с ID в названии) и удалить черновой мусор")
    p_clean.set_defaults(func=cmd_cleanup)

    # organize
    p_org = sub.add_parser("organize", help="Авто-раскладка документов по целевым папкам")
    p_org.add_argument("--trash", action="store_true", help="Отправлять мусорные черновики в корзину")
    p_org.set_defaults(func=cmd_organize)

    # rename
    p_ren = sub.add_parser("rename", help="Переименовать файл или папку на Диске")
    p_ren.add_argument("id", help="ID файла или папки")
    p_ren.add_argument("name", help="Новое название")
    p_ren.set_defaults(func=cmd_rename)

    # export-pdf
    p_pdf = sub.add_parser("export-pdf", help="Экспортировать Google Doc в PDF на Google Диске")
    p_pdf.add_argument("file_id", help="ID Google Документа")
    p_pdf.add_argument("--name", "-n", help="Имя итогового PDF файла")
    p_pdf.add_argument("--folder", "-f", help="Папка для сохранения PDF")
    p_pdf.set_defaults(func=cmd_export_pdf)

    # audit
    p_aud = sub.add_parser("audit", help="Полный аудит документов на Диске")
    p_aud.add_argument("--json", action="store_true", help="Вывод в JSON")
    p_aud.set_defaults(func=cmd_audit)

    parsed = parser.parse_args()
    parsed.func(parsed)


if __name__ == "__main__":
    main()
