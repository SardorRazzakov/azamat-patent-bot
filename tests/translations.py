"""Полнота переводов. Запуск: python tests/translations.py

Клиентские тексты живут в texts.py тремя параллельными словарями. Забытый
язык у ключа не ломает бота: t() молча подставит DEFAULT_LANG, и человек,
выбравший русский, получит узбекскую латиницу. Опечатка в имени ключа
хуже — KeyError прилетает клиенту посреди диалога.

Ни то, ни другое не всплывает до продакшена, потому что проверяется здесь.
"""

import ast
import sys
from pathlib import Path
from string import Formatter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import texts  # noqa: E402

# Модули, из которых берутся тексты для клиента.
CALLERS = (
    Path("handlers") / "client.py",
    Path("handlers") / "admin.py",
    Path("reminders.py"),
)


def placeholders(text: str) -> set[str]:
    """Имена подстановок: 'Дата: {title}' -> {'title'}."""
    return {name for _, name, _, _ in Formatter().parse(text) if name}


# ---------- ПРОВЕРКИ ----------

def all_languages_present() -> list[str]:
    """У каждого ключа должны быть все три языка.

    Пропуск не падает: t() отдаёт DEFAULT_LANG, и клиент просто получает
    текст не на своём языке.
    """
    bad = []
    for key, translations in texts.TEXTS.items():
        missing = [lang for lang in texts.LANGUAGES if lang not in translations]
        if missing:
            bad.append(f"{key}: нет перевода на {', '.join(missing)}")

        extra = [lang for lang in translations if lang not in texts.LANGUAGES]
        if extra:
            bad.append(f"{key}: неизвестный язык {', '.join(extra)}")

    for lang in texts.LANGUAGES:
        if lang not in texts.LANGUAGE_NAMES:
            bad.append(f"LANGUAGE_NAMES: нет подписи для {lang}")
    return bad


def no_empty_texts() -> list[str]:
    """Пустая строка проходит все прочие проверки, а клиент видит пустоту."""
    return [
        f"{key}/{lang}: пустой текст"
        for key, translations in texts.TEXTS.items()
        for lang, value in translations.items()
        if not (value or "").strip()
    ]


def placeholders_match() -> list[str]:
    """Подстановки должны совпадать во всех языках одного ключа.

    Лишняя в переводе — KeyError при форматировании, потерянная — текст
    без даты или без ссылки на оплату.
    """
    bad = []
    for key, translations in texts.TEXTS.items():
        by_lang = {lang: placeholders(value) for lang, value in translations.items()}
        reference = by_lang.get(texts.DEFAULT_LANG, set())
        for lang, found in by_lang.items():
            if lang == texts.DEFAULT_LANG:
                continue
            lost = reference - found
            extra = found - reference
            if lost:
                bad.append(f"{key}/{lang}: потеряна подстановка {sorted(lost)}")
            if extra:
                bad.append(f"{key}/{lang}: лишняя подстановка {sorted(extra)}")
    return bad


def faq_structure_complete() -> list[str]:
    """FAQ_SECTIONS задаёт структуру, а тексты к ней собираются по шаблону.

    Раздел без подписи или вопрос без ответа обрушат экран у клиента —
    в t() такого ключа просто нет.
    """
    bad = []
    for section, questions in texts.FAQ_SECTIONS:
        if f"faq_sec_{section}" not in texts.TEXTS:
            bad.append(f"раздел {section}: нет ключа faq_sec_{section}")
        for qid in questions:
            for kind in ("q", "a"):
                key = f"faq_{kind}_{qid}"
                if key not in texts.TEXTS:
                    bad.append(f"вопрос {qid}: нет ключа {key}")

    if texts.FAQ_MANAGER not in texts.FAQ_PARENT:
        bad.append(
            f"FAQ_MANAGER = {texts.FAQ_MANAGER}: такого вопроса нет в FAQ_SECTIONS, "
            "уведомление админам не сработает"
        )
    return bad


def used_keys_exist() -> list[str]:
    """Каждый texts.t('...') в коде должен ссылаться на существующий ключ.

    Опечатка тут — KeyError у клиента посреди диалога. Ключи, собранные
    через f-строку, проверяются по неизменяемому началу: оно должно
    совпасть хотя бы с одним существующим ключом.
    """
    bad = []
    for relative in CALLERS:
        path = ROOT / relative
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "t"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "texts"):
                continue
            if not node.args:
                continue

            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                if first.value not in texts.TEXTS:
                    bad.append(
                        f"{relative}:{node.lineno}: нет ключа {first.value}"
                    )
            elif isinstance(first, ast.JoinedStr):
                head = ""
                for part in first.values:
                    if isinstance(part, ast.Constant) and isinstance(part.value, str):
                        head += part.value
                    else:
                        break
                if head and not any(k.startswith(head) for k in texts.TEXTS):
                    bad.append(
                        f"{relative}:{node.lineno}: под шаблон {head}* "
                        "не подходит ни один ключ"
                    )
    return bad


CHECKS = (
    ("все языки на месте", all_languages_present),
    ("нет пустых текстов", no_empty_texts),
    ("подстановки совпадают", placeholders_match),
    ("структура FAQ полна", faq_structure_complete),
    ("ключи из кода существуют", used_keys_exist),
)


def main() -> int:
    failed = 0
    for title, check in CHECKS:
        problems = check()
        if problems:
            failed += 1
            print(f"FAIL  {title}")
            for line in problems:
                print(f"        {line}")
        else:
            print(f"ok    {title}")

    print()
    print(f"ключей: {len(texts.TEXTS)}, языков: {len(texts.LANGUAGES)}, "
          f"вопросов FAQ: {len(texts.FAQ_PARENT)}")
    print("переводы полны" if not failed else f"провалено проверок: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
