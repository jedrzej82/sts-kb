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


def test_dwa_zrodla_flashscore_pierwszy():
    # te same mecze w dwoch zrodlach z roznymi nazwami ligi — nie moga dac „kilku kandydatow”
    fs = T.assign(kraj=T.kraj.str.upper(), turniej='Liga FS', zrodlo='fs')
    t = pd.concat([fs, T.assign(zrodlo='365')], ignore_index=True)
    m = terminarz.znajdz('Independiente Yumbo', 'Real Cundinamarca', t)
    assert (m['kraj'], m['turniej']) == ('COLOMBIA', 'Liga FS')
    # mecz tylko w 365scores nadal znaleziony
    t2 = pd.concat([fs.iloc[1:], T.assign(zrodlo='365')], ignore_index=True)
    assert terminarz.znajdz('Independiente Yumbo', 'Real Cundinamarca', t2)['kraj'] == 'Colombia'


def test_wczytaj_laczy_pliki(tmp_path, monkeypatch):
    T.to_csv(tmp_path / 'fs.csv.gz', index=False); T.iloc[:1].to_csv(tmp_path / '365.csv.gz', index=False)
    monkeypatch.setattr(terminarz, 'PLIK_FS', str(tmp_path / 'fs.csv.gz'))
    monkeypatch.setattr(terminarz, 'PLIK', str(tmp_path / '365.csv.gz'))
    t = terminarz.wczytaj()
    assert len(t) == 5 and sorted(t.zrodlo.unique()) == ['365', 'fs']
    monkeypatch.setattr(terminarz, 'PLIK_FS', str(tmp_path / 'brak.csv.gz'))
    assert list(terminarz.wczytaj().zrodlo.unique()) == ['365']


def test_kraje_flashscore():
    import typuj
    n = typuj.norm
    assert typuj._ten_sam_kraj(n('BOSNIA AND HERZEGOVINA'), n('Bosnia & Herzegovina'))
    assert typuj._ten_sam_kraj(n('CZECH REPUBLIC'), n('Czechia')) and not typuj._ten_sam_kraj('oman', 'romania')
    znane = typuj._kraje_znane()
    assert typuj._kanon_kraju(n('PARAGUAY')) in znane and typuj._kanon_kraju(n('ITF MEN - SINGLES')) not in znane
    assert n('AUSTRALIA & OCEANIA') in typuj._KRAJE_OGOLNE
