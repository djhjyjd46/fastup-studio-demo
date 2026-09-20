#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""
scripts/check_ai_markers.py — Проверка текста на маркеры ИИ и признаки машинной генерации.

Основано на правилах:
- content/ai-detection-markers-checklist.md
- content/voice.md
- .claude/skills/fastup-content/SKILL.md

Проверяет:
1. Жёсткие маркеры (артефакты LLM-интерфейсов, теги, мусор).
2. Обороты-штампы и книжные клише («золотое правило», «переломный момент», «задействовал» и т.д.).
3. Стоковые аналогии («швейцарский нож», «рабочая лошадка», «термометр» и др.).
4. Запрещённые конструкции («X, а не Y»).
5. Плотность длинного тире (—) на 1000 знаков.
6. Эмодзи в техническом/деловом тексте.
7. Burstiness (ритмическая неровность / вариативность длины предложений).
8. Лексическое разнообразие (Type-Token Ratio).

Использование:
    python scripts/check_ai_markers.py path/to/file.md
    python scripts/check_ai_markers.py --text "Текст для быстрой проверки..."
"""

import sys
import os
import re
import math
import argparse
from typing import List, Dict, Any

# Жёсткие маркеры генерации (копипаст из чат-ботов)
RIGID_PATTERNS = [
    (r"\[cite:\s*\d+\]", "Обрывок цитирования [cite: N]"),
    (r"citeturn\d+search\d+", "Маркер поиска citeturn0search0"),
    (r":contentReference\[oaicite:\d+\]", "Служебный тег OpenAI oaicite"),
    (r"sandbox:/mnt/data/", "Путь песочницы Python sandbox:/mnt/data/"),
    (r"<\/?think>", "Тег процесса размышления <think>"),
    (r"```(?:markdown|python|bash)?\s*$", "Висячий пустой блок кода"),
    (r"^(?:Конечно|Безусловно|Рад помочь|Вот готовый вариант)[!:,]", "Вводная вежливая фраза ассистента"),
]

# Книжные клише и маркерные обороты русскоязычной генерации
CLICHE_PATTERNS = [
    (r"\bэто стало переломным моментом\b", "Клише «это стало переломным моментом»"),
    (r"\bзолотое правило\b", "Клише «золотое правило»"),
    (r"\bклассическая фаза [«\"]песочницы[»\"]\b", "Клише «классическая фаза песочницы»"),
    (r"\bважно подчеркнуть\b", "Канцелярский штамп «важно подчеркнуть»"),
    (r"\bважно отметить\b", "Канцелярский штамп «важно отметить»"),
    (r"\bследует отметить\b", "Канцелярский штамп «следует отметить»"),
    (r"\bне секрет, что\b", "Вводный штамп «не секрет, что»"),
    (r"\bв современном мире\b", "Штамп «в современном мире»"),
    (r"\bв эпоху стремительного\b", "Штамп «в эпоху стремительного...»"),
    (r"\bзадействовал\b", "Книжное «задействовал» вместо разговорного «использовал/взял»"),
    (r"\bпредпринял попытку\b", "Книжное «предпринял попытку» вместо «попробовал»"),
    (r"\bданное обстоятельство представляет собой\b", "Тяжёлый канцелярит вместо «это»"),
    (r"\bзакрывает боли?\b", "Инфобизнесовый штамп «закрывать боль»"),
    (r"\bподводя итоги\b", "Школьный штамп «подводя итоги»"),
    (r"\bв заключение хочется отметить\b", "Школьный штамп заключения"),
]

# Стоковые метафоры
STOCK_METAPHORS = [
    (r"\bрабочая лошадка\b", "Стоковая метафора «рабочая лошадка»"),
    (r"\bшвейцарский нож\b", "Стоковая метафора «швейцарский нож»"),
    (r"\bверхушка айсберга\b", "Стоковая метафора «верхушка айсберга»"),
    (r"\bпалка о двух концах\b", "Стоковая метафора «палка о двух концах»"),
    (r"\bкраеугольный камень\b", "Стоковая метафора «краеугольный камень»"),
    (r"\bсеребряная пуля\b", "Стоковая метафора «серебряная пуля»"),
]

# Конструкция «X, а не Y» (включая мягкие формы)
NOT_X_PATTERNS = [
    (r",\s*а\s+не\s+", "Конструкция «..., а не ...» (защитное оправдание вместо прямого утверждения)"),
]

# Эмодзи
EMOJI_PATTERN = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)


def split_sentences(text: str) -> List[str]:
    """Разбивает текст на предложения."""
    # Удаляем блоки кода
    clean_text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # Удаляем YAML фронтматтер
    clean_text = re.sub(r"^---.*?---\s*", "", clean_text, flags=re.DOTALL)
    # Удаляем markdown-ссылки, оставляя анкоры
    clean_text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean_text)
    
    # Разбивка по знакам препинания
    raw_sentences = re.split(r"(?<=[.!?…])\s+", clean_text)
    sentences = []
    for s in raw_sentences:
        s = s.strip()
        # Игнорируем заголовки и пустые строки
        if s and not s.startswith("#") and len(s) > 3:
            sentences.append(s)
    return sentences


def count_words(s: str) -> int:
    return len(re.findall(r"\b[a-zA-Zа-яА-Я0-9_-]+\b", s))


def analyze_text(text: str) -> Dict[str, Any]:
    findings = []
    
    # 1. Жёсткие маркеры
    for pattern, desc in RIGID_PATTERNS:
        matches = list(re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE))
        if matches:
            findings.append({
                "severity": "CRITICAL",
                "category": "Жёсткий маркер ИИ",
                "desc": f"{desc} (найдено {len(matches)} раз)",
                "snippets": [m.group(0) for m in matches[:3]]
            })
            
    # 2. Клише
    for pattern, desc in CLICHE_PATTERNS:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            findings.append({
                "severity": "HIGH",
                "category": "Оборот-клише",
                "desc": f"{desc} (совпадений: {len(matches)})",
                "snippets": [m.group(0) for m in matches[:3]]
            })

    # 3. Метафоры
    for pattern, desc in STOCK_METAPHORS:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            findings.append({
                "severity": "MEDIUM",
                "category": "Стоковая метафора",
                "desc": f"{desc}",
                "snippets": [m.group(0) for m in matches[:3]]
            })

    # 4. Конструкция «X, а не Y»
    for pattern, desc in NOT_X_PATTERNS:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            findings.append({
                "severity": "MEDIUM",
                "category": "Конструкция «X, а не Y»",
                "desc": f"{desc} (встретилось {len(matches)} раз)",
                "snippets": [text[max(0, m.start()-20):min(len(text), m.end()+20)] for m in matches[:2]]
            })

    # 5. Эмодзи
    emojis = EMOJI_PATTERN.findall(text)
    if emojis:
        findings.append({
            "severity": "MEDIUM",
            "category": "Эмодзи в тексте",
            "desc": f"Найдено {len(emojis)} эмодзи (маркер соцсеточного спама/генерации)",
            "snippets": emojis[:5]
        })

    # 6. Длинное тире (U+2014)
    char_len = len(text)
    em_dashes = text.count("—")
    em_dash_density = (em_dashes / max(1, char_len)) * 1000
    if em_dash_density > 5.0 and em_dashes > 2:
        findings.append({
            "severity": "MEDIUM",
            "category": "Высокая плотность длинных тире",
            "desc": f"Плотность: {em_dash_density:.1f} на 1000 знаков (всего {em_dashes} тире). Норма для FastUp — минимум тире, точка/запятая/двоеточие.",
            "snippets": []
        })

    # 7. Ритмика и вариативность длины предложений (Burstiness)
    sentences = split_sentences(text)
    sentence_lengths = [count_words(s) for s in sentences if count_words(s) > 0]
    
    burstiness_score = 0.0
    mean_len = 0.0
    if len(sentence_lengths) >= 4:
        mean_len = sum(sentence_lengths) / len(sentence_lengths)
        variance = sum((l - mean_len) ** 2 for l in sentence_lengths) / len(sentence_lengths)
        std_dev = math.sqrt(variance)
        # Коэффициент вариации: std_dev / mean. У человека обычно > 0.45. У ИИ часто < 0.35 (монотонная длина).
        burstiness_score = std_dev / max(1.0, mean_len)
        if burstiness_score < 0.32:
            findings.append({
                "severity": "HIGH",
                "category": "Монотонный ритм (низкий Burstiness)",
                "desc": f"Коэффициент вариации длины предложений = {burstiness_score:.2f} (средняя длина: {mean_len:.1f} слов, разброс мал). Текст звучит синтетически ровно.",
                "snippets": []
            })

    # 8. Type-Token Ratio (Лексическое разнообразие)
    words = [w.lower() for w in re.findall(r"\b[a-zA-Zа-яА-Я0-9_-]+\b", text)]
    ttr = (len(set(words)) / max(1, len(words))) if words else 0.0

    # Расчет суммарного риска
    score = 0
    for f in findings:
        if f["severity"] == "CRITICAL":
            score += 50
        elif f["severity"] == "HIGH":
            score += 20
        elif f["severity"] == "MEDIUM":
            score += 10

    risk_level = "LOW (низкий)"
    if score >= 40:
        risk_level = "HIGH (высокий — модератор/детектор с высокой вероятностью забракует)"
    elif score >= 20:
        risk_level = "MEDIUM (средний — требуется точечная правка)"

    return {
        "char_count": char_len,
        "word_count": len(words),
        "sentence_count": len(sentences),
        "mean_sentence_length": round(mean_len, 1),
        "burstiness_coefficient": round(burstiness_score, 2),
        "type_token_ratio": round(ttr, 2),
        "em_dash_count": em_dashes,
        "risk_level": risk_level,
        "risk_score": score,
        "findings": findings
    }


def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        
    parser = argparse.ArgumentParser(description="Анализатор текста на маркеры ИИ.")
    parser.add_argument("file", nargs="?", help="Путь к файлу для проверки")
    parser.add_argument("--text", help="Прямой текст для проверки")
    args = parser.parse_args()

    content = ""
    target_name = "входной текст"
    if args.text:
        content = args.text
    elif args.file:
        if not os.path.exists(args.file):
            print(f"Ошибка: Файл {args.file} не найден.")
            sys.exit(1)
        target_name = args.file
        with open(args.file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    else:
        parser.print_help()
        sys.exit(0)

    res = analyze_text(content)

    print("=" * 60)
    print(f"ОТЧЁТ АНАЛИЗА ИИ-МАРКЕРОВ: {target_name}")
    print("=" * 60)
    print(f"Символов (с пробелами): {res['char_count']}")
    print(f"Слов: {res['word_count']} | Предложений: {res['sentence_count']}")
    print(f"Средняя длина предложения: {res['mean_sentence_length']} слов")
    print(f"Ритмическая вариативность (Burstiness): {res['burstiness_coefficient']} (норма человека > 0.40)")
    print(f"Лексическое разнообразие (TTR): {res['type_token_ratio']}")
    print(f"Длинных тире (—): {res['em_dash_count']}")
    print(f"\nИТОГОВЫЙ РИСК ДЕТЕКЦИИ: {res['risk_level']}")
    print("-" * 60)

    if not res["findings"]:
        print("✅ Маркеров машинного текста не обнаружено. Текст звучит чисто и естественно.")
    else:
        print(f"Обнаружено замечаний: {len(res['findings'])}")
        for i, f in enumerate(res["findings"], 1):
            print(f"\n[{f['severity']}] {i}. {f['category']}")
            print(f"   {f['desc']}")
            if f["snippets"]:
                print(f"   Примеры: {', '.join(map(str, f['snippets']))}")
    print("=" * 60)


if __name__ == "__main__":
    main()
