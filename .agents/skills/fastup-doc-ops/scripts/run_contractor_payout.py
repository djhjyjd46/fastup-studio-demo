
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
from datetime import datetime
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


def find_contractor(name_query: str) -> dict:
    res = call_tool("crm_search_requisites", {"query": name_query})
    items = res if isinstance(res, list) else res.get("items", [])
    if not items:
        raise ValueError(f"Подрядчик «{name_query}» не найден в CRM.")
    
    q_lower = name_query.lower()
    matched = [i for i in items if q_lower in (i.get("name") or "").lower()]
    return matched[0] if matched else items[0]


def get_leadgen_stats(contractor_name: str) -> dict:
    try:
        report = call_tool("crm_leadgen_report", {})
        managers = report.get("managers", [])
        q = contractor_name.lower()
        for m in managers:
            full = (m.get("full_name") or "").lower()
            name = (m.get("name") or "").lower()
            if q in full or q in name:
                return m
    except Exception:
        pass
    return {}


def run_payout(
    contractor_query: str,
    profile: str,
    period_from: str,
    period_to: str,
    confirm: bool = False,
    override_sum: float = None,
):
    print(f"=== РАСЧЁТ С ПОДРЯДЧИКОМ: {contractor_query} ===")
    
    # 1. Поиск реквизитов
    c = find_contractor(contractor_query)
    req_id = c.get("id")
    c_name = c.get("name")
    unp = c.get("unp")
    print(f"👤 Подрядчик: {c_name} (ID {req_id}, УНП {unp})")
    print(f"📅 Отчётный период: с {period_from} по {period_to}")
    print(f"💼 Профиль акта: {profile.upper()}")

    # 2. Сбор статистики / расчет вознаграждения
    works = []
    payments = []
    
    if profile == "leadgen":
        stats = get_leadgen_stats(c_name)
        p_stats = stats.get("period_stats", {})
        payable_leads = p_stats.get("payable", 0)
        processed = p_stats.get("processed", 0)
        
        # Если задана сумма вручную или взята из статистики
        if override_sum is not None:
            sum_val = override_sum
            works.append({"name": f"Информационное сопровождение и квалификация лидов ({period_from} — {period_to})"})
            payments.append({"label": "Вознаграждение за результат валидации лидов", "amount": sum_val})
        else:
            lead_rate = 5.0  # Базовая ставка за лид
            calculated = payable_leads * lead_rate
            sum_val = max(calculated, 50.0) if payable_leads == 0 else calculated
            works.append({"name": f"Обработка базы ({processed} контактов) и квалификация {payable_leads} целевых лидов"})
            payments.append({"label": f"Оплата за результат валидации лидов ({payable_leads} лидов по {lead_rate:.2f} BYN)", "amount": sum_val})

        print(f"📊 Статистика звонилки: обработано {processed}, принято к оплате: {payable_leads} лидов")
        print(f"💰 Итого к начислению: {sum_val:.2f} BYN")

    elif profile == "pm":
        sum_val = override_sum if override_sum is not None else 330.0
        works.append({"name": f"Комплекс услуг по координации проектов и администрированию CRM ({period_from} — {period_to})"})
        payments.append({"label": "Базовое вознаграждение за администрирование проектов", "amount": sum_val})
        print(f"💰 Итого к начислению: {sum_val:.2f} BYN")

    elif profile == "dev":
        sum_val = override_sum if override_sum is not None else 200.0
        works.append({"name": f"Услуги по разработке и визуальной вёрстке компонентов ({period_from} — {period_to})"})
        payments.append({"label": "Вознаграждение за этап разработки", "amount": sum_val})
        print(f"💰 Итого к начислению: {sum_val:.2f} BYN")

    # 3. Вызов act_create с dry_run
    dry_payload = {
        "profile": profile,
        "requisite_id": req_id,
        "period_from": period_from,
        "period_to": period_to,
        "works": works,
        "payments": payments,
        "dry_run": True,
    }

    print("\n[1/2] Предварительный расчёт и аудит соответствия ст. 33 НК РБ...")
    dry_res = call_tool("act_create", dry_payload)
    
    if not confirm:
        print("\n--- ПРЕДПРОСМОТР АКТА (DRY-RUN) ---")
        print(f"Исполнитель: {dry_res.get('executor')}")
        print(f"Сумма: {dry_res.get('total')} ({dry_res.get('total_words')})")
        print(f"Договор: {dry_res.get('contract')}")
        print("\nДля фактического выпуска акта в Google Docs/PDF и регистрации проводки запустите с флагом --confirm")
        return

    # 4. Фактический выпуск акта
    print("\n[2/2] Выпуск оригинального Акта и PDF...")
    real_payload = {**dry_payload, "dry_run": False, "pdf": True}
    real_res = call_tool("act_create", real_payload)

    doc_link = real_res.get("link", "")
    pdf_link = real_res.get("pdf", "")
    act_no = real_res.get("doc_no", "")
    print(f"✅ Акт № {act_no} успешно создан!")
    print(f"  📄 Google Doc: {doc_link}")
    print(f"  📥 PDF в папку печати: {pdf_link}")

    # 5. Уведомление в Telegram топик задач/служебный
    tg_text = (
        f"📑 <b>Готов Акт с подрядчиком: {c_name}</b>\n\n"
        f"👤 <b>Исполнитель:</b> {c_name} ({profile.upper()})\n"
        f"📅 <b>Период:</b> {period_from} — {period_to}\n"
        f"💰 <b>К выплате:</b> {sum_val:.2f} BYN\n"
        f"📄 <b>Акт:</b> № {act_no}\n\n"
        f"🔗 <a href=\"{pdf_link}\">Открыть PDF для печати/подписи</a>"
    )

    try:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "tg_agent.py"), "send", tg_text, "--topic", "tasks"],
            check=True,
            capture_output=True,
        )
        print("✅ Уведомление отправлено в Telegram")
    except Exception as e:
        print(f"⚠️ Ошибка отправки TG: {e}")

    print("\n=== РАСЧЁТ УСПЕШНО ЗАВЕРШЁН ===")


def main():
    parser = argparse.ArgumentParser(description="Автоматический расчёт с подрядчиками FastUp Studio")
    parser.add_argument("--contractor", required=True, help="Фамилия или имя подрядчика в CRM")
    parser.add_argument("--profile", choices=["leadgen", "pm", "dev"], default="leadgen", help="Профиль акта")
    parser.add_argument("--period-from", required=True, help="Дата начала периода (ГГГГ-ММ-ДД)")
    parser.add_argument("--period-to", required=True, help="Дата конца периода (ГГГГ-ММ-ДД)")
    parser.add_argument("--sum", type=float, default=None, help="Переопределить итоговую сумму в BYN")
    parser.add_argument("--confirm", action="store_true", help="Фактически создать документ и PDF (без этого только dry-run)")
    args = parser.parse_args()

    run_payout(
        contractor_query=args.contractor,
        profile=args.profile,
        period_from=args.period_from,
        period_to=args.period_to,
        confirm=args.confirm,
        override_sum=args.sum,
    )


if __name__ == "__main__":
    main()
