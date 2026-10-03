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
  7  Darty             D  ranking DartsOrakel; wyniki dartow sa w Sofascore (sport darts, wczoraj+dzis)
                                                                              -> zrodla_darty_ranking_*
  8  NHL               P  wyniki/terminarz NHL (api-web.nhle.com) + bramkarze (Daily Faceoff)
                                                                              -> zrodla_nhl_*, zrodla_nhl_bramkarze_*
  9  Open-Meteo        P  pogoda na godzine meczu dla meczow z wspolrzednymi stadionu (FotMob/Sofascore)
                                                                              -> zrodla_pogoda_*
  10 Sedziowie         P  sedzia meczu + jego srednie kartek (Sofascore), sedzia z FotMob -> zrodla_sedziowie_*

Diagnostyka kazdego uruchomienia: zrodla_diag_*.txt (status kazdego zrodla) i zrodla_surowe_*.jsonl.gz (do 4 surowych
odpowiedzi na zrodlo, przyciete) — z nich poprawiamy parsery bez zrzutow ekranu z telefonu.

Uzycie:  python zrodla.py [--katalog /sdcard/Download] [--tylko fotmob,nhl] [--historia] [--budzet-min 12] [--wszystkie-dzienne]"""
import csv
import datetime as dt
import gzip
import html as _html
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

UA = 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36'
H_JSON = {'User-Agent': UA, 'Accept': 'application/json, text/plain, */*', 'Accept-Language': 'en-GB,en;q=0.9'}
H_HTML = {'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8', 'Accept-Language': 'en-GB,en;q=0.9'}
CTX = ssl.create_default_context()
STAN = os.path.expanduser('~/.zrodla_stan.json')
OKNO_H = 3.5            # szczegoly dla meczow zaczynajacych sie w ciagu tylu godzin
MAKS_SZCZEGOLY = 60     # na zrodlo i uruchomienie
SURowe_NA_ZRODLO = 4
SURowe_MAKS_B = 300_000

SOFA = ('https://api.sofascore.com/api/v1', 'https://www.sofascore.com/api/v1')
SOFA_SPORTY = ('football', 'basketball', 'ice-hockey', 'handball', 'volleyball', 'darts', 'tennis')
TM_LIGI = ('GB1', 'GB2', 'ES1', 'ES2', 'IT1', 'IT2', 'L1', 'L2', 'FR1', 'FR2', 'NL1', 'PO1', 'BE1', 'TR1', 'PL1',
           'A1', 'C1', 'SC1', 'DK1', 'SE1', 'NO1', 'GR1', 'TS1', 'UKR1', 'RU1')
US_LIGI = ('EPL', 'La_liga', 'Bundesliga', 'Serie_A', 'Ligue_1', 'RFPL')


class Sesja:
    """Pobieranie z limitem czasu, licznikami HTTP i probkami surowych odpowiedzi do diagnozy."""

    def __init__(self, budzet_s):
        self.koniec = time.time() + budzet_s
        self.surowe, self.diag, self.kody = [], [], {}

    def czas(self):
        return time.time() < self.koniec

    def get(self, zrodlo, url, naglowki=H_JSON, proby=2, pauza=0.4):
        """(kod HTTP, tekst) — nigdy nie rzuca; kod 0 = blad sieci, -1 = koniec budzetu czasu."""
        if not self.czas(): return -1, ''
        kod, tekst = 0, ''
        for i in range(proby):
            try:
                r = urllib.request.urlopen(urllib.request.Request(url, headers=naglowki), timeout=30, context=CTX)
                b = r.read()
                if r.headers.get('Content-Encoding') == 'gzip': b = gzip.decompress(b)
                kod, tekst = r.status, b.decode('utf-8', 'replace')
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
        if sum(1 for s in self.surowe if s['zrodlo'] == zrodlo) < SURowe_NA_ZRODLO or kod != 200:
            if sum(1 for s in self.surowe if s['zrodlo'] == zrodlo) < SURowe_NA_ZRODLO * 3:
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
    out = []
    for m in re.finditer(r'<table([^>]*)>(.*?)</table>', s or '', re.S | re.I):
        if klasa and klasa not in m.group(1): continue
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', m.group(2), re.S | re.I):
            kom = [tekst_html(c) for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S | re.I)]
            if any(kom): out.append(kom)
    return out


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


def nhl_mecze(j, data):
    out = []
    for g in (j or {}).get('games', []) or []:
        h, a = g.get('homeTeam') or {}, g.get('awayTeam') or {}
        nm = lambda t: (t.get('name') or {}).get('default') if isinstance(t.get('name'), dict) else t.get('name')
        out.append({'data': data, 'id': g.get('id'), 'start_utc': g.get('startTimeUTC'), 'stan': g.get('gameState'),
                    'gosp': h.get('abbrev'), 'gosp_nazwa': nm(h), 'gosc': a.get('abbrev'), 'gosc_nazwa': nm(a),
                    'wynik_g': h.get('score', ''), 'wynik_a': a.get('score', ''),
                    'koniec': (g.get('periodDescriptor') or {}).get('periodType', '')})
    return out


def bramkarze(tekst):
    """Daily Faceoff: __NEXT_DATA__ -> slowniki z polami bramkarzy (zapis wszystkich pol *oalie*/*News*/*Team*)."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', tekst or '', re.S)
    if not m: return []
    try: j = json.loads(m.group(1))
    except ValueError: return []
    out = []
    for d in chodz(j):
        if any('oalie' in k for k in d) and any('Team' in k or 'team' in k for k in d):
            out.append({'dane': json.dumps({k: v for k, v in d.items() if not isinstance(v, (dict, list))}, ensure_ascii=False)})
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
        if isinstance(x, (int, float)) or str(x).isdigit(): return dt.datetime.utcfromtimestamp(int(x))
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
    baza = None
    mecze = []
    for sport in SOFA_SPORTY:
        for d in (dzis - dt.timedelta(days=1), dzis):
            for b in ([baza] if baza else SOFA):
                j = s.get_json('sofascore', f'{b}/sport/{sport}/scheduled-events/{d}')
                if j is not None: baza = b; mecze += sofa_mecze(j, sport, str(d)); break
    w['sofascore_mecze'] = mecze
    if not baza: return
    out = []
    for m in [m for m in mecze if m['sport'] == 'football' and m['status'] == 'notstarted'
              and (lambda t: t and teraz <= t <= teraz + dt.timedelta(hours=OKNO_H))(utc_z(m['start_ts']))][:MAKS_SZCZEGOLY]:
        lu = s.get_json('sofascore', f"{baza}/event/{m['id']}/lineups")
        ev = s.get_json('sofascore', f"{baza}/event/{m['id']}")
        out.append({'id': m['id'], 'turniej': m['turniej'], 'kategoria': m['kategoria'], 'gosp': m['gosp'], 'gosc': m['gosc'],
                    'start_utc': utc_z(m['start_ts']).isoformat(), **sofa_sklad(lu, ev)})
    w['sofascore_sklady'] = out


def z_transfermarkt(s, w):
    out = []
    for lg in TM_LIGI:
        for typ, sciezka in (('kontuzje', 'verletztespieler'), ('wartosci', 'startseite')):
            kod, t = s.get('transfermarkt', f'https://www.transfermarkt.com/liga/{sciezka}/wettbewerb/{lg}', H_HTML, pauza=2.0)
            if kod != 200: continue
            for kom in tabele_html(t, 'items'):
                out.append({'liga': lg, 'typ': typ, 'komorki': ' | '.join(kom)})
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
        kod, t = s.get('tenis_elo', f'https://tennisabstract.com/reports/{tura}_elo_ratings.html', H_HTML, pauza=1.0)
        if kod != 200: continue
        tab = tabele_html(t, 'reportable') or tabele_html(t)
        for kom in tab:
            out.append({'tura': tura, 'pozycja': kom[0], 'zawodnik': kom[1] if len(kom) > 1 else '', 'komorki': ' | '.join(kom)})
    w['tenis_elo'] = out


def z_darty(s, w):
    kod, t = s.get('darty', 'https://dartsorakel.com/rank', H_HTML)
    w['darty_ranking'] = [{'komorki': ' | '.join(k)} for k in tabele_html(t)] if kod == 200 else []


def z_nhl(s, w, dzis):
    out = []
    for d in (dzis - dt.timedelta(days=1), dzis, dzis + dt.timedelta(days=1)):
        out += nhl_mecze(s.get_json('nhl', f'https://api-web.nhle.com/v1/score/{d}'), str(d))
    w['nhl'] = out
    kod, t = s.get('nhl', 'https://www.dailyfaceoff.com/starting-goalies/', H_HTML)
    w['nhl_bramkarze'] = bramkarze(t) if kod == 200 else []


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


DZIENNE = ('elo', 'transfermarkt', 'understat', 'tenis', 'darty')
WSZYSTKIE = DZIENNE + ('fotmob', 'sofascore', 'nhl', 'pogoda')


def zapisz(kat, nazwa, wiersze, znacznik):
    if not wiersze: return None
    kol = list(dict.fromkeys(k for r in wiersze for k in r))
    p = os.path.join(kat, f'zrodla_{nazwa}_{znacznik}.csv.gz')
    with gzip.open(p, 'wt', encoding='utf-8', newline='') as f:
        cw = csv.DictWriter(f, kol)
        cw.writeheader(); cw.writerows(wiersze)
    return p


def main(a):
    kat = a[a.index('--katalog') + 1] if '--katalog' in a else '/sdcard/Download'
    budzet = float(a[a.index('--budzet-min') + 1]) if '--budzet-min' in a else 12.0
    tylko = set(a[a.index('--tylko') + 1].split(',')) if '--tylko' in a else set(WSZYSTKIE)
    teraz = dt.datetime.utcnow()
    dzis = (teraz + dt.timedelta(hours=2)).date()
    try: stan = json.load(open(STAN))
    except (OSError, ValueError): stan = {}
    gotowe = set(stan.get('gotowe', []))
    s, w, bledy = Sesja(budzet * 60), {}, {}
    zadania = [('fotmob', lambda: z_fotmob(s, w, dzis, teraz, gotowe)), ('sofascore', lambda: z_sofa(s, w, dzis, teraz)),
               ('nhl', lambda: z_nhl(s, w, dzis)), ('pogoda', lambda: z_pogoda(s, w)),
               ('elo', lambda: z_elo(s, w)), ('tenis', lambda: z_tenis(s, w)), ('darty', lambda: z_darty(s, w)),
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
    zn = (teraz + dt.timedelta(hours=2)).strftime('%Y-%m-%d_%H-%M')
    os.makedirs(kat, exist_ok=True)
    pliki = [p for p in (zapisz(kat, n, r, zn) for n, r in w.items()) if p]
    linie = [f'ZRODLA {zn} (czas PL), budzet {budzet:.0f} min, zuzyto {budzet * 60 - (s.koniec - time.time()):.0f} s']
    for nazwa in WSZYSTKIE:
        if nazwa not in tylko: continue
        linie.append(f'{nazwa:<14} HTTP {json.dumps(s.kody.get(nazwa, {}))} {bledy.get(nazwa, "")}')
    for n, r in w.items():
        linie.append(f'  {n:<22} {len(r)} wierszy')
    with open(os.path.join(kat, f'zrodla_diag_{zn}.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(linie) + '\n')
    with gzip.open(os.path.join(kat, f'zrodla_surowe_{zn}.jsonl.gz'), 'wt', encoding='utf-8') as f:
        for x in s.surowe: f.write(json.dumps(x, ensure_ascii=False) + '\n')
    stan['gotowe'] = sorted(gotowe)[-3000:]
    try: json.dump(stan, open(STAN, 'w'))
    except OSError: pass
    print('\n'.join(linie))
    print(f'Zapisano {len(pliki)} plikow danych + diag + surowe w {kat}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
