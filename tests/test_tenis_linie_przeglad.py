"""30.09.2026 (przeglad tenis.py / linie.py): kalibracja raz, bo5 po kalibracji, bez zgadywania nazw."""
import pandas as pd
import pytest

import linie
import sporty
import tenis


def _cal(tmp_path, monkeypatch):
    f = tmp_path / 'tenis_kalibracja.csv'
    pd.DataFrame({'p_model': [0.5, 0.9, 0.99], 'p_kalibr': [0.5, 0.8, 0.85]}).to_csv(f, index=False)
    monkeypatch.setattr(tenis, 'CAL', str(f))


ST = {'R': {'A': 1900., 'B': 1500.}, 'Rs': {}, 'N': {'A': 100, 'B': 100}, 'last': {}}


def test_bo5_liczone_po_kalibracji(tmp_path, monkeypatch):
    _cal(tmp_path, monkeypatch)
    p3, pc3 = tenis.p_skalibr(ST, 'A', 'B', 'Hard')
    p5, pc5 = tenis.p_skalibr(ST, 'A', 'B', 'Hard', bo5=True)
    assert abs(tenis.na_bo5(0.3) + tenis.na_bo5(0.7) - 1) < 1e-12
    assert pc5 == pytest.approx(tenis.na_bo5(pc3)) and pc5 > pc3            # dotad pc5 == pc3 (plaska krzywa)
    _, pcb = tenis.p_skalibr(ST, 'B', 'A', 'Hard', bo5=True)
    assert pcb == pytest.approx(1 - pc5)


def test_samo_nazwisko_bez_zgadywania(monkeypatch):
    pula = {'Qiang Wang', 'Xinyu Wang', 'Iga Swiatek'}
    monkeypatch.setattr(tenis, 'OSTATNI', {})
    assert tenis.resolve('Wang', pula) is None                              # dotad: najczesciej grajacy
    monkeypatch.setattr(tenis, 'OSTATNI', {'Xinyu Wang': '2026-09-20', 'Qiang Wang': '2019-01-01'})
    assert tenis.resolve('Wang', pula) == 'Xinyu Wang'                     # jedyny aktywny
    assert tenis.resolve('Swiatek', pula) == 'Iga Swiatek'


def test_linie_tenis_kalibracja_linii_raz(tmp_path, monkeypatch, capsys):
    _cal(tmp_path, monkeypatch)
    lc = tmp_path / 'linie_kalibracja.csv'
    pd.DataFrame({'sport': 'tenis', 'rodzina': 'handicap setowy', 'p_model': [0.0, 1.0], 'p_kalibr': [0.0, 0.9],
                  'n': [200, 200]}).to_csv(lc, index=False)
    monkeypatch.setattr(linie, 'CAL', str(lc))
    monkeypatch.setattr(tenis, 'state', lambda: ST)
    monkeypatch.setattr(tenis, 'resolve', lambda n, p: n)
    linie.main(['tenis', 'A', 'B'])
    wiersz = [x for x in capsys.readouterr().out.splitlines() if 'A handicap -1,5' in x][0]
    p = tenis.p_win(ST, 'A', 'B', 'Hard')
    oczek = 0.9 * linie.tennis_markets(p)['A handicap -1,5 seta']           # surowe P -> tabela linii, raz
    assert f'{oczek:.1%}' in wiersz


def test_linie_mapy_nieznana_druzyna_to_stop(monkeypatch):
    monkeypatch.setattr(sporty, 'load', lambda: pd.DataFrame())
    monkeypatch.setattr(sporty, 'elo', lambda d, s: ({'Natus Vincere': 1600., 'G2': 1550.}, {}, 0))
    with pytest.raises(SystemExit):
        linie.main(['mapy', 'esport_cs2', 'Natus Vincere', 'Zupelnie Nieznana Druzyna'])
