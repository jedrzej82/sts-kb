#!/usr/bin/env python3
"""Walk-forward backtest (refit co miesiąc) — trafność modelu i kalibracja progów. Bez kursów."""
import sqlite3, os, sys, numpy as np, pandas as pd
from model import fit_dc, dc_lambdas, fit_elo_glm, elo_lambdas, markets, blend

HERE = os.path.dirname(os.path.abspath(__file__))
db = sqlite3.connect(os.path.join(HERE, 'kb.sqlite'))
m = pd.read_sql('select * from matches', db, parse_dates=['MatchDate'])
START, END = sys.argv[1] if len(sys.argv) > 1 else '2024-08-01', sys.argv[2] if len(sys.argv) > 2 else '2026-06-30'
test = m[(m.MatchDate >= START) & (m.MatchDate <= END)]
divs = [d for d, c in test.Division.value_counts().items() if c >= 150]
glm = fit_elo_glm(m[m.MatchDate < START])
rows = []
months = pd.date_range(START, END, freq='MS')
for div in divs:
    dm = m[m.Division == div]
    for ms in months:
        me = ms + pd.offsets.MonthBegin(1)
        tm = dm[(dm.MatchDate >= ms) & (dm.MatchDate < me)]
        if tm.empty: continue
        mdl = fit_dc(dm, ms)
        for r in tm.itertuples():
            ldc = dc_lambdas(mdl, r.HomeTeam, r.AwayTeam)
            lel = elo_lambdas(glm, r.HomeElo, r.AwayElo, div) if pd.notna(r.HomeElo) and pd.notna(r.AwayElo) else None
            if ldc is None and lel is None: continue
            rows.append(dict(div=div, date=r.MatchDate, h=r.HomeTeam, a=r.AwayTeam, fh=r.FTHome, fa=r.FTAway,
                             hth=r.HTHome, hta=r.HTAway, ldc=ldc, lel=lel, rho=mdl['rho'] if mdl else -0.05))
bt = pd.DataFrame(rows)
print('mecze w teście:', len(bt), 'ligi:', len(divs))
res = np.where(bt.fh > bt.fa, '1', np.where(bt.fh == bt.fa, 'X', '2'))
# wybór wagi blendu po log-loss 1X2
best = None
for w in (0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 1.0):
    ll = []
    for r, y in zip(bt.itertuples(), res):
        lam = blend(r.ldc, r.lel, w)
        mk = markets(*lam, r.rho)
        ll.append(-np.log(max(mk[y], 1e-9)))
    v = np.mean(ll); print(f'w_dc={w}: logloss 1X2={v:.4f}')
    if best is None or v < best[1]: best = (w, v)
W = best[0]; print('najlepsza waga DC =', W)
recs = []
for r, y in zip(bt.itertuples(), res):
    mk = markets(*blend(r.ldc, r.lel, W), r.rho)
    t = r.fh + r.fa
    outc = {'1': y == '1', 'X': y == 'X', '2': y == '2', '1X': y != '2', 'X2': y != '1', '12': y != 'X',
            'O1.5': t > 1.5, 'O2.5': t > 2.5, 'U2.5': t < 2.5, 'U3.5': t < 3.5, 'U4.5': t < 4.5, 'O0.5': t > 0.5,
            'BTTS_tak': r.fh > 0 and r.fa > 0, 'BTTS_nie': not (r.fh > 0 and r.fa > 0),
            'gosp_O0.5': r.fh > 0, 'gość_O0.5': r.fa > 0, 'DNB_1': (y == '1') if y != 'X' else None,
            'DNB_2': (y == '2') if y != 'X' else None}
    if pd.notna(r.hth):
        outc['HT_O0.5'] = (r.hth + r.hta) > 0
    for k, v in outc.items():
        if v is None: continue
        recs.append((r.div, k, mk[k], bool(v)))
cal = pd.DataFrame(recs, columns=['div', 'rynek', 'p', 'traf'])
# mapa kalibracji (izotoniczna, PAV na 20 przedziałach) per rynek
maps = []
for rk, g in cal.groupby('rynek'):
    g = g.sort_values('p'); P = g.p.values; T = g.traf.values.astype(float)
    q = np.array_split(np.arange(len(g)), min(20, max(2, len(g) // 150)))
    xs = [P[c].mean() for c in q]; ys = [T[c].mean() for c in q]; ws = [len(c) for c in q]
    blocks = [[x, y, w] for x, y, w in zip(xs, ys, ws)]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][1] > blocks[i + 1][1]:
            a, b = blocks[i], blocks[i + 1]; w = a[2] + b[2]
            blocks[i] = [(a[0] * a[2] + b[0] * b[2]) / w, (a[1] * a[2] + b[1] * b[2]) / w, w]; del blocks[i + 1]
            i = max(i - 1, 0)
        else:
            i += 1
    maps += [(rk, x, y, w) for x, y, w in blocks]
pd.DataFrame(maps, columns=['rynek', 'p_model', 'p_kalibr', 'n']).to_csv(os.path.join(HERE, 'kalibracja_mapa.csv'), index=False, float_format='%.4f')
bins = [0, .5, .6, .7, .75, .8, .85, .9, .95, 1.01]
cal['przedział'] = pd.cut(cal.p, bins, right=False)
tab = cal.groupby(['rynek', 'przedział'], observed=True).agg(n=('traf', 'size'), p_model=('p', 'mean'), trafność=('traf', 'mean')).reset_index()
tab = tab[tab.n >= 30]
pd.set_option('display.width', 200)
print(tab[tab.p_model >= 0.7].to_string(index=False, float_format=lambda x: f'{x:.3f}'))
tab.to_csv(os.path.join(HERE, 'kalibracja.csv'), index=False, float_format='%.4f')
# trafność per liga dla progu 75%+
hi = cal[cal.p >= 0.75]
lg = hi.groupby('div').agg(n=('traf', 'size'), p_model=('p', 'mean'), trafność=('traf', 'mean')).reset_index()
lg.to_csv(os.path.join(HERE, 'kalibracja_ligi.csv'), index=False, float_format='%.4f')
print(lg.to_string(index=False, float_format=lambda x: f'{x:.3f}'))
open(os.path.join(HERE, 'blend_weight.txt'), 'w').write(str(W))
