"""30.09.2026 (przeglad skryptow kalibracji): PAV zamiast biezacego maksimum."""
import numpy as np

import kalib


def test_pav_usrednia_zamiast_podnosic():
    y = kalib.pav([0.5, 0.7, 0.6, 0.8], [1, 1, 1, 1])
    assert np.allclose(y, [0.5, 0.65, 0.65, 0.8])                 # biezace maksimum dawalo 0.7 w trzecim koszu
    assert np.allclose(kalib.pav([0.6, 0.5], [3, 1]), [0.575, 0.575])   # wagi = liczba meczow
    y = kalib.pav(np.random.default_rng(0).random(20), np.ones(20))
    assert (np.diff(y) >= -1e-12).all()


def test_tabela_tenisa_monotoniczna_i_nie_wyzsza_niz_p_model():
    import pandas as pd, os
    c = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tenis_kalibracja.csv'))
    assert (c.p_kalibr.diff().dropna() >= -1e-9).all() and (c.p_kalibr <= c.p_model + 0.01).all()
