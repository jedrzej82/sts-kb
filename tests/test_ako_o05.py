"""15.10.2026 (decyzja uzytkownika „2”): papierowy AKO O0.5 — 3 i 4 nogi O0.5 z meczow o najwyzszym P(O2.5)."""
import pandas as pd

import kupon
import typuj


def _plik(tmp_path, w):
    nogi = tmp_path / 'nogi.csv'
    pd.DataFrame(w, columns=['mecz', 'p_o25', 'p_o05', 'kurs_o05', 'kurs_o25', 'szacunek', 'polski', 'p_rynek_o25', 'p_wybor']).to_csv(
        tmp_path / 'nogi_o25.csv', index=False)
    return str(nogi)


def test_wybor_po_p_o25_rozne_mecze_bez_szacunkow(tmp_path):
    f = _plik(tmp_path, [('A - B', .55, .94, 1.02, 1.40, 0, 0, .70, .625), ('C - D', .60, .95, 1.01, 1.30, 0, 0, .74, .67),
                         ('E - F', .58, .95, 1.03, 1.45, 1, 0, .69, .635),      # szacunek — pomijany
                         ('G - H', .62, .96, 1.02, 1.42, 0, 0, .66, .64), ('I - J', .50, .92, 1.04, 1.70, 0, 0, .58, .54),
                         ('C - D', .60, .95, 1.01, 1.30, 0, 0, .74, .67)])     # dubel z drugiego przebiegu
    o = kupon.kupon_o05(f, 3)
    assert list(o['nogi'].mecz) == ['C - D', 'G - H', 'A - B'] and abs(o['kurs'] - 1.01 * 1.02 * 1.02) < 1e-9
    assert kupon.kupon_o05(f, 4) is None                     # I - J ponizej 60%, E - F szacunek
    t = '\n'.join(kupon.linie_o05(f))
    assert 'PAPIEROWY' in t and 'nawet WYGRANY zwraca mniej niz stawke' in t and 'AKOO05-3' in t


def test_brak_pliku_o25(tmp_path):
    assert kupon.kupon_o05(str(tmp_path / 'nogi.csv'), 3) is None
    assert 'brak' in kupon.linie_o05(str(tmp_path / 'nogi.csv'))[0]


def test_typuj_zapisuje_p_o25_i_p_rynku(tmp_path, monkeypatch):
    monkeypatch.setattr(typuj, 'NOGI_PLIK', str(tmp_path / 'nogi.csv'))
    typuj._dopisz_o25('A - B', {'O2.5': 0.53, 'O0.5': 0.94}, {'O0.5': 1.01, 'O2.5': 1.34, 'U2.5': 3.0}, False, False)
    typuj._dopisz_o25('C - D', {'O2.5': 0.40}, {'O2.5': 2.1}, True, False)   # bez U2.5 i O0.5
    x = pd.read_csv(typuj.plik_o25(typuj.NOGI_PLIK))
    pr = (1 / 1.34) / (1 / 1.34 + 1 / 3.0)
    assert abs(x.p_rynek_o25[0] - pr) < 1e-4 and abs(x.p_wybor[0] - (0.53 + pr) / 2) < 1e-4
    assert pd.isna(x.kurs_o05[1]) and abs(x.p_wybor[1] - 0.40) < 1e-9 and x.szacunek[1] == 1
