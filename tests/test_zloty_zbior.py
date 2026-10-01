"""ZLOTY ZBIOR (01.10.2026): wszystkie rozne zapisy rynkow z dziennikow 20.09-01.10 (bez dat, kursow, stawek) z
oczekiwanym odczytem — staly test regresji parsera rozliczen. Kazda poprawka parsera musi przejsc CALY zbior.

stan=OBSERVATION     — nowy zapis z raportu, oczekiwany wynik jeszcze nieustalony: tylko zapisany, CI go nie ocenia.
stan=ZNANA_ANOMALIA  — potwierdzona reprodukcja, dzis dziala zle; test oczekuje porazki (xfail strict). Gdy poprawka
                       zacznie dzialac, test zglosi XPASS — wtedy zmien stan na OK.
stan=OK              — tak dziala i ma tak zostac (regresja = czerwone CI). Naprawionych wierszy NIE usuwamy."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dzienniki  # noqa: E402
import ucz  # noqa: E402

ZBIOR = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'zloty_rynki.csv'),
                    dtype=str, keep_default_na=False)


def _odczyt(w):
    if w.rodzaj == 'rynek_pilka':
        kod = dzienniki.rynek_pilka(w.rynek)
        # kod musi byc rozliczalny przez ucz.hit (inaczej noga konczy jako BRAK WYNIKU)
        return kod if ucz.hit(kod, 1, 1, None, None) is not None else f'{kod} (nierozliczalny)'
    return dzienniki._typ_zwyciezcy(w.rynek, w.gosp, w.gosc, '1', '2') or ''


@pytest.mark.parametrize('w', [pytest.param(w, id=f'{w.rodzaj}:{w.rynek}:{w.gosp}',
                                            marks=[pytest.mark.xfail(strict=True, reason=w.uwaga)] if w.stan == 'ZNANA_ANOMALIA' else [])
                               for w in ZBIOR[ZBIOR.stan != 'OBSERVATION'].itertuples()])
def test_zloty_zbior(w):
    assert _odczyt(w) == w.oczekiwane


def test_zbior_kompletny():
    assert len(ZBIOR) >= 50 and set(ZBIOR.stan) <= {'OK', 'ZNANA_ANOMALIA', 'OBSERVATION'}
    # ZNANA_ANOMALIA = potwierdzona reprodukcja: musi miec opis (uwaga); OBSERVATION — jeszcze nie
    assert not ((ZBIOR.stan == 'ZNANA_ANOMALIA') & (ZBIOR.uwaga == '')).any()
    assert not ZBIOR.duplicated(['rodzaj', 'rynek', 'gosp', 'gosc']).any()
