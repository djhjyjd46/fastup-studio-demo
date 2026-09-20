#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Publish/update a WordPress post via the REST API using Application Password auth.

Credentials come from .env (WP_SITE_URL, WP_APP_USER, WP_APP_PASSWORD) — never hardcode
them here. See integrations/wordpress.md for setup and the approval policy.

Credentials are read from .env if present, otherwise from the process environment
(the "Fastup-mentor" environment sets WP_* vars directly — no .env file needed).

Usage:
    # create/update a blog post (default type)
    python3 scripts/wp_publish.py --title "..." --content-file content/some-article.md \
        [--status draft|publish] [--post-id 123 to update instead of create]

    # full draft with metadata: category, excerpt, featured image, FAQ (ACF)
    python3 scripts/wp_publish.py --title "..." --content-file content/article.html \
        --category web-development --excerpt "Краткое описание для выдачи" \
        --featured-image content/img/preview.jpg --faq-file content/article.faq.json

    # update an existing PAGE (e.g. the "О нас" page, id 1851)
    python3 scripts/wp_publish.py --type page --post-id 1851 --title "О нас" \
        --content-file positioning/about-page.body.html --status publish

    # list available categories (to pick a slug for --category)
    python3 scripts/wp_publish.py --list-categories

FAQ file format (--faq-file), matches the site's ACF group:
    {"heading": "Частые вопросы по теме",
     "items": [{"question": "...", "answer": "..."}, ...]}
"""
import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; FastUP-Agent/1.0)"}


def load_env(repo_root: Path) -> dict:
    """Read WP_* from .env if it exists, else fall back to the process environment."""
    keys = ("WP_SITE_URL", "WP_APP_USER", "WP_APP_PASSWORD")
    env = {}
    from env_load import env_file_path  # из worktree — .env основной копии
    env_path = env_file_path()
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"')
    for k in keys:
        if not env.get(k) and os.environ.get(k):
            env[k] = os.environ[k]
    missing = [k for k in keys if not env.get(k)]
    if missing:
        sys.exit(
            f"Missing credentials: {', '.join(missing)} — set them in .env or the "
            "environment (see integrations/wordpress.md)."
        )
    return env


def api_get(env: dict, path: str, **params):
    """GET a REST endpoint and return parsed JSON."""
    resp = requests.get(
        f"{env['WP_SITE_URL'].rstrip('/')}/wp-json/wp/v2/{path}",
        params=params,
        auth=(env["WP_APP_USER"], env["WP_APP_PASSWORD"]),
        headers=UA,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def resolve_category(env: dict, wanted: str) -> int:
    """Turn a category slug (or numeric id) into a category id, failing loudly if unknown."""
    if wanted.isdigit():
        return int(wanted)
    cats = api_get(env, "categories", per_page=100)
    for c in cats:
        if c["slug"] == wanted:
            return c["id"]
    known = ", ".join(sorted(c["slug"] for c in cats))
    sys.exit(f"Unknown category '{wanted}'. Available slugs: {known}")


def upload_media(env: dict, image_path: Path) -> int:
    """Upload an image to the media library, return its attachment id (for featured_media)."""
    if not image_path.exists():
        sys.exit(f"Featured image not found: {image_path}")
    mime, _ = mimetypes.guess_type(image_path.name)
    headers = dict(UA)
    headers["Content-Disposition"] = f'attachment; filename="{image_path.name}"'
    headers["Content-Type"] = mime or "application/octet-stream"
    resp = requests.post(
        f"{env['WP_SITE_URL'].rstrip('/')}/wp-json/wp/v2/media",
        data=image_path.read_bytes(),
        auth=(env["WP_APP_USER"], env["WP_APP_PASSWORD"]),
        headers=headers,
        timeout=120,
    )
    resp.raise_for_status()
    media_id = resp.json()["id"]
    print(f"  uploaded featured image → media id={media_id}")
    return media_id


def build_faq(faq_path: Path) -> dict:
    """Read a FAQ json file and map it onto the site's ACF field names."""
    data = json.loads(faq_path.read_text(encoding="utf-8"))
    items = data.get("items") or []
    if not items:
        sys.exit(f"FAQ file {faq_path} has no 'items' — omit --faq-file instead.")
    return {
        "faq_heading": data.get("heading", "Частые вопросы"),
        "faq_items": [
            {"faq_question": i["question"], "faq_answer": i["answer"]} for i in items
        ],
    }


def build_tldr(tldr_path: Path) -> dict:
    """Read a TL;DR json file and map it onto the ACF repeater `tldr_items`.

    Feeds the theme's "Главное за 30 секунд" block (components/tldr-block.php),
    rendered by single-article.php before the article body. The block is skipped
    entirely when the field is empty, so omit --tldr-file rather than passing an
    empty list.

    Accepts either {"items": ["...", "..."]} or a bare JSON list of strings.
    """
    data = json.loads(tldr_path.read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else (data.get("items") or [])
    items = [str(i).strip() for i in items if str(i).strip()]
    if not items:
        sys.exit(f"TL;DR file {tldr_path} has no items — omit --tldr-file instead.")
    return {"tldr_items": [{"tldr_item": i} for i in items]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", type=Path, help="Markdown file to publish (optional positional arg)")
    parser.add_argument("--title")
    parser.add_argument("--content-file", type=Path, help="Markdown or HTML file with content")
    parser.add_argument(
        "--status",
        default=None,
        choices=["draft", "publish"],
        help="New posts default to draft. On --post-id updates the current status is "
        "preserved unless you pass this flag explicitly.",
    )
    parser.add_argument("--post-id", type=int, default=None)
    parser.add_argument(
        "--type",
        default="post",
        choices=["post", "page"],
        help="post → /wp/v2/posts, page → /wp/v2/pages (e.g. the О нас page)",
    )
    parser.add_argument("--parent", type=int, default=None, help="Parent page ID for hierarchical pages")
    parser.add_argument("--slug", help="URL slug; WordPress derives one from the title if omitted")
    parser.add_argument("--excerpt", help="Short description shown in listings and meta")
    parser.add_argument(
        "--category",
        help="Category slug (or numeric id) — run --list-categories to see options",
    )
    parser.add_argument(
        "--featured-image", type=Path, help="Local image file to upload and set as the preview"
    )
    parser.add_argument(
        "--faq-file",
        type=Path,
        help="JSON file with FAQ items, written into the site's ACF faq fields",
    )
    parser.add_argument(
        "--tldr-file",
        type=Path,
        help=(
            "JSON file with TL;DR items ({\"items\": [...]} or a bare list), written into "
            "the ACF repeater tldr_items — the «Главное за 30 секунд» block above the article"
        ),
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="Print available categories and exit (no changes made)",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip interactive confirmation (use only when explicitly approved by Egor)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    env = load_env(repo_root)

    if args.list_categories:
        for c in api_get(env, "categories", per_page=100):
            print(f"{c['id']}\t{c['slug']}\t{c['name']} ({c['count']} posts)")
        return

    content_path = args.file or args.content_file
    if not content_path:
        sys.exit("Please provide a file to publish (e.g. `python scripts/wp_publish.py content/drafts/post.md`).")
    args.content_file = content_path

    import re
    import yaml

    raw_text = args.content_file.read_text(encoding="utf-8")
    frontmatter = {}
    content = raw_text

    # Parse YAML frontmatter if present
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw_text, flags=re.DOTALL)
    if match:
        fm_raw, content = match.groups()
        try:
            frontmatter = yaml.safe_load(fm_raw) or {}
        except yaml.YAMLError:
            pass

    # Title: CLI arg > Frontmatter > First H1
    title = args.title or frontmatter.get("title")
    if not title:
        h1_match = re.search(r"^\s*#\s+(.+)$", content, flags=re.MULTILINE)
        if h1_match:
            title = h1_match.group(1).strip()
        else:
            title = args.content_file.stem.replace("-", " ").capitalize()

    # Auto-discover adjacent FAQ/TLDR files if not explicitly provided
    auto_faq = args.content_file.with_suffix(".faq.json")
    if not args.faq_file and auto_faq.exists():
        args.faq_file = auto_faq
        print(f"  [ACF FAQ] Автоматически подключён сопутствующий файл: {auto_faq.name}")

    auto_tldr = args.content_file.with_suffix(".tldr.json")
    if not args.tldr_file and auto_tldr.exists():
        args.tldr_file = auto_tldr
        print(f"  [ACF TL;DR] Автоматически подключён сопутствующий файл: {auto_tldr.name}")

    # Convert Markdown to HTML if .md file
    if args.content_file.suffix.lower() == ".md":
        try:
            import markdown
            content = markdown.markdown(content, extensions=["extra", "tables", "toc", "fenced_code", "nl2br"])
        except ImportError:
            pass

    # Commercial cross-linking check (mandatory for agency posts)
    if args.type == "post":
        core_targets = [
            "/geo-prodvizhenie/",
            "/razrabotka-saitov/",
            "/seo-prodvizhenie/",
            "/kontekstnaya-reklama/",
            "/graficheskiy-i-veb-dizayn/",
            "/geo-audit-system/",
            "/keys-",
        ]
        found_links = [t for t in core_targets if t in content]
        if not found_links:
            print("[ВНИМАНИЕ] В статье НЕТ коммерческой перелинковки на услуги FastUp!")
            print("  Рекомендуется добавить ссылки на /geo-prodvizhenie/, /razrabotka-saitov/, /geo-audit-system/ и т.д.")
        else:
            print(f"  [OK] Коммерческая перелинковка ({len(found_links)} целей): {', '.join(found_links)}")

    # Status resolution.
    endpoint = "pages" if args.type == "page" else "posts"
    current_status = None
    if args.post_id:
        current_status = api_get(env, f"{endpoint}/{args.post_id}").get("status")
    status = args.status or frontmatter.get("status") or (current_status if args.post_id else "draft")
    if status == "published":
        status = "publish"
    effective_status = status or (current_status if args.post_id else "draft")
    if effective_status == "published":
        effective_status = "publish"


    # Live change confirmation
    live_change = effective_status == "publish"
    if live_change and not args.yes:
        what = "страница" if args.type == "page" else "статья"
        if args.post_id and status and status != current_status:
            change = f"status {current_status} → {status}"
        elif args.post_id:
            change = f"остаётся published, меняется содержимое (id={args.post_id})"
        else:
            change = "новая публикация сразу в published"
        confirm = input(
            f"Изменение уйдёт на живой сайт сразу ({what}, {change}). "
            "Это одобрено Егором на этот конкретный материал? (yes/no): "
        )
        if confirm.strip().lower() != "yes":
            sys.exit("Отменено — меняй живой сайт только после явного одобрения.")

    if args.post_id and status == "draft" and current_status == "publish" and not args.yes:
        confirm = input(
            f"ВНИМАНИЕ: {args.post_id} сейчас опубликован, а --status draft снимет его "
            "с сайта. Точно снимаем с публикации? (yes/no): "
        )
        if confirm.strip().lower() != "yes":
            sys.exit("Отменено — материал остаётся опубликованным.")

    payload = {"title": title, "content": content.strip()}
    if effective_status:
        payload["status"] = effective_status

    # Slug
    slug = args.slug or frontmatter.get("slug")
    if slug:
        payload["slug"] = slug

    # Author (defaults to Egor Voronov: ID 9)
    author_id = 9
    payload["author"] = author_id

    # Excerpt
    excerpt = args.excerpt or frontmatter.get("excerpt")
    if excerpt:
        payload["excerpt"] = excerpt

    # Categories
    categories = []
    if args.category:
        categories.append(resolve_category(env, args.category))
    elif frontmatter.get("categories") and args.type == "post":
        for cat in frontmatter["categories"]:
            try:
                categories.append(resolve_category(env, str(cat)))
            except SystemExit:
                pass
    if categories:
        payload["categories"] = categories

    if args.parent is not None and args.type == "page":
        payload["parent"] = args.parent

    if args.featured_image:
        payload["featured_media"] = upload_media(env, args.featured_image)

    # ACF fields
    acf_data = {}
    if args.faq_file:
        acf_data.update(build_faq(args.faq_file))
    elif frontmatter.get("faq_items"):
        raw_faq = frontmatter["faq_items"]
        faq_items = []
        for item in raw_faq:
            q = item.get("faq_question") or item.get("question") or ""
            a = item.get("faq_answer") or item.get("answer") or ""
            if q and a:
                faq_items.append({"faq_question": q, "faq_answer": a})
        acf_data["faq_heading"] = frontmatter.get("faq_heading", "Частые вопросы")
        acf_data["faq_items"] = faq_items

    if args.tldr_file:
        acf_data.update(build_tldr(args.tldr_file))
    elif frontmatter.get("tldr_items"):
        raw_tldr = frontmatter["tldr_items"]
        tldr_items = []
        for item in raw_tldr:
            if isinstance(item, dict):
                tldr_items.append(item)
            elif isinstance(item, str) and item.strip():
                tldr_items.append({"tldr_item": item.strip()})
        acf_data["tldr_items"] = tldr_items

    if frontmatter.get("related_service"):
        acf_data["related_service"] = frontmatter["related_service"]

    if frontmatter.get("cta_heading"):
        acf_data["cta_heading"] = frontmatter["cta_heading"]
    if frontmatter.get("cta_text"):
        acf_data["cta_text"] = frontmatter["cta_text"]

    if acf_data:
        payload["acf"] = acf_data
        details = []
        if "faq_items" in acf_data:
            details.append(f"FAQ ({len(acf_data['faq_items'])} вопр.)")
        if "tldr_items" in acf_data:
            details.append(f"TL;DR ({len(acf_data['tldr_items'])} п.)")
        if "related_service" in acf_data:
            details.append(f"Услуга ({acf_data['related_service']})")
        print(f"  [ACF] Нативные поля темы: {', '.join(details)}")

    # Rank Math description check & meta
    rm_desc = frontmatter.get("rank_math_description", "")
    if rm_desc and len(rm_desc) > 160:
        print(f"WARNING: rank_math_description is {len(rm_desc)} chars (recommended <= 160 chars).")

    meta = {}
    if frontmatter.get("rank_math_title"):
        meta["rank_math_title"] = frontmatter["rank_math_title"]
    if frontmatter.get("rank_math_description"):
        meta["rank_math_description"] = frontmatter["rank_math_description"]
    if frontmatter.get("rank_math_focus_keyword"):
        meta["rank_math_focus_keyword"] = frontmatter["rank_math_focus_keyword"]
    if meta:
        payload["meta"] = meta


    base = env["WP_SITE_URL"].rstrip("/")
    url = f"{base}/wp-json/wp/v2/{endpoint}"
    if args.post_id:
        url = f"{url}/{args.post_id}"

    resp = requests.post(
        url,
        json=payload,
        auth=(env["WP_APP_USER"], env["WP_APP_PASSWORD"]),
        headers=UA,
        timeout=30,
    )
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        print(f"ERROR: {e}\nResponse: {resp.text}")
        sys.exit(1)

    data = resp.json()
    print(f"OK: {args.type} id={data['id']} status={data['status']} link={data.get('link')}")
    if acf_data.get("faq_items"):
        print(f"  FAQ items written: {len(acf_data['faq_items'])}")
    if acf_data.get("tldr_items"):
        print(f"  TL;DR items written: {len(acf_data['tldr_items'])}")


if __name__ == "__main__":
    main()

