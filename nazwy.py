"""Wspolne elementy dopasowania nazw druzyn i zawodnikow — JEDNO zrodlo zamiast kopii w typuj.py, sporty.py,
sezon.py i tenis.py (audyt 29.09.2026: ~20 tabel aliasow i 8 roznych normalizacji; te same poprawki trzeba
bylo wnosic w kilku plikach, a kopie zaczynaly sie rozjezdzac).

  LITERY       — litery, ktorych NFKD nie rozklada (ł, ø, ß…); encode('ascii','ignore') by je SKASOWAL
  ZNACZNIK     — czlon nazwy oznaczajacy druzyne inna niz pierwsza (kobiety, rezerwy, mlodziez, rocznik)
  znaczniki(s) — RODZAJE znacznikow w nazwie; porownanie jest symetryczne: rozne znaczniki = rozne druzyny
  wspolna_liga(m, a, b) — czy dwa kluby graly w jednej lidze (dopasowanie LACZNE pary z oferty)
"""
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
    od = m.MatchDate.max() - __import__('pandas').Timedelta(days=dni)
    x = m[m.MatchDate >= od]
    def ligi(t):
        return set(x.loc[(x.HomeTeam == t) | (x.AwayTeam == t), 'Division'].dropna())
    return bool(ligi(a) & ligi(b))
