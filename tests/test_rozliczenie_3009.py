"""01.10.2026 (proba rozliczenia 30.09): wskazowka z przebiegu „dopasowanie po terminarzu -> X”, mecz bez wyniku
z dzis/jutra, data konca zrodla w powodzie BRAK WYNIKU."""
import pandas as pd

import dzienniki

T = pd.Timestamp
KOL = ['d', 'h', 'a', 'g', 'ga', 'hg', 'ha']


def _noga(zd, rynek='12', uwaga='', data='2026-09-30', sport='pilka'):
    return dict(data=data, sport=sport, zdarzenie=zd, rynek=rynek, uwaga=uwaga)


def _W(rows):
    return dict(pilka=pd.DataFrame(rows, columns=KOL), inne=pd.DataFrame(columns=['d', 'sport', 'h', 'a', 'pg', 'pa', 'ot']),
                tenis=pd.DataFrame(columns=['d', 'w', 'l', 'score']))


def test_wskazowka_z_terminarza(monkeypatch):
    monkeypatch.setattr(dzienniki, '_rozwiaz_pilka', lambda n, p: n if n in p else None)   # bez aliasow
    W = _W([(T('2026-09-30'), 'CSD Amatitlan', 'Santa Lucia Cotzumalguapa FC', 2, 1, None, None)])
    zd = 'Deportivo Amatitlan - Santa Lucia Cotzumalguapa FC'
    assert dzienniki.rozlicz_noge(_noga(zd), W)[0] == 'BRAK WYNIKU'
    s, w, _ = dzienniki.rozlicz_noge(_noga(zd, uwaga='mecz 23:30; dopasowanie po terminarzu -> CSD Amatitlan; EV -17%'), W)
    assert (s, w) == ('TRAFIONY', '2:1')
    # wskazowka spoza puli nic nie zmienia — nie zgadujemy
    assert dzienniki.rozlicz_noge(_noga(zd, uwaga='dopasowanie po terminarzu -> Inny Klub'), W)[0] == 'BRAK WYNIKU'


def test_mecz_dzis_bez_wyniku(monkeypatch):
    monkeypatch.setattr(dzienniki, '_dzis', lambda: T('2026-10-01'))
    W = _W([(T('2026-09-30'), 'Argentina', 'Bolivia', 3, 0, None, None)])
    s, _, uw = dzienniki.rozlicz_noge(_noga('Panama - Nowa Zelandia', 'O1.5', 'mecz 2026-10-01 08:10'), W)
    assert s == 'BRAK WYNIKU' and uw.startswith('mecz 2026-10-01 jeszcze bez wyniku')
    s, _, uw = dzienniki.rozlicz_noge(_noga('Panama - Nowa Zelandia', 'O1.5', 'mecz 2026-09-29 20:00'), W)
    assert s == 'BRAK WYNIKU' and 'jeszcze bez wyniku' not in uw   # stary mecz — zwykly powod


def test_brak_danych_z_data_konca_zrodla():
    W = _W([(T('2026-09-28'), 'A', 'B', 1, 0, None, None)])
    s, _, uw = dzienniki.rozlicz_noge(_noga('A - B', data='2026-09-30', uwaga='mecz 2026-09-30'), dict(W, pilka=W['pilka']))
    assert s == 'BRAK WYNIKU'
    x, powod = dzienniki._szukaj(W['pilka'].assign(d=W['pilka'].d), T('2026-09-30') + pd.Timedelta(days=5), 'A', 'B', lambda n, p: n)
    assert x is None and 'zrodlo konczy sie 2026-09-28' in powod
