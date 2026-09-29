"""Bramka drugiego zrodla (Poprawka 48) i arytmetyka EV po podatku."""
import pytest

import typuj


def _mecze(druzyna, wyniki, rywal='R'):
    """Lista (data, gosp, gosc, gole_g, gole_a) z perspektywy gospodarza."""
    return [(i, druzyna, f'{rywal}{i}', g, a) for i, (g, a) in enumerate(wyniki)]


def test_brak_drugiego_zrodla_przy_malej_probie(capsys):
    w = _mecze('H', [(1, 0)] * 5) + _mecze('A', [(0, 1)] * 10)
    assert typuj.drugie_zrodlo(w, 'H', 'A', [('1', 0.8, 0.8)]) == {}
    assert 'BRAK DRUGIEGO ZRODLA' in capsys.readouterr().out


def test_zgodne_daje_mniejsze_z_dwoch():
    # H wygrywa 8/10, A przegrywa 8/10 -> forma '1' = (9/12 + 9/12)/2 = 0.75
    w = _mecze('H', [(2, 0)] * 8 + [(0, 1)] * 2) + _mecze('A', [(0, 1)] * 8 + [(1, 0)] * 2)
    wynik = typuj.drugie_zrodlo(w, 'H', 'A', [('1', 0.80, 0.80)])
    assert wynik['1'] == pytest.approx(0.75)


def test_rozbiezne_to_none():
    w = _mecze('H', [(0, 1)] * 10) + _mecze('A', [(1, 0)] * 10)
    assert typuj.drugie_zrodlo(w, 'H', 'A', [('1', 0.80, 0.80)])['1'] is None


@pytest.mark.parametrize('dz, k, oczekiwane', [
    (None, '1X', (None, 'drugie zrodlo nie liczone')),
    ({}, '1X', (None, 'BRAK DRUGIEGO ZRODLA')),
    ({'1': 0.7}, '1X', (None, 'rynek bez drugiego zrodla')),
    ({'1X': None}, '1X', (None, 'ROZBIEZNE zrodla')),
    ({'1X': 0.8}, '1X', (0.8, None)),
])
def test_werdykt_nogi(dz, k, oczekiwane):
    assert typuj.werdykt_nogi(k, dz) == oczekiwane


def test_ev_po_podatku():
    ev, kelly = typuj.ev_kelly(0.80, 1.40)
    assert ev == pytest.approx(0.80 * 1.40 * 0.88 - 1)
    assert kelly == 0.0                      # EV < 0 -> brak stawki
    assert typuj.ev_kelly(0.5, 1.10)[1] == 0.0   # kurs po podatku < 1


def test_value_liczy_ev_z_p_po_bramce(capsys):
    # P modelu 82% daje EV > 0, ale P do kuponu 80% juz nie — noga ma odpasc
    typuj.value([('1X', 0.80, 0.82)], {'1X': 1.40}, {'1X': 0.80})
    out = capsys.readouterr().out
    assert '✔ wartość' in out and 'NIE NA KUPON: EV ≤ 0 po bramce' in out
