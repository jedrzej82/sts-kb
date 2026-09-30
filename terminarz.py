#!/usr/bin/env python3
"""Terminarz 365scores (faza 3b): mecz z oferty STS -> kraj i rozgrywki, po OBU druzynach naraz.
  python3 terminarz.py "Gosp" "Gosc" [--data RRRR-MM-DD]

Pliki zewn/terminarz_fs.csv.gz (Flashscore) i zewn/terminarz_365.csv.gz zapisuje Apps Script „wyniki STS” co godzine (mecze dzis i jutro, takze
nierozegrane). Nazwy z oferty czesto nie pasuja pojedynczo ("Independiente Yumbo"), ale para
(gospodarz + gosc + data) wskazuje jeden mecz — a z nim kraj i lige. typuj.py uzywa tego, zeby ODRZUCIC
dopasowanie do klubu z innego kraju. Brak pliku albo brak meczu w terminarzu niczego nie blokuje.

Dopasowanie strony: te same czlony nazwy po odrzuceniu form prawnych (FC, CF, SK…), z polskimi nazwami
miast przetlumaczonymi, albo czlony jednej nazwy zawarte w drugiej (min. jeden czlon >= 4 znaki).
Znaczniki (kobiety, rezerwy, mlodziez) musza byc identyczne. Wynik tylko przy JEDNYM pasujacym meczu."""
import functools
import os
import re
import sys
import unicodedata

import pandas as pd

from nazwy import LITERY, znaczniki

HERE = os.path.dirname(os.path.abspath(__file__))
PLIK = os.path.join(HERE, 'zewn', 'terminarz_365.csv.gz')
PLIK_FS = os.path.join(HERE, 'zewn', 'terminarz_fs.csv.gz')   # Flashscore (od 29.09) — pelniejszy, sprawdzany najpierw
_FORMY = frozenset('fc cf sc ac afc cfc fk nk sk bk hk hc kk rk ok ks sv ss ec fbc sad bc cd ca cs club de la'.split())


def _czlony(s):
    """Czlony nazwy (frozenset). 30.09.2026: wynik zapamietywany — funkcja czysta, a zewn._fsx_bez_dubli wolal ja
    1,9 mln razy dla tych samych nazw (45 s z 314 s hist_import)."""
    return _czlony_z(str(s))


@functools.lru_cache(maxsize=None)
def _czlony_z(s):
    from sezon import _MIASTA_PL
    t = re.findall(r'[a-z0-9]+', unicodedata.normalize('NFKD', s.translate(LITERY)).encode('ascii', 'ignore').decode().lower())
    out = set()
    for x in t:
        if x in _FORMY or znaczniki(x): continue   # znaczniki (II/2/B, W/K, U20) porownuje pasuje() osobno
        out.add(x)
        out.update(_MIASTA_PL.get(x, ()))   # "monachium" pasuje tez do "munich"
    # 30.09.2026 (proba generalna): „Junior FC” (Barranquilla) — „junior” to znacznik mlodziezy, „fc” forma prawna;
    # nie zostawal ZADEN czlon i kontrola terminarza nigdy nie dzialala (po cichu). Gdy nic nie zostaje — znaczniki
    # sa nazwa klubu, nie znacznikiem.
    if not out:
        out = {x for x in t if x not in _FORMY}
    return frozenset(out)


def pasuje(oferta, zrodlo):
    """Czy nazwa z oferty i nazwa z terminarza to ta sama druzyna (bez kontekstu rywala)."""
    if znaczniki(oferta) != znaczniki(zrodlo): return False
    a, b = _czlony(oferta), _czlony(zrodlo)
    if not a or not b: return False
    if not {x for x in a & b if len(x) >= 4}: return False
    return a <= b or b <= a


def _czytaj(plik):
    if not os.path.exists(plik): return None
    try:
        return pd.read_csv(plik, dtype=str, keep_default_na=False)
    except Exception as e:
        print(f'  UWAGA: terminarz {os.path.basename(plik)} nieczytelny ({e}) — pominiety', file=sys.stderr)
        return None


def wczytaj(plik=None):
    """Oba terminarze (kolumna zrodlo: fs, 365) albo None. Flashscore ma wiecej sportow i nizszych lig."""
    if plik: return _czytaj(plik)
    czesci = [t.assign(zrodlo=z) for z, p in (('fs', PLIK_FS), ('365', PLIK)) for t in [_czytaj(p)] if t is not None]
    return pd.concat(czesci, ignore_index=True) if czesci else None


def _wspolny(oferta, zrodlo):
    """Luzniej niz pasuje(): te same znaczniki i co najmniej jeden wspolny czlon >= 4 litery
    („CD Platense Zacatecoluca” / „Platense Municipal”). Tylko dla drugiej druzyny, gdy pierwsza pasuje scisle."""
    if znaczniki(oferta) != znaczniki(zrodlo): return False
    # surowe czlony (bez form prawnych): „CD Junior Barranquilla” / „Junior FC” — „junior” to tu nazwa klubu,
    # a znacznik mlodziezy i tak musi byc po obu stronach taki sam (warunek wyzej)
    sur = lambda s: {x for x in re.findall(r'[a-z0-9]+', unicodedata.normalize('NFKD', str(s).translate(LITERY))
                                          .encode('ascii', 'ignore').decode().lower()) if x not in _FORMY}
    return bool({x for x in (_czlony(oferta) | sur(oferta)) & (_czlony(zrodlo) | sur(zrodlo)) if len(x) >= 4})


def znajdz(gosp, gosc, t=None, data=None, sport='football', luzno=False):
    """Zwraca dict(kraj, turniej, gosp, gosc, data, godzina_utc) jednego meczu albo None (brak / kilka).
    luzno=True (30.09.2026, tylko do ponownego dopasowania w kraju meczu w typuj.py): gdy scisle nic nie ma, wystarczy,
    ze JEDNA druzyna pasuje scisle, a druga ma wspolny czlon >= 4 litery — i taki mecz jest jeden."""
    t = wczytaj() if t is None else t
    if t is None or not len(t): return None
    if 'zrodlo' in t and t.zrodlo.nunique() > 1:   # zrodla nazywaja ligi inaczej — kazde osobno, Flashscore pierwszy
        for z in ('fs', '365'):
            m = znajdz(gosp, gosc, t[t.zrodlo == z].drop(columns='zrodlo'), data, sport)
            if m: return m
        if luzno:
            for z in ('365', 'fs'):   # luzno: najpierw 365 — jego zapis nazw jest zwykle ten sam co w bazie
                m = znajdz(gosp, gosc, t[t.zrodlo == z].drop(columns='zrodlo'), data, sport, luzno=True)
                if m: return m
        return None
    x = t[t.sport == sport] if 'sport' in t else t
    if data:
        d0 = pd.Timestamp(data)
        dd = pd.to_datetime(x.data, errors='coerce')
        x = x[(dd - d0).abs() <= pd.Timedelta(days=1)]
    traf = x[[pasuje(gosp, g) and pasuje(gosc, a) for g, a in zip(x.gosp, x.gosc)]]
    if traf.empty and luzno:
        traf = x[[(pasuje(gosp, g) and _wspolny(gosc, a)) or (_wspolny(gosp, g) and pasuje(gosc, a))
                  for g, a in zip(x.gosp, x.gosc)]]
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
    if t is None: sys.exit('BRAK zewn/terminarz_fs.csv.gz i terminarz_365.csv.gz — pobierz z Dysku (Apps Script „wyniki STS”)')
    m = znajdz(a[0], a[1], t, data)
    print(f'TERMINARZ: {m["gosp"]} – {m["gosc"]} | {m["kraj"]} | {m["turniej"]} | {m["data"]} {m["godzina_utc"]} UTC'
          if m else 'TERMINARZ: brak jednoznacznego meczu (nazwy nie pasuja albo kilka kandydatow)')


if __name__ == '__main__':
    main(sys.argv[1:])
