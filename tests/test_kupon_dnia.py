"""08.10.2026 — KUPON DNIA (decyzja uzytkownika: codziennie jeden AKO o najwyzszej szansie). Dane: nogi z Raportu 08.10 18:00."""
import pandas as pd

import kupon


def _nogi(tmp_path, wiersze):
    p = tmp_path / 'nogi.csv'
    pd.DataFrame(wiersze, columns=['mecz', 'rynek', 'p', 'kurs', 'sport', 'szacunek', 'polski', 'marza', 'ev_dodatni']).to_csv(p, index=False)
    return kupon.wczytaj(str(p))


R18 = [('Maghreb Fez - Raja', 'U4.5', 0.916, 1.03, 'pilka', 0, 0, 1.06, 0),
       ('UCV Moquegua - Cienciano', 'U4.5', 0.854, 1.12, 'pilka', 0, 0, 1.06, 0),
       ('Shamrock - Drogheda', 'U4.5', 0.824, 1.17, 'pilka', 0, 0, 1.06, 0),
       ('MC Oran - ES Setif', '12', 0.747, 1.35, 'pilka', 0, 0, 1.06, 0),
       ('UCV Moquegua - Cienciano', '12', 0.729, 1.30, 'pilka', 0, 0, 1.06, 0),
       ('BKS Bydgoszcz - Czarni Radom', 'Z1', 0.95, 1.30, 'siatkowka', 0, 1, 1.06, 1)]


def test_dwie_najpewniejsze_nogi_z_roznych_meczow_z_kursem_ponad_podatek(tmp_path):
    w = _nogi(tmp_path, R18)
    o = kupon.kupon_dnia(w)
    assert sorted(w.loc[o['nogi'], 'mecz']) == ['Maghreb Fez - Raja', 'UCV Moquegua - Cienciano']
    assert o['kurs'] >= kupon.DNIA_MIN_KURS and abs(o['p'] - (0.886 * 0.824)) < 1e-3
    tekst = '\n'.join(kupon.linie_dnia(w, 5))
    assert 'KUPON DNIA' in tekst and 'tag KD' in tekst and 'stawka 5 zl' in tekst


def test_kurs_laczny_ponizej_progu_albo_brak_nog_to_brak(tmp_path):
    w = _nogi(tmp_path, [('A - B', 'U4.5', 0.95, 1.02, 'pilka', 0, 0, 1.06, 0), ('C - D', 'U4.5', 0.95, 1.03, 'pilka', 0, 0, 1.06, 0)])
    assert kupon.kupon_dnia(w) is None            # 1,02 x 1,03 = 1,05 — wygrana po podatku mniejsza od stawki
    assert 'brak' in kupon.linie_dnia(w)[0]
    w = _nogi(tmp_path, [('A - B', 'U4.5', 0.95, 1.10, 'pilka', 1, 0, 1.06, 0), ('C - D', 'U4.5', 0.95, 1.10, 'pilka', 0, 1, 1.06, 0)])
    assert kupon.kupon_dnia(w) is None            # szacunek i polski klub nie wchodza
