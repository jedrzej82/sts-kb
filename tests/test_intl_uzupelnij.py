"""30.09.2026 (proba generalna): martj42 (intl) konczy sie 26.08 — wrzesniowe mecze reprezentacji z zewn/."""
import pandas as pd

import build_kb

KOL = 'data,sport,kraj,turniej,runda,gosp,gosc,wg,wa,okresy_g,okresy_a,zwyciezca,nawierzchnia'.split(',')


def test_mecze_reprezentacji_dopisane_tylko_znane_i_seniorskie(tmp_path):
    intl = pd.DataFrame([('2025-06-10', 'United States', 'Peru', 1, 0, 'Friendly', '', '', False),
                         ('2026-08-26', 'Poland', 'Czech Republic', 2, 2, 'Friendly', '', '', False)],
                        columns=['date', 'home_team', 'away_team', 'home_score', 'away_score', 'tournament', 'city', 'country', 'neutral'])
    w = [['2026-09-26', 'football', 'International', 'Friendly International', '', 'USA', 'Peru', 4, 1, '', '', 1, ''],
         ['2026-09-27', 'football', 'Europe', 'UEFA Nations League', '', 'Czechia', 'Poland', 1, 1, '', '', 0, ''],
         ['2026-09-27', 'football', 'International', 'Friendly International', '', 'Poland U19', 'Peru U19', 2, 0, '', '', 1, ''],
         ['2026-09-27', 'football', 'Europe', 'UEFA Nations League', '', 'Atlantis', 'Poland', 0, 3, '', '', 2, ''],
         ['2026-08-20', 'football', 'International', 'Friendly International', '', 'USA', 'Peru', 9, 9, '', '', 0, '']]
    pd.DataFrame(w, columns=KOL).to_csv(tmp_path / 'wyniki_365_pilka_2026-09.csv.gz', index=False)
    pd.DataFrame([w[1][:3] + ['UEFA Nations League - League B'] + w[1][4:]], columns=KOL).to_csv(
        tmp_path / 'wyniki_fs_pilka_2026-09.csv.gz', index=False)                       # ten sam mecz z Flashscore
    o = build_kb.uzupelnij_intl(intl, str(tmp_path))
    nowe = o.iloc[len(intl):]
    assert sorted(zip(nowe.home_team, nowe.away_team)) == [('Czech Republic', 'Poland'), ('United States', 'Peru')]
    assert (nowe.date > '2026-08-26').all()                                              # nic sprzed konca martj42
