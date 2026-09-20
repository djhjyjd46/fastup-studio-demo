#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Clear fastup-page-cache plugin cache without WP-CLI or SSH.

Performs the exact equivalent of `FastUp_Page_Cache::clear_all_cache()` and the button in
Settings -> FastUp Cache: deletes all `*.html` files from the cache directory. Required because
hb.by shared hosting has SSH disabled (see integrations/wordpress.md), and without a cache flush,
template changes remain invisible as the server continues serving cached copies with
`X-Fastup-Cache: HIT`.

Panel credentials are read from `HOSTING_USER` / `HOSTING_PASS` (environment or `.env`),
matching scripts/deploy_static_file.py. Deletion success is verified via the documented
`doc.ok` response, and the directory is re-scanned afterward: past issues occurred where
deletions were assumed successful while stale cached HTML remained on the server.

Usage:
    python scripts/clear_page_cache.py
    python scripts/clear_page_cache.py --dry-run
"""
import argparse

from deploy_static_file import DeployError, Panel, validate_remote_path

CACHE_DIR = 'www/fastup.by/wp-content/cache/fastup-page-cache'


def list_cache(panel):
    names = []
    for name in panel.list_dir(CACHE_DIR):
        if not name.endswith('.html'):
            continue
        validate_remote_path(name)
        if '/' in name:
            raise DeployError(f'Cache listing entry is not a pure filename: {name!r}')
        names.append(name)
    return names


def clear_cache(panel=None, dry_run=False):
    panel = panel or Panel()
    files = list_cache(panel)
    print(f'Cache contains {len(files)} HTML files')
    if dry_run:
        return
    for name in files:
        panel.call_ok('file.delete', {'elid': name, 'plid': CACHE_DIR})
    left = list_cache(panel)
    if left:
        raise DeployError(
            f'Cache is not empty: {len(left)} files remaining. Retry or check for concurrent cache writers.'
        )
    print(f'[OK] Deleted {len(files)} files, cache directory is clear')
    print("Verify: curl -sD - -o /dev/null -A 'Mozilla/5.0' https://fastup.by/ | grep -i fastup-cache")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dry-run', action='store_true', help='only display number of cached files')
    args = parser.parse_args()
    try:
        clear_cache(dry_run=args.dry_run)
    except (DeployError, OSError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
