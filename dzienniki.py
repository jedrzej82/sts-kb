#!/usr/bin/env python3
"""Dzienniki i rozliczenie W KODZIE (29.09.2026, Raport 12:00 usterki 3 i 4) — zamiast recznego skladania delt
i szukania wynikow noga po nodze, ktore nie miescilo sie w czasie przebiegu (zaleglosci 25-28.09).

  python3 dzienniki.py scal KATALOG
      KATALOG = pobrane z Dysku delty (nazwa pliku zaczyna sie od typy_log / sporty_typy / ako_log, dowolny dopisek).
      Tworzy kb/typy_log.csv, kb/sporty_typy.csv, kb/ako_log.csv — pelne dzienniki bez duplikatow
      (przy powtorzonym wierszu wygrywa ten z wypelnionym wynikiem, potem pozniejszy plik).
  python3 dzienniki.py rozlicz RRRR-MM-DD [--ako kb/ako_log.csv | KATALOG_Z_DELTAMI] [--wyjscie Rozliczenie_RRRR-MM-DD.csv]
      Rozlicza kupony z ako_log uruchomione tego dnia: wynik kazdej nogi z kb.sqlite (kluby, reprezentacje),
      zewn/wyniki_* (365scores, Flashscore, Liga Pro), sporty_hist.csv i tenis_hist.csv. Zapisuje plik
      „Rozliczenie” (kolumny KROKU 5.3 + wiersze RAZEM_*) i wypisuje wiersz Bilansu dnia.
      Noga bez wyniku = „BRAK WYNIKU” (do recznego sprawdzenia, maks. kilka) — kupon z taka noga NIEROZLICZONY.

Kod NIE zgaduje: nazwa dopasowana niejednoznacznie albo brak meczu w oknie +-1 dnia = BRAK WYNIKU."""
import glob
import math
import os
import re
import sqlite3
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TAX = 0.88
RODZAJE = {  # rodzaj -> klucz wiersza (bez duplikatow) i kolumna wyniku (wypelniona wygrywa)
    'typy_log': (['data', 'gosp', 'gość', 'rynek'], 'trafiony'),
    'sporty_typy': (['data', 'sport', 'gosp', 'gosc', 'rynek'], 'trafiony'),
    'ako_log': (['data', 'godzina_uruchomienia', 'tag', 'nr_kuponu', 'noga_nr'], 'trafiona'),
}


def _czytaj(plik):
    d = pd.read_csv(plik, dtype=str, keep_default_na=False, skipinitialspace=True)
    d.columns = [str(c).strip() for c in d.columns]
    return d.apply(lambda s: s.str.strip())


def scal(katalog, cel=HERE):
    """Laczy delty kazdego rodzaju w jeden plik. Zwraca {rodzaj: (plikow, wierszy, po_scaleniu)}."""
    wynik = {}
    for rodzaj, (klucz, kol_wyn) in RODZAJE.items():
        pliki = sorted(f for f in glob.glob(os.path.join(katalog, '*'))
                       if os.path.basename(f).lower().replace(' ', '_').startswith(rodzaj))
        if not pliki: continue
        czesci = []
        for i, f in enumerate(sorted(pliki, key=os.path.getmtime)):
            try:
                x = _czytaj(f)
            except Exception as e:
                print(f'  UWAGA: {os.path.basename(f)} nieczytelny ({e}) — pominiety')
                continue
            if not set(klucz) <= set(x.columns):
                print(f'  UWAGA: {os.path.basename(f)} bez kolumn {sorted(set(klucz) - set(x.columns))} — pominiety')
                continue
            czesci.append(x.assign(_kol=i))
        if not czesci: continue
        d = pd.concat(czesci, ignore_index=True)
        n0 = len(d)
        if kol_wyn not in d: d[kol_wyn] = ''
        d = (d.assign(_ma=(d[kol_wyn] != '').astype(int)).sort_values(['_ma', '_kol'], kind='stable')
             .drop_duplicates(klucz, keep='last').drop(columns=['_ma', '_kol']))
        d = d.sort_values([c for c in ('data', 'godzina_uruchomienia', 'tag', 'nr_kuponu', 'noga_nr') if c in d], kind='stable')
        d.to_csv(os.path.join(cel, f'{rodzaj}.csv'), index=False)
        wynik[rodzaj] = (len(pliki), n0, len(d))
        print(f'{rodzaj}: {len(pliki)} plikow, {n0} wierszy -> {len(d)} po usunieciu duplikatow -> {rodzaj}.csv')
    return wynik


# ---------------- wyniki ----------------
def _data(s):
    return pd.to_datetime(s, errors='coerce')


def wyniki_pilka(kb=HERE):
    """(data, gosp, gosc, g, a, ht_g, ht_a) z kb.sqlite (matches + intl) i zewn/wyniki_*_pilka_*."""
    czesci = []
    db = os.path.join(kb, 'kb.sqlite')
    if os.path.exists(db):
        con = sqlite3.connect(db)
        m = pd.read_sql("select MatchDate d, HomeTeam h, AwayTeam a, FTHome g, FTAway ga, HTHome hg, HTAway ha from matches "
                        "where MatchDate >= date('now', '-60 day')", con)
        czesci.append(m)
        try:
            i = pd.read_sql("select date d, home_team h, away_team a, home_score g, away_score ga from intl "
                            "where date >= date('now', '-60 day')", con)
            czesci.append(i.assign(hg=None, ha=None))
        except Exception:
            pass
    for f in glob.glob(os.path.join(kb, 'zewn', 'wyniki_*_pilka_*.csv*')):
        try:
            z = pd.read_csv(f, dtype=str, keep_default_na=False)
            czesci.append(pd.DataFrame({'d': z.data, 'h': z.gosp, 'a': z.gosc, 'g': z.wg, 'ga': z.wa, 'hg': None, 'ha': None}))
        except Exception as e:
            print(f'  UWAGA: {os.path.basename(f)} nieczytelny ({e})')
    if not czesci: return pd.DataFrame(columns=['d', 'h', 'a', 'g', 'ga', 'hg', 'ha'])
    w = pd.concat(czesci, ignore_index=True)
    w['d'] = _data(w.d).dt.normalize()
    for c in ('g', 'ga', 'hg', 'ha'): w[c] = pd.to_numeric(w[c], errors='coerce')
    return w.dropna(subset=['d', 'g', 'ga']).drop_duplicates(['d', 'h', 'a'], keep='last')


def wyniki_inne(kb=HERE):
    """(data, sport, gosp, gosc, pg, pa, dogrywka) z sporty_hist/sporty_delta i zewn (inne sporty, Liga Pro)."""
    czesci = []
    for f in ('sporty_hist.csv', 'sporty_delta.csv'):
        p = os.path.join(kb, f)
        if os.path.exists(p): czesci.append(pd.read_csv(p, dtype=str, keep_default_na=False))
    try:
        import zewn
        zewn.ZD = os.path.join(kb, 'zewn')
        z = zewn.inne()
        if len(z): czesci.append(z.astype(str))
    except Exception as e:
        print(f'  UWAGA: zewn.inne() niedostepne ({e})')
    if not czesci: return pd.DataFrame(columns=['d', 'sport', 'h', 'a', 'pg', 'pa', 'ot'])
    w = pd.concat(czesci, ignore_index=True)
    w = pd.DataFrame({'d': _data(w.data).dt.normalize(), 'sport': w.sport, 'h': w.gosp, 'a': w.gosc,
                      'pg': pd.to_numeric(w.pg, errors='coerce'), 'pa': pd.to_numeric(w.pa, errors='coerce'),
                      'ot': pd.to_numeric(w.get('dogrywka', 0), errors='coerce')})
    return w.dropna(subset=['d', 'pg', 'pa'])


def wyniki_tenis(kb=HERE):
    p = os.path.join(kb, 'tenis_hist.csv')
    if not os.path.exists(p): return pd.DataFrame(columns=['d', 'w', 'l', 'score'])
    t = pd.read_csv(p, dtype=str, keep_default_na=False, usecols=['date', 'zwyciezca', 'przegrany', 'score'])
    t = t.assign(d=_data(t.date).dt.normalize())
    return t[t.d >= pd.Timestamp.today().normalize() - pd.Timedelta(days=60)].rename(columns={'zwyciezca': 'w', 'przegrany': 'l'})


# ---------------- rynki ----------------
_SLOWA = {'powyzej': 'O', 'ponizej': 'U', 'over': 'O', 'under': 'U'}


def rynek_pilka(r):
    """Rynek z ako_log -> kod ucz.hit ('powyzej 1.5 gola' -> 'O1.5', 'Podwojna szansa X2' -> 'X2',
    'Zwyciezca meczu 1' -> '1', 'obie strzela tak' -> 'BTTS_tak'). Zapisy z przebiegow 22-29.09."""
    s = re.sub(r'(?i)\b(podw[oó]jna szansa|liczba goli|zwyci[eę]zca meczu|zwyci[eę]zca)\b', ' ', str(r))
    s = re.sub(r'(?i)\s+(gola|goli|gole|bramki|bramek)$', '', s.strip()).strip()
    m = re.match(r'^(powyzej|ponizej|powyżej|poniżej|over|under)\s+(\d+[.,]5)$', s, re.I)
    if m: return _SLOWA[m.group(1).lower().replace('ż', 'z')] + m.group(2).replace(',', '.')
    if re.match(r'^obie\s+strzel\w*\s+tak$', s, re.I): return 'BTTS_tak'
    if re.match(r'^obie\s+strzel\w*\s+nie$', s, re.I): return 'BTTS_nie'
    return s


def _para(zdarzenie):
    p = re.split(r'\s+[-–]\s+', str(zdarzenie).strip(), maxsplit=1)
    return (p[0].strip(), p[1].strip()) if len(p) == 2 else (None, None)


def _data_meczu(r):
    m = re.search(r'mecz\s+(\d{4}-\d{2}-\d{2})', str(r.get('uwaga', '')))
    return pd.Timestamp(m.group(1) if m else r['data'])


def _szukaj(w, d0, gosp, gosc, rozwiaz, kol_h='h', kol_a='a'):
    """Mecz z okna +-1 dnia, obie nazwy dopasowane jednoznacznie. Zwraca (wiersz, odwrocone) albo (None, powod)."""
    okno = w[(w.d >= d0 - pd.Timedelta(days=1)) & (w.d <= d0 + pd.Timedelta(days=1))]
    if okno.empty:   # 01.10.2026: z data konca zrodla (dart z walker95sam/darts potrafi miec 2-3 dni opoznienia)
        return None, 'brak wynikow z tych dni' + (f' (zrodlo konczy sie {w.d.max():%Y-%m-%d})' if len(w) else '')
    pula = set(okno[kol_h]) | set(okno[kol_a])
    h, g = rozwiaz(gosp, pula), rozwiaz(gosc, pula)
    if h and g:
        # 29.09.2026 (przeglad): obie orientacje RAZEM — mecz dnia ma pierwszenstwo takze wtedy, gdy wczoraj ta sama
        # para grala u drugiej druzyny (dwumecz „u siebie / na wyjezdzie” dzien po dniu)
        x = pd.concat([okno[(okno[kol_h] == h) & (okno[kol_a] == g)].assign(_odw=False),
                       okno[(okno[kol_h] == g) & (okno[kol_a] == h)].assign(_odw=True)])
        if len(x):
            x, powod = _jeden_mecz(x, d0)
            return (x.drop(labels='_odw'), bool(x['_odw'])) if x is not None else (None, f'{h} - {g}: {powod}')
    k = _po_kotwicy(okno, h, g, gosp, gosc, rozwiaz, kol_h, kol_a)
    if k is not None: return k
    if not h or not g: return None, f'nie dopasowano: {gosp if not h else gosc}'
    return None, f'{h} - {g}: brak meczu w oknie +-1 dnia'


_WYNIK = (('g', 'ga'), ('pg', 'pa'))


def _jeden_mecz(x, d0):
    """29.09.2026 (przeglad): ta sama para 2 dni z rzedu (seria MLB, koszykowka) — x.iloc[-1] bral przypadkowy
    mecz z okna +-1 dnia. Pierwszenstwo ma dzien meczu; gdy go nie ma, a w oknie sa rozne dni, albo tego dnia
    sa rozne wyniki (dwumecz) — nie zgadujemy."""
    tego = x[x.d == d0]
    if len(tego): x = tego
    elif x.d.nunique() > 1: return None, 'kilka meczow tej pary w oknie +-1 dnia — nie zgadujemy'
    kol = [c for c in ('g', 'ga', 'pg', 'pa') if c in x.columns]
    if kol and len(x.drop_duplicates(kol)) > 1: return None, 'kilka meczow tej pary tego dnia (rozne wyniki) — nie zgadujemy'
    return x.iloc[-1], ''


def _po_kotwicy(okno, h, g, gosp, gosc, rozwiaz, kol_h, kol_a):
    """29.09.2026 (proba generalna, 28.09): dwa zrodla pisza ten sam mecz inaczej — Flashscore „Maccabi Bnei Raina –
    H. Raanana”, 365 „Maccabi Bnei Reineh – Hapoel Raanana”. Kazda nazwa z oferty trafiala w INNE zrodlo i para nie
    istniala nigdzie. Kotwica: druzyna dopasowana w puli, a jej rywal w tym wierszu musi dac sie dopasowac do drugiej
    nazwy z oferty (resolve z pula JEDNEJ nazwy — tylko ten rywal). Wszystkie takie wiersze musza sie zgadzac co do
    wyniku; inaczej nie rozstrzygamy (BRAK WYNIKU)."""
    kand = []
    for kotw, drugi, gosp_kotw in ((h, gosc, True), (g, gosp, False)):
        if not kotw: continue
        for r in okno[(okno[kol_h] == kotw) | (okno[kol_a] == kotw)].itertuples(index=False):
            r = r._asdict()
            na_gosp = r[kol_h] == kotw
            rywal = r[kol_a] if na_gosp else r[kol_h]
            if _cicho_bez_uwag(rozwiaz, drugi, {rywal}) != rywal: continue
            kand.append((pd.Series(r), na_gosp != gosp_kotw, rywal))
    if not kand: return None
    def _wyn(s, odwr):
        for a, b in _WYNIK:
            if a in s and b in s: return (s[b], s[a]) if odwr else (s[a], s[b])
        return tuple(s[c] for c in s.index if c not in (kol_h, kol_a, 'd'))
    if len({_wyn(s, o) for s, o, _ in kand}) != 1: return None
    s, odwr, rywal = kand[0]
    _OSTRZEZENIA.append(f'dopasowano po jednej druzynie: {gosp} - {gosc} = {s[kol_h]} - {s[kol_a]} (sprawdz)')
    return s, odwr


def _cicho_bez_uwag(rozwiaz, nazwa, pula):
    n = len(_OSTRZEZENIA)
    r = rozwiaz(nazwa, pula)
    del _OSTRZEZENIA[n:]
    return r


_OSTRZEZENIA = []   # komunikaty dopasowania nazw z biezacej nogi (ROZMYTO, po rdzeniu...) -> kolumna uwaga


def _cicho(f, nazwa, pula):
    """Wywolanie resolve bez wydruku; ostrzezenia o dopasowaniu rozmytym trafiaja do _OSTRZEZENIA."""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = f(nazwa, pula)
    for l in buf.getvalue().splitlines():
        if r and re.search(r'ROZMYTO|rdzeniu|pominieciu roku|Wikidata', l): _OSTRZEZENIA.append(f'sprawdz dopasowanie: {nazwa} -> {r}')
    return r


def _rozwiaz_pilka(nazwa, pula):
    import typuj
    return _cicho(lambda n, p: typuj._kraj_pl(n, p) or typuj.resolve(n, p), nazwa, pula)


def _rozwiaz_inne(nazwa, pula):
    import sporty
    return _cicho(sporty.resolve, nazwa, pula)


def _kandydaci_tenis(nazwa, pula):
    """29.09.2026: WSZYSCY zawodnicy zgodni z nazwa ze STS („Hurkacz”, „De Minaur A.”, „Cerundolo J. M.”):
    kazdy czlon nazwy musi miec odpowiednik, a co najmniej jeden jako pelne slowo (tenis._wspolne_czlony) —
    inicjal nie zastapi nazwiska („Linette M.” != „Cinalli L. M.”). Wczesniej sporty.resolve wybieral po
    cichu jednego z kilku („Hurkacz” -> „Nika Hurkacz”, w puli byl tez Hubert)."""
    import tenis
    n = len(tenis._czl_norm(nazwa))
    if not n: return set()
    return {p for p in pula if (lambda z: z[0] >= n and z[1] >= 1)(tenis._zgodnosc(nazwa, p))}


def _dzis():
    from zoneinfo import ZoneInfo
    return pd.Timestamp.now(tz=ZoneInfo('Europe/Warsaw')).tz_localize(None).normalize()


def rozlicz_noge(r, W):
    """(TRAFIONY/PRZEGRANY/BRAK WYNIKU, wynik, uwaga). W = dict z tabelami wynikow. Dopasowanie rozmyte
    nazwy nie blokuje rozliczenia (mecz musi i tak zgadzac sie obiema druzynami i data), ale trafia do uwagi."""
    _OSTRZEZENIA.clear()
    stan, wyn, uw = _rozlicz_noge(r, W)
    # 01.10.2026: noga kuponu z 30.09 na mecz 01.10 (AKOP do 12:00 jutra) dawala „nie dopasowano: Panama” — meczu po
    # prostu jeszcze nie bylo w wynikach. Mecz z dzis lub pozniej bez wyniku = do rozliczenia w kolejnym przebiegu.
    if stan == 'BRAK WYNIKU' and _data_meczu(r).normalize() >= _dzis():
        uw = f'mecz {_data_meczu(r):%Y-%m-%d} jeszcze bez wyniku — rozliczy kolejny przebieg ({uw})'
    uw = '; '.join([x for x in [uw] + sorted(set(_OSTRZEZENIA)) if x])
    return stan, wyn, uw


def _rozlicz_noge(r, W):
    from ucz import hit
    sport = str(r.get('sport', '')).lower()
    gosp, gosc = _para(r['zdarzenie'])
    if not gosp: return 'BRAK WYNIKU', '', 'zdarzenie bez „A - B”'
    d0 = _data_meczu(r)
    rynek = str(r['rynek']).strip()
    if sport in ('pilka', 'piłka', 'piłka nożna', 'football', ''):
        # 01.10.2026: przebieg zapisuje w uwadze „dopasowanie po terminarzu -> X” (typuj._kraj_z_terminarza) — ta sama
        # nazwa z bazy rozlicza noge, ale tylko gdy X jest w puli meczow okna (nic nie zgadujemy)
        m = re.search(r'dopasowanie po terminarzu\s*->\s*([^;]+)', str(r.get('uwaga', '')))
        wsk = m.group(1).strip() if m else None
        roz = (lambda n, p: _rozwiaz_pilka(n, p) or (wsk if wsk in p else None)) if wsk else _rozwiaz_pilka
        x, odw = _szukaj(W['pilka'], d0, gosp, gosc, roz)
        if x is None: return 'BRAK WYNIKU', '', odw
        g, a = (x.ga, x.g) if odw else (x.g, x.ga)
        hg, ha = (x.ha, x.hg) if odw else (x.hg, x.ha)
        h = hit(rynek_pilka(rynek), int(g), int(a), hg, ha)
        wyn = f'{int(g)}:{int(a)}'
        if h is None: return 'BRAK WYNIKU', wyn, f'rynek „{rynek}” nieobslugiwany albo zwrot (DNB przy remisie)'
        return ('TRAFIONY' if h else 'PRZEGRANY'), wyn, ''
    if sport == 'tenis':
        t = W['tenis']
        okno = t[(t.d >= d0 - pd.Timedelta(days=1)) & (t.d <= d0 + pd.Timedelta(days=1))]
        pula = set(okno.w) | set(okno.l)
        H, G = _kandydaci_tenis(gosp, pula), _kandydaci_tenis(gosc, pula)
        if not H or not G: return 'BRAK WYNIKU', '', f'nie dopasowano: {gosp if not H else gosc}'
        # mecz rozstrzyga PARA: kilku kandydatow po jednej stronie jest dopuszczalne, jesli dokladnie
        # jedna para (kandydat, kandydat) grala w oknie +-1 dnia
        x = okno[(okno.w.isin(H) & okno.l.isin(G)) | (okno.w.isin(G) & okno.l.isin(H))]
        pary = {frozenset((a, b)) for a, b in zip(x.w, x.l)}
        if not pary: return 'BRAK WYNIKU', '', f'{"/".join(sorted(H))} - {"/".join(sorted(G))}: brak meczu w oknie +-1 dnia'
        if len(pary) > 1: return 'BRAK WYNIKU', '', f'kilka pasujacych meczow ({len(pary)}) — nie zgadujemy'
        h = x.iloc[-1].w if x.iloc[-1].w in H else x.iloc[-1].l
        g = x.iloc[-1].l if h == x.iloc[-1].w else x.iloc[-1].w
        if len(H) > 1 or len(G) > 1: _OSTRZEZENIA.append(f'tenis: {gosp} - {gosc} = {h} - {g} (jedyna pasujaca para, sprawdz)')
        zw = x.iloc[-1].w
        typ = _typ_zwyciezcy(rynek, gosp, gosc, h, g)
        if typ is None: return 'BRAK WYNIKU', x.iloc[-1].score, f'rynek „{rynek}” nieobslugiwany'
        return ('TRAFIONY' if typ == zw else 'PRZEGRANY'), f'{zw} {x.iloc[-1].score}', ''
    import sporty
    sp = sporty.nazwa_sportu({'koszykowka': 'koszykówka', 'pilka reczna': 'piłka ręczna'}.get(sport, sport))
    w = W['inne'][W['inne'].sport == sp]
    # 29.09.2026 (przeglad): ze sportem — jak w typuj (krok Wikidata), inaczej noga dopuszczona przez Wikidata
    # nigdy by sie nie rozliczyla
    x, odw = _szukaj(w, d0, gosp, gosc, lambda n, p: _cicho(lambda a_, b_: sporty.resolve(a_, b_, sp), n, p))
    if x is None: return 'BRAK WYNIKU', '', odw
    pg, pa = (x.pa, x.pg) if odw else (x.pg, x.pa)
    wyn = f'{int(pg)}:{int(pa)}' + (' (dogr.)' if x.ot == 1 else '')
    typ = _typ_zwyciezcy(rynek, gosp, gosc, gosp, gosc)
    if typ is None and _bez_strony(rynek):
        # 30.09.2026 (Rozliczenie 29.09, Hapoel Jerozolima – Rostock): w ako_log samo „zwyciezca” — nie wiadomo, na kogo
        return 'BRAK WYNIKU', wyn, 'rynek „zwyciezca” BEZ STRONY w ako_log — nie zgadujemy (zapisuj „Zwyciezca 1/2” albo nazwe druzyny)'
    if typ is None: return 'BRAK WYNIKU', wyn, f'rynek „{rynek}” nieobslugiwany'
    regulamin = not re.search(r'dogryw|z OT|incl', rynek, re.I) and sp in sporty.DRAW_PRIOR
    if regulamin and x.ot == 1: return 'PRZEGRANY', wyn, 'rozstrzygniety w dogrywce, a rynek w czasie regulaminowym'
    if regulamin and x.ot == -1: return 'BRAK WYNIKU', wyn, 'brak informacji o dogrywce'
    # 29.09.2026 (przeglad): remis byl liczony jako wygrana goscia („2” TRAFIONY przy 3:3 w futsalu)
    if pg == pa:
        if regulamin: return 'PRZEGRANY', wyn, 'remis w czasie regulaminowym'
        return 'BRAK WYNIKU', wyn, 'remis przy rynku zwyciezcy — sprawdz recznie'
    zw = gosp if pg > pa else gosc
    return ('TRAFIONY' if typ == zw else 'PRZEGRANY'), wyn, ''


def _bez_strony(rynek):
    return not re.sub(r'(?i)^zwyci[eę]zca(\s+meczu)?|\(?z?\s*dogryw\w*\)?', '', str(rynek)).strip()


def _typ_zwyciezcy(rynek, gosp, gosc, h, g):
    """'1' / '2' / 'Zwyciezca 1' / 'Zwyciezca Nazwisko' -> h albo g (ta sama strona co w zdarzeniu)."""
    s = re.sub(r'(?i)^zwyci[eę]zca(\s+meczu)?\s*', '', str(rynek)).strip()
    s = re.sub(r'(?i)\s*\(?z?\s*dogryw\w*\)?$', '', s).strip()
    if s in ('1', 'gosp'): return h
    if s in ('2', 'gosc', 'gość'): return g
    import sporty
    k = sporty.norm(s)
    if k and k in sporty.norm(gosp) and k not in sporty.norm(gosc): return h
    if k and k in sporty.norm(gosc) and k not in sporty.norm(gosp): return g
    return None


def _liczba(s):
    try:
        return float(str(s).replace(',', '.'))
    except ValueError:
        return None


def rozlicz_dzien(data, ako, W):
    """Wiersze pliku Rozliczenie dla kuponow uruchomionych w dniu `data` + podsumowanie Bilansu."""
    a = ako[ako.data == data]
    wiersze, bil = [], dict(postawione=0.0, wyplacone=0.0, pap_liczba=0, pap_traf=0, pap_nierozl=0, pap_P=[],
                            pap_wirt=0.0, pien=0, pien_traf=0, nierozliczone=[])
    for (godz, tag, nr), k in a.groupby(['godzina_uruchomienia', 'tag', 'nr_kuponu'], sort=False):
        nogi, razem = k[k.noga_nr != 'RAZEM'], k[k.noga_nr == 'RAZEM']
        stany = []
        for _, r in nogi.iterrows():
            stan, wyn, uw = rozlicz_noge(r, W)
            kz, kt = _liczba(r.get('kurs_zamkniecia', '')), _liczba(r.get('kurs', ''))
            clv = f'{kt / kz - 1:+.1%}' if kz and kt else ''
            wiersze.append(dict(tag=tag, zdarzenie=r.zdarzenie, rynek=r.rynek, P=r.get('P', ''), kurs_typu=r.get('kurs', ''),
                                kurs_zamkniecia=r.get('kurs_zamkniecia', ''), CLV=clv, wynik=wyn, TRAFIONY_PRZEGRANY=stan,
                                kategoria='', uwaga=uw))
            stany.append(stan)
        if not stany: continue
        r0 = razem.iloc[0] if len(razem) else pd.Series(dtype=str)
        # 29.09.2026 (przeglad): pusty kurs RAZEM dawal kurs 1,0 (wygrana ksiegowana jako strata) —
        # teraz iloczyn kursow nog, a gdy i tego brak: kupon NIEROZLICZONY (brak kursu)
        kurs = _liczba(r0.get('kurs', ''))
        if not kurs:
            kn = [_liczba(v) for v in nogi.get('kurs', pd.Series(dtype=str))]
            kurs = float(math.prod(kn)) if kn and all(kn) else None
        # „stawka: 5 zl”, „stawka 5 zl”, „stawka=5” — dawniej tylko „stawka 5 z…”, a reszta robila z kuponu papierowy
        m = re.search(r'stawka\W*(\d+(?:[.,]\d+)?)', str(r0.get('uwaga', '')), re.I)
        stawka = _liczba(m.group(1)) if m else 0.0
        status = str(r0.get('status', '')).upper()
        pien = stawka > 0 and not any(x in status for x in ('PAPIER', 'ODWOL', 'NIE GRAC'))
        n, traf = len(stany), stany.count('TRAFIONY')
        if 'PRZEGRANY' in stany: wynik = f'PRZEGRANY {traf}/{n}'
        elif 'BRAK WYNIKU' in stany: wynik = f'NIEROZLICZONY ({stany.count("BRAK WYNIKU")} bez wyniku)'
        else: wynik = f'TRAFIONY {traf}/{n}'
        if not pien and stawka == 0 and re.search(r'ZAGRAN|DO GRY', status) and not re.search(r'NIE\s*(ZAGRAN|DO GRY)', status):
            wynik = 'NIEROZLICZONY (status gry bez stawki)'   # nie wolno go po cichu uznac za papierowy
        if kurs is None:
            if wynik.startswith('TRAFIONY'): wynik = 'NIEROZLICZONY (brak kursu)'
            kurs = 1.0 if not wynik.startswith('NIEROZL') else 0.0
        wygral = wynik.startswith('TRAFIONY')
        if pien:
            wypl = round(stawka * kurs * TAX, 2) if wygral else 0.0
            if not wynik.startswith('NIEROZL'):
                bil['postawione'] += stawka; bil['wyplacone'] += wypl; bil['pien'] += 1; bil['pien_traf'] += int(wygral)
            uw = f'stawka {stawka:.2f} zl; kurs laczny {kurs:.3f}; wyplata {wypl:.2f} zl; zysk/strata {wypl - stawka:+.2f} zl'
        elif wynik == 'NIEROZLICZONY (status gry bez stawki)':
            uw = 'status ZAGRANY / DO GRY, ale stawki nie odczytano — uzupelnij „stawka N zl” w RAZEM (poza Bilansem i papierowymi)'
            _OSTRZEZENIA.append(f'{tag}#{nr}: {uw}')
        else:
            bil['pap_liczba'] += 1
            if wynik.startswith('NIEROZL'): bil['pap_nierozl'] += 1
            else:
                bil['pap_traf'] += int(wygral); bil['pap_wirt'] += (5 * kurs * TAX - 5) if wygral else -5
            p = _liczba(r0.get('P', ''))
            if p: bil['pap_P'].append(p / 100 if p > 1 else p)
            uw = f'papierowy; wirtualnie z 5 zl: {(5 * kurs * TAX - 5) if wygral else -5:+.2f} zl' if not wynik.startswith('NIEROZL') else 'papierowy'
        if wynik.startswith('NIEROZL'): bil['nierozliczone'].append(f'{tag}#{nr}')
        wiersze.append(dict(tag=f'RAZEM_{tag}_{nr}', zdarzenie=f'{n} nogi ({godz})', rynek='', P=r0.get('P', ''), kurs_typu=f'{kurs:.3f}',
                            kurs_zamkniecia='', CLV='', wynik='', TRAFIONY_PRZEGRANY=wynik, kategoria='', uwaga=uw))
    wynik_dnia = bil['wyplacone'] - bil['postawione']
    wiersze.append(dict(tag='RAZEM_DZIEN', zdarzenie='', rynek='', P='', kurs_typu='', kurs_zamkniecia='', CLV='', wynik='',
                        TRAFIONY_PRZEGRANY=f'postawione {bil["postawione"]:.2f} zl; wyplacone {bil["wyplacone"]:.2f} zl; '
                                           f'wynik dnia {wynik_dnia:+.2f} zl',
                        kategoria='', uwaga=f'papierowe {bil["pap_traf"]}/{bil["pap_liczba"] - bil["pap_nierozl"]} trafione'
                                           + (f'; NIEROZLICZONE: {", ".join(bil["nierozliczone"])}' if bil['nierozliczone'] else '')))
    return pd.DataFrame(wiersze), bil


def main(a):
    if not a or a[0] not in ('scal', 'rozlicz'): sys.exit(__doc__)
    if a[0] == 'scal':
        if len(a) < 2: sys.exit(__doc__)
        scal(a[1]); return
    if len(a) < 2: sys.exit(__doc__)
    data = a[1]
    ako_p = a[a.index('--ako') + 1] if '--ako' in a else os.path.join(HERE, 'ako_log.csv')
    wyj = a[a.index('--wyjscie') + 1] if '--wyjscie' in a else os.path.join(HERE, f'Rozliczenie_{data}.csv')
    if os.path.isdir(ako_p):
        # 29.09.2026 (proba generalna): --ako KATALOG_Z_DELTAMI konczylo sie IsADirectoryError — scalamy tu
        print(f'--ako wskazuje katalog — scalam delty z {ako_p}')
        scal(ako_p, cel=HERE)
        ako_p = os.path.join(HERE, 'ako_log.csv')
    if not os.path.exists(ako_p): sys.exit(f'brak {ako_p} — najpierw: python3 dzienniki.py scal KATALOG_Z_DELTAMI')
    ako = _czytaj(ako_p)
    W = dict(pilka=wyniki_pilka(), inne=wyniki_inne(), tenis=wyniki_tenis())
    roz, bil = rozlicz_dzien(data, ako, W)
    roz.to_csv(wyj, index=False)
    nogi = roz[~roz.tag.str.startswith('RAZEM_')]
    print(f'ROZLICZENIE {data}: {len(nogi)} nog | ' + ', '.join(f'{k} {v}' for k, v in nogi.TRAFIONY_PRZEGRANY.value_counts().items()))
    for r in nogi[nogi.TRAFIONY_PRZEGRANY == 'BRAK WYNIKU'].itertuples():
        print(f'  BRAK WYNIKU: {r.tag} | {r.zdarzenie} | {r.rynek} | {r.uwaga}')
    print(roz[roz.tag.str.startswith('RAZEM_')][['tag', 'TRAFIONY_PRZEGRANY', 'uwaga']].to_string(index=False))
    sr = sum(bil['pap_P']) / len(bil['pap_P']) if bil['pap_P'] else float('nan')
    print(f'\nBILANS {data}: postawione_zl {bil["postawione"]:.2f} | wyplacone_zl {bil["wyplacone"]:.2f} | '
          f'wynik_dnia_zl {bil["wyplacone"] - bil["postawione"]:+.2f} | kupony pieniezne {bil["pien_traf"]}/{bil["pien"]} | '
          f'AKO_papierowe {bil["pap_liczba"]} (trafione {bil["pap_traf"]}, nierozliczone {bil["pap_nierozl"]}) | '
          f'srednie laczne P {sr:.3f} | wirtualnie z 5 zl {bil["pap_wirt"]:+.2f} zl')
    print(f'(saldo narastajaco = saldo z poprzedniego Bilansu + wynik dnia; zapisano {wyj})')


if __name__ == '__main__':
    main(sys.argv[1:])
