#!/usr/bin/env python3
"""Test „na ślepo” na ostatnich dniach: model widzi tylko dane SPRZED dnia meczu, typuje wszystkie rynki (bez kursów),
potem porównanie z wynikiem. Piłka: 1X2, podwójne szanse, DNB, O/U 0.5–4.5, BTTS, gole drużyn, do przerwy, rożne.
Inne sporty: zwycięzca (Elo). Tenis: zwycięzca meczu (Elo + nawierzchnia).
  python3 test_ostatnie.py [OD=2026-09-12] [DO=2026-09-18] [PROG=0.75]"""
import sys, os, sqlite3, random, numpy as np, pandas as pd
from model import fit_dc, dc_lambdas, fit_elo_glm, elo_lambdas, markets, blend, load_calibration, calibrate

HERE = os.path.dirname(os.path.abspath(__file__))
OD, DO = pd.Timestamp(sys.argv[1] if len(sys.argv) > 1 else '2026-09-12'), pd.Timestamp(sys.argv[2] if len(sys.argv) > 2 else '2026-09-18')
PROG = float(sys.argv[3]) if len(sys.argv) > 3 else 0.75
CAL = load_calibration(os.path.join(HERE, 'kalibracja_mapa.csv'))
W = float(open(os.path.join(HERE, 'blend_weight.txt')).read()) if os.path.exists(os.path.join(HERE, 'blend_weight.txt')) else 0.5
wyniki = []   # (sport, data, mecz, wynik, rynek, P, trafiony)


def pilka():
    m = pd.read_sql('select * from matches', sqlite3.connect(os.path.join(HERE, 'kb.sqlite')), parse_dates=['MatchDate'])
    test = m[(m.MatchDate >= OD) & (m.MatchDate <= DO)].dropna(subset=['FTHome', 'FTAway'])
    glm = fit_elo_glm(m[m.MatchDate < OD])
    import specjalne as S
    for (div, d), g in test.groupby(['Division', 'MatchDate']):
        dm = m[m.Division == div]; mdl = fit_dc(dm, d)
        Rc = S.team_rates(dm, d, 'rożne')
        for r in g.itertuples():
            ldc = dc_lambdas(mdl, r.HomeTeam, r.AwayTeam) if mdl else None
            lel = elo_lambdas(glm, r.HomeElo, r.AwayElo, div) if pd.notna(r.HomeElo) and pd.notna(r.AwayElo) else None
            if ldc is None and lel is None: continue
            mk = markets(*blend(ldc, lel, W), mdl['rho'] if mdl else -0.05)
            fh, fa = int(r.FTHome), int(r.FTAway); t = fh + fa; y = '1' if fh > fa else 'X' if fh == fa else '2'
            out = {'1': y == '1', 'X': y == 'X', '2': y == '2', '1X': y != '2', 'X2': y != '1', '12': y != 'X',
                   'BTTS_tak': fh > 0 and fa > 0, 'BTTS_nie': not (fh > 0 and fa > 0)}
            for k in (0.5, 1.5, 2.5, 3.5, 4.5): out[f'O{k}'] = t > k; out[f'U{k}'] = t < k
            for k in (0.5, 1.5, 2.5): out[f'gosp_O{k}'] = fh > k; out[f'gość_O{k}'] = fa > k
            if y != 'X': out['DNB_1'] = y == '1'; out['DNB_2'] = y == '2'
            if pd.notna(r.HTHome):
                hy = '1' if r.HTHome > r.HTAway else 'X' if r.HTHome == r.HTAway else '2'
                out.update({'HT_1': hy == '1', 'HT_X': hy == 'X', 'HT_2': hy == '2', 'HT_O0.5': r.HTHome + r.HTAway > 0,
                            'HT_O1.5': r.HTHome + r.HTAway > 1})
            mecz = f'{r.HomeTeam} – {r.AwayTeam} ({div})'; wyn = f'{fh}:{fa}' + (f' (do przerwy {int(r.HTHome)}:{int(r.HTAway)})' if pd.notna(r.HTHome) else '')
            for k, v in out.items():
                wyniki.append(('piłka', d.date(), mecz, wyn, k, calibrate(CAL, k, mk[k]), bool(v)))
            if Rc is not None and pd.notna(getattr(r, 'HomeCorners', np.nan)):
                C = S.calib(); _, _, _, mc = S.markets(Rc, r.HomeTeam, r.AwayTeam, 'rożne')
                tc = r.HomeCorners + r.AwayCorners
                for k, p in mc.items():
                    parts = k.split()
                    if len(parts) != 2: continue
                    L = float(parts[1][1:]); hit = tc > L if parts[1][0] == 'O' else tc < L
                    wyniki.append(('piłka', d.date(), mecz, wyn + f', rożne {int(tc)}', k, S.apply_cal(C, k, p), bool(hit)))


def inne():
    import sporty as sp
    d = sp.load()
    for sport in ('baseball', 'futbol amerykański', 'koszykówka', 'hokej', 'esport_cs2', 'snooker', 'rugby', 'mma', 'dart'):
        test = d[(d.sport == sport) & (d.data >= OD) & (d.data <= DO)]
        for day, g in test.groupby('data'):
            R, N, hfa, draws, pdraw = sp.elo(d[d.data < day], sport)
            for r in g.itertuples():
                e = 1 / (1 + 10 ** ((R.get(r.gosc, 1500) - R.get(r.gosp, 1500) - hfa) / 400))
                ec, _ = sp.calibrate(sport, e)
                wyn = f'{r.pg:.0f}:{r.pa:.0f}'; mecz = f'{r.gosp} – {r.gosc} ({r.liga})'
                wyniki.append((sport, day.date(), mecz, wyn, '1 (gosp. wygra)', ec, bool(r.pg > r.pa)))
                wyniki.append((sport, day.date(), mecz, wyn, '2 (gość wygra)', 1 - ec, bool(r.pa > r.pg)))


def tenis():
    import tenis as T
    d = T.load(); test = d[(d.date >= OD - pd.Timedelta(days=7)) & (d.date <= DO)]
    st, _ = T.run_elo(d[d.date < test.date.min()])
    for r in test.itertuples():
        p = T.p_win(st, r.winner_name, r.loser_name, r.surface, str(r.best_of) == '5')
        pc = T.calibrate(max(p, 1 - p)); pw = pc if p >= 0.5 else 1 - pc   # P, że wygra faktyczny zwycięzca
        mecz = f'{r.winner_name} – {r.loser_name} ({r.tourney_name} {r.round})'
        wyniki.append(('tenis', r.date.date(), mecz, f'wygrał {r.winner_name} {r.score}', f'wygra {r.winner_name}', pw, True))
        wyniki.append(('tenis', r.date.date(), mecz, f'wygrał {r.winner_name} {r.score}', f'wygra {r.loser_name}', 1 - pw, False))


pilka(); inne(); tenis()
W_ = pd.DataFrame(wyniki, columns=['sport', 'data', 'mecz', 'wynik', 'rynek', 'P', 'trafiony'])
W_.to_csv(os.path.join(HERE, 'test_ostatnie.csv'), index=False)
typy = W_[(W_.P >= PROG) & (W_.P < 0.995)]
print(f'Okres {OD.date()} – {DO.date()}, próg P ≥ {PROG:.0%}. Wszystkie oceny rynków: {len(W_)}; typy „postawiłbym”: {len(typy)}')
print('\nTrafność typów per sport:')
print(typy.groupby('sport').agg(typów=('trafiony', 'size'), średnie_P=('P', 'mean'), trafność=('trafiony', 'mean')).to_string(float_format=lambda x: f'{x:.1%}'))
typy = typy.assign(b=pd.cut(typy.P, [PROG, .8, .85, .9, .95, 1.0], right=False))
print('\nTrafność wg przedziału P (czy model nie przesadza):')
print(typy.groupby('b', observed=True).agg(typów=('trafiony', 'size'), średnie_P=('P', 'mean'), trafność=('trafiony', 'mean')).to_string(float_format=lambda x: f'{x:.1%}'))
def rodz(k):
    if k in ('1', '2', '1 (gosp. wygra)', '2 (gość wygra)') or k.startswith('wygra'): return 'zwycięzca (1/2)'
    if k in ('1X', 'X2', '12'): return 'podwójna szansa'
    if k == 'X': return 'remis'
    if k.startswith('DNB'): return 'DNB (zakład bez remisu)'
    if k.startswith('HT_O'): return 'gole do przerwy O'
    if k.startswith('HT_'): return 'wynik do przerwy'
    if k.startswith('BTTS'): return 'BTTS'
    if k.startswith('gosp_O') or k.startswith('gość_O'): return 'gole drużyny O'
    if k.startswith('rożne'): return 'rożne ' + ('powyżej' if ' O' in k else 'poniżej')
    if k.startswith('O'): return 'gole powyżej (O)'
    if k.startswith('U'): return 'gole poniżej (U)'
    return k
fam = typy.assign(f=typy.rynek.map(rodz))
print('\nTrafność wg rodzaju rynku (min. 10 typów):')
t = fam.groupby('f').agg(typów=('trafiony', 'size'), średnie_P=('P', 'mean'), trafność=('trafiony', 'mean'))
print(t[t.typów >= 10].sort_values('typów', ascending=False).to_string(float_format=lambda x: f'{x:.1%}'))
random.seed(19092026); print('\nLOSOWE MECZE — najmocniejszy typ modelu vs wynik:')
for sport, g in W_.groupby('sport'):
    ms = list(g.mecz.unique()); random.shuffle(ms)
    for mz in ms[:6 if sport == 'piłka' else 3]:
        x = g[(g.mecz == mz) & (g.P < 0.995)].sort_values('P', ascending=False)
        x = x[x.P >= PROG] if (x.P >= PROG).any() else x.head(1)
        typs = '; '.join(f'{r.rynek} {r.P:.0%} {"✔" if r.trafiony else "✘"}' for r in x.itertuples())
        print(f'  [{sport}] {x.data.iloc[0]} {mz} → {x.wynik.iloc[0]} | {typs}')
