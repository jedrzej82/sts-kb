"""Wspolne elementy dopasowania nazw druzyn i zawodnikow — JEDNO zrodlo zamiast kopii w typuj.py, sporty.py,
sezon.py i tenis.py (audyt 29.09.2026: ~20 tabel aliasow i 8 roznych normalizacji; te same poprawki trzeba
bylo wnosic w kilku plikach, a kopie zaczynaly sie rozjezdzac).

  LITERY       — litery, ktorych NFKD nie rozklada (ł, ø, ß…); encode('ascii','ignore') by je SKASOWAL
  ZNACZNIK     — czlon nazwy oznaczajacy druzyne inna niz pierwsza (kobiety, rezerwy, mlodziez, rocznik)
  znaczniki(s) — RODZAJE znacznikow w nazwie; porownanie jest symetryczne: rozne znaczniki = rozne druzyny
  wspolna_liga(m, a, b) — czy dwa kluby graly w jednej lidze (dopasowanie LACZNE pary z oferty)
"""
import functools
import os
import re

LITERY = str.maketrans({'ł': 'l', 'Ł': 'L', 'đ': 'd', 'Đ': 'D', 'ø': 'o', 'Ø': 'O', 'ß': 'ss',
                        'æ': 'ae', 'Æ': 'AE', 'œ': 'oe', 'Œ': 'OE', 'þ': 'th', 'Þ': 'TH',
                        'ð': 'd', 'Ð': 'D', 'ı': 'i', 'ŋ': 'n', 'ħ': 'h', 'ŧ': 't',
                        # 08.10.2026 (Raport 15:00 nr 1): twarde/typograficzne laczniki z PDF STS („Al‑Duhail”, U+2011)
                        # to zwykly „-” — inaczej ascii-ignore sklejal „Al‑Duhail” w jeden czlon „alduhail”
                        '\u2010': '-', '\u2011': '-', '\u2012': '-', '\u2043': '-', '\u00ad': None})

# 29.09.2026 (faza 3): dopisane "talang" (szwedzkie druzyny akademii — raport 25.09 12:00: "Hammarby Talang"
# dopasowane do pierwszej druzyny Hammarby), "jong" (holenderskie drugie zespoly: Jong Ajax, Jong PSV)
# i "primavera" (wloska mlodziez). Sprawdzone na bazie 29.09: w pilce "jong" wystepuje tylko w Jong X,
# "talang" i "primavera" nigdzie; test symetryczny, wiec zapis identyczny po obu stronach dalej pasuje.
ZNACZNIK = re.compile(r'^(b|ii|iii|2|3|c|k|u-?1[6-9]|u-?2[0-3]|sub-?2[0-3]|jun|juniors?|res|reserves?|rezerwy|jong|'
                      r'young|youth|yth|academy|akademia|talang|primavera|w|women|kobiet[ay]?|damen|femenino|femenil|'
                      r'feminin[oa]?|fem)\.?$', re.I)


def znaczniki(s):
    """Rodzaje znacznikow w nazwie (posortowana krotka): kobiety / rezerwy / zespol_c / uNN / mlodziez.
    22.09.2026: STS pisze "[K]" i "(W)" — nawiasy zdejmujemy. 23.09.2026: porownujemy RODZAJE, nie liczbe
    ("Barcelona (K)" to nie "Barcelona B", choc obie maja po jednym znaczniku).
    30.09.2026: wynik zapamietywany (funkcja czysta, krotka niezmienna) — hist_import wolal ja 7,3 mln razy
    dla tych samych nazw (76 s z 314 s przebiegu)."""
    return _znaczniki(str(s))


@functools.lru_cache(maxsize=None)
def _znaczniki(s):
    out = []
    for t0 in re.split(r'[\s]+', s.strip()):
        # 06.10.2026: Superbet pisze rezerwy „Racing Club (R)” — samo „R” w nawiasie (bez nawiasu to inicjal: „Bhosale R”)
        if re.fullmatch(r'\(R\)', t0, re.I):
            out.append('rezerwy'); continue
        t0 = t0.strip('[](){}<>.,;:')
        # 30.09.2026 (przeglad): „Zenit-2”, „CSKA-2 Moscow” — znacznik po lacznika nie byl widziany i pierwsza druzyna
        # („Zenit”) trafiala w rezerwy. Ostatni czlon po '-' sprawdzamy osobno (bez rozbijania „U-19”, „Sub-21”).
        # tylko cyfra albo cyfra rzymska po laczniku (Zenit-2, CSKA-2, Dinamo-II) — nie „Kyong-Jun”, „Y.-B.”, „J.-K.”
        _po = t0.rsplit('-', 1)[1] if '-' in t0 else ''
        cz = [t0] + ([_po] if re.fullmatch(r'\d+|[ivxIVX]+', _po) and not re.match(r'^(u|sub)-?\d+$', t0, re.I) else [])
        t = next((c for c in cz if ZNACZNIK.match(c)), None)
        if t is None: continue
        t = t.lower().rstrip('.')
        if re.match(r'^(k|w|women|kobiet[ay]?|damen|femenino|femenil|feminin[oa]?|fem)$', t): out.append('kobiety')
        elif re.match(r'^(b|ii|2|res|reserves?|rezerwy|jong)$', t): out.append('rezerwy')
        elif re.match(r'^(c|iii|3)$', t): out.append('zespol_c')
        elif re.match(r'^(u|sub)-?\d+$', t): out.append('u' + re.sub(r'\D', '', t))
        else: out.append('mlodziez')
    return tuple(sorted(out))


def wspolna_liga(m, a, b, dni=730):
    """Czy kluby a i b graly w tej samej lidze (Division) w ostatnich `dni` dniach bazy.
    m: DataFrame z kolumnami MatchDate, HomeTeam, AwayTeam, Division. Sluzy do dopasowania LACZNEGO:
    gdy nazwa z oferty zgubila czlon rozrozniajacy ("Independiente Yumbo" -> "Independiente"), para jest
    wiarygodna tylko wtedy, gdy oba kluby naprawde dziela lige. Puchar krajowy z roznych lig -> False
    (noga MNIEJ — bezpieczny kierunek bledu)."""
    if a is None or b is None or m is None or not len(m): return False
    import pandas as pd
    od = m.MatchDate.max() - pd.Timedelta(days=dni)
    x = m[m.MatchDate >= od]
    def ligi(t):
        return set(x.loc[(x.HomeTeam == t) | (x.AwayTeam == t), 'Division'].dropna())
    return bool(ligi(a) & ligi(b))


ALIASY_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aliasy.csv')


# 03.10.2026: aliasy uczone w przebiegu (dopasuj.py auto) — wczytywane PO aliasy.csv (setdefault: reczne wygrywaja)
ALIASY_AUTO_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aliasy_auto.csv')


def aliasy_z_pliku(modul, klucz, slownik, plik=None):
    """29.09.2026 (faza 3b): aliasy jako DANE — aliasy.csv (modul,nazwa,cel,uzasadnienie,data), nazwa tak jak
    w ofercie; klucz liczy funkcja danego modulu. Dopisuje przez setdefault, wiec wpis w kodzie wygrywa
    (istniejace dopasowania sie nie zmieniaja). Nowe pary nazw: jeden wiersz w CSV zamiast zmian w kilku plikach.
    Zwraca liczbe dodanych wpisow."""
    import csv
    plik = plik or ALIASY_CSV
    if not os.path.exists(plik): return 0
    n = 0
    with open(plik, encoding='utf-8', newline='') as fh:
        for r in csv.DictReader(fh):
            if (r.get('modul') or '').strip() != modul or not (r.get('nazwa') or '').strip() or not (r.get('cel') or '').strip():
                continue
            k = klucz(r['nazwa'].strip())
            if k and k not in slownik:
                slownik[k] = r['cel'].strip(); n += 1
    return n


def aliasy_wiele(modul, klucz, pliki=None):
    """03.10.2026: WSZYSTKIE cele dla nazwy (lista w kolejnosci plikow) — modul „sporty” dzieli aliasy miedzy sporty,
    a ten sam klub ma rozne zapisy w roznych sportach („Buducnost Podgorica”: pilka wodna „Buducnost”, koszykowka
    „KK Budućnost”). Wolajacy bierze pierwszy cel obecny w puli danego sportu."""
    import csv
    out = {}
    for plik in pliki or (ALIASY_CSV, ALIASY_AUTO_CSV):
        if not os.path.exists(plik): continue
        with open(plik, encoding='utf-8', newline='') as fh:
            for r in csv.DictReader(fh):
                if (r.get('modul') or '').strip() != modul or not (r.get('nazwa') or '').strip() or not (r.get('cel') or '').strip():
                    continue
                k = klucz(r['nazwa'].strip())
                if k and r['cel'].strip() not in out.setdefault(k, []): out[k].append(r['cel'].strip())
    return out


# Polskie nazwy miast (egzonimy) -> zapis w zrodlach wynikow. Wspolne dla typuj.py i sporty.py (29.09.2026:
# „Hapoel Tel Awiw”, „Hapoel Beer Szewa” nie dopasowywaly sie ani w pilce, ani w koszykowce). Tylko pojedyncze
# czlony nazwy miasta; zamiana jest probą dodatkowa — nazwa oryginalna ma pierwszenstwo.
EGZONIMY = {'madryt': 'Madrid', 'monachium': 'Munich', 'wieden': 'Wien', 'lizbona': 'Lisbon',
            'mediolan': 'Milan', 'rzym': 'Roma', 'neapol': 'Napoli', 'turyn': 'Torino', 'ateny': 'Athens',
            'sewilla': 'Sevilla', 'walencja': 'Valencia', 'stambul': 'Istanbul', 'kopenhaga': 'Copenhagen',
            'bruksela': 'Brussels', 'belgrad': 'Belgrade', 'moskwa': 'Moscow', 'praga': 'Prague',
            'bukareszt': 'Bucharest', 'sztokholm': 'Stockholm', 'kijow': 'Kyiv', 'lwow': 'Lviv',
            'zagrzeb': 'Zagreb', 'genua': 'Genoa', 'saloniki': 'Thessaloniki', 'pireus': 'Piraeus',
            'awiw': 'Aviv', 'szewa': 'Sheva', 'jerozolima': 'Jerusalem', 'hajfa': 'Haifa', 'kowno': 'Kaunas',
            'wilno': 'Vilnius', 'ryga': 'Riga', 'bazylea': 'Basel', 'genewa': 'Geneve', 'zurych': 'Zurich',
            'marsylia': 'Marseille', 'wenecja': 'Venezia', 'antwerpia': 'Antwerp',
            'kolonia': 'Koln', 'norymberga': 'Nurnberg', 'akwizgran': 'Aachen', 'brema': 'Bremen',
            'lipsk': 'Leipzig', 'drezno': 'Dresden', 'erywan': 'Yerevan',
            'nikozja': 'Nicosia', 'lublana': 'Ljubljana', 'bratyslawa': 'Bratislava'}


def egzonim(nazwa, klucz):
    """Nazwa z polskimi nazwami miast zamienionymi na zapis zrodel (klucz = funkcja norm modulu)."""
    czl = str(nazwa).split()
    return ' '.join(EGZONIMY.get(klucz(c), c) for c in czl)
