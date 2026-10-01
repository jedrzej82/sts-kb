"""01.10.2026 SETTLEMENT v2: kod anomalii (kolumna „kategoria” Rozliczenia) z warstwa bledu.
Stan, wynik i uwaga nogi bez zmian — sprawdzone na 209 nogach ako_log 22-30.09 (0 zmian stanu/wyniku/uwagi)."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dzienniki  # noqa: E402

T = pd.Timestamp

# komunikaty, ktore kod rozliczen naprawde zwraca (wzorce z dzienniki.py) -> oczekiwany kod
KOMUNIKATY = [
    ('mecz 2026-10-02 jeszcze bez wyniku — rozliczy kolejny przebieg (nie dopasowano: Panama)', 'MECZ_PRZYSZLY'),
    ('brak wynikow z tych dni (zrodlo konczy sie 2026-09-28)', 'ZRODLO_OPOZNIONE'),
    ('brak wynikow z tych dni', 'ZRODLO_OPOZNIONE'),
    ('zdarzenie bez „A - B”', 'ZAPIS_BEZ_PARY'),
    ('rynek „zwyciezca” BEZ STRONY w ako_log — nie zgadujemy (zapisuj „Zwyciezca 1/2” albo nazwe druzyny)', 'RYNEK_BEZ_STRONY'),
    ('zwrot (DNB przy remisie)', 'ZWROT'),
    ('rynek „handicap -1.5” nieobslugiwany', 'RYNEK_NIEOBSLUGIWANY'),
    ('rynek „X” bez remisu w tym sporcie', 'BRAK_REMISU_W_SPORCIE'),
    ('brak informacji o dogrywce', 'DOGRYWKA_NIEZNANA'),
    ('remis przy rynku zwyciezcy — sprawdz recznie', 'REMIS_PRZY_ZWYCIEZCY'),
    ('kilka meczow tej pary w oknie +-1 dnia — nie zgadujemy', 'KILKA_MECZOW'),
    ('kilka pasujacych meczow (2) — nie zgadujemy', 'KILKA_MECZOW'),
    ('A - B: kilka meczow tej pary tego dnia (rozne wyniki) — nie zgadujemy', 'KILKA_MECZOW'),
    ('nie dopasowano: Maccabi Ironi Kiryat Gat', 'NAZWA_NIEDOPASOWANA'),
    ('Lukko - Ilves: brak meczu w oknie +-1 dnia', 'BRAK_MECZU'),
]


@pytest.mark.parametrize('uwaga,kod', KOMUNIKATY)
def test_kazdy_komunikat_ma_kod(uwaga, kod):
    assert dzienniki.kod_anomalii('BRAK WYNIKU', uwaga) == kod


def test_kazdy_kod_ma_warstwe_i_wzorzec_z_listy():
    kody = {k for k, _, _ in dzienniki.ANOMALIE}
    assert kody == {k for _, k in KOMUNIKATY}       # nowy kod = nowy przypadek w KOMUNIKATY
    assert all(w for _, w, _ in dzienniki.ANOMALIE)


def test_rozstrzygniete():
    assert dzienniki.kod_anomalii('TRAFIONY', '') == ''
    assert dzienniki.kod_anomalii('PRZEGRANY', 'sprawdz dopasowanie: Fortuna Koeln -> Fortuna Koln') == 'DOPASOWANIE_DO_SPRAWDZENIA'
    assert dzienniki.kod_anomalii('TRAFIONY', 'dopasowano po jednej druzynie: A - B = C - D (sprawdz)') == 'DOPASOWANIE_DO_SPRAWDZENIA'
    assert dzienniki.kod_anomalii('BRAK WYNIKU', 'cos nowego') == 'INNE'


def _W(pilka=(), inne=()):
    return dict(pilka=pd.DataFrame(list(pilka), columns=['d', 'h', 'a', 'g', 'ga', 'hg', 'ha']),
                tenis=pd.DataFrame(columns=['d', 'w', 'l', 'score']),
                inne=pd.DataFrame(list(inne), columns=['d', 'sport', 'h', 'a', 'pg', 'pa', 'ot']))


def test_dnb_zwrot_oddzielony_od_rynku_nieobslugiwanego():
    W = _W(pilka=[(T('2026-09-28'), 'Legia Warsaw', 'Lech Poznan', 1, 1, None, None)])
    r = dict(sport='pilka', zdarzenie='Legia Warszawa - Lech Poznan', data='2026-09-28', uwaga='')
    st, wyn, uw = dzienniki.rozlicz_noge(dict(r, rynek='DNB_1'), W)
    assert (st, wyn, dzienniki.kod_anomalii(st, uw)) == ('BRAK WYNIKU', '1:1', 'ZWROT')
    st, wyn, uw = dzienniki.rozlicz_noge(dict(r, rynek='handicap -1.5'), W)
    assert (st, dzienniki.kod_anomalii(st, uw)) == ('BRAK WYNIKU', 'RYNEK_NIEOBSLUGIWANY')


def test_kategoria_w_rozliczeniu_i_frazy_p119():
    W = _W(inne=[(T('2026-09-28'), 'dart', 'Luke Humphries', 'Josh Rock', 6, 4, 0)])
    ako = pd.DataFrame([dict(data='2026-09-30', godzina_uruchomienia='21:00', tag='K3', nr_kuponu='1', noga_nr='1',
                             sport='dart', zdarzenie='Woodhouse Luke - Aspinall Nathan', rynek='Zwyciezca 1', P='70',
                             kurs='1.5', status='NIE GRAC', uwaga='', kurs_zamkniecia=''),
                        dict(data='2026-09-30', godzina_uruchomienia='21:00', tag='K3', nr_kuponu='1', noga_nr='RAZEM',
                             sport='', zdarzenie='', rynek='', P='70', kurs='1.5', status='NIE GRAC', uwaga='', kurs_zamkniecia='')])
    roz, _ = dzienniki.rozlicz_dzien('2026-09-30', ako, W)
    noga = roz.iloc[0]
    assert noga.TRAFIONY_PRZEGRANY == 'BRAK WYNIKU' and noga.kategoria == 'ZRODLO_OPOZNIONE'
    assert 'zrodlo konczy sie 2026-09-28' in noga.uwaga          # fraza wyszukiwana przez P119 bez zmian
