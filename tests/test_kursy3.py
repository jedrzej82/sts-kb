"""02.10.2026: porownanie kursow STS / SUPERBET / LVBET (kursy3.py). Dane syntetyczne — prawdziwe kursy tylko na Dysku."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kursy3  # noqa: E402

D = '2026-10-02'


def _sts(*w):
    return pd.DataFrame([dict(sport=s, data_meczu=D, godzina_meczu=g, gospodarz=a, gosc=b, rynek=r, kurs=k)
                         for s, g, a, b, r, k in w])


def _buk(*w):
    return pd.DataFrame([dict(bukmacher=bk, sport=s, data_meczu=D, godzina_meczu=g, gospodarz=a, gosc=b, rynek=r, kurs=k)
                         for bk, s, g, a, b, r, k in w])


P = 'PIŁKA NOŻNA'


def test_u21_o_tej_samej_godzinie_nie_jest_niejednoznaczne():
    sts = _sts((P, '18:00', 'Słowenia U21', 'Holandia U21', '1', '3.10'), (P, '18:00', 'Austria U21', 'Dania U21', '1', '2.00'))
    buk = _buk(('SUPERBET', P, '18:00', 'Słowenia U21', 'Holandia U21', '1', '3.20'),
               ('SUPERBET', P, '18:00', 'Austria U21', 'Dania U21', '1', '2.05'),
               ('SUPERBET', P, '18:00', 'Ukraina U21', 'Chorwacja U21', '1', '1.90'))
    tab, st = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    assert st['SUPERBET'] == {'jednoznaczne': 2, 'brak': 0, 'kilka': 0}
    assert list(tab.SUPERBET) == [3.20, 2.05]


def test_znaczniki_musza_sie_zgadzac_i_godzina_5_min():
    sts = _sts((P, '18:00', 'Barcelona', 'Sevilla', '1', '1.50'), (P, '20:00', 'Legia Warszawa', 'Lech Poznań', 'X', '3.40'))
    buk = _buk(('LVBET', P, '18:00', 'Barcelona (Wom)', 'Sevilla (Wom)', '1', '1.20'),   # kobiety -> inny mecz
               ('LVBET', P, '20:04', 'Legia Warszawa', 'Lech Poznań', 'X', '3.50'))
    tab, st = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    assert st['LVBET'] == {'jednoznaczne': 1, 'brak': 1, 'kilka': 0}
    assert pd.isna(tab.LVBET.iloc[0]) and tab.LVBET.iloc[1] == 3.50
    buk = _buk(('LVBET', P, '20:06', 'Legia Warszawa', 'Lech Poznań', 'X', '3.50'))
    _, st = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    assert st['LVBET']['jednoznaczne'] == 0


def test_dwa_mozliwe_mecze_to_brak_dopasowania_i_podejrzany_kurs_odrzucony():
    sts = _sts((P, '18:00', 'Dinamo', 'Spartak', '1', '2.00'), (P, '19:00', 'Wisła Kraków', 'Cracovia', '1', '2.00'))
    buk = _buk(('SUPERBET', P, '18:00', 'Dinamo Moskwa', 'Spartak Moskwa', '1', '2.10'),
               ('SUPERBET', P, '18:00', 'Dinamo Mińsk', 'Spartak Trnava', '1', '1.90'),
               ('SUPERBET', P, '19:00', 'Wisła Kraków', 'Cracovia', '1', '3.50'))           # +75% -> podejrzany
    tab, st = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    assert st['SUPERBET'] == {'jednoznaczne': 1, 'brak': 0, 'kilka': 1}
    assert tab.SUPERBET.isna().all() and bool(tab.SUPERBET_podejrzany.iloc[1])


def test_kupon_kurs_laczny_tylko_gdy_kazda_noga_ma_kurs():
    sts = _sts((P, '18:00', 'Walia', 'Norwegia', 'U3.5', '1.60'), (P, '20:45', 'Anglia', 'Łotwa', 'U3.5', '1.50'))
    buk = _buk(('LVBET', P, '18:00', 'Walia', 'Norwegia', 'U3.5', '1.65'), ('LVBET', P, '20:45', 'Anglia', 'Łotwa', 'U3.5', '1.55'),
               ('SUPERBET', P, '18:00', 'Walia', 'Norwegia', 'U3.5', '1.70'))
    tab, _ = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    nogi, laczne = kursy3.kupon(tab, [('Walia - Norwegia', 'U3.5'), ('Anglia - Łotwa', 'U3.5')])
    assert set(laczne) == {'STS', 'LVBET'} and round(laczne['LVBET'], 4) == round(1.65 * 1.55, 4)
    assert kursy3.najlepszy(nogi[0][2]) == ('SUPERBET', 1.70)
