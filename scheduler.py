#!/usr/bin/env python3
"""
Volleyball Tournament Scheduler v10 — web app entry point.

Run:  python scheduler.py      (or:  PORT=5050 python scheduler.py)
Open: http://localhost:5000

The scheduling engine lives in the ``tournament`` package; this module is only
the Flask layer: routes, form parsing, and file/JSON responses. Page markup
lives in ``templates/``.
"""
import os
from datetime import datetime

from flask import Flask, render_template, request, send_file, jsonify

from tournament.double_elim import build_de_bracket
from tournament.generate import (generate_schedule, generate_mw_schedule,
                                 generate_bigde_mw_schedule)

app = Flask(__name__)

XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


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


# ── Co-ed tournament ─────────────────────────────────────────────────────────
def _coed_counts():
    return (int(request.form.get('b', 0)), int(request.form.get('bb', 0)),
            int(request.form.get('a', 0)), int(request.form.get('open', 0)))


@app.route('/generate', methods=['POST'])
def generate():
    try: b, bb, a, opn = _coed_counts()
    except ValueError: return 'Invalid input.', 400
    buf, _, err = generate_schedule(b, bb, a, opn)
    if err: return err, 400
    return send_file(buf, mimetype=XLSX_MIME, as_attachment=True,
                     download_name='volleyball_schedule.xlsx')


@app.route('/summary', methods=['POST'])
def summary():
    try: b, bb, a, opn = _coed_counts()
    except ValueError: return jsonify({'error': 'Invalid input'}), 400
    _, result, err = generate_schedule(b, bb, a, opn)
    if err: return jsonify({'error': err}), 400
    return jsonify(result)


# ── Men's / Women's tournament ───────────────────────────────────────────────
def _mw_counts():
    def gi(k):
        try: return max(0, int(request.form.get(k, 0)))
        except (TypeError, ValueError): return 0
    return (gi('w_b'), gi('w_bb'), gi('w_a'), gi('w_open'),
            gi('m_b'), gi('m_bb'), gi('m_a'), gi('m_open'))


@app.route('/generate-mw', methods=['POST'])
def generate_mw():
    buf, _, err = generate_mw_schedule(*_mw_counts())
    if err: return jsonify({'error': err}), 400
    fname = f'mw_tournament_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(buf, mimetype=XLSX_MIME, as_attachment=True, download_name=fname)


@app.route('/summary-mw', methods=['POST'])
def summary_mw():
    _, result, err = generate_mw_schedule(*_mw_counts())
    if err: return jsonify({'error': err}), 400
    return jsonify(result)


# ── Big-DE Men's / Women's tournament ────────────────────────────────────────
@app.route('/generate-bigde-mw', methods=['POST'])
def generate_bigde_mw():
    buf, _, err = generate_bigde_mw_schedule(*_mw_counts())
    if err: return err, 400
    return send_file(buf, mimetype=XLSX_MIME, as_attachment=True,
                     download_name='bigde_tournament.xlsx')


@app.route('/summary-bigde-mw', methods=['POST'])
def summary_bigde_mw():
    _, result, err = generate_bigde_mw_schedule(*_mw_counts())
    if err: return jsonify({'error': err}), 400
    return jsonify(result)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print('\n  Volleyball Tournament Scheduler v10')
    print(f'  Open: http://localhost:{port}\n')
    app.run(debug=False, port=port)
