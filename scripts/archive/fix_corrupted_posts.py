import re
from pathlib import Path
import requests
from scripts.wp_publish import load_env, api_get, UA

def main():
    env = load_env(Path('.'))
    base = env['WP_SITE_URL'].rstrip('/') + '/wp-json/wp/v2'
    auth = (env['WP_APP_USER'], env['WP_APP_PASSWORD'])

    def update_post(pid, new_content):
        resp = requests.post(
            f"{base}/posts/{pid}",
            json={'content': new_content},
            auth=auth,
            headers=UA,
            timeout=30
        )
        resp.raise_for_status()
        print(f"Successfully updated post {pid}")

    # 1. POST 3074
    p3074 = api_get(env, 'posts/3074', context='edit')
    c3074 = p3074['content']['raw']
    m3074 = re.search(r'<a href="/geo-audit-system/">FastUp <a href="https://fastup\.by/matematika-fastup-gas-standart/"[^>]*>\?+ \?+ FastUp GAS</a> v1\.4</a>', c3074)
    if m3074:
        good_3074 = '<a href="/geo-audit-system/">FastUp GAS v1.4</a> (разобранному в <a href="/matematika-fastup-gas-standart/">математическом регламенте</a>)'
        c3074_fixed = c3074[:m3074.start()] + good_3074 + c3074[m3074.end():]
        update_post(3074, c3074_fixed)
    else:
        print("Pattern not found in 3074!")

    # 2. POST 2957
    p2957 = api_get(env, 'posts/2957', context='edit')
    c2957 = p2957['content']['raw']
    m2957 = re.search(r'<a href="/seo-prodvizhenie/"><a href="https://fastup\.by/seo-vnutri-geo-prodvizheniya/"[^>]*>\?+ \?+ SEO \?+ GEO</a>-продвижении</a>', c2957)
    if m2957:
        good_2957 = '<a href="/seo-prodvizhenie/">SEO-продвижении</a> (подробнее о различиях — в статье <a href="/seo-vnutri-geo-prodvizheniya/">SEO внутри GEO</a>)'
        c2957_fixed = c2957[:m2957.start()] + good_2957 + c2957[m2957.end():]
        update_post(2957, c2957_fixed)
    else:
        print("Pattern not found in 2957!")

    # 3. POST 2938
    p2938 = api_get(env, 'posts/2938', context='edit')
    c2938 = p2938['content']['raw']
    m2938 = re.search(r'<a href="/geo-audit-system/"><a href="https://fastup\.by/matematika-fastup-gas-standart/"[^>]*>\?+<a href="https://fastup\.by/indeks-vidimosti/"[^>]*>.*?</a> FastUp GAS v1\.4</a></a>', c2938)
    if m2938:
        good_2938 = '<a href="/geo-audit-system/">FastUp GAS v1.4</a>, формулы которого описаны в <a href="/matematika-fastup-gas-standart/">математическом регламенте</a>, а результаты — в <a href="/indeks-vidimosti/">индексе видимости</a>'
        c2938_fixed = c2938[:m2938.start()] + good_2938 + c2938[m2938.end():]
        update_post(2938, c2938_fixed)
    else:
        print("Pattern not found in 2938!")

    # 4. POST 2836
    p2836 = api_get(env, 'posts/2836', context='edit')
    c2836 = p2836['content']['raw']
    m2836 = re.search(r'<a href="https://fastup\.by/wordpress-ili-tilda-chto-vybrat-v-belarusi-2026/"[^>]*>\?+ WordPress \?+ Tilda</a>', c2836)
    if m2836:
        good_2836 = 'WordPress (подробнее — в статье <a href="/wordpress-ili-tilda-chto-vybrat-v-belarusi-2026/">WordPress или Tilda: что выбрать</a>)'
        c2836_fixed = c2836[:m2836.start()] + good_2836 + c2836[m2836.end():]
        update_post(2836, c2836_fixed)
    else:
        print("Pattern not found in 2836!")

if __name__ == '__main__':
    main()
