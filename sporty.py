#!/usr/bin/env python3
"""Wszystkie sporty z oferty STS poza piłką i tenisem (hokej, koszykówka, siatkówka, piłka ręczna, futsal, esport, baseball,
futbol amerykański, rugby, snooker, dart, MMA/boks …): Elo z przewagą gospodarza per sport, budowane z wyników dopisywanych
codziennie do sporty_delta.csv. Model uczy się od zera — im więcej wyników, tym pewniejszy; kalibracja z własnych prognoz.
  python3 sporty.py wynik RRRR-MM-DD SPORT LIGA "Gosp" "Gość" PKT_G PKT_A [dogrywka:0/1]
  python3 sporty.py typuj SPORT "Gosp" "Gość" [--neutral]
  python3 sporty.py typ RRRR-MM-DD SPORT "Gosp" "Gość" RYNEK P [KURS_TYPU [PIENIADZE]] — zapis prognozy (RYNEK: 1 / 2 / X / 1_60min …)
  python3 sporty.py rozlicz                                         — rozliczenie + kalibracja per sport
  python3 sporty.py stan                                            — ile meczów/drużyn w bazie per sport
  python3 sporty.py druzyny SPORT FRAGMENT                           — nazwy drużyn w bazie (Elo, liczba meczów)
  python3 sporty.py backtest                                        — kalibracja z historii (sporty_hist.csv) → sporty_kalibracja_hist.csv
Baza = sporty_hist.csv (NBA/WNBA/NHL/NFL/MLB z GitHub, hist_import.py) + sporty_delta.csv (wyniki dopisywane codziennie)."""
import os, sys, re, difflib, unicodedata, numpy as np, pandas as pd
import functools, html
import rynek

HERE = os.path.dirname(os.path.abspath(__file__))
DB, LOG, CAL = (os.path.join(HERE, f) for f in ('sporty_delta.csv', 'sporty_typy.csv', 'sporty_kalibracja.csv'))
HIST, CALH = os.path.join(HERE, 'sporty_hist.csv'), os.path.join(HERE, 'sporty_kalibracja_hist.csv')  # cache historyczny (hist_import.py)
TAB = os.path.join(HERE, 'tabele_eu.csv')  # tabele lig europejskich (sport, liga, sezon, data, drużyna, gp, w, d, l, otw, otl, gf, ga)
PYTH = {'hokej': 2.0, 'koszykówka': 13.9, 'piłka ręczna': 7.5, 'siatkówka': 2.5, 'futsal': 2.0, 'unihokej': 2.0, 'piłka wodna': 4.0}


def seeds(sport):
    """Startowe Elo z tabeli ligowej: udział zwycięstw (dogrywki = wygrane, remis = ½) + Pitagoras z bramek/punktów/setów,
    ściągnięte do średniej (6 meczów). Elo = 1500 + 400·log10(w/(1−w)) — siła względem średniej ligi."""
    # 22.09.2026: JEDEN uszkodzony wiersz w tabele_eu.csv wywracal caly skrypt, a przez to
    # caly dzien konczyl sie bez kuponu — tak bylo 21.09 (Bilans: "sporty.py padal na
    # uszkodzonym tabele_eu.csv"). Tabela daje tylko SILE STARTOWA, wiec zly wiersz ma byc
    # pominiety i GLOSNO zgloszony, a nie zatrzymywac analize wszystkich sportow.
    if not os.path.exists(TAB): return []
    t = pd.read_csv(TAB)
    t = t[t.sport == sport].copy()
    if not len(t): return []
    n0 = len(t)
    for kol in ('gp', 'w', 'd', 'l', 'otw', 'otl', 'gf', 'ga'):
        t[kol] = pd.to_numeric(t.get(kol), errors='coerce')
    t['data'] = pd.to_datetime(t.get('data'), errors='coerce')
    t = t.dropna(subset=['gp', 'w', 'd', 'l', 'otw', 'otl', 'gf', 'ga', 'data', 'druzyna'])
    t = t[(t.gp > 0) & (t.gf >= 0) & (t.ga >= 0)]
    if len(t) < n0:
        print(f'  tabele_eu.csv ({sport}): pominieto {n0 - len(t)} z {n0} wierszy z uszkodzonymi danymi '
              f'— sila startowa z tabeli bedzie niepelna dla tego sportu.')
    out = []
    for r in t.itertuples():
        try:
            wp = (r.w + r.otw + 0.5 * r.d) / r.gp
            k = PYTH.get(sport, 2.0)
            c = 0.5 * wp + 0.5 * (r.gf ** k / (r.gf ** k + r.ga ** k)) if r.gf + r.ga > 0 else wp
            c = (c * r.gp + 0.5 * 6) / (r.gp + 6); c = min(max(c, 0.03), 0.97)
            out.append((pd.Timestamp(r.data), r.druzyna, 1500 + 400 * np.log10(c / (1 - c)), int(r.gp), r.liga))
        except (ValueError, TypeError, ZeroDivisionError, OverflowError) as e:
            print(f'  tabele_eu.csv ({sport}): wiersz "{r.druzyna}" pominiety ({type(e).__name__}: {e})')
    return sorted(out)
NFL = dict(ARI='Arizona Cardinals', ATL='Atlanta Falcons', BAL='Baltimore Ravens', BUF='Buffalo Bills', CAR='Carolina Panthers', CHI='Chicago Bears',
           CIN='Cincinnati Bengals', CLE='Cleveland Browns', DAL='Dallas Cowboys', DEN='Denver Broncos', DET='Detroit Lions', GB='Green Bay Packers',
           HOU='Houston Texans', IND='Indianapolis Colts', JAX='Jacksonville Jaguars', KC='Kansas City Chiefs', LV='Las Vegas Raiders', OAK='Las Vegas Raiders',
           LAC='Los Angeles Chargers', SD='Los Angeles Chargers', LA='Los Angeles Rams', STL='Los Angeles Rams', MIA='Miami Dolphins', MIN='Minnesota Vikings',
           NE='New England Patriots', NO='New Orleans Saints', NYG='New York Giants', NYJ='New York Jets', PHI='Philadelphia Eagles', PIT='Pittsburgh Steelers',
           SF='San Francisco 49ers', SEA='Seattle Seahawks', TB='Tampa Bay Buccaneers', TEN='Tennessee Titans', WAS='Washington Commanders')
MLB = dict(ANA='Los Angeles Angels', ARI='Arizona Diamondbacks', ATL='Atlanta Braves', BAL='Baltimore Orioles', BOS='Boston Red Sox', CHA='Chicago White Sox',
           CHN='Chicago Cubs', CIN='Cincinnati Reds', CLE='Cleveland Guardians', COL='Colorado Rockies', DET='Detroit Tigers', HOU='Houston Astros',
           KCA='Kansas City Royals', LAN='Los Angeles Dodgers', MIA='Miami Marlins', FLO='Miami Marlins', MIL='Milwaukee Brewers', MIN='Minnesota Twins',
           NYA='New York Yankees', NYN='New York Mets', OAK='Athletics', ATH='Athletics', PHI='Philadelphia Phillies', PIT='Pittsburgh Pirates',
           SDN='San Diego Padres', SEA='Seattle Mariners', SFN='San Francisco Giants', SLN='St. Louis Cardinals', TBA='Tampa Bay Rays',
           TEX='Texas Rangers', TOR='Toronto Blue Jays', WAS='Washington Nationals', MON='Washington Nationals')
# przewaga gospodarza (pkt Elo) i czy możliwy remis w regulaminowym czasie
DRAW_PRIOR = {'hokej': 0.22, 'piłka ręczna': 0.08, 'futsal': 0.20, 'rugby': 0.03, 'żużel': 0.05, 'unihokej': 0.18, 'piłka wodna': 0.12}
SPORT = {'hokej': (50, True), 'koszykówka': (70, False), 'siatkówka': (40, False), 'piłka ręczna': (60, True),
         'futsal': (50, True), 'baseball': (25, False), 'futbol amerykański': (55, False), 'rugby': (60, True),
         'esport': (0, False), 'snooker': (0, False), 'dart': (0, False), 'mma': (0, False), 'boks': (0, False),
         'żużel': (60, True), 'unihokej': (50, True), 'piłka wodna': (40, True),
         'esport_cs2': (0, False), 'esport_lol': (0, False), 'esport_val': (0, False), 'esport_dota': (0, False),
         'tenis stołowy': (0, False), 'krykiet': (20, False), 'badminton': (0, False), 'siatkówka plażowa': (0, False), 'futbol australijski': (30, False)}
# LoL w bazie = pojedyncze mapy → P serii liczone z P mapy (--bo3/--bo5); CS2/Valorant w bazie = całe serie
MAPOWE = {'esport_lol'}
K = 24


# Litery, ktorych NFKD NIE rozklada — encode('ascii','ignore') po prostu je KASUJE.
# 21.09.2026: przez to norm("Wisla Plock" z polskimi znakami) dawalo "wisapock" zamiast
# "wislaplock" i klub w ogole nie pasowal do bazy; ratowalo to tylko dopasowanie rozmyte,
# czyli przypadek. Dotyczy wszystkich nazw z l z kreska, d z kreska, o z kreska itd.
from nazwy import LITERY as _LITERY   # 29.09.2026: jedna tabela dla wszystkich modulow (nazwy.py)

# 29.09.2026: html.unescape — w bazie dart byl „William O&#039;Connor” obok „William O’Connor” (dwa klucze, dwa Elo)
def norm(s): return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', html.unescape(str(s)).translate(_LITERY)).encode('ascii', 'ignore').decode().lower())


def scal_warianty(d, cicho=False):
    """Ta sama druzyna zapisana na dwa sposoby to w bazie DWIE rozne druzyny: kazda z czescia meczow
    i wlasnym Elo, a resolve() trafia w losowa z nich (slownik {norm: nazwa} zostawia ostatnia).
    Zmierzone 21.09.2026 na trzech miesiacach danych: 15 takich grup w sportach (804 wystapienia
    druzyn w meczach) i 11 w pilce — m.in. "China (W)"/"China W", "Cuba"/"CUBA",
    "Havlickuv Brod"/"Havlíčkův Brod". Sprowadzamy warianty do najczestszej pisowni W OBREBIE SPORTU."""
    if not len(d): return d
    par = pd.concat([d[['sport', c]].rename(columns={c: 'n'}) for c in ('gosp', 'gosc')], ignore_index=True)
    par['k'] = par.n.map(norm); par = par[par.k != '']
    cnt = par.groupby(['sport', 'k', 'n']).size().rename('ile').reset_index()
    wiele = cnt.groupby(['sport', 'k']).n.transform('size') > 1
    if not wiele.any(): return d
    cnt = cnt[wiele].sort_values('ile', kind='stable')
    kanon = cnt.groupby(['sport', 'k']).n.last()          # najczestsza pisownia wygrywa
    zm = {(r.sport, r.n): kanon[(r.sport, r.k)] for r in cnt.itertuples() if r.n != kanon[(r.sport, r.k)]}
    if zm:
        if not cicho:
            prz = ', '.join(f'{a[1]!r}->{b!r}' for a, b in list(zm.items())[:3])
            print(f'  scalono warianty pisowni nazw: {len(zm)} (np. {prz})')
        for c in ('gosp', 'gosc'):
            d[c] = [zm.get((sp, n), n) for sp, n in zip(d.sport, d[c])]
    return d


# 03.10.2026 (zdarzenia.py, MOZLIWY_DUBEL przejrzany recznie): TEN SAM klub pod dwiema nazwami z dwoch zrodel —
# historia rozbita na dwa wpisy. Scalane tylko pary sprawdzone (ta sama liga/kraj, zmiana nazwy ligi albo spadek):
# Zemgale (LHL -> Optibet Hokeja Liga), Troja/Ljungby (HockeyAllsvenskan -> HockeyEttan), Dinamo Bukareszt (pilka
# reczna: Liga Mistrzow / Liga Nationala), Czechy (K) w hokeju. NIE scalamy par, ktore okazaly sie roznymi klubami
# („Zaglebie Lubin W” z I ligi i „Zaglebie W” z Superligi).
SCAL_SPORTY = {('hokej', 'Zemgale'): 'HK Zemgale/Jlss', ('hokej', 'Troja/Ljungby'): 'If Troja/Ljungby',
               ('piłka ręczna', 'Din. Bucuresti'): 'Dinamo Bucuresti', ('hokej', 'Czech Republic W'): 'Czechia (W)',
               # 07.10.2026 (Raport 06.10 21:00, zdarzenia.py CONFLICT Harem Spor – Fenerbahce Koleji): TBL, do 05.2026
               # „Fenerbahce Koleji”, od 09.2026 zrodlo pisze „Fenerbahce 2” — ta sama liga, okresy rozlaczne
               ('koszykówka', 'Fenerbahce Koleji'): 'Fenerbahce 2',
               # 10.10.2026 (Raport 18:00 nr 3): „Cayirova” (TBL do 04.2026) = „Çayırova Belediyespor” (Super Ligi od 09.2026, awans)
               ('koszykówka', 'Cayirova'): 'Çayırova Belediyespor',
               # tenze raport: sponsor w nazwie — „Talenet Giants Antwerp” (BNXT do 06.2026) = „Windrose Giants Antwerp” (od 10.2026)
               ('koszykówka', 'Talenet Giants Antwerp'): 'Windrose Giants Antwerp'}


def scal_recznie(d):
    """Pary z SCAL_SPORTY (w obrebie sportu) -> jedna nazwa."""
    if not len(d): return d
    for c in ('gosp', 'gosc'):
        d[c] = [SCAL_SPORTY.get((sp, n), n) for sp, n in zip(d.sport, d[c])]
    return d


def rozwin_skroty(d):
    """NFL/MLB z GitHuba (hist_import) maja skroty druzyn ('SEA', 'LAC') — pelne nazwy jak w ofercie i w 365scores.
    05.10.2026: wspolne z dzienniki.wyniki_inne (rozliczenie nog NFL z 04.10 konczylo sie „nie dopasowano”)."""
    for liga, m in (('NFL', NFL), ('MLB', MLB)):
        i = d.liga == liga; d.loc[i, 'gosp'] = d.loc[i, 'gosp'].replace(m); d.loc[i, 'gosc'] = d.loc[i, 'gosc'].replace(m)
    return d


def load():
    cols = ['data', 'sport', 'liga', 'gosp', 'gosc', 'pg', 'pa', 'dogrywka']
    h = pd.read_csv(HIST) if os.path.exists(HIST) else pd.DataFrame(columns=cols)
    x = pd.read_csv(DB) if os.path.exists(DB) else pd.DataFrame(columns=cols)
    if len(x):  # wynik dopisany ręcznie wygrywa z historią; w samym delta — ostatni zapis wygrywa
        x = x.drop_duplicates(['data', 'sport', 'gosp', 'gosc'], keep='last')
        k = lambda z: z.data.astype(str).str[:10] + '|' + z.sport + '|' + z.gosp.astype(str) + '|' + z.gosc.astype(str)
        h = h[~k(h).isin(set(k(x)))]
    d = pd.concat([h, x], ignore_index=True); d['data'] = pd.to_datetime(d.data)
    d = scal_recznie(scal_warianty(rozwin_skroty(d)))
    return d.sort_values('data', kind='stable')


# --- dopasowanie nazw z tabel ligowych do nazw z bazy meczow (21.09.2026) ---
# Tabele (tabele_eu.csv) maja nazwy oficjalne/wikipediowe, a baza meczow nazwy skrocone z 365scores:
# "Montpellier Handball" vs "Montpellier", "Ademar Leon" vs "ABANCA Ademar Leon", "Nitra" vs "MHK Nitra".
# Bez tego seed nie przypina sie do zadnej druzyny i sila startowa z tabeli przepada.
SEED_POMIN = {'hc', 'bc', 'bm', 'sc', 'sg', 'tv', 'tsv', 'vfb', 'vfl', 'hbc', 'cb', 'kk', 'mhk', 'hk', 'ehc', 'erc',
              'ev', 'sv', 'if', 'ik', 'bk', 'fc', 'cf', 'ac', 'as', 'us', 'club', 'de', 'la', 'el', 'del',
              'handball', 'hand', 'basket', 'basketball', 'volley', 'volleyball', 'pallacanestro', 'pallavolo',
              'team', 'the', 'sk', 'hkm', 'khl', 'ks', 'mks', 'gks', 'kh'}


def _tok_seed(s):
    t = re.findall(r'[a-z0-9]+', unicodedata.normalize('NFKD', str(s).translate(_LITERY)).encode('ascii', 'ignore').decode().lower())
    return [x for x in t if x not in SEED_POMIN and len(x) > 1]


# Znacznik rezerw/mlodziezy/kobiet jako OSOBNY czlon nazwy. Liczymy je po obu stronach i blokujemy
# dopasowanie tylko wtedy, gdy kandydat ma ich WIECEJ niz zrodlo. Samo "czy kandydat zawiera znacznik"
# nie wystarczalo: "Boca Juniors" i "Young Boys" to pierwsze zespoly, a zawieraja "juniors" i "young",
# przez co ochrona sie dla nich wylaczala i "Boca Juniors" lapalo sie na "Boca Juniors Sub-20".


from nazwy import znaczniki as _znaczniki   # historia zmian (22.09 [K]/(W), 23.09 rodzaje): nazwy.py


def _rezerwa_a_nie_pierwsza(zrodlo, kandydat):
    """Blokuje "Lvi Praha" -> "Lvi Praha B" i pierwsza druzyne -> zespol kobiecy/mlodziezowy.
    Test jest SYMETRYCZNY: rozna liczba znacznikow w obie strony znaczy, ze to nie ten sam
    zespol. 22.09.2026: wersja jednostronna przepuszczala "Club Leon [K]" -> "Club Leon"
    i "Barcelona (W)" -> "Barcelona", bo znacznik byl po stronie ZRODLA, nie kandydata."""
    return _znaczniki(kandydat) != _znaczniki(zrodlo)


def dopasuj_seed(nazwa, pula):
    """pula: dict {norm(nazwa_z_bazy): nazwa_z_bazy}. Zwraca nazwe z bazy albo None.
    Dopasowuje TYLKO gdy kandydat jest jednoznaczny — przy dwoch i wiecej woli nie przypiac nic."""
    k = norm(nazwa)
    if not k: return None
    if k in pula: return pula[k]
    pula = {kb: v for kb, v in pula.items() if not _rezerwa_a_nie_pierwsza(nazwa, v)}
    if not pula: return None
    # zawieranie: krotszy ciag musi stanowic >=45% dluzszego i miec >=5 znakow,
    # inaczej "CucineLubeCivitaNOVA" zlapie sie na "Nova"
    def _zawiera(a, b):
        if len(a) < 5 or len(b) < 5: return False
        if min(len(a), len(b)) / max(len(a), len(b)) < 0.45: return False
        return a.startswith(b) or b.startswith(a) or b.endswith(a) or a.endswith(b)
    kand = {v for kb, v in pula.items() if _zawiera(k, kb)}
    if len(kand) == 1: return kand.pop()
    tn = set(_tok_seed(nazwa))
    if tn:
        eq = [v for v in pula.values() if set(_tok_seed(v)) == tn]
        if len(eq) == 1: return eq[0]
        sub = [v for v in pula.values() if _tok_seed(v) and (set(_tok_seed(v)) <= tn or tn <= set(_tok_seed(v)))]
        if len(sub) == 1: return sub[0]
    mm = difflib.get_close_matches(k, list(pula), n=2, cutoff=0.86)
    if len(mm) == 1: return pula[mm[0]]
    return None


def elo(d, sport, pre=None, info=None):
    hfa, draws = SPORT.get(sport, (40, False))
    R, N, last, draw_n, tot = {}, {}, {}, 0, 0
    S = seeds(sport); si = 0; seeded = {}
    # przypnij nazwy z tabel do nazw wystepujacych w bazie meczow tego sportu
    _pula = {}
    for _r in d[d.sport == sport].itertuples():
        for _t in (_r.gosp, _r.gosc): _pula.setdefault(norm(_t), _t)
    if _pula and S:
        _S2, _zm = [], 0
        for _dd, _t, _rt, _gp, _lg in S:
            # 05.10.2026 (Raport 18:00, usterka 3): tabela „APU Udine” (Lega A) nie przypinala sie do meczow
            # „Amici Pallacanestro Udinese” — w Elo dwa wpisy, a typowanie trafialo w wpis bez meczow (forma N 10/0).
            # Alias reczny (aliasy.csv) obowiazuje tez dla nazw z tabel, gdy cel jest w bazie meczow tego sportu.
            _a = _ALIASY_RECZNE.get(norm(_t))
            _c = _pula.get(norm(_t)) or (_a if _a and _pula.get(norm(_a)) == _a else None) or dopasuj_seed(_t, _pula)
            if _c and _c != _t: _zm += 1
            _S2.append((_dd, _c or _t, _rt, _gp, _lg))
        S = sorted(_S2)
        if info is not None: info['seed_dopasowane'] = _zm

    def apply_seeds(until):
        nonlocal si
        while si < len(S) and (until is None or S[si][0] <= until):
            dd, t, rt, gp, liga = S[si]; si += 1
            if t in last and (dd - last[t]).days > 90: R[t] = 1500 + (R[t] - 1500) * 0.67
            R[t] = rt if t not in R else (R[t] * 20 + rt * gp) / (20 + gp)
            N[t] = max(N.get(t, 0), gp); last[t] = dd; seeded[t] = liga

    for r in d[d.sport == sport].itertuples():
        apply_seeds(r.data)
        for t in (r.gosp, r.gosc):  # przerwa > 90 dni = nowy sezon → regresja 1/3 do średniej
            if t in last and (r.data - last[t]).days > 90: R[t] = 1500 + (R[t] - 1500) * 0.67
            last[t] = r.data
        a, b = R.get(r.gosp, 1500.), R.get(r.gosc, 1500.)
        if pre is not None: pre.append((a, b, N.get(r.gosp, 0), N.get(r.gosc, 0)))
        e = 1 / (1 + 10 ** ((b - a - hfa) / 400))
        # 30.09.2026 (przeglad): remis w sporcie bez remisow (82:82 w koszykowce, 0:0 w baseballu) to migawka albo mecz
        # przelozony — dotad liczony jako wygrana GOSCIA z pelnym K
        if not draws and r.pg == r.pa: continue
        reg_draw = getattr(r, 'dogrywka', 0) == 1 and draws
        s = 0.5 if (r.pg == r.pa or reg_draw) and draws else (1.0 if r.pg > r.pa else 0.0)
        margin = np.log1p(abs(r.pg - r.pa)) if r.pg != r.pa else 1
        kk = K * min(margin, 2.5) * (1.5 if N.get(r.gosp, 0) < 10 or N.get(r.gosc, 0) < 10 else 1.0)
        R[r.gosp] = a + kk * (s - e); R[r.gosc] = b - kk * (s - e)
        N[r.gosp] = N.get(r.gosp, 0) + 1; N[r.gosc] = N.get(r.gosc, 0) + 1
        if getattr(r, 'dogrywka', 0) != -1: tot += 1; draw_n += int(reg_draw or r.pg == r.pa)
    apply_seeds(None)
    if info is not None: info.update(last=last, seeded=seeded)
    pr = DRAW_PRIOR.get(sport, 0.0)
    return R, N, hfa, draws, (draw_n + 50 * pr) / (tot + 50)


@functools.lru_cache(maxsize=None)
def _tokeny(s):
    return tuple(re.findall(r'[a-z0-9]+', unicodedata.normalize('NFKD', html.unescape(str(s)).translate(_LITERY)).encode('ascii', 'ignore').decode().lower()))


# Nazwy reprezentacji: STS pisze po polsku, bazy po angielsku — i to KAZDA INACZEJ.
# Baza piłkarska (intl) uzywa 'Czech Republic', 'Turkey', 'United States';
# baza 365scores (siatkowka/koszykowka) 'Czechia', 'Turkiye', 'USA'. Dlatego wartoscia
# jest LISTA wariantow sprawdzanych po kolei przeciwko puli danego sportu — pierwszy
# obecny w puli wygrywa. Dopisanie wariantu jest bezpieczne: to test przynaleznosci
# do puli, a nie dopasowanie rozmyte, wiec nie moze wskazac innej druzyny.
_KRAJE_PL = {
    'albania': ('Albania',), 'algieria': ('Algeria',), 'andora': ('Andorra',),
    'anglia': ('England',), 'angola': ('Angola',), 'arabiasaudyjska': ('Saudi Arabia',),
    'argentyna': ('Argentina',), 'armenia': ('Armenia',), 'australia': ('Australia',),
    'austria': ('Austria',), 'azerbejdzan': ('Azerbaijan',), 'belgia': ('Belgium',),
    'bialorus': ('Belarus',), 'boliwia': ('Bolivia',),
    'bosniaihercegowina': ('Bosnia and Herzegovina', 'Bosnia & Herzegovina', 'Bosnia-Herzegovina'),
    'bosnia': ('Bosnia and Herzegovina', 'Bosnia & Herzegovina', 'Bosnia-Herzegovina'),
    'brazylia': ('Brazil',), 'bulgaria': ('Bulgaria',), 'chile': ('Chile',),
    'chiny': ('China', 'China PR'), 'chorwacja': ('Croatia',), 'cypr': ('Cyprus',),
    'czarnogora': ('Montenegro',), 'czechy': ('Czechia', 'Czech Republic'),
    'dania': ('Denmark',), 'dominikana': ('Dominican Republic',), 'dominika': ('Dominica',),   # 30.09: Dominika != Dominikana
    # 30.09 (Rozliczenie 29.09): skroty STS „Pn.”/„Pd.” — „Macedonia Pn.” nie rozliczala sie (BRAK WYNIKU)
    'macedoniapn': ('North Macedonia',), 'irlandiapn': ('Northern Ireland',),
    'koreapd': ('South Korea', 'Korea Republic'), 'koreapn': ('North Korea', 'Korea DPR'),
    'brytyjskiewyspydziewicze': ('British Virgin Islands',), 'wyspydziewiczeusa': ('United States Virgin Islands',),
    # 01.10.2026 (Raport 21:00, Kajmany - Portoryko -> „NIE ZNALEZIONO reprezentacji”): wszystkie reprezentacje meskie
    # z oferty 24-30.09 bez polskiej nazwy w tabeli — kazda jest w bazie intl (54-333 meczow)
    'kajmany': ('Cayman Islands',), 'gwadelupa': ('Guadeloupe',), 'martynika': ('Martinique',),
    'malediwy': ('Maldives',), 'seszele': ('Seychelles',), 'saintkittsinevis': ('Saint Kitts and Nevis',),
    'wyspycooka': ('Cook Islands',),
    'amerykanskiewyspydziewicze': ('United States Virgin Islands',), 'egipt': ('Egypt',),
    'ekwador': ('Ecuador',), 'estonia': ('Estonia',), 'filipiny': ('Philippines',),
    'finlandia': ('Finland',), 'francja': ('France',), 'ghana': ('Ghana',),
    'gibraltar': ('Gibraltar',), 'grecja': ('Greece',), 'gruzja': ('Georgia',),
    'hiszpania': ('Spain',), 'holandia': ('Netherlands', 'Holland'),
    'niderlandy': ('Netherlands', 'Holland'), 'indie': ('India',),
    'indonezja': ('Indonesia',), 'iran': ('Iran',),
    'irlandia': ('Republic of Ireland', 'Ireland'),
    'republikairlandii': ('Republic of Ireland', 'Ireland'),
    'irlandiapolnocna': ('Northern Ireland',), 'islandia': ('Iceland',),
    'izrael': ('Israel',), 'japonia': ('Japan',), 'kamerun': ('Cameroon',),
    'kanada': ('Canada',), 'katar': ('Qatar',), 'kazachstan': ('Kazakhstan',),
    'kenia': ('Kenya',), 'kolumbia': ('Colombia',),
    'koreapoludniowa': ('South Korea', 'Korea Republic'),
    'koreapolnocna': ('North Korea', 'Korea DPR'),
    'kosowo': ('Kosovo',), 'kostaryka': ('Costa Rica',), 'kuba': ('Cuba',),
    'liechtenstein': ('Liechtenstein',), 'litwa': ('Lithuania',), 'lotwa': ('Latvia',),
    'luksemburg': ('Luxembourg',), 'macedoniapolnocna': ('North Macedonia',),
    'malta': ('Malta',), 'maroko': ('Morocco',), 'meksyk': ('Mexico',),
    'moldawia': ('Moldova',), 'niemcy': ('Germany',), 'nigeria': ('Nigeria',),
    'norwegia': ('Norway',), 'nowazelandia': ('New Zealand',), 'panama': ('Panama',),
    'paragwaj': ('Paraguay',), 'peru': ('Peru',), 'polska': ('Poland',),
    'portoryko': ('Puerto Rico',), 'portugalia': ('Portugal',),
    'republikapoludniowejafryki': ('South Africa',), 'rpa': ('South Africa',),
    'rosja': ('Russia',), 'rumunia': ('Romania',), 'salwador': ('El Salvador',),
    'sanmarino': ('San Marino',), 'senegal': ('Senegal',), 'serbia': ('Serbia',),
    'slowacja': ('Slovakia',), 'slowenia': ('Slovenia',),
    'stanyzjednoczone': ('USA', 'United States'), 'usa': ('USA', 'United States'),
    'szkocja': ('Scotland',), 'szwajcaria': ('Switzerland',), 'szwecja': ('Sweden',),
    'tajlandia': ('Thailand',), 'tajwan': ('Chinese Taipei', 'Taiwan'),
    'tunezja': ('Tunisia',), 'turcja': ('Turkiye', 'Turkey'), 'ukraina': ('Ukraine',),
    'urugwaj': ('Uruguay',), 'walia': ('Wales',), 'wegry': ('Hungary',),
    'wenezuela': ('Venezuela',), 'wietnam': ('Vietnam',), 'wlochy': ('Italy',),
    'wyspyowcze': ('Faroe Islands',), 'wybrzezekoscisloniowej': ('Ivory Coast',),
    'zjednoczoneemiratyarabskie': ('United Arab Emirates',),
    # Poprawka 42 (24.09.2026): nazwy z oferty 24.09, ktore nie trafialy w baze
    'afganistan': ('Afghanistan',),
    'antiguaibarbuda': ('Antigua and Barbuda',),
    'bahrajn': ('Bahrain',),
    'bermudy': ('Bermuda',),
    'birma': ('Myanmar',),
    'czad': ('Chad',),
    'demokratycznarepublikakonga': ('DR Congo',),
    'drkongo': ('DR Congo',),
    'dzibuti': ('Djibouti',),
    'erytrea': ('Eritrea',),
    'etiopia': ('Ethiopia',),
    'fidzi': ('Fiji',),
    'gujana': ('Guyana',),
    'gwatemala': ('Guatemala',),
    'gwinea': ('Guinea',),
    'gwineabissau': ('Guinea-Bissau',),
    'gwinearownikowa': ('Equatorial Guinea',),
    'hongkong': ('Hong Kong',),
    'irak': ('Iraq',),
    'jamajka': ('Jamaica',),
    'jemen': ('Yemen',),
    'jordania': ('Jordan',),
    'kambodza': ('Cambodia',),
    'kirgistan': ('Kyrgyzstan',),
    'komory': ('Comoros',),
    'kongo': ('Congo',),
    'kuwejt': ('Kuwait',),
    'liban': ('Lebanon',),
    'libia': ('Libya',),
    'madagaskar': ('Madagascar',),
    'malezja': ('Malaysia',),
    'mauretania': ('Mauritania',),
    'mjanma': ('Myanmar',),
    'mozambik': ('Mozambique',),
    'nikaragua': ('Nicaragua',),
    'nowakaledonia': ('New Caledonia',),
    'palestyna': ('Palestine',),
    'papuanowagwinea': ('Papua New Guinea',),
    'republikasrodkowoafrykanska': ('Central African Republic',),
    'republikazielonegoprzyladka': ('Cape Verde',),
    'singapur': ('Singapore',),
    'sudanpoludniowy': ('South Sudan',),
    'surinam': ('Suriname',),
    'tadzykistan': ('Tajikistan',),
    'trynidaditobago': ('Trinidad and Tobago',),
    'wyspyzielonegoprzyladka': ('Cape Verde',),
}


def _kraj_pl(name, pool):
    """Angielska nazwa reprezentacji dla polskiej, wybrana sposrod wariantow obecnych w PULI.
    Zwraca None, gdy zadnego wariantu nie ma — a None jest poprawnym wynikiem."""
    k = norm(name)
    kand = _KRAJE_PL.get(k)
    if kand is None:                      # druzyna kobieca: "Polska [K]", "Niemcy (K)", "Chiny W"
        for suf in ('k', 'w', 'kobiety', 'kobiet'):
            if k.endswith(suf) and k[:-len(suf)] in _KRAJE_PL:
                baza = _KRAJE_PL[k[:-len(suf)]]
                kand = tuple(f'{b} (W)' for b in baza) + tuple(f'{b} W' for b in baza)
                break
    if not kand: return None
    for c in kand:
        if c in pool: return c
    return None

def _zaw_nazwy(a, b):
    """Czy jedna nazwa jest skrotem drugiej. Porownujemy CZLONY nazwy, nie litery.
    21.09.2026, trzecia proba — dwie poprzednie mylily druzyny:
      wersja 1 (udzial dlugosci >=45%): "Legia" wpadalo w "coLEGIAles",
      wersja 2 (prefiks/sufiks na literach): "Inter" wpadalo w "INTERnational Pacific University",
        "Magda" w "MAGDAlena Frech", "South" w "SOUTHern Connecticut State", "Basket" w "BASKETball Lowen".
    Skrot klubu ucina cale czlony z poczatku albo z konca ("MHK Nitra" -> "Nitra",
    "Montpellier Handball" -> "Montpellier"), nigdy polowe slowa. Dlatego czlony musza
    zgadzac sie w calosci i lezec na brzegu nazwy."""
    ta, tb = _tokeny(a), _tokeny(b)
    if not ta or not tb: return False
    d, k = (ta, tb) if len(ta) >= len(tb) else (tb, ta)
    if len(''.join(k)) < 4: return False        # "US", "AC", "Tre" — za malo, zeby cokolwiek rozstrzygac
    return d[:len(k)] == k or d[-len(k):] == k


# Czlony, ktorych brak NIE zmienia klubu: forma prawna / typ klubu i nazwa dyscypliny.
# "FC Barcelona" -> "Barcelona", "MHK Nitra" -> "Nitra", "Montpellier Handball" -> "Montpellier".
# CELOWO NIE MA tu: u19/u21/u23, ii, b, reserves (to INNE druzyny) ani rdzeni typu
# Real/Sporting/Dinamo/Independiente (to ONE sa wspolne dla wielu klubow).
_OGOLNE = frozenset('fc cf sc ac as ss sv fk nk sk bk hk hc mhk vk kk rk ok ks cd ca cs ud sd ec afc cfc fbc sad '
                    'club clube klub calcio futbol football fussball handball basket basketball volley volleyball '
                    'hockey sport sports de del la el the da do '
                    # Poprawka 43 (24.09.2026): dopiski STS bez znaczenia rozrozniajacego
                    # ("Lancashire County", "Colomiers Rugby", "Storhamar Ishockey", "Narvik IK", "IF Bjorkloven")
                    'county rugby ishockey ik if '
                    # 30.09.2026 (Raport 12:00, usterka 1): skroty formy prawnej/sekcji z oferty STS bez znaczenia rozrozniajacego
                    # ("BC Lietkabelis", "Besiktas JK", "BM Logrono La Rioja", "Tatabanya KC", "CB Canarias")
                    'bc kc bm cb jk '
                    # 07.10.2026 (Raport 07.10 12:00, usterka 4): „EHC Visp”, „EHC Olten” (Eishockey-Club; Flashscore: Visp, Olten)
                    'ehc'.split())


# Poprawka 54 (24.09.2026): STS podaje druzyny NCAA z przydomkiem („Coastal Carolina Chanticleers”,
# „Liberty Flames”), baza 365scores bez niego („Coastal Carolina”, „Liberty”). Przydomek to NIE czlon
# rozrozniajacy — odpada TYLKO gdy wszystkie odciete czlony stoja NA KONCU nazwy i sa na tej liscie.
_PRZYDOMKI_USA = frozenset('''49ers aggies anteaters antelopes aztecs badgers baylor bearcats bears beavers bengals big bison black blazers blue bobcats boilermakers bonnies broncos bruins buccaneers buckeyes bucs buffaloes bulldogs bulls cajuns cardinal cardinals catamounts cavaliers chanticleers chargers chippewas colonels commodores cornhuskers cougars cowboys coyotes crimson crusaders cyclones deacons demon devils dolphins dons ducks dukes eagles explorers falcons fighting flames flash flashes friars frogs gaels gamecocks gators golden gophers governors green greyhounds grizzlies hatters hawkeyes hawks heels herd highlanders hilltoppers hokies hoosiers horned hornets hoyas hurricane hurricanes huskers huskies illini irish jackets jackrabbits jaguars jayhawks keydets knights lancers leathernecks lions lobos longhorns lumberjacks matadors mavericks mean midshipmen miners minutemen mocs monarchs mountaineers mustangs niners nittany orange ospreys owls pack paladins panthers penguins phoenix pilots pirates quakers racers ragin raiders rainbow rams razorbacks rebels red redbirds redhawks retrievers roadrunners rockets runnin salukis scarlet seahawks seawolves seminoles skyhawks sooners spartans spiders stags statesmen sun sycamores tar terrapins terriers thunderbirds thundering tide tigers titans toreros tribe tritons trojans utes vandals volunteers warhawks warriors wave wildcats wolf wolfpack wolverines wolves yellow zips'''.split())


OSOBOWE = {'snooker', 'dart', 'mma', 'boks', 'tenis stołowy', 'badminton', 'żużel'}   # nazwa = imie i nazwisko osoby


def _skrot_albo_nic(name, wyn, pula, osoba=True):
    """22.09.2026, USTERKA U1 z przebiegu 21:00: "Independiente Yumbo" (Kolumbia, II liga) zostalo
    policzone jako "Independiente" (Argentyna, Avellaneda) — oczekiwane gole 2,05 : 0,84 z sily
    klubu z innego kraju. Kod wypisywal ostrzezenie i MIMO TO zwracal klub. Ostrzezenie w logu
    nie zatrzymuje modelu, wiec zamiast ostrzegac — rozstrzygamy:
      (a) odpadly wylacznie czlony ogolne (FC, MHK, Handball) — ten sam klub, zwracamy;
      (b) odpadl czlon rozrozniajacy, a zachowany rdzen maja w bazie TAKZE inne kluby — nie da sie
          ustalic, ktory to, zwracamy None;
      (c) odpadl czlon rozrozniajacy, rdzen jednoznaczny ("Chievo Verona" -> "Chievo") — zwracamy
          z ostrzezeniem. Tego przypadku NIE DA SIE odroznic od "Independiente Yumbo" po samym
          napisie (w bazie jest jedno Independiente), dlatego typuj.py sprawdza dodatkowo KRAJ ligi."""
    tn, tk = _tokeny(name), _tokeny(wyn)
    if len(tn) <= len(tk):
        # 30.09.2026 (przeglad): nazwa z oferty KROTSZA niz w bazie wracala bez kontroli („Zenit” -> „Zenit-2”,
        # „New Zealand” -> „New Zealand Breakers”, „Nigeria” -> „Nigeria Customs”). Dodatkowe czlony w bazie wolno
        # pominac tylko, gdy sa ogolne („Nitra” -> „MHK Nitra”) albo sa przydomkiem druzyny z USA („Boston” -> „Boston Celtics”).
        dod = tk[len(tn):] if tk[:len(tn)] == tn else tk[:-len(tn)] if tn and tk[-len(tn):] == tn else tuple(t for t in tk if t not in tn)
        if all(t in _OGOLNE for t in dod) or (tk[:len(tn)] == tn and all(t in _PRZYDOMKI_USA for t in dod)):
            return wyn
        if osoba and len(tn) == 1 and len(tk) == 2 and tk[1] == tn[0]:   # samo nazwisko osoby: „Littler” -> „Luke Littler”
            print(f'  UWAGA: "{name}" -> "{wyn}" (samo nazwisko, jeden kandydat w bazie)')
            return wyn
        print(f'  ODRZUCONO: "{name}" -> "{wyn}": w bazie dodatkowe czlony {" ".join(dod)} — to moze byc INNA druzyna, noga MNIEJ.')
        _KANDYDAT[str(name)] = wyn
        return None
    if tn[:len(tk)] == tk: odp = tn[len(tk):]
    elif tn[-len(tk):] == tk: odp = tn[:-len(tk)]
    else: odp = tuple(t for t in tn if t not in tk)
    if odp and all(t in _OGOLNE for t in odp): return wyn
    if odp and tn[:len(tk)] == tk and all(t in _PRZYDOMKI_USA for t in odp):
        print(f'  UWAGA: "{name}" -> "{wyn}" (pominiety przydomek druzyny: {" ".join(odp)})')
        return wyn
    inne = sorted(p for p in pula if p != wyn and len(_tokeny(p)) > len(tk)
                  and (_tokeny(p)[:len(tk)] == tk or _tokeny(p)[-len(tk):] == tk))
    if inne:
        print(f'  ODRZUCONO: "{name}" -> "{wyn}" zgubiloby czlon rozrozniajacy, a rdzen "{wyn}" maja '
              f'w bazie tez: {", ".join(inne[:4])}{" ..." if len(inne) > 4 else ""}. '
              f'Nie da sie ustalic, ktory to klub — noga MNIEJ.')
        return None
    # 23.09.2026 (recenzja): w typuj.py taki przypadek lapie kontrola KRAJU, w sporty.py jej nie ma —
    # "Independiente Yumbo" -> "Independiente" przeszloby tu z samym ostrzezeniem. Bez drugiego
    # zabezpieczenia skrot gubiacy czlon rozrozniajacy jest niedopuszczalny: noga MNIEJ.
    print(f'  ODRZUCONO: "{name}" -> "{wyn}" gubi czlon rozrozniajacy, a w tym sporcie nie ma kontroli '
          f'kraju, ktora by potwierdzila, ze to ten sam klub — noga MNIEJ.')
    _KANDYDAT[str(name)] = wyn
    return None


# 30.09.2026 (Raport 15:00): „Karpat Oulu”, „SaiPa Lappeenranta”, „Ferencvaros TC”, „Black Wings Linz”, „PAOK Saloniki”,
# „Union Neuchatel” odpadaly jako „gubi czlon” / „dodatkowe czlony”, choc to jedyne takie kluby w bazie. W sporty.py nie ma
# kontroli kraju (jak w typuj.py), ale jest inna: RYWAL. Odrzucona nazwa ma jednego kandydata (_KANDYDAT); jesli ten kandydat
# i rywal z oferty (dopasowany albo tez kandydat) grali ze soba w lidze KRAJOWEJ w ostatnich 2 latach, to jest ten sam klub
# („Independiente Yumbo” -> argentynskie Independiente nie gralo ligowo z kolumbijskim rywalem). Puchary miedzynarodowe
# nic nie potwierdzaja. Kandydaci „z kilku klubow o tym rdzeniu” nie trafiaja do _KANDYDAT — tam nadal noga MNIEJ.
_KANDYDAT = {}
_MIEDZYNAR_LIGA = re.compile(r'^(europe|world|international|asia|africa|america|south america|north america|oceania|'
                             r'concacaf|conmebol|uefa|fiba|ehf|iihf|cev)\b', re.I)


# 30.09.2026 (audyt oferty 01.10): „Torpedo Ust-Kamenogorsk” — w bazie trzy kluby Torpedo (KHL, VHL, Kazachstan), wiec
# nazwa byla nierozstrzygalna. Terminarz (Flashscore/365) zna mecz i KRAJ; nazwe szukamy wylacznie wsrod druzyn, ktore
# graly w lidze krajowej tego kraju (jak typuj._kraj_z_terminarza). Tylko wynik jednoznaczny; inaczej noga MNIEJ.
_SPORT_TERMINARZ = {'hokej': 'hockey', 'koszykówka': 'basketball', 'piłka ręczna': 'handball', 'siatkówka': 'volleyball',
                    'baseball': 'baseball', 'futsal': 'futsal'}


def _kraj_klucz(k):
    from zewn import _kraj_365
    return re.sub(r'[^a-z]', '', unicodedata.normalize('NFKD', _kraj_365(k)).encode('ascii', 'ignore').decode().lower())


def kraj_z_terminarza(d, sport, nazwy, wyniki, mt=None):
    kod = _SPORT_TERMINARZ.get(sport)
    if not kod: return wyniki
    if mt is None:
        try:
            import terminarz as _tm
            mt = _tm.znajdz(nazwy[0], nazwy[1], sport=kod) or _tm.znajdz(nazwy[0], nazwy[1], sport=kod, luzno=True)
        except Exception:
            return wyniki
    if not mt: return wyniki
    kt = _kraj_klucz(mt['kraj'])
    if not kt or kt in ('world', 'international', 'europe', 'asia', 'africa', 'america', 'southamerica', 'northamerica',
                        'oceania'):
        return wyniki
    x = d[d.sport == sport]
    x = x[x.data >= x.data.max() - pd.Timedelta(days=730)]   # jak typuj._w_kraju: zapis bez meczu od 2 lat nie jest kandydatem
    kraj = x.liga.astype(str).str.split('|').str[0].map(_kraj_klucz)
    x = x[(kraj == kt).values]
    pula = set(x.gosp) | set(x.gosc)
    if not pula: return wyniki
    nowe = list(wyniki)
    for i, (n, zt) in enumerate(((nazwy[0], mt['gosp']), (nazwy[1], mt['gosc']))):
        if nowe[i] is not None: continue
        import io, contextlib
        wyn = set()
        for q in (zt, n):
            with contextlib.redirect_stdout(io.StringIO()):
                r = resolve(q, pula, sport)
            if r: wyn.add(r)
        if len(wyn) != 1: return wyniki
        nowe[i] = next(iter(wyn))
        print(f'  UWAGA: "{n}" dopasowane w kraju meczu z terminarza ({mt["kraj"]}, {mt["turniej"]}: {mt["gosp"]} – {mt["gosc"]}) '
              f'-> {nowe[i]}.')
    return tuple(nowe)


def potwierdz_rywalem(d, sport, nazwy, wyniki, dni=730):
    kand = [w if w else _KANDYDAT.get(str(n)) for n, w in zip(nazwy, wyniki)]
    if None in kand or list(kand) == list(wyniki) or kand[0] == kand[1]: return wyniki
    x = d[(d.sport == sport) & (d.data >= d.data.max() - pd.Timedelta(days=dni))]
    x = x[(((x.gosp == kand[0]) & (x.gosc == kand[1])) | ((x.gosp == kand[1]) & (x.gosc == kand[0])))
          & ~x.liga.astype(str).str.match(_MIEDZYNAR_LIGA)]
    if not len(x): return wyniki
    for n, w, k in zip(nazwy, wyniki, kand):
        if w is None:
            print(f'  UWAGA: "{n}" -> "{k}" potwierdzone rywalem: {len(x)} mecz(e) ligowe z nim w bazie '
                  f'({x.liga.iloc[-1]}, ostatni {str(x.data.max())[:10]}) — ten sam klub.')
    return kand


# 23.09.2026 (wyd. 24): STS pisze "Panathinaikos Ateny [K]" i "Emlak Konut SK [K]", baza 365scores ma
# "Panathinaikos (W)" i "Emlak Konut (W)". Znacznik kobiet po obu stronach mial inna litere ([K] vs (W)),
# a STS dokleja polska nazwe miasta i forme prawna — zadna sciezka nie dawala trafienia.
# Porownujemy RDZEN: czlony bez form prawnych (_OGOLNE), z polska nazwa miasta PRZETLUMACZONA
# (Mediolan -> milan/milano), ze znacznikiem kobiet sprowadzonym do jednego. Dwa kroki:
#   1) rdzen rowny rdzeniowi kandydata (miasto przetlumaczone) i kandydat jeden -> trafienie;
#   2) dopiero gdy 1) nic nie dal: miasto w ogole pominiete ("Panathinaikos Ateny" -> "Panathinaikos"),
#      ale TYLKO gdy zaden inny wpis w puli nie zaczyna sie ani nie konczy tym samym rdzeniem — recenzja:
#      "Real Madryt" -> "Real Club", "Sparta Praga" -> "Sparta" (Argentyna), "Olimpia Mediolan" -> "Olimpia"
#      (Paragwaj) przy wersji, ktora miasto po prostu wycinala.
# Znacznik kobiet jest czescia rdzenia, wiec druzyna kobieca nie trafi w meska i odwrotnie.
_MIASTA_PL = {'madryt': ('madrid',), 'monachium': ('munich', 'munchen', 'muenchen'), 'wieden': ('wien', 'vienna'),
              'lizbona': ('lisbon', 'lisboa'), 'mediolan': ('milan', 'milano'), 'rzym': ('roma', 'rome'),
              'neapol': ('napoli', 'naples'), 'turyn': ('torino', 'turin'), 'ateny': ('athens', 'athina'),
              'sewilla': ('sevilla', 'seville'), 'walencja': ('valencia',), 'stambul': ('istanbul',),
              'kopenhaga': ('copenhagen', 'kobenhavn'), 'bruksela': ('brussels', 'bruxelles'),
              'belgrad': ('belgrade', 'beograd'), 'moskwa': ('moscow', 'moskva'), 'praga': ('prague', 'praha'),
              'bukareszt': ('bucharest', 'bucuresti'), 'sztokholm': ('stockholm',), 'kijow': ('kyiv', 'kiev'),
              'lwow': ('lviv', 'lvov'), 'zagrzeb': ('zagreb',), 'genua': ('genoa', 'genova'),
              'saloniki': ('thessaloniki',), 'pireus': ('piraeus', 'pireas'),
              'kowno': ('kaunas',), 'wilno': ('vilnius',), 'ryga': ('riga',)}   # Poprawka 42
_ALIASY_RECZNE = {
    # Poprawka 43 (24.09.2026) — hokej: STS dokleja miasto (kazda para sprawdzona w lidze)
    'lukkorauma': 'Lukko', 'tapparatampere': 'Tappara', 'bilitygriliberec': 'Liberec',
    'stjernenfredrikstad': 'Stjernen', 'stavangeroilers': 'Stavanger', 'hv71jonkoping': 'HV 71',
    'ehckloten': 'Kloten Flyers', 'hkzemgalellu': 'HK Zemgale/Jlss', 'jkhgksjastrzebie': 'GKS Jastrzêbie',
    # koszykowka
    'riesenludwigsburg': 'N.R. Ludwigsburg', 'mhpriesenludwigsburg': 'N.R. Ludwigsburg',
    'semelbournephoenix': 'South East Melbourne', 'southeastmelbournephoenix': 'South East Melbourne',
    'perthwildcats': 'Perth',
    # Poprawka 45 (24.09.2026): hokej — Liga Alpejska (Flashscore), PHL (365: nazwa sponsora), EHL (Flashscore)
    'stssanok': 'Ciarko PBS Bank', 'ciarkostssanok': 'Ciarko PBS Bank', 'ciarkopbsbanksanok': 'Ciarko PBS Bank',
    'hddjesenice': 'Acroni Jesenice', 'hcasiago': 'Asiago', 'dieadlerkitzbuhel': 'Kitzbuhel', 'ecdieadlerkitzbuhel': 'Kitzbuhel',
    'unterlandcavaliers': 'Unterland', 'wipptalbroncos': 'Vipiteno', 'hcgherdeina': 'Gherdeina', 'rittensport': 'Ritten',
    'hcmerano': 'Merano', 'sgcortina': 'Cortina', 'sgcortinahafro': 'Cortina', 'zellereisbaren': 'Eisbaren',
    'ringerikepanthers': 'Ringerike',
    # koszykowka — Basketligaen (365): Bears Academy Aarhus = EBAA Aarhus (eurobasket), Holbaek-Stenhus = Bc Holbaek
    'bearsacademyaarhus': 'EBAA Aarhus', 'ebcholbaekstenhus': 'Bc Holbæk', 'holbaekstenhus': 'Bc Holbæk',
    # WNBA: STS oznacza [K], w bazie druzyny WNBA sa bez znacznika (liga jest wylacznie kobieca)
    'atlantadreamk': 'Atlanta Dream', 'atlantadreamw': 'Atlanta Dream',
    'chicagoskyk': 'Chicago Sky', 'chicagoskyw': 'Chicago Sky',
    'connecticutsunk': 'Connecticut Sun', 'connecticutsunw': 'Connecticut Sun',
    'dallaswingsk': 'Dallas Wings', 'dallaswingsw': 'Dallas Wings',
    'goldenstatevalkyriesk': 'Golden State Valkyries', 'goldenstatevalkyriesw': 'Golden State Valkyries',
    'indianafeverk': 'Indiana Fever', 'indianafeverw': 'Indiana Fever',
    'lasvegasacesk': 'Las Vegas Aces', 'lasvegasacesw': 'Las Vegas Aces',
    'losangelessparksk': 'Los Angeles Sparks', 'losangelessparksw': 'Los Angeles Sparks',
    'minnesotalynxk': 'Minnesota Lynx', 'minnesotalynxw': 'Minnesota Lynx',
    'newyorklibertyk': 'New York Liberty', 'newyorklibertyw': 'New York Liberty',
    'phoenixmercuryk': 'Phoenix Mercury', 'phoenixmercuryw': 'Phoenix Mercury',
    'seattlestormk': 'Seattle Storm', 'seattlestormw': 'Seattle Storm',
    'washingtonmysticsk': 'Washington Mystics', 'washingtonmysticsw': 'Washington Mystics',
    'torontotempok': 'Toronto Tempo', 'torontotempow': 'Toronto Tempo',
    'portlandfirek': 'Portland Fire', 'portlandfirew': 'Portland Fire',
    'saskibaskonia': 'Baskonia Vitoria',
                  'olympiakospireus': 'Olympiacos', 'olympiakos': 'Olympiacos',
                  'asvellyonvilleurbanne': 'ASVEL Villeurbanne', 'ldlcasvel': 'ASVEL Villeurbanne'}
_KOBIETY = frozenset('k w women kobiety kobiet'.split())
# dlugie, ale OGOLNE rdzenie — wiele klubow na swiecie (recenzja: "Instituto", "Politechnika")
_OGOLNE_DLUGIE = frozenset('instituto politechnika universidad university universitario universitatea '
                           'uniwersytet independiente deportivo deportiva municipal internacional '
                           'nacional'.split())


def _rdzen(s, miasto=None):
    """miasto=None: nazwy miast zostaja jak sa; 'bez': polskie nazwy miast wyciete;
    krotka wariantow: polska nazwa miasta zamieniona na podany wariant."""
    t = list(_tokeny(s))
    kob = bool(t) and t[-1] in _KOBIETY
    if kob: t = t[:-1]
    out = []
    for x in t:
        if x in _OGOLNE: continue
        if x in _MIASTA_PL and miasto is not None:
            if miasto == 'bez': continue
            x = miasto.get(x, x)
        out.append(x)
    return tuple(out) + (('#kobiety',) if kob else ())


def _rdzen_rowny(name, kandydaci):
    kandydaci = list(kandydaci)
    rk = {p: _rdzen(p) for p in kandydaci}
    miasta = [x for x in _tokeny(name) if x in _MIASTA_PL]
    # krok 1: miasto przetlumaczone na kazdy z wariantow
    warianty = [None] if not miasta else [dict(zip(miasta, c)) for c in
                                          __import__('itertools').product(*[_MIASTA_PL[m] for m in miasta])]
    traf = set()
    for w_ in warianty:
        r = _rdzen(name, w_) if w_ is not None else _rdzen(name)
        if len(''.join(x for x in r if x != '#kobiety')) < 4: continue
        traf |= {p for p in kandydaci if rk[p] == r}
    if len(traf) == 1:
        wyn = next(iter(traf))
        if norm(wyn) != norm(name):
            print(f'  UWAGA: "{name}" dopasowane po rdzeniu nazwy (forma prawna/miasto/znacznik kobiet) -> "{wyn}".')
        return wyn
    if len(traf) > 1 or not miasta: return None
    # krok 2: miasto pominiete, tylko przy jednoznacznym rdzeniu
    r = _rdzen(name, 'bez')
    baza_ = [x for x in r if x != '#kobiety']
    # rdzen po wycieciu miasta musi byc SAM W SOBIE rozpoznawalny: co najmniej dwa czlony albo jeden
    # dlugi ("panathinaikos", "olympiakos"). "Sparta", "Olimpia", "Real" to nazwy wielu klubow na
    # swiecie, a sporty.py nie ma kontroli kraju — pula moze nie miec wlasciwego klubu wcale.
    if not (len(baza_) >= 2 or (len(baza_) == 1 and len(baza_[0]) >= 9 and baza_[0] not in _OGOLNE_DLUGIE)):
        return None
    traf = [p for p in kandydaci if rk[p] == r]
    if len(traf) != 1: return None
    baza = tuple(x for x in r if x != '#kobiety')
    kob = '#kobiety' in r
    def _b(p): return tuple(x for x in rk[p] if x != '#kobiety')
    # inne druzyny TEJ SAMEJ kategorii (meskie/kobiece), ktorych rdzen zaczyna sie albo konczy tym rdzeniem
    inne = [p for p in kandydaci if p != traf[0] and ('#kobiety' in rk[p]) == kob and len(_b(p)) > len(baza)
            and (_b(p)[:len(baza)] == baza or _b(p)[-len(baza):] == baza)]
    if inne:
        print(f'  ODRZUCONO: "{name}" -> "{traf[0]}" po pominieciu nazwy miasta, ale rdzen maja tez: '
              f'{", ".join(sorted(inne)[:4])} — noga MNIEJ.')
        return None
    print(f'  UWAGA: "{name}" dopasowane po pominieciu polskiej nazwy miasta -> "{traf[0]}".')
    return traf[0]


def _osoba_rowna(a, b):
    """Dwa czlony nazwy osoby: te same w dowolnej kolejnosci albo nazwisko + inicjal imienia ("stolfa","j").
    29.09.2026: 3-4 czlony — imie przeniesione z konca na poczatek („van Veen Gian” = „Gian van Veen”)."""
    if not all(a) or not all(b): return False
    if len(a) == len(b) >= 3:
        return (a[:-1] == b[1:] and a[-1] == b[0]) or (b[:-1] == a[1:] and b[-1] == a[0])
    if len(b) != 2 or len(a) != 2: return False
    for x, y in ((a, b), (a, b[::-1])):
        if x == y: return True
        if x[0] == y[0] and len(x[0]) >= 3 and (len(x[1]) == 1 and y[1].startswith(x[1]) or len(y[1]) == 1 and x[1].startswith(y[1])):
            return True
    return False


_KRAJE_EN = None


def _kraj(s):
    """Czy nazwa (bez znacznika kobiet) to nazwa kraju — polska albo angielska z _KRAJE_PL."""
    global _KRAJE_EN
    if _KRAJE_EN is None:
        _KRAJE_EN = set(_KRAJE_PL) | {norm(x) for v in _KRAJE_PL.values() for x in v}
    t = [x for x in _tokeny(s) if x not in _KOBIETY]
    return bool(t) and norm(' '.join(t)) in _KRAJE_EN


def resolve(name, pool, sport=None):
    """30.09.2026 (przeglad): reprezentacja nie moze trafic w klub — „Qatar” -> „Qatar SC”, „Cameroon” -> „Cameron”,
    „El Salvador (W)” -> „Salvador Basketball (W)”, „Hong Kong (W)” -> „Hong Kong VC (W)” (sciezki rdzenia i rozmyta).
    Gdy nazwa z oferty to kraj, wynik tez musi byc krajem — inaczej None (noga MNIEJ)."""
    r = _resolve(name, pool, sport)
    if r and _kraj(name) and not _kraj(r):
        print(f'  ODRZUCONO: "{name}" to reprezentacja, a "{r}" nie — noga MNIEJ.')
        return None
    return r


def _resolve(name, pool, sport=None):
    """Zwraca nazwe z bazy albo None. None JEST POPRAWNYM WYNIKIEM — wolacz ma sie wtedy zatrzymac.
    21.09.2026: naprawiona ta sama usterka, ktora wykryto w typuj.py. Nazwa zapisana cyrylica
    (np. "Pyx") po norm() daje PUSTY klucz, a pusty ciag zawiera sie w kazdym napisie, wiec
    warunek "kk in k_" byl dla niej zawsze prawdziwy. Taka nazwa stawala sie uniwersalnym jokerem:
    kazda nieznana druzyna z oferty dostawala jej Elo i pelna, wiarygodnie wygladajaca tabele P.
    Dawny warunek "k_ and (...)" chronil tylko przed pustym ZRODLEM, nie przed pustym wpisem w PULI.
    Sprawdzone na 7000 nazw: po wstrzykknieciu jednej nazwy cyrylica 5 z 6 nieznanych nazw
    dostawalo dopasowanie. Dlatego ponizej odrzucamy z puli wszystkie klucze puste."""
    k_ = norm(name)
    if not k_: return None
    pool = {p for p in pool if isinstance(p, str)}   # recenzja: NaN w puli rugby wywracal sorted()
    # Poprawka 42 (24.09.2026): nazwy sponsorskie / inna pisownia — test przynaleznosci do puli
    _al = _ALIASY_RECZNE.get(k_)
    if _al and _al in pool: return _al
    for _al in _ALIASY_WIELE.get(k_, ()):   # 03.10.2026: inny cel tej samej nazwy w innym sporcie
        if _al in pool: return _al
    _kr = _kraj_pl(name, pool)
    if _kr: return _kr
    # sorted(): pool to zbior, a kolejnosc iteracji zbioru zalezy od losowego ziarna
    # hasha w danym procesie. Bez tego przy dwoch nazwach o tym samym kluczu wynik
    # bywal RAZ jeden, RAZ drugi — ta sama nazwa z oferty dawala rozne druzyny.
    by = {norm(p): p for p in sorted(pool) if norm(p) and not _rezerwa_a_nie_pierwsza(name, p)}
    # dwie ROZNE nazwy moga uproscic sie do tego samego klucza ("Andreeva" i "Andreev A.",
    # "Rangers" i "Ranger's") — slownik zostawia wtedy jedna z nich po cichu. Ostrzegamy.
    _kol = {}
    for _p in sorted(pool):
        _k = norm(_p)
        if _k: _kol.setdefault(_k, set()).add(_p)
    if k_ in _kol and len(_kol[k_]) > 1:
        print(f'  UWAGA: "{name}" pasuje do {len(_kol[k_])} roznych wpisow w bazie '
              f'({", ".join(sorted(_kol[k_]))}) — sprawdz, ktory to.')
    if k_ in by: return by[k_]
    # 29.09.2026 (po dokladnym dopasowaniu): polskie nazwy miast („Hapoel Tel Awiw”, „Hapoel Beer Szewa”) — lista w nazwy.py
    from nazwy import egzonim
    _alt = egzonim(name, norm)
    if _alt != str(name):
        r = resolve(_alt, pool)
        if r:
            print(f'  UWAGA: "{name}" dopasowane po zamianie polskiej nazwy miasta -> "{_alt}" -> {r}.')
            return r
    # 29.09.2026 (Liga Pro): scores24 pisze gracza "Jakub Stolfa", STS "Stolfa Jakub" albo "Stolfa J." —
    # dwuczlonowe nazwy osob porownujemy tez w odwrotnej kolejnosci i z inicjalem imienia; tylko jeden kandydat.
    # 29.09.2026: apostrof nie dzieli nazwiska („O'Connor William” to 2 czlony, nie 3) i 3-4 czlony („van Veen Gian”)
    # 30.09.2026 (przeglad): cyfry zostaja czlonami — „CSKA-2 Moscow” nie jest „CSKA Moscow”
    _czl = lambda s: [norm(x) for x in re.findall(r'[^\W_]+', re.sub(r"['’ʼ`´]", '', html.unescape(str(s))).translate(_LITERY))]
    _n2 = _czl(name)
    if 2 <= len(_n2) <= 4:
        kand = sorted({p for p in by.values() if _osoba_rowna(_n2, _czl(p))})
        if len(kand) == 1: return kand[0]
        if len(kand) > 1:
            print(f'  ODRZUCONO: "{name}" pasuje do {len(kand)} graczy ({", ".join(kand)}) — noga MNIEJ')
            return None
    # Poprawka 51 (24.09.2026): rok zalozenia w nazwie ("TVB Stuttgart" w STS, "TVB 1898 Stuttgart" w bazie).
    # Rok wolno pominac TYLKO gdy rdzen bez roku ma >= 2 czlony (chroni "Metalist 1925" != "Metalist",
    # Poprawka 33, oraz "1860 Munich" != "Munich") i gdy pasuje DOKLADNIE jeden kandydat.
    _rok = lambda s: re.sub(r'\b(18|19|20)\d\d\b', ' ', str(s))
    _dwa = lambda s: len(re.findall(r'[A-Za-z0-9\u00C0-\u024F]+', _rok(s))) >= 2
    kr_ = norm(_rok(name))
    if kr_ and _dwa(name):
        kand = sorted({p for p in by.values() if re.search(r'\b(18|19|20)\d\d\b', p) and _dwa(p) and norm(_rok(p)) == kr_}
                      | ({by[kr_]} if kr_ != k_ and kr_ in by else set()))
        if len(kand) == 1:
            print(f'  UWAGA: "{name}" dopasowane po pominieciu roku zalozenia w nazwie -> "{kand[0]}"')
            return kand[0]
        if len(kand) > 1:
            print(f'  ODRZUCONO: "{name}" po pominieciu roku pasuje do {len(kand)} druzyn ({", ".join(kand)}) — noga MNIEJ')
            return None
    r = _rdzen_rowny(name, by.values())
    if r: return r
    # 29.09.2026: Wikidata PRZED dopasowaniem po zawieraniu — „Kouvot Kouvola” odpadalo tam jako „gubi czlon”,
    # a Wikidata potwierdza, ze to ten sam klub co „Kouvot”
    w = _wikidata(name, by.values(), sport) if sport else None
    if w:
        print(f'  UWAGA: "{name}" dopasowane przez Wikidata (ten sam klub, inna nazwa) -> "{w}"')
        return w
    c = [p for p in by.values() if _zaw_nazwy(name, p)]
    if c:
        if len(c) == 1:
            wyn = c[0]
        else:   # "Chievo Verona" zawiera i "Chievo", i "Verona" — pierwszy czlon to niemal zawsze wlasciwy klub
            pref = [p for p in c if k_.startswith(norm(p)) or norm(p).startswith(k_)]
            if len(pref) == 1: wyn = pref[0]
            else:
                # 29.09.2026: wczesniej wybor NAJDLUZSZEGO / najblizszego dlugoscia kandydata — zgadywanie.
                # Dart „Price” -> „Sam Price” (w puli Gerwyn, Lewis, Kane...), snooker „Higgins” -> „Alex
                # Higgins” (zm. 2010), „Wilson” -> „Erik Wilson”. Kilku kandydatow = noga MNIEJ.
                print(f'  ODRZUCONO: "{name}" pasuje do {len(c)} wpisow ({", ".join(sorted(c)[:5])}) — '
                      f'nie zgadujemy, noga MNIEJ.')
                return None
        return _skrot_albo_nic(name, wyn, by.values(), osoba=sport is None or sport in OSOBOWE)
    # prog 0.7 byl za luzny i milczacy; 0.80 jak w typuj.py, z ostrzezeniem dla czlowieka
    # rozmyte tylko dla dluzszych nazw i z wysokim progiem (0,87 zamiast 0,80:
    # przy 0,80 "Argentinos"->"Argentino MM", "Champions"->"Campion", "Karlstad"->"Harstad") — przy 3-5 znakach prog 0,80 osiaga sie trywialnie
    # i dawal "Nart"->"Lenart", "Amal"->"Samail", "Pro"->"Paro", "Cuba"->"Cuiaba"
    m = difflib.get_close_matches(k_, list(by), n=1, cutoff=0.90) if len(k_) >= 8 else []
    # dodatkowo pierwsze trzy znaki musza sie zgadzac: przy samym progu 0,90
    # przechodzilo jeszcze "Champions"->"Campion" i "Academico"->"Academica" (dwa rozne kluby).
    # Brak dopasowania to noga MNIEJ na kuponie, pomylona druzyna to kupon przegrany —
    # ta asymetria kaze wybrac ostroznosc.
    # 30.09.2026 (przeglad): i dlugosc rozna najwyzej o 1 znak (literowka, transliteracja „Moskva”/„Moskwa”) —
    # „Club Italiano (W)” -> „Club Italia (W)” i „Cameroon” -> „Cameron” to inne druzyny, nie literowki
    m = [x for x in m if x[:3] == k_[:3] and abs(len(x) - len(k_)) <= 1]
    if m:
        print(f'  UWAGA: "{name}" dopasowane ROZMYTO do "{by[m[0]]}" — upewnij sie, ze to ta sama druzyna.')
        return by[m[0]]
    return None


WIKIDATA_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wikidata_kluby.csv.gz')


@functools.lru_cache(maxsize=1)
def _wikidata_indeks():
    """wikidata_kluby.csv.gz (qid, sport, nazwy „|”): etykiety i aliasy klubow z Wikidata (CC0), pobrane 29.09.2026
    skryptem Termux (hokej, pilka reczna, koszykowka, siatkowka). Zwraca (klucz->qid, qid->klucze, czlon->qid) na sport."""
    from collections import defaultdict
    klucz, nazwy, czlon = defaultdict(lambda: defaultdict(set)), {}, defaultdict(lambda: defaultdict(set))
    if not os.path.exists(WIKIDATA_CSV): return klucz, nazwy, czlon
    w = pd.read_csv(WIKIDATA_CSV, dtype=str, keep_default_na=False)
    for q, sp, ns in zip(w.qid, w.sport, w.nazwy):
        surowe = [x for x in ns.split('|') if x]
        nazwy[(sp, q)] = {norm(x) for x in surowe} - {''}
        for k in nazwy[(sp, q)]: klucz[sp][k].add(q)
        for x in surowe:
            for t in _tokeny(x): czlon[sp][t].add(q)
    return klucz, nazwy, czlon


def _wikidata(name, pula, sport):
    """29.09.2026: ten sam klub pod inna nazwa wg Wikidata („Langnau Tigers” = „SCL Tigers”, „Kouvot Kouvola” = „Kouvot”).
    Tylko gdy: nazwa z oferty jest nazwa DOKLADNIE jednego klubu Wikidata tego sportu; z jego nazw w puli jest
    dokladnie jedna; ta nazwa z puli nie jest nazwa innego klubu Wikidata i nie zawiera sie w nazwie innego
    klubu (samo „Metallurg” to i Nowokuznieck, i Magnitogorsk). Druzyny kobiet/rezerwy/mlodziezowe — pomijane."""
    if _znaczniki(name): return None
    klucz, nazwy, czlon = _wikidata_indeks()
    it = klucz.get(sport, {}).get(norm(name), set())
    if len(it) != 1: return None
    q = next(iter(it)); N = nazwy[(sport, q)]
    traf = sorted({p for p in pula if isinstance(p, str) and not _znaczniki(p) and norm(p) in N})
    if len({norm(p) for p in traf}) != 1: return None
    p = traf[0]
    if klucz[sport].get(norm(p), set()) != {q}: return None
    tp = _tokeny(p)
    if not tp or set.intersection(*[czlon[sport].get(t, set()) for t in tp]) - {q}: return None
    return p


# 29.09.2026 (backtest walk-forward 09.2025-09.2026): kalibracja hokeja „z NHL” zanizala P w ligach europejskich
# o ok. 5 pp (P 70-75% -> trafnosc 81%), a w NHL zawyzala o 3 pp. Osobna tabela dla meczow bez druzyny z NHL
# (OOS, 3 podzialy czasu: Brier 0,2227 -> 0,2181, logloss 0,637 -> 0,627). NHL zostaje przy tabeli dotychczasowej.
KAL_POZA_NHL = 'hokej_poza_nhl'
OD_POZA_NHL = '2025-09-01'   # wczesniej w bazie praktycznie tylko NHL


def poza_nhl(ligi):
    """Czy zadna z lig druzyn (zbior nazw lig) nie jest NHL — wtedy hokej kalibrujemy tabela „poza NHL”."""
    return bool(ligi) and not any(re.search(r'\bNHL\b', str(x)) for x in ligi)


def calibrate(sport, p, klucz=None):
    """Najpierw własne rozliczone prognozy (n≥150), potem backtest historyczny (dotyczy P faworyta/zwycięzcy, bez remisu).
    klucz: osobna tabela w backteście historycznym (np. 'hokej_poza_nhl'); brak jej w pliku = tabela sportu."""
    # 30.09.2026 (przeglad): tabela WLASNYCH prognoz (CAL) mierzy logowane P (juz skalibrowane, P do kuponu) — stosowanie
    # jej do surowego Elo kalibrowalo dwa razy; teraz idzie osobno, na koncu (kal_wlasna), a tu tylko backtest historyczny.
    for path, lab in ((CALH, 'backtest historyczny'),):
        if not os.path.exists(path): continue
        c = pd.read_csv(path)
        if klucz and path == CALH and (c.sport == klucz).any(): c, lab = c[c.sport == klucz], f'{lab}, {klucz}'
        else: c = c[c.sport == sport]
        if c.n.sum() < 150: continue
        q = max(p, 1 - p); pc = float(np.interp(q, c.p_model, c.p_kalibr))
        return (pc if p >= 0.5 else 1 - pc), f'skalibrowane ({lab}, n={int(c.n.sum())})'
    return p, 'BRAK KALIBRACJI dla tego sportu — P traktuj jak „szacunek” (max 1 na kupon), dopóki sporty.py rozlicz nie zbierze ≥150 prognoz'


def rynki_60min(ec, pdraw):
    """P wygranej 1 i 2 w czasie regulaminowym przy P meczu z dogrywka `ec` i P remisu po 60 min `pdraw`.
    Mniejsza z dwoch wersji (dogrywka wygrywana z P = ec albo 50/50) — nigdy nie zawyza zadnej strony."""
    return (max(0.0, min(ec * (1 - pdraw), ec - pdraw / 2)), max(0.0, min((1 - ec) * (1 - pdraw), (1 - ec) - pdraw / 2)))


def kal_wlasna(sport, p):
    """Korekta z wlasnych rozliczonych prognoz (sporty_kalibracja.csv, rynki 1/2, n >= 150) na KONCOWYM P faworyta."""
    if not os.path.exists(CAL): return p, ''
    c = pd.read_csv(CAL); c = c[c.sport == sport]
    if c.n.sum() < 150: return p, ''
    q = max(p, 1 - p); pc = float(np.interp(q, c.p_model, c.p_kalibr))
    return (pc if p >= 0.5 else 1 - pc), f'; korekta z wlasnych prognoz (n={int(c.n.sum())})'


PARAM = os.path.join(HERE, 'sporty_param.json')   # v5n: model marży punktowej + zespół z Elo (sporty_bt.py)


def p_gospodarza(d, sport, R, L_, hfa, draws, h, g, neutral=False, dzien=None, pamiec=None):
    """P wygranej gospodarza tak, jak liczy `sporty.py typuj` (Elo z regresja po przerwie > 90 dni, kalibracja historyczna
    — dla hokeja poza NHL osobna — zespol v5n z marza punktowa i Plattem, korekta z wlasnych prognoz).
    30.09.2026: wyjete z main(), zeby test_ostatnie.py oceniał ten sam model, ktory typuje. Zwraca (P, notka, P_Elo, linie).
    R nie jest zmieniane (regresja liczona na kopii dwoch ocen). pamiec: slownik na tabele marzy tego samego d
    (test_ostatnie.py liczy wiele meczow jednego dnia — marza() to ~1 s na wywolanie)."""
    hf = 0 if neutral else hfa
    dzien = pd.Timestamp.today().normalize() if dzien is None else dzien
    Rt = {}
    for t in (h, g):  # ostatnie dane > 90 dni temu = nowy sezon → regresja 1/3 do średniej (jak w pętli Elo)
        Rt[t] = R.get(t, 1500)
        if t in R and t in L_ and (dzien - L_[t]).days > 90: Rt[t] = 1500 + (R[t] - 1500) * 0.67
    e = 1 / (1 + 10 ** ((Rt[g] - Rt[h] - hf) / 400))
    _, Lh0, Lg0 = wspolna_skala(d, sport, h, g)
    ec, note = calibrate(sport, e, KAL_POZA_NHL if sport == 'hokej' and poza_nhl(Lh0 | Lg0) else None)
    linie = []
    prm = (__import__('json').load(open(PARAM)) if os.path.exists(PARAM) else {}).get(sport)
    if prm and not draws:
        from scipy.stats import norm as _nd
        M = pamiec.get('marza') if pamiec is not None else None
        if M is None:
            M = marza(d, sport, prm)
            if pamiec is not None: pamiec['marza'] = M
        pm_ = M.get(h, 0.) - M.get(g, 0.) + (0 if neutral else prm['hfa'])
        p_m = float(_nd.cdf(pm_ / prm['sd'])); lg_ = lambda p: np.log(min(max(p, 1e-6), 1 - 1e-6) / (1 - min(max(p, 1e-6), 1 - 1e-6)))
        z = prm['w_elo'] * lg_(e) + (1 - prm['w_elo']) * lg_(p_m); z = prm['platt'][0] * z + prm['platt'][1]
        ec = float(1 / (1 + np.exp(-z)))
        linie.append(f'  v5n: przewidywana różnica punktów {pm_:+.1f} (odch. std {prm["sd"]:.1f}); P Elo {e:.1%}, P marży {p_m:.1%}')
        note = (f'v5n: zespół Elo + marża punktowa, kalibracja Platta (test od {prm["test_od"]}: logloss '
                f'{prm["logloss_obecny"]:.4f} → {prm["logloss_nowy"]:.4f})')
    ec, _kw = kal_wlasna(sport, ec); note += _kw
    return ec, note, e, linie


def marza(d, sport, k):
    """Rating w punktach (oczekiwana różnica punktów), aktualizowany po każdym meczu; nowy sezon (>90 dni) → ściągnięcie o 25%."""
    R, last = {}, {}
    x = d[(d.sport == sport)].dropna(subset=['pg', 'pa'])
    for r in x.itertuples():
        for t in (r.gosp, r.gosc):
            if t in last and (r.data - last[t]).days > 90: R[t] = R[t] * 0.75
            last[t] = r.data
        a_, b_ = R.get(r.gosp, 0.), R.get(r.gosc, 0.)
        err = float(np.clip((r.pg - r.pa) - (a_ - b_ + k['hfa']), -30, 30))
        R[r.gosp] = a_ + k['k'] * err; R[r.gosc] = b_ - k['k'] * err
    today = pd.Timestamp.today().normalize()
    for t in list(R):
        if (today - last[t]).days > 90: R[t] *= 0.75
    return R


def backtest(d, sport, od='2015-01-01', maska=None, klucz=None, do=None):
    """maska: funkcja (ramka meczow sportu) -> bool, np. mecze bez NHL; klucz: nazwa tabeli w pliku (domyslnie sport)."""
    pre = []; hfa = elo(d, sport, pre)[2]
    t = d[d.sport == sport].assign(ra=[x[0] for x in pre], rb=[x[1] for x in pre], na=[x[2] for x in pre], nb=[x[3] for x in pre])
    t = t[(t.data >= od) & (t.na >= 20) & (t.nb >= 20) & (t.pg != t.pa)]
    if do is not None: t = t[t.data < do]
    if maska is not None: t = t[maska(t)]
    sport = klucz or sport
    if len(t) < 300: return None
    e = 1 / (1 + 10 ** ((t.rb - t.ra - hfa) / 400)); win = (t.pg > t.pa).astype(float)
    pf = np.maximum(e, 1 - e); hit = np.where(e >= 0.5, win, 1 - win)
    c = pd.DataFrame({'p': pf, 'h': hit}).sort_values('p'); q = np.array_split(np.arange(len(c)), 12)
    cal = pd.DataFrame([(sport, c.p.values[i].mean(), c.h.values[i].mean(), len(i)) for i in q], columns=['sport', 'p_model', 'p_kalibr', 'n'])
    from kalib import pav
    cal['p_kalibr'] = pav(cal.p_kalibr.values, cal.n.values)   # 30.09.2026: PAV zamiast biezacego maksimum
    home = win.mean()
    print(f'{sport}: test {len(t)} m. od {od}, trafność faworyta {hit.mean():.1%}, Brier {((e - win) ** 2).mean():.4f}, gospodarz wygrywa {home:.1%}')
    print(cal[['p_model', 'p_kalibr', 'n']].to_string(index=False, float_format=lambda x: f'{x:.3f}'))
    return cal

# ---------------------------------------------------------------------------------------------
# Poprawka 51 (24.09.2026) — wymog uzytkownika: KAZDA noga musi miec drugie, zgodne zrodlo.
# Dla hokeja (SHL, DEL, NL, Liiga, Liga Alpejska...), pilki recznej i innych sportow bez arkusza
# statystyki_<sport> drugim zrodlem jest FORMA z 10 ostatnich meczow obu druzyn w tej bazie —
# czestosc zwyciestw liczona wprost z wynikow, bez Elo. Gdy liga JEST w arkuszu, noga musi byc
# zgodna ROWNIEZ z sezon.py (oba zrodla).
DZ_PROG, DZ_MIN_MECZOW, DZ_OKNO = 0.10, 6, 10


def forma_z_innej_ligi(d, sport, t, okno):
    """(stara, nowa, ile_poza_stara) gdy druzyna zmienila lige, a okno formy jest wciaz zdominowane przez STARA
    lige — mniej niz DZ_MIN_MECZOW meczow poza nia. Inaczej None.

    03.10.2026 (Raport 21:00 KOREKTA 1, Leyma Coruna - Bilbao Basket): forma z `tail(DZ_OKNO)` bierze ostatnie
    mecze BEZ WZGLEDU NA LIGE. Leyma Coruna awansowala z 1ª FEB do ACB i ma w bazie 38 meczow 1ª FEB wobec
    jednego w ACB (26.09 Barcelona 119:101). Model dawal jej 60,6%, bo Elo zbudowala w drugiej lidze; „forma”
    8/10 wygranych to te same mecze drugiej ligi, wiec werdykt ZGODNE powstawal automatycznie i niczego nie
    potwierdzal. Rynek wycenial Corune na 46,7% (LVBET 1,96/1,72), H2H z Bilbao 0-6 — model nie zna zadnego
    z tych szesciu meczow, bo nigdy nie grali w tej samej lidze.

    To NIE jest bramka kalibracyjna (ta dla hokeja to ZMIANA_LIGI_SPORTY/P124 i zostaje bez zmian — pomiar
    03.10 na koszykowce nie dal istotnosci: awans przy P >= 55% blad +19,3 pp, ale n=18, p=0,12). To bramka
    DOWODOWA: A9 wymaga zrodla NIEZALEZNEGO, a forma z innych rozgrywek nie mowi nic o tym meczu — ten sam
    argument, ktorym P130.4 zamknelo forme przestarzala w typuj.py. Bramka tylko ODRZUCA (P130.7) i zwalnia
    sama, gdy druzyna rozegra DZ_MIN_MECZOW meczow poza stara liga."""
    if 'liga' not in getattr(d, 'columns', ()) or 'liga' not in getattr(okno, 'columns', ()):
        return None                                      # bez kolumny ligi nie ma na czym oprzec wnioskowania
    z = zmiana_ligi(d, sport, t)
    if not z: return None
    stara, nowa, _ = z
    poza = int((okno.liga.astype(str) != stara).sum())   # puchary i nowa liga = dowod o obecnym poziomie
    return None if poza >= DZ_MIN_MECZOW else (stara, nowa, poza)


def drugie_zrodlo(d, sport, h, g, p_h):
    """p_h = P modelu, ze wygra PIERWSZA druzyna (h) — przy hokeju „z dogrywka”."""
    x = d[d.sport == sport]
    def forma(t):
        m = x[(x.gosp == t) | (x.gosc == t)].tail(DZ_OKNO)
        w = int(((m.gosp == t) & (m.pg > m.pa)).sum() + ((m.gosc == t) & (m.pa > m.pg)).sum())
        return w, len(m), m
    (wh, nh, mh), (wg, ng, mg) = forma(h), forma(g)
    print(f'\nDRUGIE ZRODLO — forma z ostatnich meczow (N {nh}/{ng}), niezalezna od modelu:')
    if min(nh, ng) < DZ_MIN_MECZOW:
        print(f'  BRAK DRUGIEGO ZRODLA (mniej niz {DZ_MIN_MECZOW} meczow jednej z druzyn) — ZADNA noga z tego meczu NIE idzie na kupon.')
        return None
    for t, okno in ((h, mh), (g, mg)):
        zi = forma_z_innej_ligi(d, sport, t, okno)
        if zi:
            stara, nowa, poza = zi
            print(f'  BRAK DRUGIEGO ZRODLA: {t} zmienil lige ({stara} -> {nowa}), a w {DZ_OKNO} ostatnich meczach ma '
                  f'tylko {poza} poza "{stara}" — forma opisuje INNE rozgrywki, wiec nie jest zrodlem niezaleznym '
                  f'dla tego meczu (A9 + A1c). ZADNA noga z tego meczu NIE idzie na kupon, takze papierowy.')
            return None
    rh, rg = (wh + 1) / (nh + 2), (wg + 1) / (ng + 2)
    pf_h = rh * (1 - rg) / (rh * (1 - rg) + rg * (1 - rh))   # log5 (Bill James): P(h > g) z odsetkow zwyciestw
    fm, pm = (h, p_h) if p_h >= 0.5 else (g, 1 - p_h)
    ff, pf = (h, pf_h) if pf_h >= 0.5 else (g, 1 - pf_h)
    pf_tego = pf_h if fm == h else 1 - pf_h
    print(f'  bilans: {h} {wh}/{nh} wygranych, {g} {wg}/{ng}')
    print(f'  FAWORYT WG MODELU: {fm} {pm:.1%}   |   FAWORYT WG FORMY: {ff} {pf:.1%}')
    if fm != ff:
        print('  ROZNI FAWORYCI → NIE NA KUPON')
        return None
    if abs(pm - pf_tego) > DZ_PROG:
        print(f'  ROZBIEZNE ({(pf_tego - pm) * 100:+.0f} pp) → NIE NA KUPON')
        return None
    # 29.09.2026 (Poprawka 58, docs/BACKTEST_P48.md): zgodnosc obowiazkowa, P do kuponu = P modelu. Backtest
    # 3119 nog (dart, LoL, koszykowka, rugby, snooker; P >= 70%, 01-09.2026): min(P) 74,6% przy trafnosci 78,7%
    # (P modelu 76,7%), gorszy Brier i log loss; odrzucone przez bramke trafialy 79,2% — nie gorzej.
    print(f'  ZGODNE → P do kuponu {pm:.1%} ({fm}; P modelu, Poprawka 58)')
    print('  Zasada (Poprawka 51): gdy liga jest tez w arkuszu statystyk, noga musi byc zgodna rowniez z sezon.py.')
    return pm


# 29.09.2026 (Poprawka 60): ligi, w ktorych backtest nie znalazl przewagi modelu — WERDYKT zawsze NIE NA KUPON.
# Liga Pro (CZ), walk-forward Elo na 4912 meczach 04-29.09 (2156 ocenionych, obaj gracze >= 15 meczow):
# Brier 0,257 przy 0,250 dla rzutu moneta; faworyci P 70-80% wygrali 38% (n=65), P 60-70% — 54% (n=556).
LIGI_BEZ_PRZEWAGI = {'Liga Pro': 'Liga Pro — backtest 29.09: model bez przewagi (Brier 0,257 > 0,25)',
                     'Setka Cup': 'Setka Cup — nowe zrodlo 03.10 (scores24), bez testu wstecznego'}


# 02.10.2026 (Raport 12:00/18:00: hokej DEL/DEL2, P modelu o 16-49 pp nad rynkiem): druzyna po AWANSIE albo SPADKU
# niesie Elo z innej ligi (Krefeld: dominowal w DEL2, w DEL model 76% przy rynku 47%; Dresdner Eislowen: dol DEL,
# w DEL2 model widzi slabeusza, rynek faworyta). Sezon 2026/27 do 30.09, mecze ligowe, obie druzyny >= 10 meczow:
# hokej — mecze z druzyna po zmianie ligi: faworyt modelu wygral 47,4% przy P 67,6% (n=19), pozostale 61,1% przy
# P 63,9% (n=601). W koszykowce (n=108: 66,7% przy 70,1%) i siatkowce (n=36: 77,8% przy 69,9%) efektu brak —
# dlatego tylko hokej. Do ZMIANA_LIGI_MIN meczow w nowej lidze noga NIE idzie na kupon (takze papierowy).
ZMIANA_LIGI_SPORTY = ('hokej',)
ZMIANA_LIGI_MIN = 15
_PUCHAR = re.compile(r'cup|puchar|pokal|coppa|copa|coupe|champions|euro|friendl|super|trophy|playoff|qualif|nations|'
                     r'world|olymp', re.I)


def zmiana_ligi(d, sport, t, start=None):
    """(liga poprzedniego sezonu, liga tego sezonu, mecze w nowej) gdy druzyna gra w tym sezonie (od START_SEZONU)
    w innej lidze niz w poprzednim (>= 10 meczow ligowych) i ma w nowej mniej niz ZMIANA_LIGI_MIN meczow; inaczej None.
    Puchary, CHL, sparingi i play-offy nie sa liga."""
    start = pd.Timestamp(start or START_SEZONU)
    x = d[(d.sport == sport) & ((d.gosp == t) | (d.gosc == t))]
    x = x[~x.liga.astype(str).str.contains(_PUCHAR)]
    dt_ = pd.to_datetime(x.data)
    teraz = x[dt_ >= start].liga.value_counts()
    przed = x[(dt_ >= start - pd.DateOffset(years=1)) & (dt_ < start)].liga.value_counts()
    if teraz.empty or przed.empty or przed.iloc[0] < 10: return None
    stara, nowa = przed.index[0], teraz.index[0]
    if stara == nowa or teraz.iloc[0] >= ZMIANA_LIGI_MIN: return None
    # zmiana NAZWY ligi (Lotwa: „LHL” -> „Optibet Hokeja Liga”) to nie awans: wiekszosc druzyn starej ligi gra w nowej
    y = d[(d.sport == sport) & ~d.liga.astype(str).str.contains(_PUCHAR)]
    dy = pd.to_datetime(y.data)
    def druzyny(m): return set(m.gosp) | set(m.gosc)
    stare = druzyny(y[(y.liga == stara) & (dy >= start - pd.DateOffset(years=1)) & (dy < start)])
    w_nowej = druzyny(y[(y.liga == nowa) & (dy >= start)])
    if len(stare) and len(stare & w_nowej) / len(stare) >= 0.5: return None
    return stara, nowa, int(teraz.iloc[0])


# 07.10.2026 (audyt usterek, Raport 23.09 20:00 nr 7): reprezentacje graja kilka-kilkanascie meczow rocznie — Elo
# Wloch (1693, 34 mecze) bylo nizsze niz Finlandii (1707, 25), a ostrzezenie ELO NIEZBIEZNE konczylo sie na 25 meczach
# i noga przechodzila. Mecz dwoch reprezentacji: noga tylko, gdy obie maja co najmniej tyle meczow w bazie.
REPREZENTACJE_MIN_MECZOW = 60


def werdykt_meczu(skala_ok, p_dz, n, ligi=(), zmiany=(), reprezentacje=False):
    """29.09.2026: jedna linia WERDYKT zamiast bramek rozrzuconych po wyjsciu (wspolna skala, drugie
    zrodlo z Poprawek 48/51, dane rywala z Poprawki 15). Zwraca (P do kuponu | None, lista powodow).
    ligi — ligi obu druzyn/graczy (Poprawka 60: LIGI_BEZ_PRZEWAGI); zmiany — [(druzyna, stara, nowa, n)] (02.10)."""
    powody = [p for k, p in LIGI_BEZ_PRZEWAGI.items() if any(k in str(l) for l in ligi)]
    for t, stara, nowa, k in zmiany:
        powody.append(f'zmiana ligi: {t} {stara} -> {nowa} ({k} mecz(e) w nowej, < {ZMIANA_LIGI_MIN}) — Elo z innej ligi')
    if not skala_ok: powody.append('rozne ligi bez wspolnej skali')
    if p_dz is None: powody.append('brak zgodnego drugiego zrodla')
    if n < 5: powody.append(f'brak danych rywala ({n} mecz(e))')
    elif reprezentacje and n < REPREZENTACJE_MIN_MECZOW:
        powody.append(f'reprezentacje: Elo niezbiezne ({n} mecz(e) < {REPREZENTACJE_MIN_MECZOW})')
    return (None if powody else p_dz), powody


def _ligi_druzyny(x, t, min_m=3):
    v = pd.concat([x.loc[x.gosp == t, 'liga'], x.loc[x.gosc == t, 'liga']]).value_counts()
    return set(v[v >= min_m].index)


def wspolna_skala(d, sport, h, g, dni=730):
    """Czy ligi obu druzyn sa polaczone meczami (inaczej Elo z roznych basenow jest nieporownywalne).
    Polaczenie: wspolna liga ALBO >= 2 ROZNE inne druzyny grajace (>= 3 mecze) w lidze h i w lidze g
    ALBO >= 3 mecze miedzy druzynami z tych lig (puchary: CHL, EuroLiga). Jedna druzyna, ktora spadla,
    NIE wystarcza — to ona robila falszywe polaczenie SHL–Allsvenskan."""
    x = d[(d.sport == sport) & (d.data >= d.data.max() - pd.Timedelta(days=dni))]
    Lh, Lg = _ligi_druzyny(x, h), _ligi_druzyny(x, g)
    if not Lh or not Lg or Lh & Lg: return True, Lh, Lg
    c = pd.concat([x[['liga', 'gosp']].rename(columns={'gosp': 't'}), x[['liga', 'gosc']].rename(columns={'gosc': 't'})])
    cnt = c.groupby(['t', 'liga']).size()
    cnt = cnt[cnt >= 3].reset_index()
    wh = set(cnt[cnt.liga.isin(Lh)].t) - {h, g}
    wg = set(cnt[cnt.liga.isin(Lg)].t) - {h, g}
    if len(wh & wg) >= 2: return True, Lh, Lg
    th, tg = set(cnt[cnt.liga.isin(Lh)].t), set(cnt[cnt.liga.isin(Lg)].t)
    krzyz = x[((x.gosp.isin(th - tg)) & (x.gosc.isin(tg - th))) | ((x.gosp.isin(tg - th)) & (x.gosc.isin(th - tg)))]
    return len(krzyz) >= 3, Lh, Lg



START_SEZONU = '2026-08-01'


def biezacy_sezon(d, od=None, min_meczow=20):
    """Ligi z >= min_meczow meczami od startu sezonu: mecze, druzyny, kolejki (mediana meczow na druzyne)."""
    x = d[d.data.astype(str) >= (od or START_SEZONU)]
    t = pd.concat([x[['sport', 'liga', 'gosp']].rename(columns={'gosp': 'd'}), x[['sport', 'liga', 'gosc']].rename(columns={'gosc': 'd'})])
    g = t.groupby(['sport', 'liga', 'd']).size().groupby(['sport', 'liga']).agg(druzyn='size', kolejki='median')
    g['mecze'] = x.groupby(['sport', 'liga']).size()
    g = g[g.mecze >= min_meczow]
    g['kolejki'] = g.kolejki.round().astype(int)
    g['szacunek'] = (g.kolejki < 3).map({True: 'TAK (< 3 kolejki)', False: 'nie'})
    return g[['mecze', 'druzyn', 'kolejki', 'szacunek']]


def nazwa_sportu(s):
    """29.09.2026 (Raport 12:00, usterka 6): "koszykowka", "pilka_reczna", "tenis-stolowy" -> nazwa z bazy
    ("koszykówka", "piłka ręczna", "tenis stołowy"). Nieznana nazwa wraca bez zmian (dalej BRAK W BAZIE)."""
    s = str(s).strip().lower()
    if s in SPORT: return s
    k = norm(s.replace('_', ' ').replace('-', ' '))
    r = next((x for x in SPORT if norm(x) == k), None)
    if r: return r
    # 29.09.2026 (Raport 15:00): „sporty.py typuj reczna …” -> BRAK W BAZIE dla calej pilki recznej
    # (Füchse Berlin, VfL Gummersbach sa w bazie). Skroty i nazwy angielskie:
    r = _SPORT_SYNONIMY.get(k)
    if r in SPORT: return r
    kand = [x for x in SPORT if k and norm(x.split()[-1]) == k]      # „reczna”, „stolowy”, „wodna”
    return kand[0] if len(kand) == 1 else s


_SPORT_SYNONIMY = {'handball': 'piłka ręczna', 'basketball': 'koszykówka', 'volleyball': 'siatkówka',
                   'hockey': 'hokej', 'icehockey': 'hokej', 'hokejnalodzie': 'hokej', 'darts': 'dart',
                   'tabletennis': 'tenis stołowy', 'pingpong': 'tenis stołowy', 'americanfootball': 'futbol amerykański',
                   'nfl': 'futbol amerykański', 'floorball': 'unihokej'}


def _rynek_typu(m):
    """Rynek z sporty_typy.csv -> zapis rozliczany przez dzienniki.rozlicz_noge. W logu „1”/„2” = zwyciezca meczu
    z dogrywka (tak liczyl dawny kod: pg > pa), „1_60min” = czas regulaminowy. AKOP_/ODRZ_ to znacznik kuponu."""
    m = re.sub(r'^(AKOP|ODRZ)_', '', str(m).strip())
    m = re.sub(r'(?i)^(zwyci[eę]zca_?|z)([12])$|^([12])_dogrywka$|^([12])$', lambda x: 'Z' + (x.group(2) or x.group(3) or x.group(4)), m)
    return {'1_60min': '1 (60 min)', '2_60min': '2 (60 min)'}.get(m, m)


def rozlicz_typy(L, W=None):
    """05.10.2026: rozliczenie sporty_typy.csv TYM SAMYM silnikiem co ako_log (dzienniki.rozlicz_noge). Dawny kod
    porownywal nazwy dokladnie (norm), wiec nazwa z oferty („Motor Ceske Budejovice”) nigdy nie trafiala w nazwe z bazy
    („HC České Budějovice”), nie znal Z1 / zwyciezca_1 / 1_dogrywka ani tenisa — 200 z 216 typow bez rozliczenia,
    a kalibracja sportow czekala na >=150. Teraz: aliasy i resolve, dogrywka, serie (pierwszenstwo dnia meczu)."""
    import dzienniki
    if W is None:
        W = dict(pilka=pd.DataFrame(columns=['d', 'h', 'a', 'g', 'ga', 'hg', 'ha']), inne=dzienniki.wyniki_inne(),
                 tenis=dzienniki.wyniki_tenis())
    n = 0
    for i, r in L[L.trafiony.isna()].iterrows():
        noga = dict(sport=r.sport, zdarzenie=f'{r.gosp} - {r["gosc"]}', rynek=_rynek_typu(r.rynek), data=str(r.data)[:10], uwaga='')
        stan = dzienniki.rozlicz_noge(noga, W)[0]
        if stan in ('TRAFIONY', 'PRZEGRANY'):
            L.loc[i, 'trafiony'] = int(stan == 'TRAFIONY'); n += 1
    print(f'rozliczono {n} typow; bez wyniku {int(L.trafiony.isna().sum())}')
    return L


def linia_dopuszczona(fav, draws, p_k, n, klucz=None, kursy=None):
    """Linia WERDYKT dla nogi dopuszczonej. Raport 09.10 18:00 nr 2: z podanym kursem tego rynku (--kurs Z1/Z2 albo 1/2)
    EV liczy kod — dotad raport liczyl je recznie tym samym wzorem P × kurs × 0,88 − 1."""
    k_ = (kursy or {}).get(klucz) if klucz else None
    return (f'WERDYKT: NOGA DOPUSZCZONA — {fav}' + (' (z dogrywka)' if draws else '')
            + f', P do kuponu {p_k:.1%}' + (' (SZACUNEK: < 10 meczow)' if n < 10 else '')
            + (f' | kurs {klucz} {k_:.2f} | EV {p_k * k_ * 0.88 - 1:+.1%} (P × kurs × 0,88 − 1)' if k_ else
               '; EV licz z TEGO P: P × kurs × 0,88 − 1'))


def main(a):
    a = list(a)
    if a and a[0] in ('wynik', 'typ') and len(a) > 2: a[2] = nazwa_sportu(a[2])
    elif len(a) > 1: a[1] = nazwa_sportu(a[1])
    if a[0] == 'wynik':
        row = dict(data=a[1], sport=a[2].lower(), liga=a[3], gosp=a[4], gosc=a[5], pg=float(a[6]), pa=float(a[7]),
                   dogrywka=int(a[8]) if len(a) > 8 else 0)
        pd.DataFrame([row]).to_csv(DB, mode='a', header=not os.path.exists(DB), index=False); print('dopisano', row)
    elif a[0] == 'backtest':
        d = load(); cals = [c for sp in sorted(d.sport.unique()) for c in [backtest(d, sp)] if c is not None]
        c = backtest(d, 'hokej', od=OD_POZA_NHL, maska=lambda t: ~t.liga.astype(str).str.contains(r'\bNHL\b'), klucz=KAL_POZA_NHL)
        if c is not None: cals.append(c)
        if cals: pd.concat(cals).to_csv(CALH, index=False, float_format='%.4f'); print('zapisano', CALH)
    elif a[0] == 'druzyny':  # lista drużyn w bazie pasujących do fragmentu nazwy
        sport = a[1].lower(); inf = {}; R, N, *_ = elo(load(), sport, info=inf); q = norm(a[2]) if len(a) > 2 else ''
        for t in sorted(R, key=lambda t: -R[t]):
            if q in norm(t): print(f'{t:<40} Elo {R[t]:6.0f}  meczów {N.get(t, 0):5d}  {inf["seeded"].get(t, "")}')
    elif a[0] == 'stan':
        d = load()
        if len(d):
            print(d.groupby('sport').agg(mecze=('gosp', 'size'), od=('data', 'min'), do=('data', 'max')).to_string())
        else:
            # 22.09.2026. Wczesniej bylo po prostu "baza pusta" — i to jest mylace, bo najczestsza
            # przyczyna nie jest pusta baza, tylko BRAK PLIKU: hist_import.py jeszcze nie skonczyl
            # albo padl. W przebiegu 17:02 sporty.py pokazal "baza pusta" dokladnie w tej sytuacji,
            # a gdyby przebieg temu zaufal, odrzucilby wszystkie sporty poza pilka i tenisem.
            # Rozroznienie kosztuje dwie linie i zapobiega cichemu wyrzuceniu polowy oferty.
            brak = [f for f in (HIST, DB) if not os.path.exists(f)]
            if brak:
                print('BRAK PLIKU BAZY: ' + ', '.join(os.path.basename(f) for f in brak))
                print('To NIE znaczy, ze baza jest pusta — plik jeszcze nie powstal.')
                print('Uruchom hist_import.py i POCZEKAJ na jego zakonczenie, zanim uznasz sporty za niedostepne.')
                sys.exit(2)
            print('baza pusta (pliki istnieja, ale nie zawieraja zadnego meczu) — sprawdz hist_import.py')
        if os.path.exists(TAB):
            t = pd.read_csv(TAB)
            # 29.09.2026 (Raport 15:00): kolumna „sezon” to sezon TABELI SILY STARTOWEJ (poprzedni sezon),
            # a przebieg odczytal ja jako „trwa sezon 2025-26” i uznal hokej za szacunek. Stan biezacego
            # sezonu (A1 a: >= 3 kolejki) jest nizej, liczony z wynikow.
            print('\nTabele lig — SILA STARTOWA z poprzedniego sezonu (to NIE jest stan biezacego sezonu):')
            print(t.groupby(['sport', 'liga']).agg(druzyn=('druzyna', 'size'), sezon_tabeli=('sezon', 'max')).to_string())
        if len(d):
            print(f'\nBIEZACY SEZON (od {START_SEZONU}) — rozegrane kolejki na lige (A1 a: szacunek, gdy < 3):')
            print(biezacy_sezon(d).to_string())
    elif a[0] == 'typuj':
        # 03.10.2026: sporty.py przyjmuje teraz kursy (--kurs 1=1.72 --kurs X=4.25 --kurs 2=3.60,
        # albo Z1/Z2 dla rynku "Zwyciezca meczu" z dogrywka), zeby wykonac KROK 6.4 w kodzie.
        a, kursy_cli = rynek.kursy_z_argv(a)
        sport = a[1].lower(); d = load(); inf = {}; R, N, hfa, draws, pdraw = elo(d, sport, info=inf); L_ = inf['last']
        pool = set(R); _KANDYDAT.clear(); h, g = resolve(a[2], pool, sport), resolve(a[3], pool, sport)
        h, g = potwierdz_rywalem(d, sport, (a[2], a[3]), (h, g))
        if h is None or g is None:
            h, g = kraj_z_terminarza(d, sport, (a[2], a[3]), (h, g))
        # 21.09.2026 (POPRAWKA 11): dawniej bylo "resolve(...) or a[2]" — przy nieznanej nazwie
        # skrypt podstawial surowa nazwe z oferty, nadawal jej domyslne Elo 1500 i mimo ostrzezenia
        # DRUKOWAL PELNA TABELE P. To ten sam typ usterki co joker w resolve(): zamiast bledu
        # czlowiek dostawal wiarygodnie wygladajace liczby dla druzyny, ktorej nie ma w bazie.
        brak = [n for n, r in ((a[2], h), (a[3], g)) if r is None]
        if brak:
            sys.exit(f'BRAK W BAZIE: {", ".join(repr(x) for x in brak)} — analiza przerwana.\n'
                     f'Sprawdz nazwe: python3 sporty.py druzyny {sport} FRAGMENT\n'
                     f'Brak dopasowania jest poprawnym wynikiem — to noga MNIEJ na kuponie, '
                     f'a nie noga policzona z cudzych danych.')
        # Gospodarz i gosc NIE MOGA rozwiazac sie do tej samej druzyny. Gdy to sie stanie,
        # dwie rozne nazwy z oferty wskazuja jeden wpis w bazie — model policzylby wtedy
        # mecz druzyny z sama soba i wyprodukowal P blisko 50% dla obu stron, wygladajace
        # zupelnie normalnie. 22.09.2026 taka sytuacja siedziala w bazie 122 razy.
        if h == g:
            sys.exit(f'TA SAMA DRUZYNA PO OBU STRONACH: "{a[2]}" i "{a[3]}" wskazuja na "{h}" '
                     f'— analiza przerwana.\n'
                     f'Sprawdz nazwy: python3 sporty.py druzyny {sport} FRAGMENT\n'
                     f'Lepiej nie miec tej nogi, niz miec ja policzona z pomylonych druzyn.')
        n = min(N.get(h, 0), N.get(g, 0))
        print(f'{sport}: {h} (Elo {R.get(h, 1500):.0f}, {N.get(h, 0)} m.) – {g} (Elo {R.get(g, 1500):.0f}, {N.get(g, 0)} m.)')
        for t in (h, g):
            if t in inf['seeded']: print(f'  {t}: siła startowa z tabeli ligi {inf["seeded"][t]} (+ wyniki dopisane później)')
        ec, note, e, _linie = p_gospodarza(d, sport, R, L_, hfa, draws, h, g, '--neutral' in a)
        for _l in _linie: print(_l)
        if draws:
            # 30.09.2026 (przeglad): ec*(1-pdraw) zaklada, ze dogrywke wygrywa faworyt z P = ec; przy dogrywce ~50/50
            # wychodzi ec - pdraw/2. Bez danych o dogrywkach (dogrywka = -1) nie da sie tego zmierzyc — bierzemy MNIEJSZA
            # wartosc z obu, zeby nie zawyzac zadnej strony (dotad slabszy dostawal ok. 15,6% zamiast ok. 10%).
            p1_60, p2_60 = rynki_60min(ec, pdraw)
            for k_, p in (('1 (60 min / regulaminowy czas)', p1_60), ('X', pdraw), ('2', p2_60),
                          ('1 z dogrywką', ec), ('2 z dogrywką', 1 - ec)):
                print(f'  {k_:<32} {p:6.1%}')
        else:
            for k_, p in (('1', ec), ('2', 1 - ec)): print(f'  {k_:<32} {p:6.1%}' + ('  (pojedyncza mapa)' if sport in MAPOWE else ''))
            if sport in MAPOWE:
                bo3 = ec ** 2 * (3 - 2 * ec); bo5 = ec ** 3 * (10 - 15 * ec + 6 * ec ** 2)
                print(f'  {"1 seria Bo3":<32} {bo3:6.1%}\n  {"2 seria Bo3":<32} {1 - bo3:6.1%}\n  {"1 seria Bo5":<32} {bo5:6.1%}\n  {"2 seria Bo5":<32} {1 - bo5:6.1%}')
        ok_, Lh_, Lg_ = wspolna_skala(d, sport, h, g)
        if not ok_:
            print(f'  ROZNE LIGI BEZ WSPOLNEJ SKALI: {h} ({", ".join(sorted(Lh_))}) i {g} ({", ".join(sorted(Lg_))}) — '
                  f'Elo z rozlacznych basenow, P NIEPOROWNYWALNE; nie buduj nogi kuponu z tego meczu, takze papierowej.')
        p_dz = drugie_zrodlo(d, sport, h, g, ec)
        stale = [t for t in (h, g) if t in L_ and (pd.Timestamp.today() - L_[t]).days > 150]
        if stale: print('  OSTRZEŻENIE: ostatni mecz w bazie >150 dni temu dla:', ', '.join(stale), '— sprawdź transfery/formę w sieci, korekta maks. ±6 pp.')
        print(f'  {note}')
        if n < 5:
            print(f'  BRAK DANYCH RYWALA: najslabiej opisana druzyna ma {n} mecz(e) w bazie. Elo jest')
            print('  wtedy bliskie domyslnemu 1500, wiec powyzsze P nie jest pomiarem, tylko artefaktem')
            print('  braku danych. NIE buduj na tym nogi kuponu, nawet jesli EV wychodzi wysokie.')
        elif n < 10:
            print(f'  UWAGA: mało meczów w bazie ({n}) — P to szacunek; opieraj się na statystykach z sieci (MASTER PROMPT część B).')
        elif n < 25:
            # 22.09.2026. Polska-Niemcy (siatkowka, 16 i 10 meczow) nie dostawalo ZADNEGO ostrzezenia,
            # bo prog konczyl sie na n<10. A to wlasnie ten zakres myli sie w PRZEWIDYWALNA strone.
            # Elo startuje od 1500 i po kilkunastu meczach jeszcze tam nie dotarlo: cale reprezentacje
            # siatkarskie mieszcza sie w pasmie 1383-1718 (335 pkt), podczas gdy same KLUBY, majace
            # po 22-28 meczow, siegaja 1783. Rozstep jest scisniety, wiec faworyt dostaje P za niskie,
            # a slabszy za wysokie — i to tym mocniej, im wieksza jest prawdziwa roznica klas.
            # Skutek praktyczny: na slabszej druzynie wychodzi pozorne, bardzo wysokie EV. To nie jest
            # przewaga, tylko brak zbieznosci Elo. Ostrzegamy o kierunku bledu, nie o jego istnieniu.
            print(f'  ELO NIEZBIEZNE: najslabiej opisana druzyna ma {n} mecz(e) — za malo, by Elo')
            print('  odeszlo od startowych 1500. Rozstep jest scisniety KU SRODKOWI: P faworyta jest')
            print('  zanizone, P slabszego zawyzone, tym bardziej im wieksza roznica klas.')
            print('  Wysokie EV na SLABSZEJ druzynie jest tu artefaktem, nie przewaga — nie graj go.')
            print('  P faworyta traktuj jako DOLNA granice. Mecze wyrownane sa wiarygodniejsze.')
        fav = h if ec >= 0.5 else g
        zmiany = [(t,) + z for t in (h, g) if sport in ZMIANA_LIGI_SPORTY for z in [zmiana_ligi(d, sport, t)] if z]
        for t, stara, nowa, k in zmiany:
            print(f'  ZMIANA LIGI (awans/spadek): {t}: {stara} -> {nowa}, {k} mecz(e) w nowej lidze — Elo z innej ligi, '
                  f'P NIEPOROWNYWALNE z rynkiem (02.10: Krefeld, Dresdner Eislowen); nie buduj nogi kuponu, takze papierowej.')
        p_k, powody = werdykt_meczu(ok_, p_dz, n, _ligi_druzyny(d[d.sport == sport], h, 1) | _ligi_druzyny(d[d.sport == sport], g, 1),
                                    zmiany, reprezentacje=_kraj(h) and _kraj(g))
        # 03.10.2026 (KROK 6.4 + KROK 4.5). Dwie bramki, obie tylko odrzucajace:
        # (a) P "z dogrywka" nie opisuje rynku 1/X/2, ktory jest czasem regulaminowym (P121.2).
        #     03.10 na 11 nogach hokeja i recznej STS mial w ofercie WYLACZNIE 1/X/2, a doslowne
        #     zastosowanie werdyktu dawalo EV +24,9% / +9,1% / +9,0% zamiast +3,2% / -9,8% / -10,0%.
        # (b) rozbieznosc z rynkiem > 15 pp (03.10: Vitoria SC - FC Porto 42,0% vs 5,7% = 36,3 pp).
        pow_rynek = None; klucz = None
        if not powody and kursy_cli:
            strona = '1' if fav == h else '2'
            if draws and not any(k in kursy_cli for k in ('Z1', 'Z2')) and any(k in kursy_cli for k in ('1', 'X', '2')):
                pow_rynek = ('P jest "z dogrywka", a podane kursy to rynek 1/X/2 = CZAS REGULAMINOWY (P121.2) — '
                             'to nie jest ten sam rynek. Podaj --kurs Z1/Z2 ("Zwyciezca meczu") albo policz EV '
                             'z P dla 60 min z tabeli wyzej')
            else:
                klucz = ('Z' + strona) if ('Z' + strona) in kursy_cli else strona
                pow_rynek = rynek.filtr_model_rynek(klucz, p_k, kursy_cli)
        if powody or pow_rynek:
            print(f'\nWERDYKT: NIE NA KUPON — {"; ".join(powody) if powody else pow_rynek}')
        else:
            print('\n' + linia_dopuszczona(fav, draws, p_k, n, klucz, kursy_cli))
    elif a[0] == 'typ':
        from clv import dopisz_typ   # opcjonalnie KURS_TYPU [PIENIADZE] na koncu (P56.3, CLV)
        # 07.10.2026 (Raport 15:00 nr 5): „1”/„2” w sporty_typy znaczy zwyciezca Z DOGRYWKA (_rynek_typu -> Z1/Z2), ale w ako_log
        # i w P121.2 ten sam napis to czas regulaminowy — przebieg poprawial wiersze recznie. Zapis od razu jednoznaczny.
        row = dict(data=a[1], sport=a[2].lower(), gosp=a[3], gosc=a[4], rynek=re.sub(r'^((?:AKOP|ODRZ)_)?([12])$', r'\1Z\2', a[5].strip()), p=float(a[6]), trafiony=None)
        print('zapisano', dopisz_typ(LOG, row, a[7:9]))
    elif a[0] == 'rozlicz':
        if not os.path.exists(LOG): sys.exit('brak prognoz')
        L = pd.read_csv(LOG)
        rozlicz_typy(L)
        L.to_csv(LOG, index=False)
        done = L.dropna(subset=['trafiony'])
        # tabela kal_wlasna: tylko zwyciezca z dogrywka (P faworyta) — „1”/„2” i ten sam rynek pod innym zapisem (Z1, zwyciezca_1)
        done = done[done.rynek.map(_rynek_typu).isin(['Z1', 'Z2'])]
        done = done.assign(sport=done.sport.map(nazwa_sportu))   # „koszykowka” i „koszykówka” to jeden sport (05.10.2026)
        if done.empty: print('brak rozliczonych'); return
        rows = []
        for sp, g in done.groupby('sport'):
            g = g.sort_values('p'); q = np.array_split(np.arange(len(g)), max(1, min(10, len(g) // 40)))
            for i in q: rows.append((sp, g.p.values[i].mean(), g.trafiony.values[i].mean(), len(i)))
            print(f'{sp}: {len(g)} prognoz, średnie P {g.p.mean():.1%}, trafność {g.trafiony.mean():.1%}')
        c = pd.DataFrame(rows, columns=['sport', 'p_model', 'p_kalibr', 'n'])
        from kalib import pav
        c['p_kalibr'] = np.concatenate([pav(g.p_kalibr.values, g.n.values) for _, g in c.groupby('sport', sort=False)])
        c.to_csv(CAL, index=False, float_format='%.4f')


# 29.09.2026 (faza 3b): aliasy z pliku danych aliasy.csv (modul=sporty) — na koncu, zeby wpisy w kodzie wygrywaly
from nazwy import aliasy_z_pliku as _aliasy_z_pliku
import nazwy as _nazwy
_aliasy_z_pliku('sporty', norm, _ALIASY_RECZNE)
_aliasy_z_pliku('sporty', norm, _ALIASY_RECZNE, _nazwy.ALIASY_AUTO_CSV)   # dopasuj.py auto (03.10.2026)
_ALIASY_WIELE = _nazwy.aliasy_wiele('sporty', norm)

if __name__ == '__main__':
    main(sys.argv[1:] or ['stan'])
