"""01.10.2026: nauka dopasowan nazw STS -> baza (dopasuj.py) — przypadki z oferty 24-30.09 i zrodel Flashscore/365."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dopasuj  # noqa: E402
import nazwy  # noqa: E402

T = pd.Timestamp


def _ev(rows):
    """(S, data, godz PL, A, B)"""
    k = pd.DataFrame([(dict(pilka='PIŁKA NOŻNA', hokej='HOKEJ NA LODZIE', koszykówka='KOSZYKÓWKA', dart='DART',
                            **{'piłka ręczna': 'PIŁKA RĘCZNA'})[s], d, g, a, b) for s, d, g, a, b in rows],
                     columns=['sport', 'data_meczu', 'godzina_meczu', 'gospodarz', 'gosc'])
    return dopasuj.zdarzenia_sts(k)


def _z(rows):
    """(S, data, godzina_utc|None, gosp, gosc)"""
    z = pd.DataFrame([(s, T(d), T(f'{d} {g}') if g else pd.NaT, a, b, 'test') for s, d, g, a, b in rows],
                     columns=['S', 'd', 't', 'gosp', 'gosc', 'zrodlo'])
    return z


def _ucz(ev, z, znane, pule):
    return dopasuj.ucz(ev, z, lambda S, n: znane.get(n), pule)


def test_kotwica_uczy_rywala():
    # Raport 27.09: „Berani Zlin” nie dopasowane; HC Litvinov rozpoznany, w zrodle jedyny mecz Litvinova to z „Zlin”
    ev = _ev([('hokej', '2026-09-27', '17:00', 'HC Litvinov', 'Berani Zlin')])
    z = _z([('hokej', '2026-09-27', None, 'Litvinov', 'Zlin'), ('hokej', '2026-09-27', None, 'Sparta Prague', 'Kladno')])
    a, k, _ = _ucz(ev, z, {'HC Litvinov': 'Litvinov'}, {'hokej': {'Litvinov', 'Zlin', 'Sparta Prague', 'Kladno'}})
    assert a[['nazwa', 'cel']].values.tolist() == [['Berani Zlin', 'Zlin']] and k.empty


def test_mecz_z_dnia_wczesniej_to_nie_dowod():
    # 30.09 (Dimitrov - Rincon): zrodlo nie mialo jeszcze meczu z dnia oferty, a okno +-1 dnia wzielo mecz z dnia
    # wczesniej (z innym rywalem) — falszywa kotwica. Dzien meczu = data PL albo UTC godziny z oferty, nic wiecej.
    ev = _ev([('hokej', '2026-09-28', '18:00', 'HC Litvinov', 'Berani Zlin')])
    z = _z([('hokej', '2026-09-27', None, 'Litvinov', 'Zlin')])
    a, k, _ = _ucz(ev, z, {'HC Litvinov': 'Litvinov'}, {'hokej': {'Litvinov', 'Zlin'}})
    assert a.empty and k.empty


def test_po_polnocy_dzien_utc():
    # 01:30 PL = 23:30 UTC dnia poprzedniego — zrodlo w UTC zapisuje mecz pod ta data
    ev = _ev([('hokej', '2026-09-28', '01:30', 'HC Litvinov', 'Berani Zlin')])
    z = _z([('hokej', '2026-09-27', None, 'Litvinov', 'Zlin')])
    a, _, _ = _ucz(ev, z, {'HC Litvinov': 'Litvinov'}, {'hokej': {'Litvinov', 'Zlin'}})
    assert a.nazwa.tolist() == ['Berani Zlin']


def test_niejednoznaczna_kotwica_i_odwrocona_strona():
    pule = {'hokej': {'Litvinov', 'Zlin', 'Kladno'}}
    ev = _ev([('hokej', '2026-09-27', '17:00', 'HC Litvinov', 'Berani Zlin')])
    dwa = _z([('hokej', '2026-09-27', None, 'Litvinov', 'Zlin'), ('hokej', '2026-09-27', None, 'Litvinov', 'Kladno')])
    assert _ucz(ev, dwa, {'HC Litvinov': 'Litvinov'}, pule)[0].empty
    odwr = _z([('hokej', '2026-09-27', None, 'Zlin', 'Litvinov')])
    assert _ucz(ev, odwr, {'HC Litvinov': 'Litvinov'}, pule)[0].empty


def test_znaczniki_kobiet_musza_byc_rowne():
    ev = _ev([('piłka ręczna', '2026-09-27', '17:00', 'Fana [K]', 'Molde HK [K]')])
    z = _z([('piłka ręczna', '2026-09-27', None, 'Fana W', 'Molde')])     # Molde mezczyzni — nie ta druzyna
    a, _, st = _ucz(ev, z, {'Fana [K]': 'Fana W'}, {'piłka ręczna': {'Fana W', 'Molde', 'Molde W'}})
    assert a.empty
    z = _z([('piłka ręczna', '2026-09-27', None, 'Fana W', 'Molde W')])
    a, _, _ = _ucz(ev, z, {'Fana [K]': 'Fana W'}, {'piłka ręczna': {'Fana W', 'Molde', 'Molde W'}})
    assert a[['nazwa', 'cel']].values.tolist() == [['Molde HK [K]', 'Molde W']]


def test_kraj_nie_dostaje_klubu():
    # nauka 01.10: „Kuwejt” (reprezentacja) -> „Kuwait SC” (klub) — reprezentacje maja sciezke --intl
    ev = _ev([('pilka', '2026-09-27', '17:00', 'Al-Arabi SC', 'Kuwejt')])
    z = _z([('pilka', '2026-09-27', None, 'Al-Arabi', 'Kuwait SC')])
    a, _, st = _ucz(ev, z, {'Al-Arabi SC': 'Al-Arabi'}, {'pilka': {'Al-Arabi', 'Kuwait SC'}})
    assert a.empty and st['odrzucone: kraj'] == 1
    # i odwrotnie: klub „Al-Kuwait SC” (WASL) -> „Kuwait” (w bazie reprezentacja: Asia Cup, Asian Games)
    ev = _ev([('koszykówka', '2026-09-27', '17:00', 'Al-Riyadi Beirut', 'Al-Kuwait SC')])
    z = _z([('koszykówka', '2026-09-27', None, 'Al Riyadi', 'Kuwait')])
    a, _, st = _ucz(ev, z, {'Al-Riyadi Beirut': 'Al Riyadi'}, {'koszykówka': {'Al Riyadi', 'Kuwait'}})
    assert a.empty and st['odrzucone: kraj'] == 1


def test_konflikt_nie_nadpisuje_tylko_raportuje():
    # wzor z 28.09: „Al-Orooba FC” (liga saudyjska) -> kod dal „Al Orouba FC” (liga jemenska), a jedyny mecz rywala
    # w dniu oferty jest z saudyjskim klubem. Alias sie nie tworzy (kod juz cos wskazal) — sprzecznosc idzie do raportu.
    ev = _ev([('pilka', '2026-09-28', '19:00', 'Al-Ittifaq FC', 'Al-Orooba FC')])
    z = _z([('pilka', '2026-09-28', None, 'Al Ittifaq', 'Al Orooba')])
    a, k, _ = _ucz(ev, z, {'Al-Ittifaq FC': 'Al Ittifaq', 'Al-Orooba FC': 'Al Orouba FC'},
                   {'pilka': {'Al Ittifaq', 'Al Orooba', 'Al Orouba FC'}})
    assert a.empty
    assert k[['nazwa', 'kod_dal', 'zrodlo_cel']].values.tolist() == [['Al-Orooba FC', 'Al Orouba FC', 'Al Orooba']]


def test_niepodobna_nazwa_wymaga_dwoch_dowodow():
    # „SYNTAINICS MBC” to sponsor Mitteldeutscher BC — napis bez wspolnego czlonu, 2 mecze w 2 dni
    pule = {'koszykówka': {'Bamberg', 'Ulm', 'Mitteldeutscher'}}
    znane = {'Bamberg Baskets': 'Bamberg', 'ratiopharm Ulm': 'Ulm'}
    jeden = _ev([('koszykówka', '2026-09-27', '18:00', 'Bamberg Baskets', 'SYNTAINICS MBC')])
    z = _z([('koszykówka', '2026-09-27', None, 'Bamberg', 'Mitteldeutscher'), ('koszykówka', '2026-09-29', None, 'Ulm', 'Mitteldeutscher')])
    assert _ucz(jeden, z, znane, pule)[0].empty
    dwa = _ev([('koszykówka', '2026-09-27', '18:00', 'Bamberg Baskets', 'SYNTAINICS MBC'),
               ('koszykówka', '2026-09-29', '18:00', 'ratiopharm Ulm', 'SYNTAINICS MBC')])
    a, _, _ = _ucz(dwa, z, znane, pule)
    assert a[['nazwa', 'cel', 'dowody']].values.tolist() == [['SYNTAINICS MBC', 'Mitteldeutscher', 2]]


def test_sport_osobowy_tylko_podobne():
    pule = {'dart': {'Luke Humphries', 'Josh Rock', 'Gerwyn Price'}}
    ev = _ev([('dart', '2026-09-27', '18:00', 'Humphries Luke', 'Kowalski Jan'),
              ('dart', '2026-09-28', '18:00', 'Price Gerwyn', 'Kowalski Jan')])
    z = _z([('dart', '2026-09-27', None, 'Luke Humphries', 'Josh Rock'), ('dart', '2026-09-28', None, 'Gerwyn Price', 'Josh Rock')])
    a, _, _ = _ucz(ev, z, {'Humphries Luke': 'Luke Humphries', 'Price Gerwyn': 'Gerwyn Price'}, pule)
    assert a.empty


def test_godzina_z_terminarza():
    # zadna strona nie rozpoznana: mecz w terminarzu o tej samej godzinie (UTC = PL - 2 h), obie nazwy podobne
    pule = {'koszykówka': {'Leszno', 'Pelplin'}}
    ev = _ev([('koszykówka', '2026-09-27', '18:00', 'Polonia Leszno', 'Decka Pelplin')])
    z = _z([('koszykówka', '2026-09-27', '16:00', 'Leszno', 'Pelplin')])
    a, _, _ = _ucz(ev, z, {}, pule)
    assert sorted(a[['nazwa', 'cel']].values.tolist()) == [['Decka Pelplin', 'Pelplin'], ['Polonia Leszno', 'Leszno']]
    z = _z([('koszykówka', '2026-09-27', '16:20', 'Leszno', 'Pelplin')])     # 20 min roznicy — to nie ten mecz
    assert _ucz(ev, z, {}, pule)[0].empty


def test_podobne_skroty_i_egzonimy():
    assert dopasuj.podobne('Dinamo Bukareszt', 'Din. Bucuresti')
    assert dopasuj.podobne('Gwinea', 'Guinea') and dopasuj.podobne('Sparta Praga', 'Sparta Prague')
    assert not dopasuj.podobne('FC Barcelona', 'Real Madrid') and not dopasuj.podobne('SC Fc', 'FC Sc')


def test_jako_aliasy_i_odczyt_przez_aliasy_z_pliku(tmp_path):
    a = pd.DataFrame([('pilka', 'Vasalunds IF', 'Vasalund', 1, 'x'), ('hokej', 'Berani Zlin', 'Zlin', 2, 'y')],
                     columns=['S', 'nazwa', 'cel', 'dowody', 'przyklad'])
    p = tmp_path / 'aliasy.csv'
    dopasuj.jako_aliasy(a, '2026-10-01').to_csv(p, index=False)
    sl = {}
    assert nazwy.aliasy_z_pliku('sporty', str.lower, sl, str(p)) == 1 and sl == {'berani zlin': 'Zlin'}
    sl = {}
    assert nazwy.aliasy_z_pliku('typuj', str.lower, sl, str(p)) == 1 and sl == {'vasalunds if': 'Vasalund'}


def test_skrot_z_kolizja_rdzenia_idzie_do_przegladu():
    # nauka 01.10: „Torpedo Ust-Kamenogorsk” -> „Torpedo” poprawne dzis, ale w puli jest tez „Torpedo Nizhny Novgorod”
    pule = {'hokej': {'Nomad Astana', 'Torpedo', 'Torpedo Nizhny Novgorod'}}
    ev = _ev([('hokej', '2026-09-27', '15:00', 'Nomad Astana', 'Torpedo Ust-Kamenogorsk')])
    z = _z([('hokej', '2026-09-27', None, 'Nomad Astana', 'Torpedo')])
    a, _, st = _ucz(ev, z, {'Nomad Astana': 'Nomad Astana'}, pule)
    assert a.empty and st['do przegladu: skrot z kolizja'] == 1
    assert a.attrs['przeglad'][['nazwa', 'cel']].values.tolist() == [['Torpedo Ust-Kamenogorsk', 'Torpedo']]
    # bez drugiego wpisu z tym rdzeniem — alias pewny; wpis rozniacy sie tylko znacznikiem (U20) to nie kolizja
    pule = {'hokej': {'Nomad Astana', 'Torpedo', 'Torpedo U20'}}
    a, _, _ = _ucz(ev, z, {'Nomad Astana': 'Nomad Astana'}, pule)
    assert a[['nazwa', 'cel']].values.tolist() == [['Torpedo Ust-Kamenogorsk', 'Torpedo']]
    # skrot bez zgubionego czlonu znaczacego (tylko forma prawna) — bez przegladu
    assert dopasuj.kolizja('Lugi HF', 'Lugi', {'Lugi', 'Lugi Lund'}) == []
