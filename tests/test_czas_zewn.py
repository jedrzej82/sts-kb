"""30.09.2026 (czas przebiegu): klucz wyniku sklejany kolumnami, _przemianowane_dubli tylko po grupach z >= 2 rywalami.
Zachowanie bez zmian: dwumecz baseballu zostaje, powtorzony zapis i sprzeczny wynik w pilce — jeden wiersz."""
import gzip

import pandas as pd

import zewn


def test_czytaj_dwumecz_baseball_i_duble(tmp_path, monkeypatch):
    csv = ('data,sport,kraj,turniej,gosp,gosc,pg,pa\n'
           '2026-09-20,baseball,USA,MLB,A,B,3,1\n'
           '2026-09-20,baseball,USA,MLB,A,B,2,5\n'     # drugi mecz dwumeczu — zostaje
           '2026-09-20,baseball,USA,MLB,A,B,3,1\n'     # powtorzony zapis — odsiany
           '2026-09-20,football,Spain,LaLiga,C,D,0,0\n'
           '2026-09-20,football,Spain,LaLiga,C,D,2,0\n')  # ten sam mecz, inny wynik — jeden wiersz
    (tmp_path / 'wyniki_test_inne_2026-09.csv.gz').write_bytes(gzip.compress(csv.encode()))
    monkeypatch.setattr(zewn, 'ZD', str(tmp_path))
    d = zewn.czytaj('wyniki_test_inne_2026-09.csv')
    b = d[d.sport == 'baseball']
    assert len(b) == 2 and set(zip(b.pg.astype(str), b.pa.astype(str))) == {('3', '1'), ('2', '5')}
    assert (d.sport == 'football').sum() == 1


def test_przemianowane_dubli_ta_sama_druzyna():
    d = pd.DataFrame(dict(data=['2026-09-20'] * 3 + ['2026-09-21'], sport=['koszykówka'] * 4, liga=['X'] * 4,
                          gosp=['Maxima Roma', 'Virtus Roma', 'Karhu', 'Maxima Roma'],
                          gosc=['Cluj', 'Cluj', 'Kouvot', 'Cluj'], pg=[88, 88, 70, 90], pa=[80, 80, 71, 85]))
    out = zewn._przemianowane_dubli(d)
    assert len(out) == 3 and 'Virtus Roma' not in set(out.gosp)   # rzadsza nazwa odpada, reszta bez zmian
