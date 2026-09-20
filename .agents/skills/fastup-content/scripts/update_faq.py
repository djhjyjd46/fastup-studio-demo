#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Read and update the ACF FAQ block of a page on fastup.by via the REST API.

Replaces the two one-shot scripts that used to live here (update_faq.py for the
«Разработка сайтов» page and update_kontakty_faq.py for «Контакты»). Those hardcoded
both the page id and the answer text, wrote straight to the live site with no
confirmation, and addressed items by blind index — so a changed FAQ order silently
overwrote the wrong question. FAQ text now lives in content/faq/*.json, and answers are
matched by question text, never by position.

Credentials come from .env or the process environment, same as wp_publish.py.

Usage:
    # inspect what is live right now (read-only, always safe)
    python3 scripts/update_faq.py --page-id 1736 --show

    # replace the whole FAQ block from a data file
    python3 scripts/update_faq.py --page-id 2519 --faq-file content/faq/kontakty.faq.json

    # patch one answer, matching the question by a substring
    python3 scripts/update_faq.py --page-id 1736 \
        --set-answer "качество сайта" "Ошибки по нашей вине исправляем бесплатно..."

    # preview any change without writing
    python3 scripts/update_faq.py --page-id 1736 --set-answer "..." "..." --dry-run

FAQ file format matches wp_publish.py --faq-file:
    {"heading": "Частые вопросы", "items": [{"question": "...", "answer": "..."}, ...]}
"""
import argparse
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wp_publish import UA, load_env  # noqa: E402


def get_page(env: dict, page_id: int) -> dict:
    resp = requests.get(
        f"{env['WP_SITE_URL'].rstrip('/')}/wp-json/wp/v2/pages/{page_id}",
        auth=(env["WP_APP_USER"], env["WP_APP_PASSWORD"]),
        headers=UA,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def show(items: list, heading: str) -> None:
    print(f"heading: {heading!r}")
    if not items:
        print("  (no faq_items on this page)")
    for i, item in enumerate(items):
        print(f"\n  [{i}] {item.get('faq_question', '')}")
        print(f"      {item.get('faq_answer', '')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page-id", type=int, required=True)
    parser.add_argument("--show", action="store_true", help="Print the live FAQ and exit")
    parser.add_argument("--faq-file", type=Path, help="Replace the whole FAQ block from this file")
    parser.add_argument(
        "--set-answer",
        nargs=2,
        action="append",
        metavar=("QUESTION_SUBSTRING", "NEW_ANSWER"),
        help="Patch one answer; the question is matched case-insensitively by substring",
    )
    parser.add_argument("--heading", help="Override the faq_heading value")
    parser.add_argument("--dry-run", action="store_true", help="Show the diff, write nothing")
    args = parser.parse_args()

    env = load_env(Path(__file__).resolve().parent.parent)
    page = get_page(env, args.page_id)
    acf = page.get("acf") or {}
    items = list(acf.get("faq_items") or [])
    heading = acf.get("faq_heading", "Частые вопросы")

    title = (page.get("title") or {}).get("rendered", "")
    print(f"page {args.page_id} — {title} ({page.get('link', '')})\n")

    if args.show or not (args.faq_file or args.set_answer or args.heading):
        show(items, heading)
        if not args.show:
            print("\nNothing to do — pass --faq-file, --set-answer or --heading to change something.")
        return

    changes = []

    if args.faq_file:
        data = json.loads(args.faq_file.read_text(encoding="utf-8"))
        new_items = data.get("items") or []
        if not new_items:
            sys.exit(f"{args.faq_file} has no 'items'.")
        changes.append(f"replace all {len(items)} item(s) with {len(new_items)} from {args.faq_file}")
        items = [{"faq_question": i["question"], "faq_answer": i["answer"]} for i in new_items]
        heading = args.heading or data.get("heading", heading)

    for needle, new_answer in args.set_answer or []:
        matches = [
            i for i, item in enumerate(items)
            if needle.lower() in (item.get("faq_question") or "").lower()
        ]
        if not matches:
            sys.exit(
                f"No question matches {needle!r}. Run --show to see the live questions."
            )
        if len(matches) > 1:
            found = "; ".join(items[i].get("faq_question", "") for i in matches)
            sys.exit(f"{needle!r} matches {len(matches)} questions — be more specific: {found}")
        idx = matches[0]
        old_answer = items[idx].get("faq_answer", "")
        if old_answer == new_answer:
            print(f"  [{idx}] already up to date, skipping: {items[idx].get('faq_question','')}")
            continue
        changes.append(
            f"[{idx}] {items[idx].get('faq_question','')}\n"
            f"      было:  {old_answer}\n"
            f"      стало: {new_answer}"
        )
        items[idx] = dict(items[idx], faq_answer=new_answer)

    if args.heading and heading != args.heading:
        changes.append(f"heading: {heading!r} → {args.heading!r}")
        heading = args.heading

    if not changes:
        print("Nothing changed — the live FAQ already matches what you asked for.")
        return

    print("Планируемые изменения:")
    for c in changes:
        print(f"  {c}")

    if args.dry_run:
        print("\n--dry-run: ничего не записано.")
        return

    confirm = input(
        f"\nЭто уйдёт на живой сайт сразу (страница {args.page_id}, {title}). "
        "Одобрено Егором на этот конкретный материал? (yes/no): "
    )
    if confirm.strip().lower() != "yes":
        sys.exit("Отменено — меняй живой сайт только после явного одобрения.")

    resp = requests.post(
        f"{env['WP_SITE_URL'].rstrip('/')}/wp-json/wp/v2/pages/{args.page_id}",
        json={"acf": dict(acf, faq_heading=heading, faq_items=items)},
        auth=(env["WP_APP_USER"], env["WP_APP_PASSWORD"]),
        headers=UA,
        timeout=30,
    )
    resp.raise_for_status()
    written = ((resp.json().get("acf") or {}).get("faq_items")) or []
    print(f"OK: страница {args.page_id}, FAQ items на сайте: {len(written)}")


if __name__ == "__main__":
    main()
