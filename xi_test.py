#!/usr/bin/env python3
"""xi_test.py — dodatek v5n: dobór zaniku czasowego (półokresu) Dixon-Colesa walk-forward. Bez kursów.
  python3 xi_test.py  → logloss zespołu dla półokresów 180/365/730 dni na tych samych meczach"""
import sys, os, pickle, numpy as np
sys.argv = sys.argv[:1]
import model, ensemble as E
res = {}
for hl in (180, 365, 730):
    model.XI = np.log(2) / hl
    E.START, E.END = '2025-08-01', E.END
    cp = os.path.join(E.HERE, 'cache', f'bt_v5n_{E.START}_{E.END}.pkl')
    alt = cp.replace('.pkl', f'_hl{hl}.pkl')
    if hl == 365 and os.path.exists(cp): bt = pickle.load(open(cp, 'rb'))
    elif os.path.exists(alt): bt = pickle.load(open(alt, 'rb'))
    else:
        if os.path.exists(cp): os.rename(cp, cp + '.tmp')
        bt = E.build_rows(); os.rename(cp, alt)
        if os.path.exists(cp + '.tmp'): os.rename(cp + '.tmp', cp)
    for w in ((1, 0, 0), (0.5, 0, 0.5)):
        res[(hl, w)] = E.score(bt, w)[0]
        print(f'półokres {hl} dni, wagi {w}: logloss {res[(hl, w)]:.4f}', flush=True)
