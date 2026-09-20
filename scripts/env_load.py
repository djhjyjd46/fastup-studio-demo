#!/usr/bin/env python3
"""Загрузка секретов из .env в переменные окружения процесса.

Скрипты берут ключи из окружения, но окружение сессии не всегда настроено — особенно
в новой сессии или на другой машине. Этот модуль подхватывает `.env` из корня репозитория
и заполняет то, чего в окружении ещё нет (значения из окружения имеют приоритет).

    from env_load import load_env, require
    load_env()
    token = require("YANDEX_DIRECT_TOKEN")

`.env` в `.gitignore` и в репозиторий не попадает. Формат — `KEY=value` построчно,
кавычки вокруг значения снимаются, строки с `#` игнорируются.
"""
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def is_evgeniy_session():
    """Определяет сессию Евгения по git config user.name или FASTUP_USER."""
    if os.environ.get("FASTUP_USER", "").strip().lower() in ("evgeniy", "eugene"):
        return True
    try:
        import subprocess
        res = subprocess.run(
            ["git", "config", "user.name"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        name = (res.stdout or "").strip().lower()
        if "evgeniy" in name or "евгений" in name:
            return True
    except Exception:
        pass
    return False


def env_file_path():
    """Определяет путь к .env файлу с поддержкой партнёрского окружения (env.evgeniy) и worktrees.

    `.env` в `.gitignore`, поэтому в worktree (`.claude/worktrees/<имя>`) его нет: там `.git` —
    файл со ссылкой `gitdir: <основной>/.git/worktrees/<имя>`.
    """
    custom = os.environ.get("ENV_FILE")
    if custom:
        p = Path(custom)
        if not p.is_absolute():
            p = ROOT / p
        if p.exists():
            return p

    repo_root = ROOT
    git = ROOT / ".git"
    if git.is_file():
        gitdir = git.read_text(encoding="utf-8").strip().partition("gitdir:")[2].strip()
        if gitdir:
            main_root = Path(gitdir).resolve().parent.parent.parent
            if main_root.is_dir():
                repo_root = main_root

    evgeniy_candidates = [
        repo_root / "env.evgeniy",
        repo_root / ".env.evgeniy",
        repo_root / "secrets" / "env.evgeniy",
        repo_root / "evgen.env",
    ]

    general_candidates = [
        repo_root / ".env",
    ]

    candidates = evgeniy_candidates + general_candidates if is_evgeniy_session() else general_candidates + evgeniy_candidates

    for cand in candidates:
        if cand.exists():
            return cand

    return repo_root / ".env"


def load_env(path=None):
    """Читает .env и дописывает в os.environ то, чего там ещё нет."""
    env_file = Path(path) if path else env_file_path()
    if not env_file.exists():
        return {}
    loaded = {}
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded


def require(name, hint=""):
    """Значение переменной или понятная ошибка вместо трассировки."""
    load_env()
    value = os.environ.get(name)
    if not value:
        raise SystemExit(
            "нет {} — добавь строку `{}=...` в .env в корне репозитория{}".format(
                name, name, (" (" + hint + ")") if hint else ""))
    return value
