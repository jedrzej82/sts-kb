#!/usr/bin/env python3
"""Wszystkie sporty z oferty STS poza piłką i tenisem (hokej, koszykówka, siatkówka, piłka ręczna, futsal, esport, baseball,
futbol amerykański, rugby, snooker, dart, MMA/boks …): Elo z przewagą gospodarza per sport, budowane z wyników dopisywanych
codziennie do sporty_delta.csv. Model uczy się od zera — im więcej wyników, tym pewniejszy; kalibracja z własnych prognoz.
  python3 sporty.py wynik RRRR-MM-DD SPORT LIGA "Gosp" "Gość" PKT_G PKT_A [dogrywka:0/1]
  python3 sporty.py typuj SPORT "Gosp" "Gość" [--neutral]
  python3 sporty.py typ RRRR-MM-DD SPORT "Gosp" "Gość" RYNEK P     — zapis prognozy (RYNEK: 1 / 2 / X / 1_60min …)
  python3 sporty.py rozlicz                                         — rozliczenie + kalibracja per sport
  python3 sporty.py stan                                            — ile meczów/drużyn w bazie per sport
  python3 sporty.py druzyny SPORT FRAGMENT                           — nazwy drużyn w bazie (Elo, liczba meczów)
  python3 sporty.py backtest                                        — kalibracja z historii (sporty_hist.csv) → sporty_kalibracja_hist.csv
Baza = sporty_hist.csv (NBA/WNBA/NHL/NFL/MLB z GitHub, hist_import.py) + sporty_delta.csv (wyniki dopisywane codziennie)."""
import os, sys, re, difflib, unicodedata, numpy as np, pandas as pd
import functools

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
_LITERY = str.maketrans({'ł':'l','Ł':'L','đ':'d','Đ':'D','ø':'o','Ø':'O','ß':'ss',
                         'æ':'ae','Æ':'AE','œ':'oe','Œ':'OE','þ':'th','Þ':'TH',
                         'ð':'d','Ð':'D','ı':'i','ŋ':'n','ħ':'h','ŧ':'t'})

def norm(s): return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(s).translate(_LITERY)).encode('ascii', 'ignore').decode().lower())


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


def load():
    cols = ['data', 'sport', 'liga', 'gosp', 'gosc', 'pg', 'pa', 'dogrywka']
    h = pd.read_csv(HIST) if os.path.exists(HIST) else pd.DataFrame(columns=cols)
    x = pd.read_csv(DB) if os.path.exists(DB) else pd.DataFrame(columns=cols)
    if len(x):  # wynik dopisany ręcznie wygrywa z historią; w samym delta — ostatni zapis wygrywa
        x = x.drop_duplicates(['data', 'sport', 'gosp', 'gosc'], keep='last')
        k = lambda z: z.data.astype(str).str[:10] + '|' + z.sport + '|' + z.gosp.astype(str) + '|' + z.gosc.astype(str)
        h = h[~k(h).isin(set(k(x)))]
    d = pd.concat([h, x], ignore_index=True); d['data'] = pd.to_datetime(d.data)
    for liga, m in (('NFL', NFL), ('MLB', MLB)):
        i = d.liga == liga; d.loc[i, 'gosp'] = d.loc[i, 'gosp'].replace(m); d.loc[i, 'gosc'] = d.loc[i, 'gosc'].replace(m)
    d = scal_warianty(d)
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
_ZNACZNIK = re.compile(r'^(b|ii|iii|2|3|c|k|u-?1[6-9]|u-?2[0-3]|sub-?2[0-3]|jun|juniors?|res|reserves?|'
                       r'young|youth|yth|academy|akademia|w|women|kobiet[ay]?|damen|femenino|femenil|'
                       r'feminin[oa]?|fem)\.?$', re.I)


def _znaczniki(s):
    # 22.09.2026: STS oznacza druzyny kobiece sufiksem "[K]", a czasem "(W)". Bez zdjecia
    # nawiasow token "[K]" nie pasowal do wzorca i "Club Leon [K]" dopasowywalo sie
    # do meskiego "Club Leon" — zmierzone na 5 meczach w przebiegu 21:00 dnia 21.09,
    # bez zadnego ostrzezenia. Model liczyl mecze meskie dla zdarzen kobiecych.
    # 23.09.2026 (wyd. 24, recenzja): liczyl tylko ILE jest znacznikow, nie JAKIE — "Barcelona (K)"
    # (kobiety) trafiala na "Barcelona B" (rezerwy), a "Real Madryt [K]" na "Real Madrid C", bo po obu
    # stronach byl jeden znacznik. Teraz porownujemy RODZAJE: kobiety / rezerwy B / zespol C /
    # kategoria wiekowa (z rocznikiem) / mlodziez ogolnie.
    out = []
    for t in re.split(r'[\s]+', str(s).strip()):
        t = t.strip('[](){}<>.,;:')
        if not _ZNACZNIK.match(t): continue
        t = t.lower().rstrip('.')
        if re.match(r'^(k|w|women|kobiet[ay]?|damen|femenino|femenil|feminin[oa]?|fem)$', t): out.append('kobiety')
        elif re.match(r'^(b|ii|2|res|reserves?)$', t): out.append('rezerwy')
        elif re.match(r'^(c|iii|3)$', t): out.append('zespol_c')
        elif re.match(r'^(u|sub)-?\d+$', t): out.append('u' + re.sub(r'\D', '', t))
        else: out.append('mlodziez')
    return tuple(sorted(out))


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
            _c = _pula.get(norm(_t)) or dopasuj_seed(_t, _pula)
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
    return tuple(re.findall(r'[a-z0-9]+', unicodedata.normalize('NFKD', str(s).translate(_LITERY)).encode('ascii', 'ignore').decode().lower()))


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
    'dania': ('Denmark',), 'dominikana': ('Dominican Republic',), 'egipt': ('Egypt',),
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
                    'county rugby ishockey ik if'.split())


# Poprawka 54 (24.09.2026): STS podaje druzyny NCAA z przydomkiem („Coastal Carolina Chanticleers”,
# „Liberty Flames”), baza 365scores bez niego („Coastal Carolina”, „Liberty”). Przydomek to NIE czlon
# rozrozniajacy — odpada TYLKO gdy wszystkie odciete czlony stoja NA KONCU nazwy i sa na tej liscie.
_PRZYDOMKI_USA = frozenset('''49ers aggies anteaters antelopes aztecs badgers baylor bearcats bears beavers bengals big bison black blazers blue bobcats boilermakers bonnies broncos bruins buccaneers buckeyes bucs buffaloes bulldogs bulls cajuns cardinal cardinals catamounts cavaliers chanticleers chargers chippewas colonels commodores cornhuskers cougars cowboys coyotes crimson crusaders cyclones deacons demon devils dolphins dons ducks dukes eagles explorers falcons fighting flames flash flashes friars frogs gaels gamecocks gators golden gophers governors green greyhounds grizzlies hatters hawkeyes hawks heels herd highlanders hilltoppers hokies hoosiers horned hornets hoyas hurricane hurricanes huskers huskies illini irish jackets jackrabbits jaguars jayhawks keydets knights lancers leathernecks lions lobos longhorns lumberjacks matadors mavericks mean midshipmen miners minutemen mocs monarchs mountaineers mustangs niners nittany orange ospreys owls pack paladins panthers penguins phoenix pilots pirates quakers racers ragin raiders rainbow rams razorbacks rebels red redbirds redhawks retrievers roadrunners rockets runnin salukis scarlet seahawks seawolves seminoles skyhawks sooners spartans spiders stags statesmen sun sycamores tar terrapins terriers thunderbirds thundering tide tigers titans toreros tribe tritons trojans utes vandals volunteers warhawks warriors wave wildcats wolf wolfpack wolverines wolves yellow zips'''.split())


def _skrot_albo_nic(name, wyn, pula):
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
    if len(tn) <= len(tk): return wyn
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
    return None


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


def resolve(name, pool):
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
    c = [p for p in by.values() if _zaw_nazwy(name, p)]
    if c:
        if len(c) == 1:
            wyn = c[0]
        else:   # "Chievo Verona" zawiera i "Chievo", i "Verona" — pierwszy czlon to niemal zawsze wlasciwy klub
            pref = [p for p in c if k_.startswith(norm(p)) or norm(p).startswith(k_)]
            if len(pref) == 1: wyn = pref[0]
            elif pref: wyn = max(pref, key=lambda p: len(norm(p)))
            else: wyn = min(c, key=lambda p: abs(len(norm(p)) - len(k_)))
        return _skrot_albo_nic(name, wyn, by.values())
    # prog 0.7 byl za luzny i milczacy; 0.80 jak w typuj.py, z ostrzezeniem dla czlowieka
    # rozmyte tylko dla dluzszych nazw i z wysokim progiem (0,87 zamiast 0,80:
    # przy 0,80 "Argentinos"->"Argentino MM", "Champions"->"Campion", "Karlstad"->"Harstad") — przy 3-5 znakach prog 0,80 osiaga sie trywialnie
    # i dawal "Nart"->"Lenart", "Amal"->"Samail", "Pro"->"Paro", "Cuba"->"Cuiaba"
    m = difflib.get_close_matches(k_, list(by), n=1, cutoff=0.90) if len(k_) >= 8 else []
    # dodatkowo pierwsze trzy znaki musza sie zgadzac: przy samym progu 0,90
    # przechodzilo jeszcze "Champions"->"Campion" i "Academico"->"Academica" (dwa rozne kluby).
    # Brak dopasowania to noga MNIEJ na kuponie, pomylona druzyna to kupon przegrany —
    # ta asymetria kaze wybrac ostroznosc.
    m = [x for x in m if x[:3] == k_[:3]]
    if m:
        print(f'  UWAGA: "{name}" dopasowane ROZMYTO do "{by[m[0]]}" — upewnij sie, ze to ta sama druzyna.')
        return by[m[0]]
    return None


def calibrate(sport, p):
    """Najpierw własne rozliczone prognozy (n≥150), potem backtest historyczny (dotyczy P faworyta/zwycięzcy, bez remisu)."""
    for path, lab in ((CAL, 'własne prognozy'), (CALH, 'backtest historyczny')):
        if not os.path.exists(path): continue
        c = pd.read_csv(path); c = c[c.sport == sport]
        if c.n.sum() < 150: continue
        q = max(p, 1 - p); pc = float(np.interp(q, c.p_model, c.p_kalibr))
        return (pc if p >= 0.5 else 1 - pc), f'skalibrowane ({lab}, n={int(c.n.sum())})'
    return p, 'BRAK KALIBRACJI dla tego sportu — P traktuj jak „szacunek” (max 1 na kupon), dopóki sporty.py rozlicz nie zbierze ≥150 prognoz'


PARAM = os.path.join(HERE, 'sporty_param.json')   # v5n: model marży punktowej + zespół z Elo (sporty_bt.py)


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


def backtest(d, sport, od='2015-01-01'):
    pre = []; hfa = elo(d, sport, pre)[2]
    t = d[d.sport == sport].assign(ra=[x[0] for x in pre], rb=[x[1] for x in pre], na=[x[2] for x in pre], nb=[x[3] for x in pre])
    t = t[(t.data >= od) & (t.na >= 20) & (t.nb >= 20) & (t.pg != t.pa)]
    if len(t) < 300: return None
    e = 1 / (1 + 10 ** ((t.rb - t.ra - hfa) / 400)); win = (t.pg > t.pa).astype(float)
    pf = np.maximum(e, 1 - e); hit = np.where(e >= 0.5, win, 1 - win)
    c = pd.DataFrame({'p': pf, 'h': hit}).sort_values('p'); q = np.array_split(np.arange(len(c)), 12)
    cal = pd.DataFrame([(sport, c.p.values[i].mean(), c.h.values[i].mean(), len(i)) for i in q], columns=['sport', 'p_model', 'p_kalibr', 'n'])
    cal['p_kalibr'] = np.maximum.accumulate(cal.p_kalibr.values)
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


def drugie_zrodlo(d, sport, h, g, p_h):
    """p_h = P modelu, ze wygra PIERWSZA druzyna (h) — przy hokeju „z dogrywka”."""
    x = d[d.sport == sport]
    def forma(t):
        m = x[(x.gosp == t) | (x.gosc == t)].tail(DZ_OKNO)
        w = int(((m.gosp == t) & (m.pg > m.pa)).sum() + ((m.gosc == t) & (m.pa > m.pg)).sum())
        return w, len(m)
    (wh, nh), (wg, ng) = forma(h), forma(g)
    print(f'\nDRUGIE ZRODLO — forma z ostatnich meczow (N {nh}/{ng}), niezalezna od modelu:')
    if min(nh, ng) < DZ_MIN_MECZOW:
        print(f'  BRAK DRUGIEGO ZRODLA (mniej niz {DZ_MIN_MECZOW} meczow jednej z druzyn) — ZADNA noga z tego meczu NIE idzie na kupon.')
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
    print(f'  ZGODNE → P do kuponu {min(pm, pf_tego):.1%} ({fm}; mniejsze z dwoch)')
    print('  Zasada (Poprawka 51): gdy liga jest tez w arkuszu statystyk, noga musi byc zgodna rowniez z sezon.py.')
    return min(pm, pf_tego)


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



def main(a):
    if a[0] == 'wynik':
        row = dict(data=a[1], sport=a[2].lower(), liga=a[3], gosp=a[4], gosc=a[5], pg=float(a[6]), pa=float(a[7]),
                   dogrywka=int(a[8]) if len(a) > 8 else 0)
        pd.DataFrame([row]).to_csv(DB, mode='a', header=not os.path.exists(DB), index=False); print('dopisano', row)
    elif a[0] == 'backtest':
        d = load(); cals = [c for sp in sorted(d.sport.unique()) for c in [backtest(d, sp)] if c is not None]
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
            t = pd.read_csv(TAB); print('\nTabele lig (siła startowa):'); print(t.groupby(['sport', 'liga']).agg(druzyn=('druzyna', 'size'), sezon=('sezon', 'max')).to_string())
    elif a[0] == 'typuj':
        sport = a[1].lower(); d = load(); inf = {}; R, N, hfa, draws, pdraw = elo(d, sport, info=inf); L_ = inf['last']
        pool = set(R); h, g = resolve(a[2], pool), resolve(a[3], pool)
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
        hf = 0 if '--neutral' in a else hfa
        today = pd.Timestamp.today().normalize()
        for t in (h, g):  # ostatnie dane > 90 dni temu = nowy sezon → regresja 1/3 do średniej (jak w pętli Elo)
            if t in R and t in L_ and (today - L_[t]).days > 90: R[t] = 1500 + (R[t] - 1500) * 0.67
        e = 1 / (1 + 10 ** ((R.get(g, 1500) - R.get(h, 1500) - hf) / 400))
        print(f'{sport}: {h} (Elo {R.get(h, 1500):.0f}, {N.get(h, 0)} m.) – {g} (Elo {R.get(g, 1500):.0f}, {N.get(g, 0)} m.)')
        for t in (h, g):
            if t in inf['seeded']: print(f'  {t}: siła startowa z tabeli ligi {inf["seeded"][t]} (+ wyniki dopisane później)')
        ec, note = calibrate(sport, e)
        prm = (__import__('json').load(open(PARAM)) if os.path.exists(PARAM) else {}).get(sport)
        if prm and not draws:
            from scipy.stats import norm as _nd
            M = marza(d, sport, prm); pm_ = M.get(h, 0.) - M.get(g, 0.) + (0 if '--neutral' in a else prm['hfa'])
            p_m = float(_nd.cdf(pm_ / prm['sd'])); lg_ = lambda p: np.log(min(max(p, 1e-6), 1 - 1e-6) / (1 - min(max(p, 1e-6), 1 - 1e-6)))
            z = prm['w_elo'] * lg_(e) + (1 - prm['w_elo']) * lg_(p_m); z = prm['platt'][0] * z + prm['platt'][1]
            ec = float(1 / (1 + np.exp(-z)))
            print(f'  v5n: przewidywana różnica punktów {pm_:+.1f} (odch. std {prm["sd"]:.1f}); P Elo {e:.1%}, P marży {p_m:.1%}')
            note = (f'v5n: zespół Elo + marża punktowa, kalibracja Platta (test od {prm["test_od"]}: logloss '
                    f'{prm["logloss_obecny"]:.4f} → {prm["logloss_nowy"]:.4f})')
        if draws:
            for k_, p in (('1 (60 min / regulaminowy czas)', ec * (1 - pdraw)), ('X', pdraw), ('2', (1 - ec) * (1 - pdraw)),
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
        drugie_zrodlo(d, sport, h, g, ec)
        stale = [t for t in (h, g) if t in L_ and (pd.Timestamp.today() - L_[t]).days > 150]
        if stale: print('  OSTRZEŻENIE: ostatni mecz w bazie >150 dni temu dla:', ', '.join(stale), '— sprawdź transfery/formę w sieci, korekta maks. ±6 pp.')
        print(f'  {note}')
        if n < 5:
            print(f'  BRAK DANYCH RYWALA: najslabiej opisana druzyna ma {n} mecz(e) w bazie. Elo jest')
            print(f'  wtedy bliskie domyslnemu 1500, wiec powyzsze P nie jest pomiarem, tylko artefaktem')
            print(f'  braku danych. NIE buduj na tym nogi kuponu, nawet jesli EV wychodzi wysokie.')
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
            print(f'  odeszlo od startowych 1500. Rozstep jest scisniety KU SRODKOWI: P faworyta jest')
            print(f'  zanizone, P slabszego zawyzone, tym bardziej im wieksza roznica klas.')
            print(f'  Wysokie EV na SLABSZEJ druzynie jest tu artefaktem, nie przewaga — nie graj go.')
            print(f'  P faworyta traktuj jako DOLNA granice. Mecze wyrownane sa wiarygodniejsze.')
    elif a[0] == 'typ':
        row = dict(data=a[1], sport=a[2].lower(), gosp=a[3], gosc=a[4], rynek=a[5], p=float(a[6]), trafiony=None)
        pd.DataFrame([row]).to_csv(LOG, mode='a', header=not os.path.exists(LOG), index=False); print('zapisano', row)
    elif a[0] == 'rozlicz':
        if not os.path.exists(LOG): sys.exit('brak prognoz')
        L = pd.read_csv(LOG); d = load()
        key = {(str(r.data.date()), r.sport, norm(r.gosp), norm(r.gosc)): r for r in d.itertuples()}
        for i, r in L[L.trafiony.isna()].iterrows():
            x = key.get((str(r.data)[:10], r.sport, norm(r.gosp), norm(r['gosc'])))
            if x is None: continue
            reg_draw = bool(x.dogrywka) or x.pg == x.pa
            m = str(r.rynek)
            hit = {'1': x.pg > x.pa, '2': x.pa > x.pg, 'X': reg_draw, '1_60min': (x.pg > x.pa) and not reg_draw,
                   '2_60min': (x.pa > x.pg) and not reg_draw}.get(m)
            if hit is not None: L.loc[i, 'trafiony'] = int(hit)
        L.to_csv(LOG, index=False)
        done = L.dropna(subset=['trafiony'])
        if done.empty: print('brak rozliczonych'); return
        rows = []
        for sp, g in done.groupby('sport'):
            g = g.sort_values('p'); q = np.array_split(np.arange(len(g)), max(1, min(10, len(g) // 40)))
            for i in q: rows.append((sp, g.p.values[i].mean(), g.trafiony.values[i].mean(), len(i)))
            print(f'{sp}: {len(g)} prognoz, średnie P {g.p.mean():.1%}, trafność {g.trafiony.mean():.1%}')
        c = pd.DataFrame(rows, columns=['sport', 'p_model', 'p_kalibr', 'n'])
        c['p_kalibr'] = c.groupby('sport').p_kalibr.transform(lambda s: np.maximum.accumulate(s.values))
        c.to_csv(CAL, index=False, float_format='%.4f')


if __name__ == '__main__':
    main(sys.argv[1:] or ['stan'])
