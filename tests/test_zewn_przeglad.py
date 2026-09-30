"""30.09.2026 (przeglad zewn.py): duble pod dwiema nazwami ligi/sportu, serie tego samego dnia, WTA 125."""
import pandas as pd

import zewn

KOL = 'data,sport,kraj,turniej,runda,gosp,gosc,wg,wa,okresy_g,okresy_a,zwyciezca,nawierzchnia'.split(',')


def _w(sport, kraj, tur, g, a, wg, wa, data='2026-09-20', zw=None):
    return [data, sport, kraj, tur, '', g, a, wg, wa, '', '', zw if zw else (1 if wg > wa else 2), '']


def _zapisz(tmp_path, monkeypatch, nazwa, wiersze):
    pd.DataFrame(wiersze, columns=KOL).to_csv(tmp_path / nazwa, index=False)
    monkeypatch.setattr(zewn, 'ZD', str(tmp_path))


def test_hokej_pod_dwiema_nazwami_sportu_raz(tmp_path, monkeypatch):
    _zapisz(tmp_path, monkeypatch, 'wyniki_365_inne_2026-09.csv.gz',
            [_w('hockey', 'Denmark', 'Ligaen', 'Odense Bulldogs', 'Rungsted Cobras', 1, 3),
             _w('ice-hockey', 'Denmark', 'Ligaen', 'Odense Bulldogs', 'Rungsted Cobras', 1, 3)])
    assert len(zewn.inne()) == 1


def test_seria_tego_samego_dnia_zostaje_lustro_odpada(tmp_path, monkeypatch):
    _zapisz(tmp_path, monkeypatch, 'wyniki_365_inne_2026-09.csv.gz',
            [_w('basketball', 'Colombia', 'LBP', 'Titanes', 'Piratas', 118, 94),
             _w('basketball', 'Colombia', 'LBP', 'Titanes', 'Piratas', 117, 122),      # drugi mecz serii, data przesunieta
             _w('volleyball', 'Peru', 'LNSV', 'Regatas', 'Alianza', 1, 3),
             _w('volleyball', 'Peru', 'LNSV', 'Regatas', 'Alianza', 3, 1)])            # lustro = sprzecznosc
    x = zewn.inne()
    assert sorted(zip(x.pg, x.pa)) == [(117, 122), (118, 94)]


def test_ten_sam_mecz_pod_dwiema_nazwami_ligi_raz(tmp_path, monkeypatch):
    w = [_w('football', 'Germany', 'Regional League North', f'N{i}', f'M{i}', 2, 1, data=f'2025-{8 + i // 28:02d}-{1 + i % 28:02d}')
         for i in range(70)]
    w += [_w('football', 'Germany', 'Regionalliga', f'R{i}', f'S{i}', 1, 1, data=f'2025-{8 + i // 28:02d}-{1 + i % 28:02d}')
          for i in range(60)]
    w += w[:5]                                                               # zwykly dubel pliku
    w += [r[:3] + ['Regionalliga'] + r[4:] for r in w[:9]]                   # te same mecze pod druga nazwa
    _zapisz(tmp_path, monkeypatch, 'wyniki_365_pilka_2026-09.csv.gz', w)
    p = zewn.pilka()
    assert p.duplicated(['MatchDate', 'HomeTeam', 'AwayTeam']).sum() == 0 and len(p) == 130
    assert (p[p.HomeTeam == 'N0'].Division.str.contains('North')).all()     # zostaje pod liczniejsza liga


def test_wta125_challenger_to_wta(tmp_path, monkeypatch):
    _zapisz(tmp_path, monkeypatch, 'wyniki_365_inne_2026-09.csv.gz',
            [_w('tennis', 'WTA 125K', 'Limoges Challenger', 'Anhelina Kalinina', 'Elsa Jacquemot', 2, 1, zw='1')])
    t = zewn.tenis()
    assert t.tour.tolist() == ['WTA']
