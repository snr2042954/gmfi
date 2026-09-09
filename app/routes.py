from collections import defaultdict
from datetime import date, datetime, timedelta
import json

from flask import (
    redirect,
    render_template,
    request,
    url_for,
)

from app.achievements import (
    evaluate_weekly_achievements,
    load_achievements,
)
from app.db import get_db
from app.progression import (
    get_character_progress,
    get_rank,
    get_skill_ids,
    get_skill_progress,
)
from app.quests import (
    get_quest_by_id,
    load_quests,
)
from app.timeutils import (
    now_local,
    today_local,
)
from app.xp import calculate_rewards


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


def get_weeks_in_year(year):
    return date(
        year,
        12,
        28,
    ).isocalendar().week


def get_today_context():
    today = today_local().isoformat()
    quests = load_quests()

    with get_db() as db:
        today_logs = db.execute(
            """
            SELECT *
            FROM quest_logs
            WHERE completed_date = ?
            """,
            (today,),
        ).fetchall()

    log_map = {
        row["quest_id"]: row
        for row in today_logs
    }

    for quest in quests:
        log = log_map.get(
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

    return (
        today,
        quests,
        today_logs,
    )


def register_routes(app):

    @app.route("/")
    def today_page():
        (
            today,
            quests,
            today_logs,
        ) = get_today_context()

        daily_quests = [
            quest
            for quest in quests
            if quest["category"] != "workout"
        ]

        today_xp = sum(
            row["xp_earned"]
            for row in today_logs
        )

        return render_template(
            "today.html",
            today=today,
            active_page="today",
            daily_quests=daily_quests,
            today_xp=today_xp,
            completed_today=len(
                today_logs
            ),
            total_today=len(
                quests
            ),
        )


    @app.route("/workouts")
    def workouts_page():
        (
            today,
            quests,
            _,
        ) = get_today_context()

        workout_quests = [
            quest
            for quest in quests
            if quest["category"] == "workout"
        ]

        return render_template(
            "workouts.html",
            today=today,
            active_page="workouts",
            workout_quests=workout_quests,
        )


    @app.route("/character")
    def character_page():
        today = (
            today_local().isoformat()
        )

        with get_db() as db:
            all_logs = db.execute(
                """
                SELECT *
                FROM quest_logs
                ORDER BY completed_date
                """
            ).fetchall()

        total_xp = sum(
            row["xp_earned"]
            for row in all_logs
        )

        character = (
            get_character_progress(
                total_xp
            )
        )

        skill_totals = defaultdict(
            float
        )

        for log in all_logs:
            skill_data = json.loads(
                log["skill_xp_json"]
            )

            for (
                skill_id,
                amount,
            ) in skill_data.items():

                skill_totals[
                    skill_id
                ] += amount

        skills = [
            get_skill_progress(
                skill_id,
                skill_totals.get(
                    skill_id,
                    0,
                ),
            )
            for skill_id
            in get_skill_ids()
        ]

        rank = get_rank(
            skills
        )

        return render_template(
            "character.html",
            today=today,
            active_page="character",
            total_xp=total_xp,
            character=character,
            skills=skills,
            rank=rank,
        )


    @app.route("/week")
    def week_page():
        current_date = today_local()
        current_iso = (
            current_date.isocalendar()
        )

        try:
            selected_year = int(
                request.args.get(
                    "year",
                    current_iso.year,
                )
            )

            max_weeks = get_weeks_in_year(
                selected_year
            )

            selected_week = int(
                request.args.get(
                    "week",
                    current_iso.week,
                )
            )

            if not (
                1
                <= selected_week
                <= max_weeks
            ):
                return "Invalid week", 400

            week_dates = get_week_dates(
                selected_year,
                selected_week,
            )

        except (
            ValueError,
            TypeError,
        ):
            return "Invalid week", 400

        today = (
            current_date.isoformat()
        )

        week_start = (
            week_dates[0].isoformat()
        )

        week_end = (
            week_dates[-1].isoformat()
        )

        quests = load_quests()

        with get_db() as db:
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
                day_string = (
                    day.isoformat()
                )

                log = week_log_map.get(
                    (
                        quest["id"],
                        day_string,
                    )
                )

                days.append(
                    {
                        "date": day_string,
                        "completed": (
                            log is not None
                        ),
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

        week_xp = sum(
            row["xp_earned"]
            for row in week_logs
        )

        if week_end < today:
            evaluate_weekly_achievements(
                selected_year,
                selected_week,
            )

        available_years = range(
            current_iso.year - 5,
            current_iso.year + 2,
        )

        return render_template(
            "week.html",

            today=today,
            active_page="week",

            selected_year=selected_year,
            selected_week=selected_week,

            available_years=available_years,

            available_weeks=range(
                1,
                max_weeks + 1,
            ),

            week_dates=week_dates,
            week_rows=week_rows,
            week_xp=week_xp,
        )


    @app.route("/trophies")
    def trophies_page():
        today = (
            today_local().isoformat()
        )

        achievements = (
            load_achievements()
        )

        with get_db() as db:
            earned_rows = db.execute(
                """
                SELECT *
                FROM trophies
                ORDER BY
                    iso_year DESC,
                    iso_week DESC
                """
            ).fetchall()

        earned_by_achievement = {}

        for row in earned_rows:
            achievement_id = (
                row["achievement_id"]
            )

            earned_by_achievement.setdefault(
                achievement_id,
                [],
            )

            week_start = (
                date.fromisocalendar(
                    row["iso_year"],
                    row["iso_week"],
                    1,
                )
            )

            week_end = (
                date.fromisocalendar(
                    row["iso_year"],
                    row["iso_week"],
                    7,
                )
            )

            earned_by_achievement[
                achievement_id
            ].append(
                {
                    "year": (
                        row["iso_year"]
                    ),
                    "week": (
                        row["iso_week"]
                    ),
                    "start": (
                        week_start
                    ),
                    "end": (
                        week_end
                    ),
                    "earned_at": (
                        row["earned_at"]
                    ),
                }
            )

        trophies = []

        for achievement in achievements:
            weeks = (
                earned_by_achievement.get(
                    achievement["id"],
                    [],
                )
            )

            trophies.append(
                {
                    "id": (
                        achievement["id"]
                    ),
                    "name": (
                        achievement["name"]
                    ),
                    "description": (
                        achievement[
                            "description"
                        ]
                    ),
                    "icon": (
                        achievement.get(
                            "icon",
                            "★",
                        )
                    ),
                    "requirements": (
                        achievement.get(
                            "requirement_text",
                            [],
                        )
                    ),
                    "unlocked": (
                        len(weeks) > 0
                    ),
                    "count": (
                        len(weeks)
                    ),
                    "weeks": weeks,
                }
            )

        return render_template(
            "trophies.html",
            today=today,
            active_page="trophies",
            trophies=trophies,
        )


    @app.post(
        "/quest/<quest_id>/toggle"
    )
    def toggle_quest(quest_id):
        quest = get_quest_by_id(
            quest_id
        )

        if quest is None:
            return (
                "Quest not found",
                404,
            )

        completed_date = (
            request.form.get(
                "date",
                today_local().isoformat(),
            )
        )

        try:
            selected_date = (
                datetime.strptime(
                    completed_date,
                    "%Y-%m-%d",
                ).date()
            )
        except ValueError:
            return (
                "Invalid date",
                400,
            )

        if (
            selected_date
            > today_local()
        ):
            return (
                "Cannot log quests in the future",
                400,
            )

        measurement_value = (
            request.form.get(
                "measurement_value"
            )
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

            else:
                measurement = (
                    quest.get(
                        "measurement"
                    )
                )

                if measurement:
                    if (
                        measurement_value
                        is None
                    ):
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

                    minimum = (
                        measurement.get(
                            "min"
                        )
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

                rewards = (
                    calculate_rewards(
                        quest,
                        measurement_value,
                    )
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
                        now_local().isoformat(),
                        measurement_value,
                        rewards["total"],
                        json.dumps(
                            rewards[
                                "skills"
                            ]
                        ),
                    ),
                )

        # If you edited a completed historical
        # week, immediately check its trophies.
        iso = selected_date.isocalendar()

        week_sunday = (
            date.fromisocalendar(
                iso.year,
                iso.week,
                7,
            )
        )

        if week_sunday < today_local():
            evaluate_weekly_achievements(
                iso.year,
                iso.week,
            )

        return redirect(
            request.referrer
            or url_for(
                "today_page"
            )
        )