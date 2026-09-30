#!/usr/bin/env python3
"""Test „na ślepo” na ostatnich dniach: model widzi tylko dane SPRZED dnia meczu, typuje wszystkie rynki (bez kursów),
potem porównanie z wynikiem. Piłka: 1X2, podwójne szanse, DNB, O/U 0.5–4.5, BTTS, gole drużyn, do przerwy, rożne.
Inne sporty: zwycięzca (Elo). Tenis: zwycięzca meczu (Elo + nawierzchnia).
  python3 test_ostatnie.py [OD=2026-09-12] [DO=2026-09-18] [PROG=0.75]"""
import sys, os, sqlite3, random, pandas as pd
from model import markets

HERE = os.path.dirname(os.path.abspath(__file__))
OD, DO = pd.Timestamp(sys.argv[1] if len(sys.argv) > 1 else '2026-09-12'), pd.Timestamp(sys.argv[2] if len(sys.argv) > 2 else '2026-09-18')
PROG = float(sys.argv[3]) if len(sys.argv) > 3 else 0.75
wyniki = []   # (sport, data, mecz, wynik, rynek, P, trafiony)


def pilka():
    """30.09.2026: dawniej stary model (blend DC+Elo z blend_weight.txt i kalibracja_mapa.csv) — test „na slepo” oceniał
    INNY model niz ten, ktory typuje. Teraz ten sam co typuj.py: zespol v5n (DC+Elo+pi, wagi ensemble_wagi.json,
    wiersze walk-forward z ensemble.build_rows), korekta per rynek z korekta_rynkow_v5n.csv (+ −4 pp dla „ponizej”)
    i korekta_wlasna.csv."""
    import json, ensemble as E, specjalne as S
    from typuj import kalibruj_v5n, korekta_wlasna, KEY_MARKETS
    E.START, E.END = str(OD.replace(day=1).date()), str(DO.date())
    bt = E.build_rows(); bt = bt[(bt.date >= OD) & (bt.date <= DO)]
    w = tuple(json.load(open(os.path.join(HERE, 'ensemble_wagi.json')))['wagi_dc_elo_pi'])
    KR = pd.read_csv(os.path.join(HERE, 'korekta_rynkow_v5n.csv'))
    kw = os.path.join(HERE, 'korekta_wlasna.csv'); KW = pd.read_csv(kw) if os.path.exists(kw) else None
    m = pd.read_sql('select * from matches', sqlite3.connect(os.path.join(HERE, 'kb.sqlite')), parse_dates=['MatchDate'])
    rc = {}
    for r in bt.itertuples():
        lam = E.comb(r, w)
        if lam is None: continue
        mk = markets(*lam, r.rho)
        fh, fa = int(r.fh), int(r.fa); t = fh + fa; y = '1' if fh > fa else 'X' if fh == fa else '2'
        out = {'1': y == '1', 'X': y == 'X', '2': y == '2', '1X': y != '2', 'X2': y != '1', '12': y != 'X',
               'BTTS_tak': fh > 0 and fa > 0, 'BTTS_nie': not (fh > 0 and fa > 0)}
        for k in (0.5, 1.5, 2.5, 3.5, 4.5): out[f'O{k}'] = t > k; out[f'U{k}'] = t < k
        for k in (0.5, 1.5): out[f'gosp_O{k}'] = fh > k; out[f'gość_O{k}'] = fa > k
        if y != 'X': out['DNB_1'] = y == '1'; out['DNB_2'] = y == '2'
        if pd.notna(r.hth):
            hy = '1' if r.hth > r.hta else 'X' if r.hth == r.hta else '2'
            out.update({'HT_1': hy == '1', 'HT_X': hy == 'X', 'HT_2': hy == '2', 'HT_O0.5': r.hth + r.hta > 0})
        mecz = f'{r.gosp} – {r.gosc} ({r.div})'; wyn = f'{fh}:{fa}' + (f' (do przerwy {int(r.hth)}:{int(r.hta)})' if pd.notna(r.hth) else '')
        for k, v in out.items():
            if k not in KEY_MARKETS or k not in mk: continue
            pc = kalibruj_v5n(KR, k, mk[k])
            if KW is not None: pc = korekta_wlasna(pc, KW[KW.rynek == k])
            wyniki.append(('piłka', r.date.date(), mecz, wyn, k, pc, bool(v)))
        if pd.notna(r.hc) and pd.notna(r.ac):
            if (r.div, r.date) not in rc: rc[(r.div, r.date)] = S.team_rates(m[m.Division == r.div], r.date, 'rożne')
            Rc = rc[(r.div, r.date)]
            if Rc is None: continue
            C = S.calib(); _, _, _, mc = S.markets(Rc, r.gosp, r.gosc, 'rożne')
            tc = r.hc + r.ac
            for k, p in mc.items():
                parts = k.split()
                if len(parts) != 2: continue
                L = float(parts[1][1:]); hit = tc > L if parts[1][0] == 'O' else tc < L
                wyniki.append(('piłka', r.date.date(), mecz, wyn + f', rożne {int(tc)}', k, S.apply_cal(C, k, p), bool(hit)))


def inne():
    """30.09.2026: P jak w `sporty.py typuj` (sporty.p_gospodarza: kalibracja hokeja poza NHL, zespol v5n z marza,
    korekta z wlasnych prognoz) — dawniej samo Elo + calibrate, czyli inny model niz ten, ktory typuje."""
    import sporty as sp
    d = sp.load()
    for sport in ('baseball', 'futbol amerykański', 'koszykówka', 'hokej', 'piłka ręczna', 'siatkówka', 'esport_cs2',
                  'snooker', 'rugby', 'mma', 'dart'):
        test = d[(d.sport == sport) & (d.data >= OD) & (d.data <= DO)]
        for day, g in test.groupby('data'):
            hist = d[d.data < day]; inf = {}; pam = {}
            R, N, hfa, draws, pdraw = sp.elo(hist, sport, info=inf)
            for r in g.itertuples():
                ec, _, _, _ = sp.p_gospodarza(hist, sport, R, inf['last'], hfa, draws, r.gosp, r.gosc, dzien=day, pamiec=pam)
                wyn = f'{r.pg:.0f}:{r.pa:.0f}'; mecz = f'{r.gosp} – {r.gosc} ({r.liga})'
                wyniki.append((sport, day.date(), mecz, wyn, '1 (gosp. wygra)', ec, bool(r.pg > r.pa)))
                wyniki.append((sport, day.date(), mecz, wyn, '2 (gość wygra)', 1 - ec, bool(r.pa > r.pg)))


def tenis():
    import tenis as T
    d = T.load(); test = d[(d.date >= OD - pd.Timedelta(days=7)) & (d.date <= DO)]
    st, _ = T.run_elo(d[d.date < test.date.min()])
    for r in test.itertuples():
        p, pw = T.p_skalibr(st, r.winner_name, r.loser_name, r.surface, str(r.best_of) == '5')   # P, że wygra faktyczny zwycięzca
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
