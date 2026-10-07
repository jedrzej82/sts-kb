"""Tryb wsadowy tenis.py (07.10.2026): wiele meczow tenisa w JEDNYM procesie, stan Elo wczytany raz.

Raporty 02.10 12:00 (usterka 2) i 02.10 18:00 (usterka 4): kazde `python3 tenis.py "A" "B"` wczytuje stan Elo
(cache/tenis_state.pkl, a przy nieaktualnym cache cala baze ATP+WTA) — cala oferta tenisa nie miesci sie w oknie
przebiegu. Tu state() liczony jest RAZ (przed pierwszym meczem), a kazdy mecz liczy ten sam kod (tenis.main) —
wynik identyczny jak osobne wywolanie przy aktualnym cache. Przed kazdym meczem czyszczone sa slowniki modulu,
ktore main() wypelnia (NCOUNT, ALIASY, OSTATNI), a main dostaje kopie slownikow stanu.
Gdy cache byl nieaktualny, komunikaty przebudowy (np. „sklejono N wariantow nazwisk”) ida raz na stderr, nie do
bloku meczu — tak jak przy drugim i kolejnych osobnych wywolaniach.

Uzycie:  python3 tenis_wsad.py LISTA.tsv [--wyjscie KATALOG]
LISTA.tsv — jeden mecz w wierszu: "A"<TAB>"B"[<TAB>--hard|--clay|--grass|--bo5] (opcje jak dla tenis.py);
puste wiersze i wiersze od # pomijane.
Wyjscie (stdout): dla kazdego meczu naglowek „##### N/M A | B”, potem DOKLADNIE to, co wypisaloby `tenis.py A B`
(stdout i stderr), i linia „KOD: 0” albo „KOD: <kod wyjscia>”. Z --wyjscie KATALOG dodatkowo KATALOG/NNNN.txt na mecz.
Postep na stderr. Blad jednego meczu nie przerywa reszty."""
import contextlib
import os
import sys
import time

from sporty_wsad import uruchom, wczytaj_liste


def resetuj(tenis):
    """Slowniki modulu, ktore osobny proces zaczyna puste, a main() wypelnia ze stanu."""
    tenis.NCOUNT.clear(); tenis.ALIASY.clear(); tenis.OSTATNI.clear()


def kopia_stanu(st):
    return {k: (dict(v) if isinstance(v, dict) else v) for k, v in st.items()}


def licz(tenis, st, pola, opcje):
    resetuj(tenis)
    oryg = tenis.state
    tenis.state = lambda: kopia_stanu(st)
    try:
        return uruchom(tenis.main, ['tenis.py'] + list(pola) + list(opcje))
    finally:
        tenis.state = oryg


def main(a):
    if not a or a[0].startswith('--'): print(__doc__); return 2
    wyj = a[a.index('--wyjscie') + 1] if '--wyjscie' in a else None
    if wyj: os.makedirs(wyj, exist_ok=True)
    lista = wczytaj_liste(a[0], 2)
    t0 = time.time()
    import tenis
    with contextlib.redirect_stdout(sys.stderr):
        tenis.fetch()
        st = tenis.state()
    bledy = 0
    for i, (linia, pola, opcje) in enumerate(lista, 1):
        t = time.time()
        if pola is None:
            tekst, kod = f'ZLY WIERSZ LISTY (oczekiwane: "A"<TAB>"B"[<TAB>opcje]): {linia!r}\n', 2
        else:
            tekst, kod = licz(tenis, st, pola, opcje)
        naglowek = f'##### {i}/{len(lista)} ' + (' | '.join(pola) if pola else linia)
        blok = f'{naglowek}\n{tekst}KOD: {kod}\n'
        sys.stdout.write(blok); sys.stdout.flush()
        if wyj:
            with open(os.path.join(wyj, f'{i:04d}.txt'), 'w', encoding='utf-8') as f: f.write(blok)
        bledy += kod != 0
        print(f'{i}/{len(lista)} {" - ".join(pola) if pola else linia}: kod {kod}, {time.time() - t:.1f} s',
              file=sys.stderr, flush=True)
    resetuj(tenis)
    print(f'TENIS WSAD: {len(lista)} meczow, {bledy} zakonczonych bledem/odmowa, {time.time() - t0:.0f} s',
          file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
