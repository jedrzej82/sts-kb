"""swiezosc.py: przerwa reprezentacyjna nie jest „dniem niepelnym” (dane sztuczne)."""
import datetime as dt

import pandas as pd

import swiezosc


def _plik(katalog, wiersze):
    pd.DataFrame(wiersze, columns=['data', 'kraj', 'turniej']).to_csv(katalog / 'wyniki_365_pilka_2026-09.csv.gz', index=False)


def test_przerwa_liczy_tylko_seniorskie_reprezentacje(tmp_path):
    w = ([('2026-09-26', 'Europe', 'UEFA Nations League')] * 20
         + [('2026-09-27', 'Africa', 'Africa Cup of Nations Qualification')] * 15
         + [('2026-09-27', 'International', 'U19 Friendly International')] * 50       # mlodziez — nie liczy sie
         + [('2026-09-27', 'Europe', 'UEFA Champions League Qualification')] * 50     # kluby — nie licza sie
         + [('2026-09-27', 'Poland', 'Ekstraklasa')] * 50)
    _plik(tmp_path, w)
    r = swiezosc.mecze_reprezentacji(str(tmp_path))
    assert len(r) == 35
    assert swiezosc.przerwa_reprezentacyjna(dt.date(2026, 9, 28), r) == 35 >= swiezosc.PROG_PRZERWY
    assert swiezosc.przerwa_reprezentacyjna(dt.date(2026, 9, 14), r) == 0


def test_brak_plikow_to_zwykly_tydzien(tmp_path):
    r = swiezosc.mecze_reprezentacji(str(tmp_path / 'nie_ma'))
    assert swiezosc.przerwa_reprezentacyjna(dt.date(2026, 9, 28), r) == 0
