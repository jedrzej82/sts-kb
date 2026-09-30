#!/usr/bin/env python3
"""Caly przebieg budowy bazy JEDNYM poleceniem, w jedynej poprawnej kolejnosci, z twarda kontrola danych.
  python3 przebieg.py            — kontrola plikow zewn/ → build_kb → uzupelnij_ligi → build_kb → hist_import → swiezosc
  python3 przebieg.py --kontrola — tylko kontrola plikow zewn/ (sekundy), bez budowy
  python3 przebieg.py --archiwum-arkuszy — spakuj statystyki_*.csv do arkusze_RRRR-MM-DD.tar.gz (historia arkuszy)
  python3 przebieg.py --dzienniki — rozpakuj kb/dzienniki.zip (Apps Script dzienniki.gs) do kb/dzienniki/ i scal dzienniki
  Pliki zwrocone przez Dysk W TRESCI (base64): zapisz tekst jako zewn/NAZWA.csv.gz.b64 — przebieg sam je zdekoduje.

Ostatnia linia wyniku to WERDYKT:
  „PRZEBIEG OK — mozna typowac”                        → dane kompletne i swieze
  „PRZEBIEG BLAD: <powod> — ZADNEGO kuponu za pieniadze” → nie typuj na pieniadze, napisz powod w raporcie

24.09.2026 (Poprawka 50). Po co: przebieg 18:50 policzyl wszystko na danych z 20.09 i bez archiwum sezonu
2025/26 (336 tys. meczow zamiast ~398 tys.), bo (1) w repo leza pliki zewn/ z 21.09 i po sklonowaniu wygladaja
na dzisiejsze, (2) pominieto uzupelnij_ligi.py — archiwum wchodzi do bazy TYLKO przez ten skrypt.
Nic tu nie zgaduje: sprawdza daty meczow w plikach i liczbe meczow w bazie."""
import os, sys, subprocess, sqlite3, datetime as dt, glob
import pandas as pd
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ZD = os.path.join(HERE, 'zewn')
# 28.09.2026 (Poprawka 55, USTERKA 2 z przebiegu 21:00): kontener chodzi w UTC, a arkusze Google zapisuja
# data_aktualizacji w czasie POLSKIM. Porownanie z dt.datetime.now() (UTC) zanizalo wiek arkusza o 1–2 h
# (21:29 PL: „statystyki_koszykowka … 19:46 (-1 h)”). Arkusz stary o 25 h wychodzil jako 23 h i NIE dostawal
# ostrzezenia. Wszystkie „teraz” i „dzis” w tym pliku licza sie w strefie uzytkownika.
STREFA = ZoneInfo('Europe/Warsaw')


def teraz_pl():
    """Biezacy czas polski jako naiwny datetime — w tej samej strefie co data_aktualizacji arkuszy."""
    return dt.datetime.now(STREFA).replace(tzinfo=None)


DZIS = teraz_pl().date()
MIN_MECZOW = 390_000          # po poprawnym przebiegu 24.09: 398 738
MAKS_WIEK_DNI = 1             # wyniki z biezacego miesiaca musza siegac co najmniej wczoraj
KROKI = [('build_kb.py', 'b1'), ('uzupelnij_ligi.py', 'u'), ('build_kb.py', 'b2'), ('hist_import.py', 'h'), ('swiezosc.py', 'sw')]


def dekoduj_inline():
    """Poprawka 51: konektor Dysku zwraca male pliki (np. wyniki_lol_inne) W TRESCI odpowiedzi, jako base64.
    Zapisz sam tekst base64 (albo cala odpowiedz JSON z polem content) do zewn/NAZWA.csv.gz.b64 —
    ten krok zamieni go na zewn/NAZWA.csv.gz i sprawdzi, czy to poprawny gzip."""
    import base64, json, gzip
    for f in sorted(glob.glob(os.path.join(ZD, '*.b64'))):
        t = open(f, encoding='utf-8', errors='replace').read().strip()
        try:
            if t.startswith('{'): t = json.loads(t)['content']
            raw = base64.b64decode(''.join(t.split()))
            gzip.decompress(raw)                      # test: czy to caly, poprawny gzip
        except Exception as e:
            print(f'  BLAD: {os.path.basename(f)} nie jest poprawnym base64 pliku gzip ({e}) — pobierz ponownie')
            continue
        cel = f[:-4]
        open(cel, 'wb').write(raw); os.remove(f)
        print(f'  zdekodowano {os.path.basename(f)} -> zewn/{os.path.basename(cel)} ({len(raw)} B)')


ARKUSZE = ('statystyki_druzyn', 'statystyki_tenis', 'statystyki_koszykowka', 'statystyki_siatkowka')
# opcjonalne — odswiezane raz na dobe (wieczorem), wiec aktualne do ok. 30 h
ARKUSZE_OPCJ = ('statystyki_hokej', 'statystyki_reczna', 'statystyki_baseball', 'statystyki_futbol_amerykanski', 'statystyki_rugby')
MAKS_WIEK_ARKUSZA_OPCJ_H = 30
MAKS_WIEK_ARKUSZA_H = 24


ARKUSZ_SPORT = {'statystyki_hokej': 'hockey', 'statystyki_reczna': 'handball', 'statystyki_baseball': 'baseball',
                'statystyki_futbol_amerykanski': 'american-football', 'statystyki_rugby': 'rugby-union'}
DO_POBRANIA = []


def mecze_w_terminarzu(sport, dzien=None):
    """Liczba meczow sportu (kod Flashscore/365) w terminarzu na dany dzien; None = brak terminarza."""
    if not sport: return None
    try:
        import terminarz
        t = terminarz.wczytaj()
    except Exception:
        return None
    if t is None or not len(t) or 'sport' not in t or 'data' not in t: return None
    d = str(dzien or DZIS)
    return int(((t.sport == sport) & (t.data.astype(str).str[:10] == d)).sum())


def _aktualizacja(f):
    """Najnowsza data_aktualizacji arkusza jako datetime (None, gdy nieczytelna).
    30.09.2026 (audyt tenisa): arkusze pisza godzine BEZ zera („2026-09-30 8:45”), a max() na napisach dawal
    „8:45” > „16:46” — porownujemy daty, nie napisy."""
    try:
        v = pd.read_csv(f, usecols=['data_aktualizacji'], low_memory=False).data_aktualizacji.astype(str).str[:16]
        t = pd.to_datetime(v, format='%Y-%m-%d %H:%M', errors='coerce').max()
        return None if pd.isna(t) else t.to_pydatetime()
    except Exception:
        return None


def rozpakuj_arkusze():
    """30.09.2026 (Raport 15:00, usterka 4): arkusz pobrany jako tekst CSV konektor zwraca W TRESCI odpowiedzi,
    a przepisanie go w calosci nie miescilo sie w budzecie — przebieg zapisal hokej i reczna NIEPELNE (85 i 39 wierszy).
    Apps Script arkusze.gs zapisuje co 30 min statystyki_*.csv.gz (i absencje.csv.gz) — kilka razy mniej tekstu.
    Zapisz je do kb/ jako NAZWA.csv.gz (duzy plik: jq -r .content | base64 -d) albo tekst base64 jako NAZWA.csv.gz.b64;
    ten krok sprawdza gzip i rozpakowuje do NAZWA.csv. Gdy jest tez NAZWA.csv, zostaje ten z nowsza data_aktualizacji."""
    import base64, json, gzip
    for f in sorted(glob.glob(os.path.join(HERE, 'statystyki_*.csv.gz.b64')) + glob.glob(os.path.join(HERE, 'absencje.csv.gz.b64'))):
        t = open(f, encoding='utf-8', errors='replace').read().strip()
        try:
            if t.startswith('{'): t = json.loads(t)['content']
            raw = base64.b64decode(''.join(t.split())); gzip.decompress(raw)
        except Exception as e:
            print(f'  BLAD: {os.path.basename(f)} nie jest poprawnym base64 pliku gzip ({e}) — pobierz ponownie')
            continue
        open(f[:-4], 'wb').write(raw); os.remove(f)
    for f in sorted(glob.glob(os.path.join(HERE, 'statystyki_*.csv.gz')) + glob.glob(os.path.join(HERE, 'absencje.csv.gz'))):
        cel = f[:-3]
        try:
            raw = gzip.decompress(open(f, 'rb').read())
        except Exception as e:
            print(f'  BLAD: {os.path.basename(f)} nie jest poprawnym gzip ({e}) — pobierz ponownie'); continue
        tmp = cel + '.nowy'; open(tmp, 'wb').write(raw)
        stary, nowy = (_aktualizacja(cel) if os.path.exists(cel) else None), _aktualizacja(tmp)
        if stary and (nowy is None or stary > nowy):
            print(f'  {os.path.basename(f)}: starszy niz {os.path.basename(cel)} ({nowy:%Y-%m-%d %H:%M} < {stary:%Y-%m-%d %H:%M}) — zostaje CSV'
                  if nowy else f'  {os.path.basename(f)}: bez czytelnej data_aktualizacji — zostaje {os.path.basename(cel)}')
            os.remove(tmp)
        else:
            os.replace(tmp, cel); n = raw.count(b'\n')
            print(f'  rozpakowano {os.path.basename(f)} -> {os.path.basename(cel)} ({n} wierszy)')
        os.remove(f)


def rozpakuj_dzienniki(zrodlo=HERE, cel=None):
    """30.09.2026 (Raport 18:00, usterka 1): 62 pliki dziennikow (typy_log, sporty_typy, ako_log) pobierane z Dysku
    po jednym zajely 88 min z budzetu przebiegu — przy 436 KB danych. Apps Script dzienniki.gs pakuje je co 30 min
    w JEDEN plik dzienniki.zip (z manifestem: nazwa pliku, czas utworzenia na Dysku). Zapisz go do kb/ jako
    dzienniki.zip (jq -r .content | base64 -d) albo tekst base64 jako dzienniki.zip.b64. Ten krok sprawdza zip,
    rozpakowuje do kb/dzienniki/ i ustawia czas pliku = czas utworzenia na Dysku (dzienniki.scal: pozniejszy wygrywa).
    Zwraca liczbe rozpakowanych plikow albo None, gdy zipa nie ma."""
    import base64, json, zipfile, io, csv
    cel = cel or os.path.join(zrodlo, 'dzienniki')
    b64, zp = os.path.join(zrodlo, 'dzienniki.zip.b64'), os.path.join(zrodlo, 'dzienniki.zip')
    if os.path.exists(b64):
        t = open(b64, encoding='utf-8', errors='replace').read().strip()
        try:
            if t.startswith('{'): t = json.loads(t)['content']
            raw = base64.b64decode(''.join(t.split()))
            zipfile.ZipFile(io.BytesIO(raw)).testzip()
        except Exception as e:
            print(f'  BLAD: dzienniki.zip.b64 nie jest poprawnym base64 pliku zip ({e}) — pobierz ponownie')
            return None
        open(zp, 'wb').write(raw); os.remove(b64)
    if not os.path.exists(zp): return None
    try:
        z = zipfile.ZipFile(zp)
        zly = z.testzip()
        if zly: raise ValueError(f'uszkodzony wpis {zly}')
    except Exception as e:
        print(f'  BLAD: dzienniki.zip nie jest poprawnym plikiem zip ({e}) — pobierz ponownie'); return None
    nazwy = [n for n in z.namelist() if not n.endswith('/')]
    if 'dzienniki_manifest.csv' not in nazwy:
        print('  BLAD: dzienniki.zip bez dzienniki_manifest.csv — nie wiadomo, ktory plik jest pozniejszy; pobierz ponownie')
        return None
    man = {r['plik']: r['utworzony'] for r in csv.DictReader(io.StringIO(z.read('dzienniki_manifest.csv').decode('utf-8')))}
    brak = [n for n in man if n not in nazwy]
    if brak:
        print(f'  BLAD: dzienniki.zip niepelny — w manifescie, a nie w zipie: {brak[:3]} — pobierz ponownie'); return None
    os.makedirs(cel, exist_ok=True)
    n = 0
    for nazwa, kiedy in man.items():
        base = os.path.basename(nazwa)
        if not base or base.startswith('.'): continue
        f = os.path.join(cel, base)
        open(f, 'wb').write(z.read(nazwa))
        t = pd.Timestamp(kiedy)
        t = (t.tz_localize('UTC') if t.tzinfo is None else t).timestamp()
        os.utime(f, (t, t)); n += 1
    print(f'  rozpakowano dzienniki.zip -> {os.path.relpath(cel, zrodlo)}/ ({n} plikow dziennikow)')
    return n


def kontrola_arkuszy():
    """Poprawka 53 (24.09, przebieg 21:00): arkusze statystyk to DRUGIE ZRODLO dla pilki klubowej (sezon.py),
    tenisa, koszykowki i siatkowki. Przebieg 21:00 ich nie pobral i sezon.py konczyl sie „BRAK PLIKU”.
    Brak arkusza = BLAD (bez niego te sporty nie maja drugiego zrodla). Arkusz starszy niz 24 h = ostrzezenie."""
    rozpakuj_arkusze()
    bledy = []
    for a in ARKUSZE:
        f = os.path.join(HERE, a + '.csv')
        if not os.path.exists(f):
            bledy.append(f'brak {a}.csv — pobierz z Dysku plik {a}.csv.gz do kb/ (Apps Script arkusze.gs); gdy go nie ma — '
                         f'arkusz Google „{a}” (download_file_content, exportMimeType text/csv) jako kb/{a}.csv')
            continue
        try:
            t = _aktualizacja(f)
            if t is None: raise ValueError('brak czytelnej data_aktualizacji')
            h = (teraz_pl() - t).total_seconds() / 3600
            print(f'  {a}.csv: aktualizacja {t:%Y-%m-%d %H:%M} ({h:.0f} h)'
                  + ('' if h <= MAKS_WIEK_ARKUSZA_H else '  UWAGA: starszy niz 24 h — sezon.py tego sportu tylko informacyjnie')
                  + ('  UWAGA: data z PRZYSZLOSCI — sprawdz strefe czasowa arkusza (oczekiwany czas polski)'
                     if h < -0.5 else ''))
        except Exception as e:
            bledy.append(f'{a}.csv nieczytelny ({e}) — pobierz ponownie jako CSV')
    # 29.09.2026 (Raport 12:00, usterka 5): hokej / reczna / baseball / futbol amerykanski / rugby Apps Script odswieza
    # RAZ NA DOBE wieczorem — w poludnie maja 14-20 h i sa aktualne. Przebieg uznal je za „niezapisane” i pominal.
    # Opcjonalne: brak nie blokuje przebiegu, ale jest wypisany z nazwa pliku na Dysku.
    for a in ARKUSZE_OPCJ:
        f = os.path.join(HERE, a + '.csv')
        if not os.path.exists(f):
            n = mecze_w_terminarzu(ARKUSZ_SPORT.get(a))
            if n:
                # 29.09.2026 (Raport 15:00, usterka 7): hokej i reczna byly w ofercie, arkuszy nie pobrano
                print(f'  {a}.csv: BRAK, a ten sport JEST DZIS W TERMINARZU ({n} meczow) — POBIERZ arkusz „{a}” '
                      f'z Dysku jako CSV do kb/ przed typowaniem (Poprawka 63.2)')
                DO_POBRANIA.append(a)
            elif n is None:
                # 29.09.2026 (Raport 18:00, usterka 6): bez terminarza „brak meczow” bylo nieodroznialne od „nie wiem” —
                # MLB bylo w ofercie, a arkusza baseball nie pobrano. Nie wiemy = pobierz.
                print(f'  {a}.csv: BRAK, a terminarza nie ma (nie da sie sprawdzic, czy sport jest dzis) — POBIERZ '
                      f'arkusz „{a}” z Dysku jako CSV do kb/, jesli ten sport jest w ofercie (Poprawka 63.2)')
                DO_POBRANIA.append(a)
            else:
                print(f'  {a}.csv: brak — arkusz „{a}” jest na Dysku (baza-wiedzy, odswiezany raz na dobe); '
                      f'pobierz jako CSV, gdy ten sport jest w ofercie')
            continue
        try:
            t = _aktualizacja(f)
            if t is None: raise ValueError('brak czytelnej data_aktualizacji')
            h = (teraz_pl() - t).total_seconds() / 3600
            print(f'  {a}.csv: aktualizacja {t:%Y-%m-%d %H:%M} ({h:.0f} h)' + ('' if h <= MAKS_WIEK_ARKUSZA_OPCJ_H else
                  f'  UWAGA: starszy niz {MAKS_WIEK_ARKUSZA_OPCJ_H} h — sezon.py tego sportu tylko informacyjnie'))
        except Exception as e:
            print(f'  UWAGA: {a}.csv nieczytelny ({e}) — pobierz ponownie jako CSV')
    return bledy


def kontrola_zewn():
    dekoduj_inline()
    bledy = []
    mies = DZIS.strftime('%Y-%m')
    if DZIS.day == 1:        # pierwszego dnia miesiaca plik nowego miesiaca moze jeszcze nie miec wczoraj
        mies = (DZIS - dt.timedelta(days=1)).strftime('%Y-%m')
    for rodzaj in ('365_pilka', '365_inne', 'fs_inne', 'fs_pilka'):   # fs_pilka: czyta go zewn.py (Poprawka 46b)
        f = os.path.join(ZD, f'wyniki_{rodzaj}_{mies}.csv.gz')
        if not os.path.exists(f):
            bledy.append(f'brak zewn/wyniki_{rodzaj}_{mies}.csv.gz — pobierz z Dysku (folder baza-wiedzy)')
            continue
        try:
            d = dt.date.fromisoformat(pd.read_csv(f, usecols=['data'], low_memory=False).data.astype(str).str[:10].max())
        except Exception as e:
            bledy.append(f'zewn/{os.path.basename(f)} nieczytelny ({e}) — pobierz ponownie z Dysku')
            continue
        wiek = (DZIS - d).days
        print(f'  zewn/{os.path.basename(f)}: ostatni mecz {d} ({wiek} d)')
        if wiek > MAKS_WIEK_DNI:
            bledy.append(f'zewn/{os.path.basename(f)} konczy sie {d} ({wiek} dni temu) — to stara kopia '
                         f'(np. z repo); pobierz aktualny plik z Dysku i nadpisz')
    f = os.path.join(ZD, f'wyniki_lol_inne_{mies}.csv.gz')
    if os.path.exists(f):
        try:
            d = pd.read_csv(f, usecols=['data'], low_memory=False).data.astype(str).str[:10].max()
            print(f'  zewn/{os.path.basename(f)}: ostatni mecz {d}' + ('' if (DZIS - dt.date.fromisoformat(d)).days <= 7
                  else '  (UWAGA: stary — przy e-sporcie w ofercie pobierz z Dysku; nie blokuje przebiegu)'))
        except Exception as e:
            print(f'  UWAGA: zewn/{os.path.basename(f)} nieczytelny ({e}) — e-sport bez swiezych danych')
    # 29.09.2026 (faza 3b): terminarz 365scores (Apps Script, co godzine) — opcjonalny; bez niego typuj.py
    # po prostu nie robi kontroli kraju meczu z terminarza. Tylko informacja, nie blad.
    # 29.09.2026: Liga Pro (tenis stolowy) ze scores24 — opcjonalna; brak pliku = tenis stolowy Ligi Pro bez danych
    f = os.path.join(ZD, f'wyniki_lp_inne_{DZIS.strftime("%Y-%m")}.csv.gz')
    if os.path.exists(f):
        try:
            t = pd.read_csv(f, usecols=['data'], dtype=str)
            print(f'  zewn/{os.path.basename(f)}: {len(t)} meczow Ligi Pro, ostatni {t.data.max()}')
        except Exception as e:
            print(f'  UWAGA: zewn/{os.path.basename(f)} nieczytelny ({e}) — tenis stolowy Ligi Pro bez danych')
    else:
        print(f'  zewn/{os.path.basename(f)}: brak (opcjonalny — Liga Pro, Apps Script „ligapro”)')
    # 29.09.2026: koszykowka / reczna / siatkowka z Flashscore (Apps Script wynikiFsDruzynowe) — opcjonalne
    f = os.path.join(ZD, f'wyniki_fsx_inne_{DZIS.strftime("%Y-%m")}.csv.gz')
    if os.path.exists(f):
        try:
            t = pd.read_csv(f, usecols=['data', 'sport'], dtype=str)
            print(f'  zewn/{os.path.basename(f)}: {len(t)} meczow (' + ', '.join(f'{k} {v}' for k, v in t.sport.value_counts().items())
                  + f'), ostatni {t.data.max()}')
        except Exception as e:
            print(f'  UWAGA: zewn/{os.path.basename(f)} nieczytelny ({e}) — koszykowka/reczna/siatkowka tylko z 365')
    else:
        print(f'  zewn/{os.path.basename(f)}: brak (opcjonalny — Flashscore koszykowka/reczna/siatkowka, Apps Script „wynikiFsDruzynowe”)')
    # od 29.09 takze terminarz_fs.csv.gz (Flashscore) — wiecej sportow i nizszych lig niz 365scores
    for nazwa in ('terminarz_fs.csv.gz', 'terminarz_365.csv.gz'):
        f = os.path.join(ZD, nazwa)
        if os.path.exists(f):
            try:
                t = pd.read_csv(f, usecols=['data', 'sport'], dtype=str)
                print(f'  zewn/{nazwa}: mecze do {t.data.max()} (pilka {int((t.sport == "football").sum())}, razem {len(t)})')
            except Exception as e:
                print(f'  UWAGA: zewn/{nazwa} nieczytelny ({e}) — kontrola terminarza w typuj.py bez tego pliku')
        else:
            print(f'  zewn/{nazwa}: brak (opcjonalny — pobierz z Dysku, jesli Apps Script go zapisuje)')
    # archiwa sezonu 2025/26 sa w repo (Poprawka 74); „inne” niesie cala historie hokeja/koszykowki/siatkowki —
    # bez niego sporty.py liczy Elo z samych biezacych miesiecy i nikt tego nie widzi
    for rodzaj, skutek in (('pilka', 'baza pilkarska ma ~60 tys. meczow mniej'),
                           ('inne', 'Elo innych sportow tylko z biezacych miesiecy')):
        arch = glob.glob(os.path.join(ZD, f'wyniki_365_{rodzaj}_archiwum_*.csv.gz'))
        if not arch:
            bledy.append(f'brak zewn/wyniki_365_{rodzaj}_archiwum_*.csv.gz (sezon 2025/26, powinien byc w repo) — '
                         f'pobierz z Dysku; bez niego {skutek}')
        else:
            print(f'  archiwum: {", ".join(os.path.basename(a) for a in sorted(arch))}')
    return bledy


def uruchom(skrypt, tag):
    log = os.path.join(HERE, f'przebieg_{tag}.txt')
    t0 = dt.datetime.now()
    with open(log, 'w') as fh:
        r = subprocess.run([sys.executable, skrypt], cwd=HERE, stdout=fh, stderr=subprocess.STDOUT)
    sek = (dt.datetime.now() - t0).seconds
    ogon = open(log, encoding='utf-8', errors='replace').read().splitlines()[-3:]
    print(f'  {skrypt:<18} kod {r.returncode}  {sek:4d} s  log {os.path.basename(log)}')
    for l in ogon: print(f'      {l[:160]}')
    tb = 'Traceback (most recent call last)' in open(log, encoding='utf-8', errors='replace').read()
    return r.returncode, tb


def kontrola_bazy():
    bledy = []
    c = sqlite3.connect(os.path.join(HERE, 'kb.sqlite'))
    n, d = c.execute('select count(*), max(MatchDate) from matches').fetchone()
    c.close()
    print(f'  baza: {n} meczow, ostatni {d}')
    if n < MIN_MECZOW:
        bledy.append(f'w bazie {n} meczow, oczekiwane >= {MIN_MECZOW} — archiwum lub uzupelnij_ligi nie weszly')
    if (DZIS - dt.date.fromisoformat(str(d)[:10])).days > 2:
        bledy.append(f'ostatni mecz klubowy w bazie {d} — dane klubowe nieaktualne')
    th = os.path.join(HERE, 'tenis_hist.csv')
    if os.path.exists(th):
        t = pd.read_csv(th, usecols=['date'], low_memory=False).date.astype(str).max()[:10]
        print(f'  tenis_hist: ostatni mecz {t}')
        if (DZIS - dt.date.fromisoformat(t)).days > 2:
            bledy.append(f'tenis_hist konczy sie {t} — tenis nieaktualny')
    else:
        bledy.append('brak tenis_hist.csv — hist_import nie zadzialal')
    return bledy


MAKS_WIEK_KALIBRACJI_DNI = 7


def kontrola_kalibracji():
    """29.09.2026: pliki kalibracji (ensemble_wagi.json, korekta_rynkow_v5n.csv) mialy jeden commit z 21.09
    i byly dopasowane na bazie sprzed naprawy 19 392 dat (Poprawka 47). Nic tego nie zglaszalo.
    Znacznik daty to pole "data" w ensemble_wagi.json (zapisuje je ensemble.py). Tylko ostrzezenie."""
    import json
    try:
        d = dt.date.fromisoformat(json.load(open(os.path.join(HERE, 'ensemble_wagi.json')))['data'])
    except Exception as e:
        print(f'  UWAGA: nie da sie odczytac daty kalibracji z ensemble_wagi.json ({e})')
        return
    wiek = (DZIS - d).days
    print(f'  kalibracja (ensemble_wagi.json): {d} ({wiek} d)'
          + ('' if wiek <= MAKS_WIEK_KALIBRACJI_DNI else
             f'  UWAGA: starsza niz {MAKS_WIEK_KALIBRACJI_DNI} dni — przelicz w bloku poniedzialkowym: '
             f'python3 ensemble.py && python3 korekta_rynkow.py (wpisz do USTERKI)'))


def archiwum_arkuszy():
    """29.09.2026 (faza 4): arkusze statystyki_*.csv sa nadpisywane co godzine, wiec nie ma ich historii — a bez
    niej nie da sie sprawdzic backtestem regul z sezon.py i tenisa (docs/BACKTEST_P48.md). Pakuje biezace arkusze
    do arkusze_RRRR-MM-DD.tar.gz; pierwszy przebieg dnia zapisuje ten plik na Dysku (Poprawka 57.7)."""
    import tarfile
    pliki = sorted(glob.glob(os.path.join(HERE, 'statystyki_*.csv')))
    if not pliki:
        print('BRAK arkuszy statystyki_*.csv — nic do spakowania'); return 1
    cel = os.path.join(HERE, f'arkusze_{DZIS}.tar.gz')
    with tarfile.open(cel, 'w:gz') as t:
        for f in pliki: t.add(f, arcname=os.path.basename(f))
    print(f'spakowano {len(pliki)} arkuszy -> {os.path.basename(cel)} ({os.path.getsize(cel) // 1024} KB)')
    return 0


def main():
    if '--archiwum-arkuszy' in sys.argv:
        return archiwum_arkuszy()
    if '--dzienniki' in sys.argv:
        n = rozpakuj_dzienniki()
        if not n:
            print('BRAK dzienniki.zip w kb/ (albo zip bledny) — pobierz z Dysku plik dzienniki.zip (Apps Script dzienniki.gs)')
            return 2
        import dzienniki
        dzienniki.scal(os.path.join(HERE, 'dzienniki'))
        return 0
    print(f'PRZEBIEG {teraz_pl():%Y-%m-%d %H:%M} (czas polski)\n1) Pliki zewn/:')
    bledy = kontrola_zewn()
    print('   Arkusze statystyk (drugie zrodlo):')
    bledy += kontrola_arkuszy()
    if bledy:
        for b in bledy: print('  BLAD: ' + b)
        print(f'\nPRZEBIEG BLAD: {bledy[0]} — ZADNEGO kuponu za pieniadze')
        return 2
    if '--kontrola' in sys.argv:
        print('\nKONTROLA PLIKOW I ARKUSZY OK — uruchom: python3 przebieg.py')
        return 0
    print('2) Budowa (5 krokow, razem ok. 4–6 min):')
    for skrypt, tag in KROKI:
        kod, tb = uruchom(skrypt, tag)
        # swiezosc: 1 = ostrzezenia (to nie awaria), 2 = BRAK DANYCH (brak bazy albo plikow) — blad (30.09.2026)
        if tb or (kod != 0 and (skrypt != 'swiezosc.py' or kod == 2)):
            print(f'\nPRZEBIEG BLAD: {skrypt} zakonczyl sie bledem (log przebieg_{tag}.txt) — ZADNEGO kuponu za pieniadze')
            return 3
    print('3) Kontrola bazy:')
    bledy = kontrola_bazy()
    if bledy:
        for b in bledy: print('  BLAD: ' + b)
        print(f'\nPRZEBIEG BLAD: {bledy[0]} — ZADNEGO kuponu za pieniadze')
        return 4
    kontrola_kalibracji()
    print('\nPRZEBIEG OK — mozna typowac (ostrzezenia swiezosc.py: patrz przebieg_sw.txt, wklej do raportu)')
    if DO_POBRANIA:
        print('DO POBRANIA PRZED TYPOWANIEM (sport dzis w terminarzu, brak arkusza): ' + ', '.join(DO_POBRANIA))
    return 0


if __name__ == '__main__':
    sys.exit(main())
