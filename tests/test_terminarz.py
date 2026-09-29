import pandas as pd

import terminarz

T = pd.DataFrame([
    dict(data='2026-09-29', godzina_utc='23:00', sport='football', kraj='Colombia', turniej='Primera B',
         gosp='Independiente Yumbo', gosc='Real Cundinamarca', status='2'),
    dict(data='2026-09-29', godzina_utc='18:30', sport='football', kraj='Germany', turniej='Bundesliga',
         gosp='Bayern Munich', gosc='Borussia Dortmund', status='2'),
    dict(data='2026-09-29', godzina_utc='16:00', sport='football', kraj='Sweden', turniej='U21 Allsvenskan',
         gosp='Hammarby U21', gosc='AIK U21', status='2'),
    dict(data='2026-09-30', godzina_utc='19:00', sport='basketball', kraj='Spain', turniej='ACB',
         gosp='Real Madrid', gosc='Barcelona', status='2'),
])


def test_para_wskazuje_kraj_i_lige():
    m = terminarz.znajdz('Independiente Yumbo', 'Real Cundinamarca', T)
    assert (m['kraj'], m['turniej']) == ('Colombia', 'Primera B')


def test_polskie_miasto_i_forma_prawna():
    m = terminarz.znajdz('Bayern Monachium', 'BV Borussia Dortmund', T, data='2026-09-29')
    assert m and m['kraj'] == 'Germany'


def test_mlodziez_nie_pasuje_do_seniorow():
    assert terminarz.znajdz('Hammarby', 'AIK', T) is None


def test_sport_i_data_filtruja():
    assert terminarz.znajdz('Real Madrid', 'Barcelona', T) is None                   # to koszykowka
    assert terminarz.znajdz('Real Madrid', 'Barcelona', T, sport='basketball')['kraj'] == 'Spain'
    assert terminarz.znajdz('Bayern Munich', 'Borussia Dortmund', T, data='2026-10-05') is None


def test_jeden_czlon_nie_wystarcza():
    assert not terminarz.pasuje('Independiente Medellin', 'Independiente Yumbo')


def test_brak_pliku(tmp_path):
    assert terminarz.wczytaj(str(tmp_path / 'brak.csv.gz')) is None
