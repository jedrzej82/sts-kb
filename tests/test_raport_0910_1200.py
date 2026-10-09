"""09.10.2026 — Raport 09.10 12:00.
  1. „Hyeres Tulon” / „Caen Basket Calvados” (STS) — arkusz koszykowki: „Hyeres-Toulon”, „Caen” (sezon.py NIE ZNALEZIONO).
  2. NIESWIEZA przy klubie grajacym dzis: Bayern Munich II (D3 do 2021) = Bayern München II (Regionalliga), Hvidovre IF (DEN do
     05.2024) = Hvidovre (1st Division), Sepsi (Liga 2 do 05.2026) = Sepsi Sf. Gheorghe; „Dinamo Bukareszt” -> None.
  5. PDF: „Corona Brasov - Fehervar Hockey Akademia 19” (kurs 19.0 wklejony w nazwe) wygrywal przy scalaniu wariantow nazwy
     jako „dluzsza nazwa” — zostaje nazwa bez liczby."""
import os

import pandas as pd

import kluby
import oferta


def test_scalanie_wariantow_nie_bierze_nazwy_z_doklejona_liczba():
    r = lambda zd, g, a, sek: dict(data_meczu='2026-10-09', godzina_meczu='17:00', sport='HOKEJ', zdarzenie=zd, gospodarz=g,
                                   gosc=a, sekcja=sek)
    d = pd.DataFrame([r('Corona Brasov - Fehervar Hockey Akademia', 'Corona Brasov', 'Fehervar Hockey Akademia', '1X2'),
                      r('Corona Brasov - Fehervar Hockey Akademia 19', 'Corona Brasov', 'Fehervar Hockey Akademia 19', 'Zwycięzca meczu')])
    w = oferta.scal_zdarzenia(d, [])
    assert set(w.zdarzenie) == {'Corona Brasov - Fehervar Hockey Akademia'}
    assert set(w.gosc) == {'Fehervar Hockey Akademia'}


def test_kluby_i_aliasy_0910():
    sr = kluby.SCAL_RECZNIE
    assert sr[('D3', 'Bayern Munich II')] == 'Bayern München II'
    assert sr[('DEN', 'Hvidovre IF')] == 'Hvidovre'
    assert sr[('Romania | Liga 2', 'Sepsi')] == 'Sepsi Sf. Gheorghe'
    a = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'aliasy.csv'), dtype=str)
    m = {(r.modul, r.nazwa): r.cel for r in a.itertuples()}
    assert m[('typuj', 'Bayern Monachium II')] == 'Bayern München II' and m[('typuj', 'Dinamo Bukareszt')] == 'Din. Bucuresti'
    assert m[('sezon', 'Hyeres Tulon')] == 'Hyeres-Toulon' and m[('sporty', 'Hyeres Tulon')] == 'Hyeres-Toulon'
    assert m[('sezon', 'Caen Basket Calvados')] == 'Caen'
