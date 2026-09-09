from datetime import date, timedelta
from pathlib import Path

import yaml

from app.db import get_db
from app.quests import load_quests
from app.timeutils import now_local


BASE_DIR = Path(__file__).resolve().parent.parent

ACHIEVEMENTS_PATH = (
    BASE_DIR / "achievements.yaml"
)


def load_achievements():
    with ACHIEVEMENTS_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = yaml.safe_load(file)

    return data.get(
        "achievements",
        [],
    )


def get_achievement_by_id(
    achievement_id,
):
    for achievement in load_achievements():
        if (
            achievement["id"]
            == achievement_id
        ):
            return achievement

    return None


def get_week_dates(
    iso_year,
    iso_week,
):
    monday = date.fromisocalendar(
        iso_year,
        iso_week,
        1,
    )

    return [
        monday + timedelta(days=offset)
        for offset in range(7)
    ]


def perfect_week_completed(
    iso_year,
    iso_week,
):
    week_dates = get_week_dates(
        iso_year,
        iso_week,
    )

    quests = load_quests()

    daily_quests = [
        quest
        for quest in quests
        if quest["category"] != "workout"
    ]

    workout_ids = {
        quest["id"]
        for quest in quests
        if quest["category"] == "workout"
    }

    daily_ids = {
        quest["id"]
        for quest in daily_quests
    }

    week_start = (
        week_dates[0].isoformat()
    )

    week_end = (
        week_dates[-1].isoformat()
    )

    with get_db() as db:
        logs = db.execute(
            """
            SELECT
                quest_id,
                completed_date
            FROM quest_logs
            WHERE completed_date
            BETWEEN ? AND ?
            """,
            (
                week_start,
                week_end,
            ),
        ).fetchall()

    logs_by_date = {}

    for log in logs:
        logs_by_date.setdefault(
            log["completed_date"],
            set(),
        ).add(
            log["quest_id"]
        )

    for day in week_dates:
        completed = logs_by_date.get(
            day.isoformat(),
            set(),
        )

        completed_daily = (
            completed & daily_ids
        )

        if completed_daily != daily_ids:
            return False

        completed_workouts = (
            completed & workout_ids
        )

        if len(completed_workouts) < 1:
            return False

    return True


def evaluate_weekly_achievements(
    iso_year,
    iso_week,
):
    earned = []

    achievements = load_achievements()

    for achievement in achievements:

        achievement_id = (
            achievement["id"]
        )

        qualifies = False

        if (
            achievement_id
            == "perfect_week"
        ):
            qualifies = (
                perfect_week_completed(
                    iso_year,
                    iso_week,
                )
            )

        if not qualifies:
            continue

        with get_db() as db:
            existing = db.execute(
                """
                SELECT id
                FROM trophies
                WHERE achievement_id = ?
                AND iso_year = ?
                AND iso_week = ?
                """,
                (
                    achievement_id,
                    iso_year,
                    iso_week,
                ),
            ).fetchone()

            if existing:
                continue

            db.execute(
                """
                INSERT INTO trophies (
                    achievement_id,
                    iso_year,
                    iso_week,
                    earned_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    achievement_id,
                    iso_year,
                    iso_week,
                    now_local().isoformat(),
                ),
            )

            earned.append(
                achievement_id
            )

    return earned