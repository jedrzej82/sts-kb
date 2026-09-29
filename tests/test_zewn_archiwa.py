"""29.09.2026 (Raport 21:00): przebieg nie zdolal pobrac z Dysku kompletu danych (ok. 5,5 MB przez konektor base64,
z czego 4,4 MB to dwa NIEZMIENNE archiwa sezonu 2025/26) i skonczyl sie PRZEBIEG BLAD. Archiwa leza w repo (zewn/),
jak pliki miesieczne 365scores od 21.09 — przebieg pobiera z Dysku juz tylko biezace pliki miesieczne."""
import glob
import os

import pandas as pd

ZD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'zewn')


def test_archiwa_sezonu_w_repo():
    for rodzaj in ('pilka', 'inne'):
        f = glob.glob(os.path.join(ZD, f'wyniki_365_{rodzaj}_archiwum_2025-07_2026-06.csv.gz'))
        assert f, rodzaj
        d = pd.read_csv(f[0], usecols=['data'], dtype=str)
        assert len(d) > 90000 and d.data.min() <= '2025-07-02' and d.data.max() >= '2026-06-29'
