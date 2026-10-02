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


def test_graj_u_zawsze_jest():
    """02.10.2026: Telegram (POWIADOMIENIE / AKO DNIA) zawsze pokazuje, u ktorego bukmachera grac kupon."""
    sts = _sts((P, '18:00', 'Walia', 'Norwegia', 'U3.5', '1.60'), (P, '20:45', 'Anglia', 'Łotwa', 'U3.5', '1.50'))
    nogi = [('Walia - Norwegia', 'U3.5', '1.60'), ('Anglia - Łotwa', 'U3.5', '1.50')]
    # brak pliku z telefonu -> STS
    tab, _ = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow([]))
    assert kursy3.gdzie_grac(*kursy3.kupon(tab, nogi)).startswith('GRAJ U: STS @2.400')
    # LVBET ma wszystkie nogi i lepszy kurs laczny; SUPERBET bez nogi 2
    buk = _buk(('LVBET', P, '18:00', 'Walia', 'Norwegia', 'U3.5', '1.65'), ('LVBET', P, '20:45', 'Anglia', 'Łotwa', 'U3.5', '1.55'),
               ('SUPERBET', P, '18:00', 'Walia', 'Norwegia', 'U3.5', '1.90'))
    tab, _ = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    assert kursy3.gdzie_grac(*kursy3.kupon(tab, nogi)) == 'GRAJ U: LVBET @2.558 (STS 2.400 | SUPERBET brak nogi 2)'
    # remis kursow -> STS
    buk = _buk(('LVBET', P, '18:00', 'Walia', 'Norwegia', 'U3.5', '1.60'), ('LVBET', P, '20:45', 'Anglia', 'Łotwa', 'U3.5', '1.50'))
    tab, _ = kursy3.tabela(sts, kursy3.wczytaj_bukmacherow_df(buk))
    assert kursy3.gdzie_grac(*kursy3.kupon(tab, nogi)).startswith('GRAJ U: STS @2.400')
    # noga spoza oferty STS: kurs STS z ako_log
    tab, _ = kursy3.tabela(sts.iloc[:1], kursy3.wczytaj_bukmacherow([]))
    assert kursy3.gdzie_grac(*kursy3.kupon(tab, nogi)).startswith('GRAJ U: STS @2.400')


def test_cli_kupon_kazdy_kupon_ma_linie(tmp_path, capsys):
    p_sts = tmp_path / 'kursy_sts.csv'
    _sts((P, '18:00', 'Walia', 'Norwegia', 'U3.5', '1.60')).to_csv(p_sts, index=False)
    p_ako = tmp_path / 'ako_log.csv'
    pd.DataFrame([dict(data=D, godzina_uruchomienia='12:00', tag=t, nr_kuponu='1', noga_nr=n, zdarzenie=z, rynek='U3.5', kurs='1.60')
                  for t in ('K5', 'AKOP-1200-1') for n, z in (('1', 'Walia - Norwegia'), ('RAZEM', ''))]).to_csv(p_ako, index=False)
    kursy3.main(['kupon', str(p_sts), str(tmp_path / 'kursy_bukmacherow_*.csv.gz'), '--ako', str(p_ako), '--data', D, '--godzina', '12:00'])
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith('kursy SUPERBET/LVBET: BRAK pliku')
    assert [x.split(' GRAJ U: ')[0] for x in out if 'GRAJ U:' in x] == ['K5#1', 'AKOP-1200-1#1']
