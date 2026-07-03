"""Parse the registration CSV export into the rosters the engine needs.

The file is the tournament registration export. Columns are matched by header
name (order and extra columns like payment info don't matter). Required headers:

    Division, Level, Full Name (Player 1), Full Name (Player 2)

Optional per-player contact headers (populate the Contacts sheet):

    Phone Number Player 1/2, Email Address Player 1/2

- division must be Men, Women, or Coed
- level must be B, BB, A, or Open

A single combined export can be uploaded to any tab: rows whose division doesn't
belong to that tab are ignored (filtered), and only genuinely invalid division
or level *values* raise an error. Each team's display name is
"Full Name 1 / Full Name 2".
"""
import csv
import io
import re

from .constants import LEVELS

VALID_DIVISIONS = ('Men', 'Women', 'Coed')
_DIV_LOOKUP = {d.lower(): d for d in VALID_DIVISIONS}
_LEVEL_LOOKUP = {l.lower(): l for l in LEVELS}   # B, BB, A, Open

# logical field -> the normalized header it maps to
_COLUMNS = {
    'division':  'division',
    'level':     'level',
    'p1_name':   'fullnameplayer1',
    'p2_name':   'fullnameplayer2',
    'p1_phone':  'phonenumberplayer1',
    'p2_phone':  'phonenumberplayer2',
    'p1_email':  'emailaddressplayer1',
    'p2_email':  'emailaddressplayer2',
}
_REQUIRED = ('division', 'level', 'p1_name', 'p2_name')
_LABEL = {'division': 'Division', 'level': 'Level',
          'p1_name': 'Full Name (Player 1)', 'p2_name': 'Full Name (Player 2)'}


class RosterError(Exception):
    """Raised with a human-readable message when the CSV can't be used."""


def _norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def parse_teams(csv_text, allowed_divisions):
    """Parse CSV text into a list of team dicts for the given tournament side.

    allowed_divisions: divisions this side accepts (e.g. {'Coed'} or
    {'Men', 'Women'}). Rows in other valid divisions are skipped; rows with an
    invalid division or level value raise RosterError.
    """
    allowed = set(allowed_divisions)
    rows = [r for r in csv.reader(io.StringIO(csv_text)) if any(c.strip() for c in r)]
    if not rows:
        raise RosterError('The CSV is empty.')

    header = [_norm(h) for h in rows[0]]
    idx = {}
    for field, target in _COLUMNS.items():
        if target in header:
            idx[field] = header.index(target)
    missing = [f for f in _REQUIRED if f not in idx]
    if missing:
        raise RosterError(
            'CSV header is missing required column(s): '
            + ', '.join(_LABEL[m] for m in missing)
            + '. Make sure the first row is the header from the registration export.')

    def cell(row, field):
        i = idx.get(field)
        return row[i].strip() if i is not None and i < len(row) else ''

    teams = []
    for lineno, row in enumerate(rows[1:], 2):
        divraw = cell(row, 'division')
        if not divraw and not cell(row, 'p1_name'):
            continue   # blank/trailing row
        div = _DIV_LOOKUP.get(divraw.lower())
        if div is None:
            raise RosterError(
                f"Row {lineno}: division '{divraw}' must be one of "
                f"{', '.join(VALID_DIVISIONS)}.")
        if div not in allowed:
            continue   # valid division, just not this tab — ignore

        lvl = _LEVEL_LOOKUP.get(cell(row, 'level').lower())
        if lvl is None:
            raise RosterError(
                f"Row {lineno}: level '{cell(row, 'level')}' must be one of "
                f"{', '.join(LEVELS)}.")
        p1, p2 = cell(row, 'p1_name'), cell(row, 'p2_name')
        if not p1 or not p2:
            raise RosterError(f"Row {lineno}: both players' full names are required.")

        teams.append({
            'division': div, 'level': lvl,
            'p1_name': p1, 'p2_name': p2,
            'p1_phone': cell(row, 'p1_phone'), 'p1_email': cell(row, 'p1_email'),
            'p2_phone': cell(row, 'p2_phone'), 'p2_email': cell(row, 'p2_email'),
            'name': f'{p1} / {p2}',
        })

    if not teams:
        raise RosterError(
            f"No {' or '.join(sorted(allowed))} teams found in the CSV.")
    return teams


def group_by_level(teams):
    """{level: [team, ...]} preserving CSV order (single-division side)."""
    rosters = {lvl: [] for lvl in LEVELS}
    for t in teams:
        rosters[t['level']].append(t)
    return rosters


def group_by_gender_level(teams):
    """(women_rosters, men_rosters), each {level: [team, ...]} in CSV order."""
    women = {lvl: [] for lvl in LEVELS}
    men = {lvl: [] for lvl in LEVELS}
    for t in teams:
        (women if t['division'] == 'Women' else men)[t['level']].append(t)
    return women, men
