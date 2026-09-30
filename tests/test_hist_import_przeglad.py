"""30.09.2026 (przeglad hist_import / zewn.czytaj)."""
import gzip

import pandas as pd
import pytest

import hist_import
import zewn


def test_ten_sam_turniej():
    assert hist_import.ten_sam_turniej('Jiujiang, China', 'Jiujiang')
    assert hist_import.ten_sam_turniej('Davis Cup - World Group I', 'Davis Cup WG1 PO: FIN vs POL')
    assert not hist_import.ten_sam_turniej('Sarasota', 'Houston')          # 2026-04-07 Basavareddy–Draxl: inny turniej
    assert not hist_import.ten_sam_turniej('Parma', 'Rome')
    assert not hist_import.ten_sam_turniej('Open de Rennes', 'Open Occitanie')   # sam „open” nie wystarcza


def test_nieczytelny_plik_opcjonalny_nie_wywraca_calosci(tmp_path, monkeypatch, capsys):
    kol = 'data,sport,kraj,turniej,runda,gosp,gosc,wg,wa,okresy_g,okresy_a,zwyciezca,nawierzchnia'.split(',')
    pd.DataFrame([['2026-09-28', 'volleyball', 'Poland', 'PlusLiga', '', 'Resovia', 'Jastrzebski', 3, 1, '', '', 1, '']],
                 columns=kol).to_csv(tmp_path / 'wyniki_365_inne_2026-09.csv.gz', index=False)
    caly = gzip.compress(b'data,sport\n' + b'2026-09-28,handball\n' * 5000)
    (tmp_path / 'wyniki_fsx_inne_2026-09.csv.gz').write_bytes(caly[:len(caly) // 2])   # uciete pobranie
    monkeypatch.setattr(zewn, 'ZD', str(tmp_path))
    x = zewn.inne()
    assert len(x) == 1 and 'BLAD ODCZYTU zewn/wyniki_fsx_inne_2026-09.csv.gz' in capsys.readouterr().out


def test_blad_zewn_inne_zatrzymuje_hist_import(monkeypatch):
    for f in ('espn', 'nhl', 'nfl', 'mlb', 'esport', 'fetch'):
        monkeypatch.setattr(hist_import, f, lambda *a, **k: pd.DataFrame(columns=hist_import.COLS))
    def zly(): raise ValueError('uszkodzony plik')
    monkeypatch.setattr(zewn, 'inne', zly)
    with pytest.raises(SystemExit) as e:
        hist_import.main()
    assert 'zewn.inne' in str(e.value)
