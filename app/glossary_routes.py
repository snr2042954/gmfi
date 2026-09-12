from collections import defaultdict
import json

from flask import (
    redirect,
    render_template,
    url_for,
)

from app.db import get_db
from app.progression import load_progression
from app.quests import (
    get_quest_by_id,
    get_quest_states,
    load_quests,
    quest_is_active,
    set_quest_active,
)
from app.timeutils import today_local


CATEGORY_ORDER = {
    "daily": 0,
    "nutrition": 1,
    "workout": 2,
}


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

            stats[quest_id][
                "completions"
            ] += 1

            stats[quest_id][
                "total_xp"
            ] += log["xp_earned"]


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

                stats[quest_id][
                    "skills"
                ][skill_id] += float(
                    amount
                )


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

                item["quest"]["name"].lower(),
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
        )


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