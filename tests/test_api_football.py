"""17.10.2026: api_football.py (TRYB OBSERWACJI) — dopasowanie oferty STS do API-Football na parach z 17.10."""
import json
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api_football as af  # noqa: E402


@pytest.mark.parametrize('sts,api', [
    ('Tvaakers IF', 'Tvååker'), ('Kyzylzhar Petropavlovsk', 'Kyzyl-Zhar'), ('Aalesunds FK', 'Aalesund'),
    ('Airdrieonians FC', 'Airdrie United'), ('Kolding IF [K]', 'KoldingQ W'), ('Sariyer SK', 'Sarıyer'),
    ('Skellefteaa FF', 'Skellefteå'), ('Union Berlin', '1. FC Union Berlin'),
])
def test_ta_sama_druzyna_inna_pisownia(sts, api):
    assert af.ta_sama(sts, api)


@pytest.mark.parametrize('x,y', [
    ('Club Tijuana', 'Club Tijuana U21'),          # U21 to inna drużyna
    ('Kolding IF', 'KoldingQ W'),                  # mężczyźni vs kobiety
    ('Hednesford Town', 'Brackley Town'),          # samo „Town” nie jest dowodem
    ('Hapoel Tel Aviv', 'Hapoel Haifa'), ('Real Madrid', 'Real Sociedad'), ('Stuttgart II', 'VfB Stuttgart'),
])
def test_rozne_druzyny(x, y):
    assert not af.ta_sama(x, y)


def test_samo_miasto_wymaga_drugiej_druzyny():
    # „Shandong Taishan” / „Shandong Luneng” (ten sam klub po zmianie nazwy) i „Dalian Yingbo” / „Dalian Zhixing” (różne kluby)
    # dzielą nazwę miasta — ta_sama to przepuszcza, więc chroni dopiero wymóg tej samej godziny i DRUGIEJ drużyny (dopasuj)
    assert af.ta_sama('Shandong Taishan', 'Shandong Luneng') and af.ta_sama('Dalian Yingbo', 'Dalian Zhixing')


def test_start_utc_czas_letni_i_zimowy():
    assert af.start_utc('2026-10-17', '18:00') == int(pd.Timestamp('2026-10-17 16:00', tz='UTC').timestamp())
    assert af.start_utc('2026-10-26', '18:00') == int(pd.Timestamp('2026-10-26 17:00', tz='UTC').timestamp())
    assert af.start_utc('2026-10-17', '') is None


def _kursy(rows):
    return pd.DataFrame([dict(data_meczu=d, godzina_meczu=g, sport='PIŁKA NOŻNA', liga=l, gospodarz=a, gosc=b, rynek='1')
                         for d, g, l, a, b in rows])


def test_dopasuj_jednoznacznie_i_kilku_kandydatow():
    t = af.start_utc('2026-10-17', '16:00')
    sts = af.mecze_sts(_kursy([('2026-10-17', '16:00', 'ANGLIA - CHAMPIONSHIP', 'Southampton', 'Bolton'),
                               ('2026-10-17', '16:00', 'X', 'Halesowen Town', 'Hitchin Town'),
                               ('2026-10-17', '16:00', 'X', 'Dalian Yingbo', 'Shenzhen Peng City'),
                               ('2026-10-17', '16:00', 'X', 'Alfa FC', 'Beta FC'),
                               ('2026-10-17', '17:00', 'X', 'Alfa FC', 'Beta FC')]))
    api = [dict(t=t, a='Southampton', b='Bolton', lid=40, sez=2026), dict(t=t, a='Hitchin', b='Halesowen'),
           dict(t=t, a='Dalian Zhixing', b='Sichuan Jiuniu'), dict(t=t, a='Alfa', b='Beta'), dict(t=t, a='Alfa W', b='Beta')]
    w = af.dopasuj(sts, api)
    assert [p for _, _, p in w] == ['ok', 'brak w API o tej godzinie', 'inna nazwa jednej drużyny', 'ok', 'brak w API o tej godzinie']
    assert w[0][1]['lid'] == 40 and w[3][1]['a'] == 'Alfa'


def test_ligi_zapisuje_liste_dla_skryptu(tmp_path, capsys):
    t = af.start_utc('2026-10-17', '16:00')
    k = tmp_path / 'kursy.csv'
    _kursy([('2026-10-17', '16:00', 'ANGLIA - CHAMPIONSHIP', 'Southampton', 'Bolton'),
            ('2026-10-17', '16:00', 'ANGLIA - CHAMPIONSHIP', 'Leeds', 'Hull'),
            ('2026-10-18', '16:00', 'ANGLIA - CHAMPIONSHIP', 'Stoke', 'Derby')]).to_csv(k, index=False)
    f = tmp_path / 'feed.json'
    f.write_text(json.dumps({'mecze': [dict(s='football', t=t, a='Southampton', b='Bolton', lid=40, sez=2026, lg='Championship', kr='England'),
                                       dict(s='football', t=t, a='Leeds', b='Hull City', lid=40, sez=2026, lg='Championship', kr='England'),
                                       dict(s='hockey', t=t, a='Leeds', b='Hull')]}))
    wyj = tmp_path / 'api_ligi.json'
    af.main(['ligi', str(k), str(f), '--wyjscie', str(wyj)])
    out = capsys.readouterr().out
    assert 'POKRYCIE 2026-10-17: 2 meczów piłki STS, w API jednoznacznie 2 (100.0%)' in out   # 18.10 poza plikiem API
    j = json.loads(wyj.read_text())
    assert j['ligi'] == [dict(lid=40, sezon=2026, liga='Championship', kraj='England', mecze_sts=2, ligi_sts=['ANGLIA - CHAMPIONSHIP'])]


def test_rozliczenia_brak_wyniku_i_rozne_wyniki(tmp_path, capsys):
    r = tmp_path / 'Rozliczenie_2026-10-17.csv'
    pd.DataFrame([dict(tag='AKO1', zdarzenie='Tvaakers IF - Rosengard 1917', rynek='O2.5', wynik='', TRAFIONY_PRZEGRANY='BRAK WYNIKU',
                       kategoria='MECZ_BEZ_WYNIKU', uwaga='mecz w zrodle bez wyniku'),
                  dict(tag='AKO1', zdarzenie='Southampton - Bolton', rynek='1', wynik='2:1', TRAFIONY_PRZEGRANY='TRAFIONY', kategoria='', uwaga=''),
                  dict(tag='AKO2', zdarzenie='Leeds - Hull', rynek='X', wynik='1:1', TRAFIONY_PRZEGRANY='TRAFIONY', kategoria='', uwaga=''),
                  dict(tag='RAZEM_DZIEN', zdarzenie='', rynek='', wynik='', TRAFIONY_PRZEGRANY='', kategoria='', uwaga='')]).to_csv(r, index=False)
    w = tmp_path / 'api_wyniki_2026-10.csv'
    pd.DataFrame([dict(data='2026-10-17', gosp='Tvååker', gosc='Rosengård', gg=3, ga=0, status='FT'),
                  dict(data='2026-10-17', gosp='Southampton', gosc='Bolton', gg=2, ga=1, status='FT'),
                  dict(data='2026-10-17', gosp='Leeds', gosc='Hull City', gg=2, ga=1, status='FT'),
                  dict(data='2026-10-15', gosp='Leeds', gosc='Hull City', gg=0, ga=0, status='FT')]).to_csv(w, index=False)
    zysk, rozne = af.main(['rozliczenia', str(r), str(w)]) or (None, None)
    out = capsys.readouterr().out
    assert 'BRAK WYNIKU 1 — API ma wynik dla 1' in out and 'API MA WYNIK: AKO1 | Tvaakers IF - Rosengard 1917 | O2.5 | API 3:0' in out
    assert 'WYNIK RÓŻNY OD API: 1' in out and 'Leeds - Hull | X | rozliczenie 1:1 | API 2:1' in out


def test_statystyki_i_kontuzje(tmp_path, capsys):
    s = tmp_path / 's.csv'
    pd.DataFrame([dict(fid=1, lid=40, strzaly=10, celne=4, rozne=5, zolte=2, xg=1.2), dict(fid=1, lid=40, strzaly=8, celne=2, rozne=3, zolte=1, xg=0.9),
                  dict(fid=2, lid=41, strzaly=None, celne=None, rozne=4, zolte=0, xg=None),
                  dict(fid=2, lid=41, strzaly=None, celne=None, rozne=2, zolte=3, xg=None)]).to_csv(s, index=False)
    af.main(['statystyki', str(s)])
    k = tmp_path / 'k.csv'
    pd.DataFrame([dict(fid=1, druzyna='A', typ='Missing Fixture'), dict(fid=1, druzyna='A', typ='Questionable')]).to_csv(k, index=False)
    af.main(['kontuzje', str(k)])
    out = capsys.readouterr().out
    assert 'STATYSTYKI: 2 meczów, 2 lig' in out and 'strzaly: 1/2' in out and 'rozne: 2/2' in out
    assert 'KONTUZJE: 2 wpisów, 1 drużyn, 1 meczów' in out
