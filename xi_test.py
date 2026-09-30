#!/usr/bin/env python3
"""xi_test.py — dodatek v5n: dobór zaniku czasowego (półokresu) Dixon-Colesa walk-forward. Bez kursów.
  python3 xi_test.py  → logloss zespołu dla półokresów 180/365/730 dni na tych samych meczach"""
import sys, numpy as np
sys.argv = sys.argv[:1]
import model, ensemble as E
res = {}
for hl in (180, 365, 730):
    # 30.09.2026: dawniej sciezka cache nie zgadzala sie z ensemble.build_rows (os.rename -> FileNotFoundError),
    # a istniejacy cache innego polokresu byl po cichu uzywany. Teraz kazdy polokres ma wlasny klucz (tag).
    model.XI = np.log(2) / hl
    E.START = '2025-08-01'
    bt = E.build_rows(tag=f'_hl{hl}')
    for w in ((1, 0, 0), (0.5, 0, 0.5)):
        res[(hl, w)] = E.score(bt, w)[0]
        print(f'półokres {hl} dni, wagi {w}: logloss {res[(hl, w)]:.4f}', flush=True)
