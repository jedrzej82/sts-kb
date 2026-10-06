"""KURSY SUPERBET + LVBET (02.10.2026) — uruchamiany w Termuxie na telefonie uzytkownika (srodowisko przebiegu nie ma
dostepu do stron bukmacherow). Tylko biblioteka standardowa Pythona (pip w Termuxie bywa zepsuty po aktualizacji).

Zrodla (ustalone diagnozami 02.10, diagnoza_kursy1-4.txt w baza-wiedzy):
  Superbet: production-superbet-offer-pl.freetls.fastly.net/v2/pl-PL/events/by-date (lista, kursy glowne)
            + /v2/pl-PL/events/{eventId} (wszystkie rynki meczu) — pilka, hokej, koszykowka, reczna.
  LVBET:    offer.lvbet.pl/client-api/v5/matches/?lang=pl (lista) + matches/{match_id}/markets/?lang=pl (rynki).

Wynik: kursy_bukmacherow_RRRR-MM-DD_GG-MM.csv.gz (Pobrane) — kolumny:
  bukmacher, sport, data_meczu, godzina_meczu (czas polski), gospodarz, gosc, rynek_oryg, wybor_oryg, linia, rynek, kurs
  rynek = kod jak w ako_log (1, X, 2, 1X, X2, 12, O1.5, U3.5, BTTS_tak, BTTS_nie, DNB_1, DNB_2, Zwyciezca 1/2,
          gosp_O0.5, gość_O0.5; koszykowka O/U z dogrywka); pusty = rynek zapisany tylko surowo (rynek_oryg/wybor_oryg).

Uzycie:  python kursy_bukmacherow.py --diag-lvbet   (numery sportow LVBET)
         python kursy_bukmacherow.py --diag-sts [--katalog /sdcard/Download]   (skad strona STS bierze oferte;
                                                    plik diag_sts_*.txt do wgrania na Dysk)
         python kursy_bukmacherow.py [--godzin 30] [--bez-lvbet] [--bez-superbet] [--katalog /sdcard/Download] [--wszystko]
         (--wszystko = takze rynki bez kodu; domyslnie tylko z kodem — plik ok. 30 razy mniejszy)"""
import csv
import datetime as dt
import gzip
import io
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

H = {'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/128 Mobile Safari/537.36',
     'Accept': 'application/json, text/plain, */*', 'Accept-Language': 'pl-PL,pl;q=0.9'}
CTX = ssl.create_default_context()
SB = 'https://production-superbet-offer-pl.freetls.fastly.net/v2/pl-PL'
LV = 'https://offer.lvbet.pl/client-api/v5/'
# Superbet sportId -> nazwa sportu jak w PDF STS
SB_SPORT = {5: 'PIŁKA NOŻNA', 3: 'HOKEJ NA LODZIE', 4: 'KOSZYKÓWKA', 11: 'PIŁKA RĘCZNA', 1: 'SIATKÓWKA', 2: 'TENIS', 13: 'DART'}
SB_DETAL = {5, 3, 4, 11}           # szczegoly: pilka, hokej, koszykowka, reczna
# LVBET sports_groups_ids[0] -> sport (1 pilka, 2 hokej — diagnoza 02.10; 3 koszykowka, 4 tenis, 29 reczna —
# --diag-lvbet 02.10 08:19: NBA / BC Elbrus, turnieje tenisowe, BM Granollers; 6 = futbol amerykanski)
# 04.10.2026 (Raport 15:00 usterka 6): NFL na kuponach (P130, Zwyciezca meczu) nie mialo zadnego kursu poza STS —
# grupa 6 (futbol amerykanski, rozpoznana --diag-lvbet 02.10) byla pomijana.
LV_SPORT = {1: 'PIŁKA NOŻNA', 2: 'HOKEJ NA LODZIE', 3: 'KOSZYKÓWKA', 4: 'TENIS', 29: 'PIŁKA RĘCZNA', 6: 'FUTBOL AMERYKAŃSKI'}
SPORTY_Z_REMISEM = ('PIŁKA NOŻNA', 'PIŁKA RĘCZNA')
KOLUMNY = ['bukmacher', 'sport', 'data_meczu', 'godzina_meczu', 'gospodarz', 'gosc', 'rynek_oryg', 'wybor_oryg', 'linia',
           'rynek', 'kurs']


def get(url, naglowki=None, proby=3):
    for i in range(proby):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=naglowki or H), timeout=40, context=CTX)
            return json.loads(r.read().decode('utf-8', 'replace'))
        except Exception:
            if i == proby - 1: raise
            time.sleep(2 * (i + 1))


def _ost_niedziela(rok, mies):
    d = dt.datetime(rok, mies, 31 if mies in (3, 10) else 30)
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)


def na_pl(t):
    """UTC -> czas polski regula UE (CEST od ostatniej niedzieli marca 01:00 UTC do ostatniej niedzieli pazdziernika
    01:00 UTC). Bez zoneinfo — Termux bywa bez bazy stref czasowych."""
    t = t.astimezone(dt.timezone.utc).replace(tzinfo=None) if t.tzinfo else t
    lato = _ost_niedziela(t.year, 3).replace(hour=1) <= t < _ost_niedziela(t.year, 10).replace(hour=1)
    return t + dt.timedelta(hours=2 if lato else 1)


def czas_pl(utc):
    t = dt.datetime.fromisoformat(str(utc).replace('Z', '+00:00'))
    if t.tzinfo is None: t = t.replace(tzinfo=dt.timezone.utc)
    t = na_pl(t)
    return t.strftime('%Y-%m-%d'), t.strftime('%H:%M')


def _n(s):
    return re.sub(r'\s+', ' ', str(s)).strip().lower()


def kod_rynku(rynek, wybor, linia, gosp, gosc, sport, z_remisem=None):
    """Rynek bukmachera -> kod jak w ako_log; '' gdy rynek spoza uzywanych (zostaje surowy).
    z_remisem = rynek ma wybor „Remis” (trojdrogowy) — wtedy NIE jest to „Zwyciezca” z dogrywka; False (LVBET: rynek
    bez „Remis”) w pilce/recznej = dwudrogowy (02.10: reczna LVBET „Zwycięzca meczu” 1/2 bez X, kursy o ~10% nizsze
    niz 1/2 STS) — bez kodu; None = nie wiadomo (Superbet)."""
    r, w = _n(rynek), _n(wybor)
    g, a = _n(gosp), _n(gosc)
    reg = r.endswith('(regulaminowy czas)')
    r = r.replace(' (regulaminowy czas)', '')
    # LVBET: w hokeju „Zwycięzca meczu” bez dopisku = z dogrywka (dwudrogowy), „(regulaminowy czas)” = 1/X/2.
    # 02.10: tak samo koszykowka; Superbet „Zwycięzca” (tenis, siatkowka, dart) = dwudrogowy. Pilka nozna i reczna
    # maja remis — tam „zwycięzca meczu” to 1/X/2 (nizej).
    if sport not in SPORTY_Z_REMISEM and r in ('zwycięzca meczu', 'zwycięzca') and not reg and not z_remisem:
        return {g: 'Zwyciezca 1', a: 'Zwyciezca 2', '1': 'Zwyciezca 1', '2': 'Zwyciezca 2'}.get(w, '')
    if r == 'zwycięzca meczu' and sport in SPORTY_Z_REMISEM and z_remisem is False:
        return ''
    if r in ('mecz', '1x2', 'wynik meczu', 'wynik meczu (1x2)', 'zwycięzca meczu (1x2)', 'zwycięzca meczu'):
        return {'1': '1', 'x': 'X', '2': '2', 'remis': 'X', g: '1', a: '2'}.get(w, '')
    if r == 'podwójna szansa':
        k = {'1x': '1X', 'x2': 'X2', '12': '12', '2x': 'X2', 'x1': '1X', '21': '12'}.get(w.replace(' ', '').replace('/', ''))
        if k: return k
        # LVBET: „A lub remis” / „B lub remis” / „A lub B” („B or A”)
        cz = [c.strip() for c in re.split(r'\s+(?:lub|or)\s+', w)]
        if len(cz) == 2 and 'remis' in cz:
            t = cz[0] if cz[1] == 'remis' else cz[1]
            return '1X' if t == g else ('X2' if t == a else '')
        if len(cz) == 2 and set(cz) == {g, a}: return '12'
        return ''
    if sport in SPORTY_Z_REMISEM and r in ('liczba goli', 'suma goli', 'gole', 'liczba bramek') and linia not in (None, ''):
        if w.startswith('powyżej'): return f'O{float(linia):g}' if float(linia) % 1 else ''
        if w.startswith('poniżej'): return f'U{float(linia):g}' if float(linia) % 1 else ''
    if r in ('obie drużyny strzelą', 'obie drużyny strzelą gola', 'obie strzelą'):
        return {'tak': 'BTTS_tak', 'nie': 'BTTS_nie'}.get(w, '')
    if r in ('zakład bez remisu', 'remis - brak zakładu', 'remis bez zakładu'):
        return {g: 'DNB_1', a: 'DNB_2', '1': 'DNB_1', '2': 'DNB_2'}.get(w, '')
    if sport not in SPORTY_Z_REMISEM and r.startswith('zwycięzca') and ('dogryw' in r or 'karn' in r) and not z_remisem:
        return {g: 'Zwyciezca 1', a: 'Zwyciezca 2', '1': 'Zwyciezca 1', '2': 'Zwyciezca 2'}.get(w, '')
    # koszykowka: suma punktow z dogrywka (jak STS „Liczba punktów (z dogrywką)”)
    if (sport == 'KOSZYKÓWKA' and re.match(r'^(liczba|suma) punktów', r) and 'dogryw' in r
            and linia not in (None, '') and float(linia) % 1):
        if w.startswith(('powyżej', 'więcej', '+')): return f'O{float(linia):g}'
        if w.startswith(('poniżej', 'mniej', '-')): return f'U{float(linia):g}'
    m = re.match(r'^(.*) - (liczba goli|suma goli)$', r)
    if sport == 'PIŁKA NOŻNA' and m and linia not in (None, '') and float(linia) == 0.5 and w.startswith('powyżej'):
        if m.group(1) == g: return 'gosp_O0.5'
        if m.group(1) == a: return 'gość_O0.5'
    return ''


def superbet(od, do, wiersze):
    lista = get(f'{SB}/events/by-date?currentStatus=active&offerState=prematch'
                f'&startDate={od:%Y-%m-%d+%H:%M:%S}&endDate={do:%Y-%m-%d+%H:%M:%S}')['data']
    n_det = 0
    for e in lista:
        sport = SB_SPORT.get(e.get('sportId'))
        if not sport or '·' not in str(e.get('matchName', '')): continue
        gosp, gosc = [x.strip() for x in e['matchName'].split('·', 1)]
        d, g = czas_pl(e.get('utcDate') or e['matchDate'])
        kursy = e.get('odds') or []
        if e['sportId'] in SB_DETAL:
            try:
                kursy = get(f'{SB}/events/{e["eventId"]}')['data'][0].get('odds') or kursy; n_det += 1
            except Exception as x:
                print(f'  superbet: brak szczegolow {e["matchName"]} ({x})')
        for o in kursy:
            if o.get('status') != 'active' or o.get('marketId') == 231194: continue   # 231194 = gotowe kombinacje „superbets”
            linia = (o.get('specifiers') or {}).get('total', '')
            wiersze.append(dict(bukmacher='SUPERBET', sport=sport, data_meczu=d, godzina_meczu=g, gospodarz=gosp, gosc=gosc,
                                rynek_oryg=o.get('marketName', ''), wybor_oryg=o.get('name', ''), linia=linia,
                                rynek=kod_rynku(o.get('marketName', ''), o.get('name', ''), linia, gosp, gosc, sport),
                                kurs=o.get('price', '')))
    print(f'SUPERBET: {len(lista)} zdarzen w oknie, szczegoly {n_det}')


def lvbet(od, do, wiersze):
    hl = dict(H, Origin='https://lvbet.pl', Referer='https://lvbet.pl/')
    lista = get(f'{LV}matches/?lang=pl', hl)
    n = 0
    for m in lista:
        sg = (m.get('sports_groups_ids') or [None])[0]
        sport = LV_SPORT.get(sg)
        st = m.get('state') or {}
        if not sport or not st.get('is_pre') or st.get('status') != 'open': continue
        if len(m.get('home') or []) != 1 or len(m.get('away') or []) != 1: continue
        t = dt.datetime.fromisoformat(m['date'])
        if not (od <= t.astimezone(dt.timezone.utc).replace(tzinfo=None) <= do): continue
        gosp, gosc = m['home'][0], m['away'][0]
        d, g = czas_pl(m['date'])
        try:
            rynki = get(f'{LV}matches/{m["match_id"]}/markets/?lang=pl', hl); n += 1
        except Exception as x:
            print(f'  lvbet: brak rynkow {gosp} - {gosc} ({x})'); continue
        for r in rynki:
            if (r.get('state') or {}).get('status') != 'open': continue
            linia = r.get('line')
            z_remisem = any(_n(s.get('name', '')) == 'remis' for s in r.get('selections') or [])
            for s in r.get('selections') or []:
                if s.get('status') != 'open': continue
                wiersze.append(dict(bukmacher='LVBET', sport=sport, data_meczu=d, godzina_meczu=g, gospodarz=gosp, gosc=gosc,
                                    rynek_oryg=r.get('name', ''), wybor_oryg=s.get('name', ''), linia='' if linia is None else linia,
                                    rynek=kod_rynku(re.sub(r'\s+[\d.]+$', '', r.get('name', '')), s.get('name', ''), linia, gosp, gosc,
                                                    sport, z_remisem),
                                    kurs=(s.get('rate') or {}).get('decimal', '')))
    print(f'LVBET: {len(lista)} meczow w ofercie, rynki pobrane dla {n}')


def diag_lvbet():
    """Numery sportow LVBET (sports_groups_ids[0]): liczba meczow, przyklady par i nazwy rynkow pierwszego meczu."""
    hl = dict(H, Origin='https://lvbet.pl', Referer='https://lvbet.pl/')
    grupy = {}
    for m in get(f'{LV}matches/?lang=pl', hl):
        grupy.setdefault((m.get('sports_groups_ids') or [None])[0], []).append(m)
    for sg, ms in sorted(grupy.items(), key=lambda x: -len(x[1])):
        pary = [f"{(m.get('home') or ['?'])[0]} - {(m.get('away') or ['?'])[0]}" for m in ms[:3]]
        print(f'{sg}: {len(ms)} | ' + ' | '.join(pary))
        if sg not in LV_SPORT and len(ms) >= 5:
            try:
                nz = sorted({r.get('name', '') for r in get(f'{LV}matches/{ms[0]["match_id"]}/markets/?lang=pl', hl)})
                print('    rynki: ' + ' ; '.join(nz[:15]))
            except Exception as x:
                print(f'    rynki: blad {x}')


# ---------------- diagnoza STS (06.10.2026) ----------------
# Kursy STS bierzemy z PDF oferty — STS ucina w nim dlugie nazwy, a uklad PDF moze sie zmienic. Cel: kursy STS ze strony
# (jak Superbet i LVBET). Srodowisko przebiegu i sesja w chmurze nie maja dostepu do sts.pl, wiec diagnoza idzie
# na telefonie: strona -> skrypty -> adresy API -> jedna proba kazdego adresu. Bez logowania, bez danych konta.
STS_STRONY = ('https://www.sts.pl/', 'https://www.sts.pl/zaklady-bukmacherskie/pilka-nozna')
_STS_ADRES = re.compile(r"(?:https?:|wss?:)?//[a-z0-9][a-z0-9.-]*(?:\.|^)sts(?:bet)?\.[a-z]{2,3}(?:/[^\s\"'`<>)\\]*)?", re.I)
_STS_SCIEZKA = re.compile(r"[\"'`](/(?:api|offer|oferta|graphql|gql|sportsbook|feed|odds|events|betting)[^\"'`\s<>]*)[\"'`]", re.I)
_STS_SKRYPT = re.compile(r"<script[^>]+src=[\"']([^\"']+)[\"']", re.I)
_STS_DANE = re.compile(r'(__NEXT_DATA__|__NUXT__|__INITIAL_STATE__|__APOLLO_STATE__|window\.__[A-Z_]+__)')
_STS_STATYCZNY = re.compile(r'\.(?:js|css|png|jpe?g|svg|gif|webp|woff2?|ttf|ico|map)(?:\?|$)', re.I)


def _sts_pobierz(url, naglowki=None, limit=3_000_000):
    """(status, typ, tekst) — bez wyjatkow (diagnoza ma zapisac tez bledy)."""
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=naglowki or H), timeout=30, context=CTX)
        b = r.read(limit)
        if r.headers.get('Content-Encoding') == 'gzip': b = gzip.decompress(b)
        return r.status, r.headers.get('Content-Type', ''), b.decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, (e.headers.get('Content-Type', '') if e.headers else ''), (e.read(2000) or b'').decode('utf-8', 'replace')
    except Exception as e:
        return None, '', f'{type(e).__name__}: {e}'


def sts_skrypty(html, baza):
    """Adresy skryptow strony (wzgledne -> pelne), bez powtorzen, w kolejnosci."""
    out = []
    for src in _STS_SKRYPT.findall(html):
        u = src if src.startswith('http') else ('https:' + src if src.startswith('//') else baza.rstrip('/') + '/' + src.lstrip('/'))
        if u not in out: out.append(u)
    return out


def sts_adresy(tekst):
    """Adresy, ktore wygladaja na zrodlo oferty: hosty STS (ze sciezka) i sciezki /api, /offer, /graphql...
    Bez plikow statycznych (.js, .css, obrazki, czcionki)."""
    a = {m.group(0).rstrip('.,;') for m in _STS_ADRES.finditer(tekst)}
    a |= {m.group(1) for m in _STS_SCIEZKA.finditer(tekst)}
    return sorted(x for x in a if not _STS_STATYCZNY.search(x) and len(x) < 200)


_HOST_W_ADRESIE = re.compile(r"(?:https?|wss?):\\?/\\?/([a-z0-9][a-z0-9.-]*\.[a-z]{2,})", re.I)
_HOST_GOLY = re.compile(r"[\"'`]([a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:pl|com|io|net|eu|cloud|bet|app))[\"'`/]", re.I)
_STS_CHUNK = re.compile(r"[\"'`(/]((?:nextweb-assets/)?(?:chunk|[a-z-]+)-[A-Z0-9]{6,}\.js)", re.I)
_STS_SLOWA = ('offer', 'odds', 'market', 'apiUrl', 'baseUrl', 'apiBase', 'graphql', 'websocket', 'wss:', 'sportsbook',
              'betting', 'eventId', 'environment')


def sts_hosty(tekst):
    """Wszystkie hosty w kodzie (nie tylko sts.pl): adres API bywa w innej domenie albo skladany z czesci."""
    h = {}
    for m in list(_HOST_W_ADRESIE.finditer(tekst)) + list(_HOST_GOLY.finditer(tekst)):
        x = m.group(1).lower().rstrip('.')
        if re.search(r'\.(?:js|css|png|svg|jpg|json|map|html)$', x): continue
        h[x] = h.get(x, 0) + 1
    return h


def sts_chunki(tekst, baza='https://www.sts.pl/nextweb-assets/'):
    """Doladowywane pliki aplikacji (import() w main.js): „chunk-ABC123.js” -> pelny adres."""
    out = []
    for m in _STS_CHUNK.finditer(tekst):
        n = m.group(1).split('/')[-1]
        u = baza + n
        if u not in out: out.append(u)
    return out


def sts_konteksty(tekst, slowo, ile=8, szer=110):
    """Fragmenty kodu wokol slowa (bez powtorzen) — z nich widac, jak aplikacja sklada adres oferty."""
    out = []
    for m in re.finditer(re.escape(slowo), tekst):
        f = re.sub(r'\s+', ' ', tekst[max(0, m.start() - szer):m.end() + szer])
        if f not in out: out.append(f)
        if len(out) >= ile: break
    return out


def diag_sts(a):
    kat = a[a.index('--katalog') + 1] if '--katalog' in a else '/sdcard/Download'
    teraz = na_pl(dt.datetime.now(dt.timezone.utc))
    linie = [f'DIAGNOZA STS v2 {teraz:%Y-%m-%d %H:%M} (czas polski)']
    hs = dict(H, Accept='text/html,application/xhtml+xml,*/*')
    skrypty, adresy, hosty, kod = [], set(), {}, {}
    for url in STS_STRONY:
        st, typ, t = _sts_pobierz(url, hs)
        linie.append(f'\n== STRONA {url}: status {st}, typ {typ}, {len(t)} znakow')
        linie.append('   osadzone dane: ' + (', '.join(sorted(set(_STS_DANE.findall(t)))) or 'brak'))
        if st != 200: linie.append('   poczatek: ' + t[:400].replace('\n', ' '))
        for i, s in enumerate(re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', t, re.S | re.I)[:8]):
            if s.strip(): linie.append(f'   skrypt w HTML {i + 1}: ' + re.sub(r'\s+', ' ', s)[:300])
        for m in re.findall(r'<(?:link|meta)[^>]+>', t, re.I)[:40]:
            if re.search(r'(?i)preload|preconnect|dns-prefetch|config|env|api', m): linie.append('   ' + m[:200])
        skrypty += [s for s in sts_skrypty(t, 'https://www.sts.pl') if s not in skrypty]
        adresy |= set(sts_adresy(t))
    kolejka = list(skrypty)
    linie.append('\n== SKRYPTY (strona + doladowywane chunk-*.js, do 60)')
    i = 0
    while i < len(kolejka) and i < 60:
        u = kolejka[i]; i += 1
        st, typ, t = _sts_pobierz(u, dict(H, Accept='*/*'))
        if st == 200:
            kod[u] = t
            adresy |= set(sts_adresy(t))
            for x, n in sts_hosty(t).items(): hosty[x] = hosty.get(x, 0) + n
            kolejka += [c for c in sts_chunki(t) if c not in kolejka]
        linie.append(f'   {st} {len(t):>8} {u[:120]}')
        time.sleep(0.3)
    linie.append(f'   (znalezionych plikow: {len(kolejka)}, pobranych: {i})')
    linie.append(f'\n== HOSTY w kodzie: {len(hosty)}')
    linie += [f'   {n:>4} {x}' for x, n in sorted(hosty.items(), key=lambda z: -z[1])[:80]]
    adresy = sorted(adresy)
    linie.append(f'\n== ADRESY (mozliwe zrodla oferty): {len(adresy)}')
    linie += ['   ' + x for x in adresy[:300]]
    linie.append('\n== KOD WOKOL SLOW (jak aplikacja sklada adres oferty)')
    caly = '\n'.join(kod.values())
    for s in _STS_SLOWA:
        k = sts_konteksty(caly, s)
        linie.append(f'-- {s}: {len(k)}')
        linie += ['   ' + x for x in k]
    linie.append('\n== PROBY (GET, jedna na adres; bez adresow ze zmiennymi)')
    pr = [x for x in adresy if x.startswith(('http', '//')) and not re.search(r'[{}$]', x)]
    pr += ['https://www.sts.pl' + x for x in adresy if x.startswith('/') and not re.search(r'[{}$]', x)]
    pr += [f'https://{x}/' for x, _ in sorted(hosty.items(), key=lambda z: -z[1])
           if re.search(r'(?i)api|offer|feed|sport|bet', x) and 'sts' in x][:15]
    hj = dict(H, Origin='https://www.sts.pl', Referer='https://www.sts.pl/')
    for u in list(dict.fromkeys(pr))[:60]:
        u = 'https:' + u if u.startswith('//') else u
        st, typ, t = _sts_pobierz(u, hj, limit=200_000)
        jest_json = t.lstrip()[:1] in ('{', '[')
        linie.append(f'   {st} {typ[:40]:<40} {len(t):>7} {"JSON " if jest_json else ""}{u[:140]}')
        if st == 200 and jest_json: linie.append('      ' + t[:600].replace('\n', ' '))
        time.sleep(0.3)
    plik = f'{kat}/diag_sts_{teraz:%Y-%m-%d_%H-%M}.txt'
    with open(plik, 'w', encoding='utf-8') as fh: fh.write('\n'.join(linie) + '\n')
    print('\n'.join(linie[:12]))
    print(f'\nzapisano {plik} — wgraj ten plik na Dysk do folderu baza-wiedzy')
    return plik

def main(a):
    if '--diag-lvbet' in a: return diag_lvbet()
    if '--diag-sts' in a: return diag_sts(a)
    godzin = float(a[a.index('--godzin') + 1]) if '--godzin' in a else 30
    kat = a[a.index('--katalog') + 1] if '--katalog' in a else '/sdcard/Download'
    od = dt.datetime.now(dt.timezone.utc).replace(microsecond=0, tzinfo=None); do = od + dt.timedelta(hours=godzin)
    wiersze = []
    for nazwa, f, wyl in (('superbet', superbet, '--bez-superbet'), ('lvbet', lvbet, '--bez-lvbet')):
        if wyl in a: continue
        try:
            f(od, do, wiersze)
        except Exception as x:
            print(f'BLAD {nazwa}: {x} — plik bez tego bukmachera')
    teraz = na_pl(dt.datetime.now(dt.timezone.utc))
    plik = f'{kat}/kursy_bukmacherow_{teraz:%Y-%m-%d_%H-%M}.csv.gz'
    wszystkie = len(wiersze)
    if '--wszystko' not in a: wiersze = [x for x in wiersze if x['rynek']]   # domyslnie tylko rynki z kodem (maly plik)
    buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=KOLUMNY); w.writeheader(); w.writerows(wiersze)
    with gzip.open(plik, 'wt', encoding='utf-8') as fh: fh.write(buf.getvalue())
    print(f'zapisano {plik}: {len(wiersze)} kursow z kodem rynku (pobrano {wszystkie})')
    return plik


if __name__ == '__main__':
    main(sys.argv[1:])
