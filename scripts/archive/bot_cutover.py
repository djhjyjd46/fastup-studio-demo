#!/usr/bin/env python3
"""Переключение Алеси (@FastupAgent_bot) с VPS на хостинг tools.fastup.by и откат.

Запускает Егор в своём терминале: скрипт ходит на VPS по SSH-ключу и меняет webhook бота.

    python scripts/bot_cutover.py pull          # забрать с VPS состояние бота и нужные переменные
    python scripts/bot_cutover.py webhook-on    # бот на хостинг; роутер на VPS останавливается
    python scripts/bot_cutover.py webhook-off   # ОТКАТ: webhook снят, роутер на VPS снова слушает
    python scripts/bot_cutover.py status        # что сейчас у Telegram: url, очередь, последняя ошибка

Порядок первого переключения:
    pull → (deploy_tools_server.py) secrets, state, upload, start, check → webhook-on → status
Вкладка «Ассистент» и ИИ-ПМ переключаются отдельно: в WP опции microapps_agent_vps_url и
microapps_agent_vps_secret (значение — AGENT_SECRET из secrets/tools-server.json).

Секреты в вывод не печатаются. Всё забранное лежит в secrets/bot/ (в .gitignore).
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_load import load_env  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VPS = "root@5.35.91.122"
SSH_KEY = Path.home() / ".ssh" / "id_ed25519_agentvps"
INGEST = "/opt/microapps/ingest"
BOT_DIR = ROOT / "secrets" / "bot"
STATE_DIR = BOT_DIR / "state"
SERVER_SECRETS_FILE = ROOT / "secrets" / "tools-server.json"
APP_DIR = Path(r"G:\OSPanel\domains\admin.microapps\agent\crm-mcp")
WEBHOOK_URL = "https://tools.fastup.by/tg/webhook"
ALLOWED_UPDATES = ["message", "edited_message", "callback_query", "my_chat_member", "business_connection", "business_message"]
ENV_KEYS = ("WP_WEBHOOK_URL", "WP_WEBHOOK_SECRET", "TG_LOG_URL", "TG_LOG_SECRET", "DEFAULT_MODE", "MODE_FILE", "BIZ_CONN_FILE")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def ssh(command, capture=True):
    result = subprocess.run(
        ["ssh", "-i", str(SSH_KEY), "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", VPS, command],
        capture_output=capture, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        sys.exit(f"ssh: код {result.returncode}: {(result.stderr or '').strip()[:200]}")
    return result.stdout


def remote_path(value, default):
    path = (value or default).strip()
    return path if path.startswith("/") else f"{INGEST}/{path.lstrip('./')}"


def pull():
    BOT_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    env = {}
    for line in ssh(f"cat {INGEST}/.env").splitlines():
        key, _, value = line.partition("=")
        if key.strip() in ENV_KEYS:
            env[key.strip()] = value.strip()
    (BOT_DIR / "ingest.env").write_text("".join(f"{k}={v}\n" for k, v in env.items() if k in ENV_KEYS[:5]), encoding="utf-8")
    print(f"ingest.env: ключи {', '.join(k for k in ENV_KEYS[:5] if k in env)}")

    files = {
        "modes.json": remote_path(env.get("MODE_FILE"), "modes.json"),
        "biz-connections.json": remote_path(env.get("BIZ_CONN_FILE"), "biz-connections.json"),
        "qa-pending.json": f"{INGEST}/data/qa-pending.json",
        "voice-usage.json": f"{INGEST}/data/voice-usage.json",
        "playbook.json": "/opt/microapps/crm-mcp/playbook.json",
    }
    for name, path in files.items():
        content = subprocess.run(
            ["ssh", "-i", str(SSH_KEY), "-o", "BatchMode=yes", VPS, f"test -f {path} && cat {path}"],
            capture_output=True, text=True, encoding="utf-8",
        )
        if content.returncode != 0 or not content.stdout.strip():
            print(f"{name}: на VPS нет ({path}) — начнётся с пустого")
            continue
        json.loads(content.stdout)  # битый JSON не везём
        (STATE_DIR / name).write_text(content.stdout, encoding="utf-8")
        print(f"{name}: забран")

    playbook = STATE_DIR / "playbook.json"
    if playbook.exists():
        load_env()
        if not os.environ.get("ROUTERAI_API_KEY"):
            sys.exit("нет ROUTERAI_API_KEY в .env — индекс базы знаний не пересобрать")
        subprocess.run(["node", "build-kb-index.mjs"], cwd=APP_DIR, check=True,
                       env={**os.environ, "PLAYBOOK": str(playbook)})
        print("индекс базы знаний пересобран из боевого playbook.json")
    print("дальше: python scripts/deploy_tools_server.py secrets, затем state, upload, start, check")


def bot_api(method, payload=None):
    load_env()
    token = os.environ.get("FASTUP_AGENT_BOT_TOKEN", "").strip()
    if not token:
        sys.exit("нет FASTUP_AGENT_BOT_TOKEN в .env")
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}",
                                 data=json.dumps(payload or {}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    if not data.get("ok"):
        sys.exit(f"{method}: {data.get('description')}")
    return data.get("result")


def webhook_on():
    if not SERVER_SECRETS_FILE.exists():
        sys.exit("нет secrets/tools-server.json — сначала deploy_tools_server.py secrets")
    secret = json.loads(SERVER_SECRETS_FILE.read_text(encoding="utf-8"))["TG_WEBHOOK_SECRET"]
    # Проверка, что хостинг принимает апдейты, до переключения: без секрета — 403, не 404/502.
    try:
        urllib.request.urlopen(urllib.request.Request(WEBHOOK_URL, data=b"{}", headers={"Content-Type": "application/json"}), timeout=20)
    except urllib.error.HTTPError as error:
        if error.code != 403:
            sys.exit(f"{WEBHOOK_URL} отвечает {error.code}, ожидался 403 — бот на хостинге не включён, переключать рано")
    ssh("systemctl stop agent-tgrouter && systemctl is-active agent-tgrouter || true")
    print("VPS: agent-tgrouter остановлен")
    bot_api("setWebhook", {"url": WEBHOOK_URL, "secret_token": secret, "allowed_updates": ALLOWED_UPDATES, "max_connections": 10})
    print(f"webhook установлен: {WEBHOOK_URL}")
    status()


def webhook_off():
    bot_api("deleteWebhook", {"drop_pending_updates": False})
    print("webhook снят")
    ssh("systemctl start agent-tgrouter && systemctl is-active agent-tgrouter")
    print("VPS: agent-tgrouter запущен — бот снова на VPS")


def status():
    info = bot_api("getWebhookInfo")
    print(json.dumps({k: info.get(k) for k in ("url", "pending_update_count", "last_error_date", "last_error_message", "allowed_updates")},
                     ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["pull", "webhook-on", "webhook-off", "status"])
    args = parser.parse_args()
    {"pull": pull, "webhook-on": webhook_on, "webhook-off": webhook_off, "status": status}[args.step]()


if __name__ == "__main__":
    main()
