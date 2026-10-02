"""02.10.2026 (Raport 18:00, usterka 3): klub z Primera RFEF 2025/26 po powrocie do SP2 — jedna nazwa w bazie."""
import pandas as pd

import build_kb


def _m(w):
    return pd.DataFrame(w, columns=['Division', 'MatchDate', 'HomeTeam', 'AwayTeam', 'FTHome', 'FTAway'])


def test_cd_eldense_i_celta_vigo_b_sklejone_z_nazwami_sp2(monkeypatch):
    monkeypatch.setitem(build_kb._ELO_CACHE, 'e', {})
    w = [('SP2', '2025-05-10', 'Eldense', 'Burgos', 1, 0),
         ('Spain | Primera Division RFEF', '2025-09-01', 'CD Eldense', 'Alcorcon', 2, 1),
         ('Spain | Primera Division RFEF', '2026-05-24', 'Merida', 'CD Eldense', 0, 0),
         ('Spain | Primera Division RFEF', '2026-03-01', 'Celta Vigo B', 'Arenteiro', 1, 1),
         ('SP2', '2026-09-19', 'Eldense', 'Eibar', 1, 1),
         ('SP2', '2026-09-20', 'Celta B', 'Cadiz', 0, 2)]
    out = build_kb.scal_zapis_nazw(_m(w))
    druz = set(out.HomeTeam) | set(out.AwayTeam)
    assert 'CD Eldense' not in druz and 'Celta Vigo B' not in druz
    assert ((out.HomeTeam == 'Eldense') | (out.AwayTeam == 'Eldense')).sum() == 4
    assert ((out.HomeTeam == 'Celta B') | (out.AwayTeam == 'Celta B')).sum() == 2
