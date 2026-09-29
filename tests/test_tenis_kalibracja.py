"""29.09.2026: tenis_kalibracja.csv w repo — dawniej powstawal tylko w bloku poniedzialkowym w kontenerze przebiegu,
wiec prawie kazdy przebieg liczyl tenis na surowym P (zawyzonym o ok. 6 pp przy P >= 70%) podpisanym jako „P_skalibr”."""
import os

import numpy as np
import pandas as pd

import tenis


def test_plik_kalibracji_jest_i_jest_monotoniczny():
    assert os.path.exists(tenis.CAL)
    c = pd.read_csv(tenis.CAL)
    assert list(c.columns) == ['p_model', 'p_kalibr', 'n'] and len(c) >= 10 and c.n.sum() > 10000
    assert (np.diff(c.p_kalibr) >= 0).all()


def test_kalibracja_obniza_wysokie_p():
    # backtest poza proba (od 07.2025): surowe P 78,7% -> trafnosc 72,9%; po kalibracji 76,5% -> 76,0%
    assert tenis.calibrate(0.79) < 0.75 and tenis.calibrate(0.51) < 0.53
