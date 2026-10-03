"""03.10.2026: warstwa ZDARZENIA (zdarzenia.py) — MATCH / UNKNOWN / CONFLICT z dowodami, przypadki z danych 30.09-03.10."""
import pandas as pd

import zdarzenia


def _ev(*mecze):
    d = pd.Timestamp('2026-10-03')
    return pd.DataFrame([dict(S='pilka', d=d, t=pd.Timestamp('2026-10-03 16:00'), dni=frozenset({d}), A=a, B=b) for a, b in mecze])


def _z(*mecze):
    d = pd.Timestamp('2026-10-03')
    return pd.DataFrame([dict(S='pilka', d=d, t=pd.Timestamp('2026-10-03 16:02'), gosp=a, gosc=b, zrodlo='wyniki_365')
                         for a, b in mecze], columns=['S', 'd', 't', 'gosp', 'gosc', 'zrodlo'])


POOL = {'pilka': {'Start', 'Pisa', 'Lech Poznan', 'Legia', 'Llanelli Town', 'Llanelli', 'Baglan Dragons', 'Wisla Plock', 'Rakow'}}
MAPA = {'Start Nidzica': 'Start', 'Pisa Barczewo': 'Pisa', 'Lech Poznań': 'Lech Poznan', 'Legia Warszawa': 'Legia',
        'Raków Częstochowa': 'Rakow', 'Wisła Płock': 'Wisla Plock'}


def _rozwiaz(S, n):
    return MAPA.get(n)


def _stan(ev, z=None, ligi=None, h2h=None):
    k = zdarzenia.klasyfikuj(ev, z if z is not None else _z(), _rozwiaz, POOL, ligi or {}, h2h or set())
    return list(zip(k.stan, k.dowody))


def test_skrot_bez_dowodu_pary_to_unknown():
    # „Start Nidzica - Pisa Barczewo” -> Start - Pisa: obie nazwy „rozpoznane”, ale para nie ma wspolnej ligi ani meczu
    (stan, dow), = _stan(_ev(('Start Nidzica', 'Pisa Barczewo')))
    assert stan == 'UNKNOWN' and 'BRAK_DOWODU_PARY' in dow


def test_para_w_zrodle_i_godzina_to_match():
    (stan, dow), = _stan(_ev(('Lech Poznań', 'Legia Warszawa')), _z(('Legia', 'Lech Poznan')))
    assert stan == 'MATCH' and 'PARA_W_ZRODLE' in dow and 'GODZINA' in dow


def test_wspolna_liga_lub_h2h_to_match():
    ligi = {('pilka', 'Lech Poznan'): {'POL'}, ('pilka', 'Legia'): {'POL'}}
    assert _stan(_ev(('Lech Poznań', 'Legia Warszawa')), ligi=ligi)[0][0] == 'MATCH'
    assert _stan(_ev(('Lech Poznań', 'Legia Warszawa')), h2h={('pilka', frozenset({'Lech Poznan', 'Legia'}))})[0][0] == 'MATCH'


def test_rywal_inny_to_conflict():
    # rozpoznana druzyna gra tego dnia (jedyny mecz) z INNYM, rozpoznanym klubem -> jedna z nazw wskazuje zly klub
    ligi = {('pilka', 'Lech Poznan'): {'POL'}, ('pilka', 'Legia'): {'POL'}}
    (stan, dow), = _stan(_ev(('Lech Poznań', 'Legia Warszawa')), _z(('Lech Poznan', 'Rakow')), ligi=ligi)
    assert stan == 'CONFLICT' and 'RYWAL_INNY:Lech Poznan~Rakow' in dow


def test_mozliwy_dubel_bez_ligi_to_conflict():
    # przeglad 03.10: podobna nazwa rywala w zrodle bywa INNYM klubem („San Antonio FC” USA vs San Antonio z Ekwadoru)
    MAPA.update({'Baglan Dragons': 'Baglan Dragons', 'Llanelli Town': 'Llanelli Town'})
    try:
        (stan, dow), = _stan(_ev(('Llanelli Town', 'Baglan Dragons')), _z(('Baglan Dragons', 'Llanelli')))
        ligi = {('pilka', 'Llanelli Town'): {'WAL'}, ('pilka', 'Baglan Dragons'): {'WAL'}}
        (stan2, _), = _stan(_ev(('Llanelli Town', 'Baglan Dragons')), _z(('Baglan Dragons', 'Llanelli')), ligi=ligi)
    finally:
        del MAPA['Baglan Dragons'], MAPA['Llanelli Town']
    assert stan == 'CONFLICT' and 'MOZLIWY_DUBEL:Llanelli Town=Llanelli' in dow
    assert stan2 == 'MATCH'                                     # wspolna liga potwierdza pare
    assert any('MOZLIWE DUBLE' in x for x in zdarzenia.raport(pd.DataFrame(
        [dict(S='pilka', d=pd.Timestamp('2026-10-03'), A='a', B='b', eA='x', eB='y', stan=stan, dowody=dow)])))


def test_brak_i_ta_sama_druzyna():
    (stan, dow), = _stan(_ev(('Nieznany FC', 'Legia Warszawa')))
    assert stan == 'UNKNOWN' and 'A_BRAK' in dow
    MAPA['Legia II'] = 'Legia'
    try:
        (stan, dow), = _stan(_ev(('Legia II', 'Legia Warszawa')))
    finally:
        del MAPA['Legia II']
    assert stan == 'CONFLICT' and 'TA_SAMA_DRUZYNA' in dow
