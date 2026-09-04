"""Smoke-проверки записи в базу. Запуск: python tests/smoke.py

Без pytest: в requirements.txt его нет, а проверок мало и они самодостаточны.
Каждая гоняет настоящий db.py поверх временного файла базы, поэтому ловит
ровно то, что сломается в бою, — блокировки и транзакции, а не моки.

Главная проверка здесь — confirmation_survives_full_date_race. Она стоит на
регрессии, из-за которой подтверждение оплаты молча пропадало: все запросы
идут через один коннект, и create_booking, упёршийся в кончившиеся места,
уносил в свой ROLLBACK чужой UPDATE, успевший влезть на await.
"""

import asyncio
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# DB_PATH читается на импорте config, поэтому подменяем до импорта db.
_TMP = tempfile.mkdtemp(prefix="patentbot-smoke-")
os.environ["DB_PATH"] = os.path.join(_TMP, "smoke.db")
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_IDS", "1")

import db  # noqa: E402


# ---------- ХЕЛПЕРЫ ----------

_counter = 0


async def make_date(seats_limit: int) -> int:
    """Своя дата на каждый прогон: названия уникальны (title UNIQUE)."""
    global _counter
    _counter += 1
    date_id = await db.add_date(f"проверка-{_counter}", seats_limit)
    assert date_id is not None, "дату не удалось создать"
    return date_id


async def book(user_id: int, date_id: int) -> int | None:
    return await db.create_booking(
        user_id, f"Клиент {user_id}", "", date_id, "passport", "receipt"
    )


# ---------- ПРОВЕРКИ ----------

async def confirmation_survives_full_date_race():
    """Подтверждение оплаты не должно пропадать из-за чужого ROLLBACK.

    Расклад: на дате единственное место, оно занято заявкой victim. Админ
    подтверждает victim ровно в тот момент, когда второй клиент дошёл до
    чека и получает отказ по лимиту.

    До починки claim_booking выполнялся внутри открытого create_booking
    BEGIN IMMEDIATE и своим commit() закрывал чужую транзакцию, после чего
    create_booking падал на «cannot rollback - no transaction is active»:
    оплативший последнее место клиент получал сбой вместо отказа по местам.

    Гоняем несколько раундов: порядок переключения корутин не фиксирован,
    и одного прохода мало, чтобы поймать окно.
    """
    for round_no in range(25):
        date_id = await make_date(seats_limit=1)

        victim = await book(1001, date_id)
        assert victim is not None, "первое место должно заниматься"

        loser, claim = await asyncio.gather(
            book(1002, date_id),                       # упрётся в лимит -> ROLLBACK
            db.claim_booking(victim, 777, "Админ"),    # влезает на await внутри
        )

        assert loser is None, (
            f"раунд {round_no}: место кончилось, а заявка всё равно создалась"
        )

        won, client_id, winner = claim
        assert won, f"раунд {round_no}: claim_booking не сработал"
        assert client_id == 1001

        row = await db.get_booking(victim)
        assert row[5] == db.CONFIRMED, (
            f"раунд {round_no}: подтверждение оплаты потерялось — "
            f"в базе статус {row[5]!r} вместо {db.CONFIRMED!r}"
        )


async def seats_limit_holds_under_concurrency():
    """Лимит мест не пробивается, когда клиенты присылают чеки одновременно."""
    date_id = await make_date(seats_limit=3)

    results = await asyncio.gather(*(book(2000 + i, date_id) for i in range(12)))
    created = [r for r in results if r is not None]

    assert len(created) == 3, f"мест 3, а заявок создалось {len(created)}"

    _, _, _, _, confirmed, pending, _ = await db.get_date_overview(date_id)
    assert confirmed + pending == 3, f"в базе занято {confirmed + pending} мест из 3"


async def writes_survive_alongside_rollback():
    """Любая запись, а не только claim_booking, переживает соседний ROLLBACK.

    Тот же коннект: досрочный commit() чужой транзакции ломал бы и отметки
    вроде mark_reminded, поэтому проверяем и их.
    """
    date_id = await make_date(seats_limit=1)
    victim = await book(3001, date_id)

    _, _, cancelled = await asyncio.gather(
        book(3002, date_id),                       # ROLLBACK по лимиту
        db.set_user_lang(3001, "ru"),              # соседняя запись
        db.cancel_booking(victim, 777, "Админ"),   # ещё одна, многошаговая
    )

    changed, user_id = cancelled
    assert changed, "отмена не применилась"
    assert user_id == 3001
    assert await db.get_user_lang(3001) == "ru", "язык клиента не сохранился"

    row = await db.get_booking(victim)
    assert row[5] == db.CANCELLED, f"статус {row[5]!r} вместо {db.CANCELLED!r}"


CHECKS = (
    confirmation_survives_full_date_race,
    seats_limit_holds_under_concurrency,
    writes_survive_alongside_rollback,
)


async def main() -> int:
    await db.db_init()

    failed = 0
    for check in CHECKS:
        name = check.__name__
        try:
            await check()
        except Exception:
            failed += 1
            print(f"FAIL  {name}")
            traceback.print_exc()
        else:
            print(f"ok    {name}")

    await db.close()

    print()
    if failed:
        print(f"провалено проверок: {failed} из {len(CHECKS)}")
    else:
        print(f"все проверки прошли ({len(CHECKS)})")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        code = asyncio.run(main())
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
    sys.exit(code)
