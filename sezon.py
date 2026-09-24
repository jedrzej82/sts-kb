#!/usr/bin/env python3
"""
sezon.py — prawdopodobieństwa z BIEŻĄCEGO SEZONU/FORMY (arkusze Apps Script „statystyki 365”)
i łączenie ich z P modelu. Dodatek v5m (19.09.2026).

Pliki wejściowe (CSV, pierwsza zakładka arkusza; zapisz w katalogu kb/ pod tymi nazwami):
  statystyki_druzyn.csv (piłka), statystyki_tenis.csv, statystyki_koszykowka.csv, statystyki_siatkowka.csv,
  statystyki_hokej.csv, statystyki_reczna.csv, statystyki_baseball.csv, statystyki_futbol_amerykanski.csv, statystyki_rugby.csv

Użycie:
  python3 sezon.py pilka "Gospodarz" "Gość"            # λ, 1X2, DC, DNB, O/U 0.5–4.5, BTTS, gole drużyn
  python3 sezon.py tenis "Zawodnik A" "Zawodnik B" [--bo5]
  python3 sezon.py kosz "Gospodarz" "Gość" [--linia 165.5] [--handicap -4.5]
  python3 sezon.py siatka "Gospodarz" "Gość"
  python3 sezon.py forma SPORT "Drużyna"                # hokej, reczna, baseball, futbol_amerykanski, rugby, … — sam bilans
  python3 sezon.py polacz P_MODEL P_SEZON N             # P łączone (N = mniejsza liczba meczów ze statystykami obu stron)
  python3 sezon.py druzyny PLIK FRAGMENT                # szukanie nazw

Zasady łączenia (heurystyka startowa — do kalibracji na rozliczeniach):
  waga_sezonu = N / (N + 10), max 0,5  →  N=3: 0,23; N=6: 0,38; N=10+: 0,5
  P = (1 − waga) · P_model + waga · P_sezon
  ROZBIEŻNOŚĆ, gdy |P_model − P_sezon| > 10 pp — typ nie idzie do K1/K2 (reguła użytkownika).
Wszystkie wyniki są orientacyjne; nie używają kursów.
"""
import csv, math, os, sys, unicodedata, difflib

KATALOG = os.path.dirname(os.path.abspath(__file__))
PLIKI = {
    'pilka': 'statystyki_druzyn.csv', 'tenis': 'statystyki_tenis.csv', 'kosz': 'statystyki_koszykowka.csv',
    'koszykowka': 'statystyki_koszykowka.csv', 'siatka': 'statystyki_siatkowka.csv', 'siatkowka': 'statystyki_siatkowka.csv',
    'hokej': 'statystyki_hokej.csv', 'reczna': 'statystyki_reczna.csv', 'baseball': 'statystyki_baseball.csv',
    'futbol_amerykanski': 'statystyki_futbol_amerykanski.csv', 'rugby': 'statystyki_rugby.csv',
}


# ------------------------------------------------------------------ narzędzia
def f(x, d=None):
    try:
        if x is None or str(x).strip() == '':
            return d
        return float(str(x).replace(',', '.'))
    except ValueError:
        return d


def norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    for zb in (' fc', 'fc ', ' cf', ' sc', ' ac', ' afc', ' cp', ' sad', '.', '-', "'"):
        s = s.replace(zb, ' ')
    return ' '.join(s.split())


def wczytaj(sport, plik=None):
    p = plik or os.path.join(KATALOG, PLIKI[sport])
    if not os.path.exists(p):
        sys.exit(f'BRAK PLIKU {p} — pobierz arkusz {os.path.basename(p)[:-4]} jako CSV do kb/')
    with open(p, encoding='utf-8-sig', newline='') as fh:
        return list(csv.DictReader(fh))


def _zaw_czlony(a, b):
    """Zawieranie po CALYCH czlonach, na poczatku albo koncu — jak w typuj.py i sporty.py."""
    ta, tb = a.split(), b.split()
    if not ta or not tb: return False
    d, k = (ta, tb) if len(ta) >= len(tb) else (tb, ta)
    if len(''.join(k)) < 4: return False
    return d[:len(k)] == k or d[-len(k):] == k


# 24.09.2026 (wyd. 27): WYLACZNIE formy prawne i nazwy dyscypliny — tylko takie czlony wolno "zgubic"
# przy dopasowaniu przez zawieranie. Celowo NIE ma tu "club", "cs", "ca", "cd", "de", "la": "Club Nacional"
# (Paragwaj) i "Nacional" (Urugwaj), "CS San Lorenzo" (Paragwaj) i "San Lorenzo" (Argentyna), "Racing Club"
# i "Racing" to rozne kluby (recenzja 24.09).
_OGOLNE = frozenset('fc cf sc ac afc cfc fk nk sk bk hk hc kk rk ok ks sv ss ec fbc sad bc '
                    'basket basketball volley volleyball hockey ishockey handball calcio futbol football fussball '
                    'county rugby ik if'.split())
# polskie nazwy miast z oferty STS -> zapisy zrodlowe (te same co w sporty.py i typuj.py)
_MIASTA_PL = {'madryt': ('madrid',), 'monachium': ('munich', 'munchen', 'muenchen'), 'wieden': ('wien', 'vienna'),
              'lizbona': ('lisbon', 'lisboa'), 'mediolan': ('milan', 'milano'), 'rzym': ('roma', 'rome'),
              'neapol': ('napoli', 'naples'), 'turyn': ('torino', 'turin'), 'ateny': ('athens', 'athina'),
              'sewilla': ('sevilla', 'seville'), 'walencja': ('valencia',), 'stambul': ('istanbul',),
              'kopenhaga': ('copenhagen', 'kobenhavn'), 'bruksela': ('brussels', 'bruxelles'),
              'belgrad': ('belgrade', 'beograd'), 'moskwa': ('moscow', 'moskva'), 'praga': ('prague', 'praha'),
              'bukareszt': ('bucharest', 'bucuresti'), 'sztokholm': ('stockholm',), 'kijow': ('kyiv', 'kiev'),
              'lwow': ('lviv', 'lvov'), 'zagrzeb': ('zagreb',), 'genua': ('genoa', 'genova'),
              'saloniki': ('thessaloniki',), 'pireus': ('piraeus', 'pireas'), 'kowno': ('kaunas',),
              'wilno': ('vilnius',), 'ryga': ('riga',)}


def _tok(s):
    return norm(s).replace('/', ' ').split()


def _tok_osoba(s):
    """Czlony nazwiska: apostrof NIE dzieli nazwiska ("O'Connell" to jeden czlon)."""
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    s = s.replace("'", '').replace('-', ' ').replace('.', ' ')
    return s.split()


def _warianty(nazwa):
    """Nazwa z oferty z polskimi miastami zamienionymi na kazdy zapis zrodlowy (lista list czlonow)."""
    import itertools
    t = _tok(nazwa)
    opcje = [(_MIASTA_PL[x] + (x,)) if x in _MIASTA_PL else (x,) for x in t]
    return [list(k) for k in itertools.product(*opcje)][:64]


def _alias(nazwa):
    """Reczne pary z sporty.py (Poprawki 42–45, zapis 365scores — ten sam co w arkuszach):
    "SE Melbourne Phoenix" -> "South East Melbourne". Aliasow z typuj.py NIE uzywamy: ich cele sa zapisem
    kb.sqlite (klub z innego kraju ma tam przyrostek kraju), a arkusz przyrostkow nie ma — recenzja:
    "Independiente Medellin" -> "Independiente" trafialo w argentynskie Independiente."""
    k_ = ''.join(ch for ch in norm(nazwa) if ch.isalnum())
    try:
        import sporty
        v = getattr(sporty, '_ALIASY_RECZNE', {}).get(k_)
        return [v] if v else []
    except Exception:
        return []


def znajdz(wiersze, nazwa, liga=None, sport=None):
    """22.09.2026: naprawione podstawianie INNEGO meczu ("Nueva Chicago" -> "Chicago Fire").
    24.09.2026 (wyd. 27, po dwoch recenzjach): kolejnosc prob — (1) dokladnie; (2) reczny alias z sporty.py;
    (3) te same czlony w DOWOLNEJ kolejnosci, polskie miasta przetlumaczone ("Cerundolo Juan Manuel",
    "Bayern Monachium"); (3b) polska nazwa miasta pominieta, gdy reszta jest sama rozpoznawalna;
    (4) zawieranie TYLKO gdy odpadly formy prawne (FC, SK, Basket...); (5) wylacznie w tenisie: nazwisko
    + WSZYSTKIE inicjaly. Dopasowania rozmytego (difflib) juz nie ma: "Australia (W)"~"Austria (W)",
    "Andrej Martin"~"Andres Martin" to rozne druzyny/osoby. Brak trafienia = None (noga mniej).
    Gdy podano lige, kandydat musi byc TA SAMA druzyna co przy szukaniu w calym arkuszu (patrz pilka())."""
    cel = norm(nazwa)
    if not cel: return None, 0.0
    kand = [w for w in wiersze if not liga or w.get('liga') == liga]
    mec = lambda w: f(w.get('mecze'), 0) or 0
    dokl = sorted([w for w in kand if norm(w['druzyna']) == cel], key=mec, reverse=True)
    if dokl:   # v5p: ta sama drużyna w lidze i w pucharach → wiersz z największą liczbą meczów (liga krajowa)
        return dokl[0], 1.0
    for al in _alias(nazwa):
        tr = sorted([w for w in kand if norm(w['druzyna']) == norm(al)], key=mec, reverse=True)
        if tr:
            print(f'  „{nazwa}” → „{al}” (para reczna, sporty.py)')
            return tr[0], 1.0
    # (3) te same czlony, dowolna kolejnosc, miasta przetlumaczone
    for war in _warianty(nazwa):
        ws = sorted(war)
        tr = [w for w in kand if sorted(_tok(w['druzyna'])) == ws]
        if len({norm(w['druzyna']) for w in tr}) == 1:
            return max(tr, key=mec), 0.95
        if tr: return None, 0.0                       # kilka roznych druzyn — nie zgadujemy
    # (3b) polska nazwa miasta, ktorej w arkuszu nie ma wcale ("Panathinaikos Ateny" -> "Panathinaikos")
    t0 = [x for x in cel.split() if x not in _MIASTA_PL]
    if len(t0) < len(cel.split()) and (len(t0) >= 2 or (len(t0) == 1 and len(t0[0]) >= 9)):
        tr = [w for w in kand if sorted(_tok(w['druzyna'])) == sorted(t0)]
        if len({norm(w['druzyna']) for w in tr}) == 1:
            return max(tr, key=mec), 0.9
        if tr: return None, 0.0
    # (4) zawieranie: wolno zgubic tylko formy prawne / nazwe dyscypliny
    zaw = []
    for w in kand:
        tw = _tok(w['druzyna'])
        if not _zaw_czlony(cel, ' '.join(tw)): continue
        tc = cel.split()
        dluzsze, krotsze = (tc, tw) if len(tc) >= len(tw) else (tw, tc)
        odp = list(dluzsze)
        for x in krotsze:
            if x in odp: odp.remove(x)
        if odp and all(x in _OGOLNE for x in odp): zaw.append(w)
    if zaw:
        if len({norm(w['druzyna']) for w in zaw}) == 1: return max(zaw, key=mec), 0.9
        return None, 0.0
    # (5) tenis: „Mensik J.” vs „Jakub Mensik” — nazwisko i WSZYSTKIE inicjaly imion
    if sport == 'tenis':
        tq = _tok_osoba(nazwa)
        if len(tq) >= 2:
            tr = []
            for w in kand:
                tw = _tok_osoba(w['druzyna'])
                if len(tw) < 2: continue
                for naz_q, ini_q in ((tq[:1], tq[1:]), (tq[-1:], tq[:-1])):      # "Nazwisko I." albo "I. Nazwisko"
                    for naz_w, im_w in ((tw[-1:], tw[:-1]), (tw[:1], tw[1:])):
                        if naz_q == naz_w and len(ini_q) == len(im_w) and \
                                all(len(i) <= 2 and im.startswith(i) for i, im in zip(ini_q, im_w)):
                            tr.append(w)
            if len({norm(w['druzyna']) for w in tr}) == 1:
                return tr[0], 0.8
    return None, 0.0


def wymagaj(wiersze, nazwa, liga=None, sport=None):
    w, pew = znajdz(wiersze, nazwa, liga, sport)
    if not w:
        sys.exit(f'NIE ZNALEZIONO: „{nazwa}” — sprawdź: python3 sezon.py druzyny <plik> '
                 f'{max(str(nazwa).split(), key=len) if str(nazwa).split() else nazwa}')
    if pew < 1.0:
        print(f'  dopasowano „{nazwa}” → „{w["druzyna"]}” (pewność {pew:.2f})')
    return w


def proc(x):
    return f'{100 * x:5.1f}%'


def pois(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# ------------------------------------------------------------------ piłka
def pilka(a, b):
    W = wczytaj('pilka')
    # p27: najpierw ustal OBIE druzyny globalnie, potem szukaj wspolnej ligi tylko dla TYCH samych nazw
    h0 = wymagaj(W, a)
    g0 = wymagaj(W, b)
    nh, ng = norm(h0['druzyna']), norm(g0['druzyna'])
    if nh == ng:
        raise SystemExit(f'NIE ZNALEZIONO: {a!r} i {b!r} wskazuja te sama druzyne ({h0["druzyna"]}) — pomijam')
    wsp = []
    for lg in {w['liga'] for w in W}:
        hh = [w for w in W if w['liga'] == lg and norm(w['druzyna']) == nh]
        gg = [w for w in W if w['liga'] == lg and norm(w['druzyna']) == ng]
        if len(hh) == 1 and len(gg) == 1:
            wsp.append((min(f(hh[0].get('mecze'), 0), f(gg[0].get('mecze'), 0)), hh[0], gg[0]))
    if wsp:
        _, h, g = max(wsp, key=lambda x: x[0])
    else:
        h, g = h0, g0
        print(f'  UWAGA: drużyny w różnych ligach w arkuszu ({h["liga"]} vs {g["liga"]}) — P_sezon tylko informacyjnie')
    liga = [w for w in W if w['liga'] == h['liga']]
    sd = lambda k: sum(f(w.get(k), 0) for w in liga)
    dm, wm = sd('dom_mecze'), sd('wyj_mecze')
    sr_dom = sd('dom_gz') / dm if dm else 1.45
    sr_wyj = sd('wyj_gz') / wm if wm else 1.15
    sr = (sr_dom + sr_wyj) / 2
    K = 6.0  # siła priorytetu (mecze) — ściąganie do średniej ligi

    def sila(t):
        n = f(t.get('mecze'), 0)
        gz, gs = f(t.get('gole_na_mecz'), sr), f(t.get('stracone_na_mecz'), sr)
        xg, xga = f(t.get('xg_na_mecz')), f(t.get('xg_rywala_na_mecz'))
        atk = (gz + xg) / 2 if xg is not None else gz
        obr = (gs + xga) / 2 if xga is not None else gs
        atk, obr = atk / sr, obr / sr
        return (n * atk + K) / (n + K), (n * obr + K) / (n + K), n

    ah, oh, nh = sila(h)
    ag, og, ng = sila(g)
    lh = sr_dom * ah * og
    lg = sr_wyj * ag * oh
    rho = -0.05
    M = [[0.0] * 11 for _ in range(11)]
    for i in range(11):
        for j in range(11):
            p = pois(i, lh) * pois(j, lg)
            if i == 0 and j == 0: p *= 1 - lh * lg * rho
            elif i == 0 and j == 1: p *= 1 + lh * rho
            elif i == 1 and j == 0: p *= 1 + lg * rho
            elif i == 1 and j == 1: p *= 1 - rho
            M[i][j] = p
    s = sum(map(sum, M))
    M = [[x / s for x in r] for r in M]
    P = lambda war: sum(M[i][j] for i in range(11) for j in range(11) if war(i, j))
    p1, px, p2 = P(lambda i, j: i > j), P(lambda i, j: i == j), P(lambda i, j: i < j)
    n = min(nh, ng)
    print(f'SEZON  {h["druzyna"]} – {g["druzyna"]}  ({h["liga"]}; mecze {int(nh)}/{int(ng)}; '
          f'historia ligi kompletna: {h.get("liga_historia_kompletna","?")}; aktualizacja {h.get("data_aktualizacji","?")})')
    print(f'  λ {lh:.2f} : {lg:.2f}   (śr. ligi dom {sr_dom:.2f}, wyjazd {sr_wyj:.2f}; xG: {"tak" if h.get("xg_na_mecz") else "nie"})')
    print(f'  celne/mecz {h.get("celne_na_mecz")} vs rywale {h.get("celne_rywala_na_mecz")} | '
          f'{g.get("celne_na_mecz")} vs rywale {g.get("celne_rywala_na_mecz")}; obrony/mecz {h.get("obrony_na_mecz")} | {g.get("obrony_na_mecz")}')
    rynki = [('1', p1), ('X', px), ('2', p2), ('1X', p1 + px), ('X2', px + p2), ('12', p1 + p2),
             ('DNB 1', p1 / (p1 + p2)), ('DNB 2', p2 / (p1 + p2))]
    for L in (0.5, 1.5, 2.5, 3.5, 4.5):
        o = P(lambda i, j, L=L: i + j > L)
        rynki += [(f'O{L}', o), (f'U{L}', 1 - o)]
    rynki += [('BTTS tak', P(lambda i, j: i > 0 and j > 0)), ('BTTS nie', P(lambda i, j: i == 0 or j == 0)),
              ('gosp O0.5', P(lambda i, j: i > 0)), ('gosp O1.5', P(lambda i, j: i > 1)),
              ('gość O0.5', P(lambda i, j: j > 0)), ('gość O1.5', P(lambda i, j: j > 1))]
    for nazwa, p in rynki:
        print(f'  {nazwa:10s} {proc(p)}')
    print(f'  N (do łączenia) = {int(n)}   → python3 sezon.py polacz P_MODEL P_SEZON {int(n)}')


# ------------------------------------------------------------------ tenis (Barnett–Clarke)
def gem(p):
    q = 1 - p
    return p ** 4 * (1 + 4 * q + 10 * q ** 2) + 20 * p ** 3 * q ** 3 * p ** 2 / (1 - 2 * p * q)


def tiebreak(pa, pb):
    """pa, pb — P wygrania punktu przy własnym serwisie. A zaczyna serwować."""
    from functools import lru_cache

    @lru_cache(None)
    def T(i, j):
        if i >= 7 and i - j >= 2: return 1.0
        if j >= 7 and j - i >= 2: return 0.0
        if i >= 6 and j >= 6 and i == j:
            # od 6:6 — dwa punkty (po jednym serwisie każdego) w pętli
            w = pa * (1 - pb); l = (1 - pa) * pb
            return w / (w + l)
        k = i + j
        a_serw = (k % 4 == 0) or (k % 4 == 3)
        p = pa if a_serw else 1 - pb
        return p * T(i + 1, j) + (1 - p) * T(i, j + 1)
    return T(0, 0)


def set_(pa, pb):
    ga, gb = gem(pa), gem(pb)
    from functools import lru_cache

    @lru_cache(None)
    def S(i, j):
        if i >= 6 and i - j >= 2: return 1.0
        if j >= 6 and j - i >= 2: return 0.0
        if i == 6 and j == 6: return tiebreak(pa, pb)
        a_serw = (i + j) % 2 == 0
        p = ga if a_serw else 1 - gb
        return p * S(i + 1, j) + (1 - p) * S(i, j + 1)
    return S(0, 0)


def mecz(ps, do):
    from functools import lru_cache

    @lru_cache(None)
    def Mc(i, j):
        if i == do: return 1.0
        if j == do: return 0.0
        return ps * Mc(i + 1, j) + (1 - ps) * Mc(i, j + 1)
    return Mc(0, 0)


def tenis(a, b, bo5=False):
    W = wczytaj('tenis')
    A, B = wymagaj(W, a, sport='tenis'), wymagaj(W, b, sport='tenis')
    zserw = [f(w.get('proc_st_service_points')) for w in W if f(w.get('proc_st_service_points')) and f(w.get('mecze_ze_statami'), 0) >= 3]
    t = (sum(zserw) / len(zserw) / 100) if zserw else 0.62
    K = 5.0

    def sr(w):
        n = f(w.get('mecze_ze_statami'), 0)
        s = f(w.get('proc_st_service_points'))
        r = f(w.get('proc_op_service_points'))
        s = s / 100 if s is not None else t
        r = 1 - r / 100 if r is not None else 1 - t
        return (n * s + K * t) / (n + K), (n * r + K * (1 - t)) / (n + K), n

    sa, ra, na = sr(A)
    sb, rb, nb = sr(B)
    pa = min(max(t + (sa - t) - (rb - (1 - t)), 0.3), 0.9)
    pb = min(max(t + (sb - t) - (ra - (1 - t)), 0.3), 0.9)
    ps = (set_(pa, pb) + 1 - set_(pb, pa)) / 2          # średnio po kolejności serwisu
    do = 3 if bo5 else 2
    pm = mecz(ps, do)
    print(f'SEZON (30 dni)  {A["druzyna"]} – {B["druzyna"]}  (mecze ze statystykami {int(na)}/{int(nb)}; bo{2 * do - 1})')
    print(f'  punkty serwisowe {proc(sa)} / {proc(sb)}; returny {proc(ra)} / {proc(rb)}; forma {A.get("forma_10")} / {B.get("forma_10")}')
    print(f'  P(punkt przy serwisie) A {pa:.3f}, B {pb:.3f}; utrzymanie gema A {proc(gem(pa))}, B {proc(gem(pb))}')
    print(f'  P(set) A {proc(ps)}   P(mecz) A {proc(pm)}   B {proc(1 - pm)}')
    if do == 2:
        print(f'  2:0 A {proc(ps ** 2)}  2:1 A {proc(2 * ps ** 2 * (1 - ps))}  O2.5 seta {proc(2 * ps * (1 - ps))}')
    print(f'  N (do łączenia) = {int(min(na, nb))}')


# ------------------------------------------------------------------ koszykówka
def kosz(a, b, linia=None, handicap=None):
    W = wczytaj('kosz')
    H, G = wymagaj(W, a), wymagaj(W, b)
    K, SD, DOM = 5.0, 12.0, 2.5
    wszyscy = [w for w in W if f(w.get('mecze'), 0) >= 2]
    sr_pkt = sum(f(w['zdobyte_na_mecz'], 0) for w in wszyscy) / max(len(wszyscy), 1)

    def net(w):
        n = f(w.get('mecze'), 0)
        return n * (f(w['zdobyte_na_mecz'], sr_pkt) - f(w['stracone_na_mecz'], sr_pkt)) / (n + K), n

    nh, mh = net(H)
    ng, mg = net(G)
    roznica = (nh - ng) / 2 + DOM
    ph = phi(roznica / SD)
    suma = (f(H['zdobyte_na_mecz'], sr_pkt) + f(G['stracone_na_mecz'], sr_pkt)
            + f(G['zdobyte_na_mecz'], sr_pkt) + f(H['stracone_na_mecz'], sr_pkt)) / 2
    print(f'SEZON  {H["druzyna"]} – {G["druzyna"]}  (mecze {int(mh)}/{int(mg)}; rozgrywki: {H.get("rozgrywki")} | {G.get("rozgrywki")})')
    print(f'  bilans pkt/mecz {nh:+.1f} / {ng:+.1f} (ściągnięty); % z gry {H.get("proc_st_field_goals")} / {G.get("proc_st_field_goals")}; '
          f'za 3 {H.get("proc_st_3_pointers")} / {G.get("proc_st_3_pointers")}; straty {H.get("sr_st_turnovers")} / {G.get("sr_st_turnovers")}')
    print(f'  oczekiwana różnica {roznica:+.1f} pkt (z przewagą parkietu {DOM}); suma ~{suma:.1f}')
    print(f'  wygrana gosp {proc(ph)}   gość {proc(1 - ph)}')
    if handicap is not None:
        print(f'  gosp {handicap:+} : {proc(phi((roznica + handicap) / SD))}')
    if linia is not None:
        print(f'  suma > {linia}: {proc(1 - phi((linia - suma) / 17.0))}')
    print(f'  N (do łączenia) = {int(min(mh, mg))}  (uwaga: sparingi i superpuchary mają mniejszą wagę informacyjną)')


# ------------------------------------------------------------------ siatkówka
def siatka(a, b):
    W = wczytaj('siatka')
    H, G = wymagaj(W, a), wymagaj(W, b)
    K = 6.0

    def s(w):
        z, st, n = f(w.get('zdobyte'), 0), f(w.get('stracone'), 0), f(w.get('mecze'), 0)
        return (z + K * 0.5 * 3) / (z + st + K * 3) if z + st else 0.5, n

    sa, na = s(H)
    sb, nb = s(G)
    ps = sa * (1 - sb) / (sa * (1 - sb) + sb * (1 - sa))
    pm = mecz(ps, 3)
    print(f'SEZON  {H["druzyna"]} – {G["druzyna"]}  (mecze {int(na)}/{int(nb)}; % ataku {H.get("proc_st_attack")} / {G.get("proc_st_attack")}; '
          f'przyjęcie {H.get("proc_st_reception")} / {G.get("proc_st_reception")})')
    print(f'  P(set) {proc(ps)}   wygrana gosp {proc(pm)}   gość {proc(1 - pm)}   3:0 gosp {proc(ps ** 3)}')
    print(f'  N (do łączenia) = {int(min(na, nb))}')


def forma(sport, nazwa):
    W = wczytaj(sport)
    w = wymagaj(W, nazwa)
    print(f'{w["druzyna"]}: mecze {w["mecze"]}, {w["w"]}-{w["r"]}-{w["p"]} ({w["proc_wygranych"]}% wygranych), '
          f'{w["zdobyte_na_mecz"]}:{w["stracone_na_mecz"]} na mecz, forma {w["forma_10"]}, ostatni {w["ostatni_mecz"]}, '
          f'ze statystykami {w["mecze_ze_statami"]}')


def polacz(pm, ps, n):
    pm, ps, n = float(pm), float(ps), float(n)
    if pm > 1: pm /= 100
    if ps > 1: ps /= 100
    w = min(n / (n + 10), 0.5)
    p = (1 - w) * pm + w * ps
    roz = round(abs(pm - ps) * 100, 1)
    print(f'P_model {proc(pm)}  P_sezon {proc(ps)}  waga sezonu {w:.2f}  →  P {proc(p)}  '
          f'{"ROZBIEŻNOŚĆ >10 pp — nie do K1/K2" if roz > 10 else "zgodne"} ({roz:.1f} pp)')


def druzyny(plik, frag):
    p = plik if os.path.exists(plik) else os.path.join(KATALOG, PLIKI.get(plik, plik))
    for w in wczytaj(None, p):
        if norm(frag) in norm(w['druzyna']):
            print(w.get('liga') or w.get('rozgrywki'), '|', w['druzyna'], '| mecze', w.get('mecze'))


if __name__ == '__main__':
    a = sys.argv[1:]
    opcja = lambda k: float(a[a.index(k) + 1]) if k in a else None
    if not a:
        print(__doc__); sys.exit(0)
    c = a[0]
    if c == 'pilka': pilka(a[1], a[2])
    elif c == 'tenis': tenis(a[1], a[2], '--bo5' in a)
    elif c in ('kosz', 'koszykowka'): kosz(a[1], a[2], opcja('--linia'), opcja('--handicap'))
    elif c in ('siatka', 'siatkowka'): siatka(a[1], a[2])
    elif c == 'forma': forma(a[1], a[2])
    elif c == 'polacz': polacz(a[1], a[2], a[3])
    elif c == 'druzyny': druzyny(a[1], a[2])
    else: print(__doc__)
