"""06.10.2026 — KONTROLA PDF w oferta.py: podejrzany odczyt PDF STS -> mecz NIE za pieniadze (decyzja uzytkownika)."""
import pandas as pd

import oferta


def _w(zd, sek, wybor, kurs, rynek=None, godz='18:00', liga='L'):
    g, a = zd.split(' - ')
    return dict(data_meczu='2026-10-06', godzina_meczu=godz, sport='PIŁKA NOŻNA', liga=liga, gospodarz=g, gosc=a,
                rynek=rynek or wybor, kurs=f'{kurs:.2f}', sekcja=sek, wybor=wybor, zdarzenie=zd)


def _d(w):
    return pd.DataFrame(w).reindex(columns=oferta.KOLUMNY, fill_value='')


def test_poprawny_odczyt_ok():
    d = _d([_w('A - B', 'Mecz', '1', 1.80), _w('A - B', 'Mecz', 'X', 3.60), _w('A - B', 'Mecz', '2', 4.50),
            _w('A - B', 'Liczba goli', '+', 1.40, 'O1.5'), _w('A - B', 'Liczba goli', '-', 2.80, 'U1.5'),
            _w('A - B', 'Liczba goli', '+', 2.05, 'O2.5'), _w('A - B', 'Liczba goli', '-', 1.75, 'U2.5')])
    linia, zle = oferta.kontrola_pdf(d)
    assert linia.startswith('KONTROLA PDF: OK') and not zle


def test_bledy_odczytu_wykryte():
    d = _d([_w('A - B', 'Mecz', '1', 1.80), _w('A - B', 'Mecz', 'X', 1.20), _w('A - B', 'Mecz', '2', 1.30),   # zle etykiety
            _w('C - D', 'Liczba goli', '+', 1.40, 'O2.5'), _w('C - D', 'Liczba goli', '-', 2.80, 'U2.5'),
            _w('C - D', 'Liczba goli', '+', 1.30, 'O3.5'), _w('C - D', 'Liczba goli', '-', 3.40, 'U3.5'),   # O spada
            _w('E - F', 'Mecz', '1', 2.0), _w('E - F', 'Zakład bez remisu', '1', 1.5, godz='20:00')])        # 2 godziny
    linia, zle = oferta.kontrola_pdf(d, ['POMINIETA LINIA z kursami str. 3: Nowa sekcja 1.45 2.60'])
    assert set(zle) == {'A - B', 'C - D', 'E - F'}
    assert 'marza 1X2' in zle['A - B'] and 'nie rosnie' in zle['C - D'] and 'godzina' in zle['E - F']
    assert 'NIE ZA PIENIADZE' in linia and '1 linii z kursami pominietych' in linia
