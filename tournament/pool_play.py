"""Pool-play scheduling, staggered starts, and gap checks."""
from collections import defaultdict

from .constants import NUM_COURTS, POOL_DUR, DAY_AVAIL, RR, RR6_ROUNDS
from .courts import Courts
from .utils import base_level


def _stagger_ok(start_slots, level_info, available):
    if not start_slots: return True
    max_t = max(s + level_info.get(l,{}).get('max_slots',0) for l,s in start_slots.items() if l in level_info)
    for t in range(int(max_t)+1):
        active = sum(level_info[l]['n_pools'] for l,s in start_slots.items()
                     if l in level_info and s <= t < s+level_info[l]['max_slots'])
        if active > available: return False
    return True


def compute_stagger_offsets(pools, n_de_courts):
    """Greedily assign start slots (0=7:20,1=8:05,2=8:50) to each level.
    Largest pool counts start first; all must start by 10:00 AM (slot 3 max)."""
    available = NUM_COURTS - n_de_courts
    level_info = {}
    for p in pools:
        lvl = p['level']; n = len(p['teams']); is_six = p.get('is_six', False)
        if lvl not in level_info: level_info[lvl] = {'n_pools':0,'max_slots':0}
        # Six-pools need 3 courts simultaneously; regular pools need 1
        level_info[lvl]['n_pools'] += 3 if is_six else 1
        level_info[lvl]['max_slots'] = max(level_info[lvl]['max_slots'],
            len(RR6_ROUNDS) if is_six else n*(n-1)//2)
    sorted_levels = sorted(level_info, key=lambda l:(-level_info[l]['n_pools'], l))
    start_slots = {}
    for lvl in sorted_levels:
        for s in range(4):  # 0=7:20, 1=8:05, 2=8:50, 3=9:35 (all before 10:00 AM)
            if _stagger_ok({**start_slots, lvl:s}, level_info, available):
                start_slots[lvl] = s; break
        else:
            start_slots[lvl] = 3  # forced to latest slot
    if not _stagger_ok(start_slots, level_info, available):
        return None, ('Cannot schedule all divisions within 9 courts and start by 10:00 AM. '
                      'Reduce team counts or allow double elimination for large divisions.')
    return {lvl: s*POOL_DUR for lvl,s in start_slots.items()}, None


def add_gender_prefix(pools, de_divs, combined_info, prefix):
    """Add 'W_' or 'M_' prefix to all level names and team names."""
    p2=[]
    for p in pools:
        pp=dict(p)
        pp['level']=prefix+p['level']; pp['pool_id']=prefix+str(p['pool_id'])
        pp['teams']=[prefix+t for t in p['teams']]
        if 'origin' in pp: pp['origin']={prefix+t:prefix+g for t,g in p['origin'].items()}
        p2.append(pp)
    de2={prefix+k:[prefix+t for t in v] for k,v in de_divs.items()}
    ci2={'+'.join(prefix+x for x in k.split('+')):{prefix+t:prefix+g for t,g in v.items()}
         for k,v in combined_info.items()}
    return p2, de2, ci2


def _assign_courts_staggered(pools, reserved, start_offsets):
    """Dynamic court assignment for staggered starts: pools that don't overlap share courts."""
    avail=[c for c in range(1,NUM_COURTS+1) if c not in reserved]
    ct_free={c:0 for c in avail}; home={}
    for p in sorted(pools, key=lambda p:(start_offsets.get(p['level'],0),p['level'])):
        start=start_offsets.get(p['level'],0); n=len(p['teams'])
        end=start+n*(n-1)//2*POOL_DUR
        assigned=False
        for c in avail:
            if ct_free[c]<=start:
                home[id(p)]=c; ct_free[c]=end; assigned=True; break
        if not assigned: home[id(p)]=0  # float fallback
    return home


def schedule_pool_play(pools, courts=None, reserved_courts=None, start_offsets=None):
    if courts is None:
        courts = Courts()
    reserved = set(reserved_courts or [])
    home     = {}
    six_pools     = [p for p in pools if p['is_six']]
    regular_pools = [p for p in pools if not p['is_six']]
    # Reserve 3 courts per pool-of-6, from the high end
    n_six_courts = len(six_pools) * 3
    six_reserved = [c for c in range(NUM_COURTS, 0, -1) if c not in reserved][:n_six_courts]
    reserved = reserved | set(six_reserved)
    n_reg = len(regular_pools)
    if start_offsets:
        # Dynamic assignment: pools with non-overlapping windows share courts
        n_float=0; float_reg=set()
        home=_assign_courts_staggered(regular_pools, reserved, start_offsets)
    else:
        avail_reg = NUM_COURTS - len(reserved)
        n_float   = max(0, n_reg - avail_reg)
        if n_float:
            b_idxs=[i for i,p in enumerate(regular_pools) if base_level(p['level']).startswith('B')]
            float_reg=set(b_idxs[-n_float:]) if len(b_idxs)>=n_float else set(range(n_reg-n_float, n_reg))
        else:
            float_reg=set()
        # Assign courts HIGH→LOW so B-level pools land on the highest court numbers
        court_num=NUM_COURTS
        for i,p in enumerate(regular_pools):
            if i in float_reg: home[id(p)]=0
            else:
                while court_num in reserved: court_num-=1
                home[id(p)]=court_num; court_num-=1

    home_list  = [i for i in range(n_reg) if i not in float_reg]
    float_list = [i for i in range(n_reg) if i in float_reg]
    reservation={}; home_yield={}
    for seq,fi in enumerate(float_list):
        hi=home_list[seq]; pc=home[id(regular_pools[hi])]
        reservation[fi]=[(0,pc)]; home_yield[hi]={0}; courts.soft_book(pc,0)

    matches = []

    # Pool of 6: each gets its own 3 dedicated courts (use the courts we pre-reserved for them)
    # six_reserved is the list of courts reserved for six-pools (in descending order)
    six_court_sets = []
    temp = list(six_reserved)  # e.g. [9,8,7,6,5,4] for 2 six-pools
    for _ in six_pools:
        grp = sorted(temp[:3])   # take 3, sort ascending for court order
        temp = temp[3:]
        six_court_sets.append(grp)

    for p, p_six_courts in zip(six_pools, six_court_sets):
        _p6start=(start_offsets or {}).get(p['level'],0)
        for ri,games in enumerate(RR6_ROUNDS):
            t = _p6start + ri*POOL_DUR
            for gi,(ta_i,tb_i) in enumerate(games):
                ct=p_six_courts[gi]; courts.book(ct,t,POOL_DUR)
                matches.append({'start':t,'end':t+POOL_DUR,'court':ct,
                    'level':p['level'],'pool_id':p['pool_id'],'round':ri+1,
                    'label':f"{p['level']} Pool {p['pool_id']} - R{ri+1} G{gi+1}",
                    'team_a':p['teams'][ta_i-1],'team_b':p['teams'][tb_i-1],
                    'team_work':'(all playing)','note':'','phase':'POOL PLAY','is_pool':True})

    ordered = home_list + float_list
    for p_idx in ordered:
        p=regular_pools[p_idx]; hc=home[id(p)]; is_float=(hc==0); nm=p['matches']
        if is_float:
            reserved=reservation.get(p_idx,[]); round_num=0
            for (slot,ct) in reserved:
                if round_num>=nm: break
                t=slot*POOL_DUR
                courts.soft_slots[ct].discard(slot); courts.book(ct,t,POOL_DUR)
                _add(matches,p,p_idx,round_num,t,ct); round_num+=1
            last_slot=reserved[-1][0] if reserved and round_num>0 else -1
            while round_num<nm:
                t,c=courts.earliest(not_before=(last_slot+1)*POOL_DUR,duration=POOL_DUR)
                if c==0: break
                courts.book(c,t,POOL_DUR); last_slot=t//POOL_DUR
                _add(matches,p,p_idx,round_num,t,c); round_num+=1
        else:
            _sl0=((start_offsets or {}).get(p['level'],0)//POOL_DUR)
            skip=home_yield.get(p_idx,set()); round_num=0; slot=_sl0
            while round_num<nm:
                if slot in skip: slot+=1; continue
                if not courts.is_free(hc,slot):
                    ns=slot+1
                    while ns in skip or not courts.is_free(hc,ns):
                        if not courts.is_free(hc,ns) and ns not in skip:
                            ns=max(ns+1,(courts.free_at[hc]+POOL_DUR-1)//POOL_DUR)
                        else: ns+=1
                    slot=ns; continue
                t=slot*POOL_DUR
                if t+POOL_DUR>DAY_AVAIL: break
                courts.book(hc,t,POOL_DUR); _add(matches,p,p_idx,round_num,t,hc)
                round_num+=1; slot+=1

    level_end={}
    for m in matches:
        level_end[m['level']]=max(level_end.get(m['level'],0),m['end'])
    return matches, courts, level_end


def _add(matches,p,p_idx,round_num,t,c):
    rn=round_num+1; ai,bi,wi=RR[p['size']][rn-1]
    ta,tb,tw=p['teams'][ai-1],p['teams'][bi-1],p['teams'][wi-1]
    matches.append({'start':t,'end':t+POOL_DUR,'court':c,'level':p['level'],
        'pool_id':p['pool_id'],'round':rn,'label':f"{p['level']} Pool {p['pool_id']} - Match {rn}",
        'team_a':ta,'team_b':tb,'team_work':tw,'note':'','phase':'POOL PLAY','is_pool':True})


def check_pool_gaps(matches, pools):
    pool_slots = defaultdict(list)
    for m in matches:
        if m['is_pool']:
            key=(m['level'],m['pool_id'])
            sl=m['start']//POOL_DUR
            if sl not in pool_slots[key]: pool_slots[key].append(sl)
    violations=[]
    for key,slots in pool_slots.items():
        slots=sorted(set(slots))
        if len(slots)<2: continue
        max_gap=max(slots[i+1]-slots[i]-1 for i in range(len(slots)-1))
        if max_gap>1: violations.append((key,max_gap))
    return violations
