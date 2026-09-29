"""zewn: wyniki koszykowki/recznej/siatkowki z Flashscore (wyniki_fsx_inne_*) — bez dubli z 365, nazwy do zapisu 365."""
import pandas as pd

import zewn

KOL = 'data,sport,kraj,turniej,runda,gosp,gosc,wg,wa,okresy_g,okresy_a,zwyciezca,nawierzchnia'.split(',')


def _w(sport, kraj, tur, g, a, wg, wa):
    return ['2026-09-28', sport, kraj, tur, '', g, a, wg, wa, '', '', 1 if wg > wa else 2, '']


def test_fsx_dubel_i_nazwy(tmp_path, monkeypatch):
    s365 = pd.DataFrame([_w('handball', 'Europe', 'EHF Champions League', 'Füchse Berlin', 'Kielce', 30, 28),
                         _w('handball', 'Germany', 'Bundesliga', 'SC Magdeburg', 'THW Kiel', 31, 29)], columns=KOL)
    fsx = pd.DataFrame([_w('handball', 'EUROPE', 'Champions League', 'Fuchse Berlin', 'Kielce', 30, 28),      # dubel 365
                        _w('handball', 'EUROPE', 'European League', 'THW Kiel', 'Benfica', 33, 30),              # nowy
                        _w('handball', 'EUROPE', 'European League', 'Magdeburg', 'Porto', 35, 30)], columns=KOL)  # nazwa -> 365
    s365.to_csv(tmp_path / 'wyniki_365_inne_2026-09.csv.gz', index=False)
    fsx.to_csv(tmp_path / 'wyniki_fsx_inne_2026-09.csv.gz', index=False)
    monkeypatch.setattr(zewn, 'ZD', str(tmp_path))
    x = zewn.inne()
    assert len(x) == 4                                           # 2 z 365 + 2 z Flashscore (dubel odrzucony)
    el = x[x.liga.str.contains('European League')]
    assert sorted(el.gosp) == ['SC Magdeburg', 'THW Kiel'] and el.liga.iloc[0].startswith('Europe |')
