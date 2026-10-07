"""07.10.2026 — audyt usterek (Raport 29.09 21:00 nr 3): dwie delty typy_log z ta sama noga zapisana jako „Mołdawia” i
„Moldawia” byly po scaleniu DWOMA typami (klucz porownywany dosłownie)."""
import pandas as pd

import dzienniki


def test_ta_sama_noga_rozna_pisownia_jeden_wiersz(tmp_path):
    kat = tmp_path / 'dz'
    kat.mkdir()
    k = 'data,gosp,gość,rynek,p\n'
    (kat / 'typy_log 2026-09-29 18_00.csv').write_text(k + '2026-09-29,Mołdawia,Wyspy Owcze,12,0.71\n', encoding='utf-8')
    (kat / 'typy_log 2026-09-29 21_00.csv').write_text(k + '2026-09-29,Moldawia,Wyspy  Owcze,12,0.71\n'
                                                      + '2026-09-29,Moldawia,Wyspy Owcze,O1.5,0.70\n', encoding='utf-8')
    dzienniki.scal(str(kat), cel=str(tmp_path))
    d = pd.read_csv(tmp_path / 'typy_log.csv', dtype=str, keep_default_na=False)
    assert sorted(d.rynek) == ['12', 'O1.5']           # rozne rynki zostaja osobno
    assert not any(c.startswith('_k_') for c in d.columns)
