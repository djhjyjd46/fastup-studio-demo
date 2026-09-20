#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Deploy a single fastup-v2 theme file to hb.by production hosting via ISPmanager API.

On hb.by shared hosting, SSH access is disabled (/bin/date in /etc/passwd), so theme files
are deployed using the ISPmanager Panel API on port 1500/2087. Authentication, atomic
writing, and pre-deployment backups are reused from scripts/deploy_static_file.py.

Workflow:
- Before overwriting, the live remote version is backed up locally to `secrets/deploy-backups/`.
- The new content is uploaded atomically via Panel API.
- Post-write verification compares hashes; rolls back automatically on mismatch.
- `--no-backup` skips backup/verification (use only if panel limits fail on read).

Usage:
    python scripts/deploy_theme_file.py design/wp-templates/schema-org.php --remote inc/schema-org.php
    python scripts/deploy_theme_file.py design/wp-templates/author.php --remote author.php
    python scripts/deploy_theme_file.py design/wp-templates/author.php --remote author.php --no-backup

Next steps after deployment:
    python scripts/clear_page_cache.py
    curl -s -A "Mozilla/5.0" https://fastup.by/ | grep -c "<expected string>"
"""
import argparse
import json
from pathlib import Path

from deploy_static_file import (
    DeployError,
    Panel,
    replace_file,
    validate_local_file,
    validate_remote_path,
)

THEME_DIR = 'www/fastup.by/wp-content/themes/fastup-v2'


def deploy_theme_file(local_file, remote, backup=True, panel=None):
    """Deploy a single local file to a relative path within the active WordPress theme."""
    validate_remote_path(remote.strip('/'))
    target = f'{THEME_DIR}/{remote.strip("/")}'
    content = validate_local_file(local_file, target)
    receipt = replace_file(panel or Panel(), target, content, backup=backup)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(f'[OK] {local_file} -> {target} ({len(content)} bytes)')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('local_file', type=Path, help='path to the local source file')
    parser.add_argument('--remote', required=True, help='relative target path inside the theme (e.g. inc/schema-org.php)')
    parser.add_argument('--no-backup', action='store_true',
                        help='deploy without remote backup or verification (use only if panel cannot download the current version)')
    args = parser.parse_args()
    try:
        deploy_theme_file(args.local_file, args.remote, backup=not args.no_backup)
    except (DeployError, OSError) as error:
        parser.exit(1, f'{error}\n')
    print('Next: python scripts/clear_page_cache.py, then verify changes live.')


if __name__ == '__main__':
    main()
