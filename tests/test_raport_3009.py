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
