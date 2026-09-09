from pathlib import Path

import yaml


BASE_DIR = Path(__file__).resolve().parent.parent
QUESTS_PATH = BASE_DIR / "quests.yaml"


def load_quests():
    with QUESTS_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = yaml.safe_load(file)

    return data.get("quests", [])


def get_quest_by_id(quest_id):
    quests = load_quests()

    for quest in quests:
        if quest["id"] == quest_id:
            return quest

    return None