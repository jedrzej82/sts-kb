"""zewn._hokej_fs_nazwy: reczne pary Flashscore -> 365 dla hokeja (29.09.2026)."""
import pandas as pd

import zewn


def test_reczne_pary_hokej():
    s = pd.DataFrame({'sport': ['hockey'] * 4, 'kraj': ['Canada', 'Canada', 'Netherlands', 'Netherlands'],
                      'turniej': ['OHL', 'OHL', 'Eredivisie', 'Eredivisie'],
                      'gosp': ['Sault Ste. Marie Greyhounds', 'Soo Greyhounds', 'Hys The Hague', 'Den Haag'],
                      'gosc': ['Erie Otters', 'Erie Otters', 'Tilburg Trappers', 'Tilburg Trappers']})
    fs = pd.Series([False, True, False, True])
    w = zewn._hokej_fs_nazwy(s, fs)
    assert w.gosp.tolist() == ['Sault Ste. Marie Greyhounds'] * 2 + ['Hys The Hague'] * 2
