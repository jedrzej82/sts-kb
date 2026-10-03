"""03.10.2026 — A1(b) w kupon.py.

Raport 2026-10-03 15:00, usterka 2: kupon.py dal "DO GRY: stawka 2 zl" dla K3 na nodze
SS Monopoli (SZACUNEK, przedzial 53%-73%) i dla K5b (SaiPa, "SZACUNEK: < 10 meczow"),
bo liczyl EV z P punktowego. A1(b) wymaga EV od DOLNEGO krania przedzialu:
0,53 x 1,90 x 0,88 - 1 = -11,4% -> nogi nie ma.
"""
import pytest

import kupon


def _plik(tmp_path, wiersze, naglowek='mecz,rynek,p,kurs,szacunek,polski,marza,kryteria'):
    p = tmp_path / 'nogi.csv'
    p.write_text(naglowek + '\n' + '\n'.join(wiersze) + '\n')
    return str(p)


def test_p_min_domyslnie_dla_szacunku(tmp_path):
    """Bez kolumny p_min: noga szacunkowa dostaje p - 0,10, zwykla zostaje bez zmian."""
    d = kupon.wczytaj(_plik(tmp_path, ['A - B,X2,0.630,1.90,1,0,1.08,2',
                                       'C - D,X2,0.634,1.88,0,0,1.07,2']))
    assert d.p_min.iloc[0] == pytest.approx(0.530)
    assert d.p_min.iloc[1] == pytest.approx(0.634)


def test_p_min_jawna_kolumna_wygrywa(tmp_path):
    d = kupon.wczytaj(_plik(tmp_path, ['A - B,X2,0.630,1.90,1,0,1.08,2,0.480'],
                            naglowek='mecz,rynek,p,kurs,szacunek,polski,marza,kryteria,p_min'))
    assert d.p_min.iloc[0] == pytest.approx(0.480)


def test_p_min_nigdy_ujemne(tmp_path):
    d = kupon.wczytaj(_plik(tmp_path, ['A - B,X2,0.050,9.00,1,0,1.08,2']))
    assert d.p_min.iloc[0] >= 0.0


def test_monopoli_idzie_na_papier(tmp_path):
    """Reprodukcja z Raportu 15:00 — kupon ma byc PAPIEROWY z powodem A1(b)."""
    d = kupon.wczytaj(_plik(tmp_path, ['SS Monopoli - AC Savoia,X2,0.630,1.90,1,0,1.0822,2']))
    o = kupon._opis(d, [0])
    assert o['ev'] > 0                                   # EV punktowe bylo dodatnie — stad blad
    assert o['ev_dol'] == pytest.approx(-0.114, abs=0.002)

    class A: faza, depozyt, wydane_lacznie, lacznie = 1, 300.0, 0.0, 0.0
    stawka, powod = kupon.za_pieniadze(o, 'K3', A(), 0, 0)
    assert stawka == 0
    assert 'A1 b' in powod and 'DOLNEGO' in powod


def test_szacunek_z_duzym_zapasem_nadal_przechodzi(tmp_path):
    """Bramka ma odrzucac nogi na styk, nie kazdy szacunek — inaczej byloby to luzowanie w druga strone."""
    d = kupon.wczytaj(_plik(tmp_path, ['A - B,X2,0.800,2.20,1,0,1.05,6']))
    o = kupon._opis(d, [0])
    assert o['ev_dol'] > 0

    class A: faza, depozyt, wydane_lacznie, lacznie = 1, 300.0, 0.0, 0.0
    stawka, powod = kupon.za_pieniadze(o, 'K3', A(), 0, 0)
    assert stawka > 0 and powod is None


def test_noga_bez_szacunku_nie_jest_karana(tmp_path):
    """Noga bez flagi szacunek ma p_min = p, wiec bramka A1(b) jej nie dotyczy."""
    d = kupon.wczytaj(_plik(tmp_path, ['A - B,X2,0.634,1.88,0,0,1.07,4']))
    o = kupon._opis(d, [0])
    assert o['ev_dol'] == pytest.approx(o['ev'])


def test_margines_zgodny_z_przedzialem_typuj():
    """typuj.py drukuje przedzialy o szerokosci ok. +-10 pp — margines nie moze byc wezszy."""
    assert kupon.MARGINES_SZACUNKU >= 0.10
