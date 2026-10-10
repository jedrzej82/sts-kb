"""Raport 10.10 15:00.
  1. „Ilves Tampere” (Veikkausliiga) -> sam wpis clubelo bez meczow (liga None, ROZNE LIGI BEZ ELO); mecze sa pod „Ilves”,
     ktorego w clubelo nie ma. Ta sama klasa: Honka Espoo, TPS Turku (FC Krasnodar — alias). Sprawdzone na bazie:
     Mariehamn – Ilves liczy model.
  2. Toronto FC – CF Montreal (MLS): rozdziel_kraje robil z kanadyjskich klubow MLS dwa kluby (Puchar Kanady: „Toronto FC
     [canada]”, „Vancouver Whitecaps [canada]”, „CF Montréal”). Na bazie: zmienia sie tylko 12 wierszy tych 3 klubow.
  5. Przerwa reprezentacyjna 21.09–08.10 potwierdzona w 365 i Flashscore (zero meczow PL/LaLiga/Serie A, nizsze ligi graly)."""
import pandas as pd

import kluby
import typuj


def _m(wiersze):
    return pd.DataFrame([dict(MatchDate=d, HomeTeam=h, AwayTeam=a, Division=dv) for d, h, a, dv in wiersze])


def test_wpis_clubelo_bez_meczow_bierze_klub_z_ligi_tego_kraju():
    m = _m([('2026-09-19', 'Ilves', 'Mariehamn', 'FIN'), ('2026-09-12', 'KuPS', 'Ilves', 'FIN'),
            ('2026-09-10', 'Ilves Kissat', 'Haka', 'Finland | Kakkonen')])
    ce = pd.DataFrame([dict(club='Ilves Tampere', country='FIN', elo=1199.0), dict(club='Mariehamn', country='FIN', elo=1200.0)])
    assert typuj._z_meczami('Ilves Tampere', m, ce) == 'Ilves'                      # przed: 'Ilves Tampere' (liga None)
    # kandydat z innego kraju — bez zmiany
    m2 = _m([('2026-09-19', 'Ilves', 'Hammarby', 'SWE')])
    assert typuj._z_meczami('Ilves Tampere', m2, ce) == 'Ilves Tampere'
    # dwa kandydaci — nie zgadujemy
    m3 = _m([('2026-09-19', 'Ilves', 'Mariehamn', 'FIN'), ('2026-09-19', 'Ilves Tampere Juniors', 'KuPS', 'FIN')])
    ce3 = pd.DataFrame([dict(club='Ilves Tampere Juniors Akatemia', country='FIN', elo=1.0)])
    assert typuj._z_meczami('Ilves Tampere Juniors Akatemia', m3, ce3) == 'Ilves Tampere Juniors Akatemia'


def test_kanadyjskie_kluby_mls_nie_sa_rozdzielane():
    m = _m([('2026-09-27', 'Toronto FC', 'CF Montreal', 'USA'), ('2026-05-05', 'Toronto FC', 'Ottawa', 'Canada | Canadian Championship'),
            ('2026-09-16', 'CF Montréal', 'Vancouver Fc', 'Canada | Canadian Championship'),
            ('2026-09-20', 'Santos', 'Flamengo', 'Brazil | Serie A'), ('2026-09-21', 'Santos', 'Toluca', 'Mexico | Liga MX'),
            ('2026-09-22', 'Santos', 'Palmeiras', 'Brazil | Serie A')])
    kr = {'USA': 'usa', 'Canada | Canadian Championship': 'canada', 'Brazil | Serie A': 'brazil', 'Mexico | Liga MX': 'mexico'}
    w = kluby.rozdziel_kraje(m, kr.get, {})
    druzyny = set(w.HomeTeam) | set(w.AwayTeam)
    assert {'Toronto FC', 'CF Montreal'} <= druzyny and not any('[canada]' in d for d in druzyny)   # przed: Toronto FC [canada]
    assert 'CF Montréal' not in druzyny
    assert 'Santos [mexico]' in druzyny                                              # inne kraje — rozdzielane jak dotad


def test_alias_fc_krasnodar():
    import os
    a = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'aliasy.csv'), dtype=str)
    assert {(r.modul, r.nazwa): r.cel for r in a.itertuples()}[('typuj', 'FC Krasnodar')] == 'Krasnodar'
