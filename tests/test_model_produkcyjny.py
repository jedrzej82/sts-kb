"""30.09.2026: test „na slepo” (test_ostatnie.py) i typowanie maja liczyc P TYM SAMYM kodem."""
import os, sys
import pandas as pd
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import typuj, sporty


def test_kalibruj_v5n():
    KR = pd.DataFrame({'rynek': ['1', '1', 'U3.5'], 'przedzial': ['[0.7, 0.8)', '[0.9, 1.01)', '[0.7, 0.8)'],
                       'przesuniecie': [-0.01, -0.02, -0.02]})
    assert abs(typuj.kalibruj_v5n(KR, '1', 0.75) - 0.74) < 1e-9
    assert abs(typuj.kalibruj_v5n(KR, '1', 0.95) - 0.93) < 1e-9
    assert abs(typuj.kalibruj_v5n(KR, '1', 0.85) - 0.85) < 1e-9          # brak przedzialu = bez korekty
    assert abs(typuj.kalibruj_v5n(KR, 'U3.5', 0.75) - 0.71) < 1e-9       # „ponizej”: co najmniej −4 pp
    assert abs(typuj.kalibruj_v5n(KR, 'U2.5', 0.60) - 0.56) < 1e-9


def test_p_gospodarza_nie_zmienia_elo():
    d = pd.DataFrame({'data': pd.to_datetime(['2026-01-01', '2026-01-08', '2026-09-20']), 'sport': 'koszykówka',
                      'liga': 'X | L', 'gosp': ['A', 'B', 'A'], 'gosc': ['B', 'A', 'C'],
                      'pg': [90, 80, 85], 'pa': [80, 85, 70], 'dogrywka': 0})
    R = {'A': 1600.0, 'B': 1450.0}; L_ = {'A': pd.Timestamp('2026-09-20'), 'B': pd.Timestamp('2026-01-08')}
    p, _, e, _ = sporty.p_gospodarza(d, 'koszykówka', R, L_, 0, False, 'A', 'B', dzien=pd.Timestamp('2026-09-30'))
    assert R == {'A': 1600.0, 'B': 1450.0}                                 # regresja B (> 90 dni) liczona na kopii
    e_bez = 1 / (1 + 10 ** ((1450 - 1600) / 400))
    e_reg = 1 / (1 + 10 ** ((1500 + (1450 - 1500) * 0.67 - 1600) / 400))  # B po przerwie > 90 dni blizej 1500
    assert abs(e - e_reg) < 1e-12 and e < e_bez and 0 < p < 1


def test_test_ostatnie_bez_starego_modelu():
    s = open(os.path.join(HERE, 'test_ostatnie.py'), encoding='utf-8').read()
    for stare in ('load_calibration', 'fit_elo_glm', 'blend(', "'blend_weight.txt')).read()"):
        assert stare not in s, stare
    kod = s.split('def pilka')[1].split('def tenis')[0]
    for nowe in ('kalibruj_v5n', 'korekta_wlasna', 'E.comb', 'p_gospodarza'):
        assert nowe in kod, nowe


def test_pi_srednia_ligi_nie_zeruje_lambdy():
    """Liga z 3 meczami 0:0 dawala wspolczynnik ligi 0 -> λ = 0 (214 meczow w backteście)."""
    import numpy as np, pi
    rng = np.random.default_rng(0)
    n = 400
    d = pd.DataFrame({'Division': ['DUZA'] * n + ['MALA'] * 3, 'gd_hat': np.r_[rng.normal(0, 1, n), [0.0, 0.1, -0.1]],
                      'FTHome': np.r_[rng.poisson(1.5, n), [0, 0, 0]], 'FTAway': np.r_[rng.poisson(1.1, n), [0, 0, 0]]})
    g = pi.fit_pi_glm(d)
    lh, la = pi.pi_lambdas(g, 0.0, 'MALA')
    assert lh > 0.5 and la > 0.5                                  # sciagniete do sredniej globalnej, nie 0
    lh2, _ = pi.pi_lambdas(g, 0.0, 'DUZA')
    assert abs(g['league']['DUZA'][0] - d[d.Division == 'DUZA'].FTHome.mean()) < 0.05   # duza liga prawie bez zmian


def test_xi_test_klucz_cache():
    s = open(os.path.join(HERE, 'xi_test.py'), encoding='utf-8').read()
    assert "build_rows(tag=f'_hl{hl}')" in s and 'os.rename(' not in s
    import inspect, ensemble
    assert 'tag' in inspect.signature(ensemble.build_rows).parameters
