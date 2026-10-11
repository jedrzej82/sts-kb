"""Raport 11.10 18:00 nr 2: PDF STS rozbil mecz na „Olympiacos Pireus – Panathinaikos Ateny” (tylko 1X2) i „Olympiakos Pireus
– Panathinaikos Ateny” (tylko gole/BTTS) — rozni sie jedna litera, wiec scalanie P179.4 (podzbior czlonow) nie dzialalo; nogi
goli mialy pusta marze. Sprawdzone na „oferta-dzisiaj-auto 2026-10-11 17-30.pdf”: jedno scalenie, mecz z pelna oferta."""
import pandas as pd

import oferta


def _d(w):
    return pd.DataFrame([dict(data_meczu='2026-10-11', godzina_meczu=g, sport='PIŁKA NOŻNA', zdarzenie=f'{a} - {b}', gospodarz=a,
                              gosc=b, rynek=r, kurs=1.5) for g, a, b, r in w])


def test_literowka_w_jednym_czlonie_scala():
    w = [('20:00', 'Olympiacos Pireus', 'Panathinaikos Ateny', r) for r in ('1', 'X', '2')]
    w += [('20:00', 'Olympiakos Pireus', 'Panathinaikos Ateny', r) for r in ('O2.5', 'U2.5', 'BTTS_tak', 'BTTS_nie')]
    d = oferta._scal_warianty_nazwy(_d(w), [])
    assert set(d.zdarzenie) == {'Olympiakos Pireus - Panathinaikos Ateny'}     # wariant z wieksza liczba kursow


def test_literowka_nie_scala_innych_par():
    assert not oferta._literowka({'olympiacos', 'pireus'}, {'olympiakos', 'ateny'})        # dwa czlony inne
    assert not oferta._literowka({'ajax'}, {'ajaxx'})                                       # za krotkie
    assert oferta._literowka({'olympiacos', 'pireus'}, {'olympiakos', 'pireus'})
    # inna godzina albo obie strony rozne — bez zmian
    w = [('20:00', 'Olympiacos Pireus', 'Panathinaikos Ateny', '1'), ('21:00', 'Olympiakos Pireus', 'Panathinaikos Ateny', 'O2.5'),
         ('20:00', 'Olympiakos Pireus', 'Aris Saloniki', 'O2.5')]
    assert set(oferta._scal_warianty_nazwy(_d(w), []).zdarzenie) == {'Olympiacos Pireus - Panathinaikos Ateny',
                                                                     'Olympiakos Pireus - Panathinaikos Ateny',
                                                                     'Olympiakos Pireus - Aris Saloniki'}


def test_alias_saint_louis_city():
    # Raport 11.10 21:00 nr 2: „Saint Louis City SC” -> Saint Louis (USL 2017–20, inny klub); w bazie MLS: St. Louis City
    import os
    a = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'aliasy.csv'), dtype=str)
    assert {(r.modul, r.nazwa): r.cel for r in a.itertuples()}[('typuj', 'Saint Louis City SC')] == 'St. Louis City'
