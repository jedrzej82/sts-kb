import argparse

import pandas as pd
import pytest

import kupon


def _d(rows):
    d = pd.DataFrame(rows)
    for c, v in (('sport', ''), ('szacunek', 0), ('polski', 0), ('marza', 1.05), ('kryteria', 6)):
        if c not in d: d[c] = v
    return d


def _a(**kw):
    a = dict(depozyt=100.0, faza=1, wydane_lacznie=0.0)
    a.update(kw); return argparse.Namespace(**a)


def test_ev_i_kelly_po_podatku():
    assert kupon.ev(0.8, 1.5) == pytest.approx(0.8 * 1.5 * 0.88 - 1)
    assert kupon.kelly_cwiartka(0.5, 1.1) == 0.0


def test_poziom_to_najslabsza_noga():
    assert kupon.poziom([6, 6]) == 'A' and kupon.poziom([6, 4]) == 'B' and kupon.poziom([3]) == 'C' and kupon.poziom([1, 6]) == 'D'


def test_k1_bez_dwoch_nog_z_meczu():
    d = _d([dict(mecz='A-B', rynek='1X', p=0.95, kurs=1.25), dict(mecz='A-B', rynek='O0.5', p=0.93, kurs=1.20),
            dict(mecz='C-D', rynek='1X', p=0.90, kurs=1.35)])
    o = kupon.najlepszy(d, 'K1')
    assert o is not None and len({d.at[i, 'mecz'] for i in o['nogi']}) == len(o['nogi'])
    assert o['p'] >= 0.78 and o['kurs'] >= 1.42 and o['ev'] > 0


def test_k3_wymaga_ev_5_procent():
    d = _d([dict(mecz='A-B', rynek='1', p=0.60, kurs=1.95), dict(mecz='C-D', rynek='2', p=0.56, kurs=2.20)])
    o = kupon.najlepszy(d, 'K3')
    assert o['nogi'] == [1] and o['ev'] >= 0.05


def test_brak_kombinacji():
    assert kupon.najlepszy(_d([dict(mecz='A-B', rynek='1X', p=0.70, kurs=1.10)]), 'K1') is None


@pytest.mark.parametrize('zmiana, powod', [
    (dict(polski=True), 'polski'), (dict(poziom='D'), 'poziom D'), (dict(ev=-0.01), 'EV'),
    (dict(marza_max=1.12), 'marza'), (dict(szacunki=2), 'szacunek'),
])
def test_bramki_daja_papierowy(zmiana, powod):
    o = dict(p=0.8, kurs=1.6, ev=kupon.ev(0.8, 1.6), szacunki=0, polski=False, marza_max=1.05, poziom='A')
    o.update(zmiana)
    st, p = kupon.za_pieniadze(o, 'K1', _a(), 0, 0)
    assert st == 0 and powod in p


def test_stawka_faza_kelly_i_limity():
    o = dict(p=0.8, kurs=1.6, ev=kupon.ev(0.8, 1.6), szacunki=0, polski=False, marza_max=1.05, poziom='A')
    assert kupon.za_pieniadze(o, 'K1', _a(), 0, 0) == (5, None)            # faza 1, poziom A = 5 zl
    assert kupon.za_pieniadze(o, 'K1', _a(), 8, 1)[0] == 2                 # limit 10 zl dziennie
    assert kupon.za_pieniadze(o, 'K1', _a(), 0, 3)[1].startswith('limit')  # 3 kupony dziennie
    assert kupon.za_pieniadze(o, 'K1', _a(wydane_lacznie=300), 0, 0)[1].startswith('budzet')


def test_k5_ponizej_2_maks_2_zl():
    o = dict(p=0.62, kurs=1.95, ev=kupon.ev(0.62, 1.95), szacunki=0, polski=False, marza_max=1.05, poziom='A')
    assert kupon.za_pieniadze(o, 'K5', _a(depozyt=500), 0, 0)[0] == 2


def test_k5_omija_polski_klub_gdy_jest_inna_kombinacja(capsys):
    import os, tempfile
    d = _d([dict(mecz='Arsenal - Leeds', rynek='1X', p=0.90, kurs=1.22), dict(mecz='PSV - Heracles', rynek='1', p=0.80, kurs=1.40),
            dict(mecz='Legia - Lech', rynek='1X', p=0.78, kurs=1.45, polski=1), dict(mecz='Inter - Lecce', rynek='O1.5', p=0.84, kurs=1.30),
            dict(mecz='Bayern - Mainz', rynek='1', p=0.86, kurs=1.28)])
    f = os.path.join(tempfile.mkdtemp(), 'n.csv'); d.to_csv(f, index=False)
    kupon.main([f, '--depozyt', '100'])
    k5 = capsys.readouterr().out.split('K5:')[1]
    assert 'Legia' not in k5 and 'PAPIEROWY' not in k5


# 29.09.2026 — przeglad kupon.py: budzet 300 zl i K5 8 zl dziennie liczone lacznie
def test_budzet_300_z_kuponami_tego_przebiegu(tmp_path, capsys):
    rows = [dict(mecz=f'M{i}', rynek='1', p=p, kurs=k) for i, (p, k) in enumerate([(0.9, 1.3), (0.9, 1.3), (0.88, 1.4), (0.87, 1.45), (0.62, 2.0), (0.6, 2.1)])]
    f = tmp_path / 'nogi.csv'; _d(rows).to_csv(f, index=False)
    kupon.main([str(f), '--depozyt', '200', '--wydane-lacznie', '296'])
    stawki = [int(x.split('stawka ')[1].split(' zl')[0]) for x in capsys.readouterr().out.splitlines() if 'DO GRY' in x]
    assert sum(stawki) <= 4


def test_k5_limit_8_zl_z_wczesniejszymi():
    o = dict(ev=0.1, polski=0, szacunki=0, marza_max=1.05, poziom='A', p=0.55, kurs=2.25)
    assert kupon.za_pieniadze(o, 'K5', _a(depozyt=2000.0, k5_dzis=5), 5, 1) == (3, None)
    assert kupon.za_pieniadze(o, 'K5', _a(depozyt=2000.0, k5_dzis=8), 5, 1)[0] == 0
