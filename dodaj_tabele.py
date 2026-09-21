#!/usr/bin/env python3
"""Dopisuje tabele lig (np. z WebFetch Wikipedii) do tabele_eu.csv — siła startowa drużyn w sporty.py. Blok:
# sport|liga|sezon|data|kolumny   (kolumny np. team,gp,w,l,pf,pa  lub team,gp,w,d,l,gf,ga  lub team,gp,w,otw,otl,l,gf,ga)
wiersze CSV...
Istniejące wiersze (sport, liga, sezon, druzyna) są zastępowane."""
import sys, csv, io, os, pandas as pd

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tabele_eu.csv')
COLS = ['sport', 'liga', 'sezon', 'data', 'druzyna', 'gp', 'w', 'd', 'l', 'otw', 'otl', 'gf', 'ga']
rows, meta = [], None
for line in open(sys.argv[1], encoding='utf-8'):
    line = line.strip()
    if not line or line.startswith('```'): continue
    if line.startswith('#'):
        sport, liga, sezon, data, kol = [x.strip() for x in line[1:].split('|')]; meta = (sport, liga, sezon, data, kol.split(',')); continue
    if line.lower().startswith('team,'): continue
    v = next(csv.reader(io.StringIO(line)))
    r = dict(zip(meta[4], v)); x = dict(sport=meta[0], liga=meta[1], sezon=meta[2], data=meta[3], druzyna=r['team'].strip())
    for c in ('gp', 'w', 'd', 'l', 'otw', 'otl'): x[c] = float(r.get(c, 0) or 0)
    x['gf'] = float(r.get('gf', r.get('pf', r.get('sw', 0))) or 0); x['ga'] = float(r.get('ga', r.get('pa', r.get('sl', 0))) or 0)
    rows.append(x)
new = pd.DataFrame(rows, columns=COLS)
old = pd.read_csv(OUT) if os.path.exists(OUT) else pd.DataFrame(columns=COLS)
key = ['sport', 'liga', 'sezon', 'druzyna']
allr = pd.concat([old, new]).drop_duplicates(key, keep='last')
allr.to_csv(OUT, index=False)
print(f'dodano {len(new)}; razem {len(allr)}'); print(new.groupby(['sport', 'liga']).size().to_string())
