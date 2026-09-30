"""30.09.2026 (Raport 12:00, usterka 1): nazwy z oferty STS odrzucane mimo jednoznacznego klubu w bazie
oraz dwa wiersze tego samego meczu po zmianie nazwy druzyny w 365scores."""
import os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sporty, zewn


def test_skroty_formy_prawnej():
    assert sporty.resolve('BC Lietkabelis', {'Lietkabelis', 'Rytas'}, 'koszykówka') == 'Lietkabelis'
    assert sporty.resolve('Besiktas JK', {'Besiktas', 'Besiktas (W)', 'Fenerbahce'}, 'koszykówka') == 'Besiktas'
    assert sporty.resolve('BM Logrono La Rioja', {'Logrono La Rioja', 'Barcelona'}, 'piłka ręczna') == 'Logrono La Rioja'
    assert sporty.resolve('Tatabanya KC', {'Tatabanya', 'Veszprem'}, 'piłka ręczna') == 'Tatabanya'
    # miasto nadal nie jest czlonem ogolnym — bez aliasu nie zgadujemy
    assert sporty.resolve('Slovan Lublana', {'Slovan', 'Celje'}, 'piłka ręczna') is None


def test_aliasy_z_raportu():
    assert sporty.resolve('KooKoo Kouvola', {'KooKoo', 'Tappara'}, 'hokej') == 'KooKoo'
    assert sporty.resolve('KAC Klagenfurt', {'EC-KAC', 'Graz 99ers'}, 'hokej') == 'EC-KAC'
    assert sporty.resolve('CB Canarias Tenerife', {'La Laguna Tenerife', 'Barcelona'}, 'koszykówka') == 'La Laguna Tenerife'
    assert sporty.resolve('Pelister Bitola', {'Eurofarm Pelister', 'Eurofarm Pelister 2'}, 'piłka ręczna') == 'Eurofarm Pelister'
    # alias dziala tylko, gdy cel jest w puli
    assert sporty.resolve('KooKoo Kouvola', {'Tappara'}, 'hokej') is None


def _df(rows):
    return pd.DataFrame(rows, columns=['data', 'sport', 'liga', 'gosp', 'gosc', 'pg', 'pa', 'dogrywka'])


def test_dubel_po_zmianie_nazwy():
    d = _df([('2026-09-26', 'koszykówka', 'L', 'Lietkabelis', 'Tauragės KK Tauragė', 85, 79, 0),
             ('2026-09-26', 'koszykówka', 'L', 'Lietkabelis', 'Tauragė', 85, 79, 0),
             ('2026-09-20', 'koszykówka', 'L', 'Tauragė', 'Rytas', 70, 80, 0),
             # odwrocona strona: ten sam mecz zapisany jako gosc
             ('2026-09-27', 'koszykówka', 'L', 'Sydney', 'Illawarra Hawks', 100, 121, 0),
             ('2026-09-27', 'koszykówka', 'L', 'Illawarra Hawks', 'Sydney Kings', 121, 100, 0)])
    o = zewn._przemianowane_dubli(d)
    assert len(o) == 3
    # zostaje nazwa rywala z wieksza liczba meczow w danych
    assert set(o[o.data == '2026-09-26'].gosc) == {'Tauragė'}


def test_wyniki_czeste_bez_zmian():
    d = _df([('2026-09-24', 'siatkówka', 'L', 'Canada (W)', 'Cuba (W)', 3, 0, 0),
             ('2026-09-24', 'siatkówka', 'L', 'Canada (W)', 'Puerto Rico (W)', 3, 0, 0),
             ('2026-09-24', 'hokej', 'L', 'Tappara', 'Ilves', 3, 2, 0),
             ('2026-09-24', 'hokej', 'L', 'Tappara', 'KooKoo', 3, 2, 0),
             ('2026-09-24', 'koszykówka', 'L', 'A', 'B', 20, 0, 0),   # walkower — za malo punktow, by rozstrzygac
             ('2026-09-24', 'koszykówka', 'L', 'A', 'C', 20, 0, 0)])
    assert len(zewn._przemianowane_dubli(d)) == 6


def _hist(rows):
    d = pd.DataFrame(rows, columns=['data', 'sport', 'liga', 'gosp', 'gosc'])
    return d.assign(data=pd.to_datetime(d.data))


def test_potwierdzenie_rywalem():
    """Raport 15:00: „Karpat Oulu” / „SaiPa Lappeenranta” — jedyni kandydaci, grali ze soba w Liidze.
    Ta para ma od 30.09 alias w aliasy.csv, wiec mechanizm sprawdzamy na nazwach bez aliasu."""
    d = _hist([('2026-01-14', 'hokej', 'Finland | Liiga', 'Jokerit', 'Pelicans'),
               ('2026-09-20', 'hokej', 'Finland | Liiga', 'Tappara', 'Ilves')])
    pula = {'Jokerit', 'Pelicans', 'Tappara', 'Ilves'}
    sporty._KANDYDAT.clear()
    h, g = sporty.resolve('Jokerit Helsinki', pula, 'hokej'), sporty.resolve('Pelicans Lahti', pula, 'hokej')
    assert (h, g) == (None, None)
    assert sporty.potwierdz_rywalem(d, 'hokej', ('Jokerit Helsinki', 'Pelicans Lahti'), (h, g)) == ['Jokerit', 'Pelicans']


def test_aliasy_raport_3009_1500():
    """Raport 30.09 15:00: nazwy STS z doklejonym miastem/przedrostkiem — alias trafia w jedyny klub ligi."""
    pula = {'Karpat', 'Saipa', 'TPS', 'Nybro', "HC TWK Innsbruck 'Die Haie'", 'Tappara'}
    for n, cel in (('Karpat Oulu', 'Karpat'), ('SaiPa Lappeenranta', 'Saipa'), ('TPS Turku', 'TPS'),
                   ('Nybro Vikings', 'Nybro'), ('TWK Innsbruck', "HC TWK Innsbruck 'Die Haie'")):
        assert sporty.resolve(n, pula, 'hokej') == cel
    pula = {'Kauhajoen Karhu', 'Karhu Basket', 'Handlova', 'BK Svit', 'Levice', 'Neuchâtel', 'PAOK'}
    for n, cel in (('Kauhajoki Karhu', 'Kauhajoen Karhu'), ('MBK Handlova', 'Handlova'), ('Iskra Svit', 'BK Svit'),
                   ('Patrioti Levice', 'Levice'), ('Union Neuchatel', 'Neuchâtel'), ('PAOK Saloniki', 'PAOK')):
        assert sporty.resolve(n, pula, 'koszykówka') == cel
    assert sporty.resolve('TPS Turku', {'Tappara'}, 'hokej') is None   # alias tylko, gdy cel jest w puli


def test_bez_meczu_ligowego_nadal_mniej():
    """„Independiente Yumbo”: mecz z rywalem tylko w pucharze miedzynarodowym albo dawno — nic nie potwierdza."""
    d = _hist([('2026-05-01', 'koszykówka', 'South America | Liga Sudamericana', 'Independiente', 'Rival'),
               ('2022-01-01', 'koszykówka', 'Colombia | Liga', 'Independiente', 'Rival'),
               ('2026-09-01', 'koszykówka', 'Colombia | Liga', 'Rival', 'Other')])
    pula = {'Independiente', 'Rival', 'Other'}
    sporty._KANDYDAT.clear()
    h, g = sporty.resolve('Independiente Yumbo', pula, 'koszykówka'), sporty.resolve('Rival', pula, 'koszykówka')
    assert h is None and g == 'Rival'
    assert sporty.potwierdz_rywalem(d, 'koszykówka', ('Independiente Yumbo', 'Rival'), (h, g)) == (None, 'Rival')


def test_niejednoznaczny_rdzen_bez_kandydata():
    """Rdzen wspolny dla kilku klubow („Slovan”, „Slovan Bratislava”) — brak kandydata, rywal nic nie zmienia."""
    d = _hist([('2026-09-01', 'piłka ręczna', 'Slovenia | 1. NLB', 'Slovan', 'Celje')])
    pula = {'Slovan', 'Slovan Bratislava', 'Celje'}
    sporty._KANDYDAT.clear()
    h = sporty.resolve('Slovan Lublana', pula, 'piłka ręczna')
    assert h is None and 'Slovan Lublana' not in sporty._KANDYDAT
    assert sporty.potwierdz_rywalem(d, 'piłka ręczna', ('Slovan Lublana', 'Celje'), (h, 'Celje')) == (None, 'Celje')


def test_aliasy_audyt_oferty_0110():
    assert sporty.resolve('PSG', {'Paris Handball', 'Nantes'}, 'piłka ręczna') == 'Paris Handball'
    assert sporty.resolve('HSV Hamburg', {'HSV Handball', 'ThSV Eisenach'}, 'piłka ręczna') == 'HSV Handball'
    assert sporty.resolve('Penarol Mar del Plata', {'Penarol', 'Ca Penarol'}, 'koszykówka') == 'Penarol'
    assert sporty.resolve('Gimnasia Indalo', {'Gimnasia y Esgrima (CR)', 'Gimnasia Y Esgrima La Plata'}, 'koszykówka') == 'Gimnasia y Esgrima (CR)'


def test_aliasy_pilka_audyt_0110():
    import typuj
    pula = {'Junior FC', 'CD Junior', 'Atletico Nacional', 'Cerro Porteño', 'CD Platense', 'Platense Municipal'}
    assert typuj.resolve('CD Junior Barranquilla', pula) == 'Junior FC'
    assert typuj.resolve('Atletico Nacional Medellin', pula) == 'Atletico Nacional'
    assert typuj.resolve('Cerro Porteno Asuncion', pula) == 'Cerro Porteño'
    assert typuj.resolve('CD Platense Zacatecoluca', pula) == 'Platense Municipal'


def test_tenis_powtorzony_czlon():
    import tenis
    pula = {'Bryce Nakashima', 'Brandon Nakashima'}
    assert tenis.resolve('Nakashima Bryce Nakashima', pula) == 'Bryce Nakashima'
    assert tenis.resolve('Nakashima Nakashima', pula) is None          # dwa czlony — bez zgadywania


def test_reprezentacje_concacaf():
    import typuj
    pula = {'Dominica', 'Dominican Republic', 'British Virgin Islands', 'United States Virgin Islands', 'Montserrat'}
    assert typuj.resolve('Dominika', pula) == 'Dominica'
    assert typuj.resolve('Dominikana', pula) == 'Dominican Republic'
    assert typuj.resolve('Brytyjskie Wyspy Dziewicze', pula) == 'British Virgin Islands'
    assert typuj.resolve('Wyspy Dziewicze USA', pula) == 'United States Virgin Islands'


def test_sezon_formy_niemieckie_i_aliasy():
    import sezon
    w = [{'druzyna': 'Stuttgart', 'liga': 'Bundesliga', 'mecze': '5'}, {'druzyna': 'Wolfsburg', 'liga': 'Bundesliga', 'mecze': '5'},
         {'druzyna': 'Atletico Nacional', 'liga': 'Primera A COL', 'mecze': '9'}, {'druzyna': 'Junior FC', 'liga': 'Primera A COL', 'mecze': '9'}]
    assert sezon.znajdz(w, 'VfB Stuttgart')[0]['druzyna'] == 'Stuttgart'
    assert sezon.znajdz(w, 'VfL Wolfsburg')[0]['druzyna'] == 'Wolfsburg'
    assert sezon.znajdz(w, 'Atletico Nacional Medellin')[0]['druzyna'] == 'Atletico Nacional'
    assert sezon.znajdz(w, 'CD Junior Barranquilla')[0]['druzyna'] == 'Junior FC'
    assert sezon.znajdz(w, 'VfB Lubeck')[0] is None                   # inna druzyna — nie zgadujemy


def test_sezon_tenis_drugie_imie_w_arkuszu():
    import sezon
    w = [{'druzyna': 'Joel Josef Schwaerzler', 'mecze': '5'}, {'druzyna': 'Yulia Starodubtsewa', 'mecze': '5'},
         {'druzyna': 'Anna Maria Kowalska', 'mecze': '3'}, {'druzyna': 'Anna Beata Kowalska', 'mecze': '3'}]
    assert sezon.znajdz(w, 'Schwaerzler Joel', sport='tenis')[0]['druzyna'] == 'Joel Josef Schwaerzler'
    assert sezon.znajdz(w, 'Starodubtseva Yuliia', sport='tenis')[0]['druzyna'] == 'Yulia Starodubtsewa'
    assert sezon.znajdz(w, 'Kowalska Anna', sport='tenis')[0] is None          # dwie rozne osoby — bez zgadywania


def test_rozliczenie_skroty_krajow_i_zwyciezca_bez_strony():
    import typuj, dzienniki
    pula = {'North Macedonia', 'Northern Ireland', 'South Korea', 'North Korea', 'Macedonia'}
    assert typuj.resolve('Macedonia Pn.', pula) == 'North Macedonia'
    assert typuj.resolve('Irlandia Pn.', pula) == 'Northern Ireland'
    assert typuj.resolve('Korea Pd.', pula) == 'South Korea' and typuj.resolve('Korea Pn.', pula) == 'North Korea'
    assert dzienniki._bez_strony('zwyciezca') and dzienniki._bez_strony('Zwycięzca meczu (z dogrywką)')
    assert not dzienniki._bez_strony('Zwyciezca 1') and not dzienniki._bez_strony('zwyciezca Hapoel')


def test_sporty_kraj_z_terminarza():
    d = _hist([('2026-09-20', 'hokej', 'Kazakhstan | Championship', 'Torpedo', 'Beibarys Atyrau'),
               ('2026-09-21', 'hokej', 'Russia | KHL', 'Torpedo Nizhny Novgorod', 'CSKA'),
               ('2026-09-22', 'hokej', 'Russia | VHL', 'Torpedo-Gorkiy', 'Dynamo'),
               ('2026-09-23', 'hokej', 'Europe | Champions Hockey League', 'Torpedo Nizhny Novgorod', 'Tappara')])
    mt = dict(kraj='KAZAKHSTAN', turniej='Championship', gosp='Beibarys Atyrau', gosc='Torpedo')
    wyn = (sporty.resolve('Beibarys Atyrau', set(d.gosp) | set(d.gosc), 'hokej'), None)
    assert sporty.kraj_z_terminarza(d, 'hokej', ('Beibarys Atyrau', 'Torpedo Ust-Kamenogorsk'), wyn, mt) == ('Beibarys Atyrau', 'Torpedo')
    # kraj ogolny albo brak meczu — bez zmian
    assert sporty.kraj_z_terminarza(d, 'hokej', ('A', 'Torpedo Ust-Kamenogorsk'), (None, None), dict(mt, kraj='World')) == (None, None)
    assert sporty.kraj_z_terminarza(d, 'tenis stołowy', ('A', 'B'), (None, None), mt) == (None, None)
