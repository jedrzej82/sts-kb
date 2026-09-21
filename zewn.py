#!/usr/bin/env python3
"""Wczytywanie wyników pobieranych przez Google Apps Script (apps_script/wyniki_sts.gs) z ESPN i Sofascore.
Pliki z Drive (folder baza-wiedzy) kładzie się do kb/zewn/:
  wyniki_espn_RRRR-MM.csv, wyniki_sofa_pilka_RRRR-MM.csv, wyniki_sofa_inne_RRRR-MM.csv
Funkcje używane przez uzupelnij_ligi.py (piłka) i hist_import.py / tenis.py (reszta). Kursy nie są pobierane."""
import os, re, glob, unicodedata, pandas as pd, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ZD = os.path.join(HERE, 'zewn')

ESPN_DIV = {'nor.1': 'NOR', 'swe.1': 'SWE', 'swe.2': 'SWE2', 'den.1': 'DEN', 'fin.1': 'FIN', 'irl.1': 'IRL', 'sui.1': 'SUI',
            'aut.1': 'AUT', 'rus.1': 'RUS', 'rou.1': 'ROM', 'pol.1': 'POL', 'pol.2': 'POL2', 'mex.1': 'MEX', 'usa.1': 'USA',
            'usa.usl.1': 'USL', 'arg.1': 'ARG', 'bra.1': 'BRA', 'bra.2': 'BRA2', 'jpn.1': 'JAP', 'jpn.2': 'JAP2', 'chn.1': 'CHN',
            'cze.1': 'CZE', 'cro.1': 'CRO', 'srb.1': 'SRB', 'ukr.1': 'UKR', 'kor.1': 'KOR', 'ksa.1': 'KSA', 'aus.1': 'AUS',
            'bul.1': 'BUL', 'hun.1': 'HUN', 'chi.1': 'CHI', 'col.1': 'COL', 'ecu.1': 'ECU', 'uru.1': 'URU', 'per.1': 'PER',
            'par.1': 'PAR', 'bol.1': 'BOL', 'ven.1': 'VEN', 'rsa.1': 'RSA', 'can.1': 'CAN', 'bel.1': 'B1', 'bel.2': 'B2',
            'ger.1': 'D1', 'ger.2': 'D2', 'ger.3': 'D3', 'ned.1': 'N1', 'ned.2': 'N2', 'eng.1': 'E0', 'eng.2': 'E1', 'eng.3': 'E2',
            'eng.4': 'E3', 'esp.1': 'SP1', 'esp.2': 'SP2', 'ita.1': 'I1', 'ita.2': 'I2', 'fra.1': 'F1', 'fra.2': 'F2', 'por.1': 'P1',
            'tur.1': 'T1', 'gre.1': 'G1', 'sco.1': 'SC0', 'isr.1': 'ISR', 'cyp.1': 'CYP', 'svk.1': 'SVK', 'svn.1': 'SVN'}
NOWE_DIV = {'POL2': 'Polska I liga', 'ISR': 'Izrael', 'CYP': 'Cypr', 'SVK': 'Słowacja', 'SVN': 'Słowenia'}

# Sofascore: (fragment kraju, wzorzec nazwy rozgrywek) → Division kb; reszta lig → „Kraj | Liga” (każda liga świata)
SOFA_DIV = [('england', r'^premier league$', 'E0'), ('england', r'^championship$', 'E1'), ('england', r'^league one$', 'E2'),
            ('england', r'^league two$', 'E3'), ('england', r'^national league$', 'EC'), ('spain', r'^laliga$', 'SP1'),
            ('spain', r'laliga 2|hypermotion|^segunda division$', 'SP2'), ('germany', r'^bundesliga$', 'D1'), ('germany', r'^2\. bundesliga$', 'D2'),
            ('germany', r'^3\. liga$', 'D3'), ('italy', r'^serie a$', 'I1'), ('italy', r'^serie b$', 'I2'), ('france', r'^ligue 1$', 'F1'),
            ('france', r'^ligue 2$', 'F2'), ('netherlands', r'^eredivisie$', 'N1'), ('netherlands', r'eerste divisie|keuken kampioen', 'N2'),
            ('portugal', r'liga portugal$|^liga portugal betclic|primeira liga', 'P1'), ('belgium', r'^(jupiler )?pro league$|jupiler', 'B1'),
            ('belgium', r'challenger pro league', 'B2'), ('scotland', r'^premiership$', 'SC0'), ('scotland', r'^championship$', 'SC1'),
            ('turk', r'^(trendyol )?s[uü]per lig$', 'T1'), ('greece', r'super league( 1)?$|stoiximan', 'G1'),
            ('norway', r'^eliteserien$', 'NOR'), ('sweden', r'^allsvenskan$', 'SWE'), ('sweden', r'^superettan$', 'SWE2'),
            ('denmark', r'superliga', 'DEN'), ('finland', r'veikkausliiga', 'FIN'), ('ireland', r'premier division', 'IRL'),
            ('switzerland', r'^super league$', 'SUI'), ('austria', r'^bundesliga$', 'AUT'), ('russia', r'^premier league$', 'RUS'),
            ('romania', r'^(superliga|liga i)$', 'ROM'), ('poland', r'^ekstraklasa$', 'POL'), ('poland', r'^(i liga|1\. liga|betclic 1\. liga)$', 'POL2'),
            ('mexico', r'^liga mx', 'MEX'), ('usa', r'^mls$', 'USA'), ('usa', r'usl championship', 'USL'),
            ('argentina', r'liga profesional', 'ARG'), ('brazil', r's[eé]rie a$', 'BRA'), ('brazil', r's[eé]rie b$', 'BRA2'),
            ('japan', r'^j1 league$', 'JAP'), ('japan', r'^j2 league$', 'JAP2'), ('china', r'super league', 'CHN'),
            ('czech', r'(1\. liga|chance liga)$', 'CZE'), ('croatia', r'hnl$', 'CRO'), ('serbia', r'super ?liga', 'SRB'),
            ('ukraine', r'^premier league$', 'UKR'), ('korea', r'^k league 1$', 'KOR'), ('saudi', r'pro league', 'KSA'),
            ('australia', r'a-league men', 'AUS'), ('bulgaria', r'(parva liga|efbet liga|first league)', 'BUL'),
            ('hungary', r'^nb i$', 'HUN'), ('chile', r'liga de primera|primera divisi', 'CHI'), ('colombia', r'primera a', 'COL'),
            ('ecuador', r'ligapro', 'ECU'), ('uruguay', r'primera divisi', 'URU'), ('peru', r'^liga 1', 'PER'),
            ('paraguay', r'primera divisi', 'PAR'), ('bolivia', r'divisi[oó]n profesional', 'BOL'), ('venezuela', r'^(liga futve|primera divisi[oó]n)$', 'VEN'),
            ('south africa', r'premiership', 'RSA'), ('iran', r'pro league', 'IRN'), ('canada', r'canadian premier league', 'CAN'),
            ('israel', r'premier league', 'ISR'), ('cyprus', r'1st division|first division', 'CYP'),
            ('slovakia', r'(niké liga|super liga|1\. liga)', 'SVK'), ('slovenia', r'prvaliga', 'SVN')]
PUCHAR = re.compile(r'cup|pokal|copa|coupe|coppa|ta[cç]a|beker|pohar|puchar|friendl|qualif|play-?off|super ?cup|trophy|shield|u1\d|u2\d|youth|reserv|amateur|femen|feminin|women|frauen|damen|\(w\)|liga f$|premier league 2|primavera|juvenil|sub-?\d\d', re.I)


def _n(s): return unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower().strip()


def czytaj(wzor):
    fs = sorted(glob.glob(os.path.join(ZD, wzor)) + glob.glob(os.path.join(ZD, wzor + '.gz')))
    if not fs: return pd.DataFrame()
    d = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in fs], ignore_index=True).drop_duplicates()
    klucz = [c for c in ('data', 'sport', 'liga', 'gosp', 'gosc') if c in d.columns]
    if 'okresy_g' in d.columns:   # ten sam mecz pobrany ponownie: zostaje wiersz z pełniejszymi danymi (okresy/nawierzchnia)
        d = d.assign(_pel=(d.okresy_g != '').astype(int) + (d.get('nawierzchnia', '') != '').astype(int)).sort_values('_pel', kind='stable')
        d = d.drop(columns='_pel')
    return d.drop_duplicates(klucz, keep='last').reset_index(drop=True)


def sofa_div(kraj, turniej):
    k, t = _n(kraj), _n(turniej)
    for kk, rx, div in SOFA_DIV:
        if kk in k and re.search(rx, t): return div
    return None


def pilka():
    """Mecze piłkarskie z ESPN (z rożnymi/faulami/strzałami/kartkami) i Sofascore (wszystkie ligi świata)."""
    out = []
    e = czytaj('wyniki_espn_*.csv')
    if len(e):
        e = e[e.liga.isin(ESPN_DIV)]
        num = lambda c: pd.to_numeric(e[c], errors='coerce')
        out.append(pd.DataFrame(dict(Division=e.liga.map(ESPN_DIV), MatchDate=pd.to_datetime(e.data), HomeTeam=e.gosp, AwayTeam=e.gosc,
                                     FTHome=num('gg'), FTAway=num('ga'), HomeCorners=num('rozne_g'), AwayCorners=num('rozne_a'),
                                     HomeFouls=num('faule_g'), AwayFouls=num('faule_a'), HomeShots=num('strzaly_g'), AwayShots=num('strzaly_a'),
                                     HomeTarget=num('celne_g'), AwayTarget=num('celne_a'), HomeYellow=num('zolte_g'), AwayYellow=num('zolte_a'),
                                     HomeRed=num('czerwone_g'), AwayRed=num('czerwone_a'), src='espn')))
    s = czytaj('wyniki_*_pilka_*.csv')
    if len(s):
        s = s[~s.turniej.str.contains(PUCHAR) & ~s.kraj.str.contains(r'international|world|europe|south america|africa|asia|north|club', case=False)]
        div = [sofa_div(k, t) or f'{k} | {t}' for k, t in zip(s.kraj, s.turniej)]
        s = s.assign(Division=div)
        n = s.groupby('Division').Division.transform('size')
        s = s[(n >= 60) | s.Division.isin(set(ESPN_DIV.values()) | {'EC', 'SC1'})]   # nieznane ligi: tylko z historią ≥60 meczów
        out.append(pd.DataFrame(dict(Division=s.Division, MatchDate=pd.to_datetime(s.data), HomeTeam=s.gosp, AwayTeam=s.gosc,
                                     FTHome=pd.to_numeric(s.wg, errors='coerce'), FTAway=pd.to_numeric(s.wa, errors='coerce'),
                                     HTHome=pd.to_numeric(s.okresy_g.str.split(';').str[0], errors='coerce'),
                                     HTAway=pd.to_numeric(s.okresy_a.str.split(';').str[0], errors='coerce'), src='sofa')))
    if not out: return pd.DataFrame()
    d = pd.concat(out, ignore_index=True).dropna(subset=['FTHome', 'FTAway', 'MatchDate'])
    d[['FTHome', 'FTAway']] = d[['FTHome', 'FTAway']].astype(int)
    return d


SPORT = {'ice-hockey': ('hokej', 3), 'basketball': ('koszykówka', 4), 'volleyball': ('siatkówka', 0), 'handball': ('piłka ręczna', 2),
         'futsal': ('futsal', 2), 'darts': ('dart', 0), 'snooker': ('snooker', 0), 'rugby': ('rugby', 2),
         'american-football': ('futbol amerykański', 4), 'baseball': ('baseball', 0), 'floorball': ('unihokej', 3),
         'waterpolo': ('piłka wodna', 4), 'cricket': ('krykiet', 0), 'badminton': ('badminton', 0),
         'beach-volley': ('siatkówka plażowa', 0), 'aussie-rules': ('futbol australijski', 0), 'table-tennis': ('tenis stołowy', 0)}


ALIAS_SPORT = {'hockey': 'ice-hockey', 'a-football': 'american-football', 'ice-hockey': 'ice-hockey', 'e-sports': 'esports', 'esport': 'esports', 'beach-volleyball': 'beach-volley',
               'australian-football': 'aussie-rules', 'aussie-rules-football': 'aussie-rules', 'water-polo': 'waterpolo',
               'rugby-union': 'rugby', 'soccer': 'football', 'ping-pong': 'table-tennis'}
NAZWA_PL = {'mma': 'mma', 'boxing': 'boks', 'field-hockey': 'hokej na trawie', 'netball': 'netball', 'bandy': 'bandy',
            'lacrosse': 'lacrosse', 'squash': 'squash', 'rugby-league': 'rugby league', 'beach-soccer': 'piłka plażowa',
            'pesapallo': 'pesapallo', 'field-hockey': 'hokej na trawie', 'padel': 'padel', 'kabaddi': 'kabaddi', 'speedway': 'żużel'}
WYGRANA = {'mma', 'boks', 'krykiet'}   # liczy się zwycięzca, nie punkty


def inne():
    """Sporty drużynowe i indywidualne (bez tenisa) → wiersze w formacie sporty_hist (data,sport,liga,gosp,gosc,pg,pa,dogrywka)."""
    s = czytaj('wyniki_*_inne_*.csv')
    if not len(s): return pd.DataFrame()
    s = s[~(s.kraj + ' ' + s.turniej).str.contains(r'\b(?:NHL|NBA|WNBA|MLB)\b')]   # te ligi są z GitHuba
    rows = []
    s = s.assign(sport=s.sport.map(lambda x: ALIAS_SPORT.get(x, x)))
    kt = s.kraj + ' ' + s.turniej
    s = s[~kt.str.contains(r'friendl|\bu-?1\d\b|\bu-?2[0-3]\b|youth|junior|juvenil|\bu\d\d\b', case=False)]
    kob = (s.kraj + ' ' + s.turniej).str.contains(r'women|\(w\)|female|femen|feminin|damen|frauen|ladies|wnba|wta', case=False)
    dop = lambda n: n if re.search(r'(?:\(W\)|\(K\)|\bW|\bWomen)$', str(n).strip()) else f'{n} (W)'
    s = s.assign(gosp=np.where(kob, s.gosp.map(dop), s.gosp), gosc=np.where(kob, s.gosc.map(dop), s.gosc))
    for r in s.itertuples():
        if r.sport in ('tennis', 'football'): continue
        pg, pa = pd.to_numeric(r.wg, errors='coerce'), pd.to_numeric(r.wa, errors='coerce')
        sp0 = SPORT[r.sport][0] if r.sport in SPORT else NAZWA_PL.get(r.sport, r.sport.replace('-', ' '))
        if pd.isna(pg) or pd.isna(pa) or sp0 in WYGRANA:
            if str(r.zwyciezca) not in ('1', '2'): continue
            pg, pa = (1, 0) if str(r.zwyciezca) == '1' else (0, 1)
        liga = f'{r.kraj} | {r.turniej}'
        if r.sport == 'esports' and 'league of legends' in _n(r.kraj) and 'lol' != _n(r.kraj): continue   # LoL z lolesports (pełne dane)
        if r.sport == 'esports':
            k = _n(r.kraj + ' ' + r.turniej)
            sp = 'esport_cs2' if 'counter' in k or 'cs2' in k or 'cs:' in k else 'esport_lol' if 'league of legends' in k or 'lol' in k.split() \
                else 'esport_dota' if 'dota' in k else 'esport_val' if 'valorant' in k else 'esport'
            if sp == 'esport_lol':   # w bazie LoL = pojedyncze mapy
                rows += [(r.data, sp, liga, r.gosp, r.gosc, 1, 0, 0)] * int(pg) + [(r.data, sp, liga, r.gosp, r.gosc, 0, 1, 0)] * int(pa)
                continue
            rows.append((r.data, sp, liga, r.gosp, r.gosc, pg, pa, 0)); continue
        sp, nreg = SPORT.get(r.sport, (sp0, 0)); ot = 0
        if nreg:
            try:
                g = [float(x) for x in str(r.okresy_g).split(';') if x != ''][:nreg]; a = [float(x) for x in str(r.okresy_a).split(';') if x != ''][:nreg]
                if len(g) == nreg and len(a) == nreg and (sum(g) != pg or sum(a) != pa): ot = 1
            except ValueError: ot = -1
        rows.append((r.data, sp, liga, r.gosp, r.gosc, pg, pa, ot))
    return pd.DataFrame(rows, columns=['data', 'sport', 'liga', 'gosp', 'gosc', 'pg', 'pa', 'dogrywka'])


# Challengery/WTA125 bez nawierzchni w API: turnieje ziemne (reszta = twarda; trawa tylko czerwiec–lipiec)
ZIEMNE = '''aix en provence bergamo biella bordeaux braga brasov buenos aires cagliari campinas cordoba curitiba
 florianopolis genoa montreux antalya genova guayaquil heilbronn iasi lima lisbon lyon madrid marbella medellin milan modena montevideo
 mestre napoli oeiras olbia orleans? ostrava perugia piracicaba poznan prague praha prostejov rome roma sabadell salzburg
 san marino santa cruz santiago sao leopoldo sao paulo sevilla seville sibiu skopje split szczecin tigre todi trieste tulln
 tunis verona vicenza wroclaw zadar zagreb caldas da rainha bucharest bucuresti la bisbal rabat valencia ljubljana
 bogota barranquilla tampere bastad palermo iasi grodzisk ambato asuncion lima villa maria mar del plata porto alegre
 cordenons san benedetto amersfoort hamburg kitzbuhel umag gstaad kiel meerbusch luedenscheid troisdorf'''.split()
ZIEMNE_S = {w.rstrip('?') for w in ZIEMNE} | {'caldas da rainha', 'la bisbal', 'sao paulo', 'buenos aires', 'san marino', 'santa cruz',
            'sao leopoldo', 'villa maria', 'mar del plata', 'porto alegre', 'san benedetto'}
TRAWIASTE = '''ilkley nottingham surbiton birmingham eastbourne halle queens queen's s-hertogenbosch mallorca newport
 bad homburg berlin wimbledon'''.split()


def _nawierzchnie():
    znane = {}
    try:
        th = pd.read_csv(os.path.join(HERE, 'tenis_hist.csv'), usecols=['tourney_name', 'nawierzchnia'], low_memory=False).dropna()
        th['m'] = th.tourney_name.map(lambda t: _n(re.sub(r'\b(open|challenger|cup|ii|2|125k?|wta|atp|itf)\b', ' ', str(t))).strip())
        znane = th.groupby('m').nawierzchnia.agg(lambda x: x.value_counts().index[0]).replace({'Carpet': 'Hard'}).to_dict()
    except Exception as e:
        # bylo "pass": gdy tenis_hist.csv nie wczytal sie, WSZYSTKIE nawierzchnie stawaly sie nieznane
        # i model tenisowy liczyl dalej bez slowa — cichy spadek jakosci zamiast bledu
        print(f'UWAGA: nawierzchnie z tenis_hist.csv nie wczytane ({e}) — zostaja tylko turnieje z list ZIEMNE/TRAWIASTE.')
    for w in ZIEMNE: znane.setdefault(w.rstrip('?'), 'Clay')
    znane['sao paulo'] = 'Hard'   # WTA 250 São Paulo (wrzesień) — twarda
    for w in TRAWIASTE: znane.setdefault(w, 'Grass')
    return znane


def tenis(max_tcl=None):
    """Tenis z Sofascore (Challenger, ITF, a ATP/WTA po ostatniej dacie TennisCourtLog) → format tenis_hist."""
    s = czytaj('wyniki_*_inne_*.csv')
    if not len(s): return pd.DataFrame()
    s = s[(s.sport == 'tennis') & ~s.gosp.str.contains('/') & ~s.gosc.str.contains('/') & s.zwyciezca.isin(['1', '2'])]
    k = (s.kraj + ' ' + s.turniej).map(_n)
    tour = np.select([k.str.contains('challenger'), k.str.contains('itf') & k.str.contains('women'), k.str.contains('itf'),
                      k.str.contains('wta'), k.str.contains('atp')], ['CH', 'ITF-W', 'ITF', 'WTA', 'ATP'], 'INNE')
    poziom = np.select([k.str.contains('125'), k.str.contains('davis|billie jean|united cup'), k.str.contains('challenger')],
                       ['WTA125', 'DC', 'CH'], tour)
    s = s.assign(tour=tour, poz=poziom)
    s = s[s.tour != 'INNE']
    # krecz/walkower: zwycięzca bez kompletu setów (365 podaje tylko sety) — do bazy Elo nie wchodzi
    wg_, wa_ = pd.to_numeric(s.wg, errors='coerce'), pd.to_numeric(s.wa, errors='coerce')
    s = s[np.maximum(wg_, wa_) >= 2]
    if max_tcl is not None: s = s[~s.tour.isin(['ATP', 'WTA']) | (pd.to_datetime(s.data) > max_tcl)]
    g = (s.ground.fillna('') if 'ground' in s else s.nawierzchnia.fillna('')) + ' ' + s.turniej.fillna('')   # Flashscore: „Monastir (Tunisia), hard”
    surf = np.where(g.str.contains('clay|ziem|terre', case=False), 'Clay', np.where(g.str.contains('grass|trawa', case=False), 'Grass',
                    np.where(g.str.contains('hard|carpet|indoor', case=False), 'Hard', '')))
    # brak nawierzchni w źródle → z historii turnieju (TennisCourtLog + wcześniejsze pobrania) albo z tabeli NAWIERZCHNIE
    miasto = s.turniej.map(lambda t: _n(re.sub(r'\b(open|challenger|cup|ii|2|125k?|wta|atp|itf|m\d+|w\d+)\b', ' ', str(t))).strip())
    znane = _nawierzchnie()
    niski = s.poz.isin(['CH', 'WTA125', 'ITF', 'ITF-W']).values   # Challenger/125/ITF: lista ZIEMNE (historia to turnieje główne w tym mieście)
    mies = pd.to_datetime(s.data).dt.month.values
    zg = [('Clay' if m in ZIEMNE_S else 'Hard') if n else znane.get(m, 'Hard') for m, n in zip(miasto, niski)]
    zg = [('Clay' if m in ZIEMNE_S else 'Hard') if z == 'Grass' and mm not in (6, 7) else z for z, m, mm in zip(zg, miasto, mies)]
    surf = np.where(surf != '', surf, zg)
    # LiveScore podaje „Nazwisko I.” — zamiana na pełne imię i nazwisko z TennisCourtLog, gdy jednoznaczne
    try:
        th = pd.read_csv(os.path.join(HERE, 'tenis_hist.csv'), usecols=['tour', 'zwyciezca', 'przegrany'], low_memory=False)
        th = th[th.tour.isin(['ATP', 'WTA'])]
        full = pd.unique(pd.concat([th.zwyciezca, th.przegrany]).dropna())
        idx = {}
        for f in full:
            p = str(f).split()
            if len(p) < 2: continue
            key = (_n(' '.join(p[1:])), _n(p[0])[:1]); idx.setdefault(key, set()).add(f)
        def pelne(n):
            m = re.match(r'^(.+?)\s+([A-Z])\.?(?:-[A-Z]\.)?$', str(n).strip())
            if not m: return n
            c = idx.get((_n(m.group(1)), m.group(2).lower()))
            return next(iter(c)) if c and len(c) == 1 else n
        s = s.assign(gosp=s.gosp.map(pelne), gosc=s.gosc.map(pelne))
    except Exception as e:
        # bylo "pass": nazwiska zostawaly w formie skroconej "Nowak J.", co psuje pozniejsze dopasowanie
        print(f'UWAGA: rozwijanie skroconych nazwisk tenisistow nie powiodlo sie ({e}) — zostaja skroty.')
    w1 = s.zwyciezca == '1'
    def wynik(a, b, first, n=None):
        A = [x for x in str(a).split(';') if x != '']; B = [x for x in str(b).split(';') if x != '']
        if n: A, B = A[:n], B[:n]   # 365scores: po setach bywa wpis zbiorczy — tylko rozegrane sety (wg+wa)
        return ' '.join(f'{x}-{y}' if first else f'{y}-{x}' for x, y in zip(A, B))
    nset = (pd.to_numeric(s.wg, errors='coerce').fillna(0) + pd.to_numeric(s.wa, errors='coerce').fillna(0)).astype(int)
    score = [wynik(a, b, f, n) for a, b, f, n in zip(s.okresy_g, s.okresy_a, w1, nset)]
    bo = np.where(np.maximum(pd.to_numeric(s.wg, errors='coerce').fillna(0), pd.to_numeric(s.wa, errors='coerce').fillna(0)) >= 3, 5, 3)
    return pd.DataFrame(dict(date=s.data, tour=np.where(s.tour == 'CH', 'ATP', s.tour), tourney_name=s.turniej, poziom=s.poz,
                             nawierzchnia=surf, round=s.runda,
                             best_of=bo, zwyciezca=np.where(w1, s.gosp, s.gosc), przegrany=np.where(w1, s.gosc, s.gosp), score=score))


if __name__ == '__main__':
    p, i, t = pilka(), inne(), tenis()
    print('piłka:', len(p), p.groupby('Division').size().sort_values(ascending=False).head(30).to_dict() if len(p) else '')
    print('inne:', len(i), i.groupby('sport').size().to_dict() if len(i) else '')
    print('tenis:', len(t), t.groupby('tour').size().to_dict() if len(t) else '')
