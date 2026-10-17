"""17.10.2026: oddspapi_analiza.py (TRYB OBSERWACJI) — kurs Superbet a kurs uczciwy Pinnacle."""
import gzip
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import oddspapi_analiza as oa  # noqa: E402


def _gz(p, o):
    p.write_bytes(gzip.compress(json.dumps(o).encode()))
    return str(p)


def test_uczciwe_bez_marzy():
    p = oa.uczciwe({101: 2.0, 102: 3.5, 103: 4.0})
    assert sum(p.values()) == pytest.approx(1) and p[101] > p[102] > p[103]
    assert oa.uczciwe({101: 2.0}) is None and oa.uczciwe({101: 2.0, 102: None}) is None


def test_przewaga_ev_i_ako(tmp_path, capsys):
    # mecz A: Pinnacle 1X2 2.00/3.60/4.00 (marża ~5%), Superbet na „1” 2.30 -> przewaga ~ +10%
    # mecz B: Superbet gorszy od uczciwego; mecz C: kurs Superbet 9.0 przy uczciwym ~2 -> podejrzane, pominięte
    serie = []
    for fid, sb1 in (('A', 2.30), ('B', 1.80), ('C', 9.0)):
        for w, k in ((101, 2.0), (102, 3.6), (103, 4.0)):
            serie.append([fid, 'pinnacle', 101, w, k, k, k, 5])
        serie.append([fid, 'superbet.pl', 101, 101, sb1, sb1, sb1, 3])
    for fid in ('A', 'B', 'C'):
        serie += [[fid, 'superbet.pl', 101, 102, 3.3, None, 3.3, 1], [fid, 'superbet.pl', 101, 103, 3.7, 3.7, 3.7, 1]]
    # rynek 200: Pinnacle ma tylko 2 z 3 wyników Superbet -> niepełny, pomijany (inaczej „przewaga” zawyżona)
    serie += [['A', 'pinnacle', 200, 1, 2.0, 2.0, 2.0, 1], ['A', 'pinnacle', 200, 2, 2.0, 2.0, 2.0, 1],
              ['A', 'superbet.pl', 200, 1, 3.0, 3.0, 3.0, 1], ['A', 'superbet.pl', 200, 2, 3.0, 3.0, 3.0, 1], ['A', 'superbet.pl', 200, 3, 3.0, 3.0, 3.0, 1]]
    h = _gz(tmp_path / 'oddspapi_hist_2026-10-17_1200.json.gz', {'serie': serie})
    l = _gz(tmp_path / 'oddspapi_2026-10-17_RANO.json.gz', {'mecze': [
        {'id': 'A', 't': 1792263600, 'a': 'Alfa', 'b': 'Beta'}, {'id': 'B', 't': 1792263600, 'a': 'Gamma', 'b': 'Delta'}]})
    lista = oa.main([h, '--listy', l, '--prog', '0.03', '--nog', '4'])
    out = capsys.readouterr().out
    a = [n for n in lista if n['id'] == 'A'][0]
    p1 = (1 / 2.0) / (1 / 2.0 + 1 / 3.6 + 1 / 4.0)
    assert a['przewagaz'] == pytest.approx(p1 * 2.30 - 1) and a['ev_z'] == pytest.approx(p1 * 2.30 * 0.88 - 1)
    assert len(lista) == 6 and {n['rynek'] for n in lista} == {101}                       # bez kursu 6 h przed i rynek niepełny pominięte
    assert 'podejrzane (> 35%) 1' in out
    assert '2026-10-17: dostępnych nóg 1, w kuponie 1, kurs 2.30' in out
    assert 'Alfa - Beta | 1X2 1 | Superbet 2.3' in out


def test_brak_superbet_brak_nog(tmp_path, capsys):
    h = _gz(tmp_path / 'h.json.gz', {'serie': [['A', 'pinnacle', 101, 101, 2.0, 2.0, 2.0, 1], ['A', 'pinnacle', 101, 102, 3.0, 3.0, 3.0, 1]]})
    assert oa.main([h]) == []
    assert 'Brak nóg do oceny.' in capsys.readouterr().out
