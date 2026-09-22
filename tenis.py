#!/usr/bin/env python3
"""Tenis: Elo ogólne + Elo na nawierzchni (styl FiveThirtyEight) z bazy tenis_hist.csv (ATP i WTA 1968–dziś, TennisCourtLog) + wyniki
dopisywane dziennie do tenis_delta.csv (także Challenger/ITF — baza rośnie z każdym dniem).
  python3 tenis.py "Zawodnik A" "Zawodnik B" [--hard|--clay|--grass] [--bo5]
  python3 tenis.py --backtest            — kalibracja na 2024–2025
  python3 tenis.py --wynik RRRR-MM-DD "Zwycięzca" "Przegrany" NAWIERZCHNIA POZIOM   — dopisanie wyniku (np. ITF, WTA)"""
import os, sys, glob, subprocess, difflib, re, unicodedata, pickle, numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(HERE, 'tenis_hist.csv')  # ATP+WTA 1968–dziś (hist_import.py)
DELTA = os.path.join(HERE, 'tenis_delta.csv')
CAL = os.path.join(HERE, 'tenis_kalibracja.csv')


def fetch():
    """Źródło główne: tenis_hist.csv (ATP+WTA 1968–dziś, budowany przez hist_import.py). Brak pliku → uruchom hist_import."""
    if not os.path.exists(HIST):
        subprocess.run([sys.executable, os.path.join(HERE, 'hist_import.py')], check=False)


def load():
    d = pd.read_csv(HIST, low_memory=False)
    d['date'] = pd.to_datetime(d.date); d['src'] = d.tour
    if os.path.exists(DELTA):
        x = pd.read_csv(DELTA); x['date'] = pd.to_datetime(x.date); x['src'] = 'delta'
        d = pd.concat([d, x], ignore_index=True)
    d = d.rename(columns={'zwyciezca': 'winner_name', 'przegrany': 'loser_name', 'nawierzchnia': 'surface', 'poziom': 'tourney_level'})
    d = d.dropna(subset=['date', 'winner_name', 'loser_name'])
    d = d[~d.score.astype(str).str.contains('W/O|RET|DEF|Walkover|w/o|Ret', na=False)]
    d['surface'] = d.surface.fillna('Hard').replace({'Carpet': 'Hard'})
    return d.sort_values('date', kind='stable').reset_index(drop=True)


def k(n): return 250 / (n + 5) ** 0.4


def run_elo(d, until=None):
    R, Rs, N, Ns, last = {}, {}, {}, {}, {}
    pre = []
    for r in d.itertuples():
        if until is not None and r.date >= until: break
        w, l, s = r.winner_name, r.loser_name, r.surface
        rw, rl = R.get(w, 1500.), R.get(l, 1500.); sw, sl = Rs.get((w, s), 1500.), Rs.get((l, s), 1500.)
        pre.append((rw, rl, sw, sl, N.get(w, 0), N.get(l, 0)))
        e = 1 / (1 + 10 ** ((rl - rw) / 400)); es = 1 / (1 + 10 ** ((sl - sw) / 400))
        R[w] = rw + k(N.get(w, 0)) * (1 - e); R[l] = rl - k(N.get(l, 0)) * (1 - e)
        Rs[(w, s)] = sw + k(Ns.get((w, s), 0)) * (1 - es); Rs[(l, s)] = sl - k(Ns.get((l, s), 0)) * (1 - es)
        for p in (w, l): N[p] = N.get(p, 0) + 1; last[p] = r.date
        Ns[(w, s)] = Ns.get((w, s), 0) + 1; Ns[(l, s)] = Ns.get((l, s), 0) + 1
    return dict(R=R, Rs=Rs, N=N, Ns=Ns, last=last), pre


def p_win(st, a, b, s, bo5=False):
    ra, rb = st['R'].get(a, 1500.), st['R'].get(b, 1500.)
    sa, sb = st['Rs'].get((a, s), ra), st['Rs'].get((b, s), rb)
    ea, eb = 0.5 * ra + 0.5 * sa, 0.5 * rb + 0.5 * sb
    p = 1 / (1 + 10 ** ((eb - ea) / 400))
    if bo5:  # mecz do 3 wygranych setów wzmacnia faworyta
        ps = p ** 0.55 / (p ** 0.55 + (1 - p) ** 0.55)
        p = ps ** 3 * (1 + 3 * (1 - ps) + 6 * (1 - ps) ** 2)
    return p


# Litery, ktorych NFKD NIE rozklada — encode('ascii','ignore') po prostu je KASUJE.
# 21.09.2026: przez to norm("Wisla Plock" z polskimi znakami) dawalo "wisapock" zamiast
# "wislaplock" i klub w ogole nie pasowal do bazy; ratowalo to tylko dopasowanie rozmyte,
# czyli przypadek. Dotyczy wszystkich nazw z l z kreska, d z kreska, o z kreska itd.
_LITERY = str.maketrans({'ł':'l','Ł':'L','đ':'d','Đ':'D','ø':'o','Ø':'O','ß':'ss',
                         'æ':'ae','Æ':'AE','œ':'oe','Œ':'OE','þ':'th','Þ':'TH',
                         'ð':'d','Ð':'D','ı':'i','ŋ':'n','ħ':'h','ŧ':'t'})

def norm(s): return re.sub(r'[^a-z]', '', unicodedata.normalize('NFKD', str(s).translate(_LITERY)).encode('ascii', 'ignore').decode().lower())


NCOUNT = {}


NIEJEDNOZNACZNE = object()   # odrzucenie ostateczne — zadna inna sciezka nie ma prawa go cofnac


def _skrot(p):
    """Czy wpis w bazie jest w formie skroconej: "Johnson S." / "Wang X."."""
    t = str(p).replace('.', ' ').split()
    return len(t) > 1 and len(t[-1]) == 1


def _pelne_dla_skrotu(skrot, players):
    """Pelne nazwiska pasujace do skrotu "Nazwisko I." — jesli jest ich kilka, skrot jest wieloznaczny."""
    t = str(skrot).replace('.', ' ').split()
    if len(t) < 2: return []
    naz, ini = norm(' '.join(t[:-1])), norm(t[-1])[:1]
    out = []
    for p in players:
        if _skrot(p) or p == skrot: continue
        tp = str(p).split()
        if len(tp) > 1 and norm(tp[-1]) == naz and norm(tp[0])[:1] == ini: out.append(p)
    return out



def _czl_norm(s):
    return [norm(t) for t in str(s).replace('.', ' ').split() if norm(t)]


def _czlon_pasuje(a, b):
    """Czy dwa czlony nazwiska to ten sam czlon: identyczne, jeden przedrostkiem drugiego,
    albo jeden jest inicjalem drugiego ("S." i "Sofia")."""
    if a == b: return True
    if len(a) == 1 or len(b) == 1: return a[:1] == b[:1]
    return a.startswith(b) or b.startswith(a)


def _wspolne_czlony(zrodlo, kandydat):
    """Ile czlonow nazwy ze zrodla ma odpowiednik u kandydata. Kazdy czlon kandydata
    moze byc zuzyty tylko raz, zeby "Tyler" nie liczyl sie dwa razy."""
    tz, tk = _czl_norm(zrodlo), list(_czl_norm(kandydat))
    n = 0
    for z in tz:
        for i, k in enumerate(tk):
            if _czlon_pasuje(z, k):
                n += 1; tk.pop(i); break
    return n


def _resolve1(name, players):
    k_ = norm(name)
    if not k_: return None
    by = {norm(p): p for p in players if norm(p)}
    if k_ in by: return by[k_]
    parts = [x for x in str(name).replace('.', ' ').split() if x]
    sur = norm(parts[-1]) if parts else k_
    if not sur: return None
    c = [p for p in players if p.split() and norm(p.split()[-1]) == sur]
    # 22.09.2026. Dopasowanie po OSTATNIM czlonie zwracalo kandydata BEZ sprawdzenia pozostalych:
    #   "Zink Tyler"    -> "Michelle Tyler"  (inna osoba, inna plec, inny tour)
    #   "Grabher Julia" -> "Marilda Julia"   (ostatni mecz w bazie 1987-10-12)
    # STS podaje "Nazwisko Imie", wiec ostatni czlon to czesto IMIE, a nie nazwisko — i wtedy
    # trafiamy na przypadkowa osobe, ktora akurat tak sie nazywa. Sciezka odwracania czlonow
    # istniala, ale nigdy nie startowala, bo kod zwracal zle trafienie zamiast None.
    # Przy nazwie wieloczlonowej zadamy zgodnosci CO NAJMNIEJ DWOCH czlonow.
    if len(parts) > 1:
        c = [p for p in c if _wspolne_czlony(name, p) >= 2]
    if len(c) == 1: return c[0]
    if c and len(parts) == 1:
        # kilku zawodnikow o tym nazwisku, a w ofercie samo nazwisko — wybor po liczbie meczow
        # jest ZGADYWANIEM, wiec musi byc widoczny dla czlowieka
        w = max(c, key=lambda p: NCOUNT.get(p, 0))
        print(f'  UWAGA: "{name}" to samo nazwisko, w bazie {len(c)} zawodnikow '
              f'({", ".join(sorted(c)[:4])}) — wybrano najczesciej grajacego: "{w}". Sprawdz, czy to ten.')
        return w
    if c and len(parts) > 1:
        ini = norm(parts[0])[:1]
        c2 = [p for p in c if ini and norm(p)[:1] == ini]
        if len(c2) == 1: return c2[0]
        if c2:
            print(f'  UWAGA: "{name}" pasuje do {len(c2)} zawodnikow ({", ".join(sorted(c2)[:4])}) — '
                  f'nie dopasowano. Podaj pelne imie i nazwisko.')
            return NIEJEDNOZNACZNE
    m = difflib.get_close_matches(k_, list(by), n=1, cutoff=0.8)
    if m:
        kand = by[m[0]]
        # 22.09.2026: nie dopasowuj do wpisu SKROCONEGO, jesli skrot pasuje do kilku pelnych nazwisk.
        # W przebiegu 12:00 "Sofia Johnson" (WTA 125 Porto) trafilo tak na "Johnson S.", a wsrod
        # pasujacych byl Steve Johnson — zawodnik ATP.
        pelne = _pelne_dla_skrotu(kand, players) if _skrot(kand) else []
        if len(pelne) > 1:
            print(f'  UWAGA: "{name}" -> skrot "{kand}" pasuje do {len(pelne)} pelnych nazwisk '
                  f'({", ".join(sorted(pelne)[:4])}) — NIE dopasowano.')
            return NIEJEDNOZNACZNE
        # ta sama zasada co wyzej: przy nazwie wieloczlonowej rozmyte trafienie musi zgadzac
        # sie na dwoch czlonach, inaczej "Zink Tyler" i "Michelle Tyler" przechodza przez
        # difflib tylko dlatego, ze dziela czlon "Tyler".
        if len(parts) > 1 and _wspolne_czlony(name, kand) < 2:
            print(f'  UWAGA: "{name}" -> rozmyte "{kand}" zgadza sie tylko na jednym czlonie '
                  f'— NIE dopasowano.')
            return None
        print(f'  UWAGA: "{name}" dopasowane ROZMYTO do "{kand}" — upewnij sie, ze to ten zawodnik.')
        return kand
    return None


def resolve(name, players):
    """Zwraca nazwe z bazy albo None. None JEST POPRAWNYM WYNIKIEM — wolacz ma sie zatrzymac.
    21.09.2026 (POPRAWKA 11.4): STS podaje zawodnikow jako "Nazwisko Imie", a baza ma
    "Imie Nazwisko". W przebiegu 19:30 wszystkie cztery mecze tenisa zwrocily "Brak zawodnika
    w bazie" wlasnie z tego powodu. Dlatego przy braku trafienia probujemy tez odwroconej
    kolejnosci czlonow. Dolozone tez ostrzezenia tam, gdzie kod wczesniej po cichu zgadywal."""
    r = _resolve1(name, players)
    if r is NIEJEDNOZNACZNE:
        # 22.09.2026: ODRZUCENIE Z POWODU WIELOZNACZNOSCI JEST OSTATECZNE. Wczesniej sciezka
        # odwracania imienia i nazwiska (dodana 21.09) wpuszczala z powrotem dopasowanie, ktore
        # skrypt sam przed chwila odrzucil: "Sofia Johnson" -> odrzucone jako 4 kandydatow ->
        # po odwroceniu na "Johnson Sofia" dopasowane ROZMYTO do "Johnson S.". Zabezpieczenie
        # dzialalo tylko w jedna strone, dokladnie jak w Poprawce 15.2.
        print(f'  "{name}": odrzucone jako niejednoznaczne — nie probuje innych sciezek.')
        return None
    if r: return r
    czl = [x for x in str(name).replace('.', ' ').split() if x]
    if len(czl) > 1:
        for war in ([czl[-1]] + czl[:-1], list(reversed(czl))):   # "Mensik Jakub" -> "Jakub Mensik"
            alt = ' '.join(war)
            if norm(alt) == norm(name): continue
            r = _resolve1(alt, players)
            if r is NIEJEDNOZNACZNE:
                print(f'  "{name}": po odwroceniu tez niejednoznaczne — nie dopasowano.')
                return None
            if r:
                print(f'  UWAGA: "{name}" dopasowane po ODWROCENIU imienia i nazwiska -> "{r}".')
                return r
    return None


def state():
    p = os.path.join(HERE, 'cache', 'tenis_state.pkl'); os.makedirs(os.path.dirname(p), exist_ok=True)
    mt = max(os.path.getmtime(f) for f in (HIST, DELTA) if os.path.exists(f))
    if os.path.exists(p) and os.path.getmtime(p) > mt: return pickle.load(open(p, 'rb'))
    st, _ = run_elo(load()); pickle.dump(st, open(p, 'wb')); return st


def calibrate(p):
    if not os.path.exists(CAL): return p
    c = pd.read_csv(CAL); return float(np.interp(p, c.p_model, c.p_kalibr))


def main():
    a = sys.argv[1:]
    if a and a[0] == '--wynik':
        row = dict(date=a[1], zwyciezca=a[2], przegrany=a[3], nawierzchnia=a[4], poziom=a[5] if len(a) > 5 else 'ITF', score='', best_of=3)
        pd.DataFrame([row]).to_csv(DELTA, mode='a', header=not os.path.exists(DELTA), index=False); print('dopisano', row); return
    fetch()
    if a and a[0] == '--backtest':
        d = load(); cut = pd.Timestamp('2024-01-01')  # test: 2024–dziś, ATP i WTA razem
        _, pre = run_elo(d)
        t = d.iloc[:len(pre)].assign(rw=[x[0] for x in pre], rl=[x[1] for x in pre], sw=[x[2] for x in pre], sl=[x[3] for x in pre],
                                      nw=[x[4] for x in pre], nl=[x[5] for x in pre])
        t = t[(t.date >= cut) & (t.nw >= 10) & (t.nl >= 10)]
        ew = 0.5 * t.rw + 0.5 * t.sw; el = 0.5 * t.rl + 0.5 * t.sl
        pw = 1 / (1 + 10 ** ((el - ew) / 400))
        # faworyt = wyższe P; trafienie = faworyt wygrał
        pf = np.maximum(pw, 1 - pw); hit = (pw >= 0.5).astype(float)
        c = pd.DataFrame({'p': pf, 'hit': hit}).sort_values('p')
        q = np.array_split(np.arange(len(c)), 15)
        cal = pd.DataFrame([(c.p.values[i].mean(), c.hit.values[i].mean(), len(i)) for i in q], columns=['p_model', 'p_kalibr', 'n'])
        cal['p_kalibr'] = np.maximum.accumulate(cal.p_kalibr.values)
        cal.to_csv(CAL, index=False, float_format='%.4f')
        print(f'mecze testowe {len(c)}, trafność faworyta {hit.mean():.1%}, Brier {((pw - 1) ** 2).mean():.4f}')
        print(cal.to_string(index=False, float_format=lambda x: f'{x:.3f}')); return
    surf = 'Clay' if '--clay' in a else 'Grass' if '--grass' in a else 'Hard'
    names = [x for x in a if not x.startswith('--')]
    st = state(); pl = set(st['R']); NCOUNT.update(st['N'])
    A, B = resolve(names[0], pl), resolve(names[1], pl)
    print(f'Dopasowano: {A} | {B} (nawierzchnia {surf})')
    if not A or not B: sys.exit('Brak zawodnika w bazie (ATP+WTA 1968–dziś, główne turnieje + tenis_delta). Dla ITF/WTA: szacunek ręczny i dopisuj wyniki --wynik.')
    p = p_win(st, A, B, surf, '--bo5' in a); pc = calibrate(max(p, 1 - p)); fav = A if p >= 0.5 else B
    for x in (A, B):
        print(f'  {x}: Elo {st["R"].get(x, 1500):.0f}, {surf} {st["Rs"].get((x, surf), st["R"].get(x, 1500)):.0f}, meczów {st["N"].get(x, 0)}, ostatni w bazie {st["last"].get(x).date()}')
    _nmin = min(st['N'].get(A, 0), st['N'].get(B, 0))
    if _nmin < 5:
        # 22.09.2026, usterka z przebiegu 21:00: Vekic - Wang Xinyu. Wang miala w bazie JEDEN mecz,
        # dostala domyslne Elo 1487 i model wypisal Vekic 85,3% przy kursie 1,90, czyli EV +42%
        # — najwyzsza "wartosc" calego okna, podczas gdy rynek wycenial mecz na 50/50.
        # To nie jest przewaga informacyjna, tylko BRAK DANYCH UDAJACY PRZEWAGE.
        print(f'  BRAK DANYCH RYWALA: najslabiej opisany zawodnik ma {_nmin} mecz(e) w bazie.')
        print(f'  Elo jest wtedy bliskie domyslnemu 1500, wiec ponizsze P NIE JEST pomiarem, tylko')
        print(f'  artefaktem braku danych. NIE buduj na tym nogi kuponu — szczegolnie gdy wychodzi')
        print(f'  wysokie EV przy kursie bliskim 2,00: to sygnal falszywy, nie okazja.')
        print(f'Faworyt: {fav}  P (SZACUNEK, brak danych rywala) ok. {max(p, 1 - p):.0%}')
    else:
        print(f'Faworyt: {fav}  P_model {max(p, 1 - p):.1%}  P_skalibr {pc:.1%}')
    stale = [x for x in (A, B) if (pd.Timestamp.today() - st['last'].get(x)).days > 90]
    if stale: print('OSTRZEŻENIE: dane nieaktualne (>90 dni) dla:', ', '.join(stale), '— sprawdź formę 2026 w sieci, korekta maks. ±6 pp.')


if __name__ == '__main__':
    main()
