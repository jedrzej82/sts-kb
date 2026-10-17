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


def test_nazwy_rynkow_i_wyniki_rozliczen(tmp_path, capsys):
    serie = []
    for fid, sb1 in (('A', 2.30), ('B', 2.40)):
        for w, k in ((101, 2.0), (102, 3.6), (103, 4.0)):
            serie.append([fid, 'pinnacle', 101, w, k, k, k, 5])
        serie += [[fid, 'superbet.pl', 101, 101, sb1, sb1, sb1, 3], [fid, 'superbet.pl', 101, 102, 3.3, 3.3, 3.3, 1],
                  [fid, 'superbet.pl', 101, 103, 3.7, 3.7, 3.7, 1]]
    h = _gz(tmp_path / 'h.json.gz', {'serie': serie})
    r = tmp_path / 'oddspapi_rynki.json'
    r.write_text(json.dumps({'101': ['Full Time Result', 0, 'fulltime', {'101': '1', '102': 'X', '103': '2'}]}))
    z = _gz(tmp_path / 'oddspapi_rozl_2026-10-18_0230.json.gz', {'wyniki': [['A', 101, 101, 'WIN'], ['B', 101, 101, 'LOSE']]})
    oa.main([h, '--rynki', str(r), '--rozliczenia', z])
    out = capsys.readouterr().out
    assert 'Full Time Result: 1 [WIN] | Superbet 2.3' in out and 'Full Time Result: 1 [LOSE] | Superbet 2.4' in out
    assert f'WYNIKI nóg z przewagą >= 3% (rozliczenia OddsPapi): 2 nóg, trafione 1, zysk {2.30 * 0.88 - 2:+.2f} zł' in out
    assert '— nie wszedł' in out                                                          # AKO z A i B: B przegrało
    assert oa.zysk('HALFWIN', 2.0, 0.12) == pytest.approx(0.38) and oa.zysk('UNDECIDED', 2.0, 0.12) is None


def _nogi(n_meczow, przewagi, dzien0=1792252800, meczow_dziennie=40):
    out, info = [], {}
    for i in range(n_meczow):
        fid = f'm{i}'
        info[fid] = {'t': dzien0 + (i // meczow_dziennie) * 86400}
        for j, e in enumerate(przewagi(i)):
            out.append(dict(id=fid, rynek=101, wynik=101 + j, przewaga6=0.05, przewagaz=e, pz=0.5, kurs_sb=2.1))
    return out, info


def test_werdykt_za_malo_dalej_stop():
    nogi_, info = _nogi(50, lambda i: [0.05, 0.04])
    assert oa.werdykt(nogi_, info, 0.03)[0] == 'ZA MAŁO DANYCH' and '100/200' in oa.werdykt(nogi_, info, 0.03)[1]
    nogi_, info = _nogi(150, lambda i: [0.06 + 0.02 * (i % 3 - 1), 0.05])
    w, uz = oa.werdykt(nogi_, info, 0.03)
    assert w == 'DALEJ' and '300 nóg w 150 meczach' in uz
    nogi_, info = _nogi(150, lambda i: [-0.02 + 0.04 * (i % 2), -0.03])
    assert oa.werdykt(nogi_, info, 0.03)[0] == 'STOP'
    # mało okazji: 8 dni, 2 okazje dziennie
    nogi_, info = _nogi(16, lambda i: [0.05], meczow_dziennie=2)
    w, uz = oa.werdykt(nogi_, info, 0.03)
    assert w == 'STOP' and '2.0/dzień' in uz


def test_bootstrap_po_meczach_przedzial():
    nogi_, _ = _nogi(100, lambda i: [0.1 if i % 2 else -0.1] * 3)
    sr, lo, hi = oa.bootstrap_po_meczach(nogi_)
    assert sr == pytest.approx(0) and lo < 0 < hi and hi - lo > 0.02                   # mecze, nie nogi: szeroki przedział
