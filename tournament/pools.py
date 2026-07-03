"""Pool sizing and pool/DE format decisions."""
import math
from math import comb
from collections import defaultdict

from .constants import LEVELS, NUM_COURTS
from .double_elim import schedule_de_division_plan


def min_pools_needed(n):
    if n < 3: return 0
    if n <= 6: return 1
    return math.ceil(n/5)

def optimal_pools(n):
    if n < 3: return []
    if n == 6: return [6]
    if n < 6: return [n]
    best_score, best_sizes = 9999, []
    for num_p in range(2,10):
        if n//num_p < 3: break
        bs=n//num_p; rm=n%num_p
        if bs>5: continue
        if bs==5 and rm>0: continue
        mx=bs+(1 if rm>0 else 0)
        if mx>5 or bs<3: continue
        sizes=sorted([bs+(1 if pp<rm else 0) for pp in range(num_p)],reverse=True)
        score=(max(sizes)-min(sizes))*10+sum(5-s for s in sizes)+num_p*0.05
        if score<best_score: best_score,best_sizes=score,sizes
    return best_sizes

# ── Build pools ────────────────────────────────────────────────────────────────
def build_pools(counts, combine_open=True):
    """
    Returns (pools, de_divisions, combined_info, error_message).
    de_divisions: {level: [team_names]} for divisions using double elimination.
    combined_info: {combined_pool_level: {team_name: original_level}} for eligibility.
    """
    de_divisions   = {}
    combined_info  = {}   # level of combined pool → {team: original_level}
    adjusted       = dict(counts)

    # Step 1: combine tiny divisions (1–5 teams) with A.
    #   Pool play is ALWAYS preferred over DE.
    #   Only BB→A (and Open→A when combine_open=True) allowed when tiny.
    #   M/W passes combine_open=False: Open always stays separate regardless of size.
    for tiny_lvl in ['Open', 'BB']:
        if tiny_lvl == 'Open' and not combine_open and adjusted.get('Open', 0) >= 3:
            continue   # M/W rule: Open with 3+ teams keeps its own pool; 1-2 team Open still merges
        n = adjusted.get(tiny_lvl, 0)
        if 0 < n < 6:
            a_n = adjusted.get('A', 0)
            if a_n >= 3:  # A has enough teams to combine with
                tiny_teams  = [f'{tiny_lvl} T{i+1}' for i in range(n)]
                a_teams     = [f'A T{i+1}' for i in range(a_n)]
                merged_n    = a_n + n
                combined_key = f'A+{tiny_lvl}'
                origin = {}
                for t in a_teams:    origin[t] = 'A'
                for t in tiny_teams: origin[t] = tiny_lvl
                combined_info[combined_key] = origin
                adjusted['A']      = merged_n
                adjusted[tiny_lvl] = 0

    # Step 2: compute courts needed for pool play (max pool size 5; pool-of-6 uses 3 courts)
    def _pool_courts(n):
        if n < 3:  return 0
        if n == 6: return 3   # six-pool format needs 3 simultaneous courts
        return math.ceil(n / 5)

    # Step 3: pool play is preferred. Only fall back to DE when courts truly can't fit.
    #   Loop: if total pool courts > 9, convert the largest non-combined division to DE.
    #   "absorbed" = tiny divisions already merged into A (don't double-count as DE candidates).
    absorbed = {p for ck in combined_info for p in ck.split('+')[1:]}
    n_de_courts = 0   # courts reserved for DE brackets

    for _guard in range(len(LEVELS) + 2):   # safety cap on iterations
        total_pc = sum(_pool_courts(adjusted.get(l, 0)) for l in LEVELS)
        if total_pc <= NUM_COURTS - n_de_courts:
            break   # everything fits in pool play — done

        # Pick the largest non-absorbed, non-DE division to convert to DE
        candidates = [(l, adjusted.get(l, 0)) for l in LEVELS
                      if adjusted.get(l, 0) >= 3
                      and l not in de_divisions
                      and l not in absorbed]
        if not candidates:                   # last resort: include A (primary of combined)
            candidates = [(l, adjusted.get(l, 0)) for l in LEVELS
                          if adjusted.get(l, 0) >= 3 and l not in de_divisions]
        if not candidates:
            return None, None, None, "Cannot fit all divisions in 9 courts."

        big_lvl, big_n = max(candidates, key=lambda x: x[1])
        big_teams = [f'{big_lvl} T{i+1}' for i in range(big_n)]
        de_divisions[big_lvl] = big_teams
        adjusted[big_lvl] = 0
        # Use the actual trial-based court count (may exceed ceil(n/8) for large brackets)
        _, de_cts = schedule_de_division_plan(big_lvl, big_teams)
        n_de_courts += de_cts
        # If this was the A-host of a combined pool, undo combining
        for ck in list(combined_info.keys()):
            if ck.split('+')[0] == big_lvl:
                del combined_info[ck]; break
        if n_de_courts > NUM_COURTS:
            return None, None, None, "Too many teams: cannot fit in 9 courts even with double elimination."
    else:
        return None, None, None, "Too many teams: cannot reduce to 9 simultaneous pools."

    # Step 4: build pools for non-DE, non-tiny divisions
    pools = []
    for lvl in LEVELS:
        n = adjusted.get(lvl, 0)
        if n < 3: continue

        # Determine effective level name for combined pools
        eff_lvl = lvl
        for ck, origin in combined_info.items():
            if ck.startswith('A+') and lvl == 'A':
                eff_lvl = ck
                break

        sizes = optimal_pools(n)
        if not sizes: continue

        # Build team list (combined or normal)
        if eff_lvl.startswith('A+') and eff_lvl in combined_info:
            origin = combined_info[eff_lvl]
            a_teams     = [t for t,ol in origin.items() if ol=='A']
            other_teams = [t for t,ol in origin.items() if ol!='A']
            # Distribute non-A teams evenly: one per pool where possible
            n_pools_for_lvl = len(sizes)
            pool_slots = [[] for _ in range(n_pools_for_lvl)]
            for i, ot in enumerate(other_teams):
                pool_slots[i % n_pools_for_lvl].append(ot)
            a_idx = 0
            for pi, (pool_size, slot) in enumerate(zip(sizes, pool_slots)):
                while len(slot) < pool_size:
                    slot.append(a_teams[a_idx]); a_idx += 1
            all_teams = [t for slot in pool_slots for t in slot]
        else:
            all_teams = [f'{lvl} T{i+1}' for i in range(n)]

        t = 0
        for pid, k in enumerate(sizes):
            pool_teams = all_teams[t:t+k]
            pools.append({
                'level':   eff_lvl,
                'pool_id': pid+1,
                'size':    k,
                'teams':   pool_teams,
                'matches': 4 if k==6 else comb(k,2),
                'is_six':  k==6,
                'origin':  combined_info.get(eff_lvl, {t: eff_lvl for t in pool_teams}),
            })
            t += k

    # Enforce max 9 pools
    while len(pools) > NUM_COURTS:
        by_lvl = defaultdict(list)
        for p in pools: by_lvl[p['level']].append(p)
        big = max(by_lvl, key=lambda l: len(by_lvl[l]))
        lp  = by_lvl[big]
        if len(lp)<=1: break
        n2=sum(p['size'] for p in lp); np2=len(lp)-1
        bs=n2//np2; rm=n2%np2
        if bs<3 or bs>6: break
        new_sizes=sorted([bs+(1 if pp<rm else 0) for pp in range(np2)],reverse=True)
        pools=[p for p in pools if p['level']!=big]
        orig={}
        for p in by_lvl[big]:
            for t,ol in p['origin'].items(): orig[t]=ol
        all_t=list(orig.keys()); t2=0
        for pid,k in enumerate(new_sizes):
            pt=all_t[t2:t2+k]
            pools.append({'level':big,'pool_id':pid+1,'size':k,'teams':pt,
                          'matches':4 if k==6 else comb(k,2),'is_six':k==6,
                          'origin':{t:orig[t] for t in pt}})
            t2+=k
        pools.sort(key=lambda p:(LEVELS.index(p['level'].split('+')[0]),p['pool_id']))

    pools.sort(key=lambda p:(LEVELS.index(p['level'].split('+')[0]),p['pool_id']))
    return pools, de_divisions, combined_info, None
