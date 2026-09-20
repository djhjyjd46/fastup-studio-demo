
import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from env_load import load_env

load_env()

CLIENTS_DIR = Path(os.environ.get("FASTUP_CLIENTS_DIR", ROOT.parent / "fastup-clients")).resolve()


def get_slug(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    netloc = re.sub(r"^www\.", "", netloc)
    slug = re.sub(r"[^a-z0-9\-]", "-", netloc.split(".")[0])
    return slug or "client"


def run_crawl(url: str, out_path: Path) -> dict:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "site_crawl.py"),
        url,
        "--max-pages",
        "15",
        "--out",
        str(out_path),
    ]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    subprocess.run(cmd, check=True, env=env)
    return json.loads(out_path.read_text(encoding="utf-8"))


def analyze_crawl(data: dict) -> dict:
    pages = data.get("pages", [])
    robots = data.get("robots", {})
    sitemap = data.get("sitemap", {})
    llms_txt = data.get("llms_txt", {})

    issues = []
    strengths = []

    if not robots.get("exists"):
        issues.append("Отсутствует файл robots.txt (поисковики не получают инструкций об индексации).")
    else:
        strengths.append("Файл robots.txt присутствует.")

    if not sitemap.get("found"):
        issues.append("Карта сайта sitemap.xml не обнаружена (замедляет появление новых страниц в индексе).")
    else:
        strengths.append(f"Карта сайта обнаружена ({sitemap.get('url_count', 0)} URL).")

    if not llms_txt.get("exists"):
        issues.append("Отсутствует llms.txt (сайт не адаптирован для прямого считывания ИИ-краулерами).")

    if pages:
        p0 = pages[0]
        title = p0.get("title") or ""
        desc = p0.get("description") or ""
        h1 = p0.get("h1") or []

        if not title:
            issues.append("Главная страница без Title.")
        elif len(title) > 80:
            issues.append(f"Title слишком длинный ({len(title)} симв.): «{title[:60]}...».")
        else:
            strengths.append(f"Корректный Title: «{title}».")

        if not desc:
            issues.append("Отсутствует Meta Description (сниппет в поиске формируется случайно).")
        else:
            strengths.append(f"Meta Description заполнен ({len(desc)} симв.).")

        if not h1:
            issues.append("На главной странице отсутствует заголовок H1.")
        elif len(h1) > 1:
            issues.append(f"Несколько заголовков H1 ({len(h1)} шт.), размывает релевантность.")
        else:
            strengths.append(f"Один четкий заголовок H1: «{h1[0]}».")

        text_dumps = json.dumps(p0, ensure_ascii=False)
        placeholders = []
        for phrase in ["Замените", "Lorem ipsum", "placeholder", "test", "пример"]:
            if phrase.lower() in text_dumps.lower():
                matches = re.findall(rf"[^.\n]*?{phrase}[^.\n]*", text_dumps, re.IGNORECASE)
                placeholders.extend([m.strip() for m in matches[:2]])

        if placeholders:
            issues.append(f"В коде/тексте найдены остатки разработки/заглушки: «{placeholders[0]}».")

        resp_time = p0.get("response_time_s", 0)
        if resp_time > 1.5:
            issues.append(f"Медленный ответ сервера (TTFB {resp_time} сек).")
        else:
            strengths.append(f"Быстрый сервер (TTFB {resp_time} сек).")

        jsonld = p0.get("jsonld", {})
        if not jsonld.get("types"):
            issues.append("Отсутствует микроразметка Schema.org / JSON-LD (нет Organization, LocalBusiness).")
        else:
            strengths.append(f"Микроразметка Schema.org найдена ({', '.join(jsonld.get('types', []))}).")

    return {
        "issues": issues,
        "strengths": strengths,
        "pages_crawled": len(pages),
    }


def detect_cms(p0: dict, text_dump: str) -> str:
    lower_dump = text_dump.lower()
    if "_next/" in lower_dump or "__next_data__" in lower_dump:
        return "Next.js (React)"
    if "wp-content" in lower_dump or "wp-includes" in lower_dump:
        return "WordPress"
    if "bitrix" in lower_dump:
        return "1С-Битрикс"
    if "tilda" in lower_dump:
        return "Tilda"
    if "modx" in lower_dump:
        return "MODX"
    return "HTML / Чистый код"


def generate_html_report(url: str, client_name: str, analysis: dict, crawl_data: dict, out_html: Path) -> str:
    pages = crawl_data.get("pages", [])
    p0 = pages[0] if pages else {}
    robots = crawl_data.get("robots", {})
    sitemap = crawl_data.get("sitemap", {})
    ttfb = p0.get("response_time_s", 0)
    title = p0.get("title") or ""
    desc = p0.get("description") or ""
    h1_list = p0.get("h1") or []
    h1_text = h1_list[0] if h1_list else ""
    jsonld = p0.get("jsonld", {})
    jsonld_types = ", ".join(jsonld.get("types", [])) if jsonld.get("types") else "нет"

    text_dump = json.dumps(p0, ensure_ascii=False)
    cms = detect_cms(p0, text_dump)

    # Status pills
    robots_badge = '<span class="badge-status badge-success">🟢 Настроен</span>' if robots.get("exists") else '<span class="badge-status badge-danger">🔴 Отсутствует</span>'
    sitemap_badge = f'<span class="badge-status badge-success">🟢 Найдена ({sitemap.get("url_count", 0)} URL)</span>' if sitemap.get("found") else '<span class="badge-status badge-danger">🔴 Не найдена</span>'
    
    if not title:
        title_badge = '<span class="badge-status badge-danger">🔴 Отсутствует</span>'
    elif len(title) > 80:
        title_badge = f'<span class="badge-status badge-warning">🟠 Слишком длинный ({len(title)} симв.)</span>'
    else:
        title_badge = f'<span class="badge-status badge-success">🟢 Корректный ({len(title)} симв.)</span>'

    desc_badge = f'<span class="badge-status badge-success">🟢 Заполнен ({len(desc)} симв.)</span>' if desc else '<span class="badge-status badge-danger">🔴 Отсутствует</span>'

    if not h1_text:
        h1_badge = '<span class="badge-status badge-danger">🔴 Отсутствует</span>'
    elif len(h1_list) > 1:
        h1_badge = f'<span class="badge-status badge-warning">🟠 Несколько ({len(h1_list)} шт.)</span>'
    else:
        h1_badge = '<span class="badge-status badge-success">🟢 1 заголовок</span>'

    schema_badge = f'<span class="badge-status badge-success">🟢 {jsonld_types}</span>' if jsonld.get("types") else '<span class="badge-status badge-danger">🔴 Отсутствует</span>'

    # Placeholders
    placeholders = []
    for phrase in ["Замените", "Lorem ipsum", "placeholder", "test", "пример"]:
        if phrase.lower() in text_dump.lower():
            matches = re.findall(rf"[^.\n]*?{phrase}[^.\n]*", text_dump, re.IGNORECASE)
            placeholders.extend([m.strip() for m in matches[:2]])

    placeholders_badge = f'<span class="badge-status badge-danger">🔴 Найдено в коде ({len(placeholders)} шт.)</span>' if placeholders else '<span class="badge-status badge-success">🟢 Чисто</span>'

    ttfb_badge = '<span class="badge-status badge-success">🟢 Быстрый</span>' if ttfb < 0.6 else ('<span class="badge-status badge-warning">🟠 Средний</span>' if ttfb < 1.5 else '<span class="badge-status badge-danger">🔴 Медленный</span>')

    # Metric boxes
    server_color = "green" if ttfb < 0.6 else ("orange" if ttfb < 1.5 else "red")
    indexing_color = "green" if (robots.get("exists") and sitemap.get("found")) else "red"
    indexing_text = "В норме" if (robots.get("exists") and sitemap.get("found")) else "Ошибки"
    meta_color = "green" if (title and desc) else "red"
    meta_text = "Заполнены" if (title and desc) else "Требуют правок"

    # Issue blocks
    issue_cards = []
    for iss in analysis["issues"]:
        issue_cards.append(f"""
            <div class="issue-box">
                <h4 style="color: var(--accent-danger);">⚠️ Точка потери клиентов / Дефект:</h4>
                <p>{iss}</p>
            </div>
        """)
    issues_html = "\n".join(issue_cards)

    now_str = datetime.now().strftime('%d.%m.%Y %H:%M')

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="noindex, nofollow">
    <title>FastUp.by | Экспресс SEO & Технический Аудит — {url}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Outfit:wght@600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-page: #f8fafc;
            --bg-card: #ffffff;
            --bg-card-hover: #f1f5f9;
            --accent-primary: #2563eb;
            --accent-gradient: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
            --accent-success: #10b981;
            --accent-warning: #d97706;
            --accent-danger: #ef4444;
            --text-main: #0f172a;
            --text-muted: #475569;
            --border-color: #e2e8f0;
            --radius-lg: 16px;
            --radius-md: 12px;
            --shadow: 0 10px 30px -10px rgba(15, 23, 42, 0.06);
            --badge-bg: rgba(37, 99, 235, 0.08);
            --badge-border: rgba(37, 99, 235, 0.2);
            --badge-text: #1d4ed8;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-page);
            color: var(--text-main);
            line-height: 1.6;
            padding-bottom: 60px;
        }}

        .container {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 0 24px;
        }}

        .top-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 24px 0;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 36px;
        }}

        .brand-logo {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.4rem;
            font-weight: 800;
            color: var(--text-main);
            text-decoration: none;
        }}

        .brand-logo span {{
            color: var(--accent-primary);
        }}

        .tag-badge {{
            background: var(--badge-bg);
            border: 1px solid var(--badge-border);
            color: var(--badge-text);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 700;
        }}

        .hero {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 36px;
            margin-bottom: 32px;
            box-shadow: var(--shadow);
        }}

        .hero h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 2rem;
            font-weight: 800;
            margin-bottom: 8px;
            color: var(--text-main);
        }}

        .hero-subtitle {{
            font-size: 1.05rem;
            color: var(--text-muted);
        }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}

        .metric-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            padding: 20px;
            text-align: center;
            box-shadow: var(--shadow);
        }}

        .metric-value {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.8rem;
            font-weight: 800;
            margin-bottom: 4px;
        }}

        .metric-value.red {{ color: var(--accent-danger); }}
        .metric-value.orange {{ color: var(--accent-warning); }}
        .metric-value.green {{ color: var(--accent-success); }}
        .metric-value.blue {{ color: var(--accent-primary); }}

        .metric-label {{
            font-size: 0.85rem;
            color: var(--text-muted);
            font-weight: 600;
        }}

        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 32px;
            box-shadow: var(--shadow);
            margin-bottom: 32px;
        }}

        .section-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.35rem;
            font-weight: 800;
            margin-bottom: 20px;
            color: var(--text-main);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }}

        th, td {{
            padding: 14px 20px;
            border-bottom: 1px solid var(--border-color);
            font-size: 0.9rem;
        }}

        th {{
            background: var(--bg-page);
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        .badge-status {{
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.82rem;
            font-weight: 700;
        }}

        .badge-success {{ background: rgba(16, 185, 129, 0.12); color: #059669; }}
        .badge-danger {{ background: rgba(239, 68, 68, 0.12); color: #dc2626; }}
        .badge-warning {{ background: rgba(217, 119, 6, 0.12); color: #d97706; }}
        .badge-info {{ background: rgba(37, 99, 235, 0.12); color: #2563eb; }}

        .issue-box {{
            background: var(--bg-page);
            border-left: 4px solid var(--accent-danger);
            padding: 18px 20px;
            border-radius: var(--radius-md);
            margin-bottom: 14px;
        }}

        .issue-box h4 {{
            font-size: 0.98rem;
            margin-bottom: 4px;
        }}

        .issue-box p {{
            font-size: 0.92rem;
            color: var(--text-muted);
        }}

        .solution-box {{
            background: rgba(37, 99, 235, 0.04);
            border: 1px solid var(--badge-border);
            padding: 24px;
            border-radius: var(--radius-md);
        }}

        .solution-box h4 {{
            font-size: 1.15rem;
            color: var(--accent-primary);
            margin-bottom: 10px;
        }}

        .solution-box ul {{
            padding-left: 20px;
            margin-bottom: 16px;
        }}

        .solution-box li {{
            margin-bottom: 8px;
            font-size: 0.95rem;
        }}

        .cta-btn {{
            display: inline-block;
            background: var(--accent-gradient);
            color: #ffffff;
            font-weight: 700;
            padding: 12px 28px;
            border-radius: 8px;
            text-decoration: none;
            box-shadow: 0 4px 14px rgba(37, 99, 235, 0.3);
            transition: opacity 0.2s;
        }}

        .cta-btn:hover {{
            opacity: 0.9;
        }}

        .footer {{
            text-align: center;
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-top: 40px;
        }}
    </style>
</head>
<body>

    <div class="container">
        <!-- Top Bar -->
        <div class="top-bar">
            <a href="https://fastup.by" class="brand-logo">FastUp<span>.by</span></a>
            <div class="tag-badge">Экспресс-Аудит</div>
        </div>

        <!-- Hero Header -->
        <div class="hero">
            <h1>Экспресс-Аудит сайта: {url}</h1>
            <p class="hero-subtitle">Подготовлено для: <b>{client_name}</b> | Дата проверки: {now_str}</p>
        </div>

        <!-- Metrics Grid -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value blue">{cms}</div>
                <div class="metric-label">Движок / Архитектура</div>
            </div>
            <div class="metric-card">
                <div class="metric-value {server_color}">{ttfb} сек</div>
                <div class="metric-label">Время отклика сервера (TTFB)</div>
            </div>
            <div class="metric-card">
                <div class="metric-value {indexing_color}">{indexing_text}</div>
                <div class="metric-label">Индексация роботами</div>
            </div>
            <div class="metric-card">
                <div class="metric-value {meta_color}">{meta_text}</div>
                <div class="metric-label">Мета-теги и поисковый сниппет</div>
            </div>
        </div>

        <!-- Detailed Breakdown -->
        <div class="card">
            <h2 class="section-title">📊 Сводный чек-лист поисковой готовности</h2>
            <table>
                <thead>
                    <tr>
                        <th>Элемент аудита</th>
                        <th>Фактическое состояние</th>
                        <th>Статус</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Файл robots.txt</strong></td>
                        <td>Инструкции для поисковых ботов (Яндекс, Google)</td>
                        <td>{robots_badge}</td>
                    </tr>
                    <tr>
                        <td><strong>Карта сайта sitemap.xml</strong></td>
                        <td>Индекс всех доступных страниц сайта</td>
                        <td>{sitemap_badge}</td>
                    </tr>
                    <tr>
                        <td><strong>Тег Title (Главная)</strong></td>
                        <td>{title or "Не указан"}</td>
                        <td>{title_badge}</td>
                    </tr>
                    <tr>
                        <td><strong>Тег Meta Description</strong></td>
                        <td>{desc or "Не заполнен (сниппет формируется случайным куском текста)"}</td>
                        <td>{desc_badge}</td>
                    </tr>
                    <tr>
                        <td><strong>Заголовок H1</strong></td>
                        <td>{h1_text or "Отсутствует"}</td>
                        <td>{h1_badge}</td>
                    </tr>
                    <tr>
                        <td><strong>Микроразметка Schema.org</strong></td>
                        <td>Структурированные данные для поисковиков и ИИ</td>
                        <td>{schema_badge}</td>
                    </tr>
                    <tr>
                        <td><strong>Остатки разработки / Заглушки в коде</strong></td>
                        <td>Проверка на наличие не удаленных технических фраз</td>
                        <td>{placeholders_badge}</td>
                    </tr>
                    <tr>
                        <td><strong>Скорость отклика сервера</strong></td>
                        <td>Время первого байта (TTFB): {ttfb} сек</td>
                        <td>{ttfb_badge}</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- Key Findings Section -->
        <div class="card">
            <h2 class="section-title">💡 Выявленные дефекты и точки потери заявок</h2>
            {issues_html}
        </div>

        <!-- Recommended Solutions -->
        <div class="card">
            <h2 class="section-title">🛠️ Рекомендуемый план работ от FastUp Studio</h2>
            <div class="solution-box">
                <h4>Комплексное устранение дефектов и запуск потока клиентов:</h4>
                <ul>
                    <li><b>1. Технический ремонт сайта (1–2 дня):</b> чистка артефактов в коде, настройка robots.txt и sitemap.xml, создание продающих мета-описаний под услуги, внедрение разметки Schema.org/LocalBusiness. <i>Ориентир: от 450–600 BYN.</i></li>
                    <li><b>2. Настройка контекстной рекламы в Яндекс.Директ:</b> сбор коммерческих запросов по региону, отсечение нецелевого трафика минус-словами, запуск рекламной кампании с контролем стоимости заявки. <i>Ориентир: от 700 BYN.</i></li>
                </ul>
                <a href="https://fastup.by" class="cta-btn">Обсудить запуск с FastUp Studio</a>
            </div>
        </div>

        <div class="footer">
            FastUp Studio © 2026. Маркетинг и разработка для бизнеса в Беларуси. Контакты: +375 (29) 168-23-89 | info@fastup.by
        </div>

    </div>

</body>
</html>
"""
    out_html.write_text(html, encoding="utf-8")
    return html


def generate_report(url: str, client_name: str, analysis: dict, out_md: Path) -> str:
    issues_md = "\n".join([f"- ❌ {i}" for i in analysis["issues"]])
    strengths_md = "\n".join([f"- ✅ {s}" for s in analysis["strengths"]])

    content = f"""# Экспресс-аудит сайта: {url}
**Клиент:** {client_name}  
**Дата аудита:** {datetime.now().strftime('%d.%m.%Y %H:%M')}  
**Подготовлено:** FastUp Studio (автоматический сбор + анализ)

---

## 📌 Ключевые выводы для переговоров

### Выявленные проблемы и точки роста (для КП):
{issues_md}

### Сильные стороны сайта:
{strengths_md}

---

## 💼 Рекомендуемый пакет услуг FastUp Studio

1. **Техническое исправление сайта (разово):**
   - Устранение артефактов и забытых заглушек разработчиков.
   - Настройка корректного robots.txt и автогенерации sitemap.xml.
   - Прописывание продающих Title и Meta Description под ключевые услуги.
   - Внедрение микроразметки Schema.org/LocalBusiness для доверия поисковиков.
   *Ориентир по цене: от 450–600 BYN (1–2 дня работы).*

2. **Маркетинг и реклама:**
   - Настройка контекстной рекламы в Яндекс.Директ на целевую аудиторию региона.
   - Базовая SEO/GEO-оптимизация под локальные запросы.
   *Ориентир по цене: от 700 BYN.*
"""
    out_md.write_text(content, encoding="utf-8")
    return content


def generate_sales_brief(url: str, client_name: str, analysis: dict, crawl_data: dict) -> tuple:
    """Генерирует лаконичный коммерческий крючок (1 предложение) и готовые офферы с ценами «от N BYN»."""
    pages = crawl_data.get("pages", [])
    p0 = pages[0] if pages else {}
    title = p0.get("title") or ""
    desc = p0.get("description") or ""
    ttfb = p0.get("response_time_s", 0)
    robots = crawl_data.get("robots", {})
    sitemap = crawl_data.get("sitemap", {})
    broken_links = analysis.get("broken_links", [])

    # 1. Крючок для разговора: ровно 1 ёмкое предложение (суть потери клиентов/денег)
    if broken_links:
        hook = f"На сайте {len(broken_links)} битых ссылок — клиенты натыкаются на ошибки 404 и уходят."
    elif not title or not desc:
        hook = "В поиске случайный обрывок текста вместо описания — клиенты кликают на конкурентов."
    elif ttfb > 1.5:
        hook = f"Сайт грузится {ttfb:.1f} сек — мобильные клиенты закрывают страницу, не дождавшись каталога."
    elif not robots.get("exists") or not sitemap.get("found"):
        hook = "Поисковики не видят новые страницы и каталог — сайт теряет клиентов из органики."
    else:
        hook = "Ошибки в разметке мешают сайту подняться в топ и привлекать клиентов без рекламы."

    # 2. Готовые пакеты услуг для менеджера (всегда «от N BYN», 1 строка на оффер)
    offers_tg = (
        "• <b>SEO и сниппет (от 450 BYN, 2 дня):</b> продающий вид в поиске и на картах.\n"
        "• <b>Яндекс.Директ (от 700 BYN):</b> горячие заявки с поиска уже на этой неделе.\n"
        "• <b>Комплекс (SEO + Директ):</b> от 1 100 BYN."
    )

    offers_plain = (
        "• SEO и сниппет (от 450 BYN, 2 дня): продающий вид в поиске и на картах.\n"
        "• Яндекс.Директ (от 700 BYN): горячие заявки с поиска уже на этой неделе.\n"
        "• Комплекс (SEO + Директ): от 1 100 BYN."
    )

    return hook, offers_tg, offers_plain


def run_crm_and_tg(url: str, client_name: str, lead_id: int, analysis: dict, crawl_data: dict, report_path: Path, public_url: str = "", existing_task_id: int = 0):
    sales_hook, offers_tg, offers_plain = generate_sales_brief(url, client_name, analysis, crawl_data)

    deadline_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    task_title = f"Презентовать аудит и предложить решение: {client_name} ({url})"
    task_desc = f"Готов аудит: {public_url}\n\n" if public_url else "Готов отчёт аудита.\n\n"
    task_desc += f"💡 Боль: {sales_hook}\n\n"
    task_desc += f"💼 Что предложить:\n{offers_plain}"

    # Проверяем, есть ли уже привязанный проект у клиента (если клиент уже в производстве)
    project_id = 0
    if lead_id:
        try:
            p_check = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "tools.py"),
                    "crm_sql_query",
                    "db=wp",
                    f'query=SELECT p.ID FROM wp_posts p JOIN wp_postmeta m ON p.ID=m.post_id AND m.meta_key="_tm_project_client_id" WHERE p.post_type="crm_tm_project" AND m.meta_value="{lead_id}" LIMIT 1',
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            data = json.loads(p_check.stdout)
            rows = data.get("rows", [])
            if rows:
                project_id = int(rows[0]["ID"])
        except Exception:
            pass

    task_id = 0
    try:
        if existing_task_id:
            update_cmd = [
                sys.executable,
                str(ROOT / "scripts" / "tools.py"),
                "crm_update_task",
                f"id={existing_task_id}",
                f"title={task_title}",
                f"description={task_desc}",
                "assignee_id=7",
                "status=todo",
                "priority=high",
                f"deadline={deadline_date}",
                "notify=false",
            ]
            if project_id:
                update_cmd.append(f"project_id={project_id}")
            subprocess.run(
                update_cmd,
                check=False,
                capture_output=True,
            )
            print(f"✅ Задача CRM #{existing_task_id} обновлена актуальными офферами")
        else:
            create_cmd = [
                sys.executable,
                str(ROOT / "scripts" / "tools.py"),
                "crm_create_task",
                f"title={task_title}",
                f"description={task_desc}",
                f"client_id={lead_id}",
                "assignee_id=7",
                "status=todo",
                "priority=high",
                f"deadline={deadline_date}",
                "notify=false",
                "source=ai",
            ]
            if project_id:
                create_cmd.append(f"project_id={project_id}")
            p = subprocess.run(
                create_cmd,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            try:
                task_res = json.loads(p.stdout)
                if task_res.get("id"):
                    task_id = int(task_res["id"])
                    print(f"✅ Создана задача CRM #{task_id}")
            except Exception:
                pass
    except Exception as e:
        print(f"CRM task error: {e}")

    target_tid = existing_task_id or task_id
    task_link = f"https://admin.microapps.by/wp-admin/admin.php?page=microapps-crm#tasks/task/{target_tid}" if target_tid else ""
    client_link = f"https://admin.microapps.by/wp-admin/admin.php?page=microapps-crm-client&amp;id={lead_id}" if lead_id else ""

    if target_tid:
        header_title = f"🎯 <a href=\"{task_link}\"><b>Задача #{target_tid}: Презентовать аудит и предложить решение</b></a>"
    else:
        header_title = "🎯 <b>Новая задача: Презентовать аудит и предложить решение</b>"

    client_line = f"👤 <b>Клиент:</b> <a href=\"{client_link}\">{client_name}</a>" if client_link else f"👤 <b>Клиент:</b> {client_name}"
    link_line = f"🔗 <b>Страница аудита для клиента:</b>\n👉 <a href=\"{public_url}\">{public_url}</a>\n\n" if public_url else ""

    tg_text = (
        f"{header_title}\n\n"
        f"{client_line}\n"
        f"🌐 <b>Сайт:</b> {url}\n"
        f"👤 <b>Ответственный:</b> Евгений (дедлайн: {deadline_date})\n\n"
        f"{link_line}"
        f"💡 <b>Боль:</b> {sales_hook}\n\n"
        f"💼 <b>Что предложить:</b>\n{offers_tg}"
    )

    try:
        tg_cmd = [
            sys.executable,
            str(ROOT / "scripts" / "tg_agent.py"),
            "send",
            tg_text,
            "--topic",
            "tasks",
        ]
        target_tid = existing_task_id or task_id
        if target_tid:
            tg_cmd.extend(["--task-id", str(target_tid), "--deadline", str(deadline_date)])
        p_tg = subprocess.run(
            tg_cmd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if p_tg.stdout:
            print(p_tg.stdout.strip())
        if p_tg.stderr:
            print(f"TG error output: {p_tg.stderr.strip()}")
    except Exception as e:
        print(f"TG notification error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Сквозной аудит сайта клиента")
    parser.add_argument("--url", required=True, help="URL сайта для аудита")
    parser.add_argument("--lead-id", type=int, default=0, help="ID лида в CRM")
    parser.add_argument("--client-name", default="", help="Название компании/клиента")
    parser.add_argument("--existing-task-id", type=int, default=0, help="ID существующей задачи в CRM для обновления")
    args = parser.parse_args()

    slug = get_slug(args.url)
    client_dir = CLIENTS_DIR / slug
    client_dir.mkdir(parents=True, exist_ok=True)

    crawl_json = client_dir / "crawl.json"
    report_md = client_dir / "audit.md"
    report_html = client_dir / "index.html"

    client_name = args.client_name or slug

    print(f"=== ЗАПУСК СКВОЗНОГО АУДИТА: {args.url} ===")
    print(f"Папка клиента: {client_dir}")

    print("\n[1/5] Сбор данных сайта краулером...")
    crawl_data = run_crawl(args.url, crawl_json)

    print("\n[2/5] Анализ дефектов и структуры...")
    analysis = analyze_crawl(crawl_data)

    print("\n[3/5] Генерация отчётов аудита (Markdown и HTML)...")
    generate_report(args.url, client_name, analysis, report_md)
    generate_html_report(args.url, client_name, analysis, crawl_data, report_html)
    print(f"Markdown отчёт сохранён: {report_md}")
    print(f"HTML отчёт сохранён: {report_html}")

    print("\n[4/5] Деплой HTML-страницы на fastup.by/tz/<slug>/...")
    public_url = f"https://fastup.by/tz/{slug}/"
    try:
        from deploy_static_file import deploy_file
        remote_name = f"tz/{slug}/index.html"
        deploy_file(report_html, site="fastup.by", remote_name=remote_name, backup=False)
        print(f"✅ Страница аудита опубликована: {public_url}")
    except Exception as e:
        print(f"⚠️ Предупреждение деплоя HTML: {e}")

    print("\n[5/5] Синхронизация с CRM и Telegram...")
    run_crm_and_tg(args.url, client_name, args.lead_id, analysis, crawl_data, report_md, public_url=public_url, existing_task_id=args.existing_task_id)

    print("\n=== АУДИТ УСПЕШНО ЗАВЕРШЁН ===")
    print(f"Публичный URL: {public_url}")
    print(f"Найдено дефектов: {len(analysis['issues'])}")
    for iss in analysis["issues"]:
        print(f"  {iss}")


if __name__ == "__main__":
    main()
