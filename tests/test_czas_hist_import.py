"""30.09.2026 (czas przebiegu): hist_import 330 s -> 90 s. Zapamietywanie znaczniki()/_czlony() i szybsze
_scal_nazwy_rozgrywek nie moga zmienic wyniku."""
import pandas as pd

import nazwy
import terminarz
import zewn


def test_znaczniki_ten_sam_wynik_dla_nie_napisu():
    assert nazwy.znaczniki(float('nan')) == nazwy.znaczniki('nan') == ()
    assert nazwy.znaczniki('Barcelona (K)') == ('kobiety',)
    assert nazwy.znaczniki('Zenit-2') == ('rezerwy',)
    assert nazwy.znaczniki('Zenit-2') is nazwy.znaczniki('Zenit-2')   # z pamieci


def test_czlony_niezmienne():
    a = terminarz._czlony('Bayern Monachium')
    assert isinstance(a, frozenset) and {'bayern', 'monachium', 'munich'} <= a
    assert terminarz._czlony('Junior FC') == {'junior'}
    assert terminarz.pasuje('Bayern Monachium', 'Bayern Munich')


def _m(rows):
    return pd.DataFrame(rows, columns=['data', 'sport', 'kraj', 'turniej', 'gosp', 'gosc', 'pg', 'pa'])


def test_scal_przemianowanie_i_bez_bledu_dla_pojedynczych():
    r = [('2026-09-20', 'pilka', 'Andorra', 'Super League', 'A', 'B', 1, 0),
         ('2026-09-20', 'pilka', 'Andorra', 'Primera Divisio', 'A', 'B', 1, 0),
         ('2026-09-21', 'pilka', 'Andorra', 'Primera Divisio', 'C', 'D', 2, 2),
         ('2026-09-21', 'pilka', 'Andorra', 'Primera Divisio', 'E', 'F', 0, 3),
         ('2026-09-22', 'pilka', 'Andorra', 'Segunda Divisio', 'G', 'H', 1, 1)]
    out = zewn._scal_nazwy_rozgrywek(_m(r))
    assert set(out.turniej) == {'Primera Divisio', 'Segunda Divisio'}
    assert len(out) == 5 and '_wez' not in out.columns


def test_scal_nic_wspolnego_bez_zmian():
    r = [('2026-09-20', 'pilka', 'Andorra', 'Primera Divisio', 'A', 'B', 1, 0),
         ('2026-09-21', 'pilka', 'Andorra', 'Segunda Divisio', 'C', 'D', 2, 2)]
    out = zewn._scal_nazwy_rozgrywek(_m(r))
    assert list(out.turniej) == ['Primera Divisio', 'Segunda Divisio']
