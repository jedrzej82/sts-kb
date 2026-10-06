#!/usr/bin/env python3
"""Backtest rynku „ponizej / powyzej 3.5 gola” w pilce (06.10.2026).
  python3 bt_ou35.py [START=2024-08-01] [KONIEC=2026-09-30] [--intl]

Pytanie uzytkownika po 05.10 (Francja – Belgia i Wlochy – Turcja U3.5 przegrane): czy model dobrze szacuje U3.5/O3.5
we WSZYSTKICH meczach, nie tylko przy P >= 70%. Dla kazdego meczu (walk-forward jak typuj.py / bt_drugie_zrodlo.py):
  p_model  — P(U3.5) po korektach jak w kuponie (korekta_rynkow_v5n.csv, −4 pp „ponizej” przy P >= 50%)
  p_surowe — P(U3.5) prosto z modelu (bez korekt)
  p_rynek  — P(U3.5) wyliczone z kursow rynku na 2.5 gola (raw/Matches.csv): kurs bez marzy -> P(>= 3 gole) ->
             oczekiwana liczba goli (Poisson) -> P(<= 3 gole). Kursow na 3.5 w historii nie ma; to przyblizenie
             rynku, sprawdzane tez samo (kalibracja p_rynek).
Raport: kalibracja w przedzialach P (cala skala), Brier/log loss, mieszanka w*p_model + (1-w)*p_rynek z w dobranym
na 1. polowie okresu i sprawdzonym na 2. (bez przecieku), wyniki wg grupy lig (srednia goli ligi).
--intl: reprezentacje (typuj.intl), bez kursow — tylko kalibracja."""
import json
import math
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

from bt_drugie_zrodlo import korekta
from ensemble import comb
from model import fit_dc, dc_lambdas, fit_elo_glm, elo_lambdas, markets
from pi import prepare, fit_pi_glm, pi_lambdas

HERE = os.path.dirname(os.path.abspath(__file__))


def p_ponizej(lam, k=3):
    """P(Poisson(lam) <= k)."""
    return sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(k + 1))


def lam_z_over25(p_o25):
    """Oczekiwana liczba goli, przy ktorej P(Poisson >= 3) = p_o25 (bisekcja)."""
    lo, hi = 0.05, 8.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if 1 - p_ponizej(mid, 2) < p_o25: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def p_rynku_u35(over25, under25):
    """Kursy rynku na 2.5 gola -> P(U3.5) wg rynku (przyblizenie Poissona). None, gdy brak kursow."""
    if not (pd.notna(over25) and pd.notna(under25) and over25 > 1 and under25 > 1): return None
    p_o = (1 / over25) / (1 / over25 + 1 / under25)
    return p_ponizej(lam_z_over25(p_o), 3)


def wiersze(start, koniec):
    m = pd.read_sql('select * from matches', sqlite3.connect(os.path.join(HERE, 'kb.sqlite')), parse_dates=['MatchDate'])
    m = m.dropna(subset=['FTHome', 'FTAway']).sort_values('MatchDate')
    m, _, _ = prepare(m)
    kursy = {}
    p = os.path.join(HERE, 'raw', 'Matches.csv')
    if os.path.exists(p):
        k = pd.read_csv(p, low_memory=False, usecols=['Division', 'MatchDate', 'HomeTeam', 'AwayTeam', 'Over25', 'Under25'])
        k = k[(k.MatchDate >= start) & (k.MatchDate <= koniec)]
        kursy = {(r.Division, pd.Timestamp(r.MatchDate), r.HomeTeam, r.AwayTeam): p_rynku_u35(r.Over25, r.Under25)
                 for r in k.itertuples()}
    w = tuple(json.load(open(os.path.join(HERE, 'ensemble_wagi.json')))['wagi_dc_elo_pi'])
    kal = korekta(pd.read_csv(os.path.join(HERE, 'korekta_rynkow_v5n.csv')))
    glm = fit_elo_glm(m[m.MatchDate < start])
    out = []
    for ms in pd.date_range(start, koniec, freq='MS'):
        tm = m[(m.MatchDate >= ms) & (m.MatchDate < ms + pd.offsets.MonthBegin(1))]
        if tm.empty: continue
        pg = fit_pi_glm(m[(m.MatchDate < ms) & (m.MatchDate >= ms - pd.Timedelta(days=365 * 4))])
        for div, tdm in tm.groupby('Division'):
            dm = m[m.Division == div]
            mdl = fit_dc(dm, ms)
            hist = dm[(dm.MatchDate < ms) & (dm.MatchDate >= ms - pd.Timedelta(days=365))]
            sr_lig = float((hist.FTHome + hist.FTAway).mean()) if len(hist) >= 30 else np.nan
            for r in tdm.itertuples():
                ldc = dc_lambdas(mdl, r.HomeTeam, r.AwayTeam)
                if ldc and min(mdl['cnt'].get(r.HomeTeam, 0), mdl['cnt'].get(r.AwayTeam, 0)) < 10: ldc = None
                lel = elo_lambdas(glm, r.HomeElo, r.AwayElo, div) if pd.notna(r.HomeElo) and pd.notna(r.AwayElo) else None
                lam = comb(pd.Series(dict(ldc=ldc, lel=lel, lpi=pi_lambdas(pg, r.gd_hat, div))), w)
                if lam is None: continue
                mk = markets(*lam, mdl['rho'] if mdl else -0.05)
                out.append((r.MatchDate, div, kal('U3.5', mk['U3.5']), mk['U3.5'], sum(lam), sr_lig,
                            kursy.get((div, r.MatchDate, r.HomeTeam, r.AwayTeam)), int(r.FTHome + r.FTAway <= 3)))
        print(ms.date(), len(out), flush=True)
    return pd.DataFrame(out, columns=['data', 'liga', 'p_model', 'p_surowe', 'lam', 'sr_ligi', 'p_rynek', 'u35'])


def intl_wiersze(od='2022-01-01'):
    # jak bt_drugie_zrodlo.intl_wiersze, ale WSZYSTKIE mecze (tam tylko nogi z P >= 70%)
    from typuj import intl_elo
    df = pd.read_sql('select * from intl order by date', sqlite3.connect(os.path.join(HERE, 'kb.sqlite')))
    df = df.dropna(subset=['home_score', 'away_score']).reset_index(drop=True)
    _, pre = intl_elo(df)
    x = np.array([(rh + adv - ra) / 100 for rh, ra, adv in pre])
    def fit(msk, y, sgn):
        X = np.c_[np.ones(msk.sum()), sgn * x[msk]]; bb = np.zeros(2)
        for _ in range(30):
            l = np.exp(X @ bb); bb += np.linalg.solve((X * l[:, None]).T @ X, X.T @ (y[msk] - l))
        return bb
    msk = ((df.date >= '2010-01-01') & (df.date < od)).values
    bh = fit(msk, df.home_score.values.astype(float), 1); ba = fit(msk, df.away_score.values.astype(float), -1)
    out = []
    for i, r in enumerate(df.itertuples()):
        if r.date < od: continue
        lh, la = float(np.exp(bh[0] + bh[1] * x[i])), float(np.exp(ba[0] - ba[1] * x[i]))
        mk = markets(lh, la, -0.05)
        pu = mk['U3.5']; pc = max(pu - 0.04, 0.0) if pu >= 0.5 else pu
        out.append((pd.Timestamp(r.date), r.tournament, pc, pu, lh + la, np.nan, None, int(r.home_score + r.away_score <= 3)))
    return pd.DataFrame(out, columns=['data', 'liga', 'p_model', 'p_surowe', 'lam', 'sr_ligi', 'p_rynek', 'u35'])


def _ll(p, y):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def kalibracja(d, kol, nazwa):
    print(f'\n  {nazwa} — U3.5: srednie P vs trafnosc (O3.5 = 1 − U3.5)')
    b = pd.cut(d[kol], [0, .3, .4, .5, .6, .7, .8, .9, 1.0])
    for przedzial, g in d.groupby(b, observed=True):
        print(f'    P {str(przedzial):<12} n={len(g):6}  P {g[kol].mean():6.1%}  trafnosc {g.u35.mean():6.1%}  '
              f'roznica {(g.u35.mean() - g[kol].mean()) * 100:+5.1f} pp')
    print(f'    Brier {((d[kol] - d.u35) ** 2).mean():.4f}  log loss {_ll(d[kol], d.u35):.4f}')


def raport(d, intl=False):
    print(f'\nMECZE: {len(d)}  ({d.data.min():%Y-%m-%d} – {d.data.max():%Y-%m-%d}), U3.5 weszlo w {d.u35.mean():.1%}')
    kalibracja(d, 'p_model', 'P_model (po korektach, jak w kuponie)')
    kalibracja(d, 'p_surowe', 'P_model surowe (bez korekt)')
    if intl:
        print('\n  wg turnieju (n >= 150):')
        for t, g in d.groupby('liga'):
            if len(g) >= 150:
                print(f'    {t[:40]:<40} n={len(g):5}  P {g.p_model.mean():6.1%}  trafnosc {g.u35.mean():6.1%}')
        return
    r = d.dropna(subset=['p_rynek']).copy()
    if len(r):
        print(f'\n  MECZE Z KURSAMI RYNKU: {len(r)}')
        kalibracja(r, 'p_rynek', 'P_rynku (z kursow na 2.5, Poisson)')
        kalibracja(r, 'p_model', 'P_model na tych samych meczach')
        pol = r.data.quantile(0.5)
        a, t = r[r.data < pol], r[r.data >= pol]
        wyn = []
        for wm in np.round(np.arange(0, 1.01, 0.1), 1):
            pa = wm * a.p_model + (1 - wm) * a.p_rynek
            wyn.append((wm, _ll(pa, a.u35)))
        wbest = min(wyn, key=lambda x: x[1])[0]
        print(f'\n  Mieszanka w*P_model + (1-w)*P_rynku: w dobrane na 1. polowie (do {pol:%Y-%m-%d}) = {wbest}')
        for wm in sorted({0.0, wbest, 1.0}):
            pt = wm * t.p_model + (1 - wm) * t.p_rynek
            print(f'    test (2. polowa, n={len(t)}): w={wm:.1f}  Brier {((pt - t.u35) ** 2).mean():.4f}  log loss {_ll(pt, t.u35):.4f}')
        for nazwa, x in (('P_model >= 70%', r[r.p_model >= .7]), ('P_rynku >= 70%', r[r.p_rynek >= .7]),
                         ('model >= rynek + 5 pp', r[r.p_model - r.p_rynek >= .05]),
                         ('model <= rynek − 5 pp', r[r.p_model - r.p_rynek <= -.05])):
            if len(x):
                print(f'    {nazwa:<24} n={len(x):5}  P_model {x.p_model.mean():6.1%}  P_rynku {x.p_rynek.mean():6.1%}  '
                      f'trafnosc {x.u35.mean():6.1%}')
    print('\n  Wg sredniej goli ligi (ostatnie 12 mies.):')
    for nazwa, x in (('< 2.4', d[d.sr_ligi < 2.4]), ('2.4–2.8', d[(d.sr_ligi >= 2.4) & (d.sr_ligi < 2.8)]),
                     ('2.8–3.2', d[(d.sr_ligi >= 2.8) & (d.sr_ligi < 3.2)]), ('>= 3.2', d[d.sr_ligi >= 3.2])):
        if len(x):
            k = x[x.p_model >= .7]
            print(f'    srednia {nazwa:<8} n={len(x):6}  P {x.p_model.mean():6.1%}  traf {x.u35.mean():6.1%}  |  '
                  f'P>=70%: n={len(k):5}  P {k.p_model.mean() if len(k) else float("nan"):6.1%}  traf {k.u35.mean() if len(k) else float("nan"):6.1%}')


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if '--intl' in sys.argv:
        raport(intl_wiersze(a[0] if a else '2022-01-01'), intl=True)
    else:
        d = wiersze(a[0] if a else '2024-08-01', a[1] if len(a) > 1 else '2026-09-30')
        d.to_csv('bt_ou35_wiersze.csv.gz', index=False)
        raport(d)
