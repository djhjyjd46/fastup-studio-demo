---
date: 2026-09-17
tags: [architecture, index, roadmap, ai-studio, bots, migration]
status: active
---

# Архитектурный хаб FastUp AI Studio

Единая папка архитектурного проектирования и модернизации ментора, ботов, CRM и агентного контура.
Построена строго по принципам Google Cloud Architecture (*Non-agentic first*) и Antigravity 2.0 (*Coordinator + Skills + MCP + Subagents*).

## Документы в этой папке

| Файл | Описание | Статус |
|---|---|---|
| [03-fastup-ai-studio-master-plan.md](03-fastup-ai-studio-master-plan.md) | **Действующий Мастер-план:** разделение на 2 контура (серверный бэкенд 24/7 и десктоп Antigravity 2.0), иерархия «инструмент → процедура → субагент», прямой DeepSeek API, правила Human-in-the-loop | **Канон архитектуры** |
| [04-unified-bot-and-crm-migration.md](04-unified-bot-and-crm-migration.md) | Вынос `telegram-bot.php`: схлопывание в одного бота (Алеся), серверные workflow без LLM, закрытие гонок базы | **План миграции ботов** |
| [05-bot-decomposition-prompt.md](05-bot-decomposition-prompt.md) | **Промпт исполнителю Сессии 1:** разнос монолита по модулям в PHP и атомарные переходы для двух гонок в `admin-microapps` | **Исполнительский промпт** |

---

## Общая карта взаимосвязанных репозиториев экосистемы

1. **`fastup-mentor` (этот репозиторий):** База знаний, память (Markdown), регламенты, навыки (`.agents/skills/`), субагенты, локальные скрипты автоматизации (`scripts/`).
2. **`admin-microapps` (`G:/OSPanel/domains/admin.microapps`):** WordPress темы CRM (`microapps`, `microapps-v2`) + Node.js сервер инструментов и бота (`agent/crm-mcp` → прод `tools.fastup.by`).
3. **`crm` (`G:/OSPanel/domains/crm`):** Laravel CRM обзвонщиков, база лидов, сдельная оплата звонков, антифрод.
4. **`fastup-ad-agent` (`G:/fastup-ad-agent`):** Коробочный standalone-шаблон ИИ-агента контекстной рекламы для установки клиентам (пилот — «Палеандр»).
5. **`fastup-clients` (`G:/fastup-clients`):** Изолированное хранилище клиентских данных, аудитов и отчётов.
6. **`fastup-docs` (`G:/fastup-docs`):** Архив первичных документов, договоров, актов и чеков.

---

## Дорожная карта следующих двух сессий

- **Сессия 1 (Хостинг и Бот):** Выполняется в `admin-microapps`. Задача: переключение текстов на прямой `api.deepseek.com`, расширение прав токена Евгения (`ceo`), модульный разбор `telegram-bot.php` (2 461 строка) по промпту `05-bot-decomposition-prompt.md`, ликвидация гонок и перевод уведомлений на одного бота (Алеся).
- **Сессия 2 (Агентная среда Antigravity 2.0):** Выполняется в `fastup-mentor`. Задача: настройка `.agents/rules/`, полировка 10 проектных Skills, подключение MCP к `tools.fastup.by`, настройка субагентов для изоляции контекста и прогон 5 сквозных контрольных кейсов.
