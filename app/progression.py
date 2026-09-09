SKILLS = {
    "strength": {
        "name": "Strength",
        "short": "STR",
    },
    "endurance": {
        "name": "Endurance",
        "short": "END",
    },
    "vitality": {
        "name": "Vitality",
        "short": "VIT",
    },
    "intelligence": {
        "name": "Intelligence",
        "short": "INT",
    },
    "creativity": {
        "name": "Creativity",
        "short": "CRE",
    },
    "discipline": {
        "name": "Discipline",
        "short": "DISC",
    },
}


def xp_required_for_next_level(level):
    return 100 + ((level - 1) * 50)


def get_level_progress(total_xp):
    level = 1
    remaining_xp = total_xp

    while True:
        required = xp_required_for_next_level(level)

        if remaining_xp < required:
            break

        remaining_xp -= required
        level += 1

    required = xp_required_for_next_level(level)

    percentage = (
        remaining_xp / required * 100
        if required
        else 0
    )

    return {
        "level": level,
        "current_xp": remaining_xp,
        "required_xp": required,
        "percentage": percentage,
    }