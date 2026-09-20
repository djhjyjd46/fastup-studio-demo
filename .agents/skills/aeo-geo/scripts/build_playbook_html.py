#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""
scripts/build_playbook_html.py

Собирает справочник по GEO в один самодостаточный HTML-файл для чтения с телефона
или ноутбука без редактора markdown.

Источники — существующие файлы репозитория, ничего не дублируется руками:
    playbook/glossary-geo.md        — словарь терминов
    playbook/geo-method.md          — что проверено замером, что гипотеза
    geo/GEO-AUDIT-PIPELINE.md       — регламент аудита и состав продукта

Файл на выходе один, без внешних зависимостей: открывается двойным кликом,
работает офлайн, подстраивается под светлую и тёмную тему системы.

Запуск (после любой правки исходных .md — пересобрать):
    python scripts/build_playbook_html.py
"""


import html
import re
import sys
from pathlib import Path

import markdown

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_HTML = REPO_ROOT / "playbook" / "geo-spravochnik.html"

SECTIONS = [
    ("glossary", "Словарь терминов", REPO_ROOT / "playbook" / "glossary-geo.md"),
    ("method", "Что проверено, что гипотеза", REPO_ROOT / "playbook" / "geo-method.md"),
    ("pipeline", "Регламент аудита", REPO_ROOT / "geo" / "GEO-AUDIT-PIPELINE.md"),
]

FRONTMATTER = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)
# Блоки mermaid оставляем как есть текстом: рендерить их нечем, а выкидывать нельзя —
# в регламенте это описание последовательности фаз.
MERMAID = re.compile(r"```(?:mermaid|gantt|flowchart)\n(.*?)```", re.DOTALL)

CSS = """
:root {
  --bg: #ffffff; --fg: #1a1a1a; --muted: #666666; --line: #e2e2e2;
  --accent: #1f5fd8; --card: #f7f7f8; --code-bg: #f0f0f2; --th: #efeff1;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #16171a; --fg: #e8e8ea; --muted: #9a9aa2; --line: #2e2f34;
    --accent: #7aa7ff; --card: #1e1f24; --code-bg: #24262b; --th: #24262b;
  }
}
:root[data-theme="dark"] {
  --bg: #16171a; --fg: #e8e8ea; --muted: #9a9aa2; --line: #2e2f34;
  --accent: #7aa7ff; --card: #1e1f24; --code-bg: #24262b; --th: #24262b;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.65 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  -webkit-text-size-adjust: 100%;
}
.wrap { max-width: 900px; margin: 0 auto; padding: 24px 18px 96px; }
header { border-bottom: 1px solid var(--line); padding-bottom: 16px; margin-bottom: 8px; }
h1 { font-size: 1.6rem; margin: 0 0 6px; letter-spacing: -0.01em; }
.sub { color: var(--muted); font-size: 0.9rem; }
nav { position: sticky; top: 0; background: var(--bg); padding: 12px 0;
      border-bottom: 1px solid var(--line); margin-bottom: 28px; z-index: 5; }
nav a { display: inline-block; margin-right: 16px; color: var(--accent);
        text-decoration: none; font-size: 0.9rem; font-weight: 600; }
nav a:hover { text-decoration: underline; }
h2 { font-size: 1.3rem; margin: 40px 0 10px; padding-top: 8px; letter-spacing: -0.01em; }
h3 { font-size: 1.08rem; margin: 28px 0 8px; }
h4 { font-size: 0.98rem; margin: 20px 0 6px; color: var(--muted); }
section > h2:first-child {
  border-top: 3px solid var(--accent); padding-top: 22px; margin-top: 52px;
}
p, li { overflow-wrap: break-word; }
ul, ol { padding-left: 22px; }
li { margin: 4px 0; }
code { background: var(--code-bg); padding: 1px 5px; border-radius: 4px;
       font: 0.86em/1.5 ui-monospace, "SF Mono", Consolas, monospace; }
pre { background: var(--card); border: 1px solid var(--line); border-radius: 8px;
      padding: 12px 14px; overflow-x: auto; }
pre code { background: none; padding: 0; }
blockquote { margin: 16px 0; padding: 10px 16px; border-left: 3px solid var(--accent);
             background: var(--card); border-radius: 0 8px 8px 0; color: var(--fg); }
blockquote p { margin: 6px 0; }
.tablewrap { overflow-x: auto; margin: 16px 0; -webkit-overflow-scrolling: touch; }
table { border-collapse: collapse; width: 100%; font-size: 0.9rem; min-width: 520px; }
th, td { border: 1px solid var(--line); padding: 8px 10px; text-align: left;
         vertical-align: top; }
th { background: var(--th); font-weight: 600; }
hr { border: none; border-top: 1px solid var(--line); margin: 32px 0; }
a { color: var(--accent); }
.note { color: var(--muted); font-size: 0.85rem; margin-top: 56px;
        border-top: 1px solid var(--line); padding-top: 14px; }
@media print {
  nav { display: none; }
  body { font-size: 11pt; }
  section > h2:first-child { page-break-before: always; }
  a { color: inherit; text-decoration: none; }
}
"""


def render_markdown(path: Path) -> str:
    text = FRONTMATTER.sub("", path.read_text(encoding="utf-8"))
    text = MERMAID.sub(
        lambda m: "```\n" + m.group(1).strip() + "\n```", text
    )
    body = markdown.markdown(
        text, extensions=["tables", "fenced_code", "sane_lists", "attr_list"]
    )
    # Таблицы широкие, на телефоне должны скроллиться сами, а не растягивать страницу.
    return body.replace("<table>", '<div class="tablewrap"><table>').replace(
        "</table>", "</table></div>"
    )


def main() -> int:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    missing = [p for _, _, p in SECTIONS if not p.exists()]
    if missing:
        print("[STOP] Нет исходных файлов: " + ", ".join(str(p) for p in missing))
        return 1

    nav = " ".join(
        f'<a href="#{slug}">{html.escape(title)}</a>' for slug, title, _ in SECTIONS
    )
    parts = []
    for slug, title, path in SECTIONS:
        print(f"  -> {path.relative_to(REPO_ROOT)}")
        parts.append(
            f'<section id="{slug}">\n<h2>{html.escape(title)}</h2>\n'
            f"{render_markdown(path)}\n</section>"
        )

    doc = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GEO: справочник FastUp</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>GEO: справочник FastUp</h1>
  <div class="sub">Термины, что проверено замерами, регламент аудита. Внутренний документ.</div>
</header>
<nav>{nav}</nav>
<blockquote>
  <p><strong>Как читать пометки.</strong> В справочнике намеренно разделено то, что стоит на
  отраслевой документации, и то, что держится на наших собственных гипотезах. Гипотезу нельзя
  защищать как факт: спросят на первом же созвоне.</p>
  <p><strong>У терминов:</strong>
  🌍 общепринятый (своим не называть) ·
  💬 отраслевой жаргон (единого определения нет) ·
  🏷 наш собственный (вводить со словами «мы это называем»).</p>
  <p><strong>У утверждений и работ:</strong>
  🟢 устоявшаяся практика ·
  🟡 наша гипотеза, применяем, строго не доказана ·
  🔴 опровергнуто нашим же замером ·
  <strong>[ПОДТВЕРЖДЕНО]</strong> есть замер до/после ·
  <strong>[ГИПОТЕЗА]</strong> ·
  <strong>[ОПРОВЕРГНУТО]</strong> ·
  <strong>[МИФ]</strong> рыночное заблуждение.</p>
  <p>Раздел «Регламент аудита» начинается со списка того, что в нём практика, что гипотеза и
  каких блоков в нём нет вообще.</p>
</blockquote>
{"".join(parts)}
<p class="note">
  Собрано скриптом <code>scripts/build_playbook_html.py</code> из файлов репозитория
  <code>fastup-mentor</code>. Править нужно исходные <code>.md</code> и пересобирать,
  а не этот файл. Печать в PDF: Ctrl+P, каждый раздел начинается с новой страницы.
</p>
</div>
</body>
</html>
"""
    OUT_HTML.write_text(doc, encoding="utf-8")
    size_kb = OUT_HTML.stat().st_size / 1024
    print(f"[OK] {OUT_HTML.relative_to(REPO_ROOT)} ({size_kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
