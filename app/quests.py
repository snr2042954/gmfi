from pathlib import Path

import os
import re
import tempfile
import time

import yaml

from app.db import get_db
from app.timeutils import now_local


BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = BASE_DIR / "configuration"

QUESTS_PATH = CONFIG_DIR / "quests.yaml"

USER_QUESTS_PATH = (
    CONFIG_DIR / "user-quests.yaml"
)

USER_QUESTS_LOCK = (
    CONFIG_DIR / ".user-quests.lock"
)


# =========================
# LOADING
# =========================

def load_yaml_quests(path):
    if not path.exists():
        return []

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        data = yaml.safe_load(file) or {}

    return data.get(
        "quests",
        [],
    )


def load_builtin_quests():
    return load_yaml_quests(
        QUESTS_PATH
    )


def load_user_quests():
    return load_yaml_quests(
        USER_QUESTS_PATH
    )


def load_quests():
    return (
        load_builtin_quests()
        + load_user_quests()
    )


def get_quest_by_id(quest_id):
    for quest in load_quests():

        if quest["id"] == quest_id:
            return quest

    return None


# =========================
# ACTIVE STATE
# =========================

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

    # YAML active is only the default
    # for a user who has no override.
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


# =========================
# USER QUEST CREATION
# =========================

def make_quest_id(name):
    quest_id = name.strip().lower()

    quest_id = re.sub(
        r"[^a-z0-9]+",
        "_",
        quest_id,
    )

    quest_id = quest_id.strip("_")

    if not quest_id:
        raise ValueError(
            "Could not generate a valid task ID."
        )

    return quest_id


def acquire_user_quest_lock(
    timeout_seconds=5,
):
    start = time.monotonic()

    while True:

        try:
            USER_QUESTS_LOCK.mkdir()

            return

        except FileExistsError:

            if (
                time.monotonic() - start
                >= timeout_seconds
            ):
                raise TimeoutError(
                    "Task catalog is currently busy."
                )

            time.sleep(0.05)


def release_user_quest_lock():
    try:
        USER_QUESTS_LOCK.rmdir()

    except FileNotFoundError:
        pass


def write_user_quests(quests):
    CONFIG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    data = {
        "quests": quests,
    }

    temp_path = None

    try:

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=CONFIG_DIR,
            prefix="user-quests-",
            suffix=".tmp",
            delete=False,
        ) as temp_file:

            yaml.safe_dump(
                data,
                temp_file,
                sort_keys=False,
                allow_unicode=True,
            )

            temp_path = Path(
                temp_file.name
            )

        os.replace(
            temp_path,
            USER_QUESTS_PATH,
        )

    finally:

        if (
            temp_path is not None
            and temp_path.exists()
        ):
            temp_path.unlink()


def create_user_quest(quest):
    acquire_user_quest_lock()

    try:

        existing = load_quests()

        existing_ids = {
            item["id"]
            for item in existing
        }

        if quest["id"] in existing_ids:
            raise ValueError(
                "A task with this ID already exists."
            )

        user_quests = (
            load_user_quests()
        )

        user_quests.append(
            quest
        )

        write_user_quests(
            user_quests
        )

    finally:
        release_user_quest_lock()