#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Deploy fastup-v2 theme files and invalidate page cache.

On hb.by shared hosting, SSH/shell access is disabled (/bin/date in /etc/passwd), so scp,
rsync, and remote Tailwind builds cannot run. Template deployments are executed via
the ISPmanager Panel API on port 1500/2087. Tailwind CSS must be built locally prior to
deployment (`npx @tailwindcss/cli -i css/input.css -o css/styles.css --minify`).

Pre-flight checks:
- All target files are validated locally first (`php -l` syntax check, UTF-8 encoding, valid relative paths).
- Remote target versions are backed up to `secrets/deploy-backups/` before writing.
- Post-write hash verification ensures integrity.
- Page cache is automatically invalidated upon completion.

Transport modes:
- `--file <path>` (Default & Primary): Uploads specific theme templates via Panel API (atomic, verified, safe).
- `--drift`: Compares local files against production, normalizing CRLF/LF on text files.
- `--sync`: Bulk synchronization of all drifted files using FTP (used for byte-for-byte binary preservation, e.g. fonts/images).

Usage:
    python scripts/deploy_theme.py --file header.php --file inc/schema-org.php
    python scripts/deploy_theme.py --file pages/page-geo-prodvizhenie.php --file css/styles.css
    python scripts/deploy_theme.py --drift
    python scripts/deploy_theme.py --sync
"""
import argparse
import subprocess
import sys
from pathlib import Path

from clear_page_cache import clear_cache
from deploy_static_file import (BINARY_SUFFIXES, DeployError, Panel, Transfer, normalize_newlines,
                                replace_file, validate_local_file, validate_remote_path)
from deploy_theme_file import THEME_DIR, deploy_theme_file

THEME_ROOT = Path(__file__).resolve().parent.parent / 'design' / 'wp-templates'
MIRROR = 'design/wp-templates/'
# Binary extensions where CRLF normalization must not be applied
BINARY_SUFFIXES = {'.woff2', '.woff', '.ttf', '.png', '.jpg', '.jpeg', '.webp', '.ico', '.gif'}


def tracked_files():
    """Retrieve tracked files in design/wp-templates from git index."""
    out = subprocess.run(['git', 'ls-files', MIRROR], capture_output=True, text=True,
                         encoding='utf-8', errors='replace')
    return [f.strip() for f in out.stdout.splitlines() if f.strip()]


def check_drift(quiet=False):
    """Compare local theme mirror against live production server."""
    panel, same, drift, absent = Panel(), 0, [], []
    files = tracked_files()
    if not files:
        raise DeployError('git ls-files returned no tracked mirror files')
    for path in files:
        rel = path[len(MIRROR):]
        local = Path(path).read_bytes()
        try:
            live = panel.read_file(f'{THEME_DIR}/{rel}')
        except DeployError:
            absent.append(rel)
            continue
        if Path(rel).suffix.lower() in BINARY_SUFFIXES:
            equal = local == live
        else:
            equal = normalize_newlines(local) == normalize_newlines(live)
        if equal:
            same += 1
        else:
            drift.append((rel, len(local), len(live)))
    if not quiet:
        print(f'Matching files: {same} of {len(files)}')
        for rel, a, b in sorted(drift, key=lambda r: r[0]):
            print(f'  DRIFT        {rel}  local {a} / remote {b} bytes')
        for rel in sorted(absent):
            print(f'  NOT ON LIVE  {rel}')
    return [rel for rel, _, _ in drift]


def sync_drifted(backup=True):
    """Synchronize all drifted files to production via FTP and purge page cache.

    FTP is used instead of Panel API for bulk synchronization because it writes
    byte-for-byte and preserves binaries (fonts, images), whereas Panel API's
    file.edit strictly expects UTF-8 text and normalizes CRLF -> LF.
    """
    drifted = check_drift(quiet=True)
    if not drifted:
        print('No drift detected, nothing to deploy.')
        return
    print(f'Drifted files count: {len(drifted)}')

    payload = {}
    for rel in drifted:
        local = THEME_ROOT / rel
        if not local.exists():
            raise DeployError(f'Local file not found: {local}')
        payload[rel] = validate_local_file(local, rel)

    transfer = Transfer()
    try:
        for rel in drifted:
            receipt = replace_file(transfer, f'{THEME_DIR}/{rel}', payload[rel], backup=backup)
            state = 'created' if receipt.get('created') else ('unchanged' if receipt.get('unchanged') else 'updated')
            print(f'  {state:14} {rel}  ({len(payload[rel])} bytes)')
    finally:
        transfer.close()

    clear_cache(Panel())
    print(f'[OK] Deployed via FTP: {len(drifted)} files, page cache purged. Verify live site.')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--drift', action='store_true',
                        help='check differences between local files and live production without modifying anything')
    parser.add_argument('--sync', action='store_true',
                        help='bulk sync all drifted files to production via FTP and purge page cache')
    parser.add_argument('--file', action='append', dest='files',
                        help='theme relative file path, can be repeated: --file header.php --file css/styles.css')
    parser.add_argument('--no-backup', action='store_true',
                        help='deploy without remote backup or verification (use only if panel fails to read current version)')
    args = parser.parse_args()

    if args.drift:
        try:
            sys.exit(1 if check_drift() else 0)
        except (DeployError, OSError) as error:
            parser.exit(1, f'{error}\n')
    if args.sync:
        try:
            sync_drifted(backup=not args.no_backup)
        except (DeployError, OSError) as error:
            parser.exit(1, f'Deployment failed: {error}\n')
        return
    if not args.files:
        parser.error('requires at least one --file, --drift to inspect, or --sync for bulk synchronization')

    try:
        # Pre-validate all files before writing anything
        for relative in args.files:
            validate_remote_path(relative.strip('/'))
            local = THEME_ROOT / relative
            if not local.exists():
                raise DeployError(f'Local file not found: {local}')
            validate_local_file(local, f'{THEME_DIR}/{relative.strip("/")}')

        panel = Panel()
        for relative in args.files:
            deploy_theme_file(THEME_ROOT / relative, relative, backup=not args.no_backup, panel=panel)
        clear_cache(panel)
    except (DeployError, OSError) as error:
        parser.exit(1, f'Deployment failed: {error}\n')
    print(f'[OK] Deployed files: {len(args.files)}, page cache purged. Verify live site.')


if __name__ == '__main__':
    main()
