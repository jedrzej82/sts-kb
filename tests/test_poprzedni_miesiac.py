"""01.10.2026: plik poprzedniego miesiaca w zewn/ musi siegac jego konca — repo mialo wrzesien tylko do 20.09,
a paczka.zip niesie poprzedni miesiac tylko w dniach 1-3; od 4. dnia baza tracilaby cicho koniec miesiaca."""
import datetime as dt
import gzip
import os

import pandas as pd

import przebieg

ZD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'zewn')


def _plik(p, do):
    p.write_bytes(gzip.compress(f'data,gosp\n2026-09-01,A\n{do},B\n'.encode()))


def _bledy(tmp_path, monkeypatch, dzis, do):
    monkeypatch.setattr(przebieg, 'ZD', str(tmp_path))
    monkeypatch.setattr(przebieg, 'DZIS', dzis)
    for r in ('365_pilka', '365_inne', 'fs_inne', 'fs_pilka'):
        _plik(tmp_path / f'wyniki_{r}_2026-09.csv.gz', do)
        _plik(tmp_path / f'wyniki_{r}_2026-10.csv.gz', '2026-10-03')
    return [b for b in przebieg.kontrola_zewn() if '2026-09 niepelny' in b]


def test_poprzedni_miesiac_niepelny_to_blad(tmp_path, monkeypatch):
    assert len(_bledy(tmp_path, monkeypatch, dt.date(2026, 10, 4), '2026-09-20')) == 4


def test_poprzedni_miesiac_pelny_bez_bledu(tmp_path, monkeypatch):
    assert _bledy(tmp_path, monkeypatch, dt.date(2026, 10, 4), '2026-09-30') == []
    assert _bledy(tmp_path, monkeypatch, dt.date(2026, 10, 4), '2026-09-29') == []   # ostatni dzien bez meczow


def test_wrzesien_w_repo_pelny():
    for r in ('365_pilka', '365_inne', 'fs_inne', 'fs_pilka', 'fsx_inne', 'lp_inne', 'lol_inne'):
        d = pd.read_csv(os.path.join(ZD, f'wyniki_{r}_2026-09.csv.gz'), usecols=['data'], dtype=str)
        assert d.data.str[:10].max() >= '2026-09-29', r
