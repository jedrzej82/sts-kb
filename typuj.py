#!/usr/bin/env python3
"""Typowanie meczu wyłącznie ze statystyk.
  python3 typuj.py "Athletic" "Alaves"                 # klubowe (auto-dopasowanie nazw)
  python3 typuj.py "Poland" "Netherlands" --intl [--neutral]
  python3 typuj.py A B --kurs 1X=1.35 --kurs O1.5=1.28   # kursy TYLKO po wyborze: EV po podatku 12%
  python3 typuj.py A B --live 60 1:0 [--czerwona-gosp] [--czerwona-gosc]   # na żywo: minuta i wynik
Wynik: prawdopodobieństwa (skalibrowane backtestem), statystyki formy/H2H/rożnych/kartek, ostrzeżenia."""
import os, sys, re, sqlite3, pickle, difflib, unicodedata, datetime as dt
import numpy as np, pandas as pd
from model import fit_dc, dc_lambdas, fit_elo_glm, elo_lambdas, markets, blend, load_calibration, calibrate, live_markets
import json
# v5n (20.09.2026): zespół DC + Elo + pi-ratings (wagi z ensemble.py) i korekta per rynek (korekta_rynkow.py)

HERE = os.path.dirname(os.path.abspath(__file__))
TAX = 0.88
KEY_MARKETS = ['1', 'X', '2', '1X', 'X2', '12', 'DNB_1', 'DNB_2', 'O0.5', 'O1.5', 'O2.5', 'U2.5', 'U3.5', 'U4.5',
               'BTTS_tak', 'BTTS_nie', 'gosp_O0.5', 'gość_O0.5', 'gosp_O1.5', 'gość_O1.5', '1_strzeli_pierwsza',
               '2_strzeli_pierwsza', 'HT_O0.5', 'HT_1', 'HT_X', 'HT_2']


def db():
    return sqlite3.connect(os.path.join(HERE, 'kb.sqlite'))


def norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]', '', s)


ALIASES = {'lech': 'Lech Poznan', 'lechpoznan': 'Lech Poznan', 'legiawarszawa': 'Legia', 'legiawarsaw': 'Legia', 'rakowczestochowa': 'Rakow', 'jagielloniabialystok': 'Jagiellonia', 'zaglebielubin': 'Zaglebie', 'brukbettermalica': 'Termalica', 'termalicanieciecza': 'Termalica', 'wislaplock': 'Wisla Plock', 'athletic': 'Ath Bilbao', 'athleticbilbao': 'Ath Bilbao', 'athleticclub': 'Ath Bilbao', 'alaves': 'Alaves',
           'atleticomadrid': 'Ath Madrid', 'atletico': 'Ath Madrid', 'realmadrid': 'Real Madrid', 'intermediolan': 'Inter',
           'internazionale': 'Inter', 'acmilan': 'Milan', 'manchesterunited': 'Man United', 'manchestercity': 'Man City',
           'psg': 'Paris SG', 'parissaintgermain': 'Paris SG', 'bayernmunich': 'Bayern Munich', 'bayernmonachium': 'Bayern Munich',
           'borussiadortmund': 'Dortmund', 'sportingcp': 'Sp Lisbon', 'sporting': 'Sp Lisbon', 'realsociedad': 'Sociedad',
           'rayovallecano': 'Vallecano', 'celtavigo': 'Celta', 'realbetis': 'Betis', 'wolverhampton': 'Wolves',
           'nottinghamforest': "Nott'm Forest", 'newcastleunited': 'Newcastle', 'tottenhamhotspur': 'Tottenham'}


def resolve(name, pool):
    k = norm(name)
    if k in ALIASES and ALIASES[k] in pool: return ALIASES[k]
    by = {norm(p): p for p in pool}
    if k in by: return by[k]
    c = [p for kk, p in by.items() if k and (k in kk or kk in k)]
    if len(c) == 1: return c[0]
    if c: return min(c, key=lambda p: abs(len(norm(p)) - len(k)))
    m = difflib.get_close_matches(k, list(by), n=1, cutoff=0.55)
    return by[m[0]] if m else None


def cached(key, fn):
    p = os.path.join(HERE, 'cache', f'{key}.pkl'); os.makedirs(os.path.dirname(p), exist_ok=True)
    if os.path.exists(p): return pickle.load(open(p, 'rb'))
    v = fn(); pickle.dump(v, open(p, 'wb')); return v


def team_stats(m, team, n=10):
    t = m[(m.HomeTeam == team) | (m.AwayTeam == team)].sort_values('MatchDate').tail(n)
    if t.empty: return None
    home = t.HomeTeam == team
    gf = np.where(home, t.FTHome, t.FTAway); ga = np.where(home, t.FTAway, t.FTHome)
    res = np.where(gf > ga, 'W', np.where(gf == ga, 'D', 'L'))
    tot = gf + ga
    s = dict(forma=''.join(res), pkt=int((res == 'W').sum() * 3 + (res == 'D').sum()), gole=f'{int(gf.sum())}:{int(ga.sum())}',
             O15=(tot > 1.5).mean(), O25=(tot > 2.5).mean(), U35=(tot < 3.5).mean(), BTTS=((gf > 0) & (ga > 0)).mean(),
             CS=(ga == 0).mean(), FTS=(gf == 0).mean(), ostatni=t.MatchDate.max().date(),
             mecze=[f"{r.MatchDate.date()} {r.HomeTeam} {int(r.FTHome)}:{int(r.FTAway)} {r.AwayTeam}" for r in t.tail(5).itertuples()])
    cf = np.where(home, t.HomeCorners, t.AwayCorners); ca = np.where(home, t.AwayCorners, t.HomeCorners)
    yc = np.where(home, t.HomeYellow, t.AwayYellow); sh = np.where(home, t.HomeTarget, t.AwayTarget)
    if np.isfinite(cf.astype(float)).sum() >= 3:
        s['rożne_za'] = np.nanmean(cf.astype(float)); s['rożne_przeciw'] = np.nanmean(ca.astype(float))
        s['żółte'] = np.nanmean(yc.astype(float)); s['strzały_celne'] = np.nanmean(sh.astype(float))
    return s


def venue_stats(m, team, where, since):
    col = 'HomeTeam' if where == 'dom' else 'AwayTeam'
    t = m[(m[col] == team) & (m.MatchDate >= since)]
    if len(t) < 3: return None
    gf = t.FTHome if where == 'dom' else t.FTAway; ga = t.FTAway if where == 'dom' else t.FTHome
    return dict(n=len(t), W=(gf > ga).mean(), D=(gf == ga).mean(), L=(gf < ga).mean(), gf=gf.mean(), ga=ga.mean(),
                O15=((gf + ga) > 1.5).mean(), U35=((gf + ga) < 3.5).mean(), BTTS=((gf > 0) & (ga > 0)).mean(),
                strzela_pierwszy_HT=(((t.HTHome if where == 'dom' else t.HTAway) > 0)).mean())


def club(home, away, kursy, live=None):
    con = db()
    m = pd.read_sql('select * from matches', con, parse_dates=['MatchDate'])
    elo = pd.read_sql('select club, country, elo, date from clubelo', con)
    elo = elo.sort_values('date').groupby('club').last()
    pool = set(m.HomeTeam) | set(m.AwayTeam) | set(elo.index)
    h, a = resolve(home, pool), resolve(away, pool)
    print(f'Dopasowano: "{home}" → {h} | "{away}" → {a}')
    if not h or not a: sys.exit('Nie znaleziono drużyny w bazie — podaj inną pisownię.')
    today = pd.Timestamp(dt.date.today())
    ostrz = []
    div_of = lambda t: (m[(m.HomeTeam == t) | (m.AwayTeam == t)].sort_values('MatchDate').Division.iloc[-1]
                        if ((m.HomeTeam == t) | (m.AwayTeam == t)).any() else None)
    dh, da = div_of(h), div_of(a)
    ldc, rho = None, -0.05
    if dh and dh == da:
        mdl = cached(f'dc_{dh}_{today.date()}', lambda: fit_dc(m[m.Division == dh], today))
        ldc = dc_lambdas(mdl, h, a); rho = mdl['rho'] if mdl else rho
        if mdl and min(mdl['cnt'].get(h, 0), mdl['cnt'].get(a, 0)) < 10:
            ldc = None; ostrz.append('Beniaminek / mało meczów w tej lidze (<10) — tylko model Elo.')
    else:
        ostrz.append(f'Różne ligi ({dh} vs {da}) — tylko model Elo.')
    glm = cached(f'glm_{today.date()}', lambda: fit_elo_glm(m))
    eh, ea = (elo.elo.get(h), elo.elo.get(a))
    lel = elo_lambdas(glm, eh, ea, dh if dh == da else None) if eh and ea else None
    if lel is None: ostrz.append('Brak Elo jednej z drużyn.')
    lpi = None
    try:
        from pi import prepare, fit_pi_glm, pi_lambdas, gd_hat_for
        def _pi():
            mm, R, N = prepare(m.dropna(subset=['FTHome', 'FTAway']))
            return R, N, fit_pi_glm(mm[mm.MatchDate >= today - pd.Timedelta(days=365 * 4)])
        R, N, pg = cached(f'pi_{today.date()}', _pi)
        if min(N.get(h, 0), N.get(a, 0)) >= 10:
            lpi = pi_lambdas(pg, gd_hat_for(R, h, a), dh if dh == da else None)
        else: ostrz.append('pi-ratings: <10 meczów jednej z drużyn — pominięte.')
    except Exception as e:
        ostrz.append(f'pi-ratings niedostępne ({e}).')
    # v5p: odrzuć składnik z nierealną sumą goli (błąd danych ligi, np. Chacarita–Quilmes 0,68–0,16 z 20.09.2026)
    for nm_ in ('ldc', 'lel', 'lpi'):
        l_ = locals()[nm_]
        if l_ is not None and not (1.2 <= l_[0] + l_[1] <= 5.5):
            ostrz.append(f'{nm_[1:].upper()}: nierealna suma goli {l_[0] + l_[1]:.2f} — składnik pominięty (błąd danych ligi).')
            if nm_ == 'ldc': ldc = None
            elif nm_ == 'lel': lel = None
            else: lpi = None
    if sum(x is not None for x in (ldc, lel, lpi)) <= 1:
        ostrz.append('TYLKO JEDEN MODEL — traktuj P jak „szacunek” (max 1 noga na kupon, nie do K1).')
    wp = os.path.join(HERE, 'ensemble_wagi.json')
    if os.path.exists(wp):
        wd, we, wpi = json.load(open(wp))['wagi_dc_elo_pi']
        parts = [(x, l) for x, l in ((wd, ldc), (we, lel), (wpi, lpi)) if l is not None and x > 0] or \
                [(1.0, l) for l in (ldc, lel, lpi) if l is not None]
        lam = tuple(float(np.exp(sum(x * np.log(l[k]) for x, l in parts) / sum(x for x, _ in parts))) for k in (0, 1)) if parts else None
        zrodla = '+'.join(n for n, (x, l) in zip(('DC', 'Elo', 'pi'), ((wd, ldc), (we, lel), (wpi, lpi))) if l is not None and (x > 0 or len(parts) and parts[0][0] == 1.0))
        print(f'Model v5n: zespół {zrodla} (wagi DC/Elo/pi = {wd}/{we}/{wpi})')
    else:
        W = float(open(os.path.join(HERE, 'blend_weight.txt')).read()) if os.path.exists(os.path.join(HERE, 'blend_weight.txt')) else 0.5
        lam = blend(ldc, lel, W)
    if lam is None: sys.exit('Za mało danych do modelu.')
    if live:
        mn, sc, rh_, ra_ = live
        gh, ga = [int(x) for x in sc.split(':')]
        lm = live_markets(lam[0], lam[1], mn, gh, ga, rh_, ra_, rho)
        print(f'\n=== NA ŻYWO {h} {gh}:{ga} {a} | {mn}. min | czerwone {rh_}/{ra_} ===')
        print(f'Przedmeczowe λ {lam[0]:.2f}–{lam[1]:.2f} → pozostały czas λ {lm["λ_reszta_gosp"]:.2f}–{lm["λ_reszta_gość"]:.2f}')
        for k, p in sorted(((k, v) for k, v in lm.items() if not k.startswith('λ')), key=lambda x: -x[1]):
            print(f'{k:<22}{p:7.1%}' + (' ★' if p >= 0.75 else ''))
        print('(walidacja w przerwie na 6000 meczach 2025/26: P 75% → 76% trafień, 84% → 83%, Brier 0.159)')
        value([(k, v, v) for k, v in lm.items()], kursy)
        return
    mk = markets(*lam, rho)
    kr_p = os.path.join(HERE, 'korekta_rynkow_v5n.csv')
    if os.path.exists(kr_p) and os.path.exists(os.path.join(HERE, 'ensemble_wagi.json')):
        KR = pd.read_csv(kr_p); cal = {}
        def calibrate_v5n(k, p):   # korekta per rynek tylko w dół; rynki „poniżej” zawsze min. −4 pp (reguła użytkownika)
            s = 0.0
            for r in KR[KR.rynek == k].itertuples():
                lo, hi = [float(x) for x in str(r.przedzial).strip('[)').split(',')]
                if lo <= p < hi: s = float(r.przesuniecie)
            if k.startswith('U') and p >= 0.5: s = min(s, -0.04)
            return max(p + s, 0.0)
    else:
        calibrate_v5n = None
        cal = load_calibration(os.path.join(HERE, 'kalibracja_mapa.csv'))
    print(f'\n=== {h} – {a} | liga: {dh}/{da} | Elo {eh and round(eh)} vs {ea and round(ea)} ===')
    print(f'Oczekiwane gole: {lam[0]:.2f} – {lam[1]:.2f} (DC: {ldc and tuple(round(x, 2) for x in ldc)}, Elo: {lel and tuple(round(x, 2) for x in lel)}, pi: {lpi and tuple(round(x, 2) for x in lpi)})')
    print('Najczęstsze wyniki:', mk['wyniki'])
    kor = pd.read_csv(os.path.join(HERE, 'korekta_wlasna.csv')) if os.path.exists(os.path.join(HERE, 'korekta_wlasna.csv')) else None
    rows = []
    for k in KEY_MARKETS:
        p = mk[k]; pc = calibrate_v5n(k, p) if calibrate_v5n else calibrate(cal, k, p)
        if kor is not None:  # uczenie na własnych rozliczonych typach
            for r in kor[kor.rynek == k].itertuples():
                lo, hi = [float(x) for x in str(r.przedział).strip('[)').split(',')]
                if lo <= pc < hi: pc = (1 - r.waga) * pc + r.waga * r.trafność
        rows.append((k, p, pc))
    print('\nRynek            P_model  P_skalibr.' + ('   (v5n: korekta per rynek z backtestu; „poniżej” już −4 pp — nie odejmuj drugi raz)' if calibrate_v5n else ''))
    for k, p, pc in sorted(rows, key=lambda r: -r[2]):
        flag = ' ★' if pc >= 0.75 else ''
        print(f'{k:<18}{p:7.1%}  {pc:7.1%}{flag}')
    for t, lbl in ((h, 'GOSP'), (a, 'GOŚĆ')):
        s = team_stats(m, t)
        if s:
            print(f'\n[{lbl}] {t}: ost.10 {s["forma"]} ({s["pkt"]} pkt, {s["gole"]}) | O1.5 {s["O15"]:.0%} O2.5 {s["O25"]:.0%} '
                  f'U3.5 {s["U35"]:.0%} BTTS {s["BTTS"]:.0%} CS {s["CS"]:.0%} bez gola {s["FTS"]:.0%} | ostatni mecz w bazie {s["ostatni"]}')
            if 'rożne_za' in s:
                print(f'   rożne {s["rożne_za"]:.1f}/{s["rożne_przeciw"]:.1f} | żółte {s["żółte"]:.1f} | strzały celne {s["strzały_celne"]:.1f}')
            for x in s['mecze']: print('   ', x)
            if (today - pd.Timestamp(s['ostatni'])).days > 60:
                ostrz.append(f'{t}: ostatni mecz w bazie {s["ostatni"]} — dane nieaktualne, dopisz wyniki do delta.')
    since = today - pd.Timedelta(days=400)
    vh, va = venue_stats(m, h, 'dom', since), venue_stats(m, a, 'wyjazd', since)
    if vh: print(f'\n{h} u siebie (13 mies., n={vh["n"]}): W{vh["W"]:.0%} D{vh["D"]:.0%} L{vh["L"]:.0%}, gole {vh["gf"]:.2f}:{vh["ga"]:.2f}, O1.5 {vh["O15"]:.0%}, U3.5 {vh["U35"]:.0%}, BTTS {vh["BTTS"]:.0%}')
    if va: print(f'{a} na wyjeździe (n={va["n"]}): W{va["W"]:.0%} D{va["D"]:.0%} L{va["L"]:.0%}, gole {va["gf"]:.2f}:{va["ga"]:.2f}, O1.5 {va["O15"]:.0%}, U3.5 {va["U35"]:.0%}, BTTS {va["BTTS"]:.0%}')
    hh = m[((m.HomeTeam == h) & (m.AwayTeam == a)) | ((m.HomeTeam == a) & (m.AwayTeam == h))].sort_values('MatchDate').tail(8)
    if len(hh):
        print('\nH2H (ost. 8):', ' | '.join(f"{r.MatchDate.date()} {r.HomeTeam} {int(r.FTHome)}:{int(r.FTAway)} {r.AwayTeam}" for r in hh.itertuples()))
    value(rows, kursy)
    if ostrz: print('\nOSTRZEŻENIA:', *ostrz, sep='\n - ')
    print('\nUwaga: model nie zna składów, kontuzji i motywacji z dnia meczu — sprawdź je osobno (korekta maks. ±6 pp).')


def value(rows, kursy):
    if not kursy: return
    d = {k: pc for k, p, pc in rows}
    print('\nWARTOŚĆ (kurs użyty dopiero po wyliczeniu P; podatek 12%):')
    for k, o in kursy.items():
        if k not in d: print(f'  {k}: brak rynku'); continue
        p = d[k]; ev = p * o * TAX - 1
        kelly = max(0.0, (p * o * TAX - 1) / (o * TAX - 1)) if o * TAX > 1 else 0
        print(f'  {k} @ {o}: P={p:.1%}, kurs sprawiedliwy={1 / p / TAX:.2f}, EV={ev:+.1%}, ¼ Kelly={kelly / 4:.1%} bankrollu'
              + ('  ✔ wartość' if ev > 0 else '  ✘ brak wartości'))


# ---------------- reprezentacje ----------------
K_T = [('FIFA World Cup qualification', 40), ('FIFA World Cup', 60), ('UEFA Euro qualification', 40), ('UEFA Euro', 50),
       ('Nations League', 40), ('Copa América', 50), ('African Cup of Nations', 50), ('AFC Asian Cup', 50),
       ('Gold Cup', 50), ('Friendly', 20)]


def intl_elo(df):
    R = {}; rows = []
    for r in df.itertuples():
        k = next((v for t, v in K_T if t in r.tournament), 30)
        rh, ra = R.get(r.home_team, 1500.0), R.get(r.away_team, 1500.0)
        adv = 0 if r.neutral in (True, 'TRUE', 1) else 100
        rows.append((rh, ra, adv))
        e = 1 / (1 + 10 ** (-(rh + adv - ra) / 400)); gd = abs(r.home_score - r.away_score)
        g = 1 if gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8)
        s = 1 if r.home_score > r.away_score else (0.5 if r.home_score == r.away_score else 0)
        R[r.home_team] = rh + k * g * (s - e); R[r.away_team] = ra - k * g * (s - e)
    return R, rows


def intl(home, away, neutral, kursy):
    df = pd.read_sql('select * from intl order by date', db())
    R, pre = cached(f'intl_{dt.date.today()}', lambda: intl_elo(df))
    h, a = resolve(home, set(R)), resolve(away, set(R))
    print(f'Dopasowano: {h} | {a}')
    df = df.assign(rh=[p[0] for p in pre], ra=[p[1] for p in pre], adv=[p[2] for p in pre])
    d = df[df.date >= '2010-01-01']
    x = ((d.rh + d.adv - d.ra) / 100).values

    def fit(y, sgn):
        X = np.c_[np.ones_like(x), sgn * x]; b = np.zeros(2)
        for _ in range(30):
            lam = np.exp(X @ b); b += np.linalg.solve((X * lam[:, None]).T @ X, X.T @ (y - lam))
        return b
    bh, ba = fit(d.home_score.values.astype(float), 1), fit(d.away_score.values.astype(float), -1)
    xx = (R[h] + (0 if neutral else 100) - R[a]) / 100
    lh, la = float(np.exp(bh[0] + bh[1] * xx)), float(np.exp(ba[0] - ba[1] * xx))
    mk = markets(lh, la, -0.05)
    print(f'\n=== {h} – {a} | Elo {R[h]:.0f} vs {R[a]:.0f} {"(neutralny)" if neutral else ""} ===')
    print(f'Oczekiwane gole: {lh:.2f} – {la:.2f} | wyniki: {mk["wyniki"]}')
    rows = [(k, mk[k], mk[k]) for k in KEY_MARKETS]
    for k, p, _ in sorted(rows, key=lambda r: -r[1]): print(f'{k:<18}{p:7.1%}' + (' ★' if p >= 0.75 else ''))
    for t in (h, a):
        t10 = df[(df.home_team == t) | (df.away_team == t)].tail(6)
        print(f'\n{t} ost. 6:', ' | '.join(f'{r.date} {r.home_team} {int(r.home_score)}:{int(r.away_score)} {r.away_team} ({r.tournament})' for r in t10.itertuples()))
    hh = df[((df.home_team == h) & (df.away_team == a)) | ((df.home_team == a) & (df.away_team == h))].tail(6)
    if len(hh): print('\nH2H:', ' | '.join(f'{r.date} {r.home_team} {int(r.home_score)}:{int(r.away_score)} {r.away_team}' for r in hh.itertuples()))
    value(rows, kursy)


if __name__ == '__main__':
    args = [x for x in sys.argv[1:]]
    kursy = {}
    while '--kurs' in args:
        i = args.index('--kurs'); k, v = args[i + 1].split('='); kursy[k] = float(v.replace(',', '.')); del args[i:i + 2]
    live = None
    if '--live' in args:
        i = args.index('--live'); live = (int(args[i + 1]), args[i + 2], args.count('--czerwona-gosp'), args.count('--czerwona-gosc'))
        del args[i:i + 3]
    flags = {x for x in args if x.startswith('--')}; names = [x for x in args if not x.startswith('--')]
    if len(names) != 2: sys.exit(__doc__)
    if '--intl' in flags: intl(names[0], names[1], '--neutral' in flags, kursy)
    else: club(names[0], names[1], kursy, live)
