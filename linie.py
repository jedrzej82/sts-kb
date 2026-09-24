#!/usr/bin/env python3
"""Rynki poza zwycięzcą dla sportów drużynowych i tenisa (bez kursów, tylko statystyka):
  • suma punktów/goli/runów (O/U dowolna linia), handicap (spread), suma drużyny — koszykówka, hokej, baseball, futbol amer.,
    piłka ręczna, siatkówka (sety), esport (mapy); model: atak/obrona drużyny (EWMA z wagą świeżości) × średnia ligi,
    rozkład normalny z odchyleniem z historii ligi, kalibracja izotoniczna z backtestu (sezon 2015+).
  • tenis: sety — 2:0 / 2:1 (bo3), 3:0/3:1/3:2 (bo5), „powyżej 2,5 seta”, handicap setowy; z Elo tenis.py; kalibracja z backtestu.
  python3 linie.py typuj SPORT "Gosp" "Gość" [--linia 215.5] [--handicap -5.5]
  python3 linie.py tenis "Zawodnik A" "Zawodnik B" [--clay|--grass] [--bo5]
  python3 linie.py mapy esport_cs2|esport_lol "A" "B" [--bo5]  — mapy: 2:0/2:1, O/U 2,5 mapy, handicap ±1,5
  python3 linie.py backtest            — sigma + kalibracja (linie_kalibracja.csv) dla wszystkich sportów + tenisa"""
import os, sys, numpy as np, pandas as pd
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
CAL = os.path.join(HERE, 'linie_kalibracja.csv'); SIG = os.path.join(HERE, 'linie_sigma.csv')
ALPHA = 0.04      # waga ostatniego meczu (≈ ostatnie 25–50 meczów); dobrane na RMSE 2015–2026 (NFL: 0.08)
ALPHA_SPORT = {'futbol amerykański': 0.08}
PRIOR = 5.0       # ściąganie do średniej ligi (w meczach)
STEP = {'koszykówka': 2.0, 'futbol amerykański': 1.5, 'hokej': 0.5, 'baseball': 0.5, 'piłka ręczna': 1.0,
        'siatkówka': 0.5}   # esport: mapy liczone z P serii (mapy_markets), nie ze średnich punktów


def rate_pass(d, sport, rec=None):
    """Jedno przejście chronologiczne: przed każdym meczem prognoza μ gosp/gość, potem aktualizacja. Zwraca stan."""
    T, L, last = {}, {}, {}; ALPHA = ALPHA_SPORT.get(sport, globals()['ALPHA'])
    for r in d[d.sport == sport].itertuples():
        lg = L.setdefault(r.liga, [None, None])
        if lg[0] is None: lg[0], lg[1] = float(r.pg), float(r.pa)
        for t in (r.gosp, r.gosc):
            if t in T and (r.data - last[t]).days > 90:  # nowy sezon → 1/3 z powrotem do średniej
                s = T[t]; s[0] = 1 + (s[0] - 1) * 0.67; s[1] = 1 + (s[1] - 1) * 0.67; s[2] = min(s[2], 10)
            last[t] = r.data
        h = T.setdefault(r.gosp, [1.0, 1.0, 0]); a = T.setdefault(r.gosc, [1.0, 1.0, 0])
        sh = lambda s, i: (s[i] * s[2] + PRIOR) / (s[2] + PRIOR)
        mh = lg[0] * sh(h, 0) * sh(a, 1); ma = lg[1] * sh(a, 0) * sh(h, 1)
        if rec is not None and h[2] >= 8 and a[2] >= 8: rec.append((r.data, r.liga, mh, ma, r.pg, r.pa))
        ah = r.pg / max(lg[0], 1e-6); aa = r.pa / max(lg[1], 1e-6)   # wynik względem średniej (gosp./gość osobno)
        h[0] += ALPHA * (ah / max(sh(a, 1), .2) - h[0]); h[1] += ALPHA * (aa / max(sh(a, 0), .2) - h[1])
        a[0] += ALPHA * (aa / max(sh(h, 1), .2) - a[0]); a[1] += ALPHA * (ah / max(sh(h, 0), .2) - a[1])
        h[2] += 1; a[2] += 1
        lg[0] += 0.01 * (r.pg - lg[0]); lg[1] += 0.01 * (r.pa - lg[1])
    return T, L, last


def _iso(p, y, nb=15):
    o = np.argsort(p); p, y = p[o], y[o].astype(float)
    q = np.array_split(np.arange(len(p)), nb)
    B = [[p[i].mean(), y[i].mean(), len(i)] for i in q if len(i)]
    i = 0
    while i < len(B) - 1:
        if B[i][1] > B[i + 1][1]:
            x, z = B[i], B[i + 1]; w = x[2] + z[2]
            B[i] = [(x[0] * x[2] + z[0] * z[2]) / w, (x[1] * x[2] + z[1] * z[2]) / w, w]; del B[i + 1]; i = max(i - 1, 0)
        else: i += 1
    return B


def cal_apply(sport, fam, p):
    if not os.path.exists(CAL): return p
    c = pd.read_csv(CAL); c = c[(c.sport == sport) & (c.rodzina == fam)]
    if c.n.sum() < 300: return p
    return float(np.interp(p, c.p_model, c.p_kalibr))


def sigma(sport, liga):
    if not os.path.exists(SIG): return None
    s = pd.read_csv(SIG); x = s[(s.sport == sport) & (s.liga == liga)]
    if x.empty: x = s[s.sport == sport]
    return (float(x.sd_suma.median()), float(x.sd_roznica.median())) if len(x) else None


def backtest_team(d):
    out_s, out_c = [], []
    for sport in sorted(set(d.sport)):
        if sport not in STEP: continue
        rec = []; rate_pass(d, sport, rec)
        r = pd.DataFrame(rec, columns=['data', 'liga', 'mh', 'ma', 'pg', 'pa'])
        r = r[r.data >= '2015-01-01'] if (r.data >= '2015-01-01').sum() > 800 else r
        if len(r) < 300: continue
        r['es'] = r.pg + r.pa - (r.mh + r.ma); r['em'] = (r.pg - r.pa) - (r.mh - r.ma)
        sg = r.groupby('liga').agg(sd_suma=('es', 'std'), sd_roznica=('em', 'std'), n=('es', 'size')).reset_index()
        sg = sg[sg.n >= 100]; sg['sport'] = sport; out_s.append(sg)
        sgd = sg.set_index('liga')
        st = STEP[sport]; rows = []
        for x in r.itertuples():
            if x.liga not in sgd.index: continue
            ss, sm = sgd.loc[x.liga, 'sd_suma'], sgd.loc[x.liga, 'sd_roznica']
            mu_s, mu_m = x.mh + x.ma, x.mh - x.ma; tot, mar = x.pg + x.pa, x.pg - x.pa
            base = np.floor(mu_s / st) * st + st / 2 if st >= 1 else np.floor(mu_s) + 0.5
            for k in range(-10, 11):
                Lk = base + k * st
                po = 1 - norm.cdf(Lk, mu_s, ss)
                rows.append(('suma O', po, tot > Lk)); rows.append(('suma U', 1 - po, tot < Lk))
            hb = np.floor(-mu_m) + 0.5
            for k in range(-10, 11):
                H = hb + k * max(st, 1) / (2 if st < 1 else 1)
                ph = 1 - norm.cdf(-H, mu_m, sm)          # P(gosp. + H wygrywa)  ⇔ margin > -H
                rows.append(('handicap', ph, mar > -H)); rows.append(('handicap', 1 - ph, mar < -H))
        c = pd.DataFrame(rows, columns=['rodzina', 'p', 'y'])
        for fam, g in c.groupby('rodzina'):
            for b in _iso(g.p.values, g.y.values, 20): out_c.append((sport, fam, *b))
        t = c[(c.p >= .75)]
        print(f'{sport}: {len(r)} m. testowych | typy P≥75%: {len(t)}, śr. P model {t.p.mean():.1%}, trafność {t.y.mean():.1%} '
              f'(sd sumy ~{sg.sd_suma.median():.1f}, sd różnicy ~{sg.sd_roznica.median():.1f})')
    return out_s, out_c


def sets_probs(p, bo5=False):
    """P wygrania seta z P meczu (odwrócenie), potem rozkład wyników setowych."""
    lo, hi = 0.0, 1.0
    f = (lambda s: s ** 3 * (1 + 3 * (1 - s) + 6 * (1 - s) ** 2)) if bo5 else (lambda s: s * s * (3 - 2 * s))
    for _ in range(60):
        m = (lo + hi) / 2
        if f(m) < p: lo = m
        else: hi = m
    s = (lo + hi) / 2; q = 1 - s
    if not bo5:
        return {'2:0': s * s, '2:1': 2 * s * s * q, '1:2': 2 * q * q * s, '0:2': q * q}
    return {'3:0': s ** 3, '3:1': 3 * s ** 3 * q, '3:2': 6 * s ** 3 * q * q, '2:3': 6 * q ** 3 * s * s, '1:3': 3 * q ** 3 * s, '0:3': q ** 3}


def tennis_markets(p, bo5=False):
    S = sets_probs(p, bo5); out = dict(S)
    if not bo5:
        out['powyżej 2,5 seta'] = S['2:1'] + S['1:2']; out['poniżej 2,5 seta'] = S['2:0'] + S['0:2']
        out['A handicap -1,5 seta'] = S['2:0']; out['B handicap +1,5 seta'] = 1 - S['2:0']
        out['B handicap -1,5 seta'] = S['0:2']; out['A handicap +1,5 seta'] = 1 - S['0:2']
    else:
        out['powyżej 3,5 seta'] = 1 - S['3:0'] - S['0:3']; out['poniżej 3,5 seta'] = S['3:0'] + S['0:3']
        out['powyżej 4,5 seta'] = S['3:2'] + S['2:3']; out['poniżej 4,5 seta'] = 1 - out['powyżej 4,5 seta']
    return out


def backtest_tennis():
    import tenis as T
    d = T.load(); cut = pd.Timestamp('2024-01-01')
    _, pre = T.run_elo(d)
    t = d.iloc[:len(pre)].copy()
    t['p'] = [1 / (1 + 10 ** (((0.5 * x[1] + 0.5 * x[3]) - (0.5 * x[0] + 0.5 * x[2])) / 400)) for x in pre]
    t['n'] = [min(x[4], x[5]) for x in pre]
    t = t[(t.date >= cut) & (t.n >= 10) & t.score.notna()]
    t['sety'] = t.score.astype(str).str.count('-'); t['bo5'] = t.best_of.astype(str) == '5'
    rows = []; rng = np.random.default_rng(1)
    for r in t.itertuples():
        if r.bo5 or r.sety not in (2, 3): continue
        a_wins = rng.random() < 0.5                     # losowa strona — nie warunkujemy na zwycięzcy
        pA = r.p if a_wins else 1 - r.p; mk = tennis_markets(pA, False)
        a20 = a_wins and r.sety == 2; b20 = (not a_wins) and r.sety == 2
        rows += [('sety O/U', mk['powyżej 2,5 seta'], r.sety == 3), ('sety O/U', mk['poniżej 2,5 seta'], r.sety == 2),
                 ('handicap setowy', mk['A handicap -1,5 seta'], a20), ('handicap setowy', mk['B handicap +1,5 seta'], not a20),
                 ('handicap setowy', mk['B handicap -1,5 seta'], b20), ('handicap setowy', mk['A handicap +1,5 seta'], not b20)]
    c = pd.DataFrame(rows, columns=['rodzina', 'p', 'y']); out = []
    for fam, g in c.groupby('rodzina'):
        for b in _iso(g.p.values, g.y.values, 20): out.append(('tenis', fam, *b))
    x = c[c.p >= .75]
    print(f'tenis sety: {len(t)} m. testowych | typy P≥75%: {len(x)}, śr. P {x.p.mean():.1%}, trafność {x.y.mean():.1%}')
    return out


def mapy_markets(p_seria=None, p_mapa=None, bo=3):
    """Esport: z P serii (CS2/Valorant) lub P mapy (LoL) → wynik mapowy, powyżej 2,5 mapy, handicap ±1,5 mapy."""
    if p_mapa is None: p_mapa = sets_probs(p_seria, bo == 5).__class__ and _inv(p_seria, bo)
    S = sets_probs_from_set(p_mapa, bo); out = dict(S)
    if bo == 3:
        out['powyżej 2,5 mapy'] = S['2:1'] + S['1:2']; out['poniżej 2,5 mapy'] = 1 - out['powyżej 2,5 mapy']
        out['A -1,5 mapy'] = S['2:0']; out['B +1,5 mapy'] = 1 - S['2:0']; out['B -1,5 mapy'] = S['0:2']; out['A +1,5 mapy'] = 1 - S['0:2']
    return out


def _inv(p, bo):
    f = (lambda s: s ** 3 * (1 + 3 * (1 - s) + 6 * (1 - s) ** 2)) if bo == 5 else (lambda s: s * s * (3 - 2 * s))
    lo, hi = 0.0, 1.0
    for _ in range(60):
        m = (lo + hi) / 2; lo, hi = (m, hi) if f(m) < p else (lo, m)
    return (lo + hi) / 2


def sets_probs_from_set(s, bo=3):
    q = 1 - s
    if bo == 3: return {'2:0': s * s, '2:1': 2 * s * s * q, '1:2': 2 * q * q * s, '0:2': q * q}
    return {'3:0': s ** 3, '3:1': 3 * s ** 3 * q, '3:2': 6 * s ** 3 * q * q, '2:3': 6 * q ** 3 * s * s, '1:3': 3 * q ** 3 * s, '0:3': q ** 3}


def backtest_cs2(d):
    import sporty as sp
    pre = []; hfa = sp.elo(d, 'esport_cs2', pre)[2]
    t = d[d.sport == 'esport_cs2'].assign(ra=[x[0] for x in pre], rb=[x[1] for x in pre], na=[x[2] for x in pre], nb=[x[3] for x in pre])
    t = t[(t.na >= 15) & (t.nb >= 15) & (t.pg + t.pa).isin([2, 3])]
    rows = []
    for r in t.itertuples():
        e = 1 / (1 + 10 ** ((r.rb - r.ra) / 400)); mk = mapy_markets(p_mapa=_inv(e, 3))
        a20, b20, three = (r.pg == 2 and r.pa == 0), (r.pa == 2 and r.pg == 0), (r.pg + r.pa == 3)
        rows += [('mapy O/U', mk['powyżej 2,5 mapy'], three), ('mapy O/U', mk['poniżej 2,5 mapy'], not three),
                 ('handicap mapowy', mk['A -1,5 mapy'], a20), ('handicap mapowy', mk['B +1,5 mapy'], not a20),
                 ('handicap mapowy', mk['B -1,5 mapy'], b20), ('handicap mapowy', mk['A +1,5 mapy'], not b20)]
    c = pd.DataFrame(rows, columns=['rodzina', 'p', 'y']); out = []
    for fam, g in c.groupby('rodzina'):
        for b in _iso(g.p.values, g.y.values, 12): out.append(('esport_cs2', fam, *b))
    x = c[c.p >= .75]
    print(f'CS2 mapy: {len(t)} serii | typy P≥75%: {len(x)}, śr. P {x.p.mean():.1%}, trafność {x.y.mean():.1%}')
    return out


def main(a):
    if a[0] == 'backtest':
        import sporty as sp
        d = sp.load(); s, c = backtest_team(d); c += backtest_tennis(); c += backtest_cs2(d)
        pd.concat(s).to_csv(SIG, index=False, float_format='%.3f')
        pd.DataFrame(c, columns=['sport', 'rodzina', 'p_model', 'p_kalibr', 'n']).to_csv(CAL, index=False, float_format='%.4f')
        print('zapisano', SIG, CAL)
    elif a[0] == 'typuj':
        import sporty as sp
        sport = a[1].lower(); d = sp.load(); T, L, last = rate_pass(d, sport)
        h, g = sp.resolve(a[2], set(T)) or a[2], sp.resolve(a[3], set(T)) or a[3]
        if h not in T or g not in T: sys.exit(f'Brak drużyny w bazie wyników ({h if h not in T else g}) — linie liczone tylko dla drużyn z historią meczów.')
        ds = d[(d.sport == sport) & ((d.gosp == h) | (d.gosc == h))]; liga = ds.liga.iloc[-1]
        lg = L[liga]; sh = lambda s, i: (s[i] * s[2] + PRIOR) / (s[2] + PRIOR)
        today = pd.Timestamp.today().normalize()
        for t in (h, g):   # nowy sezon (ostatni mecz > 90 dni temu) → 1/3 do średniej, jak w pętli
            if (today - last[t]).days > 90:
                T[t] = [1 + (T[t][0] - 1) * 0.67, 1 + (T[t][1] - 1) * 0.67, min(T[t][2], 10)]
        mh = lg[0] * sh(T[h], 0) * sh(T[g], 1); ma = lg[1] * sh(T[g], 0) * sh(T[h], 1)
        sg = sigma(sport, liga) or (max(1.0, 0.12 * (mh + ma)), max(1.0, 0.12 * (mh + ma)))
        st = STEP.get(sport, 1.0); mu_s, mu_m = mh + ma, mh - ma
        print(f'{sport} ({liga}): {h} – {g}\n  oczekiwane: {mh:.1f} – {ma:.1f}, suma {mu_s:.1f} (±{sg[0]:.1f}), różnica {mu_m:+.1f} (±{sg[1]:.1f})')
        lines = [float(x) for x in a[a.index('--linia') + 1].split(',')] if '--linia' in a else \
            [np.floor(mu_s / st) * st + st / 2 + k * st for k in range(-3, 4)] if st >= 1 else [np.floor(mu_s) + 0.5 + k for k in range(-2, 3)]
        print('  SUMA (O/U):')
        for Lk in lines:
            po = 1 - norm.cdf(Lk, mu_s, sg[0])
            print(f'    {Lk:>7.1f}:  powyżej {cal_apply(sport, "suma O", po):6.1%}   poniżej {cal_apply(sport, "suma U", 1 - po):6.1%}')
        hs = [float(x) for x in a[a.index('--handicap') + 1].split(',')] if '--handicap' in a else \
            [np.floor(-mu_m) + 0.5 + k * max(st, 1) for k in range(-3, 4)]
        print('  HANDICAP gospodarza (np. -5,5 = gosp. musi wygrać 6+):')
        for H in hs:
            ph = 1 - norm.cdf(-H, mu_m, sg[1])
            print(f'    gosp. {H:+6.1f}: {cal_apply(sport, "handicap", ph):6.1%}   gość {-H:+6.1f}: {cal_apply(sport, "handicap", 1 - ph):6.1%}')
        for nm, mu in ((h, mh), (g, ma)):
            ls = np.floor(mu) + 0.5
            print(f'  suma drużyny {nm}: oczekiwane {mu:.1f}; powyżej {ls:.1f}: {1 - norm.cdf(ls, mu, sg[0] / np.sqrt(2)):.1%} (nieskalibrowane)')
        if sport == 'hokej': print('  UWAGA: w bazie NHL wynik końcowy zawiera dogrywkę; STS w hokeju zwykle liczy O/U w 60 min — odejmij ~0,1 gola od oczekiwanej sumy.')
        if not os.path.exists(CAL) or pd.read_csv(CAL).query('sport == @sport').empty: print('  BRAK KALIBRACJI linii dla tego sportu — traktuj jak „szacunek”.')
    elif a[0] == 'mapy':   # python3 linie.py mapy esport_cs2|esport_lol "A" "B" [--bo5]
        import sporty as sp
        sport = a[1]; d = sp.load(); R, N, *_ = sp.elo(d, sport); A, B = sp.resolve(a[2], set(R)), sp.resolve(a[3], set(R))
        e = 1 / (1 + 10 ** ((R.get(B, 1500) - R.get(A, 1500)) / 400)); bo = 5 if '--bo5' in a else 3
        ec, _ = sp.calibrate(sport, e)
        pm = ec if sport == 'esport_lol' else _inv(ec, 3)   # LoL: Elo liczone na mapach; CS2: na seriach
        mk = mapy_markets(p_mapa=pm, bo=bo)
        print(f'{sport}: {A} – {B} | P mapy {A}: {pm:.1%}')
        for k, v in mk.items():
            fam = 'mapy O/U' if 'mapy' in k and ('powyżej' in k or 'poniżej' in k) else 'handicap mapowy' if 'mapy' in k else None
            print(f'  {k.replace("A ", A + " ").replace("B ", B + " "):<34} {cal_apply("esport_cs2", fam, v) if fam else v:6.1%}')
    elif a[0] == 'tenis':
        import tenis as T
        st = T.state(); pl = set(st['R']); T.NCOUNT.update(st['N']); T.ALIASY.update(st.get('alias', {}))
        A, B = T.resolve(a[1], pl), T.resolve(a[2], pl)
        surf = 'Clay' if '--clay' in a else 'Grass' if '--grass' in a else 'Hard'; bo5 = '--bo5' in a
        if not A or not B: sys.exit('Brak zawodnika w bazie.')
        p = T.p_win(st, A, B, surf, bo5); pc = T.calibrate(max(p, 1 - p)); pA = pc if p >= 0.5 else 1 - pc
        print(f'{A} – {B} ({surf}{", bo5" if bo5 else ""}): P({A} wygra) = {pA:.1%}')
        mk = tennis_markets(pA, bo5)
        for k, v in mk.items():
            fam = 'sety O/U' if 'seta' in k and 'handicap' not in k else 'handicap setowy' if 'handicap' in k else None
            vv = cal_apply('tenis', fam, v) if fam else v
            print(f'  {k.replace("A ", A.split()[-1] + " ").replace("B ", B.split()[-1] + " "):<32} {vv:6.1%}')


if __name__ == '__main__':
    main(sys.argv[1:] or ['backtest'])
