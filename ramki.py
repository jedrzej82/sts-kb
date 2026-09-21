#!/usr/bin/env python3
"""Snooker (frame'y), dart (legi) i MMA (metoda zwycięstwa) — rynki poza „kto wygra”.
Model snooker/dart: Elo na poziomie pojedynczego frame'a/lega (aktualizacja udziałem wygranych frame'ów, waga √liczby frame'ów),
potem „wyścig do N” (rozkład ujemny dwumianowy) → zwycięzca, dokładny wynik, handicap frame'ów/legów, suma frame'ów/legów.
Kalibracja izotoniczna z backtestu (dane 2024+ dla snookera; dart: druga połowa okresu).
MMA: zwycięzca z Elo (sporty.py), metoda: częstości zawodników (KO / poddanie / decyzja) ściągnięte do średniej kategorii.
  python3 ramki.py backtest
  python3 ramki.py typuj snooker "Judd Trump" "Mark Selby" --do 6        (do 6 wygranych = bo11)
  python3 ramki.py typuj dart "Luke Littler" "Luke Humphries" --do 6
  python3 ramki.py mma "Fighter A" "Fighter B"
Kursy NIE wchodzą do modelu (tylko do EV: EV = P × kurs × 0,88 − 1)."""
import os, sys, math, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
CAL = os.path.join(HERE, 'ramki_kalibracja.csv')
KF = {'snooker': 10.0, 'dart': 10.0}


def race(p, n):
    """Rozkład wyników wyścigu do n (A ma p na frame). Zwraca {(a,b): P}."""
    q = 1 - p; out = {}
    for k in range(n):
        c = math.comb(n - 1 + k, k)
        out[(n, k)] = c * p ** n * q ** k; out[(k, n)] = c * q ** n * p ** k
    return out


def elo_frames(d, sport, pre=None):
    R, N = {}, {}
    k0 = KF.get(sport, 10.0)
    for r in d.itertuples():
        a, b = R.get(r.gosp, 1500.), R.get(r.gosc, 1500.); tot = r.pg + r.pa
        if pre is not None: pre.append((a, b, N.get(r.gosp, 0), N.get(r.gosc, 0)))
        if tot <= 0: continue
        e = 1 / (1 + 10 ** ((b - a) / 400)); s = r.pg / tot
        kk = k0 * math.sqrt(tot) * (1.6 if min(N.get(r.gosp, 0), N.get(r.gosc, 0)) < 15 else 1.0)
        R[r.gosp] = a + kk * (s - e); R[r.gosc] = b - kk * (s - e)
        N[r.gosp] = N.get(r.gosp, 0) + 1; N[r.gosc] = N.get(r.gosc, 0) + 1
    return R, N


_AVG = None


def dart_avg(name, date, n=20):
    """Średnia 3-lotkowa zawodnika z ostatnich n meczów przed datą (ściągnięta do 85 z wagą 3 meczów)."""
    global _AVG
    if _AVG is None:
        s = pd.read_csv(os.path.join(HERE, 'dart_srednie.csv')); s['match_date'] = pd.to_datetime(s.match_date)
        a = s[['player_name', 'match_date', 'three_dart_average']]
        b = s[['opponent', 'match_date', 'opponent_avg']].rename(columns={'opponent': 'player_name', 'opponent_avg': 'three_dart_average'})
        _AVG = pd.concat([a, b]).dropna().drop_duplicates().sort_values('match_date')
    x = _AVG[(_AVG.player_name == name) & (_AVG.match_date < date)].three_dart_average.tail(n)
    return (x.sum() + 85 * 3) / (len(x) + 3), len(x)


def p_leg_dart(A, B, date, R=None):
    """P lega z różnicy średnich (k=0,06 na 1 pkt średniej, dopasowane w backteście: log-loss 0,630 vs Elo 0,660)."""
    a, na = dart_avg(A, date); b, nb = dart_avg(B, date)
    if min(na, nb) >= 3: return 1 / (1 + math.exp(-0.06 * (a - b))), f'średnie {a:.1f} vs {b:.1f} (z {na}/{nb} meczów)'
    return 1 / (1 + 10 ** ((R.get(B, 1500) - R.get(A, 1500)) / 400)), 'Elo (za mało średnich)'


def data(sport):
    import sporty as sp
    d = sp.load(); d = d[d.sport == sport].copy()
    d = d[(d.pg != d.pa)]
    return d


def markets(p, n):
    S = race(p, n); out = {'A wygra': sum(v for (x, y), v in S.items() if x == n)}
    out['B wygra'] = 1 - out['A wygra']
    for h in range(1, n):
        hh = h + 0.5
        out[f'A -{hh}'] = sum(v for (x, y), v in S.items() if x - y > hh)
        out[f'B +{hh}'] = 1 - out[f'A -{hh}']
        out[f'B -{hh}'] = sum(v for (x, y), v in S.items() if y - x > hh)
        out[f'A +{hh}'] = 1 - out[f'B -{hh}']
    for L in range(n, 2 * n - 1):
        LL = L + 0.5
        out[f'suma > {LL}'] = sum(v for (x, y), v in S.items() if x + y > LL)
        out[f'suma < {LL}'] = 1 - out[f'suma > {LL}']
    return out, S


def fam(k):
    return 'zwycięzca' if 'wygra' in k else 'handicap' if ('+' in k or '-' in k) and 'suma' not in k else 'suma'


def _iso(p, y, nb=12):
    o = np.argsort(p); p, y = np.asarray(p)[o], np.asarray(y, float)[o]
    q = np.array_split(np.arange(len(p)), max(1, min(nb, len(p) // 60)))
    pm = np.array([p[i].mean() for i in q]); ym = np.array([y[i].mean() for i in q]); n = np.array([len(i) for i in q])
    ym = np.maximum.accumulate(ym)
    return [(a, b, c) for a, b, c in zip(pm, ym, n)]


def cal_apply(sport, f, p):
    if not os.path.exists(CAL): return p
    c = pd.read_csv(CAL); c = c[(c.sport == sport) & (c.rodzina == f)]
    if c.empty: return p
    return float(np.interp(p, c.p_model, c.p_kalibr))


def backtest():
    rows_out = []
    for sport, od in (('snooker', '2024-01-01'), ('dart', None), ('tenis stołowy', None), ('siatkówka', None), ('siatkówka plażowa', None), ('badminton', None)):
        d = data(sport)
        if len(d) < 300: continue
        if od is None: od = d.data.min() + (d.data.max() - d.data.min()) / 2
        pre = []; elo_frames(d, sport, pre)
        d = d.assign(ra=[x[0] for x in pre], rb=[x[1] for x in pre], na=[x[2] for x in pre], nb=[x[3] for x in pre])
        t = d[(d.data >= od) & (d.na >= (15 if sport == 'snooker' else 5)) & (d.nb >= (15 if sport == 'snooker' else 5))]
        rows = []
        for r in t.itertuples():
            n = int(max(r.pg, r.pa));
            if n < 2 or n > 18: continue
            p = p_leg_dart(r.gosp, r.gosc, r.data, {r.gosp: r.ra, r.gosc: r.rb})[0] if sport == 'dart' else 1 / (1 + 10 ** ((r.rb - r.ra) / 400))
            mk, _ = markets(p, n)
            for k, v in mk.items():
                x, y = r.pg, r.pa
                if k == 'A wygra': hit = x > y
                elif k == 'B wygra': hit = y > x
                elif k.startswith('suma'):
                    L = float(k.split()[-1]); hit = (x + y > L) if '>' in k else (x + y < L)
                else:
                    side, h = k.split()[0], float(k.split()[1]); diff = (x - y) if side == 'A' else (y - x)
                    hit = diff + h > 0
                rows.append((fam(k), v, hit))
        c = pd.DataFrame(rows, columns=['rodzina', 'p', 'y'])
        for f, g in c.groupby('rodzina'):
            for b in _iso(g.p.values, g.y.values): rows_out.append((sport, f, *b))
        x = c[(c.p >= .75) & (c.p < .995)]
        print(f'{sport}: {len(t)} meczów testowych od {pd.Timestamp(od).date()} | typy P≥75%: {len(x)}, śr. P {x.p.mean():.1%}, trafność {x.y.mean():.1%}')
        for f, g in x.groupby('rodzina'): print(f'    {f:<10} {len(g):6d} typów, śr. P {g.p.mean():.1%}, trafność {g.y.mean():.1%}')
    pd.DataFrame(rows_out, columns=['sport', 'rodzina', 'p_model', 'p_kalibr', 'n']).to_csv(CAL, index=False, float_format='%.4f')
    print('zapisano', CAL)


def mma(A, B):
    import sporty as sp
    d = sp.load(); R, N, *_ = sp.elo(d, 'mma'); A, B = sp.resolve(A, set(R)) or A, sp.resolve(B, set(R)) or B
    e = 1 / (1 + 10 ** ((R.get(B, 1500) - R.get(A, 1500)) / 400)); ec, note = sp.calibrate('mma', e)
    m = pd.read_csv(os.path.join(HERE, 'mma_metody.csv'))
    base = m.metoda.value_counts(normalize=True)
    def rates(f):
        x = m[(m.zwyciezca == f) | (m.przegrany == f)]
        c = x.metoda.value_counts(); n = len(x); k = 8
        return {z: (c.get(z, 0) + k * base.get(z, 0)) / (n + k) for z in ('KO', 'SUB', 'DEC')}, n
    ra, na = rates(A); rb, nb = rates(B)
    dec = (ra['DEC'] + rb['DEC']) / 2; ko = (ra['KO'] + rb['KO']) / 2; sub = (ra['SUB'] + rb['SUB']) / 2; s = dec + ko + sub
    dec, ko, sub = dec / s, ko / s, sub / s
    print(f'MMA: {A} (Elo {R.get(A, 1500):.0f}, {N.get(A, 0)} walk) – {B} (Elo {R.get(B, 1500):.0f}, {N.get(B, 0)} walk)')
    print(f'  {A} wygra {ec:6.1%}\n  {B} wygra {1 - ec:6.1%}')
    print(f'  walka przez decyzję (pełny dystans) {dec:6.1%}   |   koniec przed czasem {1 - dec:6.1%}')
    print(f'  KO/TKO {ko:6.1%}   poddanie {sub:6.1%}   (częstości obu zawodników, ściągnięte do średniej UFC; szacunek, nieskalibrowane)')
    print(f'  {note}')
    if min(N.get(A, 0), N.get(B, 0)) < 5: print('  UWAGA: mało walk w UFC — P to szacunek.')


def main(a):
    if a[0] == 'backtest': backtest()
    elif a[0] == 'mma': mma(a[1], a[2])
    elif a[0] == 'typuj':
        import sporty as sp
        sport = a[1].lower(); d = data(sport); R, N = elo_frames(d, sport)
        A, B = sp.resolve(a[2], set(R)) or a[2], sp.resolve(a[3], set(R)) or a[3]
        n = int(a[a.index('--do') + 1]) if '--do' in a else (6 if sport == 'dart' else 5)
        if sport == 'dart': p, src = p_leg_dart(A, B, pd.Timestamp.today() + pd.Timedelta(days=1), R)
        else: p, src = 1 / (1 + 10 ** ((R.get(B, 1500) - R.get(A, 1500)) / 400)), 'Elo frame\'owe'
        mk, S = markets(p, n)
        jed = 'frame' if sport == 'snooker' else 'leg' if sport == 'dart' else 'set'
        print(f'{sport}: {A} ({N.get(A, 0)} m.) – {B} ({N.get(B, 0)} m.) | P {jed}a dla {A}: {p:.1%} | do {n} wygranych | źródło: {src}')
        for k, v in mk.items():
            nm = k.replace('A ', A + ' ').replace('B ', B + ' ')
            print(f'  {nm:<44} {cal_apply(sport, fam(k), v):6.1%}')
        top = sorted(S.items(), key=lambda kv: -kv[1])[:6]
        print('  najbardziej prawdopodobne wyniki: ' + ', '.join(f'{x}:{y} {v:.1%}' for (x, y), v in top))
        for t in (A, B):
            if t not in R: print(f'  UWAGA: {t} — brak w bazie (python3 sporty.py druzyny {sport} FRAGMENT)')
        if sport == 'dart': print('  Dart: baza tylko od 02.2026 (posiadacze kart PDC) — przy <10 meczach traktuj P jako szacunek.')


if __name__ == '__main__':
    main(sys.argv[1:] or ['backtest'])
