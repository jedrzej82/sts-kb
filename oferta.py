#!/usr/bin/env python3
"""Kursy z PDF oferty STS W KODZIE (01.10.2026) — zamiast recznego odczytu PDF w kazdym przebiegu.

  python3 oferta.py PDF [PDF ...] [--wyjscie kursy_RRRR-MM-DD_GG-MM.csv.gz] [--pobrano "RRRR-MM-DD GG:MM"]
      Czyta oferte („oferta-dzisiaj-auto …pdf”, „oferta-jutro-auto …pdf”) i zapisuje JEDEN plik kursow (KROK 8.1 pkt 5)
      w stalym formacie: data_meczu, godzina_meczu, sport, liga, gospodarz, gosc, rynek, kurs, marza_1x2,
      godzina_pobrania + nr, sekcja, linia, wybor, zdarzenie. Wypisuje liczbe meczow i rynkow oraz ostrzezenia.
  python3 oferta.py PDF --mecz "Litwa" "Andora"
      Wszystkie kursy jednego meczu (do typuj.py --kurs ...) — bez przepisywania liczb z PDF recznie.
  python3 oferta.py zamkniecia PDF [PDF ...] [--ako kb/ako_log.csv] --wyjscie "ako_log zamkniecia RRRR-MM-DD GG-MM.csv"
      kurs_zamkniecia (P56.3) dla nog ako_log, ktorych mecz jeszcze sie nie zaczal w chwili wygenerowania PDF:
      plik: klucz nogi ako_log (data, godzina_uruchomienia, tag, nr_kuponu, noga_nr) + zdarzenie, rynek, kurs,
      kurs_zamkniecia — zapis do folderu baza-wiedzy; dzienniki.py scal bierze z plikow „… zamkniecia …” TYLKO
      kurs_zamkniecia (NAJPOZNIEJSZY niepusty, wiec ostatni PDF przed meczem wygrywa) i nie nadpisuje nimi nog.

PO CO: przebiegi 29-30.09 zapisywaly kursy kazdy w innym formacie (raz rynek 1/X/2, raz k1..k6, raz kilka kursow
w jednej komorce), plik 30.09 18:00 mial uszkodzona sume kontrolna gzip, a kurs_zamkniecia w ako_log zostal pusty.
Uklad PDF jest staly: dwie szpalty, w kazdej naglowki (dzien, sport, liga), tytul rynku z etykietami kolumn
(np. „Mecz 1 X 2 1X X2 12”, „Liczba goli - +”) i wiersze: numer, zdarzenie, kursy pod etykietami, godzina.
Kurs przypisywany jest do etykiety po POLOZENIU na stronie (nie po kolejnosci) — brakujacy kurs nie przesuwa reszty.

Kody rynkow jak w typuj.py / ako_log: Mecz -> 1, X, 2, 1X, X2, 12; Liczba goli (L) -> O{L} („+”), U{L} („-”);
Obie druzyny - strzela gola -> BTTS_tak / BTTS_nie; pozostale „sekcja|wybor”."""
import gzip
import os
import re
import sys

import pandas as pd

KOLUMNY = ['data_meczu', 'godzina_meczu', 'sport', 'liga', 'gospodarz', 'gosc', 'rynek', 'kurs', 'marza_1x2',
           'godzina_pobrania', 'nr', 'sekcja', 'linia', 'wybor', 'zdarzenie']
SZPALTA = 297.0          # granica szpalt (strona A4 595 pt; lewa konczy sie ok. 294, prawa zaczyna 300)
_KURS = re.compile(r'\d+\.\d{2}')
_DZIEN = re.compile(r'(\d{4}-\d{2}-\d{2})')


def _bialy(s):
    """PDF ma w nazwach waska twarda spacje (U+202F) i podwojne spacje („Leicester City  U21”) — jedna zwykla spacja."""
    return re.sub(r'\s+', ' ', str(s)).strip()


def _znaki(pdf):
    """Strony PDF -> listy znakow (x0, x1, y_od_gory, rozmiar, tekst)."""
    try:
        from pdfminer.high_level import extract_pages
    except BaseException as e:     # brak pdfminer albo zepsute cryptography/cffi (PanicException) w swiezym srodowisku
        if isinstance(e, KeyboardInterrupt): raise
        import subprocess
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'pdfminer.six', 'cffi'], check=False)
        from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTChar, LAParams

    def zbierz(o):
        if isinstance(o, LTChar): yield o
        elif hasattr(o, '__iter__'):
            for x in o: yield from zbierz(x)
    for p in extract_pages(pdf, laparams=LAParams()):
        yield [(c.x0, c.x1, p.height - c.y1, round(c.size, 1), c.get_text()) for c in zbierz(p)]


def _linie(znaki):
    """Znaki jednej szpalty -> linie (lista slow (x0, x1, rozmiar, tekst)), z gory na dol. Znaki rozniace sie
    wysokoscia o <= 3 pt to jedna linia (numer zdarzenia stoi 1 pt wyzej niz nazwa)."""
    linie, akt, y0 = [], [], None
    for z in sorted(znaki, key=lambda z: (z[2], z[0])):
        if y0 is None or z[2] - y0 > 3:
            if akt: linie.append(akt)
            akt, y0 = [], z[2]
        akt.append(z)
    if akt: linie.append(akt)
    wynik = []
    for l in linie:
        l.sort(key=lambda z: z[0])
        slowa, cur = [], [l[0]]
        for a, b in zip(l, l[1:]):
            if b[0] - a[1] > 2.0 or abs(b[3] - a[3]) > 0.6: slowa.append(cur); cur = [b]
            else: cur.append(b)
        slowa.append(cur)
        wynik.append([(s[0][0], s[-1][1], s[0][3], ''.join(z[4] for z in s), s) for s in slowa])
    return wynik


def _kursy_w_wierszu(slowa, x_lewy=0.0):
    """Slowa wiersza (bez numeru) -> (nazwa, [(kurs, x_srodek)], godzina) albo None. Slowa bywaja sklejone
    („22.0040.0021:00”), dlatego kursy i godzina sa wycinane z ciagu znakow z zachowaniem polozenia kazdego znaku."""
    znaki = []
    for s in slowa:
        if znaki: znaki.append((None, ' '))
        znaki += [(z[0], z[4]) for z in s[4]]
    tekst = ''.join(t for _, t in znaki)
    m = re.search(r'(\d{1,2}:\d{2})\s*$', tekst)
    if not m: return None
    tokeny = [(t.start(), t.end()) for t in re.finditer(r'\S+', tekst[:m.start()])]
    # od prawej: tokeny zlozone wylacznie z kursow („1.17”, „22.0040.00”); pierwszy inny token konczy nazwe
    # (nazwa moze konczyc sie „(163.5)”, „U21” — to nie sa kursy)
    def kurs(a, b):
        t = tekst[a:b]
        # pojedynczy kurs bywa z 1 miejscem po kropce („50.0”) albo bez kropki („250”, ale tylko w polu kursow,
        # >= 140 pt od krawedzi szpalty — nazwa tam nie siega); sklejone („22.0040.00”) zawsze maja po 2
        return (re.fullmatch(r'\d+\.\d{1,2}', t) or re.fullmatch(r'(?:\d+\.\d{2})+', t)
                or (re.fullmatch(r'[1-9]\d{0,3}', t) and znaki[a][0] - x_lewy >= 140))
    i = len(tokeny)
    while i > 0 and kurs(*tokeny[i - 1]):
        i -= 1
    kursy = []
    for a, b in tokeny[i:]:
        wzor = re.compile(r'\d+(?:\.\d{1,2})?') if re.fullmatch(r'\d+(?:\.\d{1,2})?', tekst[a:b]) else _KURS
        for k in wzor.finditer(tekst[a:b]):
            xs = [znaki[j][0] for j in range(a + k.start(), a + k.end())]
            kursy.append((float(k.group(0)), (min(xs) + max(xs)) / 2 + 1.5))
    nazwa = tekst[:tokeny[i][0]].strip() if i < len(tokeny) else tekst[:m.start()].strip()
    return nazwa, kursy, m.group(1)


def _rozdziel_etykiety(slowa):
    """Etykiety z dwoch czlonow stoja ciasno („- TAK+ TAK”): slowo dzielone przed „+”/„-”, ktory stoi tuz po literze."""
    wynik = []
    for x0, x1, rozm, tekst, zn in slowa:
        cur = [zn[0]]
        for a, b in zip(zn, zn[1:]):
            if b[4] in '+-' and a[4].isalpha():
                wynik.append((cur[0][0], cur[-1][1], rozm, ''.join(z[4] for z in cur), cur)); cur = [b]
            else:
                cur.append(b)
        wynik.append((cur[0][0], cur[-1][1], rozm, ''.join(z[4] for z in cur), cur))
    return wynik


def _rynek(sekcja, wybor, linia):
    s = sekcja.lower()
    if s == 'mecz' and wybor in ('1', 'X', '2', '1X', 'X2', '12'): return wybor
    if s == 'liczba goli' and linia and wybor in ('+', '-'): return ('O' if wybor == '+' else 'U') + linia
    if s == 'obie drużyny - strzelą gola' and wybor in ('TAK', 'NIE'): return 'BTTS_' + wybor.lower()
    return f'{sekcja}|{wybor}'


def bez_wstrzymanych(d, ostrz):
    """04.10.2026 (Raport 15:00 usterka 8): Unia Oswiecim – Podhale „1 = 1.00, X = 15, 2 = 150” i Ekoball Sanok 1X = 1.00
    przeszly bez slowa. Kurs 1.00 nic nie wyplaca (rynek wstrzymany) — taki kurs nie jest kursem do typowania."""
    zero = pd.to_numeric(d.kurs, errors='coerce') <= 1.0
    for zd_, g_ in d[zero].groupby('zdarzenie', sort=False):
        ostrz.append(f'{zd_}: kurs 1.00 ({", ".join(g_.rynek.astype(str))}) — rynek wstrzymany, kursy pominiete')
    return d[~zero].reset_index(drop=True)


def czytaj(pdf, pobrano=''):
    """PDF oferty -> (DataFrame w KOLUMNY, lista ostrzezen). pobrano = wymuszona chwila kursow (domyslnie stopka PDF)."""
    wiersze, ostrz = [], []
    dzien = sport = liga = ''
    sekcja, etykiety = '', []
    liga_ciag = False
    wygenerowano = podmecz = ''
    for nr_str, znaki in enumerate(_znaki(pdf), 1):
        for lewa in (True, False):
            szp = [z for z in znaki if (z[0] < SZPALTA) == lewa]
            if not szp: continue
            x_lewy = 26.0 if lewa else 300.0
            for slowa in _linie(szp):
                rozm = max(s[2] for s in slowa)
                tekst = _bialy(' '.join(s[3] for s in slowa))
                if rozm >= 16.5:
                    m = _DZIEN.search(tekst)
                    if m: dzien = m.group(1)
                    liga_ciag = False
                    continue
                if 14.5 <= rozm < 16.5:
                    sport, liga, sekcja, etykiety, liga_ciag, podmecz = tekst.strip(), '', '', [], False, ''
                    continue
                if 12.5 <= rozm < 14.5 and all(s[2] >= 12.5 for s in slowa):
                    t = tekst.strip()
                    liga = (liga + ' ' + t) if liga_ciag else t
                    liga_ciag = t.endswith('-')
                    sekcja, etykiety, podmecz = '', [], ''
                    continue
                m = re.fullmatch(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2})', tekst.strip())
                if m:                 # stopka: chwila wygenerowania PDF = chwila, z ktorej sa kursy
                    wygenerowano = wygenerowano or m.group(1)
                    continue
                if rozm >= 11.5:      # „OFERTA KURSOWA”, „Strona n / m”
                    continue
                liga_ciag = False
                pierwsze = slowa[0]
                jest_nr = re.fullmatch(r'\d{2,6}', pierwsze[3]) and abs(pierwsze[0] - x_lewy) < 6 and pierwsze[2] >= 7.9
                if not jest_nr and re.search(r'\d{1,2}:\d{2}$', tekst) and slowa[0][2] < 8.0:
                    # podnaglowek rynkow zawodnikow: „SC Magdeburg - THW Kiel 19:00”, ponizej wiersze z nazwiskami
                    podmecz = _bialy(re.sub(r'\d{1,2}:\d{2}$', '', tekst))
                    continue
                if not jest_nr:
                    # tytul rynku zaczyna sie ok. 28 pt od lewej krawedzi szpalty (dlugi bywa pomniejszony do 8.4);
                    # etykiety kolumn stoja nad kursami (zwykle >= 140 pt od krawedzi) i maja inny rozmiar niz tytul
                    tytul = []
                    if slowa[0][0] - x_lewy < 60:
                        for s in slowa:
                            if s[0] - x_lewy >= 140 or abs(s[2] - slowa[0][2]) > 0.3: break
                            tytul.append(s)
                    etyk = slowa[len(tytul):]
                    etyk = _rozdziel_etykiety(etyk)
                    if tytul:
                        sekcja, podmecz = _bialy(' '.join(s[3] for s in tytul)), ''
                        etykiety = [(s[3], (s[0] + s[1]) / 2 - x_lewy) for s in etyk]
                    elif etyk and all(len(s[3]) <= 6 for s in etyk) and not any(_KURS.fullmatch(s[3]) for s in etyk):
                        etykiety = [(s[3], (s[0] + s[1]) / 2 - x_lewy) for s in etyk]
                    continue
                r = _kursy_w_wierszu(slowa[1:], x_lewy)
                if r is None:
                    ostrz.append(f'str. {nr_str}: wiersz {pierwsze[3]} bez godziny: {tekst[:80]}')
                    continue
                nazwa, kursy, godz = r
                nazwa = _bialy(nazwa)
                mlin = re.search(r'\s*\(([^()]*)\)$', nazwa)
                linia = mlin.group(1) if mlin else ''
                zd = nazwa[:mlin.start()].strip() if mlin else nazwa
                p = re.split(r'\s+-\s+', zd, maxsplit=1)
                gosp, gosc = (p[0], p[1]) if len(p) == 2 else (zd, '')
                przyp = []
                for kurs, x in kursy:
                    if etykiety:
                        e, d = min(((e, abs(x - x_lewy - xe)) for e, xe in etykiety), key=lambda t: t[1])
                        if d > 10:
                            ostrz.append(f'str. {nr_str}: {pierwsze[3]} {zd}: kurs {kurs} nie trafia w etykiete ({sekcja})')
                            continue
                    else:
                        e = f'k{len(przyp) + 1}'
                    przyp.append((e, kurs))
                if len({e for e, _ in przyp}) != len(przyp):
                    ostrz.append(f'str. {nr_str}: {pierwsze[3]} {zd}: dwa kursy pod jedna etykieta ({sekcja}) — pominiety')
                    continue
                k1x2 = dict(przyp)
                marza = (round(sum(1 / k1x2[e] for e in ('1', 'X', '2')), 4)
                         if sekcja.lower() == 'mecz' and all(e in k1x2 for e in ('1', 'X', '2')) else '')
                for e, kurs in przyp:
                    wiersze.append(dict(data_meczu=dzien, godzina_meczu=godz.zfill(5), sport=sport, liga=liga,
                                        gospodarz=gosp, gosc=gosc, kurs=f'{kurs:.2f}',
                                        rynek=_rynek(f'{sekcja} ({podmecz})' if podmecz else sekcja, e, linia),
                                        marza_1x2=marza, godzina_pobrania=pobrano, nr=pierwsze[3],
                                        sekcja=f'{sekcja} ({podmecz})' if podmecz else sekcja,
                                        linia=linia, wybor=e, zdarzenie=zd))
    d = pd.DataFrame(wiersze, columns=KOLUMNY)
    d = bez_wstrzymanych(d, ostrz)
    # chwila kursow: stopka PDF (np. 20:25), a gdy jej brak — z nazwy pliku (20-30, chwila zapisu na Dysk)
    d['godzina_pobrania'] = pobrano or wygenerowano or pobrano_z_nazwy(pdf)
    if not len(d): ostrz.append('brak kursow — to nie jest PDF oferty STS albo zmienil sie jego uklad')
    return d, ostrz


def pobrano_z_nazwy(pdf):
    m = re.search(r'(\d{4}-\d{2}-\d{2})[ _](\d{2})-(\d{2})', os.path.basename(pdf))
    return f'{m.group(1)} {m.group(2)}:{m.group(3)}' if m else ''


def _klucz_nazwy(s):
    """Ta sama nazwa z polskimi znakami i bez nich („Węgry” = „Wegry”), bez wielkosci liter i podwojnych spacji.
    To NIE jest dopasowanie rozmyte: kazda litera musi sie zgadzac."""
    import unicodedata
    from nazwy import LITERY
    s = unicodedata.normalize('NFKD', _bialy(s).translate(LITERY))
    return ''.join(c for c in s if not unicodedata.combining(c)).lower()


KLUCZ_AKO = ['data', 'godzina_uruchomienia', 'tag', 'nr_kuponu', 'noga_nr']   # jak dzienniki.RODZAJE['ako_log']
_PILKA = re.compile(r'(?i)^(pi[lł]ka|pi[lł]ka no[zż]na|football|soccer)$')


def zamkniecia(kursy, ako):
    """Kurs zamkniecia (P56.3: kurs z OSTATNIEGO PDF przed poczatkiem meczu) dla nog ako_log.
    kursy: wynik czytaj() (jeden lub kilka PDF), ako: ako_log (str). Zwraca wiersze ako_log z wpisanym
    kurs_zamkniecia — tylko nogi pilkarskie, mecz jeszcze nierozpoczety w chwili wygenerowania PDF, zdarzenie i rynek
    znalezione JEDNOZNACZNIE (bez zgadywania nazw: inna pisownia = brak kursu, nie cudzy kurs)."""
    from dzienniki import rynek_pilka, _para
    if not len(kursy) or not len(ako): return ako.iloc[0:0].copy(), []
    k = kursy.copy()
    k['t_start'] = pd.to_datetime(k.data_meczu + ' ' + k.godzina_meczu, errors='coerce')
    k['t_pobr'] = pd.to_datetime(k.godzina_pobrania, errors='coerce')
    k = k[(k.sport == 'PIŁKA NOŻNA') & k.t_start.notna() & k.t_pobr.notna() & (k.t_pobr < k.t_start)]
    k = k.sort_values('t_pobr').drop_duplicates(['data_meczu', 'gospodarz', 'gosc', 'rynek'], keep='last')
    idx = {}
    for r in k.itertuples():
        idx.setdefault((_klucz_nazwy(r.gospodarz), _klucz_nazwy(r.gosc), r.rynek), []).append(r)
    wynik, info = [], []
    nogi = ako[(ako.get('noga_nr', '') != 'RAZEM') & ako.get('sport', pd.Series('', index=ako.index)).map(
        lambda s: bool(_PILKA.match(str(s).strip())))]
    for _, r in nogi.iterrows():
        # dzienniki pisza czasem godzine w nazwie: „Juventus - Atalanta (18:00)”
        h, g = _para(re.sub(r'\s*\(\d{1,2}:\d{2}\)\s*$', '', str(r.get('zdarzenie', ''))))
        if not h: continue
        kod = rynek_pilka(r.get('rynek', ''))
        m = re.search(r'mecz\s+(\d{4}-\d{2}-\d{2})', str(r.get('uwaga', '')))
        dni = {m.group(1)} if m else {str(r.get('data', ''))[:10],
                                      str((pd.Timestamp(str(r.get('data', ''))[:10]) + pd.Timedelta(days=1)).date())
                                      if re.match(r'\d{4}-\d{2}-\d{2}', str(r.get('data', ''))) else ''}
        # mecz musi zaczynac sie PO przebiegu, ktory zapisal noge (25.09 21:00: „Australia - Brazylia” bez daty w uwadze
        # trafilo na mecz z 25.09 12:00 — ten sam dzien, ale rozegrany, zanim noge w ogole wpisano)
        uruch = pd.to_datetime(f"{str(r.get('data', ''))[:10]} {str(r.get('godzina_uruchomienia', '')).strip()}", errors='coerce')
        kand = [x for x in idx.get((_klucz_nazwy(h), _klucz_nazwy(g), kod), [])
                if x.data_meczu in dni and (pd.isna(uruch) or x.t_start > uruch)]
        if len(kand) != 1: continue
        x = kand[0]
        if str(r.get('kurs_zamkniecia', '')).strip() == x.kurs: continue
        w = r.copy()
        w['kurs_zamkniecia'] = x.kurs
        wynik.append(w)
        info.append(f"{r.get('tag', '')} {r.get('zdarzenie', '')} {kod}: kurs {r.get('kurs', '')} -> zamkniecie {x.kurs} "
                    f"(PDF {x.godzina_pobrania}, mecz {x.data_meczu} {x.godzina_meczu})")
    # tylko klucz nogi + kontekst do czytania: dzienniki.scal bierze z takiego pliku WYLACZNIE kurs_zamkniecia
    # (nie nadpisze wiersza nogi), a maly plik przebieg zapisze na Dysk bez trudu
    kol = [c for c in KLUCZ_AKO + ['zdarzenie', 'rynek', 'kurs', 'kurs_zamkniecia'] if c in ako.columns or c == 'kurs_zamkniecia']
    return pd.DataFrame(wynik).reindex(columns=kol, fill_value='') if wynik else pd.DataFrame(columns=kol), info


def main(a):
    if not a: sys.exit(__doc__)
    tryb_zamk = a[0] == 'zamkniecia'
    if tryb_zamk: a = a[1:]
    wyj = a[a.index('--wyjscie') + 1] if '--wyjscie' in a else None
    pobr = a[a.index('--pobrano') + 1] if '--pobrano' in a else None
    mecz = a[a.index('--mecz') + 1:a.index('--mecz') + 3] if '--mecz' in a else None
    pdfy = [x for x in a if x.lower().endswith('.pdf')]
    if not pdfy: sys.exit('podaj plik PDF oferty')
    czesci = []
    for f in pdfy:
        d, ostrz = czytaj(f, pobr or '')
        print(f'{os.path.basename(f)}: {d.zdarzenie.nunique() if len(d) else 0} zdarzen, {len(d)} kursow'
              + (f', {len(ostrz)} ostrzezen' if ostrz else ''))
        for o in ostrz[:20]: print('  UWAGA:', o)
        czesci.append(d)
    # ten sam kurs z kilku PDF: zostaje NAJNOWSZY (wg chwili kursow, nie kolejnosci plikow w poleceniu)
    d = (pd.concat(czesci, ignore_index=True).sort_values('godzina_pobrania', kind='stable')
         .drop_duplicates(['data_meczu', 'nr', 'zdarzenie', 'linia', 'sekcja', 'wybor'], keep='last'))
    if mecz:
        # tylko podglad do recznego wyboru: fragment nazwy bez wielkosci liter i polskich znakow („andora” ~ „Andora”);
        # gdy pasuje kilka zdarzen — wypisuje wszystkie, niczego nie wybiera
        from nazwy import LITERY
        import unicodedata

        def n(s):
            s = unicodedata.normalize('NFKD', str(s).translate(LITERY)).encode('ascii', 'ignore').decode().lower()
            return re.sub(r'[^a-z0-9]', '', s)
        qh, qg = n(mecz[0]), n(mecz[1])
        x = d[d.gospodarz.map(lambda s: qh in n(s)) & d.gosc.map(lambda s: qg in n(s))]
        if x.zdarzenie.nunique() != 1:
            print(f'{x.zdarzenie.nunique()} pasujacych zdarzen: {sorted(x.zdarzenie.unique())[:10]} — podaj dokladniejsze nazwy')
        print(x[['data_meczu', 'godzina_meczu', 'zdarzenie', 'sekcja', 'linia', 'wybor', 'rynek', 'kurs']].to_string(index=False))
    if tryb_zamk:
        from dzienniki import _czytaj
        ako_p = a[a.index('--ako') + 1] if '--ako' in a else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ako_log.csv')
        if not os.path.exists(ako_p): sys.exit(f'brak {ako_p} — najpierw: python3 dzienniki.py scal KATALOG_Z_DELTAMI')
        z, info = zamkniecia(d, _czytaj(ako_p))
        for t in info: print('  ' + t)
        print(f'kurs_zamkniecia: {len(z)} nog' + (f' -> {wyj}' if wyj and len(z) else ' (nic do zapisania)' if not len(z) else ''))
        if wyj and len(z):
            z.to_csv(wyj, index=False)
        return
    if wyj:
        if wyj.endswith('.gz'):
            with gzip.open(wyj, 'wt', encoding='utf-8', newline='') as g: d.to_csv(g, index=False)
            pd.read_csv(wyj, dtype=str)          # odczyt kontrolny: plik musi sie dac otworzyc (30.09 18:00 nie dal)
        else:
            d.to_csv(wyj, index=False)
        print(f'zapisano {wyj}: {len(d)} wierszy')


if __name__ == '__main__':
    main(sys.argv[1:])
