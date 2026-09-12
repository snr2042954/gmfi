from collections import defaultdict
import json
import os

from flask import (
    redirect,
    render_template,
    request,
    url_for,
)

from app.db import get_db
from app.progression import load_progression
from app.quests import (
    create_user_quest,
    get_quest_by_id,
    get_quest_states,
    load_quests,
    make_quest_id,
    quest_is_active,
    set_quest_active,
)
from app.timeutils import today_local


CATEGORY_ORDER = {
    "daily": 0,
    "nutrition": 1,
    "workout": 2,
}

ALLOWED_CATEGORIES = {
    "daily",
    "nutrition",
    "workout",
}


def parse_float(
    value,
    field_name,
    required=False,
    minimum=None,
):
    value = (
        value.strip()
        if value
        else ""
    )

    if not value:

        if required:
            raise ValueError(
                f"{field_name} is required."
            )

        return None

    try:
        number = float(value)

    except ValueError:
        raise ValueError(
            f"{field_name} must be a number."
        )

    if (
        minimum is not None
        and number < minimum
    ):
        raise ValueError(
            f"{field_name} must be at least {minimum}."
        )

    return number


def clean_number(number):
    if number is None:
        return None

    if float(number).is_integer():
        return int(number)

    return number


def register_glossary_routes(app):

    @app.route("/glossary")
    def glossary_page():

        quests = load_quests()

        states = get_quest_states()

        progression = (
            load_progression()
        )

        skill_definitions = (
            progression["skills"][
                "definitions"
            ]
        )

        stats = defaultdict(
            lambda: {
                "completions": 0,
                "total_xp": 0,
                "skills": defaultdict(float),
            }
        )

        with get_db() as db:

            logs = db.execute(
                """
                SELECT
                    quest_id,
                    xp_earned,
                    skill_xp_json
                FROM quest_logs
                """
            ).fetchall()

        for log in logs:

            quest_id = log["quest_id"]

            stats[
                quest_id
            ]["completions"] += 1

            stats[
                quest_id
            ]["total_xp"] += (
                log["xp_earned"]
            )

            try:
                skill_data = json.loads(
                    log["skill_xp_json"]
                    or "{}"
                )

            except json.JSONDecodeError:
                skill_data = {}

            for (
                skill_id,
                amount,
            ) in skill_data.items():

                stats[
                    quest_id
                ]["skills"][
                    skill_id
                ] += float(amount)

        glossary = []

        for quest in quests:

            quest_id = quest["id"]

            quest_stats = stats[
                quest_id
            ]

            skill_contributions = []

            for (
                skill_id,
                amount,
            ) in quest_stats[
                "skills"
            ].items():

                definition = (
                    skill_definitions.get(
                        skill_id
                    )
                )

                if definition:
                    name = definition["name"]
                    short = definition["short"]

                else:
                    name = skill_id.title()
                    short = skill_id.upper()

                skill_contributions.append(
                    {
                        "id": skill_id,
                        "name": name,
                        "short": short,
                        "xp": round(
                            amount,
                            1,
                        ),
                    }
                )

            skill_contributions.sort(
                key=lambda item: (
                    -item["xp"],
                    item["name"],
                )
            )

            glossary.append(
                {
                    "quest": quest,

                    "active": (
                        quest_is_active(
                            quest,
                            states,
                        )
                    ),

                    "completions": (
                        quest_stats[
                            "completions"
                        ]
                    ),

                    "total_xp": (
                        quest_stats[
                            "total_xp"
                        ]
                    ),

                    "skills": (
                        skill_contributions
                    ),
                }
            )

        glossary.sort(
            key=lambda item: (
                not item["active"],

                CATEGORY_ORDER.get(
                    item["quest"].get(
                        "category"
                    ),
                    99,
                ),

                item["quest"][
                    "name"
                ].lower(),
            )
        )

        return render_template(
            "glossary.html",

            today=(
                today_local()
                .isoformat()
            ),

            active_page="glossary",

            glossary=glossary,

            skill_definitions=(
                skill_definitions
            ),

            create_error=(
                request.args.get(
                    "create_error"
                )
            ),
        )


    # =========================
    # ACTIVATE / DEACTIVATE
    # =========================

    @app.post(
        "/glossary/<quest_id>/toggle"
    )
    def toggle_glossary_quest(
        quest_id,
    ):

        quest = get_quest_by_id(
            quest_id
        )

        if quest is None:
            return (
                "Quest not found",
                404,
            )

        current_state = (
            quest_is_active(
                quest
            )
        )

        set_quest_active(
            quest_id,
            not current_state,
        )

        return redirect(
            url_for(
                "glossary_page"
            )
        )


    # =========================
    # CREATE TASK
    # =========================

    @app.post(
        "/glossary/create"
    )
    def create_glossary_quest():

        try:

            name = (
                request.form.get(
                    "name",
                    "",
                ).strip()
            )

            description = (
                request.form.get(
                    "description",
                    "",
                ).strip()
            )

            category = (
                request.form.get(
                    "category",
                    "",
                ).strip()
            )

            if not name:
                raise ValueError(
                    "Task name is required."
                )

            if not description:
                raise ValueError(
                    "Description is required."
                )

            if (
                category
                not in ALLOWED_CATEGORIES
            ):
                raise ValueError(
                    "Invalid category."
                )

            quest_id = make_quest_id(
                name
            )

            if get_quest_by_id(
                quest_id
            ):
                raise ValueError(
                    "A task with that name already exists."
                )

            base_xp = parse_float(
                request.form.get(
                    "base_xp"
                ),
                "Base XP",
                required=True,
                minimum=0,
            )

            measurable = (
                request.form.get(
                    "measurable"
                )
                == "yes"
            )

            quest = {
                "id": quest_id,
                "name": name,
                "category": category,
                "description": description,

                # Other users see it,
                # but it starts inactive.
                "active": False,

                "created_by": (
                    os.getenv(
                        "GMFI_USER",
                        "unknown",
                    )
                ),

                "xp": {
                    "base": clean_number(
                        base_xp
                    ),
                },
            }

            if measurable:

                measurement_label = (
                    request.form.get(
                        "measurement_label",
                        "",
                    ).strip()
                )

                measurement_unit = (
                    request.form.get(
                        "measurement_unit",
                        "",
                    ).strip()
                )

                if not measurement_label:
                    raise ValueError(
                        "Measurement label is required."
                    )

                if not measurement_unit:
                    raise ValueError(
                        "Measurement unit is required."
                    )

                measurement_min = (
                    parse_float(
                        request.form.get(
                            "measurement_min"
                        ),
                        "Measurement minimum",
                        required=True,
                        minimum=0,
                    )
                )

                measurement_step = (
                    parse_float(
                        request.form.get(
                            "measurement_step"
                        ),
                        "Measurement step",
                        required=True,
                        minimum=0.000001,
                    )
                )

                quest["measurement"] = {
                    "type": (
                        request.form.get(
                            "measurement_type",
                            "value",
                        ).strip()
                        or "value"
                    ),

                    "label": (
                        measurement_label
                    ),

                    "unit": (
                        measurement_unit
                    ),

                    "min": clean_number(
                        measurement_min
                    ),

                    "step": clean_number(
                        measurement_step
                    ),
                }

                scaling_enabled = (
                    request.form.get(
                        "scaling_enabled"
                    )
                    == "yes"
                )

                if scaling_enabled:

                    per_unit = parse_float(
                        request.form.get(
                            "xp_per_unit"
                        ),
                        "XP per unit",
                        required=True,
                        minimum=0,
                    )

                    max_units = parse_float(
                        request.form.get(
                            "max_units"
                        ),
                        "Maximum rewarded units",
                        required=True,
                        minimum=0,
                    )

                    quest["xp"][
                        "scaling"
                    ] = {
                        "per_unit": (
                            clean_number(
                                per_unit
                            )
                        ),

                        "max_units": (
                            clean_number(
                                max_units
                            )
                        ),
                    }

            progression = (
                load_progression()
            )

            skill_definitions = (
                progression[
                    "skills"
                ]["definitions"]
            )

            skill_rewards = {}

            for skill_id in (
                skill_definitions.keys()
            ):

                base = parse_float(
                    request.form.get(
                        f"skill_{skill_id}_base"
                    ),
                    f"{skill_id} base XP",
                    minimum=0,
                )

                per_unit = parse_float(
                    request.form.get(
                        f"skill_{skill_id}_per_unit"
                    ),
                    f"{skill_id} XP per unit",
                    minimum=0,
                )

                if (
                    base is None
                    and per_unit is None
                ):
                    continue

                config = {}

                if base is not None:
                    config["base"] = (
                        clean_number(base)
                    )

                if (
                    measurable
                    and per_unit is not None
                ):
                    config[
                        "per_unit"
                    ] = clean_number(
                        per_unit
                    )

                skill_rewards[
                    skill_id
                ] = config

            if skill_rewards:

                quest["xp"][
                    "skills"
                ] = skill_rewards

            create_user_quest(
                quest
            )

            # Creator gets it immediately.
            set_quest_active(
                quest_id,
                True,
            )

        except (
            ValueError,
            TimeoutError,
        ) as error:

            return redirect(
                url_for(
                    "glossary_page",
                    create_error=str(
                        error
                    ),
                )
            )

        return redirect(
            url_for(
                "glossary_page"
            )
        )