"""30.09.2026 (proba generalna przebiegu na danych z Dysku): usterki z wyjscia skryptow."""
import pandas as pd

import linie
import nazwy
import terminarz


def test_rynki_setowe_spojne(tmp_path, monkeypatch):
    lc = tmp_path / 'linie_kalibracja.csv'
    pd.DataFrame({'sport': 'tenis', 'rodzina': 'handicap setowy', 'p_model': [0.0, 1.0], 'p_kalibr': [0.0, 0.9],
                  'n': [200, 200]}).to_csv(lc, index=False)
    monkeypatch.setattr(linie, 'CAL', str(lc))
    m = linie.rynki_setowe(0.78, 0.71)
    assert abs(m['A handicap -1,5 seta'] - m['2:0']) < 1e-12                       # to samo zdarzenie
    assert abs(m['poniżej 2,5 seta'] - (m['2:0'] + m['0:2'])) < 1e-12
    assert abs(m['2:0'] + m['2:1'] + m['1:2'] + m['0:2'] - 1) < 1e-12
    assert abs(m['2:0'] + m['2:1'] - 0.71) < 1e-9                                 # P meczu = skalibrowane


def test_linie_strony_sumuja_sie_do_100(tmp_path, monkeypatch):
    lc = tmp_path / 'linie_kalibracja.csv'
    pd.DataFrame({'sport': 'hokej', 'rodzina': ['suma O'] * 2 + ['suma U'] * 2, 'p_model': [0.0, 1.0] * 2,
                  'p_kalibr': [0.1, 0.95, 0.0, 0.8], 'n': [200] * 4}).to_csv(lc, index=False)
    monkeypatch.setattr(linie, 'CAL', str(lc))
    po = linie.obie_strony('hokej', 'suma O', 'suma U', 0.7)
    assert 0 < po < 1 and abs(po + (1 - po) - 1) < 1e-12
    assert abs(linie.cal_apply('hokej', 'suma O', 0.7) + linie.cal_apply('hokej', 'suma U', 0.3) - 1) > 0.05  # dotad


def test_terminarz_junior_fc():
    T = pd.DataFrame({'data': ['2026-09-30'], 'sport': ['football'], 'kraj': ['Colombia'], 'turniej': ['Primera A'],
                      'gosp': ['Atletico Nacional'], 'gosc': ['Junior FC']})
    assert terminarz.znajdz('Atletico Nacional', 'Junior FC', T)['kraj'] == 'Colombia'
    assert terminarz.znajdz('Atletico Nacional', 'Junior', T) is not None


def test_znacznik_po_laczniku_tylko_cyfra():
    assert nazwy.znaczniki('Zenit-2') == ('rezerwy',) and nazwy.znaczniki('Dinamo-II') == ('rezerwy',)
    assert nazwy.znaczniki('Kyong-Jun M.') == () and nazwy.znaczniki('Jang Y.-B.') == () and nazwy.znaczniki('Hung J.-K.') == ()
