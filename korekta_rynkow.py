#!/usr/bin/env python3
"""korekta_rynkow.py — dodatek v5n. Z backtestu zespołu (ensemble.py) liczy, o ile model myli się per RYNEK i przedział P
(70–80 / 80–90 / 90+), i zapisuje korekta_rynkow_v5n.csv. Stosowane w typuj.py TYLKO w dół (ostrożnie):
  przesunięcie = (trafność − P) · n/(n+300), gdy ujemne; dodatnie ignorowane. Nowsze mecze ważniejsze (półokres 180 dni)."""
import os, sys, numpy as np, pandas as pd
sys.argv = sys.argv[:1]
import ensemble as E
HERE = os.path.dirname(os.path.abspath(__file__))
bt = E.build_rows(); w = tuple(__import__('json').load(open(os.path.join(HERE, 'ensemble_wagi.json')))['wagi_dc_elo_pi'])
r = E.recs(bt, w); r = r[r.p >= 0.7]
r['wt'] = 0.5 ** ((r.date.max() - r.date).dt.days / 180.0)
r['b'] = pd.cut(r.p, [.7, .8, .9, 1.01], right=False).astype(str)
out = []
for (rk, b), g in r.groupby(['rynek', 'b']):
    n = len(g); P = np.average(g.p, weights=g.wt); T = np.average(g.traf, weights=g.wt)
    s = (T - P) * n / (n + 300)
    out.append((rk, b, n, round(P, 4), round(T, 4), round(min(s, 0.0), 4)))
k = pd.DataFrame(out, columns=['rynek', 'przedzial', 'n', 'P_model', 'trafnosc', 'przesuniecie'])
k.to_csv(os.path.join(HERE, 'korekta_rynkow_v5n.csv'), index=False)
print(k[k.przesuniecie < -0.01].to_string(index=False))
