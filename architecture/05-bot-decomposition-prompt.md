---
date: 2026-09-17
tags: [prompt, decomposition, bot, php, refactoring, alesya]
status: ready
source: "Переписано 17.09.2026 под план 04: этапы 1–2 (PHP-декомпозиция и гонки)"
---

# Промпт исполнителю: этапы 1–2 выноса бота

> Выполнять в репозитории `admin-microapps` (`G:\OSPanel\domains\admin.microapps`).
> Этапы 3–6 плана [04](04-unified-bot-and-crm-migration.md) — отдельными промптами после
> приёмки этих двух: CRM REST-эндпоинты зависят от того, как лягут модули.

```markdown
# Задача: разнести telegram-bot.php по модулям и закрыть две гонки

## Контекст
Все Telegram-функции переходят к агенту Алесе (Node, `agent/crm-mcp`) как инструменты и
серверные workflow. Первый шаг — разобрать PHP-монолит `microapps/cron/telegram-bot.php`
(2 461 строка) так, чтобы логика стала библиотекой, а точка входа — тонкой. Поведение
в этом шаге НЕ меняется, кроме удаления мёртвого кода и двух гонок в отдельном коммите.
Полный план и причины: fastup-mentor `architecture/04-unified-bot-and-crm-migration.md`.

## Перед правками прочитать
- `microapps/cron/telegram-bot.php` целиком.
- `microapps-v2/includes/tg-task-sync.php` (строка ~43 делает require_once точки входа).
- `microapps/includes/pm-engine.php` (`microapps_pm_create_from_proposal`, `microapps_pm_dismiss_proposal`).
- `grep -rn "fastupcrm_bot_" microapps microapps-v2` — все внешние вызовы.

## Коммит 1 — структура, поведение то же
Создать `microapps/includes/bot/`:
- `bootstrap.php` — только require модулей, без побочных эффектов;
- `config.php` — загрузка `telegram-bot.config.php`, `*_thread_id()`, `*_chats()`;
- `tg-api.php` — `tg_api`, `agent_tg_api`, `telegram_send`, `agent_send`, `send_blocks`, `send_sales_blocks`, `tm_track_message`, `tm_history`;
- `format.php` — `format_*`, `esc`, `format_phone`, `first_lines`, `parse_services`, хелперы даты/времени;
- `keyboards.php` — все `*_keyboard`;
- `jobs/leads.php` — `send_new_leads`, `hot_escalate`, `calculate_hot_deadline`;
- `jobs/callbacks.php` — `send_today_callbacks`, `send_due_callbacks`;
- `jobs/calls.php` — `send_today_calls`, `send_soon_calls`, `today_calls_query`;
- `jobs/tasks.php` — `send_soon_tasks`, `close_task_now`, `send_closed_task_log`, `task_url`, `assignee_mention`;
- `jobs/pm.php` — `pm_scan`, `pm_ask_agent`, `pm_deadlines` и все `pm_*` хелперы;
- `webhook/router.php` — `handle_webhook`, `self_url`, `close_finish`;
- `webhook/lead.php` — `handle_lead_callback`; `webhook/pm.php` — `handle_pm_callback`.
- `status`, `ping` — в `jobs/diag.php`.

Правила:
- Функции переносить дословно, имена `fastupcrm_bot_*` не менять.
- `cron/telegram-bot.php` оставить точкой входа: определение CLI/HTTP, поиск `wp-load.php`,
  проверка `web_key`, `require bootstrap.php`, `switch` по режиму.
- Удалить: режимы `tasks-rebuild`, `patchnote`, `tg-setup` и их функции;
  `fastupcrm_bot_lead_keyboard`. Обновить строку usage.
- `tg-task-sync.php`: подключать `includes/bot/bootstrap.php` (функции могут быть уже
  объявлены — guard `function_exists` на загрузку bootstrap), а не `cron/telegram-bot.php`.

## Коммит 2 — дубли в webhook/lead.php
Ветки take / spam / recall трижды собирают итоговый текст карточки и `editMessageText`.
Вынести в одну функцию (текст подтверждения, разметка, `parse_mode` для hot). Вывод в
Telegram — байт в байт как раньше.

## Коммит 3 — гонки (атомарные переходы)
1. `_crm_hot_state`: переход `waiting → taken` в `lead:take` и `waiting → escalated` в
   `hot_escalate` — одним `$wpdb->query("UPDATE {$wpdb->postmeta} SET meta_value=%s WHERE
   post_id=%d AND meta_key='_crm_hot_state' AND meta_value='waiting'")`; 0 строк → не
   продолжать (take: тост «Лид уже передан»; escalate: пропустить лида). После прямого
   UPDATE — `wp_cache_delete( $post_id, 'post_meta' )`.
2. `microapps_pm_create_from_proposal`: прочитать предложение, затем `DELETE` меты
   `_crm_pm_proposal` для лида; если удалено 0 строк — вернуть 0 (уже создано другим нажатием),
   только потом `wp_insert_post`.

## Проверка (приложить вывод)
- `G:\php-8.5\php.exe -l` по каждому новому и изменённому файлу.
- Скрипт: список `function fastupcrm_bot_*` до (git show HEAD~N) и после — совпадает за
  вычетом удалённых; каждая объявлена ровно один раз.
- `grep` внешних вызовов — все имена существуют.
- Для прода (выполняет Егор после выкатки): `?key=…&mode=status` отдаёт last_run; закрыть
  тестовую задачу в веб-CRM — нет «forbidden», карточка в «Закрытые задачи»; тестовый лид
  с дедлайном в прошлом → уходит из 549 в 616.

## Выкатка
Не выкатывать самостоятельно. Перед выкаткой скачать живые `cron/telegram-bot.php` и
`microapps-v2/includes/tg-task-sync.php` с хостинга и сверить с HEAD: на проде могли быть
правки мимо git. Порядок заливки: `includes/bot/*` → `tg-task-sync.php` → точка входа.
Откат — вернуть две старые версии файлов.

## Не делать
- Не переносить логику в Node и не создавать REST-эндпоинты — это этап 3.
- Не менять тексты сообщений, топики, расписание, получателей.
- Не трогать `lead-validation.php`, `quality-check.php`.
```
