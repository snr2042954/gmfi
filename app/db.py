from pathlib import Path
import sqlite3


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "gmfi.db"


def get_db():
    connection = sqlite3.connect(DB_PATH)

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def init_db():
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS quest_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                quest_id TEXT NOT NULL,

                completed_date TEXT NOT NULL,
                created_at TEXT NOT NULL,

                measurement_value REAL,

                xp_earned INTEGER NOT NULL,

                skill_xp_json TEXT NOT NULL DEFAULT '{}',

                UNIQUE(
                    quest_id,
                    completed_date
                )
            );


            CREATE TABLE IF NOT EXISTS trophies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                achievement_id TEXT NOT NULL,

                iso_year INTEGER NOT NULL,
                iso_week INTEGER NOT NULL,

                earned_at TEXT NOT NULL,

                UNIQUE(
                    achievement_id,
                    iso_year,
                    iso_week
                )
            );


            CREATE INDEX IF NOT EXISTS
            idx_quest_logs_completed_date
            ON quest_logs(completed_date);


            CREATE INDEX IF NOT EXISTS
            idx_quest_logs_quest_id
            ON quest_logs(quest_id);


            CREATE INDEX IF NOT EXISTS
            idx_trophies_week
            ON trophies(
                iso_year,
                iso_week
            );
            """
        )