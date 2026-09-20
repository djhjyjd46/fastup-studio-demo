#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Инспекция действий оператора и поиск «потерянных» лидов в CRM.

Использование:
    python scripts/inspect_operator_lead.py --operator "Янина"
    python scripts/inspect_operator_lead.py --phone "375295272222"
    python scripts/inspect_operator_lead.py --lead 75623
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Подключаем вызов tools.py через sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from tools import rpc
except ImportError:
    print("Ошибка: не удалось импортировать rpc из scripts/tools.py", file=sys.stderr)
    sys.exit(2)


def run_sql(db: str, query: str):
    res = rpc("tools/call", {"name": "crm_sql_query", "arguments": {"db": db, "query": query}})
    content = res.get("content", [])
    text = "\n".join(part.get("text", "") for part in content if part.get("type") == "text")
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "rows" in parsed:
            return parsed["rows"]
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    return []


def inspect_operator(operator_query: str):
    print(f"\n🔍 Поиск оператора по запросу: {operator_query}")
    users = run_sql("crm", f"SELECT id, name, login, email, is_admin, is_senior_manager FROM users WHERE name LIKE '%{operator_query}%' OR login LIKE '%{operator_query}%'")
    if not users:
        print("❌ Оператор не найден в таблице users.")
        return

    for u in users:
        uid = u["id"]
        name = u["name"]
        print(f"\n👤 Оператор: {name} (ID: {uid}, логин: {u.get('login')})")

        # 1. Последние 10 событий оператора
        print("\n📜 Последние действия оператора (lead_events):")
        events = run_sql("crm", f"SELECT id, lead_id, source, event_type, actor, created_at, payload FROM lead_events WHERE actor_id = {uid} ORDER BY id DESC LIMIT 10")
        if not events:
            print("  (Нет зафиксированных действий)")
        else:
            for ev in events:
                lead_id = ev.get("lead_id", "—")
                ev_type = ev.get("event_type", "—")
                created = ev.get("created_at", "—")
                payload_raw = ev.get("payload", "")
                summary = ""
                try:
                    p = json.loads(payload_raw) if payload_raw else {}
                    if isinstance(p, dict):
                        if "reason" in p:
                            summary = f"причина: {p['reason']}"
                        elif "initial" in p:
                            init = p["initial"]
                            summary = f"создан лид: {init.get('company')} ({init.get('phone')}) статус: {init.get('status')}"
                        elif "status" in p:
                            summary = f"статус: {p['status'].get('old')} -> {p['status'].get('new')}"
                except Exception:
                    summary = payload_raw[:60]
                print(f"  • [{created}] Лид #{lead_id} | {ev_type} | {summary}")

        # 2. Недавние созданные лиды
        print("\n📁 Лиды, созданные оператором (или закреплённые за ним):")
        leads = run_sql("crm", f"SELECT id, company, name, phone, status, user_id, wordpress_client_id, created_at FROM leads WHERE user_id = {uid} ORDER BY id DESC LIMIT 5")
        if not leads:
            print("  (Нет назначенных лидов)")
        else:
            for l in leads:
                wp_info = f"WP ID: {l.get('wordpress_client_id')}" if l.get('wordpress_client_id') else "⚠️ В WP НЕ СИНХРОНИЗИРОВАН"
                print(f"  • Лид #{l['id']}: {l.get('company') or '—'} | Тел: {l.get('phone')} | Статус: {l.get('status')} | {wp_info}")


def inspect_phone(phone_query: str):
    clean_digits = re.sub(r"\D", "", phone_query)
    search_term = clean_digits[-9:] if len(clean_digits) >= 9 else clean_digits
    print(f"\n🔍 Поиск лида по номеру: {phone_query} (поиск по *{search_term}*)")

    leads = run_sql("crm", f"SELECT id, company, name, phone, status, user_id, wordpress_client_id, created_at FROM leads WHERE phone LIKE '%{search_term}%' ORDER BY id DESC")
    if not leads:
        print("❌ Лиды с таким номером не найдены.")
        return

    print(f"Найдено лидов: {len(leads)}")
    for l in leads:
        uid = l.get("user_id")
        user_name = "— (НИЧЕЙНЫЙ!)"
        if uid:
            u_info = run_sql("crm", f"SELECT name FROM users WHERE id = {uid}")
            if u_info:
                user_name = f"{u_info[0]['name']} (ID {uid})"
        wp_status = f"WP ID {l.get('wordpress_client_id')}" if l.get('wordpress_client_id') else "⚠️ НЕТ СИНКА В WP"
        print(f"\n  • [#{l['id']}] {l.get('company') or '—'} (Контакт: {l.get('name') or '—'})")
        print(f"    Телефон: {l.get('phone')}")
        print(f"    Статус: {l.get('status')}")
        print(f"    Менеджер: {user_name}")
        print(f"    Синхронизация: {wp_status}")
        print(f"    Создан: {l.get('created_at')}")


def inspect_lead(lead_id: int):
    print(f"\n🔍 Инспекция лида #{lead_id}")
    leads = run_sql("crm", f"SELECT * FROM leads WHERE id = {lead_id}")
    if not leads:
        print(f"❌ Лид #{lead_id} не найден.")
        return

    l = leads[0]
    uid = l.get("user_id")
    user_name = "— (НИЧЕЙНЫЙ / user_id = null)"
    if uid:
        u_info = run_sql("crm", f"SELECT name FROM users WHERE id = {uid}")
        if u_info:
            user_name = f"{u_info[0]['name']} (ID {uid})"

    print(f"Компания: {l.get('company') or '—'}")
    print(f"Контакт:  {l.get('name') or '—'}")
    print(f"Телефон:  {l.get('phone')}")
    print(f"Статус:   {l.get('status')}")
    print(f"Менеджер: {user_name}")
    print(f"WP Client ID: {l.get('wordpress_client_id') or '— (не синхронизирован)'}")
    print(f"Создан:   {l.get('created_at')}")

    # События по лиду
    events = run_sql("crm", f"SELECT id, source, event_type, actor, created_at, payload FROM lead_events WHERE lead_id = {lead_id} ORDER BY id ASC")
    print("\nИстория событий:")
    for ev in events:
        print(f"  • [{ev.get('created_at')}] {ev.get('actor') or 'system'} ({ev.get('source')}): {ev.get('event_type')}")


def main():
    parser = argparse.ArgumentParser(description="Инспекция оператора и лидов в CRM FastUp")
    parser.add_argument("--operator", "-o", help="Имя или логин оператора")
    parser.add_argument("--phone", "-p", help="Номер телефона для поиска")
    parser.add_argument("--lead", "-l", type=int, help="ID лида")

    args = parser.parse_args()
    if not (args.operator or args.phone or args.lead):
        parser.print_help()
        sys.exit(1)

    if args.operator:
        inspect_operator(args.operator)
    if args.phone:
        inspect_phone(args.phone)
    if args.lead:
        inspect_lead(args.lead)


if __name__ == "__main__":
    main()
