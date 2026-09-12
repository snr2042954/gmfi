from pathlib import Path

import yaml

from app.db import get_db
from app.timeutils import now_local


BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = BASE_DIR / "configuration"

QUESTS_PATH = CONFIG_DIR / "quests.yaml"


def load_quests():
    with QUESTS_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:

        data = yaml.safe_load(file) or {}

    return data.get(
        "quests",
        [],
    )


def get_quest_by_id(quest_id):
    for quest in load_quests():

        if quest["id"] == quest_id:
            return quest

    return None


def get_quest_states():
    with get_db() as db:

        rows = db.execute(
            """
            SELECT
                quest_id,
                active
            FROM quest_states
            """
        ).fetchall()

    return {
        row["quest_id"]: bool(
            row["active"]
        )
        for row in rows
    }


def quest_is_active(
    quest,
    states=None,
):
    if states is None:
        states = get_quest_states()

    quest_id = quest["id"]

    if quest_id in states:
        return states[quest_id]

    # YAML now defines the DEFAULT state.
    return bool(
        quest.get(
            "active",
            False,
        )
    )


def get_active_quests():
    quests = load_quests()

    states = get_quest_states()

    return [
        quest
        for quest in quests
        if quest_is_active(
            quest,
            states,
        )
    ]


def set_quest_active(
    quest_id,
    active,
):
    quest = get_quest_by_id(
        quest_id
    )

    if quest is None:
        raise ValueError(
            f"Unknown quest: {quest_id}"
        )

    with get_db() as db:

        db.execute(
            """
            INSERT INTO quest_states (
                quest_id,
                active,
                updated_at
            )
            VALUES (?, ?, ?)

            ON CONFLICT(quest_id)
            DO UPDATE SET
                active = excluded.active,
                updated_at = excluded.updated_at
            """,
            (
                quest_id,
                int(bool(active)),
                now_local().isoformat(),
            ),
        )