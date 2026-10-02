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
# --diag-lvbet 02.10 08:19: NBA / BC Elbrus, turnieje tenisowe, BM Granollers; 6 = futbol amerykanski, pominiety)
LV_SPORT = {1: 'PIŁKA NOŻNA', 2: 'HOKEJ NA LODZIE', 3: 'KOSZYKÓWKA', 4: 'TENIS', 29: 'PIŁKA RĘCZNA'}
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


def main(a):
    if '--diag-lvbet' in a: return diag_lvbet()
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
