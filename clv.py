#!/usr/bin/env python3
"""CLV (closing line value) — czy model bije rynek. Poprawka 56.3.
  python3 clv.py typy_log.csv            — podsumowanie: wszystkie nogi, za pieniadze, papierowe
  python3 clv.py typy_log.csv --od 2026-09-29
  python3 clv.py licznik [ako_log.csv]    — licznik CLV do Raportu: grupy lig, postep do 300 nog na grupe

Wymagane kolumny: kurs_typu, kurs_zamkniecia. Opcjonalne: data, pieniadze (1/0 albo tak/nie), sport, rynek.
CLV nogi = kurs_typu / kurs_zamkniecia − 1. Dodatnie = wzielismy kurs wyzszy niz rynek na zamknieciu.

Kryterium z CZESCI A pkt 4 (Faza 2 wymaga srednie CLV >= 0 przy >= 100 nogach, Faza 3 — istotnie dodatniego):
srednie CLV > 0 i jednostronny test t: p < 0,05. Ponizej 30 nog wynik jest tylko informacyjny.
Wiersze bez kursu zamkniecia sa pomijane (puste pole to brak pomiaru, nie zero)."""
import math
import re
import sys

import pandas as pd

MIN_N_INFO = 30
MIN_N_FAZA2 = 100


def dopisz_typ(plik, row, argv_kurs):
    """Dopisuje typ do logu (typy_log.csv / sporty_typy.csv) z opcjonalnymi kolumnami P56.3:
    argv_kurs = [KURS_TYPU [PIENIADZE]] z konca linii polecenia. Plik jest scalany po nazwach kolumn
    (stary log z Dysku nie ma kurs_typu/pieniadze — dopisanie trybem 'a' przesuneloby kolumny)."""
    import os
    if argv_kurs:
        row['kurs_typu'] = float(str(argv_kurs[0]).replace(',', '.'))
        row['pieniadze'] = int(_tak(argv_kurs[1])) if len(argv_kurs) > 1 else 0
    nowy = pd.DataFrame([row])
    if os.path.exists(plik):
        nowy = pd.concat([pd.read_csv(plik), nowy], ignore_index=True)
    nowy.to_csv(plik, index=False)
    return row


def _tak(x):
    # 30.09.2026: dopisz_typ scala nowy wiersz ze starym logiem bez kolumny `pieniadze` — pandas robi z niej
    # float i w pliku laduje „1.0”; tekstowe porownanie liczylo wtedy kazdy zaklad za pieniadze jako papierowy
    try:
        v = float(str(x).strip().replace(',', '.'))
        return v == 1
    except ValueError:
        return str(x).strip().lower() in ('tak', 'true', 'yes', 't', 'p', 'pieniadze')


def przygotuj(df):
    d = df.copy()
    for k in ('kurs_typu', 'kurs_zamkniecia'):
        d[k] = pd.to_numeric(d[k].astype(str).str.replace(',', '.'), errors='coerce')
    d = d[(d.kurs_typu > 1) & (d.kurs_zamkniecia > 1)].copy()
    d['clv'] = d.kurs_typu / d.kurs_zamkniecia - 1
    return d


def przygotuj_ako(df):
    """01.10.2026: ako_log -> nogi do CLV. (1) pieniadze z wiersza RAZEM kuponu (ta sama regula co rozliczenie:
    stawka > 0 i status nie PAPIER/ODWOL/NIE GRAC) — wczesniej ako_log nie mial podzialu na pieniadze i papier,
    a FAZA 2/3 czyta CLV za pieniadze; (2) rynek ujednolicony („Liczba goli powyzej 1.5”, „powyzej 1.5 gola”,
    „O1.5” to jeden rynek); (3) ta sama noga w kilku kuponach (AKOP i K5c) liczona RAZ — inaczej srednia waza
    nogi, ktore przebieg wpisal do wiecej kuponow."""
    import dzienniki
    d = df.astype(str).replace('nan', '')
    k = ['data', 'godzina_uruchomienia', 'tag', 'nr_kuponu']
    razem = d[d.noga_nr.str.upper() == 'RAZEM']
    pien = {tuple(r[c] for c in k if c in d): dzienniki.kupon_pieniezny(r)[1] for _, r in razem.iterrows()}
    n = d[d.noga_nr.str.upper() != 'RAZEM'].copy()
    n['pieniadze'] = [int(pien.get(tuple(r[c] for c in k if c in d), False)) for _, r in n.iterrows()]
    if 'rynek' in n:
        n['rynek'] = n.rynek.map(dzienniki.rynek_pilka)
    kl = [c for c in ('zdarzenie', 'rynek', 'kurs_typu') if c in n]
    if kl:   # najpierw kupony za pieniadze — gdy noga jest i tu, i w papierowym, liczy sie jako za pieniadze
        n = n.sort_values('pieniadze', ascending=False, kind='stable').drop_duplicates(kl, keep='first')
    return n


def _p_jednostronne(t, df):
    """P(T > t) dla rozkladu t-Studenta; scipy jesli jest, inaczej przyblizenie normalne."""
    try:
        from scipy.stats import t as st
        return float(st.sf(t, df))
    except Exception:
        return 0.5 * math.erfc(t / math.sqrt(2))


def podsumuj(clv):
    """Zwraca dict: n, srednia, sd, t, p (jednostronne, H1: srednia > 0), werdykt."""
    x = pd.Series(clv).dropna().astype(float)
    n = len(x)
    if n == 0:
        return dict(n=0, srednia=None, sd=None, t=None, p=None, werdykt='brak pomiaru')
    sr = float(x.mean())
    sd = float(x.std(ddof=1)) if n > 1 else 0.0
    if n > 1 and sd > 0:
        t = sr / (sd / math.sqrt(n)); p = _p_jednostronne(t, n - 1)
    else:
        t = p = None
    if n < MIN_N_INFO:
        w = f'za malo nog (< {MIN_N_INFO}) — tylko informacyjnie'
    elif p is not None and sr > 0 and p < 0.05:
        w = 'CLV istotnie dodatnie (p < 0,05)' + ('' if n >= MIN_N_FAZA2 else f' — ale < {MIN_N_FAZA2} nog')
    elif sr >= 0:
        w = 'CLV >= 0, nieistotne'
    else:
        w = 'CLV ujemne — brak przewagi nad rynkiem'
    return dict(n=n, srednia=sr, sd=sd, t=t, p=p, werdykt=w)


def _linia(nazwa, s):
    if not s['n']:
        return f'  {nazwa:<12} n=0    brak pomiaru'
    p = '—' if s['p'] is None else f'{s["p"]:.3f}'
    return f'  {nazwa:<12} n={s["n"]:<4} srednie CLV {s["srednia"]:+.2%}  p={p}  → {s["werdykt"]}'


# 05.10.2026: licznik do Raportu. Backtest z kursami (docs/BACKTEST_P48.md) — w ligach europejskich z kursami model nie ma
# przewagi nad rynkiem; jedyne miejsce, gdzie moze ja miec, to ligi slabiej wyceniane. Sygnal: srednie CLV > +3% przy
# >= 300 nogach W GRUPIE (blad std sredniej ok. 0,4 pp przy rozrzucie 6-8%).
CEL_NOG, PROG_CLV = 300, 0.03
_KRAJE_TOP = ('anglia', 'hiszpania', 'wlochy', 'niemcy', 'francja', 'holandia', 'belgia', 'portugalia', 'turcja', 'grecja',
              'szkocja')
_LIGI_TOP = ('premier league', 'championship', 'league one', 'league two', 'laliga', 'laliga 2', 'serie a', 'serie b',
             'bundesliga', '2. bundesliga', 'ligue 1', 'ligue 2', 'eredivisie', 'pro league be', 'pro league', 'primeira liga',
             'liga portugal', 'super lig', 'super league gr', 'premiership', 'la liga', 'segunda division')
_KRAJE_INNE = ('jamajka', 'brazylia', 'usa', 'izrael', 'katar', 'chile', 'peru', 'urugwaj', 'argentyna', 'kolumbia', 'paragwaj',
               'boliwia', 'panama', 'salwador', 'gwatemala', 'serbia', 'szwecja', 'norwegia', 'czechy', 'slowacja', 'austria',
               'szwajcaria', 'litwa', 'finlandia', 'dania', 'irlandia', 'australia', 'zea', 'ekwador', 'meksyk', 'japonia', 'chiny')


def grupa_ligi(liga):
    """Nazwa ligi z oferty -> 'reprezentacje' | 'europa_top' (ligi z kursami historycznymi, raw/Matches.csv) | 'pozostale'."""
    import unicodedata
    from nazwy import LITERY
    s = unicodedata.normalize('NFKD', str(liga).translate(LITERY)).encode('ascii', 'ignore').decode().lower().strip()
    s = re.sub(r'\s+', ' ', s)
    if not s or s == '-': return 'nieznana'
    if re.search(r'^miedzynarodowe(?! - klub)|liga narodow|narodow afryki|\bpna\b|asean|zatoki perskiej|reprezentacj|'
                 r'^mecze towarzyskie$|world grand prix', s):
        return 'reprezentacje'
    m = re.match(r'^([a-z]+)(?:\s*-\s*|\s+)(.*)$', s)
    if m and m.group(1) in _KRAJE_TOP:
        return 'europa_top' if m.group(2).strip() in _LIGI_TOP else 'pozostale'
    if m and m.group(1) in _KRAJE_INNE: return 'pozostale'
    return 'europa_top' if s in _LIGI_TOP else 'pozostale'


def licznik(df):
    """ako_log (str) -> linie licznika CLV do Raportu (tylko pilka — kurs zamkniecia jest z PDF oferty STS)."""
    if 'kurs_typu' not in df.columns and 'kurs' in df.columns:
        df = df.rename(columns={'kurs': 'kurs_typu'})
    n = przygotuj_ako(df)
    n = n[n.get('sport', pd.Series('', index=n.index)).astype(str).str.lower().str.startswith(('pilka', 'piłka'))]
    d = przygotuj(n)
    d['grupa'] = d.get('liga', pd.Series('', index=d.index)).map(grupa_ligi)
    out = [f'LICZNIK CLV (pilka; kurs typu vs zamkniecie STS; cel {CEL_NOG} nog na grupe, sygnal przewagi: srednie CLV > '
           f'+{PROG_CLV:.0%}) — {len(d)} z {len(n)} nog ma kurs zamkniecia']
    for g, nazwa in (('pozostale', 'ligi egzotyczne/nizsze'), ('europa_top', 'ligi europejskie top'),
                     ('reprezentacje', 'reprezentacje'), ('nieznana', 'liga nieznana')):
        x = d[d.grupa == g]
        if g == 'nieznana' and not len(x): continue
        s = podsumuj(x.clv)
        if not s['n']:
            out.append(f'  {nazwa:<24} 0/{CEL_NOG} — brak pomiaru'); continue
        stan = (f'brakuje {CEL_NOG - s["n"]}' if s['n'] < CEL_NOG else
                ('PRZEWAGA (CLV > +3%, p < 0,05)' if s['srednia'] > PROG_CLV and s['p'] is not None and s['p'] < 0.05
                 else 'BRAK PRZEWAGI (cel osiagniety, CLV <= +3% albo nieistotne)'))
        p = '—' if s['p'] is None else f'{s["p"]:.3f}'
        out.append(f'  {nazwa:<24} {s["n"]}/{CEL_NOG}  srednie CLV {s["srednia"]:+.2%}  p={p}  → {stan}')
    return out


def main(a):
    if not a:
        sys.exit(__doc__)
    if a[0] == 'licznik':
        import os
        p = a[1] if len(a) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ako_log.csv')
        print('\n'.join(licznik(pd.read_csv(p, dtype=str, keep_default_na=False))))
        return
    df = pd.read_csv(a[0], dtype=str, keep_default_na=False)
    # 01.10.2026: ako_log zapisuje kurs nogi jako „kurs”, a wiersze RAZEM to kupony, nie nogi — clv.py konczyl sie
    # „BRAK KOLUMN: kurs_typu” i nogi kuponow nigdy nie mialy CLV
    if 'kurs_typu' not in df.columns and 'kurs' in df.columns:
        df = df.rename(columns={'kurs': 'kurs_typu'})
    if 'noga_nr' in df.columns:
        df = przygotuj_ako(df)
    brak = {'kurs_typu', 'kurs_zamkniecia'} - set(df.columns)
    if brak:
        sys.exit(f'BRAK KOLUMN: {", ".join(sorted(brak))} — zapisuj je wg Poprawki 56.3')
    if '--od' in a and 'data' in df.columns:
        df = df[df.data.astype(str).str[:10] >= a[a.index('--od') + 1]]
    d = przygotuj(df)
    print(f'CLV — {len(d)} nog z kursem zamkniecia (z {len(df)} wierszy)')
    print(_linia('wszystkie', podsumuj(d.clv)))
    if 'pieniadze' in d.columns:
        m = d.pieniadze.map(_tak)
        print(_linia('za pieniadze', podsumuj(d.clv[m])))
        print(_linia('papierowe', podsumuj(d.clv[~m])))
    for k in ('sport', 'rynek'):
        if k in d.columns and d[k].nunique() > 1:
            print(f'\n  wg {k}:')
            for v, g in d.groupby(k):
                print('  ' + _linia(str(v)[:12], podsumuj(g.clv)))


if __name__ == '__main__':
    main(sys.argv[1:])
