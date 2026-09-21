#!/usr/bin/env python3
"""Buduje bazę meczów: GitHub (xgabora 2000-2026 + openfootball bieżący sezon + reprezentacje) + delta.csv z Drive.
Wynik: kb.sqlite (tabele: matches, intl). Użycie: python3 build_kb.py [--refresh]"""
import os, sys, json, glob, re, sqlite3, subprocess, difflib, unicodedata
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
os.makedirs(RAW, exist_ok=True)
SRC = {
    'Matches.csv': 'https://raw.githubusercontent.com/xgabora/Club-Football-Match-Data-2000-2025/main/data/Matches.csv',
    'EloRatings.csv': 'https://raw.githubusercontent.com/xgabora/Club-Football-Match-Data-2000-2025/main/data/EloRatings.csv',
    'intl_results.csv': 'https://raw.githubusercontent.com/martj42/international_results/master/results.csv',
}
OF_MAP = {'en.1': 'E0', 'en.2': 'E1', 'en.3': 'E2', 'en.4': 'E3', 'es.1': 'SP1', 'es.2': 'SP2', 'de.1': 'D1',
          'de.2': 'D2', 'it.1': 'I1', 'it.2': 'I2', 'fr.1': 'F1', 'fr.2': 'F2', 'nl.1': 'N1', 'pt.1': 'P1',
          'be.1': 'B1', 'sco.1': 'SC0', 'tr.1': 'T1', 'gr.1': 'G1'}
DIV_NAME = {'E0': 'Anglia Premier League', 'E1': 'Anglia Championship', 'E2': 'Anglia League One', 'E3': 'Anglia League Two',
            'EC': 'Anglia National League', 'SP1': 'Hiszpania LaLiga', 'SP2': 'Hiszpania Segunda', 'I1': 'Włochy Serie A',
            'I2': 'Włochy Serie B', 'D1': 'Niemcy Bundesliga', 'D2': 'Niemcy 2. Bundesliga', 'F1': 'Francja Ligue 1',
            'F2': 'Francja Ligue 2', 'N1': 'Holandia Eredivisie', 'P1': 'Portugalia Liga', 'B1': 'Belgia Pro League',
            'T1': 'Turcja Super Lig', 'G1': 'Grecja Super League', 'SC0': 'Szkocja Premiership', 'SC1': 'Szkocja Championship',
            'SC2': 'Szkocja League One', 'SC3': 'Szkocja League Two', 'ARG': 'Argentyna', 'AUT': 'Austria', 'BRA': 'Brazylia',
            'CHN': 'Chiny', 'DEN': 'Dania', 'FIN': 'Finlandia', 'IRL': 'Irlandia', 'JAP': 'Japonia', 'MEX': 'Meksyk',
            'NOR': 'Norwegia', 'POL': 'Polska Ekstraklasa', 'ROM': 'Rumunia', 'RUS': 'Rosja', 'SUI': 'Szwajcaria',
            'SWE': 'Szwecja', 'USA': 'USA MLS'}


def fetch(refresh):
    for fn, url in SRC.items():
        p = os.path.join(RAW, fn)
        if refresh or not os.path.exists(p):
            subprocess.run(['curl', '-s', '-m', '300', '-o', p, url], check=True)
    of = os.path.join(RAW, 'football.json')
    if not os.path.exists(of):
        subprocess.run(['git', 'clone', '-q', '--depth', '1', 'https://github.com/openfootball/football.json.git', of], check=True)
    elif refresh:
        subprocess.run(['git', '-C', of, 'pull', '-q'], check=False)


def norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r"\b(fc|cf|afc|ac|sc|ssc|as|us|ud|cd|rc|rcd|sd|ca|sv|vfl|vfb|tsg|fk|sk|bk|if|club|calcio|balompie|de|futbol|football|1\.|\d{4})\b", ' ', s)
    return re.sub(r'[^a-z]', '', s)


ALIAS = {'Athletic Club': 'Ath Bilbao', 'Borussia Mönchengladbach': "M'gladbach", 'FC Internazionale Milano': 'Inter',
         'NEC': 'Nijmegen', 'Queens Park Rangers FC': 'QPR', 'Sporting Clube de Braga': 'Sp Braga',
         'Sporting Clube de Portugal': 'Sp Lisbon', 'Stade Rennais FC 1901': 'Rennes', 'Wolverhampton Wanderers FC': 'Wolves'}


def map_names(of_names, base_names):
    base = {norm(b): b for b in base_names}
    out = {}
    for n in of_names:
        if n in ALIAS and ALIAS[n] in base_names:
            out[n] = ALIAS[n]; continue
        k = norm(n)
        if k in base:
            out[n] = base[k]; continue
        cand = [b for kb, b in base.items() if kb and (kb in k or k in kb)]
        if len(cand) == 1:
            out[n] = cand[0]; continue
        m = difflib.get_close_matches(k, list(base), n=1, cutoff=0.6)
        out[n] = base[m[0]] if m else None
    return out


def openfootball_rows(m):
    rows, unmatched = [], set()
    for f in sorted(glob.glob(os.path.join(RAW, 'football.json', '202[56]-2[67]', '*.json'))):
        code = os.path.basename(f).replace('.json', '')
        if code not in OF_MAP: continue
        div = OF_MAP[code]
        last = m.loc[m.Division == div, 'MatchDate'].max()
        j = json.load(open(f))
        ms = [x for x in j.get('matches', []) if isinstance(x.get('score'), dict) and x['score'].get('ft')
              and x['date'] > last]
        if not ms: continue
        recent = m[(m.Division == div) & (m.MatchDate >= '2025-07-01')]
        names = set(recent.HomeTeam) | set(recent.AwayTeam)
        mp = map_names({x['team1'] for x in ms} | {x['team2'] for x in ms}, names)
        for x in ms:
            h, a = mp.get(x['team1']), mp.get(x['team2'])
            if not h or not a:
                unmatched.update([t for t, v in ((x['team1'], h), (x['team2'], a)) if not v]); continue
            ht = x['score'].get('ht') or [None, None]
            rows.append(dict(Division=div, MatchDate=x['date'], MatchTime=x.get('time'), HomeTeam=h, AwayTeam=a,
                             FTHome=x['score']['ft'][0], FTAway=x['score']['ft'][1], HTHome=ht[0], HTAway=ht[1], src='openfootball'))
    return pd.DataFrame(rows), unmatched


def main():
    fetch('--refresh' in sys.argv)
    cols = ['Division', 'MatchDate', 'MatchTime', 'HomeTeam', 'AwayTeam', 'HomeElo', 'AwayElo', 'FTHome', 'FTAway',
            'HTHome', 'HTAway', 'HomeShots', 'AwayShots', 'HomeTarget', 'AwayTarget', 'HomeCorners', 'AwayCorners',
            'HomeYellow', 'AwayYellow', 'HomeRed', 'AwayRed', 'HomeFouls', 'AwayFouls']
    m = pd.read_csv(os.path.join(RAW, 'Matches.csv'), usecols=cols, low_memory=False)  # kursy celowo pominięte
    m = m.dropna(subset=['FTHome', 'FTAway'])
    m['src'] = 'xgabora'
    of, unmatched = openfootball_rows(m)
    parts = [m, of]
    delta = os.path.join(HERE, 'delta.csv')  # wyniki dopisywane przez zadania 12/15/18/21 (z Drive)
    if os.path.exists(delta):
        d = pd.read_csv(delta); d['src'] = 'delta'; parts.append(d)
    extra = os.path.join(HERE, 'ligi_extra.csv')  # uzupelnij_ligi.py: FBref (worldfootballR_data) + openfootball + matryce Wikipedii
    if os.path.exists(extra):
        e = pd.read_csv(extra); e['src'] = 'extra'; parts.append(e)
        try:
            from uzupelnij_ligi import NOWE; DIV_NAME.update({k: v for k, v in NOWE.items() if k not in DIV_NAME})
        except Exception: pass
    allm = pd.concat(parts, ignore_index=True)
    allm = allm.drop_duplicates(subset=['Division', 'MatchDate', 'HomeTeam', 'AwayTeam'], keep='first')
    DIV_NAME.update({d: d for d in allm.Division.dropna().unique() if d not in DIV_NAME})  # ligi z Sofascore: „Kraj | Liga”
    allm = allm.sort_values(['MatchDate', 'Division']).reset_index(drop=True)
    intl = pd.read_csv(os.path.join(RAW, 'intl_results.csv')).dropna(subset=['home_score', 'away_score'])
    elo = pd.read_csv(os.path.join(RAW, 'EloRatings.csv'))
    db = sqlite3.connect(os.path.join(HERE, 'kb.sqlite'))
    allm.to_sql('matches', db, if_exists='replace', index=False)
    intl.to_sql('intl', db, if_exists='replace', index=False)
    elo.to_sql('clubelo', db, if_exists='replace', index=False)
    pd.DataFrame(list(DIV_NAME.items()), columns=['Division', 'Name']).to_sql('divisions', db, if_exists='replace', index=False)
    db.execute('CREATE INDEX IF NOT EXISTS ix_m ON matches(Division, MatchDate)')
    db.commit()
    print(f'matches={len(allm)} (openfootball+{len(of)}), intl={len(intl)}, clubelo={len(elo)}, ostatni mecz={allm.MatchDate.max()}')
    if unmatched: print('Niedopasowane nazwy:', sorted(unmatched))


if __name__ == '__main__':
    main()
