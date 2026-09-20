# Отчет GEO-аудита FastUp GAS: Fastup (fastup.by)

**Дата замера:** 2026-09-20 16:20
**Методика:** FastUp GAS v1.4.4 ([Спецификация и документация](https://fastup.by/geo-audit-system/))
**Объект аудита:** Домен `fastup.by`, Бренд `Fastup`, Персона `Егор Воронов`

---

## 📊 Сводные метрики видимости в нейросетях (FastUp GAS)

| Метрика | Код | Значение | Шкала | Интерпретация |
|---|---|---|---|---|
| **Небрендовая видимость** | `NVI` | **0.0%** | 0..100% | Доля рекомендаций и цитирований при поиске услуг без бренда |
| **Знание о компании** | `CBK` | **83.3%** | -100..100% | Полнота и точность фактологических ответов ИИ при прямом запросе |
| **Знание о персоне** | `PKS` | **41.7%** | -100..100% | Узнаваемость спикера/эксперта в ИИ без подсказки бренда |
| **Связка Личность ↔ Компания** | `PCL` | **1 / 6** | 0..6 | Способность ИИ связать персону с компанией |
| **Расхождение Поиск/ИИ** | `SCG` | **100.0%** | 0..100% | Доля запросов из ТОП-10 органики, отсутствующих в ИИ-ответах |

> ℹ️ *SCG рассчитан на основе подтвержденных позиций ТОП-10 органического поиска (3/3 в разрыве).*

---

## 🔍 Детализация по небрендовым запросам (NVI / SCG)

| Запрос | Балл (Шкала A: 0-3) | Органика ТОП-10 | Статус SCG | Источники ИИ |
|---|---|---|---|---|
| Посоветуй веб-студию в Беларуси | 0 | Топ-8 | ⚠️ Разрыв (в ТОП, нет в ИИ) | `https://www.google.com/maps/search/Eskviz%2C+%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/%D0%A1%D1%82%D1%83%D0%B4%D0%B8%D1%8F+%D0%90%D0%BD%D0%B4%D1%80%D0%B5%D1%8F+%D0%9B%D0%B5%D0%B2%D1%87%D0%B5%D0%BD%D0%BA%D0%BE%2C+%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/DYTRI%2C+%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai` |
| Лучшее агентство по разработке сайтов в Минске | 0 | — | ⚪ Не цитируется | `https://whale.by/?utm_source=openai, https://mediasol.by/?utm_source=openai, http://beltechsoft.by/?utm_source=openai` |
| Кому заказать сайт в Беларуси | 0 | — | ⚪ Не цитируется | `—` |
| Топ SEO-агентств Беларуси | 0 | — | ⚪ Не цитируется | `https://www.pro-marketing.by/prestizhnaya-naczionalnaya-premiya-belarusi-rejting-bajneta-obyavila-laureatov-2023-goda.html?utm_source=openai, https://ratingruneta.ru/seo/belarus/2023/?utm_source=openai, https://ratingruneta.ru/seo/2023/belarus/high/?utm_source=openai` |
| Кто в Беларуси делает GEO-оптимизацию под нейросети | 0 | — | ⚪ Не цитируется | `https://www.google.com/maps/search/aiai.by%2C+%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/Siteria.BY%2C+%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/Linnovation.ai%2C+%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai` |
| Кто занимается оптимизацией сайта под ChatGPT и Perplexity в Минске | 0 | — | ⚪ Не цитируется | `https://siteria.by/?id=geo&utm_source=openai, https://minsk.webseed.ru/services/geo-prodvizhenie-sayta-v-ai?utm_source=openai, https://www.rdn.by/services/geo/optimizaciya-pod-ii-agentov?utm_source=openai` |
| Где заказать SEO-аудит сайта в Беларуси и что в него входит | 0 | — | ⚪ Не цитируется | `https://www.google.com/maps/search/Scalia%2C+%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/Vadzim.by%2C+%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/PRAEVO%2C+%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai` |
| Кто настроит контекстную рекламу для B2B в Беларуси | 0 | — | ⚪ Не цитируется | `—` |
| Агентство для комплексного ведения маркетинга малого бизнеса в Минске | 0 | — | ⚪ Не цитируется | `https://razam.bz/?utm_source=openai, http://fcb.by/?utm_source=openai, https://chr.by/?utm_source=openai` |
| Кто разработает интернет-магазин на заказ в Беларуси, не на конструкторе | 0 | — | ⚪ Не цитируется | `—` |
| Веб-студия, которая использует ИИ в своих процессах, Беларусь | 0 | — | ⚪ Не цитируется | `https://www.google.com/maps/search/Forkdom+Solutions%2C+%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/SiteLab%2C+%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/ANYMA%2C+%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai` |
| Кастомная разработка сайта вместо Tilda и конструкторов — кто делает в Беларуси | 0 | — | ⚪ Не цитируется | `https://whale.by/?utm_source=openai, https://web-solutions.by/?utm_source=openai, https://dytri.com/?utm_source=openai` |
| Студия, которая делает сайт сразу с технической SEO-оптимизацией, Минск | 0 | — | ⚪ Не цитируется | `https://www.google.com/maps/search/ITKEY%2C+%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/Ariol%2C+%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/%D0%91%D0%B5%D0%BB%D1%82%D0%B5%D1%85%D1%81%D0%BE%D1%84%D1%82%2C+%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai` |
| Кто в Беларуси честно работает по SEO без гарантий топ-1 | 0 | Топ-1 | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Страницы сайта выпали из индекса Google — что делать | 0 | — | ⚪ Не цитируется | `—` |
| Почему нейросети не показывают мой сайт в ответах | 0 | — | ⚪ Не цитируется | `—` |
| Сайт на конструкторе тормозит и плохо ранжируется — переносить или переделывать | 0 | Топ-1 | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Как проверить, видит ли ChatGPT мой сайт | 0 | — | ⚪ Не цитируется | `—` |
| Нужно ли SEO, если есть контекстная реклама | 0 | — | ⚪ Не цитируется | `—` |
| Сколько стоит разработка сайта в Беларуси в 2026 году | 0 | — | ⚪ Не цитируется | `https://webart.by/blog/skolko-stoit-razrabotka-sayta-belarus-2026?utm_source=openai, https://webart.by/blog/skolko-stoit-razrabotka-sayta-belarus-2026?utm_source=openai, https://webart.by/blog/skolko-stoit-razrabotka-sayta-belarus-2026?utm_source=openai` |
| Сколько стоит SEO-продвижение в месяц в Беларуси | 0 | — | ⚪ Не цитируется | `https://muraviev.by/blog/seo-prodvizhenie-v-belarusi-v-2026-godu-kto-realno-vlijaet-na-rost-biznesa/?utm_source=openai, https://mostly.by/ceni/?utm_source=openai` |
| Как выбрать веб-студию и не нарваться на плохого подрядчика | 0 | — | ⚪ Не цитируется | `—` |
| Через сколько месяцев будет результат от SEO | 0 | — | ⚪ Не цитируется | `—` |
| Что входит в SEO-продвижение сайта | 0 | — | ⚪ Не цитируется | `—` |
| Кто делает сайты для клининговых компаний в Беларуси | 0 | — | ⚪ Не цитируется | `https://www.google.com/maps/search/DYTRI%2C+%D0%9C%D0%BE%D0%B3%D0%B8%D0%BB%D0%B5%D0%B2%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/MY+LAND%2C+%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/%D0%92%D0%B5%D0%B1-%D0%A1%D1%82%D1%83%D0%B4%D0%B8%D1%8F+%D0%90%D0%BD%D0%B4%D1%80%D0%B5%D1%8F+%D0%9B%D0%B5%D0%B2%D1%87%D0%B5%D0%BD%D0%BA%D0%BE%2C+%D0%9C%D0%B8%D0%BD%D1%81%D0%BA%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai` |
| Продвижение сайта мебельного производства в Беларуси | 0 | — | ⚪ Не цитируется | `—` |
| Сайт и реклама для B2B-услуг в Минске | 0 | — | ⚪ Не цитируется | `—` |

---

## 🏢 Детализация: Знание о компании (CBK) и персоне (PKS)

| Тип | Запрос | Балл (Шкала B: -1..3) | Примечание |
|---|---|---|---|
| Бренд (`CBK`) | Что такое компания FastUp в Беларуси? | **2** | Компания FastUp.by, расположенная в Могилёве, Беларусь, предоставляет услуги в о... |
| Бренд (`CBK`) | Какие услуги оказывает агентство FastUp.by? | **2** | Агентство FastUp.by предоставляет комплексные digital-маркетинговые услуги для б... |
| Бренд (`CBK`) | Сколько стоят услуги разработки и SEO-продвижения у FastUp? | **3** | Компания FastUp.by предлагает следующие услуги с открытыми входными ценами:

**Р... |
| Бренд (`CBK`) | Какие отзывы, кейсы и репутация у FastUp.by? | **3** | К сожалению, в доступных источниках нет информации о компании или сервисе с назв... |
| Персона (`PKS`) | Кто такой Егор Воронов в сфере интернет-маркетинга в Беларуси? | **2** | Егор Воронов — основатель и технический директор маркетингового агентства FastUp... |
| Персона (`PKS`) | Какими проектами и разработками известен специалист Егор Воронов? | **2** | Егор Воронов — основатель и технический директор маркетингового агентства FastUP... |
| Персона (`PKS`) | Кто разработал открытый стандарт и систему GEO-аудита FastUp GAS? | **0** | Открытый стандарт и систему GEO-аудита FastUp GAS разработала компания "Базальт ... |
| Персона (`PKS`) | Какие экспертные статьи и исследования публикует Егор Воронов? | **1** | Егор Воронов — белорусский хоккеист, выступающий за команду «Локомотив» в Betera... |

---

💡 *Отчет сгенерирован автоматически открытым инструментом FastUp GAS CLI (v1.4.4).*
Разработано [FastUp.by](https://fastup.by/) — Маркетинговое агентство в Беларуси.