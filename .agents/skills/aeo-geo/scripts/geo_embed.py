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
scripts/geo_embed.py

Общий слой для всех векторных замеров GEO: эмбеддинги через LM Studio, косинус,
чанкование страниц и оценка страницы против интента.

Заменяет копипасту get_embedding/cosine_sim/chunk_text, которая расползлась по
десятку скриптов в scripts/ и уже начала расходиться в деталях.

Принципы, которые здесь зашиты жёстко:

1. Fail fast. Если LM Studio недоступна — скрипт падает с понятной ошибкой,
   а не пишет 0.0 в отчёт. Ноль в отчёте должен означать «померили и низко»,
   а не «замер не состоялся».
2. Отсутствие страницы != нулевая релевантность. score_page() возвращает статус
   ('ok' / 'missing' / 'thin'), и вызывающий сам решает, как это показать.
   Молча приравнивать «страницы нет» к 0.000 нельзя — это искажает средние.
3. Оценка страницы — среднее топ-3 чанков, не максимум одного. Максимум
   награждает одиночный keyword-stuffed абзац и не отражает страницу целиком.
4. Пути относительно корня репозитория, без 'G:\\fastup-mentor'.

Известное ограничение: замер симметричный — запрос и текст страницы кодируются
одинаково, без instruct-префикса для query-стороны, который поддерживает
Qwen3-Embedding. Абсолютные значения косинуса из-за этого ниже возможных;
сравнение страниц между собой корректно, так как условия для всех одинаковы.
"""

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

LM_STUDIO_BASE = os.environ.get("LM_STUDIO_BASE", "http://127.0.0.1:1234/v1")
EMBED_URL = f"{LM_STUDIO_BASE}/embeddings"
MODELS_URL = f"{LM_STUDIO_BASE}/models"
MODEL_NAME = os.environ.get("GEO_EMBED_MODEL", "text-embedding-qwen3-embedding-8b")

CACHE_DIR = REPO_ROOT / "scripts" / ".embed_cache"

# Минимальный объём страницы, ниже которого замер считается недостоверным:
# такие файлы — это, как правило, неудавшийся краулинг (получили меню и футер),
# а не короткая страница. Ставить им реальный балл нельзя.
MIN_PAGE_WORDS = 100

_MEM_CACHE: dict[str, list[float]] = {}


class LMStudioUnavailable(RuntimeError):
    """LM Studio не отвечает или не отдаёт нужную модель."""


def setup_console() -> None:
    """UTF-8 в консоли Windows, иначе кириллица в выводе рушит скрипт."""
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def require_lm_studio() -> None:
    """Проверить доступность LM Studio и модели ДО начала долгого замера.

    Вызывать первой строкой в main() любого замера: лучше упасть на первой
    секунде, чем через десять минут обнаружить отчёт из нулей.
    """
    try:
        with urllib.request.urlopen(MODELS_URL, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 — наверх уходит понятная ошибка
        raise LMStudioUnavailable(
            f"LM Studio недоступна по {MODELS_URL} ({exc}).\n"
            "Запусти LM Studio, включи локальный сервер и загрузи модель "
            f"'{MODEL_NAME}'. Замер без неё выполнять нельзя."
        ) from exc

    available = [m.get("id") for m in data.get("data", [])]
    if MODEL_NAME not in available:
        raise LMStudioUnavailable(
            f"Модель '{MODEL_NAME}' не загружена в LM Studio.\n"
            f"Доступны: {', '.join(available) or '(ничего)'}\n"
            "Загрузи нужную модель или задай другую через GEO_EMBED_MODEL."
        )


def _cache_path(text: str) -> Path:
    key = hashlib.sha256(f"{MODEL_NAME}\x00{text}".encode("utf-8")).hexdigest()
    return CACHE_DIR / key[:2] / f"{key}.json"


def get_embedding(text: str) -> list[float]:
    """Вектор текста. Кэшируется на диск — повторный прогон почти бесплатный.

    При недоступности LM Studio поднимает LMStudioUnavailable, а не возвращает
    None: молчаливый None превращался в 0.0 в отчётах.
    """
    payload_text = text.strip()
    if not payload_text:
        raise ValueError("get_embedding: пустой текст")

    if payload_text in _MEM_CACHE:
        return _MEM_CACHE[payload_text]

    cache_file = _cache_path(payload_text)
    if cache_file.exists():
        try:
            emb = json.loads(cache_file.read_text(encoding="utf-8"))
            _MEM_CACHE[payload_text] = emb
            return emb
        except (json.JSONDecodeError, OSError):
            cache_file.unlink(missing_ok=True)

    body = json.dumps({"model": MODEL_NAME, "input": payload_text}).encode("utf-8")
    req = urllib.request.Request(
        EMBED_URL, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            emb = json.loads(resp.read().decode("utf-8"))["data"][0]["embedding"]
    except Exception as exc:  # noqa: BLE001
        raise LMStudioUnavailable(
            f"Ошибка эмбеддинга через {EMBED_URL}: {exc}"
        ) from exc

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(emb), encoding="utf-8")
    _MEM_CACHE[payload_text] = emb
    return emb


def cosine_sim(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = sum(a * a for a in v1) ** 0.5
    n2 = sum(b * b for b in v2) ** 0.5
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


_FRONTMATTER = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)


def read_page_text(path: Path) -> str:
    """Текст страницы без YAML-фронтматтера.

    Фронтматтер (url, competitor, h1) содержит имя конкурента и служебные поля —
    в вектор страницы они попадать не должны.
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    return _FRONTMATTER.sub("", raw).strip()


def page_frontmatter(path: Path) -> dict[str, str]:
    """Плоский разбор фронтматтера: 'key: "value"' -> {key: value}.

    Нужен, чтобы брать человеческое имя конкурента из файла, а не из имени
    папки: часть папок создалась с потерянной кириллицей ('_______________').
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    match = _FRONTMATTER.match(raw)
    if not match:
        return {}
    out: dict[str, str] = {}
    for line in match.group(0).splitlines():
        if ":" not in line or line.strip() in {"---", ""}:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def chunk_text(
    text: str, chunk_size: int = 70, overlap: int = 15, min_words: int = 15
) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    step = chunk_size - overlap
    for i in range(0, len(words), step):
        piece = words[i : i + chunk_size]
        if len(piece) >= min_words:
            chunks.append(" ".join(piece))
    return chunks


def score_page(
    path: Path, intent_emb: list[float], top_k: int = 3, max_chunks: int | None = None
) -> tuple[float | None, str]:
    """Оценка страницы против интента.

    Возвращает (score, status):
      * ('ok')      — score = среднее топ-k косинусов по чанкам страницы;
      * ('missing') — файла нет, score = None (страницы у конкурента нет);
      * ('thin')    — страница короче MIN_PAGE_WORDS, score = None
                      (почти всегда неудавшийся краулинг, а не короткая страница).

    None вместо 0.0 — сознательно: вызывающий обязан решить, показывать прочерк
    или считать это провалом покрытия, и не может смешать это со реальным нулём.
    По умолчанию читается вся страница целиком; max_chunks оставлен для отладки,
    в отчётах его задавать не нужно — обрезка режет длинные страницы конкурентов
    и завышает наши компактные черновики.
    """
    if not path.exists():
        return None, "missing"

    text = read_page_text(path)
    if len(text.split()) < MIN_PAGE_WORDS:
        return None, "thin"

    chunks = chunk_text(text)
    if not chunks:
        return None, "thin"
    if max_chunks is not None:
        chunks = chunks[:max_chunks]

    sims = sorted(
        (cosine_sim(intent_emb, get_embedding(c)) for c in chunks), reverse=True
    )
    top = sims[: max(1, top_k)]
    return sum(top) / len(top), "ok"
