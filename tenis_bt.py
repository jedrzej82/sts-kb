import re, numpy as np, pandas as pd, itertools, sys
from tenis import load
d = load()
def games(s):
    w=l=0
    for a,b in re.findall(r'(\d+)-(\d+)', str(s)):
        a,b=int(a),int(b)
        if a>7 or b>7: continue   # super-tiebreak / tiebreak points
        w+=a; l+=b
    return (w/(w+l)) if w+l>0 else np.nan
d['gs']=[games(s) for s in d.score]
W=d.winner_name.values; L=d.loser_name.values; S=d.surface.values; G=d.gs.values; D=d.date.values
def run(c1=250,c2=5,c3=0.4,mov=0.0,decay=0.0):
    R,Rs,N,Ns,last={},{},{},{},{}
    out=np.empty((len(d),6))
    for i in range(len(d)):
        w,l,s=W[i],L[i],S[i]
        rw,rl=R.get(w,1500.),R.get(l,1500.); sw,sl=Rs.get((w,s),1500.),Rs.get((l,s),1500.)
        out[i]=(rw,rl,sw,sl,N.get(w,0),N.get(l,0))
        e=1/(1+10**((rl-rw)/400)); es=1/(1+10**((sl-sw)/400))
        m=1.0
        if mov and G[i]==G[i]: m=1+mov*(G[i]-0.58)/0.1   # dominacja w gemach (0.58 ≈ typowy udział zwycięzcy)
        m=min(max(m,0.5),2.0)
        kw=c1/(N.get(w,0)+c2)**c3; kl=c1/(N.get(l,0)+c2)**c3
        kws=c1/(Ns.get((w,s),0)+c2)**c3; kls=c1/(Ns.get((l,s),0)+c2)**c3
        R[w]=rw+kw*m*(1-e); R[l]=rl-kl*m*(1-e)
        Rs[(w,s)]=sw+kws*m*(1-es); Rs[(l,s)]=sl-kls*m*(1-es)
        N[w]=N.get(w,0)+1; N[l]=N.get(l,0)+1; Ns[(w,s)]=Ns.get((w,s),0)+1; Ns[(l,s)]=Ns.get((l,s),0)+1
    return out
tr=(d.date>='2024-01-01')&(d.date<'2025-07-01'); te=(d.date>='2025-07-01')
def evalp(o,ws,mask):
    ok=mask.values&(o[:,4]>=10)&(o[:,5]>=10)
    ew=(1-ws)*o[ok,0]+ws*o[ok,2]; el=(1-ws)*o[ok,1]+ws*o[ok,3]
    p=1/(1+10**((el-ew)/400))   # P(zwycięzca) — logloss = -log p
    return p
res=[]
cache={}
for c1,c3,mov in itertools.product([200,250,300],[0.35,0.4,0.5],[0.0,0.5,1.0]):
    o=run(c1,5,c3,mov); cache[(c1,c3,mov)]=o
    for ws in (0.3,0.5,0.7):
        p=evalp(o,ws,tr); res.append((-np.log(p).mean(),c1,c3,mov,ws))
    print(c1,c3,mov,min(r[0] for r in res if r[1:4]==(c1,c3,mov)),flush=True)
res.sort(); best=res[0]; print('najlepsze (uczenie):',best)
base=(250,0.4,0.0,0.5)
for name,(c1,c3,mov,ws) in (('obecny',base),('nowy',best[1:])):
    p=evalp(cache[(c1,c3,mov)],ws,te)
    pf=np.maximum(p,1-p); hit=(p>=0.5)
    print(name,'test logloss %.4f Brier %.4f n=%d'%(-np.log(p).mean(),((1-p)**2).mean(),len(p)))
# Platt na uczeniu
from scipy.optimize import minimize
c1,c3,mov,ws=best[1:]; o=cache[(c1,c3,mov)]
def lg(x): return np.log(x/(1-x))
ptr=evalp(o,ws,tr); pte=evalp(o,ws,te)
# symetryzacja: losowo odwracamy stronę, żeby P nie było zawsze P(zwycięzcy)
rng=np.random.default_rng(1); f=rng.random(len(ptr))<0.5; x=np.where(f,1-ptr,ptr); y=np.where(f,0,1)
nll=lambda a: -np.mean(y*np.log(1/(1+np.exp(-a[0]*lg(x))))+(1-y)*np.log(1-1/(1+np.exp(-a[0]*lg(x)))))
a=minimize(nll,[1.0]).x[0]; print('Platt a=%.3f'%a)
pc=1/(1+np.exp(-a*lg(pte)))
print('nowy+Platt test logloss %.4f'%(-np.log(pc).mean()))
t=pd.DataFrame({'p':np.maximum(pc,1-pc),'hit':(pc>=0.5)}); t['b']=pd.cut(t.p,[.5,.6,.7,.75,.8,.85,.9,1.01],right=False)
print(t.groupby('b',observed=True).agg(n=('hit','size'),P=('p','mean'),traf=('hit','mean')).round(3).to_string())
t0=pd.DataFrame({'p':np.maximum(pte,1-pte),'hit':(pte>=0.5)}); t0['b']=pd.cut(t0.p,[.5,.6,.7,.75,.8,.85,.9,1.01],right=False)
print('bez Platta:\n',t0.groupby('b',observed=True).agg(n=('hit','size'),P=('p','mean'),traf=('hit','mean')).round(3).to_string())
import json; json.dump(dict(c1=c1,c2=5,c3=c3,mov=mov,ws=ws,platt=a),open('tenis_param.json','w'))
