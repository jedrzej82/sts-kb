import pandas as pd
import pytest

import clv


def test_przygotuj_liczy_clv_i_pomija_braki():
    df = pd.DataFrame({'kurs_typu': ['2,10', '1.50', '1.80'], 'kurs_zamkniecia': ['2.00', '', '2.00']})
    d = clv.przygotuj(df)
    assert list(d.clv.round(4)) == [0.05, -0.1]      # pusty kurs zamkniecia to brak pomiaru, nie zero


def test_mala_proba_tylko_informacyjnie():
    assert 'za malo' in clv.podsumuj([0.05] * 10 + [0.04] * 10)['werdykt']


def test_istotnie_dodatnie():
    s = clv.podsumuj([0.03, 0.05, 0.02, 0.04, 0.06, 0.01] * 20)
    assert s['n'] == 120 and s['p'] < 0.05 and 'istotnie dodatnie' in s['werdykt']


def test_ujemne():
    assert 'ujemne' in clv.podsumuj([-0.03, -0.01, 0.01, -0.05] * 10)['werdykt']


def test_brak_danych():
    assert clv.podsumuj([])['werdykt'] == 'brak pomiaru'


def test_main_bez_kolumn(tmp_path):
    f = tmp_path / 't.csv'; f.write_text('data,kurs\n2026-09-29,1.5\n')
    with pytest.raises(SystemExit, match='BRAK KOLUMN'):
        clv.main([str(f)])


def test_dopisz_typ_scala_kolumny_ze_starym_logiem(tmp_path):
    f = tmp_path / 'typy_log.csv'
    f.write_text('data,gosp,gość,rynek,p,trafiony\n2026-09-28,A,B,1X,0.8,1\n')
    clv.dopisz_typ(str(f), dict(data='2026-09-29', gosp='C', gość='D', rynek='O1.5', p=0.78, trafiony=None), ['1,35', 'tak'])
    clv.dopisz_typ(str(f), dict(data='2026-09-29', gosp='E', gość='F', rynek='1', p=0.7, trafiony=None), [])
    d = pd.read_csv(f)
    assert list(d.gosp) == ['A', 'C', 'E']
    assert d.kurs_typu.iloc[1] == 1.35 and d.pieniadze.iloc[1] == 1
    assert pd.isna(d.kurs_typu.iloc[0]) and pd.isna(d.kurs_typu.iloc[2])
