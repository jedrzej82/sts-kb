"""Liga Pro (29.09.2026): ta sama para kilka razy dziennie — id meczu scores24 w kolumnie runda rozroznia mecze."""
import pandas as pd

import zewn

KOL = 'data,sport,kraj,turniej,runda,gosp,gosc,wg,wa,okresy_g,okresy_a,zwyciezca,nawierzchnia'.split(',')


def _w(runda, wg, wa):
    return ['2026-09-29', 'table-tennis', 'CZECH REPUBLIC', 'Liga Pro', runda, 'Jakub Vales', 'Lukas Jindrak',
            wg, wa, '', '', 1 if wg > wa else 2, '']


def test_dwa_mecze_pary_jednego_dnia_i_duplikat(tmp_path, monkeypatch):
    d = pd.DataFrame([_w('sc24:a', 3, 1), _w('sc24:b', 1, 3), _w('sc24:a', 3, 1)], columns=KOL)
    d.to_csv(tmp_path / 'wyniki_lp_inne_2026-09.csv.gz', index=False)
    monkeypatch.setattr(zewn, 'ZD', str(tmp_path))
    x = zewn.inne()
    assert len(x) == 2 and sorted(zip(x.pg, x.pa)) == [(1, 3), (3, 1)]
    assert set(x.sport) == {'tenis stołowy'}
