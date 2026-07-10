#!/usr/bin/env python3
"""
generate_brackets.py

Builds the four double-elimination bracket pages (Men's/Women's A&Open and
B&BB) into docs/ for GitHub Pages, from a registration CSV export.

    python generate_brackets.py                 # uses newest upload/*.csv
    python generate_brackets.py path/to/roster.csv

Team names are "Full Name 1 / Full Name 2" and are grouped by division + level.
Push the result and the site updates automatically.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from tournament.double_elim import build_de_bracket
from tournament.roster import parse_teams

# Each output bracket = one gender + a pair of levels. Seed order follows the
# CSV row order within the group.
LEVEL_GROUPS: dict[str, tuple[str, set[str]]] = {
    "mens-a-open":   ("Men",   {"A", "Open"}),
    "mens-b-bb":     ("Men",   {"B", "BB"}),
    "womens-a-open": ("Women", {"A", "Open"}),
    "womens-b-bb":   ("Women", {"B", "BB"}),
}

# Populated from the registration CSV at run time (see load_teams_from_csv).
TEAMS: dict[str, list[str]] = {slug: [] for slug in LEVEL_GROUPS}

LABELS: dict[str, str] = {
    "mens-a-open":   "Men's A & Open",
    "mens-b-bb":     "Men's B & BB",
    "womens-a-open": "Women's A & Open",
    "womens-b-bb":   "Women's B & BB",
}


def newest_csv():
    """Most recent CSV in upload/ (filenames are timestamped, so sort works)."""
    files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "upload", "*.csv")))
    return files[-1] if files else None


# Seeding priority within a combined bracket (lower = higher seed). The stronger
# level gets the top seeds, so standard bracket seeding spreads them to opposite
# halves and they only meet late (e.g. the two Open teams end up seeds 1 & 2).
LEVEL_RANK = {"Open": 0, "A": 1, "BB": 2, "B": 3}


def load_teams_from_csv(path):
    """Build {slug: [team_name, ...]} from a registration export.

    Team name is "Full Name 1 / Full Name 2" (from the roster parser). Teams are
    grouped into the four brackets by division + level, then seeded by level
    strength (CSV order breaks ties within a level).
    """
    text = open(path, encoding="utf-8-sig").read()
    teams = parse_teams(text, {"Men", "Women", "Coed"})   # Coed rows are ignored below
    out = {slug: [] for slug in LEVEL_GROUPS}
    for t in teams:
        for slug, (gender, levels) in LEVEL_GROUPS.items():
            if t["division"] == gender and t["level"] in levels:
                out[slug].append(t)
    return {slug: [t["name"] for t in sorted(ts, key=lambda t: LEVEL_RANK.get(t["level"], 9))]
            for slug, ts in out.items()}

DOCS_DIR = os.path.join(os.path.dirname(__file__), "docs")

# ─────────────────────────────────────────────────────────────────────────────
# Bracket page template.
# Uses __PLACEHOLDER__ tokens instead of .format() to avoid escaping CSS braces.
# ─────────────────────────────────────────────────────────────────────────────
HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__LABEL__ — DC Doubles</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#f4f6f9;--sur:#ffffff;--brd:#cfd6df;--acc:#157347;--acc2:#0e7490;--txt:#111827;--mut:#54606f;--win:#157347;--WB:#1667b3;--LB:#b5540f;--GF:#6d28d9}
body{font-family:'DM Mono',monospace;background:var(--bg);color:var(--txt);min-height:100vh;padding:32px 20px 80px}
header{text-align:center;margin-bottom:32px}
h1{font-family:'Syne',sans-serif;font-size:clamp(1.6rem,4vw,2.6rem);font-weight:800;letter-spacing:-.03em;color:var(--acc)}
.sub{margin-top:10px;color:var(--mut);font-size:.8rem;letter-spacing:.05em}
.sub a{color:var(--acc2);text-decoration:none}
.toolbar{max-width:900px;margin:0 auto 24px;display:flex;gap:10px;justify-content:flex-end}
button{background:transparent;color:var(--mut);border:1px solid var(--brd);border-radius:9px;font-family:'Syne',sans-serif;font-size:.78rem;font-weight:700;letter-spacing:.05em;padding:9px 16px;cursor:pointer;transition:opacity .2s}
button:hover{opacity:.7}button:active{opacity:.5}
.empty{max-width:900px;margin:60px auto;text-align:center;color:var(--mut);font-size:.85rem;line-height:2}
#bracket{overflow:auto;padding:4px 4px 30px}
.canvas{position:relative;margin:0 auto}
svg.wires{position:absolute;top:0;left:0;pointer-events:none;z-index:0;overflow:visible}
.wire{fill:none;stroke:#b7c1cd;stroke-width:1.5}
.wire.loser{stroke:#d8c3a6;stroke-dasharray:4 4}
.band-title{position:absolute;left:2px;font-family:'Syne',sans-serif;font-size:.9rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
.match{position:absolute;width:235px;background:var(--sur);border:1px solid var(--brd);border-radius:9px;padding:6px 8px;z-index:1}
.mnum{position:absolute;top:-8px;left:8px;background:var(--bg);border:1px solid var(--brd);border-radius:5px;font-size:.58rem;color:var(--mut);padding:1px 5px}
.slot{display:flex;align-items:center;gap:6px;padding:2px 0}
.team{flex:1;min-width:0;font-size:.76rem;padding:5px 7px;border-radius:6px;border:1.5px solid var(--brd);background:var(--bg);color:var(--txt);line-height:1.25;overflow-wrap:anywhere}
.team.pending{color:var(--mut);font-style:italic}
.slot.won .team{border-color:var(--win);color:var(--win);font-weight:500}
.slot.lost .team{opacity:.4}
.win-btn{flex:none;width:22px;height:22px;background:transparent;border:1.5px solid var(--brd);border-radius:6px;color:var(--mut);font-size:.75rem;display:flex;align-items:center;justify-content:center;cursor:pointer;padding:0}
.slot.won .win-btn{background:var(--win);border-color:var(--win);color:#ffffff}
.mnote{font-size:.58rem;color:var(--mut);font-style:italic;padding-top:4px;line-height:1.3}
footer{text-align:center;margin-top:40px;font-size:.72rem;color:var(--mut)}
@page{size:landscape}
@media print{
  body{background:#fff;color:#000;padding:0}
  .toolbar,header .sub,footer{display:none!important}
  #bracket{overflow:visible}
  .match{border-color:#999;background:#fff}
  .team{border-color:#ccc;color:#000;background:#fff}
  .slot.won .team{color:#000;font-weight:700;border-color:#000}
  .wire{stroke:#999}.wire.loser{stroke:#bbb}
  h1{color:#000}.band-title{color:#000!important}
}
</style></head><body>
<header>
  <h1>__LABEL_UPPER__</h1>
  <p class="sub">Double Elimination &nbsp;&#183;&nbsp; <a href="index.html">&larr; all divisions</a></p>
</header>

<div class="toolbar">
  <button id="btn-print">PRINT</button>
  <button id="btn-clear">RESET RESULTS</button>
</div>

<div id="bracket"></div>
<footer>Results saved in your browser &mdash; DC Doubles __YEAR__</footer>

<script>
const MATCHES = __MATCHES_JSON__;
const LS_KEY  = 'winners___SLUG____TEAMS_HASH__';

// winner[matchId] = 'a' | 'b' | null
let winner = {};

function loadWinners() {
  try { winner = JSON.parse(localStorage.getItem(LS_KEY) || '{}'); } catch(e) { winner = {}; }
}
function saveWinners() {
  try { localStorage.setItem(LS_KEY, JSON.stringify(winner)); } catch(e) {}
}

function parseRef(s) {
  const m = /^M(\\d+) (Winner|Loser)$/.exec(s || '');
  return m ? {ref: +m[1], kind: m[2] === 'Winner' ? 'W' : 'L'} : null;
}
const byId = {};
MATCHES.forEach(m => { byId[m.id] = m; });

function resolveTeam(s, depth) {
  if (depth > 50) return null;
  const ref = parseRef(s);
  if (!ref) return s || null;
  const w = winner[ref.ref];
  if (!w) return null;
  const src = byId[ref.ref];
  const chosen = ref.kind === 'W' ? w : (w === 'a' ? 'b' : 'a');
  return resolveTeam(chosen === 'a' ? src.team_a : src.team_b, depth + 1);
}

function slotHTML(m, side) {
  const raw  = side === 'a' ? m.team_a : m.team_b;
  const name = resolveTeam(raw, 0);
  const ref  = parseRef(raw);
  const isPending = !name && !!ref;
  const displayName = name || (ref ? (ref.kind==='W'?'Winner':'Loser')+' of M'+ref.ref : '\\u2014');
  const w = winner[m.id];
  const wonClass  = w === side ? ' won'  : '';
  const lostClass = (w && w !== side) ? ' lost' : '';
  return `<div class="slot${wonClass}${lostClass}" data-id="${m.id}" data-side="${side}">
    <button class="win-btn" data-id="${m.id}" data-side="${side}" title="Mark winner">&#10003;</button>
    <div class="team${isPending?' pending':''}">${displayName}</div>
  </div>`;
}

function matchCard(m) {
  return `<div class="match" data-id="${m.id}">
    <div class="mnum">M${m.id}</div>
    ${slotHTML(m,'a')}${slotHTML(m,'b')}
    ${m.note ? `<div class="mnote">${m.note}</div>` : ''}
  </div>`;
}

// Layout constants (a "game" is one card holding both team slots).
const SEC = [['WB','Winners Bracket'],['LB','Losers Bracket'],['GF','Grand Final']];
const CARD_W = 235, COL_GAP = 64, GAME_GAP = 22, SECTION_GAP = 46, TITLE_H = 32;

// Same-section feeder match ids for a game (used to center it over its children).
function sameSectionFeeders(m, idset) {
  const out = [];
  [m.team_a, m.team_b].forEach(s => {
    const r = parseRef(s);
    if (r && idset.has(r.ref)) out.push(r.ref);
  });
  return out;
}

function render() {
  const wrap = document.getElementById('bracket');
  if (!MATCHES.length) {
    wrap.innerHTML = '<div class="empty">No teams yet.<br>Add a CSV to upload/ and re-run generate_brackets.py.</div>';
    return;
  }

  // Column index per (section, round), in encounter order.
  const colIdx = {};
  SEC.forEach(([bk]) => {
    const rounds = [...new Set(MATCHES.filter(m => m.bracket === bk).map(m => m.round))];
    rounds.forEach((rd, ci) => { colIdx[bk + '|' + rd] = ci; });
  });

  // Render cards into a canvas, place X, then measure heights (names wrap).
  wrap.innerHTML = '<div class="canvas" id="canvas"><svg class="wires" id="wires"></svg>'
    + MATCHES.map(matchCard).join('') + '</div>';
  const canvas = document.getElementById('canvas');
  const el = {}; MATCHES.forEach(m => { el[m.id] = canvas.querySelector('.match[data-id="' + m.id + '"]'); });
  MATCHES.forEach(m => {
    el[m.id].style.left = (colIdx[m.bracket + '|' + m.round] * (CARD_W + COL_GAP)) + 'px';
    el[m.id].style.top = '0px';
  });
  const H = {}; MATCHES.forEach(m => { H[m.id] = el[m.id].offsetHeight; });

  // Vertical layout: each game centers on its same-section feeders; round-1
  // (and cross-section-fed) games stack evenly. Sections stack top to bottom.
  const CY = {}; const bands = []; let bandY = 0, maxRight = 0;
  SEC.forEach(([bk, title]) => {
    const ms = MATCHES.filter(m => m.bracket === bk);
    if (!ms.length) return;
    bands.push({ title, bk, y: bandY });
    const top = bandY + TITLE_H;
    const idset = new Set(ms.map(m => m.id));
    const rounds = [...new Set(ms.map(m => m.round))];
    let bottom = top;
    rounds.forEach(rd => {
      const col = ms.filter(m => m.round === rd)
        .map(m => {
          const fs = sameSectionFeeders(m, idset).filter(id => CY[id] != null);
          const d = fs.length ? fs.reduce((s, id) => s + CY[id], 0) / fs.length : null;
          return { m, d };
        })
        .sort((a, b) => (a.d == null ? 1e12 : a.d) - (b.d == null ? 1e12 : b.d) || a.m.id - b.m.id);
      let cursor = top;
      col.forEach(({ m, d }) => {
        const h = H[m.id];
        let y = d != null ? d - h / 2 : cursor;
        if (y < cursor) y = cursor;
        el[m.id].style.top = y + 'px';
        CY[m.id] = y + h / 2;
        cursor = y + h + GAME_GAP;
        bottom = Math.max(bottom, y + h);
      });
      maxRight = Math.max(maxRight, colIdx[bk + '|' + rd] * (CARD_W + COL_GAP) + CARD_W);
    });
    bandY = bottom + SECTION_GAP;
  });

  bands.forEach(b => {
    const d = document.createElement('div');
    d.className = 'band-title'; d.textContent = b.title;
    d.style.top = b.y + 'px'; d.style.color = 'var(--' + b.bk + ')';
    canvas.appendChild(d);
  });
  canvas.style.width = (maxRight + 8) + 'px';
  canvas.style.height = bandY + 'px';
  drawWires(canvas, el);
}

// Elbow connectors from each feeder game to the slot it feeds.
function drawWires(canvas, el) {
  const svg = document.getElementById('wires');
  const cr = canvas.getBoundingClientRect();
  svg.setAttribute('width', parseFloat(canvas.style.width));
  svg.setAttribute('height', parseFloat(canvas.style.height));
  let d = '';
  MATCHES.forEach(m => {
    const tc = el[m.id].getBoundingClientRect();
    ['a', 'b'].forEach(side => {
      const ref = parseRef(side === 'a' ? m.team_a : m.team_b);
      if (!ref || !el[ref.ref]) return;
      const sc = el[ref.ref].getBoundingClientRect();
      const sl = el[m.id].querySelector('.slot[data-side="' + side + '"]').getBoundingClientRect();
      const x1 = sc.right - cr.left, y1 = sc.top - cr.top + sc.height / 2;
      const x2 = tc.left - cr.left, y2 = sl.top - cr.top + sl.height / 2;
      const mx = (x1 + x2) / 2;
      d += '<path class="wire' + (ref.kind === 'L' ? ' loser' : '') + '" d="M' + x1 + ' ' + y1
        + ' H' + mx + ' V' + y2 + ' H' + x2 + '"/>';
    });
  });
  svg.innerHTML = d;
}

document.getElementById('bracket').addEventListener('click', e => {
  const btn = e.target.closest('.win-btn');
  if (!btn) return;
  const id = +btn.dataset.id, side = btn.dataset.side;
  winner[id] = winner[id] === side ? null : side;
  saveWinners();
  render();
});

document.getElementById('btn-print').addEventListener('click', () => window.print());
document.getElementById('btn-clear').addEventListener('click', () => {
  if (!confirm('Reset all results?')) return;
  winner = {};
  try { localStorage.removeItem(LS_KEY); } catch(e) {}
  render();
});

loadWinners();
render();
// Re-layout once the web font loads (card heights change → connector accuracy).
if (document.fonts && document.fonts.ready) document.fonts.ready.then(render);
</script></body></html>
"""

INDEX_HTML = """\
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DC Doubles — Brackets</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap');
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#f4f6f9;--sur:#ffffff;--brd:#cfd6df;--acc:#157347;--acc2:#0e7490;--txt:#111827;--mut:#54606f}}
body{{font-family:'DM Mono',monospace;background:var(--bg);color:var(--txt);min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:64px 20px 80px}}
header{{text-align:center;margin-bottom:52px}}
h1{{font-family:'Syne',sans-serif;font-size:clamp(2.4rem,6vw,4rem);font-weight:800;letter-spacing:-.03em;color:var(--acc);line-height:1}}
header p{{margin-top:14px;color:var(--mut);font-size:.82rem;letter-spacing:.08em;text-transform:uppercase}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;width:100%;max-width:760px}}
.card{{display:block;text-decoration:none;background:var(--sur);border:1px solid var(--brd);border-radius:16px;padding:28px 24px;transition:border-color .2s,transform .15s}}
.card:hover{{border-color:var(--acc2);transform:translateY(-2px)}}
.card .div{{font-family:'Syne',sans-serif;font-size:1.1rem;font-weight:800;letter-spacing:.02em;color:var(--txt);margin-bottom:6px}}
.card .sub{{font-size:.74rem;color:var(--mut);letter-spacing:.05em}}
.card .arrow{{margin-top:20px;font-size:.78rem;color:var(--acc2)}}
.mens .div{{color:#1667b3}}
.womens .div{{color:#a62d80}}
footer{{margin-top:60px;font-size:.72rem;color:var(--mut);text-align:center}}
</style></head><body>
<header>
  <h1>DC DOUBLES</h1>
  <p>Tournament Brackets</p>
</header>
<div class="grid">
  <a class="card mens" href="mens-a-open.html">
    <div class="div">Men's A &amp; Open</div>
    <div class="sub">Double Elimination</div>
    <div class="arrow">View bracket &rarr;</div>
  </a>
  <a class="card mens" href="mens-b-bb.html">
    <div class="div">Men's B &amp; BB</div>
    <div class="sub">Double Elimination</div>
    <div class="arrow">View bracket &rarr;</div>
  </a>
  <a class="card womens" href="womens-a-open.html">
    <div class="div">Women's A &amp; Open</div>
    <div class="sub">Double Elimination</div>
    <div class="arrow">View bracket &rarr;</div>
  </a>
  <a class="card womens" href="womens-b-bb.html">
    <div class="div">Women's B &amp; BB</div>
    <div class="sub">Double Elimination</div>
    <div class="arrow">View bracket &rarr;</div>
  </a>
</div>
<footer>DC Doubles {year}</footer>
</body></html>
"""


def generate(csv_path=None):
    import hashlib
    import datetime

    csv_path = csv_path or newest_csv()
    if csv_path:
        global TEAMS
        TEAMS = load_teams_from_csv(csv_path)
        print(f"loaded teams from {os.path.basename(csv_path)}")
    else:
        print("no CSV found in upload/ — generating empty brackets")

    os.makedirs(DOCS_DIR, exist_ok=True)
    year = datetime.date.today().year

    with open(os.path.join(DOCS_DIR, "index.html"), "w") as f:
        f.write(INDEX_HTML.format(year=year))
    print("wrote docs/index.html")

    for slug, teams in TEAMS.items():
        label = LABELS[slug]
        label_upper = label.upper()

        if teams:
            matches_raw = build_de_bracket(label, teams)
            matches_out = [
                {
                    "id": m["id"],
                    "bracket": m["bracket"],
                    "round": m["round_label"],
                    "team_a": m.get("team_a") or "",
                    "team_b": m.get("team_b") or "",
                    "note": m.get("note") or "",
                }
                for m in matches_raw
            ]
        else:
            matches_out = []

        # Hash the team list so localStorage is scoped to this exact bracket.
        # If teams change and you re-run the script, old saved results are ignored.
        teams_hash = hashlib.md5("|".join(teams).encode()).hexdigest()[:8]

        html = (HTML_TEMPLATE
            .replace("__LABEL__", label)
            .replace("__LABEL_UPPER__", label_upper)
            .replace("__SLUG__", slug)
            .replace("__MATCHES_JSON__", json.dumps(matches_out))
            .replace("__TEAMS_HASH__", teams_hash)
            .replace("__YEAR__", str(year))
        )
        out_path = os.path.join(DOCS_DIR, f"{slug}.html")
        with open(out_path, "w") as f:
            f.write(html)
        status = f"{len(teams)} teams" if teams else "no teams yet"
        print(f"wrote docs/{slug}.html  [{status}]")


if __name__ == "__main__":
    generate(sys.argv[1] if len(sys.argv) > 1 else None)
