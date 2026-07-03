#!/usr/bin/env python3
"""
Volleyball Tournament Scheduler v10 — web app entry point.

Run:  python scheduler.py      (or:  PORT=5050 python scheduler.py)
Open: http://localhost:5000

The scheduling engine lives in the ``tournament`` package; this module is only
the Flask layer: routes, CSV intake, and file/JSON responses. Page markup lives
in ``templates/``.
"""
import os
from datetime import datetime

from flask import Flask, render_template, request, send_file, jsonify

from tournament.double_elim import build_de_bracket
from tournament.roster import (parse_teams, group_by_level, group_by_gender_level,
                               RosterError)
from tournament.generate import (generate_schedule, generate_mw_schedule,
                                 generate_bigde_mw_schedule)

app = Flask(__name__)

XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def _csv_text():
    """Roster CSV from an uploaded file (field 'file') or pasted text ('csv')."""
    f = request.files.get('file')
    if f and f.filename:
        return f.read().decode('utf-8-sig', errors='replace')
    return request.form.get('csv', '') or ''


def _xlsx(buf, name):
    return send_file(buf, mimetype=XLSX_MIME, as_attachment=True, download_name=name)


# ── Pages ────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/bracket')
def bracket_page():
    return render_template('bracket.html')


@app.route('/bracket/build', methods=['POST'])
def bracket_build():
    raw  = request.form.get('teams', '') or ''
    name = (request.form.get('name', '') or '').strip()
    teams = [t.strip() for t in raw.replace('\r', '').split('\n') if t.strip()]
    if len(teams) <= 1 and ',' in raw:   # allow comma-separated as a fallback
        teams = [t.strip() for t in raw.split(',') if t.strip()]
    if len(teams) < 2:
        return jsonify({'error': 'Enter at least 2 teams (one per line).'}), 400
    if len(teams) > 64:
        return jsonify({'error': 'Maximum 64 teams.'}), 400
    matches = build_de_bracket(name or 'DE', teams)
    out = [{'id': m['id'], 'bracket': m['bracket'], 'round': m['round_label'],
            'team_a': m['team_a'], 'team_b': m['team_b'], 'note': m.get('note', '')}
           for m in matches]
    return jsonify({'teams': teams, 'matches': out})


# ── Co-ed tournament (division must be Coed) ─────────────────────────────────
@app.route('/generate', methods=['POST'])
def generate():
    try:
        rosters = group_by_level(parse_teams(_csv_text(), {'Coed'}))
    except RosterError as e:
        return str(e), 400
    buf, _, err = generate_schedule(rosters)
    if err: return err, 400
    return _xlsx(buf, 'volleyball_schedule.xlsx')


@app.route('/summary', methods=['POST'])
def summary():
    try:
        rosters = group_by_level(parse_teams(_csv_text(), {'Coed'}))
    except RosterError as e:
        return jsonify({'error': str(e)}), 400
    _, result, err = generate_schedule(rosters)
    if err: return jsonify({'error': err}), 400
    return jsonify(result)


# ── Men's / Women's tournament (division must be Men or Women) ────────────────
@app.route('/generate-mw', methods=['POST'])
def generate_mw():
    try:
        women, men = group_by_gender_level(parse_teams(_csv_text(), {'Men', 'Women'}))
    except RosterError as e:
        return str(e), 400
    buf, _, err = generate_mw_schedule(women, men)
    if err: return err, 400
    fname = f'mw_tournament_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return _xlsx(buf, fname)


@app.route('/summary-mw', methods=['POST'])
def summary_mw():
    try:
        women, men = group_by_gender_level(parse_teams(_csv_text(), {'Men', 'Women'}))
    except RosterError as e:
        return jsonify({'error': str(e)}), 400
    _, result, err = generate_mw_schedule(women, men)
    if err: return jsonify({'error': err}), 400
    return jsonify(result)


# ── Big-DE Men's / Women's tournament (division must be Men or Women) ─────────
@app.route('/generate-bigde-mw', methods=['POST'])
def generate_bigde_mw():
    try:
        women, men = group_by_gender_level(parse_teams(_csv_text(), {'Men', 'Women'}))
    except RosterError as e:
        return str(e), 400
    buf, _, err = generate_bigde_mw_schedule(women, men)
    if err: return err, 400
    return _xlsx(buf, 'bigde_tournament.xlsx')


@app.route('/summary-bigde-mw', methods=['POST'])
def summary_bigde_mw():
    try:
        women, men = group_by_gender_level(parse_teams(_csv_text(), {'Men', 'Women'}))
    except RosterError as e:
        return jsonify({'error': str(e)}), 400
    _, result, err = generate_bigde_mw_schedule(women, men)
    if err: return jsonify({'error': err}), 400
    return jsonify(result)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print('\n  Volleyball Tournament Scheduler v10')
    print(f'  Open: http://localhost:{port}\n')
    app.run(debug=False, port=port)
