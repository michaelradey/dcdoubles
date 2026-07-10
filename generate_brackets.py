#!/usr/bin/env python3
"""
generate_brackets.py

Edit the TEAMS dict below, then run:

    python generate_brackets.py

Outputs pre-built bracket HTML into docs/ for GitHub Pages.
Push the result and the site updates automatically.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from tournament.double_elim import build_de_bracket

# ─────────────────────────────────────────────────────────────────────────────
# EDIT THIS — one list of team names per division, in seed order.
# ─────────────────────────────────────────────────────────────────────────────
TEAMS: dict[str, list[str]] = {
    "mens-a-open": [
        # "Smith / Jones",
        # "Lee / Park",
    ],
    "mens-b-bb": [
        # "Smith / Jones",
    ],
    "womens-a-open": [
        # "Smith / Jones",
    ],
    "womens-b-bb": [
        # "Smith / Jones",
    ],
}

LABELS: dict[str, str] = {
    "mens-a-open":   "Men's A & Open",
    "mens-b-bb":     "Men's B & BB",
    "womens-a-open": "Women's A & Open",
    "womens-b-bb":   "Women's B & BB",
}

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
#bracket{overflow-x:auto;padding-bottom:20px;max-width:900px;margin:0 auto}
.section{margin-bottom:36px}
.sec-title{font-family:'Syne',sans-serif;font-size:.9rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:14px;padding-left:2px}
.section:nth-child(1) .sec-title{color:var(--WB)}
.section:nth-child(2) .sec-title{color:var(--LB)}
.section:nth-child(3) .sec-title{color:var(--GF)}
.cols{display:flex;gap:20px;align-items:flex-start}
.col{display:flex;flex-direction:column;gap:16px;min-width:200px}
.col-h{font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;color:var(--mut);text-align:center;margin-bottom:2px}
.match{background:var(--sur);border:1px solid var(--brd);border-radius:10px;padding:8px;position:relative}
.mnum{position:absolute;top:-8px;left:8px;background:var(--bg);border:1px solid var(--brd);border-radius:5px;font-size:.6rem;color:var(--mut);padding:1px 5px}
.slot{display:flex;align-items:center;gap:6px;padding:3px 0}
.team{flex:1;font-size:.82rem;padding:7px 8px;border-radius:6px;border:1.5px solid var(--brd);background:var(--bg);color:var(--txt);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.team.pending{color:var(--mut);font-style:italic}
.slot.won .team{border-color:var(--win);color:var(--win);font-weight:500}
.slot.lost .team{opacity:.4}
.win-btn{flex:none;width:24px;height:24px;background:transparent;border:1.5px solid var(--brd);border-radius:6px;color:var(--mut);font-size:.8rem;display:flex;align-items:center;justify-content:center;cursor:pointer;padding:0}
.slot.won .win-btn{background:var(--win);border-color:var(--win);color:#ffffff}
.mnote{font-size:.62rem;color:var(--mut);font-style:italic;padding:4px 2px 2px;line-height:1.4}
footer{text-align:center;margin-top:40px;font-size:.72rem;color:var(--mut)}
@media print{
  body{background:#fff;color:#000;padding:0}
  .toolbar,header .sub,footer{display:none!important}
  .match{border-color:#999;background:#fff;break-inside:avoid}
  .team{border-color:#ccc;color:#000;background:#fff}
  .slot.won .team{color:#000;font-weight:700;border-color:#000}
  h1,.sec-title{color:#000}
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

function render() {
  if (!MATCHES.length) {
    document.getElementById('bracket').innerHTML =
      '<div class="empty">No teams yet.<br>Edit TEAMS in generate_brackets.py and re-run it.</div>';
    return;
  }
  const sections = [['WB','Winners Bracket'],['LB','Losers Bracket'],['GF','Grand Final']];
  let html = '';
  sections.forEach(([bk, title]) => {
    const ms = MATCHES.filter(m => m.bracket === bk);
    if (!ms.length) return;
    const rounds = [...new Set(ms.map(m => m.round))];
    html += `<div class="section"><div class="sec-title">${title}</div><div class="cols">`;
    rounds.forEach(rd => {
      const col = ms.filter(m => m.round === rd).sort((a,b) => a.id - b.id);
      html += `<div class="col"><div class="col-h">${rd}</div>`;
      col.forEach(m => { html += matchCard(m); });
      html += '</div>';
    });
    html += '</div></div>';
  });
  document.getElementById('bracket').innerHTML = html;
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


def generate():
    import hashlib
    import datetime

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
    generate()
