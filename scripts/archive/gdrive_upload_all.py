#!/usr/bin/env python3
"""Пакетная загрузка всех структурированных бухгалтерских документов на Google Диск FastUp.

Работает через шлюз Google Apps Script компании (под аккаунтом fastup.by@gmail.com).
"""
import base64
import mimetypes
import os
import sys
from pathlib import Path

from gdocs import gas_request  # адрес шлюза и секрет — из .env

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID") or "1YIvypoZFWwxmpQby2LOOXhI4LoeHFUDl"
LOCAL_BASE = Path(r"G:\fastup-docs\документы-структурированные")

# Карта папок: локальный каталог -> целевая папка на Диске компании
FOLDER_MAPPING = {
    "01_договоры_клиенты": "Договоры/Клиенты",
    "02_акты_клиенты": "Акты/Клиенты",
    "03_договоры_подрядчики": "Договоры/Подрядчики",
    "04_акты_подрядчики": "Акты/Подрядчики",
    "05_чеки_нпд": "Чеки НПД",
    "06_расходы_поставщики": "Расходы",
}


# Ошибочные экземпляры: имя выглядит правильным, содержимое — нет.
BROKEN_FILES = {
    # Акт выписан на Василюк В.Ю., другое лицо; корректная версия — от 19.06.
    "12_Акт_Громыко_85BYN_17.06.2026_ПОДПИСАН_ЕГОРОМ.pdf",
}


def skip_reason(path: Path):
    """Почему файл не должен уезжать на Диск.

    Скрипт грузил всё подряд из пяти каталогов. В рабочем архиве рядом с настоящими
    документами лежат: HTML-заглушки под расширением .pdf (сохранённая страница входа
    в Google, ~939 КБ), неподписанные бланки-дубли к каждому подписанному акту,
    технические исходники и ошибочная версия акта Громыко от 17.06 (выписана на другое
    лицо). Любой из них, попав в рабочую папку Диска, снова становится кандидатом
    на печать и на ссылку подрядчику.
    """
    if path.suffix.lower() == ".pdf":
        with open(path, "rb") as fh:
            if fh.read(5) != b"%PDF-":
                return "не PDF внутри (HTML-заглушка)"

    lowered = path.name.lower()
    for marker in ("_бланк_без_подписей", "_исходник", "_черновик", "_копия", "вопрос_открыт", "_clean"):
        if marker in lowered:
            return "служебный файл (" + marker + ")"

    if path.name in BROKEN_FILES:
        return "ошибочный экземпляр, заменён другим файлом"

    # Неподписанный бланк рядом с подписанным экземпляром: на Диске такие дубли уже
    # убирали руками 11.09, чтобы на печать не ушёл экземпляр без подписи Егора.
    if "ПОДПИСАН" not in path.name:
        prefix = path.name.split("_", 1)[0]
        if prefix.isdigit():
            for sibling in path.parent.iterdir():
                if (
                    sibling != path
                    and sibling.name.startswith(prefix + "_")
                    and "ПОДПИСАН" in sibling.name
                ):
                    return "неподписанный бланк, есть подписанный экземпляр"

    return None


def check_gas_ready():
    """Проверка, обновлён ли Google Apps Script новой версией с поддержкой upload."""
    data = gas_request({"action": "gdrive_upload_file"}, timeout=20, retries=0)
    error = str(data.get("error") or "")
    return error != "Unknown action: gdrive_upload_file" and not error.startswith("запрос к шлюзу")


def upload_via_gas(filepath: Path, target_folder_name: str):
    """Загрузка одного файла через Google Apps Script."""
    with open(filepath, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    mime_type, _ = mimetypes.guess_type(str(filepath))
    if not mime_type:
        mime_type = "application/pdf"

    payload = {
        "action": "gdrive_upload_file",
        "folderId": ROOT_FOLDER_ID,
        "folderName": target_folder_name,
        "fileName": filepath.name,
        "mimeType": mime_type,
        "base64Data": b64,
    }

    return gas_request(payload, timeout=90, retries=2)


def main():
    if not LOCAL_BASE.exists():
        print(f"Ошибка: Каталог {LOCAL_BASE} не найден!")
        sys.exit(1)

    print("Проверка готовности Google Apps Script шлюза...")
    if not check_gas_ready():
        print("ВНИМАНИЕ: Google Apps Script на script.google.com ещё не обновлён новой версией!")
        print("Нужно вставить код из google-apps-script.js и нажать Deploy -> New version.")
        sys.exit(2)

    print("Шлюз Google Apps Script готов к загрузке файлов!\n")

    all_files = []
    skipped = []
    for local_dir, gfolder in FOLDER_MAPPING.items():
        src_path = LOCAL_BASE / local_dir
        if not src_path.exists():
            continue
        for f in sorted(src_path.iterdir()):
            if not f.is_file() or f.name.startswith("."):
                continue
            reason = skip_reason(f)
            if reason:
                skipped.append((f, reason))
                continue
            all_files.append((f, gfolder))

    if skipped:
        print("Пропущено " + str(len(skipped)) + " файлов (на Диск не поедут):")
        for f, reason in skipped:
            print("  - " + f.name + ": " + reason)
        print()

    print(f"Всего к загрузке: {len(all_files)} файлов.\n")

    uploaded = 0
    failed = []

    for idx, (filepath, target_folder) in enumerate(all_files, 1):
        print(f"[{idx}/{len(all_files)}] Загрузка {filepath.name} -> {target_folder}...", end=" ", flush=True)
        res = upload_via_gas(filepath, target_folder)
        if res.get("ok"):
            finfo = res.get("data", {})
            print(f"OK (ID: {finfo.get('id')})")
            uploaded += 1
        else:
            err = res.get("error", "неизвестная ошибка")
            print(f"ОШИБКА: {err}")
            failed.append((filepath.name, err))

    print("\n" + "=" * 50)
    print(f"Загрузка завершена: успешно {uploaded} из {len(all_files)}")
    if failed:
        print(f"Ошибок: {len(failed)}")


if __name__ == "__main__":
    main()
