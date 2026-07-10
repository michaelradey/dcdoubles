"""Double-elimination bracket construction and scheduling."""
import math
import random

from .constants import NUM_COURTS, DAY_AVAIL, DE_DUR, DE_SHORT_DUR
from .courts import Courts


def de_group_matches(group_teams, group_id):
    """
    Returns ordered list of match dicts for a double elimination group.
    Sequential on 1 court. Handles groups of 4, 6, or 8.
    """
    n   = len(group_teams)
    gp  = f'Group {group_id}'
    mid = [0]
    matches = []

    def r(m, wl): return f'BB {gp} M{m} {"Winner" if wl=="W" else "Loser"}'
    def t(i): return group_teams[i] if i < n else 'BYE'

    def add(phase, rnd, ta, tb, note=''):
        mid[0] += 1
        m = mid[0]
        matches.append({'match_num':m,'de_phase':phase,'round':rnd,
            'label':f'BB {gp} - {phase} {rnd}','team_a':ta,'team_b':tb,'note':note,
            'ref_w':r(m,'W'),'ref_l':r(m,'L')})
        return m

    if n == 6:
        m1=add('WB','R1-M1',t(2),t(5))          # S3 vs S6
        m2=add('WB','R1-M2',t(3),t(4))           # S4 vs S5
        m3=add('LB','R1-M1',r(m1,'L'),r(m2,'L'))
        m4=add('WB','R2-M1',t(0),r(m2,'W'))      # S1 vs M2W
        m5=add('WB','R2-M2',t(1),r(m1,'W'))      # S2 vs M1W
        m6=add('LB','R2-M1',r(m4,'L'),r(m3,'W'))
        m7=add('LB','R2-M2',r(m5,'L'),r(m6,'W'))
        m8=add('WB','Final',r(m4,'W'),r(m5,'W'))
        m9=add('LB','Final',r(m7,'W'),r(m8,'L'))
        m10=add('GF','Grand Final',r(m8,'W'),r(m9,'W'))
        add('GF','Grand Final Reset',r(m10,'L'),r(m10,'W'),
            note='Only played if Losers Bracket team wins Grand Final')

    elif n == 4:
        m1=add('WB','R1-M1',t(0),t(3))
        m2=add('WB','R1-M2',t(1),t(2))
        m3=add('LB','R1-M1',r(m1,'L'),r(m2,'L'))
        m4=add('WB','Final',r(m1,'W'),r(m2,'W'))
        m5=add('LB','Final',r(m3,'W'),r(m4,'L'))
        m6=add('GF','Grand Final',r(m4,'W'),r(m5,'W'))
        add('GF','Grand Final Reset',r(m6,'L'),r(m6,'W'),
            note='Only played if Losers Bracket team wins Grand Final')

    elif n == 8:
        m1=add('WB','R1-M1',t(0),t(7))
        m2=add('WB','R1-M2',t(3),t(4))
        m3=add('WB','R1-M3',t(2),t(5))
        m4=add('WB','R1-M4',t(1),t(6))
        m5=add('LB','R1-M1',r(m1,'L'),r(m2,'L'))
        m6=add('LB','R1-M2',r(m3,'L'),r(m4,'L'))
        m7=add('WB','R2-M1',r(m1,'W'),r(m2,'W'))
        m8=add('WB','R2-M2',r(m3,'W'),r(m4,'W'))
        m9=add('LB','R2-M1',r(m5,'W'),r(m8,'L'))
        m10=add('LB','R2-M2',r(m6,'W'),r(m7,'L'))
        m11=add('WB','Final',r(m7,'W'),r(m8,'W'))
        m12=add('LB','Semi',r(m9,'W'),r(m10,'W'))
        m13=add('LB','Final',r(m12,'W'),r(m11,'L'))
        m14=add('GF','Grand Final',r(m11,'W'),r(m13,'W'))
        add('GF','Grand Final Reset',r(m14,'L'),r(m14,'W'),
            note='Only played if Losers Bracket team wins Grand Final')

    else:
        # Generic: simplified sequential bracket
        for i in range(0,n-1,2):
            add('WB',f'R1-M{i//2+1}',t(i),t(i+1))

    return matches



def _bracket_seeding(B):
    if B == 1: return [1]
    h = _bracket_seeding(B // 2)
    return [x for pair in zip(h, [B+1-x for x in h]) for x in pair]


def build_de_bracket(level, teams):
    n = len(teams); B = 1
    while B < n: B *= 2
    seed_order = _bracket_seeding(B)
    mid = [0]; all_matches = []
    def new_m(ta, ta_dep, tb, tb_dep, bracket, rnd, note=''):
        mid[0] += 1; m_id = mid[0]
        deps = [d for d in [ta_dep, tb_dep] if d is not None]
        all_matches.append({'id':m_id,'bracket':bracket,'round_label':rnd,
            'team_a':ta,'team_b':tb,'deps':deps,'note':note,
            'label':f'{level} {bracket} {rnd}','level':level,'phase':'DOUBLE ELIM',
            'team_work':'Teams will ref internally',
            'is_pool':False,'is_de':True,'de_phase':bracket,'is_playin':False})
        return m_id
    def slot(s): return (teams[s-1], None) if s <= n else (None, None)
    wb = [slot(s) for s in seed_order]; wb_losers = []; wb_r = 1
    while len(wb) > 1:
        next_wb, rl = [], []
        for i in range(0, len(wb), 2):
            ta,ta_d = wb[i]; tb,tb_d = wb[i+1]
            if ta is not None and tb is not None:
                m = new_m(ta,ta_d,tb,tb_d,'WB',f'R{wb_r}')
                next_wb.append((f'M{m} Winner',m)); rl.append((f'M{m} Loser',m))
            else:
                # bye/empty: the present team (if any) advances; no loser here.
                next_wb.append((ta,ta_d) if ta is not None else (tb,tb_d))
                rl.append((None,None))   # keep loser lists full-length for LB pairing
        wb_losers.append(rl); wb = next_wb; wb_r += 1
    wb_champ = wb[0]; lr = [0]

    def lb_game(a, b, rlabel):
        """One LB match, propagating byes (a lone team advances; empties stay empty)."""
        ta,ta_d = a; tb,tb_d = b
        if ta is None and tb is None: return (None,None)
        if ta is None: return (tb,tb_d)
        if tb is None: return (ta,ta_d)
        m = new_m(ta,ta_d,tb,tb_d,'LB',rlabel)
        return (f'M{m} Winner', m)

    def lb_pair(slots, rlabel):
        """Major round: LB survivors play each other."""
        return [lb_game(slots[i], slots[i+1] if i+1 < len(slots) else (None,None), rlabel)
                for i in range(0, len(slots), 2)]

    def lb_drop(surv, drops, rlabel):
        """Minor round: each LB survivor plays a fresh WB drop-down (one-to-one)."""
        return [lb_game(s, d, rlabel) for s, d in zip(surv, drops)]

    # LB R1 pairs the WB R1 losers; then each WB round drops down into a minor
    # round (survivor vs drop-down), followed by a major round (survivor vs
    # survivor) — except the final drop, which is the LB final.
    lb_champ = (None,None)
    if wb_losers:
        lr[0] += 1
        cur = lb_pair(wb_losers[0], f'R{lr[0]}')
        for r in range(1, len(wb_losers)):
            last = (r == len(wb_losers) - 1)
            lr[0] += 1
            cur = lb_drop(cur, wb_losers[r], 'Final' if last else f'R{lr[0]}')
            if not last and len(cur) > 1:
                lr[0] += 1
                cur = lb_pair(cur, f'R{lr[0]}')
        lb_champ = cur[0] if cur else (None,None)

    lb_l, lb_d = lb_champ
    if lb_l:
        wc_l, wc_d = wb_champ
        new_m(wc_l, wc_d, lb_l, lb_d, 'GF', 'Grand Final')
    # Tag intro-round matches: WB R1-R3 + LB R1-R2  (DE_DUR = 40 min)
    # WB R1/R2/R3 and the LB rounds that run concurrently (LB R1 with WB R2,
    # LB R2 with WB R3) all play at the longer intro duration.
    # Everything after (WB R4+, LB R3+, GF) drops to DE_SHORT_DUR = 30 min.
    for m in all_matches:
        wb_r = (int(m['round_label'][1:])
                if m['bracket'] == 'WB' and m['round_label'].startswith('R')
                   and m['round_label'][1:].isdigit() else 0)
        lb_r = (int(m['round_label'][1:])
                if m['bracket'] == 'LB' and m['round_label'].startswith('R')
                   and m['round_label'][1:].isdigit() else 0)
        m['is_intro'] = (
            (m['bracket'] == 'WB' and 1 <= wb_r <= 3) or
            (m['bracket'] == 'LB' and 1 <= lb_r <= 2)
        )
    return all_matches


def schedule_de_parallel(match_defs, courts_obj):
    """Greedy parallel DE scheduler. Uses courts_obj.free_at for all NUM_COURTS
    courts, so any court freed by pool play / brackets is automatically available
    to DE as the day progresses."""
    from collections import defaultdict as _dd
    _dn = _dd(list)
    for _m in match_defs:
        for _d in _m['deps']: _dn[_d].append(_m['id'])
    _urg = {}
    def _u(mid):
        if mid in _urg: return _urg[mid]
        _urg[mid]=1+(max(_u(c) for c in _dn.get(mid,[])) if _dn.get(mid) else 0)
        return _urg[mid]
    for _m in match_defs: _u(_m['id'])

    match_end={}; pending=list(match_defs); scheduled=[]; seen=set()
    for _ in range(max(len(match_defs)*200,500)):
        if not pending: break
        t=min(courts_obj.free_at[1:])
        ready=[m for m in pending if all(d in match_end and match_end[d]<=t
                                         for d in m.get('deps',[]))]
        if not ready:
            fut=sorted(v for v in match_end.values() if v>t)
            if not fut: break
            # Advance idle courts to when the next dependency completes
            for c in range(1,NUM_COURTS+1):
                if courts_obj.free_at[c]<=t: courts_obj.free_at[c]=fut[0]
            continue
        avail=sorted(c for c in range(1,NUM_COURTS+1) if courts_obj.free_at[c]<=t)
        if not avail: continue  # all courts busy; next iter finds correct t
        ready.sort(key=lambda m:-_urg.get(m['id'],0))  # critical-path first
        for m,court in zip(ready,avail):
            if m['id'] in seen: continue
            _dur = DE_DUR if m.get('is_intro', True) else DE_SHORT_DUR
            seen.add(m['id']); courts_obj.book(court,t,_dur)
            match_end[m['id']]=t+_dur; pending.remove(m)
            scheduled.append({**{k:v for k,v in m.items() if k not in('deps',)},
                               'start':t,'end':t+_dur,'court':court})
    return scheduled


def renumber_de_matches(scheduled):
    """
    After scheduling, assign sequential display numbers to every DE match
    in time+court order. Replaces 'M{id} Winner/Loser' references with
    '#N Winner/Loser' and prefixes each match label with '#N' so every
    reference in the spreadsheet resolves to a visible row.
    """
    import re
    sorted_m = sorted(scheduled, key=lambda m: (m['start'], m['court']))
    # internal id -> sequential display number
    id_to_num = {m['id']: i+1 for i, m in enumerate(sorted_m)}

    def replace_ref(s):
        return re.sub(
            r'M(\d+) (Winner|Loser)',
            lambda mo: f'#{id_to_num[int(mo.group(1))]} {mo.group(2)}'
                       if int(mo.group(1)) in id_to_num else mo.group(0),
            str(s)
        )

    for m in sorted_m:
        num = id_to_num[m['id']]
        m['label']  = f'#{num} {m["label"]}'
        m['team_a'] = replace_ref(m['team_a'])
        m['team_b'] = replace_ref(m['team_b'])
        # drop internal id — no longer needed
        m.pop('id', None)
    return sorted_m


def schedule_de_division_plan(level, teams):
    """Determine minimum primary courts needed and pre-generate bracket.
    Returns (bracket, n_courts). Actual scheduling happens later in
    generate_schedule, after pool/bracket courts are known."""
    n=len(teams); n_courts=math.ceil(n/8)
    shuffled=list(teams); random.shuffle(shuffled)
    bracket=build_de_bracket(level,shuffled)
    # Trial: primary courts 1..n_courts free, rest blocked
    while n_courts<=NUM_COURTS:
        _d=Courts()
        for c in range(n_courts+1,NUM_COURTS+1): _d.free_at[c]=DAY_AVAIL+1
        _t=schedule_de_parallel(bracket,_d)
        if not _t or max(m['end'] for m in _t)<=DAY_AVAIL: break
        n_courts+=1
    return bracket,n_courts
