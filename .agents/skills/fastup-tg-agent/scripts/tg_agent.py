#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""CLI-утилита для управления Telegram-ботом FastUp (@FastupAgent_bot) и топиками чата.

Использование:
    # Показать список всех тем и их ID
    python scripts/tg_agent.py topics

    # Отправить сообщение в тему по алиасу или ID
    python scripts/tg_agent.py send "Текст сообщения" --topic digest
    python scripts/tg_agent.py send "<b>Жирный текст</b>" --topic leads
    python scripts/tg_agent.py send "Задача выполнена" --topic closed
    python scripts/tg_agent.py send "Сообщение в чат" --topic chat
    python scripts/tg_agent.py send "Документ получен" --topic docs
    python scripts/tg_agent.py send "В общий пул задач" --topic tasks
    python scripts/tg_agent.py send "В архив" --topic archive
    python scripts/tg_agent.py send "По прямому ID" --topic 545

    # Удалить сообщение по его message_id
    python scripts/tg_agent.py delete 556

    # Создать новый топик (требуется право 'can_manage_topics' у бота в админке чата)
    python scripts/tg_agent.py create-topic "🎉 Флудилка"

    # Последние сообщения из базы CRM
    python scripts/tg_agent.py history --limit 10
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Принудительный UTF-8 вывод в Windows-консоли
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Подключаем загрузчик .env
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from env_load import load_env
    load_env()
except ImportError:
    pass

# Основной рабочий чат супергруппы FastUp
DEFAULT_CHAT_ID = -1003819058234

# Токен бота @FastupAgent_bot (Алеся Fastup.by) — только из .env (FASTUP_AGENT_BOT_TOKEN).
# В код не зашивать: репозиторий на GitHub, токен даёт полный контроль над ботом.
DEFAULT_TOKEN = os.environ.get("FASTUP_AGENT_BOT_TOKEN", os.environ.get("TELEGRAM_BOT_TOKEN", ""))
if not DEFAULT_TOKEN:
    sys.exit("Нет токена: задай FASTUP_AGENT_BOT_TOKEN в .env")

# Реестр тем канала
TOPICS = {
    "general": {
        "id": None,
        "name": "Общий",
        "aliases": ["общ", "general", "главная", "общий", "main"],
        "desc": "Общий чат команды, объявления и сообщения вне специализированных тем"
    },
    "tasks": {
        "id": 581,
        "name": "Открытые задачи",
        "aliases": ["оз", "tasks", "open", "задачи", "открытые"],
        "desc": "Актуальный пул задач в работе (обновляется крон-пересборкой)"
    },
    "pins": {
        "id": 535,
        "name": "Закрепленки",
        "aliases": ["зак", "закр", "закрепленки", "pins", "пароли"],
        "desc": "Закрепленные сообщения, важные доступы, ссылки и реквизиты"
    },
    "leads": {
        "id": 549,
        "name": "🔥 Горячие заявки",
        "aliases": ["заяв", "leads", "заявки", "горячие", "hot"],
        "desc": "Горячие целевые заявки (сайт, разработка, реклама, КП, созвоны) — в работу Евгению"
    },
    "sales": {
        "id": 616,
        "name": "📞 Лиды обзвона и перезвоны",
        "aliases": ["обзвон", "sales", "перезвоны", "лиды", "света"],
        "desc": "Топик старшего: карточки обзвона «В работе», дайджест и «Пора перезвонить»"
    },
    "qa": {
        "id": 606,
        "name": "Вопросы-ответы",
        "aliases": ["qa", "вопросы-ответы", "вопрос", "ответы"],
        "desc": "Петля обучения Алеси: вопросы операторов без ответа, ответ руководителя реплаем"
    },
    "digest": {
        "id": 543,
        "name": "Недельный дайджест",
        "aliases": ["дайдж", "digest", "дайджест", "отчеты"],
        "desc": "Понедельничный дайджест дедлайнов и динамики агентства"
    },
    "docs": {
        "id": 541,
        "name": "Первичка (акты, чеки, договоры)",
        "aliases": ["акт", "docs", "документы", "первичка", "чеки"],
        "desc": "Инбокс первички: автоприём фото чеков, PDF и накладных"
    },
    "chat": {
        "id": 545,
        "name": "Обсуждение / Общение",
        "aliases": ["обсуж", "chat", "общение", "диалог", "вопросы"],
        "desc": "Живой диалог команды и вопросы к ИИ-агенту Алесе"
    },
    "archive": {
        "id": 547,
        "name": "Архив задач",
        "aliases": ["арх", "archive", "архив", "закрытые", "closed", "done"],
        "desc": "Архив задач: аудит-лог выполненных и закрытых задач (всегда без звука / silent)"
    },
    "flood": {
        "id": 578,
        "name": "Флудилка (закрыта)",
        "aliases": ["флуд", "флудилка", "flood", "оффтоп"],
        "desc": "Неформальное общение, мемы, ссылки (архивный закрытый топик)"
    },
    "service": {
        "id": 626,
        "name": "⚙️ Служебные уведомления",
        "aliases": ["сервис", "служебные", "тех", "технические", "service", "tech", "антифрод", "рассинхрон", "фолбэк", "фоллбэк"],
        "desc": "Системные алерты: антифрод операторов, рассинхрон лидов, сбои/фолбэки бота"
    }
}


def resolve_topic(topic_arg):
    """Преобразует алиас или числовую строку в (thread_id, display_name)."""
    if not topic_arg:
        return None, "Открытые задачи (General)"
    
    clean = str(topic_arg).strip().lower()
    
    # Прямой ID
    if clean.isdigit():
        tid = int(clean)
        for t_info in TOPICS.values():
            if t_info["id"] == tid:
                return tid, t_info["name"]
        return tid, f"Тема #{tid}"
    
    if clean in ("none", "null", "general", "0"):
        return None, "Открытые задачи (General)"
        
    for t_key, t_info in TOPICS.items():
        if clean == t_key or clean in t_info["aliases"]:
            return t_info["id"], t_info["name"]
            
    # Если не найдено — ошибка
    valid_aliases = []
    for k, v in TOPICS.items():
        valid_aliases.append(f"{k} ({', '.join(v['aliases'][:2])})")
    raise SystemExit(
        f"Ошибка: неизвестная тема '{topic_arg}'. Доступные темы:\n  - " +
        "\n  - ".join(valid_aliases)
    )


def tg_api(method, payload=None, token=None):
    """Выполняет вызов Telegram Bot API."""
    tok = token or DEFAULT_TOKEN
    url = f"https://api.telegram.org/bot{tok}/{method}"
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_body)
            desc = err_json.get("description", err_body)
        except Exception:
            desc = err_body
        raise SystemExit(f"Telegram API Error {e.code} ({method}): {desc}")
    except Exception as e:
        raise SystemExit(f"Сетевая ошибка при запросе к Telegram: {e}")


def make_task_keyboard(task_id: int, deadline: str = "") -> dict:
    """Создаёт стандартную inline-клавиатуру FastUpCRM для задачи.
    
    Кнопки:
    - ✅ Выполнено (callback: t:done:<task_id>)
    - ❌ Закрыть (callback: t:close:<task_id>)
    - 🔗 Открыть в CRM (переход в SPA CRM к задаче)
    """
    row1 = [
        {"text": "✅ Выполнено", "callback_data": f"t:done:{task_id}"},
        {"text": "❌ Закрыть", "callback_data": f"t:close:{task_id}"},
    ]
    base_url = "https://admin.microapps.by/wp-admin/admin.php?page=microapps-crm"
    clean_dl = str(deadline).strip()
    url = f"{base_url}#calendar/day/{clean_dl}/task/{task_id}" if clean_dl else f"{base_url}#tasks/task/{task_id}"
    row2 = [{"text": "🔗 Открыть в CRM", "url": url}]
    return {"inline_keyboard": [row1, row2]}


def send_topic(text: str, topic="tasks", silent=False, chat_id=DEFAULT_CHAT_ID, reply_markup=None):
    """Отправляет сообщение в топик форума Telegram.
    
    Топик 'archive' (ID 547) всегда отправляется без звука (disable_notification=True).
    """
    thread_id, topic_name = resolve_topic(topic)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if thread_id is not None:
        payload["message_thread_id"] = thread_id
    if silent or thread_id == 547:
        payload["disable_notification"] = True
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    res = tg_api("sendMessage", payload)
    return res, topic_name, payload.get("disable_notification", False)


def parse_reply_markup_arg(args):
    """Извлекает reply_markup из аргументов CLI: либо через --task-id, либо через JSON --reply-markup."""
    if getattr(args, "task_id", None):
        return make_task_keyboard(args.task_id, getattr(args, "deadline", ""))
    if getattr(args, "reply_markup", None):
        raw = args.reply_markup.strip()
        return json.loads(raw)
    return None


def cmd_topics(args):
    """Выводит красивую таблицу всех зарегистрированных тем."""
    print("=" * 80)
    print(f"{'Тема':<32} | {'ID темы':<10} | {'Алиасы для CLI'}")
    print("=" * 80)
    for key, info in TOPICS.items():
        tid_str = str(info["id"]) if info["id"] is not None else "General"
        alias_str = ", ".join(info["aliases"])
        print(f"{info['name']:<32} | {tid_str:<10} | {alias_str}")
    print("=" * 80)
    print("Пример отправки: python scripts/tg_agent.py send 'Привет' --topic digest")


def cmd_send(args):
    """Отправляет HTML сообщение в заданный топик."""
    if getattr(args, "file", None):
        text = args.file.read_text(encoding="utf-8")
    elif getattr(args, "stdin", False) or args.text == "-":
        text = sys.stdin.read()
    else:
        text = args.text

    if not text:
        sys.exit("Текст сообщения пуст")

    reply_markup = parse_reply_markup_arg(args)

    res, topic_name, is_silent = send_topic(
        text=text,
        topic=args.topic,
        silent=getattr(args, "silent", False),
        chat_id=args.chat_id,
        reply_markup=reply_markup,
    )
    if res.get("ok"):
        msg_id = res["result"]["message_id"]
        silent_mark = " (тихое / без звука)" if is_silent else ""
        btn_mark = " [с кнопками задачи]" if reply_markup else ""
        print(f"✅ Сообщение успешно отправлено в [{topic_name}]{silent_mark}{btn_mark} (msg_id: {msg_id})")
    else:
        print(f"❌ Ошибка отправки: {res}")


def edit_topic_message(message_id, text=None, chat_id=DEFAULT_CHAT_ID, reply_markup=None):
    """Редактирует сообщение или его клавиатуру по message_id."""
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
    }
    if text is not None:
        payload["text"] = text
        payload["parse_mode"] = "HTML"
        payload["disable_web_page_preview"] = True
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    if text is not None:
        return tg_api("editMessageText", payload)
    return tg_api("editMessageReplyMarkup", payload)


def cmd_edit(args):
    """Редактирует сообщение по его message_id."""
    if getattr(args, "file", None):
        text = args.file.read_text(encoding="utf-8")
    elif getattr(args, "stdin", False) or args.text == "-":
        text = sys.stdin.read()
    else:
        text = args.text

    reply_markup = parse_reply_markup_arg(args)

    if not text and reply_markup is None:
        sys.exit("Для редактирования укажи новый текст или --task-id/--reply-markup")

    try:
        res = edit_topic_message(
            message_id=args.message_id,
            text=text if text else None,
            chat_id=args.chat_id,
            reply_markup=reply_markup,
        )
        if res.get("ok"):
            btn_mark = " [кнопки обновлены]" if reply_markup else ""
            print(f"✅ Сообщение {args.message_id} успешно отредактировано{btn_mark}")
        else:
            print(f"❌ Ошибка редактирования: {res}")
    except SystemExit as e:
        if "message is not modified" in str(e):
            print(f"✅ Сообщение {args.message_id} уже содержит актуальный текст и кнопки (без изменений)")
        else:
            raise


def cmd_delete(args):
    """Удаляет сообщение по его message_id."""
    try:
        res = tg_api("deleteMessage", {
            "chat_id": args.chat_id,
            "message_id": args.message_id
        })
        if res.get("ok"):
            print(f"✅ Сообщение {args.message_id} успешно удалено из чата {args.chat_id}")
            return
    except SystemExit as e:
        err_msg = str(e)
        if "message can't be deleted" in err_msg:
            print(f"⚠️ Ошибка Telegram: сообщение {args.message_id} старше 48 часов. Telegram Bot API запрещает ботам удалять сообщения старше 48ч — удали его вручную в клиенте Telegram.")
            return
        raise


def cmd_create_topic(args):
    """Создаёт новый топик в форуме."""
    payload = {
        "chat_id": args.chat_id,
        "name": args.name
    }
    try:
        res = tg_api("createForumTopic", payload)
        if res.get("ok"):
            tid = res["result"]["message_thread_id"]
            name = res["result"]["name"]
            print(f"🎉 Топик '{name}' успешно создан! ID темы: {tid}")
        else:
            print(f"❌ Ошибка: {res}")
    except SystemExit as e:
        if "not enough rights to create a topic" in str(e):
            print("\n❌ Ошибка прав: Telegram отклонил создание темы.")
            print("👉 Чтобы бот мог создавать темы программно:")
            print("   1. Откройте группу в Telegram Desktop/Mobile;")
            print("   2. Настройки группы -> Администраторы -> @FastupAgent_bot;")
            print("   3. Включите тумблер: 'Управление темами' (Manage Topics);\n")
            print(e)


def cmd_rename_topic(args):
    """Переименовывает топик форума."""
    thread_id, current_name = resolve_topic(args.topic)
    if thread_id is None:
        sys.exit("Ошибка: нельзя переименовать General топик через editForumTopic")
    payload = {
        "chat_id": args.chat_id,
        "message_thread_id": thread_id,
        "name": args.name
    }
    res = tg_api("editForumTopic", payload)
    if res.get("ok"):
        print(f"✅ Топик #{thread_id} ({current_name}) успешно переименован в '{args.name}'")
    else:
        print(f"❌ Ошибка переименования: {res}")


def cmd_close_topic(args):
    """Закрывает топик форума."""
    thread_id, current_name = resolve_topic(args.topic)
    if thread_id is None:
        sys.exit("Ошибка: нельзя закрыть General топик")
    payload = {
        "chat_id": args.chat_id,
        "message_thread_id": thread_id
    }
    res = tg_api("closeForumTopic", payload)
    if res.get("ok"):
        print(f"🔒 Топик #{thread_id} ({current_name}) успешно закрыт")
    else:
        print(f"❌ Ошибка закрытия: {res}")


def cmd_reopen_topic(args):
    """Открывает закрытый топик форума."""
    thread_id, current_name = resolve_topic(args.topic)
    if thread_id is None:
        sys.exit("Ошибка: нельзя открыть General топик")
    payload = {
        "chat_id": args.chat_id,
        "message_thread_id": thread_id
    }
    res = tg_api("reopenForumTopic", payload)
    if res.get("ok"):
        print(f"🔓 Топик #{thread_id} ({current_name}) успешно открыт")
    else:
        print(f"❌ Ошибка открытия: {res}")


def cmd_history(args):
    """Запрашивает последние сообщения через REST API CRM."""
    auth = base64.b64encode(b"ai-agent:ApSbkIUk2OQMs082WSLK1Jvw").decode("ascii")
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json"
    }
    sql = (
        f"SELECT tg_message_id, from_name, message_text, sent_at "
        f"FROM wp_crm_tg_messages "
        f"WHERE chat_id = '{args.chat_id}' "
        f"ORDER BY id DESC LIMIT {args.limit}"
    )
    req = urllib.request.Request(
        "https://admin.microapps.by/wp-json/microapps/v1/agent/sql",
        data=json.dumps({"db": "wp", "query": sql}).encode("utf-8"),
        headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rows = data.get("rows", [])
            print(f"--- Последние {len(rows)} сообщений чата {args.chat_id} ---")
            for r in reversed(rows):
                print(f"[{r.get('sent_at')}] (ID {r.get('tg_message_id')}) {r.get('from_name')}: {r.get('message_text')}")
    except Exception as e:
        print(f"❌ Ошибка запроса истории: {e}")


def main():
    parser = argparse.ArgumentParser(description="Управление Telegram-ботом FastUp и топиками форума.")
    parser.add_argument("--chat-id", type=int, default=DEFAULT_CHAT_ID, help="ID чата (по умолчанию FastUp общий)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # topics
    subparsers.add_parser("topics", help="Показать все зарегистрированные темы")

    # send
    p_send = subparsers.add_parser("send", help="Отправить сообщение в тему")
    p_send.add_argument("text", nargs="?", default="", help="Текст сообщения (поддерживает HTML: <b>, <i>, <code>, <a href='...'>)")
    p_send.add_argument("--file", type=Path, help="Читать текст из файла")
    p_send.add_argument("--stdin", action="store_true", help="Читать текст из stdin")
    p_send.add_argument("--topic", default="tasks", help="Тема: tasks, pins, leads, digest, docs, chat, archive или числовой ID")
    p_send.add_argument("--silent", action="store_true", help="Отправить без звука и всплывающего уведомления")
    p_send.add_argument("--task-id", type=int, default=None, help="ID задачи в CRM — автоматически формирует кнопки (✅ Выполнено, ❌ Закрыть, 🔗 Открыть в CRM)")
    p_send.add_argument("--deadline", type=str, default="", help="Дедлайн задачи (ГГГГ-ММ-ДД) для ссылки кнопки Открыть")
    p_send.add_argument("--reply-markup", type=str, default=None, help="Произвольный reply_markup в формате JSON")

    # edit
    p_edit = subparsers.add_parser("edit", help="Отредактировать существующее сообщение по message_id")
    p_edit.add_argument("message_id", type=int, help="ID сообщения для редактирования")
    p_edit.add_argument("text", nargs="?", default="", help="Новый текст сообщения (HTML)")
    p_edit.add_argument("--file", type=Path, help="Читать текст из файла")
    p_edit.add_argument("--stdin", action="store_true", help="Читать текст из stdin")
    p_edit.add_argument("--task-id", type=int, default=None, help="ID задачи в CRM — автоматически формирует кнопки (✅ Выполнено, ❌ Закрыть, 🔗 Открыть в CRM)")
    p_edit.add_argument("--deadline", type=str, default="", help="Дедлайн задачи (ГГГГ-ММ-ДД) для ссылки кнопки Открыть")
    p_edit.add_argument("--reply-markup", type=str, default=None, help="Произвольный reply_markup в формате JSON")

    # delete
    p_del = subparsers.add_parser("delete", help="Удалить сообщение по message_id")
    p_del.add_argument("message_id", type=int, help="ID сообщения")

    # create-topic
    p_create = subparsers.add_parser("create-topic", help="Создать новый топик")
    p_create.add_argument("name", help="Название нового топика")

    # rename-topic
    p_ren = subparsers.add_parser("rename-topic", help="Переименовать топик форума")
    p_ren.add_argument("topic", help="Тема: leads, flood или числовой thread_id")
    p_ren.add_argument("name", help="Новое название топика")

    # close-topic
    p_cls = subparsers.add_parser("close-topic", help="Закрыть топик форума")
    p_cls.add_argument("topic", help="Тема: flood или числовой thread_id")

    # reopen-topic
    p_rop = subparsers.add_parser("reopen-topic", help="Открыть ранее закрытый топик форума")
    p_rop.add_argument("topic", help="Тема: flood или числовой thread_id")

    # history
    p_hist = subparsers.add_parser("history", help="Показать историю сообщений")
    p_hist.add_argument("--limit", type=int, default=10, help="Количество строк")

    args = parser.parse_args()

    if args.command == "topics":
        cmd_topics(args)
    elif args.command == "send":
        cmd_send(args)
    elif args.command == "edit":
        cmd_edit(args)
    elif args.command == "delete":
        cmd_delete(args)
    elif args.command == "create-topic":
        cmd_create_topic(args)
    elif args.command == "rename-topic":
        cmd_rename_topic(args)
    elif args.command == "close-topic":
        cmd_close_topic(args)
    elif args.command == "reopen-topic":
        cmd_reopen_topic(args)
    elif args.command == "history":
        cmd_history(args)


if __name__ == "__main__":
    main()
