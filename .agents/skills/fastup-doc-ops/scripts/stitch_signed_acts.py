
import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
import base64
from pathlib import Path
import sys
import fitz  # PyMuPDF

from gdocs import gas_request  # адрес шлюза и секрет — из .env

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LOCAL_ACTS_DIR = Path(r"G:\fastup-docs\документы-структурированные\04_акты_подрядчики")
PHOTO_DIR = Path(r"D:\telegram")
TARGET_FOLDER_ID = "11bXxnljHCjVC8ae373v8iTbtTqwvPeDG"  # Акты/Подрядчики

# A4 dimensions in points
A4_WIDTH = 595.32
A4_HEIGHT = 841.92
A4_RECT = fitz.Rect(0, 0, A4_WIDTH, A4_HEIGHT)

def add_image_page(doc, image_path: Path):
    """Добавляет страницу A4 с аккуратно вписанным изображением высокого качества."""
    page = doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
    page.insert_image(A4_RECT, filename=str(image_path), keep_proportion=True)

# Спецификация сборки 8 подписанных актов:
# (имя выходного файла, список источников страниц: ('pdf', path, from_p, to_p) или ('img', path))
TASKS = [
    {
        "name": "03_Акт_Шепеленко_335BYN_25.06-10.07.2026_ПОДПИСАН_ЕГОРОМ.pdf",
        "base_name": "03_Акт_Шепеленко_335BYN_25.06-10.07.2026.pdf",
        "pages": [
            ("pdf", LOCAL_ACTS_DIR / "03_Акт_Шепеленко_335BYN_25.06-10.07.2026.pdf", 0, 0),
            ("img", PHOTO_DIR / "photo_2_2026-09-11_18-41-11.jpg")
        ]
    },
    {
        "name": "04_Акт_Шепеленко_290BYN_10.07-27.07.2026_ПОДПИСАН_ЕГОРОМ.pdf",
        "base_name": "04_Акт_Шепеленко_290BYN_10.07-27.07.2026.pdf",
        "pages": [
            ("pdf", LOCAL_ACTS_DIR / "04_Акт_Шепеленко_290BYN_10.07-27.07.2026.pdf", 0, 1),
            ("img", PHOTO_DIR / "photo_3_2026-09-11_18-41-11.jpg")
        ]
    },
    {
        "name": "05_Акт_Шепеленко_145BYN_28.07-05.08.2026_ПОДПИСАН_ЕГОРОМ.pdf",
        "base_name": "05_Акт_Шепеленко_145BYN_28.07-05.08.2026.pdf",
        "pages": [
            ("pdf", LOCAL_ACTS_DIR / "05_Акт_Шепеленко_145BYN_28.07-05.08.2026.pdf", 0, 1),
            ("img", PHOTO_DIR / "photo_5_2026-09-11_18-41-11.jpg")
        ]
    },
    {
        "name": "06_Акт_Шепеленко_334BYN_06.08-18.08.2026_ПОДПИСАН_ЕГОРОМ.pdf",
        "base_name": "06_Акт_Шепеленко_334BYN_06.08-18.08.2026.pdf",
        "pages": [
            ("pdf", LOCAL_ACTS_DIR / "06_Акт_Шепеленко_334BYN_06.08-18.08.2026.pdf", 0, 0),
            ("img", PHOTO_DIR / "photo_4_2026-09-11_18-41-11.jpg")
        ]
    },
    {
        "name": "07_Акт_Шепеленко_225BYN_19.08-01.09.2026_ПОДПИСАН_ЕГОРОМ.pdf",
        "base_name": "07_Акт_Шепеленко_225BYN_19.08-01.09.2026.pdf",
        "pages": [
            ("pdf", LOCAL_ACTS_DIR / "07_Акт_Шепеленко_225BYN_19.08-01.09.2026.pdf", 0, 0),
            ("img", PHOTO_DIR / "photo_10_2026-09-11_18-41-11.jpg")
        ]
    },
    {
        "name": "08_Акт_Андрейчук_50BYN_22.06.2026_ПОДПИСАН_ЕГОРОМ.pdf",
        "base_name": "08_Акт_Андрейчук_50BYN_22.06.2026.pdf",
        "pages": [
            ("img", PHOTO_DIR / "photo_8_2026-09-11_18-41-11.jpg"), # стр 1 с подписью
            ("img", PHOTO_DIR / "photo_9_2026-09-11_18-41-11.jpg")  # стр 2 с реквизитами и подписью (четкий вариант photo_1)
        ]
    },
    {
        "name": "10_Акт_Ковалевич_100BYN_11.08-25.08.2026_ПОДПИСАН_ЕГОРОМ.pdf",
        "base_name": "10_Акт_Ковалевич_100BYN_11.08-25.08.2026.pdf",
        "pages": [
            ("pdf", LOCAL_ACTS_DIR / "10_Акт_Ковалевич_100BYN_11.08-25.08.2026.pdf", 0, 0),
            ("img", PHOTO_DIR / "photo_6_2026-09-11_18-41-11.jpg")
        ]
    },
    {
        "name": "11_Акт_Ковалевич_336BYN_10.09.2026_ПОДПИСАН_ЕГОРОМ.pdf",
        "base_name": "11_Акт_Ковалевич_336BYN_10.09.2026.pdf",
        "pages": [
            ("pdf", LOCAL_ACTS_DIR / "kovalevich_clean.pdf", 0, 0), # стр 1 чистый перечень работ
            ("img", PHOTO_DIR / "photo_7_2026-09-11_18-41-11.jpg")  # стр 2 реквизиты и подпись Егора
        ]
    },
]

def build_pdf(task):
    out_pdf = fitz.open()
    docs_to_close = []
    for item in task["pages"]:
        itype = item[0]
        if itype == "pdf":
            _, src_path, from_p, to_p = item
            src_doc = fitz.open(src_path)
            out_pdf.insert_pdf(src_doc, from_page=from_p, to_page=to_p)
            docs_to_close.append(src_doc)
        elif itype == "img":
            _, img_path = item
            add_image_page(out_pdf, img_path)
    
    for d in docs_to_close:
        d.close()

    dest_path = LOCAL_ACTS_DIR / task["name"]
    out_pdf.save(dest_path)
    out_pdf.close()
    print(f"Собран PDF: {task['name']} -> {dest_path.name}")
    return dest_path

def upload_to_gdrive(filepath: Path, target_folder_id: str):
    with open(filepath, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    payload = {
        "action": "gdrive_upload_file",
        "folderId": target_folder_id,
        "fileName": filepath.name,
        "mimeType": "application/pdf",
        "base64Data": b64,
        "overwrite": True
    }
    return gas_request(payload, timeout=40)

def main():
    print("=== Начало сборки 8 подписанных актов с фотоподписями ===")
    built_files = []
    for task in TASKS:
        dest_path = build_pdf(task)
        built_files.append(dest_path)
    
    print("\n=== Загрузка подписанных актов на Google Диск (Акты/Подрядчики) ===")
    for f in built_files:
        print(f"Загрузка {f.name}...", end=" ", flush=True)
        res = upload_to_gdrive(f, TARGET_FOLDER_ID)
        print("OK" if res.get("ok") else f"ERR: {res.get('error')}")

if __name__ == "__main__":
    main()
