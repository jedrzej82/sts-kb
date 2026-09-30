"""30.09.2026 (przeglad sporty.py): rozliczenie przy nieznanej dogrywce i dacie ±1, nazwy, remisy, 60 min."""
import pandas as pd

import nazwy
import sporty


def _baza(w):
    return pd.DataFrame(w, columns=['data', 'sport', 'liga', 'gosp', 'gosc', 'pg', 'pa', 'dogrywka']).assign(
        data=lambda x: pd.to_datetime(x.data))


def test_rozlicz_nieznana_dogrywka_i_data_plus_minus_dzien(tmp_path, monkeypatch):
    d = _baza([('2026-06-15', 'hokej', 'NHL', 'Vegas Golden Knights', 'Carolina Hurricanes', 0, 3, -1),
               ('2025-10-07', 'hokej', 'NHL', 'Los Angeles Kings', 'Colorado Avalanche', 1, 4, -1)])
    log = tmp_path / 'log.csv'
    pd.DataFrame([('2026-06-15', 'hokej', 'Vegas Golden Knights', 'Carolina Hurricanes', 'X', 0.2, None),
                  ('2026-06-15', 'hokej', 'Vegas Golden Knights', 'Carolina Hurricanes', '2_60min', 0.3, None),
                  ('2026-06-15', 'hokej', 'Vegas Golden Knights', 'Carolina Hurricanes', '2', 0.4, None),
                  ('2025-10-08', 'hokej', 'Los Angeles Kings', 'Colorado Avalanche', '2', 0.5, None)],   # data polska
                 columns=['data', 'sport', 'gosp', 'gosc', 'rynek', 'p', 'trafiony']).to_csv(log, index=False)
    monkeypatch.setattr(sporty, 'LOG', str(log)); monkeypatch.setattr(sporty, 'CAL', str(tmp_path / 'cal.csv'))
    monkeypatch.setattr(sporty, 'load', lambda: d)
    sporty.main(['rozlicz'])
    t = pd.read_csv(log).trafiony.tolist()
    assert pd.isna(t[0]) and pd.isna(t[1])          # dotad X = 1, 2_60min = 0 (nieznane liczone jak dogrywka)
    assert t[2] == 1 and t[3] == 1                  # LA Kings–Colorado: w bazie dzien wczesniej (czas USA)


def test_nazwy_bez_zgadywania():
    assert sporty.resolve('Zenit', {'Zenit-2', 'Spartak'}) is None
    assert nazwy.znaczniki('Zenit-2') == ('rezerwy',) and nazwy.znaczniki('U-19') == nazwy.znaczniki('U19')
    assert sporty.resolve('CSKA Moscow', {'CSKA-2 Moscow'}) is None
    assert sporty.resolve('Qatar', {'Qatar SC'}) is None and sporty.resolve('Cameroon', {'Cameron'}) is None
    assert sporty.resolve('Jaen', {'Avanza Jaen'}, 'futsal') is None
    assert sporty.resolve('Littler', {'Luke Littler'}, 'dart') == 'Luke Littler'
    assert sporty.resolve('Nitra', {'MHK Nitra'}) == 'MHK Nitra'
    assert sporty.resolve('Club Italiano (W)', {'Club Italia (W)'}) is None


def test_remis_w_sporcie_bez_remisow_nie_zmienia_elo():
    w = [('2026-01-0%d' % i, 'koszykówka', 'L', 'A', 'B', 80 + i, 70, 0) for i in range(1, 6)]
    R1 = sporty.elo(_baza(w), 'koszykówka')[0]
    R2 = sporty.elo(_baza(w + [('2026-01-09', 'koszykówka', 'L', 'A', 'B', 82, 82, 0)]), 'koszykówka')[0]
    assert R1 == R2                                  # dotad 82:82 = wygrana goscia z pelnym K


def test_rynki_60min_nie_zawyzaja():
    p1, p2 = sporty.rynki_60min(0.80, 0.22)
    assert p1 <= 0.80 * 0.78 + 1e-12 and p2 <= 0.20 - 0.11 + 1e-12   # slabszy ok. 9%, nie 15,6%
    assert p1 + p2 + 0.22 <= 1 + 1e-12
