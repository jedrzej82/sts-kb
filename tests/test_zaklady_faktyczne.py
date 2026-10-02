"""02.10.2026: faktyczne zaklady (STS / LVBET / Superbet) w Bilansie. Dane syntetyczne — prawdziwe zaklady sa tylko
na Dysku (zaklady_faktyczne.csv), nigdy w repo."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dzienniki  # noqa: E402

T = pd.Timestamp
D = '2026-09-28'


def _W():
    return dict(pilka=pd.DataFrame([(T(D), 'Legia Warsaw', 'Lech Poznan', 1, 0, None, None),
                                    (T(D), 'Wisla Krakow', 'Cracovia', 1, 1, None, None)],
                                   columns=['d', 'h', 'a', 'g', 'ga', 'hg', 'ha']),
                tenis=pd.DataFrame(columns=['d', 'w', 'l', 'score']),
                inne=pd.DataFrame(columns=['d', 'sport', 'h', 'a', 'pg', 'pa', 'ot']))


def _ako():
    """Zalecenie systemu: K5 za 2 zl na STS, kurs 2,50."""
    w = lambda n, z, ry, k, st, uw: dict(data=D, godzina_uruchomienia='12:00', tag='K5', nr_kuponu='1', noga_nr=n,
                                         sport='pilka' if n != 'RAZEM' else '', zdarzenie=z, rynek=ry, P='50', kurs=k,
                                         status=st, uwaga=uw, kurs_zamkniecia='')
    return pd.DataFrame([w('1', 'Legia Warszawa - Lech Poznan', 'U3.5', '1.60', 'DO GRY', ''),
                         w('2', 'Wisla Krakow - Cracovia', 'U3.5', '1.5625', 'DO GRY', ''),
                         w('RAZEM', '', '', '2.50', 'DO GRY', 'stawka 2 zl')])


def _zaklad(buk, nr, kursy, stawka, status='', wyplata='', sport=''):
    nogi = [('Legia Warszawa - Lech Poznan', 'U3.5'), ('Wisla Krakow - Cracovia', 'U3.5')]
    w = [dict(data=D, godzina='12:59', bukmacher=buk, nr_zakladu=nr, noga_nr=str(i + 1), sport=sport, zdarzenie=z, rynek=r,
              kurs=k, stawka='', wyplata='', status_bukmachera='', tag_systemu='', uwaga='')
         for i, ((z, r), k) in enumerate(zip(nogi, kursy))]
    w.append(dict(data=D, godzina='12:59', bukmacher=buk, nr_zakladu=nr, noga_nr='RAZEM', sport='', zdarzenie='', rynek='',
                  kurs='', stawka=stawka, wyplata=wyplata, status_bukmachera=status, tag_systemu='K5', uwaga=''))
    return w


def test_bez_faktycznych_bilans_jak_dotad():
    _, b = dzienniki.rozlicz_dzien(D, _ako(), _W())
    assert (b['postawione'], b['wyplacone'], b['pien']) == (2.0, 4.4, 1)


def test_faktyczny_zaklad_u_innego_bukmachera_zastepuje_zalecenie():
    z = pd.DataFrame(_zaklad('LVBET', '1001', ['1.65', '1.65'], '10', status='WYGRANY', wyplata='23.96'))
    roz, b = dzienniki.rozlicz_dzien(D, _ako(), _W(), z)
    assert (b['postawione'], round(b['wyplacone'], 2), b['pien'], b['pien_traf']) == (10.0, 23.96, 1, 1)
    k5 = roz[roz.tag == 'RAZEM_K5_1'].iloc[0]
    assert 'zalecenie systemu' in k5.uwaga and k5.TRAFIONY_PRZEGRANY.startswith('TRAFIONY')
    fakt = roz[roz.tag == 'RAZEM_FAKT_LVBET_1001'].iloc[0]
    assert fakt.TRAFIONY_PRZEGRANY == 'TRAFIONY 2/2' and fakt.kategoria == '' and 'FAKTYCZNY LVBET' in fakt.uwaga
    # sport nogi brany z ako_log (ten sam mecz), nogi rozliczone kodem
    assert list(roz[roz.tag == 'FAKT_LVBET_1001'].TRAFIONY_PRZEGRANY) == ['TRAFIONY', 'TRAFIONY']


def test_wyplata_liczona_gdy_brak_i_kilku_bukmacherow():
    z = pd.DataFrame(_zaklad('STS', 'A1', ['1.60', '1.5625'], '2') + _zaklad('SUPERBET', 'S9', ['1.70', '1.60'], '5'))
    _, b = dzienniki.rozlicz_dzien(D, _ako(), _W(), z)
    # 2 x 2,50 x 0,88 = 4,40 ; 5 x 2,72 x 0,88 = 11,968 -> 11,97
    assert (b['postawione'], round(b['wyplacone'], 2), b['pien'], b['pien_traf']) == (7.0, 16.37, 2, 2)


def test_niezgodnosc_z_bukmacherem_jest_sygnalem():
    z = pd.DataFrame(_zaklad('SUPERBET', 'S1', ['1.70', '1.60'], '5', status='PRZEGRANY'))
    roz, b = dzienniki.rozlicz_dzien(D, _ako(), _W(), z)
    r = roz[roz.tag == 'RAZEM_FAKT_SUPERBET_S1'].iloc[0]
    assert r.kategoria == 'ROZLICZENIE_NIEZGODNE_Z_BUKMACHEREM' and r.TRAFIONY_PRZEGRANY.startswith('PRZEGRANY')
    assert (b['postawione'], b['wyplacone']) == (5.0, 0.0)          # pieniadze wg bukmachera


def test_inny_dzien_bez_wpisow_nie_zmienia_bilansu(tmp_path):
    p = tmp_path / 'zaklady_faktyczne.csv'
    z = pd.DataFrame(_zaklad('LVBET', '1', ['1.65', '1.65'], '10'))
    z['data'] = '2026-09-27'
    z.to_csv(p, index=False)
    _, b = dzienniki.rozlicz_dzien(D, _ako(), _W(), dzienniki.czytaj_zaklady(str(p)))
    assert (b['postawione'], b['pien']) == (2.0, 1)
    assert dzienniki.czytaj_zaklady(str(tmp_path / 'brak.csv')) is None
