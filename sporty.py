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
    if not os.path.exists(TAB): return []
    t = pd.read_csv(TAB); t = t[(t.sport == sport) & (t.gp > 0)]
    out = []
    for r in t.itertuples():
        wp = (r.w + r.otw + 0.5 * r.d) / r.gp
        k = PYTH.get(sport, 2.0)
        c = 0.5 * wp + 0.5 * (r.gf ** k / (r.gf ** k + r.ga ** k)) if r.gf + r.ga > 0 else wp
        c = (c * r.gp + 0.5 * 6) / (r.gp + 6); c = min(max(c, 0.03), 0.97)
        out.append((pd.Timestamp(r.data), r.druzyna, 1500 + 400 * np.log10(c / (1 - c)), int(r.gp), r.liga))
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
    return sum(1 for t in re.split(r'[\s]+', str(s).strip())
               if _ZNACZNIK.match(t.strip('[](){}<>.,;:')))


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
    c = [p for p in by.values() if _zaw_nazwy(name, p)]
    if len(c) == 1:
        # gdy nazwa z oferty ma WIECEJ czlonow niz dopasowana, gubimy czlon rozrozniajacy:
        # "Independiente Rivadavia" -> "Independiente" i "Operario Ferroviario" -> "Ferroviario"
        # to INNE kluby. Strukturalnie nie da sie tego odroznic od "Montpellier Handball" ->
        # "Montpellier", wiec zamiast blokowac — mowimy o tym glosno.
        if len(_tokeny(name)) > len(_tokeny(c[0])):
            print(f'  UWAGA: "{name}" dopasowane do KROTSZEJ nazwy "{c[0]}" — pominieto czlon '
                  f'rozrozniajacy. Sprawdz, czy to ten sam klub, a nie inny o podobnej nazwie.')
        return c[0]
    if c:   # pierwszy czlon nazwy jest niemal zawsze wlasciwym klubem
        pref = [p for p in c if k_.startswith(norm(p)) or norm(p).startswith(k_)]
        if len(pref) == 1: return pref[0]
        if pref: return max(pref, key=lambda p: len(norm(p)))
        return min(c, key=lambda p: abs(len(norm(p)) - len(k_)))
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
        d = load(); print(d.groupby('sport').agg(mecze=('gosp', 'size'), od=('data', 'min'), do=('data', 'max')).to_string() if len(d) else 'baza pusta')
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
        stale = [t for t in (h, g) if t in L_ and (pd.Timestamp.today() - L_[t]).days > 150]
        if stale: print('  OSTRZEŻENIE: ostatni mecz w bazie >150 dni temu dla:', ', '.join(stale), '— sprawdź transfery/formę w sieci, korekta maks. ±6 pp.')
        print(f'  {note}')
        if n < 5:
            print(f'  BRAK DANYCH RYWALA: najslabiej opisana druzyna ma {n} mecz(e) w bazie. Elo jest')
            print(f'  wtedy bliskie domyslnemu 1500, wiec powyzsze P nie jest pomiarem, tylko artefaktem')
            print(f'  braku danych. NIE buduj na tym nogi kuponu, nawet jesli EV wychodzi wysokie.')
        elif n < 10:
            print(f'  UWAGA: mało meczów w bazie ({n}) — P to szacunek; opieraj się na statystykach z sieci (MASTER PROMPT część B).')
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
