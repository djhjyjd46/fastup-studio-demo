# Отчет GEO-аудита FastUp GAS: Kubdecor (kubdecor.by)

**Дата замера:** 2026-08-23 00:25
**Методика:** FastUp GAS v1.4.3 ([Спецификация и документация](https://fastup.by/geo-audit-system/))
**Объект аудита:** Домен `kubdecor.by`, Бренд `Kubdecor`, Персона ``

---

## 📊 Сводные метрики видимости в нейросетях (FastUp GAS)

| Метрика | Код | Значение | Шкала | Интерпретация |
|---|---|---|---|---|
| **Небрендовая видимость** | `NVI` | **25.6%** | 0..100% | Доля рекомендаций и цитирований при поиске услуг без бренда |
| **Знание о компании** | `CBK` | **50.0%** | -100..100% | Полнота и точность фактологических ответов ИИ при прямом запросе |
| **Знание о персоне** | `PKS` | **0.0%** | -100..100% | Узнаваемость спикера/эксперта в ИИ без подсказки бренда |
| **Связка Личность ↔ Компания** | `PCL` | **0 / 6** | 0..6 | Способность ИИ связать персону с компанией |
| **Расхождение Поиск/ИИ** | `SCG` | **61.5%** | 0..100% | Доля запросов из ТОП-10 органики, отсутствующих в ИИ-ответах |

> ℹ️ *SCG рассчитан по общему пулу небрендовых запросов (для точной калибровки укажите `organic_top10: true` в queries.json).*

---

## 🔍 Детализация по небрендовым запросам (NVI / SCG)

| Запрос | Балл (Шкала A: 0-3) | Органика ТОП-10 | Статус SCG | Источники ИИ |
|---|---|---|---|---|
| Отделка балкона в Могилёве под ключ | 2 | — | ✅ Цитируется | `https://okna-master24.by/otdelka-balkonov/, https://www.instagram.com/pv_mogilev/, https://mogilev.domodel.by/categories/balkon-pod-klyuch` |
| Остекление балкона в Могилёве цена | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `https://oknapvhmogilev.by/osteklenie-balkonov-v-mogileve, https://balconov.by/, https://okna-ori.by/Могилёв/Остекление` |
| Утепление балкона в Могилёве | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Отделка лоджии ламинатом в Могилёве | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Утепление балконов и лоджий в Могилёве | 2 | — | ✅ Цитируется | `https://okna-master24.by/otdelka-balkonov/, https://mogilev24.by/uteplenie-balkonov/, https://domex.by/mogilev/remont/uteplenie-balkonov-i-lodzhij` |
| Обшивка балкона вагонкой Могилёв | 2 | — | ✅ Цитируется | `https://okna-master24.by/otdelka-balkonov/, https://mogilev.pulscen.by/price/180211-otdelka-balkonov-i-lodzhiy, https://kubdecor.by/` |
| Остекление балкона тёплое или холодное что выбрать | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Ремонт балкона под ключ Могилёв цена | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Какие профильные системы для остекления балкона лучше | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Отделка балкона ламинатом или вагонкой что дешевле | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `https://profmontag.by/obshivka-balkona-derevyannoj-vagonkoj-minsk/, https://superbalkon.by/otdelka, https://ardom.by/balkony/vnutrennyaya-obshivka-balkona.html` |
| Куда обратиться за отделкой балкона в Могилёве | 2 | — | ✅ Цитируется | `https://okna-master24.by/otdelka-balkonov/, https://bel-stroy.by/uteplenie-i-otdelka-balkonov-v-mogileve/, https://mogilev.redsale.by/remont/otdelka-balkonov-i-lodzhii` |
| Сколько стоит отделка балкона в Могилёве за м2 | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Компания по остеклению и отделке балконов в Могилёве | 2 | — | ✅ Цитируется | `http://www.altec.by/, https://okna-master24.by/otdelka-balkonov/, https://balkonmogilev.by/obshivka-uteplenie-otdelka/` |

---

## 🏢 Детализация: Знание о компании (CBK) и персоне (PKS)

| Тип | Запрос | Балл (Шкала B: -1..3) | Примечание |
|---|---|---|---|
| Бренд (`CBK`) | Что такое Куб Декор (kubdecor.by) в Могилёве? | **0** | <?xml version="1.0" encoding="UTF-8" ?>
<yandexsearch version="1.0">
  <respon... |
| Бренд (`CBK`) | Расскажи про компанию Kubdecor, отделка балконов | **2** | <answer>PGRpdiBjbGFzcz0iaGR6YVdlIiBqc2NvbnRyb2xsZXI9IiIgZGF0YS1pcy1kZXNrdG9wPSIx... |
| Бренд (`CBK`) | Kubdecor Могилёв отзывы | **2** | <?xml version="1.0" encoding="UTF-8" ?>
<yandexsearch version="1.0">
  <respon... |
| Бренд (`CBK`) | Куб Декор балконы — чем занимается компания? | **2** | <answer>PGRpdiBjbGFzcz0iaGR6YVdlIiBqc2NvbnRyb2xsZXI9IiIgZGF0YS1pcy1kZXNrdG9wPSIx... |

---

💡 *Отчет сгенерирован автоматически открытым инструментом FastUp GAS CLI (v1.4.3).*
Разработано [FastUp.by](https://fastup.by/) — Маркетинговое агентство в Беларуси.