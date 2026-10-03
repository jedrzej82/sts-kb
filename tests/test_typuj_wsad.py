"""03.10.2026: tryb wsadowy typuj.py — przebieg 12:00 policzyl 80 z 448 meczow (kazde wywolanie wczytuje baze,
12 procesow = brak pamieci). Wsad: baza raz na proces, wynik identyczny jak osobne wywolanie."""
import sys
import types

import pandas as pd

import typuj
import typuj_wsad


def test_licz_lapie_exit_i_ustawia_argv():
    widziane = []

    def main(args):
        widziane.append(list(sys.argv))
        print('Dopasowano: A -> X')
        if args[0] == 'zle': sys.exit('ROZNE KRAJE: ...')
    fake = types.SimpleNamespace(main=main)
    tekst, kod = typuj_wsad.licz(fake, ['A', 'B', '--kontynentalny'])
    assert kod == 0 and 'Dopasowano' in tekst and widziane[0] == ['typuj.py', 'A', 'B', '--kontynentalny']
    tekst, kod = typuj_wsad.licz(fake, ['zle', 'B'])
    assert kod == 1 and 'ROZNE KRAJE' in tekst
    assert sys.argv[1:] != ['zle', 'B']                      # argv przywrocone po meczu


def test_main_resetuje_stan_miedzy_meczami(monkeypatch):
    wolane = []
    monkeypatch.setattr(typuj, 'club', lambda h, a, kursy, live=None: wolane.append((h, a, kursy, typuj.NOGI_PLIK, list(typuj.PARY))))
    typuj.main(['A', 'B', '--kurs', '1=2.5', '--nogi', 'n1.csv', '--para', 'X+Y=3'])
    typuj.LIGA_BEZ_TESTU = 'liga z poprzedniego meczu'
    typuj.main(['C', 'D'])
    assert wolane[0] == ('A', 'B', {'1': 2.5}, 'n1.csv', [('X', 'Y', 3.0)])
    assert wolane[1] == ('C', 'D', {}, None, []) and typuj.LIGA_BEZ_TESTU is None


def test_baza_czytana_raz_na_stan(monkeypatch):
    czytane = []
    df = pd.DataFrame({'a': [1]})
    monkeypatch.setattr(typuj.pd, 'read_sql', lambda q, con, **k: czytane.append(q) or df)
    monkeypatch.setattr(typuj, 'stan_bazy', lambda: 's1')
    typuj._BAZA.clear()
    m1, _ = typuj._baza(None); m1['a'] = 99          # zmiana kopii nie psuje bazy dla kolejnego meczu
    m2, _ = typuj._baza(None)
    assert len(czytane) == 2 and int(m2.a.iloc[0]) == 1
    monkeypatch.setattr(typuj, 'stan_bazy', lambda: 's2')   # przebudowa bazy -> czytamy od nowa
    typuj._baza(None)
    assert len(czytane) == 4
    typuj._BAZA.clear()
