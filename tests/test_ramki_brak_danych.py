"""ramki.py typuj (sporty osobowe: dart, snooker, tenis stolowy ...) — 07.10.2026.
1. Raport 21.09 20:27 nr 3 / Raport 22.09 13:20 U4 (POPRAWKA 11): zawodnik z 0 meczami w bazie -> przerwanie,
   kod != 0, zadnych tabel P; N < 5 -> „BRAK DANYCH RYWALA (N=..)” i „WERDYKT: NIE NA KUPON”.
2. Raport 22.09 13:00 nr 2: po kalibracji pary wzajemnie wykluczajacych sie rynkow sumuja sie do 100%.
Dane syntetyczne (monkeypatch), bez plikow z Dysku."""
import re

import pandas as pd
import pytest

import ramki
import sporty


def _baza(n_slaby):
    """Snooker: 'Mocny' i 'Sredni' po 20 meczow, 'Slaby' n_slaby meczow (rywale spoza pary)."""
    w = []
    for t, k, wyg in (('Mocny', 20, 0.7), ('Sredni', 20, 0.5), ('Slaby', n_slaby, 0.5)):
        for i in range(k):
            win = i < k * wyg
            w.append(dict(data=pd.Timestamp('2026-01-01') + pd.Timedelta(days=i), sport='snooker', gosp=t,
                          gosc=f'R{i}', pg=6 if win else 3, pa=3 if win else 6))
    return pd.DataFrame(w)


@pytest.fixture
def srodowisko(monkeypatch, tmp_path):
    def ustaw(n_slaby, krzywa=None):
        monkeypatch.setattr(ramki, 'data', lambda sport: _baza(n_slaby))
        monkeypatch.setattr(sporty, 'resolve', lambda nazwa, pula, *a, **k: nazwa if nazwa in pula else None)
        cal = tmp_path / 'kal.csv'
        if krzywa is not None:
            pd.DataFrame([('snooker', f, pm, pk, 100) for f in ('zwycięzca', 'handicap', 'suma') for pm, pk in krzywa],
                         columns=['sport', 'rodzina', 'p_model', 'p_kalibr', 'n']).to_csv(cal, index=False)
        monkeypatch.setattr(ramki, 'CAL', str(cal))
    return ustaw


def _procenty(out):
    return [ln for ln in out.splitlines() if re.search(r'\d+\.\d%$', ln.strip())]


def test_zero_meczow_przerywa_bez_tabeli(srodowisko, capsys):
    srodowisko(5)
    with pytest.raises(SystemExit) as e:
        ramki.main(['typuj', 'snooker', 'Mocny', 'Nieznany Zawodnik'])
    assert e.value.code not in (None, 0)
    assert 'BRAK W BAZIE: Nieznany Zawodnik' in str(e.value.code)
    assert 'noga MNIEJ / NIE NA KUPON' in str(e.value.code)
    assert _procenty(capsys.readouterr().out) == []


def test_malo_meczow_werdykt_nie_na_kupon(srodowisko, capsys):
    srodowisko(3)
    ramki.main(['typuj', 'snooker', 'Mocny', 'Slaby'])
    out = capsys.readouterr().out
    assert 'BRAK DANYCH RYWALA (N=3)' in out
    assert re.search(r'^WERDYKT: NIE NA KUPON — za malo meczow', out, re.M)


def test_dosc_meczow_bez_werdyktu_i_bez_ostrzezenia(srodowisko, capsys):
    srodowisko(10)
    ramki.main(['typuj', 'snooker', 'Mocny', 'Slaby'])
    out = capsys.readouterr().out
    assert 'BRAK DANYCH RYWALA' not in out and 'WERDYKT' not in out
    assert len(_procenty(out)) > 4


def test_pary_po_kalibracji_sumuja_sie_do_100(srodowisko, capsys):
    # krzywa sciagajaca do srodka (jak w ramki_kalibracja.csv): 0,5 -> 0,498 — przed poprawka 49,8% + 49,8%
    srodowisko(10, krzywa=[(0.0, 0.05), (0.5, 0.498), (1.0, 0.9)])
    ramki.main(['typuj', 'snooker', 'Sredni', 'Slaby'])
    out = capsys.readouterr().out
    p = {ln.strip().rsplit(None, 1)[0].strip(): float(ln.strip().rsplit(None, 1)[1][:-1]) for ln in _procenty(out)}
    assert p['Sredni wygra'] + p['Slaby wygra'] == pytest.approx(100.0, abs=0.11)
    assert p['Sredni -1.5'] + p['Slaby +1.5'] == pytest.approx(100.0, abs=0.11)
    assert p['suma > 6.5'] + p['suma < 6.5'] == pytest.approx(100.0, abs=0.11)


def test_kazdy_rynek_ma_pare_i_skalibruj_normalizuje(monkeypatch):
    mk, _ = ramki.markets(0.55, 6)
    for k in mk:
        assert ramki.para(k) in mk and ramki.para(ramki.para(k)) == k
        assert mk[k] + mk[ramki.para(k)] == pytest.approx(1.0)
    monkeypatch.setattr(ramki, 'cal_apply', lambda sport, f, p: 0.9 * p + 0.02)
    c = ramki.skalibruj('dart', mk)
    for k in mk:
        assert c[k] + c[ramki.para(k)] == pytest.approx(1.0)
