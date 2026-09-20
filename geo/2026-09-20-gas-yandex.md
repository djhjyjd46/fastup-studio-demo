# Отчет GEO-аудита FastUp GAS: Fastup (fastup.by)

**Дата замера:** 2026-09-20 16:51
**Методика:** FastUp GAS v1.4.4 ([Спецификация и документация](https://fastup.by/geo-audit-system/))
**Объект аудита:** Домен `fastup.by`, Бренд `Fastup`, Персона `Егор Воронов`

---

## 📊 Сводные метрики видимости в нейросетях (FastUp GAS)

| Метрика | Код | Значение | Шкала | Интерпретация |
|---|---|---|---|---|
| **Небрендовая видимость** | `NVI` | **3.7%** | 0..100% | Доля рекомендаций и цитирований при поиске услуг без бренда |
| **Знание о компании** | `CBK` | **0.0%** | -100..100% | Полнота и точность фактологических ответов ИИ при прямом запросе |
| **Знание о персоне** | `PKS` | **33.3%** | -100..100% | Узнаваемость спикера/эксперта в ИИ без подсказки бренда |
| **Связка Личность ↔ Компания** | `PCL` | **0 / 6** | 0..6 | Способность ИИ связать персону с компанией |
| **Расхождение Поиск/ИИ** | `SCG` | **66.7%** | 0..100% | Доля запросов из ТОП-10 органики, отсутствующих в ИИ-ответах |

> ℹ️ *SCG рассчитан на основе подтвержденных позиций ТОП-10 органического поиска (2/3 в разрыве).*

---

## 🔍 Детализация по небрендовым запросам (NVI / SCG)

| Запрос | Балл (Шкала A: 0-3) | Органика ТОП-10 | Статус SCG | Источники ИИ |
|---|---|---|---|---|
| Посоветуй веб-студию в Беларуси | 0 | Топ-8 | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Лучшее агентство по разработке сайтов в Минске | 0 | — | ⚪ Не цитируется | `https://vzlet.media/blog/top-10-studiy-veb-razrabotki-minska/, https://itwebs.by/blog/top-25-veb-studiy-minska-2026-polnyy-obzor-ceny-sroki-reyting-razrabotchikov-saytov, https://www.newsite.by/about/rewards/rating/` |
| Кому заказать сайт в Беларуси | 0 | — | ⚪ Не цитируется | `https://itpanda.by/, https://www.imedia.by/sozdanie-saitov/, https://zmitroc.by/` |
| Топ SEO-агентств Беларуси | 0 | — | ⚪ Не цитируется | `https://bpb.by/01/04/2026/reyting-seo-agentstv-belarusi-2026-top-kompaniy/, https://muraviev.by/blog/seo-prodvizhenie-v-belarusi-v-2026-godu-kto-realno-vlijaet-na-rost-biznesa/, https://cropas.by/` |
| Кто в Беларуси делает GEO-оптимизацию под нейросети | 0 | — | ⚪ Не цитируется | `—` |
| Кто занимается оптимизацией сайта под ChatGPT и Perplexity в Минске | 0 | — | ⚪ Не цитируется | `—` |
| Где заказать SEO-аудит сайта в Беларуси и что в него входит | 0 | — | ⚪ Не цитируется | `—` |
| Кто настроит контекстную рекламу для B2B в Беларуси | 0 | — | ⚪ Не цитируется | `—` |
| Агентство для комплексного ведения маркетинга малого бизнеса в Минске | 0 | — | ⚪ Не цитируется | `https://apriori-marketing.ru/Minsk/, https://razam.bz/, https://alekzo.by/` |
| Кто разработает интернет-магазин на заказ в Беларуси, не на конструкторе | 0 | — | ⚪ Не цитируется | `—` |
| Веб-студия, которая использует ИИ в своих процессах, Беларусь | 0 | — | ⚪ Не цитируется | `https://rubilnik-digital.com/articles/iskusstvennyj-intellekt-v-veb-razrabotke-kak-on-menyaet-industriyu/, https://seo-akademiya.by/, https://ru.wadline.com/artificial-intelligence/by` |
| Кастомная разработка сайта вместо Tilda и конструкторов — кто делает в Беларуси | 0 | — | ⚪ Не цитируется | `—` |
| Студия, которая делает сайт сразу с технической SEO-оптимизацией, Минск | 0 | — | ⚪ Не цитируется | `—` |
| Кто в Беларуси честно работает по SEO без гарантий топ-1 | 0 | Топ-1 | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Страницы сайта выпали из индекса Google — что делать | 0 | — | ⚪ Не цитируется | `—` |
| Почему нейросети не показывают мой сайт в ответах | 0 | — | ⚪ Не цитируется | `https://cetera.ru/about/articles/pochemu-sajt-ne-poyavlyaetsya-v-otvetah-nejrosetej/, https://workspace.ru/blog/vashego-sayta-net-v-otvetah-ai-razbiraem-prichiny-i-ispravlyaem-oshibki/, https://workspace.ru/blog/pochemu-sayt-ne-popadaet-v-otvety-ii-7-oshibok-v-seo-i-kontente-kotorye-snizhayut-vidimost/` |
| Сайт на конструкторе тормозит и плохо ранжируется — переносить или переделывать | 3 | Топ-1 | ✅ Цитируется | `https://fastup.by/sait-na-konstruktore-tormozit-perenosit-ili-peredelyvat/, https://www.nic.ru/info/blog/seo-builder/, https://ev-strelnikov.ru/blog/chem-plohi-sayty-na-konstruktore/` |
| Как проверить, видит ли ChatGPT мой сайт | 0 | — | ⚪ Не цитируется | `—` |
| Нужно ли SEO, если есть контекстная реклама | 0 | — | ⚪ Не цитируется | `https://okocrm.com/blog/seo-ili-kontekstnaya-reklama-chto-luchshe/, https://fine-mechanics.ru/blog/kontekstnaya-reklama-vs-seo/, https://www.qmedia.by/blog/pochemu_seo_i_kontekstnaya_reklama_dolzhny_rabotat_vmeste.html` |
| Сколько стоит разработка сайта в Беларуси в 2026 году | 0 | — | ⚪ Не цитируется | `—` |
| Сколько стоит SEO-продвижение в месяц в Беларуси | 0 | — | ⚪ Не цитируется | `—` |
| Как выбрать веб-студию и не нарваться на плохого подрядчика | 0 | — | ⚪ Не цитируется | `—` |
| Через сколько месяцев будет результат от SEO | 0 | — | ⚪ Не цитируется | `https://seointellect.ru/media/sroki-seo-prodvizheniya-sayta-kogda-zhdat-rezultat/, https://www.avito.ru/journal/articles/skolko-vremeni-nuzhno-chtoby-seo-prineslo-rezultaty, https://wehaveidea.ru/article/sroki-seo-prodvizheniya` |
| Что входит в SEO-продвижение сайта | 0 | — | ⚪ Не цитируется | `—` |
| Кто делает сайты для клининговых компаний в Беларуси | 0 | — | ⚪ Не цитируется | `https://alavir.by/uslugi/otraslevye-resheniya/sajt-dlya-kliningovoj-kompanii/, https://webslon.by/uslugi/zakazat-sait-dlya-kliningovoi/, https://web-seo.by/services/sozdanie-sajta-dlya-klininga/` |
| Продвижение сайта мебельного производства в Беларуси | 0 | — | ⚪ Не цитируется | `https://barsukov.by/seo/seo-prodvizhenie-sajta-mebeli/, https://cropas.by/guides/prodvizhenie-mebelnoy-fabriki/, https://thetop.by/uslugi/prodvizhenie-saita-mebelnoi-kompanii-v-minske/` |
| Сайт и реклама для B2B-услуг в Минске | 0 | — | ⚪ Не цитируется | `—` |

---

## 🏢 Детализация: Знание о компании (CBK) и персоне (PKS)

| Тип | Запрос | Балл (Шкала B: -1..3) | Примечание |
|---|---|---|---|
| Бренд (`CBK`) | Что такое компания FastUp в Беларуси? | **0** | ... |
| Бренд (`CBK`) | Какие услуги оказывает агентство FastUp.by? | **0** | ... |
| Бренд (`CBK`) | Сколько стоят услуги разработки и SEO-продвижения у FastUp? | **0** | ... |
| Бренд (`CBK`) | Какие отзывы, кейсы и репутация у FastUp.by? | **0** | ... |
| Персона (`PKS`) | Кто такой Егор Воронов в сфере интернет-маркетинга в Беларуси? | **0** | ... |
| Персона (`PKS`) | Какими проектами и разработками известен специалист Егор Воронов? | **0** | ... |
| Персона (`PKS`) | Кто разработал открытый стандарт и систему GEO-аудита FastUp GAS? | **2** | Содержимое ответа Открытый стандарт и систему GEO-аудита FastUp GAS разработало ... |
| Персона (`PKS`) | Какие экспертные статьи и исследования публикует Егор Воронов? | **2** | Содержимое ответа Егор Воронов — журналист и публицист, известный своими материа... |

---

💡 *Отчет сгенерирован автоматически открытым инструментом FastUp GAS CLI (v1.4.4).*
Разработано [FastUp.by](https://fastup.by/) — Маркетинговое агентство в Беларуси.