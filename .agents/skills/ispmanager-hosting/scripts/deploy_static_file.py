#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Deploy static file to hb.by production hosting via ISPmanager API (port 2087) without SSH.

SSH access is disabled on shared hosting (see integrations/wordpress.md), making the Panel API
the primary path for file modifications. Credentials are read from environment variables or
`.env` in the repository root: `HOSTING_BASE_URL`, `HOSTING_USER`, `HOSTING_PASS`.
`HOSING_*` (legacy typo) is accepted as fallback.

Write workflow:
- Files on production are **never deleted prior to writing**. New files use `file.new`; existing files are overwritten in-place.
- Before overwriting, the live remote version is downloaded to `secrets/deploy-backups/` (.gitignored).
- After writing, content is read back and hash-verified; any mismatch triggers an immediate rollback.
- Panel API responses are verified via the documented `<doc><ok/></doc>` element.

Panel limit: `FileMaxEditSize` (default 1024 Kb) constrains reading large files through the panel.
If current version cannot be downloaded, deployment halts unless `--no-backup` is explicitly passed.

Usage:
    python scripts/deploy_static_file.py content/llms.txt --site fastup.by --remote-name llms.txt
    python scripts/deploy_static_file.py content/llms-full.txt --site fastup.by
    python scripts/deploy_static_file.py content/robots.txt --site fastup.by --no-backup
"""
import argparse
import ftplib
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import ssl
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid

from env_load import env_file_path

ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = ROOT / 'secrets' / 'deploy-backups'


class DeployError(RuntimeError):
    """User-safe exception without panel raw response bodies or credentials."""


def _from_env(*names):
    """Return value of first resolved environment or .env variable."""
    for name in names:
        if os.environ.get(name):
            return os.environ[name].strip()
    env_file = env_file_path()  # From git worktree — points to primary .env
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            key, _, value = line.partition('=')
            if key.strip() in names and value.strip():
                return value.strip().strip('"').strip("'")
    return None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DeployError('Panel responded with redirect — verify HOSTING_BASE_URL')


def validate_remote_path(path):
    """Ensure path is strictly relative: no directory traversal, backslashes, or commas.

    Commas delimit entities in ISPmanager batch operations; a comma inside an elid
    parameter would transform a single-file update into a multi-file batch.
    """
    if (not path or path.startswith('/') or '\\' in path or ',' in path
            or any(ord(c) < 32 for c in path)
            or any(p in ('', '.', '..') for p in path.split('/'))):
        raise DeployError(f'Invalid remote relative path: {path!r}')
    return path


class Panel:
    # file.edit strictly accepts UTF-8; binaries cannot be transferred via panel
    accepts_binary = False

    def __init__(self):
        self.url = _from_env('HOSTING_BASE_URL', 'HOSING_BASE_URL') or 'https://by5000.hbby-cloud.com:2087/ispmgr'
        parsed = urllib.parse.urlsplit(self.url)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            raise DeployError('HOSTING_BASE_URL must be HTTPS without credentials or query params')
        self.user = _from_env('HOSTING_USER', 'HOSING_USER')
        self.password = _from_env('HOSTING_PASS', 'HOSING_PASS')
        if not self.user or not self.password:
            raise DeployError(
                'Missing hosting credentials: set HOSTING_USER and HOSTING_PASS in environment '
                'or .env (see integrations/wordpress.md).'
            )
        context = ssl.create_default_context()
        ca = _from_env('HOSTING_CA_BUNDLE', 'HOSING_CA_BUNDLE')
        if ca:
            try:
                context.load_verify_locations(cafile=ca)
            except (OSError, ssl.SSLError):
                raise DeployError('Cannot read HOSTING_CA_BUNDLE') from None
        self.opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), NoRedirect())

    def request(self, func, params, out='json'):
        """out=None omits JSON formatting, allowing `file.download` to stream raw bytes."""
        if {'authinfo', 'auth', 'func', 'out'} & params.keys():
            raise DeployError('Cannot override internal panel query parameters')
        data = {'authinfo': f'{self.user}:{self.password}', 'func': func, **params}
        if out:
            data['out'] = out
        request = urllib.request.Request(self.url, data=urllib.parse.urlencode(data).encode(), headers={
            'User-Agent': 'Mozilla/5.0 (compatible; FastUp-Deploy/2.0)',
            'Content-Type': 'application/x-www-form-urlencoded',
        })
        try:
            with self.opener.open(request, timeout=30) as response:
                return response.read(), response.headers
        except urllib.error.HTTPError as error:
            raise DeployError(f'{func}: HTTP {error.code}, operation unconfirmed') from None
        except (urllib.error.URLError, OSError, TimeoutError):
            raise DeployError(f'{func}: network or TLS timeout, operation unconfirmed') from None

    def call(self, func, params):
        """Invoke panel method expecting JSON. Panel errors are parsed from doc.error."""
        raw, _ = self.request(func, params)
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise DeployError(f'{func}: panel returned non-JSON response') from None
        doc = result.get('doc') if isinstance(result, dict) else None
        if not isinstance(doc, dict) or 'error' in doc:
            err_msg = 'panel error or unexpected response'
            if isinstance(doc, dict) and 'error' in doc:
                err = doc['error']
                if isinstance(err, dict):
                    err_msg = err.get('msg', {}).get('$') or err.get('$type') or err_msg
            raise DeployError(f'{func}: {err_msg}')
        return result

    def call_ok(self, func, params):
        """Write operations: verifies success via doc.ok, otherwise raises DeployError."""
        doc = self.call(func, params)['doc']
        if 'ok' not in doc:
            raise DeployError(f'{func}: panel did not confirm success (missing doc.ok)')
        return doc

    def list_dir(self, remote_dir):
        """List filenames in a remote directory. Used for existence checks and cache purge."""
        remote_dir = validate_remote_path(remote_dir)
        doc = self.call('file', {'plid': remote_dir})['doc']
        actual_plid = doc.get('plid')
        if isinstance(actual_plid, dict):
            actual_plid = actual_plid.get('$')
        if actual_plid and actual_plid.rstrip('/') != remote_dir.rstrip('/'):
            # ISPmanager silently falls back to parent if requested dir does not exist.
            # Without this guard, exists('dir/index.html') wrongly returns True if index.html
            # exists in parent directory, skipping subdirectory creation.
            raise DeployError(f'Remote directory does not exist: {remote_dir}')
        elems = doc.get('elem', [])
        if not isinstance(elems, list):
            raise DeployError(f'Unexpected directory listing format for {remote_dir}')
        names = []
        for elem in elems:
            if not isinstance(elem, dict):
                raise DeployError(f'Unexpected entry in directory listing {remote_dir}')
            name = elem.get('name')
            name = name.get('$') if isinstance(name, dict) else name
            if not isinstance(name, str) or not name:
                raise DeployError(f'Nameless entry in directory listing {remote_dir}')
            names.append(name)
        return names

    def ensure_dir(self, remote_dir):
        path = PurePosixPath(validate_remote_path(remote_dir))
        parts = path.parts
        current = parts[0]
        for part in parts[1:]:
            parent = current
            current = f"{current}/{part}"
            try:
                names = self.list_dir(parent)
            except Exception:
                names = []
            if part not in names:
                self.call_ok('file.new', {'name': part, 'plid': parent,
                                          'filetype': '1', 'sok': 'ok'})

    def exists(self, target):
        path = PurePosixPath(validate_remote_path(target))
        try:
            return path.name in self.list_dir(str(path.parent))
        except Exception:
            return False

    def read_file(self, target):
        """Read live file content. May raise DeployError if constrained by FileMaxEditSize."""
        path = PurePosixPath(validate_remote_path(target))
        raw, headers = self.request('file.download', {'plid': str(path.parent), 'elid': path.name},
                                    out=None)
        # Login page or error JSON must not be mistaken for file content or backed up.
        if not headers.get('Content-Disposition', '').lower().startswith('attachment'):
            raise DeployError(
                f'file.download failed for {target} (missing Content-Disposition: attachment). '
                'Likely blocked by panel FileMaxEditSize. Use --no-backup to bypass backup/verification.'
            )
        return raw

    def create_file(self, target):
        path = PurePosixPath(validate_remote_path(target))
        self.ensure_dir(str(path.parent))
        self.call_ok('file.new', {'name': path.name, 'plid': str(path.parent),
                                  'filetype': '0', 'sok': 'ok'})

    def write_file(self, target, content):
        validate_remote_path(target)
        try:
            value = content.decode('utf-8')
        except UnicodeError:
            raise DeployError('file.edit strictly accepts UTF-8') from None
        self.call_ok('file.edit', {'elid': target, 'fdata': value, 'encoding': 'UTF-8', 'sok': 'ok'})


class Transfer:
    """Byte-exact FTP transport — fallback for binaries where Panel API cannot be used.

    ISPmanager Panel API normalizes CRLF -> LF and only accepts UTF-8 via file.edit.
    Fonts, images, and archives must be deployed via FTP to preserve exact bytes.

    Target host must be a direct IP or domain, not a Cloudflare-proxied panel hostname.
    Interface matches Panel class, allowing replace_file() to handle backups, verification,
    and automatic rollbacks across both transports.
    """

    accepts_binary = True

    def __init__(self, host=None):
        self.host = host or _from_env('FTP_HOST', 'HOSTING_FTP_HOST') or '176.60.210.120'
        user = _from_env('FTP_USER', 'HOSTING_FTP_USER', 'HOSTING_USER', 'HOSING_USER')
        password = _from_env('FTP_PASS', 'HOSTING_FTP_PASS', 'HOSTING_PASS', 'HOSING_PASS')
        if not user or not password:
            raise DeployError('Missing credentials: set FTP_USER and FTP_PASS (or HOSTING_USER/PASS) in .env')
        try:
            self.ftp = ftplib.FTP()
            self.ftp.connect(self.host, 21, timeout=30)
            self.ftp.login(user, password)
            self.ftp.set_pasv(True)
            self._root_items = set()
            try:
                self._root_items = {PurePosixPath(e).name for e in self.ftp.nlst()}
            except Exception:
                pass
        except Exception:
            raise DeployError(
                f'FTP to {self.host} failed. Ensure target is direct IP or site domain, '
                'not a Cloudflare-proxied panel hostname.'
            ) from None

    def _map_target(self, target):
        path = validate_remote_path(target)
        parts = PurePosixPath(path).parts
        # Full user root (contains www/)
        if 'www' in self._root_items:
            return path
        # Root at site level (fastup.by/)
        if len(parts) >= 2 and parts[1] in self._root_items:
            return str(PurePosixPath(*parts[1:]))
        # Root at subfolder level (tz/, kp/, outreach/)
        for folder in ('tz', 'kp', 'outreach'):
            if folder in self._root_items and folder in parts:
                idx = parts.index(folder)
                return str(PurePosixPath(*parts[idx:]))
        # User restricted strictly to isolated subfolder (e.g. fastup.by/tz/)
        if 'tz' in parts:
            idx = parts.index('tz')
            if idx + 1 < len(parts):
                return str(PurePosixPath(*parts[idx + 1:]))
        return path

    def close(self):
        try:
            self.ftp.quit()
        except Exception:
            pass

    def exists(self, target):
        """ProFTPD NLST yields full paths; compare by basename."""
        mapped = self._map_target(target)
        path = PurePosixPath(mapped)
        parent = str(path.parent) if str(path.parent) != '.' else ''
        try:
            entries = self.ftp.nlst(parent) if parent else self.ftp.nlst()
        except Exception:
            return False
        return path.name in {PurePosixPath(e).name for e in entries}

    def read_file(self, target):
        mapped = self._map_target(target)
        buffer = io.BytesIO()
        try:
            self.ftp.retrbinary(f'RETR {mapped}', buffer.write)
        except Exception:
            raise DeployError(f'FTP failed to download file: {target} ({mapped})') from None
        return buffer.getvalue()

    def ensure_dir(self, remote_dir):
        path = PurePosixPath(validate_remote_path(remote_dir))
        parts = path.parts
        current = parts[0]
        for part in parts[1:]:
            parent = current
            current = f"{current}/{part}"
            try:
                entries = self.ftp.nlst(parent)
            except Exception:
                entries = []
            names = {PurePosixPath(e).name for e in entries}
            if part not in names:
                try:
                    self.ftp.mkd(current)
                except Exception:
                    pass

    def create_file(self, target):
        """Create parent directories prior to STOR if missing."""
        mapped = self._map_target(target)
        path = PurePosixPath(mapped)
        if str(path.parent) != '.':
            self.ensure_dir(str(path.parent))

    def write_file(self, target, content):
        mapped = self._map_target(target)
        try:
            self.ftp.storbinary(f'STOR {mapped}', io.BytesIO(content))
        except Exception:
            raise DeployError(f'FTP failed to write file: {target} ({mapped})') from None


def call_api(func, params):
    """Legacy compatibility helper."""
    return Panel().call(func, params)


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def save_backup(target, original, backup_dir):
    """Save copy of current remote production version to local session disk with receipt."""
    folder = Path(backup_dir) / uuid.uuid4().hex
    folder.mkdir(parents=True, mode=0o700)
    backup = folder / 'original.bin'
    with backup.open('xb') as output:
        output.write(original)
        output.flush()
        os.fsync(output.fileno())
    if backup.read_bytes() != original:
        raise OSError('Backup verification failed on reread')
    receipt = {'target': target, 'backup': str(backup.resolve()), 'sha256': sha256(original)}
    with (folder / 'receipt.json').open('x', encoding='utf-8') as output:
        json.dump(receipt, output, ensure_ascii=False, indent=2)
        output.flush()
        os.fsync(output.fileno())
    return receipt


def replace_file(panel, target, content, backup_dir=BACKUP_DIR, backup=True):
    """Deploy file to remote server without deletion. Creates new or updates existing.

    file.edit is not an atomic rename. A crashed process or dropped panel connection
    may require manual restoration from secrets/deploy-backups/.
    backup=False (--no-backup) deploys without backup or hash check (for FileMaxEditSize limits).
    """
    validate_remote_path(target)
    if not getattr(panel, 'accepts_binary', False):
        try:
            content.decode('utf-8')
        except UnicodeError:
            raise DeployError('Panel API only accepts UTF-8; deploy binaries via FTP') from None

    is_binary = getattr(panel, 'accepts_binary', False)
    def _eq(a, b):
        return a == b if is_binary else normalize_newlines(a) == normalize_newlines(b)

    if not panel.exists(target):
        panel.create_file(target)
        panel.write_file(target, content)
        if backup and not _eq(panel.read_file(target), content):
            raise DeployError(f'File created, but hash verification failed: {target}')
        return {'target': target, 'created': True, 'sha256': sha256(content)}

    if not backup:
        panel.write_file(target, content)
        return {'target': target, 'unverified': True, 'sha256': sha256(content)}

    original = panel.read_file(target)
    if _eq(original, content):
        return {'target': target, 'unchanged': True}
    try:
        receipt = save_backup(target, original, backup_dir)
    except OSError:
        raise DeployError('Local backup could not be saved; remote file unmodified') from None
    if not _eq(panel.read_file(target), original):
        raise DeployError('Remote file was modified concurrently during staging. Aborted.')
    try:
        panel.write_file(target, content)
        if not _eq(panel.read_file(target), content):
            raise DeployError('Post-write hash verification failed')
    except (DeployError, OSError) as error:
        try:
            if panel.read_file(target) != original:
                panel.write_file(target, original)
            if panel.read_file(target) != original:
                raise DeployError('Rollback could not be verified')
        except (DeployError, OSError):
            raise DeployError(f'MANUAL RESTORATION REQUIRED: {target}; backup at: {receipt["backup"]}') from None
        raise DeployError(f'Deployment failed, restored original. Backup: {receipt["backup"]}') from error
    return receipt


def normalize_newlines(content):
    """Normalize CRLF -> LF prior to deployment.

    Panel saves content with LF regardless of input payload, while Windows working tree
    keeps CRLF. Without normalization, post-write verification fails on text files.
    """
    return content.replace(b'\r\n', b'\n')


BINARY_SUFFIXES = {'.woff2', '.woff', '.ttf', '.otf', '.eot',
                   '.png', '.jpg', '.jpeg', '.webp', '.ico', '.gif', '.svgz',
                   '.zip', '.gz', '.tgz', '.tar', '.pdf'}


def validate_local_file(local, target):
    raw = Path(local).read_bytes()
    if Path(str(target)).suffix.lower() in BINARY_SUFFIXES:
        return raw
    content = normalize_newlines(raw)
    try:
        content.decode('utf-8')
    except UnicodeError:
        raise DeployError(f'Local file is not UTF-8: {local}') from None
    if target.lower().endswith('.php'):
        result = subprocess.run(['php', '-l', str(local)], capture_output=True, text=True,
                                encoding='utf-8', errors='replace')
        if result.returncode:
            raise DeployError(f'php -l syntax error, deployment aborted:\n{result.stdout}{result.stderr}')
        print(f'php -l: clean ({local})')
    return content


def deploy_file(local_path, site, remote_name, backup=True):
    if not re.fullmatch(r'[a-zA-Z0-9.-]+', site) or site in ('.', '..'):
        raise DeployError(f'Invalid site directory: {site!r}')
    target = validate_remote_path(f'www/{site}/{remote_name}')
    content = validate_local_file(local_path, target)
    if _from_env('HOSTING_USER', 'HOSING_USER') and _from_env('HOSTING_PASS', 'HOSING_PASS'):
        transport = Panel()
    elif _from_env('FTP_USER', 'HOSTING_FTP_USER') and _from_env('FTP_PASS', 'HOSTING_FTP_PASS'):
        transport = Transfer()
    else:
        transport = Panel()
    receipt = replace_file(transport, target, content, backup=backup)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(f'[OK] {local_path} -> {target} ({len(content)} bytes)')
    print('Next: clear page cache and verify live via curl.')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('local_file', type=Path, help='path to local source file')
    parser.add_argument('--site', default='fastup.by', help='site domain folder under www/ (default: fastup.by)')
    parser.add_argument('--remote-name', help='remote filename on server (defaults to local basename)')
    parser.add_argument('--no-backup', action='store_true',
                        help='deploy without remote backup or verification (use only when panel limits fail on read)')
    args = parser.parse_args()
    try:
        deploy_file(args.local_file, args.site, args.remote_name or args.local_file.name,
                    backup=not args.no_backup)
    except (DeployError, OSError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
