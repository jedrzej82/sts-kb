"""Bramki w sporty.py: drugie zrodlo (log5 z formy) i laczny WERDYKT."""
import pandas as pd
import pytest

import sporty


def _baza(wyg_h, wyg_g, n=10):
    """H wygrywa wyg_h z n, G wygrywa wyg_g z n (rywale spoza pary)."""
    w = []
    for t, k in (('H', wyg_h), ('G', wyg_g)):
        for i in range(n):
            w.append(dict(sport='hokej', gosp=t, gosc=f'R{i}', pg=3 if i < k else 1, pa=1 if i < k else 3))
    return pd.DataFrame(w)


def test_zgodne_daje_p_modelu():
    # forma H 8/10 -> 0.75, G 3/10 -> 1/3; log5 = 0.75*(2/3) / (0.75*(2/3) + (1/3)*0.25) = 6/7 ~ 0.857
    # Poprawka 58: przy zgodnych zrodlach P do kuponu = P modelu (docs/BACKTEST_P48.md)
    assert sporty.drugie_zrodlo(_baza(8, 3), 'hokej', 'H', 'G', 0.80) == pytest.approx(0.80)
    assert sporty.drugie_zrodlo(_baza(8, 3), 'hokej', 'H', 'G', 0.90) == pytest.approx(0.90)


def test_rozni_faworyci_to_none():
    assert sporty.drugie_zrodlo(_baza(2, 8), 'hokej', 'H', 'G', 0.70) is None


def test_mala_proba_to_none():
    assert sporty.drugie_zrodlo(_baza(8, 3, n=5), 'hokej', 'H', 'G', 0.80) is None


@pytest.mark.parametrize('skala, p_dz, n, oczekiwane', [
    (True, 0.78, 30, (0.78, [])),
    (False, 0.78, 30, (None, ['rozne ligi bez wspolnej skali'])),
    (True, None, 30, (None, ['brak zgodnego drugiego zrodla'])),
    (True, 0.78, 3, (None, ['brak danych rywala (3 mecz(e))'])),
    (False, None, 3, (None, ['rozne ligi bez wspolnej skali', 'brak zgodnego drugiego zrodla',
                             'brak danych rywala (3 mecz(e))'])),
])
def test_werdykt_meczu(skala, p_dz, n, oczekiwane):
    assert sporty.werdykt_meczu(skala, p_dz, n) == oczekiwane


@pytest.mark.parametrize('oferta, oczekiwane', [
    ('Stolfa Jakub', 'Jakub Stolfa'), ('Stolfa J.', 'Jakub Stolfa'), ('Jan Trefny', 'Trefny Jan'),
    ('Novak J.', None),            # dwaj Novakowie na J. — noga MNIEJ, nie zgadujemy
    ('Stolfa Petr', None),         # inne imie to inny gracz
])
def test_gracz_w_odwrotnej_kolejnosci(oferta, oczekiwane):
    # Liga Pro (29.09.2026): scores24 "Imie Nazwisko" albo "Nazwisko Imie", STS "Nazwisko Imie" / "Nazwisko I."
    pula = ['Jakub Stolfa', 'Trefny Jan', 'Jan Novak', 'Jiri Novak', 'Lukas Jindrak']
    assert sporty.resolve(oferta, pula) == oczekiwane
