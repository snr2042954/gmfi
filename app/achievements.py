from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import yaml

from app.db import get_db
from app.quests import load_quests
from app.timeutils import now_local


BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = BASE_DIR / "configuration"

ACHIEVEMENTS_PATH = (
    CONFIG_DIR / "achievements.yaml"
)


def load_achievements():
    with ACHIEVEMENTS_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = yaml.safe_load(file) or {}

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


def get_week_logs(
    iso_year,
    iso_week,
):
    week_dates = get_week_dates(
        iso_year,
        iso_week,
    )

    week_start = (
        week_dates[0].isoformat()
    )

    week_end = (
        week_dates[-1].isoformat()
    )

    with get_db() as db:
        logs = db.execute(
            """
            SELECT *
            FROM quest_logs
            WHERE completed_date
            BETWEEN ? AND ?
            """,
            (
                week_start,
                week_end,
            ),
        ).fetchall()

    return (
        week_dates,
        logs,
    )


def build_logs_by_date(logs):
    result = {}

    for log in logs:
        completed_date = (
            log["completed_date"]
        )

        result.setdefault(
            completed_date,
            set(),
        )

        result[
            completed_date
        ].add(
            log["quest_id"]
        )

    return result


def build_quest_groups():
    quests = load_quests()

    category_ids = defaultdict(set)

    workout_type_ids = defaultdict(set)

    for quest in quests:

        quest_id = quest["id"]

        category = quest.get(
            "category"
        )

        if category:
            category_ids[
                category
            ].add(
                quest_id
            )

        if category == "workout":

            workout_type = quest.get(
                "workout_type"
            )

            if workout_type:
                workout_type_ids[
                    workout_type
                ].add(
                    quest_id
                )

    return (
        category_ids,
        workout_type_ids,
    )


def count_days_with_any(
    week_dates,
    logs_by_date,
    quest_ids,
):
    completed_days = 0

    for day in week_dates:

        completed = logs_by_date.get(
            day.isoformat(),
            set(),
        )

        if completed & quest_ids:
            completed_days += 1

    return completed_days


def achievement_completed(
    achievement,
    iso_year,
    iso_week,
):
    week_dates, logs = get_week_logs(
        iso_year,
        iso_week,
    )

    logs_by_date = build_logs_by_date(
        logs
    )

    requirements = achievement.get(
        "requirements",
        {},
    )

    (
        category_ids,
        workout_type_ids,
    ) = build_quest_groups()

    workout_ids = category_ids.get(
        "workout",
        set(),
    )

    # =========================
    # REQUIRED QUESTS EVERY DAY
    # =========================

    required_every_day = (
        requirements.get(
            "required_quests_every_day"
        )
    )

    if required_every_day:
        required_ids = set(
            required_every_day
        )

        for day in week_dates:

            completed = logs_by_date.get(
                day.isoformat(),
                set(),
            )

            if not required_ids.issubset(
                completed
            ):
                return False

    # =========================
    # MINIMUM WORKOUT DAYS
    # Legacy condition.
    # Equivalent to category:
    # workout.
    # =========================

    minimum_workout_days = (
        requirements.get(
            "minimum_workout_days"
        )
    )

    if minimum_workout_days is not None:

        workout_days = count_days_with_any(
            week_dates,
            logs_by_date,
            workout_ids,
        )

        if (
            workout_days
            < minimum_workout_days
        ):
            return False

    # =========================
    # MINIMUM CATEGORY DAYS
    #
    # Example:
    #
    # minimum_category_days:
    #   daily: 7
    #   nutrition: 7
    #   workout: 4
    # =========================

    minimum_category_days = (
        requirements.get(
            "minimum_category_days",
            {},
        )
    )

    for (
        category,
        required_days,
    ) in minimum_category_days.items():

        quest_ids = category_ids.get(
            category,
            set(),
        )

        completed_days = (
            count_days_with_any(
                week_dates,
                logs_by_date,
                quest_ids,
            )
        )

        if completed_days < required_days:
            return False

    # =========================
    # MINIMUM WORKOUT TYPE DAYS
    #
    # Example:
    #
    # minimum_workout_type_days:
    #   strength: 3
    #   cardio: 2
    # =========================

    minimum_workout_type_days = (
        requirements.get(
            "minimum_workout_type_days",
            {},
        )
    )

    for (
        workout_type,
        required_days,
    ) in minimum_workout_type_days.items():

        quest_ids = workout_type_ids.get(
            workout_type,
            set(),
        )

        completed_days = (
            count_days_with_any(
                week_dates,
                logs_by_date,
                quest_ids,
            )
        )

        if completed_days < required_days:
            return False

    # =========================
    # MINIMUM DAYS PER QUEST
    # =========================

    minimum_days_per_quest = (
        requirements.get(
            "minimum_days_per_quest",
            {},
        )
    )

    for (
        quest_id,
        required_days,
    ) in minimum_days_per_quest.items():

        completed_days = sum(
            1
            for day in week_dates
            if quest_id
            in logs_by_date.get(
                day.isoformat(),
                set(),
            )
        )

        if completed_days < required_days:
            return False

    # =========================
    # ANY QUEST FROM SET
    # =========================

    any_quest_requirement = (
        requirements.get(
            "minimum_days_with_any_quest"
        )
    )

    if any_quest_requirement:

        quest_ids = set(
            any_quest_requirement.get(
                "quest_ids",
                [],
            )
        )

        required_days = (
            any_quest_requirement.get(
                "days",
                0,
            )
        )

        completed_days = (
            count_days_with_any(
                week_dates,
                logs_by_date,
                quest_ids,
            )
        )

        if completed_days < required_days:
            return False

    return True


def evaluate_weekly_achievements(
    iso_year,
    iso_week,
):
    earned = []

    for achievement in load_achievements():

        if not achievement_completed(
            achievement,
            iso_year,
            iso_week,
        ):
            continue

        achievement_id = (
            achievement["id"]
        )

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