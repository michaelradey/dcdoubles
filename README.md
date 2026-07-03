# Volleyball Tournament Scheduler

A Flask web app that generates volleyball tournament schedules and exports them
as formatted Excel (`.xlsx`) workbooks.

Upload (or paste) a CSV roster of teams and the app computes a court-by-court
schedule — pool play, brackets, and double-elimination where needed —
respecting the venue constraints (9 courts, 7:20 AM–8:30 PM).

## Roster CSV

Upload the registration export directly. The **first row must be a header** and
columns are matched by name (order and extra columns like payment/date are
ignored). Required columns:

```text
Division, Level, Full Name (Player 1), Full Name (Player 2)
```

Optional per-player contact columns populate a **Contacts** sheet:

```text
Phone Number Player 1, Email Address Player 1,
Phone Number Player 2, Email Address Player 2
```

- **Division** — `Men`, `Women`, or `Coed`
- **Level** — `B`, `BB`, `A`, or `Open`
- One combined export works on any tab: the Co-ed tab uses only `Coed` rows and
  the M/W tabs use only `Men`/`Women` rows; other divisions are ignored. Only an
  invalid division/level *value* is an error.
- Each team's display name becomes `Full Name 1 / Full Name 2`; an internal team
  identifier (e.g. `B T1`) is kept so it ties to the rest of the workbook

It supports three modes:

- **Co-ed** — a single set of B/BB/A/Open divisions
- **Men's / Women's** — 8 divisions sharing the 9 courts with staggered starts
- **Big DE M/W** — a large Men's BB field run as double-elimination across all
  courts, with other divisions filling in as courts free up

## Requirements

- Python 3.9+
- [Flask](https://flask.palletsprojects.com/) and
  [openpyxl](https://openpyxl.readthedocs.io/) (see `requirements.txt`)

## Setup

Pick whichever tool you prefer.

### Option A — `uv` (fastest)

If you don't have `uv` yet:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then, from the project directory:

```bash
uv venv                       # create a virtual environment (.venv)
uv pip install -r requirements.txt
```

### Option B — `pip` + `venv` (standard library only)

```bash
python3 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running

Activate the virtual environment, then start the app:

```bash
source .venv/bin/activate     # Windows: .venv\Scripts\activate
python scheduler.py
```

Then open <http://localhost:5000> in your browser, upload or paste your roster
CSV, and click **Generate** to download the schedule as an `.xlsx` file.

Run `deactivate` when you're done to exit the virtual environment. Activation
only lasts for the current terminal session — re-run the `source` command in any
new terminal.

### Alternatives

```bash
# with uv, no activation needed
uv run scheduler.py

# use a different port (e.g. if 5000 is taken)
PORT=5050 python scheduler.py
```

## The generated workbook

Each download contains seven sheets:

- **Full Schedule** — every match with time, court, division, and teams
- **Court Rotation** — a grid of what's on each court in each 45-min slot
- **Bracket Summary** — advancement format per division
- **Team Tracker** — team names pre-filled; enter results (WW/WL/LL) and pool
  ranks + bracket seeds update automatically via live Excel formulas
- **Open Eligibility** — tracks the Open Championship eligibility rule
- **Format Guide** — a reference for the tournament format and timing
- **Contacts** — each team's players, phones, and emails from the roster CSV
