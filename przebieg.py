#!/usr/bin/env python3
"""Caly przebieg budowy bazy JEDNYM poleceniem, w jedynej poprawnej kolejnosci, z twarda kontrola danych.
  python3 przebieg.py            — kontrola plikow zewn/ → build_kb → uzupelnij_ligi → build_kb → hist_import → swiezosc
  python3 przebieg.py --kontrola — tylko kontrola plikow zewn/ (sekundy), bez budowy
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

HERE = os.path.dirname(os.path.abspath(__file__))
ZD = os.path.join(HERE, 'zewn')
DZIS = dt.date.today()
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
    arch = glob.glob(os.path.join(ZD, 'wyniki_365_pilka_archiwum_*.csv.gz'))
    if not arch:
        bledy.append('brak zewn/wyniki_365_pilka_archiwum_*.csv.gz (sezon 2025/26) — pobierz z Dysku; '
                     'bez niego baza ma ~60 tys. meczow mniej')
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


def main():
    print(f'PRZEBIEG {dt.datetime.now():%Y-%m-%d %H:%M}\n1) Pliki zewn/:')
    bledy = kontrola_zewn()
    if bledy:
        for b in bledy: print('  BLAD: ' + b)
        print(f'\nPRZEBIEG BLAD: {bledy[0]} — ZADNEGO kuponu za pieniadze')
        return 2
    if '--kontrola' in sys.argv:
        print('\nKONTROLA PLIKOW OK — uruchom: python3 przebieg.py')
        return 0
    print('2) Budowa (5 krokow, razem ok. 15–20 min):')
    for skrypt, tag in KROKI:
        kod, tb = uruchom(skrypt, tag)
        if tb or (kod != 0 and skrypt != 'swiezosc.py'):     # swiezosc zwraca 1 przy ostrzezeniach — to nie awaria
            print(f'\nPRZEBIEG BLAD: {skrypt} zakonczyl sie bledem (log przebieg_{tag}.txt) — ZADNEGO kuponu za pieniadze')
            return 3
    print('3) Kontrola bazy:')
    bledy = kontrola_bazy()
    if bledy:
        for b in bledy: print('  BLAD: ' + b)
        print(f'\nPRZEBIEG BLAD: {bledy[0]} — ZADNEGO kuponu za pieniadze')
        return 4
    print('\nPRZEBIEG OK — mozna typowac (ostrzezenia swiezosc.py: patrz przebieg_sw.txt, wklej do raportu)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
