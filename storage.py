"""Хранилище FSM в той же SQLite, что и остальные данные.

MemoryStorage держит состояние в памяти процесса, поэтому каждый деплой
Railway ронял клиентов посреди записи: приславший паспорт человек после
перезапуска оказывался в пустоте. Здесь состояние переживает рестарт.

Реплика одна, объёмы маленькие — отдельное соединение на операцию
дешевле, чем возня с блокировками общего.
"""

import json

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey

from db import session


def _key(key: StorageKey) -> str:
    return f"{key.bot_id}:{key.chat_id}:{key.user_id}"


# Строка без состояния и с пустыми данными не нужна — чтобы таблица
# не росла от каждого /start.
_CLEANUP = """
    DELETE FROM fsm_storage
    WHERE key = ? AND state IS NULL AND (data IS NULL OR data = '{}')
"""


class SQLiteStorage(BaseStorage):
    def __init__(self):
        pass

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        value = state.state if isinstance(state, State) else state
        async with session() as conn:
            if value is None:
                await conn.execute(
                    "UPDATE fsm_storage SET state = NULL WHERE key = ?", (_key(key),)
                )
                await conn.execute(_CLEANUP, (_key(key),))
            else:
                await conn.execute(
                    """INSERT INTO fsm_storage (key, state, data) VALUES (?, ?, '{}')
                       ON CONFLICT(key) DO UPDATE SET state = excluded.state""",
                    (_key(key), value),
                )
            await conn.commit()

    async def get_state(self, key: StorageKey) -> str | None:
        async with session() as conn:
            cur = await conn.execute(
                "SELECT state FROM fsm_storage WHERE key = ?", (_key(key),)
            )
            row = await cur.fetchone()
            return row[0] if row else None

    async def set_data(self, key: StorageKey, data) -> None:
        payload = json.dumps(dict(data), ensure_ascii=False)
        async with session() as conn:
            await conn.execute(
                """INSERT INTO fsm_storage (key, state, data) VALUES (?, NULL, ?)
                   ON CONFLICT(key) DO UPDATE SET data = excluded.data""",
                (_key(key), payload),
            )
            await conn.execute(_CLEANUP, (_key(key),))
            await conn.commit()

    async def get_data(self, key: StorageKey) -> dict:
        async with session() as conn:
            cur = await conn.execute(
                "SELECT data FROM fsm_storage WHERE key = ?", (_key(key),)
            )
            row = await cur.fetchone()
        if not row or not row[0]:
            return {}
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            # битую запись лечим сбросом, а не падением посреди диалога
            return {}

    async def close(self) -> None:
        pass
