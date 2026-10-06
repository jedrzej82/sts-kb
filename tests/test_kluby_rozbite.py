"""06.10.2026 — ten sam klub z dwoch zrodel (football-data do spadku, 365scores od 2025) sklejany w build_kb
(Raport 12:00 usterka 4: „Hyde United NIESWIEZA 2014-04-26”, „Welling United NIESWIEZA 2016-04-30”)."""
import pandas as pd

import build_kb
import kluby


def _scal(w, monkeypatch):
    monkeypatch.setattr(build_kb, '_elo_nazwy', lambda: {})
    m = pd.DataFrame(w, columns=['Division', 'MatchDate', 'HomeTeam', 'AwayTeam', 'FTHome', 'FTAway'])
    out = build_kb.scal_zapis_nazw(m)
    out = out[0] if isinstance(out, tuple) else out
    return out


def test_stary_i_nowy_wpis_klubu_sklejone(monkeypatch):
    out = _scal([('EC', '2014-04-26', 'Hyde United', 'Alfreton Town', 1, 2),
                 ('England | Non League Premier', '2026-10-03', 'Hyde', 'Ilkeston', 2, 2),
                 ('EC', '2016-04-30', 'Welling United', 'Alfreton Town', 0, 1),
                 ('England | Non League Premier', '2026-10-03', 'Welling Utd', 'Ilkeston', 1, 0),
                 ('EC', '2012-04-28', 'AFC Telford United', 'Alfreton Town', 1, 1),
                 ('EC', '2015-04-25', 'Telford United', 'Alfreton Town', 0, 0),
                 ('England | National League N/S', '2026-09-26', 'AFC Telford', 'Ilkeston', 3, 1)], monkeypatch)
    n = set(out.HomeTeam) | set(out.AwayTeam)
    for stary, nowy in (('Hyde United', 'Hyde'), ('Welling United', 'Welling Utd')):
        assert len({stary, nowy} & n) == 1                       # jeden wpis klubu
        k = ({stary, nowy} & n).pop()
        assert out[(out.HomeTeam == k) | (out.AwayTeam == k)].MatchDate.max() == '2026-10-03'
    assert len({'AFC Telford United', 'Telford United', 'AFC Telford'} & n) == 1


def test_nastepcy_to_nie_ten_sam_klub():
    # Wimbledon FC (do 2004) i AFC Wimbledon, Austin Bold (USL) i Austin FC — celowo poza lista
    cele = {(k[1], v) for k, v in kluby.SCAL_RECZNIE.items()}
    for a, b in (('AFC Wimbledon', 'Wimbledon'), ('Wimbledon', 'AFC Wimbledon'), ('Austin FC', 'Austin'),
                 ('Austin', 'Austin FC'), ('Airdrie Utd', 'Airdrie'), ('Clydebank FC', 'Clydebank')):
        assert (a, b) not in cele
