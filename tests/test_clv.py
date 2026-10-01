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


def test_archiwum_arkuszy(tmp_path, monkeypatch):
    import tarfile, przebieg
    (tmp_path / 'statystyki_druzyn.csv').write_text('a,b\n1,2\n')
    monkeypatch.setattr(przebieg, 'HERE', str(tmp_path))
    assert przebieg.archiwum_arkuszy() == 0
    f = next(tmp_path.glob('arkusze_*.tar.gz'))
    assert tarfile.open(f).getnames() == ['statystyki_druzyn.csv']


def test_pieniadze_zapisane_jako_float_to_nadal_pieniadze(tmp_path, capsys):
    # 30.09.2026 (przeglad): dopisz_typ do starego logu bez kolumny `pieniadze` — pandas zapisuje „1.0”,
    # a _tak porownywal tekst i liczyl zaklady za pieniadze jako papierowe
    f = tmp_path / 'typy_log.csv'
    pd.DataFrame([{'data': '2026-09-28', 'mecz': 'x', 'kurs_zamkniecia': 1.5}]).to_csv(f, index=False)
    clv.dopisz_typ(str(f), {'data': '2026-09-29', 'mecz': 'a', 'kurs_zamkniecia': 1.30}, ['1,35', 'tak'])
    clv.dopisz_typ(str(f), {'data': '2026-09-29', 'mecz': 'b', 'kurs_zamkniecia': 1.90}, ['2,00', 'nie'])
    assert '1.0' in open(f).read()
    assert clv._tak('1.0') and clv._tak(1) and clv._tak('tak') and not clv._tak('0.0') and not clv._tak('nan')
    clv.main([str(f)])
    out = capsys.readouterr().out
    assert 'za pieniadze n=1' in out and 'papierowe    n=1' in out


def test_main_ako_log_kurs_i_bez_razem(tmp_path, capsys):
    """01.10.2026: ako_log ma kolumne „kurs” i wiersze RAZEM (kupony) — liczymy CLV samych nog."""
    f = tmp_path / 'ako_log.csv'
    pd.DataFrame(dict(data=['2026-09-30'] * 3, tag=['K5'] * 3, noga_nr=['1', '2', 'RAZEM'],
                      kurs=['2.10', '1,50', '3.15'], kurs_zamkniecia=['2.00', '1.50', '2.80'])).to_csv(f, index=False)
    clv.main([str(f)])
    out = capsys.readouterr().out
    assert 'CLV — 2 nog z kursem zamkniecia (z 2 wierszy)' in out


def test_ako_log_pieniadze_rynek_i_jedna_noga_raz(capsys):
    """01.10.2026: ako_log — pieniadze z wiersza RAZEM, rynek ujednolicony, ta sama noga w dwoch kuponach liczona raz."""
    import io
    import clv
    csv = ('data,godzina_uruchomienia,tag,nr_kuponu,noga_nr,zdarzenie,rynek,kurs,kurs_zamkniecia,status,uwaga\n'
           '2026-09-24,18:00,AKOP,AKOP1,4,Liechtenstein - Litwa,Liczba goli powyzej 1.5,1.48,1.52,,\n'
           '2026-09-24,18:00,AKOP,AKOP1,RAZEM,,,2.10,,PAPIEROWY,\n'
           '2026-09-24,18:00,K5c,K5c,2,Liechtenstein - Litwa,Liczba goli powyzej 1.5,1.48,1.52,,\n'
           '2026-09-24,18:00,K5c,K5c,RAZEM,,,2.60,,,stawka 2 zl\n'
           '2026-09-24,18:50,AKOP,1,2,Tunezja - Uganda,powyzej 1.5 gola,1.33,1.30,,\n'
           '2026-09-24,18:50,AKOP,1,RAZEM,,,2.00,,PAPIEROWY,stawka 0\n')
    d = pd.read_csv(io.StringIO(csv), dtype=str, keep_default_na=False).rename(columns={'kurs': 'kurs_typu'})
    n = clv.przygotuj_ako(d)
    assert len(n) == 2                                             # Liechtenstein raz, nie dwa
    w = {r.zdarzenie: (r.rynek, r.pieniadze) for r in n.itertuples()}
    assert w == {'Liechtenstein - Litwa': ('O1.5', 1), 'Tunezja - Uganda': ('O1.5', 0)}
