from pathlib import Path

import yaml


BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = BASE_DIR / "configuration"
QUESTS_PATH = CONFIG_DIR / "quests.yaml"


def load_quests():
    with QUESTS_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = yaml.safe_load(file)

    return data.get(
        "quests",
        [],
    )


def get_active_quests():
    return [
        quest
        for quest in load_quests()
        if quest.get(
            "active",
            True,
        )
    ]


def get_quest_by_id(quest_id):
    for quest in load_quests():
        if quest["id"] == quest_id:
            return quest

    return None