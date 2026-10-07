"""Tryb wsadowy `sporty.py typuj` (07.10.2026): wiele meczow innych sportow w JEDNYM procesie.

Raporty 02.10 12:00 (usterka 2) i 02.10 18:00 (usterka 4): kazde `python3 sporty.py typuj SPORT "A" "B"` trwa ok. 5 s
(wczytanie i sklejanie bazy ok. 3,5 s, Elo sportu ok. 1-2 s, marza punktowa ok. 1 s) — cala oferta innych sportow nie
miesci sie w oknie przebiegu. Tu baza jest wczytana RAZ, Elo i marza policzone raz na sport, a kazdy mecz liczy ten
sam kod (sporty.main(['typuj', ...])) — wynik identyczny jak osobne wywolanie:
  - load()/elo()/marza() zapamietane na czas wsadu; to, co wypisaly przy pierwszym liczeniu (np. „scalono warianty
    pisowni”), wypisywane jest ponownie przy kazdym meczu, jak w osobnym procesie; slowniki Elo oddawane jako kopie;
  - stan globalny modulu zmieniany przez typowanie (_KANDYDAT) czyszczony przed kazdym meczem.

Uzycie:  python3 sporty_wsad.py LISTA.tsv [--wyjscie KATALOG]
LISTA.tsv — jeden mecz w wierszu: SPORT<TAB>Gospodarz<TAB>Gosc[<TAB>opcje], opcje jak dla sporty.py typuj
(np. --neutral --kurs Z1=1.80); nazwy moga byc w cudzyslowach; puste wiersze i wiersze od # pomijane.
Wyjscie (stdout): dla kazdego meczu naglowek „##### N/M SPORT | A | B”, potem DOKLADNIE to, co wypisaloby
`sporty.py typuj SPORT A B` (stdout i stderr), i linia „KOD: 0” albo „KOD: <kod wyjscia>”. Z --wyjscie KATALOG
dodatkowo KATALOG/NNNN.txt na mecz (jak typuj_wsad.py). Postep na stderr. Blad jednego meczu nie przerywa reszty."""
import contextlib
import io
import os
import shlex
import sys
import time
import traceback


def wczytaj_liste(sciezka, min_pol):
    """Wiersze TSV -> lista (linia, pola, opcje). Pola bez cudzyslowow i spacji na brzegach; ostatnie pole po min_pol
    to opcje (shlex). Wiersz z za mala liczba pol -> pola=None (mecz zakonczony bledem, reszta liczona dalej)."""
    out = []
    for x in open(sciezka, encoding='utf-8'):
        linia = x.rstrip('\r\n')
        if not linia.strip() or linia.lstrip().startswith('#'): continue
        p = [c.strip() for c in linia.split('\t')]
        p = [c[1:-1] if len(c) >= 2 and c[0] == c[-1] and c[0] in '"\'' else c for c in p]
        if len(p) < min_pol or not all(p[:min_pol]):
            out.append((linia, None, []))
            continue
        opcje = [o for c in p[min_pol:] for o in shlex.split(c)]
        out.append((linia, p[:min_pol], opcje))
    return out


def uruchom(fn, argv, args=None):
    """Jedno wywolanie main jak osobny proces -> (tekst stdout+stderr, kod wyjscia). sys.argv ustawiany jak w procesie."""
    buf = io.StringIO()
    kod = 0
    stary_argv = sys.argv
    sys.argv = list(argv)
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            fn() if args is None else fn(args)
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


def _z_wypisem(fn):
    """Wywolanie z przechwyceniem tego, co funkcja wypisala -> (wynik, tekst)."""
    def f(*a, **k):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            w = fn(*a, **k)
        return w, buf.getvalue()
    return f


class Pamiec:
    """Zapamietane load()/elo()/marza() modulu sporty na czas wsadu (zakladane przez zaloz(), zdejmowane przez zdejmij())."""

    def __init__(self, sporty):
        self.s = sporty
        self.orig = dict(load=sporty.load, elo=sporty.elo, marza=sporty.marza)
        self.d = None; self.d_tekst = ''
        self.elo_ = {}; self.marza_ = {}

    def load(self):
        if self.d is None:
            self.d, self.d_tekst = _z_wypisem(self.orig['load'])()
        sys.stdout.write(self.d_tekst)
        return self.d

    def elo(self, d, sport, pre=None, info=None):
        if pre is not None or d is not self.d:   # backtest (pre) i inne ramki — bez pamieci
            return self.orig['elo'](d, sport, pre, info)
        if sport not in self.elo_:
            inf = {}
            self.elo_[sport] = _z_wypisem(self.orig['elo'])(d, sport, None, inf) + (inf,)
        (R, N, hfa, draws, pdraw), tekst, inf = self.elo_[sport]
        sys.stdout.write(tekst)
        if info is not None: info.update({k: (dict(v) if isinstance(v, dict) else v) for k, v in inf.items()})
        return dict(R), dict(N), hfa, draws, pdraw

    def marza(self, d, sport, k):
        if d is not self.d: return self.orig['marza'](d, sport, k)
        klucz = (sport, repr(sorted(k.items())))
        if klucz not in self.marza_:
            self.marza_[klucz] = _z_wypisem(self.orig['marza'])(d, sport, k)
        M, tekst = self.marza_[klucz]
        sys.stdout.write(tekst)
        return dict(M)

    def zaloz(self):
        self.s.load, self.s.elo, self.s.marza = self.load, self.elo, self.marza

    def zdejmij(self):
        self.s.load, self.s.elo, self.s.marza = self.orig['load'], self.orig['elo'], self.orig['marza']


def resetuj(sporty):
    """Stan globalny, ktory typowanie zmienia, a osobny proces zaczyna pusty."""
    sporty._KANDYDAT.clear()


def licz(sporty, pola, opcje):
    sport, a, b = pola
    resetuj(sporty)
    args = ['typuj', sport, a, b] + list(opcje)
    return uruchom(sporty.main, ['sporty.py'] + args, args)


def main(a):
    if not a or a[0].startswith('--'): print(__doc__); return 2
    wyj = a[a.index('--wyjscie') + 1] if '--wyjscie' in a else None
    if wyj: os.makedirs(wyj, exist_ok=True)
    lista = wczytaj_liste(a[0], 3)
    t0 = time.time()
    with contextlib.redirect_stdout(io.StringIO()):
        import sporty
    pam = Pamiec(sporty); pam.zaloz()
    bledy = 0
    try:
        for i, (linia, pola, opcje) in enumerate(lista, 1):
            t = time.time()
            if pola is None:
                tekst, kod = f'ZLY WIERSZ LISTY (oczekiwane: SPORT<TAB>Gosp<TAB>Gosc[<TAB>opcje]): {linia!r}\n', 2
            else:
                tekst, kod = licz(sporty, pola, opcje)
            naglowek = f'##### {i}/{len(lista)} ' + (' | '.join(pola) if pola else linia)
            blok = f'{naglowek}\n{tekst}KOD: {kod}\n'
            sys.stdout.write(blok); sys.stdout.flush()
            if wyj:
                with open(os.path.join(wyj, f'{i:04d}.txt'), 'w', encoding='utf-8') as f: f.write(blok)
            bledy += kod != 0
            print(f'{i}/{len(lista)} {" - ".join(pola[1:]) if pola else linia}: kod {kod}, {time.time() - t:.1f} s',
                  file=sys.stderr, flush=True)
    finally:
        pam.zdejmij()
    print(f'SPORTY WSAD: {len(lista)} meczow, {bledy} zakonczonych bledem/odmowa, {time.time() - t0:.0f} s',
          file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
