"""06.10.2026 — oferta.py: ucieta nazwa i rynki jednej druzyny przypisane do meczu (Raport 12:00 usterka 5)."""
import pandas as pd

import oferta


def _d(w):
    return pd.DataFrame([dict(zip(['data_meczu', 'godzina_meczu', 'sport', 'gospodarz', 'gosc', 'sekcja', 'zdarzenie'], x))
                         for x in w]).reindex(columns=oferta.KOLUMNY, fill_value='')


def test_ucieta_nazwa_i_jedna_druzyna_do_meczu():
    D, S = '2026-10-04', 'PIŁKA RĘCZNA'
    d = _d([(D, '15:00', S, 'MMTS Kwidzyn', 'Ostrovia Ostrów Wielkopolski', 'Mecz', 'MMTS Kwidzyn - Ostrovia Ostrów Wielkopolski'),
            (D, '15:00', S, 'MMTS Kwidzyn', 'Ostrovia Ostrów Wielkop...', '1. połowa / wynik końcowy', 'MMTS Kwidzyn - Ostrovia Ostrów Wielkop...'),
            (D, '15:00', S, 'Ostrovia Ostrów Wielkopolski', '', '2. drużyna - liczba goli', 'Ostrovia Ostrów Wielkopolski'),
            (D, '15:00', S, 'MMTS Kwidzyn', '', '1. drużyna - liczba goli', 'MMTS Kwidzyn'),
            (D, '13:00', 'TENIS', 'Zverev Alexander', 'Djokovic Novak', 'Zwycięzca meczu', 'Zverev Alexander - Djokovic Novak'),
            (D, '13:00', 'TENIS', 'Djokovic Novak', '', '2. zawodnik - liczba gemów', 'Djokovic Novak')])
    o = []
    x = oferta.scal_zdarzenia(d, o)
    assert set(x.zdarzenie) == {'MMTS Kwidzyn - Ostrovia Ostrów Wielkopolski', 'Zverev Alexander - Djokovic Novak'}
    assert (x.gosc != '').all() and not o


def test_bez_jednoznacznego_meczu_bez_zmian():
    D, S = '2026-10-04', 'PIŁKA NOŻNA'
    d = _d([(D, '17:00', S, 'Limanovia Limanowa', 'Kalwarianka Kalwaria Zebrzy...', 'Mecz', 'Limanovia Limanowa - Kalwarianka Kalwaria Zebrzy...'),
            # druga druzyna o tej samej nazwie o tej samej godzinie, ale w innym sporcie — nie ten mecz
            (D, '18:00', S, 'Wisła Kraków', '', '1. drużyna - liczba goli', 'Wisła Kraków'),
            (D, '18:00', 'KOSZYKÓWKA', 'Wisła Kraków', 'Ślęza Wrocław', 'Mecz', 'Wisła Kraków - Ślęza Wrocław'),
            # dwa mecze z ta sama druzyna o tej godzinie — nie zgadujemy
            (D, '20:00', S, 'Polonia', '', '2. drużyna - liczba goli', 'Polonia'),
            (D, '20:00', S, 'A', 'Polonia', 'Mecz', 'A - Polonia'), (D, '20:00', S, 'B', 'Polonia', 'Mecz', 'B - Polonia')])
    o = []
    x = oferta.scal_zdarzenia(d, o)
    assert list(x.zdarzenie) == list(d.zdarzenie)
    assert any('Limanovia' in t for t in o)
