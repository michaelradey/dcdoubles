"""Single-elimination bracket structure and scheduling."""
from .constants import BRKT_DUR
from .utils import base_level


def bracket_structure(pools, combined_info, time_budget_per_level):
    """Returns bracket info per level. Handles combined A+Open pools."""
    result={}
    # Determine effective levels from pools
    pool_levels = list(dict.fromkeys(p['level'] for p in pools))

    for eff_lvl in pool_levels:
        lp = [p for p in pools if p['level']==eff_lvl]
        n_pools=len(lp); budget=time_budget_per_level.get(eff_lvl,9999)
        is_six=(n_pools==1 and lp[0]['is_six'])

        if is_six:
            result[eff_lvl]={'n_pools':1,'n_qual':4,'advances_per_pool':4,
                             'n_playin':0,'n_direct':4,'format':'4-team','total':4,'is_six':True}
            continue

        base_adv=n_pools*2; base_rounds=2 if n_pools==2 else 3
        exp_adv=n_pools*3;  exp_rounds=3 if n_pools==2 else 4

        if exp_rounds*BRKT_DUR<=budget: adv,rounds,adv_pp=exp_adv,exp_rounds,3
        else:                            adv,rounds,adv_pp=base_adv,base_rounds,2

        if adv<=4:    n_pi=0; n_dir=adv
        elif adv==6:  n_pi=2; n_dir=2
        elif adv==8:  n_pi=0; n_dir=8
        elif adv==9:  n_pi=1; n_dir=7
        elif adv==12: n_pi=4; n_dir=4
        else:         n_pi=max(0,adv-8); n_dir=adv-n_pi

        result[eff_lvl]={'n_pools':n_pools,'n_qual':adv,'advances_per_pool':adv_pp,
                         'n_playin':n_pi,'n_direct':n_dir,'format':f'{adv}-team',
                         'total':adv,'is_six':False}
    return result


# ── Bracket scheduling ─────────────────────────────────────────────────────────
def schedule_brackets(pools, combined_info, courts, level_end, bstruct):
    matches=[]
    for eff_lvl in list(dict.fromkeys(p['level'] for p in pools)):
        bs=bstruct.get(eff_lvl)
        if not bs: continue
        n_dir=bs['n_direct']; n_pi=bs['n_playin']; total=bs['total']
        pool_done=level_end.get(eff_lvl,0)

        # Determine if this is a combined level and which sub-brackets to create
        is_combined = base_level(eff_lvl).startswith('A+')
        sub_levels = eff_lvl.split('+') if is_combined else [eff_lvl]
        primary_lvl = sub_levels[0]   # 'A'

        def book_next(nb, dur=BRKT_DUR):
            t,c=courts.earliest(not_before=nb,duration=dur)
            if c: courts.book(c,t,dur)
            return t,c

        def add(t,c,lbl,ta,tb,note='',phase='BRACKET PLAY',is_pi=False,lvl_override=None):
            lv=lvl_override or primary_lvl
            matches.append({'start':t,'end':t+BRKT_DUR,'court':c,'level':lv,'label':lbl,
                'team_a':ta,'team_b':tb,'team_work':'Teams will ref internally',
                'note':note,'phase':phase,'is_pool':False,'is_playin':is_pi,'is_de':False})

        def s(n): return f'{primary_lvl} Seed {n}' if n<=n_dir else f'{primary_lvl} Play-In {n-n_dir} Winner'

        is_open_primary = (base_level(primary_lvl)=='Open')
        cn = 'Open team ineligible if 2+ losses vs A in pool play' if is_open_primary else ''

        pi_done=pool_done
        if n_pi==1:
            t,c=book_next(pool_done)
            if c: pi_done=max(pi_done,t+BRKT_DUR); add(t,c,f'{primary_lvl} PLAY-IN 1',s(8),f'{primary_lvl} Seed 9',phase='PLAY-IN',is_pi=True)
        elif n_pi==2:
            for i,(sa,sb) in enumerate([(3,6),(4,5)],1):
                t,c=book_next(pool_done)
                if c: pi_done=max(pi_done,t+BRKT_DUR); add(t,c,f'{primary_lvl} PLAY-IN {i}',f'{primary_lvl} Seed {sa}',f'{primary_lvl} Seed {sb}',phase='PLAY-IN',is_pi=True)
        elif n_pi==4:
            for i,(sa,sb) in enumerate([(5,12),(6,11),(7,10),(8,9)],1):
                t,c=book_next(pool_done)
                if c: pi_done=max(pi_done,t+BRKT_DUR); add(t,c,f'{primary_lvl} PLAY-IN {i}',f'{primary_lvl} Seed {sa}',f'{primary_lvl} Seed {sb}',phase='PLAY-IN',is_pi=True)

        bs_=pi_done
        if total<=4 and n_pi==0:
            sf_done=bs_
            for si,(ta,tb) in enumerate([(s(1),s(4)),(s(2),s(3))],1):
                t,c=book_next(bs_)
                if c: sf_done=max(sf_done,t+BRKT_DUR); add(t,c,f'{primary_lvl} SEMI {si}',ta,tb)
            t,c=book_next(sf_done)
            if c: add(t,c,f'{primary_lvl} CHAMPIONSHIP',f'{primary_lvl} Semi 1 Winner',f'{primary_lvl} Semi 2 Winner',note=cn)
        elif total==6:
            sf_done=bs_
            for si,(top,pi) in enumerate([(1,2),(2,1)],1):
                t,c=book_next(bs_)
                if c: sf_done=max(sf_done,t+BRKT_DUR); add(t,c,f'{primary_lvl} SEMI {si}',f'{primary_lvl} Seed {top}',f'{primary_lvl} Play-In {pi} Winner')
            t,c=book_next(sf_done)
            if c: add(t,c,f'{primary_lvl} CHAMPIONSHIP',f'{primary_lvl} Semi 1 Winner',f'{primary_lvl} Semi 2 Winner',note=cn)
        elif total in (8,9):
            qf_p=[(s(1),s(8),1),(s(4),s(5),2),(s(3),s(6),3),(s(2),s(7),4)]
            qf_done=bs_
            for ta,tb,qi in qf_p:
                t,c=book_next(bs_)
                if c: qf_done=max(qf_done,t+BRKT_DUR); add(t,c,f'{primary_lvl} QF {qi}',ta,tb)
            sf_done=qf_done
            for si,(ta,tb) in enumerate([('QF1 Winner','QF2 Winner'),('QF3 Winner','QF4 Winner')],1):
                t,c=book_next(qf_done)
                if c: sf_done=max(sf_done,t+BRKT_DUR); add(t,c,f'{primary_lvl} SEMI {si}',ta,tb)
            t,c=book_next(sf_done)
            if c: add(t,c,f'{primary_lvl} CHAMPIONSHIP',f'{primary_lvl} Semi 1 Winner',f'{primary_lvl} Semi 2 Winner',note=cn)
        elif total==12:
            qf_p=[(f'{primary_lvl} Seed 1',f'{primary_lvl} Play-In 4 Winner',1),
                  (f'{primary_lvl} Seed 4',f'{primary_lvl} Play-In 1 Winner',2),
                  (f'{primary_lvl} Seed 3',f'{primary_lvl} Play-In 2 Winner',3),
                  (f'{primary_lvl} Seed 2',f'{primary_lvl} Play-In 3 Winner',4)]
            qf_done=bs_
            for ta,tb,qi in qf_p:
                t,c=book_next(bs_)
                if c: qf_done=max(qf_done,t+BRKT_DUR); add(t,c,f'{primary_lvl} QF {qi}',ta,tb)
            sf_done=qf_done
            for si,(ta,tb) in enumerate([('QF1 Winner','QF2 Winner'),('QF3 Winner','QF4 Winner')],1):
                t,c=book_next(qf_done)
                if c: sf_done=max(sf_done,t+BRKT_DUR); add(t,c,f'{primary_lvl} SEMI {si}',ta,tb)
            t,c=book_next(sf_done)
            if c: add(t,c,f'{primary_lvl} CHAMPIONSHIP',f'{primary_lvl} Semi 1 Winner',f'{primary_lvl} Semi 2 Winner',note=cn)

        # For combined level (e.g. A+Open): also schedule the secondary bracket
        if is_combined and len(sub_levels) > 1:
            sec_lvl = sub_levels[1]  # 'Open'
            # Estimate 2 Open qualifiers (or however many eligible)
            # Schedule Open bracket using the already-known pool_done time
            # Simple: find Open teams in combined pools and give them 1 match (the final)
            t,c=book_next(pool_done)
            is_open_sec=(sec_lvl=='Open')
            if c:
                add(t,c,f'{sec_lvl} CHAMPIONSHIP',
                    f'{sec_lvl} Pool Qualifier 1',f'{sec_lvl} Pool Qualifier 2',
                    note='Open eligibility rules apply - see Open Eligibility tab',
                    lvl_override=sec_lvl)

    return matches
