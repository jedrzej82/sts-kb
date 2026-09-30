"""Wspolne narzedzia kalibracji.
30.09.2026 (przeglad skryptow kalibracji): tabele P_model -> trafnosc byly „monotonizowane” biezacym maksimum
(np.maximum.accumulate), ktore tylko PODNOSI kosze — kazda tabela byla zawyzona (rugby do +3,3 pp, CS2 +3,4 pp,
NFL +2,3 pp, dart +2,3 pp w pojedynczych koszach). Wlasciwa regresja izotoniczna usrednia sasiednie kosze
lamiace monotonicznosc, wazac liczba meczow (PAV)."""
import numpy as np


def pav(y, n):
    """Niemalejaca wersja trafnosci koszy `y` (wagi `n` = liczba meczow w koszu). Dlugosc jak wejscie."""
    y = np.asarray(y, float); n = np.asarray(n, float)
    bloki = [[y[i], n[i], [i]] for i in range(len(y))]
    j = 0
    while j < len(bloki) - 1:
        if bloki[j][0] > bloki[j + 1][0]:
            a, b = bloki[j], bloki[j + 1]; w = a[1] + b[1]
            bloki[j] = [(a[0] * a[1] + b[0] * b[1]) / w, w, a[2] + b[2]]; del bloki[j + 1]; j = max(j - 1, 0)
        else:
            j += 1
    out = np.empty(len(y))
    for v, _, idx in bloki: out[idx] = v
    return out
