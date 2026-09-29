"""Zloty zestaw dopasowan nazw — przypadki z Poprawek i usterek z raportow.
Kazda para to realny blad z przeszlosci; test pilnuje, zeby nie wrocil.
Znane, jeszcze nienaprawione defekty sa oznaczone xfail(strict=True): gdy ktos je naprawi,
test zacznie przechodzic i pytest to zglosi — wtedy nalezy zdjac oznaczenie."""
import pytest

import sezon
import typuj


# ---------- sezon.norm (29.09.2026: formy prawne tylko jako cale czlony) ----------
@pytest.mark.parametrize('nazwa, oczekiwane', [
    ('FC Schalke 04', 'schalke 04'),          # bylo "halke 04"
    ('Hearts Scotland', 'hearts scotland'),   # bylo "hearts otland"
    ('Sporting Achaia', 'sporting achaia'),   # bylo "sporting haia"
    ('Śląsk Wrocław', 'slask wroclaw'),       # bylo "slask wrocaw"
    ('Łódzki KS', 'lodzki ks'),               # bylo "odzki ks"
    ('FCSB', 'fcsb'),                         # " fc" nie moze ucinac poczatku slowa
    ('FC Porto', 'porto'),
    ('Sporting CP', 'sporting'),
    ('AC Milan', 'milan'),
    ('Racing Club', 'racing club'),           # "club" celowo NIE jest forma prawna (Racing != Racing Club)
    ('Olimpia Asunción', 'olimpia asuncion'),
])
def test_sezon_norm(nazwa, oczekiwane):
    assert sezon.norm(nazwa) == oczekiwane


# ---------- sezon.znajdz ----------
ARKUSZ = [
    {'druzyna': 'Olimpia', 'liga': 'PAR', 'mecze': '10'},
    {'druzyna': 'Libertad', 'liga': 'PAR', 'mecze': '10'},
    {'druzyna': 'Schalke 04', 'liga': 'GER2', 'mecze': '8'},
    {'druzyna': 'Chicago Fire', 'liga': 'MLS', 'mecze': '30'},
    {'druzyna': 'Austria (W)', 'liga': 'INT', 'mecze': '5'},
    {'druzyna': 'Bayern Munich', 'liga': 'GER', 'mecze': '6'},
]


@pytest.mark.parametrize('nazwa, oczekiwana', [
    ('Olimpia Asuncion', 'Olimpia'),        # Poprawka 55
    ('Libertad Asuncion', 'Libertad'),      # Poprawka 55
    ('FC Schalke 04', 'Schalke 04'),
    ('Bayern Monachium', 'Bayern Munich'),  # polskie nazwy miast
    ('Nueva Chicago', None),                # 22.09: podstawialo Chicago Fire
    ('Australia (W)', None),                # Australia != Austria — bez difflib
])
def test_sezon_znajdz(nazwa, oczekiwana):
    w, _ = sezon.znajdz(ARKUSZ, nazwa)
    assert (w['druzyna'] if w else None) == oczekiwana


# ---------- typuj.norm / resolve ----------
def test_typuj_norm_polskie_litery():
    assert typuj.norm('Wisła Płock') == 'wislaplock'   # 21.09: bylo "wisapock"


PULA = {'Legia', 'Colegiales', 'Independiente', 'Chicago Fire', 'Wisla Plock', 'Bayern Munich',
        'Athletic Club', 'Hammarby', 'Pyx'}


@pytest.mark.parametrize('nazwa, oczekiwana', [
    ('Legia Warszawa', 'Legia'),
    ('Colegiales', 'Colegiales'),       # Legia != Colegiales (podciag "legia")
    ('Nueva Chicago', None),
    ('Wisła Płock', 'Wisla Plock'),
    ('Bayern Monachium', 'Bayern Munich'),
    ('xyz', None),                      # 21.09: resolve zwracal ZAWSZE cos
    ('Пых', None),                      # cyrylica -> pusty klucz nie moze byc dzika karta
])
def test_typuj_resolve(nazwa, oczekiwana):
    assert typuj.resolve(nazwa, PULA) == oczekiwana


@pytest.mark.parametrize('nazwa', ['Hammarby Talang', 'Jong Ajax', 'Juventus Primavera'])
def test_mlodziez_i_rezerwy_nie_do_pierwszej_druzyny(nazwa):
    # 29.09.2026 (faza 3): nowe znaczniki w nazwy.py — raport 25.09 12:00 (Hammarby Talang -> Hammarby)
    assert typuj.resolve(nazwa, PULA | {'Ajax', 'Juventus'}) is None


def test_druga_druzyna_pasuje_do_siebie():
    assert typuj.resolve('Jong Ajax', {'Ajax', 'Jong Ajax'}) == 'Jong Ajax'


def test_znaczniki_wspolne_dla_modulow():
    import sporty
    assert typuj._znaczniki is sporty._znaczniki


def test_skrot_jest_zapamietywany_do_kontroli_lacznej():
    # "Independiente Yumbo" -> "Independiente" nadal zwraca klub (rdzen jednoznaczny), ale jest zapisany
    # w _SKROTY — club() wymaga wtedy wspolnej ligi obu druzyn meczu (dopasowanie laczne, faza 3)
    typuj._SKROTY.clear()
    assert typuj.resolve('Independiente Yumbo', PULA) == 'Independiente'
    assert typuj._SKROTY == {'Independiente Yumbo': 'Independiente'}


def test_wspolna_liga():
    import pandas as pd
    from nazwy import wspolna_liga
    m = pd.DataFrame({'MatchDate': pd.to_datetime(['2026-08-01', '2026-08-08', '2026-08-15', '2023-01-01']),
                      'HomeTeam': ['Independiente', 'Quindio', 'Cortulua', 'Independiente'],
                      'AwayTeam': ['Racing', 'Cortulua', 'Quindio', 'Quindio'],
                      'Division': ['ARG', 'COL2', 'COL2', 'COL2']})
    assert wspolna_liga(m, 'Quindio', 'Cortulua')
    assert not wspolna_liga(m, 'Independiente', 'Quindio')   # wspolna liga tylko sprzed 2 lat
    assert not wspolna_liga(m, 'Independiente', None)


def test_brak_nowych_sprzecznosci_w_aliasach():
    # faza 3: nowy alias, ktory kieruje znana nazwe do INNEGO klubu niz inna tabela, musi zostac
    # swiadomie przejrzany i dopisany do rejestr_konflikty_znane.csv (albo poprawiony)
    import rejestr
    n = rejestr.nowe_konflikty()
    assert n.empty, n.to_string()


def test_aliasy_z_pliku_kod_wygrywa(tmp_path):
    from nazwy import aliasy_z_pliku
    f = tmp_path / 'aliasy.csv'
    f.write_text('modul,nazwa,cel,uzasadnienie,data\n'
                 'typuj,Independiente Yumbo,Independiente Valle del Cauca,Primera B COL,2026-09-29\n'
                 'typuj,Legia Warszawa,Inny Klub,probuje nadpisac kod,2026-09-29\n'
                 'sporty,Lukko Rauma,Lukko,inny modul,2026-09-29\n', encoding='utf-8')
    d = {'legiawarszawa': 'Legia'}
    assert aliasy_z_pliku('typuj', typuj.norm, d, str(f)) == 1
    assert d == {'legiawarszawa': 'Legia', 'independienteyumbo': 'Independiente Valle del Cauca'}


def test_aliasy_csv_ma_naglowek():
    import csv
    from nazwy import ALIASY_CSV
    assert csv.DictReader(open(ALIASY_CSV, encoding='utf-8')).fieldnames == ['modul', 'nazwa', 'cel', 'uzasadnienie', 'data']


def test_druzyna_kobiet_rozny_zapis_znacznika():
    # rozliczenie 27.09: STS "Bay FC [K]", baza "Bay FC W"; rezerwy kobiet "Barcelona B W" to inna druzyna
    import typuj
    pula = {'Bay FC', 'Bay FC W', 'Barcelona', 'Barcelona B', 'Barcelona W', 'Barcelona B W'}
    assert typuj.resolve('Bay FC [K]', pula) == 'Bay FC W'
    assert typuj.resolve('Barcelona [K]', pula) == 'Barcelona W'
    assert typuj.resolve('Barcelona B [K]', pula) == 'Barcelona B W'
    assert typuj.resolve('Bay FC', pula) == 'Bay FC'
