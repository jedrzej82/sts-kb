"""Wspolne elementy dopasowania nazw druzyn i zawodnikow — JEDNO zrodlo zamiast kopii w typuj.py, sporty.py,
sezon.py i tenis.py (audyt 29.09.2026: ~20 tabel aliasow i 8 roznych normalizacji; te same poprawki trzeba
bylo wnosic w kilku plikach, a kopie zaczynaly sie rozjezdzac).

  LITERY       — litery, ktorych NFKD nie rozklada (ł, ø, ß…); encode('ascii','ignore') by je SKASOWAL
  ZNACZNIK     — czlon nazwy oznaczajacy druzyne inna niz pierwsza (kobiety, rezerwy, mlodziez, rocznik)
  znaczniki(s) — RODZAJE znacznikow w nazwie; porownanie jest symetryczne: rozne znaczniki = rozne druzyny
  wspolna_liga(m, a, b) — czy dwa kluby graly w jednej lidze (dopasowanie LACZNE pary z oferty)
"""
import os
import re

LITERY = str.maketrans({'ł': 'l', 'Ł': 'L', 'đ': 'd', 'Đ': 'D', 'ø': 'o', 'Ø': 'O', 'ß': 'ss',
                        'æ': 'ae', 'Æ': 'AE', 'œ': 'oe', 'Œ': 'OE', 'þ': 'th', 'Þ': 'TH',
                        'ð': 'd', 'Ð': 'D', 'ı': 'i', 'ŋ': 'n', 'ħ': 'h', 'ŧ': 't'})

# 29.09.2026 (faza 3): dopisane "talang" (szwedzkie druzyny akademii — raport 25.09 12:00: "Hammarby Talang"
# dopasowane do pierwszej druzyny Hammarby), "jong" (holenderskie drugie zespoly: Jong Ajax, Jong PSV)
# i "primavera" (wloska mlodziez). Sprawdzone na bazie 29.09: w pilce "jong" wystepuje tylko w Jong X,
# "talang" i "primavera" nigdzie; test symetryczny, wiec zapis identyczny po obu stronach dalej pasuje.
ZNACZNIK = re.compile(r'^(b|ii|iii|2|3|c|k|u-?1[6-9]|u-?2[0-3]|sub-?2[0-3]|jun|juniors?|res|reserves?|jong|'
                      r'young|youth|yth|academy|akademia|talang|primavera|w|women|kobiet[ay]?|damen|femenino|femenil|'
                      r'feminin[oa]?|fem)\.?$', re.I)


def znaczniki(s):
    """Rodzaje znacznikow w nazwie (posortowana krotka): kobiety / rezerwy / zespol_c / uNN / mlodziez.
    22.09.2026: STS pisze "[K]" i "(W)" — nawiasy zdejmujemy. 23.09.2026: porownujemy RODZAJE, nie liczbe
    ("Barcelona (K)" to nie "Barcelona B", choc obie maja po jednym znaczniku)."""
    out = []
    for t in re.split(r'[\s]+', str(s).strip()):
        t = t.strip('[](){}<>.,;:')
        if not ZNACZNIK.match(t): continue
        t = t.lower().rstrip('.')
        if re.match(r'^(k|w|women|kobiet[ay]?|damen|femenino|femenil|feminin[oa]?|fem)$', t): out.append('kobiety')
        elif re.match(r'^(b|ii|2|res|reserves?|jong)$', t): out.append('rezerwy')
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
