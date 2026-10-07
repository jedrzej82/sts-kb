"""07.10.2026 — AKO NISKI KURS (prosba uzytkownika): 6–10 nog pilkarskich z roznych meczow, P − 2 pp >= 90%, tylko papierowy."""
import pandas as pd

import kupon


def _w(nogi):
    return pd.DataFrame([dict(mecz=m, rynek=r, p=p, kurs=k, sport=s, szacunek=sz, polski=0, marza=1.05, kryteria=0, ev_dodatni=0)
                         for m, r, p, k, s, sz in nogi])


def test_buduje_od_6_nog_z_roznych_meczow():
    nogi = [(f'A{i} - B{i}', 'O0.5', 0.97 - i * 0.005, 1.06, 'pilka', 0) for i in range(8)]
    nogi += [('A0 - B0', 'U4.5', 0.99, 1.03, 'pilka', 0),            # ten sam mecz — drugi raz nie
             ('T1 - T2', 'Z1', 0.99, 1.05, 'tenis', 0),              # nie pilka
             ('S1 - S2', 'O0.5', 0.99, 1.04, 'pilka', 1),            # szacunek
             ('N1 - N2', 'O1.5', 0.91, 1.20, 'pilka', 0)]            # 0,91 − 2 pp < 90%
    o = kupon.ako_niski(_w(nogi))
    w = _w(nogi)
    assert len(o['nogi']) == 8 and len({w.at[i, 'mecz'] for i in o['nogi']}) == 8
    assert all(w.at[i, 'sport'] == 'pilka' and w.at[i, 'szacunek'] == 0 for i in o['nogi'])
    assert abs(o['p'] - (w.loc[o['nogi']].p - 0.02).prod()) < 1e-12
    assert 'PAPIEROWY' in kupon.linie_niski(w)[0]


def test_za_malo_nog_brak():
    w = _w([(f'A{i} - B{i}', 'O0.5', 0.95, 1.06, 'pilka', 0) for i in range(5)])
    assert kupon.ako_niski(w) is None and 'brak' in kupon.linie_niski(w)[0]


def test_najwyzej_10_nog():
    w = _w([(f'A{i} - B{i}', 'O0.5', 0.97, 1.04, 'pilka', 0) for i in range(14)])
    assert len(kupon.ako_niski(w)['nogi']) == 10


def test_ostrzezenie_gdy_wygrana_mniejsza_od_stawki():
    # test na ofertach 02–06.10: 8 nog po 1,01–1,03 = kurs 1,11; 1,11 x 0,88 < 1
    w = _w([(f'A{i} - B{i}', 'O0.5', 0.99, 1.013, 'pilka', 0) for i in range(8)])
    assert any('mniej niz stawke' in x for x in kupon.linie_niski(w))
    w = _w([(f'A{i} - B{i}', 'O0.5', 0.97, 1.10, 'pilka', 0) for i in range(8)])
    assert not any('mniej niz stawke' in x for x in kupon.linie_niski(w))
