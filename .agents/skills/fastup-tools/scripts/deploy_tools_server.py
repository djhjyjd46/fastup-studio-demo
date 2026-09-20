#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Выкладка MCP-сервера инструментов (agent/crm-mcp) на Node.js-сайт tools.fastup.by (hb.by).

Сервер заменяет инструменты агента на VPS: Antigravity и Claude Code подключаются к нему по
HTTPS с личным токеном. Код — репозиторий admin-microapps, `agent/crm-mcp` (собрать `npm run build`).

Шаги (каждый можно запустить отдельно):
    python scripts/deploy_tools_server.py discover      # формы функций Node.js в панели, без записи
    python scripts/deploy_tools_server.py site          # создать сайт, если его нет
    python scripts/deploy_tools_server.py secrets       # ~/secrets/tools.env и индекс базы знаний
    python scripts/deploy_tools_server.py upload        # package.json, lock, dist/*.js
    python scripts/deploy_tools_server.py start         # npm install + перезапуск
    python scripts/deploy_tools_server.py check         # healthz, 401 без токена, список тулов

Секреты:
- из `.env`: HOSTING_* (панель), TOOLS_CRM_APP_PASSWORD (пароль приложения `tools-hosting`
  пользователя ai-agent), ROUTERAI_API_KEY (эмбеддинги kb_search);
- личные токены генерируются один раз и лежат в `secrets/tools-tokens.json` (gitignored);
  на сервер уходят только их sha256.
Пароли в вывод не печатаются.
"""
import argparse
import hashlib
import json
import secrets as pysecrets
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_static_file import DeployError, Panel, _from_env, normalize_newlines, replace_file  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = Path(r"G:\OSPanel\domains\admin.microapps\agent\crm-mcp")
SITE = "tools.fastup.by"
SITE_DIR = f"www/{SITE}"
SECRETS_DIR = "secrets"  # от домашнего каталога пользователя, вне www
HOME_DIR = "/var/www/u43541-2796/data"  # домашний каталог пользователя панели (корень путей API)
TOKENS_FILE = ROOT / "secrets" / "tools-tokens.json"
KB_INDEX_LOCAL = APP_DIR / "data" / "playbook.index.json"
KNOWLEDGE_DIR = APP_DIR.parent / "knowledge"
SERVER_SECRETS_FILE = ROOT / "secrets" / "tools-server.json"  # AGENT_SECRET, TG_WEBHOOK_SECRET
BOT_STATE_LOCAL = ROOT / "secrets" / "bot" / "state"  # забирает bot_cutover.py pull
BOT_ENV_LOCAL = ROOT / "secrets" / "bot" / "ingest.env"  # WP_WEBHOOK_*, TG_LOG_*, DEFAULT_MODE с VPS
NODE_VERSION = "24.21.0"
# Кто получает токен и с каким профилем инструментов crm-mcp (full | ceo).
PEOPLE = {"egor": "full", "evgeniy": "ceo"}


def doc(result):
    return result.get("doc", {}) if isinstance(result, dict) else {}


def discover(panel):
    """Поля форм Node.js-функций: вызов без sok=ok ничего не меняет, панель отдаёт описание формы."""
    for func in ("site.nodejs.params", "webdomain.nodejs.restart", "webdomain.nodejs.npm.install"):
        try:
            d = doc(json.loads(panel.request(func, {"elid": SITE})[0]))
        except (DeployError, ValueError) as error:
            print(f"== {func}: {error}")
            continue
        if "error" in d:
            print(f"== {func}: error {json.dumps(d['error'], ensure_ascii=False)[:160]}")
            continue
        fields = {k: (v.get("$") if isinstance(v, dict) else v) for k, v in d.items()
                  if k not in ("messages", "metadata", "tparams", "slist") and not k.startswith("$")}
        print(f"== {func}: {json.dumps(fields, ensure_ascii=False)[:600]}")


def root_entries(panel):
    """Листинг домашнего каталога: `file` без plid. list_dir так не умеет — пустой путь он отвергает."""
    elems = doc(panel.call("file", {})).get("elem", [])
    elems = elems if isinstance(elems, list) else [elems]
    return {(e.get("name") or {}).get("$"): (e.get("type") or {}).get("$") for e in elems}


def ensure_dir(panel, parent, name):
    """Каталог name в parent ("" — домашний). Тип в file.new задаётся filetype=1, не type=dir.

    Пустой файл с тем же именем — след прошлого неудачного запуска (создавался файл вместо
    каталога); его убираем, непустой — не трогаем и останавливаемся.
    """
    if parent:
        entries = {}
        for e in doc(panel.call("file", {"plid": parent})).get("elem", []):
            entries[(e.get("name") or {}).get("$")] = ((e.get("type") or {}).get("$"), (e.get("size") or {}).get("$"))
        kind, size = entries.get(name, (None, None))
    else:
        kind, size = root_entries(panel).get(name), None
    if kind == "dir":
        return
    if kind is not None:
        if parent and size in ("0 B", "0"):
            panel.call_ok("file.delete", {"plid": parent, "elid": name, "sok": "ok"})
        else:
            raise DeployError(f"На месте каталога {parent}/{name} лежит файл — разберись руками")
    params = {"name": name, "filetype": "1", "sok": "ok"}
    if parent:
        params["plid"] = parent
    panel.call_ok("file.new", params)


def site_exists(panel):
    elems = doc(panel.call("webdomain", {})).get("elem", [])
    return any((e.get("name") or {}).get("$") == SITE for e in (elems if isinstance(elems, list) else [elems]))


def create_site(panel):
    if site_exists(panel):
        print(f"{SITE}: уже есть")
        return
    panel.call_ok("webdomain.edit", {
        "name": SITE,
        "ipsrc": "auto",
        "php": "off",
        "nodejs": "on",
        "nodejs_version": NODE_VERSION,
        "nodejs_server": "dist/index.js",
        "nodejs_use_port": "on",
        "secure": "on",
        "ssl_cert": "letsencrypt",
        "redirect_http": "on",
        "emailcreate": "off",
        "sok": "ok",
    })
    print(f"{SITE}: создан (Node.js {NODE_VERSION}, SSL Let's Encrypt)")


def load_tokens():
    """Личные токены: создаются один раз, дальше переиспользуются."""
    if TOKENS_FILE.exists():
        tokens = json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
    else:
        tokens = {}
    changed = False
    for name in PEOPLE:
        if name not in tokens:
            tokens[name] = "fut_" + pysecrets.token_urlsafe(32)
            changed = True
    if changed:
        TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKENS_FILE.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
        print(f"токены сохранены локально: {TOKENS_FILE}")
    return tokens


def server_secrets():
    """Секреты самого сервера: создаются один раз и переиспользуются (WP и Telegram знают их значения)."""
    data = json.loads(SERVER_SECRETS_FILE.read_text(encoding="utf-8")) if SERVER_SECRETS_FILE.exists() else {}
    changed = False
    for key in ("AGENT_SECRET", "TG_WEBHOOK_SECRET"):
        if key not in data:
            data[key] = pysecrets.token_hex(32)
            changed = True
    if changed:
        SERVER_SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SERVER_SECRETS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def agent_env_lines():
    """Переменные агента (чат «Ассистент», ИИ-ПМ) и Алеси. Бот включается, только если есть
    забранный с VPS ingest.env — без WP_WEBHOOK_* кнопки задач и лидов перестали бы работать."""
    secrets_ = server_secrets()
    lines = [
        f"AGENT_SECRET={secrets_['AGENT_SECRET']}",
        f"STATE_DIR={HOME_DIR}/bot-state",
        f"PLAYBOOK_FILE={HOME_DIR}/{SECRETS_DIR}/playbook.json",
        f"INBOX_DIR={HOME_DIR}/documents_inbox",
    ]
    for key in ("GDOCS_GAS_URL", "GDOCS_GAS_SECRET", "GDRIVE_FOLDER_ID"):
        value = _from_env(key)
        if value:
            lines.append(f"{key}={value}")
    bot_token = _from_env("FASTUP_AGENT_BOT_TOKEN")
    if BOT_ENV_LOCAL.exists() and bot_token:
        lines += [f"BOT_TOKEN={bot_token}", f"TG_WEBHOOK_SECRET={secrets_['TG_WEBHOOK_SECRET']}"]
        for raw in BOT_ENV_LOCAL.read_text(encoding="utf-8").splitlines():
            key = raw.partition("=")[0].strip()
            if key in ("WP_WEBHOOK_URL", "WP_WEBHOOK_SECRET", "TG_LOG_URL", "TG_LOG_SECRET", "DEFAULT_MODE"):
                lines.append(raw.strip())
        print("Алеся: переменные бота добавлены")
    else:
        print("Алеся: бот пока выключен (нет secrets/bot/ingest.env или FASTUP_AGENT_BOT_TOKEN)")
    return lines


KB_REPLACE = False  # --kb: заменить живую базу знаний на сервере локальной копией


def current_server_value(panel, key):
    """Значение из текущего ~/secrets/tools.env на сервере (или None). Сам файл не печатается."""
    try:
        if not panel.exists(f"{SECRETS_DIR}/tools.env"):
            return None
        text = panel.read_file(f"{SECRETS_DIR}/tools.env").decode("utf-8", "replace")
    except DeployError:
        return None
    for line in text.splitlines():
        name, _, value = line.partition("=")
        if name.strip() == key and value.strip():
            return value.strip()
    return None


def write_secrets(panel):
    password = _from_env("TOOLS_CRM_APP_PASSWORD")
    routerai = _from_env("ROUTERAI_API_KEY")
    if not password:
        raise DeployError("Нет TOOLS_CRM_APP_PASSWORD в .env (пароль приложения tools-hosting у ai-agent)")
    tokens = load_tokens()
    hashes = ",".join(f"{name}:{PEOPLE[name]}:{hashlib.sha256(tokens[name].encode()).hexdigest()}" for name in PEOPLE)
    lines = [
        "# tools.fastup.by — секреты MCP-сервера. Генерируется scripts/deploy_tools_server.py",
        "CRM_BASE_URL=https://admin.microapps.by",
        "CRM_USER=ai-agent",
        f"CRM_APP_PASSWORD={password}",
        "MCP_TRANSPORT=http",
        "MCP_AUTH=token",
        f"MCP_TOKENS={hashes}",
    ]
    if routerai:
        lines.append(f"ROUTERAI_API_KEY={routerai}")
    lines += agent_env_lines()
    ensure_dir(panel, "", SECRETS_DIR)
    # Индекс (~1,2 МБ) больше FileMaxEditSize: существующий файл такого размера панель
    # перезаписать через file.edit не даёт, новый — создаёт. Поэтому каждая версия — новый
    # файл с хэшем содержимого в имени; tools.env указывает на актуальную.
    #
    # ЖИВАЯ БАЗА: после kb_add/kb_update/kb_delete и петли 606 правда — индекс на сервере,
    # локальный устарел. Без --kb сохраняем путь к индексу из текущего tools.env сервера.
    live_index = current_server_value(panel, "KB_INDEX_FILE")
    if live_index and not KB_REPLACE:
        lines.append(f"KB_INDEX_FILE={live_index}")
        print(f"индекс базы знаний: оставлен живой {live_index.rsplit('/', 1)[-1]} (заменить — флаг --kb)")
    elif KB_INDEX_LOCAL.exists():
        content = KB_INDEX_LOCAL.read_bytes()
        name = f"playbook.index.{hashlib.sha256(content).hexdigest()[:12]}.json"
        if panel.exists(f"{SECRETS_DIR}/{name}"):
            print(f"индекс базы знаний уже на сервере: {name}")
        else:
            panel.create_file(f"{SECRETS_DIR}/{name}")
            panel.write_file(f"{SECRETS_DIR}/{name}", content)
            print(f"индекс базы знаний залит: {name}")
        lines.append(f"KB_INDEX_FILE={HOME_DIR}/{SECRETS_DIR}/{name}")
    else:
        print("индекс базы знаний не собран локально — kb_search работать не будет")
    # Секреты не бэкапим на диск сессии — только факт записи.
    replace_file(panel, f"{SECRETS_DIR}/tools.env", ("\n".join(lines) + "\n").encode("utf-8"), backup=False)
    print(f"{SECRETS_DIR}/tools.env записан (токены: {', '.join(f'{n}({p})' for n, p in PEOPLE.items())})")


def upload(panel):
    """Код (dist/**) и персона агента (agent/knowledge: *.md и memory/*.md) — в папку сайта."""
    if not (APP_DIR / "dist" / "index.js").exists():
        raise DeployError("Нет dist/index.js — сначала npm run build в agent/crm-mcp")
    files = [(APP_DIR / "package.json", "package.json"), (APP_DIR / "package-lock.json", "package-lock.json")]
    files += [(p, p.relative_to(APP_DIR).as_posix()) for p in sorted((APP_DIR / "dist").rglob("*.js"))]
    files += [(p, "knowledge/" + p.relative_to(KNOWLEDGE_DIR).as_posix())
              for p in sorted(KNOWLEDGE_DIR.glob("*.md")) + sorted((KNOWLEDGE_DIR / "memory").glob("*.md"))
              if p.name != "README.md"]
    made = set()
    for _, rel in files:
        parts = rel.split("/")[:-1]
        for depth in range(len(parts)):
            parent = "/".join([SITE_DIR, *parts[:depth]])
            if (parent, parts[depth]) not in made:
                ensure_dir(panel, parent, parts[depth])
                made.add((parent, parts[depth]))
    for local, rel in files:
        result = replace_file(panel, f"{SITE_DIR}/{rel}", normalize_newlines(local.read_bytes()))
        state = "создан" if result.get("created") else "без изменений" if result.get("unchanged") else "обновлён"
        print(f"  {rel}: {state}")


def upload_state(panel):
    """Состояние Алеси, забранное с VPS (`bot_cutover.py pull`): режимы чатов, очередь 606,
    лимит голосовых, Business-подключения, playbook.json. Без сверки чтением — файлы меняются ботом."""
    if not BOT_STATE_LOCAL.exists():
        raise DeployError(f"Нет {BOT_STATE_LOCAL} — сначала python scripts/bot_cutover.py pull")
    ensure_dir(panel, "", "bot-state")
    for local in sorted(BOT_STATE_LOCAL.glob("*.json")):
        if local.name == "playbook.json" and not KB_REPLACE:
            print("  playbook.json пропущен: на сервере живая база (заменить — флаг --kb)")
            continue
        target = f"{SECRETS_DIR}/playbook.json" if local.name == "playbook.json" else f"bot-state/{local.name}"
        replace_file(panel, target, local.read_bytes(), backup=False)
        print(f"  {local.name} → {target}")


def run_action(panel, func):
    """Действия Node.js в панели фоновые: ответ бывает без doc.ok, хотя задача запущена.
    Ошибкой считаем только doc.error; итог проверяет шаг check."""
    d = doc(json.loads(panel.request(func, {"elid": SITE, "sok": "ok"})[0]))
    if "error" in d:
        raise DeployError(f"{func}: {json.dumps(d['error'], ensure_ascii=False)[:200]}")
    print(f"{func}: запущено" + ("" if "ok" in d else " (панель не вернула ok — проверить check)"))


def start(panel):
    run_action(panel, "webdomain.nodejs.npm.install")
    run_action(panel, "webdomain.nodejs.restart")


def restart(panel):
    run_action(panel, "webdomain.nodejs.restart")


def check():
    base = f"https://{SITE}"
    ctx = ssl.create_default_context()

    def post(token, payload):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                   "User-Agent": "Mozilla/5.0 (compatible; FastUp-Deploy/2.0)"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(f"{base}/mcp", data=json.dumps(payload).encode(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, ""

    try:
        req = urllib.request.Request(f"{base}/healthz", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            print("healthz:", r.status, r.read().decode()[:100])
    except Exception as error:  # сеть, TLS, 502 от nginx — всё это ответ на вопрос «живо ли»
        print("healthz: не отвечает —", str(error)[:150])
        return
    print("без токена:", post(None, {})[0])
    tokens = load_tokens()
    listing = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    for name in PEOPLE:
        status, body = post(tokens[name], listing)
        data = next((l[5:].strip() for l in body.splitlines() if l.startswith("data:")), body)
        try:
            count = len(json.loads(data)["result"]["tools"])
        except (ValueError, KeyError, TypeError):
            count = "?"
        print(f"{name}: HTTP {status}, инструментов {count}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["discover", "site", "secrets", "upload", "state", "start", "restart", "check"])
    parser.add_argument("--kb", action="store_true",
                        help="заменить живую базу знаний на сервере локальной копией (затрёт правки kb_* и ответы из 606)")
    args = parser.parse_args()
    global KB_REPLACE
    KB_REPLACE = args.kb
    try:
        if args.step == "check":
            check()
            return
        panel = Panel()
        {"discover": discover, "site": create_site, "secrets": write_secrets,
         "upload": upload, "state": upload_state, "start": start, "restart": restart}[args.step](panel)
    except DeployError as error:
        sys.exit(f"ошибка: {error}")


if __name__ == "__main__":
    main()
