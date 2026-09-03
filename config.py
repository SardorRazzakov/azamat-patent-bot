import os
from datetime import timedelta, timezone

# В базе время хранится в UTC, а админам показывается в этом поясе.
TZ = timezone(timedelta(hours=5))  # Ташкент, UTC+5

TOKEN = os.environ.get("BOT_TOKEN")
DB_PATH = os.environ.get("DB_PATH", "bot.db")


def parse_admin_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for part in (raw or "").replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            ids.append(int(part))
    return ids


ADMIN_IDS = parse_admin_ids(
    os.environ.get("ADMIN_IDS") or os.environ.get("ADMIN_ID", "")
)

# Посев дат при поднятии базы с нуля: (название, мест). 0 — без лимита.
# На уже работающей базе не применяется — там даты заводятся через админку.
# Формат названия нейтральный: его видят клиенты на всех трёх языках.
DEFAULT_DATES = [
    ("07.09.2026", 5),
    ("09.09.2026", 25),
    ("11.09.2026", 25),
    ("14.09.2026", 5),
    ("16.09.2026", 25),
    ("18.09.2026", 25),
    ("21.09.2026", 25),
    ("25.09.2026", 25),
    ("28.09.2026", 25),
    ("29.09.2026", 25),
]

PAYME_LINK = "https://payme.uz/fallback/merchant/?id=6a4673b9ccf9c1de0aa04520"
CLICK_LINK = "https://indoor.click.uz/pay?id=0105991&t=0"

EXAM_LOCATION_LAT = 41.29872833124857
EXAM_LOCATION_LON = 69.34990462234283

GREETING_VOICE = "greeting.ogg"


def validate():
    if not TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN")
    if not ADMIN_IDS:
        raise RuntimeError("Не задан ADMIN_IDS (пример: 123456789,987654321)")
