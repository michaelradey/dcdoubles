"""Top-level schedule generators for each tournament mode."""
import io

from .constants import NUM_COURTS, DAY_AVAIL, POOL_DUR, LEVELS, RR
from .utils import fmt
from .courts import Courts
from .pools import build_pools
from .double_elim import (build_de_bracket, schedule_de_parallel,
                          renumber_de_matches, schedule_de_division_plan)
from .pool_play import (schedule_pool_play, compute_stagger_offsets,
                        add_gender_prefix, check_pool_gaps)
from .brackets import bracket_structure, schedule_brackets
from .excel import build_excel


def generate_schedule(b, bb, a, opn):
    counts = {'B':b,'BB':bb,'A':a,'Open':opn}
    pools, de_divs, combined_info, err = build_pools(counts)
    if err: return None, None, err
    if not pools and not de_divs:
        return None, None, 'No valid pools or brackets could be formed.'

    # ── Step 1: Plan DE divisions (bracket + primary courts, no scheduling yet) ──
    all_matches   = []
    courts_obj    = Courts()
    de_end_times  = {}
    de_courts_all = []
    de_plans      = {}   # lvl -> (bracket, primary_courts)

    for lvl, teams in de_divs.items():
        bracket, n_courts = schedule_de_division_plan(lvl, teams)
        primary = []
        for c in range(1, NUM_COURTS+1):
            if c not in de_courts_all:
                primary.append(c)
                if len(primary) == n_courts: break
        if len(primary) < n_courts:
            return None, None, f'Not enough courts to run {lvl} double elimination.'
        de_courts_all.extend(primary)
        de_plans[lvl] = (bracket, primary)
        # Block primary DE courts so pool/bracket scheduling never touches them
        for c in primary:
            courts_obj.free_at[c] = DAY_AVAIL + 999

    # ── Step 2: Schedule pool play on non-DE courts ───────────────────────────
    pool_matches, courts_after, level_end = (
        schedule_pool_play(pools, courts=courts_obj, reserved_courts=de_courts_all)
        if pools else ([], courts_obj, {})
    )

    if pool_matches:
        gaps = check_pool_gaps(pool_matches, pools)
        if gaps:
            details=[f"{lvl} Pool {pid} (gap={g} slots)" for (lvl,pid),g in sorted(gaps)]
            return None,None,(
                "Pool gap constraint violated (max 1 idle slot between matches). "
                "Not enough courts available. Violations: "+', '.join(details)+". "
                "Reduce team counts to free up courts.")

    # Compute per-level time budgets for brackets
    time_budget = {}
    for p in pools:
        lvl = p['level']
        pool_done = level_end.get(lvl, 0)
        time_budget[lvl] = DAY_AVAIL - pool_done

    bstruct  = bracket_structure(pools, combined_info, time_budget)
    brkt     = schedule_brackets(pools, combined_info, courts_obj, level_end, bstruct)
    last_brk = max((m['end'] for m in brkt), default=0)

    warning = None
    if last_brk > DAY_AVAIL:
        # Retry with base case (top 2 per pool)
        base_bs={}
        for lvl,bsv in bstruct.items():
            np=bsv['n_pools']; ba=np*2
            if bsv.get('is_six'): base_bs[lvl]=bsv
            else:
                npi=2 if np==3 else 0; ndir=2 if np==3 else ba
                base_bs[lvl]={**bsv,'n_qual':ba,'total':ba,'n_playin':npi,'n_direct':ndir,'format':f'{ba}-team','advances_per_pool':2}
        courts_obj2=courts_after.copy()
        brkt2=schedule_brackets(pools,combined_info,courts_obj2,level_end,base_bs)
        courts_obj=courts_obj2
        last2=max((m['end'] for m in brkt2),default=0)
        brkt=brkt2; bstruct=base_bs
        warning=('Expanded bracket removed to fit 8:30 PM cutoff. Top-2-per-pool only.'
                 if last2<=DAY_AVAIL else
                 f'Tournament may exceed 8:30 PM (est {fmt(last2)}). Reduce team counts.')

    # Championship verification
    for lvl in list(bstruct.keys()):
        primary=lvl.split('+')[0]
        if not any(m['level']==primary and 'CHAMPIONSHIP' in m['label'] for m in brkt):
            bsv=bstruct[lvl]; np=bsv['n_pools']
            if np>=2:
                fb={**bsv,'n_qual':6,'total':6,'n_playin':2,'n_direct':2,'format':'6-team','advances_per_pool':2}
                bst2={k:(fb if k==lvl else v) for k,v in bstruct.items()}
                brkt3=schedule_brackets(pools,combined_info,courts_obj.copy(),level_end,bst2)
                if any(m['level']==primary and 'CHAMPIONSHIP' in m['label'] for m in brkt3):
                    brkt=brkt3; bstruct=bst2

    # ── Step 5: Schedule DE using ALL courts ─────────────────────────────────
    # DE primary courts are reset to t=0. Pool/bracket courts in courts_obj
    # carry their real free-at times, so DE picks them up the moment they free.
    for lvl, (bracket, primary) in de_plans.items():
        for c in primary:
            courts_obj.free_at[c] = 0   # unblock primary courts
        de_sched = schedule_de_parallel(bracket, courts_obj)
        de_sched = renumber_de_matches(de_sched)
        all_matches.extend(de_sched)
        de_end = max(m['end'] for m in de_sched) if de_sched else 0
        de_end_times[lvl] = de_end
        if de_end > DAY_AVAIL:
            return None, None, (f'{lvl} double elimination cannot finish by 8:30 PM '
                f'(estimated end: {fmt(de_end)}). Reduce {lvl} team count.')

    # Combine all matches
    combined = sorted(all_matches + pool_matches + brkt,
                      key=lambda x:(x['start'],x['court']))
    for m in combined:
        m['time_label']=fmt(m['start']); m['end_label']=fmt(m['end'])

    wb_obj = build_excel(pools, de_divs, combined, bstruct, combined_info, level_end, de_end_times, warning, counts)
    buf = io.BytesIO(); wb_obj.save(buf); buf.seek(0)

    final_end = max(m['end'] for m in combined) if combined else 0
    courts_start = len([m for m in combined if m['start']==0])
    summary = {
        'pools':len(pools),'de_divisions':list(de_divs.keys()),
        'pool_matches':len(pool_matches),'brkt_matches':len(brkt),
        'de_matches':len(all_matches),
        'ends':fmt(final_end),'warning':warning,'courts_730':courts_start,
        'pool_list':[(p['level'],p['pool_id'],p['size'],len(p['teams'])) for p in pools],
        'bracket_info':{lvl:dict(v) for lvl,v in bstruct.items()},
        'level_pool_end':{lvl:fmt(t) for lvl,t in level_end.items()},
    }
    return buf, summary, None


def _first_open_slot(intervals, dur, not_before=0):
    """
    Given sorted (start, end) busy intervals, find the first t >= not_before
    where 'dur' consecutive minutes are free.
    """
    t = not_before
    for (s, e) in intervals:
        if s >= t + dur:   # gap before this interval is big enough
            return t
        t = max(t, e)
    return t   # after all intervals (or = not_before if list is empty)


def schedule_pools_freed_courts(sorted_pools, court_ivs):
    """
    Schedule pool play on courts freed between DE matches.
    sorted_pools  : pools in desired priority order (longest/combined first)
    court_ivs     : {court: sorted [(start,end),...]} busy periods from DE
    Returns (pool_matches, level_end, courts_obj).
    """
    pool_matches = []; level_end = {}
    busy = {c: list(ivs) for c, ivs in court_ivs.items()}
    courts_obj = Courts()

    for p in sorted_pools:
        n = p['size']
        if n not in RR:
            continue
        rr = RR[n]; nm = len(rr)
        pool_dur = nm * POOL_DUR

        # Find the court whose gap gives the earliest start for this full pool
        best_start, best_court = DAY_AVAIL + 1, 0
        for c in range(1, NUM_COURTS + 1):
            s = _first_open_slot(busy[c], pool_dur)
            if s < best_start:
                best_start, best_court = s, c

        if best_court == 0 or best_start + pool_dur > DAY_AVAIL:
            continue   # pool won't fit — skip

        # Schedule all matches for this pool sequentially on best_court
        for i, (ai, bi, wi) in enumerate(rr):
            t = best_start + i * POOL_DUR
            pool_matches.append({
                'start': t, 'end': t + POOL_DUR, 'court': best_court,
                'level': p['level'], 'pool_id': p['pool_id'], 'round': i + 1,
                'label': f"{p['level']} Pool {p['pool_id']} - Match {i+1}",
                'team_a': p['teams'][ai-1], 'team_b': p['teams'][bi-1],
                'team_work': p['teams'][wi-1],
                'note': '', 'phase': 'POOL PLAY', 'is_pool': True,
                'is_de': False, 'is_playin': False,
            })

        pool_end = best_start + pool_dur
        busy[best_court].append((best_start, pool_end))
        busy[best_court].sort()
        courts_obj.book(best_court, best_start, pool_dur)
        level_end[p['level']] = max(level_end.get(p['level'], 0), pool_end)

    return pool_matches, level_end, courts_obj


def generate_bigde_mw_schedule(wb, wbb, wa, wopen, mb, mbb, ma, mopen):
    """
    M/W scheduler for a large Men's BB field that cannot fit in pool play.

    Men's BB runs as full double-elimination on all 9 courts from 7:20 AM.
      - First 3 round-depths  →  DE_DUR     (40 min/match)
      - Subsequent rounds     →  DE_SHORT_DUR (30 min/match)

    All other divisions schedule on courts freed as the BB DE bracket narrows:
      - W_BB+A combined pools get first priority (need multiple courts)
      - Then M_A, M_B (longest single pools)
      - Then M_Open, W_BB+A size-4 pool, W_B

    Target: major divisions (W_BB+A, M_A, M_B) all start by 10:00 AM.
    """
    if mbb < 1:
        return generate_mw_schedule(wb, wbb, wa, wopen, mb, mbb, ma, mopen)

    # ── 1. Build & schedule Men's BB DE on all 9 courts ──────────────────
    bb_teams = [f'M_BB Seed {i+1}' for i in range(mbb)]
    bb_bracket = build_de_bracket('M_BB', bb_teams)
    courts_de = Courts()
    bb_sched = schedule_de_parallel(bb_bracket, courts_de)
    bb_sched = renumber_de_matches(bb_sched)
    de_end = max(m['end'] for m in bb_sched) if bb_sched else 0
    if de_end > DAY_AVAIL:
        return None, None, (f'M_BB double elimination cannot finish by 8:30 PM '
                            f'(est. {fmt(de_end)}). Reduce M_BB team count.')

    # ── 2. Per-court busy intervals from DE ───────────────────────────────
    court_ivs = {c: [] for c in range(1, NUM_COURTS + 1)}
    for m in bb_sched:
        court_ivs[m['court']].append((m['start'], m['end']))
    for c in court_ivs:
        court_ivs[c].sort()

    # ── 3. Build pool definitions for every other division ────────────────
    w_pools_raw, w_de_raw, w_ci_raw, err = build_pools(
        {'B': wb, 'BB': wbb, 'A': wa, 'Open': wopen}, combine_open=False)
    if err:
        return None, None, f"Women's: {err}"
    m_pools_raw, m_de_raw, m_ci_raw, err = build_pools(
        {'B': mb, 'BB': 0, 'A': ma, 'Open': mopen})
    if err:
        return None, None, f"Men's (excl. BB): {err}"

    w_pools, _, w_ci = add_gender_prefix(w_pools_raw, w_de_raw, w_ci_raw, 'W_')
    m_pools, _, m_ci = add_gender_prefix(m_pools_raw, m_de_raw, m_ci_raw, 'M_')
    all_pools = w_pools + m_pools
    all_ci    = {**w_ci, **m_ci}

    # ── 4. Priority-sort pools then schedule on freed courts ──────────────
    # Combined multi-pool levels (W_BB+A) → priority 0
    # Single large pools (M_A, M_B)       → priority 1
    # Everything else by duration desc
    def _pp(p):
        dur = len(RR.get(p['size'], [])) * POOL_DUR
        return (0 if '+' in p['level'] else 1, -dur, p['level'])
    sorted_pools = sorted(all_pools, key=_pp)
    pool_matches, level_end, courts_pool = schedule_pools_freed_courts(
        sorted_pools, court_ivs)

    # ── 5. 10 AM check ────────────────────────────────────────────────────
    TEN_AM = 160   # minutes from 7:20 AM = 10:00 AM
    late_keys = {}
    for m in pool_matches:
        if m['round'] == 1 and m['start'] > TEN_AM:
            key = (m['level'], m['pool_id'])
            if key not in late_keys:
                late_keys[key] = fmt(m['start'])
    warning = None
    if late_keys:
        parts = [f"{l} P{p} ({t})" for (l, p), t in list(late_keys.items())[:6]]
        warning = "Late start (>10 AM): " + ", ".join(parts)

    # ── 6. Courts object for bracket scheduling ───────────────────────────
    courts_brkt = Courts()
    for m in pool_matches:
        courts_brkt.book(m['court'], m['start'], POOL_DUR)
    for m in bb_sched:
        courts_brkt.book(m['court'], m['start'], m['end'] - m['start'])

    # ── 7. Schedule brackets ──────────────────────────────────────────────
    def _run_brkt(pools_raw, ci_raw, pfx, le_all):
        le   = {k[len(pfx):]: v for k, v in le_all.items() if k.startswith(pfx)}
        tb   = {k: DAY_AVAIL - v for k, v in le.items()}
        bst  = bracket_structure(pools_raw, ci_raw, tb)
        snap = courts_brkt.copy()
        brkt = schedule_brackets(pools_raw, ci_raw, snap, le, bst)
        last = max((m['end'] for m in brkt), default=0)
        if last > DAY_AVAIL:
            base = {}
            for lvl, bsv in bst.items():
                np = bsv['n_pools']
                if bsv.get('is_six'):
                    base[lvl] = bsv
                else:
                    ba = np*2; npi = 2 if np==3 else 0; ndir = 2 if np==3 else ba
                    base[lvl] = {**bsv, 'n_qual':ba, 'total':ba, 'n_playin':npi,
                                 'n_direct':ndir, 'format':f'{ba}-team', 'advances_per_pool':2}
            snap2 = courts_brkt.copy()
            brkt2 = schedule_brackets(pools_raw, ci_raw, snap2, le, base)
            if max((m['end'] for m in brkt2), default=0) <= last:
                brkt, bst = brkt2, base
        for m in brkt:
            m['level'] = pfx + m['level']
            m['label'] = pfx + m['label']
        return brkt, {pfx+k: v for k, v in bst.items()}

    w_brkt, w_bst = _run_brkt(w_pools_raw, w_ci_raw, 'W_', level_end)
    m_brkt, m_bst = _run_brkt(m_pools_raw, m_ci_raw, 'M_', level_end)
    brkt   = w_brkt + m_brkt
    bstruct = {**w_bst, **m_bst}

    # ── 8. Combine, label, build Excel ────────────────────────────────────
    all_matches = sorted(bb_sched + pool_matches + brkt,
                         key=lambda x: (x['start'], x['court']))
    for m in all_matches:
        m['time_label'] = fmt(m['start'])
        m['end_label']  = fmt(m['end'])
    final_end = max(m['end'] for m in all_matches) if all_matches else 0
    if final_end > DAY_AVAIL:
        msg = f'Schedule may exceed 8:30 PM (est. {fmt(final_end)}).'
        warning = (warning + ' · ' + msg) if warning else msg

    counts_mw = {'W_B':wb,'W_BB':wbb,'W_A':wa,'W_Open':wopen,
                 'M_B':mb,'M_BB':mbb,'M_A':ma,'M_Open':mopen}
    de_end_times = {'M_BB': de_end}

    wb_obj = build_excel(all_pools, {'M_BB': bb_teams}, all_matches, bstruct, all_ci,
                         level_end, de_end_times, warning, counts_mw,
                         title="MEN'S/WOMEN'S  ·  BIG DE MODE",
                         stagger_offsets={})
    buf = io.BytesIO(); wb_obj.save(buf); buf.seek(0)
    return buf, {
        'pools':        len(all_pools),
        'de_divisions': ['M_BB'],
        'pool_matches': len(pool_matches),
        'brkt_matches': len(brkt),
        'de_matches':   len(bb_sched),
        'ends':         fmt(final_end),
        'de_ends':      fmt(de_end),
        'stagger':      {},
    }, None


def generate_mw_schedule(wb, wbb, wa, wopen, mb, mbb, ma, mopen):
    w_pools_raw, w_de_raw, w_ci_raw, err = build_pools({'B':wb,'BB':wbb,'A':wa,'Open':wopen}, combine_open=False)
    if err: return None, None, f"Women's: {err}"
    m_pools_raw, m_de_raw, m_ci_raw, err = build_pools({'B':mb,'BB':mbb,'A':ma,'Open':mopen}, combine_open=False)
    if err: return None, None, f"Men's: {err}"
    w_pools, w_de, w_ci = add_gender_prefix(w_pools_raw, w_de_raw, w_ci_raw, 'W_')
    m_pools, m_de, m_ci = add_gender_prefix(m_pools_raw, m_de_raw, m_ci_raw, 'M_')
    all_pools = w_pools + m_pools
    all_de    = {**w_de, **m_de}
    all_ci    = {**w_ci, **m_ci}
    if not all_pools and not all_de:
        return None, None, 'No valid pools or brackets could be formed.'

    # Combined-court overflow check: each gender's build_pools only sees its own 4
    # divisions. If together they exceed 9 simultaneous courts, apply DE to the largest
    # pool divisions from either gender until the combined count fits.
    def _pool_court_cost(p): return 3 if p.get('is_six') else 1
    n_mw_de_cts = sum(schedule_de_division_plan(lvl, teams)[1]
                      for lvl, teams in all_de.items())  # courts already locked by gender DE
    for _overflow_guard in range(len(LEVELS)*2 + 4):
        total_pc = sum(_pool_court_cost(p) for p in all_pools)
        if total_pc <= NUM_COURTS - n_mw_de_cts:
            break
        by_lvl = {}
        for p in all_pools: by_lvl.setdefault(p['level'], []).append(p)
        if not by_lvl:
            return None, None, 'Cannot fit all 8 divisions in 9 courts.'
        big_lvl = max(by_lvl, key=lambda l: sum(p['size'] for p in by_lvl[l]))
        big_teams = [t for p in by_lvl[big_lvl] for t in p['teams']]
        all_de[big_lvl] = big_teams
        all_pools = [p for p in all_pools if p['level'] != big_lvl]
        all_ci = {k: v for k, v in all_ci.items() if big_lvl not in k.split('+')}
        _, de_cts = schedule_de_division_plan(big_lvl, big_teams)
        n_mw_de_cts += de_cts
        if n_mw_de_cts >= NUM_COURTS:
            return None, None, 'Cannot fit all divisions even with double elimination.'
    else:
        return None, None, 'Too many teams: cannot reduce to ≤9 simultaneous pool courts.'

    all_matches=[]; courts_obj=Courts(); de_plans={}; de_courts_all=[]; de_end_times={}
    for lvl, teams in all_de.items():
        bracket, n_courts = schedule_de_division_plan(lvl, teams)
        primary=[]
        for c in range(1, NUM_COURTS+1):
            if c not in de_courts_all:
                primary.append(c)
                if len(primary)==n_courts: break
        if len(primary)<n_courts:
            return None, None, f'Not enough courts for {lvl} double elimination.'
        de_courts_all.extend(primary)
        de_plans[lvl]=(bracket, primary)
        for c in primary: courts_obj.free_at[c]=DAY_AVAIL+999
    stagger_offsets, err = compute_stagger_offsets(all_pools, len(de_courts_all))
    if err: return None, None, err
    stagger_offsets = stagger_offsets or {}
    pool_matches, courts_after, level_end = (
        schedule_pool_play(all_pools, courts=courts_obj, reserved_courts=de_courts_all,
                           start_offsets=stagger_offsets)
        if all_pools else ([], courts_obj, {})
    )
    if pool_matches:
        gaps = check_pool_gaps(pool_matches, all_pools)
        if gaps:
            details=[f"{l} Pool {p} (gap={g})" for (l,p),g in sorted(gaps)]
            return None, None, "Pool gap violated: "+', '.join(details)
    def _glend(pfx): return {k[len(pfx):]:v for k,v in level_end.items() if k.startswith(pfx)}
    def _gtb(pfx):   return {k[len(pfx):]:DAY_AVAIL-level_end.get(k,0) for k in level_end if k.startswith(pfx)}
    def _run_brackets(pr, cr, pfx, le, tb):
        bst=bracket_structure(pr, cr, tb)
        brkt=schedule_brackets(pr, cr, courts_obj, le, bst)
        last=max((m['end'] for m in brkt),default=0)
        warn=None
        if last>DAY_AVAIL:
            base_bs={}
            for lvl,bsv in bst.items():
                np=bsv['n_pools']; ba=np*2
                if bsv.get('is_six'): base_bs[lvl]=bsv
                else:
                    npi=2 if np==3 else 0; ndir=2 if np==3 else ba
                    base_bs[lvl]={**bsv,'n_qual':ba,'total':ba,'n_playin':npi,'n_direct':ndir,'format':f'{ba}-team','advances_per_pool':2}
            snap=courts_after.copy()
            for c in range(1,NUM_COURTS+1): snap.free_at[c]=max(snap.free_at[c],courts_obj.free_at[c])
            brkt2=schedule_brackets(pr, cr, snap, le, base_bs)
            if max((m['end'] for m in brkt2),default=0)<=last: brkt,bst=brkt2,base_bs
            warn=f'{pfx[:-1]} brackets may exceed 8:30 PM.'
        for lvl in list(bst.keys()):
            prim=lvl.split('+')[0]
            if not any(m['level']==prim and 'CHAMPIONSHIP' in m['label'] for m in brkt):
                bsv=bst[lvl]; np=bsv['n_pools']
                if np>=2:
                    fb={**bsv,'n_qual':6,'total':6,'n_playin':2,'n_direct':2,'format':'6-team','advances_per_pool':2}
                    bst2={k:(fb if k==lvl else v) for k,v in bst.items()}
                    brkt3=schedule_brackets(pr,cr,courts_obj.copy(),le,bst2)
                    if any(m['level']==prim and 'CHAMPIONSHIP' in m['label'] for m in brkt3):
                        brkt,bst=brkt3,bst2
        for m in brkt: m['level']=pfx+m['level']; m['label']=pfx+m['label']
        return brkt, {pfx+k:v for k,v in bst.items()}, warn
    w_brkt,w_bst,w_warn=_run_brackets(w_pools_raw,w_ci_raw,'W_',_glend('W_'),_gtb('W_'))
    m_brkt,m_bst,m_warn=_run_brackets(m_pools_raw,m_ci_raw,'M_',_glend('M_'),_gtb('M_'))
    brkt=w_brkt+m_brkt; bstruct={**w_bst,**m_bst}
    warning='; '.join(x for x in [w_warn,m_warn] if x) or None
    for lvl,(bracket,primary) in de_plans.items():
        for c in primary: courts_obj.free_at[c]=0
        de_sched=schedule_de_parallel(bracket, courts_obj)
        de_sched=renumber_de_matches(de_sched)
        all_matches.extend(de_sched)
        de_end=max(m['end'] for m in de_sched) if de_sched else 0
        de_end_times[lvl]=de_end
        if de_end>DAY_AVAIL:
            return None,None,(f'{lvl} DE cannot finish by 8:30 PM (est {fmt(de_end)}).')
    combined=sorted(all_matches+pool_matches+brkt,key=lambda x:(x['start'],x['court']))
    for m in combined: m['time_label']=fmt(m['start']); m['end_label']=fmt(m['end'])
    counts_mw={'W_B':wb,'W_BB':wbb,'W_A':wa,'W_Open':wopen,'M_B':mb,'M_BB':mbb,'M_A':ma,'M_Open':mopen}
    wb_obj=build_excel(all_pools,all_de,combined,bstruct,all_ci,level_end,de_end_times,
                       warning,counts_mw,title="MEN'S / WOMEN'S TOURNAMENT",
                       stagger_offsets=stagger_offsets)
    buf=io.BytesIO(); wb_obj.save(buf); buf.seek(0)
    final_end=max(m['end'] for m in combined) if combined else 0
    return buf, {
        'pools':len(all_pools),'de_divisions':list(all_de.keys()),
        'pool_matches':len(pool_matches),'brkt_matches':len(brkt),
        'de_matches':len(all_matches),'ends':fmt(final_end),
        'stagger':{l:fmt(t) for l,t in stagger_offsets.items() if t>0},
    }, None

