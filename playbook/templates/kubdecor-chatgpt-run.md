# Отчет GEO-аудита FastUp GAS: Kubdecor (kubdecor.by)

**Дата замера:** 2026-08-23 00:40
**Методика:** FastUp GAS v1.4.3 ([Спецификация и документация](https://fastup.by/geo-audit-system/))
**Объект аудита:** Домен `kubdecor.by`, Бренд `Kubdecor`, Персона ``

---

## 📊 Сводные метрики видимости в нейросетях (FastUp GAS)

| Метрика | Код | Значение | Шкала | Интерпретация |
|---|---|---|---|---|
| **Небрендовая видимость** | `NVI` | **0.0%** | 0..100% | Доля рекомендаций и цитирований при поиске услуг без бренда |
| **Знание о компании** | `CBK` | **58.3%** | -100..100% | Полнота и точность фактологических ответов ИИ при прямом запросе |
| **Знание о персоне** | `PKS` | **0.0%** | -100..100% | Узнаваемость спикера/эксперта в ИИ без подсказки бренда |
| **Связка Личность ↔ Компания** | `PCL` | **1 / 6** | 0..6 | Способность ИИ связать персону с компанией |
| **Расхождение Поиск/ИИ** | `SCG` | **100.0%** | 0..100% | Доля запросов из ТОП-10 органики, отсутствующих в ИИ-ответах |

> ℹ️ *SCG рассчитан по общему пулу небрендовых запросов (для точной калибровки укажите `organic_top10: true` в queries.json).*

---

## 🔍 Детализация по небрендовым запросам (NVI / SCG)

| Запрос | Балл (Шкала A: 0-3) | Органика ТОП-10 | Статус SCG | Источники ИИ |
|---|---|---|---|---|
| Отделка балкона в Могилёве под ключ | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `https://www.google.com/maps/search/%D0%9E%D0%BA%D0%BD%D0%B0+%D0%9C%D0%B0%D1%81%D1%82%D0%B5%D1%80%2C+%D0%9C%D0%BE%D0%B3%D0%B8%D0%BB%D1%91%D0%B2%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/%D0%A1%D0%B8%D1%82%D0%B8%D0%A1%D1%82%D1%80%D0%BE%D0%B9%D0%9A%D0%BE%D0%BC%D0%BF%D0%B0%D0%BD%D0%B8%2C+%D0%9C%D0%BE%D0%B3%D0%B8%D0%BB%D1%91%D0%B2%D1%81%D0%BA%D0%B0%D1%8F+%D0%BE%D0%B1%D0%BB%D0%B0%D1%81%D1%82%D1%8C%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/%D0%90%D0%BB%D0%B5%D0%BA%D1%81%D0%B5%D0%B9+%D0%9A.%2C+%D0%9C%D0%BE%D0%B3%D0%B8%D0%BB%D1%91%D0%B2%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai` |
| Остекление балкона в Могилёве цена | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `https://balkonmogilev.by/?utm_source=openai, https://mogilev.redsale.by/prices/remont/okna/osteklenie-balkona?utm_source=openai, https://oknolux.by/?utm_source=openai` |
| Утепление балкона в Могилёве | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `https://utepleniealp.by/service/fasadnie-rabota/?utm_source=openai, https://balkonmogilev.by/?utm_source=openai, https://okna-master24.by/otdelka-balkonov/?utm_source=openai` |
| Отделка лоджии ламинатом в Могилёве | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Утепление балконов и лоджий в Могилёве | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `https://okna-master24.by/?utm_source=openai, http://www.windtech.by/?utm_source=openai, http://aleont.by/?utm_source=openai` |
| Обшивка балкона вагонкой Могилёв | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `https://www.google.com/maps/search/%D0%A1%D1%82%D1%80%D0%BE%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D0%BD%D0%B0%D1%8F+%D0%BA%D0%BE%D0%BC%D0%BF%D0%B0%D0%BD%D0%B8%D1%8F+%22%D0%9C%D0%BE%D0%B3%D0%B8%D0%BB%D1%91%D0%B2%D0%A1%D1%82%D1%80%D0%BE%D0%B9%22%2C+%D0%9C%D0%BE%D0%B3%D0%B8%D0%BB%D1%91%D0%B2%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/%D0%9A%D0%BE%D0%BC%D0%BF%D0%B0%D0%BD%D0%B8%D1%8F+%22%D0%91%D0%B0%D0%BB%D0%BA%D0%BE%D0%BD%D0%9F%D0%BB%D1%8E%D1%81%22%2C+%D0%9C%D0%BE%D0%B3%D0%B8%D0%BB%D1%91%D0%B2%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/%D0%A1%D1%82%D1%83%D0%B4%D0%B8%D1%8F+%22%D0%94%D0%B8%D0%B7%D0%B0%D0%B9%D0%BD%D0%91%D0%B0%D0%BB%D0%BA%D0%BE%D0%BD%22%2C+%D0%9C%D0%BE%D0%B3%D0%B8%D0%BB%D1%91%D0%B2%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai` |
| Остекление балкона тёплое или холодное что выбрать | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Ремонт балкона под ключ Могилёв цена | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `https://www.rabotniki.ua/price/kosmeticheskiy-remont-balkona/mogilevpodolskiy?utm_source=openai` |
| Какие профильные системы для остекления балкона лучше | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Отделка балкона ламинатом или вагонкой что дешевле | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Куда обратиться за отделкой балкона в Могилёве | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `https://www.google.com/maps/search/%D0%A1%D0%BE%D0%B2%D1%80%D0%B5%D0%BC%D0%B5%D0%BD%D0%BD%D1%8B%D0%B5+%D0%B1%D0%B0%D0%BB%D0%BA%D0%BE%D0%BD%D1%8B%2C+%D0%9C%D0%BE%D0%B3%D0%B8%D0%BB%D1%91%D0%B2%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/%D0%9E%D0%BA%D0%BD%D0%B0+%D0%9C%D0%B0%D1%81%D1%82%D0%B5%D1%80%2C+%D0%9C%D0%BE%D0%B3%D0%B8%D0%BB%D1%91%D0%B2%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai, https://www.google.com/maps/search/%D0%A7%D0%B8%D1%81%D1%82%D1%8B%D0%B5+%D0%BE%D0%BA%D0%BD%D0%B0%2C+%D0%9C%D0%BE%D0%B3%D0%B8%D0%BB%D1%91%D0%B2%2C+%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D1%8C?utm_source=openai` |
| Сколько стоит отделка балкона в Могилёве за м2 | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `—` |
| Компания по остеклению и отделке балконов в Могилёве | 0 | — | ⚠️ Разрыв (в ТОП, нет в ИИ) | `http://www.windtech.by/?utm_source=openai, https://globalstroy.by/?utm_source=openai, https://www.demplast.by/kontakty?utm_source=openai` |

---

## 🏢 Детализация: Знание о компании (CBK) и персоне (PKS)

| Тип | Запрос | Балл (Шкала B: -1..3) | Примечание |
|---|---|---|---|
| Бренд (`CBK`) | Что такое Куб Декор (kubdecor.by) в Могилёве? | **0** | 
## [Куб Декор](https://www.google.com/maps/search/%D0%9A%D1%83%D0%B1+%D0%94%D0%... |
| Бренд (`CBK`) | Расскажи про компанию Kubdecor, отделка балконов | **2** | Компания «Куб Декор» специализируется на ремонте и отделке балконов в Могилёве. ... |
| Бренд (`CBK`) | Kubdecor Могилёв отзывы | **3** | К сожалению, мне не удалось найти отзывов о компании "Kubdecor" в Могилёве. Возм... |
| Бренд (`CBK`) | Куб Декор балконы — чем занимается компания? | **2** | Компания «Куб Декор» из Могилёва специализируется на ремонте и отделке балконов ... |

---

💡 *Отчет сгенерирован автоматически открытым инструментом FastUp GAS CLI (v1.4.3).*
Разработано [FastUp.by](https://fastup.by/) — Маркетинговое агентство в Беларуси.