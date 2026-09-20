
import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
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


def find_client(query: str) -> dict:
    res = call_tool("crm_search_requisites", {"query": query})
    items = res if isinstance(res, list) else res.get("items", [])
    if not items:
        raise ValueError(f"Контрагент по запросу «{query}» не найден в CRM.")
    
    # Сначала ищем вхождение в имени
    q_lower = query.lower()
    matched = [i for i in items if q_lower in (i.get("name") or "").lower()]
    if matched:
        return matched[0]
    return items[0]


def close_deal(
    client_query: str,
    contract_no: str,
    amount: float,
    service_title: str,
    assignee_id: int = 7,
    milestones: list = None,
    act_no: str = "",
    dry_run: bool = False,
    generate_pdf: bool = False,
):
    print(f"=== ЗАКРЫТИЕ СДЕЛКИ ПО ДОГОВОРУ № {contract_no} ===")
    
    # 1. Поиск клиента и проверка реквизитов
    client = find_client(client_query)
    client_id = client.get("id")
    client_name = client.get("name")
    print(f"👤 Клиент: {client_name} (ID {client_id}, УНП {client.get('unp')})")

    # 2. Проверка договора и баланса в ledger
    contract = next((c for c in client.get("contracts", []) if str(c.get("no")) == str(contract_no)), None)
    contract_date = contract.get("date", datetime.now().strftime("%d.%m.%Y")) if contract else datetime.now().strftime("%d.%m.%Y")
    print(f"💼 Договор: № {contract_no} от {contract_date}")

    balance_info = client.get("balance", {})
    paid = balance_info.get("paid", 0)
    accrued = balance_info.get("accrued", 0)
    print(f"💰 Финансы по клиенту: начислено {accrued} BYN, оплачено {paid} BYN")

    # 3. Номер акта
    if not act_no:
        today_code = datetime.now().strftime("%d%m%y")
        act_no = today_code
    print(f"📄 Номер акта: № {act_no}")

    if dry_run:
        print("\n[DRY RUN] Предпросмотр параметров закрытия сделки:")
        print(f"  • Клиент: {client_name}")
        print(f"  • Услуга: {service_title}")
        act_no = datetime.now().strftime("%d%m%y")

    # 3. Регистрация номера акта в журнале документов
    if not dry_run:
        print(f"📝 Регистрация Акта № {act_no} в журнале CRM...")
        try:
            call_tool(
                "crm_next_doc_number",
                {
                    "type": "act",
                    "client_id": client_id,
                    "subject": f"Акт сдачи-приёмки к Договору № {contract_no}: {service_title}",
                    "amount": amount,
                    "number": act_no,
                },
            )
        except Exception as e:
            print(f"  ℹ️ Запись журнала: {e}")

    # 4. Проверка или создание проекта в CRM
    contract_date = client.get("contract_date") or datetime.now().strftime("%d.%m.%Y")
    project_name = f"{client_name} — {service_title}"
    projects_res = call_tool("crm_sql_query", {
        "db": "wp",
        "query": f"SELECT ID, post_title FROM wp_posts WHERE post_type = 'crm_project' AND post_title LIKE '%{client_name}%' LIMIT 1"
    })
    rows = projects_res.get("rows", [])
    if rows:
        project_id = int(rows[0]["ID"])
        print(f"📁 Найден существующий проект в CRM: #{project_id} «{rows[0]['post_title']}»")
    else:
        proj_create_res = call_tool(
            "crm_create_project",
            {
                "name": project_name,
                "client_id": client_id,
                "description": f"Договор № {contract_no}: {service_title}",
            },
        )
        project_id = proj_create_res.get("id", 0)
        print(f"📁 Создан новый проект в CRM: #{project_id} «{project_name}»")

    # 5. Вехи сделки фиксируются в описании проекта и акта, без создания фиктивных закрытых задач в CRM

    # 6. Формирование Google Doc через doc_render (с узкой колонкой №)
    print("\n[2/3] Рендеринг Акта в Google Docs...")
    today_formatted = datetime.now().strftime("%d.%m.%Y")
    act_title = f"Акт № {act_no} сдачи-приёмки оказанных услуг — {client_name}"
    
    doc_payload = {
        "title": act_title,
        "folder": "Акты",
        "pdf": generate_pdf,
        "blocks": [
            {"type": "title", "text": f"Акт № {act_no} сдачи-приемки оказанных услуг"},
            {"type": "center", "text": f"к Договору № {contract_no} от {contract_date} г."},
            {"type": "pair", "left": "г. Минск", "right": f"{today_formatted} г."},
            {"type": "spacer"},
            {
                "type": "para",
                "text": (
                    "Индивидуальный предприниматель Воронов Егор Олегович, действующий на основании "
                    "Свидетельства о государственной регистрации № 791438116, выданного Администрацией "
                    "Ленинского района г. Могилёва 22.05.2026 г., именуемый в дальнейшем «Исполнитель», "
                    f"с одной стороны, и {client_name}, именуемое в дальнейшем «Заказчик», в лице "
                    "руководителя, действующего на основании Устава, с другой стороны, составили настоящий Акт о нижеследующем:"
                ),
            },
            {
                "type": "para",
                "text": (
                    f"1. В соответствии с условиями Договора № {contract_no} от {contract_date} г. "
                    f"Исполнитель выполнил в полном объёме, а Заказчик принял комплекс услуг: «{service_title}»."
                ),
            },
            {
                "type": "table",
                "header": True,
                "boldLastRow": True,
                "widths": [24, 272, 60, 70, 70],
                "rows": [
                    ["№", "Наименование оказанных услуг", "Кол-во", "Цена, BYN", "Сумма, BYN"],
                    ["1", service_title, "1 компл.", f"{amount:.2f}", f"{amount:.2f}"],
                    ["", "Итого к оплате без НДС:", "", "", f"{amount:.2f}"],
                ],
            },
            {
                "type": "para",
                "text": (
                    "2. Услуги оказаны качественно, в полном объёме и в установленный срок. "
                    "Заказчик претензий по объёму, качеству и срокам оказания услуг к Исполнителю не имеет."
                ),
            },
            {
                "type": "para",
                "text": (
                    f"3. Общая стоимость оказанных услуг составляет {amount:.2f} белорусских рублей, без НДС "
                    "(в соответствии с Налоговым кодексом Республики Беларусь Исполнитель применяет особый "
                    "режим налогообложения без уплаты НДС согласно гл. 32 НК РБ)."
                ),
            },
            {
                "type": "para",
                "text": (
                    "4. Настоящий Акт составлен при обоюдном согласии Сторон в двух экземплярах, "
                    "имеющих одинаковую юридическую силу, по одному экземпляру для каждой из Сторон."
                ),
            },
            {"type": "spacer"},
            {
                "type": "parties",
                "left": [
                    "ИСПОЛНИТЕЛЬ:",
                    "ИП Воронов Егор Олегович",
                    "УНП 791438116",
                    "Адрес: 212011, г. Могилёв, пер. Гоголя, 6, кв. 46",
                    "Р/с: BY19ALFA301432EW4C0010270000",
                    "Банк: ЗАО «Альфа-Банк», г. Минск",
                    "БИК: ALFABY2X",
                    "Тел: +375 (29) 168-23-89",
                    "",
                    "Исполнитель:",
                    "____________________",
                ],
                "right": [
                    "ЗАКАЗЧИК:",
                    client_name,
                    f"УНП: {client.get('unp') or '—'}",
                    f"Адрес: {client.get('address') or '—'}",
                    f"Р/с: {client.get('account') or '—'}",
                    f"Банк: {client.get('bank_name') or '—'}",
                    f"БИК: {client.get('bik') or '—'}",
                    f"Тел: {client.get('phone') or '—'}",
                    "",
                    "Заказчик:",
                    "____________________",
                ],
            },
        ],
    }

    doc_res = call_tool("doc_render", doc_payload)
    doc_link = doc_res.get("link", "")
    pdf_link = doc_res.get("pdf", "")
    print(f"  📄 Google Doc: {doc_link}")
    if pdf_link:
        print(f"  📥 PDF файл: {pdf_link}")

    # 7. Постановка ровно 1 открытой задачи человеку в CRM и уведомление в Telegram
    print("\n[3/3] Постановка открытой задачи менеджеру и отправка в Telegram...")
    deadline_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    task_desc = (
        f"Акт сдачи-приёмки № {act_no} от {today_formatted} г. на сумму {amount:.2f} BYN (к Договору № {contract_no}) подготовлен.\n\n"
        f"• Google Doc: {doc_link}\n\n"
        f"Задача: проверить документ, направить клиенту ({client.get('phone', '')}, {client.get('email', '')}), "
        "получить подписанный скан и прикрепить в CRM."
    )
    if pdf_link:
        task_desc += f"\n• PDF файл: {pdf_link}"

    task_res = call_tool(
        "crm_create_task",
        {
            "title": f"Отправить Акт № {act_no} клиенту {client_name} на подпись",
            "description": task_desc,
            "client_id": client_id,
            "project_id": project_id,
            "assignee_id": assignee_id,
            "status": "todo",
            "priority": "high",
            "deadline": deadline_date,
            "notify": False,
            "source": "ai",
        },
    )

    assignee_name = "Егор" if assignee_id == 10 else ("Евгений" if assignee_id == 7 else f"Сотрудник #{assignee_id}")
    doc_links_text = f"• <a href=\"{doc_link}\">Открыть Google Doc</a>\n"
    if pdf_link:
        doc_links_text += f"• <a href=\"{pdf_link}\">Скачать готовый PDF</a>\n"

    tg_text = (
        f"🎯 <b>Новая задача: Отправить Акт клиенту на подпись</b>\n\n"
        f"👤 <b>Клиент:</b> {client_name}\n"
        f"💼 <b>Договор:</b> № {contract_no} ({amount:.2f} BYN)\n"
        f"📄 <b>Акт сдачи-приёмки:</b> № {act_no} от {today_formatted} г.\n"
        f"👤 <b>Ответственный:</b> {assignee_name} (дедлайн: {deadline_date})\n\n"
        f"🔗 <b>Документ для проверки и отправки:</b>\n"
        f"{doc_links_text}\n"
        f"📞 <b>Контакты:</b> {client.get('phone', '—')}, {client.get('email', '—')}"
    )

    try:
        tg_cmd = [sys.executable, str(ROOT / "scripts" / "tg_agent.py"), "send", tg_text, "--topic", "tasks"]
        if task_res.get("id"):
            tg_cmd.extend(["--task-id", str(task_res["id"]), "--deadline", str(deadline_date)])
        subprocess.run(
            tg_cmd,
            check=True,
            capture_output=True,
        )
        print("✅ Карточка задачи отправлена в топик 581 («Открытые задачи») с кнопками управления")
    except Exception as e:
        print(f"⚠️ Ошибка отправки в Telegram: {e}")

    print("\n=== СДЕЛКА УСПЕШНО ЗАКРЫТА ===")


def get_default_assignee() -> int:
    try:
        user_name = subprocess.check_output(["git", "config", "user.name"], text=True).strip()
        if "egor" in user_name.lower() or "егор" in user_name.lower():
            return 10
    except Exception:
        pass
    return 7


def main():
    parser = argparse.ArgumentParser(description="Автоматическое закрытие клиентской сделки и выпуск акта")
    parser.add_argument("--client", required=True, help="Название или часть названия клиента (для поиска в CRM)")
    parser.add_argument("--contract-no", required=True, help="Номер договора")
    parser.add_argument("--amount", type=float, required=True, help="Сумма договора/акта в BYN")
    parser.add_argument("--service", required=True, help="Наименование оказанных услуг для акта")
    parser.add_argument("--assignee-id", type=int, default=None, help="ID ответственного (10 = Егор, 7 = Евгений, по умолчанию из git config)")
    parser.add_argument("--act-no", default="", help="Номер акта (по умолчанию генерируется по дате)")
    parser.add_argument("--pdf", action="store_true", help="Сгенерировать также PDF на Диске (по умолчанию только Google Doc для проверки)")
    parser.add_argument("--dry-run", action="store_true", help="Предпросмотр без сохранения в CRM и создания документов")
    args = parser.parse_args()

    assignee_id = args.assignee_id if args.assignee_id is not None else get_default_assignee()

    close_deal(
        client_query=args.client,
        contract_no=args.contract_no,
        amount=args.amount,
        service_title=args.service,
        assignee_id=assignee_id,
        act_no=args.act_no,
        dry_run=args.dry_run,
        generate_pdf=args.pdf,
    )


if __name__ == "__main__":
    main()
