---
name: ispmanager-hosting
description: >-
  File and deployment operations on ISPmanager 6 shared hosting without SSH access:
  transport selection (FTP vs Panel API), binary preservation, webroot security hygiene,
  and deployment via deterministic repository scripts. Use whenever uploading, inspecting,
  or deploying files to FastUp.by (hb.by) or client ISPmanager hosting.
---

# ISPmanager 6 Hosting Operations (SSH-less Deployments)

On ISPmanager 6 shared hosting plans, shell access is disabled (`/bin/date` in `/etc/passwd`). SSH, `scp`, `rsync`, and WP-CLI do not work. All file operations must use either the ISPmanager XML/JSON API or FTP.

---

## 1. Transport Selection Matrix

| Operation | Required Transport | Rationale |
|---|---|---|
| Single or few text files with diff & rollback | **Panel API** (`scripts/deploy_*.py`) | Atomic write, readback verification, automatic backup |
| Binaries (fonts, images, media, archives) | **FTP only** | `file.edit` API strictly accepts UTF-8; binaries will corrupt |
| Exact byte-precision files (CRLF preservation) | **FTP only** | Panel API unconditionally normalizes CRLF → LF |
| Bulk deployments (10+ files) | **FTP upload (.zip) + Panel API (`file.extract`)** | Avoids hundreds of individual HTTP requests |
| Pre-deployment snapshot | **Panel API (`file.pack`)** | Archive created server-side; store **outside webroot** |

---

## 2. FTP Transport: Direct IP & Passive Mode

Passive FTP works reliably when configured properly:

1. **Host Address:** Connect to the **direct server IP** or the website domain. **NEVER** connect to the panel hostname (e.g. `by5000.hbby-cloud.com`) because panel domains often route through Cloudflare, which blocks raw FTP traffic and leads to false "passive port firewall" assumptions.
2. **Data Integrity:** FTP preserves exact byte sequences, null bytes, and CRLF line endings.
3. **Credentials:** Read strictly from `.env` (`HOSTING_USER`, `HOSTING_PASS`). Never hardcode or log credentials.

---

## 3. Panel API Quirks & Implementation Rules

Naively written code against ISPmanager 6 API fails silently due to five specific behaviors:

1. **`file.download` Must NOT Include `out=json`:**
   When invoked with `out=json`, the panel returns a JSON description of the download form instead of file bytes. Call `func=file.download` without `out=json` to receive raw stream content.
2. **Automatic CRLF → LF Normalization on Write:**
   The panel normalizes all line endings to LF. Normalize line endings locally before sending to prevent false drift in post-write SHA256 / diff verifications.
3. **Validate Success via `<doc><ok/></doc>` Only:**
   Check explicitly for the presence of `doc.ok` (or `<ok/>`), never merely the absence of `error`.
4. **Never Delete Before Writing:**
   Do NOT use `file.delete` → `file.new` → `file.edit`. A connection interruption leaves the production file missing. Overwrite existing files directly. Use `file.new` only if the file does not exist in the directory listing (`func=file`).
5. **`FileMaxEditSize` Limit:**
   The panel built-in editor has a file size ceiling (typically 1024 KB). Read larger files using `file.download`.

### API Function Reference

To inspect an unfamiliar function schema, call it with `out=json` to retrieve all form fields:

| Function | Required / Key Parameters |
|---|---|
| `file.upload` | `plid` (target dir), `name`, `filename`, `type` (`data` for multipart or `link` for remote URL) |
| `file.extract` | `plid` (archive path), `dirlist` (destination path), `newdir`, `goto` |
| `file.pack` | `plid` (source dir), `arcname`, `filetype` (`zip`, `tar`, `tgz`) |
| `file.new` | `plid` (target dir), `name`, `type` (`file` or `dir`) |
| `file.edit` | `elid` (absolute file path), `fdata` (content), `encoding=UTF-8`, `sok=ok` |
| `file.delete` | `plid` (parent dir), `elid` (target name) |

> [!WARNING]
> In ISPmanager API, commas in `elid` separate multiple items for bulk actions. Validate that target paths contain no unescaped commas.

---

## 4. Webroot Security Hygiene

Every file inside the document root is publicly accessible over HTTP. Never leave exposed artifacts:

- **Local Backups Only:** Keep rollback backups in `secrets/deploy-backups/` locally. Never store `.bak`, `.old`, or timestamped dumps in webroot.
- **Immediate Archive Removal:** After unpacking a deployment zip via `file.extract`, immediately delete the `.zip` file.
- **Pack Outside Webroot:** When generating snapshots with `file.pack`, write to a folder outside webroot (e.g., `agent-tmp/` or parent directory), then retrieve via FTP.
- **Post-Deploy Audit:** Check the directory listing after mass operations to confirm zero temporary files remain.

---

## 5. Repository Deployment Scripts

Do not invent custom deployment scripts. Use the tested repository tools:

```bash
# Deploy a single static file or standalone landing page
python scripts/deploy_static_file.py <file> --site <domain> --remote-name <name>

# Deploy a theme template
python scripts/deploy_theme_file.py <file> --remote <path-in-theme>

# Deploy multiple theme files and purge WP cache atomically
python scripts/deploy_theme.py --file header.php --file style.css

# Check production drift (normalized diff between local git and live server)
python scripts/deploy_theme.py --drift
```

Scripts automatically:
1. Verify syntax locally (`php -l` for PHP files).
2. Download and backup the live version to `secrets/deploy-backups/`.
3. Upload new version and read it back to verify byte match.
4. Rollback automatically if write fails.

---

## 6. Staging / Pre-launch Domain Protection

When deploying drafts, mirrors, or staging sites to subdomains, apply three-layer index protection:

1. **`robots.txt` in root:**
   ```txt
   User-agent: *
   Disallow: /
   ```
2. **Template `<head>` tag:**
   ```html
   <meta name="robots" content="noindex, nofollow">
   ```
3. **`.htaccess` HTTP header:**
   ```apache
   Header set X-Robots-Tag "noindex, nofollow"
   ```

---

## 7. Document-Root by Framework

Always check the site's configured document root in ISPmanager before uploading:
- **WordPress:** Root directory (`/www/<domain>/`).
- **Statamic & Laravel:** `public/` subdirectory (`/www/<domain>/public`).
Uploading to the root when the panel expects `public/` appears successful but serves nothing to visitors.
