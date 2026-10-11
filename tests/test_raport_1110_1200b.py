"""Raport 11.10 12:00 nr 1–3 (wieczorna paczka): nazwy z oferty i rozbite zapisy klubow.
  FC Koeln -> FC Koln; Union Saint-Gilloise -> St. Gilloise; Karlsruher SC -> Karlsruhe (stary zapis D3 sklejony);
  VV Sint-Truiden -> St Truiden (stary zapis B2 sklejony); Al-Faisaly FC -> Al Faysaly (Jordania: inny klub, bez SCAL);
  Olympiacos Pireus -> Olympiakos. Klasa B2/D3 (inne zrodlo niz B1/D2): 14 par sklejonych — na bazie zadna nie odrzucona,
  wszystkie mecze z raportu licza model."""
import os

import pandas as pd

import kluby
import typuj


def test_scal_b2_d3():
    sr = kluby.SCAL_RECZNIE
    assert sr[('D3', 'Karlsruher')] == 'Karlsruhe' and sr[('B2', 'Sint-Truiden')] == 'St Truiden'
    assert sr[('B2', 'OH Leuven')] == 'Oud-Heverlee Leuven' and sr[('B2', 'Union SG')] == 'St. Gilloise'
    assert sr[('D3', 'MSV Duisburg')] == 'Duisburg' and sr[('D3', 'Arminia')] == 'Bielefeld'
    assert ('B2', 'R.Oc. De Charleroi') not in sr and ('B2', 'KRC Mechelen') not in sr and ('B2', 'Excel Mouscron') not in sr
    # alias z SCAL_RECZNIE nie moze przejac innego klubu tej samej nazwy (Al Faisaly — Jordania)
    assert typuj.ALIASES_KLUBY.get(typuj.norm('Al Faisaly')) in (None, 'Al Faisaly')


def test_aliasy_1110():
    a = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'aliasy.csv'), dtype=str)
    m = {(r.modul, r.nazwa): r.cel for r in a.itertuples()}
    assert m[('typuj', 'FC Koeln')] == 'FC Koln' and m[('typuj', 'Union Saint-Gilloise')] == 'St. Gilloise'
    assert m[('typuj', 'Al-Faisaly FC')] == 'Al Faysaly' and m[('typuj', 'Olympiacos Pireus')] == 'Olympiakos'
    assert m[('typuj', 'TSV 1860 Munchen')] == 'Munich 1860'
    assert typuj.ALIASES[typuj.norm('Jahn Regensburg')] == 'SSV Jahn Regensburg'   # alias w kodzie — zapis D3 zostaje


def test_jastrzebie_zapis_nazwy():
    # Raport 11.10 15:00 nr 4: 365 pisze „GKS Jastrzêbie” — w bazie i WERDYKT „GKS Jastrzębie” (ta sama historia, 50 meczow)
    import sporty
    d = pd.DataFrame([dict(sport='hokej', gosp='GKS Jastrzêbie', gosc='Podhale Nowy Targ')])
    assert sporty.scal_recznie(d).gosp.iloc[0] == 'GKS Jastrzębie'
    assert sporty._ALIASY_RECZNE['jkhgksjastrzebie'] == 'GKS Jastrzębie'
