#!/usr/bin/env python3
"""Import historycznych wyników wszystkich sportów spoza piłki z publicznych repozytoriów GitHub (bez kursów) → cache CSV.
  sporty_hist.csv  — NBA 2002–dziś, WNBA 2002–dziś, NHL 2002–dziś (sportsdataverse, paczki releases aktualizowane na bieżąco),
                     NFL 1999–dziś (nflverse), MLB 2000–dziś (retrosheet + baseballr-data), CS2 2023–dziś (HLTV), LoL 2024–dziś (Oracle's Elixir, mapy),
                     + ligi europejskie z sporty_eu.csv (wyniki zebrane z Wikipedii itp. — patrz eu_import w README)
                     KBO+NPB 2021–dziś (dentearl), snooker 1990–dziś (snookerdb/CueTracker), UFC 1994–dziś (ufcstats),
                     dart PDC 2026 (dartsorakel przez walker95sam/darts), rugby union 2002–dziś (Rugby-Data)
  tenis_hist.csv   — ATP i WTA 1968–dziś (LuckyLoser91/TennisCourtLog, format Sackmanna, aktualizowane co tydzień)
Kolumna dogrywka: 1 = dogrywka/karne/dodatkowe inningi, 0 = regulaminowy czas, -1 = nieznane.
  python3 hist_import.py          — pobiera/aktualizuje źródła i przebudowuje cache (ok. 2–3 min)"""
import os, glob, subprocess, datetime as dt, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); RAW = os.path.join(HERE, 'raw'); REL = os.path.join(RAW, 'rel')
REPOS = {'hoopR-data': ('sportsdataverse/hoopR-data', 'nba/schedules/csv/*'),
         'fastRhockey-data': ('sportsdataverse/fastRhockey-data', 'nhl/schedules/csv/*'),
         'retrosheet': ('chadwickbureau/retrosheet', 'seasons/20*/GL20*.TXT'),
         'baseballr-data': ('sportsdataverse/baseballr-data', 'mlb/schedule/20*.parquet'),
         'cs2_pred': ('ppxdpp17/CS2-Predictor', 'data/matches_clean.csv'),
         'esports_oracle': ('ChenxingJi-Innovate/Esports-Oracle', 'data/processed/*.csv'),
         'kbo': ('dentearl/kbo-data', 'data/kbo/*.json'), 'npb': ('dentearl/npb-data', 'data/npb/*.json'),
         'snookerdb': ('obrienjoey/snookerdb', 'Parquet/*.parquet'),
         'ufc': ('Greco1899/scrape_ufc_stats', '*.csv'),
         'rugby': ('transientlunatic/Rugby-Data', 'json/*.json')}
SDV = 'https://github.com/sportsdataverse/sportsdataverse-data/releases/download'
TCL = 'https://media.githubusercontent.com/media/LuckyLoser91/TennisCourtLog/main'
COLS = ['data', 'sport', 'liga', 'gosp', 'gosc', 'pg', 'pa', 'dogrywka']
YEAR = dt.date.today().year
NHL_FIX = {'NYI': 'New York Islanders', 'NYR': 'New York Rangers', 'NJD': 'New Jersey Devils', 'LAK': 'Los Angeles Kings', 'UTA': 'Utah Mammoth', 'ARI': 'Arizona Coyotes', 'PHX': 'Arizona Coyotes', 'ATL': 'Atlanta Thrashers', 'SEA': 'Seattle Kraken'}


def sh(*a): subprocess.run(list(a), check=False)


def get(url, path, force=False):
    if force or not os.path.exists(path) or os.path.getsize(path) == 0:
        sh('curl', '-sLf', '-m', '120', '-o', path, url)
    return os.path.exists(path) and os.path.getsize(path) > 0


def fetch():
    os.makedirs(REL, exist_ok=True)
    for d, (repo, pat) in REPOS.items():
        p = os.path.join(RAW, d)
        if not os.path.exists(p):
            sh('git', 'clone', '-q', '--depth', '1', '--filter=blob:none', '--no-checkout', f'https://github.com/{repo}', p)
            sh('git', '-C', p, 'sparse-checkout', 'set', '--no-cone', pat); sh('git', '-C', p, 'checkout', '-q', 'HEAD')
        else:
            sh('git', '-C', p, 'pull', '-q')
    get('https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv', os.path.join(RAW, 'nfl_games.csv'), force=True)
    for y in range(2002, YEAR + 2):  # bieżący i przyszły sezon zawsze świeżo
        f = y >= YEAR
        get(f'{SDV}/espn_nba_schedules/nba_schedule_{y}.parquet', os.path.join(REL, f'nba_{y}.parquet'), f)
        get(f'{SDV}/espn_wnba_schedules/wnba_schedule_{y}.parquet', os.path.join(REL, f'wnba_{y}.parquet'), f)
        get(f'{SDV}/nhl_schedules/nhl_schedule_{y}.parquet', os.path.join(REL, f'nhl_{y}.parquet'), f)
    td = os.path.join(RAW, 'tcl'); os.makedirs(td, exist_ok=True)
    for t in ('atp', 'wta'):
        for y in range(1968, YEAR + 1):
            get(f'{TCL}/tennis_{t}/{t}_matches_{y}.csv', os.path.join(td, f'{t}_{y}.csv'), force=y >= YEAR - 1)


def espn(prefix, liga):
    out = []
    for f in sorted(glob.glob(os.path.join(REL, f'{prefix}_*.parquet'))):
        x = pd.read_parquet(f)
        if 'status_type_completed' in x: x = x[x.status_type_completed.astype(str).str.lower() == 'true']
        x = x.dropna(subset=['home_score', 'away_score'])
        x = x[(pd.to_numeric(x.home_score, errors='coerce') + pd.to_numeric(x.away_score, errors='coerce')) > 0]
        per = pd.to_numeric(x.get('status_period', 4), errors='coerce').fillna(4)
        out.append(pd.DataFrame(dict(data=pd.to_datetime(x.date, utc=True).dt.tz_convert('America/New_York').dt.date.astype(str),
                                     sport='koszykówka', liga=liga, gosp=x.home_display_name, gosc=x.away_display_name,
                                     pg=pd.to_numeric(x.home_score), pa=pd.to_numeric(x.away_score), dogrywka=(per > 4).astype(int))))
    return pd.concat(out)


def _ok(hs, as_):
    """Kontrola jakości: w hokeju gospodarz wygrywa ~50–58%; 0% lub 100% = wyniki posortowane/zepsute w źródle."""
    r = (pd.to_numeric(hs, errors='coerce') > pd.to_numeric(as_, errors='coerce')).mean()
    return 0.40 < r < 0.70


def nhl():
    out, names, good = [], {}, set()
    rel = sorted(glob.glob(os.path.join(REL, 'nhl_*.parquet')))
    for f in rel:  # pełna nazwa per skrót (najnowsza)
        x = pd.read_parquet(f, columns=['home_team_abbr', 'home_team_name'])
        for a, n in zip(x.home_team_abbr, x.home_team_name):
            if isinstance(n, str) and ' ' in n and len(n) > len(names.get(a, '')): names[a] = n  # najdłuższa = pełna nazwa
    names.update(NHL_FIX)
    for f in rel:
        x = pd.read_parquet(f, columns=['game_type', 'game_date', 'home_team_abbr', 'away_team_abbr', 'home_score', 'away_score', 'game_state'])
        x = x[x.game_type.astype(str).isin(['R', 'P', '2', '3']) & x.game_state.isin(['OFF', 'FINAL', 'Final'])].dropna(subset=['home_score', 'away_score'])
        if len(x) < 100 or not _ok(x.home_score, x.away_score): continue
        good.add(int(os.path.basename(f)[4:8]))
        out.append(pd.DataFrame(dict(data=pd.to_datetime(x.game_date).dt.date.astype(str), gosp=x.home_team_abbr.map(names).fillna(x.home_team_abbr),
                                     gosc=x.away_team_abbr.map(names).fillna(x.away_team_abbr), pg=x.home_score, pa=x.away_score)))
    for f in sorted(glob.glob(os.path.join(RAW, 'fastRhockey-data/nhl/schedules/csv/*.csv'))):  # lata bez poprawnej paczki
        y = int(f[-8:-4])
        if y in good: continue
        x = pd.read_csv(f)
        if 'home_final_score' in x:
            x = x.rename(columns={'date': 'game_date', 'home_name': 'home_team_name', 'away_name': 'away_team_name',
                                  'home_final_score': 'home_score', 'away_final_score': 'away_score'})
        elif 'status_abstract_game_state' in x:
            x = x[x.status_abstract_game_state == 'Final']
        x = x.dropna(subset=['home_score', 'away_score'])
        if len(x) < 100 or not _ok(x.home_score, x.away_score): print('NHL: pominięto zepsuty sezon', y); continue
        out.append(pd.DataFrame(dict(data=pd.to_datetime(x.game_date).dt.date.astype(str), gosp=x.home_team_name, gosc=x.away_team_name,
                                     pg=x.home_score, pa=x.away_score)))
    d = pd.concat(out); d['sport'] = 'hokej'; d['liga'] = 'NHL'; d['dogrywka'] = -1  # OT nieznane (brak w harmonogramie)
    d['gosp'] = d.gosp.replace({'Montreal Canadiens': 'Montréal Canadiens', 'St Louis Blues': 'St. Louis Blues', 'Utah Hockey Club': 'Utah Mammoth'})
    d['gosc'] = d.gosc.replace({'Montreal Canadiens': 'Montréal Canadiens', 'St Louis Blues': 'St. Louis Blues', 'Utah Hockey Club': 'Utah Mammoth'})
    return d


def nfl():
    x = pd.read_csv(os.path.join(RAW, 'nfl_games.csv')).dropna(subset=['home_score'])
    return pd.DataFrame(dict(data=x.gameday, sport='futbol amerykański', liga='NFL', gosp=x.home_team, gosc=x.away_team,
                             pg=x.home_score, pa=x.away_score, dogrywka=x.overtime.fillna(0).astype(int)))


def mlb():
    """Retrosheet (2000–2023, dodatkowe inningi znane) + baseballr-data/MLB Stats API (2024–dziś, aktualizowane codziennie)."""
    out = []
    for f in sorted(glob.glob(os.path.join(RAW, 'retrosheet/seasons/*/GL*.TXT'))):
        if int(f[-8:-4]) >= 2024: continue
        x = pd.read_csv(f, header=None, usecols=[0, 3, 6, 9, 10, 11])
        out.append(pd.DataFrame(dict(data=pd.to_datetime(x[0].astype(str), format='%Y%m%d').dt.date.astype(str), sport='baseball', liga='MLB',
                                     gosp=x[6], gosc=x[3], pg=x[10], pa=x[9], dogrywka=(x[11].fillna(54) > 54).astype(int))))
    for f in sorted(glob.glob(os.path.join(RAW, 'baseballr-data/mlb/schedule/20*.parquet'))):
        if int(os.path.basename(f)[:4]) < 2024: continue
        x = pd.read_parquet(f)
        x = x[(x.abstract_state == 'Final') & x.game_type.isin(['R', 'F', 'D', 'L', 'W'])].dropna(subset=['home_score', 'away_score'])
        out.append(pd.DataFrame(dict(data=x.game_date.astype(str).str[:10], sport='baseball', liga='MLB', gosp=x.home_team_name,
                                     gosc=x.away_team_name, pg=x.home_score, pa=x.away_score, dogrywka=0)))
    return pd.concat(out)


def esport():
    """CS2: serie (mapy wygrane) z HLTV; LoL: pojedyncze mapy (1:0) z Oracle's Elixir. Brak gospodarza — przewaga 0."""
    a = pd.read_csv(os.path.join(RAW, 'cs2_pred/data/matches_clean.csv'))
    cs = pd.DataFrame(dict(data=a.data.str[:10], liga='CS2 ' + a.evento_nome.astype(str).str[:40], gosp=a.team_a_nome, gosc=a.team_b_nome,
                           pg=a.mapas_ganhos_a, pa=a.mapas_ganhos_b))
    b = pd.read_csv(os.path.join(RAW, 'esports_oracle/data/processed/cs2_matches.csv'))
    cs = pd.concat([cs, pd.DataFrame(dict(data=b.date, liga='CS2 ' + b.event.astype(str), gosp=b.team_a, gosc=b.team_b, pg=b.score_a, pa=b.score_b))])
    import re as _re
    fix = lambda n: _re.sub(r'^(Team )|( Team| Esports| Gaming| Clan)$', '', str(n)).strip()  # „Team Spirit” = „Spirit”
    cs['gosp'] = cs.gosp.map(fix); cs['gosc'] = cs.gosc.map(fix)
    cs['sport'] = 'esport_cs2'
    c = pd.read_csv(os.path.join(RAW, 'esports_oracle/data/processed/model_features.csv'), usecols=['date', 'league', 'blue_team', 'red_team', 'target'])
    lol = pd.DataFrame(dict(data=c.date.str[:10], sport='esport_lol', liga='LoL ' + c.league.astype(str), gosp=c.blue_team, gosc=c.red_team,
                            pg=c.target.astype(int), pa=1 - c.target.astype(int)))
    v = pd.read_csv(os.path.join(RAW, 'esports_oracle/data/processed/val_matches.csv'))
    val = pd.DataFrame(dict(data=v.date, sport='esport_val', liga='VCT ' + v.event.astype(str), gosp=v.team_a, gosc=v.team_b, pg=v.score_a, pa=v.score_b))
    d = pd.concat([cs, lol, val]); d['dogrywka'] = 0
    return d


def kbo_npb():
    """KBO i NPB 2021–dziś (dentearl, aktualizowane codziennie). Remisy (NPB/KBO po 12 inningach) pominięte w Elo."""
    import json
    out = []
    for liga, d in (('KBO', 'kbo/data/kbo'), ('NPB', 'npb/data/npb')):
        for f in sorted(glob.glob(os.path.join(RAW, d, '20*.json'))):
            for g in json.load(open(f)):
                if g.get('status', {}).get('abstractGameState') != 'F' or g.get('isTie'): continue
                h, a = g['teams']['home'], g['teams']['away']
                if h.get('score') is None or a.get('score') is None: continue
                out.append(dict(data=g['officialDate'], sport='baseball', liga=liga, gosp=h['team']['name'], gosc=a['team']['name'],
                                pg=h['score'], pa=a['score'], dogrywka=-1))
    return pd.DataFrame(out)


def snooker():
    """Snooker 1990–dziś (obrienjoey/snookerdb = CueTracker, aktualizowane codziennie): wynik we frame'ach, bez walkowerów."""
    m = pd.read_parquet(os.path.join(RAW, 'snookerdb/Parquet/matches.parquet'))
    t = pd.read_parquet(os.path.join(RAW, 'snookerdb/Parquet/tournament.parquet'))[['tourn_id', 'name', 'category']]
    m = m.merge(t, on='tourn_id', how='left')
    m = m[(~m.walkover.astype(str).isin(['True', '1'])) & (m.date >= '1990-01-01')]
    m = m[~m.category.isin(['6-reds'])]
    pg, pa = pd.to_numeric(m.player_1_score, errors='coerce'), pd.to_numeric(m.player_2_score, errors='coerce')
    d = pd.DataFrame(dict(data=m.date.astype(str).str[:10], sport='snooker', liga=m.category.fillna('') + ' | ' + m.name.fillna('') + ' | bo' + m.best_of.astype(str),
                          gosp=m.player_1, gosc=m.player_2, pg=pg, pa=pa, dogrywka=0))
    return d[(d.pg != d.pa) & d.pg.notna()]


def ufc():
    """UFC 1994–dziś (Greco1899/scrape_ufc_stats = ufcstats.com, aktualizowane po każdej gali). pg/pa: 1/0 zwycięzca;
    metody (KO/SUB/DEC) i runda → mma_metody.csv (do rynków „walka przez decyzję” / „koniec przed czasem”)."""
    r = pd.read_csv(os.path.join(RAW, 'ufc/ufc_fight_results.csv')); e = pd.read_csv(os.path.join(RAW, 'ufc/ufc_event_details.csv'))
    e['EVENT'] = e.EVENT.str.strip(); r['EVENT'] = r.EVENT.str.strip()
    r = r.merge(e[['EVENT', 'DATE']], on='EVENT', how='left')
    r['data'] = pd.to_datetime(r.DATE, errors='coerce').dt.strftime('%Y-%m-%d')
    ab = r.BOUT.str.split(r'\s+vs\.?\s+', n=1, expand=True)
    r['a'], r['b'] = ab[0].str.strip(), ab[1].str.strip()
    r = r[r.OUTCOME.isin(['W/L', 'L/W']) & r.data.notna()]
    w = r.OUTCOME == 'W/L'
    d = pd.DataFrame(dict(data=r.data, sport='mma', liga='UFC ' + r.WEIGHTCLASS.str.replace(' Bout', '').str.strip(),
                          gosp=r.a, gosc=r.b, pg=w.astype(int), pa=(~w).astype(int), dogrywka=0))
    met = r.METHOD.str.strip()
    kind = met.map(lambda x: 'DEC' if str(x).startswith('Decision') else 'SUB' if 'Submission' in str(x) else 'KO' if 'KO' in str(x) or 'Doctor' in str(x) else 'INNE')
    pd.DataFrame(dict(data=r.data, zwyciezca=r.a.where(w, r.b), przegrany=r.b.where(w, r.a), metoda=kind, runda=r.ROUND,
                      format=r['TIME FORMAT'], kategoria=r.WEIGHTCLASS)).to_csv(os.path.join(HERE, 'mma_metody.csv'), index=False)
    return d


def dart():
    """Dart PDC 02–dziś 2026 (walker95sam/darts: ostatnie mecze posiadaczy kart tourowych z dartsorakel, dzienne migawki
    w historii gita → suma migawek). pg/pa = legi; średnie 3-lotkowe → dart_srednie.csv."""
    p = os.path.join(RAW, 'darts_git')
    if not os.path.exists(p): sh('git', 'clone', '-q', '--filter=blob:none', 'https://github.com/walker95sam/darts', p)
    else: sh('git', '-C', p, 'pull', '-q')
    f = 'docs/data/tourcard_matches_long.csv'
    hs = subprocess.run(['git', '-C', p, 'log', '--format=%h', '--', f], capture_output=True, text=True).stdout.split()
    import io
    snaps = []
    for h in hs:
        t = subprocess.run(['git', '-C', p, 'show', f'{h}:{f}'], capture_output=True, text=True).stdout
        if t: snaps.append(pd.read_csv(io.StringIO(t)))
    if not snaps: return pd.DataFrame(columns=COLS)
    d = pd.concat(snaps).drop_duplicates(['player_key', 'match_date', 'tournament', 'round', 'opponent_key', 'score'])
    sc = d.score.str.extract(r'(\d+)\s*V\s*(\d+)').astype(float)
    d['lp'], d['lo'] = sc[0], sc[1]
    d = d.dropna(subset=['lp', 'lo'])
    d[['player_name', 'opponent', 'match_date', 'tournament', 'category', 'round', 'lp', 'lo', 'three_dart_average', 'opponent_avg']].to_csv(
        os.path.join(HERE, 'dart_srednie.csv'), index=False)
    d['k1'] = d[['player_key', 'opponent_key']].min(axis=1); d['k2'] = d[['player_key', 'opponent_key']].max(axis=1)
    d = d.drop_duplicates(['k1', 'k2', 'match_date', 'tournament', 'round'])
    return pd.DataFrame(dict(data=d.match_date, sport='dart', liga='PDC ' + d.category.astype(str) + ' | ' + d.tournament.astype(str),
                             gosp=d.player_name, gosc=d.opponent, pg=d.lp, pa=d.lo, dogrywka=0))


def rugby():
    """Rugby union 2002–dziś (transientlunatic/Rugby-Data): URC, Premiership, Top 14, Pro D2, Champions/Challenge Cup,
    Super Rugby, Six Nations, Puchar Świata, testy. Wynik końcowy (remisy możliwe)."""
    import json, re as _re
    NAZWY = {'celtic': 'URC', 'championship': 'RFU Championship', 'currie-cup': 'Currie Cup', 'end-of-year-internationals': 'Testy (jesień)',
             'euro-challenge': 'Challenge Cup', 'euro-champions': 'Champions Cup', 'mid-year-internationals': 'Testy (lato)', 'npc': 'NPC',
             'premiership': 'Premiership', 'pro-d2': 'Pro D2', 'rugby-world-cup': 'Puchar Świata', 'six-nations': 'Sześć Narodów',
             'super-rugby': 'Super Rugby', 'top14': 'Top 14'}
    out = []
    for f in sorted(glob.glob(os.path.join(RAW, 'rugby/json/*.json'))):
        comp = _re.sub(r'-\d{4}(-\d{4})?$', '', os.path.basename(f)[:-5])
        try: j = json.load(open(f))
        except Exception as e:
            # bylo "continue": uszkodzony plik znikal po cichu, wiec liga po prostu miala mniej meczow
            print(f'UWAGA: pominieto nieczytelny plik rugby {os.path.basename(f)} ({e})'); continue
        for m in j if isinstance(j, list) else []:
            h, a = m.get('home', {}), m.get('away', {})
            if h.get('score') is None or a.get('score') is None or not m.get('date'): continue
            out.append(dict(data=str(m['date'])[:10], sport='rugby', liga=NAZWY.get(comp, comp), gosp=h.get('team'), gosc=a.get('team'),
                            pg=h['score'], pa=a['score'], dogrywka=0))
    return pd.DataFrame(out)


def tenis():
    out = []
    for t in ('atp', 'wta'):
        for f in sorted(glob.glob(os.path.join(RAW, 'tcl', f'{t}_*.csv'))):
            x = pd.read_csv(f, encoding='utf-8-sig', low_memory=False,
                            usecols=lambda c: c in {'tourney_name', 'tourney_level', 'tourney_date', 'surface', 'round', 'best_of', 'winner_name', 'loser_name', 'score'})
            x['tour'] = t.upper(); out.append(x)
    d = pd.concat(out, ignore_index=True)
    d['date'] = pd.to_datetime(d.tourney_date.astype(str).str.replace('/', '-').str[:10], errors='coerce')
    RO = {'Q1': 0, 'Q2': 1, 'Q3': 2, 'Q4': 3, 'R128': 4, 'R64': 5, 'R32': 6, 'R16': 7, 'QF': 8, 'SF': 9, 'BR': 10, 'F': 11, 'RR': 6}
    d['rk'] = d['round'].map(RO).fillna(6)
    d = d.dropna(subset=['date', 'winner_name', 'loser_name']).sort_values(['date', 'tourney_name', 'rk'], kind='stable')
    return d.rename(columns={'tourney_level': 'poziom', 'surface': 'nawierzchnia', 'winner_name': 'zwyciezca', 'loser_name': 'przegrany'})[
        ['date', 'tour', 'tourney_name', 'poziom', 'nawierzchnia', 'round', 'best_of', 'zwyciezca', 'przegrany', 'score']]


def main():
    fetch()
    parts = [espn('nba', 'NBA'), espn('wnba', 'WNBA'), nhl(), nfl(), mlb(), esport()]
    try:
        import zewn; parts.append(zewn.inne())   # Sofascore przez Apps Script: siatkówka, ręczna, hokej EU, tenis stołowy, futsal…
    except Exception as ex: print('UWAGA: zewn.inne nie wczytany:', ex)
    for fn in (kbo_npb, snooker, ufc, dart, rugby):
        try: parts.append(fn())
        except Exception as ex: print('UWAGA:', fn.__name__, 'nie wczytany:', ex)
    eu = os.path.join(HERE, 'sporty_eu.csv')
    if os.path.exists(eu): parts.append(pd.read_csv(eu))
    h = pd.concat(parts, ignore_index=True)[COLS].dropna(subset=['gosp', 'gosc', 'pg', 'pa'])
    lol = h.sport == 'esport_lol'  # LoL = pojedyncze mapy: kolejne mapy serii tego samego dnia to NIE duplikaty
    h = pd.concat([h[~lol].drop_duplicates(['data', 'sport', 'gosp', 'gosc', 'pg', 'pa']), h[lol]]).sort_values('data', kind='stable')
    h.to_csv(os.path.join(HERE, 'sporty_hist.csv'), index=False)
    s = h.assign(grupa=h.liga.where(~h.sport.str.startswith('esport') & ~h.sport.isin(['snooker', 'mma', 'dart']), h.sport))
    print(s.groupby(['sport', 'grupa']).agg(mecze=('gosp', 'size'), od=('data', 'min'), do=('data', 'max')).to_string())
    t = tenis()
    try:
        import zewn; z = zewn.tenis(max_tcl=t.date.max())
        if len(z): z['date'] = pd.to_datetime(z.date); t = pd.concat([t, z], ignore_index=True).sort_values('date', kind='stable')
    except Exception as ex: print('UWAGA: zewn.tenis nie wczytany:', ex)
    t.to_csv(os.path.join(HERE, 'tenis_hist.csv'), index=False)
    print(t.groupby('tour').agg(mecze=('zwyciezca', 'size'), od=('date', 'min'), do=('date', 'max')).to_string())


if __name__ == '__main__':
    main()
