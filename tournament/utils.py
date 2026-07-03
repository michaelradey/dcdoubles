"""Small shared helpers: time formatting and level-name normalization."""
from datetime import datetime

from .constants import START_MIN


def fmt(offset_min):
    total = START_MIN + int(offset_min)
    return datetime(2000,1,1,total//60,total%60).strftime('%I:%M %p').lstrip('0')


def base_level(lvl):
    """Strip gender prefix: 'W_BB'→'BB', 'M_A+M_Open'→'A+Open'. Safe on unprefixed names."""
    return '+'.join(p.split('_',1)[-1] for p in lvl.split('+'))
