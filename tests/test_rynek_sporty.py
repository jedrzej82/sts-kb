"""03.10.2026 — filtr model-rynek (6.4) w rynek.py i w sporty.py typuj.

Raport 2026-10-03 18:00: STS mial w ofercie dla 11 meczow hokeja i recznej WYLACZNIE
rynek Mecz 1/X/2 (czas regulaminowy, P121.2), a sporty.py wydawal werdykt dla zwyciezcy
Z DOGRYWKA. Doslowne zastosowanie werdyktu dawalo EV +24,9% / +9,1% / +9,0% zamiast
+3,2% / -9,8% / -10,0% po dopasowaniu rynku.
"""
import pytest

import rynek


def test_kursy_z_argv_wyciaga_i_zostawia_reszte():
    a, k = rynek.kursy_z_argv(['typuj', 'hokej', 'A', 'B', '--kurs', '1=1.72', '--kurs', 'X=4.25'])
    assert a == ['typuj', 'hokej', 'A', 'B']
    assert k == {'1': 1.72, 'X': 4.25}


def test_kursy_z_argv_pomija_smieci():
    a, k = rynek.kursy_z_argv(['typuj', '--kurs', 'X2=abc', '--kurs', '1=1.50'])
    assert k == {'1': 1.50} and a == ['typuj']


def test_kursy_z_argv_bez_kursow():
    a, k = rynek.kursy_z_argv(['typuj', 'hokej', 'A', 'B'])
    assert k == {} and a == ['typuj', 'hokej', 'A', 'B']


def test_z1_z2_to_rynek_dwustronny():
    """Zwyciezca meczu (z dogrywka) — ksiega z pary Z1/Z2."""
    kursy = {'Z1': 1.40, 'Z2': 2.90}
    assert rynek.p_rynku('Z1', kursy) == pytest.approx(0.674, abs=0.003)
    assert rynek.p_rynku('Z1', kursy) + rynek.p_rynku('Z2', kursy) == pytest.approx(1.0)


def test_hokej_na_wlasciwym_rynku_przechodzi():
    """SCL Tigers: P 72,1% (z dogrywka) vs rynek Z1 67,4% = 4,7 pp — filtr nie reaguje."""
    assert rynek.filtr_model_rynek('Z1', 0.721, {'Z1': 1.40, 'Z2': 2.90}) is None


def test_vitoria_porto_odrzucone():
    """03.10, reczna: model 42,0% vs rynek 5,7% = 36,3 pp — klasyczny 'brak danych rywala'."""
    powod = rynek.filtr_model_rynek('1', 0.420, {'1': 17.0, 'X': 15.0, '2': 1.05})
    assert powod is not None and 'FILTR MODEL-RYNEK' in powod


def test_filtr_bez_kursow_nic_nie_robi():
    assert rynek.filtr_model_rynek('1', 0.9, {}) is None
    assert rynek.filtr_model_rynek('1', 0.9, None) is None


def test_kurs_ponizej_jedynki_ignorowany():
    """Kurs <= 1 to blad odczytu, nie rynek — nie liczymy z niego ksiegi."""
    assert rynek.p_rynku('Z1', {'Z1': 1.0, 'Z2': 2.90}) is None
    assert rynek.p_rynku('Z1', {'Z1': 1.40, 'Z2': 0.5}) is None


def test_progi_zgodne_z_instrukcja():
    assert rynek.MAX_ROZBIEZNOSC_RYNEK <= 0.15


def test_typuj_reeksportuje_filtr():
    """typuj.py ma dalej wystawiac te nazwy — testy i starsze wywolania po nie siegaja."""
    import typuj
    assert typuj.filtr_model_rynek is rynek.filtr_model_rynek
    assert typuj.p_rynku is rynek.p_rynku
