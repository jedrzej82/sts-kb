#!/usr/bin/env python3
"""CLV (closing line value) — czy model bije rynek. Poprawka 56.3.
  python3 clv.py typy_log.csv            — podsumowanie: wszystkie nogi, za pieniadze, papierowe
  python3 clv.py typy_log.csv --od 2026-09-29

Wymagane kolumny: kurs_typu, kurs_zamkniecia. Opcjonalne: data, pieniadze (1/0 albo tak/nie), sport, rynek.
CLV nogi = kurs_typu / kurs_zamkniecia − 1. Dodatnie = wzielismy kurs wyzszy niz rynek na zamknieciu.

Kryterium z CZESCI A pkt 4 (Faza 2 wymaga srednie CLV >= 0 przy >= 100 nogach, Faza 3 — istotnie dodatniego):
srednie CLV > 0 i jednostronny test t: p < 0,05. Ponizej 30 nog wynik jest tylko informacyjny.
Wiersze bez kursu zamkniecia sa pomijane (puste pole to brak pomiaru, nie zero)."""
import math
import sys

import pandas as pd

MIN_N_INFO = 30
MIN_N_FAZA2 = 100


def _tak(x):
    return str(x).strip().lower() in ('1', 'tak', 'true', 'yes', 't', 'p', 'pieniadze')


def przygotuj(df):
    d = df.copy()
    for k in ('kurs_typu', 'kurs_zamkniecia'):
        d[k] = pd.to_numeric(d[k].astype(str).str.replace(',', '.'), errors='coerce')
    d = d[(d.kurs_typu > 1) & (d.kurs_zamkniecia > 1)].copy()
    d['clv'] = d.kurs_typu / d.kurs_zamkniecia - 1
    return d


def _p_jednostronne(t, df):
    """P(T > t) dla rozkladu t-Studenta; scipy jesli jest, inaczej przyblizenie normalne."""
    try:
        from scipy.stats import t as st
        return float(st.sf(t, df))
    except Exception:
        return 0.5 * math.erfc(t / math.sqrt(2))


def podsumuj(clv):
    """Zwraca dict: n, srednia, sd, t, p (jednostronne, H1: srednia > 0), werdykt."""
    x = pd.Series(clv).dropna().astype(float)
    n = len(x)
    if n == 0:
        return dict(n=0, srednia=None, sd=None, t=None, p=None, werdykt='brak pomiaru')
    sr = float(x.mean())
    sd = float(x.std(ddof=1)) if n > 1 else 0.0
    if n > 1 and sd > 0:
        t = sr / (sd / math.sqrt(n)); p = _p_jednostronne(t, n - 1)
    else:
        t = p = None
    if n < MIN_N_INFO:
        w = f'za malo nog (< {MIN_N_INFO}) — tylko informacyjnie'
    elif p is not None and sr > 0 and p < 0.05:
        w = 'CLV istotnie dodatnie (p < 0,05)' + ('' if n >= MIN_N_FAZA2 else f' — ale < {MIN_N_FAZA2} nog')
    elif sr >= 0:
        w = 'CLV >= 0, nieistotne'
    else:
        w = 'CLV ujemne — brak przewagi nad rynkiem'
    return dict(n=n, srednia=sr, sd=sd, t=t, p=p, werdykt=w)


def _linia(nazwa, s):
    if not s['n']:
        return f'  {nazwa:<12} n=0    brak pomiaru'
    p = '—' if s['p'] is None else f'{s["p"]:.3f}'
    return f'  {nazwa:<12} n={s["n"]:<4} srednie CLV {s["srednia"]:+.2%}  p={p}  → {s["werdykt"]}'


def main(a):
    if not a:
        sys.exit(__doc__)
    df = pd.read_csv(a[0])
    brak = {'kurs_typu', 'kurs_zamkniecia'} - set(df.columns)
    if brak:
        sys.exit(f'BRAK KOLUMN: {", ".join(sorted(brak))} — zapisuj je wg Poprawki 56.3')
    if '--od' in a and 'data' in df.columns:
        df = df[df.data.astype(str).str[:10] >= a[a.index('--od') + 1]]
    d = przygotuj(df)
    print(f'CLV — {len(d)} nog z kursem zamkniecia (z {len(df)} wierszy)')
    print(_linia('wszystkie', podsumuj(d.clv)))
    if 'pieniadze' in d.columns:
        m = d.pieniadze.map(_tak)
        print(_linia('za pieniadze', podsumuj(d.clv[m])))
        print(_linia('papierowe', podsumuj(d.clv[~m])))
    for k in ('sport', 'rynek'):
        if k in d.columns and d[k].nunique() > 1:
            print(f'\n  wg {k}:')
            for v, g in d.groupby(k):
                print('  ' + _linia(str(v)[:12], podsumuj(g.clv)))


if __name__ == '__main__':
    main(sys.argv[1:])
