from datetime import date, datetime
from pathlib import Path
import sqlite3

from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "gmfi.db"


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                xp INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                completed_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (activity_id) REFERENCES activities(id),
                UNIQUE(activity_id, completed_date)
            );
            """
        )

        activity_count = db.execute(
            "SELECT COUNT(*) AS count FROM activities"
        ).fetchone()["count"]

        if activity_count == 0:
            activities = [
                ("Vitamins", "daily", 5),
                ("4 eggs", "daily", 5),
                ("Kwark", "daily", 5),
                ("Read 10 pages", "daily", 15),
                ("Hobby 1 hour", "daily", 20),
                ("Gym - Push", "workout", 30),
                ("Gym - Pull", "workout", 30),
                ("Gym - Legs", "workout", 35),
                ("Jogging", "workout", 30),
                ("Cycling", "workout", 30),
            ]

            db.executemany(
                """
                INSERT INTO activities (name, category, xp)
                VALUES (?, ?, ?)
                """,
                activities,
            )


@app.route("/")
def dashboard():
    today = date.today().isoformat()

    with get_db() as db:
        activities = db.execute(
            """
            SELECT
                activities.*,
                CASE
                    WHEN activity_logs.id IS NOT NULL THEN 1
                    ELSE 0
                END AS completed
            FROM activities
            LEFT JOIN activity_logs
                ON activity_logs.activity_id = activities.id
                AND activity_logs.completed_date = ?
            WHERE activities.active = 1
            ORDER BY activities.category, activities.id
            """,
            (today,),
        ).fetchall()

        total_xp = db.execute(
            """
            SELECT COALESCE(SUM(activities.xp), 0) AS total_xp
            FROM activity_logs
            JOIN activities
                ON activities.id = activity_logs.activity_id
            """
        ).fetchone()["total_xp"]

        today_xp = db.execute(
            """
            SELECT COALESCE(SUM(activities.xp), 0) AS today_xp
            FROM activity_logs
            JOIN activities
                ON activities.id = activity_logs.activity_id
            WHERE activity_logs.completed_date = ?
            """,
            (today,),
        ).fetchone()["today_xp"]

    daily_activities = [
        activity for activity in activities if activity["category"] == "daily"
    ]

    workout_activities = [
        activity for activity in activities if activity["category"] == "workout"
    ]

    level = (total_xp // 100) + 1
    xp_in_level = total_xp % 100

    return render_template(
        "dashboard.html",
        daily_activities=daily_activities,
        workout_activities=workout_activities,
        total_xp=total_xp,
        today_xp=today_xp,
        level=level,
        xp_in_level=xp_in_level,
        today=today,
    )


@app.post("/activity/<int:activity_id>/toggle")
def toggle_activity(activity_id):
    completed_date = request.form.get(
        "date",
        date.today().isoformat(),
    )

    with get_db() as db:
        existing = db.execute(
            """
            SELECT id
            FROM activity_logs
            WHERE activity_id = ?
            AND completed_date = ?
            """,
            (activity_id, completed_date),
        ).fetchone()

        if existing:
            db.execute(
                """
                DELETE FROM activity_logs
                WHERE id = ?
                """,
                (existing["id"],),
            )
        else:
            db.execute(
                """
                INSERT INTO activity_logs (
                    activity_id,
                    completed_date,
                    created_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    activity_id,
                    completed_date,
                    datetime.now().isoformat(),
                ),
            )

    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(
        host="0.0.0.0",
        port=8014,
        debug=True,
    )