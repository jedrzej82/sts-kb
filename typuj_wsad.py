"""Tryb wsadowy typuj.py (03.10.2026): wiele meczow w JEDNYM procesie, baza wczytana raz.

Przebieg 03.10 12:00: kazde wywolanie typuj.py wczytuje baze (414 tys. meczow, ok. 5 s z 7 s, ok. 750 MB);
12 rownoleglych procesow przekroczylo 8 GB pamieci ("Killed") i KROK 4 policzyl 80 z 448 meczow pilki.
Tu baza jest czytana raz na proces, a kazdy mecz liczony tym samym kodem (typuj.main) — wynik identyczny
jak osobne wywolanie. Kilka procesow wsadowych naraz = kilka list (np. 4 po 1/4 meczow).

Uzycie:  python3 typuj_wsad.py LISTA.txt [--wyjscie KATALOG]
LISTA.txt — jeden mecz w wierszu, argumenty DOKLADNIE jak dla typuj.py (nazwy w cudzyslowach), np.:
    "Estonia" "Luksemburg" --kurs 1X=1.52 --kurs O1.5=1.60 --nogi nogi_1.csv
Wyjscie: KATALOG/NNNN.txt (domyslnie typuj_wsad/) = to, co typuj.py wypisalby dla tego meczu (stdout i stderr),
z ostatnia linia "KOD: 0" albo "KOD: <powod zakonczenia>". Blad jednego meczu (np. ROZNE KRAJE, brak druzyny)
nie przerywa pozostalych. Na ekranie: jedna linia postepu na mecz."""
import contextlib
import io
import os
import shlex
import sys
import time
import traceback


def licz(typuj, args):
    """Jeden mecz -> (tekst wyjscia, kod). sys.argv ustawiany jak przy osobnym wywolaniu (typuj czyta z niego flagi)."""
    buf = io.StringIO()
    kod = 0
    stary_argv = sys.argv
    sys.argv = ['typuj.py'] + list(args)
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            typuj.main(args)
    except SystemExit as e:
        if e.code not in (None, 0):
            kod = e.code if isinstance(e.code, int) else 1
            if not isinstance(e.code, int): buf.write(f'{e.code}\n')
    except Exception:
        kod = 1
        buf.write(traceback.format_exc())
    finally:
        sys.argv = stary_argv
    return buf.getvalue(), kod


def main(a):
    if not a or a[0].startswith('--'): print(__doc__); return 2
    wyj = a[a.index('--wyjscie') + 1] if '--wyjscie' in a else 'typuj_wsad'
    os.makedirs(wyj, exist_ok=True)
    linie = [x.strip() for x in open(a[0], encoding='utf-8') if x.strip() and not x.lstrip().startswith('#')]
    t0 = time.time()
    with contextlib.redirect_stdout(io.StringIO()):
        import typuj
    bledy = 0
    for i, linia in enumerate(linie, 1):
        args = shlex.split(linia)
        t = time.time()
        tekst, kod = licz(typuj, args)
        with open(os.path.join(wyj, f'{i:04d}.txt'), 'w', encoding='utf-8') as f:
            f.write(f'# {linia}\n{tekst}KOD: {kod}\n')
        bledy += kod != 0
        nazwy = [x for x in args if not x.startswith('--')][:2]
        print(f'{i}/{len(linie)} {" - ".join(nazwy)}: kod {kod}, {time.time() - t:.1f} s', flush=True)
    print(f'TYPUJ WSAD: {len(linie)} meczow, {bledy} zakonczonych bledem/odmowa, {time.time() - t0:.0f} s -> {wyj}/')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
