#!/usr/bin/env python3
"""Uzupełnia ligi piłkarskie spoza football-data (NOR, SWE, FIN, IRL, DEN, SUI, RUS, ROM, MEX, USA, ARG, BRA, JAP, CHN, AUT, POL)
oraz dodaje nowe ligi (CZE, CRO, SRB, UKR, KOR, ...). Źródła (wszystkie z GitHuba, bez kursów):
  1) worldfootballR_data (FBref) – release 'match_results' – mecze z datami, do ~09.2025
  2) openfootball football.json – BRA 2025/2026, AUT 2024-26, MEX 2024-25, ARG/MLS/JPN/CHN 2025 (z datami)
  3) eu/wiki/*.csv – pełne sezony z matryc Wikipedii (zweryfikowane z tabelami), bez dat → daty rozkładane
     równomiernie między ostatnim meczem z datą a końcem sezonu (przybliżenie tylko dla wag czasowych).
Wynik: ligi_extra.csv (format tabeli matches) — build_kb.py dokleja go jak delta.
  python3 uzupelnij_ligi.py [--refresh]"""
import os, re, sys, glob, json, subprocess, sqlite3, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); RAW = os.path.join(HERE, 'raw'); WFR = os.path.join(RAW, 'wfr')
sys.path.insert(0, HERE)
from build_kb import norm, map_names

REL = 'https://github.com/JaseZiv/worldfootballR_data/releases/download/match_results/{}_match_results.rds'
# kod FBref -> {nazwa rozgrywek: Division w kb}
WFR_MAP = {
    'NOR': {'Eliteserien': 'NOR'}, 'SWE': {'Allsvenskan': 'SWE', 'Superettan': 'SWE2'}, 'FIN': {'Veikkausliiga': 'FIN'},
    'DEN': {'Danish Superliga': 'DEN', 'Superliga': 'DEN'}, 'SUI': {'Swiss Super League': 'SUI'},
    'RUS': {'Russian Premier League': 'RUS'}, 'ROU': {'Liga I': 'ROM'}, 'MEX': {'Liga MX': 'MEX'},
    'USA': {'Major League Soccer': 'USA', 'USL Championship': 'USL'}, 'ARG': {'Liga Profesional de Fútbol Argentina': 'ARG',
    'Argentine Primera División': 'ARG'}, 'BRA': {'Campeonato Brasileiro Série A': 'BRA', 'Campeonato Brasileiro Série B': 'BRA2'},
    'JPN': {'J1 League': 'JAP', 'J2 League': 'JAP2'}, 'CHN': {'Chinese Football Association Super League': 'CHN',
    'Chinese Super League': 'CHN'}, 'AUT': {'Austrian Football Bundesliga': 'AUT'}, 'POL': {'Ekstraklasa': 'POL'},
    'CZE': {'Czech First League': 'CZE'}, 'CRO': {'Croatian Football League': 'CRO', 'Croatian First Football League': 'CRO'},
    'SRB': {'Serbian SuperLiga': 'SRB'}, 'UKR': {'Ukrainian Premier League': 'UKR'}, 'KOR': {'K League 1': 'KOR'},
    'KSA': {'Saudi Professional League': 'KSA'}, 'AUS': {'A-League Men': 'AUS', 'A-League': 'AUS'},
    'BUL': {'First Professional Football League': 'BUL'}, 'HUN': {'Nemzeti Bajnokság I': 'HUN'},
    'CHI': {'Chilean Primera División': 'CHI'}, 'COL': {'Categoría Primera A': 'COL'}, 'ECU': {'Liga Profesional Ecuador': 'ECU'},
    'URU': {'Uruguayan Primera División': 'URU'}, 'PER': {'Liga 1 de Fútbol Profesional': 'PER'},
    'PAR': {'Paraguayan Primera División': 'PAR'}, 'BOL': {'División de Fútbol Profesional': 'BOL'},
    'VEN': {'Venezuelan Primera División': 'VEN'}, 'RSA': {'South African Premier Division': 'RSA'},
    'IRN': {'Persian Gulf Pro League': 'IRN'}, 'CAN': {'Canadian Premier League': 'CAN'},
    'BEL': {'Challenger Pro League': 'B2'}, 'GER': {'3. Fußball-Liga': 'D3'}, 'NED': {'Eerste Divisie': 'N2'},
    'IND': {'Indian Super League': 'IND'}}
NOWE = {'SWE2': 'Szwecja Superettan', 'USL': 'USA USL Championship', 'BRA2': 'Brazylia Serie B', 'JAP2': 'Japonia J2',
        'CZE': 'Czechy 1. liga', 'CRO': 'Chorwacja HNL', 'SRB': 'Serbia SuperLiga', 'UKR': 'Ukraina Premier Liha',
        'KOR': 'Korea K League 1', 'KSA': 'Arabia Saudyjska', 'AUS': 'Australia A-League', 'BUL': 'Bułgaria', 'HUN': 'Węgry NB I',
        'CHI': 'Chile', 'COL': 'Kolumbia', 'ECU': 'Ekwador', 'URU': 'Urugwaj', 'PER': 'Peru', 'PAR': 'Paragwaj', 'BOL': 'Boliwia',
        'VEN': 'Wenezuela', 'RSA': 'RPA', 'IRN': 'Iran', 'CAN': 'Kanada CPL', 'B2': 'Belgia Challenger Pro League',
        'D3': 'Niemcy 3. Liga', 'N2': 'Holandia Eerste Divisie', 'IND': 'Indie ISL'}
OF_JSON = {('2025', 'br.1'): 'BRA', ('2026', 'br.1'): 'BRA', ('2024-25', 'at.1'): 'AUT', ('2025-26', 'at.1-full'): 'AUT',
           ('2024-25', 'mx.1'): 'MEX', ('2025', 'ar.1'): 'ARG', ('2025', 'mls'): 'USA', ('2025', 'jp.1'): 'JAP',
           ('2025', 'cn.1'): 'CHN', ('2024-25', 'au.1'): 'AUS', ('2025', 'co.1'): 'COL'}
# koniec sezonu (do rozkładania dat meczów bez daty z plików wiki)
WIKI_END = {('NOR', '2025'): '2025-11-30', ('SWE', '2025'): '2025-11-09', ('FIN', '2025'): '2025-11-09',
            ('IRL', '2025'): '2025-11-01', ('DEN', '2025-26'): '2026-05-25', ('RUS', '2025-26'): '2026-05-17',
            ('SUI', '2025-26'): '2026-05-17', ('JAP', '2025'): '2025-12-06', ('JAP', '2026'): '2026-06-07',
            ('CHN', '2025'): '2025-11-22', ('CHN', '2026'): '2026-09-06', ('FIN', '2026'): '2026-08-23',
            ('DEN', '2026-27'): '2026-08-30', ('SUI', '2026-27'): '2026-09-05'}
WIKI_START = {('JAP', '2026'): '2026-02-06', ('CHN', '2026'): '2026-02-27', ('FIN', '2026'): '2026-04-04',
              ('DEN', '2026-27'): '2026-07-17', ('SUI', '2026-27'): '2026-07-24', ('IRL', '2025'): '2025-02-14',
              ('NOR', '2025'): '2025-03-29', ('SWE', '2025'): '2025-03-29', ('FIN', '2025'): '2025-04-05',
              ('DEN', '2025-26'): '2025-07-18', ('RUS', '2025-26'): '2025-07-19', ('SUI', '2025-26'): '2025-07-25',
              ('JAP', '2025'): '2025-02-14', ('CHN', '2025'): '2025-02-21'}


def season_range(s):
    return (pd.Timestamp(f'{s[:4]}-07-01'), pd.Timestamp(f'{int(s[:4]) + 1}-06-30')) if '-' in s else \
        (pd.Timestamp(f'{s}-01-01'), pd.Timestamp(f'{s}-12-31'))


def wfr(refresh):
    import pyreadr
    os.makedirs(WFR, exist_ok=True); out = []
    for c, comps in WFR_MAP.items():
        p = os.path.join(WFR, f'{c}.rds')
        if refresh or not os.path.exists(p):
            subprocess.run(['curl', '-sL', '-m', '120', '-o', p, REL.format(c)], check=False)
        try: d = list(pyreadr.read_r(p).values())[0]
        except Exception as e: print('wfr', c, e); continue
        d = d[(d.Gender == 'M') & d.Competition_Name.isin(comps) & d.HomeGoals.notna() & d.AwayGoals.notna()]
        out.append(pd.DataFrame(dict(Division=d.Competition_Name.map(comps), MatchDate=pd.to_datetime(d.Date),
                                     MatchTime=d.Time, HomeTeam=d.Home, AwayTeam=d.Away, FTHome=d.HomeGoals.astype(int),
                                     FTAway=d.AwayGoals.astype(int), src='fbref')))
    return pd.concat(out, ignore_index=True)


def ofjson():
    rows = []
    for (s, code), div in OF_JSON.items():
        f = os.path.join(RAW, 'football.json', s, code + '.json')
        if not os.path.exists(f): continue
        for x in json.load(open(f)).get('matches', []):
            sc = x.get('score')
            if not isinstance(sc, dict) or not sc.get('ft'): continue
            ht = sc.get('ht') or [None, None]
            rows.append(dict(Division=div, MatchDate=pd.Timestamp(x['date']), MatchTime=x.get('time'), HomeTeam=x['team1'],
                             AwayTeam=x['team2'], FTHome=sc['ft'][0], FTAway=sc['ft'][1], HTHome=ht[0], HTAway=ht[1],
                             src='openfootball'))
    return pd.DataFrame(rows)


ALIAS2 = {
 'SWE': {'AIK Stockholm': 'AIK', 'Östersund': 'Ostersunds', 'Östersunds FK': 'Ostersunds'},
 'USA': {'LA Galaxy': 'Los Angeles Galaxy', 'NE Revolution': 'New England Revolution', 'NYCFC': 'New York City',
         'New York RB': 'New York Red Bulls', 'Sporting KC': 'Sporting Kansas City'},
 'JAP': {'Yamaga': 'Matsumoto Yamaga', 'Tokyo Verdy': 'Verdy', 'Urawa Red Diamonds': 'Urawa Reds',
         'V-V Nagasaki': 'V-Varen Nagasaki'},
 'DEN': {'OB': 'Odense', 'AGF': 'Aarhus', 'AGF Aarhus': 'Aarhus', 'Copenhagen': 'FC Copenhagen', 'Randers': 'Randers FC'},
 'ARG': {'Arg Juniors': 'Argentinos Jrs', 'Argentinos Jun': 'Argentinos Jrs', 'Argentinos Juniors': 'Argentinos Jrs',
         'Independiente Rivadavia': 'Ind. Rivadavia', 'Instituto Atlético Central Córdoba': 'Instituto',
         'Instituto de Córdoba': 'Instituto', 'CC Córdoba': 'Central Cordoba', 'Cen. Córdoba–SdE': 'Central Cordoba',
         'Central Córdoba SdE': 'Central Cordoba', 'Central Córdoba': 'Central Cordoba', 'Atlé Tucumán': 'Atl. Tucuman',
         'Tucumán': 'Atl. Tucuman', 'Atlético Tucumán': 'Atl. Tucuman', 'Estudiantes–LP': 'Estudiantes L.P.',
         'Estudiantes': 'Estudiantes L.P.', 'Estudiantes de La Plata': 'Estudiantes L.P.', 'Gimnasia ELP': 'Gimnasia L.P.',
         'Gimnasia–LP': 'Gimnasia L.P.', 'Gimnasia de La Plata': 'Gimnasia L.P.', "Newell's OB": 'Newells Old Boys',
         "Newell's Old Boys": 'Newells Old Boys', 'Rosario Cent': 'Rosario Central', 'Defensa y Just': 'Defensa y Justicia',
         'Deportivo Riestra': 'Dep. Riestra', 'Talleres': 'Talleres Cordoba', 'Talleres de Córdoba': 'Talleres Cordoba',
         'Sarmiento': 'Sarmiento Junin', 'Sarmiento de Junín': 'Sarmiento Junin', 'CA Unión': 'Union de Santa Fe',
         'Unión': 'Union de Santa Fe', 'Unión de Santa Fe': 'Union de Santa Fe', 'Belgrano de Córdoba': 'Belgrano',
         'Club Atlético Belgrano': 'Belgrano', 'Arsenal': 'Arsenal Sarandi', 'Colón': 'Colon Santa Fe',
         'Vélez Sarsfield': 'Velez Sarsfield', 'Huracán': 'Huracan', 'CA Huracán': 'Huracan', 'Lanús': 'Lanus',
         'Racing': 'Racing Club', 'River': 'River Plate', 'Boca': 'Boca Juniors'},
 'BRA': {'Ath Paranaense': 'Athletico-PR', 'CA Paranaense': 'Athletico-PR', 'Athletico Paranaense': 'Athletico-PR',
         'Athletico-PR': 'Athletico-PR', 'Atl Goianiense': 'Atletico GO', 'Atlético Goianiense': 'Atletico GO',
         'Atlético Mineiro': 'Atletico-MG', 'Red Bull Bragantino': 'Bragantino', 'RB Bragantino': 'Bragantino',
         'Botafogo (RJ)': 'Botafogo RJ', 'Botafogo FR': 'Botafogo RJ', 'Botafogo': 'Botafogo RJ', 'Flamengo': 'Flamengo RJ',
         'CR Flamengo': 'Flamengo RJ', 'Vasco da Gama': 'Vasco', 'CR Vasco da Gama': 'Vasco', 'América (MG)': 'America MG', 'CA Mineiro': 'Atletico-MG'},
 'CHN': {'Henan': 'Henan Songshan Longmen', 'Henan FC': 'Henan Songshan Longmen', 'Shenzhen Peng City': 'Shenzhen Xinpengcheng',
         'Jinmen Tiger': 'Tianjin Jinmen Tiger', 'Zhejiang': 'Zhejiang Professional', 'Zhejiang FC': 'Zhejiang Professional',
         'Shandong Taishan': 'Shandong Taishan', 'Shanghai Port FC': 'Shanghai Port'},
 'MEX': {'Atlético San Luis': 'Atl. San Luis', 'San Luis': 'Atl. San Luis', 'UANL': 'U.A.N.L.- Tigres',
         'UANL Tigres': 'U.A.N.L.- Tigres', 'Tigres UANL': 'U.A.N.L.- Tigres', 'Tigres': 'U.A.N.L.- Tigres',
         'UNAM': 'U.N.A.M.- Pumas', 'Pumas UNAM': 'U.N.A.M.- Pumas', 'Pumas': 'U.N.A.M.- Pumas', 'América': 'Club America',
         'CF América': 'Club America', 'León': 'Club Leon', 'Club León': 'Club Leon', 'Tijuana': 'Club Tijuana',
         'Guadalajara': 'Guadalajara Chivas', 'Chivas': 'Guadalajara Chivas', 'FC Juárez': 'Juarez', 'Santos': 'Santos Laguna',
         'Mazatlán': 'Mazatlan FC', 'Atlético': 'Atl. San Luis', 'Deportivo Guadalajara': 'Guadalajara Chivas', 'Gallos Blancos': 'Queretaro', 'Mazatlán FC': 'Mazatlan FC'},
 'ROM': {'CS U Craiova': 'Univ. Craiova', 'Universitatea Craiova': 'Univ. Craiova', 'CS Universitatea Craiova': 'Univ. Craiova',
         'FC U Craiova': 'U Craiova 1948', 'FC U Craiova 1948': 'U Craiova 1948', 'U Cluj': 'U. Cluj',
         'Universitatea Cluj': 'U. Cluj', 'Dinamo București': 'Din. Bucuresti', 'Rapid București': 'FC Rapid Bucuresti',
         'Sepsi': 'Sepsi Sf. Gheorghe', 'Sepsi OSK': 'Sepsi Sf. Gheorghe', 'Oțelul Galați': 'Otelul'},
 'RUS': {'Nizhny Novgorod': 'Pari NN', 'Pari Nizhny Novgorod': 'Pari NN', 'Krylia Sovetov Samara': 'Krylya Sovetov',
         'Krylia Sovetov': 'Krylya Sovetov', 'Samara': 'Krylya Sovetov', 'Akron Tolyatti': 'Akron Togliatti',
         'FK Akron Tolyatti': 'Akron Togliatti', "D'mo Makhachkala": 'Dynamo Makhachkala', 'Dynamo Mosc': 'Dynamo Moscow',
         'Loko Moscow': 'Lokomotiv Moscow', 'Lokomotiv Moskva': 'Lokomotiv Moscow', 'Zenit Saint Petersburg': 'Zenit',
         'Zenit St. Petersburg': 'Zenit', 'Rostov': 'FK Rostov', 'Baltika Kaliningrad': 'Baltika',
         'FC Baltika Kaliningrad': 'Baltika', 'FK Rodina Moskva': 'Rodina Moscow', 'Akhmat': 'Akhmat Grozny'},
}


# nazwy z 365scores/ESPN → nazwy football-data (stosowane tylko, gdy cel istnieje w danej lidze)
ALIAS_ZEWN = {'PSG': 'Paris SG', 'Paris Saint-Germain': 'Paris SG', 'Borussia Mönchengladbach': "M'gladbach",
              'Borussia Monchengladbach': "M'gladbach", 'MK Dons': 'Milton Keynes Dons', 'Vaasa PS': 'VPS',
              'Başakşehir': 'Buyuksehyr', 'Basaksehir': 'Buyuksehyr', 'Istanbul Basaksehir': 'Buyuksehyr',
              'Deportivo A Coruña': 'La Coruna', 'Deportivo La Coruna': 'La Coruna', 'Atletico Madrid': 'Ath Madrid',
              'Atlético Madrid': 'Ath Madrid', 'Athletic Bilbao': 'Ath Bilbao', 'Athletic Club': 'Ath Bilbao',
              'Sporting CP': 'Sp Lisbon', 'Sporting Lisbon': 'Sp Lisbon', 'Sporting Braga': 'Sp Braga', 'SC Braga': 'Sp Braga',
              'STVV': 'St Truiden', 'Sint-Truiden': 'St Truiden', 'La Louvière Centre': 'RAAL La Louviere',
              'Asteras Aktor': 'Asteras Tripolis', 'Wolverhampton': 'Wolves', 'Nottingham Forest': "Nott'm Forest",
              'Bayer Leverkusen': 'Leverkusen', 'Eintracht Frankfurt': 'Ein Frankfurt', 'Hellas Verona': 'Verona',
              'Real Sociedad': 'Sociedad', 'Rayo Vallecano': 'Vallecano', 'Celta Vigo': 'Celta', 'Espanyol Barcelona': 'Espanol',
              'Olympiacos': 'Olympiakos', 'PAOK Salonika': 'PAOK', 'Red Star Belgrade': 'Crvena Zvezda', 'Sheffield Wednesday': 'Sheffield Weds',
              'Queens Park Rangers': 'QPR', 'West Bromwich Albion': 'West Brom', 'Brighton & Hove Albion': 'Brighton',
              'Tottenham Hotspur': 'Tottenham', 'Newcastle United': 'Newcastle', 'West Ham United': 'West Ham',
              'Leeds United': 'Leeds', 'Leicester City': 'Leicester', 'Norwich City': 'Norwich', 'Stoke City': 'Stoke',
              'Swansea City': 'Swansea', 'Cardiff City': 'Cardiff', 'Coventry City': 'Coventry', 'Preston North End': 'Preston',
              'Blackburn Rovers': 'Blackburn', 'Bristol City': 'Bristol City', 'Oxford United': 'Oxford', 'Paderborn 07': 'Paderborn',
              'Austria Lustenau': 'A. Lustenau', 'Austria Vienna': 'Austria Vienna', 'Austria Wien': 'Austria Vienna'}
ALIAS_ZEWN.update({'Inter Milan': 'Inter', 'Internazionale': 'Inter', 'Amed SK': 'Amedspor', 'Östers IF': 'Oster',
                   'Osters IF': 'Oster', 'Stabæk': 'Stabaek', 'Deportivo Cuenca': 'CD Cuenca'})
NIE_MAPUJ = {'Cerro Largo', 'NK Zagreb', 'FSV Frankfurt', 'Bury Town', 'Bayern Munich II', 'Bayern München II',
             'Felixstowe & Walton Utd.', 'Redditch Utd', 'Welling Utd', 'Ath Paranaense', 'Paraná', 'Remo', 'Clube do Remo',
             'Naft Tehran', 'Sanat Naft', 'Rukh Lviv', 'Esteghlal Ahvaz', 'Esteghlal Khuz', 'Wieczysta Krakow'}
TOK_POMIN = {'fc', 'cf', 'ac', 'sc', 'if', 'is', 'ik', 'bk', 'sk', 'cd', 'ud', 'sd', 'kaa', 'krc', 'kv', 'kvc', 'rsc', 'ogc', 'club',
             'calcio', 'de', 'la', 'el', 'cp', 'afc', 'cfc', 'the', 'fbc', 'ssc', 'as', 'us'}
TOK_ROZW = {'man': 'manchester', 'utd': 'united', 'sp': 'sporting', 'st': 'saint', 'ath': 'athletic', 'nott': 'nottingham',
            'nottm': 'nottingham', 'weds': 'wednesday', 'wed': 'wednesday', 'ein': 'eintracht', 'dep': 'deportivo',
            'a': 'austria', 'jrs': 'juniors', 'ind': 'independiente'}
OGOLNE = {'united', 'city', 'town', 'athletic', 'athletico', 'atletico', 'sporting', 'real', 'rovers', 'wanderers', 'county',
          'albion', 'deportivo', 'racing', 'olympique', 'dynamo', 'dinamo', 'union', 'nacional', 'national', 'central',
          'sport', 'sports', 'fk', 'nk', 'ii', 'b', 'reserves', 'women', 'austria', 'saint', 'juniors', 'independiente'}
ZNAKI = str.maketrans({'ł': 'l', 'Ł': 'L', 'ø': 'o', 'Ø': 'O', 'æ': 'ae', 'Æ': 'Ae', 'ß': 'ss', 'đ': 'd', 'Đ': 'D', 'ı': 'i',
                       'ð': 'd', 'þ': 'th', 'œ': 'oe'})


def _tok(s):
    import unicodedata as _u
    s = str(s).translate(ZNAKI)
    t = re.findall(r'[a-z0-9]+', _u.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower().replace("'", ''))
    return [TOK_ROZW.get(x, x) for x in t if x not in TOK_POMIN]


def _sprzeczne(zrodlo, baza):
    """Czy obie nazwy maja WLASNY, charakterystyczny czlon, ktorego nie ma ta druga.
    22.09.2026. Bez tego testu dopasowanie rozmyte scalalo ROZNE kluby:
      "Melbourne Victory"   -> "Melbourne City FC"
      "Deportivo Lara"      -> "Deportivo La Guaira"
      "Radnicki Nis" oraz "Radnicki Kragujevac" -> "Radnicki 1923"
    Wspolny czlon ("Melbourne", "Deportivo", "Radnicki") to nazwa miasta albo
    slowo rodzajowe; rozroznia dopiero ten drugi. Gdy KAZDA strona ma swoj wlasny,
    to sa dwa rozne kluby, choćby litery byly podobne.
    Nie blokuje skrotow: "Hull" -> "Hull City" ma czlony {hull} c {hull, city},
    wiec zrodlo nie wnosi nic wlasnego i dopasowanie przechodzi."""
    import difflib as _d
    tz, tb = set(_tok(zrodlo)), set(_tok(baza))
    if not tz or not tb: return False

    def _ten_sam(x, y):
        # Czy to ten sam czlon zapisany inaczej ("espanyol"/"espanol", "munchen"/"munich"),
        # czy dwa rozne slowa ("lara"/"guaira", "victory"/"city"). Zmierzone 22.09.2026:
        # czlony bedace wariantem pisowni maja WSPOLNY PRZEDROSTEK >= 3 znaki (3-5),
        # a czlony roznych klubow maja przedrostek 0 — nawet gdy ocena podobienstwa
        # jest wysoka ("lara"/"guaira" to 0,60, wiecej niz "munchen"/"munich" bylo by
        # warte bez przedrostka). Dlatego rozstrzyga przedrostek, a ocena tylko go potwierdza.
        if x == y: return True
        if min(len(x), len(y)) >= 4 and (x.startswith(y) or y.startswith(x)): return True
        wsp = 0
        for i in range(min(len(x), len(y))):
            if x[i] != y[i]: break
            wsp += 1
        return wsp >= 3 and _d.SequenceMatcher(None, x, y).ratio() >= 0.65

    wlasne_z = {t for t in tz if not any(_ten_sam(t, u) for u in tb)}
    wlasne_b = {t for t in tb if not any(_ten_sam(t, u) for u in tz)}
    wl_z = {t for t in wlasne_z if t not in OGOLNE and len(t) >= 3}
    return bool(wl_z) and bool(wlasne_b)


def match_one(n, pool, div, zwroc_sile=False):
    """Zwraca nazwe z puli albo None. Z zwroc_sile=True zwraca (nazwa, sila),
    gdzie sila rosnie wraz z pewnoscia dopasowania — canon() uzywa jej do
    rozstrzygania, ktora nazwa ma prawo zajac dany klub."""
    import difflib
    def w(cel, sila): return (cel, sila) if zwroc_sile else cel
    a = ALIAS2.get(div, {})
    if n in a: return w(a[n], 9)
    if n in NIE_MAPUJ: return w(n if n in pool else None, 9)
    if n in ALIAS_ZEWN and ALIAS_ZEWN[n] in pool: return w(ALIAS_ZEWN[n], 9)
    k = norm(str(n).translate(ZNAKI))
    base = {norm(str(b).translate(ZNAKI)): b for b in pool}
    if k in base: return w(base[k], 8)
    if len(k) >= 5:
        cand = {b for kb_, b in base.items() if len(kb_) >= 5 and (k.startswith(kb_) or kb_.startswith(k) or kb_.endswith(k)
                                                                   or (len(kb_) >= 8 and k.endswith(kb_)))}
        cand = {b for b in cand if not _sprzeczne(n, b)}
        if len(cand) == 1: return w(cand.pop(), 5)
    # tokeny bez dopisków (FC, KAA, OGC…) i z rozwinięciami skrótów (Man→Manchester, Sp→Sporting)
    tn = _tok(n)
    if tn:
        st = set(tn)
        eq = [b for b in pool if set(_tok(b)) == st]
        if len(eq) == 1: return w(eq[0], 7)
        # nazwa w bazie krótsza (AIK ⊂ AIK Solna, Hull ⊂ Hull City) — ale nie same ogólniki (United, Athletic…)
        def _goly(b):   # „FC Lviv”, „SC Paderborn”: po odrzuceniu FC zostaje samo miasto — to za mało
            surowe = re.findall(r'[a-z0-9]+', str(b).lower())
            return len(_tok(b)) == 1 and len(surowe) > 1
        kr = [b for b in pool if _tok(b) and set(_tok(b)) < st and not set(_tok(b)) <= OGOLNE and not _goly(b)]
        if len(kr) == 1: return w(kr[0], 4)
        # nazwa ze źródła krótsza — tylko jednowyrazowa i charakterystyczna (Shamrock → Shamrock Rovers)
        if len(tn) == 1 and len(tn[0]) >= 5 and tn[0] not in OGOLNE:
            dl = [b for b in pool if st < set(_tok(b))]
            if len(dl) == 1: return w(dl[0], 4)
    # sorted(): bez tego kolejnosc zalezy od ziarna hasha procesu
    m = difflib.get_close_matches(k, sorted(base), n=1, cutoff=0.8)
    if m and not _sprzeczne(n, base[m[0]]): return w(base[m[0]], 2)
    return w(None, 0)


def canon(df, kb):
    """Ujednolica nazwy do nazw kb (tylko drużyny aktywne od 07.2022, żeby nie łapać starych nazw), nowe drużyny —
    do pierwszej napotkanej wersji."""
    out, mapping = [], {}
    rec = kb[kb.MatchDate >= '2022-07-01']
    for div, g in df.groupby('Division'):
        base = sorted(set(rec.loc[rec.Division == div, 'HomeTeam']) | set(rec.loc[rec.Division == div, 'AwayTeam']))
        known, sila = {}, {}
        for src in ('espn', 'sofa', 'fbref', 'openfootball', 'wiki'):
            gs = g[g.src == src]
            names = sorted(set(gs.HomeTeam) | set(gs.AwayTeam))
            for n in names:
                if n in known: continue
                pool = base + sorted(set(known.values()) - set(base))
                cel, sl = match_one(n, pool, div, zwroc_sile=True)
                known[n], sila[n] = (cel or n), (sl if cel else 0)

        # W JEDNEJ LIDZE przypisanie musi byc ROZNOWARTOSCIOWE: dwie rozne nazwy ze
        # zrodel nie moga wskazywac tego samego klubu. 22.09.2026 wskazywaly, i to
        # scalalo ROZNE kluby w jeden: "Melbourne Victory" wpadalo na "Melbourne City FC",
        # "Radnicki Nis" i "Radnicki Kragujevac" na "Radnicki 1923", a w bazie pojawialy
        # sie mecze, w ktorych klub gra SAM ZE SOBA (122 takie mecze, m.in. derby Sydney).
        # Przy konflikcie klub zostaje przy nazwie o NAJWYZSZEJ sile dopasowania;
        # pozostale zachowuja wlasna nazwe i wchodza jako osobne kluby. Tracimy wtedy
        # powiazanie z historia, ale NIE psujemy historii cudzej — a to jest gorszy blad.
        zajete = {}
        # Kolejnosc ma znaczenie i pierwszenstwo jest BEZWZGLEDNE dla nazwy, ktora wskazuje
        # sama siebie. Bez tego "W Sydney" (Western Sydney Wanderers) zajmowalo nazwe
        # "Sydney FC", bo mialo wyzsza sile dopasowania i trafialo wczesniej — a wtedy
        # prawdziwe "Sydney FC" tez zostawalo przy "Sydney FC" i derby dalej byly
        # meczem klubu z samym soba. Nazwa zawsze ma prawo do siebie.
        for n in sorted(known, key=lambda x: (0 if known[x] == x else 1, -sila.get(x, 0), x)):
            cel = known[n]
            if cel not in base:          # nowa druzyna, nie zabiera nikomu miejsca
                if cel in zajete and zajete[cel] != n:
                    known[n] = n
                else:
                    zajete.setdefault(cel, n)
                continue
            if cel in zajete:
                print(f'  UZUPELNIJ_LIGI [{div}]: "{n}" i "{zajete[cel]}" wskazuja na ten sam klub '
                      f'"{cel}". Zostaje "{zajete[cel]}" (dopasowanie pewniejsze); "{n}" wchodzi '
                      f'jako osobny klub. Jesli to ta sama druzyna, dopisz ja do ALIAS2["{div}"].')
                known[n] = n
            else:
                zajete[cel] = n
        mapping[div] = known
        g = g.copy(); g['HomeTeam'] = g.HomeTeam.map(known); g['AwayTeam'] = g.AwayTeam.map(known); out.append(g)
    return pd.concat(out, ignore_index=True), mapping


def wiki():
    rows = []
    for f in sorted(glob.glob(os.path.join(HERE, 'eu', 'wiki', '*.csv'))):
        d = pd.read_csv(f, dtype={'season': str})
        d = d.dropna(subset=['fh', 'fa'])
        rows.append(pd.DataFrame(dict(Division=d['div'], season=d.season, phase=d.phase, MatchDate=pd.to_datetime(d.date),
                                      HomeTeam=d.home.str.strip(), AwayTeam=d.away.str.strip(), FTHome=d.fh.astype(int),
                                      FTAway=d.fa.astype(int), src='wiki')))
    if not rows:
        print('  wiki: brak plikow eu/wiki/*.csv — matryce Wikipedii pominiete')
        return pd.DataFrame(columns=['Division', 'season', 'phase', 'MatchDate', 'HomeTeam', 'AwayTeam',
                                     'FTHome', 'FTAway', 'src'])
    return pd.concat(rows, ignore_index=True)


def main():
    refresh = '--refresh' in sys.argv
    kb = pd.read_sql('select Division, MatchDate, HomeTeam, AwayTeam from matches where src != "extra"',
                     sqlite3.connect(os.path.join(HERE, 'kb.sqlite')), parse_dates=['MatchDate'])
    last = kb.groupby('Division').MatchDate.max()
    import zewn
    NOWE.update(zewn.NOWE_DIV)
    a = pd.concat([wfr(refresh), ofjson(), zewn.pilka(), wiki()], ignore_index=True)   # zewn: ESPN + Sofascore z Apps Script
    a = a[a.HomeTeam.fillna('').astype(str).str.strip().ne('') & a.AwayTeam.fillna('').astype(str).str.strip().ne('')]
    a, mapping = canon(a, kb)
    # tylko mecze nowsze niż to, co już jest w kb (dla lig istniejących); nowe ligi – całość
    a = a[a.MatchDate.isna() | (a.MatchDate > a.Division.map(last).fillna(pd.Timestamp('1900-01-01')))]
    dated = a[a.MatchDate.notna()].copy()
    dated['k'] = dated.Division + '|' + dated.MatchDate.dt.strftime('%Y-%m-%d') + '|' + dated.HomeTeam.map(norm) + '|' + dated.AwayTeam.map(norm)
    dated = dated.sort_values('src').drop_duplicates('k')   # fbref < openfootball (alfabetycznie) – jeden rekord na mecz
    # ± 1 dzień różnicy stref czasowych między źródłami
    dated['k2'] = dated.Division + '|' + dated.HomeTeam.map(norm) + '|' + dated.AwayTeam.map(norm)
    dated = dated.sort_values(['k2', 'MatchDate'])
    dup = (dated.k2 == dated.k2.shift()) & ((dated.MatchDate - dated.MatchDate.shift()).dt.days.abs() <= 2)
    dated = dated[~dup]
    # wiki: dodaj tylko mecze, których nie ma z datą w tym sezonie
    add = []
    w = a[a.src == 'wiki'] if 'src' in a.columns else pd.DataFrame()
    if len(w) == 0 or 'season' not in w.columns:
        print('  wiki: nic do uzupelnienia (brak matryc albo brak kolumny season) — pomijam ten krok')
        w = w.iloc[0:0]
        grupy = []
    else:
        grupy = list(w.groupby(['Division', 'season']))
    for (div, s), g in grupy:
        lo, hi = season_range(s)
        lo = pd.Timestamp(WIKI_START.get((div, s), lo)); hi = pd.Timestamp(WIKI_END.get((div, s), hi))
        dd = dated[(dated.Division == div) & (dated.MatchDate >= lo - pd.Timedelta(days=30)) & (dated.MatchDate <= hi)]
        dd_src = dd[dd.src != 'wiki']
        kbs = kb[(kb.Division == div) & (kb.MatchDate >= lo - pd.Timedelta(days=30)) & (kb.MatchDate <= hi)]
        have = {}
        for h, aw in list(zip(dd.HomeTeam, dd.AwayTeam)) + list(zip(kbs.HomeTeam, kbs.AwayTeam)):
            have[(norm(h), norm(aw))] = have.get((norm(h), norm(aw)), 0) + 1
        rest = []
        for r in g.itertuples():
            key = (norm(r.HomeTeam), norm(r.AwayTeam))
            if have.get(key, 0) > 0: have[key] -= 1; continue
            rest.append(r)
        if not rest: continue
        start = max(lo, dd_src.MatchDate.max() + pd.Timedelta(days=1) if len(dd_src) else lo, kbs.MatchDate.max() + pd.Timedelta(days=1) if len(kbs) else lo)
        order = {'regular': 0, 'regional-east': 0, 'regional-west': 0}
        rng = np.random.default_rng(19)
        rest = [rest[i] for i in rng.permutation(len(rest))]          # przemieszaj (matryca nie jest chronologiczna)
        rest.sort(key=lambda r: order.get(r.phase, 1))                # fazy końcowe na koniec sezonu
        # 22.09.2026, druga poprawka. Najpierw bylo date_range(start, max(hi, start), ...),
        # ktore przy start za koncem okna zwracalo N KOPII JEDNEJ DATY (143 mecze CHN
        # z 2026-09-07). Rownomierne rozlozenie to naprawilo tylko polowicznie: daty
        # przestaly sie stakowac, ale KLUB nadal trafial dwa razy na ten sam dzien,
        # bo rozkladalismy mecze po LICZBIE, nie ogladajac, kto w nich gra.
        # Teraz przydzielamy daty tak, zeby zaden klub nie gral dwa razy jednego dnia.
        # To nie jest zgadywanie na sile: te daty sa z zalozenia przyblizone (matryca
        # wiki nie zawiera dat), wiec wybranie sposrod nich takiego wariantu, ktory
        # spelnia oczywista regule terminarza, jest BLIZEJ prawdy niz wariant, ktory
        # jej lamie. Zajete dni zaczytujemy tez z meczow, ktore juz maja prawdziwa date,
        # zeby dopisane nie wpadaly na nie.
        zajete = set()
        for _df in (dd, kbs):
            for _h, _a, _d in zip(_df.HomeTeam, _df.AwayTeam, _df.MatchDate):
                _d = pd.Timestamp(_d).normalize()
                zajete.add((norm(_h), _d)); zajete.add((norm(_a), _d))

        koniec = max(hi, start)
        dni = list(pd.date_range(start, koniec).normalize()) or [start]
        przydzial, rozszerzono = [], False
        for r in rest:
            kh, ka = norm(r.HomeTeam), norm(r.AwayTeam)
            wybrany = None
            for d in dni:
                if (kh, d) not in zajete and (ka, d) not in zajete:
                    wybrany = d; break
            if wybrany is None:                      # okno wyczerpane — dokladamy dni na koncu
                wybrany = dni[-1] + pd.Timedelta(days=1)
                dni.append(wybrany); rozszerzono = True
            zajete.add((kh, wybrany)); zajete.add((ka, wybrany))
            przydzial.append((r, wybrany))
        if rozszerzono:
            print(f'  wiki {div} {s}: okno sezonu za krotkie dla {len(rest)} meczow — '
                  f'rozszerzam do {dni[-1].date()}, zeby zaden klub nie gral 2x jednego dnia.')
        for r, d in przydzial:
            add.append(dict(Division=div, MatchDate=d, HomeTeam=r.HomeTeam, AwayTeam=r.AwayTeam, FTHome=r.FTHome,
                            FTAway=r.FTAway, src='wiki'))
        print(f'  wiki {div} {s}: {len(g)} meczów w matrycy, dopisano {len(rest)} (daty przybliżone {start.date()}–{hi.date()})')
    out = pd.concat([dated.drop(columns=['k', 'k2', 'season', 'phase'], errors='ignore'), pd.DataFrame(add)], ignore_index=True)
    out['MatchDate'] = out.MatchDate.dt.strftime('%Y-%m-%d')
    out = out.sort_values(['Division', 'MatchDate'])
    out.to_csv(os.path.join(HERE, 'ligi_extra.csv'), index=False)
    with open(os.path.join(HERE, 'ligi_extra_nazwy.json'), 'w') as f:
        json.dump({d: {k: v for k, v in m.items() if k != v} for d, m in mapping.items()}, f, ensure_ascii=False, indent=0)
    s = out.groupby('Division').agg(meczów=('MatchDate', 'size'), od=('MatchDate', 'min'), do=('MatchDate', 'max'))
    print(s.to_string())


if __name__ == '__main__':
    main()
