"""02.10.2026 (Raport 15:00, usterka 11): historia zakladow i pliki tworzone przez przebieg nie moga trafic do repo
(CLAUDE.md „Czego nie wolno”). Sprawdzenie przez `git check-ignore` — tak samo, jak zadziala `git add -A`."""
import os
import subprocess

import pytest

KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRYWATNE = ['zaklady_faktyczne.csv', 'zaklady_faktyczne_2026-10.csv', 'ako_log.csv', 'ako_log DELTA 2026-10-02 12-00.csv',
            'typy_log.csv', 'Bilans 2026-10-01.csv', 'kursy_bukmacherow_2026-10-02_11-38.csv.gz', 'kursy_2026-10-02_15-30.csv.gz',
            'oferta-dzisiaj-auto 2026-10-02 11-30.pdf', 'paczka.zip', 'dzienniki.zip', 'Rozliczenie_2026-10-01.csv',
            'ligi_extra.csv', 'ligi_extra_nazwy.json', 'mma_metody.csv']


@pytest.mark.parametrize('plik', PRYWATNE)
def test_prywatne_pliki_ignorowane(plik):
    r = subprocess.run(['git', 'check-ignore', '-q', '--no-index', plik], cwd=KORZEN)
    assert r.returncode == 0, f'{plik} NIE jest w .gitignore'
