#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Закрытие открытой задачи в CRM и тихая отправка в Архив задач Telegram (топик 547).

Использование:
    python scripts/complete_task.py 1531
    python scripts/complete_task.py 1531 --note "Акт отправлен клиенту в Telegram, ждём подписанный скан"
    python scripts/complete_task.py 1531 --delete-msg 589 # удалить карточку из топика 581
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from env_load import load_env

load_env()


def call_tool(action: str, payload: dict) -> dict:
    cmd = [sys.executable, str(ROOT / "scripts" / "tools.py"), action, "--json", "-"]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    p = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )
    out, err = p.communicate(json.dumps(payload, ensure_ascii=False))
    if p.returncode != 0:
        raise RuntimeError(f"Error calling {action}: {out} {err}")
    try:
        return json.loads(out)
    except Exception:
        return {"raw": out}


def get_task_info(task_id: int) -> dict:
    q = (
        f"SELECT p.ID, p.post_title, "
        f"pm_status.meta_value as status, "
        f"pm_assignee.meta_value as assignee_id, "
        f"pm_client.meta_value as client_id "
        f"FROM wp_posts p "
        f"LEFT JOIN wp_postmeta pm_status ON p.ID = pm_status.post_id AND pm_status.meta_key = '_tm_status' "
        f"LEFT JOIN wp_postmeta pm_assignee ON p.ID = pm_assignee.post_id AND pm_assignee.meta_key = '_tm_assignee_id' "
        f"LEFT JOIN wp_postmeta pm_client ON p.ID = pm_client.post_id AND pm_client.meta_key = '_tm_client_id' "
        f"WHERE p.ID = {task_id} AND p.post_type = 'crm_tm_task' LIMIT 1"
    )
    res = call_tool("crm_sql_query", {"db": "wp", "query": q})
    rows = res.get("rows", [])
    if not rows:
        return {"id": task_id, "title": f"Задача #{task_id}", "status": "unknown"}
    row = rows[0]
    return {
        "id": int(row.get("ID")),
        "title": row.get("post_title", ""),
        "status": row.get("status", ""),
        "assignee_id": int(row.get("assignee_id") or 0),
        "client_id": int(row.get("client_id") or 0),
    }


def resolve_assignee_name(assignee_id: int) -> str:
    known = {
        7: "Евгений",
        10: "Егор",
        8: "Светлана",
        14: "AI-агент",
        25: "Ира Латышева",
        29: "Янина",
    }
    return known.get(assignee_id, f"ID #{assignee_id}" if assignee_id else "Не назначен")


def complete_task(task_id: int, note: str = "", delete_msg_id: int = None):
    print(f"🔍 Получение информации по задаче #{task_id}...")
    task = get_task_info(task_id)
    title = task.get("title") or f"Задача #{task_id}"
    assignee = resolve_assignee_name(task.get("assignee_id", 0))

    print(f"  Название: {title}")
    print(f"  Исполнитель: {assignee}")

    # 1. Обновляем статус в CRM
    print("⚙️ Обновление статуса в CRM (status='done')...")
    upd_res = call_tool("crm_update_task", {"id": task_id, "status": "done"})
    print("  ✅ Статус задачи в CRM переведён в «done»")

    # 2. Если передан message_id, удаляем карточку из топика 581
    if delete_msg_id:
        print(f"🗑️ Удаление открытой карточки (msg_id: {delete_msg_id}) из топика 581...")
        try:
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "tg_agent.py"), "delete", str(delete_msg_id)],
                check=True,
                capture_output=True,
            )
            print("  ✅ Карточка удалена из «Открытых задач»")
        except Exception as e:
            print(f"  ⚠️ Не удалось удалить сообщение {delete_msg_id}: {e}")

    # 3. Отправляем тихую строку в топик 547 («Архив задач»)
    print("🤫 Отправка тихой записи в «Архив задач» (топик 547)...")
    archive_lines = [
        f"✅ <b>[Выполнено] Задача #{task_id}</b>",
        f"<b>Что:</b> {title}",
        f"👤 <b>Исполнитель:</b> {assignee}",
    ]
    if note:
        archive_lines.append(f"💬 <b>Отчёт:</b> <i>{note}</i>")

    archive_text = "\n".join(archive_lines)

    try:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "tg_agent.py"), "send", archive_text, "--topic", "archive", "--silent"],
            check=True,
            capture_output=True,
        )
        print("  ✅ Задача успешно зафиксирована в «Архиве задач» (тихо, без звука)")
    except Exception as e:
        print(f"  ⚠️ Ошибка отправки в архив задач: {e}")

    print(f"\n=== ЗАДАЧА #{task_id} УСПЕШНО ЗАКРЫТА ===")


def main():
    parser = argparse.ArgumentParser(description="Закрытие задачи в CRM и тихий лог в Архив задач")
    parser.add_argument("task_id", type=int, help="ID задачи в CRM (например, 1531)")
    parser.add_argument("--note", type=str, default="", help="Комментарий или отчёт о выполнении")
    parser.add_argument("--delete-msg", type=int, default=None, help="ID сообщения в топике 581 для удаления")

    args = parser.parse_args()
    complete_task(args.task_id, args.note, args.delete_msg)


if __name__ == "__main__":
    main()
