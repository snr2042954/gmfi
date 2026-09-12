# gmfi

gmfi is a self-hosted life-gamification dashboard for tracking habits, nutrition, workouts, reading, personal routines, progression, and weekly achievements.

The application is intentionally small and configuration-driven:

- Flask serves the web application.
- SQLite stores personal history and progression data.
- YAML defines quests, XP rewards, progression, skills, ranks, and achievements.
- Jinja templates render the interface.
- Docker provides the production deployment.
- Tailscale provides private access to the home server.
- Multiple users run separate gmfi containers with separate databases.
- The quest catalog can be shared between users while activity history remains private per user.

The main design principle is:

**configuration should remain separate from application logic whenever practical.**

Adding quests, changing XP values, adjusting progression, or defining trophies should generally happen through YAML rather than by rewriting Python.

---

# Core concepts

gmfi revolves around five main concepts:

1. Quests
2. Quest logs
3. Progression
4. Achievements / trophies
5. Per-user quest state

A quest is something that can be completed at most once per day.

Examples include:

- take vitamins
- read pages
- go for a walk
- eat fruit
- go jogging
- go cycling
- complete a strength workout
- spend time on a hobby
- complete a user-created task

Some quests are simple yes/no completions.

Other quests are measurable.

Examples of measurements include:

- kilometers
- pages
- sets
- minutes
- hours
- repetitions

Completing a quest creates a permanent row in SQLite.

That row contains the global XP and skill XP actually earned at the time of completion.

Changing a quest's future reward therefore does **not** rewrite historical progression.

---

# Architecture

gmfi separates three different types of information.

## Shared game configuration

Stored primarily in:

```text
configuration/
```

Examples:

- built-in quests
- user-created shared quests
- progression rules
- skill definitions
- trophy definitions

## Per-user state

Stored in each user's SQLite database.

Examples:

- completed quests
- measurements
- earned XP
- skill XP
- active/inactive quest choices
- earned trophies

## Application logic

Stored in Python.

Examples:

- quest loading
- XP calculations
- progression calculations
- achievement evaluation
- database access
- routes

This separation allows multiple users to use the same game definition without sharing their personal history.

---

# Project structure

The current project is approximately:

```text
gmfi/
├── app/
│   ├── __init__.py
│   ├── achievements.py
│   ├── db.py
│   ├── glossary_routes.py
│   ├── progression.py
│   ├── quests.py
│   ├── routes.py
│   ├── timeutils.py
│   └── xp.py
│
├── configuration/
│   ├── README.md
│   ├── achievements.yaml
│   ├── progression.yaml
│   ├── quests.yaml
│   └── user-quests.yaml
│
├── data/
│   └── gmfi.db
│
├── static/
│   ├── gmfi-logo.png
│   ├── gmfi-touch-icon.png
│   └── style.css
│
├── templates/
│   ├── partials/
│   │   └── quest_card.html
│   ├── base.html
│   ├── character.html
│   ├── glossary.html
│   ├── today.html
│   ├── trophies.html
│   └── week.html
│
├── .dockerignore
├── .env
├── .gitignore
├── Dockerfile
├── docker-compose.dev.yml
├── docker-compose.yml
├── main.py
├── README.md
└── requirements.txt
```

On the production server, each user has a separate host data directory.

For example:

```text
data_bram/
data_wouter/
```

Inside each container, the application still sees:

```text
/app/data/gmfi.db
```

---

# Application entry point

## `main.py`

`main.py` is the application entry point.

It intentionally remains small.

```python
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8050,
        debug=True,
    )
```

There are two ways this file is used.

## Local development

Running:

```powershell
python main.py
```

starts Flask's development server on:

```text
http://localhost:8050
```

## Production

Gunicorn imports:

```text
main:app
```

That means:

1. import `main.py`
2. find the variable called `app`
3. serve that Flask application

The following block:

```python
if __name__ == "__main__":
```

is therefore ignored by Gunicorn.

The Flask development server and Gunicorn are two separate execution paths.

---

# Application factory

## `app/__init__.py`

The application factory creates the Flask application and registers its components.

The current structure is approximately:

```python
from flask import Flask

from app.db import init_db
from app.glossary_routes import register_glossary_routes
from app.routes import register_routes


def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )

    init_db()

    register_routes(app)
    register_glossary_routes(app)

    return app
```

Keeping application construction here prevents `main.py` from becoming the central location for application logic.

---

# Database

## `app/db.py`

SQLite is used for persistent personal data.

The application database path is:

```text
data/gmfi.db
```

In Docker this becomes:

```text
/app/data/gmfi.db
```

because `/app/data` is bind-mounted from the host.

The database should never be baked into the Docker image.

---

# Database tables

## `quest_logs`

Each row represents one quest completion.

Important columns:

```text
id
quest_id
completed_date
created_at
measurement_value
xp_earned
skill_xp_json
```

Example:

```text
quest_id: jogging
completed_date: 2026-09-10
measurement_value: 5.2
xp_earned: 36
```

Skill rewards are stored as JSON.

Example:

```json
{
    "endurance": 5.64,
    "vitality": 2.04,
    "discipline": 1
}
```

There is a uniqueness constraint on:

```text
quest_id + completed_date
```

Therefore, a quest can only be completed once per day.

---

## `quest_states`

Quest activation is personal.

The table is conceptually:

```sql
CREATE TABLE IF NOT EXISTS quest_states (
    quest_id TEXT PRIMARY KEY,
    active INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (active IN (0, 1))
);
```

This table allows two users to share the same quest catalog while having different active tasks.

For example:

```text
Bram:
Swimming = active

Wouter:
Swimming = inactive
```

Both still see the same shared quest definition.

---

## `trophies`

Earned weekly achievements are stored in:

```text
trophies
```

Important columns:

```text
id
achievement_id
iso_year
iso_week
earned_at
```

The combination:

```text
achievement_id
iso_year
iso_week
```

is unique.

A trophy can therefore only be awarded once for a particular ISO week.

---

# Why XP is stored in the database

Quest rewards can change.

For example, jogging may initially award:

```yaml
xp:
  base: 10

  scaling:
    per_unit: 5
```

and later become:

```yaml
xp:
  base: 10

  scaling:
    per_unit: 4
```

Historical sessions should not suddenly lose XP.

Therefore gmfi stores:

```text
xp_earned
skill_xp_json
```

inside every completed quest log.

Progression is based on those stored rewards.

Historical XP is not recalculated from the current quest YAML.

---

# Configuration

The primary game configuration lives in:

```text
configuration/
```

Current files:

```text
configuration/
├── achievements.yaml
├── progression.yaml
├── quests.yaml
├── user-quests.yaml
└── README.md
```

These files do not all have the same ownership model.

---

# Built-in quests

## `configuration/quests.yaml`

This contains administrator-maintained quests.

It is committed to Git.

Example:

```yaml
quests:

  - id: reading
    name: Reading
    category: daily
    description: Read a book
    active: true

    measurement:
      type: pages
      label: Pages
      unit: pages
      min: 1
      step: 1

    xp:
      base: 5

      scaling:
        per_unit: 1
        max_units: 50

      skills:
        intelligence:
          base: 1
          per_unit: 0.2

        discipline:
          base: 1
```

---

# User-created quests

## `configuration/user-quests.yaml`

Tasks created through the Task Glossary are stored separately in:

```text
configuration/user-quests.yaml
```

This file is shared between gmfi containers.

It is intentionally **not committed to Git**.

The resulting model is:

```text
quests.yaml
    administrator-maintained catalog

user-quests.yaml
    shared runtime-created catalog
```

Both files are loaded together by `app/quests.py`.

---

# Shared custom quests

When a user creates a task through the UI:

1. the form is validated
2. a stable quest ID is generated from its name
3. duplicate IDs are rejected
4. the quest is written to `user-quests.yaml`
5. its YAML default is stored as inactive
6. the creator receives an active override in their own database

For example, Bram creates:

```text
Swimming
```

The shared quest definition might become:

```yaml
- id: swimming
  name: Swimming
  category: workout
  workout_type: cardio
  description: Complete a swimming session
  active: false
  created_by: bram

  measurement:
    type: distance
    label: Distance
    unit: km
    min: 0.1
    step: 0.1

  xp:
    base: 10
```

The shared definition says:

```yaml
active: false
```

but Bram's personal database receives:

```text
swimming = active
```

Therefore:

```text
Bram   -> sees Swimming active
Wouter -> sees Swimming inactive
```

Wouter can activate it independently.

---

# Quest IDs

Every quest has a permanent machine identifier.

Example:

```yaml
id: jogging
```

The ID is used in:

- SQLite quest logs
- quest state overrides
- trophy rules
- historical linkage

Do not casually rename existing quest IDs.

Changing:

```yaml
id: jogging
```

to:

```yaml
id: running
```

does not migrate historical rows.

Human-readable names may safely change.

For example:

```yaml
id: jogging
name: Running
```

preserves linkage.

---

# Quest categories

Every quest belongs to one of the current top-level categories:

```text
daily
nutrition
workout
```

Example:

```yaml
category: daily
```

or:

```yaml
category: workout
```

Categories determine:

- Today page grouping
- Week page grouping
- generic trophy evaluation
- general task semantics

Custom tasks use the same categories as built-in tasks.

This means trophies can target categories without depending on exact quest IDs.

---

# Workout types

Workout quests may additionally define:

```yaml
workout_type:
```

Current supported values are:

```text
strength
cardio
```

Example strength quest:

```yaml
- id: gym_push
  name: Push
  category: workout
  workout_type: strength
```

Example cardio quest:

```yaml
- id: jogging
  name: Jogging
  category: workout
  workout_type: cardio
```

The important distinction is:

```text
category = broad UI/game category
workout_type = workout subtype
```

Both strength and cardio tasks remain:

```yaml
category: workout
```

Therefore they continue to appear together under the Workout section of Today and Week.

The subtype is primarily useful for:

- trophy evaluation
- glossary information
- future workout-specific behavior

A user-created workout must choose either:

```text
Strength
Cardio
```

when it is created.

An older workout without `workout_type` still counts as a generic workout, but it does not count toward strength-specific or cardio-specific trophies.

---

# Quest activation

The meaning of:

```yaml
active:
```

is important.

It is **not** the user's current live state.

Instead:

```yaml
active: true
```

means:

> active by default for a user who has never made a personal choice for this quest

and:

```yaml
active: false
```

means:

> inactive by default for a user who has never made a personal choice for this quest

The real resolution logic is:

```text
if quest exists in quest_states:
    use the user's database override
else:
    use quest.active from YAML
```

Conceptually:

```python
if quest_id in states:
    return states[quest_id]

return bool(
    quest.get(
        "active",
        False,
    )
)
```

This makes the YAML catalog suitable for multiple users.

---

# Deactivating quests

A user can activate or deactivate quests from the Task Glossary.

Deactivation:

- removes the quest from normal active tracking
- does not delete the quest definition
- does not delete historical logs
- does not remove XP
- does not remove skill XP
- does not remove trophies
- can be reversed later

Historical data remains valid.

---

# Removing shared custom quests

Shared custom quests are intentionally not deletable by ordinary users.

If a task should be removed from the shared catalog, the user asks the administrator.

The administrator can manually edit:

```text
configuration/user-quests.yaml
```

This prevents one user from deleting a shared task that another user may still use.

Deletion is therefore an administrative action.

---

# Promoting user-created quests

A useful custom quest can be promoted into the built-in catalog.

The administrator can:

1. find the quest in `user-quests.yaml`
2. copy it to `quests.yaml`
3. preserve its existing `id`
4. remove the duplicate from `user-quests.yaml`

Preserving the ID is important.

For example:

```yaml
id: swimming
```

should remain:

```yaml
id: swimming
```

after promotion.

This preserves:

- quest logs
- active-state overrides
- historical XP
- trophy relationships

---

# Measurements

A task becomes measurable when it contains:

```yaml
measurement:
```

Example:

```yaml
measurement:
  type: distance
  label: Distance
  unit: km
  min: 0.1
  step: 0.1
```

The UI primarily relies on:

```text
label
unit
min
step
```

The `type` field provides semantic information but is not heavily interpreted by application logic.

---

# Reading as a measurable task

Reading is a normal Daily-category task even though it has a measurement.

Example:

```yaml
- id: reading
  name: Reading
  category: daily
  description: Read a book

  measurement:
    type: pages
    label: Pages
    unit: pages
    min: 1
    step: 1
```

This demonstrates an important rule:

**measurement behavior is independent from category.**

A task does not need to be a workout in order to be measurable.

---

# Quest UI behavior

On Today, normal quests have a compact completion button.

For a simple quest:

```text
Take vitamins              +
```

clicking `+` immediately completes it.

For a measurable quest:

```text
Reading                    +
```

clicking `+` expands the card:

```text
Reading

Pages
[ 24 ]

[ Complete ]
```

Once completed, the quest displays its completed state and can be undone.

---

# XP configuration

Global XP is configured under:

```yaml
xp:
```

The simplest form is:

```yaml
xp:
  base: 10
```

A measurable quest can scale with its measurement:

```yaml
xp:
  base: 10

  scaling:
    per_unit: 5
    max_units: 15
```

For a 5 km run:

```text
10 base XP
+
5 × 5 XP
=
35 XP
```

For a 30 km run:

```text
10 base XP
+
15 × 5 XP
=
85 XP
```

Only the first 15 units receive scaling XP because:

```yaml
max_units: 15
```

This prevents extreme measurements from disproportionately affecting progression.

---

# Skill XP

Skill XP is independent from global XP.

Example:

```yaml
skills:

  endurance:
    base: 2
    per_unit: 0.7

  vitality:
    base: 1
    per_unit: 0.2

  discipline:
    base: 1
```

Skill XP earned at completion is stored in:

```text
quest_logs.skill_xp_json
```

It is therefore historical and does not change if the YAML reward is later adjusted.

---

# Skills

Current skills are:

```text
strength
endurance
vitality
intelligence
creativity
discipline
```

Each skill has progression data such as:

- name
- abbreviation
- XP
- level
- title
- XP toward next level

Example:

```text
STR Lv. 5
Ironbound
62 / 100 XP
```

---

# Character progression

## `configuration/progression.yaml`

Progression configuration controls:

- global character levels
- character titles
- skill definitions
- skill level progression
- skill titles
- overall rank thresholds

Example:

```yaml
character:

  level_curve:
    base_xp: 100
    growth_per_level: 50
```

The progression engine lives in:

```text
app/progression.py
```

Character levels themselves are not stored separately in SQLite.

They are calculated dynamically from historical XP.

---

# Character rank

Overall rank is based on combined skill levels.

Example:

```text
STR 6
END 4
VIT 7
INT 3
CRE 2
DISC 8
```

Combined:

```text
30
```

The highest configured rank whose threshold is at or below that total becomes active.

---

# Achievement system

## `configuration/achievements.yaml`

Weekly trophies are administrator-controlled.

Users may create tasks, but they cannot create or modify trophy definitions through the UI.

The achievement system is intentionally based primarily on stable task semantics rather than a fixed quest list.

Trophies can depend on:

- quest category
- workout type
- selected core quest IDs

This allows the quest catalog to evolve without making the Trophy Room obsolete.

---

# Trophy philosophy

Most trophies should not depend on exact combinations such as:

```text
vitamins + eggs + kwark
```

because individual routines are fluid.

Instead, generic trophies can target concepts such as:

```text
Daily activity
Nutrition consistency
Workout frequency
Strength training
Cardio training
```

A small number of permanent core tasks may still have dedicated trophies.

Examples include:

```text
Reading
Jogging
Walking
```

The Bookworm trophy is an example of an intentionally quest-specific achievement.

---

# Achievement format

Example:

```yaml
- id: bookworm
  name: Bookworm
  description: Read every day for an entire week.
  icon: "▤"

  requirement_text:
    - Complete Reading on all 7 days.

  requirements:
    minimum_days_per_quest:
      reading: 7
```

There are two distinct sections.

## `requirement_text`

Human-readable information shown in the Trophy Room.

Example:

```yaml
requirement_text:
  - Complete Reading on all 7 days.
```

This text does not perform the evaluation.

## `requirements`

Machine-readable rules evaluated by:

```text
app/achievements.py
```

---

# Supported achievement requirements

The evaluator supports both older quest-specific rules and newer semantic rules.

---

## Required quests every day

```yaml
requirements:

  required_quests_every_day:
    - reading
```

Every listed quest must be completed on every day of the ISO week.

This rule remains supported for backwards compatibility.

---

## Minimum days per quest

```yaml
requirements:

  minimum_days_per_quest:
    reading: 7
```

The specified quest must appear on at least the given number of distinct days.

This is appropriate for permanent/core tasks.

---

## Minimum workout days

```yaml
requirements:

  minimum_workout_days: 5
```

At least one `workout` category quest must be completed on five distinct days.

This is retained as a legacy convenience rule.

Equivalent newer logic can be represented as:

```yaml
requirements:

  minimum_category_days:
    workout: 5
```

---

## Minimum category days

```yaml
requirements:

  minimum_category_days:
    daily: 7
    nutrition: 7
    workout: 4
```

For each listed category, at least one task from that category must be completed on the required number of distinct days.

For example:

```yaml
daily: 7
```

means:

> complete at least one Daily-category quest on every day of the week

It does **not** mean that every active Daily quest has to be completed.

This is intentionally independent of the specific quest catalog.

---

## Minimum workout type days

```yaml
requirements:

  minimum_workout_type_days:
    strength: 3
    cardio: 2
```

This counts distinct days on which at least one matching workout subtype was completed.

A task counts toward:

```text
strength
```

when its definition contains:

```yaml
category: workout
workout_type: strength
```

A task counts toward:

```text
cardio
```

when it contains:

```yaml
category: workout
workout_type: cardio
```

This works for both built-in and user-created tasks.

---

## Minimum days with any quest from a set

```yaml
requirements:

  minimum_days_with_any_quest:
    quest_ids:
      - jogging
      - cycling

    days: 3
```

At least one quest from the specified group must appear on the required number of distinct days.

This remains available for special achievements.

---

# Combining achievement rules

Multiple rule types can be combined.

Example:

```yaml
- id: the_standard
  name: The Standard
  description: An exceptional week across routine, nutrition, learning and physical training.
  icon: "♛"

  requirement_text:
    - Complete Reading on all 7 days.
    - Complete at least one Daily task on all 7 days.
    - Complete at least one Nutrition task on all 7 days.
    - Complete Strength workouts on at least 3 different days.
    - Complete Cardio workouts on at least 2 different days.

  requirements:

    minimum_days_per_quest:
      reading: 7

    minimum_category_days:
      daily: 7
      nutrition: 7

    minimum_workout_type_days:
      strength: 3
      cardio: 2
```

All configured requirements must pass.

---

# Achievement evaluation

## `app/achievements.py`

The achievement engine:

1. loads `achievements.yaml`
2. loads quest definitions
3. loads quest logs for an ISO week
4. groups logs by date
5. groups quest IDs by category
6. groups workout IDs by workout type
7. evaluates all configured requirements
8. stores newly earned trophies

Category-based trophies automatically recognize user-created tasks because the evaluator uses the shared quest catalog.

For example:

```yaml
- id: swimming
  category: workout
  workout_type: cardio
```

automatically contributes toward cardio trophies.

No achievement definition needs to know the ID `swimming`.

---

# Trophy permanence

Once a trophy is inserted into SQLite, it is permanent.

For example:

```text
Bookworm
Week 37 · 2026
```

records the fact that the achievement was earned for that week.

Changing the current YAML later does not automatically revoke existing trophy rows.

This is intentional.

---

# Historical achievement caveat

Generic achievement evaluation needs the current quest definition in order to know a historical quest's category or workout type.

Therefore, when removing a shared custom quest from:

```text
user-quests.yaml
```

the administrator should be aware that historical, not-yet-awarded achievement evaluation can no longer infer that quest's category from the catalog.

Already-earned trophies remain unaffected because trophies are stored permanently in SQLite.

Preserving quest definitions is therefore preferable when historical evaluation matters.

---

# Quest loader

## `app/quests.py`

The quest loader reads both:

```text
configuration/quests.yaml
configuration/user-quests.yaml
```

Conceptually:

```python
load_quests()
```

returns the combined shared catalog.

Other responsibilities include:

- retrieving a quest by ID
- reading personal active-state overrides
- resolving current quest state
- writing user-created quests
- generating IDs for custom tasks
- safely updating `user-quests.yaml`

---

# Custom quest writes

`user-quests.yaml` is mutable runtime configuration.

Writes use:

- a temporary file
- atomic replacement
- a lock

This helps prevent two gmfi containers from writing the shared task catalog simultaneously.

The lock lives inside the shared configuration directory.

---

# Task Glossary

## `GET /glossary`

The Task Glossary displays the complete shared quest catalog.

It includes:

- built-in tasks
- user-created tasks
- active tasks
- inactive tasks
- category
- workout type where applicable
- description
- measurement configuration
- base XP
- XP scaling
- historical completions
- lifetime global XP
- historical skill XP contribution
- creator information for user-created quests

Inactive quests remain visible but are visually muted.

---

# Task activation

Each glossary card includes an action to:

```text
Activate
```

or:

```text
Deactivate
```

This modifies only the current user's `quest_states` table.

It does not modify the shared quest YAML.

---

# Adding tasks through the Glossary

The Task Glossary includes:

```text
+ Add task
```

The task creation form supports:

- name
- description
- category
- workout type for workout quests
- base XP
- optional measurement
- measurement label
- measurement unit
- minimum
- step
- optional global XP scaling
- maximum rewarded units
- base skill XP
- per-unit skill XP

A task is added to the shared catalog immediately after successful validation.

---

# Custom workout creation

If:

```text
Category = Workout
```

the form additionally requires:

```text
Workout type
```

with:

```text
Strength
Cardio
```

Examples:

```yaml
name: Calisthenics
category: workout
workout_type: strength
```

and:

```yaml
name: Swimming
category: workout
workout_type: cardio
```

These tasks automatically work with type-based trophy rules.

---

# Routes

Most main application routes currently live in:

```text
app/routes.py
```

Task Glossary routes have been split into:

```text
app/glossary_routes.py
```

This is the beginning of gradually reducing the size of `routes.py`.

A possible future structure is:

```text
app/routes/
├── __init__.py
├── today.py
├── character.py
├── week.py
├── trophies.py
├── glossary.py
└── quests.py
```

This refactor is not required for current functionality.

---

# Current pages

The main navigation contains five pages.

```text
Today
Character
Week
Trophy Room
Task Glossary
```

---

# Today

## `GET /`

Today is the primary interaction page.

It shows active quests grouped into:

```text
Daily
Nutrition
Workout
```

The page supports:

- normal quest completion
- measurable quest entry
- undoing completions
- today's XP
- compact quest cards

A quest can only be completed once on the current date.

---

# Character

## `GET /character`

The Character page shows:

- character level
- character title
- global XP
- progress toward the next level
- skills
- skill levels
- skill titles
- overall rank

Progression is calculated from stored historical quest rewards.

---

# Week

## `GET /week`

The Week page uses ISO weeks.

Example:

```text
/week?year=2026&week=37
```

A selected week runs:

```text
Monday -> Sunday
```

The page shows:

- all active quests
- Monday through Sunday
- completion state
- measurements
- weekly XP
- category groups
- historical editing
- future-date disabled states
- a compact XP history chart

---

# Week grouping

The Week table groups tasks based on quest category.

Current order:

```text
Daily
Nutrition
Workout
```

The grouping is category-driven rather than determined by the physical order of quests inside the YAML files.

This ensures user-created Daily tasks appear alongside other Daily tasks instead of simply appearing at the bottom.

---

# Historical editing

The Week page allows previous days to be corrected.

A historical completion uses the same quest completion route but sends a specific date.

Example:

```html
<input
    type="hidden"
    name="date"
    value="2026-09-08"
>
```

Future dates are rejected.

Historical entries receive the reward configuration that exists at the time the historical entry is actually logged.

Once stored, those rewards become historical snapshots.

---

# Weekly XP chart

The Week page contains a compact bar chart showing XP earned across the previous ten weeks relative to the selected week.

The chart is intentionally subtle:

- ten bars
- gmfi accent green
- week number underneath
- selected week highlighted
- XP/details available through hover
- no external charting dependency

The chart uses stored:

```text
quest_logs.xp_earned
```

so it reflects historical earned XP rather than recalculating quest rewards.

When viewing an older week, the chart follows that selected week.

For example:

```text
selected week = 37

chart = weeks 28 through 37
```

---

# Trophy Room

## `GET /trophies`

The Trophy Room displays every configured achievement.

Locked trophies remain visible.

Each trophy can show:

- icon
- name
- description
- requirements
- locked/unlocked state
- number of times earned
- historical earning weeks
- links back to those weeks

This makes achievements discoverable before they are earned.

---

# Templates

Templates live in:

```text
templates/
```

---

## `templates/base.html`

Contains shared application layout:

- document structure
- gmfi logo
- date
- navigation
- stylesheet
- shared content block

---

## `templates/today.html`

Renders the Today page.

Uses the shared quest-card partial.

---

## `templates/partials/quest_card.html`

Handles:

- normal tasks
- measurable tasks
- completed state
- XP display
- measurement display
- expansion
- collapse
- undo behavior

---

## `templates/character.html`

Renders character and skill progression.

---

## `templates/week.html`

Renders:

- ISO year selector
- ISO week selector
- date range
- weekly XP
- ten-week XP history chart
- grouped weekly quest table
- editable historical cells
- measurement input
- future-date state

---

## `templates/trophies.html`

Renders:

- locked trophies
- unlocked trophies
- trophy requirements
- earning history
- links to completed weeks

---

## `templates/glossary.html`

Renders:

- shared task catalog
- per-user activation state
- task statistics
- workout subtype
- task creation form
- measurement configuration
- skill reward configuration

---

# Styling

## `static/style.css`

gmfi currently uses one main CSS file.

The UI is intentionally dark and minimal.

Core variables:

```css
:root {
    --background: #09090b;
    --panel: #111114;
    --panel-hover: #18181c;

    --border: #27272a;

    --text: #f4f4f5;
    --muted: #8b8b94;

    --accent: #78ff8d;
    --accent-dark: #173d1f;

    --input: #0c0c0f;
}
```

Major styling areas include:

```text
Header
Navigation
Panels
Quest cards
Measured quest expansion
Character progression
Week table
Week editor
Week XP history
Trophy Room
Task Glossary
Task creator
Responsive layout
```

---

# Logo and icons

The header uses:

```text
static/gmfi-logo.png
```

The intended header version has a transparent background so it appears as a logo rather than as an app-icon tile.

The iOS Home Screen icon is separate:

```text
static/gmfi-touch-icon.png
```

The touch icon should remain:

- square
- opaque
- full-bleed
- suitable for iOS icon masking

This separation allows the web header logo to be transparent without compromising the Home Screen icon.

---

# Time handling

## `app/timeutils.py`

gmfi should not depend on whatever timezone the operating system or container happens to use.

Timezone configuration supports:

```text
TZ
```

and:

```text
TIMEZONE
```

with a fallback of:

```text
Europe/Amsterdam
```

Conceptually:

```python
TIMEZONE_NAME = (
    os.getenv("TZ")
    or os.getenv("TIMEZONE")
    or "Europe/Amsterdam"
)
```

Helpers include:

```python
now_local()
today_local()
```

These functions are used for local date handling.

---

# Why `tzdata` is installed

Python's `zoneinfo` module requires timezone data.

Windows may not provide the same IANA timezone data available on Linux.

Installing:

```text
tzdata
```

keeps timezone handling consistent across:

- Windows development
- Linux
- Docker

---

# Multi-user model

gmfi does not currently implement application-level accounts or login sessions.

Instead, each person runs a separate container.

For example:

```text
gmfi_bram
gmfi_wouter
```

Both containers use the same application code and configuration catalog.

Each container has its own:

```text
/app/data/gmfi.db
```

The result is:

```text
shared:
    application code
    built-in quest catalog
    custom quest catalog
    progression rules
    trophy rules

separate:
    quest logs
    measurements
    XP
    skill XP
    active task choices
    trophies
```

---

# `GMFI_USER`

Each container receives:

```text
GMFI_USER
```

Example:

```yaml
environment:
  GMFI_USER: bram
```

or:

```yaml
environment:
  GMFI_USER: wouter
```

This is used when recording the creator of shared custom quests.

It is not an authentication mechanism.

---

# Environment variables

A production `.env` may contain values such as:

```env
COMPOSE_PROJECT_NAME=gmfi

USER_1=bram
USER_2=wouter

TAILSCALE_IP=100.x.x.x

PORT_1=8050
PORT_2=8051

TIMEZONE=Europe/Amsterdam
```

Exact host ports are deployment-specific.

The important distinction is:

```text
host port -> container port 8050
```

The `.env` file should never be committed.

---

# Docker

gmfi runs in production using Docker and Gunicorn.

The current application/container port is:

```text
8050
```

Gunicorn serves:

```text
main:app
```

on port:

```text
8050
```

Do not confuse the Flask development server configuration with the production Gunicorn process.

Both currently use port `8050`, but they are still separate server processes.

---

# Production Docker Compose

The server uses one service per user.

Conceptually:

```yaml
services:

  gmfi-1:
    build:
      context: .
      dockerfile: Dockerfile

    container_name: ${COMPOSE_PROJECT_NAME}_${USER_1}

    restart: unless-stopped

    ports:
      - "${TAILSCALE_IP}:${PORT_1}:8050"

    env_file:
      - .env

    environment:
      GMFI_USER: ${USER_1}

    volumes:
      - ./data_${USER_1}:/app/data
      - ./configuration:/app/configuration


  gmfi-2:
    build:
      context: .
      dockerfile: Dockerfile

    container_name: ${COMPOSE_PROJECT_NAME}_${USER_2}

    restart: unless-stopped

    ports:
      - "${TAILSCALE_IP}:${PORT_2}:8050"

    env_file:
      - .env

    environment:
      GMFI_USER: ${USER_2}

    volumes:
      - ./data_${USER_2}:/app/data
      - ./configuration:/app/configuration
```

The configuration bind mount is important because:

```text
configuration/user-quests.yaml
```

is mutable runtime state shared by both containers.

---

# Compose validation

Before starting production containers, the resolved Compose configuration can be checked with:

```bash
docker compose config
```

This is especially useful when using environment-variable substitutions.

---

# Persistent data

Per-user databases live on the host.

Example:

```text
data_bram/gmfi.db
data_wouter/gmfi.db
```

These directories are bind-mounted into the corresponding container.

Running:

```bash
docker compose down
```

does not delete these files.

Running:

```bash
docker compose up -d --build
```

does not delete these files.

Replacing the application image does not delete them.

Deleting a user's database file does delete that user's:

- quest history
- XP history
- skill XP
- active quest overrides
- trophy history

---

# Shared mutable configuration

The production Compose file bind-mounts:

```text
./configuration:/app/configuration
```

This is required because custom quests are written at runtime.

Therefore:

```text
user-quests.yaml
```

persists independently of the Docker image.

Built-in YAML files also become visible through this mount.

---

# Recommended backups

At minimum, back up:

```text
data_bram/gmfi.db
data_wouter/gmfi.db
configuration/user-quests.yaml
```

The first two contain personal progress.

The third contains the runtime-created shared task catalog.

Example:

```bash
cp data_bram/gmfi.db data_bram/gmfi-backup.db
```

and:

```bash
cp configuration/user-quests.yaml configuration/user-quests-backup.yaml
```

For serious long-term use, automated backups should eventually be added.

---

# `.gitignore`

Important exclusions include:

```gitignore
.venv/
.env

data/
data_*/

__pycache__/
*.pyc

.vscode/
.idea/

.DS_Store
Thumbs.db

docker-compose.yml
configuration/user-quests.yaml
```

The following must not be committed:

- `.env`
- user databases
- server-only Compose configuration
- runtime `user-quests.yaml`
- API keys
- Tailscale auth keys
- passwords
- SSH keys

---

# Why `user-quests.yaml` is ignored

`quests.yaml` is administrator-maintained source configuration.

It belongs in Git.

`user-quests.yaml` is mutable runtime state.

It can be changed by users through the application.

Therefore:

```text
quests.yaml       -> tracked
user-quests.yaml  -> ignored
```

This avoids Git conflicts with runtime-generated content.

---

# Server Compose file

The production:

```text
docker-compose.yml
```

is also intentionally ignored by Git.

This allows server-specific values and deployment structure to remain private.

If it was previously tracked, remove it from Git tracking once with:

```bash
git rm --cached docker-compose.yml
```

The file itself remains on disk.

---

# Local development

Recommended environment:

```text
Python 3.13+
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it in PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run:

```powershell
python main.py
```

Open:

```text
http://localhost:8050
```

---

# Production workflow

On the home server:

```bash
cd ~/Docker/gmfi
git pull
docker compose up -d --build
```

Or use the server's existing helper command where appropriate.

Check status:

```bash
docker compose ps
```

Inspect logs:

```bash
docker compose logs -f
```

Validate configuration:

```bash
docker compose config
```

---

# Tailscale access

gmfi is intended to remain private.

The application should be bound to the server's Tailscale address rather than publicly exposed.

Conceptually:

```text
Internet
   X

Tailnet
   |
   v

Home server
   |
   +--> Bram gmfi
   |
   +--> Wouter gmfi
```

Each user's host port can differ.

For example:

```text
http://100.x.x.x:8050
http://100.x.x.x:8051
```

while both containers internally listen on:

```text
8050
```

---

# Security

gmfi currently has no application-level authentication.

That is intentional for the current private deployment model.

Tailscale is the access boundary.

Do **not** expose gmfi directly to the public internet without first adding proper authentication and appropriate production security controls.

The public Git repository must not contain:

```text
.env
SQLite databases
Tailscale authentication keys
API keys
passwords
SSH keys
private server configuration
user-quests.yaml
```

Note that quest configuration itself may reveal personal routines.

Even non-secret YAML should therefore be reviewed before publication.

---

# Adding a built-in quest

Add the quest to:

```text
configuration/quests.yaml
```

Example:

```yaml
- id: meditation
  name: Meditate
  category: daily
  description: Complete a meditation session
  active: false

  xp:
    base: 10

    skills:
      vitality:
        base: 1

      discipline:
        base: 2
```

Remember:

```yaml
active: false
```

means inactive **by default for fresh users**.

It does not forcibly deactivate the quest for existing users with database overrides.

---

# Adding a strength workout

```yaml
- id: gym_upper
  name: Upper Body
  category: workout
  workout_type: strength
  description: Complete an upper-body training session
  active: false

  measurement:
    type: sets
    label: Sets
    unit: sets
    min: 1
    step: 1

  xp:
    base: 10
```

---

# Adding a cardio workout

```yaml
- id: rowing
  name: Rowing
  category: workout
  workout_type: cardio
  description: Complete a rowing session
  active: false

  measurement:
    type: distance
    label: Distance
    unit: km
    min: 0.1
    step: 0.1

  xp:
    base: 10
```

No achievement changes are required for generic cardio trophies.

---

# Adding a user task

Normal users should generally use:

```text
Task Glossary -> + Add task
```

rather than editing `user-quests.yaml` manually.

The UI handles:

- ID generation
- validation
- duplicate detection
- creator metadata
- per-user activation
- safe shared-catalog writing

---

# Changing an existing quest

Usually safe to modify:

```text
name
description
XP values
measurement labels
measurement caps
skill rewards
```

Use more care with:

```text
id
category
workout_type
measurement structure
```

Changing category or workout type affects how future or retrospectively evaluated trophies classify that quest.

The quest ID is especially important because SQLite rows use it directly.

---

# Retiring a built-in quest

Because activation is now personal, `active` is primarily a default-state field rather than a global on/off switch.

To make an old built-in task inactive for fresh users:

```yaml
active: false
```

Existing users who already have a personal `quest_states` override keep their personal setting.

Historical logs remain untouched.

If the quest has important history, preserving its definition is generally safer than removing it completely.

---

# Changing a gym split

Suppose the built-in strength program changes from:

```text
Push
Pull
Legs
```

to:

```text
Upper
Lower
```

New quests can be added:

```yaml
- id: gym_upper
  category: workout
  workout_type: strength

- id: gym_lower
  category: workout
  workout_type: strength
```

Old quest IDs should not be reused for unrelated activities.

The generic Strength trophies continue to work because they care about:

```yaml
workout_type: strength
```

rather than requiring Push/Pull/Legs specifically.

This is one of the primary reasons workout subtypes exist.

---

# Adding a trophy

Most new trophies can now be created entirely through:

```text
configuration/achievements.yaml
```

Example:

```yaml
- id: strength_week
  name: Strength Week
  description: Maintain a high strength-training frequency.
  icon: "⚒"

  requirement_text:
    - Complete Strength workouts on at least 4 different days.

  requirements:
    minimum_workout_type_days:
      strength: 4
```

No Python changes are required because `minimum_workout_type_days` already exists.

---

# Category-based trophy example

```yaml
- id: balanced
  name: Balanced
  description: Maintain your routine, nutrition and training throughout the week.
  icon: "◆"

  requirement_text:
    - Complete a Daily task on all 7 days.
    - Complete a Nutrition task on all 7 days.
    - Complete a Workout on at least 4 different days.

  requirements:
    minimum_category_days:
      daily: 7
      nutrition: 7
      workout: 4
```

This remains valid even if the specific active tasks change.

---

# Core-task trophy example

Some trophies intentionally use a stable quest ID.

Example:

```yaml
- id: bookworm
  name: Bookworm
  description: Read every day for an entire week.
  icon: "▤"

  requirement_text:
    - Complete Reading on all 7 days.

  requirements:
    minimum_days_per_quest:
      reading: 7
```

This is appropriate because Reading is considered a core gmfi task.

---

# Important design rules

## Stable IDs

Treat these as permanent:

```text
quest IDs
achievement IDs
skill IDs
```

Names may change.

IDs should generally not.

---

## Shared configuration, personal history

The shared catalog defines what tasks exist.

The user's database defines what that user has done.

Do not mix these concepts.

---

## `active` is a default

In quest YAML:

```yaml
active: true
```

does not mean:

> force this quest active

It means:

> default to active when the user has no personal override

---

## Historical XP is immutable

Do not recalculate historical XP using current YAML.

Use:

```text
quest_logs.xp_earned
quest_logs.skill_xp_json
```

Those values are historical snapshots.

---

## Trophies are permanent once awarded

Changing achievement rules later does not automatically rewrite the trophy table.

This is intentional.

---

## Category-based trophies should be preferred

For fluid routines, prefer:

```yaml
minimum_category_days:
```

or:

```yaml
minimum_workout_type_days:
```

over long hardcoded quest-ID lists.

Use exact quest IDs only for intentionally permanent/core activities.

---

## Shared quest deletion is administrative

Users can deactivate tasks themselves.

Removing a quest from the shared catalog is an administrator decision.

---

# Data flow: quest completion

```text
Browser
   |
   v

POST quest completion
   |
   v

app/routes.py
   |
   +--> load quest
   |
   +--> resolve active state
   |
   +--> validate date
   |
   +--> validate measurement
   |
   v

app/xp.py
   |
   +--> global XP
   |
   +--> skill XP
   |
   v

app/db.py
   |
   v

SQLite quest_logs
```

---

# Data flow: character progression

```text
SQLite quest_logs
       |
       v

stored global XP
stored skill XP
       |
       v

app/progression.py
       |
       +--> character level
       +--> character title
       +--> skill levels
       +--> skill titles
       +--> overall rank
```

---

# Data flow: quest catalog

```text
configuration/quests.yaml
            |
            |
configuration/user-quests.yaml
            |
            v

       app/quests.py
            |
            +--> shared quest catalog
            |
            +--> per-user quest_states
            |
            v

      effective quest state
            |
            v

Today / Week / Glossary / Achievements
```

---

# Data flow: achievements

```text
configuration/achievements.yaml
             |
             v

      app/achievements.py
             |
             +--> quest logs
             |
             +--> categories
             |
             +--> workout types
             |
             v

      requirement evaluation
             |
             v

          trophies
             |
             v

        Trophy Room
```

---

# Current limitations

gmfi remains intentionally lightweight.

Current limitations include:

- no application-level authentication
- users are isolated through separate containers rather than app profiles
- no API
- no formal database migration framework
- no automated backups
- no quest scheduling beyond once-per-day behavior
- no administrator web interface for the shared catalog
- no automatic YAML schema validation
- no trophy progress bars
- no native mobile application
- no external fitness integration
- no Strava integration
- no Garmin integration
- no Apple Health integration
- no automatic conflict recovery for a stale custom-quest lock after an abnormal process crash

Several of these are acceptable for the current private Tailscale deployment.

---

# Possible future improvements

Potential future features include:

```text
Streaks
Daily streak bonuses
Monthly achievements
Annual achievements
Achievement progress indicators
Achievement rarity
Personal records
Workout notes
Bodyweight tracking
Sleep tracking
Heatmaps
Quest statistics
Weekly summaries
Monthly summaries
API endpoints
Automated backups
Import/export
Strava integration
Garmin integration
Health platform integration
Admin dashboard
Shared-catalog moderation tools
Formal database migrations
YAML schema validation
Route blueprints / route package refactor
```

---

# Data ownership

Persistent personal data remains local.

For example:

```text
data_bram/gmfi.db
data_wouter/gmfi.db
```

Shared application configuration also remains local:

```text
configuration/
```

No cloud service is required for core gmfi functionality.

---

# License

None as of yet.