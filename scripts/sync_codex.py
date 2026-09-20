#!/usr/bin/env python3
"""Подготовить конфиги Codex из `.claude/` — единственного источника правды.

Codex и Claude Code читают одно и то же из разных мест, но по-разному:

| Что | Claude Code | Codex | Как связано |
|---|---|---|---|
| Скиллы | `.claude/skills/<имя>/` | `.agents/skills/<имя>/` | junction, копии нет |
| Субагенты | `.claude/agents/<имя>.md` | `.codex/agents/<имя>.toml` | генерация, форматы разные |

**Скиллы копировать не нужно.** `.agents/skills` — это junction (символическая ссылка на
каталог) на `.claude/skills`: Codex такие ссылки проходит, правка в `.claude/` видна ему
сразу, запускать скрипт ради скиллов не надо. Поэтому `.agents/skills` в `.gitignore` —
в git лежит один экземпляр, в `.claude/`.

Указать Codex на скиллы через `[[skills.config]]` в `config.toml` нельзя: проверено
запуском 11.09.2026 — это переопределение уже найденного скилла (`enabled`), а не способ
зарегистрировать новое место поиска. Ни относительный, ни абсолютный путь скилл не
добавляют.

**Субагентов приходится генерировать:** формат честно разный — у Claude Markdown с
YAML-фронтматтером, у Codex TOML с `developer_instructions`. Меняются они редко.

Что делает перенос, кроме путей:

* `tools:` у Codex нет — доступ задаётся `sandbox_mode`. Агент без Write/Edit/Bash
  становится `read-only`, остальные — `workspace-write`
  (https://codex.danielvaughan.com/2026/04/27/codex-cli-custom-agent-definitions-toml-specialised-subagents/).
* `model:` не переносится: имена моделей у Codex свои, без поля агент наследует модель
  родителя — документированное поведение, оно нам подходит.
* Замены — только по трём явным правилам (`REWRITES`). Слово «Claude» само по себе не
  трогаем: в скиллах это имя чужого продукта (ClaudeBot, anthropic-ai, claude-seo), и
  слепая замена на «Codex» уже наврала в таблице ИИ-краулеров.

Проверить, что Codex реально видит скиллы и агентов:
    codex debug prompt-input

Usage:
    python scripts/sync_codex.py            # создать junction и пересобрать агентов
    python scripts/sync_codex.py --check    # только проверить (код 1 — надо пересобрать)
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE_AGENTS = ROOT / '.claude' / 'agents'
CLAUDE_SKILLS = ROOT / '.claude' / 'skills'
CODEX_AGENTS = ROOT / '.codex' / 'agents'
CODEX_SKILLS = ROOT / '.agents' / 'skills'

REWRITES = (
    ('.claude/skills/', '.agents/skills/'),
    ('.claude/agents/', '.codex/agents/'),
    # CLAUDE.md — тонкая обёртка, которая строкой `@AGENTS.md` импортирует настоящий
    # источник. Codex читает AGENTS.md напрямую, ссылка ведёт туда же.
    ('CLAUDE.md', 'AGENTS.md'),
)

WRITE_TOOLS = {'Write', 'Edit', 'Bash', 'NotebookEdit'}


def rewrite(text):
    for old, new in REWRITES:
        text = text.replace(old, new)
    return text


def parse_agent(path):
    """Разобрать `.claude/agents/*.md` на фронтматтер и тело."""
    text = path.read_text(encoding='utf-8')
    match = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n(.*)$', text, re.DOTALL)
    if not match:
        raise SystemExit(f'{path}: нет YAML-фронтматтера, агент не зарегистрируется ни там ни там')
    raw, body = match.groups()

    fields, key = {}, None
    for line in raw.splitlines():
        header = re.match(r'^([a-zA-Z_]+):\s*(.*)$', line)
        if header:
            key, value = header.group(1), header.group(2).strip()
            fields[key] = '' if value in ('>-', '>', '|', '|-') else value
        elif key and line.strip():
            fields[key] = (fields[key] + ' ' + line.strip()).strip()
    return fields, body.strip()


def toml_string(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ') + '"'


def toml_multiline(value):
    body = value.replace('\\', '\\\\').replace('"""', '\\"\\"\\"')
    if body.endswith('"'):
        body += '\\n'
    return '"""\n' + body + '"""'


def build_agent(path):
    fields, body = parse_agent(path)
    name = fields.get('name') or path.stem
    description = fields.get('description', '').strip()
    if not description:
        raise SystemExit(f'{path}: пустой description — Codex не сможет выбрать агента')
    tools = {t.strip() for t in fields.get('tools', '').split(',') if t.strip()}
    # Пустой tools в Claude Code означает «все инструменты», а не «никаких».
    sandbox = 'read-only' if tools and not (tools & WRITE_TOOLS) else 'workspace-write'
    return name, (
        f'name = {toml_string(name)}\n'
        f'description = {toml_string(rewrite(description))}\n'
        f'sandbox_mode = "{sandbox}"\n'
        f'developer_instructions = {toml_multiline(rewrite(body))}\n'
    )


def plan_agents():
    if not CLAUDE_AGENTS.is_dir():
        raise SystemExit('Нет .claude/agents — синхронизировать нечего')
    result = {}
    for source in sorted(CLAUDE_AGENTS.glob('*.md')):
        name, content = build_agent(source)
        result[CODEX_AGENTS / f'{name}.toml'] = content
    return result


def skills_linked():
    """Ссылка ли `.agents/skills` на `.claude/skills` (а не копия и не пусто)."""
    if not CODEX_SKILLS.exists():
        return False
    try:
        return CODEX_SKILLS.resolve() == CLAUDE_SKILLS.resolve()
    except OSError:
        return False


def link_skills():
    """Создать junction (Windows) или симлинк. Не вышло — честно скопировать."""
    if skills_linked():
        return 'ссылка на месте'
    if CODEX_SKILLS.exists():
        shutil.rmtree(CODEX_SKILLS, ignore_errors=True)
    CODEX_SKILLS.parent.mkdir(parents=True, exist_ok=True)
    try:
        if os.name == 'nt':
            # mklink /J не требует прав администратора, в отличие от симлинка.
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(CODEX_SKILLS), str(CLAUDE_SKILLS)],
                           check=True, capture_output=True)
        else:
            os.symlink(CLAUDE_SKILLS, CODEX_SKILLS, target_is_directory=True)
        return 'ссылка создана'
    except (OSError, subprocess.SubprocessError):
        shutil.copytree(CLAUDE_SKILLS, CODEX_SKILLS)
        return ('ССЫЛКА НЕ СОЗДАЛАСЬ, скопировано — копии будут расходиться, '
                'запускать скрипт после каждой правки скиллов')


def current_agents():
    return {p for p in CODEX_AGENTS.rglob('*') if p.is_file()} if CODEX_AGENTS.is_dir() else set()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true',
                        help='не менять файлы, только сказать, что разошлось (код возврата 1)')
    args = parser.parse_args()

    expected = plan_agents()
    stale = [p for p in current_agents() if p not in expected]
    changed = [p for p, value in expected.items()
               if not p.exists() or p.read_text(encoding='utf-8') != value]
    linked = skills_linked()

    if args.check:
        if not linked:
            print('скиллы: .agents/skills не ссылается на .claude/skills')
        for path in sorted(changed):
            print(f'разошлось: {path.relative_to(ROOT)}')
        for path in sorted(stale):
            print(f'лишний файл: {path.relative_to(ROOT)}')
        if changed or stale or not linked:
            print('\nПересобрать: python scripts/sync_codex.py')
            sys.exit(1)
        print(f'Всё на месте: скиллы по ссылке, агентов {len(expected)}')
        return

    print(f'скиллы: {link_skills()}')
    for path in sorted(changed):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected[path], encoding='utf-8')
        print(f'записан: {path.relative_to(ROOT)}')
    for path in sorted(stale):
        path.unlink()
        print(f'удалён лишний: {path.relative_to(ROOT)}')
    if not changed and not stale:
        print('агенты: уже актуальны')
    print('\nИсточник правды — .claude/. Проверить глазами Codex: codex debug prompt-input')


if __name__ == '__main__':
    main()
