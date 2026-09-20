
import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
import os
import requests
import re
import json
import sys
from urllib.parse import urlparse
from bs4 import BeautifulSoup, Comment

sys.stdout.reconfigure(encoding='utf-8')

urls = [
    # Main & Services
    "https://fastup.by/",
    "https://fastup.by/razrabotka-saitov/",
    "https://fastup.by/seo-prodvizhenie/",
    "https://fastup.by/kontekstnaya-reklama/",
    "https://fastup.by/graficheskiy-i-veb-dizayn/",
    "https://fastup.by/o-nas/",
    "https://fastup.by/kontakty/",
    "https://fastup.by/cases/",
    "https://fastup.by/oplata/",
    "https://fastup.by/oferta/",
    "https://fastup.by/geo-prodvizhenie/",
    "https://fastup.by/geo-audit-system/",
    "https://fastup.by/indeks-vidimosti/",

    # Articles
    "https://fastup.by/kak-vybrat-veb-studiyu-v-belarusi/",
    "https://fastup.by/seo-pricing-mesyats-belarus/",
    "https://fastup.by/kak-proverit-vidit-li-neyroset-sayt/",
    "https://fastup.by/sait-na-konstruktore-tormozit-perenosit-ili-peredelyvat/",
    "https://fastup.by/wordpress-vs-tilda-chto-vybrat-2026/",
    "https://fastup.by/kak-ya-napisal-svoi-instrumenty-na-chistom-php-bez-bd-i-s-nulya-poluchil-1500-organiki-v-mesyats/",
    "https://fastup.by/geo-ne-pro-blokirovki-botov-chto-realno-reshaet-uvidit-li-neyroset-vash-biznes/",
    "https://fastup.by/strategiya-entity-first-seo-kak-strukturirovannye-dannye-i-semanticheskoe-yadro-povyshayut-vidimost-v-2024/",
    "https://fastup.by/kakoj-sajt-luchshe-podhodit-vashemu-biznesu-v-2026-godu/",
    "https://fastup.by/skolko-stoit-sait-v-belarusi-2026/",

    # Cases
    "https://fastup.by/cases/kubdecor-by/",
    "https://fastup.by/cases/artblock-by/",
    "https://fastup.by/cases/agrofamaly-by/",
    "https://fastup.by/cases/oleg-climate-catalog/",
    "https://fastup.by/cases/selauto-1600-grid/",
    "https://fastup.by/cases/royalhouse-tailwind-booking/",
    "https://fastup.by/cases/pridemotors-2-day-launch/",
    "https://fastup.by/cases/microapps-platform/"
]

output_dir = os.path.join(r'g:\fastup-mentor', 'content', 'live-pages')
os.makedirs(output_dir, exist_ok=True)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def normalize_text(t):
    t = re.sub(r'\s+', ' ', t).strip()
    return t.rstrip('+').strip()

def extract_faqs(soup):
    faq_items = []
    seen_questions = set()

    # 1. JSON-LD FAQPage Schema
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '')
            if isinstance(data, dict):
                graph = data.get('@graph', [data])
            elif isinstance(data, list):
                graph = data
            else:
                graph = []

            for item in graph:
                if item.get('@type') == 'FAQPage':
                    entities = item.get('mainEntity', [])
                    for q in entities:
                        q_name = normalize_text(q.get('name', ''))
                        a_text = q.get('acceptedAnswer', {}).get('text', '').strip()
                        norm_q_key = re.sub(r'\W+', '', q_name.lower())
                        if q_name and a_text and norm_q_key not in seen_questions:
                            seen_questions.add(norm_q_key)
                            a_soup = BeautifulSoup(a_text, 'html.parser')
                            faq_items.append((q_name, normalize_text(a_soup.get_text())))
        except Exception:
            pass

    # 2. HTML Schema.org Question / Answer
    for q_elem in soup.find_all(attrs={'itemprop': 'name'}):
        parent = q_elem.find_parent(attrs={'itemscope': True, 'itemtype': lambda v: v and 'Question' in v})
        if parent:
            q_text = normalize_text(q_elem.get_text())
            a_elem = parent.find(attrs={'itemprop': 'text'})
            norm_q_key = re.sub(r'\W+', '', q_text.lower())
            if a_elem and q_text and norm_q_key not in seen_questions:
                seen_questions.add(norm_q_key)
                faq_items.append((q_text, normalize_text(a_elem.get_text())))

    return faq_items

def clean_html_to_markdown(html_text, page_url):
    soup = BeautifulSoup(html_text, 'html.parser')

    # Extract FAQs BEFORE decomposing script tags
    faq_items = extract_faqs(soup)

    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Decompose inline FAQ containers from main body pass to avoid double rendering
    for faq_container in soup.select('.faq, .faq-section, [itemscope][itemtype*="FAQPage"]'):
        faq_container.decompose()

    # Remove boilerplate elements
    for selector in [
        'script', 'style', 'noscript', 'iframe', 'svg', 'header', 'footer', 'nav',
        '.site-header', '.site-footer', '#masthead', '#colophon',
        '.cookie-notice', '.admin-bar', '#wpadminbar', '.header', '.footer',
        '#cookie-law-info-bar', '.modal', '.popup'
    ]:
        for el in soup.select(selector):
            el.decompose()

    # Target main content container if available
    content_node = (
        soup.select_one('article') or 
        soup.select_one('main') or 
        soup.select_one('.entry-content') or 
        soup.select_one('#primary') or 
        soup.select_one('.site-main') or 
        soup.body
    )

    if not content_node:
        return ""

    # Page H1 or title
    page_h1 = ""
    h1_tag = soup.find('h1')
    if h1_tag:
        page_h1 = normalize_text(h1_tag.get_text())
    elif soup.title:
        page_h1 = normalize_text(soup.title.get_text())

    md_lines = []
    seen_blocks = set()

    for el in content_node.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'blockquote', 'table', 'div']):
        if el.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = '#' * int(el.name[1])
            txt = normalize_text(el.get_text())
            if txt and txt not in seen_blocks:
                seen_blocks.add(txt)
                md_lines.append(f"\n{level} {txt}\n")
        elif el.name == 'p':
            txt = normalize_text(el.get_text())
            if txt and txt not in seen_blocks:
                seen_blocks.add(txt)
                md_lines.append(f"{txt}\n")
        elif el.name in ['ul', 'ol']:
            for li in el.find_all('li', recursive=False):
                li_txt = normalize_text(li.get_text())
                if li_txt:
                    md_lines.append(f"- {li_txt}")
            md_lines.append("")
        elif el.name == 'blockquote':
            txt = normalize_text(el.get_text())
            if txt:
                md_lines.append(f"> {txt}\n")
        elif el.name == 'div' and ('geo-callout' in el.get('class', []) or 'callout' in el.get('class', [])):
            txt = normalize_text(el.get_text())
            if txt:
                md_lines.append(f"> [!NOTE]\n> {txt}\n")

    # Append structured FAQ section if FAQs were found
    if faq_items:
        md_lines.append("\n## FAQ / Часто задаваемые вопросы\n")
        for q, a in faq_items:
            md_lines.append(f"### Q: {q}\n")
            md_lines.append(f"{a}\n")

    raw_md = "\n".join(md_lines)
    clean_md = re.sub(r'\n{3,}', '\n\n', raw_md).strip()

    word_count = len(clean_md.split())

    frontmatter = f"""---
title: "{page_h1}"
url: "{page_url}"
extracted_at: "2026-08-09"
faq_count: {len(faq_items)}
word_count: {word_count}
---

# {page_h1}

{clean_md}
"""
    return frontmatter

print(f"Extracting clean markdown content & FAQs for {len(urls)} live pages into {output_dir}...")

success = 0
for u in urls:
    parsed = urlparse(u)
    path_slug = parsed.path.strip('/')
    if not path_slug:
        filename = "front-page.md"
    else:
        filename = path_slug.replace('/', '_') + ".md"

    filepath = os.path.join(output_dir, filename)
    try:
        r = requests.get(u, headers=headers, timeout=10)
        if r.status_code == 200:
            md_content = clean_html_to_markdown(r.text, u)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)
            word_c = len(md_content.split())
            print(f"[OK 200] {filename:45} | {word_c:5} words | {filepath}")
            success += 1
        else:
            print(f"[ERR {r.status_code}] {u}")
    except Exception as e:
        print(f"[FAIL] {u}: {e}")

print(f"Extraction complete: {success}/{len(urls)} pages converted to clean markdown with FAQ support in content/live-pages/!")
