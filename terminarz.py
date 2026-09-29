#!/usr/bin/env python3
"""Terminarz 365scores (faza 3b): mecz z oferty STS -> kraj i rozgrywki, po OBU druzynach naraz.
  python3 terminarz.py "Gosp" "Gosc" [--data RRRR-MM-DD]

Plik zewn/terminarz_365.csv.gz zapisuje Apps Script „wyniki STS” co godzine (mecze dzis i jutro, takze
nierozegrane). Nazwy z oferty czesto nie pasuja pojedynczo ("Independiente Yumbo"), ale para
(gospodarz + gosc + data) wskazuje jeden mecz — a z nim kraj i lige. typuj.py uzywa tego, zeby ODRZUCIC
dopasowanie do klubu z innego kraju. Brak pliku albo brak meczu w terminarzu niczego nie blokuje.

Dopasowanie strony: te same czlony nazwy po odrzuceniu form prawnych (FC, CF, SK…), z polskimi nazwami
miast przetlumaczonymi, albo czlony jednej nazwy zawarte w drugiej (min. jeden czlon >= 4 znaki).
Znaczniki (kobiety, rezerwy, mlodziez) musza byc identyczne. Wynik tylko przy JEDNYM pasujacym meczu."""
import os
import re
import sys
import unicodedata

import pandas as pd

from nazwy import LITERY, znaczniki

HERE = os.path.dirname(os.path.abspath(__file__))
PLIK = os.path.join(HERE, 'zewn', 'terminarz_365.csv.gz')
_FORMY = frozenset('fc cf sc ac afc cfc fk nk sk bk hk hc kk rk ok ks sv ss ec fbc sad bc cd ca cs club de la'.split())


def _czlony(s):
    from sezon import _MIASTA_PL
    t = re.findall(r'[a-z0-9]+', unicodedata.normalize('NFKD', str(s).translate(LITERY)).encode('ascii', 'ignore').decode().lower())
    out = set()
    for x in t:
        if x in _FORMY: continue
        out.add(x)
        out.update(_MIASTA_PL.get(x, ()))   # "monachium" pasuje tez do "munich"
    return out


def pasuje(oferta, zrodlo):
    """Czy nazwa z oferty i nazwa z terminarza to ta sama druzyna (bez kontekstu rywala)."""
    if znaczniki(oferta) != znaczniki(zrodlo): return False
    a, b = _czlony(oferta), _czlony(zrodlo)
    if not a or not b: return False
    if not {x for x in a & b if len(x) >= 4}: return False
    return a <= b or b <= a


def wczytaj(plik=PLIK):
    if not os.path.exists(plik): return None
    try:
        return pd.read_csv(plik, dtype=str, keep_default_na=False)
    except Exception as e:
        print(f'  UWAGA: terminarz nieczytelny ({e}) — kontrola terminarza pominieta', file=sys.stderr)
        return None


def znajdz(gosp, gosc, t=None, data=None, sport='football'):
    """Zwraca dict(kraj, turniej, gosp, gosc, data, godzina_utc) jednego meczu albo None (brak / kilka)."""
    t = wczytaj() if t is None else t
    if t is None or not len(t): return None
    x = t[t.sport == sport] if 'sport' in t else t
    if data:
        d0 = pd.Timestamp(data)
        dd = pd.to_datetime(x.data, errors='coerce')
        x = x[(dd - d0).abs() <= pd.Timedelta(days=1)]
    traf = x[[pasuje(gosp, g) and pasuje(gosc, a) for g, a in zip(x.gosp, x.gosc)]]
    if traf.empty:   # oferta czasem odwraca strony (mecz na neutralnym / pomylka) — tylko informacyjnie
        return None
    if len(traf.drop_duplicates(['kraj', 'turniej', 'gosp', 'gosc'])) > 1:
        return None
    r = traf.iloc[0]
    return dict(kraj=r.kraj, turniej=r.turniej, gosp=r.gosp, gosc=r.gosc, data=r.data, godzina_utc=r.get('godzina_utc', ''))


def main(a):
    if len(a) < 2: sys.exit(__doc__)
    data = a[a.index('--data') + 1] if '--data' in a else None
    t = wczytaj()
    if t is None: sys.exit('BRAK zewn/terminarz_365.csv.gz — pobierz z Dysku (Apps Script „wyniki STS”)')
    m = znajdz(a[0], a[1], t, data)
    print(f'TERMINARZ: {m["gosp"]} – {m["gosc"]} | {m["kraj"]} | {m["turniej"]} | {m["data"]} {m["godzina_utc"]} UTC'
          if m else 'TERMINARZ: brak jednoznacznego meczu (nazwy nie pasuja albo kilka kandydatow)')


if __name__ == '__main__':
    main(sys.argv[1:])
