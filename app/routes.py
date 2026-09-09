from collections import defaultdict
from datetime import date, datetime, timedelta
import json

from flask import (
    redirect,
    render_template,
    request,
    url_for,
)

from app.db import get_db
from app.progression import (
    SKILLS,
    get_level_progress,
)
from app.quests import (
    get_quest_by_id,
    load_quests,
)
from app.xp import calculate_rewards


def get_week_dates(target_date):
    monday = target_date - timedelta(
        days=target_date.weekday()
    )

    return [
        monday + timedelta(days=offset)
        for offset in range(7)
    ]


def register_routes(app):

    @app.route("/")
    def dashboard():
        today_date = date.today()
        today = today_date.isoformat()

        quests = load_quests()

        week_dates = get_week_dates(
            today_date
        )

        week_start = week_dates[0].isoformat()
        week_end = week_dates[-1].isoformat()

        with get_db() as db:

            today_logs = db.execute(
                """
                SELECT *
                FROM quest_logs
                WHERE completed_date = ?
                """,
                (today,),
            ).fetchall()

            week_logs = db.execute(
                """
                SELECT *
                FROM quest_logs
                WHERE completed_date
                BETWEEN ? AND ?
                ORDER BY completed_date
                """,
                (
                    week_start,
                    week_end,
                ),
            ).fetchall()

            all_logs = db.execute(
                """
                SELECT *
                FROM quest_logs
                ORDER BY completed_date
                """
            ).fetchall()

        # =========================
        # TODAY
        # =========================

        today_log_map = {
            row["quest_id"]: row
            for row in today_logs
        }

        for quest in quests:
            log = today_log_map.get(
                quest["id"]
            )

            quest["completed"] = (
                log is not None
            )

            quest["log"] = (
                dict(log)
                if log
                else None
            )

        daily_quests = [
            quest
            for quest in quests
            if quest["category"] != "workout"
        ]

        workout_quests = [
            quest
            for quest in quests
            if quest["category"] == "workout"
        ]

        # =========================
        # GLOBAL XP
        # =========================

        total_xp = sum(
            row["xp_earned"]
            for row in all_logs
        )

        today_xp = sum(
            row["xp_earned"]
            for row in today_logs
        )

        week_xp = sum(
            row["xp_earned"]
            for row in week_logs
        )

        level = get_level_progress(
            total_xp
        )

        # =========================
        # SKILLS
        # =========================

        skill_totals = defaultdict(float)

        for log in all_logs:
            skill_data = json.loads(
                log["skill_xp_json"]
            )

            for skill, amount in skill_data.items():
                skill_totals[skill] += amount

        skills = []

        max_skill_value = max(
            skill_totals.values(),
            default=1,
        )

        for skill_id, config in SKILLS.items():
            value = round(
                skill_totals.get(
                    skill_id,
                    0,
                ),
                1,
            )

            percentage = (
                value / max_skill_value * 100
                if max_skill_value
                else 0
            )

            skills.append(
                {
                    "id": skill_id,
                    "name": config["name"],
                    "short": config["short"],
                    "value": value,
                    "percentage": percentage,
                }
            )

        # =========================
        # WEEK
        # =========================

        week_log_map = {
            (
                row["quest_id"],
                row["completed_date"],
            ): row
            for row in week_logs
        }

        week_rows = []

        for quest in quests:
            days = []

            for day in week_dates:
                day_string = day.isoformat()

                log = week_log_map.get(
                    (
                        quest["id"],
                        day_string,
                    )
                )

                days.append(
                    {
                        "date": day_string,
                        "day": day.strftime("%a"),
                        "completed": log is not None,
                        "log": (
                            dict(log)
                            if log
                            else None
                        ),
                    }
                )

            week_rows.append(
                {
                    "quest": quest,
                    "days": days,
                }
            )

        completed_today = len(
            today_logs
        )

        total_today = len(quests)

        today_percentage = (
            completed_today
            / total_today
            * 100
            if total_today
            else 0
        )

        return render_template(
            "dashboard.html",

            today=today,

            daily_quests=daily_quests,
            workout_quests=workout_quests,

            total_xp=total_xp,
            today_xp=today_xp,
            week_xp=week_xp,

            level=level,

            skills=skills,

            week_dates=week_dates,
            week_rows=week_rows,

            completed_today=completed_today,
            total_today=total_today,
            today_percentage=today_percentage,
        )


    @app.post(
        "/quest/<quest_id>/toggle"
    )
    def toggle_quest(quest_id):
        quest = get_quest_by_id(
            quest_id
        )

        if quest is None:
            return "Quest not found", 404

        completed_date = request.form.get(
            "date",
            date.today().isoformat(),
        )

        measurement_value = request.form.get(
            "measurement_value"
        )

        if measurement_value == "":
            measurement_value = None

        with get_db() as db:
            existing = db.execute(
                """
                SELECT id
                FROM quest_logs
                WHERE quest_id = ?
                AND completed_date = ?
                """,
                (
                    quest_id,
                    completed_date,
                ),
            ).fetchone()

            # Clicking an already completed quest
            # removes that day's completion.
            if existing:
                db.execute(
                    """
                    DELETE FROM quest_logs
                    WHERE id = ?
                    """,
                    (
                        existing["id"],
                    ),
                )

                return redirect(
                    url_for("dashboard")
                )

            # Measurement quests must have a value.
            measurement = quest.get(
                "measurement"
            )

            if measurement:
                if measurement_value is None:
                    return (
                        "Measurement required",
                        400,
                    )

                try:
                    measurement_value = float(
                        measurement_value
                    )
                except ValueError:
                    return (
                        "Invalid measurement",
                        400,
                    )

                minimum = measurement.get(
                    "min"
                )

                if (
                    minimum is not None
                    and measurement_value
                    < float(minimum)
                ):
                    return (
                        "Measurement below minimum",
                        400,
                    )

            rewards = calculate_rewards(
                quest,
                measurement_value,
            )

            db.execute(
                """
                INSERT INTO quest_logs (
                    quest_id,
                    completed_date,
                    created_at,
                    measurement_value,
                    xp_earned,
                    skill_xp_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    quest_id,
                    completed_date,
                    datetime.now().isoformat(),
                    measurement_value,
                    rewards["total"],
                    json.dumps(
                        rewards["skills"]
                    ),
                ),
            )

        return redirect(
            url_for("dashboard")
        )