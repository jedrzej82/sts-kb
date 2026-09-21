#!/usr/bin/env python3
"""sporty_bt.py — dodatek v5n: test i strojenie modeli dla sportów drużynowych (koszykówka, hokej, futbol amer., baseball).
Porównuje obecne Elo (sporty.py) z modelem MARŻY PUNKTOWEJ (rating w punktach z zanikiem, P z rozkładu normalnego)
i ich zespołem; wagi i kalibracja Platta z części uczącej, ocena na testowej. Wynik → sporty_param.json. Bez kursów.
  python3 sporty_bt.py koszykówka [START_TEST=2024-07-01]"""
import sys, json, os, numpy as np, pandas as pd
from scipy.stats import norm
from scipy.optimize import minimize
import sporty as S
HERE = os.path.dirname(os.path.abspath(__file__))
sport = sys.argv[1] if len(sys.argv) > 1 else 'koszykówka'
TEST = pd.Timestamp(sys.argv[2] if len(sys.argv) > 2 else '2024-07-01')
TRAIN = TEST - pd.Timedelta(days=365 * 4)
d = S.load(); d = d[(d.sport == sport)].dropna(subset=['pg', 'pa']).reset_index(drop=True)
d = d[d.pg != d.pa] if sport in ('koszykówka', 'baseball', 'futbol amerykański') else d
pre = []; S.elo(d, sport, pre=pre)
hfa_elo = S.SPORT.get(sport, (40, False))[0]
E = np.array(pre)
p_elo = 1 / (1 + 10 ** ((E[:, 1] - E[:, 0] - hfa_elo) / 400))

def margin_model(k=0.08, hfa=2.5, reg=0.25):
    R, last = {}, {}; out = np.empty(len(d))
    for i, r in enumerate(d.itertuples()):
        for t in (r.gosp, r.gosc):
            if t in last and (r.data - last[t]).days > 90: R[t] = R[t] * (1 - reg)
            last[t] = r.data
        a, b = R.get(r.gosp, 0.), R.get(r.gosc, 0.)
        pm = a - b + hfa; out[i] = pm
        err = (r.pg - r.pa) - pm; err = np.clip(err, -30, 30)
        R[r.gosp] = a + k * err; R[r.gosc] = b - k * err
    return out
y = (d.pg > d.pa).values.astype(float)
n_ok = (E[:, 2] >= 10) & (E[:, 3] >= 10)
tr = (d.data >= TRAIN).values & (d.data < TEST).values & n_ok; te = (d.data >= TEST).values & n_ok
ll = lambda p, m: -np.mean(y[m] * np.log(np.clip(p[m], 1e-6, 1 - 1e-6)) + (1 - y[m]) * np.log(np.clip(1 - p[m], 1e-6, 1 - 1e-6)))
best = None
for k in (0.03, 0.05, 0.08, 0.12):
    for hfa in (1.5, 2.5, 3.5):
        pm = margin_model(k, hfa)
        sd = np.std(((d.pg - d.pa).values - pm)[tr])
        p = norm.cdf(pm / sd)
        v = ll(p, tr)
        if best is None or v < best[0]: best = (v, k, hfa, sd, p)
    print('k', k, 'najlepsze dotąd', round(best[0], 4), flush=True)
_, K, HFA, SD, p_m = best
lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
def fit_platt(x, m):
    f = lambda a: ll(1 / (1 + np.exp(-(a[0] * x + a[1]))), m)
    return minimize(f, [1.0, 0.0]).x
res = {}
for w in np.arange(0, 1.01, 0.1):
    x = w * lg(p_elo) + (1 - w) * lg(p_m)
    a = fit_platt(x, tr); res[round(w, 1)] = (ll(1 / (1 + np.exp(-(a[0] * x + a[1]))), tr), a)
W = min(res, key=lambda w: res[w][0]); A = res[W][1]
x = W * lg(p_elo) + (1 - W) * lg(p_m); p_new = 1 / (1 + np.exp(-(A[0] * x + A[1])))
# obecny model = Elo + dotychczasowa kalibracja binowa z sporty_kalibracja_hist.csv
p_cur = np.array([S.calibrate(sport, p)[0] for p in p_elo])
print(f'\n{sport}: uczenie {tr.sum()} meczów, test {te.sum()} (od {TEST.date()})')
print(f'marża: k={K} przewaga={HFA} pkt, sd={SD:.1f} | waga Elo w zespole={W}, Platt a={A[0]:.3f} b={A[1]:.3f}')
for n, p in (('obecny (Elo+kalibracja)', p_cur), ('samo Elo', p_elo), ('model marży', p_m), ('ZESPÓŁ v5n', p_new)):
    print(f'  {n:<24} test logloss {ll(p, te):.4f}  Brier {np.mean((p[te] - y[te]) ** 2):.4f}')
t = pd.DataFrame({'p': np.maximum(p_new[te], 1 - p_new[te]), 'hit': (p_new[te] >= 0.5) == (y[te] == 1)})
t['b'] = pd.cut(t.p, [.5, .6, .7, .75, .8, .85, .9, 1.01], right=False)
print(t.groupby('b', observed=True).agg(n=('hit', 'size'), P=('p', 'mean'), traf=('hit', 'mean')).round(3).to_string())
P = json.load(open(os.path.join(HERE, 'sporty_param.json'))) if os.path.exists(os.path.join(HERE, 'sporty_param.json')) else {}
P[sport] = dict(k=K, hfa=HFA, sd=float(SD), w_elo=float(W), platt=[float(A[0]), float(A[1])], test_od=str(TEST.date()),
                logloss_obecny=float(ll(p_cur, te)), logloss_nowy=float(ll(p_new, te)))
json.dump(P, open(os.path.join(HERE, 'sporty_param.json'), 'w'), ensure_ascii=False, indent=1)
