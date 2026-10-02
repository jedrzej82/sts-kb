"""bt_drugie_zrodlo.intl_wiersze — backtest bramki drugiego zrodla dla reprezentacji (typuj.intl)."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bt_drugie_zrodlo as bt  # noqa: E402


def _intl(n=1500, seed=1):
    rng = np.random.default_rng(seed)
    sila = {f'T{i}': s for i, s in enumerate(np.linspace(-1, 1, 20))}
    dni = pd.date_range('2012-01-01', '2025-06-30', periods=n)
    w = []
    for d in dni:
        h, a = rng.choice(list(sila), 2, replace=False)
        w.append(dict(date=str(d.date()), home_team=h, away_team=a, home_score=rng.poisson(np.exp(0.3 + sila[h] - sila[a])),
                      away_score=rng.poisson(np.exp(0.1 + sila[a] - sila[h])), tournament='Nations League', neutral=False))
    return pd.DataFrame(w)


def test_intl_wiersze_bez_przecieku_i_zgodnosc():
    d = bt.intl_wiersze(_intl(), od='2024-01-01')
    assert len(d) > 50
    assert (d.data >= '2024-01-01').all()                    # tylko mecze testowe
    assert (d.p_model >= 0.70).all()
    assert set(d.rynek) <= set(bt.RYNKI_P48)
    # zgodne = |P_model - P_forma| <= 10 pp; forma z 10 meczow obu druzyn = wielokrotnosci 1/24
    assert (d.zgodne == ((d.p_model - d.p_forma).abs() <= bt.PROG)).all()
    assert np.allclose(d.p_forma * 24, (d.p_forma * 24).round())
    assert set(d.traf) <= {0, 1}
