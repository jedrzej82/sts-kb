#!/usr/bin/env python3
"""Pętla uczenia na wynikach na żywo (codziennie):
  python3 ucz.py wynik LIGA DATA GOSP GOŚĆ G_GOSP G_GOŚĆ [HT_G HT_A]  -> dopisuje wynik do delta.csv (ligi/mecze spoza GitHuba)
  python3 ucz.py typ DATA GOSP GOŚĆ RYNEK P                           -> zapisuje typ modelu do typy_log.csv
  python3 ucz.py rozlicz                                              -> rozlicza typy wynikami z bazy, liczy własną trafność
Po rozliczeniu powstaje korekta_wlasna.csv: dla każdego rynku i przedziału P miesza kalibrację z backtestu
z NASZĄ rzeczywistą trafnością (waga n/(n+100)), więc model poprawia się z każdym rozliczonym typem."""
import os, sys, sqlite3, datetime as dt, numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
LOG, DELTA, KOR = (os.path.join(HERE, f) for f in ('typy_log.csv', 'delta.csv', 'korekta_wlasna.csv'))
BINS = [0, .6, .7, .75, .8, .85, .9, .95, 1.01]


def hit(rynek, fh, fa, hth=None, hta=None):
    t = fh + fa
    r = {'1': fh > fa, 'X': fh == fa, '2': fh < fa, '1X': fh >= fa, 'X2': fh <= fa, '12': fh != fa,
         'BTTS_tak': fh > 0 and fa > 0, 'BTTS_nie': not (fh > 0 and fa > 0), 'gosp_O0.5': fh > 0, 'gość_O0.5': fa > 0,
         'gosp_O1.5': fh > 1, 'gość_O1.5': fa > 1, 'DNB_1': None if fh == fa else fh > fa, 'DNB_2': None if fh == fa else fa > fh}
    for k in (0.5, 1.5, 2.5, 3.5, 4.5): r[f'O{k}'] = t > k; r[f'U{k}'] = t < k
    if hth is not None and not pd.isna(hth): r['HT_O0.5'] = hth + hta > 0
    return r.get(rynek)


def main(a):
    if a[0] == 'wynik':
        row = dict(Division=a[1], MatchDate=a[2], HomeTeam=a[3], AwayTeam=a[4], FTHome=int(a[5]), FTAway=int(a[6]),
                   HTHome=int(a[7]) if len(a) > 8 else None, HTAway=int(a[8]) if len(a) > 8 else None)
        pd.DataFrame([row]).to_csv(DELTA, mode='a', header=not os.path.exists(DELTA), index=False); print('dopisano', row)
    elif a[0] == 'typ':
        row = dict(data=a[1], gosp=a[2], gość=a[3], rynek=a[4], p=float(a[5]), trafiony=None)
        pd.DataFrame([row]).to_csv(LOG, mode='a', header=not os.path.exists(LOG), index=False); print('zapisano typ', row)
    elif a[0] == 'rozlicz':
        if not os.path.exists(LOG): sys.exit('brak typów')
        L = pd.read_csv(LOG)
        m = pd.read_sql('select MatchDate, HomeTeam, AwayTeam, FTHome, FTAway, HTHome, HTAway from matches',
                        sqlite3.connect(os.path.join(HERE, 'kb.sqlite')))
        key = {(r.MatchDate[:10], r.HomeTeam, r.AwayTeam): r for r in m.itertuples()}
        for i, r in L[L.trafiony.isna()].iterrows():
            x = key.get((str(r.data)[:10], r.gosp, r['gość']))
            if x is not None:
                h = hit(r.rynek, x.FTHome, x.FTAway, x.HTHome, x.HTAway)
                L.loc[i, 'trafiony'] = None if h is None else int(h)
        L.to_csv(LOG, index=False)
        done = L.dropna(subset=['trafiony'])
        print(f'Rozliczone typy: {len(done)} | trafność {done.trafiony.mean():.1%} | średnie P {done.p.mean():.1%}' if len(done) else 'Brak rozliczonych')
        if len(done):
            done = done.assign(przedział=pd.cut(done.p, BINS, right=False))
            k = done.groupby(['rynek', 'przedział'], observed=True).agg(n=('trafiony', 'size'), p_model=('p', 'mean'),
                                                                        trafność=('trafiony', 'mean')).reset_index()
            k['waga'] = k.n / (k.n + 100)
            k.to_csv(KOR, index=False, float_format='%.4f'); print(k.to_string(index=False))


if __name__ == '__main__':
    main(sys.argv[1:] or ['rozlicz'])
