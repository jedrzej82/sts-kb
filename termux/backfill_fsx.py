#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""backfill_fsx.py — historia koszykowki, pilki recznej i siatkowki z Flashscore (Termux, telefon).

PO CO TO JEST
-------------
Pomiar z 2026-10-03 (oferta w oknie 19:00-22:00, 70 zdarzen innych sportow):
  - model mogl policzyc        32 (46%)
  - brak danych (< 5 meczow)   24 (34%)
  - nazwa nierozpoznana        14 (20%)
Pilka reczna najgorzej: 8 policzalnych z 30. W bazie jest 964 druzyn recznej,
ale tylko 109 (11%) ma >= 10 meczow; 780 (81%) ma od 1 do 4.

Przyczyna NIE jest bledem pobierania — w plikach zewn/ za wrzesien i pazdziernik
jest ok. 853 meczow recznej, a w bazie 792. Nic istotnego nie ginie. Przyczyna jest
w datach: kanal Flashscore dla sportow druzynowych (apps_script/terminarz.gs,
wynikiFsDruzynowe) ruszyl 2026-09-22 i pobiera tylko dzien -1 i -2. Historii po prostu
jeszcze nie ma. Elo nie zdazy odejsc od startowych 1500, model zbiega do ~50%,
a rynek przebija go o 20-36 pp — stad "brak zgodnego drugiego zrodla".

Bez nadrobienia reczna wyleczy sie sama dopiero w okolicach 15.11 (druzyna gra 1-2 mecze
tygodniowo, do 10 meczow trzeba 6-8 tygodni) — czyli dokladnie wtedy, gdy konczy sie
okres pomiaru przewagi modelu.

Ten skrypt siega po TEN SAM kanal co terminarz.gs, tylko dowolnie daleko wstecz,
i produkuje pliki wyniki_fsx_inne_RRRR-MM.csv.gz w formacie bajt-w-bajt zgodnym
z tym, co zapisuje Apps Script. NIE modyfikuje zadnego .gs.

CZEGO NIE WIEM
--------------
Nie sprawdzilem, jak daleko wstecz Flashscore oddaje dane — nie uruchamialem tego
kanalu. Dlatego PIERWSZE, co masz zrobic, to sonda (--sonda): skrypt sam ustali
granice empirycznie i wypisze ja. Dopiero potem ma sens backfill.

UZYCIE
------
  python backfill_fsx.py --sonda
      Sprawdza dni -1, -3, -7, -14, -30, -60, -90, -180, -270, -365 i mowi,
      dla ktorych kanal jeszcze oddaje mecze. Nic nie zapisuje.

  python backfill_fsx.py --od -3 --do -120
      Pobiera dni od -3 do -120 wstecz i zapisuje pliki miesieczne.

  python backfill_fsx.py --od 2025-08-01 --do 2026-09-21
      To samo, ale zakresem dat.

  Opcje: --katalog /sdcard/Download   (domyslnie)
         --sporty handball,basketball,volleyball
         --przerwa 1.5                (sekundy miedzy dniami; nie schodz ponizej 1.0)
         --sucho                      (nic nie zapisuje, tylko liczy)

PO POBRANIU
-----------
Wgrywaj TYLKO plik scalony z aktualna kopia z Dysku. Skrypt scala sie wylacznie z plikiem,
ktory lezy w --katalog; najpierw pobierz tam aktualne wyniki_fsx_inne_RRRR-MM.csv.gz z baza-wiedzy.
Bez tego wynik zawiera same nadrobione dni i dostaje nazwe *_TYLKO_NADROBIONE.csv.gz — NIE wgrywaj go:
paczka.gs przy dwoch plikach o tej samej nazwie bierze najnowszy i przebieg straci reszte miesiaca.
"""

import csv
import gzip
import io
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

HOSTY = ['https://global.flashscore.ninja/2/x/feed/', 'https://d.flashscore.com/x/feed/']
SPORTY = {'3': 'basketball', '7': 'handball', '12': 'volleyball'}
NAGLOWEK = ['data', 'sport', 'kraj', 'turniej', 'runda', 'gosp', 'gosc',
            'wg', 'wa', 'okresy_g', 'okresy_a', 'zwyciezca', 'nawierzchnia']
NAGLOWKI_HTTP = {
    'x-fsign': 'SW9D1eZo',
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/128.0 Safari/537.36'),
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.flashscore.com/',
}
OKRESY = [('BA', 'BB'), ('BC', 'BD'), ('BE', 'BF'), ('BG', 'BH'), ('BI', 'BJ')]


def pobierz(sport_id, dzien, prob=3):
    """Surowy tekst kanalu dla jednego sportu i jednego dnia wzglednego. '' gdy sie nie udalo."""
    sciezka = 'f_%s_%d_0_en_1' % (sport_id, dzien)
    for host in HOSTY:
        for p in range(prob):
            try:
                req = urllib.request.Request(host + sciezka, headers=NAGLOWKI_HTTP)
                with urllib.request.urlopen(req, timeout=30) as r:
                    if r.status != 200:
                        continue
                    t = r.read().decode('utf-8', 'replace')
                    if 'AA÷' in t:
                        return t
                    return ''          # 200, ale bez meczow — dzien pusty, nie blad hosta
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
                time.sleep(1.5 * (p + 1))
    return ''


def parsuj(tekst, sport):
    """Rekordy kanalu -> wiersze CSV. Logika 1:1 z terminarz.gs (wynikiFsDruzynowe)."""
    wiersze, kraj, turniej = [], '', ''
    for rek in tekst.split('~'):
        f = {}
        for p in rek.split('¬'):
            k = p.find('÷')
            if k > 0:
                f[p[:k]] = p[k + 1:]
        if 'ZA' in f:
            c = f['ZA'].find(': ')
            kraj = f['ZA'][:c] if c > 0 else f.get('ZY', '')
            turniej = f['ZA'][c + 2:] if c > 0 else f['ZA']
        elif 'AA' in f and f.get('AB') == '3' and 'AG' in f and 'AH' in f and f.get('AD'):
            try:
                t = datetime.fromtimestamp(int(f['AD']), tz=timezone.utc)
                g, a = int(f['AG']), int(f['AH'])
            except (TypeError, ValueError):
                continue
            og, oa = [], []
            for x, y in OKRESY:
                if x in f and y in f:
                    og.append(f[x]); oa.append(f[y])
            wiersze.append([t.strftime('%Y-%m-%d'), sport, kraj, turniej, f.get('ER', ''),
                            f.get('AE') or f.get('FH') or '', f.get('AF') or f.get('FK') or '',
                            f['AG'], f['AH'], ';'.join(og), ';'.join(oa),
                            1 if g > a else 2 if a > g else 0, ''])
    return wiersze


def klucz7(w):
    """Klucz scalania identyczny jak _klucz7_ w terminarz.gs: pierwsze 7 POL (data..gosc)."""
    return '\u0001'.join(str(x) for x in w[:7])


def wczytaj_istniejace(sciezka):
    """Wiersze z juz istniejacego pliku miesiecznego (zeby niczego nie zgubic)."""
    if not os.path.exists(sciezka):
        return {}
    out = {}
    try:
        with gzip.open(sciezka, 'rt', encoding='utf-8', newline='') as fh:
            r = csv.reader(fh)
            naglowek = next(r, None)
            if naglowek != NAGLOWEK:
                print('  UWAGA: %s ma inny naglowek — plik zostaje nietkniety, pomijam' % sciezka)
                return None
            for w in r:
                if w:
                    out[klucz7(w)] = w
    except (OSError, EOFError, csv.Error) as e:
        print('  UWAGA: nie moge odczytac %s (%s) — plik zostaje nietkniety, pomijam' % (sciezka, e))
        return None
    return out


def zapisz_miesiac(katalog, miesiac, wiersze, sucho):
    """Zwraca (nowych, razem, nazwa_pliku). nowych = UNIKALNE mecze, ktorych nie bylo w pliku.

    03.10.2026 (pierwsze prawdziwe uruchomienie): gdy w katalogu NIE bylo pliku miesiecznego z Dysku, wynik zawiera
    wylacznie nadrobione dni. paczka.gs przy dwoch plikach o tej samej nazwie bierze NAJNOWSZY — wgranie takiego pliku
    zastapiloby w przebiegu pelny miesiac (ok. 1600 meczow wrzesnia, 300 pazdziernika) kilkoma dniami. Dlatego bez
    pliku bazowego zapisujemy pod nazwa, ktorej paczka.gs nie podejmie (_TYLKO_NADROBIONE)."""
    sciezka = os.path.join(katalog, 'wyniki_fsx_inne_%s.csv.gz' % miesiac)
    bazowy = os.path.exists(sciezka)
    stare = wczytaj_istniejace(sciezka)
    if stare is None:
        return 0, 0, None
    nowe = {klucz7(w): w for w in wiersze}            # ten sam mecz bywa w dwoch dziennych odczytach
    nowych = sum(1 for k in nowe if k not in stare)
    scalone = dict(stare)
    scalone.update(nowe)
    if not bazowy:
        sciezka = os.path.join(katalog, 'wyniki_fsx_inne_%s_TYLKO_NADROBIONE.csv.gz' % miesiac)
    if sucho:
        return nowych, len(scalone), os.path.basename(sciezka)
    buf = io.StringIO()
    wr = csv.writer(buf, lineterminator='\n')
    wr.writerow(NAGLOWEK)
    for k in sorted(scalone):
        wr.writerow(scalone[k])
    tmp = sciezka + '.tmp'
    with gzip.open(tmp, 'wt', encoding='utf-8', newline='') as fh:
        fh.write(buf.getvalue())
    os.replace(tmp, sciezka)           # podmiana dopiero po udanym zapisie
    return nowych, len(scalone), os.path.basename(sciezka)


def sonda(sporty, przerwa):
    print('SONDA — jak daleko wstecz Flashscore oddaje wyniki?')
    print('(sprawdzam tylko pilke reczna, bo o nia chodzi; kanal jest wspolny dla trzech sportow)\n')
    sid = '7' if 'handball' in sporty.values() else list(sporty)[0]
    granica = None
    for dzien in (-1, -3, -7, -14, -30, -60, -90, -180, -270, -365):
        t = pobierz(sid, dzien)
        n = len(parsuj(t, SPORTY[sid])) if t else 0
        d = (date.today() + timedelta(days=dzien)).isoformat()
        print('  dzien %5d (%s): %s' % (dzien, d, ('%d meczow' % n) if n else 'BRAK'))
        if n:
            granica = dzien
        time.sleep(przerwa)
    print()
    if granica is None:
        print('WNIOSEK: kanal nie oddal nic nawet dla dnia -1 — sprawdz polaczenie albo czy x-fsign')
        print('         nie wymaga odswiezenia (ta sama wartosc dziala w terminarz.gs).')
    elif granica <= -180:
        print('WNIOSEK: kanal siega co najmniej %d dni wstecz — backfill calego sezonu ma sens:' % -granica)
        print('         python backfill_fsx.py --od -3 --do %d' % granica)
    else:
        print('WNIOSEK: kanal siega najwyzej ok. %d dni wstecz.' % -granica)
        print('         Tyle da sie nadrobic: python backfill_fsx.py --od -3 --do %d' % granica)
        print('         Glebsza historia wymaga innego zrodla — to jest realny wynik, nie awaria.')
    return 0


def main(argv):
    a = argv[1:]
    def opt(n, d=None):
        return a[a.index(n) + 1] if n in a else d
    katalog = opt('--katalog', '/sdcard/Download')
    przerwa = float(opt('--przerwa', '1.5'))
    sucho = '--sucho' in a
    wyb = opt('--sporty')
    sporty = {k: v for k, v in SPORTY.items() if not wyb or v in wyb.split(',')}
    if not sporty:
        print('Nie znam zadnego z podanych sportow. Dostepne: %s' % ', '.join(SPORTY.values()))
        return 2

    if '--sonda' in a:
        return sonda(sporty, przerwa)

    od, do = opt('--od'), opt('--do')
    if od is None or do is None:
        print(__doc__)
        return 2

    def na_offset(x):
        x = str(x).strip()
        if x.lstrip('-').isdigit():
            return int(x)
        return (date.fromisoformat(x) - date.today()).days

    o1, o2 = na_offset(od), na_offset(do)
    dni = list(range(max(o1, o2), min(o1, o2) - 1, -1))
    if any(d > 0 for d in dni):
        print('Backfill dotyczy przeszlosci — dni dodatnie pomijam.')
        dni = [d for d in dni if d <= 0]
    if not os.path.isdir(katalog):
        print('Brak katalogu %s — podaj --katalog' % katalog)
        return 2

    print('Backfill: %d dni (%s -> %s), sporty: %s' % (
        len(dni), (date.today() + timedelta(days=dni[0])).isoformat(),
        (date.today() + timedelta(days=dni[-1])).isoformat(), ', '.join(sporty.values())))
    print('Katalog: %s%s\n' % (katalog, '  (SUCHO — nic nie zapisze)' if sucho else ''))

    wg_miesiaca, puste, bledy = {}, 0, 0
    for i, dzien in enumerate(dni, 1):
        razem = 0
        for sid, sport in sporty.items():
            t = pobierz(sid, dzien)
            if not t:
                bledy += 1
                continue
            for w in parsuj(t, sport):
                wg_miesiaca.setdefault(w[0][:7], []).append(w)
                razem += 1
            time.sleep(przerwa)
        if not razem:
            puste += 1
        if i % 10 == 0 or i == len(dni):
            print('  %d/%d dni, zebrano %d meczow, pustych dni %d' % (
                i, len(dni), sum(len(v) for v in wg_miesiaca.values()), puste))
        if puste >= 20 and puste == i:
            print('\n20 pierwszych dni bez danych — kanal prawdopodobnie nie siega tak daleko.')
            print('Uruchom najpierw: python backfill_fsx.py --sonda')
            return 1

    print()
    if not wg_miesiaca:
        print('Nic nie zebrano. Uruchom: python backfill_fsx.py --sonda')
        return 1
    suma_nowych, tylko_nadrobione = 0, []
    for m in sorted(wg_miesiaca):
        nowych, razem, nazwa = zapisz_miesiac(katalog, m, wg_miesiaca[m], sucho)
        if nazwa is None:
            continue
        suma_nowych += nowych
        if nazwa.endswith('_TYLKO_NADROBIONE.csv.gz'):
            tylko_nadrobione.append(nazwa)
        print('  %s: +%d nowych, razem %d meczow' % (nazwa, nowych, razem))
    print('\nNowych meczow: %d (bledow pobrania: %d)' % (suma_nowych, bledy))
    if sucho:
        return 0
    if tylko_nadrobione:
        print('\nUWAGA — NIE WGRYWAJ plikow *_TYLKO_NADROBIONE na Dysk.')
        print('W katalogu nie bylo aktualnego pliku z Dysku, wiec zawieraja WYLACZNIE nadrobione dni.')
        print('paczka.gs bierze najnowszy plik o danej nazwie — pelny miesiac zostalby zastapiony kilkoma dniami.')
        print('Zeby nadrobic bezpiecznie: pobierz z baza-wiedzy aktualne wyniki_fsx_inne_RRRR-MM.csv.gz do')
        print('%s i uruchom backfill jeszcze raz — wtedy skrypt scali sie z nimi i zapisze pod wlasciwa nazwa.' % katalog)
    else:
        print('\nPliki zostaly SCALONE z aktualnymi plikami z Dysku — mozna je wgrac do baza-wiedzy.')
        print('wynikiFsDruzynowe scali je ponownie przy nastepnym uruchomieniu (klucz: data..gosc).')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
