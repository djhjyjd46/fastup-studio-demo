
import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
import requests, collections, urllib.parse
from env_load import require
tok = require("YANDEX_OAUTH_TOKEN"); uid = require("YANDEX_USER_ID"); hid = require("YANDEX_HOST_ID")
H = {"Authorization": f"OAuth {tok}"}
base = f"https://api.webmaster.yandex.net/v4/user/{uid}/hosts/{hid}/links/external/samples"
links, offset = [], 0
while True:
    r = requests.get(base, headers=H, params={"offset": offset, "limit": 100}, timeout=30)
    if r.status_code != 200:
        print("HTTP", r.status_code, r.text[:300]); break
    d = r.json()
    batch = d.get("links", [])
    links += batch
    total = d.get("count", 0)
    offset += len(batch)
    if not batch or offset >= total or offset >= 1000: 
        print(f"# всего доступно примеров: {total}, выгружено: {len(links)}")
        break
dom = collections.Counter(urllib.parse.urlparse(l["source_url"]).netloc for l in links)
dest = collections.Counter(urllib.parse.urlparse(l["destination_url"]).path for l in links)
print("\n## Доноры (домен -> сколько ссылок)")
for d_, n in dom.most_common(25): print(f"  {n}\t{d_}")
print("\n## Куда ведут (страница -> сколько ссылок)")
for p, n in dest.most_common(20): print(f"  {n}\t{p}")
print("\n## Свежие 10 (дата обнаружения)")
for l in sorted(links, key=lambda x: x.get("discovery_date",""), reverse=True)[:10]:
    print(f"  {l.get('discovery_date','')[:10]}  {l['source_url'][:80]} -> {urllib.parse.urlparse(l['destination_url']).path}")
