"""30.09.2026 (przeglad build_kb._aliasy_raz): jedno zbiegniecie meczow nie scala roznych klubow."""
import pandas as pd

import build_kb


def _m(w):
    return pd.DataFrame(w, columns=['Division', 'MatchDate', 'HomeTeam', 'AwayTeam', 'FTHome', 'FTAway']).assign(
        MatchDate=lambda x: pd.to_datetime(x.MatchDate))


def test_fc_united_to_nie_spalding_united():
    # 2025-11-01: Bamber Bridge 0:2 FC United i Alvechurch 0:2 Spalding United — ta sama liga, dzien, wynik
    m = _m([('ENG7', '2025-11-01', 'Bamber Bridge', 'FC United', 0, 2),
            ('ENG7', '2025-11-01', 'Alvechurch', 'Spalding United', 0, 2),
            ('ENG7', '2025-11-08', 'FC United', 'Leek Town', 1, 0),
            ('ENG7', '2025-11-08', 'Spalding United', 'Matlock', 2, 2)])
    out, n = build_kb._aliasy_raz(m.copy())
    assert n == 0 and {'FC United', 'Spalding United'} <= set(out.AwayTeam) | set(out.HomeTeam)


def test_rezerwy_nie_sa_aliasem_pierwszej_druzyny():
    w = [('EST2', f'2025-0{k}-01', 'Tammeka', x, 1, 0) for k, x in ((4, 'FC Nomme United II'), (5, 'FC Nomme United II'),
                                                                  (6, 'FC Nomme United II'))]
    w += [('EST2', f'2025-0{k}-01', 'Tammeka', 'Nomme United', 1, 0) for k in (4, 5, 6)]   # drugie zrodlo gubi „II”
    out, n = build_kb._aliasy_raz(_m(w))
    assert n == 0 and 'FC Nomme United II' in set(out.AwayTeam)


def test_prawdziwy_alias_nadal_dziala():
    # ten sam mecz z dwoch zrodel: „Fluminense FC” / „Fluminense” (pewna strona), „CA Mineiro” / „Atletico-MG” z eliminacji
    w = []
    for i, (dz, wy) in enumerate((('2025-05-01', (2, 0)), ('2025-05-08', (1, 1)), ('2025-05-15', (3, 2)))):
        w += [('BRA', dz, 'Fluminense FC', 'CA Mineiro', *wy), ('BRA', dz, 'Fluminense', 'Atletico-MG', *wy)]
    out, n = build_kb._aliasy_raz(_m(w))
    assert n >= 2 and out.HomeTeam.nunique() == 1 and out.AwayTeam.nunique() == 1
