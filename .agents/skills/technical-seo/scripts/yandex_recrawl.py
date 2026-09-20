
import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Отправка страниц на переобход в Яндекс.Вебмастер через официальный API.

Использование:
    python scripts/yandex_recrawl.py https://fastup.by/indeks-vidimosti/
    python scripts/yandex_recrawl.py --all-index
"""

import os
import sys
import argparse
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('YANDEX_OAUTH_TOKEN')
USER_ID = os.getenv('YANDEX_USER_ID')
HOST_ID = os.getenv('YANDEX_HOST_ID')

def get_headers():
    if not TOKEN:
        raise ValueError('YANDEX_OAUTH_TOKEN отсутствует в .env')
    return {
        'Authorization': f'OAuth {TOKEN}',
        'Content-Type': 'application/json',
    }

def check_quota():
    headers = get_headers()
    url = f'https://api.webmaster.yandex.net/v4/user/{USER_ID}/hosts/{HOST_ID}/recrawl/quota'
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()

def submit_url(url: str):
    headers = get_headers()
    queue_url = f'https://api.webmaster.yandex.net/v4/user/{USER_ID}/hosts/{HOST_ID}/recrawl/queue'
    r = requests.post(queue_url, headers=headers, json={'url': url})
    return r.status_code, r.json()

def main():
    parser = argparse.ArgumentParser(description='Отправка URL на переобход в Яндекс.Вебмастер')
    parser.add_argument('urls', nargs='*', help='Список URL для переобхода')
    parser.add_argument('--all-index', action='store_true', help='Отправить все страницы раздела рейтингов')
    args = parser.parse_args()

    targets = list(args.urls)
    if args.all_index:
        targets.extend([
            'https://fastup.by/indeks-vidimosti/',
            'https://fastup.by/indeks-vidimosti/zagorodnoe-stroitelstvo/',
        ])

    if not targets:
        print('Укажите URL или флаг --all-index')
        sys.exit(1)

    quota = check_quota()
    dq = quota.get('daily_quota')
    rem = quota.get('quota_remainder')
    print(f'Дневная квота: {dq}, остаток: {rem}')

    for url in targets:
        status, data = submit_url(url)
        task_id = data.get('task_id')
        q_rem = data.get('quota_remainder')
        if status == 202:
            print(f'[OK 202] {url} -> Задача {task_id}, остаток квоты: {q_rem}')
        else:
            print(f'[ERR {status}] {url} -> {data}')

if __name__ == '__main__':
    main()
