# Отчет GEO-аудита FastUp GAS: Kubdecor (kubdecor.by)

**Дата замера:** 2026-08-23 00:31
**Методика:** FastUp GAS v1.4.3 ([Спецификация и документация](https://fastup.by/geo-audit-system/))
**Объект аудита:** Домен `kubdecor.by`, Бренд `Kubdecor`, Персона ``

---

## 📊 Сводные метрики видимости в нейросетях (FastUp GAS)

| Метрика | Код | Значение | Шкала | Интерпретация |
|---|---|---|---|---|
| **Небрендовая видимость** | `NVI` | **15.4%** | 0..100% | Доля рекомендаций и цитирований при поиске услуг без бренда |
| **Знание о компании** | `CBK` | **83.3%** | -100..100% | Полнота и точность фактологических ответов ИИ при прямом запросе |
| **Знание о персоне** | `PKS` | **0.0%** | -100..100% | Узнаваемость спикера/эксперта в ИИ без подсказки бренда |
| **Связка Личность ↔ Компания** | `PCL` | **0 / 6** | 0..6 | Способность ИИ связать персону с компанией |
| **Расхождение Поиск/ИИ** | `SCG` | **76.9%** | 0..100% | Доля запросов из ТОП-10 органики, отсутствующих в ИИ-ответах |

> ℹ️ *SCG рассчитан по общему пулу небрендовых запросов (для точной калибровки укажите `organic_top10: true` в queries.json).*

---

## 🔍 Детализация по небрендовым запросам (NVI / SCG)

| Запрос | Балл (Шкала A: 0-3) | Органика ТОП-10 | Статус SCG | Источники ИИ |
|---|---|---|---|---|
| Отделка балкона в Могилёве под ключ | 2 | — | ✅ Цитируется | `https://balkonmogilev.by/obshivka-uteplenie-otdelka/, https://uslugi.yandex.ru/158-mogilev/category?text=балкон под ключ, https://rembor.by/portfolio/` |
| Остекление балкона в Могилёве цена | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `https://balkonmogilev.by/balkonnye-ramy-rassrochka/, https://germes-trast.by/osteklenie-balkonov-i-lodzhij/holodnoe-osteklenie-balkona/, https://mogilevoknapvh.by/tseny-kalkulyator/` |
| Утепление балкона в Могилёве | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `https://okna-komforta.by/uteplenie-balkonov, https://balkonmogilev.by/obshivka-uteplenie-otdelka/, https://uslugi.yandex.ru/158-mogilev/category?text=утепление балкона` |
| Отделка лоджии ламинатом в Могилёве | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Утепление балконов и лоджий в Могилёве | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `https://okna-komforta.by/uteplenie-balkonov, https://balkonmogilev.by/obshivka-uteplenie-otdelka/, https://uslugi.yandex.ru/158-mogilev/category?text=утепление балкона` |
| Обшивка балкона вагонкой Могилёв | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Остекление балкона тёплое или холодное что выбрать | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Ремонт балкона под ключ Могилёв цена | 2 | — | ✅ Цитируется | `https://kak-svoim.ru/cities/mogilev/, https://uslugi.yandex.ru/158-mogilev/category?text=балкон под ключ, https://okna-master24.by/otdelka-balkonov/` |
| Какие профильные системы для остекления балкона лучше | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `https://rudesignshop.ru/blog/kakoy-profil-luchshe-dlya-ostekleniya-balkona/, https://fabrikaokna.ru/blog/vybrat-okna-dlya-balkonov-i-lodzhiy/, https://oknafactoria.ru/articles/kak-vybrat-profil-dlya-balkonnogo-ostekleniya-ot-tepla-do-stilya-bez-kompromissov/` |
| Отделка балкона ламинатом или вагонкой что дешевле | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Куда обратиться за отделкой балкона в Могилёве | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Сколько стоит отделка балкона в Могилёве за м2 | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `https://balkonmogilev.by/obshivka-uteplenie-otdelka/, https://kak-svoim.ru/cities/mogilev/, https://zakazat-okna.by/balkon/otdelka-balkona-i-lodzhii/` |
| Компания по остеклению и отделке балконов в Могилёве | 2 | — | ✅ Цитируется | `https://altec.by/, https://uslugi.yandex.ru/158-mogilev/category?text=остекление балконов, https://balkonmogilev.by/` |

---

## 🏢 Детализация: Знание о компании (CBK) и персоне (PKS)

| Тип | Запрос | Балл (Шкала B: -1..3) | Примечание |
|---|---|---|---|
| Бренд (`CBK`) | Что такое Куб Декор (kubdecor.by) в Могилёве? | **2** | <?xml version="1.0" encoding="UTF-8" ?>
<yandexsearch version="1.0">
  <respon... |
| Бренд (`CBK`) | Расскажи про компанию Kubdecor, отделка балконов | **3** | <?xml version="1.0" encoding="UTF-8" ?>
<yandexsearch version="1.0">
  <respon... |
| Бренд (`CBK`) | Kubdecor Могилёв отзывы | **2** | <?xml version="1.0" encoding="UTF-8" ?>
<yandexsearch version="1.0">
  <respon... |
| Бренд (`CBK`) | Куб Декор балконы — чем занимается компания? | **3** | <?xml version="1.0" encoding="UTF-8" ?>
<yandexsearch version="1.0">
  <respon... |

---

💡 *Отчет сгенерирован автоматически открытым инструментом FastUp GAS CLI (v1.4.3).*
Разработано [FastUp.by](https://fastup.by/) — Маркетинговое агентство в Беларуси.