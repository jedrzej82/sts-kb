"""15.10.2026 (decyzja uzytkownika „2”): papierowy AKO O0.5 — 3 i 4 nogi O0.5 z meczow o najwyzszym P(O2.5)."""
import pandas as pd

import kupon
import typuj


def _plik(tmp_path, w):
    nogi = tmp_path / 'nogi.csv'
    pd.DataFrame(w, columns=['mecz', 'p_o25', 'p_o05', 'kurs_o05', 'kurs_o25', 'szacunek', 'polski', 'p_rynek_o25', 'p_wybor']).to_csv(
        tmp_path / 'nogi_o25.csv', index=False)
    return str(nogi)


def test_wszystkie_mecze_dnia_na_kuponach_3_4(tmp_path):
    w = [(f'M{i} - N{i}', .55, .95, 1.02, 1.40, 0, 0, .70, .80 - i * .02) for i in range(9)]   # 9 meczow >= 60%
    w += [('E - F', .58, .95, 1.03, 1.45, 1, 0, .69, .79),          # szacunek — na liscie, poza kuponem
          ('X - Y', .58, .95, '', 1.45, 0, 0, .69, .78),            # brak kursu O0.5 — na liscie, poza kuponem
          ('I - J', .50, .92, 1.04, 1.70, 0, 0, .58, .54),          # ponizej 60%
          ('M0 - N0', .55, .95, 1.02, 1.40, 0, 0, .70, .80)]        # dubel z drugiego przebiegu
    f = _plik(tmp_path, w)
    x, kup = kupon.kupony_o05(f)
    assert len(x) == 11 and 'I - J' not in set(x.mecz)
    assert [len(o['nogi']) for o in kup] == [3, 3, 3]
    assert {m for o in kup for m in o['nogi'].mecz} == {f'M{i} - N{i}' for i in range(9)}   # kazdy mecz z kursem na kuponie
    t = '\n'.join(kupon.linie_o05(f))
    assert 'MECZE DNIA Z P(O2.5) >= 60%' in t and 'SZACUNEK — poza kuponem' in t and 'brak kursu O0.5' in t
    assert 'AKOO05-3' in t and 'WYGRANY ZWRACA MNIEJ NIZ STAWKE' in t


def test_podzial_na_3_i_4():
    assert kupon.podzial(2) == [] and kupon.podzial(5) == [4] and kupon.podzial(7) == [4, 3] and kupon.podzial(10) == [4, 3, 3]
    assert all(sum(kupon.podzial(n)) == n for n in range(6, 40))


def test_typuj_zapisuje_p_o25_i_p_rynku(tmp_path, monkeypatch):
    monkeypatch.setattr(typuj, 'NOGI_PLIK', str(tmp_path / 'nogi.csv'))
    typuj._dopisz_o25('A - B', {'O2.5': 0.53, 'O0.5': 0.94}, {'O0.5': 1.01, 'O2.5': 1.34, 'U2.5': 3.0}, False, False)
    typuj._dopisz_o25('C - D', {'O2.5': 0.40}, {'O2.5': 2.1}, True, False)   # bez U2.5 i O0.5
    x = pd.read_csv(typuj.plik_o25(typuj.NOGI_PLIK))
    pr = (1 / 1.34) / (1 / 1.34 + 1 / 3.0)
    assert abs(x.p_rynek_o25[0] - pr) < 1e-4 and abs(x.p_wybor[0] - (0.53 + pr) / 2) < 1e-4
    assert pd.isna(x.kurs_o05[1]) and abs(x.p_wybor[1] - 0.40) < 1e-9 and x.szacunek[1] == 1
