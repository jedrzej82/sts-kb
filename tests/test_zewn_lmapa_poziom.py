"""07.10.2026 (paczka wieczorna): liga Flashscore -> liga 365 tylko w obrebie tego samego poziomu.

Zmierzone na zewn/ z 07.10 18:00: lmapa miala 36 par, w tym 5 blednych — „Tercera RFEF - Group 7/11” -> „Segunda RFEF”
(wspolny czlon „rfef”; kluby spadle z Segundy maja te same nazwy) i „Campeonato de Portugal - Group B/C/D” ->
„Taça de Portugal” (liga do pucharu, wspolny czlon „portugal”). Po poprawce 31 par — te 5 odpadlo, reszta bez zmian.
"""
import pandas as pd
import pytest

import zewn

# pary zostajace (wszystkie 31 z danych 07.10 18:00 maja przejsc warunek poziomu)
DOBRE = [
    ('argentina', 'Primera B', 'Primera B Metropolitana'),
    ('argentina', 'Torneo Federal - Play Offs', 'Federal A'),
    ('australia', 'NPL Victoria - Play Offs', 'NPL Victoria'),
    ('brazil', 'Gaucho 2', 'Gaucho A2'),
    ('costa rica', 'Liga de Ascenso - Apertura', 'Liga de Ascenso'),
    ('finland', 'Kakkonen Group C - Losers stage', 'Kakkonen'),
    ('germany', 'Regionalliga Nordost', 'Regionalliga'),
    ('italy', 'Serie D - Group A', 'Serie D'),
    ('mexico', 'Liga de Expansion MX - Apertura', 'Liga de Expansión MX'),
    ('new zealand', 'National League - Championship Group', 'National League'),
    ('san marino', 'Campionato Sammarinese', 'Campionato'),
    ('spain', 'Segunda RFEF - Group 1', 'Segunda RFEF '),
    ('paraguay', 'Copa de Primera - Apertura', 'Copa de Primera'),   # liga z „copa” w nazwie (LIGA_NIE_PUCHAR)
]
ZLE = [
    ('spain', 'Tercera RFEF - Group 7', 'Segunda RFEF '),
    ('spain', 'Tercera RFEF - Group 11', 'Segunda RFEF '),
    ('portugal', 'Campeonato de Portugal - Group B', 'Taça de Portugal'),
    ('england', 'Second Division', 'First Division'),
    ('italy', 'Serie D - Group A', 'Coppa Italia Serie D'),
]


@pytest.mark.parametrize('k,a,b', DOBRE)
def test_ten_sam_poziom_zostaje(k, a, b):
    assert zewn._liga_ten_poziom(k, a, b)


@pytest.mark.parametrize('k,a,b', ZLE)
def test_inny_poziom_albo_puchar_odpada(k, a, b):
    assert not zewn._liga_ten_poziom(k, a, b)


def _mecze(kraj, turniej, pary, dzien0, wynik='1'):
    w = []
    for i, (a, b) in enumerate(pary):
        w.append(dict(data=f'2026-09-{dzien0 + i:02d} 15:00', sport='football', kraj=kraj, turniej=turniej,
                      gosp=a, gosc=b, wg=wynik, wa='0'))
    return pd.DataFrame(w)


def _uruchom(monkeypatch, s, fs):
    monkeypatch.setattr(zewn, 'czytaj', lambda wzor, bez=None: fs if 'pilka' in wzor else pd.DataFrame())
    return zewn._pilka_fs(s)


def test_tercera_nie_trafia_do_segundy(monkeypatch):
    kluby = ['Club Alfa', 'Club Beta', 'Club Gamma', 'Club Delta']
    s = _mecze('Spain', 'Segunda RFEF', [(kluby[0], kluby[1]), (kluby[2], kluby[3])], 1)   # sezon 25/26
    fs = _mecze('SPAIN', 'Tercera RFEF - Group 7', [(kluby[0], kluby[2]), (kluby[1], kluby[3])], 20, wynik='3')
    out = _uruchom(monkeypatch, s, fs)
    nowe = out[out.data.str.startswith('2026-09-2')]
    assert len(nowe) == 2 and set(nowe.turniej) == {'Tercera RFEF - Group 7'}


def test_serie_d_grupa_trafia_do_serie_d(monkeypatch):
    kluby = ['Club Alfa', 'Club Beta', 'Club Gamma', 'Club Delta']
    s = _mecze('Italy', 'Serie D', [(kluby[0], kluby[1]), (kluby[2], kluby[3])], 1)
    fs = _mecze('ITALY', 'Serie D - Group A', [(kluby[0], kluby[2]), (kluby[1], kluby[3])], 20, wynik='3')
    out = _uruchom(monkeypatch, s, fs)
    nowe = out[out.data.str.startswith('2026-09-2')]
    assert len(nowe) == 2 and set(nowe.turniej) == {'Serie D'}


def test_liga_nie_trafia_do_pucharu(monkeypatch):
    kluby = ['Club Alfa', 'Club Beta', 'Club Gamma', 'Club Delta']
    s = _mecze('Portugal', 'Taça de Portugal', [(kluby[0], kluby[1]), (kluby[2], kluby[3])], 1)
    fs = _mecze('PORTUGAL', 'Campeonato de Portugal - Group B', [(kluby[0], kluby[2]), (kluby[1], kluby[3])], 20, wynik='3')
    out = _uruchom(monkeypatch, s, fs)
    nowe = out[out.data.str.startswith('2026-09-2')]
    assert len(nowe) == 2 and set(nowe.turniej) == {'Campeonato de Portugal - Group B'}
