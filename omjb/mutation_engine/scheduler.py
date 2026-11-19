import math

class ArmStats:
    def __init__(self,key,cost):
        self.key,self.cost,self.n,self.reward_sum=key,cost,0,0.0
    @property
    def mean(self):
        return self.reward_sum/self.n if self.n else 0.0

class CostAwareUCB:
    def __init__(self,c=1.2,lam=.05,prune_after=20,prune_below=.02):
        if not all(math.isfinite(x) for x in (c,lam,prune_below)):
            raise ValueError("scheduler values must be finite")
        if c<0 or lam<0 or prune_after<1 or not 0<=prune_below<=1:
            raise ValueError("invalid scheduler configuration")
        self.c,self.lam,self.prune_after,self.prune_below=c,lam,prune_after,prune_below
        self.stats={}
        self.pruned=set()
    def add(self,key,cost):
        cost=float(cost)
        if not math.isfinite(cost) or cost<0:
            raise ValueError("arm cost must be finite and non-negative")
        self.stats.setdefault(key,ArmStats(key,cost))
    def pick(self,keys):
        active=[k for k in keys if k not in self.pruned]
        if not active:
            return None
        for k in active:
            if self.stats[k].n==0:
                return k
        total=sum(self.stats[k].n for k in active) or 1
        return max(active,key=lambda k:self.stats[k].mean+
                   self.c*math.sqrt(math.log(total)/self.stats[k].n)-
                   self.lam*self.stats[k].cost/(1+self.stats[k].n))
    def update(self,key,reward):
        if not math.isfinite(reward) or not 0<=reward<=1:
            raise ValueError("reward must be finite and in [0,1]")
        s=self.stats[key]
        s.n+=1
        s.reward_sum+=reward
        if s.n>=self.prune_after and s.mean<self.prune_below:
            self.pruned.add(key)
    def summary(self):
        return {k:{"n":s.n,"mean":round(s.mean,3),"cost":s.cost,"pruned":k in self.pruned}
                for k,s in sorted(self.stats.items()) if s.n}
