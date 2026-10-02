#!/usr/bin/env python3
"""Dzienniki i rozliczenie W KODZIE (29.09.2026, Raport 12:00 usterki 3 i 4) — zamiast recznego skladania delt
i szukania wynikow noga po nodze, ktore nie miescilo sie w czasie przebiegu (zaleglosci 25-28.09).

  python3 dzienniki.py scal KATALOG
      KATALOG = pobrane z Dysku delty (nazwa pliku zaczyna sie od typy_log / sporty_typy / ako_log, dowolny dopisek).
      Tworzy kb/typy_log.csv, kb/sporty_typy.csv, kb/ako_log.csv — pelne dzienniki bez duplikatow
      (przy powtorzonym wierszu wygrywa ten z wypelnionym wynikiem, potem pozniejszy plik).
  python3 dzienniki.py rozlicz RRRR-MM-DD [--ako kb/ako_log.csv | KATALOG_Z_DELTAMI] [--wyjscie Rozliczenie_RRRR-MM-DD.csv]
                                     [--zaklady zaklady_faktyczne.csv]   (02.10: faktyczne zaklady STS/LVBET/Superbet)
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
    try:
        d = pd.read_csv(plik, dtype=str, keep_default_na=False, skipinitialspace=True)
    except pd.errors.ParserError:
        # 01.10.2026: „typy_log 2026-09-20 21_00 …” ma w ostatniej (opisowej) kolumnie przecinek bez cudzyslowu
        # („bez kontroli modelu hist. (jutro, -2pp)”) — caly plik wypadal ze scalania. Nadmiarowe pola wracaja
        # do ostatniej kolumny; krotszy wiersz dostaje puste pola.
        import csv
        with open(plik, newline='', encoding='utf-8') as f:
            w = list(csv.reader(f, skipinitialspace=True))
        nag, n = w[0], len(w[0])
        d = pd.DataFrame([r[:n - 1] + [','.join(r[n - 1:])] if len(r) > n else r + [''] * (n - len(r))
                          for r in w[1:] if r], columns=nag)
    d.columns = [str(c).strip() for c in d.columns]
    return d.apply(lambda s: s.str.strip())


KOLUMNY_LOGU = {'typy_log': ['data', 'gosp', 'gość', 'rynek', 'p', 'trafiony', 'kurs_typu', 'pieniadze'],
                'sporty_typy': ['data', 'sport', 'gosp', 'gosc', 'rynek', 'p', 'trafiony', 'kurs_typu', 'pieniadze']}


def _p_ulamek(v):
    """P jako ulamek: 24-25.09 przebiegi pisaly procenty („37.8”) — w ucz.py/sporty.py wypadaly z przedzialow."""
    x = _liczba(v)
    if x is None: return v
    return f'{x / 100:.4f}'.rstrip('0').rstrip('.') if x > 1 else v


def _ujednolic(rodzaj, x):
    """Stare uklady kolumn (przebiegi 20-24.09) -> obecny uklad typy_log / sporty_typy. Tylko zmiana nazw i rozbicie
    „A - B”; nic nie jest zgadywane (pieniadze/trafiony zostaja puste, gdy plik ich nie mial)."""
    if rodzaj not in KOLUMNY_LOGU: return x
    x = x.copy()
    gosc = 'gość' if rodzaj == 'typy_log' else 'gosc'
    zamiana = {'gospodarz': 'gosp', 'zawodnik_a': 'gosp', 'zawodnik_b': gosc, 'P': 'p', 'P_model': 'p', 'kurs': 'kurs_typu'}
    zamiana['gosc' if rodzaj == 'typy_log' else 'gość'] = gosc
    if 'data_meczu' in x: zamiana['data_meczu'] = 'data'
    x = x.rename(columns={k: v for k, v in zamiana.items() if k in x and v not in x})
    if 'zdarzenie' in x and ('gosp' not in x or gosc not in x):
        pary = x.zdarzenie.map(_para)
        x['gosp'], x[gosc] = pary.str[0], pary.str[1]
    if 'godzina_meczu' in x:      # „jutro 02:30” — mecz nastepnego dnia
        jutro = x.godzina_meczu.str.contains('jutro', case=False, na=False)
        x.loc[jutro, 'data'] = (pd.to_datetime(x.loc[jutro, 'data'], errors='coerce') + pd.Timedelta(days=1)).dt.strftime('%Y-%m-%d')
    if rodzaj == 'typy_log' and 'sport' in x:      # typy_log to tylko pilka (inne sporty: sporty_typy)
        x = x[x.sport.str.lower().str.replace('ł', 'l').str.startswith('pilka')]
    if rodzaj == 'sporty_typy' and 'rynek' in x:   # „zwyciezca: Valentin Royer” -> 1/2, gdy imie i nazwisko = jedna ze stron
        def kod(r):
            m = re.match(r'(?i)^zwyci[eę]zca(?: meczu)?\s*[:-]\s*(.+)$', str(r.rynek))
            if not m: return r.rynek
            t = set(m.group(1).lower().split())
            strony = [k for k, s in (('1', r.get('gosp', '')), ('2', r.get(gosc, ''))) if set(str(s).lower().split()) == t]
            return strony[0] if len(strony) == 1 else r.rynek
        x['rynek'] = x.apply(kod, axis=1) if len(x) else x.rynek
    if 'p' in x:
        x['p'] = x.p.map(_p_ulamek)
        bez = x.p.map(_liczba).isna()
        if bez.any():         # „-”, „ok. 79”, puste — prognoza bez P nie nadaje sie do kalibracji, a psula typ kolumny
            print(f'  {rodzaj}: {int(bez.sum())} wierszy bez liczbowego P pominietych')
            x = x[~bez]
    return x


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
            x = _ujednolic(rodzaj, x)
            if not set(klucz) <= set(x.columns):
                print(f'  UWAGA: {os.path.basename(f)} bez kolumn {sorted(set(klucz) - set(x.columns))} — pominiety')
                continue
            # pliki „… zamkniecia …” (oferta.py) niosa TYLKO kurs_zamkniecia — nie sa kandydatem na caly wiersz nogi
            czesci.append(x.assign(_kol=i, _zamk=int('zamkniecia' in os.path.basename(f).lower())))
        if not czesci: continue
        d = pd.concat(czesci, ignore_index=True)
        n0 = len(d)
        if kol_wyn not in d: d[kol_wyn] = ''
        d = d.fillna('')
        zamk = None
        if 'kurs_zamkniecia' in d:
            # 01.10.2026: kurs_zamkniecia dopisuja delty „ako_log zamkniecia …” (oferta.py) — kazda z kolejnego PDF przed
            # meczem; wygrywa NAJPOZNIEJSZY niepusty, nawet gdy reszte wiersza bierzemy z pliku z wynikiem
            z = d[d.kurs_zamkniecia != ''].sort_values('_kol', kind='stable').drop_duplicates(klucz, keep='last')
            zamk = z.set_index(klucz).kurs_zamkniecia
        d = (d[d._zamk == 0].assign(_ma=(d[kol_wyn] != '').astype(int)).sort_values(['_ma', '_kol'], kind='stable')
             .drop_duplicates(klucz, keep='last').drop(columns=['_ma', '_kol', '_zamk']))
        if zamk is not None and len(zamk):
            k = pd.MultiIndex.from_frame(d[klucz])
            nowe = zamk.reindex(k)
            d['kurs_zamkniecia'] = [n if isinstance(n, str) and n else s for n, s in zip(nowe, d.kurs_zamkniecia)]
        if rodzaj in KOLUMNY_LOGU:      # stare uklady wnosily wlasne kolumny (liga, status, tag…) — zostaje uklad logu
            d = d.reindex(columns=KOLUMNY_LOGU[rodzaj], fill_value='')
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
    # 01.10.2026: przebieg pisze „gosc_O0.5” (ASCII), a ucz.hit zna tylko „gość_O0.5” — noga konczyla BRAK WYNIKU
    return re.sub(r'(?i)^go[sś][cć]_', 'gość_', s)


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


# 01.10.2026 SETTLEMENT v2 — kod anomalii (kolumna „kategoria” Rozliczenia) z WARSTWA, w ktorej noga utknela.
# Stan, wynik i uwaga bez zmian (frazy „jeszcze bez wyniku” / „zrodlo konczy sie” czyta P119). Kolejnosc wzorcow
# ma znaczenie (pierwszy pasujacy). Kod INNE = komunikat bez kodu — test pilnuje, ze zaden komunikat kodu go nie daje.
ANOMALIE = (
    ('MECZ_PRZYSZLY', 'czas', r'jeszcze bez wyniku'),
    ('ZRODLO_OPOZNIONE', 'zrodlo wynikow', r'brak wynikow z tych dni'),
    ('ZAPIS_BEZ_PARY', 'zapis przebiegu', r'zdarzenie bez „A - B”'),
    ('RYNEK_BEZ_STRONY', 'zapis przebiegu', r'BEZ STRONY'),
    ('ZWROT', 'decyzja', r'zwrot \(DNB przy remisie\)'),
    ('RYNEK_NIEOBSLUGIWANY', 'interpretacja', r'nieobslugiwany'),
    ('BRAK_REMISU_W_SPORCIE', 'interpretacja', r'bez remisu w tym sporcie'),
    ('DOGRYWKA_NIEZNANA', 'zrodlo wynikow', r'brak informacji o dogrywce'),
    ('REMIS_PRZY_ZWYCIEZCY', 'decyzja', r'remis przy rynku zwyciezcy'),
    ('KILKA_MECZOW', 'dopasowanie zdarzenia', r'kilka (meczow|pasujacych)'),
    ('NAZWA_NIEDOPASOWANA', 'dopasowanie zdarzenia', r'nie dopasowano'),
    ('BRAK_MECZU', 'dopasowanie zdarzenia', r'brak meczu w oknie'),
)


def kod_anomalii(stan, uwaga):
    """Kod anomalii nogi: BRAK WYNIKU -> kod warstwy; noga rozstrzygnieta z ostrzezeniem dopasowania ->
    DOPASOWANIE_DO_SPRAWDZENIA; inaczej ''."""
    u = str(uwaga)
    if stan == 'BRAK WYNIKU':
        return next((k for k, _, w in ANOMALIE if re.search(w, u)), 'INNE')
    if re.search(r'sprawdz|po jednej druzynie', u): return 'DOPASOWANIE_DO_SPRAWDZENIA'
    return ''


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
        kod = rynek_pilka(rynek)
        h = hit(kod, int(g), int(a), hg, ha)
        wyn = f'{int(g)}:{int(a)}'
        # 01.10.2026 (Settlement v2): zwrot DNB i rynek nieobslugiwany to rozne sytuacje — dawniej jeden komunikat
        if h is None and str(kod).startswith('DNB_') and int(g) == int(a): return 'BRAK WYNIKU', wyn, 'zwrot (DNB przy remisie)'
        if h is None: return 'BRAK WYNIKU', wyn, f'rynek „{rynek}” nieobslugiwany'
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
    zakres = _zakres_rynku(rynek, sp)
    if _remis_rynek(rynek):
        # 01.10.2026: „X” = remis po czasie regulaminowym (dogrywka oznacza remis po 60 min)
        if zakres != 'regulamin': return 'BRAK WYNIKU', wyn, f'rynek „{rynek}” bez remisu w tym sporcie'
        if x.ot == -1 and pg != pa: return 'BRAK WYNIKU', wyn, 'brak informacji o dogrywce'
        return ('TRAFIONY' if x.ot == 1 or pg == pa else 'PRZEGRANY'), wyn, ''
    typ = _typ_zwyciezcy(rynek, gosp, gosc, gosp, gosc)
    if typ is None and _bez_strony(rynek):
        # 30.09.2026 (Rozliczenie 29.09, Hapoel Jerozolima – Rostock): w ako_log samo „zwyciezca” — nie wiadomo, na kogo
        return 'BRAK WYNIKU', wyn, 'rynek „zwyciezca” BEZ STRONY w ako_log — nie zgadujemy (zapisuj „Zwyciezca 1/2” albo nazwe druzyny)'
    if typ is None: return 'BRAK WYNIKU', wyn, f'rynek „{rynek}” nieobslugiwany'
    regulamin = zakres == 'regulamin'
    if regulamin and x.ot == 1: return 'PRZEGRANY', wyn, 'rozstrzygniety w dogrywce, a rynek w czasie regulaminowym'
    if regulamin and x.ot == -1: return 'BRAK WYNIKU', wyn, 'brak informacji o dogrywce'
    # 29.09.2026 (przeglad): remis byl liczony jako wygrana goscia („2” TRAFIONY przy 3:3 w futsalu)
    if pg == pa:
        if regulamin: return 'PRZEGRANY', wyn, 'remis w czasie regulaminowym'
        return 'BRAK WYNIKU', wyn, 'remis przy rynku zwyciezcy — sprawdz recznie'
    zw = gosp if pg > pa else gosc
    return ('TRAFIONY' if typ == zw else 'PRZEGRANY'), wyn, ''


_60MIN = r'\(?\s*(60\s*min\w*|czas\w*\s+regulaminow\w*|regulaminow\w*\s+czas\w*)[^)]*\)?'


def _zakres_rynku(rynek, sport):
    """01.10.2026 (Rogle - Timra, K5b): CO rozlicza rynek — 'mecz' (wynik koncowy, z dogrywka/karnymi) albo
    'regulamin' (wynik po czasie regulaminowym). „Zwyciezca …” to rynek dwudrogowy = caly mecz; 1 / X / 2 i
    „… (60 min)” = czas regulaminowy, ale tylko w sportach z remisem (sporty.DRAW_PRIOR); w pozostalych
    czas regulaminowy nie konczy sie remisem, wiec zawsze 'mecz'."""
    import sporty
    s = str(rynek).replace('_', ' ')
    if sport not in sporty.DRAW_PRIOR: return 'mecz'
    if re.search(_60MIN, s, re.I): return 'regulamin'
    if re.search(r'dogryw|\bz OT\b|incl', s, re.I): return 'mecz'
    if re.match(r'(?i)\s*zwyci[eę]zca', s): return 'mecz'
    return 'regulamin'


def _remis_rynek(rynek):
    return bool(re.fullmatch(r'(?i)\s*(remis|x)\s*(' + _60MIN + r')?\s*', str(rynek).replace('_', ' ')))


def _bez_strony(rynek):
    return not re.sub(r'(?i)^zwyci[eę]zca(\s+meczu)?|\(?z?\s*dogryw\w*\)?', '', str(rynek)).strip()


def _typ_zwyciezcy(rynek, gosp, gosc, h, g):
    """'1' / '2' / 'Zwyciezca 1' / 'Zwyciezca Nazwisko' -> h albo g (ta sama strona co w zdarzeniu)."""
    # 01.10.2026: „zwyciezca_1” (podkreslnik) i „1 (60 min)” / „1_60min” — ta sama strona, zakres rozstrzyga _zakres_rynku
    s = re.sub(r'(?i)^zwyci[eę]zca(\s+meczu)?\s*[:\-]?\s*', '', str(rynek).replace('_', ' ')).strip()
    s = re.sub(r'(?i)\s*\(?z?\s*dogryw\w*\)?$', '', s).strip()
    s = re.sub(r'(?i)\s*' + _60MIN + r'$', '', s).strip()
    if s in ('1', 'gosp'): return h
    if s in ('2', 'gosc', 'gość'): return g
    import sporty
    k = sporty.norm(s)
    if k and k in sporty.norm(gosp) and k not in sporty.norm(gosc): return h
    if k and k in sporty.norm(gosc) and k not in sporty.norm(gosp): return g
    # 01.10.2026: tenis/dart — zdarzenie „Woodhouse Luke - Aspinall Nathan”, rynek „zwyciezca meczu: Luke Woodhouse”
    # (imie i nazwisko w odwrotnej kolejnosci) dawalo BEZ STRONY. Te same SLOWA (kazde w calosci) = ta sama strona.
    slowa = lambda t: {sporty.norm(w) for w in re.split(r'[\s\-]+', str(t)) if sporty.norm(w)}
    ks = slowa(s)
    w_h, w_g = bool(ks) and ks <= slowa(gosp), bool(ks) and ks <= slowa(gosc)
    if w_h != w_g: return h if w_h else g
    return None


def _liczba(s):
    try:
        v = float(str(s).replace(',', '.'))
        return None if math.isnan(v) else v
    except ValueError:
        return None


def kupon_pieniezny(r0):
    """Wiersz RAZEM kuponu -> (stawka, czy_za_pieniadze). Wspolne dla rozliczenia i clv.py."""
    # „stawka: 5 zl”, „stawka 5 zl”, „stawka=5” — dawniej tylko „stawka 5 z…”, a reszta robila z kuponu papierowy
    m = re.search(r'stawka\W*(\d+(?:[.,]\d+)?)', str(r0.get('uwaga', '')), re.I)
    stawka = _liczba(m.group(1)) if m else 0.0
    status = str(r0.get('status', '')).upper()
    return stawka, bool(stawka > 0 and not any(x in status for x in ('PAPIER', 'ODWOL', 'NIE GRAC')))


# 02.10.2026: FAKTYCZNE zaklady (STS, LVBET, Superbet) — plik zaklady_faktyczne.csv w baza-wiedzy (dane, NIE repo).
# Jeden wiersz na noge + wiersz RAZEM (jak ako_log). Gdy dla dnia sa wpisy, Bilans liczy pieniadze WYLACZNIE z nich,
# a kupony z ako_log ze stawka sa tylko zaleceniem systemu. Status bukmachera (WYGRANY/PRZEGRANY/ZWROT) rozstrzyga
# wyplate; niezgodnosc z rozliczeniem kodu = kod ROZLICZENIE_NIEZGODNE_Z_BUKMACHEREM (sygnal bledu rozliczen).
KOLUMNY_ZAKLADOW = ['data', 'godzina', 'bukmacher', 'nr_zakladu', 'noga_nr', 'sport', 'zdarzenie', 'rynek', 'kurs',
                    'stawka', 'wyplata', 'status_bukmachera', 'tag_systemu', 'uwaga']
BUKMACHERZY = ('STS', 'LVBET', 'SUPERBET')


def rozlicz_zaklady(data, zaklady, W, ako=None):
    """Faktyczne zaklady dnia `data` -> (wiersze Rozliczenia, dict postawione/wyplacone/liczba/trafione)."""
    z = zaklady[zaklady.data == data]
    wiersze, bil = [], dict(postawione=0.0, wyplacone=0.0, liczba=0, trafione=0, nierozliczone=[])
    sport_z_ako = {} if ako is None else {str(r['zdarzenie']).strip(): r['sport'] for _, r in ako.iterrows() if r.get('sport')}
    for (buk, nr), k in z.groupby(['bukmacher', 'nr_zakladu'], sort=False):
        nogi, razem = k[k.noga_nr.astype(str) != 'RAZEM'], k[k.noga_nr.astype(str) == 'RAZEM']
        r0 = razem.iloc[0] if len(razem) else pd.Series(dtype=str)
        tag = f'FAKT_{str(buk).upper()}_{nr}'
        stany = []
        for _, r in nogi.iterrows():
            r = r.copy()
            if not str(r.get('sport', '')).strip(): r['sport'] = sport_z_ako.get(str(r['zdarzenie']).strip(), '')
            stan, wyn, uw = rozlicz_noge(r, W)
            wiersze.append(dict(tag=tag, zdarzenie=r.zdarzenie, rynek=r.rynek, P='', kurs_typu=r.get('kurs', ''),
                                kurs_zamkniecia='', CLV='', wynik=wyn, TRAFIONY_PRZEGRANY=stan,
                                kategoria=kod_anomalii(stan, uw), uwaga=uw))
            stany.append(stan)
        stawka = _liczba(r0.get('stawka', '')) or 0.0
        kurs = _liczba(r0.get('kurs', ''))
        if not kurs:
            kn = [_liczba(v) for v in nogi.get('kurs', pd.Series(dtype=str))]
            kurs = float(math.prod(kn)) if kn and all(kn) else None
        kod = 'PRZEGRANY' if 'PRZEGRANY' in stany else ('NIEROZLICZONY' if 'BRAK WYNIKU' in stany or not stany else 'TRAFIONY')
        sb = str(r0.get('status_bukmachera', '')).strip().upper()
        sb = {'WYGRANA': 'WYGRANY', 'PRZEGRANA': 'PRZEGRANY'}.get(sb, sb)
        kat = ''
        if sb in ('WYGRANY', 'PRZEGRANY', 'ZWROT'):
            if kod != 'NIEROZLICZONY' and (kod == 'TRAFIONY') != (sb == 'WYGRANY') and sb != 'ZWROT':
                kat = 'ROZLICZENIE_NIEZGODNE_Z_BUKMACHEREM'
            wynik = {'WYGRANY': 'TRAFIONY', 'PRZEGRANY': 'PRZEGRANY', 'ZWROT': 'ZWROT'}[sb]
        else:
            wynik = kod
        wypl = _liczba(r0.get('wyplata', ''))
        if wypl is None:
            wypl = round(stawka * kurs * TAX, 2) if wynik == 'TRAFIONY' and kurs else (stawka if wynik == 'ZWROT' else 0.0)
        if wynik == 'NIEROZLICZONY':
            wypl = 0.0; bil['nierozliczone'].append(tag)
        else:
            bil['postawione'] += stawka; bil['wyplacone'] += wypl; bil['liczba'] += 1; bil['trafione'] += int(wynik == 'TRAFIONY')
        wiersze.append(dict(tag=f'RAZEM_{tag}', zdarzenie=f'{len(stany)} nogi ({buk}, {r0.get("godzina", "")})', rynek='',
                            P='', kurs_typu=f'{kurs:.3f}' if kurs else '', kurs_zamkniecia='', CLV='', wynik='',
                            TRAFIONY_PRZEGRANY=f'{wynik} {stany.count("TRAFIONY")}/{len(stany)}' if wynik != 'ZWROT' else 'ZWROT',
                            kategoria=kat,
                            uwaga=f'FAKTYCZNY {buk}; stawka {stawka:.2f} zl; kurs {kurs or 0:.3f}; wyplata {wypl:.2f} zl; '
                                  f'zysk/strata {wypl - stawka:+.2f} zl'
                                  + (f'; status bukmachera {sb}' if sb else '')
                                  + (f'; zalecenie systemu {r0.get("tag_systemu")}' if str(r0.get('tag_systemu', '')).strip() else '')))
    return wiersze, bil


def czytaj_zaklady(plik):
    """zaklady_faktyczne.csv -> DataFrame (wszystko tekst) albo None, gdy pliku nie ma."""
    if not plik or not os.path.exists(plik): return None
    z = pd.read_csv(plik, dtype=str, keep_default_na=False)
    for c in KOLUMNY_ZAKLADOW:
        if c not in z: z[c] = ''
    return z


def rozlicz_dzien(data, ako, W, zaklady=None):
    """Wiersze pliku Rozliczenie dla kuponow uruchomionych w dniu `data` + podsumowanie Bilansu.
    zaklady: faktyczne zaklady (czytaj_zaklady) — gdy sa wpisy z tego dnia, pieniadze Bilansu licza sie z nich."""
    fakt = zaklady is not None and (zaklady.data == data).any()
    a = ako[ako.data == data]
    wiersze, bil = [], dict(postawione=0.0, wyplacone=0.0, pap_liczba=0, pap_traf=0, pap_nierozl=0, pap_P=[],
                            pap_wirt=0.0, pien=0, pien_traf=0, nierozliczone=[])
    for (godz, tag, nr), k in a.groupby(['godzina_uruchomienia', 'tag', 'nr_kuponu'], sort=False):
        nogi, razem = k[k.noga_nr != 'RAZEM'], k[k.noga_nr == 'RAZEM']
        stany = []
        for _, r in nogi.iterrows():
            stan, wyn, uw = rozlicz_noge(r, W)
            kat = kod_anomalii(stan, uw)
            kz, kt = _liczba(r.get('kurs_zamkniecia', '')), _liczba(r.get('kurs', ''))
            clv = f'{kt / kz - 1:+.1%}' if kz and kt else ''
            wiersze.append(dict(tag=tag, zdarzenie=r.zdarzenie, rynek=r.rynek, P=r.get('P', ''), kurs_typu=r.get('kurs', ''),
                                kurs_zamkniecia=r.get('kurs_zamkniecia', ''), CLV=clv, wynik=wyn, TRAFIONY_PRZEGRANY=stan,
                                kategoria=kat, uwaga=uw))
            stany.append(stan)
        if not stany: continue
        r0 = razem.iloc[0] if len(razem) else pd.Series(dtype=str)
        # 29.09.2026 (przeglad): pusty kurs RAZEM dawal kurs 1,0 (wygrana ksiegowana jako strata) —
        # teraz iloczyn kursow nog, a gdy i tego brak: kupon NIEROZLICZONY (brak kursu)
        kurs = _liczba(r0.get('kurs', ''))
        if not kurs:
            kn = [_liczba(v) for v in nogi.get('kurs', pd.Series(dtype=str))]
            kurs = float(math.prod(kn)) if kn and all(kn) else None
        stawka, pien = kupon_pieniezny(r0)
        zalecony = fakt and pien
        if zalecony: pien = False   # 02.10: sa faktyczne zaklady dnia — kupon systemu to tylko zalecenie
        status = str(r0.get('status', '')).upper()
        n, traf = len(stany), stany.count('TRAFIONY')
        if 'PRZEGRANY' in stany: wynik = f'PRZEGRANY {traf}/{n}'
        elif 'BRAK WYNIKU' in stany: wynik = f'NIEROZLICZONY ({stany.count("BRAK WYNIKU")} bez wyniku)'
        else: wynik = f'TRAFIONY {traf}/{n}'
        if not pien and not zalecony and stawka == 0 and re.search(r'ZAGRAN|DO GRY', status) and not re.search(r'NIE\s*(ZAGRAN|DO GRY)', status):
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
        elif zalecony:
            uw = (f'zalecenie systemu (stawka {stawka:.2f} zl, kurs {kurs:.3f}) — pieniadze dnia z faktycznych zakladow; '
                  f'wirtualnie: {(stawka * kurs * TAX - stawka) if wygral else -stawka:+.2f} zl' if not wynik.startswith('NIEROZL')
                  else f'zalecenie systemu (stawka {stawka:.2f} zl) — pieniadze dnia z faktycznych zakladow')
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
    if fakt:
        wf, bf = rozlicz_zaklady(data, zaklady, W, ako)
        wiersze.extend(wf)
        bil['postawione'] += bf['postawione']; bil['wyplacone'] += bf['wyplacone']
        bil['pien'] += bf['liczba']; bil['pien_traf'] += bf['trafione']; bil['nierozliczone'] += bf['nierozliczone']
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
    zp = a[a.index('--zaklady') + 1] if '--zaklady' in a else os.path.join(HERE, 'zaklady_faktyczne.csv')
    zaklady = czytaj_zaklady(zp)
    if zaklady is not None and (zaklady.data == data).any():
        print(f'FAKTYCZNE ZAKLADY {data}: {zaklady[(zaklady.data == data) & (zaklady.noga_nr == "RAZEM")].shape[0]} '
              f'z {os.path.basename(zp)} — Bilans pieniedzy z nich (kupony systemu = zalecenia)')
    else:
        print(f'FAKTYCZNE ZAKLADY {data}: brak wpisow ({os.path.basename(zp)}) — Bilans z kuponow ako_log jak dotad')
    roz, bil = rozlicz_dzien(data, ako, W, zaklady)
    roz.to_csv(wyj, index=False)
    nogi = roz[~roz.tag.str.startswith('RAZEM_')]
    print(f'ROZLICZENIE {data}: {len(nogi)} nog | ' + ', '.join(f'{k} {v}' for k, v in nogi.TRAFIONY_PRZEGRANY.value_counts().items()))
    for r in nogi[nogi.TRAFIONY_PRZEGRANY == 'BRAK WYNIKU'].itertuples():
        print(f'  BRAK WYNIKU [{r.kategoria}]: {r.tag} | {r.zdarzenie} | {r.rynek} | {r.uwaga}')
    an = nogi.kategoria[nogi.kategoria != ''].value_counts()
    if len(an):
        warstwa = {k: w for k, w, _ in ANOMALIE}
        print('SETTLEMENT_ANOMALY: ' + ', '.join(f'{k} {v} ({warstwa.get(k, "do sprawdzenia")})' for k, v in an.items()))
    print(roz[roz.tag.str.startswith('RAZEM_')][['tag', 'TRAFIONY_PRZEGRANY', 'uwaga']].to_string(index=False))
    for r in roz[roz.kategoria == 'ROZLICZENIE_NIEZGODNE_Z_BUKMACHEREM'].itertuples():
        print(f'  UWAGA ROZLICZENIE_NIEZGODNE_Z_BUKMACHEREM: {r.tag} — {r.TRAFIONY_PRZEGRANY} wg bukmachera, '
              f'a nogi wg kodu inaczej; sprawdz nogi tego zakladu (blad rozliczen do reprodukcji)')
    sr = sum(bil['pap_P']) / len(bil['pap_P']) if bil['pap_P'] else float('nan')
    print(f'\nBILANS {data}: postawione_zl {bil["postawione"]:.2f} | wyplacone_zl {bil["wyplacone"]:.2f} | '
          f'wynik_dnia_zl {bil["wyplacone"] - bil["postawione"]:+.2f} | kupony pieniezne {bil["pien_traf"]}/{bil["pien"]} | '
          f'AKO_papierowe {bil["pap_liczba"]} (trafione {bil["pap_traf"]}, nierozliczone {bil["pap_nierozl"]}) | '
          f'srednie laczne P {sr:.3f} | wirtualnie z 5 zl {bil["pap_wirt"]:+.2f} zl')
    print(f'(saldo narastajaco = saldo z poprzedniego Bilansu + wynik dnia; zapisano {wyj})')


if __name__ == '__main__':
    main(sys.argv[1:])
