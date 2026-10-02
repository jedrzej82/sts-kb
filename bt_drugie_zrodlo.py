#!/usr/bin/env python3
"""Backtest bramki drugiego zrodla (Poprawka 48) — czy ona w ogole pomaga. Faza 4, 29.09.2026.
  python3 bt_drugie_zrodlo.py [START=2026-01-01] [KONIEC=dzis]
  python3 bt_drugie_zrodlo.py --sporty [OD]   |   python3 bt_drugie_zrodlo.py --intl [OD=2024-01-01]

Dla kazdego meczu z okresu testowego (walk-forward, model dopasowany na danych sprzed miesiaca):
  P_model — zespol DC+Elo+pi z wagami ensemble_wagi.json, korekta_rynkow_v5n.csv i −4 pp dla „ponizej” (jak typuj.py)
  P_forma — czestosc zdarzenia w 10 ostatnich meczach obu druzyn przed data meczu, (k+1)/(n+2) (jak drugie_zrodlo())
Bramka P48: noga przechodzi, gdy obie druzyny maja >= 6 meczow i |P_model − P_forma| <= 10 pp; P do kuponu = min.
Wypisuje dla nog z P_model >= 0,70 (te ida na kupony):
  (1) trafnosc nog PRZEPUSZCZONYCH i ODRZUCONYCH przy tym samym P_model — czy bramka odsiewa nogi, ktore trafiaja rzadziej,
  (2) kalibracje: srednie P vs trafnosc dla P_model i dla min(P_model, P_forma) wsrod przepuszczonych,
  (3) Brier i log loss obu wariantow.
Bez kursow — nie mierzy EV, tylko to, czy P jest trafne."""
import json
import os
import sqlite3
import sys
from bisect import bisect_left

import numpy as np
import pandas as pd

from ensemble import comb, outcomes, MK
from model import fit_dc, dc_lambdas, fit_elo_glm, elo_lambdas, markets
from pi import prepare, fit_pi_glm, pi_lambdas

HERE = os.path.dirname(os.path.abspath(__file__))
PROG, MIN_M, OKNO = 0.10, 6, 10
RYNKI_P48 = ['1', '2', 'X', '1X', 'X2', '12', 'O0.5', 'O1.5', 'O2.5', 'U2.5', 'U3.5', 'U4.5', 'BTTS_tak', 'BTTS_nie',
             'gosp_O0.5', 'gość_O0.5']


def forma(hist, t, d, n=OKNO):
    """Ostatnie n meczow druzyny t przed data d: lista (gole_zdobyte, gole_stracone)."""
    h = hist.get(t)
    if not h: return []
    i = bisect_left(h[0], d)
    return h[1][max(0, i - n):i]


def p_forma(fh, fa):
    """Ten sam wzor co typuj.drugie_zrodlo (po jednym wierszu na rynek)."""
    r = lambda k, m: (k + 1) / (m + 2)
    def cz(f, war): return sum(1 for g in f if war(*g)), len(f)
    nh, na = len(fh), len(fa)
    wh = cz(fh, lambda z, s: z > s)[0]; dh = cz(fh, lambda z, s: z == s)[0]; lh = cz(fh, lambda z, s: z < s)[0]
    wa = cz(fa, lambda z, s: z > s)[0]; da = cz(fa, lambda z, s: z == s)[0]; la = cz(fa, lambda z, s: z < s)[0]
    sr = lambda war: (r(*cz(fh, war)) + r(*cz(fa, war))) / 2
    return {'1': (r(wh, nh) + r(la, na)) / 2, '2': (r(wa, na) + r(lh, nh)) / 2, 'X': (r(dh, nh) + r(da, na)) / 2,
            '1X': (r(wh + dh, nh) + r(la + da, na)) / 2, 'X2': (r(wa + da, na) + r(lh + dh, nh)) / 2,
            '12': 1 - (r(dh, nh) + r(da, na)) / 2,
            'O0.5': sr(lambda z, s: z + s >= 1), 'O1.5': sr(lambda z, s: z + s >= 2), 'O2.5': sr(lambda z, s: z + s >= 3),
            'U2.5': sr(lambda z, s: z + s <= 2), 'U3.5': sr(lambda z, s: z + s <= 3), 'U4.5': sr(lambda z, s: z + s <= 4),
            'BTTS_tak': sr(lambda z, s: z > 0 and s > 0), 'BTTS_nie': sr(lambda z, s: z == 0 or s == 0),
            'gosp_O0.5': (r(*cz(fh, lambda z, s: z > 0)) + r(*cz(fa, lambda z, s: s > 0))) / 2,
            'gość_O0.5': (r(*cz(fa, lambda z, s: z > 0)) + r(*cz(fh, lambda z, s: s > 0))) / 2}


def korekta(KR):
    def f(k, p):   # kopia calibrate_v5n z typuj.py
        s = 0.0
        for r in KR[KR.rynek == k].itertuples():
            lo, hi = [float(x) for x in str(r.przedzial).strip('[)').split(',')]
            if lo <= p < hi: s = float(r.przesuniecie)
        if k.startswith('U') and p >= 0.5: s = min(s, -0.04)
        return max(p + s, 0.0)
    return f


def wiersze(start, koniec):
    m = pd.read_sql('select * from matches', sqlite3.connect(os.path.join(HERE, 'kb.sqlite')), parse_dates=['MatchDate'])
    m = m.dropna(subset=['FTHome', 'FTAway']).sort_values('MatchDate')
    m, _, _ = prepare(m)
    w = tuple(json.load(open(os.path.join(HERE, 'ensemble_wagi.json')))['wagi_dc_elo_pi'])
    kal = korekta(pd.read_csv(os.path.join(HERE, 'korekta_rynkow_v5n.csv')))
    hist = {}
    for t, d, gz, gs in list(zip(m.HomeTeam, m.MatchDate, m.FTHome, m.FTAway)) + list(zip(m.AwayTeam, m.MatchDate, m.FTAway, m.FTHome)):
        hist.setdefault(t, []).append((d, (int(gz), int(gs))))
    hist = {t: ([d for d, _ in sorted(v, key=lambda x: x[0])], [g for _, g in sorted(v, key=lambda x: x[0])]) for t, v in hist.items()}
    glm = fit_elo_glm(m[m.MatchDate < start])
    out = []
    for ms in pd.date_range(start, koniec, freq='MS'):
        tm = m[(m.MatchDate >= ms) & (m.MatchDate < ms + pd.offsets.MonthBegin(1))]
        if tm.empty: continue
        pg = fit_pi_glm(m[(m.MatchDate < ms) & (m.MatchDate >= ms - pd.Timedelta(days=365 * 4))])
        for div, tdm in tm.groupby('Division'):
            mdl = fit_dc(m[m.Division == div], ms)
            for r in tdm.itertuples():
                ldc = dc_lambdas(mdl, r.HomeTeam, r.AwayTeam)
                if ldc and min(mdl['cnt'].get(r.HomeTeam, 0), mdl['cnt'].get(r.AwayTeam, 0)) < 10: ldc = None
                lel = elo_lambdas(glm, r.HomeElo, r.AwayElo, div) if pd.notna(r.HomeElo) and pd.notna(r.AwayElo) else None
                row = pd.Series(dict(ldc=ldc, lel=lel, lpi=pi_lambdas(pg, r.gd_hat, div)))
                lam = comb(row, w)
                if lam is None: continue
                mk = markets(*lam, mdl['rho'] if mdl else -0.05)
                fh, fa = forma(hist, r.HomeTeam, r.MatchDate), forma(hist, r.AwayTeam, r.MatchDate)
                pf = p_forma(fh, fa) if min(len(fh), len(fa)) >= MIN_M else {}
                oc = outcomes(r.FTHome, r.FTAway, r.HTHome, r.HTAway)
                for k in RYNKI_P48:
                    if k not in MK or oc.get(k) is None: continue
                    pc = kal(k, mk[k])
                    if pc < 0.70: continue
                    out.append((r.MatchDate, div, k, pc, pf.get(k, np.nan), int(oc[k])))
        print(ms.date(), len(out), flush=True)
    d = pd.DataFrame(out, columns=['data', 'liga', 'rynek', 'p_model', 'p_forma', 'traf'])
    d['brak_formy'] = d.p_forma.isna()
    d['zgodne'] = ~d.brak_formy & ((d.p_model - d.p_forma).abs() <= PROG)
    d['p_min'] = np.where(d.zgodne, np.minimum(d.p_model, d.p_forma), np.nan)
    return d


def _ll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def raport(d):
    print(f'\nNOGI z P_model >= 70%: {len(d)} (mecze testowe), zgodne {d.zgodne.sum()} '
          f'({d.zgodne.mean():.0%}), rozbiezne {(~d.zgodne & ~d.brak_formy).sum()}, bez formy {d.brak_formy.sum()}')
    d = d.assign(b=pd.cut(d.p_model, [.70, .75, .80, .85, .90, .95, 1.01], right=False))
    print('\n(1) Trafnosc wg P_model: przepuszczone vs odrzucone (rozbiezne)')
    print(f'  {"P_model":<12}{"n zg.":>8}{"traf zg.":>10}{"n odrz.":>9}{"traf odrz.":>11}{"sr P":>8}')
    for b, g in d.groupby('b', observed=True):
        z, o = g[g.zgodne], g[~g.zgodne & ~g.brak_formy]
        print(f'  {str(b):<12}{len(z):>8}{z.traf.mean():>10.1%}{len(o):>9}{(o.traf.mean() if len(o) else float("nan")):>11.1%}{g.p_model.mean():>8.1%}')
    z = d[d.zgodne]
    print('\n(2) Kalibracja wsrod przepuszczonych: srednie P vs trafnosc')
    print(f'  P_model: sr {z.p_model.mean():.1%} vs traf {z.traf.mean():.1%}   |   min(P): sr {z.p_min.mean():.1%} vs traf {z.traf.mean():.1%}')
    print('\n(3) Brier / log loss (przepuszczone)')
    for n, c in (('P_model', 'p_model'), ('min(P)', 'p_min')):
        print(f'  {n:<8} Brier {((z[c] - z.traf) ** 2).mean():.4f}  log loss {_ll(z[c], z.traf):.4f}')
    o = d[~d.zgodne & ~d.brak_formy]
    if len(o):
        print(f'\n  Odrzucone: sr P_model {o.p_model.mean():.1%}, trafnosc {o.traf.mean():.1%} '
              f'({"gorzej" if o.traf.mean() < o.p_model.mean() else "nie gorzej"} niz P — bramka '
              f'{"odsiewa przeszacowane nogi" if o.traf.mean() < o.p_model.mean() - 0.02 else "NIE odsiewa istotnie gorszych nog"})')


def sporty_wiersze(od='2026-01-01'):
    """To samo dla sporty.py: P faworyta z Elo (calibrate, bez modelu marzy koszykowki), forma = log5 z odsetka
    zwyciestw w 10 ostatnich meczach (jak sporty.drugie_zrodlo). Tylko mecze z >= 6 meczami obu druzyn."""
    import sporty
    d = sporty.load()
    out = []
    for sport in sorted(d.sport.unique()):
        pre = []
        try:
            hfa = sporty.elo(d, sport, pre)[2]
        except Exception as e:
            print(f'  {sport}: pominiety ({type(e).__name__})'); continue
        t = d[d.sport == sport].assign(ra=[x[0] for x in pre], rb=[x[1] for x in pre])
        t = t[(t.data >= od) & (t.pg != t.pa)]
        if len(t) < 200: continue
        x = d[d.sport == sport].sort_values('data')
        hist = {}
        for g, a_, pg, pa, dd in zip(x.gosp, x.gosc, x.pg, x.pa, x.data):
            hist.setdefault(g, ([], []))[0].append(dd); hist[g][1].append(int(pg > pa))
            hist.setdefault(a_, ([], []))[0].append(dd); hist[a_][1].append(int(pa > pg))
        def forma(tm, dd):
            h = hist.get(tm)
            if not h: return 0, 0
            i = bisect_left(h[0], dd); w = h[1][max(0, i - DZ):i]
            return sum(w), len(w)
        for r in t.itertuples():
            e = 1 / (1 + 10 ** ((r.rb - r.ra - hfa) / 400))
            ec = sporty.calibrate(sport, e)[0]
            (wh, nh), (wg, ng) = forma(r.gosp, r.data), forma(r.gosc, r.data)
            if min(nh, ng) < MIN_M: continue
            rh, rg = (wh + 1) / (nh + 2), (wg + 1) / (ng + 2)
            pf_h = rh * (1 - rg) / (rh * (1 - rg) + rg * (1 - rh))
            fav_h = ec >= 0.5
            pm = ec if fav_h else 1 - ec
            pf = pf_h if fav_h else 1 - pf_h
            if pm < 0.70: continue
            zg = (pf >= 0.5) and abs(pm - pf) <= PROG
            out.append((sport, pm, pf, int((r.pg > r.pa) == fav_h), zg))
    d = pd.DataFrame(out, columns=['sport', 'p_model', 'p_forma', 'traf', 'zgodne'])
    d['brak_formy'] = False
    d['p_min'] = np.where(d.zgodne, np.minimum(d.p_model, d.p_forma), np.nan)
    return d


def intl_wiersze(df, od='2024-01-01'):
    """To samo dla reprezentacji (typuj.intl): Elo z intl_elo, Poisson dopasowany na meczach 2010..od (bez przecieku),
    P bez korekty rynkow (jak typuj.intl: tylko −4 pp dla „ponizej”), forma jak drugie_zrodlo() z calej tabeli intl."""
    from typuj import intl_elo
    df = df.dropna(subset=['home_score', 'away_score']).reset_index(drop=True)
    _, pre = intl_elo(df)
    x = np.array([(rh + adv - ra) / 100 for rh, ra, adv in pre])
    def fit(msk, y, sgn):
        X = np.c_[np.ones(msk.sum()), sgn * x[msk]]; b = np.zeros(2)
        for _ in range(30):
            lam = np.exp(X @ b); b += np.linalg.solve((X * lam[:, None]).T @ X, X.T @ (y[msk] - lam))
        return b
    msk = ((df.date >= '2010-01-01') & (df.date < od)).values
    bh = fit(msk, df.home_score.values.astype(float), 1); ba = fit(msk, df.away_score.values.astype(float), -1)
    hist, out = {}, []
    for i, r in enumerate(df.itertuples()):
        hs, as_ = int(r.home_score), int(r.away_score)
        if r.date >= od:
            fh, fa = hist.get(r.home_team, [])[-OKNO:], hist.get(r.away_team, [])[-OKNO:]
            if min(len(fh), len(fa)) >= MIN_M:
                mk = markets(float(np.exp(bh[0] + bh[1] * x[i])), float(np.exp(ba[0] - ba[1] * x[i])), -0.05)
                pf, oc = p_forma(fh, fa), outcomes(hs, as_, np.nan, np.nan)
                for k in RYNKI_P48:
                    if k not in mk or oc.get(k) is None: continue
                    pc = max(mk[k] - 0.04, 0.0) if k.startswith('U') and mk[k] >= 0.5 else mk[k]
                    if pc >= 0.70: out.append((r.date, r.tournament, k, pc, pf[k], int(oc[k])))
        hist.setdefault(r.home_team, []).append((hs, as_)); hist.setdefault(r.away_team, []).append((as_, hs))
    d = pd.DataFrame(out, columns=['data', 'liga', 'rynek', 'p_model', 'p_forma', 'traf'])
    d['brak_formy'] = False
    d['zgodne'] = (d.p_model - d.p_forma).abs() <= PROG
    d['p_min'] = np.where(d.zgodne, np.minimum(d.p_model, d.p_forma), np.nan)
    return d


DZ = OKNO

if __name__ == '__main__':
    a = sys.argv[1:]
    if '--intl' in a:
        d = intl_wiersze(pd.read_sql('select * from intl order by date', sqlite3.connect(os.path.join(HERE, 'kb.sqlite'))),
                         a[a.index('--intl') + 1] if len(a) > a.index('--intl') + 1 else '2024-01-01')
        raport(d)
        print('\nWg rynku (n, sr P, trafnosc, odsetek zgodnych):')
        print(d.groupby('rynek').agg(n=('traf', 'size'), P=('p_model', 'mean'), traf=('traf', 'mean'),
                                     zgodne=('zgodne', 'mean')).sort_values('n', ascending=False).round(3).to_string())
        sys.exit(0)
    if '--sporty' in a:
        d = sporty_wiersze(a[a.index('--sporty') + 1] if len(a) > a.index('--sporty') + 1 else '2026-01-01')
        d.to_csv(os.path.join(HERE, 'bt_drugie_zrodlo_sporty.csv'), index=False)
        raport(d)
        for sp, g in d.groupby('sport'):
            z = g[g.zgodne]
            if len(z) >= 100:
                print(f'  {sp:<16} n={len(g):5d} zgodne {g.zgodne.mean():.0%} | przepuszcz.: P {z.p_model.mean():.1%} '
                      f'min {z.p_min.mean():.1%} traf {z.traf.mean():.1%} | odrzuc.: P {g[~g.zgodne].p_model.mean():.1%} '
                      f'traf {g[~g.zgodne].traf.mean():.1%}')
        sys.exit(0)
    s = a[0] if a else '2026-01-01'
    e = a[1] if len(a) > 1 else str(pd.Timestamp.today().date())
    d = wiersze(s, e)
    d.to_csv(os.path.join(HERE, 'bt_drugie_zrodlo.csv'), index=False)
    raport(d)
