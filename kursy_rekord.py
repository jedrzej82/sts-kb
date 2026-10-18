"""WSPOLNY ZAPIS KURSU (18.10.2026, TRYB OBSERWACJI — nic w przebiegu, typowaniu ani kuponach z tego nie korzysta).

Kazdy kurs z dowolnego zrodla -> jeden rekord: zrodlo, bukmacher, id_zdarzenia, pobrano_utc, start_utc, sport, liga,
gospodarz, gosc, rynek, kurs, status_walidacji, powod.

Zrodla:
  z_telefonu  — kursy_bukmacherow_*.csv.gz z telefonu (termux/kursy_bukmacherow.py). Stare pliki bez kolumn
                event_id/liga/start_utc/pobrano_utc tez: czas pobrania z nazwy pliku, start z daty i godziny (czas polski).
  z_importu   — adapter dla danych z AUTORYZOWANEGO zrodla (eksport dostawcy z licencja, plik od uzytkownika). Nic nie
                pobiera z sieci; brak wymaganej kolumny = ValueError z lista brakujacych kolumn.

Statusy (status_walidacji):
  OK           — kurs > 1, nazwy i czasy czytelne, pobrany przed startem, nie starszy niz MAKS_WIEK_MIN (gdy podano teraz);
  BRAK_DANYCH  — brak kursu / kurs <= 1 / brak nazwy / nieczytelny czas;
  PO_STARCIE   — pobrany w chwili startu albo po nim (to juz nie jest kurs przedmeczowy);
  NIEAKTUALNY  — (gdy podano teraz) mecz juz rozpoczety albo kurs starszy niz MAKS_WIEK_MIN (90 min, INSTRUKCJA v7
                 3.3); powyzej PAPIEROWY_H (6 h) powod mowi „tylko papierowo”;
  PODEJRZANY   — ten sam mecz (para MATCH) i ten sam rynek u drugiego zrodla rozni sie o wiecej niz MAKS_ROZNICA (35%)
                 ORAZ o wiecej niz MAKS_ROZNICA_PP (5 pp) prawdopodobienstwa (1/kurs).

Dopasowanie zdarzen miedzy zrodlami (paruj) — zero falszywych par ma pierwszenstwo przed pokryciem:
  start +-TOLERANCJA_MIN (5 min), OBIE strony zgodne (strona_zgodna) w tym samym ukladzie gospodarz/gosc i DOKLADNIE
  jedna para w obie strony -> MATCH. Jedna strona zgodna, a mecz bukmachera ma juz pewna pare z innym meczem
  -> CONFLICT. Jedna strona zgodna bez tego (inna pisownia albo inny rywal — nie wiadomo), strony zamienione, kilka
  kandydatow, brak kandydata -> UNKNOWN. Nie zgadujemy.

Uzycie:  python3 kursy_rekord.py KURSY_BUKMACHEROW.csv.gz [...] [--teraz 2026-10-18T10:00:00Z] [--csv rekordy.csv]
         python3 kursy_rekord.py --import PLIK.csv --zrodlo NAZWA [--teraz ...] [--csv ...]"""
import datetime as dt
import glob
import os
import re
import sys
from zoneinfo import ZoneInfo

import pandas as pd

import kursy3

PL = ZoneInfo('Europe/Warsaw')
POLA = ['zrodlo', 'bukmacher', 'id_zdarzenia', 'pobrano_utc', 'start_utc', 'sport', 'liga', 'gospodarz', 'gosc', 'rynek',
        'kurs', 'status_walidacji', 'powod']
WYMAGANE_IMPORT = ('bukmacher', 'gospodarz', 'gosc', 'start_utc', 'rynek', 'kurs', 'pobrano_utc')
STATUSY = ('OK', 'BRAK_DANYCH', 'PO_STARCIE', 'NIEAKTUALNY', 'PODEJRZANY')
STANY_PARY = ('MATCH', 'UNKNOWN', 'CONFLICT')
MAKS_WIEK_MIN = 90
PAPIEROWY_H = 6
MAKS_ROZNICA = kursy3.MAKS_ROZNICA
# 18.10.2026 (plik z telefonu 14:14): wszystkie 16 par > 35% to ten sam mecz, prawie same wysokie kursy (10 / 13,5;
# 20 / 11) — tam 35% to roznica 2-4 pp prawdopodobienstwa, zwykly rozrzut. PODEJRZANY = oba progi naraz.
MAKS_ROZNICA_PP = 0.05
TOLERANCJA_MIN = kursy3.TOLERANCJA_MIN


def utc(s):
    """ISO / „RRRR-MM-DD GG:MM[:SS]” (bez strefy = UTC) -> datetime UTC; None gdy nieczytelne."""
    if s is None or (isinstance(s, float) and pd.isna(s)) or str(s).strip() == '':
        return None
    try:
        t = dt.datetime.fromisoformat(str(s).strip().replace('Z', '+00:00'))
    except ValueError:
        return None
    return (t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)


def iso(t):
    return t.strftime('%Y-%m-%dT%H:%M:%SZ') if t else ''


def z_polskiego(data, godz):
    """Data i godzina w czasie polskim (lato UTC+2, zima UTC+1 — regula strefy, nie stale +2 h) -> UTC."""
    try:
        t = dt.datetime.strptime(f'{data} {godz}', '%Y-%m-%d %H:%M').replace(tzinfo=PL)
    except (TypeError, ValueError):
        return None
    return t.astimezone(dt.timezone.utc)


def pobrano_z_nazwy(plik):
    """kursy_bukmacherow_RRRR-MM-DD_GG-MM.csv.gz (czas polski z telefonu) -> UTC; None gdy nazwa bez czasu."""
    m = re.search(r'(\d{4}-\d\d-\d\d)_(\d\d)-(\d\d)', os.path.basename(str(plik)))
    return z_polskiego(m.group(1), f'{m.group(2)}:{m.group(3)}') if m else None


def _kol(df, nazwa):
    return df[nazwa].astype(str) if nazwa in df else pd.Series('', index=df.index)


def z_telefonu(df, plik=''):
    """Wiersze pliku z telefonu (stary albo nowy uklad) -> rekordy (tylko rynki z kodem)."""
    df = df[_kol(df, 'rynek') != ''] if len(df) else df
    pob_pliku = pobrano_z_nazwy(plik)
    out = []
    for r in df.to_dict('records'):
        start = utc(r.get('start_utc')) or z_polskiego(r.get('data_meczu'), r.get('godzina_meczu'))
        pob = utc(r.get('pobrano_utc')) or pob_pliku
        out.append(dict(zrodlo='TELEFON', bukmacher=str(r.get('bukmacher', '')), id_zdarzenia=str(r.get('event_id', '') or ''),
                        pobrano_utc=iso(pob), start_utc=iso(start), sport=str(r.get('sport', '')),
                        liga=str(r.get('liga', '') or ''), gospodarz=str(r.get('gospodarz', '')), gosc=str(r.get('gosc', '')),
                        rynek=str(r.get('rynek', '')), kurs=r.get('kurs', '')))
    return out


def z_importu(df, zrodlo):
    """Dane z autoryzowanego zrodla -> rekordy. Wymagane kolumny: WYMAGANE_IMPORT (czasy w UTC, ISO 8601);
    opcjonalne: id_zdarzenia, sport, liga. Rynek = kod jak w kursy3 (1, X, 2, O2.5, BTTS_tak, ...)."""
    brak = [k for k in WYMAGANE_IMPORT if k not in df.columns]
    if brak:
        raise ValueError(f'import {zrodlo}: brak kolumn {", ".join(brak)} (wymagane: {", ".join(WYMAGANE_IMPORT)})')
    out = []
    for r in df.to_dict('records'):
        out.append(dict(zrodlo=str(zrodlo), bukmacher=str(r['bukmacher']), id_zdarzenia=str(r.get('id_zdarzenia', '') or ''),
                        pobrano_utc=iso(utc(r['pobrano_utc'])), start_utc=iso(utc(r['start_utc'])),
                        sport=str(r.get('sport', '') or ''), liga=str(r.get('liga', '') or ''),
                        gospodarz=str(r['gospodarz']), gosc=str(r['gosc']), rynek=str(r['rynek']), kurs=r['kurs']))
    return out


def _kurs(k):
    try:
        k = float(str(k).replace(',', '.'))
    except (TypeError, ValueError):
        return None
    return k if k == k and k > 1.0 else None


def waliduj(rek, teraz=None):
    """(status, powod) jednego rekordu. teraz=None = bez kontroli wieku (analiza historyczna)."""
    if _kurs(rek.get('kurs')) is None: return 'BRAK_DANYCH', f'kurs {rek.get("kurs")!r}'
    if not str(rek.get('gospodarz', '')).strip() or not str(rek.get('gosc', '')).strip(): return 'BRAK_DANYCH', 'brak nazwy'
    start, pob = utc(rek.get('start_utc')), utc(rek.get('pobrano_utc'))
    if start is None: return 'BRAK_DANYCH', 'brak startu'
    if pob is None: return 'BRAK_DANYCH', 'brak czasu pobrania'
    if pob >= start: return 'PO_STARCIE', f'pobrany {int((pob - start).total_seconds() // 60)} min po starcie'
    if teraz is not None:
        if teraz >= start: return 'NIEAKTUALNY', 'mecz juz rozpoczety — kurs przedmeczowy nie do zagrania'
        wiek = (teraz - pob).total_seconds() / 60
        if wiek > PAPIEROWY_H * 60: return 'NIEAKTUALNY', f'wiek {wiek / 60:.1f} h > {PAPIEROWY_H} h — tylko papierowo'
        if wiek > MAKS_WIEK_MIN: return 'NIEAKTUALNY', f'wiek {wiek:.0f} min > {MAKS_WIEK_MIN} min'
    return 'OK', ''


# ---------------- dopasowanie zdarzen ----------------

# regula strony meczu jest jedna dla obu modulow (kursy3 od 18.10.2026 uzywa jej w dopasuj_mecze)
strona_zgodna = kursy3.strona_zgodna
_czlony = kursy3._czlony
MIN_PREFIKS = kursy3.MIN_PREFIKS


def _zdarzenia(rekordy):
    """Unikalne zdarzenia (bukmacher, gospodarz, gosc, start) z rekordow."""
    out = {}
    for r in rekordy:
        t = utc(r.get('start_utc'))
        if t is None: continue
        out.setdefault((r['bukmacher'], r['gospodarz'], r['gosc'], iso(t)),
                       dict(gospodarz=r['gospodarz'], gosc=r['gosc'], t=t, id=r.get('id_zdarzenia', '')))
    return list(out.values())


def paruj(a, b, tol_min=TOLERANCJA_MIN):
    """Zdarzenia a -> lista (zdarzenie a, stan MATCH/UNKNOWN/CONFLICT, zdarzenie b albo None, powod).
    Zdarzenie: dict gospodarz, gosc, t (datetime UTC)[, id]."""
    def kand(x, zbior):
        return [y for y in zbior if abs((x['t'] - y['t']).total_seconds()) <= tol_min * 60]

    def para(x, y):
        return strona_zgodna(x['gospodarz'], y['gospodarz']) and strona_zgodna(x['gosc'], y['gosc'])

    pewne = {}                                     # id(y) -> x dla par z jedyna pelna zgodnoscia (do CONFLICT)
    for x in a:
        p = [y for y in kand(x, b) if para(x, y)]
        if len(p) == 1: pewne.setdefault(id(p[0]), []).append(x)
    out = []
    for x in a:
        c = kand(x, b)
        pelne = [y for y in c if para(x, y)]
        if len(pelne) == 1:
            y = pelne[0]
            wstecz = [z for z in kand(y, a) if para(z, y)]
            if len(wstecz) == 1:
                out.append((x, 'MATCH', y, 'OBIE_STRONY+GODZINA')); continue
            out.append((x, 'UNKNOWN', None, 'NIEJEDNOZNACZNE_WSTECZ')); continue
        if len(pelne) > 1:
            out.append((x, 'UNKNOWN', None, f'NIEJEDNOZNACZNE ({len(pelne)})')); continue
        if any(strona_zgodna(x['gospodarz'], y['gosc']) and strona_zgodna(x['gosc'], y['gospodarz']) for y in c):
            out.append((x, 'UNKNOWN', None, 'ZAMIENIONE_STRONY')); continue
        jedna = [y for y in c if strona_zgodna(x['gospodarz'], y['gospodarz']) != strona_zgodna(x['gosc'], y['gosc'])]
        # nazwa ucieta (PDF STS „Polonia Lidzbark W...”) to brak wiedzy, nie dowod innego rywala
        if any(kursy3._zn(n) is None for y in jedna for n in (x['gospodarz'], x['gosc'], y['gospodarz'], y['gosc'])):
            out.append((x, 'UNKNOWN', None, 'NAZWA_UCIETA')); continue
        # jedna strona zgodna: ten sam mecz pod inna pisownia („Paris FC - Rennes” / „Paris FC - Stade Rennais”) ALBO
        # inny rywal — z samych nazw nie wiadomo (UNKNOWN). CONFLICT tylko gdy ten mecz bukmachera ma juz pewna pare
        # z INNYM meczem z oferty (ta sama druzyna o tej samej godzinie w dwoch meczach).
        inna = [y for y in jedna if any(z is not x for z in pewne.get(id(y), []))]
        if inna:
            out.append((x, 'CONFLICT', inna[0], 'DRUZYNA_W_INNEJ_PARZE')); continue
        if jedna:
            out.append((x, 'UNKNOWN', jedna[0], 'JEDNA_STRONA')); continue
        out.append((x, 'UNKNOWN', None, 'BRAK_PARY'))
    return out


def podejrzane(rekordy, bk_a, bk_b, tol_min=TOLERANCJA_MIN):
    """Oznacza PODEJRZANY rekordy dwoch bukmacherow, gdy dla pary MATCH ten sam rynek rozni sie o > MAKS_ROZNICA.
    Zwraca liczbe oznaczonych rekordow. Zmienia tylko rekordy ze statusem OK."""
    ra = [r for r in rekordy if r['bukmacher'] == bk_a]
    rb = [r for r in rekordy if r['bukmacher'] == bk_b]
    def indeks(lista):
        out = {}
        for r in lista:
            out.setdefault((r['gospodarz'], r['gosc'], iso(utc(r['start_utc']))), {}).setdefault(r['rynek'], []).append(r)
        return out
    po_a, po_b = indeks(ra), indeks(rb)
    n = 0
    for x, stan, y, _ in paruj(_zdarzenia(ra), _zdarzenia(rb), tol_min):
        if stan != 'MATCH': continue
        rynki_b = po_b.get((y['gospodarz'], y['gosc'], iso(y['t'])), {})
        for ry, lista_a in po_a.get((x['gospodarz'], x['gosc'], iso(x['t'])), {}).items():
            for r1 in lista_a:
                for r2 in rynki_b.get(ry, []):
                    k1, k2 = _kurs(r1['kurs']), _kurs(r2['kurs'])
                    if k1 and k2 and abs(k1 / k2 - 1) > MAKS_ROZNICA and abs(1 / k1 - 1 / k2) > MAKS_ROZNICA_PP:
                        for r, inny, k in ((r1, bk_b, k2), (r2, bk_a, k1)):
                            if r.get('status_walidacji') == 'OK':
                                r['status_walidacji'], r['powod'] = 'PODEJRZANY', f'{inny} {k:g} (> {MAKS_ROZNICA:.0%})'
                                n += 1
    return n


def rekordy(lista, teraz=None):
    """Walidacja calej listy: dopisuje status_walidacji i powod; para SUPERBET-LVBET -> PODEJRZANY."""
    for r in lista:
        r['status_walidacji'], r['powod'] = waliduj(r, teraz)
    bk = sorted({r['bukmacher'] for r in lista})
    for i, x in enumerate(bk):
        for y in bk[i + 1:]:
            podejrzane(lista, x, y)
    return lista


def _arg(a, nazwa, dom=None):
    return a[a.index(nazwa) + 1] if nazwa in a else dom


def main(a):
    if not a: sys.exit(__doc__)
    teraz = utc(_arg(a, '--teraz')) if '--teraz' in a else None
    wartosci = {a[i + 1] for i, x in enumerate(a[:-1]) if x.startswith('--')}
    if '--import' in a:
        lista = z_importu(pd.read_csv(_arg(a, '--import'), dtype=str, keep_default_na=False), _arg(a, '--zrodlo', 'IMPORT'))
    else:
        lista = []
        for p in [p for x in a if not x.startswith('--') and x not in wartosci for p in sorted(glob.glob(x))]:
            lista += z_telefonu(pd.read_csv(p, dtype=str, keep_default_na=False), p)
    rekordy(lista, teraz)
    df = pd.DataFrame(lista, columns=POLA)
    print(f'REKORDY KURSOW: {len(df)}' + (f' (teraz {iso(teraz)})' if teraz else ' (bez kontroli wieku)'))
    for (b, s), n in df.groupby(['bukmacher', 'status_walidacji']).size().items():
        print(f'  {b} {s}: {n}')
    bez_id = int((df.id_zdarzenia == '').sum()) if len(df) else 0
    if bez_id: print(f'  bez id_zdarzenia: {bez_id} (stary plik z telefonu)')
    if '--csv' in a:
        df.to_csv(_arg(a, '--csv'), index=False)
        print(f'zapisano {_arg(a, "--csv")}')
    return df


if __name__ == '__main__':
    main(sys.argv[1:])
