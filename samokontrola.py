#!/usr/bin/env python3
"""Samokontrola: gdzie system sie myli (decyzja uzytkownika 06.10.2026).
  python3 samokontrola.py [ako_log.csv] [sporty_typy.csv]     (tez na koncu: python3 dzienniki.py rozlicz DATA)

Po kazdym rozliczeniu liczy na WSZYSTKICH rozliczonych nogach (ako_log — kazda noga raz; sporty_typy — typy
rozliczone przez sporty.py rozlicz) trafnosc osobno wg: sportu, rynku (w sporcie), ligi (pilka) i rynku w lidze.
Gdy grupa ma >= MIN_N nog, a trafnosc jest nizsza od sredniego deklarowanego P o wiecej niz PROG_PP:
  PODEJRZENIE: rynek X w lidze Y zawyzony (P 75%, wchodzi 66%, n=80; 2,1 bledu std.)
To tylko WSKAZANIE miejsca. Blokada dopiero po sprawdzeniu na pelnej historii (backtest) i PR — i tylko zaostrza (A2).
„bledu std.” mowi, na ile roznica moze byc przypadkiem: < 2 — jeszcze mozliwy przypadek, >= 2 — malo prawdopodobny."""
import math
import os
import re
import sys

import pandas as pd

MIN_N, PROG_PP = 50, 0.05
_PILKA = re.compile(r'(?i)^(pilka|piłka|pilka nozna|piłka nożna|football|soccer)?$')


def _p(x):
    try:
        v = float(str(x).replace(',', '.').replace('%', ''))
    except ValueError:
        return None
    if math.isnan(v): return None
    return v / 100 if v > 1 else v


def _sport(s):
    s = str(s).strip()
    if _PILKA.match(s): return 'pilka'
    import sporty
    return sporty.nazwa_sportu(s)


def _rynek(sport, r):
    """Jeden zapis rynku na grupe: pilka — kod dziennikow (O1.5, 1X…); inne sporty — Z1/Z2/1 (60 min)/X…"""
    import dzienniki
    import sporty
    if sport == 'pilka': return str(dzienniki.rynek_pilka(r))
    s = re.sub(r'(?i)\s*\(\s*zwyci[eę]zca[^)]*\)\s*$', '', str(r).strip())   # „Z1 (Zwyciezca meczu)” = „Z1”
    if re.match(r'(?i)^zwyci[eę]zca\b', s) and not re.search(r'(?i)\b(1|2|z1|z2)\b', s):
        return 'zwyciezca (strona w nazwie)'
    return sporty._rynek_typu(re.sub(r'(?i)^zwyci[eę]zca(\s+meczu)?\s*[:\-]?\s*([12])$', r'Z\2', s))


def nogi_ako(ako, W):
    """ako_log -> rozliczone nogi (sport, liga, rynek, p, traf); ta sama noga w kilku kuponach liczona raz."""
    import dzienniki
    n = ako[ako.noga_nr.astype(str).str.upper() != 'RAZEM'].copy()
    n = n.drop_duplicates(['data', 'zdarzenie', 'rynek'])
    out = []
    for _, r in n.iterrows():
        p = _p(r.get('P', ''))
        if p is None or not str(r.get('zdarzenie', '')).strip(): continue
        stan = dzienniki.rozlicz_noge(r, W)[0]
        if stan not in ('TRAFIONY', 'PRZEGRANY'): continue
        sp = _sport(r.get('sport', ''))
        out.append(dict(zrodlo='ako_log', sport=sp, liga=str(r.get('liga', '')).strip(), rynek=_rynek(sp, r.get('rynek', '')),
                        p=p, traf=int(stan == 'TRAFIONY')))
    return pd.DataFrame(out, columns=['zrodlo', 'sport', 'liga', 'rynek', 'p', 'traf'])


def nogi_typy(typy):
    """sporty_typy.csv (rozliczone przez sporty.py rozlicz) -> nogi."""
    if typy is None or not len(typy) or 'trafiony' not in typy: return pd.DataFrame(columns=['zrodlo', 'sport', 'liga', 'rynek', 'p', 'traf'])
    t = typy[pd.to_numeric(typy.trafiony, errors='coerce').notna()].copy()
    out = []
    for _, r in t.iterrows():
        p = _p(r.get('p', ''))
        if p is None: continue
        sp = _sport(r.get('sport', ''))
        out.append(dict(zrodlo='sporty_typy', sport=sp, liga='', rynek=_rynek(sp, r.get('rynek', '')), p=p,
                        traf=int(float(r.trafiony))))
    return pd.DataFrame(out, columns=['zrodlo', 'sport', 'liga', 'rynek', 'p', 'traf'])


def podejrzenia(d, min_n=MIN_N, prog=PROG_PP):
    """Lista (opis, n, P, trafnosc, ile_bledow_std) grup z zawyzonym P; najmocniejsze na poczatku."""
    wyn = []
    grupy = [('sport', lambda g: f'sport {g[0]}', ['sport']),
             ('rynek', lambda g: f'rynek {g[1]} ({g[0]})', ['sport', 'rynek']),
             ('liga', lambda g: f'liga {g[1]} ({g[0]})', ['sport', 'liga']),
             ('rynek w lidze', lambda g: f'rynek {g[2]} w lidze {g[1]} ({g[0]})', ['sport', 'liga', 'rynek'])]
    for _, opis, kol in grupy:
        x = d if 'liga' not in kol else d[d.liga.astype(str).str.strip() != '']
        for g, z in x.groupby(kol):
            g = g if isinstance(g, tuple) else (g,)
            n = len(z)
            if n < min_n: continue
            sp, tr = float(z.p.mean()), float(z.traf.mean())
            if sp - tr <= prog: continue
            se = math.sqrt(max(sp * (1 - sp), 1e-6) / n)
            wyn.append((opis(g), n, sp, tr, (sp - tr) / se))
    return sorted(wyn, key=lambda w: -w[4])


def linie(d, min_n=MIN_N, prog=PROG_PP):
    out = [f'SAMOKONTROLA (rozliczone nogi: {len(d)}; prog: n >= {min_n} i trafnosc nizsza od P o > {prog * 100:.0f} pp)']
    if not len(d):
        return out + ['  brak rozliczonych nog']
    pod = podejrzenia(d, min_n, prog)
    for opis, n, sp, tr, z in pod:
        out.append(f'  PODEJRZENIE: {opis} zawyzony (P {sp:.0%}, wchodzi {tr:.0%}, n={n}; {z:.1f} bledu std.)')
    if not pod:
        ogol = f'  brak podejrzen — wszystkie grupy z n >= {min_n} trafiaja co najmniej P − {prog * 100:.0f} pp'
        duze = d.groupby('sport').agg(n=('traf', 'size'), P=('p', 'mean'), t=('traf', 'mean'))
        ogol += '; ' + ', '.join(f'{s} n={int(r.n)} P {r.P:.0%} wchodzi {r.t:.0%}' for s, r in duze.iterrows())
        out.append(ogol)
    out.append('  (podejrzenie = miejsce do sprawdzenia na pelnej historii; blokada dopiero po backtescie i PR, tylko zaostrza)')
    return out


def main(a):
    import dzienniki
    here = os.path.dirname(os.path.abspath(__file__))
    ako_p = a[0] if a else os.path.join(here, 'ako_log.csv')
    typy_p = a[1] if len(a) > 1 else os.path.join(here, 'sporty_typy.csv')
    ako = dzienniki._czytaj(ako_p) if os.path.exists(ako_p) else None
    W = dict(pilka=dzienniki.wyniki_pilka(), inne=dzienniki.wyniki_inne(), tenis=dzienniki.wyniki_tenis())
    d = pd.concat([nogi_ako(ako, W) if ako is not None else nogi_typy(None),
                   nogi_typy(pd.read_csv(typy_p) if os.path.exists(typy_p) else None)], ignore_index=True)
    print('\n'.join(linie(d)))


if __name__ == '__main__':
    main(sys.argv[1:])
