#!/usr/bin/env python3
"""Model statystyczny (bez kursów): Dixon-Coles z zanikiem czasowym per liga + Elo->Poisson globalnie, blend.
Z macierzy wyników liczy rynki: 1X2, podwójna szansa, O/U, BTTS, pierwszy gol, gole drużyn, HT."""
import numpy as np, pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

XI = 0.0019          # zanik wag ~ półokres 365 dni
MAXG = 10


def fit_dc(df, ref_date, years=3.0):
    """df: mecze jednej ligi przed ref_date. Zwraca dict z parametrami."""
    ref = pd.Timestamp(ref_date)
    d = df[(df.MatchDate < ref) & (df.MatchDate >= ref - pd.Timedelta(days=int(365 * years)))]
    if len(d) < 80:
        return None
    teams = sorted(set(d.HomeTeam) | set(d.AwayTeam))
    ix = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    h = d.HomeTeam.map(ix).values; a = d.AwayTeam.map(ix).values
    yh = d.FTHome.values.astype(float); ya = d.FTAway.values.astype(float)
    w = np.exp(-XI * (ref - d.MatchDate).dt.days.values)

    def nll(p):
        att, dfn, home, mu = p[:n], p[n:2 * n], p[2 * n], p[2 * n + 1]
        lh = np.exp(mu + home + att[h] - dfn[a]); la = np.exp(mu + att[a] - dfn[h])
        ll = w * (yh * np.log(lh) - lh + ya * np.log(la) - la)
        rh = w * (yh - lh); ra = w * (ya - la)
        g_att = np.bincount(h, rh, n) + np.bincount(a, ra, n)
        g_def = -np.bincount(a, rh, n) - np.bincount(h, ra, n)
        pen = 10.0
        f = -ll.sum() + pen * (att.sum() ** 2 + dfn.sum() ** 2) + 0.05 * ((att ** 2).sum() + (dfn ** 2).sum())
        g = -np.concatenate([g_att, g_def, [rh.sum(), rh.sum() + ra.sum()]])
        g[:n] += 2 * pen * att.sum() + 0.1 * att
        g[n:2 * n] += 2 * pen * dfn.sum() + 0.1 * dfn
        return f, g

    p0 = np.zeros(2 * n + 2); p0[2 * n] = 0.25; p0[2 * n + 1] = 0.25
    r = minimize(nll, p0, jac=True, method='L-BFGS-B')
    p = r.x
    att, dfn, home, mu = p[:n], p[n:2 * n], p[2 * n], p[2 * n + 1]
    lh = np.exp(mu + home + att[h] - dfn[a]); la = np.exp(mu + att[a] - dfn[h])
    # rho (korekta niskich wyników) — wyszukiwanie 1D
    best, rho = -1e18, 0.0
    for rr in np.linspace(-0.2, 0.1, 31):
        tau = np.ones(len(d))
        m00 = (yh == 0) & (ya == 0); m01 = (yh == 0) & (ya == 1); m10 = (yh == 1) & (ya == 0); m11 = (yh == 1) & (ya == 1)
        tau[m00] = 1 - lh[m00] * la[m00] * rr; tau[m01] = 1 + lh[m01] * rr; tau[m10] = 1 + la[m10] * rr; tau[m11] = 1 - rr
        if (tau <= 0).any(): continue
        v = (w * np.log(tau)).sum()
        if v > best: best, rho = v, rr
    last_seen = pd.concat([d[['MatchDate', 'HomeTeam']].rename(columns={'HomeTeam': 't'}),
                           d[['MatchDate', 'AwayTeam']].rename(columns={'AwayTeam': 't'})]).groupby('t').MatchDate.agg(['max', 'count'])
    return dict(teams=ix, att=att, dfn=dfn, home=home, mu=mu, rho=rho, n=len(d),
                last=last_seen['max'].to_dict(), cnt=last_seen['count'].to_dict())


def dc_lambdas(m, ht, at):
    if m is None or ht not in m['teams'] or at not in m['teams']:
        return None
    i, j = m['teams'][ht], m['teams'][at]
    return (float(np.exp(m['mu'] + m['home'] + m['att'][i] - m['dfn'][j])),
            float(np.exp(m['mu'] + m['att'][j] - m['dfn'][i])))


def fit_elo_glm(df):
    """Globalny Poisson: log λ = b0 + b1*dElo/100 (+ domowy), per liga baza goli. df z HomeElo/AwayElo."""
    d = df.dropna(subset=['HomeElo', 'AwayElo'])
    d = d[d.MatchDate >= d.MatchDate.max() - pd.Timedelta(days=365 * 6)]
    x = ((d.HomeElo - d.AwayElo) / 100.0).values
    lg = d.groupby('Division').apply(lambda g: (g.FTHome.mean(), g.FTAway.mean()), include_groups=False).to_dict()

    def fit(y, sign):
        X = np.c_[np.ones_like(x), sign * x]
        b = np.zeros(2)
        for _ in range(30):
            lam = np.exp(X @ b); g = X.T @ (y - lam); H = (X * lam[:, None]).T @ X
            b += np.linalg.solve(H, g)
        return b
    bh = fit(d.FTHome.values.astype(float), 1.0); ba = fit(d.FTAway.values.astype(float), -1.0)
    return dict(bh=bh, ba=ba, league=lg, gh=d.FTHome.mean(), ga=d.FTAway.mean())


def elo_lambdas(g, elo_h, elo_a, div=None):
    x = (elo_h - elo_a) / 100.0
    lh = np.exp(g['bh'][0] + g['bh'][1] * x); la = np.exp(g['ba'][0] - g['ba'][1] * x)
    if div in g['league']:  # skala ligi
        mh, ma = g['league'][div]; lh *= mh / g['gh']; la *= ma / g['ga']
    return float(lh), float(la)


def score_matrix(lh, la, rho=-0.05):
    ph = poisson.pmf(np.arange(MAXG + 1), lh); pa = poisson.pmf(np.arange(MAXG + 1), la)
    M = np.outer(ph, pa)
    M[0, 0] *= 1 - lh * la * rho; M[0, 1] *= 1 + lh * rho; M[1, 0] *= 1 + la * rho; M[1, 1] *= 1 - rho
    return M / M.sum()


def markets(lh, la, rho=-0.05, ht_ratio=0.44):
    M = score_matrix(lh, la, rho)
    i, j = np.indices(M.shape); tot = i + j
    p1, px, p2 = M[i > j].sum(), M[i == j].sum(), M[i < j].sum()
    out = {'λ_gosp': lh, 'λ_gość': la, '1': p1, 'X': px, '2': p2, '1X': p1 + px, 'X2': px + p2, '12': p1 + p2,
           'BTTS_tak': M[(i > 0) & (j > 0)].sum()}
    out['BTTS_nie'] = 1 - out['BTTS_tak']
    for k in (0.5, 1.5, 2.5, 3.5, 4.5):
        out[f'O{k}'] = M[tot > k].sum(); out[f'U{k}'] = 1 - out[f'O{k}']
    for k in (0.5, 1.5, 2.5):
        out[f'gosp_O{k}'] = M[i > k].sum(); out[f'gość_O{k}'] = M[j > k].sum()
    p00 = M[0, 0]
    out['1_strzeli_pierwsza'] = (1 - p00) * lh / (lh + la); out['2_strzeli_pierwsza'] = (1 - p00) * la / (lh + la)
    out['brak_gola'] = p00
    out['DNB_1'] = p1 / (p1 + p2); out['DNB_2'] = p2 / (p1 + p2)
    H = score_matrix(lh * ht_ratio, la * ht_ratio, rho)
    out['HT_1'] = H[i > j].sum(); out['HT_X'] = H[i == j].sum(); out['HT_2'] = H[i < j].sum()
    out['HT_O0.5'] = 1 - H[0, 0]; out['HT_O1.5'] = H[tot > 1].sum()
    top = sorted(((M[a, b], f'{a}:{b}') for a in range(6) for b in range(6)), reverse=True)[:5]
    out['wyniki'] = ', '.join(f'{s} {p:.0%}' for p, s in top)
    return out


def blend(l_dc, l_elo, w_dc=0.6):
    if l_dc is None: return l_elo
    if l_elo is None: return l_dc
    return tuple(np.exp(w_dc * np.log(a) + (1 - w_dc) * np.log(b)) for a, b in zip(l_dc, l_elo))


def load_calibration(path):
    import os
    if not os.path.exists(path): return {}
    c = pd.read_csv(path); return {k: (g.p_model.values, g.p_kalibr.values) for k, g in c.groupby('rynek')}


def calibrate(cal, market, p):
    if market not in cal: return p
    x, y = cal[market]
    return float(np.interp(p, x, y)) if len(x) > 1 else p


def remaining_share(minute):
    """Udział goli meczu, który zostaje po danej minucie (1. połowa ~45%, 2. ~55% goli)."""
    m = min(max(minute, 0), 90)
    return 0.55 + 0.45 * (45 - m) / 45 if m <= 45 else 0.55 * (90 - m) / 45


def live_markets(lh, la, minute, gh, ga, red_h=0, red_a=0, rho=-0.05):
    """Prawdopodobieństwa na żywo: wynik końcowy = obecny + gole w pozostałym czasie."""
    s = remaining_share(minute)
    rh, ra = lh * s * (0.7 ** red_h) * (1.25 ** red_a), la * s * (0.7 ** red_a) * (1.25 ** red_h)
    M = score_matrix(max(rh, 1e-6), max(ra, 1e-6), rho if minute < 5 else 0.0)
    i, j = np.indices(M.shape); fh, fa = i + gh, j + ga; tot = fh + fa
    out = {'λ_reszta_gosp': rh, 'λ_reszta_gość': ra, '1': M[fh > fa].sum(), 'X': M[fh == fa].sum(), '2': M[fh < fa].sum()}
    out['1X'] = out['1'] + out['X']; out['X2'] = out['X'] + out['2']; out['12'] = out['1'] + out['2']
    for k in (0.5, 1.5, 2.5, 3.5, 4.5):
        out[f'O{k}'] = M[tot > k].sum(); out[f'U{k}'] = 1 - out[f'O{k}']
    out['BTTS_tak'] = M[(fh > 0) & (fa > 0)].sum(); out['BTTS_nie'] = 1 - out['BTTS_tak']
    p0 = M[0, 0]
    out['następny_gol_gosp'] = (1 - p0) * rh / (rh + ra); out['następny_gol_gość'] = (1 - p0) * ra / (rh + ra); out['brak_kolejnego_gola'] = p0
    return out
