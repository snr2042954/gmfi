from pathlib import Path

import yaml


BASE_DIR = Path(__file__).resolve().parent.parent
PROGRESSION_PATH = BASE_DIR / "progression.yaml"


def load_progression():
    with PROGRESSION_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return yaml.safe_load(file)


def get_title_for_level(titles, level):
    current_title = None

    for title in titles:
        if level >= title["min_level"]:
            current_title = title["title"]

    return current_title


def get_character_progress(total_xp):
    progression = load_progression()

    config = progression["character"]["level_curve"]

    base_xp = config["base_xp"]
    growth = config["growth_per_level"]

    level = 1
    remaining_xp = total_xp

    while True:
        required = (
            base_xp
            + ((level - 1) * growth)
        )

        if remaining_xp < required:
            break

        remaining_xp -= required
        level += 1

    title = get_title_for_level(
        progression["character"]["titles"],
        level,
    )

    return {
        "level": level,
        "title": title,
        "current_xp": remaining_xp,
        "required_xp": required,
        "percentage": (
            remaining_xp / required * 100
            if required
            else 0
        ),
    }


def get_skill_progress(skill_id, total_xp):
    progression = load_progression()

    skill_config = progression[
        "skills"
    ]["definitions"][skill_id]

    xp_per_level = progression[
        "skills"
    ]["level_curve"]["xp_per_level"]

    level = int(
        total_xp // xp_per_level
    ) + 1

    xp_in_level = (
        total_xp % xp_per_level
    )

    title = get_title_for_level(
        skill_config["titles"],
        level,
    )

    return {
        "id": skill_id,
        "name": skill_config["name"],
        "short": skill_config["short"],
        "level": level,
        "title": title,
        "total_xp": round(total_xp, 1),
        "current_xp": round(xp_in_level, 1),
        "required_xp": xp_per_level,
        "percentage": (
            xp_in_level / xp_per_level * 100
        ),
    }


def get_rank(skill_progress):
    progression = load_progression()

    total_skill_levels = sum(
        skill["level"]
        for skill in skill_progress
    )

    current_rank = None

    for rank in progression["ranks"]:
        if (
            total_skill_levels
            >= rank["min_total_skill_levels"]
        ):
            current_rank = rank["name"]

    return {
        "name": current_rank,
        "total_skill_levels": total_skill_levels,
    }


def get_skill_ids():
    progression = load_progression()

    return list(
        progression[
            "skills"
        ]["definitions"].keys()
    )