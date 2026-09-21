#!/usr/bin/env python3
"""Eksport wiedzy do plików na Drive: profil każdej aktywnej drużyny + parametry lig. python3 eksport.py"""
import os, sqlite3, datetime as dt, numpy as np, pandas as pd
from model import fit_dc

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out'); os.makedirs(OUT, exist_ok=True)
con = sqlite3.connect(os.path.join(HERE, 'kb.sqlite'))
m = pd.read_sql('select * from matches', con, parse_dates=['MatchDate'])
elo = pd.read_sql('select club, elo, date from clubelo', con).sort_values('date').groupby('club').last()
today = pd.Timestamp(dt.date.today())
act = m[m.MatchDate >= today - pd.Timedelta(days=300)]
rows, lrows = [], []
for div, g in act.groupby('Division'):
    mdl = fit_dc(m[m.Division == div], today)
    lg = m[(m.Division == div) & (m.MatchDate >= today - pd.Timedelta(days=730))]
    t = lg.FTHome + lg.FTAway
    lrows.append(dict(liga=div, mecze=len(lg), gole_śr=round(t.mean(), 2), dom_W=round((lg.FTHome > lg.FTAway).mean(), 3),
                      remis=round((lg.FTHome == lg.FTAway).mean(), 3), O15=round((t > 1.5).mean(), 3), O25=round((t > 2.5).mean(), 3),
                      U35=round((t < 3.5).mean(), 3), BTTS=round(((lg.FTHome > 0) & (lg.FTAway > 0)).mean(), 3),
                      dc_home=round(float(mdl['home']), 3) if mdl else None, dc_rho=round(float(mdl['rho']), 3) if mdl else None))
    last_div = pd.concat([m[['MatchDate','HomeTeam','Division']].rename(columns={'HomeTeam':'t'}), m[['MatchDate','AwayTeam','Division']].rename(columns={'AwayTeam':'t'})]).sort_values('MatchDate').groupby('t').Division.last() if 'last_div' not in dir() else last_div
    for team in sorted(set(g.HomeTeam) | set(g.AwayTeam)):
        if last_div.get(team) != div: continue
        tm = m[(m.HomeTeam == team) | (m.AwayTeam == team)].sort_values('MatchDate').tail(20)
        hm = tm.HomeTeam == team
        gf = np.where(hm, tm.FTHome, tm.FTAway); ga = np.where(hm, tm.FTAway, tm.FTHome); tot = gf + ga
        l10 = slice(-10, None)
        res = np.where(gf > ga, 'W', np.where(gf == ga, 'D', 'L'))
        cf = np.where(hm, tm.HomeCorners, tm.AwayCorners).astype(float)
        yc = np.where(hm, tm.HomeYellow, tm.AwayYellow).astype(float)
        i = mdl['teams'].get(team) if mdl and mdl['cnt'].get(team, 0) >= 10 else None
        rows.append(dict(liga=div, drużyna=team, elo=round(elo.elo.get(team, np.nan), 0),
                         dc_atak=round(float(mdl['att'][i]), 3) if i is not None else None,
                         dc_obrona=round(float(mdl['dfn'][i]), 3) if i is not None else None,
                         forma10=''.join(res[l10]), gole10=f'{int(gf[l10].sum())}:{int(ga[l10].sum())}',
                         O15_20=round((tot > 1.5).mean(), 2), O25_20=round((tot > 2.5).mean(), 2), U35_20=round((tot < 3.5).mean(), 2),
                         BTTS_20=round(((gf > 0) & (ga > 0)).mean(), 2), CS_20=round((ga == 0).mean(), 2), bez_gola_20=round((gf == 0).mean(), 2),
                         rożne_śr=round(np.nanmean(cf), 1) if np.isfinite(cf).any() else None,
                         żółte_śr=round(np.nanmean(yc), 1) if np.isfinite(yc).any() else None,
                         ostatni=str(tm.MatchDate.max().date())))
d = str(today.date())
pd.DataFrame(rows).to_csv(os.path.join(OUT, f'wiedza_druzyny_{d}.csv'), index=False)
pd.DataFrame(lrows).to_csv(os.path.join(OUT, f'wiedza_ligi_{d}.csv'), index=False)
print(len(rows), 'drużyn,', len(lrows), 'lig →', OUT)
