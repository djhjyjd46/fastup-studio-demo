---
date: 2026-09-18
tags: [setup, demo, onboarding, antigravity]
status: active
---

# FastUp Studio Demo — Развёртывание демонстрационного окружения (Google Antigravity)

Инструкция по первичной настройке и самодиагностике публичного демонстрационного репозитория архитектуры FastUp Studio.

---

## 1. Предварительные требования

Перед запуском в системе должны быть установлены:
1. **Git**: [git-scm.com/downloads](https://git-scm.com/downloads).
2. **Python 3.11+**: [python.org/downloads](https://www.python.org/downloads/) (с опцией **«Add python.exe to PATH»**).
3. **Google Antigravity**: [antigravity.google](https://antigravity.google) (или совместимая IDE).

---

## 2. Чеклист развёртывания

- [ ] **1. Проверка окружения:** Git и Python доступны в командной строке.
- [ ] **2. Клонирование репозитория:**
  ```bash
  git clone https://github.com/djhjyjd46/fastup-studio-demo.git
  cd fastup-studio-demo
  ```
- [ ] **3. Установка зависимостей Python:**
  ```bash
  python -m pip install -r scripts/requirements.txt
  ```
- [ ] **4. Локальная индексация демонстрационной базы знаний (SQLite FTS5):**
  ```bash
  python scripts/search_memory.py --reindex
  ```
- [ ] **5. Файл конфигурации `.env`:** при необходимости скопировать `.env.example` в `.env` и указать собственные API-ключи (`DEEPSEEK_API_KEY`, `GEMINI_API_KEY`).

---

## 3. Самодиагностика и проверка (Smoke Test)

1. **Автономные регрессионные и инвариантные тесты (без сетевых вызовов):**
   ```bash
   python -m pytest
   ```
   *Ожидаемый результат:* все тесты в `tests/test_deploy_safety.py` и `tests/test_invariants.py` проходят успешно (`passed`).

2. **Поиск по локальной базе знаний (`architecture/`, `geo/`, `playbook/`):**
   ```bash
   python scripts/search_memory.py "GEO"
   ```
   *Ожидаемый результат:* выдача релевантных сниппетов из локального индекса `scripts/memory_index.db` без ошибок.

3. **Сборка контекстного пакета:**
   ```bash
   python scripts/context_pack.py "citability" --task geo
   ```
   *Ожидаемый результат:* сформированный контекстный пакет по папкам профиля `geo`.

4. **Состояние Git:**
   ```bash
   git status
   ```
   *Ожидаемый результат:* ветка `main`, рабочая копия чистая (локальный индекс `scripts/memory_index.db` и кэш `scripts/.embed_cache/` игнорируются через `.gitignore`).
