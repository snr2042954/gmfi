# gmfi

gmfi is a self-hosted life gamification dashboard for tracking habits, nutrition, workouts, reading, hobbies, progression, and weekly achievements.

The application is intentionally simple:

- Flask serves the web application.
- SQLite stores historical activity.
- YAML files define configurable game content.
- Jinja templates render the UI.
- Docker provides the production deployment.
- Tailscale can be used to access the app privately on a home server.

The main design goal is to keep **configuration separate from application logic**.

Most changes to quests, XP values, skills, level titles, ranks, and trophies should be possible without editing Python code.

---

# Core concepts

gmfi uses four main concepts:

1. Quests
2. Quest logs
3. Progression
4. Achievements / trophies

A quest is something the user can complete once per day.

Examples:

- take vitamins
- eat 4 eggs
- read pages
- go jogging
- go cycling
- complete a push workout
- spend time on a hobby

Some quests are simple yes/no completions.

Other quests have a measurement attached to them, such as:

- kilometers
- pages
- sets
- minutes
- hours
- repetitions

Completing a quest creates a permanent record in SQLite.

That record contains the XP and skill rewards that were earned at the time of completion.

This is important because changing future XP values in YAML does **not** rewrite historical progress.

---

# Project structure

```text
gmfi/
├── app/
│   ├── __init__.py
│   ├── achievements.py
│   ├── db.py
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
│   └── quests.yaml
│
├── data/
│   └── gmfi.db
│
├── static/
│   └── style.css
│
├── templates/
│   ├── partials/
│   │   └── quest_card.html
│   ├── base.html
│   ├── character.html
│   ├── today.html
│   ├── trophies.html
│   └── week.html
│
├── .dockerignore
├── .env
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── main.py
├── README.md
└── requirements.txt
```

---

# Application entry point

## `main.py`

`main.py` is the application entry point.

It should stay intentionally small.

Example:

```python
from app import create_app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8014,
        debug=True,
    )
```

There are two ways this file is used.

### Local development

When running:

```bash
python main.py
```

the Flask development server starts on port `8014`.

### Production

Inside Docker, Gunicorn imports:

```text
main:app
```

This means:

- import `main.py`
- find the variable named `app`
- serve that Flask application

The `if __name__ == "__main__"` block is not used by Gunicorn.

---

# Application factory

## `app/__init__.py`

This file creates the Flask application.

Responsibilities:

- create the Flask instance
- configure template and static paths
- initialize the database
- register routes

Typical structure:

```python
from flask import Flask

from app.db import init_db
from app.routes import register_routes


def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )

    init_db()
    register_routes(app)

    return app
```

Keeping application creation here prevents `main.py` from becoming the central location for all logic.

---

# Database layer

## `app/db.py`

This file owns SQLite access.

Responsibilities:

- determine the database path
- create the `data/` directory
- open SQLite connections
- initialize required tables
- initialize indexes
- enable foreign-key behavior where applicable

The database lives at:

```text
data/gmfi.db
```

The database should never be baked into the Docker image.

It is mounted as persistent host storage.

---

# Database schema

The primary activity table is:

```text
quest_logs
```

Each row represents one completed quest on one date.

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
skill_xp_json:
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

This means every quest can only be logged once per day.

---

# Trophy storage

Weekly achievements are stored separately in:

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

The combination of:

```text
achievement_id
iso_year
iso_week
```

is unique.

This prevents the same weekly trophy from being awarded twice for the same week.

Example:

```text
achievement_id: perfect_week
iso_year: 2026
iso_week: 37
earned_at: 2026-09-14T00:05:22+02:00
```

---

# Why XP is stored in the database

Quest definitions may change over time.

For example, jogging could originally award:

```yaml
scaling:
  per_unit: 5
```

and later be changed to:

```yaml
scaling:
  per_unit: 4
```

Historical jogging sessions should not suddenly lose XP.

Therefore, when a quest is completed, gmfi stores:

```text
xp_earned
skill_xp_json
```

directly in the database.

Historical progression is therefore based on what was earned at that moment, not on the current YAML configuration.

This also means an inactive or retired quest still contributes to historical progression.

---

# Configuration

All user-editable game configuration lives in:

```text
configuration/
```

The files are:

```text
configuration/
├── quests.yaml
├── progression.yaml
├── achievements.yaml
└── README.md
```

The intention is that most customization should happen here.

---

# Quest configuration

## `configuration/quests.yaml`

This file defines all quests.

A basic quest looks like:

```yaml
- id: vitamins
  name: Take vitamins
  category: daily
  description: Take daily vitamins
  active: true

  xp:
    base: 5

    skills:
      vitality:
        base: 2

      discipline:
        base: 1
```

A measurable quest looks like:

```yaml
- id: jogging
  name: Jogging
  category: workout
  description: Complete a run
  active: true

  measurement:
    type: distance
    label: Distance
    unit: km
    min: 0.1
    step: 0.1

  xp:
    base: 10

    scaling:
      per_unit: 5
      max_units: 15

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

---

# Quest fields

## `id`

Example:

```yaml
id: jogging
```

This is the permanent machine identifier for the quest.

It is used in the database.

Do not casually rename an existing ID.

If historical logs contain:

```text
quest_id = jogging
```

and the YAML ID becomes:

```text
running
```

those old logs will no longer match that quest definition.

Treat quest IDs as permanent database keys.

If a quest should be retired, prefer:

```yaml
active: false
```

rather than deleting or renaming it.

---

## `name`

Example:

```yaml
name: Jogging
```

This is the human-readable name displayed in the UI.

It is safe to change.

For example:

```yaml
name: Running
```

does not affect database linkage as long as the `id` stays the same.

---

## `category`

Example:

```yaml
category: workout
```

The category determines where the quest appears in the interface.

Current categories include:

```text
daily
nutrition
workout
```

The Today page groups quests by category.

The Week page also groups quests by category for readability.

Adding an entirely new category may require template or route changes depending on how it should be displayed.

---

## `description`

Example:

```yaml
description: Complete a run
```

Short explanatory text shown below the quest name.

Safe to change.

---

## `active`

Example:

```yaml
active: true
```

or:

```yaml
active: false
```

An inactive quest:

- is hidden from the normal UI
- cannot be newly logged
- remains defined in configuration
- retains all historical logs
- retains historical global XP
- retains historical skill XP
- can still be referenced by old trophy data

This is the preferred way to retire a quest.

Example:

```yaml
- id: gym_push
  name: Push
  category: workout
  active: false
```

If the training split changes, a new quest can be added separately:

```yaml
- id: gym_upper
  name: Upper Body
  category: workout
  active: true
```

Old `gym_push` history stays intact.

---

# Measurements

A quest becomes measurable when it contains:

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

The application does not strongly interpret the semantic meaning of `type`.

The main fields used by the UI are:

```text
label
unit
min
step
```

Possible measurement concepts include:

```text
km
pages
sets
minutes
hours
repetitions
```

Example reading quest:

```yaml
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

Example gym quest:

```yaml
measurement:
  type: sets
  label: Sets
  unit: sets
  min: 1
  step: 1
```

Example skating quest:

```yaml
- id: skating
  name: Skating
  category: workout
  description: Complete a skating session
  active: true

  measurement:
    type: distance
    label: Distance
    unit: km
    min: 0.1
    step: 0.1

  xp:
    base: 10

    scaling:
      per_unit: 2
      max_units: 40

    skills:
      endurance:
        base: 2
        per_unit: 0.3

      vitality:
        base: 1
        per_unit: 0.1

      discipline:
        base: 1
```

No Python changes should be required for quests that use already-supported measurement behavior.

---

# XP configuration

Global XP is configured inside:

```yaml
xp:
```

The simplest form is:

```yaml
xp:
  base: 10
```

A measurable quest may scale with the measurement:

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

= 35 XP
```

For a 30 km run:

```text
10 base XP
+
15 × 5 XP

= 85 XP
```

The extra distance beyond `max_units` does not award additional XP.

The cap prevents one unusually large activity from destabilizing progression.

---

# Skill XP

Skills are independent from global XP.

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

For a 5 km run:

```text
END:
2 + (5 × 0.7)
= 5.5

VIT:
1 + (5 × 0.2)
= 2

DISC:
1
```

These values are stored in `skill_xp_json` when the quest is logged.

---

# Quest loader

## `app/quests.py`

This file is responsible for reading:

```text
configuration/quests.yaml
```

Main functions include:

```python
load_quests()
```

Returns every quest, including inactive ones.

```python
get_active_quests()
```

Returns only quests where:

```yaml
active: true
```

```python
get_quest_by_id(quest_id)
```

Returns a single quest by its permanent ID.

This function intentionally searches inactive quests as well because historical systems may still need those definitions.

---

# XP engine

## `app/xp.py`

This file calculates rewards when a quest is completed.

Responsibilities include:

- calculate base XP
- calculate measurement-scaled XP
- apply `max_units`
- calculate individual skill XP
- return the final reward structure

Typical result:

```python
{
    "total": 35,
    "skills": {
        "endurance": 5.5,
        "vitality": 2.0,
        "discipline": 1.0,
    },
}
```

The routes layer then stores this result in SQLite.

---

# Character progression

## `configuration/progression.yaml`

This file controls:

- character level progression
- character titles
- skill definitions
- skill titles
- overall ranks

Example:

```yaml
character:
  level_curve:
    base_xp: 100
    growth_per_level: 50
```

This means each character level requires progressively more XP.

Example progression:

```text
Level 1 -> 100 XP
Level 2 -> 150 XP
Level 3 -> 200 XP
Level 4 -> 250 XP
```

---

# Character titles

Example:

```yaml
titles:
  - min_level: 1
    title: Initiate

  - min_level: 5
    title: Adventurer

  - min_level: 10
    title: Pathfinder
```

The highest title whose `min_level` has been reached becomes active.

---

# Skills

Current skills include:

```text
strength
endurance
vitality
intelligence
creativity
discipline
```

Each skill can have:

- display name
- short name
- level
- title
- total XP
- XP toward next level

Example:

```text
STR Lv. 5
Ironbound
62 / 100 XP
```

---

# Progression engine

## `app/progression.py`

This file reads:

```text
configuration/progression.yaml
```

Responsibilities:

- calculate character level
- calculate character XP progress
- determine character title
- calculate skill levels
- determine skill titles
- calculate overall rank

The progression values themselves should remain in YAML.

The Python file contains the logic for interpreting those values.

---

# Overall rank

Ranks are based on total skill levels.

Example:

```yaml
ranks:
  - name: Bronze
    min_total_skill_levels: 6

  - name: Silver
    min_total_skill_levels: 18

  - name: Gold
    min_total_skill_levels: 36
```

If the six skills are:

```text
STR 6
END 4
VIT 7
INT 3
CRE 2
DISC 8
```

the combined skill-level total is:

```text
30
```

The active rank is the highest rank whose threshold is at or below that total.

---

# Achievements

## `configuration/achievements.yaml`

Achievements define weekly trophies.

Example:

```yaml
- id: iron_week
  name: Iron Week
  description: Hit every part of your gym split during the week.
  icon: "⚒"

  requirement_text:
    - Complete Push at least once.
    - Complete Pull at least once.
    - Complete Legs at least once.

  requirements:
    minimum_days_per_quest:
      gym_push: 1
      gym_pull: 1
      gym_legs: 1
```

There are two separate parts:

```text
requirement_text
```

and:

```text
requirements
```

`requirement_text` is only for display in the Trophy Room.

`requirements` contains the machine-readable rules used by the application.

---

# Supported achievement requirements

The current achievement engine supports several rule types.

## Required quests every day

Example:

```yaml
requirements:
  required_quests_every_day:
    - vitamins
    - eggs
    - kwark
```

Every listed quest must be completed on all seven days of the selected week.

---

## Minimum workout days

Example:

```yaml
requirements:
  minimum_workout_days: 5
```

At least one workout-category quest must be completed on five distinct days.

Multiple workouts on the same day still count as one workout day.

---

## Minimum days per quest

Example:

```yaml
requirements:
  minimum_days_per_quest:
    gym_push: 1
    gym_pull: 1
    gym_legs: 1
```

Each specified quest must appear on at least the specified number of days during the week.

---

## Minimum days with any quest from a group

Example:

```yaml
requirements:
  minimum_days_with_any_quest:
    quest_ids:
      - jogging
      - cycling

    days: 3
```

At least one of the listed quests must be completed on three distinct days.

---

# Achievement engine

## `app/achievements.py`

This file:

- loads `configuration/achievements.yaml`
- fetches quest logs for a given ISO week
- groups logs by date
- evaluates each achievement's requirements
- records newly earned trophies in SQLite
- prevents duplicate trophies for the same week

Achievements are evaluated for completed historical weeks.

The Trophy Room shows both:

- unlocked trophies
- locked trophies

Unlocked trophies also show every week in which the achievement was earned.

---

# Trophy permanence

Once a trophy is inserted into the `trophies` table, it is intended to act as a permanent historical record.

This is different from XP calculations.

For example:

```text
Perfect Week
Week 37, 2026
```

represents the fact that the requirements were satisfied for that week when the trophy was awarded.

The trophy is not intended to disappear simply because the configuration changes later.

---

# Routes

## `app/routes.py`

This file connects HTTP requests to application logic.

Current main routes include:

```text
GET  /
GET  /character
GET  /week
GET  /trophies
POST /quest/<quest_id>/toggle
```

---

# Today page

## `GET /`

The Today page:

- loads active quests
- loads today's completion records
- separates quests by category
- shows daily quests
- shows nutrition quests
- shows workout quests
- displays today's XP
- allows quests to be completed or undone

Measured quests initially appear in the same compact style as normal quests.

Clicking the plus button expands the quest and reveals the measurement input.

Example:

```text
Reading
+
```

becomes:

```text
Reading

Pages
[ 24 ]

[Complete]
```

after expansion.

---

# Quest toggle route

## `POST /quest/<quest_id>/toggle`

This route handles both completing and undoing quests.

When a quest is not yet completed:

1. load the quest definition
2. validate that it exists
3. validate that it is active
4. validate the selected date
5. reject future dates
6. validate required measurements
7. calculate XP
8. calculate skill XP
9. insert a `quest_logs` row

When the same quest already exists for that date:

1. find the existing row
2. delete it
3. return to the previous page

Because of the database uniqueness constraint, the same quest cannot be logged twice on the same day.

---

# Historical editing

The Week page allows old days to be corrected.

This is useful when a task was completed but not entered at the time.

The same quest toggle route is used.

The only difference is that the Week page sends a specific date:

```html
<input
    type="hidden"
    name="date"
    value="2026-09-08"
>
```

The backend validates the date and rejects future entries.

Historical completions earn the XP configured at the moment they are entered.

---

# Character page

## `GET /character`

The Character page calculates progression from all stored logs.

It:

- sums all stored global XP
- parses all stored skill XP JSON
- calculates character level
- determines character title
- calculates each skill level
- determines skill titles
- calculates overall rank

Character progression is calculated dynamically from historical logs.

Character levels themselves are not stored separately in SQLite.

---

# Week page

## `GET /week`

The Week page uses ISO week numbering.

Example:

```text
/week?year=2026&week=37
```

The selected week is converted to a Monday-Sunday date range.

For example:

```text
Week 37
September 7 - September 13 · 2026
```

The page shows:

- all active quests
- Monday through Sunday
- completed quests
- measured values where applicable
- weekly XP
- category grouping
- historical editing

Categories are grouped visually rather than displayed as one long undifferentiated list.

Typical groups are:

```text
Daily
Nutrition
Workout
```

---

# ISO weeks

gmfi uses ISO-8601 week numbering.

ISO weeks:

- start on Monday
- end on Sunday
- are numbered from 1 to 52 or 53
- have an ISO year that can occasionally differ from the calendar year near New Year's Day

The application uses:

```python
date.fromisocalendar(
    year,
    week,
    weekday,
)
```

to determine the real dates for a selected week.

---

# Trophy Room

## `GET /trophies`

The Trophy Room loads every achievement definition, regardless of whether it has ever been earned.

Locked achievements remain visible.

A locked trophy shows:

- name
- description
- icon
- completion requirements
- locked state

Unlocked trophies additionally show:

- number of times earned
- all completed weeks
- links back to those weeks

This makes achievements discoverable before they are unlocked.

---

# Templates

Templates live in:

```text
templates/
```

---

## `templates/base.html`

Shared application layout.

Contains:

- HTML document structure
- gmfi branding
- date
- navigation
- shared CSS import
- Jinja content block

All main pages extend this template.

---

## `templates/today.html`

Renders the Today page.

Contains:

- daily quest section
- nutrition section
- workout section
- JavaScript for expandable measurable quests

---

## `templates/partials/quest_card.html`

Shared quest card markup.

This avoids duplicating quest UI code across categories.

The partial handles:

- normal quests
- measurable quests
- completed state
- XP display
- measurement display
- expand/collapse behavior
- undo behavior

---

## `templates/character.html`

Renders:

- character level
- character title
- rank
- total XP
- skill cards
- skill progress bars
- skill titles

---

## `templates/week.html`

Renders:

- ISO year selector
- ISO week selector
- date range
- weekly XP
- grouped weekly quest table
- editable historical cells
- measured historical quest input
- future-date disabled state

---

## `templates/trophies.html`

Renders:

- all trophy definitions
- locked state
- unlocked state
- trophy requirements
- number of times earned
- historical completed weeks

---

# Styling

## `static/style.css`

All application styling currently lives in one CSS file.

Major sections include:

```text
Global variables
Header
Navigation
Panels
XP bars
Quest cards
Measured quest expansion
Character stats
Week table
Week editor
Week selector
Trophy room
Responsive layout
```

The CSS uses variables defined near the top:

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

Changing these variables is the easiest way to adjust the overall theme.

---

# Time handling

## `app/timeutils.py`

gmfi does not rely directly on the operating system's local date.

Instead, the application timezone is read from:

```env
TZ=
```

Example:

```env
TZ=Europe/Amsterdam
```

The helper exposes functions such as:

```python
now_local()
today_local()
```

These functions ensure that:

- quest dates roll over at the intended local midnight
- historical entries use the correct date
- Docker host timezone differences do not affect gmfi behavior

---

# Why `tzdata` is installed

Python's `zoneinfo` module uses the IANA timezone database.

Linux environments usually provide timezone data through the OS.

Windows environments may not.

The `tzdata` package is therefore included in `requirements.txt` so timezones such as:

```text
Europe/Amsterdam
```

work consistently across:

- Windows development
- Linux
- Docker

---

# Environment variables

The project expects a root-level:

```text
.env
```

At minimum:

```env
TZ=Europe/Amsterdam
```

The `.env` file should not be committed.

Add it to:

```text
.gitignore
```

---

# Local development

## Requirements

Recommended:

```text
Python 3.13+
```

Create a virtual environment:

```bash
python -m venv .venv
```

### Windows PowerShell

Activate:

```powershell
.venv\Scripts\Activate.ps1
```

### Linux / macOS

Activate:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
python main.py
```

Open:

```text
http://localhost:8014
```

---

# Current Python dependencies

The current environment uses:

```text
blinker==1.9.0
click==8.5.0
Flask==3.1.3
gunicorn==23.0.0
itsdangerous==2.2.0
Jinja2==3.1.6
MarkupSafe==3.0.3
python-dotenv==1.2.3
PyYAML==6.0.3
tzdata==2026.3
Werkzeug==3.1.8
```

Gunicorn is used only for production deployment inside Docker.

The Flask development server is still used for:

```bash
python main.py
```

---

# Docker

gmfi is designed to run through Docker Compose.

The desired deployment workflow is:

```bash
git pull
docker compose up -d --build
```

---

# Dockerfile

The Dockerfile:

1. starts from a Python base image
2. sets `/app` as the working directory
3. installs Python dependencies
4. copies application files
5. creates the data directory
6. exposes port `8014`
7. starts Gunicorn

The production server runs:

```text
main:app
```

through Gunicorn.

---

# Docker Compose

`docker-compose.yml` defines the gmfi service.

Typical configuration:

```yaml
services:
  gmfi:
    build:
      context: .
      dockerfile: Dockerfile

    container_name: gmfi

    restart: unless-stopped

    ports:
      - "8014:8014"

    env_file:
      - .env

    volumes:
      - ./data:/app/data
```

The important line for persistence is:

```yaml
volumes:
  - ./data:/app/data
```

The SQLite database therefore lives outside the container lifecycle.

---

# Persistent data

The persistent database is:

```text
data/gmfi.db
```

Running:

```bash
docker compose down
```

does not delete it.

Running:

```bash
docker compose up -d --build
```

does not delete it.

Replacing the Docker image does not delete it.

Deleting:

```text
data/gmfi.db
```

does delete all quest history and trophy data.

Back up this file if progress matters.

---

# Recommended backups

At minimum, periodically copy:

```text
data/gmfi.db
```

Example:

```bash
cp data/gmfi.db data/gmfi-backup.db
```

For a dated backup:

```bash
cp data/gmfi.db "data/gmfi-$(date +%Y-%m-%d).db"
```

For more serious deployment use, automated SQLite backups may be added later.

---

# `.dockerignore`

The Docker build should ignore development-only and persistent files.

Typical contents:

```text
.git
.gitignore

.venv
venv

__pycache__
*.pyc
*.pyo

data
*.db

.env

.vscode
.idea
```

The `configuration/` directory should **not** be ignored.

Those YAML files need to be copied into the image.

---

# `.gitignore`

Typical contents:

```text
.venv/
.env
data/
__pycache__/
*.pyc
```

The database is intentionally not committed.

The YAML configuration files are intended to be committed.

---

# Server deployment

Clone:

```bash
git clone <repository-url>
cd gmfi
```

Create:

```text
.env
```

Example:

```env
TZ=Europe/Amsterdam
```

Create the persistent data directory:

```bash
mkdir -p data
```

Build and start:

```bash
docker compose up -d --build
```

Check status:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f
```

Stop:

```bash
docker compose down
```

---

# Updating the server

After pushing changes to Git:

```bash
cd gmfi
git pull
docker compose up -d --build
```

Because configuration files are currently copied into the Docker image, changes to:

```text
configuration/*.yaml
```

also require rebuilding the image.

The database remains untouched because it is bind-mounted separately.

---

# Tailscale access

gmfi listens on:

```text
8014
```

If the server is connected to Tailscale, another device on the same Tailnet can access:

```text
http://<tailscale-ip>:8014
```

Example:

```text
http://100.x.x.x:8014
```

If Tailscale MagicDNS is enabled:

```text
http://<server-hostname>:8014
```

No public internet exposure is required.

---

# Application data flow

The general flow for completing a quest is:

```text
Browser
   |
   v
POST /quest/<quest_id>/toggle
   |
   v
app/routes.py
   |
   +--> load quest definition
   |
   +--> validate date
   |
   +--> validate measurement
   |
   v
app/xp.py
   |
   +--> calculate global XP
   |
   +--> calculate skill XP
   |
   v
app/db.py
   |
   v
SQLite quest_logs
```

The Character page then performs:

```text
SQLite quest_logs
   |
   v
sum global XP
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

# Configuration data flow

Quest configuration:

```text
configuration/quests.yaml
        |
        v
app/quests.py
        |
        v
routes / XP engine / templates
```

Progression configuration:

```text
configuration/progression.yaml
        |
        v
app/progression.py
        |
        v
character page
```

Achievement configuration:

```text
configuration/achievements.yaml
        |
        v
app/achievements.py
        |
        v
trophies table
        |
        v
trophy room
```

---

# Adding a new simple quest

Example:

```yaml
- id: meditation
  name: Meditate
  category: daily
  description: Complete a meditation session
  active: true

  xp:
    base: 10

    skills:
      vitality:
        base: 1

      discipline:
        base: 2
```

Restart the development app or rebuild Docker.

No database migration is required.

---

# Adding a new measurable quest

Example:

```yaml
- id: skating
  name: Skating
  category: workout
  description: Complete a skating session
  active: true

  measurement:
    type: distance
    label: Distance
    unit: km
    min: 0.1
    step: 0.1

  xp:
    base: 10

    scaling:
      per_unit: 2
      max_units: 40

    skills:
      endurance:
        base: 2
        per_unit: 0.3

      vitality:
        base: 1
        per_unit: 0.1

      discipline:
        base: 1
```

The Today page should automatically render this as a compact quest.

Clicking the plus button expands the measurement form.

---

# Changing an existing quest

These fields are generally safe to modify:

```text
name
description
active
XP values
measurement labels
measurement caps
skill rewards
```

Be more careful with:

```text
id
category
measurement structure
```

The `id` is particularly important because historical database rows use it.

---

# Retiring a quest

Do this:

```yaml
active: false
```

Do not delete it unless you are deliberately abandoning historical linkage.

Example:

```yaml
- id: gym_push
  name: Push
  category: workout
  description: Legacy push workout
  active: false
```

Historical logs remain in SQLite.

Historical XP remains valid because rewards were stored when the quest was completed.

---

# Changing a gym split

Suppose the current split is:

```text
Push
Pull
Legs
```

and it changes to:

```text
Upper
Lower
```

Retire:

```yaml
gym_push
gym_pull
gym_legs
```

using:

```yaml
active: false
```

Then add:

```yaml
gym_upper
gym_lower
```

with new permanent IDs.

This preserves old PPL history while starting a clean history for the new training structure.

---

# Adding a trophy

Most trophies can be added through `configuration/achievements.yaml`.

Example:

```yaml
- id: endurance_week
  name: Endurance Week
  description: Complete cardio on four different days.
  icon: "▲"

  requirement_text:
    - Jog or cycle on at least 4 different days.

  requirements:
    minimum_days_with_any_quest:
      quest_ids:
        - jogging
        - cycling

      days: 4
```

If the desired achievement can be represented using an existing supported requirement type, no Python changes are required.

If a completely new requirement type is needed, `app/achievements.py` must be extended.

---

# Important design rules

## Stable IDs

Treat IDs as permanent.

This applies to:

```text
quest IDs
achievement IDs
skill IDs
```

Human-facing names may change.

Machine-facing IDs should remain stable.

---

## YAML defines current rules

YAML defines the current configuration.

Examples:

```text
current quest list
current XP rewards
current progression curve
current achievement requirements
```

---

## SQLite records history

SQLite stores what actually happened.

Examples:

```text
quest completion date
measurement value
XP earned
skill XP earned
trophies awarded
```

---

## Historical XP should not be recalculated

Do not derive old XP from current quest configuration.

Historical XP is already stored in:

```text
quest_logs.xp_earned
quest_logs.skill_xp_json
```

This is intentional.

---

## Inactive is better than deleted

For anything that has historical data:

```yaml
active: false
```

is safer than removal.

---

# Development workflow

Typical local workflow:

```bash
git pull
```

Activate the virtual environment:

```powershell
.venv\Scripts\Activate.ps1
```

Run:

```bash
python main.py
```

Make changes.

Test locally.

Then:

```bash
git add .
git commit -m "feat: describe change"
git push
```

---

# Production workflow

On the home server:

```bash
cd gmfi
git pull
docker compose up -d --build
```

Inspect:

```bash
docker compose ps
```

Logs:

```bash
docker compose logs -f
```

---

# Current pages

## Today

```text
/
```

Primary interaction page.

Used to:

- complete today's quests
- enter measurable values
- undo completions
- see today's XP

---

## Character

```text
/character
```

Used to view:

- character level
- title
- global XP progress
- skills
- skill levels
- skill titles
- overall rank

---

## Week

```text
/week
```

Used to view and correct historical weekly tracking.

Supports:

```text
/week?year=2026&week=37
```

---

## Trophy Room

```text
/trophies
```

Used to view:

- all achievement types
- locked achievements
- requirements
- unlocked achievements
- number of times earned
- historical earning weeks

---

# Current limitations

gmfi is intentionally still lightweight.

Current limitations include:

- single-user only
- no authentication
- no multi-user profiles
- no API
- no database migrations framework
- no automated backups
- no quest scheduling beyond once-per-day behavior
- no separate admin/configuration UI
- no automatic YAML validation
- no automatic trophy progress bars
- no mobile application
- no external fitness integrations
- no Strava/Garmin/Apple Health integration

For a private Tailscale deployment, several of these are intentional.

---

# Possible future improvements

Potential additions include:

```text
Streaks
Daily streak bonuses
Monthly achievements
Annual achievements
Quest prerequisites
Quest difficulty
Quest tags
Skill trees
Character classes
Equipment
Badges
Achievement rarity
Trophy tiers
Personal records
Workout duration
Workout notes
Bodyweight tracking
Sleep tracking
Charts
Heatmaps
Quest statistics
Weekly summaries
Monthly summaries
API endpoints
Automated backups
Import/export
Strava integration
Health platform integration
User authentication
```

---

# Security

gmfi currently assumes private access.

The intended deployment model is:

```text
Internet
   X

Tailnet
   |
   v
Home server
   |
   v
gmfi:8014
```

Do not expose the application directly to the public internet without adding proper authentication and production security controls.

Tailscale should act as the access boundary for the current deployment model.

---

# Data ownership

All persistent tracking data is stored locally in:

```text
data/gmfi.db
```

All configurable application/game rules are stored locally in:

```text
configuration/
```

No cloud service is required for core functionality.

---

# License

None as of yet!!!