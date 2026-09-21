#!/usr/bin/env python3
"""Rzuty rożne, kartki, faule, strzały — model z charakterystyki drużyn (bez kursów).
Oczekiwana wartość = średnia ligi (dom/wyjazd) × siła drużyny „za” × słabość rywala „przeciw”, z ważeniem świeżości i ściąganiem
do średniej ligi przy małej liczbie meczów. Rozkład łączny: ujemny dwumianowy (dyspersja z danych). Kalibracja z backtestu.
  python3 specjalne.py "Gosp" "Gość"            — tabela rynków
  python3 specjalne.py --backtest 2025-08-01     — walidacja i zapis kalibracji spec_kalibracja.csv"""
import os, sys, sqlite3, datetime as dt, numpy as np, pandas as pd
from scipy.stats import nbinom, poisson

HERE = os.path.dirname(os.path.abspath(__file__))
STATS = {'rożne': ('HomeCorners', 'AwayCorners'), 'żółte': ('HomeYellow', 'AwayYellow'),
         'faule': ('HomeFouls', 'AwayFouls'), 'strzały_celne': ('HomeTarget', 'AwayTarget'), 'strzały': ('HomeShots', 'AwayShots')}
LINES = {'rożne': [6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5], 'żółte': [1.5, 2.5, 3.5, 4.5, 5.5, 6.5],
         'faule': [17.5, 19.5, 21.5, 23.5, 25.5, 27.5], 'strzały_celne': [5.5, 6.5, 7.5, 8.5, 9.5, 10.5],
         'strzały': [19.5, 21.5, 23.5, 25.5, 27.5]}
TEAM_LINES = {'rożne': [2.5, 3.5, 4.5, 5.5, 6.5], 'żółte': [0.5, 1.5, 2.5], 'strzały_celne': [2.5, 3.5, 4.5, 5.5]}
XI = 0.004     # półokres ~ 6 mies.
PRIOR = 6.0    # waga średniej ligi (w „meczach”)


def load():
    return pd.read_sql('select * from matches', sqlite3.connect(os.path.join(HERE, 'kb.sqlite')), parse_dates=['MatchDate'])


def team_rates(d, ref, stat):
    """Zwraca dict: (team, 'dom'/'wyj') -> (za, przeciw) względem średniej ligi."""
    hc, ac = STATS[stat]
    d = d.dropna(subset=[hc, ac])
    d = d[(d.MatchDate < ref) & (d.MatchDate >= ref - pd.Timedelta(days=500))]
    if len(d) < 60: return None
    w = np.exp(-XI * (ref - d.MatchDate).dt.days.values)
    mh, ma = np.average(d[hc], weights=w), np.average(d[ac], weights=w)
    out = {}
    for side, tcol, f, a, base_f, base_a in (('dom', 'HomeTeam', hc, ac, mh, ma), ('wyj', 'AwayTeam', ac, hc, ma, mh)):
        g = d.assign(w=w).groupby(tcol)
        for t, x in g:
            sw = x.w.sum()
            za = (np.sum(x.w * x[f]) + PRIOR * base_f) / (sw + PRIOR) / base_f
            pr = (np.sum(x.w * x[a]) + PRIOR * base_a) / (sw + PRIOR) / base_a
            out[(t, side)] = (za, pr, len(x))
    return dict(rates=out, mh=mh, ma=ma, var_ratio=_disp(d, hc, ac))


def _disp(d, hc, ac):
    tot = d[hc] + d[ac]
    return max(1.0, tot.var() / tot.mean()) if tot.mean() > 0 else 1.0


def expect(R, h, a):
    rh = R['rates'].get((h, 'dom'), (1, 1, 0)); ra = R['rates'].get((a, 'wyj'), (1, 1, 0))
    eh = R['mh'] * rh[0] * ra[1]; ea = R['ma'] * ra[0] * rh[1]
    return eh, ea, min(rh[2], ra[2])


def dist_over(mu, line, vr):
    """P(X > line) — ujemny dwumianowy z dyspersją vr (wariancja/średnia); vr≈1 → Poisson."""
    k = int(np.floor(line))
    if vr <= 1.02: return 1 - poisson.cdf(k, mu)
    n = mu / (vr - 1); p = n / (n + mu)
    return 1 - nbinom.cdf(k, n, p)


def markets(R, h, a, stat):
    eh, ea, n = expect(R, h, a)
    vr = R['var_ratio']
    out = {}
    for L in LINES[stat]:
        po = dist_over(eh + ea, L, vr * 0.85)   # część wariancji tłumaczą różnice drużyn
        out[f'{stat} O{L}'] = po; out[f'{stat} U{L}'] = 1 - po
    for L in TEAM_LINES.get(stat, []):
        for who, mu in (('gosp', eh), ('gość', ea)):
            po = dist_over(mu, L, max(1.0, vr * 0.85))
            out[f'{stat} {who} O{L}'] = po; out[f'{stat} {who} U{L}'] = 1 - po
    return eh, ea, n, out


def calib(path=os.path.join(HERE, 'spec_kalibracja.csv')):
    if not os.path.exists(path): return {}
    c = pd.read_csv(path); return {k: (g.p_model.values, g.p_kalibr.values) for k, g in c.groupby('rodzina')}


def fam(k):  # rodzina rynku do kalibracji: np. "rożne O" / "żółte gosp U"
    parts = k.split(); return ' '.join(parts[:-1] + [parts[-1][0]])


def apply_cal(C, k, p):
    f = fam(k)
    if f not in C: return p
    x, y = C[f]; return float(np.interp(p, x, y))


def predict(home, away):
    import typuj as T
    m = load()
    pool = set(m.HomeTeam) | set(m.AwayTeam)
    h, a = T.resolve(home, pool), T.resolve(away, pool)
    print(f'Dopasowano: {h} | {a}')
    div = m[(m.HomeTeam == h) | (m.AwayTeam == h)].sort_values('MatchDate').Division.iloc[-1]
    today = pd.Timestamp(dt.date.today())
    C = calib(); rows = []
    for stat in STATS:
        R = team_rates(m[m.Division == div], today, stat)
        if R is None: continue
        eh, ea, n, mk = markets(R, h, a, stat)
        print(f'{stat:<14} oczekiwane {eh:5.2f} + {ea:5.2f} = {eh + ea:5.2f}  (meczów drużyn w próbie: {n})')
        for k, p in mk.items(): rows.append((k, p, apply_cal(C, k, p)))
    print('\nRynki z P_skalibr ≥ 75%:')
    for k, p, pc in sorted(rows, key=lambda r: -r[2]):
        if pc >= 0.75 and pc < 0.995: print(f'  {k:<26} {pc:6.1%}  (model {p:5.1%})')
    print('\nUwaga: sędzia ma duży wpływ na kartki — model go nie zna; kartki traktuj ostrożniej niż rożne.')
    return rows


def backtest(start):
    m = load(); m = m[m.Division.isin(['E0', 'E1', 'E2', 'E3', 'EC', 'SP1', 'SP2', 'I1', 'I2', 'D1', 'D2', 'F1', 'F2', 'N1', 'P1', 'B1', 'T1', 'G1', 'SC0', 'SC1', 'SC2', 'SC3'])]
    recs = []
    for div, dm in m.groupby('Division'):
        test = dm[dm.MatchDate >= start]
        for ms in pd.date_range(start, test.MatchDate.max(), freq='MS'):
            tm = test[(test.MatchDate >= ms) & (test.MatchDate < ms + pd.offsets.MonthBegin(1))]
            if tm.empty: continue
            for stat in ('rożne', 'żółte', 'faule', 'strzały_celne'):
                R = team_rates(dm, ms, stat)
                if R is None: continue
                hc, ac = STATS[stat]
                for r in tm.dropna(subset=[hc, ac]).itertuples():
                    eh, ea, n, mk = markets(R, r.HomeTeam, r.AwayTeam, stat)
                    if n < 3: continue
                    vh, va = getattr(r, hc), getattr(r, ac)
                    for k, p in mk.items():
                        parts = k.split(); L = float(parts[-1][1:]); ou = parts[-1][0]
                        val = vh + va if len(parts) == 2 else (vh if parts[1] == 'gosp' else va)
                        hit = val > L if ou == 'O' else val < L
                        recs.append((fam(k), k, p, hit))
    c = pd.DataFrame(recs, columns=['rodzina', 'rynek', 'p', 'traf'])
    maps = []
    for f, g in c.groupby('rodzina'):
        g = g.sort_values('p'); P = g.p.values; Tt = g.traf.values.astype(float)
        q = np.array_split(np.arange(len(g)), min(25, max(2, len(g) // 300)))
        blocks = [[P[i].mean(), Tt[i].mean(), len(i)] for i in q]
        i = 0
        while i < len(blocks) - 1:
            if blocks[i][1] > blocks[i + 1][1]:
                x, y = blocks[i], blocks[i + 1]; w = x[2] + y[2]
                blocks[i] = [(x[0] * x[2] + y[0] * y[2]) / w, (x[1] * x[2] + y[1] * y[2]) / w, w]; del blocks[i + 1]; i = max(i - 1, 0)
            else: i += 1
        maps += [(f, *b) for b in blocks]
    pd.DataFrame(maps, columns=['rodzina', 'p_model', 'p_kalibr', 'n']).to_csv(os.path.join(HERE, 'spec_kalibracja.csv'), index=False, float_format='%.4f')
    c['b'] = pd.cut(c.p, [0, .6, .7, .75, .8, .85, .9, .95, 1.01], right=False)
    c['stat'] = c.rodzina.str.split().str[0]
    t = c.groupby(['stat', 'b'], observed=True).agg(n=('traf', 'size'), p=('p', 'mean'), traf=('traf', 'mean')).reset_index()
    print(t[t.p >= 0.7].to_string(index=False, float_format=lambda x: f'{x:.3f}'))


if __name__ == '__main__':
    if sys.argv[1] == '--backtest': backtest(sys.argv[2] if len(sys.argv) > 2 else '2025-08-01')
    else: predict(sys.argv[1], sys.argv[2])
