import os
import re
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

def parse_markdown_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return None

    content = content.lstrip('\ufeff').replace('\r\n', '\n')

    # Extract YAML frontmatter
    yaml_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    date = ""
    tags = ""
    status = ""
    author = ""
    if yaml_match:
        yaml_content = yaml_match.group(1)
        date_match = re.search(r'^date:\s*(.*)$', yaml_content, re.MULTILINE)
        if date_match:
            date = date_match.group(1).strip().strip('\'"')
        tags_match = re.search(r'^tags:\s*\[(.*?)\]', yaml_content, re.MULTILINE)
        if tags_match:
            tags = tags_match.group(1).strip()
        status_match = re.search(r'^status:\s*(.*)$', yaml_content, re.MULTILINE)
        if status_match:
            status = status_match.group(1).strip().strip('\'"')
        author_match = re.search(r'^author:\s*(.*)$', yaml_content, re.MULTILINE)
        if author_match:
            author = author_match.group(1).strip().strip('\'"')

    # Extract Title (H1)
    title = ""
    title_match = re.search(r'^#\s+(.*)$', content, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
    if not title:
        title = os.path.basename(filepath).replace('.md', '')

    # Extract first sentence/paragraph after frontmatter and H1
    content_no_yaml = re.sub(r'^---\s*\n.*?\n---', '', content, flags=re.DOTALL)
    content_no_title = re.sub(r'^#\s+.*$', '', content_no_yaml, flags=re.MULTILINE)
    
    # Get first non-empty paragraph (skip quotes, tables, hr)
    lines = [line.strip() for line in content_no_title.split('\n')
             if line.strip() and not line.strip().startswith(('---', '>', '|', '#', '<!--'))]
    summary = lines[0] if lines else ""
    # Clean up summary
    summary = summary.replace('|', '/').replace('[', '').replace(']', '')
    summary = re.sub(r'(\+375|80)[ \-\(]*[0-9]{2}[ \-\)]*[0-9]{3}[ \-]?[0-9]{2}[ \-]?[0-9]{2}', '[телефон]', summary)
    summary = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[email]', summary)
    if len(summary) > 140:
        summary = summary[:137] + "..."

    return {
        "path": Path(filepath),
        "filename": os.path.basename(filepath),
        "date": date,
        "tags": tags,
        "status": status,
        "author": author,
        "title": title,
        "summary": summary
    }

def build_raw_index():
    raw_dir = ROOT_DIR / "notes" / "raw"
    if not raw_dir.exists():
        return
    files = [f for f in os.listdir(raw_dir) if f.endswith('.md') and f != 'INDEX.md']
    files.sort(reverse=True)
    entries = [parse_markdown_file(raw_dir / f) for f in files]
    entries = [e for e in entries if e]

    current_date = datetime.now().strftime("%Y-%m-%d")
    index_file = raw_dir / "INDEX.md"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write("---\n")
        f.write(f"date: {current_date}\n")
        f.write("tags: [notes, raw, index, auto-generated]\n")
        f.write("status: ready\n")
        f.write("---\n\n")
        f.write("# Автоматический индекс сырых монологов\n\n")
        f.write("Этот файл генерируется автоматически скриптом `scripts/build_index.py`.\n")
        f.write("**Не редактируйте его вручную!** Он обновляется на основе содержимого папки.\n\n")
        f.write("| Файл | Дата | Теги | Заголовок / Выжимка |\n")
        f.write("|---|---|---|---|\n")
        for entry in entries:
            file_link = f"[{entry['filename']}]({entry['filename']})"
            f.write(f"| {file_link} | {entry['date']} | {entry['tags']} | **{entry['title']}**<br>{entry['summary']} |\n")
    print(f"Index built: {index_file} ({len(entries)} entries)")

def build_opinions_index():
    opinions_dir = ROOT_DIR / "expert" / "opinions"
    if not opinions_dir.exists():
        return
    files = [f for f in os.listdir(opinions_dir) if f.endswith('.md') and f not in ('INDEX.md', 'README.md')]
    files.sort(reverse=True)
    entries = [parse_markdown_file(opinions_dir / f) for f in files]
    entries = [e for e in entries if e]

    current_date = datetime.now().strftime("%Y-%m-%d")
    index_file = opinions_dir / "INDEX.md"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write("---\n")
        f.write(f"date: {current_date}\n")
        f.write("tags: [expert, opinions, index, auto-generated]\n")
        f.write("status: ready\n")
        f.write("---\n\n")
        f.write("# Реестр экспертных мнений Егора\n\n")
        f.write("Автоматический индекс мнений фаундера (`expert/opinions/`). Сгенерирован `scripts/build_index.py`.\n\n")
        f.write("| Дата | Статус | Мнение / Ссылка | Теги | Выжимка |\n")
        f.write("|---|---|---|---|---|\n")
        for entry in entries:
            file_link = f"[{entry['title']}]({entry['filename']})"
            f.write(f"| {entry['date']} | {entry['status']} | {file_link} | {entry['tags']} | {entry['summary']} |\n")
    print(f"Index built: {index_file} ({len(entries)} entries)")

def build_decisions_index():
    decisions_dir = ROOT_DIR / "decisions"
    if not decisions_dir.exists():
        return
    files = [f for f in os.listdir(decisions_dir) if f.endswith('.md') and f not in ('INDEX.md', 'README.md')]
    files.sort(reverse=True)
    entries = [parse_markdown_file(decisions_dir / f) for f in files]
    entries = [e for e in entries if e]

    current_date = datetime.now().strftime("%Y-%m-%d")
    index_file = decisions_dir / "INDEX.md"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write("---\n")
        f.write(f"date: {current_date}\n")
        f.write("tags: [decisions, index, auto-generated]\n")
        f.write("status: ready\n")
        f.write("---\n\n")
        f.write("# Полный реестр бизнес-решений\n\n")
        f.write("Автоматический индекс всех решений компании (`decisions/`). Сгенерирован `scripts/build_index.py`.\n\n")
        f.write("| Дата | Статус | Решение / Ссылка | Теги | Контекст |\n")
        f.write("|---|---|---|---|---|\n")
        for entry in entries:
            file_link = f"[{entry['title']}]({entry['filename']})"
            f.write(f"| {entry['date']} | {entry['status']} | {file_link} | {entry['tags']} | {entry['summary']} |\n")
    print(f"Index built: {index_file} ({len(entries)} entries)")

def build_cases_index():
    cases_dir = ROOT_DIR / "cases"
    if not cases_dir.exists():
        return
    files = [f for f in os.listdir(cases_dir) if f.endswith('.md') and f not in ('INDEX.md', 'README.md')]
    files.sort(reverse=True)
    entries = [parse_markdown_file(cases_dir / f) for f in files]
    entries = [e for e in entries if e]

    current_date = datetime.now().strftime("%Y-%m-%d")
    index_file = cases_dir / "INDEX.md"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write("---\n")
        f.write(f"date: {current_date}\n")
        f.write("tags: [cases, index, auto-generated]\n")
        f.write("status: ready\n")
        f.write("---\n\n")
        f.write("# Полный реестр кейсов FastUp\n\n")
        f.write("Автоматический реестр кейсов студии (`cases/`). Сгенерирован `scripts/build_index.py`.\n\n")
        f.write("| Дата | Статус | Кейс / Ссылка | Теги | Суть кейса |\n")
        f.write("|---|---|---|---|---|\n")
        for entry in entries:
            file_link = f"[{entry['title']}]({entry['filename']})"
            f.write(f"| {entry['date']} | {entry['status']} | {file_link} | {entry['tags']} | {entry['summary']} |\n")
    print(f"Index built: {index_file} ({len(entries)} entries)")

def build_geo_index():
    geo_dir = ROOT_DIR / "geo"
    if not geo_dir.exists():
        return
    files = [f for f in os.listdir(geo_dir) if f.endswith('.md') and f not in ('INDEX.md', 'README.md')]
    files.sort(reverse=True)
    entries = [parse_markdown_file(geo_dir / f) for f in files]
    entries = [e for e in entries if e]

    current_date = datetime.now().strftime("%Y-%m-%d")
    index_file = geo_dir / "INDEX.md"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write("---\n")
        f.write(f"date: {current_date}\n")
        f.write("tags: [geo, index, auto-generated]\n")
        f.write("status: ready\n")
        f.write("---\n\n")
        f.write("# Индекс отчётов и методологии GEO\n\n")
        f.write("Автоматический индекс замеров, методик и отчётов (`geo/`). Сгенерирован `scripts/build_index.py`.\n\n")
        f.write("| Дата | Файл / Отчёт | Теги | Кратко |\n")
        f.write("|---|---|---|---|\n")
        for entry in entries:
            file_link = f"[{entry['title']}]({entry['filename']})"
            f.write(f"| {entry['date']} | {file_link} | {entry['tags']} | {entry['summary']} |\n")
    print(f"Index built: {index_file} ({len(entries)} entries)")

def build_posts_index():
    posts_dir = ROOT_DIR / "content" / "posts"
    if not posts_dir.exists():
        return
    files = [f for f in os.listdir(posts_dir) if f.endswith('.md') and f not in ('INDEX.md', 'README.md')]
    files.sort(reverse=True)
    entries = [parse_markdown_file(posts_dir / f) for f in files]
    entries = [e for e in entries if e]

    current_date = datetime.now().strftime("%Y-%m-%d")
    index_file = posts_dir / "INDEX.md"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write("---\n")
        f.write(f"date: {current_date}\n")
        f.write("tags: [content, posts, index, auto-generated]\n")
        f.write("status: ready\n")
        f.write("---\n\n")
        f.write("# Реестр публикаций и постов (Хабр, VC, соцсети)\n\n")
        f.write("Автоматический индекс всех внешних статей и постов (`content/posts/`). Сгенерирован `scripts/build_index.py`.\n\n")
        f.write("| Дата | Статус | Статья / Пост | Теги | Выжимка |\n")
        f.write("|---|---|---|---|---|\n")
        for entry in entries:
            file_link = f"[{entry['title']}]({entry['filename']})"
            f.write(f"| {entry['date']} | {entry['status']} | {file_link} | {entry['tags']} | {entry['summary']} |\n")
    print(f"Index built: {index_file} ({len(entries)} entries)")

def build_content_index():
    content_dir = ROOT_DIR / "content"
    if not content_dir.exists():
        return
    files = [f for f in os.listdir(content_dir) if f.endswith('.md') and f not in ('INDEX.md', 'README.md', 'ideas-archive.md')]
    files.sort(reverse=True)
    entries = [parse_markdown_file(content_dir / f) for f in files]
    entries = [e for e in entries if e]

    current_date = datetime.now().strftime("%Y-%m-%d")
    index_file = content_dir / "INDEX.md"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write("---\n")
        f.write(f"date: {current_date}\n")
        f.write("tags: [content, articles, index, auto-generated]\n")
        f.write("status: ready\n")
        f.write("---\n\n")
        f.write("# Индекс контента и статей FastUp\n\n")
        f.write("Автоматический реестр основных статей, гайдов и контент-планов (`content/`). Сгенерирован `scripts/build_index.py`.\n\n")
        f.write("### Разделы контента:\n")
        f.write("- **[Внешние публикации и посты (Хабр, VC) → `posts/INDEX.md`](posts/INDEX.md)**\n")
        f.write("- **[Черновики и заготовки статей → `drafts/INDEX.md`](drafts/INDEX.md)**\n\n")
        f.write("| Дата | Статус | Материал / Статья | Теги | Суть |\n")
        f.write("|---|---|---|---|---|\n")
        for entry in entries:
            file_link = f"[{entry['title']}]({entry['filename']})"
            f.write(f"| {entry['date']} | {entry['status']} | {file_link} | {entry['tags']} | {entry['summary']} |\n")
    print(f"Index built: {index_file} ({len(entries)} entries)")

def build_drafts_index():
    drafts_dir = ROOT_DIR / "content" / "drafts"
    if not drafts_dir.exists():
        return
    files = [f for f in os.listdir(drafts_dir) if f.endswith('.md') and f not in ('INDEX.md', 'README.md')]
    files.sort(reverse=True)
    entries = [parse_markdown_file(drafts_dir / f) for f in files]
    entries = [e for e in entries if e]

    current_date = datetime.now().strftime("%Y-%m-%d")
    index_file = drafts_dir / "INDEX.md"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write("---\n")
        f.write(f"date: {current_date}\n")
        f.write("tags: [content, drafts, index, auto-generated]\n")
        f.write("status: ready\n")
        f.write("---\n\n")
        f.write("# Реестр черновиков и заготовок материалов\n\n")
        f.write("Автоматический индекс черновиков статей (`content/drafts/`). Сгенерирован `scripts/build_index.py`.\n\n")
        f.write("| Дата | Статус | Черновик | Теги | Кратко |\n")
        f.write("|---|---|---|---|---|\n")
        for entry in entries:
            file_link = f"[{entry['title']}]({entry['filename']})"
            f.write(f"| {entry['date']} | {entry['status']} | {file_link} | {entry['tags']} | {entry['summary']} |\n")
    print(f"Index built: {index_file} ({len(entries)} entries)")

def build_positioning_index():
    pos_dir = ROOT_DIR / "positioning"
    if not pos_dir.exists():
        return
    files = [f for f in os.listdir(pos_dir) if f.endswith('.md') and f not in ('INDEX.md', 'README.md')]
    files.sort()
    entries = [parse_markdown_file(pos_dir / f) for f in files]
    entries = [e for e in entries if e]

    current_date = datetime.now().strftime("%Y-%m-%d")
    index_file = pos_dir / "INDEX.md"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write("---\n")
        f.write(f"date: {current_date}\n")
        f.write("tags: [positioning, index, auto-generated]\n")
        f.write("status: ready\n")
        f.write("---\n\n")
        f.write("# Реестр позиционирования и маркетинговых активов FastUp\n\n")
        f.write("Автоматический индекс ядра позиционирования (`positioning/`). Сгенерирован `scripts/build_index.py`.\n\n")
        f.write("| Актив / Документ | Статус | Теги | Описание |\n")
        f.write("|---|---|---|---|\n")
        for entry in entries:
            file_link = f"[{entry['title']}]({entry['filename']})"
            f.write(f"| {file_link} | {entry['status']} | {entry['tags']} | {entry['summary']} |\n")
    print(f"Index built: {index_file} ({len(entries)} entries)")

def build_playbook_index():
    playbook_dir = ROOT_DIR / "playbook"
    if not playbook_dir.exists():
        return
    files = [f for f in os.listdir(playbook_dir) if f.endswith('.md') and f not in ('INDEX.md', 'README.md')]
    files.sort()
    entries = [parse_markdown_file(playbook_dir / f) for f in files]
    entries = [e for e in entries if e]

    current_date = datetime.now().strftime("%Y-%m-%d")
    index_file = playbook_dir / "INDEX.md"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write("---\n")
        f.write(f"date: {current_date}\n")
        f.write("tags: [playbook, index, auto-generated]\n")
        f.write("status: ready\n")
        f.write("---\n\n")
        f.write("# Реестр плейбуков и регламентов FastUp\n\n")
        f.write("Автоматический индекс регламентов, шаблонов и чек-листов (`playbook/`). Сгенерирован `scripts/build_index.py`.\n\n")
        f.write("| Регламент / Плейбук | Статус | Теги | Назначение |\n")
        f.write("|---|---|---|---|\n")
        for entry in entries:
            file_link = f"[{entry['title']}]({entry['filename']})"
            f.write(f"| {file_link} | {entry['status']} | {entry['tags']} | {entry['summary']} |\n")
    print(f"Index built: {index_file} ({len(entries)} entries)")

def build_notes_index():
    notes_dir = ROOT_DIR / "notes"
    if not notes_dir.exists():
        return
    files = [f for f in os.listdir(notes_dir) if f.endswith('.md') and f not in ('INDEX.md', 'README.md')]
    files.sort(reverse=True)
    entries = [parse_markdown_file(notes_dir / f) for f in files]
    entries = [e for e in entries if e]

    current_date = datetime.now().strftime("%Y-%m-%d")
    index_file = notes_dir / "INDEX.md"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write("---\n")
        f.write(f"date: {current_date}\n")
        f.write("tags: [notes, inbox, index, auto-generated]\n")
        f.write("status: ready\n")
        f.write("---\n\n")
        f.write("# Индекс быстрых заметок инбокса\n\n")
        f.write("Автоматический индекс быстрых заметок (`notes/`). Сгенерирован `scripts/build_index.py`.\n\n")
        f.write("👉 **[Индекс сырых диктовок и монологов → `raw/INDEX.md`](raw/INDEX.md)**\n\n")
        f.write("| Дата | Статус | Заметка / Ссылка | Теги | Суть |\n")
        f.write("|---|---|---|---|---|\n")
        for entry in entries:
            file_link = f"[{entry['title']}]({entry['filename']})"
            f.write(f"| {entry['date']} | {entry['status']} | {file_link} | {entry['tags']} | {entry['summary']} |\n")
    print(f"Index built: {index_file} ({len(entries)} entries)")

def build_promotion_index():
    promo_dir = ROOT_DIR / "promotion"
    if not promo_dir.exists():
        return
    files = [f for f in os.listdir(promo_dir) if f.endswith('.md') and f not in ('INDEX.md', 'README.md')]
    files.sort(reverse=True)
    entries = [parse_markdown_file(promo_dir / f) for f in files]
    entries = [e for e in entries if e]

    current_date = datetime.now().strftime("%Y-%m-%d")
    index_file = promo_dir / "INDEX.md"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write("---\n")
        f.write(f"date: {current_date}\n")
        f.write("tags: [promotion, sales, outreach, index, auto-generated]\n")
        f.write("status: ready\n")
        f.write("---\n\n")
        f.write("# Реестр каналов продвижения и продаж FastUp\n\n")
        f.write("Автоматический индекс скриптов продаж, лидогенерации и каналов продвижения (`promotion/`). Сгенерирован `scripts/build_index.py`.\n\n")
        f.write("| Документ / Скрипт | Статус | Теги | Описание |\n")
        f.write("|---|---|---|---|\n")
        for entry in entries:
            file_link = f"[{entry['title']}]({entry['filename']})"
            f.write(f"| {file_link} | {entry['status']} | {entry['tags']} | {entry['summary']} |\n")
    print(f"Index built: {index_file} ({len(entries)} entries)")

def build_live_pages_index():
    lp_dir = ROOT_DIR / "content" / "live-pages"
    if not lp_dir.exists():
        return
    files = [f for f in os.listdir(lp_dir) if f.endswith('.md') and f not in ('INDEX.md', 'README.md')]
    files.sort()
    entries = [parse_markdown_file(lp_dir / f) for f in files]
    entries = [e for e in entries if e]

    current_date = datetime.now().strftime("%Y-%m-%d")
    index_file = lp_dir / "INDEX.md"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write("---\n")
        f.write(f"date: {current_date}\n")
        f.write("tags: [content, live-pages, index, auto-generated]\n")
        f.write("status: ready\n")
        f.write("---\n\n")
        f.write("# Зеркало живых страниц сайта FastUp.by\n\n")
        f.write("Автоматический индекс markdown-снимков живых страниц (`content/live-pages/`). Сгенерирован `scripts/build_index.py`.\n\n")
        f.write("| Страница сайта | URL | Заголовок |\n")
        f.write("|---|---|---|\n")
        for entry in entries:
            file_link = f"[{entry['filename']}]({entry['filename']})"
            f.write(f"| {file_link} | `https://fastup.by/{entry['filename'].replace('.md', '')}/` | {entry['title']} |\n")
    print(f"Index built: {index_file} ({len(entries)} entries)")

def build_research_index():
    res_dir = ROOT_DIR / "content" / "research"
    if not res_dir.exists():
        return
    files = [f for f in res_dir.rglob('*.md') if f.name not in ('INDEX.md', 'README.md')]
    files.sort()
    entries = [parse_markdown_file(f) for f in files]
    entries = [e for e in entries if e]

    current_date = datetime.now().strftime("%Y-%m-%d")
    index_file = res_dir / "INDEX.md"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write("---\n")
        f.write(f"date: {current_date}\n")
        f.write("tags: [content, research, competitors, index, auto-generated]\n")
        f.write("status: ready\n")
        f.write("---\n\n")
        f.write("# Реестр исследований рынка, конкурентов и семантики\n\n")
        f.write("Автоматический индекс ресёрча (`content/research/`). Сгенерирован `scripts/build_index.py`.\n\n")
        f.write("| Документ / Анализ | Теги | Выжимка |\n")
        f.write("|---|---|---|\n")
        for entry in entries:
            rel = entry['path'].relative_to(res_dir).as_posix()
            file_link = f"[{entry['title']}]({rel})"
            f.write(f"| {file_link} | {entry['tags']} | {entry['summary']} |\n")
    print(f"Index built: {index_file} ({len(entries)} entries)")

def build_ads_index():
    ads_dir = ROOT_DIR / "ads"
    if not ads_dir.exists():
        return
    files = []
    for sub in (ads_dir, ads_dir / "campaigns", ads_dir / "reports"):
        if sub.exists():
            files += [sub / f for f in sorted(os.listdir(sub))
                      if f.endswith('.md') and f not in ('INDEX.md', 'README.md')]
    entries = [parse_markdown_file(f) for f in files]
    entries = [e for e in entries if e]

    current_date = datetime.now().strftime("%Y-%m-%d")
    index_file = ads_dir / "INDEX.md"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write("---\n")
        f.write(f"date: {current_date}\n")
        f.write("tags: [ads, index, auto-generated]\n")
        f.write("status: ready\n")
        f.write("---\n\n")
        f.write("# Реестр рекламных материалов и отчётов\n\n")
        f.write("Автоматический индекс раздела рекламы (`ads/`). Сгенерирован `scripts/build_index.py`.\n\n")
        f.write("| Дата | Документ | Статус | Теги | Содержание |\n")
        f.write("|---|---|---|---|---|\n")
        for entry in entries:
            rel = entry['path'].relative_to(ads_dir).as_posix()
            f.write(f"| {entry['date']} | [{entry['title']}]({rel}) | {entry['status']} | {entry['tags']} | {entry['summary']} |\n")
    print(f"Index built: {index_file} ({len(entries)} entries)")

def build_all():
    build_raw_index()
    build_notes_index()
    build_opinions_index()
    build_decisions_index()
    build_cases_index()
    build_geo_index()
    build_posts_index()
    build_content_index()
    build_drafts_index()
    build_live_pages_index()
    build_research_index()
    build_positioning_index()
    build_promotion_index()
    build_playbook_index()
    build_ads_index()

if __name__ == "__main__":
    build_all()
