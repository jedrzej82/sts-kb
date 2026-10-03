"""DODATKOWE ZRODLA STATYSTYK (03.10.2026) — uruchamiany w Termuxie na telefonie uzytkownika, jak kursy_bukmacherow.py
(srodowisko przebiegu nie ma dostepu do tych serwisow). Tylko biblioteka standardowa Pythona.

TRYB OBSERWACJI: pliki tylko zbieraja dane na Dysk. Zadna regula przebiegu ich nie uzywa, dopoki nie przejda testu
wstecznego i decyzji uzytkownika (CLAUDE.md: reguly nigdy nie wyprzedzaja kodu).

Zrodla (D = raz dziennie, P = kazde uruchomienie):
  1  eloratings.net    D  Elo reprezentacji                                  -> zrodla_elo_reprezentacji_*.csv.gz
  2  FotMob            P  mecze dnia; dla meczow w ciagu 3,5 h i zakonczonych: xG, sklady, nieobecni, stadion, sedzia
                                                                              -> zrodla_fotmob_mecze_*, zrodla_fotmob_szczegoly_*
  3  Sofascore         P  mecze/wyniki 7 sportow (wczoraj+dzis); pilka w ciagu 3,5 h: sklad potwierdzony, nieobecni
                                                                              -> zrodla_sofascore_mecze_*, zrodla_sofascore_sklady_*
  4  Transfermarkt     D  kontuzjowani i wartosci kadr, 25 lig                -> zrodla_transfermarkt_*
  5  Understat         D  xG meczow 6 lig (--historia: sezony od 2014)        -> zrodla_understat_*
  6  Tennis Abstract   D  Elo ATP/WTA (ogolne i wg nawierzchni)               -> zrodla_tenis_elo_*
  7  Darty             D  DartsOrakel /api/stats/player: srednia, % meczow, % checkout, srednia z 9, 180-ki (rok wstecz)
                                                                              -> zrodla_darty_ranking_*
  8  NHL               P  wyniki/terminarz NHL (api-web.nhle.com) + bramkarze (Daily Faceoff)
                                                                              -> zrodla_nhl_*, zrodla_nhl_bramkarze_*
  9  Open-Meteo        P  pogoda na godzine meczu dla meczow z wspolrzednymi stadionu (FotMob/Sofascore)
                                                                              -> zrodla_pogoda_*
  10 Sedziowie         P  sedzia meczu + jego srednie kartek (Sofascore), sedzia z FotMob -> zrodla_sedziowie_*

Wszystko z jednego uruchomienia w JEDNYM pliku zrodla_RRRR-MM-DD_GG-MM.zip, wysylanym przez rclone do podfolderu
baza-wiedzy/zrodla/ (nie do folderu przebiegu). W zipie tez zrodla_diag_*.txt (status kazdego zrodla) i
zrodla_surowe_*.jsonl.gz (do 4 surowych odpowiedzi na zrodlo, przyciete) — z nich poprawiamy parsery bez zrzutow ekranu.

Uzycie:  python zrodla.py [--katalog /sdcard/Download] [--tylko fotmob,nhl] [--historia] [--budzet-min 12] [--wszystkie-dzienne] [--bez-wysylki]
         Setka Cup (s24): cron sam pobiera 21 dni wstecz przy pierwszym uruchomieniu i dociaga zaleglosci w kolejnych."""
import csv
import datetime as dt
import gzip
import html as _html
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile

UA = 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36'
H_JSON = {'User-Agent': UA, 'Accept': 'application/json, text/plain, */*', 'Accept-Language': 'en-GB,en;q=0.9'}
H_HTML = {'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8', 'Accept-Language': 'en-GB,en;q=0.9'}
CTX = ssl.create_default_context()
STAN = os.path.expanduser('~/.zrodla_stan.json')
OKNO_H = 3.5            # szczegoly dla meczow zaczynajacych sie w ciagu tylu godzin
MAKS_SZCZEGOLY = 60     # na zrodlo i uruchomienie
SURowe_NA_ZRODLO = 4
SUROWE_LIMIT = {'90minut': 10, 'setka': 12}   # 03.10.2026: strony lig 90minut potrzebne w calosci do sprawdzenia parsera
SURowe_MAKS_B = 300_000

H_SOFA = {**H_JSON, 'Referer': 'https://www.sofascore.com/', 'Origin': 'https://www.sofascore.com'}
# 03.10: 403 {"reason": "challenge"} z urllib — warianty probowane po kolei, pierwszy dzialajacy obsluguje cale uruchomienie;
# kazda proba zapisana w zrodla_sofascore_proby_* (Playwright dopiero, gdy wszystkie odpadna — w Termuxie wymaga proot)
H_SOFA_PELNE = {'User-Agent': UA, 'Accept': '*/*', 'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://www.sofascore.com/', 'Origin': 'https://www.sofascore.com', 'Cache-Control': 'no-cache',
                'sec-ch-ua': '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"', 'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"', 'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-site'}
SOFA_WARIANTY = (('urllib', H_SOFA, None), ('urllib_pelne', H_SOFA_PELNE, None), ('curl', H_SOFA_PELNE, ['--http1.1']),
                 ('curl_http2', H_SOFA_PELNE, ['--http2']))
SOFA = ('https://api.sofascore.com/api/v1', 'https://www.sofascore.com/api/v1')
SOFA_SPORTY = ('football', 'basketball', 'ice-hockey', 'handball', 'volleyball', 'darts', 'tennis')
TM_LIGI = ('GB1', 'GB2', 'ES1', 'ES2', 'IT1', 'IT2', 'L1', 'L2', 'FR1', 'FR2', 'NL1', 'PO1', 'BE1', 'TR1', 'PL1',
           'A1', 'C1', 'SC1', 'DK1', 'SE1', 'NO1', 'GR1', 'TS1', 'UKR1', 'RU1')
US_LIGI = ('EPL', 'La_liga', 'Bundesliga', 'Serie_A', 'Ligue_1', 'RFPL')


def dekoduj(b):
    """Bajty -> tekst. 03.10.2026: 90minut.pl jest w ISO-8859-2 — utf-8 'replace' gubil polskie litery w nazwach
    druzyn („Wis�a”). Najpierw scisle utf-8, potem kodowanie z <meta charset>, na koncu cp1250."""
    try: return b.decode('utf-8')
    except UnicodeDecodeError: pass
    m = re.search(rb'charset=["\']?([A-Za-z0-9_-]+)', b[:3000])
    for kod in ([m.group(1).decode('ascii', 'ignore')] if m else []) + ['cp1250']:
        try: return b.decode(kod)
        except (LookupError, UnicodeDecodeError): continue
    return b.decode('utf-8', 'replace')


def curl_get(url, naglowki, opcje=()):
    """Systemowy curl (Termux: OpenSSL + nghttp2) -> (kod, tekst); (0, opis) gdy brak curla albo blad."""
    if not shutil.which('curl'): return 0, 'brak curl'
    cmd = ['curl', '-sS', '--compressed', '-m', '30', '-o', '-', '-w', '\n__KOD__%{http_code}', *opcje]
    for k, v in naglowki.items():
        if k.lower() != 'accept-encoding': cmd += ['-H', f'{k}: {v}']
    try:
        r = subprocess.run(cmd + [url], capture_output=True, timeout=40)
    except (OSError, subprocess.SubprocessError) as e:
        return 0, f'{type(e).__name__}: {e}'
    out = dekoduj(r.stdout)
    tekst, _, kod = out.rpartition('\n__KOD__')
    return (int(kod) if kod.strip().isdigit() else 0), (tekst if kod.strip().isdigit() else r.stderr.decode('utf-8', 'replace'))


class Sesja:
    """Pobieranie z limitem czasu, licznikami HTTP i probkami surowych odpowiedzi do diagnozy."""

    def __init__(self, budzet_s):
        self.koniec = time.time() + budzet_s
        self.surowe, self.diag, self.kody = [], [], {}

    def czas(self):
        return time.time() < self.koniec

    def get(self, zrodlo, url, naglowki=H_JSON, proby=2, pauza=0.4, curl=None):
        """(kod HTTP, tekst) — nigdy nie rzuca; kod 0 = blad sieci, -1 = koniec budzetu czasu.
        curl = lista opcji -> zapytanie systemowym curlem (inny odcisk TLS niz Python; dla Sofascore)."""
        if not self.czas(): return -1, ''
        kod, tekst = 0, ''
        for i in range(proby):
            if curl is not None:
                kod, tekst = curl_get(url, naglowki, curl)
                if kod == 200 or kod in (401, 403, 404): break
                time.sleep(1.5 * (i + 1)); continue
            try:
                r = urllib.request.urlopen(urllib.request.Request(url, headers=naglowki), timeout=30, context=CTX)
                b = r.read()
                if r.headers.get('Content-Encoding') == 'gzip': b = gzip.decompress(b)
                kod, tekst = r.status, dekoduj(b)
                break
            except urllib.error.HTTPError as e:
                kod = e.code
                try: tekst = e.read().decode('utf-8', 'replace')
                except Exception: tekst = ''
                if e.code in (401, 403, 404): break
            except Exception as e:
                kod, tekst = 0, f'{type(e).__name__}: {e}'
            time.sleep(1.5 * (i + 1))
        time.sleep(pauza)
        self.kody.setdefault(zrodlo, {}).setdefault(kod, 0)
        self.kody[zrodlo][kod] += 1
        lim = SUROWE_LIMIT.get(zrodlo, SURowe_NA_ZRODLO)
        if sum(1 for s in self.surowe if s['zrodlo'] == zrodlo) < lim or kod != 200:
            if sum(1 for s in self.surowe if s['zrodlo'] == zrodlo) < lim * 3:
                self.surowe.append({'zrodlo': zrodlo, 'url': url, 'kod': kod, 'tekst': tekst[:SURowe_MAKS_B]})
        return kod, tekst

    def get_json(self, zrodlo, url, naglowki=H_JSON, **kw):
        kod, t = self.get(zrodlo, url, naglowki, **kw)
        if kod != 200: return None
        try: return json.loads(t)
        except ValueError: return None


# ---------- narzedzia parsowania (czyste funkcje — testy w tests/test_zrodla.py) ----------

def chodz(o):
    """Wszystkie slowniki w zagniezdzonym JSON-ie (w glab)."""
    stos = [o]
    while stos:
        x = stos.pop()
        if isinstance(x, dict):
            yield x
            stos.extend(x.values())
        elif isinstance(x, list):
            stos.extend(x)


def tekst_html(s):
    return re.sub(r'\s+', ' ', _html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def tabele_html(s, klasa=None):
    """Wiersze tabel HTML jako listy komorek (tekst). klasa = fragment atrybutu class/id tabeli."""
    # tresc = od znacznika otwierajacego do NAJBLIZSZEGO </table> — tabela zagniezdzona w innej (Tennis Abstract:
    # #reportable wewnatrz <table width=1000px>) nie moze byc pochlonieta przez zewnetrzna (diagnoza 03.10 07:50)
    out, s = [], s or ''
    for m in re.finditer(r'<table([^>]*)>', s, re.I):
        if klasa and klasa not in m.group(1): continue
        k = s.find('</table>', m.end())
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', s[m.end():k if k >= 0 else len(s)], re.S | re.I):
            kom = [tekst_html(c) for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S | re.I)]
            if any(kom): out.append(kom)
    return out


def tm_wiersze(s):
    """Transfermarkt, tabela class="items": wiersz odd/even -> nazwa (gracz albo klub), klub, komorki (tekst).
    Komorka gracza ma wewnetrzna tabele (zdjecie, nazwisko, pozycja) — dlatego nie tabele_html (diagnoza 03.10)."""
    i = (s or '').find('class="items"')
    if i < 0: return []
    out = []
    for b in re.findall(r'<tr class="(?:odd|even)"[^>]*>(.*?)(?=<tr class="(?:odd|even)"|</tbody>|$)', s[i:], re.S):
        nazwa = re.search(r'class="hauptlink[^"]*">\s*<a title="([^"]+)"', b)
        poz = re.search(r'inline-table">.*?</tr>\s*<tr>\s*<td>([^<]*)</td>', b, re.S)
        reszta = b.rsplit('</table>', 1)[-1]
        klub = re.search(r'<a title="([^"]+)" href="/[^"]*/(?:startseite|spielplan)/verein/(\d+)', reszta)
        kom = [tekst_html(c) for c in re.findall(r'<td[^>]*>(.*?)</td>', reszta, re.S)]
        if not nazwa: continue   # inne tabele "items" na stronie ligi (np. "25 | 3") — nie kluby i nie gracze (audyt 03.10)
        out.append({'nazwa': _html.unescape(nazwa.group(1)) if nazwa else '', 'pozycja': (poz.group(1).strip() if poz else ''),
                    'klub': _html.unescape(klub.group(1)) if klub else '', 'klub_id': klub.group(2) if klub else '',
                    'komorki': ' | '.join(c for c in kom if c)})
    return out


def tabela_z_naglowkiem(wiersze):
    """Pierwszy wiersz = naglowek; puste i powtorzone nazwy kolumn dostaja numer."""
    if not wiersze: return []
    nag, uzyte = [], {}
    for i, n in enumerate(wiersze[0]):
        n = n.strip() or f'k{i}'
        uzyte[n] = uzyte.get(n, 0) + 1
        nag.append(n if uzyte[n] == 1 else f'{n}_{uzyte[n]}')
    rows = [dict(zip(nag, w)) for w in wiersze[1:] if len(w) == len(nag)]
    puste = [n for i, n in enumerate(nag) if n == f'k{i}' and all(not r[n] for r in rows)]   # kolumny-odstepy
    return [{k: v for k, v in r.items() if k not in puste} for r in rows]


def elo_reprezentacji(world_tsv, teams_tsv):
    """eloratings.net: World.tsv (pozycja, ..., kod, ocena, ...) + en.teams.tsv (kod, nazwa, ...)."""
    nazwy = {}
    for ln in (teams_tsv or '').splitlines():
        p = ln.split('\t')
        if len(p) >= 2 and p[0].strip(): nazwy.setdefault(p[0].strip(), p[1].strip())
    out = []
    for ln in (world_tsv or '').splitlines():
        p = [x.strip() for x in ln.split('\t')]
        i = next((k for k, x in enumerate(p) if re.fullmatch(r'[A-Z]{2,3}', x)), None)
        if i is None: continue
        elo = next((int(x) for x in p[i + 1:] if re.fullmatch(r'\d{3,4}', x) and 500 <= int(x) <= 2600), None)
        if elo is None: continue
        out.append({'pozycja': p[0], 'kod': p[i], 'nazwa': nazwy.get(p[i], ''), 'elo': elo})
    return out


def fotmob_mecze(j, data):
    out = []
    for lg in (j or {}).get('leagues', []) or []:
        for m in lg.get('matches', []) or []:
            st = m.get('status') or {}
            out.append({'data': data, 'liga_id': lg.get('primaryId', lg.get('id')), 'liga': lg.get('name'),
                        'kraj': lg.get('ccode'), 'mecz_id': m.get('id'), 'gosp': (m.get('home') or {}).get('name'),
                        'gosc': (m.get('away') or {}).get('name'), 'start_utc': st.get('utcTime') or m.get('time'),
                        'zakonczony': st.get('finished'), 'rozpoczety': st.get('started'),
                        'wynik': st.get('scoreStr', '')})
    return out


def _nazwisko(p):
    if isinstance(p, dict):
        n = p.get('name')
        if isinstance(n, dict): n = n.get('fullName') or n.get('firstName', '') + ' ' + n.get('lastName', '')
        return str(n or p.get('fullName') or '').strip()
    return str(p)


def fotmob_szczegoly(j):
    """Wydobycie odporne na zmiany ukladu JSON-a FotMob: szukamy kluczy w calym drzewie."""
    w = {'xg_gosp': '', 'xg_gosc': '', 'sklad_status': '', 'sklad_gosp': '', 'sklad_gosc': '', 'nieobecni_gosp': '',
         'nieobecni_gosc': '', 'stadion': '', 'miasto': '', 'lat': '', 'lon': '', 'sedzia': ''}
    if not j: return w
    for d in chodz(j):
        if not w['xg_gosp'] and (d.get('key') == 'expected_goals' or str(d.get('title', '')).lower().startswith('expected goals')) \
                and isinstance(d.get('stats'), list) and len(d['stats']) == 2:
            w['xg_gosp'], w['xg_gosc'] = d['stats']
        if not w['sklad_status']:
            for k in ('lineupType', 'lineupSource', 'lineupStatus'):
                if isinstance(d.get(k), str): w['sklad_status'] = d[k]; break
        if not w['lat'] and ('lat' in d and ('long' in d or 'lon' in d)):
            w['lat'], w['lon'] = d.get('lat'), d.get('long', d.get('lon'))
            w['stadion'], w['miasto'] = d.get('name', ''), d.get('city', '')
        if not w['sedzia'] and isinstance(d.get('Referee'), dict):
            w['sedzia'] = d['Referee'].get('text', '')
    lu = next((d['lineup'] for d in chodz(j) if isinstance(d.get('lineup'), dict)
               and ('homeTeam' in d['lineup'] or 'awayTeam' in d['lineup'])), None)
    if lu:
        for strona, s in (('gosp', 'homeTeam'), ('gosc', 'awayTeam')):
            t = lu.get(s) or {}
            w[f'sklad_{strona}'] = ';'.join(_nazwisko(p) for p in t.get('starters') or [])
            nb = []
            for p in t.get('unavailable') or []:
                u = p.get('unavailability') or {} if isinstance(p, dict) else {}
                nb.append(f"{_nazwisko(p)} ({u.get('type', '')}{' do ' + str(u['expectedReturn']) if u.get('expectedReturn') else ''})")
            w[f'nieobecni_{strona}'] = ';'.join(nb)
    return w


def sofa_mecze(j, sport, data):
    out = []
    for e in (j or {}).get('events', []) or []:
        t = e.get('tournament') or {}
        out.append({'sport': sport, 'data': data, 'id': e.get('id'), 'turniej': t.get('name'),
                    'kategoria': (t.get('category') or {}).get('name'), 'gosp': (e.get('homeTeam') or {}).get('name'),
                    'gosc': (e.get('awayTeam') or {}).get('name'), 'start_ts': e.get('startTimestamp'),
                    'status': (e.get('status') or {}).get('type'), 'wynik_g': (e.get('homeScore') or {}).get('current', ''),
                    'wynik_a': (e.get('awayScore') or {}).get('current', '')})
    return out


def sofa_sklad(lineups, event):
    w = {'potwierdzony': '', 'nieobecni_gosp': '', 'nieobecni_gosc': '', 'sedzia': '', 'sedzia_mecze': '',
         'sedzia_zolte': '', 'sedzia_czerwone': '', 'miasto': '', 'lat': '', 'lon': ''}
    if lineups:
        w['potwierdzony'] = lineups.get('confirmed', '')
        for strona, s in (('gosp', 'home'), ('gosc', 'away')):
            mp = (lineups.get(s) or {}).get('missingPlayers') or []
            w[f'nieobecni_{strona}'] = ';'.join(f"{_nazwisko(x.get('player') or {})} ({x.get('type', '')}/{x.get('reason', '')})"
                                               for x in mp)
    ev = (event or {}).get('event') or {}
    r = ev.get('referee') or {}
    if r: w.update(sedzia=r.get('name', ''), sedzia_mecze=r.get('games', ''), sedzia_zolte=r.get('yellowCards', ''),
                   sedzia_czerwone=r.get('redCards', ''))
    v = ev.get('venue') or {}
    c = v.get('venueCoordinates') or {}
    w.update(miasto=(v.get('city') or {}).get('name', ''), lat=c.get('latitude', ''), lon=c.get('longitude', ''))
    return w


def understat_mecze(tekst, liga, sezon):
    """getLeagueData (JSON: dates) albo stara strona HTML (datesData = JSON.parse('\\x..'))."""
    dates = None
    try:
        dates = json.loads(tekst).get('dates')
    except (ValueError, AttributeError):
        m = re.search(r"datesData\s*=\s*JSON\.parse\('(.*?)'\)", tekst or '', re.S)
        if m: dates = json.loads(m.group(1).encode('utf-8').decode('unicode_escape'))
    out = []
    for d in dates or []:
        out.append({'liga': liga, 'sezon': sezon, 'id': d.get('id'), 'data': d.get('datetime'),
                    'gosp': (d.get('h') or {}).get('title'), 'gosc': (d.get('a') or {}).get('title'),
                    'gole_g': (d.get('goals') or {}).get('h'), 'gole_a': (d.get('goals') or {}).get('a'),
                    'xg_g': (d.get('xG') or {}).get('h'), 'xg_a': (d.get('xG') or {}).get('a'), 'rozegrany': d.get('isResult')})
    return out


# api-web.nhle.com podaje tylko przydomek ("Red Wings") — w bazie i w ofercie sa pelne nazwy (audyt nazw 03.10)
NHL_PELNE = {'ANA': 'Anaheim Ducks', 'BOS': 'Boston Bruins', 'BUF': 'Buffalo Sabres', 'CGY': 'Calgary Flames',
             'CAR': 'Carolina Hurricanes', 'CHI': 'Chicago Blackhawks', 'COL': 'Colorado Avalanche', 'CBJ': 'Columbus Blue Jackets',
             'DAL': 'Dallas Stars', 'DET': 'Detroit Red Wings', 'EDM': 'Edmonton Oilers', 'FLA': 'Florida Panthers',
             'LAK': 'Los Angeles Kings', 'MIN': 'Minnesota Wild', 'MTL': 'Montreal Canadiens', 'NSH': 'Nashville Predators',
             'NJD': 'New Jersey Devils', 'NYI': 'New York Islanders', 'NYR': 'New York Rangers', 'OTT': 'Ottawa Senators',
             'PHI': 'Philadelphia Flyers', 'PIT': 'Pittsburgh Penguins', 'SJS': 'San Jose Sharks', 'SEA': 'Seattle Kraken',
             'STL': 'St. Louis Blues', 'TBL': 'Tampa Bay Lightning', 'TOR': 'Toronto Maple Leafs', 'UTA': 'Utah Mammoth',
             'VAN': 'Vancouver Canucks', 'VGK': 'Vegas Golden Knights', 'WSH': 'Washington Capitals', 'WPG': 'Winnipeg Jets'}


def nhl_mecze(j, data):
    out = []
    for g in (j or {}).get('games', []) or []:
        h, a = g.get('homeTeam') or {}, g.get('awayTeam') or {}
        nm = lambda t: (t.get('name') or {}).get('default') if isinstance(t.get('name'), dict) else t.get('name')
        out.append({'data': data, 'id': g.get('id'), 'start_utc': g.get('startTimeUTC'), 'stan': g.get('gameState'),
                    'gosp': h.get('abbrev'), 'gosp_nazwa': NHL_PELNE.get(h.get('abbrev'), nm(h)),
                    'gosc': a.get('abbrev'), 'gosc_nazwa': NHL_PELNE.get(a.get('abbrev'), nm(a)),
                    'wynik_g': h.get('score', ''), 'wynik_a': a.get('score', ''),
                    'koniec': (g.get('periodDescriptor') or {}).get('periodType', '')})
    return out


BR_POLA = (('TeamName', 'druzyna'), ('GoalieName', 'bramkarz'), ('NewsStrengthName', 'status'),
           ('GoalieSavePercentage', 'sv_proc'), ('GoalieGoalsAgainstAvg', 'gaa'), ('GoalieWins', 'w'),
           ('GoalieLosses', 'l'), ('GoalieRating', 'ocena'), ('NewsCreatedAt', 'wiadomosc_utc'))


def bramkarze(tekst):
    """Daily Faceoff: __NEXT_DATA__ -> props.pageProps.data (lista meczow, pola home*/away*) — uklad z diagnozy 03.10."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', tekst or '', re.S)
    if not m: return []
    try: pp = json.loads(m.group(1))['props']['pageProps']
    except (ValueError, KeyError, TypeError): return []
    out = []
    for g in pp.get('data') or []:
        w = {'data': pp.get('date', ''), 'start_utc': g.get('dateGmt', g.get('date', ''))}
        for strona, s in (('gosp', 'home'), ('gosc', 'away')):
            for k, n in BR_POLA: w[f'{n}_{strona}'] = g.get(s + k, '')
        out.append(w)
    return out


def pogoda_na_godzine(odp, mecze):
    """odp: lista odpowiedzi Open-Meteo (po jednej na wspolrzedne, w tej samej kolejnosci co mecze)."""
    if isinstance(odp, dict): odp = [odp]
    out = []
    for m, o in zip(mecze, odp or []):
        h = (o or {}).get('hourly') or {}
        czasy = h.get('time') or []
        if not czasy: continue
        cel = str(m['start_utc'])[:13]
        i = next((k for k, t in enumerate(czasy) if t[:13] == cel), None)
        if i is None: continue
        out.append({**m, 'temp': h.get('temperature_2m', [None] * len(czasy))[i],
                    'opad_mm': h.get('precipitation', [None] * len(czasy))[i],
                    'wiatr_kmh': h.get('wind_speed_10m', [None] * len(czasy))[i]})
    return out


def utc_z(x):
    """ISO / znacznik czasu -> datetime UTC (naive) albo None."""
    if x in (None, ''): return None
    try:
        if isinstance(x, (int, float)) or str(x).isdigit():
            return dt.datetime.fromtimestamp(int(x), dt.timezone.utc).replace(tzinfo=None)
        t = dt.datetime.fromisoformat(str(x).replace('Z', '+00:00'))
        return t.astimezone(dt.timezone.utc).replace(tzinfo=None) if t.tzinfo else t
    except (ValueError, OverflowError, OSError):
        return None


# ---------- zrodla ----------

def z_elo(s, w):
    k1, a = s.get('elo', 'https://www.eloratings.net/World.tsv', H_HTML)
    k2, b = s.get('elo', 'https://www.eloratings.net/en.teams.tsv', H_HTML)
    w['elo_reprezentacji'] = elo_reprezentacji(a if k1 == 200 else '', b if k2 == 200 else '')


def z_fotmob(s, w, dzis, teraz, gotowe):
    mecze = []
    for d in sorted({dzis - dt.timedelta(days=1), dzis, (teraz + dt.timedelta(hours=OKNO_H)).date()}):
        j = s.get_json('fotmob', f'https://www.fotmob.com/api/data/matches?date={d:%Y%m%d}')
        if j is None: j = s.get_json('fotmob', f'https://www.fotmob.com/api/matches?date={d:%Y%m%d}')
        mecze += fotmob_mecze(j, str(d))
    w['fotmob_mecze'] = mecze
    wyb = [m for m in mecze if (lambda t: t and teraz <= t <= teraz + dt.timedelta(hours=OKNO_H))(utc_z(m['start_utc']))]
    wyb += [m for m in mecze if m['zakonczony'] and f"fm{m['mecz_id']}" not in gotowe]
    out = []
    for m in wyb[:MAKS_SZCZEGOLY]:
        j = s.get_json('fotmob', f"https://www.fotmob.com/api/data/matchDetails?matchId={m['mecz_id']}")
        if j is None: j = s.get_json('fotmob', f"https://www.fotmob.com/api/matchDetails?matchId={m['mecz_id']}")
        if j is None: continue
        out.append({'mecz_id': m['mecz_id'], 'liga': m['liga'], 'kraj': m['kraj'], 'gosp': m['gosp'], 'gosc': m['gosc'],
                    'start_utc': m['start_utc'], 'zakonczony': m['zakonczony'], 'wynik': m['wynik'], **fotmob_szczegoly(j)})
        if m['zakonczony']: gotowe.add(f"fm{m['mecz_id']}")
    w['fotmob_szczegoly'] = out


def z_sofa(s, w, dzis, teraz):
    proby, baza, war = [], None, None
    for nazwa, nag, opc in SOFA_WARIANTY:
        for b in SOFA:
            kod, t = s.get('sofascore', f'{b}/sport/football/scheduled-events/{dzis}', nag, proby=1, curl=opc)
            proby.append({'wariant': nazwa, 'adres': b, 'kod': kod, 'odpowiedz': t[:120].replace('\n', ' ')})
            if kod == 200: baza, war = b, (nag, opc); break
        if baza: break
    w['sofascore_proby'] = proby
    if not baza:   # wszystkie warianty zablokowane — nie ponawiamy dla kazdego sportu
        w['sofascore_mecze'] = []
        return
    nag, opc = war
    jget = lambda url: (lambda kt: json.loads(kt[1]) if kt[0] == 200 and kt[1][:1] in '{[' else None)(
        s.get('sofascore', url, nag, curl=opc))
    mecze = []
    for sport in SOFA_SPORTY:
        for d in (dzis - dt.timedelta(days=1), dzis):
            mecze += sofa_mecze(jget(f'{baza}/sport/{sport}/scheduled-events/{d}'), sport, str(d))
    w['sofascore_mecze'] = mecze
    out = []
    for m in [m for m in mecze if m['sport'] == 'football' and m['status'] == 'notstarted'
              and (lambda t: t and teraz <= t <= teraz + dt.timedelta(hours=OKNO_H))(utc_z(m['start_ts']))][:MAKS_SZCZEGOLY]:
        lu = jget(f"{baza}/event/{m['id']}/lineups")
        ev = jget(f"{baza}/event/{m['id']}")
        out.append({'id': m['id'], 'turniej': m['turniej'], 'kategoria': m['kategoria'], 'gosp': m['gosp'], 'gosc': m['gosc'],
                    'start_utc': utc_z(m['start_ts']).isoformat(), **sofa_sklad(lu, ev)})
    w['sofascore_sklady'] = out


def z_transfermarkt(s, w):
    out = []
    for lg in TM_LIGI:
        for typ, sciezka in (('kontuzje', 'verletztespieler'), ('wartosci', 'startseite')):
            kod, t = s.get('transfermarkt', f'https://www.transfermarkt.com/liga/{sciezka}/wettbewerb/{lg}', H_HTML, pauza=2.0)
            if kod != 200: continue
            out += [{'liga': lg, 'typ': typ, **r} for r in tm_wiersze(t)]
    w['transfermarkt'] = out


def z_understat(s, w, dzis, historia):
    biez = dzis.year if dzis.month >= 7 else dzis.year - 1
    out = []
    for lg in US_LIGI:
        for sez in (range(2014, biez + 1) if historia else (biez,)):
            kod, t = s.get('understat', f'https://understat.com/getLeagueData/{lg}/{sez}',
                           {**H_JSON, 'X-Requested-With': 'XMLHttpRequest', 'Referer': f'https://understat.com/league/{lg}/{sez}'})
            if kod != 200: kod, t = s.get('understat', f'https://understat.com/league/{lg}/{sez}', H_HTML)
            if kod == 200: out += understat_mecze(t, lg, sez)
    w['understat'] = out


def z_tenis(s, w):
    out = []
    for tura in ('atp', 'wta'):
        kod, t = s.get('tenis', f'https://tennisabstract.com/reports/{tura}_elo_ratings.html', H_HTML, pauza=1.0)
        if kod != 200: continue
        out += [{'tura': tura, **r} for r in tabela_z_naglowkiem(tabele_html(t, 'reportable'))]
    w['tenis_elo'] = out


DARTY_STATY = (('25', 'srednia'), ('10011', 'proc_meczow'), ('1053', 'proc_checkout'), ('1029', 'srednia_9'), ('26', '180'))


def darty_api(j, stat):
    """DartsOrakel /api/stats/player — uklad z odpowiedzi 03.10 08:35: {"recordsTotal", "data": [{player_key, player_name,
    country, stat, rank, sumField1, sumField2 | total_matches, wins}]}. API pomija minMatches (21 680 graczy na statystyke)."""
    out = []
    for r in (j or {}).get('data', []) if isinstance(j, dict) else (j or []):
        if not isinstance(r, dict): continue
        out.append({'stat': stat, 'klucz': r.get('player_key', ''), 'pozycja': r.get('rank', ''),
                    'zawodnik': tekst_html(str(r.get('player_name', ''))), 'kraj': r.get('country') or '',
                    'wartosc': r.get('stat', ''), 'licznik': r.get('sumField1', r.get('wins', '')),
                    'mianownik': r.get('sumField2', r.get('total_matches', ''))})
    return out


def darty_scal(wiersze, min_meczow=10):
    """Jeden wiersz na gracza: mecze/wygrane z 'proc_meczow', pozostale statystyki jako kolumny; tylko gracze z >= min_meczow."""
    g = {}
    for r in wiersze:
        x = g.setdefault(r['klucz'], {'klucz': r['klucz'], 'zawodnik': r['zawodnik'], 'kraj': r['kraj']})
        if r['stat'] == 'proc_meczow':
            x['mecze'], x['wygrane'] = r['mianownik'], r['licznik']
        else:
            x[r['stat']] = r['wartosc']
            x[r['stat'] + '_n'] = r['mianownik']
    return sorted((x for x in g.values() if isinstance(x.get('mecze'), int) and x['mecze'] >= min_meczow),
                  key=lambda x: -float(str(x.get('srednia') or 0).rstrip('%') or 0))


def z_darty(s, w, dzis):
    # /rank = 404, /stats/player = pusta tabela wypelniana przez JS z /api/stats/player (diagnoza 03.10 08:24);
    # parametry jak w formularzu strony: rok wstecz, wszystkie turnieje, min. 10 meczow
    out = []
    nag = {**H_JSON, 'X-Requested-With': 'XMLHttpRequest', 'Referer': 'https://dartsorakel.com/stats/player'}
    for klucz, nazwa in DARTY_STATY:
        url = (f'https://dartsorakel.com/api/stats/player?dateFrom={dzis - dt.timedelta(days=365)}&dateTo={dzis + dt.timedelta(days=1)}'
               f'&rankKey={klucz}&organStat=All&minMatches=10&tourCardYear=&showStatsBreakdown=0&excludeWGP=0')
        out += darty_api(s.get_json('darty', url, nag, pauza=1.0), nazwa)
    w['darty_ranking'] = darty_scal(out)


def z_nhl(s, w, dzis):
    out = []
    for d in (dzis - dt.timedelta(days=1), dzis, dzis + dt.timedelta(days=1)):
        out += nhl_mecze(s.get_json('nhl', f'https://api-web.nhle.com/v1/score/{d}'), str(d))
    w['nhl'] = out
    br = []
    for d in (dzis, dzis + dt.timedelta(days=1)):   # strona bez daty pokazuje wczorajsze mecze (diagnoza 03.10)
        kod, t = s.get('nhl', f'https://www.dailyfaceoff.com/starting-goalies/{d}', H_HTML)
        if kod == 200: br += bramkarze(t)
    w['nhl_bramkarze'] = br


def z_pogoda(s, w):
    mecze, byly = [], set()
    for zr, rows, idk in (('fotmob', w.get('fotmob_szczegoly', []), 'mecz_id'), ('sofascore', w.get('sofascore_sklady', []), 'id')):
        for r in rows:
            if r.get('lat') in ('', None) or r.get('zakonczony'): continue
            t = utc_z(r['start_utc'])
            k = (r['gosp'], str(t)[:13])
            if not t or k in byly: continue
            byly.add(k)
            mecze.append({'zrodlo': zr, 'mecz_id': r[idk], 'gosp': r['gosp'], 'gosc': r['gosc'],
                          'start_utc': t.isoformat(), 'lat': r['lat'], 'lon': r['lon']})
    out = []
    for i in range(0, len(mecze), 50):
        cz = mecze[i:i + 50]
        url = ('https://api.open-meteo.com/v1/forecast?latitude=' + ','.join(str(m['lat']) for m in cz) +
               '&longitude=' + ','.join(str(m['lon']) for m in cz) +
               '&hourly=temperature_2m,precipitation,wind_speed_10m&forecast_days=2&timezone=UTC')
        out += pogoda_na_godzine(s.get_json('pogoda', url), cz)
    w['pogoda'] = out


def sedziowie(w):
    out = [{'zrodlo': 'sofascore', 'mecz_id': r['id'], 'gosp': r['gosp'], 'gosc': r['gosc'], 'start_utc': r['start_utc'],
            'sedzia': r['sedzia'], 'mecze': r['sedzia_mecze'], 'zolte': r['sedzia_zolte'], 'czerwone': r['sedzia_czerwone']}
           for r in w.get('sofascore_sklady', []) if r.get('sedzia')]
    out += [{'zrodlo': 'fotmob', 'mecz_id': r['mecz_id'], 'gosp': r['gosp'], 'gosc': r['gosc'], 'start_utc': r['start_utc'],
             'sedzia': r['sedzia'], 'mecze': '', 'zolte': '', 'czerwone': ''}
            for r in w.get('fotmob_szczegoly', []) if r.get('sedzia') and not r.get('zakonczony')]
    return out


# ---------- WYNIKI dla bazy przebiegu (03.10.2026: 876 nazw z ofert bez druzyny w bazie) ----------
# Te zrodla NIE sa obserwacja: zapisuja wyniki_<zrodlo>_<rodzaj>_RRRR-MM.csv.gz w formacie Apps Script (jak wyniki_lp_inne)
# do GLOWNEGO folderu baza-wiedzy — paczka.gs dolacza je do paczki, zewn.py czyta wyniki_*_inne_* / wyniki_*_pilka_*.
S24 = 'https://scores24.live'
S24_LIGI = {'setka': ('UKRAINE', 'Setka Cup')}   # fragment sluga scores24 -> (kraj, turniej); Liga Pro i TT Cup ma ligapro.gs
NAGL_WYNIKI = ['data', 'sport', 'kraj', 'turniej', 'runda', 'gosp', 'gosc', 'wg', 'wa', 'okresy_g', 'okresy_a', 'zwyciezca', 'nawierzchnia']
WYNIKI_DIR = os.path.expanduser('~/.zrodla_wyniki')   # skumulowane pliki miesiaca na telefonie (scalane po id)


def s24_slugi(html):
    """Slugi lig tenisa stolowego ze strony scores24 (/en/table-tennis/l-<slug>)."""
    return sorted(set(re.findall(r'/table-tennis/l-([a-z0-9-]+)', html or '')))


def s24_wiersz(n, kraj, turniej):
    """Wezel scores24 -> wiersz wynikow (jak ligaproWiersz w apps_script/ligapro.gs) albo None (bez wyniku / remis)."""
    t = n.get('teams') or []
    data = n.get('match_date') or n.get('matchDate')
    wyn = str(n.get('result_score') or n.get('resultScore') or '').split(':')
    if len(t) != 2 or len(wyn) != 2 or not data: return None
    try: wg, wa = int(wyn[0]), int(wyn[1])
    except ValueError: return None
    if wg == wa: return None
    sety = sorted((x for x in (n.get('result_scores') or n.get('resultScores') or []) if str(x.get('type', '')).isdigit()),
                  key=lambda x: int(x['type']))
    sety = [str(x.get('value', '')).split(':') + [''] for x in sety]
    return {'data': str(data)[:10], 'sport': 'table-tennis', 'kraj': kraj, 'turniej': turniej, 'runda': f"sc24:{n.get('id')}",
            'gosp': t[0].get('name', ''), 'gosc': t[1].get('name', ''), 'wg': wg, 'wa': wa,
            'okresy_g': ';'.join(x[0] for x in sety), 'okresy_a': ';'.join(x[1] for x in sety),
            'zwyciezca': 1 if wg > wa else 2, 'nawierzchnia': ''}


def scal_miesiace(wiersze, prefiks, kat):
    """Dopisuje wiersze do skumulowanych plikow miesiaca (po kolumnie runda = id) i kopiuje je do kat. Zwraca sciezki."""
    os.makedirs(WYNIKI_DIR, exist_ok=True)
    mies = {}
    for r in wiersze: mies.setdefault(r['data'][:7], {})[r['runda']] = r
    out = []
    for m, nowe in sorted(mies.items()):
        nazwa = f'{prefiks}_{m}.csv.gz'
        p = os.path.join(WYNIKI_DIR, nazwa)
        stare = {}
        if os.path.exists(p):
            with gzip.open(p, 'rt', encoding='utf-8', newline='') as f:
                stare = {r['runda']: r for r in csv.DictReader(f)}
        stare.update(nowe)
        with gzip.open(p, 'wt', encoding='utf-8', newline='') as f:
            cw = csv.DictWriter(f, NAGL_WYNIKI); cw.writeheader()
            cw.writerows(sorted(stare.values(), key=lambda r: (r['data'], r['runda'])))
        shutil.copy(p, os.path.join(kat, nazwa)); out.append(os.path.join(kat, nazwa))
    return out


S24_HIST_DNI, S24_LIMIT_S = 21, 240
S24_STRONY = ('/en/table-tennis',)   # strony krajow (c-ukraine, c-international...) daly 404 — cron 03.10 11:40
SETKA_STRONY = ('https://setkacup.com/', 'https://www.setkacup.com/en/', 'https://setka-cup.com/')   # diagnoza: inne zrodlo
S24_KANDYDACI = ('setka-cup', 'setka-cup-1', 'ukraine-setka-cup', 'ukraine-setka-cup-1', 'international-setka-cup',
                 'international-setka-cup-1', 'world-setka-cup', 'world-setka-cup-1', 'setka-cup-men', 'setka-cup-ukraine',
                 'europe-setka-cup', 'europe-setka-cup-1', 'russia-setka-cup', 'russia-setka-cup-1')


def z_s24(s, w, teraz, stan, dni_hist, kat):
    """Setka Cup ze scores24 (jak Liga Pro w ligapro.gs, ale z telefonu): slug znajdowany na liscie lig, mecze zakonczone
    w oknach 1 h (API: max 50 meczow na odpowiedz) od ostatniego pobrania; --historia-s24 DNI = pobranie wstecz."""
    # 03.10.2026 (przebieg 10:19): strona glowna tenisa stolowego pokazala 3 ligi, bez Setka Cup, a slug „setka-cup”
    # w ligapro.gs daje 0 meczow — slug jest inny (Liga Pro to „czech-liga-pro-1”). Szukamy na kilku stronach
    # i sprawdzamy kandydatow przez API; znaleziony slug zostaje w stanie (kolejne uruchomienia go uzywaja).
    wszystkie = set()
    if stan.get('s24_slug'): wszystkie.add(stan['s24_slug'])
    for strona in S24_STRONY:
        kod, t = s.get('s24', S24 + strona, H_HTML)
        wszystkie |= set(s24_slugi(t))
    cele = [(x, v) for x in sorted(wszystkie) for k, v in S24_LIGI.items() if k in x]
    # 03.10.2026 (cron 11:40): scores24 ma 3 ligi tenisa stolowego (Liga Pro, TT Cup, TT Elite Series), Setka Cup nie ma,
    # a 14 kandydatow API dalo puste odpowiedzi. Kandydaci i inne strony Setka Cup — raz na 7 dni, nie co 3 godziny.
    dzis = str(teraz.date())
    ost = stan.get('s24_proba')
    if not cele and (not ost or (teraz.date() - dt.date.fromisoformat(ost)).days >= 7):
        stan['s24_proba'] = dzis
        for url in SETKA_STRONY:
            kod, t = s.get('setka', url, H_HTML, proby=1)
            w.setdefault('setka_strony', []).append({'url': url, 'kod': kod, 'bajty': len(t or ''),
                                                    'setka': len(re.findall(r'(?i)setka', t or ''))})
        od_ = teraz - dt.timedelta(days=2)
        for slug in S24_KANDYDACI:
            url = (f'{S24}/rapi/leagues/table-tennis/{slug}/matches?lang=en&audience=en&first=5&status=ended&with_statistics=false'
                   f'&date_between%5B%5D={od_:%Y-%m-%d+%H:%M:%S}&date_between%5B%5D={teraz:%Y-%m-%d+%H:%M:%S}')
            j = s.get_json('s24', url, {**H_JSON, 'Accept': 'application/json'}, proby=1, pauza=0.2)
            if ((j or {}).get('data') or {}).get('edges') or (j or {}).get('edges'):
                cele = [(slug, S24_LIGI['setka'])]; break
    w['s24_ligi'] = [{'slug': x, 'cel': any(x == c for c, _ in cele)} for x in sorted(wszystkie | {c for c, _ in cele})]
    if not cele: return
    stan['s24_slug'] = cele[0][0]
    # 03.10.2026: wszystko z crona, bez recznych komend — pierwsze uruchomienie (brak stanu) pobiera S24_HIST_DNI wstecz,
    # kazde nastepne dociaga od miejsca, w ktorym poprzednie skonczylo (limit S24_LIMIT_S na uruchomienie, zeby
    # zaleglosci nie zjadly budzetu pozostalych zrodel).
    od = dt.datetime.fromisoformat(stan['s24_do']) if stan.get('s24_do') and not dni_hist else teraz - dt.timedelta(days=dni_hist or S24_HIST_DNI)
    do = teraz - dt.timedelta(minutes=20)
    wiersze, a, koniec = [], od, time.time() + S24_LIMIT_S
    while a < do and s.czas() and time.time() < koniec:
        b = min(a + dt.timedelta(hours=1), do)
        for slug, (kraj, turniej) in cele:
            url = (f'{S24}/rapi/leagues/table-tennis/{slug}/matches?lang=en&audience=en&first=50&status=ended&with_statistics=false'
                   f'&date_between%5B%5D={a:%Y-%m-%d+%H:%M:%S}&date_between%5B%5D={b:%Y-%m-%d+%H:%M:%S}')
            j = s.get_json('s24', url, {**H_JSON, 'Accept': 'application/json'}, pauza=0.2)
            e = ((j or {}).get('data') or {}).get('edges') or (j or {}).get('edges') or []
            wiersze += [x for x in (s24_wiersz(z.get('node', z), kraj, turniej) for z in e) if x]
        a = b
    stan['s24_do'] = a.isoformat()
    w['s24_mecze'] = wiersze
    w.setdefault('_pliki_wynikow', []).extend(scal_miesiace(wiersze, 'wyniki_s24_inne', kat))


MIESIACE_PL = {'stycznia': 1, 'lutego': 2, 'marca': 3, 'kwietnia': 4, 'maja': 5, 'czerwca': 6, 'lipca': 7, 'sierpnia': 8,
               'wrzesnia': 9, 'września': 9, 'pazdziernika': 10, 'października': 10, 'listopada': 11, 'grudnia': 12}
# ligi z menu strony glownej (03.10.2026): nazwa w menu -> turniej w pliku (zapis jak Flashscore, do odsiewania dubli)
LIGI_90M = {'II liga': 'II Liga', 'III liga, gr. I': 'III Liga - Group I', 'III liga, gr. II': 'III Liga - Group II',
            'III liga, gr. III': 'III Liga - Group III', 'III liga, gr. IV': 'III Liga - Group IV', 'CLJ': 'CLJ U19'}


def _bez_tagow(x):
    return _html.unescape(re.sub(r'<[^>]+>', ' ', x)).replace('\xa0', ' ').strip()


def _data_pl(tekst, rok_domyslny):
    """„26 lipca 2026”, „26 lipca, 18:00”, „26.07.2026” -> 'RRRR-MM-DD' albo None."""
    m = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', tekst)
    if m: return f'{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}'
    # zakres kolejki „27-28 września” -> pierwszy dzien (wiersz meczu bez wlasnej daty; dopasowanie dubli ma +-1 dzien)
    m = re.search(r'(\d{1,2})(?:\s*[-–]\s*\d{1,2})?\s+([a-ząćęłńóśźż]+)(?:\s+(\d{4}))?', tekst.lower())
    if m and m.group(2) in MIESIACE_PL:
        return f'{int(m.group(3) or rok_domyslny):04d}-{MIESIACE_PL[m.group(2)]:02d}-{int(m.group(1)):02d}'
    return None


def m90_wiersze(html, turniej, rok):
    """Strona ligi 90minut.pl -> mecze z wynikiem (format NAGL_WYNIKI). Kolejki: naglowek „Kolejka N - <data>”,
    wiersz meczu: komorki gospodarz | wynik „2-1” | gosc [| data]. Data z wiersza, inaczej z naglowka kolejki.
    UWAGA: napisane na podstawie ogolnego ukladu strony — sprawdzane na surowych stronach z telefonu (diagnoza)."""
    out, kol, data_kol = [], '', None
    for kaw in re.split(r'(?i)(?=<tr)', html or ''):
        tekst = _bez_tagow(kaw)
        mk = re.search(r'(?i)kolejka\s+(\d+)\s*[-–]?\s*(.*)', tekst)
        if mk and len(tekst) < 120:
            kol, data_kol = mk.group(1), _data_pl(mk.group(2), rok) or data_kol
            continue
        kom = [_bez_tagow(x) for x in re.findall(r'(?is)<td[^>]*>(.*?)</td>', kaw)]
        for i in range(1, len(kom) - 1):
            w = re.fullmatch(r'(\d{1,2})\s*[-:]\s*(\d{1,2})', kom[i])
            if not w or not kom[i - 1] or not kom[i + 1] or re.search(r'\d', kom[i - 1][:1]): continue
            d = next((x for x in (_data_pl(c, rok) for c in kom[i + 2:i + 4]) if x), None) or data_kol
            if not d: break
            g, a = int(w.group(1)), int(w.group(2))
            out.append({'data': d, 'sport': 'football', 'kraj': 'Poland', 'turniej': turniej, 'runda': f'90m:{kol}',
                        'gosp': kom[i - 1], 'gosc': kom[i + 1], 'wg': g, 'wa': a, 'okresy_g': '', 'okresy_a': '',
                        'zwyciezca': 1 if g > a else (2 if a > g else 0), 'nawierzchnia': ''})
            break
    return out


def z_90minut(s, w, teraz=None):
    """90minut.pl: polskie ligi II-IV i CLJ (Flashscore/365 maja je czesciowo, bez dlugiej historii). TRYB OBSERWACJI:
    mecze tylko w zipie zrodel (zrodla_90minut_mecze), nic w przebiegu ich nie uzywa do czasu przegladu."""
    teraz = teraz or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    baza, curl = 'https://www.90minut.pl/', None
    kod, t = s.get('90minut', baza, H_HTML)
    if kod != 200:   # 03.10.2026 (przebieg 10:19): HTTP 0 z Pythona — druga proba zwyklym http i curlem (inny TLS)
        baza, curl = 'http://www.90minut.pl/', []
        kod, t = s.get('90minut', baza, H_HTML, curl=curl)
    linki = sorted(set(re.findall(r'href="(/?(?:liga|archsezon|skarb)[^"]+)"', t or '')))
    w['90minut_linki'] = [{'link': x} for x in linki[:400]]
    ligi = {}
    for href, nazwa in re.findall(r'(?is)<a[^>]+href="(/liga/[^"]+)"[^>]*>(.*?)</a>', t or ''):
        nazwa = _bez_tagow(nazwa)
        if nazwa in LIGI_90M: ligi.setdefault(LIGI_90M[nazwa], href)
    rok = teraz.year
    mecze, stat = [], []
    for turniej, href in sorted(ligi.items()):
        kod, tl = s.get('90minut', baza + href.lstrip('/'), H_HTML, curl=curl)
        r = m90_wiersze(tl, turniej, rok) if kod == 200 else []
        # sezon jesien-wiosna: mecze z „przyszlych” miesiecy naleza do poprzedniego roku
        for x in r:
            if x['data'] > str((teraz + dt.timedelta(days=2)).date()): x['data'] = str(int(x['data'][:4]) - 1) + x['data'][4:]
        # 03.10.2026 (cron 14:40): mecze z dzisiejsza data maja wynik, ktory moze byc z TRAKCIE meczu (Unia Swarzedz -
        # Kotwica Kornik 7:0 o 14:40) — bierzemy tylko do wczoraj; dzisiejsze dociagnie jutrzejsze uruchomienie
        dzis_pl = str((teraz + dt.timedelta(hours=2)).date())
        r = [x for x in r if x['data'] < dzis_pl]
        mecze += r
        stat.append({'turniej': turniej, 'link': href, 'kod': kod, 'mecze': len(r)})
    w['90minut_ligi'] = stat
    w['90minut_mecze'] = mecze


def setka_api(js):
    """Adresy API z kodu aplikacji setkacup.com (SPA: strona to tylko „Loading application...”, dane pobiera app.*.js).
    Zwraca posortowane, unikalne: pelne URL-e oraz sciezki zaczynajace sie od /api, /v1, /v2 itp."""
    pelne = re.findall(r'https?://[A-Za-z0-9.-]+(?:/[^\s"\'`<>()]*)?', js or '')
    sciezki = re.findall(r'["\'`](/(?:api|v\d|rest|graphql|socket)[^"\'`\s]*)["\'`]', js or '')
    pelne = [u for u in pelne if not re.search(r'googletagmanager|facebook|google-analytics|w3\.org|reactjs|fb\.me|schema\.org|github', u)]
    return sorted(set(pelne)), sorted(set(sciezki))


def z_setka(s, w):
    """03.10.2026: wyniki Setka Cup z oficjalnej strony (setkacup.com) — scores24, Flashscore i 365 jej nie maja.
    DIAGNOZA: strona to aplikacja JS; pobieramy app.*.js, wyciagamy adresy API i probujemy te o meczach/turniejach
    (surowe odpowiedzi w zipie). Parser wynikow — po pierwszym pobraniu, jak przy 90minut."""
    baza = 'https://setkacup.com'
    kod, t = s.get('setka', baza + '/', H_HTML, proby=1)
    skrypty = re.findall(r'src="(/[^"]+\.js)"', t or '')
    w['setka_skrypty'] = [{'skrypt': x} for x in skrypty]
    adresy, sciezki = [], []
    for sk in skrypty[:3]:
        k2, js = s.get('setka_js', baza + sk, {**H_HTML, 'Accept': '*/*'}, proby=1)
        a_, p_ = setka_api(js)
        adresy += a_; sciezki += p_
        # fragmenty kodu wokol slow match/tournament/result — do recznego odczytania ksztaltu zapytan
        w.setdefault('setka_fragmenty', []).extend(
            {'skrypt': sk, 'fragment': js[max(0, m.start() - 150):m.end() + 150]}
            for m in list(re.finditer(r'(?i)(matches|tournament|results|schedule|games)[\w/?=&{}$.-]{0,40}', js or ''))[:60])
    w['setka_api'] = [{'adres': x} for x in sorted(set(adresy))] + [{'adres': x} for x in sorted(set(sciezki))]
    kand = [x for x in sorted(set(adresy)) if re.search(r'(?i)api|match|game|tourn|result', x)][:6]
    kand += [baza + x for x in sorted(set(sciezki)) if re.search(r'(?i)match|game|tourn|result|event', x)][:6]
    for url in kand[:8]:
        if '{' in url or '$' in url: continue
        s.get('setka', url, {**H_JSON, 'Accept': 'application/json, text/plain, */*', 'Origin': baza, 'Referer': baza + '/'}, proby=1)


DZIENNE = ('elo', 'transfermarkt', 'understat', 'tenis', 'darty')
WSZYSTKIE = DZIENNE + ('fotmob', 'sofascore', 'nhl', 'pogoda', 's24', '90minut', 'setka')


def zapisz(kat, nazwa, wiersze, znacznik):
    if not wiersze: return None
    kol = list(dict.fromkeys(k for r in wiersze for k in r))
    p = os.path.join(kat, f'zrodla_{nazwa}_{znacznik}.csv.gz')
    with gzip.open(p, 'wt', encoding='utf-8', newline='') as f:
        cw = csv.DictWriter(f, kol)
        cw.writeheader(); cw.writerows(wiersze)
    return p


def wyslij_wyniki(pliki, a):
    """Pliki wynikow (wyniki_*_RRRR-MM.csv.gz) do GLOWNEGO folderu baza-wiedzy (gdrive:), nadpisujac poprzednia wersje —
    tam szuka ich paczka.gs. Kopia skumulowana zostaje w ~/.zrodla_wyniki."""
    if not pliki or '--bez-wysylki' in a or not os.path.isdir('/data/data/com.termux') or not shutil.which('rclone'): return
    for p in pliki:
        r = subprocess.run(['rclone', 'moveto', p, 'gdrive:' + os.path.basename(p)], capture_output=True, text=True)
        print('rclone ->', os.path.basename(p), 'OK' if r.returncode == 0 else f'BLAD {r.returncode}: {r.stderr[-300:]}')


def wyslij(zp, a):
    """Na telefonie: rclone do PODFOLDERU zrodla/ (gdrive: = baza-wiedzy), zeby nie zasmiecac folderu przebiegu.
    Poza Termuxem albo z --bez-wysylki — plik zostaje lokalnie."""
    if '--bez-wysylki' in a or not os.path.isdir('/data/data/com.termux') or not shutil.which('rclone'): return
    r = subprocess.run(['rclone', 'move', zp, 'gdrive:zrodla/'], capture_output=True, text=True)
    print('rclone -> gdrive:zrodla/', 'OK' if r.returncode == 0 else f'BLAD {r.returncode}: {r.stderr[-300:]}')


def main(a):
    kat = a[a.index('--katalog') + 1] if '--katalog' in a else '/sdcard/Download'
    budzet = float(a[a.index('--budzet-min') + 1]) if '--budzet-min' in a else 12.0
    tylko = set(a[a.index('--tylko') + 1].split(',')) if '--tylko' in a else set(WSZYSTKIE)
    teraz = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    dzis = (teraz + dt.timedelta(hours=2)).date()
    try: stan = json.load(open(STAN))
    except (OSError, ValueError): stan = {}
    gotowe = set(stan.get('gotowe', []))
    s, w, bledy = Sesja(budzet * 60), {}, {}
    zadania = [('setka', lambda: z_setka(s, w)),
               ('s24', lambda: z_s24(s, w, teraz, stan, int(a[a.index('--historia-s24') + 1]) if '--historia-s24' in a else 0, kat)),
               ('90minut', lambda: z_90minut(s, w, teraz)),
               ('fotmob', lambda: z_fotmob(s, w, dzis, teraz, gotowe)), ('sofascore', lambda: z_sofa(s, w, dzis, teraz)),
               ('nhl', lambda: z_nhl(s, w, dzis)), ('pogoda', lambda: z_pogoda(s, w)),
               ('elo', lambda: z_elo(s, w)), ('tenis', lambda: z_tenis(s, w)), ('darty', lambda: z_darty(s, w, dzis)),
               ('understat', lambda: z_understat(s, w, dzis, '--historia' in a)), ('transfermarkt', lambda: z_transfermarkt(s, w))]
    for nazwa, f in zadania:
        if nazwa not in tylko: continue
        if nazwa in DZIENNE and stan.get(nazwa) == str(dzis) and '--wszystkie-dzienne' not in a and '--tylko' not in a:
            bledy[nazwa] = 'pominiete (juz pobrane dzis)'; continue
        if not s.czas(): bledy[nazwa] = 'pominiete (koniec budzetu czasu)'; continue
        try:
            f()
            if nazwa in DZIENNE and s.kody.get(nazwa, {}).get(200): stan[nazwa] = str(dzis)
        except Exception as e:
            bledy[nazwa] = f'{type(e).__name__}: {e}'
    w['sedziowie'] = sedziowie(w)
    pliki_wynikow = w.pop('_pliki_wynikow', [])
    zn = (teraz + dt.timedelta(hours=2)).strftime('%Y-%m-%d_%H-%M')
    tmp = os.path.join(kat, f'.zrodla_{zn}')
    os.makedirs(tmp, exist_ok=True)
    pliki = [p for p in (zapisz(tmp, n, r, zn) for n, r in w.items()) if p]
    linie = [f'ZRODLA {zn} (czas PL), budzet {budzet:.0f} min, zuzyto {budzet * 60 - (s.koniec - time.time()):.0f} s']
    for nazwa in WSZYSTKIE:
        if nazwa not in tylko: continue
        linie.append(f'{nazwa:<14} HTTP {json.dumps(s.kody.get(nazwa, {}))} {bledy.get(nazwa, "")}')
    for n, r in w.items():
        linie.append(f'  {n:<22} {len(r)} wierszy')
    with open(os.path.join(tmp, f'zrodla_diag_{zn}.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(linie) + '\n')
    with gzip.open(os.path.join(tmp, f'zrodla_surowe_{zn}.jsonl.gz'), 'wt', encoding='utf-8') as f:
        for x in s.surowe: f.write(json.dumps(x, ensure_ascii=False) + '\n')
    # JEDEN plik na uruchomienie (03.10.2026): skrypty Apps Script (paczka, dzienniki, push_github) przegladaja caly
    # folder baza-wiedzy — kilkanascie plikow co przebieg spowalnialoby je z kazdym dniem.
    zp = os.path.join(kat, f'zrodla_{zn}.zip')
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_STORED) as zf:
        for n in sorted(os.listdir(tmp)):
            zf.write(os.path.join(tmp, n), n)
            os.remove(os.path.join(tmp, n))
    os.rmdir(tmp)
    stan['gotowe'] = sorted(gotowe)[-3000:]
    try: json.dump(stan, open(STAN, 'w'))
    except OSError: pass
    print('\n'.join(linie))
    print(f'Zapisano {zp} ({len(pliki)} plikow danych + diag + surowe)')
    wyslij(zp, a)
    if pliki_wynikow: print('Pliki wynikow dla przebiegu:', ', '.join(os.path.basename(x) for x in pliki_wynikow))
    wyslij_wyniki(pliki_wynikow, a)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
