#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Выкатка Laravel CRM (crm.fastup.by) на hb.by через API ISPmanager, без SSH.

Старый CI (`fasstupby/crm` → `.github/workflows/deploy.yml`) лил rsync на выведенный vh155 и
светился зелёным, а бой тем временем правили руками. Отсюда два дрифта: коммиты, которые
не доехали, и серверные правки, которых нет в git. Скрипт закрывает оба.

* **Маркер** `storage/app/.deployed-sha` на сервере (вне `public/`) — коммит, который сейчас
  на бою. Выкатывается `git diff маркер..origin/main`, а не «всё подряд».
* **Дрифт-гард.** Перед записью каждый файл на бою сверяется с его версией на маркере
  (переводы строк нормализуются с обеих сторон). Не совпал — выкатка не начинается: на
  сервере правка, которой нет в git, и заливка из main её молча откатит.
* Запись — `replace_file`: бэкап в `secrets/deploy-backups/`, сверка чтением, откат.
* Удалённые в git файлы только перечисляются — сервер не чистится автоматически.
* После заливки PHP артизан на этом проде не нужен: `QUEUE_CONNECTION=sync`, в
  `bootstrap/cache` нет config/route cache (проверено 12.09.2026).

**Артизан без SSH** — разовая задача планировщика панели. Команда стоит «каждую минуту», но
защищена флагом `.started`, поэтому исполняется один раз, даже если задачу не удалось снять.
Вывод пишется в `storage/logs/deploy-<id>.log`, скрипт его забирает, задачу и файлы удаляет.
**НЕ ПОДТВЕРЖДЕНО (12.09.2026):** первая такая задача за 240 с не исполнилась — см.
`decisions/2026-09-12-crm-deploy-drift-audit.md`. До разбора на артизан через скрипт не рассчитывать.
Аргументы проходят белый список символов: команда уходит в `/bin/sh` крона. `migrate` без
`--pretend` требует `--confirm-migrate` — миграции трогают живую базу звонилки.

Usage:
    python scripts/deploy_crm.py status
    python scripts/deploy_crm.py init-marker <sha>          # бой == sha по всем файлам, иначе отказ
    python scripts/deploy_crm.py deploy --dry-run
    python scripts/deploy_crm.py deploy
    python scripts/deploy_crm.py artisan "--version"
    python scripts/deploy_crm.py artisan "migrate --pretend --force"
    python scripts/deploy_crm.py artisan "migrate --force" --confirm-migrate
    python scripts/deploy_crm.py composer "install --no-dev --optimize-autoloader --no-interaction"
"""
import argparse
import io
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from pathlib import Path, PurePosixPath

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from deploy_static_file import DeployError, Panel, normalize_newlines, replace_file

REPO = Path(r'G:\OSPanel\domains\crm')
BASE = 'www/crm.fastup.by'
# Путь для крона — через $HOME. Абсолютный путь старого хостинга `/var/www/h199903/data/...`
# на hb.by не работает: проба 13.09.2026 — `touch` по $HOME сработал за 49 с, по старому
# пути не сработал вовсе. Тем же мёртвым путём записаны кроны, перенесённые с vh155.
ABS_BASE = '$HOME/www/crm.fastup.by'
# `/opt/alt/php83/usr/bin/php` — путь старого хостинга: на hb.by его нет (EXIT=127, 13.09.2026).
# Этот путь панель отдаёт в настройках сайта (webdomain: «Path to PHP»); подтверждён из крона
# 13.09.2026: `migrate --pretend` через `$HOME` отработал с EXIT=0.
PHP = '/opt/php83/bin/php'
MARKER = 'storage/app/.deployed-sha'
LOGS = 'storage/logs'
DEPLOYABLE = ('app/', 'bootstrap/app.php', 'config/', 'database/', 'lang/', 'public/',
              'resources/', 'routes/', 'artisan', 'composer.json', 'composer.lock')
SAFE_ARGS = re.compile(r'[A-Za-z0-9:+_=./ -]{1,300}')


# Сборка фронта — как делал старый CI: сначала Tailwind (сканирует исходный JS), потом terser
# перезаписывает public/js/*.js. На бою лежат сборки, в git — исходники, поэтому эти файлы
# сравниваются и заливаются только как результат сборки нужного коммита. Проверено 13.09.2026:
# сборка из `git archive` байт в байт совпала с боем по JS и CSS.
BUILD_INPUTS = ['public/css', 'public/js', 'resources', 'tailwind.config.js']
MINIFY_CJS = r"""
const fs = require('fs'), path = require('path');
const { minify } = require('module').createRequire(process.argv[1])('terser');
(async () => {
  const dir = path.join(process.cwd(), 'public', 'js');
  for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.js'))) {
    const out = await minify(fs.readFileSync(path.join(dir, f), 'utf8'),
      { compress: true, mangle: true, format: { comments: false } });
    fs.writeFileSync(path.join(dir, f), out.code);
  }
})().catch(e => { console.error(e); process.exit(1); });
"""
_built = {}
_listing = {}


def built_files(rev):
    """{путь: байты} для public/css/style.css и public/js/*.js, собранных из коммита rev."""
    sha = git('rev-parse', rev)
    if sha in _built:
        return _built[sha]
    cli = REPO / 'node_modules' / 'tailwindcss' / 'lib' / 'cli.js'
    if not cli.exists() or not (REPO / 'node_modules' / 'terser').exists():
        raise DeployError(f'Нет node_modules в {REPO}: npm ci --legacy-peer-deps')
    tmp = Path(tempfile.mkdtemp(prefix='crm-build-'))
    try:
        archive = git('archive', '--format=tar', sha, '--', *BUILD_INPUTS, binary=True)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(tmp, filter='data')
        for step in (['node', str(cli), '-i', './public/css/input.css', '-o', './public/css/style.css', '--minify'],
                     ['node', '-e', MINIFY_CJS, str(REPO / 'package.json')]):
            result = subprocess.run(step, cwd=tmp, capture_output=True, text=True, encoding='utf-8', errors='replace')
            if result.returncode:
                raise DeployError(f'Сборка {sha[:7]} упала на {step[1]}:\n{result.stderr[-2000:]}')
        files = {'public/css/style.css': (tmp / 'public/css/style.css').read_bytes()}
        for js in sorted((tmp / 'public/js').glob('*.js')):
            files[f'public/js/{js.name}'] = js.read_bytes()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    _built[sha] = files
    return files


def expected_content(rev, rel):
    """Что должно лежать на бою для коммита rev: сборка для фронта, файл из git для остального."""
    return built_files(rev).get(rel) or git('show', f'{rev}:{rel}', binary=True)


def git(*args, binary=False, check=True):
    result = subprocess.run(['git', '-C', str(REPO), *args], capture_output=True)
    if check and result.returncode:
        raise DeployError(f'git {" ".join(args)}: {result.stderr.decode("utf-8", "replace").strip()}')
    return result.stdout if binary else result.stdout.decode('utf-8', 'replace').strip()


def deployable(path):
    return any(path == p or (p.endswith('/') and path.startswith(p)) for p in DEPLOYABLE)


def read_live(panel, rel):
    """Содержимое файла на бою или None, если его нет.

    Листинг каталога кэшируется: `panel.exists` листает родителя на каждый файл, и сверка
    ~150 файлов шла вдвое дольше и выглядела зависшей. Кэш живёт один запуск — только для
    чтения до записи; `replace_file` проверяет существование сам, мимо кэша.
    """
    parent = str(PurePosixPath(f'{BASE}/{rel}').parent)
    if parent not in _listing:
        try:
            _listing[parent] = set(panel.list_dir(parent))
        except DeployError:
            _listing[parent] = set()  # каталога нет на бою
    if PurePosixPath(rel).name not in _listing[parent]:
        return None
    return panel.read_file(f'{BASE}/{rel}')


def read_marker(panel):
    raw = read_live(panel, MARKER)
    if raw is None:
        raise DeployError(f'На сервере нет {MARKER}. Сначала init-marker <sha> — после сверки боя с git.')
    sha = raw.decode('utf-8', 'replace').strip()
    if not re.fullmatch(r'[0-9a-f]{7,40}', sha):
        raise DeployError(f'Маркер повреждён: {sha!r}')
    return sha


def write_marker(panel, sha):
    replace_file(panel, f'{BASE}/{MARKER}', f'{sha}\n'.encode())


def content_from_git(rev, rel):
    """Файл ровно как в коммите — не из рабочей копии.

    В `G:\\OSPanel\\domains\\crm` параллельно работают другие сессии; раньше выкатка требовала
    чистую рабочую копию и вставала на чужой незакоммиченной правке. Берём байты из git,
    нормализуем переводы строк и прогоняем `php -l` на временной копии.
    """
    content = normalize_newlines(git('show', f'{rev}:{rel}', binary=True))
    if rel.endswith('.php'):
        with tempfile.NamedTemporaryFile(suffix='.php', delete=False) as tmp:
            tmp.write(content)
        try:
            result = subprocess.run(['php', '-l', tmp.name], capture_output=True, text=True,
                                    encoding='utf-8', errors='replace')
        finally:
            Path(tmp.name).unlink(missing_ok=True)
        if result.returncode:
            raise DeployError(f'php -l не прошёл для {rel}, выкатка отменена:\n{result.stdout}{result.stderr}')
    return content


def cmd_status(panel, _args):
    git('fetch', '-q', 'origin', 'main')
    sha = read_marker(panel)
    print(f'На бою: {git("log", "-1", "--format=%h %s", sha)}')
    pending = git('log', '--format=%h %s', f'{sha}..origin/main')
    print('Не выкачено:\n  ' + pending.replace('\n', '\n  ') if pending else 'Бой == origin/main')


def cmd_init_marker(panel, args):
    sha = git('rev-parse', args.sha)
    files = [f for f in git('ls-tree', '-r', '--name-only', sha).splitlines() if deployable(f)]
    differs = []
    for rel in files:
        live = read_live(panel, rel)
        if live is None or normalize_newlines(live) != normalize_newlines(expected_content(sha, rel)):
            differs.append(rel + (' (нет на бою)' if live is None else ''))
    if differs:
        raise DeployError(f'Бой не совпадает с {sha[:7]} — маркер не ставлю:\n  ' + '\n  '.join(differs))
    write_marker(panel, sha)
    print(f'[OK] {len(files)} файлов совпали, маркер = {sha[:7]}')


def cmd_deploy(panel, args):
    git('fetch', '-q', 'origin', 'main')
    target = git('rev-parse', 'origin/main')
    base = read_marker(panel)
    changes = {}
    for line in git('diff', '--name-status', '--no-renames', f'{base}..{target}').splitlines():
        status, rel = line.split('\t', 1)
        if deployable(rel):
            changes[rel] = status
    # Фронт сравнивается сборка-со-сборкой: правка blade-шаблона меняет style.css, хотя сам
    # style.css в git не трогали, а правка исходника JS без изменения сборки заливки не требует.
    old_build, new_build = built_files(base), built_files(target)
    for rel, content in new_build.items():
        if old_build.get(rel) != content:
            changes[rel] = 'M' if rel in old_build else 'A'
        else:
            changes.pop(rel, None)
    migrations = sorted(r for r, s in changes.items() if r.startswith('database/migrations/') and s != 'D')
    if args.only_migrations:
        changes = {r: changes[r] for r in migrations}
    elif migrations and not args.migrations_applied:
        raise DeployError(
            'В выкатке миграции — код, который их ждёт, без них может уронить прод:\n  '
            + '\n  '.join(migrations)
            + '\nПорядок: deploy --only-migrations → artisan "migrate --pretend --force" → '
              'artisan "migrate --force" --confirm-migrate → deploy --migrations-applied')
    changes = sorted((s, r) for r, s in changes.items())
    if not changes:
        print(f'Нечего выкатывать: бой {base[:7]}, main {target[:7]}')
        if base != target:
            write_marker(panel, target)
        return

    # Дрифт-гард целиком до первой записи: набор не разваливается на середине.
    drift, uploads, removed = [], [], []
    for status, rel in changes:
        live = read_live(panel, rel)
        if status == 'D':
            removed.append(rel)
            continue
        if rel in new_build:
            new, expected = new_build[rel], old_build.get(rel)
        else:
            expected = None if status == 'A' else git('show', f'{base}:{rel}', binary=True)
            new = content_from_git(target, rel)
        if live is not None and normalize_newlines(live) == normalize_newlines(new):
            continue  # уже на бою (залито руками) — не трогаем
        if (expected is None and live is not None) or (expected is not None and (
                live is None or normalize_newlines(live) != normalize_newlines(expected))):
            drift.append(rel)
        uploads.append((rel, new))
    if drift:
        raise DeployError('На бою правки, которых нет в git (или файл пропал). Выкатка отменена:\n  '
                          + '\n  '.join(drift) + '\nСверь, закоммить нужное в crm и повтори.')

    print(f'{base[:7]} -> {target[:7]}: заливка {len(uploads)}, в git удалено {len(removed)}')
    for rel, _ in uploads:
        print(f'  + {rel}')
    for rel in removed:
        print(f'  - {rel} (на сервере НЕ удаляется, убрать руками после проверки)')
    if args.dry_run:
        return
    for rel, content in uploads:
        replace_file(panel, f'{BASE}/{rel}', content)
        print(f'[OK] {rel}')
    if args.only_migrations:
        # Файлы миграций без запуска migrate инертны; маркер не двигаем — код ещё не выкачен.
        print('Миграции залиты, маркер не сдвинут. Дальше: artisan "migrate --pretend --force".')
        return
    write_marker(panel, target)
    print(f'[OK] маркер = {target[:7]}')
    touched = [rel for _, rel in changes]
    if 'composer.lock' in touched:
        print('ВНИМАНИЕ: сменился composer.lock — нужен composer "install --no-dev --optimize-autoloader --no-interaction".')


def delete_file(panel, rel):
    path = PurePosixPath(f'{BASE}/{rel}')
    panel.call_ok('file.delete', {'plid': str(path.parent), 'elid': path.name, 'sok': 'ok'})


def run_once(panel, program, shell_args, timeout):
    """Разовая задача планировщика: создать, дождаться флага, забрать лог, снять задачу."""
    run_id = time.strftime('%Y%m%d%H%M%S') + uuid.uuid4().hex[:6]
    log, started, done = (f'{LOGS}/deploy-{run_id}.{ext}' for ext in ('log', 'started', 'done'))
    # `%` в crontab — перевод строки, `, ` — разделитель elid в групповых операциях панели.
    command = (f'cd {ABS_BASE} && test ! -e {started} && touch {started} && '
               f'{{ {PHP} {program} {shell_args} > {log} 2>&1; echo "EXIT=$?" >> {log}; touch {done}; }}')
    if '%' in command or ', ' in command or len(command) > 1024:
        raise DeployError('Команда недопустима для планировщика панели')

    panel.call_ok('scheduler.edit', {
        'sok': 'ok', 'command': command, 'description': f'deploy_crm {run_id}', 'active': 'on',
        'hideout': 'on', 'schedule_type': 'type_expert', 'input_min': '*', 'input_hour': '*',
        'input_dmonth': '*', 'input_month': '*', 'input_dweek': '*',
    })
    key = None
    try:
        key = find_job_key(panel, run_id, command)
        print(f'Задача {run_id} создана, ждём крон (до {timeout} с)...')
        deadline = time.time() + timeout
        while not panel.exists(f'{BASE}/{done}'):
            if time.time() > deadline:
                raise DeployError(f'Нет {done} за {timeout} с. Задача снята; если команда ещё идёт, '
                                  f'лог позже: {BASE}/{log}')
            time.sleep(15)
        output = panel.read_file(f'{BASE}/{log}').decode('utf-8', 'replace')
    finally:
        if key:
            panel.call_ok('scheduler.delete', {'elid': key, 'sok': 'ok'})
            if find_job_key(panel, run_id, command, required=False):
                print(f'НЕ СНЯЛАСЬ задача планировщика {run_id} — убрать в панели (повторно не исполнится)')
    for rel in (log, started, done):
        try:
            delete_file(panel, rel)
        except DeployError:
            print(f'Не удалён {BASE}/{rel}')
    print(output.rstrip())
    match = re.search(r'EXIT=(\d+)\s*$', output)
    return int(match.group(1)) if match else 1


def find_job_key(panel, run_id, command, required=True):
    """Задача ищется по описанию: панель может переписать команду при сохранении, и тогда
    поиск по тексту команды не нашёл бы задачу — и она осталась бы висеть в кроне."""
    for elem in panel.call('scheduler', {})['doc'].get('elem', []):
        value = lambda k: (elem.get(k) or {}).get('$') if isinstance(elem.get(k), dict) else elem.get(k)
        if value('description') == f'deploy_crm {run_id}':
            # `dkey` у задачи с описанием — само описание; команда лежит в `command`, и при
            # hideout=on панель дописывает к ней `>/dev/null 2>&1`.
            if not str(value('command') or '').startswith(command):
                print(f'Панель сохранила команду не дословно: {value("command")!r}')
            return value('key')
    if required:
        raise DeployError('Задача создана, но не найдена в листинге планировщика — проверь панель руками')
    return None


def cmd_artisan(panel, args):
    if not SAFE_ARGS.fullmatch(args.args):
        raise DeployError('Аргументы artisan: только буквы, цифры и : _ = . / - пробел')
    words = args.args.split()
    if words and words[0].startswith('migrate') and '--pretend' not in words and not args.confirm_migrate:
        raise DeployError('migrate на живой базе — только с --confirm-migrate (сначала --pretend)')
    return run_once(panel, 'artisan', args.args, args.timeout)


def cmd_composer(panel, args):
    if not SAFE_ARGS.fullmatch(args.args):
        raise DeployError('Аргументы composer: только буквы, цифры и : _ = . / - пробел')
    return run_once(panel, 'composer.phar', args.args, args.timeout)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status')
    init = sub.add_parser('init-marker')
    init.add_argument('sha')
    deploy = sub.add_parser('deploy')
    deploy.add_argument('--dry-run', action='store_true')
    deploy.add_argument('--only-migrations', action='store_true',
                        help='залить только новые файлы миграций, маркер не двигать')
    deploy.add_argument('--migrations-applied', action='store_true',
                        help='миграции из выкатки уже применены на бою — можно лить код')
    for name in ('artisan', 'composer'):
        p = sub.add_parser(name)
        p.add_argument('args')
        p.add_argument('--timeout', type=int, default=300)
        if name == 'artisan':
            p.add_argument('--confirm-migrate', action='store_true')
    args = parser.parse_args()
    handlers = {'status': cmd_status, 'init-marker': cmd_init_marker, 'deploy': cmd_deploy,
                'artisan': cmd_artisan, 'composer': cmd_composer}
    try:
        code = handlers[args.cmd](Panel(), args)
    except (DeployError, OSError) as error:
        parser.exit(1, f'{error}\n')
    sys.exit(code or 0)


if __name__ == '__main__':
    main()
