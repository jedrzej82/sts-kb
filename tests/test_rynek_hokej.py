"""01.10.2026 (przebieg 15:00, K5b za pieniadze): semantyka rynku w sportach z remisem (hokej).

Reprodukcja: hokej, Rogle BK - Timra IK, rynek „Zwyciezca 1”, wynik 3:2 po dogrywce -> kod dawal PRZEGRANY
(„rozstrzygniety w dogrywce, a rynek w czasie regulaminowym”), oczekiwane TRAFIONY.
Warstwa: interpretacja rynku. „Zwyciezca …” = wynik CALEGO meczu (z dogrywka i karnymi);
1 / X / 2 / „1 (60 min)” = wynik po czasie regulaminowym. Sama dogrywka nie jest wynikiem — decyduje
koncowy rezultat rynku wlasciwego typu."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dzienniki  # noqa: E402

D = '2026-10-01'
ZD = 'Rogle BK - Timra IK'


def _w(pg, pa, ot):
    """Jeden mecz hokeja w zrodle wynikow; pg/pa = wynik KONCOWY, ot: 1 dogrywka/karne, 0 regulamin, -1 nieznane."""
    return dict(pilka=pd.DataFrame(columns=['d', 'h', 'a', 'g', 'ga', 'hg', 'ha']),
                tenis=pd.DataFrame(columns=['d', 'w', 'l', 'score']),
                inne=pd.DataFrame([(pd.Timestamp(D), 'hokej', 'Rogle BK', 'Timra IK', pg, pa, ot)],
                                  columns=['d', 'sport', 'h', 'a', 'pg', 'pa', 'ot']))


def _stan(rynek, pg, pa, ot):
    return dzienniki.rozlicz_noge(dict(sport='hokej', zdarzenie=ZD, rynek=rynek, data=D), _w(pg, pa, ot))[0]


# rynek, wynik koncowy, dogrywka, oczekiwany stan
ZWYCIEZCA = [
    ('Zwyciezca 1', 2, 1, 0, 'TRAFIONY'),
    ('Zwyciezca 1', 3, 2, 1, 'TRAFIONY'),        # Rogle K5b — reprodukcja z 01.10
    ('Zwyciezca 1', 2, 3, 1, 'PRZEGRANY'),       # byla dogrywka, ale wygral rywal
    ('Zwyciezca 1', 1, 3, 0, 'PRZEGRANY'),
    ('Zwyciezca 2', 1, 2, 0, 'TRAFIONY'),
    ('Zwyciezca 2', 2, 3, 1, 'TRAFIONY'),
    ('Zwyciezca 2', 3, 2, 1, 'PRZEGRANY'),
    ('Zwyciezca meczu - Rogle BK', 3, 2, 1, 'TRAFIONY'),
    ('Zwyciezca meczu - Timra IK', 3, 2, 1, 'PRZEGRANY'),
    ('Zwyciezca meczu 1', 4, 3, 1, 'TRAFIONY'),
    ('Zwyciezca 1 (z dogrywka)', 3, 2, 1, 'TRAFIONY'),
    ('1 z dogrywka', 3, 2, 1, 'TRAFIONY'),
    ('Zwyciezca 1', 3, 2, -1, 'TRAFIONY'),       # dogrywka nieznana — dla calego meczu niepotrzebna
    ('Zwyciezca 2', 3, 2, -1, 'PRZEGRANY'),
]

# rynki regulaminowe (60 min) — zachowanie BEZ ZMIAN
REGULAMIN = [
    ('1', 2, 1, 0, 'TRAFIONY'),
    ('1', 3, 2, 1, 'PRZEGRANY'),                 # po 60 min byl remis
    ('2', 1, 2, 0, 'TRAFIONY'),
    ('2', 2, 3, 1, 'PRZEGRANY'),
    ('X', 3, 2, 1, 'TRAFIONY'),
    ('X', 2, 1, 0, 'PRZEGRANY'),
    ('1 (60 min)', 3, 2, 1, 'PRZEGRANY'),
    ('1 (60 min)', 2, 1, 0, 'TRAFIONY'),
    ('1', 3, 2, -1, 'BRAK WYNIKU'),              # bez wiedzy o dogrywce nie rozliczamy 60 min
]


@pytest.mark.parametrize('rynek,pg,pa,ot,oczekiwane', ZWYCIEZCA)
def test_zwyciezca_to_caly_mecz(rynek, pg, pa, ot, oczekiwane):
    assert _stan(rynek, pg, pa, ot) == oczekiwane


@pytest.mark.parametrize('rynek,pg,pa,ot,oczekiwane', REGULAMIN)
def test_rynki_regulaminowe_bez_zmian(rynek, pg, pa, ot, oczekiwane):
    assert _stan(rynek, pg, pa, ot) == oczekiwane


@pytest.mark.parametrize('rynek', ['1X', 'X2'])
def test_podwojna_szansa_bez_zmian(rynek):
    # 1X / X2 w hokeju nie byly rozliczane kodem (BRAK WYNIKU) — poprawka tego nie zmienia
    assert _stan(rynek, 3, 2, 1) == 'BRAK WYNIKU'
