"""NAUKA DOPASOWAN NAZW (01.10.2026): nazwa z oferty STS -> nazwa w bazie, wyuczona z DOWODOW, nie z podobienstwa napisu.

Zrodla dowodow (pliki z Apps Script w zewn/): wyniki_*_RRRR-MM.csv.gz (Flashscore, 365scores, Liga Pro) i
terminarz_fs/365.csv.gz (z godzina UTC). Zdarzenia STS: kursy z oferta.py (data, godzina PL, sport, gospodarz, gosc).

Dwie metody, obie wymagaja JEDNOZNACZNOSCI:
  KOTWICA — jedna strona zdarzenia jest rozpoznana kodem produkcyjnym (resolver danego sportu), jej nazwa w zrodle jest
            do niej podobna, a ta druzyna grala w dniu meczu (data PL albo UTC godziny z oferty — BEZ okna +-1 dnia:
            dzien wczesniej ta sama druzyna grala z kims innym) DOKLADNIE jeden mecz, po tej samej stronie boiska.
            Rywal w zrodle = druga strona z oferty.
  GODZINA — mecz w terminarzu o tej samej godzinie (+-5 min), obie nazwy podobne, para jedna.
Alias jest PEWNY, gdy: jeden cel dla nazwy, cel jest nazwa z puli bazy, znaczniki (kobiety/rezerwy/U21) rowne, nazwa
z oferty ani cel nie jest krajem (reprezentacje ma sciezka --intl), oraz nazwy sa podobne albo dowody sa >= 2 (rozne dni/mecze).
Sporty osobowe (tenis, dart, snooker…) — tylko nazwy podobne. Alias skracajacy z kolizja rdzenia w puli -> przeglad. Sprzecznosci (resolver wskazal INNA druzyne niz dowod)
NIE nadpisuja niczego — ida do raportu (konflikty) do recznej oceny.

Uzycie:  python3 dopasuj.py auto KURSY.csv.gz   (w przebiegu po oferta.py: aliasy_auto.csv, wczytywany przez typuj/sporty)
         python3 dopasuj.py liga KURSY.csv.gz [--wyjscie aliasy_liga.csv]   (kotwica ligowa — mecze jeszcze bez wyniku)
         python3 dopasuj.py ucz KURSY.csv.gz [--zewn KATALOG] [--wyjscie aliasy_nauczone.csv] [--konflikty PLIK.csv]
                                    [--przeglad dopasuj_przeglad.csv]
Wynik: aliasy_nauczone.csv w formacie aliasy.csv (modul,nazwa,cel,uzasadnienie,data) — do dopisania do aliasy.csv
(dziala tylko, gdy cel jest w puli; aliasy w kodzie wygrywaja)."""
import collections
import functools
import itertools
import glob
import io
import contextlib
import os
import re
import sys
import unicodedata

import pandas as pd

import nazwy

HERE = os.path.dirname(os.path.abspath(__file__))

SPORT_STS = {'PIŁKA NOŻNA': 'pilka', 'HOKEJ NA LODZIE': 'hokej', 'KOSZYKÓWKA': 'koszykówka', 'PIŁKA RĘCZNA': 'piłka ręczna',
             'SIATKÓWKA': 'siatkówka', 'BASEBALL': 'baseball', 'FUTBOL AMERYKAŃSKI': 'futbol amerykański', 'RUGBY': 'rugby',
             'FUTSAL': 'futsal', 'DART': 'dart', 'SNOOKER': 'snooker', 'PIŁKA WODNA': 'piłka wodna',
             'TENIS STOŁOWY': 'tenis stołowy', 'BADMINTON': 'badminton'}
SPORT_ZRODLA = {'football': 'pilka', 'hockey': 'hokej', 'ice-hockey': 'hokej', 'basketball': 'koszykówka',
                'handball': 'piłka ręczna', 'volleyball': 'siatkówka', 'baseball': 'baseball', 'american-football': 'futbol amerykański',
                'a-football': 'futbol amerykański', 'rugby': 'rugby', 'rugby-union': 'rugby', 'rugby-league': 'rugby',
                'futsal': 'futsal', 'darts': 'dart', 'snooker': 'snooker', 'water-polo': 'piłka wodna', 'waterpolo': 'piłka wodna',
                'table-tennis': 'tenis stołowy', 'badminton': 'badminton'}
OSOBOWE = {'dart', 'snooker', 'tenis stołowy', 'badminton'}
TOLERANCJA_MIN = 5

# czlony bez znaczenia przy porownaniu (formy prawne, nazwy sportu); znaczniki kobiet/rezerw porownuje nazwy.znaczniki
OGOLNE = set('fc sc hc bk if ik kk sk ac as cd cf ud fk nk hk bc bm tsv sv vfl vfb ev ehc ec club cb hbc kh ks mks gks '
             'basket basketball handball volley team the de la el del al and afc sd ad ca rc us w k women '
             'hf il ff hb asd bbk umf'.split())


def _ascii(s):
    return unicodedata.normalize('NFKD', str(s).translate(nazwy.LITERY)).encode('ascii', 'ignore').decode().lower()


@functools.lru_cache(maxsize=1)
def _kraje():
    with contextlib.redirect_stdout(io.StringIO()):
        import typuj
    return typuj._KRAJE_PL, typuj.norm


@functools.lru_cache(maxsize=None)
def tokeny(n):
    """Znaczace czlony nazwy: ASCII, male litery, polskie nazwy miast i krajow przetlumaczone (Bukareszt -> Bucharest)."""
    kraje, norm = _kraje()
    kr = kraje.get(norm(re.sub(r'\s*[\[(].*$', '', str(n))))
    s = nazwy.egzonim(str(n), lambda c: re.sub(r'[^a-z]', '', _ascii(c)))
    if kr: s += ' ' + ' '.join(kr)
    return frozenset({t for t in re.split(r'[^a-z0-9]+', _ascii(s)) if t and t not in OGOLNE})


@functools.lru_cache(maxsize=None)
def podobne(a, b):
    """Wspolny czlon >= 3 litery albo skrot (prefiks >= 3 litery: „Din.” = Dinamo, „Atl.” = Atletico)."""
    for x in tokeny(a):
        for y in tokeny(b):
            k, d = (x, y) if len(x) <= len(y) else (y, x)
            if len(k) >= 3 and d.startswith(k): return True
    return False


@functools.lru_cache(maxsize=1)
def _kraje_wszystkie():
    kraje, norm = _kraje()
    return set(kraje) | {norm(x) for v in kraje.values() for x in v}


def jest_krajem(n):
    _, norm = _kraje()
    return norm(re.sub(r'\s*[\[(].*$', '', str(n))) in _kraje_wszystkie()


def zdarzenia_sts(kursy):
    """Kursy z oferta.py -> jedno zdarzenie na mecz: sport (nazwa bazy), data, dni (PL i UTC), A, B."""
    k = kursy[kursy.gospodarz.notna() & kursy.gosc.notna() & kursy.sport.isin(SPORT_STS)]
    e = k.drop_duplicates(['sport', 'data_meczu', 'gospodarz', 'gosc']).copy()
    e['S'] = e.sport.map(SPORT_STS)
    e['d'] = pd.to_datetime(e.data_meczu).dt.normalize()
    e['t'] = pd.to_datetime(e.data_meczu + ' ' + e.godzina_meczu.fillna(''), errors='coerce') - pd.Timedelta(hours=2)
    e['dni'] = [frozenset({d, t.normalize()}) if pd.notna(t) else frozenset({d}) for d, t in zip(e.d, e.t)]
    return e.rename(columns={'gospodarz': 'A', 'gosc': 'B'})[['S', 'd', 't', 'dni', 'A', 'B']].reset_index(drop=True)


def zrodla(katalog):
    """Mecze ze zrodel (wyniki i terminarze): S, d, t (UTC albo NaT), gosp, gosc, zrodlo."""
    cz = []
    for f in sorted(glob.glob(os.path.join(katalog, 'wyniki_*_20??-??.csv.gz'))) + \
            sorted(glob.glob(os.path.join(katalog, 'terminarz_*.csv.gz'))):
        x = pd.read_csv(f, dtype=str)
        if not {'data', 'sport', 'gosp', 'gosc'} <= set(x.columns): continue
        x['zrodlo'] = os.path.basename(f).split('.')[0]
        x['godzina_utc'] = x.get('godzina_utc')
        cz.append(x[['data', 'godzina_utc', 'sport', 'gosp', 'gosc', 'zrodlo']])
    if not cz: return pd.DataFrame(columns=['S', 'd', 't', 'gosp', 'gosc', 'zrodlo'])
    z = pd.concat(cz, ignore_index=True)
    z['S'] = z.sport.map(SPORT_ZRODLA)
    z = z.dropna(subset=['S', 'gosp', 'gosc'])
    z['d'] = pd.to_datetime(z.data, errors='coerce').dt.normalize()
    z['t'] = pd.to_datetime(z.data + ' ' + z.godzina_utc.fillna(''), errors='coerce')
    return z.dropna(subset=['d']).drop_duplicates(['S', 'd', 'gosp', 'gosc'])[['S', 'd', 't', 'gosp', 'gosc', 'zrodlo']]


def ucz(ev, z, rozwiaz, pule):
    """ev: zdarzenia_sts, z: zrodla, rozwiaz(S, nazwa) -> nazwa z puli albo None (kod produkcyjny),
    pule: {S: zbior nazw bazy}. Zwraca (aliasy, konflikty, statystyka)."""
    pod_dniu = collections.defaultdict(list)
    for x in z.itertuples(index=False): pod_dniu[(x.S, x.d)].append(x)
    pam = {}

    def ent(S, n):
        if (S, n) not in pam: pam[(S, n)] = n if n in pule.get(S, ()) else rozwiaz(S, n)
        return pam[(S, n)]

    def cel_w_puli(S, n):
        """nazwa ze zrodla -> nazwa z puli: dokladnie ta sama albo rozpoznana resolverem, ale podobna i z tymi samymi znacznikami"""
        if n in pule.get(S, ()): return n
        e = ent(S, n)
        return e if e and podobne(n, e) and nazwy.znaczniki(n) == nazwy.znaczniki(e) else None

    dowody = collections.defaultdict(collections.Counter)
    przyklad = {}
    konflikty, stat = [], collections.Counter()
    for r in ev.itertuples(index=False):
        if r.S not in pule: continue
        mecze = [x for d in r.dni for x in pod_dniu.get((r.S, d), [])]
        eA, eB = ent(r.S, r.A), ent(r.S, r.B)
        # KOTWICA — 04.10.2026 (Raport 15:00 usterka 7: 18 „KONFLIKT z resolverem” w Setka Cup): nie w sportach osobowych.
        # Zawodnik gra tam kilka meczow dziennie, a wyniki dnia sa czesciowe, wiec jedyny ROZEGRANY dotad mecz nie jest
        # meczem z oferty (Pysmennyi – Dukhovenko wobec rozegranego Pysmennyi – Reznychenko). Zostaje dowod GODZINA.
        for kot, ekot, inna, einna, gosp in ((r.A, eA, r.B, eB, True), (r.B, eB, r.A, eA, False)):
            if not ekot or r.S in OSOBOWE: continue
            po_str = [x for x in mecze if podobne(kot, x.gosp if gosp else x.gosc) and ent(r.S, x.gosp if gosp else x.gosc) == ekot]
            odwr = [x for x in mecze if podobne(kot, x.gosc if gosp else x.gosp) and ent(r.S, x.gosc if gosp else x.gosp) == ekot]
            pary = {(x.gosp, x.gosc) for x in po_str}
            if len(pary) != 1 or odwr: continue
            x = po_str[0]
            rn = x.gosc if gosp else x.gosp
            if nazwy.znaczniki(inna) != nazwy.znaczniki(rn): stat['rozne znaczniki'] += 1; break
            cel = cel_w_puli(r.S, rn)
            if einna:
                if cel and cel != einna:
                    konflikty.append((r.S, str(r.d.date()), r.A, r.B, inna, einna, rn, cel, x.zrodlo)); stat['KONFLIKT'] += 1
                else: stat['potwierdzone'] += 1
            elif cel:
                dowody[(r.S, inna)][(cel, podobne(inna, rn))] += 1
                przyklad.setdefault((r.S, inna), f'{r.A} - {r.B} {r.d.date()} ({x.zrodlo}: {x.gosp} - {x.gosc})')
                stat['kotwica'] += 1
            break
        # GODZINA (terminarz)
        if pd.notna(r.t) and not (eA and eB):
            k = [x for x in mecze if pd.notna(x.t) and abs((x.t - r.t).total_seconds()) <= TOLERANCJA_MIN * 60
                 and podobne(r.A, x.gosp) and podobne(r.B, x.gosc)
                 and nazwy.znaczniki(r.A) == nazwy.znaczniki(x.gosp) and nazwy.znaczniki(r.B) == nazwy.znaczniki(x.gosc)]
            if len({(x.gosp, x.gosc) for x in k}) == 1:
                x = k[0]
                for n, e, rn in ((r.A, eA, x.gosp), (r.B, eB, x.gosc)):
                    cel = cel_w_puli(r.S, rn)
                    if not e and cel:
                        dowody[(r.S, n)][(cel, True)] += 1
                        przyklad.setdefault((r.S, n), f'{r.A} - {r.B} {r.d.date()} godz. ({x.zrodlo}: {x.gosp} - {x.gosc})')
                        stat['godzina'] += 1
    out, przeglad = [], []
    for (S, n), c in sorted(dowody.items()):
        cele = {cel for cel, _ in c}
        if len(cele) != 1: stat['odrzucone: kilka celow'] += 1; continue
        cel = cele.pop(); ile = sum(c.values()); pod = any(p for _, p in c)
        # kraj <-> klub w zadna strone: „Kuwejt” -> „Kuwait SC” i „Al-Kuwait SC” -> „Kuwait” (reprezentacja; nauka 01.10)
        if jest_krajem(n) or jest_krajem(cel): stat['odrzucone: kraj'] += 1; continue
        if nazwy.znaczniki(n) != nazwy.znaczniki(cel): stat['odrzucone: znaczniki'] += 1; continue
        if not (pod or (ile >= 2 and S not in OSOBOWE)): stat['odrzucone: niepodobne, 1 dowod'] += 1; continue
        kol = kolizja(n, cel, pule.get(S, ()))
        if kol:
            przeglad.append((S, n, cel, ile, przyklad[(S, n)], '; '.join(kol[:5]))); stat['do przegladu: skrot z kolizja'] += 1; continue
        out.append((S, n, cel, ile, przyklad[(S, n)]))
    a = pd.DataFrame(out, columns=['S', 'nazwa', 'cel', 'dowody', 'przyklad'])
    a.attrs['przeglad'] = pd.DataFrame(przeglad, columns=['S', 'nazwa', 'cel', 'dowody', 'przyklad', 'inne_z_rdzeniem'])
    k = pd.DataFrame(konflikty, columns=['S', 'data', 'A', 'B', 'nazwa', 'kod_dal', 'zrodlo_nazwa', 'zrodlo_cel', 'zrodlo'])
    return a, k.drop_duplicates(['S', 'nazwa', 'kod_dal', 'zrodlo_cel']), stat


def kolizja(nazwa, cel, pula):
    """Alias SKRACAJACY (cel zgubil czlon nazwy z oferty, np. miasto: „Torpedo Ust-Kamenogorsk” -> „Torpedo”) jest
    poprawny dzis, ale nie musi byc jednoznaczny jutro. Gdy w puli jest INNY wpis z calym rdzeniem celu i tymi samymi
    znacznikami („Torpedo Nizhny Novgorod”, „Racing Club Montevideo”), alias idzie do recznego przegladu, nie do
    aliasy.csv. Zwraca liste takich wpisow (pusta = bez kolizji)."""
    tn, tc = tokeny(nazwa), tokeny(cel)
    zgub = {x for x in tn if not any(x.startswith(y) or y.startswith(x) for y in tc if min(len(x), len(y)) >= 3)}
    if not zgub or not tc: return []
    zn = nazwy.znaczniki(cel)
    return sorted(p for p in pula if p != cel and tc <= tokeny(p) and nazwy.znaczniki(p) == zn)


def jako_aliasy(a, dzis):
    """Wiersze w formacie aliasy.csv: pilka -> modul typuj, inne sporty -> modul sporty."""
    return pd.DataFrame({'modul': ['typuj' if s == 'pilka' else 'sporty' for s in a.S], 'nazwa': a.nazwa, 'cel': a.cel,
                         'uzasadnienie': [f'nauka {s}: {k} dowod(y), np. {p}' for s, k, p in zip(a.S, a.dowody, a.przyklad)],
                         'data': dzis})


def _rdzen_pasuje(ta, tb):
    """Jedna nazwa zawiera wszystkie znaczace czlony drugiej (prefiks >= 4 litery: „Lubbecke” w „N-Lubbecke”), albo sa
    tym samym napisem bez spacji („Orange Academy” = „OrangeAcademy”). Wymagany wspolny czlon >= 4 litery."""
    if not ta or not tb: return False
    razem = lambda t: {''.join(x) for x in itertools.permutations(sorted(t))} if len(t) <= 4 else {''.join(sorted(t))}
    if razem(ta) & razem(tb): return True
    mn, mx = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    zgodne = lambda x: any(x == y or (min(len(x), len(y)) >= 4 and (x.startswith(y) or y.startswith(x))) for y in mx)
    return all(zgodne(x) for x in mn) and any(len(x) >= 4 for x in mn)


def ligi_druzyn(mecze):
    """mecze: DataFrame z kolumnami S, liga, A, B -> {(S, druzyna): {ligi}}."""
    out = collections.defaultdict(set)
    for S, l, a, b in zip(mecze.S, mecze.liga, mecze.A, mecze.B):
        if isinstance(l, str):
            out[(S, a)].add(l); out[(S, b)].add(l)
    return out


def kotwica_ligowa(ev, rozwiaz, pule, ligi, bez_kolizji=False):
    """03.10.2026: druga metoda nauki, gdy mecz z oferty nie ma jeszcze wyniku w zrodlach. Jedna strona zdarzenia jest
    rozpoznana kodem produkcyjnym; druga NIE. Kandydat = wpis z puli, ktorego znaczace czlony zawieraja sie w nazwie
    z oferty (albo odwrotnie: „Medi Bayreuth” -> „Bayreuth”, „Black Wings Linz” -> „EHC Liwest Black Wings Linz”),
    z tymi samymi znacznikami i grajacy w ostatnim roku w TEJ SAMEJ lidze co rozpoznany rywal. Alias tylko gdy kandydat
    jest JEDEN i wszystkie zdarzenia z ta nazwa wskazuja ten sam cel. Reprezentacje pomijane (sciezka --intl).
    bez_kolizji=True (tryb auto): alias skracajacy z kolizja rdzenia w puli (kolizja()) odpada — w parze odpadaja oba
    („Virtus Zagreb” -> „KK Zagreb”: w puli Cedevita/Dinamo/Cibona Zagreb; razem z nim „Furnir Dubrava”)."""
    dow, stat, przyk = collections.defaultdict(collections.Counter), collections.Counter(), {}

    def kand(S, n, L=None, bez=None):
        tn, zn = tokeny(n), nazwy.znaczniki(n)
        return [p for p in pule[S] if p != bez and (L is None or ligi.get((S, p), set()) & L)
                and nazwy.znaczniki(p) == zn and _rdzen_pasuje(tn, tokeny(p))]

    for r in ev.itertuples(index=False):
        if r.S not in pule or jest_krajem(r.A) or jest_krajem(r.B): continue
        ra, rb = rozwiaz(r.S, r.A), rozwiaz(r.S, r.B)
        if ra is not None and rb is not None: continue
        if ra is None and rb is None:
            # PARA: obie strony nierozpoznane — dokladnie jedna para kandydatow ze wspolna liga
            pary = [(a, b) for a in kand(r.S, r.A) for b in kand(r.S, r.B, bez=a)
                    if ligi.get((r.S, a), set()) & ligi.get((r.S, b), set())]
            if len(pary) != 1: stat['para: kandydatow 0' if not pary else 'para: kilka par'] += 1; continue
            a, b = pary[0]
            if bez_kolizji and (kolizja(r.A, a, pule[r.S]) or kolizja(r.B, b, pule[r.S])): stat['kolizja (do przegladu)'] += 1; continue
            L = ligi[(r.S, a)] & ligi[(r.S, b)]
            for n, c in ((r.A, a), (r.B, b)):
                dow[(r.S, n)][c] += 1
                przyk.setdefault((r.S, n), f'{r.A} - {r.B} {r.d.date()}: para {a} - {b}, liga {", ".join(sorted(L))[:60]}')
            continue
        n, ri = (r.A, rb) if ra is None else (r.B, ra)
        L = ligi.get((r.S, ri), set())
        if not L: stat['brak ligi rywala'] += 1; continue
        k = kand(r.S, n, L, ri)
        if len(k) == 1 and bez_kolizji and kolizja(n, k[0], pule[r.S]): stat['kolizja (do przegladu)'] += 1; continue
        if len(k) == 1:
            dow[(r.S, n)][k[0]] += 1
            przyk.setdefault((r.S, n), f'{r.A} - {r.B} {r.d.date()}: rywal {ri}, liga {", ".join(sorted(L & ligi[(r.S, k[0])]))[:60]}')
        else:
            stat['kandydatow 0' if not k else 'kandydatow wiele'] += 1
    out = []
    for (S, n), c in sorted(dow.items()):
        if len(c) != 1: stat['sprzeczne cele'] += 1; continue
        cel, ile = next(iter(c.items()))
        out.append((S, n, cel, ile, przyk[(S, n)])); stat['alias'] += 1
    return pd.DataFrame(out, columns=['S', 'nazwa', 'cel', 'dowody', 'przyklad']), stat


def _mecze_lig(dni=400):
    """Ligi druzyn z bazy: pilka z kb.sqlite (Division), reszta z sporty.load() (liga) — ostatnie dni."""
    with contextlib.redirect_stdout(io.StringIO()):
        import typuj
        import sporty
        od = pd.Timestamp.today() - pd.Timedelta(days=dni)
        m = pd.read_sql('select MatchDate, Division, HomeTeam, AwayTeam from matches', typuj.db(), parse_dates=['MatchDate'])
        m = m[m.MatchDate >= od]
        d = sporty.load(); d = d[d.data >= od]
    cz = [pd.DataFrame({'S': 'pilka', 'liga': m.Division, 'A': m.HomeTeam, 'B': m.AwayTeam})]
    for s in set(SPORT_STS.values()) - {'pilka'}:
        x = d[d.sport == sporty.nazwa_sportu(s)]
        cz.append(pd.DataFrame({'S': s, 'liga': x.liga, 'A': x.gosp, 'B': x.gosc}))
    return pd.concat(cz, ignore_index=True)


def _produkcja():
    """Resolvery i pule z kodu produkcyjnego (typuj — pilka, sporty — reszta)."""
    with contextlib.redirect_stdout(io.StringIO()):
        import typuj
        import sporty
        con = typuj.db()
        m = pd.read_sql('select HomeTeam, AwayTeam from matches', con)
        typuj.wczytaj_warianty(con)
        d = sporty.load()
    pule = {'pilka': set(m.HomeTeam) | set(m.AwayTeam)}
    for s in set(SPORT_STS.values()) - {'pilka'}:
        x = d[d.sport == sporty.nazwa_sportu(s)]
        if len(x): pule[s] = {p for p in set(x.gosp) | set(x.gosc) if isinstance(p, str)}

    def rozwiaz(S, n):
        with contextlib.redirect_stdout(io.StringIO()):
            if S == 'pilka': return typuj.resolve(n, pule['pilka']) or typuj._przez_egzonim(n, pule['pilka'])
            return sporty.resolve(n, pule[S], sporty.nazwa_sportu(S))
    return rozwiaz, pule


def auto(kursy, zewn, wyjscie):
    """03.10.2026 (prosba uzytkownika: nazwy maja ZAWSZE pasowac): uczenie w kazdym przebiegu, bez recznego kroku.
    Do aliasy_auto.csv (wczytywany po aliasy.csv — reczne wpisy wygrywaja) trafiaja tylko:
      (1) aliasy PEWNE z ucz() (ten sam mecz w zrodle wynikow; bez skrotow z kolizja),
      (2) kotwica ligowa bez kolizji rdzenia (dwa przejscia — nowe aliasy daja kotwice kolejnym meczom).
    Konflikty z resolverem i kolizje — tylko do raportu. Zwraca (aliasy, stat, linie raportu)."""
    ev = zdarzenia_sts(pd.read_csv(kursy, dtype=str))
    rozwiaz, pule = _produkcja()
    with contextlib.redirect_stdout(io.StringIO()):
        import typuj
        import sporty
    slownik = {'typuj': (typuj.ALIASES, typuj.norm), 'sporty': (sporty._ALIASY_RECZNE, sporty.norm)}

    def zastosuj(df):
        for r in df.itertuples(index=False):
            d, kl = slownik[r.modul]
            d.setdefault(kl(r.nazwa), r.cel)
            if r.modul == 'sporty': sporty._ALIASY_WIELE.setdefault(kl(r.nazwa), []).append(r.cel)
    dzis = pd.Timestamp.today().strftime('%Y-%m-%d')
    al, kon, stat = ucz(ev, zrodla(zewn), rozwiaz, pule)
    wynik = [jako_aliasy(al, dzis)]
    zastosuj(wynik[0])
    ligi = ligi_druzyn(_mecze_lig())
    for i in (1, 2):
        lg, st = kotwica_ligowa(ev, rozwiaz, pule, ligi, bez_kolizji=True)
        stat.update({f'liga {k}': v for k, v in st.items()})
        if lg.empty: break   # 03.10: pusty wynik wywracal .str na kolumnie bez napisow
        lg = jako_aliasy(lg, dzis)
        lg['uzasadnienie'] = [u.replace('nauka ', 'kotwica ligowa ', 1) for u in lg.uzasadnienie]
        juz = {(m, n) for w in wynik for m, n in zip(w.modul, w.nazwa)}
        lg = lg[[(m, n) not in juz for m, n in zip(lg.modul, lg.nazwa)]]
        if lg.empty: break
        wynik.append(lg); zastosuj(lg)
    out = pd.concat(wynik, ignore_index=True)
    out.to_csv(wyjscie, index=False)
    linie = [f'NAZWY AUTO: {len(out)} aliasow (wyniki: {len(wynik[0])}, kotwica ligowa: {len(out) - len(wynik[0])}) -> {wyjscie}']
    linie += [f'  do przegladu (skrot z kolizja): {r.nazwa} -> {r.cel} [{r.inne_z_rdzeniem}]' for r in al.attrs['przeglad'].itertuples()]
    linie += [f'  KONFLIKT z resolverem: {r.nazwa} -> kod {r.kod_dal}, zrodlo {r.zrodlo_cel} ({r.zrodlo})' for r in kon.itertuples()]
    return out, stat, linie


def main(a):
    if not a or a[0] not in ('ucz', 'liga', 'auto'): sys.exit(__doc__)
    arg = lambda k, d: a[a.index(k) + 1] if k in a else d
    if a[0] == 'auto':
        _, stat, linie = auto(a[1], arg('--zewn', os.path.join(HERE, 'zewn')), arg('--wyjscie', nazwy.ALIASY_AUTO_CSV))
        for k, v in sorted(stat.items()): print(f'  {k}: {v}')
        print('\n'.join(linie))
        return
    if a[0] == 'liga':
        ev = zdarzenia_sts(pd.read_csv(a[1], dtype=str))
        rozwiaz, pule = _produkcja()
        al, stat = kotwica_ligowa(ev, rozwiaz, pule, ligi_druzyn(_mecze_lig()))
        for k, v in sorted(stat.items()): print(f'  {k}: {v}')
        print(f'ALIASY Z KOTWICY LIGOWEJ: {len(al)} (do przejrzenia przed dopisaniem do aliasy.csv)')
        w = jako_aliasy(al, pd.Timestamp.today().strftime('%Y-%m-%d'))
        w['uzasadnienie'] = [u.replace('nauka ', 'kotwica ligowa ', 1) for u in w.uzasadnienie]
        w.to_csv(arg('--wyjscie', 'aliasy_liga.csv'), index=False)
        return
    ev = zdarzenia_sts(pd.read_csv(a[1], dtype=str))
    z = zrodla(arg('--zewn', os.path.join(HERE, 'zewn')))
    rozwiaz, pule = _produkcja()
    al, kon, stat = ucz(ev, z, rozwiaz, pule)
    print(f'zdarzen STS {len(ev)}, meczow w zrodlach {len(z)}')
    for k, v in sorted(stat.items()): print(f'  {k}: {v}')
    print(f'ALIASY PEWNE: {len(al)}   DO PRZEGLADU (skrot z kolizja): {len(al.attrs["przeglad"])}   '
          f'KONFLIKTY (do recznej oceny): {len(kon)}')
    al.attrs['przeglad'].to_csv(arg('--przeglad', 'dopasuj_przeglad.csv'), index=False)
    jako_aliasy(al, pd.Timestamp.today().strftime('%Y-%m-%d')).to_csv(arg('--wyjscie', 'aliasy_nauczone.csv'), index=False)
    kon.to_csv(arg('--konflikty', 'dopasuj_konflikty.csv'), index=False)


if __name__ == '__main__':
    main(sys.argv[1:])
