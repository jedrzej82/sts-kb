#!/usr/bin/env python3
"""Backtest z KURSAMI: czy noga, w ktorej model daje wyraznie wiecej niz rynek, zarabia (05.10.2026).
  python3 bt_model_rynek.py [START=2025-08-01] [KONIEC=2026-09-30]

Pytanie z przegladu kuponow papierowych 20.09-04.10: nogi z P_model >= P_rynku + 5 pp daly +2,9% po podatku,
nogi zgodne z rynkiem -10,5% (n=79 / 158 — za malo na decyzje). Tu to samo na pelnej historii lig z kursami.

P_model — jak typuj.py / bt_drugie_zrodlo.py: zespol DC+Elo+pi (ensemble_wagi.json), korekta_rynkow_v5n.csv,
  -4 pp dla „ponizej”; walk-forward (model dopasowany na danych sprzed miesiaca meczu).
Kursy — raw/Matches.csv (srednie rynkowe 1X2 i 2.5 gola, ~22 ligi europejskie). P_rynku = kurs bez marzy
  (proporcjonalnie). Podwojna szansa: kurs syntetyczny 1/(1/k_a + 1/k_b) — ta sama marza co 1X2 (przyblizenie).
Zwrot = P(traf) * kurs * 0,88 - 1 (podatek 12% jak w STS). Kursy srednie rynku sa WYZSZE niz w STS, wiec zwroty
  sa optymistyczne — liczy sie ROZNICA miedzy progami, nie poziom.
Nogi: P_model >= 0,70 (kupony) — wynik wg roznicy P_model - P_rynku, z/bez filtra 6.4 (|roznica| <= 15 pp) i EV > 0."""
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

from bt_drugie_zrodlo import korekta
from ensemble import comb, outcomes
from model import fit_dc, dc_lambdas, fit_elo_glm, elo_lambdas, markets
from pi import prepare, fit_pi_glm, pi_lambdas

HERE = os.path.dirname(os.path.abspath(__file__))
TAX = 0.88
RYNKI = ['1', 'X', '2', '1X', 'X2', '12', 'O2.5', 'U2.5']


def kursy_rynku(r):
    """Wiersz Matches.csv -> {rynek: (kurs, P_rynku bez marzy)}; brak kursow -> {}."""
    o1, ox, o2, ov, un = r.OddHome, r.OddDraw, r.OddAway, r.Over25, r.Under25
    out = {}
    if all(pd.notna(x) and x > 1 for x in (o1, ox, o2)):
        i1, ix, i2 = 1 / o1, 1 / ox, 1 / o2
        s = i1 + ix + i2
        out.update({'1': (o1, i1 / s), 'X': (ox, ix / s), '2': (o2, i2 / s),
                    '1X': (1 / (i1 + ix), (i1 + ix) / s), 'X2': (1 / (ix + i2), (ix + i2) / s),
                    '12': (1 / (i1 + i2), (i1 + i2) / s)})
    if all(pd.notna(x) and x > 1 for x in (ov, un)):
        s = 1 / ov + 1 / un
        out.update({'O2.5': (ov, 1 / ov / s), 'U2.5': (un, 1 / un / s)})
    return out


def wiersze(start, koniec):
    m = pd.read_sql('select * from matches', sqlite3.connect(os.path.join(HERE, 'kb.sqlite')), parse_dates=['MatchDate'])
    m = m.dropna(subset=['FTHome', 'FTAway']).sort_values('MatchDate')
    m, _, _ = prepare(m)
    k = pd.read_csv(os.path.join(HERE, 'raw', 'Matches.csv'), low_memory=False,
                    usecols=['Division', 'MatchDate', 'HomeTeam', 'AwayTeam', 'OddHome', 'OddDraw', 'OddAway', 'Over25', 'Under25'])
    k = k[(k.MatchDate >= start) & (k.MatchDate <= koniec)].dropna(subset=['OddHome'])
    k['MatchDate'] = pd.to_datetime(k.MatchDate)
    kursy = {(r.Division, r.MatchDate, r.HomeTeam, r.AwayTeam): kursy_rynku(r) for r in k.itertuples()}
    w = tuple(json.load(open(os.path.join(HERE, 'ensemble_wagi.json')))['wagi_dc_elo_pi'])
    kal = korekta(pd.read_csv(os.path.join(HERE, 'korekta_rynkow_v5n.csv')))
    glm = fit_elo_glm(m[m.MatchDate < start])
    out, bez = [], 0
    for ms in pd.date_range(start, koniec, freq='MS'):
        tm = m[(m.MatchDate >= ms) & (m.MatchDate < ms + pd.offsets.MonthBegin(1)) & m.Division.isin(set(k.Division))]
        if tm.empty: continue
        pg = fit_pi_glm(m[(m.MatchDate < ms) & (m.MatchDate >= ms - pd.Timedelta(days=365 * 4))])
        for div, tdm in tm.groupby('Division'):
            mdl = fit_dc(m[m.Division == div], ms)
            for r in tdm.itertuples():
                kr = kursy.get((div, r.MatchDate, r.HomeTeam, r.AwayTeam))
                if not kr: bez += 1; continue
                ldc = dc_lambdas(mdl, r.HomeTeam, r.AwayTeam)
                if ldc and min(mdl['cnt'].get(r.HomeTeam, 0), mdl['cnt'].get(r.AwayTeam, 0)) < 10: ldc = None
                lel = elo_lambdas(glm, r.HomeElo, r.AwayElo, div) if pd.notna(r.HomeElo) and pd.notna(r.AwayElo) else None
                lam = comb(pd.Series(dict(ldc=ldc, lel=lel, lpi=pi_lambdas(pg, r.gd_hat, div))), w)
                if lam is None: continue
                mk = markets(*lam, mdl['rho'] if mdl else -0.05)
                oc = outcomes(r.FTHome, r.FTAway, r.HTHome, r.HTAway)
                for rk in RYNKI:
                    if rk not in kr or oc.get(rk) is None: continue
                    out.append((r.MatchDate, div, rk, kal(rk, mk[rk]), kr[rk][1], kr[rk][0], int(oc[rk])))
        print(ms.date(), len(out), flush=True)
    print(f'mecze bez kursow (pominiete): {bez}')
    return pd.DataFrame(out, columns=['data', 'liga', 'rynek', 'p_model', 'p_rynek', 'kurs', 'traf'])


def tabela(d, nazwa):
    d = d.assign(zwrot=d.traf * d.kurs * TAX - 1)
    print(f'  {nazwa:<44} n={len(d):6}  P_model {d.p_model.mean():6.1%}  P_rynku {d.p_rynek.mean():6.1%}  '
          f'trafnosc {d.traf.mean():6.1%}  zwrot/noge {d.zwrot.mean():+6.1%}  (blad std {d.zwrot.std() / np.sqrt(max(len(d), 1)):.1%})')


def raport(d):
    d = d.assign(roz=d.p_model - d.p_rynek, ev=d.p_model * d.kurs * TAX - 1)
    k = d[d.p_model >= 0.70]
    print(f'\nNOGI z P_model >= 70%: {len(k)}  (wszystkie rynki: {len(d)})')
    print(f'Brier P_model {((k.p_model - k.traf) ** 2).mean():.4f} | P_rynku {((k.p_rynek - k.traf) ** 2).mean():.4f}')
    print('\n(1) Wg roznicy P_model - P_rynku')
    for lo, hi in ((-1, -.05), (-.05, 0), (0, .05), (.05, .10), (.10, .15), (.15, 1)):
        tabela(k[(k.roz >= lo) & (k.roz < hi)], f'roznica [{lo * 100:+.0f}, {hi * 100:+.0f}) pp')
    print('\n(2) Reguly (z filtrem 6.4: |roznica| <= 15 pp)')
    f64 = k.roz.abs() <= .15
    tabela(k[f64], 'dzis: P>=70% + filtr 6.4')
    tabela(k[f64 & (k.ev > 0)], 'dzis + EV > 0')
    for prog in (.03, .05, .08):
        tabela(k[f64 & (k.roz >= prog)], f'+ wymog P_model >= P_rynku + {prog * 100:.0f} pp')
    print('\n(3) Wymog +5 pp wg rynku')
    for rk, g in k[f64].groupby('rynek'):
        tabela(g[g.roz >= .05], f'{rk}: z wymogiem +5 pp'); tabela(g[g.roz < .05], f'{rk}: bez (reszta)')
    print('\n(4) Stabilnosc w czasie (z wymogiem +5 pp, filtr 6.4)')
    x = k[f64 & (k.roz >= .05)]
    for q, g in x.groupby(x.data.dt.to_period('Q')):
        tabela(g, str(q))


if __name__ == '__main__':
    a = sys.argv[1:]
    raport(wiersze(a[0] if a else '2025-08-01', a[1] if len(a) > 1 else '2026-09-30'))
