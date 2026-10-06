"""06.10.2026 — Raport 21:00 usterka 1: „python3 linie.py” bez argumentow uruchamial pelny backtest (timeout, nadpisanie
kalibracji linii). Teraz pomoc i wyjscie, bez dotykania plikow kalibracji."""
import os
import subprocess
import sys

TU = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _stan(p):
    return os.path.getmtime(p) if os.path.exists(p) else None


def test_bez_argumentow_pomoc_bez_backtestu():
    cal, sig = os.path.join(TU, 'linie_kalibracja.csv'), os.path.join(TU, 'linie_sigma.csv')
    przed = (_stan(cal), _stan(sig))
    for argv in ([], ['--help']):
        r = subprocess.run([sys.executable, os.path.join(TU, 'linie.py')] + argv, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and 'python3 linie.py typuj' in r.stdout and 'backtest' in r.stdout
    assert (_stan(cal), _stan(sig)) == przed
