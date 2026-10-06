"""06.10.2026 — Raport 18:00: puchar EFL Trophy (kluby z roznych poziomow), drugi wpis clubelo, kluby rozbite (Alfreton)."""
import pandas as pd

import build_kb
import typuj


def _m(w):
    return pd.DataFrame(w, columns=['Division', 'MatchDate', 'HomeTeam', 'AwayTeam', 'FTHome', 'FTAway'])


def test_terminarz_potwierdza_pare_w_pucharze(monkeypatch):
    # „Grimsby Town” -> Grimsby (E3), „Burton Albion” -> Burton (E2); terminarz 365: EFL Trophy, „Grimsby – Burton Albion”
    pool = {'Grimsby', 'Burton', 'Grimsby Borough'}
    mt = {'kraj': 'England', 'turniej': 'EFL Trophy', 'gosp': 'Grimsby', 'gosc': 'Burton Albion'}
    assert typuj.terminarz_potwierdza_pare('Grimsby', 'Burton', mt, pool, ('england', 'england'))
    # liga (nie puchar) albo terminarz wskazuje inny klub — dalej NIEPEWNE
    assert not typuj.terminarz_potwierdza_pare('Grimsby', 'Burton', dict(mt, turniej='League Two'), pool, ('england', 'england'))
    assert not typuj.terminarz_potwierdza_pare('Grimsby Borough', 'Burton', mt, pool, ('england', 'england'))
    assert not typuj.terminarz_potwierdza_pare('Grimsby', 'Burton', None, pool, ('england', 'england'))


def test_drugi_wpis_clubelo_bez_meczow():
    # clubelo: „Plymouth Argyle” (bez meczow) i „Plymouth” (mecze E2); „Plymouth Parkway” (mecze) nie jest w clubelo
    m = _m([('E2', '2026-10-03', 'Plymouth', 'Burton', 1, 0), ('X', '2026-09-29', 'Plymouth Parkway', 'Y', 0, 0)])
    elo = pd.DataFrame({'club': ['Plymouth Argyle', 'Plymouth', 'Burton'], 'country': ['ENG', 'ENG', 'ENG'],
                        'elo': [1480, 1480, 1400], 'date': ['2026-09-01'] * 3})
    assert typuj._z_meczami('Plymouth Argyle', m, elo) == 'Plymouth'
    assert typuj._z_meczami('Plymouth Argyle', m) == 'Plymouth Argyle'          # bez clubelo — jak dotad


def test_alfreton_sklejony(monkeypatch):
    monkeypatch.setattr(build_kb, '_elo_nazwy', lambda: {})
    out = build_kb.scal_zapis_nazw(_m([('EC', '2015-04-25', 'Alfreton Town', 'Gateshead', 1, 0),
                                        ('England | Non League Premier', '2026-10-03', 'Alfreton', 'FC United', 2, 1)]))
    out = out[0] if isinstance(out, tuple) else out
    assert len({'Alfreton Town', 'Alfreton'} & (set(out.HomeTeam) | set(out.AwayTeam))) == 1
