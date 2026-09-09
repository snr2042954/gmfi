import os

from datetime import datetime
from zoneinfo import ZoneInfo


TIMEZONE_NAME = (
    os.getenv("TZ")
    or os.getenv("TIMEZONE")
    or "Europe/Amsterdam"
)

APP_TIMEZONE = ZoneInfo(TIMEZONE_NAME)


def now_local():
    return datetime.now(APP_TIMEZONE)


def today_local():
    return now_local().date()