"""Court availability allocator."""
from collections import defaultdict

from .constants import NUM_COURTS, DAY_AVAIL, POOL_DUR


class Courts:
    def __init__(self):
        self.free_at    = [0]*(NUM_COURTS+1)
        self.soft_slots = defaultdict(set)
    def soft_book(self,c,slot): self.soft_slots[c].add(slot)
    def book(self,c,start,dur): self.free_at[c]=max(self.free_at[c],start+dur)
    def is_free(self,c,slot):
        return slot not in self.soft_slots[c] and self.free_at[c]<=slot*POOL_DUR
    def earliest(self,not_before=0,duration=POOL_DUR):
        bt,bc=DAY_AVAIL+1,0
        for c in range(1,NUM_COURTS+1):
            t=max(self.free_at[c],not_before)
            while t+duration<=DAY_AVAIL:
                sl=t//POOL_DUR
                if sl not in self.soft_slots[c]: break
                t=(sl+1)*POOL_DUR
            if t+duration<=DAY_AVAIL and t<bt: bt,bc=t,c
        return bt,bc
    def copy(self):
        c2=Courts(); c2.free_at=self.free_at[:]
        for k,v in self.soft_slots.items(): c2.soft_slots[k]=set(v)
        return c2
