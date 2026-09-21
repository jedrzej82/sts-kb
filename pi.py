#!/usr/bin/env python3
"""pi.py — pi-ratings (Constantinou & Fenton 2013) dla piłki klubowej. Dodatek v5n (20.09.2026).
Każda drużyna ma osobny rating domowy i wyjazdowy, aktualizowany po każdym meczu z błędu przewidzianej
różnicy goli (logarytmicznie tłumione wysokie wygrane). Działa dla KAŻDEJ drużyny z wynikami w bazie
(nie wymaga ClubElo — w sezonie 2025/26 Elo ma tylko ~56% meczów). Bez kursów.
  python3 pi.py "Gospodarz" "Gość"     # ratingi + λ + rynki z samego pi
Funkcje dla typuj/ensemble: compute_pi(m), fit_pi_glm(df), pi_lambdas(g, gd_hat, div)."""
import os, sys, math, sqlite3, numpy as np, pandas as pd

LAM, GAM, C = 0.035, 0.7, 3.0          # parametry z pracy oryginalnej (zweryfikowane backtestem v5n)


def _g(r):
    return math.copysign(10 ** (abs(r) / C) - 1, r)


def compute_pi(m):
    """m posortowane po dacie. Zwraca (gd_hat przed meczem [np.array], ratingi końcowe {drużyna: (R_dom, R_wyj)}, liczba meczów)."""
    RH, RA, N = {}, {}, {}
    out = np.empty(len(m))
    for i, (h, a, fh, fa) in enumerate(zip(m.HomeTeam.values, m.AwayTeam.values, m.FTHome.values, m.FTAway.values)):
        hh, ha = RH.get(h, 0.0), RA.get(h, 0.0); ah, aa = RH.get(a, 0.0), RA.get(a, 0.0)
        gd_hat = _g(hh) - _g(aa); out[i] = gd_hat
        if fh != fh or fa != fa: continue
        e = (fh - fa) - gd_hat
        psi = C * math.log10(1 + abs(e)); ps_h = psi if e > 0 else -psi; ps_a = -ps_h
        dh = ps_h * LAM; da = ps_a * LAM
        RH[h] = hh + dh; RA[h] = ha + dh * GAM
        RA[a] = aa + da; RH[a] = ah + da * GAM
        N[h] = N.get(h, 0) + 1; N[a] = N.get(a, 0) + 1
    return out, {t: (RH.get(t, 0.0), RA.get(t, 0.0)) for t in set(RH) | set(RA)}, N


def gd_hat_for(ratings, h, a):
    if h not in ratings or a not in ratings: return None
    return _g(ratings[h][0]) - _g(ratings[a][1])


def fit_pi_glm(d):
    """d: mecze z kolumną gd_hat (tylko drużyny z ≥10 meczami historii). Poisson: log λ_h = b0 + b1·x, log λ_a = c0 − c1·x."""
    d = d.dropna(subset=['gd_hat', 'FTHome', 'FTAway'])
    x = np.clip(d.gd_hat.values, -4, 4)
    lg = d.groupby('Division').apply(lambda g: (g.FTHome.mean(), g.FTAway.mean()), include_groups=False).to_dict()

    def fit(y, s):
        X = np.c_[np.ones_like(x), s * x]; b = np.zeros(2)
        for _ in range(30):
            lam = np.exp(X @ b); b += np.linalg.solve((X * lam[:, None]).T @ X, X.T @ (y - lam))
        return b
    return dict(bh=fit(d.FTHome.values.astype(float), 1.0), ba=fit(d.FTAway.values.astype(float), -1.0),
                league=lg, gh=d.FTHome.mean(), ga=d.FTAway.mean())


def pi_lambdas(g, gd_hat, div=None):
    if gd_hat is None or gd_hat != gd_hat: return None
    x = float(np.clip(gd_hat, -4, 4))
    lh = np.exp(g['bh'][0] + g['bh'][1] * x); la = np.exp(g['ba'][0] - g['ba'][1] * x)
    if div in g['league']:
        mh, ma = g['league'][div]; lh *= mh / g['gh']; la *= ma / g['ga']
    return float(lh), float(la)


def prepare(m):
    """Dodaje do m kolumny gd_hat i n_hist (min. liczba wcześniejszych meczów obu drużyn)."""
    m = m.sort_values(['MatchDate', 'MatchTime'], na_position='first').reset_index(drop=True)
    gd, R, N = compute_pi(m)
    cnt = {}; nh = np.empty(len(m))
    for i, (h, a) in enumerate(zip(m.HomeTeam.values, m.AwayTeam.values)):
        nh[i] = min(cnt.get(h, 0), cnt.get(a, 0)); cnt[h] = cnt.get(h, 0) + 1; cnt[a] = cnt.get(a, 0) + 1
    m['gd_hat'] = gd; m['n_hist'] = nh
    m.loc[m.n_hist < 10, 'gd_hat'] = np.nan
    return m, R, N


if __name__ == '__main__':
    if len(sys.argv) != 3: sys.exit(__doc__)
    from typuj import resolve
    from model import markets
    HERE = os.path.dirname(os.path.abspath(__file__))
    m = pd.read_sql('select * from matches', sqlite3.connect(os.path.join(HERE, 'kb.sqlite')), parse_dates=['MatchDate'])
    m, R, N = prepare(m)
    h, a = resolve(sys.argv[1], set(R)), resolve(sys.argv[2], set(R))
    print(f'Dopasowano: {h} | {a}')
    g = fit_pi_glm(m[m.MatchDate >= m.MatchDate.max() - pd.Timedelta(days=365 * 4)])
    gd = gd_hat_for(R, h, a)
    print(f'pi {h}: dom {R[h][0]:+.2f} wyj {R[h][1]:+.2f} (meczów {N.get(h)}) | {a}: dom {R[a][0]:+.2f} wyj {R[a][1]:+.2f} (meczów {N.get(a)})')
    lam = pi_lambdas(g, gd); mk = markets(*lam)
    print(f'oczekiwana różnica goli {gd:+.2f} → λ {lam[0]:.2f}–{lam[1]:.2f}')
    for k in ('1', 'X', '2', '1X', 'X2', 'O1.5', 'O2.5', 'U3.5', 'BTTS_tak'): print(f'{k:<10}{mk[k]:6.1%}')
