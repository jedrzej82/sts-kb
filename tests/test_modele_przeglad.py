"""30.09.2026 (przeglad modeli): korekta wlasna raz, cache ze stanem bazy, mecz bez wyniku nie psuje dopasowania."""
import os
import time

import numpy as np
import pandas as pd

import model
import typuj


def test_korekta_wlasna_tylko_jeden_przedzial():
    kor = pd.DataFrame({'rynek': ['1X', '1X'], 'przedział': ['[0.7,0.75)', '[0.75,0.8)'],
                        'trafność': [0.80, 0.95], 'waga': [2 / 3, 2 / 3]})
    pc = typuj.korekta_wlasna(0.72, kor)
    assert abs(pc - (0.72 / 3 + 0.80 * 2 / 3)) < 1e-12                 # 0,7733; dotad dalej do 0,8911
    assert typuj.korekta_wlasna(0.60, kor) == 0.60


def test_cache_widzi_przebudowe_bazy(tmp_path, monkeypatch):
    monkeypatch.setattr(typuj, 'HERE', str(tmp_path))
    kb = tmp_path / 'kb.sqlite'; kb.write_bytes(b'a')
    assert typuj.cached('x', lambda: 1) == 1 and typuj.cached('x', lambda: 2) == 1
    kb.write_bytes(b'ab'); t = time.time() + 5; os.utime(kb, (t, t))     # przebudowa bazy
    assert typuj.cached('x', lambda: 3) == 3


def _liga(n=400, seed=0):
    rng = np.random.default_rng(seed); dr = list('ABCDEFGH'); w = []
    for i in range(n):
        h, a = rng.choice(dr, 2, replace=False)
        w.append((pd.Timestamp('2025-01-01') + pd.Timedelta(days=i), h, a, rng.poisson(1.6), rng.poisson(1.1)))
    return pd.DataFrame(w, columns=['MatchDate', 'HomeTeam', 'AwayTeam', 'FTHome', 'FTAway'])


def test_mecz_bez_wyniku_nie_zeruje_dopasowania():
    d = _liga(); ref = d.MatchDate.max() + pd.Timedelta(days=1)
    a = model.fit_dc(d, ref)
    d2 = pd.concat([d, pd.DataFrame([(ref - pd.Timedelta(days=1), 'A', 'B', np.nan, np.nan)], columns=d.columns)])
    b = model.fit_dc(d2, ref)
    assert b['home'] == a['home'] and b['home'] != 0.25
