"""typuj.elo_aktualne: Elo przepisywane bez zmian (liga porzucona przez clubelo) = brak Elo."""
import datetime as dt

import pandas as pd

import typuj


def test_zamrozone_elo_pominiete():
    daty = [f'2025-{m:02d}-01' for m in range(1, 13)] + [f'2026-{m:02d}-01' for m in range(1, 10)]
    rows = [('Legia', 'POL', 1480.0 + min(i, 5), d) for i, d in enumerate(daty)]          # od 2025-06 stala wartosc
    rows += [('Arsenal', 'ENG', 1900.0 + i, d) for i, d in enumerate(daty)]              # zmienia sie co miesiac
    e = pd.DataFrame(rows, columns=['club', 'country', 'elo', 'date'])
    ost, stare = typuj.elo_aktualne(e, dt.date(2026, 9, 29))
    assert 'Legia' in stare and 'Arsenal' not in stare
    assert ost.zmiana['Legia'] == pd.Timestamp('2025-06-01') and ost.elo['Arsenal'] == 1920.0


def test_przerwa_zimowa_to_nie_zamrozenie():
    rows = [('Bodoe Glimt', 'NOR', v, d) for v, d in [(1700.0, '2025-10-01'), (1710.0, '2025-11-15'),
                                                       (1710.0, '2026-01-01'), (1710.0, '2026-03-01'), (1715.0, '2026-04-01')]]
    ost, stare = typuj.elo_aktualne(pd.DataFrame(rows, columns=['club', 'country', 'elo', 'date']), dt.date(2026, 4, 2))
    assert not stare
