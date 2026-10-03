"""03.10.2026 — linie.py: normalizacja nazwy sportu i brak zgadywania nazw druzyn.

Dotad `linie.py typuj` robilo `sport = a[1].lower()`, wiec "reczna" nie trafialo w "piłka ręczna"
w bazie. rate_pass zwracal PUSTY stan, sp.resolve dostawal pusta pule i spadal na `or a[2]`,
a skrypt konczyl sie mylacym "Brak druzyny w bazie wynikow".

Skutek byl powazniejszy niz komunikat: linie (handicapy, sumy punktow/goli) byly w przebiegu
NIEOSIAGALNE dla kazdego sportu, ktorego nazwa w ofercie rozni sie od nazwy w bazie — czyli dla
wszystkich poza hokejem i baseballem. Przebiegi ocenialy wylacznie rynek zwyciezcy, gdzie faworyci
chodza po 1,02-1,18, czyli ponizej progu 1,137, przy ktorym podatek 12% w ogole pozwala wyjsc na zero.

Pomiar 2026-10-03 (okno 19:00-22:00): 23 z 70 zdarzen mialo i dane, i >= 2 typy rynkow,
ale drugi typ rynku byl nieosiagalny przez te jedna linie kodu.
"""
import subprocess
import sys
import os

import pytest

KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _linie(*args, timeout=300):
    return subprocess.run([sys.executable, os.path.join(KORZEN, 'linie.py'), *args],
                          capture_output=True, text=True, timeout=timeout, cwd=KORZEN)


def test_nazwa_sportu_jest_normalizowana():
    """Zrodlo bledu: 'reczna' musi trafic w 'piłka ręczna' tak samo jak w sporty.py typuj."""
    src = open(os.path.join(KORZEN, 'linie.py'), encoding='utf-8').read()
    assert "sp.nazwa_sportu(a[1])" in src, 'linie.py typuj znowu uzywa a[1].lower()'
    assert "sport = a[1].lower()" not in src


def test_nie_podstawia_surowej_nazwy_z_oferty():
    """`or a[2]` podstawialo nazwe z oferty, gdy resolve zawiodl — to jest zgadywanie nazwy."""
    src = open(os.path.join(KORZEN, 'linie.py'), encoding='utf-8').read()
    assert "sp.resolve(a[2], set(T), sport) or a[2]" not in src
    assert 'NIE DOPASOWANO NAZWY' in src


@pytest.mark.skipif(not os.path.exists(os.path.join(KORZEN, 'sporty_hist.csv')),
                    reason='wymaga zbudowanej bazy (sporty_hist.csv)')
@pytest.mark.parametrize('sport', ['reczna', 'piłka ręczna', 'pilka_reczna'])
def test_skrot_sportu_dziala_tak_samo(sport):
    """Wszystkie formy nazwy sportu, ktore przyjmuje sporty.py, musi przyjac tez linie.py."""
    r = _linie('typuj', sport, 'Bidasoa Irun', 'BM Puente Genil')
    assert r.returncode == 0, r.stdout + r.stderr
    assert 'HANDICAP' in r.stdout and 'SUMA (O/U)' in r.stdout


@pytest.mark.skipif(not os.path.exists(os.path.join(KORZEN, 'sporty_hist.csv')),
                    reason='wymaga zbudowanej bazy (sporty_hist.csv)')
def test_nazwy_z_oferty_sa_rozwiazywane():
    """Nazwy przychodza z PDF STS, nie z bazy — resolver musi je dopasowac."""
    r = _linie('typuj', 'koszykowka', 'SYNTAINICS MBC', 'Ratiopharm Ulm')
    assert r.returncode == 0, r.stdout + r.stderr
    assert 'Ratiopharm Ulm' in r.stdout


@pytest.mark.skipif(not os.path.exists(os.path.join(KORZEN, 'sporty_hist.csv')),
                    reason='wymaga zbudowanej bazy (sporty_hist.csv)')
def test_nieznana_druzyna_konczy_sie_noga_mniej():
    """Brak dopasowania = noga MNIEJ z jawnym powodem, nie ciche podstawienie."""
    r = _linie('typuj', 'koszykowka', 'Zupelnie Nieistniejacy Klub XYZ', 'Ratiopharm Ulm')
    assert r.returncode != 0
    assert 'NIE DOPASOWANO NAZWY' in (r.stdout + r.stderr)


@pytest.mark.skipif(not os.path.exists(os.path.join(KORZEN, 'sporty_hist.csv')),
                    reason='wymaga zbudowanej bazy (sporty_hist.csv)')
def test_nieznany_sport_mowi_wprost():
    r = _linie('typuj', 'quidditch', 'A', 'B')
    assert r.returncode != 0
    assert 'BRAK W BAZIE' in (r.stdout + r.stderr)


# --- 03.10.2026 (przebieg probny 20:00): brak historii to NIE jest usterka nazwy ---

def test_rozroznia_brak_historii_od_bledu_nazwy():
    src = open(os.path.join(KORZEN, 'linie.py'), encoding='utf-8').read()
    assert 'BRAK HISTORII MECZOW' in src, 'linie.py nie rozroznia braku historii od bledu nazwy'
    assert 'To NIE jest usterka nazwy' in src


@pytest.mark.skipif(not os.path.exists(os.path.join(KORZEN, 'sporty_hist.csv')),
                    reason='wymaga zbudowanej bazy (sporty_hist.csv)')
def test_klub_bez_historii_nie_jest_zglaszany_jako_zla_nazwa():
    """„Bàsquet Manresa” jest w tabelach ligi, ale nie ma meczu z wynikiem w bazie.
    Pula rate_pass zawiera tylko druzyny Z HISTORIA, wiec resolve przeciw niej zawodzil
    i komunikat sugerowal blad nazwy — przebieg szukalby aliasu, ktory juz dziala."""
    r = _linie('typuj', 'koszykowka', 'Basquet Manresa', 'CB Breogan')
    out = r.stdout + r.stderr
    assert r.returncode != 0
    assert 'BRAK HISTORII MECZOW' in out
    assert 'NIE DOPASOWANO NAZWY' not in out


@pytest.mark.skipif(not os.path.exists(os.path.join(KORZEN, 'sporty_hist.csv')),
                    reason='wymaga zbudowanej bazy (sporty_hist.csv)')
def test_nieznana_nazwa_dalej_jest_bledem_nazwy():
    """Rozroznienie nie moze przykryc prawdziwego problemu z nazwa."""
    r = _linie('typuj', 'koszykowka', 'Zupelnie Nieistniejacy Klub XYZ', 'CB Breogan')
    out = r.stdout + r.stderr
    assert r.returncode != 0
    assert 'NIE DOPASOWANO NAZWY' in out
    assert 'BRAK HISTORII MECZOW' not in out
