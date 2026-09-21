#!/usr/bin/env python3
"""ensemble.py — dodatek v5n (20.09.2026). Walk-forward backtest 3 modeli piłkarskich i ich zespołu:
  DC (Dixon-Coles z zanikiem czasu, per liga) + Elo-GLM (ClubElo) + pi-ratings (pi.py)
Wybiera wagi zespołu (log-linear na λ) na części UCZĄCEJ, sprawdza na części TESTOWEJ (bez podglądania),
potem liczy wagi końcowe i mapy kalibracji izotonicznej na całości (nowsze mecze ważniejsze, półokres 180 dni).
Wyniki: ensemble_wagi.json, kalibracja_mapa_v5n.csv, ensemble_raport.txt. Bez kursów.
  python3 ensemble.py [START=2025-08-01] [KONIEC=dziś]"""
import os, sys, json, pickle, sqlite3, itertools, numpy as np, pandas as pd
from model import fit_dc, dc_lambdas, fit_elo_glm, elo_lambdas, markets
from pi import prepare, fit_pi_glm, pi_lambdas

HERE = os.path.dirname(os.path.abspath(__file__))
START = sys.argv[1] if len(sys.argv) > 1 else '2025-08-01'
END = sys.argv[2] if len(sys.argv) > 2 else str(pd.Timestamp.today().date())
MK = ['1', 'X', '2', '1X', 'X2', '12', 'DNB_1', 'DNB_2', 'O0.5', 'O1.5', 'O2.5', 'U2.5', 'U3.5', 'U4.5', 'BTTS_tak', 'BTTS_nie',
      'gosp_O0.5', 'gość_O0.5', 'gosp_O1.5', 'gość_O1.5', 'HT_O0.5']
rep = []
def say(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); rep.append(s)


def outcomes(fh, fa, hth, hta):
    t = fh + fa
    o = {'1': fh > fa, 'X': fh == fa, '2': fh < fa, '1X': fh >= fa, 'X2': fh <= fa, '12': fh != fa,
         'DNB_1': None if fh == fa else fh > fa, 'DNB_2': None if fh == fa else fa > fh,
         'BTTS_tak': fh > 0 and fa > 0, 'BTTS_nie': not (fh > 0 and fa > 0), 'gosp_O0.5': fh > 0, 'gość_O0.5': fa > 0,
         'gosp_O1.5': fh > 1, 'gość_O1.5': fa > 1, 'HT_O0.5': None if hth != hth else (hth + hta) > 0}
    for k in (0.5, 1.5, 2.5, 3.5, 4.5): o[f'O{k}'] = t > k; o[f'U{k}'] = t < k
    return o


def build_rows():
    cp = os.path.join(HERE, 'cache', f'bt_v5n_{START}_{END}.pkl')
    if os.path.exists(cp): return pickle.load(open(cp, 'rb'))
    m = pd.read_sql('select * from matches', sqlite3.connect(os.path.join(HERE, 'kb.sqlite')), parse_dates=['MatchDate'])
    m = m.dropna(subset=['FTHome', 'FTAway'])
    m, _, _ = prepare(m)
    glm = fit_elo_glm(m[m.MatchDate < START])
    rows = []
    for ms in pd.date_range(START, END, freq='MS'):
        me = ms + pd.offsets.MonthBegin(1)
        tm = m[(m.MatchDate >= ms) & (m.MatchDate < me)]
        if tm.empty: continue
        past = m[m.MatchDate < ms]
        pg = fit_pi_glm(past[past.MatchDate >= ms - pd.Timedelta(days=365 * 4)])
        for div, tdm in tm.groupby('Division'):
            mdl = fit_dc(m[m.Division == div], ms)
            for r in tdm.itertuples():
                ldc = dc_lambdas(mdl, r.HomeTeam, r.AwayTeam)
                if ldc and min(mdl['cnt'].get(r.HomeTeam, 0), mdl['cnt'].get(r.AwayTeam, 0)) < 10: ldc = None
                lel = elo_lambdas(glm, r.HomeElo, r.AwayElo, div) if pd.notna(r.HomeElo) and pd.notna(r.AwayElo) else None
                lpi = pi_lambdas(pg, r.gd_hat, div)
                rows.append(dict(div=div, date=r.MatchDate, fh=r.FTHome, fa=r.FTAway, hth=r.HTHome, hta=r.HTAway,
                                 ldc=ldc, lel=lel, lpi=lpi, rho=mdl['rho'] if mdl else -0.05))
        print(ms.date(), len(rows), flush=True)
    bt = pd.DataFrame(rows); pickle.dump(bt, open(cp, 'wb')); return bt


def comb(r, w):
    parts = [(w[0], r.ldc), (w[1], r.lel), (w[2], r.lpi)]
    parts = [(a, l) for a, l in parts if l is not None and a > 0]
    if not parts:  # awaryjnie: cokolwiek dostępne
        parts = [(1, l) for l in (r.ldc, r.lel, r.lpi) if l is not None]
        if not parts: return None
    s = sum(a for a, _ in parts)
    return tuple(float(np.exp(sum(a * np.log(l[k]) for a, l in parts) / s)) for k in (0, 1))


def score(df, w):
    ll = []
    for r in df.itertuples():
        lam = comb(r, w)
        if lam is None: continue
        mk = markets(*lam, r.rho); o = outcomes(r.fh, r.fa, r.hth, r.hta)
        y = '1' if r.fh > r.fa else ('X' if r.fh == r.fa else '2')
        l = -np.log(max(mk[y], 1e-9))
        for k in ('O2.5', 'BTTS_tak', 'O1.5'):
            p = min(max(mk[k], 1e-6), 1 - 1e-6); l += -np.log(p if o[k] else 1 - p)
        ll.append(l)
    return float(np.mean(ll)), len(ll)


def pav(P, T, W):
    o = np.argsort(P); P, T, W = P[o], T[o], W[o]
    q = np.array_split(np.arange(len(P)), min(25, max(2, len(P) // 200)))
    bl = [[np.average(P[c], weights=W[c]), np.average(T[c], weights=W[c]), W[c].sum(), len(c)] for c in q]
    i = 0
    while i < len(bl) - 1:
        if bl[i][1] > bl[i + 1][1]:
            a, b = bl[i], bl[i + 1]; ww = a[2] + b[2]
            bl[i] = [(a[0] * a[2] + b[0] * b[2]) / ww, (a[1] * a[2] + b[1] * b[2]) / ww, ww, a[3] + b[3]]; del bl[i + 1]; i = max(i - 1, 0)
        else: i += 1
    return bl


def recs(df, w):
    out = []
    for r in df.itertuples():
        lam = comb(r, w)
        if lam is None: continue
        mk = markets(*lam, r.rho)
        for k, v in outcomes(r.fh, r.fa, r.hth, r.hta).items():
            if v is None or k not in MK: continue
            out.append((r.div, r.date, k, mk[k], int(v)))
    return pd.DataFrame(out, columns=['div', 'date', 'rynek', 'p', 'traf'])


def apply_map(maps, rk, p):
    g = maps.get(rk)
    return float(np.interp(p, g[0], g[1])) if g is not None and len(g[0]) > 1 else p


def table(c, col):
    c = c.assign(b=pd.cut(c[col], [.7, .75, .8, .85, .9, .95, 1.01], right=False))
    t = c.dropna(subset=['b']).groupby('b', observed=True).agg(n=('traf', 'size'), P=(col, 'mean'), traf=('traf', 'mean'))
    return t


if __name__ == '__main__':
    bt = build_rows()
    say(f'Backtest {START}..{END}: {len(bt)} meczów, {bt["div"].nunique()} lig | pokrycie DC {bt.ldc.notna().mean():.0%}, '
        f'Elo {bt.lel.notna().mean():.0%}, pi {bt.lpi.notna().mean():.0%}')
    cut = bt.date.quantile(0.5)
    tr, te = bt[bt.date < cut], bt[bt.date >= cut]
    say(f'Uczenie wag: do {cut.date()} ({len(tr)}), test: od {cut.date()} ({len(te)})')
    grid = [w for w in itertools.product(np.arange(0, 1.01, 0.1), repeat=3) if abs(sum(w) - 1) < 1e-6]
    base = {'stary blend DC/Elo 0.5/0.5': (0.5, 0.5, 0), 'sam DC': (1, 0, 0), 'sam Elo': (0, 1, 0), 'sam pi': (0, 0, 1)}
    res = sorted((score(tr, w)[0], tuple(round(x, 1) for x in w)) for w in grid)
    wbest = res[0][1]
    say('Najlepsze wagi (DC, Elo, pi) na części uczącej:', wbest, f'logloss {res[0][0]:.4f}')
    say('\nPorównanie na części TESTOWEJ (logloss 1X2+O2.5+BTTS+O1.5, niżej = lepiej):')
    for n, w in list(base.items()) + [('ZESPÓŁ v5n', wbest)]:
        s, k = score(te, w); say(f'  {n:<28} {s:.4f}  (n={k})')
    # kalibracja: mapy z części uczącej → sprawdzenie na testowej
    rtr, rte = recs(tr, wbest), recs(te, wbest)
    hl = 180.0
    def maps_of(c):
        age = (c.date.max() - c.date).dt.days.values
        c = c.assign(w=0.5 ** (age / hl)); M = {}
        for rk, g in c.groupby('rynek'):
            bl = pav(g.p.values, g.traf.values.astype(float), g.w.values)
            M[rk] = (np.array([b[0] for b in bl]), np.array([b[1] for b in bl]), bl)
        return M
    Mtr = maps_of(rtr)
    rte['p_kal'] = [apply_map(Mtr, k, p) for k, p in zip(rte.rynek, rte.p)]
    say('\nKalibracja na części TESTOWEJ — typy z P ≥ 70% (wszystkie rynki):')
    say('  surowe P:'); say(table(rte, 'p').to_string(float_format=lambda x: f'{x:.3f}'))
    say('  po rekalibracji (mapa z części uczącej):'); say(table(rte, 'p_kal').to_string(float_format=lambda x: f'{x:.3f}'))
    br = lambda c, col: float(((c[col] - c.traf) ** 2).mean())
    say(f'  Brier wszystkie rynki: surowe {br(rte, "p"):.4f} → po rekalibracji {br(rte, "p_kal"):.4f}')
    # końcowe: wagi i mapy na całości
    resA = sorted((score(bt, w)[0], tuple(round(x, 1) for x in w)) for w in grid)
    wfin = resA[0][1]; say('\nWagi końcowe (cały okres):', wfin)
    Mall = maps_of(recs(bt, wfin))
    rows = [(rk, b[0], b[1], b[3]) for rk, (x, y, bl) in Mall.items() for b in bl]
    pd.DataFrame(rows, columns=['rynek', 'p_model', 'p_kalibr', 'n']).to_csv(os.path.join(HERE, 'kalibracja_mapa_v5n.csv'), index=False, float_format='%.4f')
    ra = recs(bt, wfin); hi = ra[ra.p >= 0.75]
    lg = hi.groupby('div').agg(n=('traf', 'size'), P=('p', 'mean'), traf=('traf', 'mean')).reset_index()
    lg['różnica_pp'] = (lg.traf - lg.P) * 100
    lg.to_csv(os.path.join(HERE, 'kalibracja_ligi_v5n.csv'), index=False, float_format='%.4f')
    zle = lg[(lg.n >= 60) & (lg['różnica_pp'] < -5)].sort_values('różnica_pp')
    say('\nLigi, w których model PRZESZACOWUJE typy ≥75% o >5 pp (n≥60) — ostrożnie w AKO:')
    say(zle.to_string(index=False, float_format=lambda x: f'{x:.2f}') if len(zle) else '  brak')
    json.dump(dict(wagi_dc_elo_pi=wfin, wagi_test=wbest, okres=[START, END], data=str(pd.Timestamp.today().date())),
              open(os.path.join(HERE, 'ensemble_wagi.json'), 'w'), ensure_ascii=False)
    open(os.path.join(HERE, 'ensemble_raport.txt'), 'w').write('\n'.join(rep) + '\n')
