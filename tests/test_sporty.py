"""Bramki w sporty.py: drugie zrodlo (log5 z formy) i laczny WERDYKT."""
import pandas as pd
import pytest

import sporty


def _baza(wyg_h, wyg_g, n=10):
    """H wygrywa wyg_h z n, G wygrywa wyg_g z n (rywale spoza pary)."""
    w = []
    for t, k in (('H', wyg_h), ('G', wyg_g)):
        for i in range(n):
            w.append(dict(sport='hokej', gosp=t, gosc=f'R{i}', pg=3 if i < k else 1, pa=1 if i < k else 3))
    return pd.DataFrame(w)


def test_zgodne_daje_p_modelu():
    # forma H 8/10 -> 0.75, G 3/10 -> 1/3; log5 = 0.75*(2/3) / (0.75*(2/3) + (1/3)*0.25) = 6/7 ~ 0.857
    # Poprawka 58: przy zgodnych zrodlach P do kuponu = P modelu (docs/BACKTEST_P48.md)
    assert sporty.drugie_zrodlo(_baza(8, 3), 'hokej', 'H', 'G', 0.80) == pytest.approx(0.80)
    assert sporty.drugie_zrodlo(_baza(8, 3), 'hokej', 'H', 'G', 0.90) == pytest.approx(0.90)


def test_rozni_faworyci_to_none():
    assert sporty.drugie_zrodlo(_baza(2, 8), 'hokej', 'H', 'G', 0.70) is None


def test_mala_proba_to_none():
    assert sporty.drugie_zrodlo(_baza(8, 3, n=5), 'hokej', 'H', 'G', 0.80) is None


@pytest.mark.parametrize('skala, p_dz, n, oczekiwane', [
    (True, 0.78, 30, (0.78, [])),
    (False, 0.78, 30, (None, ['rozne ligi bez wspolnej skali'])),
    (True, None, 30, (None, ['brak zgodnego drugiego zrodla'])),
    (True, 0.78, 3, (None, ['brak danych rywala (3 mecz(e))'])),
    (False, None, 3, (None, ['rozne ligi bez wspolnej skali', 'brak zgodnego drugiego zrodla',
                             'brak danych rywala (3 mecz(e))'])),
])
def test_werdykt_meczu(skala, p_dz, n, oczekiwane):
    assert sporty.werdykt_meczu(skala, p_dz, n) == oczekiwane


@pytest.mark.parametrize('oferta, oczekiwane', [
    ('Stolfa Jakub', 'Jakub Stolfa'), ('Stolfa J.', 'Jakub Stolfa'), ('Jan Trefny', 'Trefny Jan'),
    ('Novak J.', None),            # dwaj Novakowie na J. — noga MNIEJ, nie zgadujemy
    ('Stolfa Petr', None),         # inne imie to inny gracz
])
def test_gracz_w_odwrotnej_kolejnosci(oferta, oczekiwane):
    # Liga Pro (29.09.2026): scores24 "Imie Nazwisko" albo "Nazwisko Imie", STS "Nazwisko Imie" / "Nazwisko I."
    pula = ['Jakub Stolfa', 'Trefny Jan', 'Jan Novak', 'Jiri Novak', 'Lukas Jindrak']
    assert sporty.resolve(oferta, pula) == oczekiwane


def test_liga_pro_zawsze_nie_na_kupon():
    # Poprawka 60: backtest 29.09 — Elo w Lidze Pro bez przewagi
    p, powody = sporty.werdykt_meczu(True, 0.75, 30, {'CZECH REPUBLIC | Liga Pro'})
    assert p is None and any('Liga Pro' in x for x in powody)
    assert sporty.werdykt_meczu(True, 0.75, 30, {'POLAND | Superliga'}) == (0.75, [])


@pytest.mark.parametrize('arg, nazwa', [('koszykowka', 'koszykówka'), ('pilka_reczna', 'piłka ręczna'),
                                        ('tenis-stolowy', 'tenis stołowy'), ('hokej', 'hokej'), ('xyz', 'xyz')])
def test_nazwa_sportu_bez_ogonkow(arg, nazwa):
    # Raport 29.09 12:00, usterka 6: "sporty.py typuj koszykowka" dawalo BRAK W BAZIE
    assert sporty.nazwa_sportu(arg) == nazwa


def test_aliasy_polskie_nazwy_sponsorskie():
    """29.09.2026: STS pisze nazwy sponsorskie (Orlen Wisla Plock, Aluron CMC Warta Zawiercie, King Szczecin)."""
    pula = {'Wisla Plock', 'Kielce', 'Zawiercie', 'Wilki Morskie Szczecin', 'Resovia Rzeszów', 'SKRA Bełchatów'}
    assert sporty.resolve('Orlen Wisła Płock', pula) == 'Wisla Plock'
    assert sporty.resolve('Barlinek Industria Kielce', pula) == 'Kielce'
    assert sporty.resolve('Aluron CMC Warta Zawiercie', pula) == 'Zawiercie'
    assert sporty.resolve('King Szczecin', pula) == 'Wilki Morskie Szczecin'
    assert sporty.resolve('Asseco Resovia', pula) == 'Resovia Rzeszów'
    assert sporty.resolve('PGE GiEK Skra Bełchatów', pula) == 'SKRA Bełchatów'
    assert sporty.resolve('Orlen Wisła Płock', {'Kielce'}) is None      # alias dziala tylko, gdy cel jest w puli


def test_aliasy_euroliga_i_siatkowka():
    pula = {'Fenerbahçe', 'Panathinaikos', 'Olimpia Milano', 'BC Dubai', 'Volley Perugia', 'Berlin RV', 'Maccabi Tel Aviv'}
    assert sporty.resolve('Fenerbahçe Beko', pula) == 'Fenerbahçe'
    assert sporty.resolve('Panathinaikos AKTOR', pula) == 'Panathinaikos'
    assert sporty.resolve('EA7 Emporio Armani Mediolan', pula) == 'Olimpia Milano'
    assert sporty.resolve('Dubai Basketball', pula) == 'BC Dubai'
    assert sporty.resolve('Maccabi Playtika Tel Aviv', pula) == 'Maccabi Tel Aviv'
    assert sporty.resolve('Sir Sicoma Monini Perugia', pula) == 'Volley Perugia'
    assert sporty.resolve('Berlin Recycling Volleys', pula) == 'Berlin RV'


def test_egzonimy_polskie_miasta():
    """29.09.2026 (raport 12:00): „Hapoel Tel Awiw”, „Hapoel Beer Szewa” — polskie nazwy miast."""
    pula = {'Hapoel Tel Aviv', 'Maccabi Tel Aviv', 'Hapoel Beer Sheva/Dimona', 'Tofas'}
    assert sporty.resolve('Hapoel Tel Awiw', pula) == 'Hapoel Tel Aviv'
    assert sporty.resolve('Maccabi Tel Awiw', pula) == 'Maccabi Tel Aviv'
    assert sporty.resolve('Tofas Bursa', pula) == 'Tofas'
    assert sporty.resolve('Hapoel Hajfa', pula) is None          # brak w puli -> nie zgadujemy


def test_aliasy_siatkowka_kobiet():
    pula = {'Conegliano (W)', 'Ks Rzeszow (W)', 'Fenerbahçe (W)', 'Fenerbahçe', 'LKS Lodz (W)'}
    assert sporty.resolve('Imoco Volley Conegliano', pula) == 'Conegliano (W)'        # klub tylko kobiecy
    assert sporty.resolve('Developres Rzeszów (K)', pula) == 'Ks Rzeszow (W)'
    assert sporty.resolve('Fenerbahce Medicana (K)', pula) == 'Fenerbahçe (W)'
    assert sporty.resolve('LKS Commercecon Łódź (K)', pula) == 'LKS Lodz (W)'
    assert sporty.resolve('Fenerbahce Medicana', pula) is None     # bez (K) niejednoznaczne (sekcja meska)


def test_aliasy_hokej():
    pula = {'Aksam Unia Oswiecim', 'Nesta Torun', 'Ciarko PBS Bank', 'Třinec', 'HIFK'}
    assert sporty.resolve('Re-Plast Unia Oświęcim', pula) == 'Aksam Unia Oswiecim'
    assert sporty.resolve('KH Energa Toruń', pula) == 'Nesta Torun'
    assert sporty.resolve('Marma Ciarko STS Sanok', pula) == 'Ciarko PBS Bank'
    assert sporty.resolve('HC Oceláři Třinec', pula) == 'Třinec'
    assert sporty.resolve('HIFK Helsinki', pula) == 'HIFK'


def test_aliasy_reczna_lm():
    pula = {'Paris Handball', 'Veszprem', 'Pick Szeged', 'PPD Zagreb'}
    assert sporty.resolve('Paris Saint-Germain', pula) == 'Paris Handball'
    assert sporty.resolve('One Veszprém', pula) == 'Veszprem'
    assert sporty.resolve('OTP Bank Pick Szeged', pula) == 'Pick Szeged'
    assert sporty.resolve('RK Zagreb', pula) == 'PPD Zagreb'
    assert sporty.resolve('Paris Saint-Germain', {'Paris Basketball'}) is None     # cel spoza puli -> nic


def test_samo_nazwisko_kilku_osob_nie_zgadujemy():
    """29.09.2026: „Price” -> „Sam Price” (Gerwyn, Lewis, Kane...), „Higgins” -> „Alex Higgins” — zgadywanie."""
    pula = {'Sam Price', 'Gerwyn Price', 'Lewis Price', 'Luke Littler', 'Alex Higgins', 'John Higgins'}
    assert sporty.resolve('Price', pula) is None and sporty.resolve('Higgins', pula) is None
    assert sporty.resolve('Price G.', pula) == 'Gerwyn Price' and sporty.resolve('Higgins J.', pula) == 'John Higgins'
    assert sporty.resolve('Littler', pula) == 'Luke Littler'                  # jeden kandydat -> dalej dziala
