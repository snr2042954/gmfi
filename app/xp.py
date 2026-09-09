def get_effective_units(quest, measurement_value):
    if measurement_value is None:
        return 0

    measurement_value = float(measurement_value)

    scaling = quest.get("xp", {}).get("scaling")

    if not scaling:
        return measurement_value

    max_units = scaling.get("max_units")

    if max_units is not None:
        measurement_value = min(
            measurement_value,
            float(max_units),
        )

    return measurement_value


def calculate_rewards(
    quest,
    measurement_value=None,
):
    xp_config = quest["xp"]

    total_xp = float(
        xp_config.get("base", 0)
    )

    effective_units = get_effective_units(
        quest,
        measurement_value,
    )

    scaling = xp_config.get("scaling")

    if scaling:
        total_xp += (
            effective_units
            * float(scaling.get("per_unit", 0))
        )

    skill_rewards = {}

    for skill, config in xp_config.get(
        "skills",
        {},
    ).items():

        if isinstance(config, (int, float)):
            skill_rewards[skill] = float(config)
            continue

        skill_xp = float(
            config.get("base", 0)
        )

        skill_xp += (
            effective_units
            * float(config.get("per_unit", 0))
        )

        skill_rewards[skill] = round(
            skill_xp,
            2,
        )

    return {
        "total": int(round(total_xp)),
        "skills": skill_rewards,
    }