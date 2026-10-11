"""Raport 11.10 12:00.
  9. nogi.csv z PUSTA kolumna marza: kupon.py bral ja jako 1,0, wiec KUPON DNIA / AKO PILKA / AKO BONUS dostaly nogi z marza
     > 110% (Palmeiras – Corinthians 110,3%, Ruzomberok – Zilina 110,4%). Teraz: pusta marza = nieznana — noga nie przechodzi
     filtra 6.3 i nie idzie za pieniadze; typuj.py wpisuje marze z kursow 1/X/2."""
import pandas as pd

import kupon
import typuj


def _plik(tmp_path, w):
    f = tmp_path / 'nogi.csv'
    pd.DataFrame(w, columns=['mecz', 'rynek', 'p', 'kurs', 'szacunek', 'polski', 'marza', 'kryteria', 'sport', 'ev_dodatni']).to_csv(f, index=False)
    return str(f)


def test_pusta_marza_nie_przechodzi_filtra_kuponu_dnia(tmp_path):
    w = kupon.wczytaj(_plik(tmp_path, [
        ('Palmeiras - Corinthians', '1X', 0.92, 1.12, 0, 0, '', '', 'pilka', 0),       # prawdziwa marza 110,3%
        ('Ruzomberok - Zilina', 'X2', 0.91, 1.15, 0, 0, '', '', 'pilka', 0),
        ('A - B', '12', 0.88, 1.20, 0, 0, '1.06', '', 'pilka', 0),
        ('C - D', 'U4.5', 0.87, 1.18, 0, 0, '1.07', '', 'pilka', 0)]))
    o = kupon.kupon_dnia(w)
    assert o is not None and {w.at[i, 'mecz'] for i in o['nogi']} == {'A - B', 'C - D'}   # przed: Palmeiras + Ruzomberok
    assert w.marza.isna().sum() == 2


def test_pusta_marza_nie_za_pieniadze(tmp_path):
    w = kupon.wczytaj(_plik(tmp_path, [('A - B', '1', 0.70, 1.80, 0, 0, '', '6', 'pilka', 1)]))
    o = kupon._opis(w, [0])
    assert o['marza_max'] == float('inf')
    a = type('A', (), dict(faza=1, depozyt=50.0, wydane_lacznie=0, lacznie=0))()
    assert kupon.za_pieniadze(o, 'K3', a, 0, 0) == (0, 'marza nieznana (pusta kolumna marza w nogi.csv; 6.3)')


def test_typuj_liczy_marze_z_1x2():
    assert typuj._marza_1x2({'1': 2.0, 'X': 3.4, '2': 3.8}) == f'{1 / 2.0 + 1 / 3.4 + 1 / 3.8:.4f}'
    assert typuj._marza_1x2({'1': 2.0, 'X': 3.4}) == ''
