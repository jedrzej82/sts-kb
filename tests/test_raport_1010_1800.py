"""Raport 10.10 18:00.
  1. Eredivisie: „NEC Nijmegen”, „Fortuna Sittard” trafialy w stary zapis z Eerste Divisie (N2, inne zrodlo), bez wspolnej
     ligi z rywalem -> NIEPEWNE DOPASOWANIE. 10 par N2/N1 tego samego klubu sklejonych (sprawdzone na bazie: zadna nie
     odrzucona; Ajax – Nijmegen, For Sittard – Twente, Waalwijk – Volendam licza model).
  3. Koszykowka: Kortrijk Spurs = Kortrijk Sport, Landstede Hammers = Zwolle Landstede, Antwerp Giants = Windrose Giants
     Antwerp (sponsor; wczesniej Talenet), Cayirova Belediyesi = Çayırova Belediyespor (TBL -> Super Ligi)."""
import os

import pandas as pd

import kluby
import sporty
import typuj


def test_holandia_n2_n1_jeden_klub():
    sr = kluby.SCAL_RECZNIE
    assert sr[('N2', 'NEC Nijmegen')] == 'Nijmegen' and sr[('N2', 'Fortuna Sittard')] == 'For Sittard'
    assert sr[('N2', 'RKC Waalwijk')] == 'Waalwijk' and sr[('N2', 'Roda JC Kerkrade')] == 'Roda'
    # pelna nazwa z oferty -> nazwa po sklejeniu (alias z SCAL_RECZNIE)
    assert typuj.ALIASES_KLUBY[typuj.norm('NEC Nijmegen')] == 'Nijmegen'
    assert typuj.ALIASES_KLUBY[typuj.norm('Fortuna Sittard')] == 'For Sittard'
    assert typuj.ALIASES_KLUBY[typuj.norm('Roda JC Kerkrade')] == 'Roda'


def test_koszykowka_historia_i_aliasy():
    d = pd.DataFrame([dict(sport='koszykówka', gosp='Cayirova', gosc='Yeni Mamak'),
                      dict(sport='koszykówka', gosp='Talenet Giants Antwerp', gosc='BC Oostende'),
                      dict(sport='hokej', gosp='Cayirova', gosc='X')])
    w = sporty.scal_recznie(d)
    assert list(w.gosp) == ['Çayırova Belediyespor', 'Windrose Giants Antwerp', 'Cayirova']   # tylko w koszykowce
    a = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'aliasy.csv'), dtype=str)
    m = {(r.modul, r.nazwa): r.cel for r in a.itertuples()}
    assert m[('sporty', 'Kortrijk Spurs')] == 'Kortrijk Sport' and m[('sporty', 'Landstede Hammers')] == 'Zwolle Landstede'
    assert m[('sporty', 'Antwerp Giants')] == 'Windrose Giants Antwerp'
    assert m[('sporty', 'Cayirova Belediyesi')] == 'Çayırova Belediyespor'
