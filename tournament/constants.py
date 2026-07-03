"""Tournament-wide constants and round-robin templates."""

# ── Constants ──────────────────────────────────────────────────────────────────
NUM_COURTS    = 9
POOL_DUR      = 45
BRKT_DUR      = 60
DE_DUR        = 40          # DE intro-round match duration (first 3 depths)
DE_SHORT_DUR  = 30          # DE subsequent-round match duration
DE_THRESHOLD  = 15          # divisions with >15 teams use double elimination
START_MIN     = 7*60+20     # 7:20 AM
END_MIN       = 20*60+30    # 8:30 PM
DAY_AVAIL     = END_MIN - START_MIN
LEVELS        = ['B','BB','A','Open']

# ── RR templates ───────────────────────────────────────────────────────────────
RR3 = [(1,2,3),(1,3,2),(2,3,1)]
RR4 = [(1,2,3),(3,4,2),(1,3,4),(2,4,1),(2,3,4),(1,4,2)]
RR5 = [(1,2,3),(1,3,2),(2,3,1),(1,4,2),(1,5,3),(2,4,5),(2,5,4),(3,4,5),(3,5,4),(4,5,1)]
RR  = {3:RR3, 4:RR4, 5:RR5}

RR6_ROUNDS = [
    [(1,2),(3,4),(5,6)],
    [(1,3),(2,5),(4,6)],
    [(1,4),(2,6),(3,5)],
    [(1,5),(2,4),(3,6)],
]
