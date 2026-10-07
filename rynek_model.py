#!/usr/bin/env python3
"""Model zakotwiczony w rynku — TRYB OBSERWACJI (07.10.2026). Nic w przebiegu nie uzywa tego do decyzji.

Pytanie: czy P modelu (typuj.py) dodaje cokolwiek do P rynku STS? Jedyne miejsca, gdzie wolno by bylo odchylac P
od rynku, to segmenty, w ktorych model rezydualny ma b > 0 istotnie (przedzial bootstrap po meczach > 0) i lepszy
log-loss w walidacji krzyzowej po dniach.

  python3 rynek_model.py zbior --typy typy_log.csv [T2 ...] [--p-sts model_p.csv ...] --kursy K1.csv.gz [K2 ...]
                               --wyjscie zbior.csv [--bez-wynikow]
      Zbior „P modelu zapisane PRZED meczem + kurs STS + wynik”, dopisywany bez dubli (klucz: data, gospodarz, gosc,
      rynek; istniejace wiersze zostaja, uzupelniany jest tylko brakujacy wynik).
      --typy   dzienniki typy_log (kolumny data, gosp, gość, rynek, p — nazwy z bazy, po resolve; takze wiersze REJESTR)
      --p-sts  P z typuj_wsad w nazwach STS (dzien|data, gospodarz, gosc, rynek, p_model|p [, intl]) — uzupelnia typy_log
      --kursy  pliki z oferta.py (data_meczu, godzina_meczu, sport, liga, gospodarz, gosc, rynek, kurs, godzina_pobrania)
               — dowolnie wiele; dla meczu: NAJWCZESNIEJSZY komplet grupy sprzed meczu (kurs) i NAJPOZNIEJSZY (kurs_zamk,
               przyblizenie zamkniecia). Plik bez tych kolumn jest pomijany z komunikatem.
      Laczenie typy_log z oferta: nazwy STS -> baza przez resolver produkcyjny (dopasuj._produkcja: typuj.resolve,
      aliasy) — reprezentacje przez pule intl; tylko jednoznacznie: obie nazwy rozpoznane, rozne, a para bazy
      w danym dniu wskazywana przez JEDNO zdarzenie oferty. Rynki: 1, X, 2, 1X, X2, 12, O/U k.5.
      Wynik: dzienniki.rozlicz_noge (nazwy STS, jak rozliczenia przebiegu).
  python3 rynek_model.py ocena zbior.csv [--boot 1000] [--zamkniecie]
      P_rynku = 1/kurs znormalizowane w grupie (1X2 -> 1; podwojna szansa -> 2; O/U linii -> 1).
      Log-loss/Brier: rynek, model, mieszanki w*model + (1-w)*rynek; model rezydualny
      logit P = logit P_rynku + b * (logit P_model - logit P_rynku) (offset, jeden parametr) oraz wariant
      a + c*logit P_rynku + b*(...); segmenty 1X2 / podwojna szansa / O-U, reprezentacje / kluby, P_rynku < / > 0.5,
      zrodlo P; walidacja krzyzowa po dniach (dopasowanie bez dnia, ocena na dniu) i bootstrap po meczach dla b.
      --zamkniecie: to samo z kotwica w kursie najpozniejszym (kurs_zamk) zamiast najwczesniejszego.
"""
import contextlib
import io
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RYNKI_1X2 = ('1', 'X', '2')
RYNKI_DC = ('1X', 'X2', '12')
_OU = re.compile(r'^([OU])(\d+\.5)$')
KOL_ZBIOR = ['data', 'godzina', 'liga', 'gospodarz', 'gosc', 'gosp_baza', 'gosc_baza', 'druzyny', 'grupa', 'rynek',
             'p_model', 'zrodlo_p', 'kurs', 'pobrano', 'marza', 'p_rynku', 'kurs_zamk', 'pobrano_zamk', 'p_rynku_zamk',
             'wynik', 'stan']
KLUCZ = ['data', 'gospodarz', 'gosc', 'rynek']
EPS = 1e-4


# ---------------------------------------------------------------- rynki i marza
def grupa_rynku(r):
    """'1'/'X'/'2' -> '1X2'; '1X'/'X2'/'12' -> 'DC'; 'O2.5'/'U2.5' -> 'OU2.5'; inne -> None."""
    r = str(r).strip()
    if r in RYNKI_1X2: return '1X2'
    if r in RYNKI_DC: return 'DC'
    m = _OU.match(r)
    return f'OU{m.group(2)}' if m else None


def normalizuj(kursy, suma=1.0):
    """Lista kursow jednej grupy -> (P znormalizowane proporcjonalnie, marza = suma 1/kurs / suma)."""
    odw = [1.0 / float(k) for k in kursy]
    s = sum(odw)
    return [suma * x / s for x in odw], s / suma


def p_rynku_grup(k):
    """Wiersze kursow (data, gospodarz, gosc, pobrano, grupa, rynek, kurs) -> dodaje p_rynku i marza w kazdej migawce grupy.
    Grupa bez kompletu stron (np. brak X) jest odrzucana — niepelnej grupy nie da sie odmarzowac."""
    k = k.drop_duplicates(['data', 'gospodarz', 'gosc', 'pobrano', 'rynek'], keep='last').copy()
    klucz = ['data', 'gospodarz', 'gosc', 'pobrano', 'grupa']
    k['_odw'] = 1.0 / k.kurs.astype(float)
    s = k.groupby(klucz)._odw.transform('sum')
    n = k.groupby(klucz).rynek.transform('nunique')
    trzy = k.grupa.isin(['1X2', 'DC'])
    suma = np.where(k.grupa == 'DC', 2.0, 1.0)
    k = k.assign(p_rynku=suma * k._odw / s, marza=s / suma)
    return k[(n == np.where(trzy, 3, 2))].drop(columns='_odw')


# ---------------------------------------------------------------- kursy z oferty
def wczytaj_kursy(pliki):
    """Pliki oferta.py -> wiersze pilki z rynkami 1X2/DC/OU, kurs > 1, kurs sprzed poczatku meczu."""
    cz = []
    for f in pliki:
        try:
            k = pd.read_csv(f, dtype=str)
        except Exception as e:
            print(f'  POMINIETO {os.path.basename(f)}: nieczytelny ({e})'); continue
        brak = {'data_meczu', 'gospodarz', 'gosc', 'rynek', 'kurs'} - set(k.columns)
        if brak:
            print(f'  POMINIETO {os.path.basename(f)}: brak kolumn {sorted(brak)} (nie format oferta.py)'); continue
        for c in ('godzina_meczu', 'sport', 'liga', 'godzina_pobrania'):
            if c not in k.columns: k[c] = ''
        cz.append(k)
    if not cz: return pd.DataFrame(columns=['data', 'godzina', 'liga', 'gospodarz', 'gosc', 'rynek', 'kurs', 'pobrano', 'grupa'])
    k = pd.concat(cz, ignore_index=True)
    k = k[k.sport.fillna('').str.upper().isin(['PIŁKA NOŻNA', 'PILKA NOZNA', ''])]
    k = k.assign(kurs=pd.to_numeric(k.kurs.astype(str).str.replace(',', '.'), errors='coerce'),
                 grupa=k.rynek.map(grupa_rynku))
    k = k[k.kurs.gt(1.0) & k.grupa.notna() & k.gospodarz.notna() & k.gosc.notna()]
    k = k.rename(columns={'data_meczu': 'data', 'godzina_meczu': 'godzina', 'godzina_pobrania': 'pobrano'})
    k['godzina'] = k.godzina.fillna('')
    k['pobrano'] = k.pobrano.fillna('')
    start = pd.to_datetime(k.data + ' ' + k.godzina, errors='coerce')
    pobr = pd.to_datetime(k.pobrano, errors='coerce')
    # kurs pobrany po rozpoczeciu meczu (live/nieaktualny) — poza zbiorem; brak godziny = zostaje
    k = k[~(start.notna() & pobr.notna() & (pobr >= start))]
    return k[['data', 'godzina', 'liga', 'gospodarz', 'gosc', 'rynek', 'kurs', 'pobrano', 'grupa']].reset_index(drop=True)


def migawki(k):
    """Kursy -> jeden wiersz na (mecz, rynek): najwczesniejsza i najpozniejsza KOMPLETNA grupa (kurs, p_rynku, marza)."""
    if not len(k): return pd.DataFrame(columns=['data', 'godzina', 'liga', 'gospodarz', 'gosc', 'grupa', 'rynek', 'kurs',
                                                'pobrano', 'marza', 'p_rynku', 'kurs_zamk', 'pobrano_zamk', 'p_rynku_zamk'])
    g = p_rynku_grup(k).sort_values('pobrano', kind='stable')
    klucz_gr = ['data', 'gospodarz', 'gosc', 'grupa']
    pierwsza = g.groupby(klucz_gr).pobrano.transform('min')
    ostatnia = g.groupby(klucz_gr).pobrano.transform('max')
    otw = g[g.pobrano == pierwsza].drop_duplicates(KLUCZ, keep='first')
    zam = g[g.pobrano == ostatnia].drop_duplicates(KLUCZ, keep='last')[KLUCZ + ['kurs', 'pobrano', 'p_rynku']]
    zam = zam.rename(columns={'kurs': 'kurs_zamk', 'pobrano': 'pobrano_zamk', 'p_rynku': 'p_rynku_zamk'})
    return otw.merge(zam, on=KLUCZ, how='left').reset_index(drop=True)


# ---------------------------------------------------------------- P modelu
def wczytaj_typy(pliki):
    """typy_log -> data, gosp_baza, gosc_baza, rynek, p (pierwszy zapis wygrywa — najwczesniejszy przebieg)."""
    cz = []
    for f in pliki:
        t = pd.read_csv(f, dtype=str)
        if not {'data', 'gosp', 'rynek', 'p'} <= set(t.columns): print(f'  POMINIETO {f}: nie typy_log'); continue
        gc = 'gość' if 'gość' in t.columns else 'gosc'
        cz.append(t.rename(columns={'gosp': 'gosp_baza', gc: 'gosc_baza'})[['data', 'gosp_baza', 'gosc_baza', 'rynek', 'p']])
    if not cz: return pd.DataFrame(columns=['data', 'gosp_baza', 'gosc_baza', 'rynek', 'p'])
    t = pd.concat(cz, ignore_index=True)
    t = t.assign(p=pd.to_numeric(t.p, errors='coerce'), data=t.data.str[:10])
    t = t[t.p.between(0, 1) & t.rynek.map(grupa_rynku).notna() & t.gosp_baza.notna() & t.gosc_baza.notna()]
    return t.drop_duplicates(['data', 'gosp_baza', 'gosc_baza', 'rynek'], keep='first').reset_index(drop=True)


def wczytaj_p_sts(pliki):
    """P z typuj_wsad w nazwach STS -> data, gospodarz, gosc, rynek, p, intl."""
    cz = []
    for f in pliki:
        t = pd.read_csv(f, dtype=str)
        t = t.rename(columns={'dzien': 'data', 'p_model': 'p'} if 'p_model' in t.columns else {'dzien': 'data'})
        if 'intl' not in t.columns: t['intl'] = ''
        cz.append(t[['data', 'gospodarz', 'gosc', 'rynek', 'p', 'intl']])
    if not cz: return pd.DataFrame(columns=['data', 'gospodarz', 'gosc', 'rynek', 'p', 'intl'])
    t = pd.concat(cz, ignore_index=True)
    t = t.assign(p=pd.to_numeric(t.p, errors='coerce'), data=t.data.str[:10])
    t = t[t.p.between(0, 1) & t.rynek.map(grupa_rynku).notna()]
    return t.drop_duplicates(KLUCZ, keep='first').reset_index(drop=True)


def rozwiaz_zdarzenia(ev, rozwiaz):
    """ev: data, liga, gospodarz, gosc (unikalne zdarzenia oferty); rozwiaz(nazwa, liga) -> (nazwa_bazy, 'intl'|'klub')|None.
    Zwraca ev z gosp_baza, gosc_baza, druzyny — tylko jednoznaczne: obie nazwy rozpoznane, rozne, ten sam rodzaj
    (dwie reprezentacje albo dwa kluby), a para (data, gosp_baza, gosc_baza) wskazana przez jedno zdarzenie."""
    w = []
    for r in ev.itertuples(index=False):
        a, b = rozwiaz(r.gospodarz, r.liga), rozwiaz(r.gosc, r.liga)
        if not a or not b or a[0] == b[0] or a[1] != b[1]: continue
        w.append(dict(data=r.data, gospodarz=r.gospodarz, gosc=r.gosc, gosp_baza=a[0], gosc_baza=b[0],
                      druzyny='reprezentacje' if a[1] == 'intl' else 'kluby'))
    m = pd.DataFrame(w, columns=['data', 'gospodarz', 'gosc', 'gosp_baza', 'gosc_baza', 'druzyny'])
    dub = m.duplicated(['data', 'gosp_baza', 'gosc_baza'], keep=False)
    return m[~dub].reset_index(drop=True)


def polacz(mig, typy, p_sts, rozwiaz):
    """Migawki kursow + P modelu. Najpierw typy_log (po resolve), potem p_sts (nazwy STS) dla brakujacych wierszy."""
    ev = mig[['data', 'liga', 'gospodarz', 'gosc']].drop_duplicates(['data', 'gospodarz', 'gosc'])
    ev = ev[ev.data.isin(set(typy.data))]          # resolver tylko dla dni, z ktorych sa zapisy typy_log
    mapa = rozwiaz_zdarzenia(ev, rozwiaz) if len(typy) else pd.DataFrame(
        columns=['data', 'gospodarz', 'gosc', 'gosp_baza', 'gosc_baza', 'druzyny'])
    a = mig.merge(mapa, on=['data', 'gospodarz', 'gosc'], how='inner') \
           .merge(typy, on=['data', 'gosp_baza', 'gosc_baza', 'rynek'], how='inner')
    # 07.10.2026: czesc wierszy typy_log (reprezentacje, kupony) ma nazwy z OFERTY („Holandia”, „Girona FC”), nie z bazy
    # — taki wiersz laczy sie wprost (ta sama data i dokladnie te same nazwy STS), bez resolvera
    t2 = typy.rename(columns={'gosp_baza': 'gospodarz', 'gosc_baza': 'gosc'})
    a2 = mig.merge(t2, on=KLUCZ, how='inner')
    if len(a2):
        a2 = a2.merge(a[KLUCZ], on=KLUCZ, how='left', indicator=True).query('_merge == "left_only"').drop(columns='_merge')
        rodz = [(rozwiaz(h, l), rozwiaz(g, l)) for h, g, l in zip(a2.gospodarz, a2.gosc, a2.liga)]
        a2 = a2.assign(gosp_baza=a2.gospodarz, gosc_baza=a2.gosc,
                       druzyny=['reprezentacje' if x and y and x[1] == y[1] == 'intl' else 'kluby' for x, y in rodz])
        a = pd.concat([a, a2], ignore_index=True)
    a = a.rename(columns={'p': 'p_model'}).assign(zrodlo_p='typy_log')
    b = mig.merge(p_sts, on=KLUCZ, how='inner').rename(columns={'p': 'p_model'})
    b = b.assign(zrodlo_p='wsad', gosp_baza='', gosc_baza='',
                 druzyny=np.where(b.intl.astype(str).str.lower().isin(['true', '1']), 'reprezentacje', 'kluby'))
    if len(a): b = b.merge(a[KLUCZ], on=KLUCZ, how='left', indicator=True).query('_merge == "left_only"').drop(columns='_merge')
    out = pd.concat([a, b], ignore_index=True)
    return out.reindex(columns=[c for c in KOL_ZBIOR if c not in ('wynik', 'stan')])


def dopisz(stary, nowy):
    """Bez dubli po KLUCZ: stare wiersze zostaja (P i kurs zamrozone), brakujacy wynik uzupelniany z nowego."""
    if stary is None or not len(stary): return nowy.reset_index(drop=True)
    s = stary.copy()
    for c in KOL_ZBIOR:
        if c not in s.columns: s[c] = ''
    idx = s.set_index(KLUCZ).index
    n = nowy.set_index(KLUCZ)
    pusty = s.wynik.isna() | s.wynik.astype(str).isin(['', 'nan'])
    for i in np.flatnonzero(pusty.to_numpy()):
        k = idx[i]
        if k in n.index:
            w = n.loc[[k]].iloc[0]
            if str(w.wynik) not in ('', 'nan'):
                s.iloc[i, s.columns.get_loc('wynik')] = w.wynik
                s.iloc[i, s.columns.get_loc('stan')] = w.stan
    nowe = nowy[~nowy.set_index(KLUCZ).index.isin(idx)]
    return pd.concat([s[KOL_ZBIOR], nowe[KOL_ZBIOR]], ignore_index=True)


# ---------------------------------------------------------------- produkcja (resolver, wyniki)
def resolver_produkcyjny():
    """Resolver jak w przebiegu: kluby — dopasuj._produkcja (typuj.resolve + egzonimy, aliasy), reprezentacje — pula intl.
    Reprezentacja tylko w lidze „MIĘDZYNARODOWE …” i tylko gdy nazwa rozpoznana w puli intl."""
    import dopasuj
    import typuj
    rozw, _ = dopasuj._produkcja()
    con = typuj.db()
    intl = set(pd.read_sql('select home_team h, away_team a from intl', con).stack())

    pamiec = {}

    def rozwiaz(n, liga):
        mi = str(liga).upper().startswith('MIĘDZYNARODOWE')
        if (n, mi) not in pamiec:
            with contextlib.redirect_stdout(io.StringIO()):
                r = typuj.resolve(n, intl) if mi else None
                if r: pamiec[n, mi] = (r, 'intl')
                else:
                    r = rozw('pilka', n)
                    pamiec[n, mi] = (r, 'klub') if r else None
        return pamiec[n, mi]
    return rozwiaz


def wynik_produkcyjny():
    """(data, gospodarz STS, gosc STS, rynek) -> (1|0|None, stan) przez dzienniki.rozlicz_noge. Dopasowanie meczu do
    wynikow (kosztowne) raz na mecz; kazdy rynek z tego samego wyniku tym samym kodem rozliczen (dzienniki._hit_pilka)."""
    import dzienniki as D
    with contextlib.redirect_stdout(io.StringIO()):
        W = dict(pilka=D.wyniki_pilka(HERE), inne=D.wyniki_inne(HERE), tenis=D.wyniki_tenis(HERE))
    mecze = {}

    def wynik(data, gosp, gosc, rynek):
        k = (data, gosp, gosc)
        if k not in mecze:
            with contextlib.redirect_stdout(io.StringIO()):
                st, wyn, _ = D.rozlicz_noge(dict(sport='pilka', zdarzenie=f'{gosp} - {gosc}', rynek='1', data=data,
                                                 uwaga=f'mecz {data}'), W)
            m = re.fullmatch(r'(\d+):(\d+)', str(wyn))
            mecze[k] = (int(m.group(1)), int(m.group(2))) if m and st in ('TRAFIONY', 'PRZEGRANY') else st
        w = mecze[k]
        if not isinstance(w, tuple): return None, w
        h = D._hit_pilka(rynek, w[0], w[1], None, None)
        return (None, 'BRAK WYNIKU') if h is None else ((1, 'TRAFIONY') if h else (0, 'PRZEGRANY'))
    return wynik


def dodaj_wyniki(z, wynik):
    w = [wynik(r.data, r.gospodarz, r.gosc, r.rynek) for r in z.itertuples(index=False)]
    return z.assign(wynik=[x[0] if x[0] is not None else '' for x in w], stan=[x[1] for x in w])


def zbior(a):
    def lista(flag):
        if flag not in a: return []
        i = a.index(flag) + 1
        j = i
        while j < len(a) and not a[j].startswith('--'): j += 1
        return a[i:j]
    wyj = a[a.index('--wyjscie') + 1] if '--wyjscie' in a else None
    kursy, typy_p, sts_p = lista('--kursy'), lista('--typy'), lista('--p-sts')
    if not wyj or not kursy or not (typy_p or sts_p): print(__doc__); return 1
    k = wczytaj_kursy(kursy)
    mig = migawki(k)
    typy, sts = wczytaj_typy(typy_p), wczytaj_p_sts(sts_p)
    print(f'kursy: {len(k)} wierszy, {mig[["data", "gospodarz", "gosc"]].drop_duplicates().shape[0]} meczow z kompletna grupa; '
          f'typy_log: {len(typy)} P, p-sts: {len(sts)} P')
    z = polacz(mig, typy, sts, resolver_produkcyjny() if len(typy) else (lambda n, l: None))
    z = dodaj_wyniki(z, wynik_produkcyjny()) if '--bez-wynikow' not in a else z.assign(wynik='', stan='')
    stary = pd.read_csv(wyj, dtype=str) if os.path.exists(wyj) else None
    out = dopisz(stary, z.astype(str).replace('nan', ''))
    out.to_csv(wyj, index=False)
    ozn = out[out.wynik.isin(['0', '1', '0.0', '1.0'])]
    print(f'zbior: {len(z)} nog z tego wywolania ({z.zrodlo_p.value_counts().to_dict()}), w pliku {len(out)} '
          f'(z wynikiem {len(ozn)}, meczow {ozn[["data", "gospodarz", "gosc"]].drop_duplicates().shape[0]}) -> {wyj}')
    return 0


# ---------------------------------------------------------------- ocena
def logit(p):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def sigm(x):
    return 1 / (1 + np.exp(-x))


def logloss(p, y):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return float(np.mean(-(y * np.log(p) + (1 - y) * np.log(1 - p))))


def brier(p, y):
    return float(np.mean((np.asarray(p, float) - y) ** 2))


def logistyczna(X, y, offset=None, l2=1e-6, it=50):
    """Regresja logistyczna z offsetem (Newton-Raphson, lekka regularyzacja dla stabilnosci). Zwraca wspolczynniki."""
    X = np.asarray(X, float)
    off = np.zeros(len(y)) if offset is None else np.asarray(offset, float)
    w = np.zeros(X.shape[1])
    for _ in range(it):
        p = sigm(off + X @ w)
        g = X.T @ (y - p) - l2 * w
        H = (X * (p * (1 - p))[:, None]).T @ X + l2 * np.eye(X.shape[1])
        krok = np.linalg.solve(H, g)
        w = w + krok
        if np.max(np.abs(krok)) < 1e-9: break
    return w


def dopasuj_b(lr, d, y, pelny=False):
    """b z modelu logit P = logit P_r + b*d (pelny=False) albo a + c*logit P_r + b*d. Zwraca (b, funkcja P)."""
    if pelny:
        w = logistyczna(np.column_stack([np.ones(len(y)), lr, d]), y)
        return w[2], (lambda lr2, d2: sigm(w[0] + w[1] * lr2 + w[2] * d2))
    w = logistyczna(d[:, None], y, offset=lr)
    return w[0], (lambda lr2, d2: sigm(lr2 + w[0] * d2))


def ocen_segment(x, boot=1000, ziarno=0):
    """x: kolumny p_rynku, p_model, wynik (0/1), dzien, mecz. Metryki + b (offset i pelny) + CV po dniach + bootstrap."""
    y = x.wynik.to_numpy(float)
    pr, pm = x.p_rynku.to_numpy(float), x.p_model.to_numpy(float)
    lr, d = logit(pr), logit(pm) - logit(pr)
    r = dict(nogi=len(x), mecze=x.mecz.nunique(), dni=x.dzien.nunique(), traf=float(y.mean()) if len(y) else float('nan'))
    r['ll_rynek'], r['br_rynek'] = logloss(pr, y), brier(pr, y)
    r['ll_model'], r['br_model'] = logloss(pm, y), brier(pm, y)
    for w in (0.25, 0.5, 0.75):
        pw = w * pm + (1 - w) * pr
        r[f'll_w{w}'], r[f'br_w{w}'] = logloss(pw, y), brier(pw, y)
    b, _ = dopasuj_b(lr, d, y)
    r['b'] = b
    r['b_pelny'] = dopasuj_b(lr, d, y, pelny=True)[0] if len(x) >= 30 else float('nan')
    # walidacja krzyzowa po dniach: P dnia z b dopasowanego na pozostalych dniach
    pcv = np.full(len(x), np.nan)
    dni = x.dzien.to_numpy()
    for dz in np.unique(dni):
        tr = dni != dz
        if tr.sum() < 10 or len(np.unique(y[tr])) < 2: continue
        _, f = dopasuj_b(lr[tr], d[tr], y[tr])
        pcv[~tr] = f(lr[~tr], d[~tr])
    ok = ~np.isnan(pcv)
    r['cv_nogi'] = int(ok.sum())
    r['cv_ll_rez'] = logloss(pcv[ok], y[ok]) if ok.any() else float('nan')
    r['cv_ll_rynek'] = logloss(pr[ok], y[ok]) if ok.any() else float('nan')
    # bootstrap po meczach (nogi meczu razem — 1, X, 2 i O/U jednego meczu sa skorelowane)
    rng = np.random.default_rng(ziarno)
    mecze = x.mecz.to_numpy()
    um, inv = np.unique(mecze, return_inverse=True)
    grupy = [np.flatnonzero(inv == i) for i in range(len(um))]
    bs = []
    for _ in range(boot if len(um) >= 5 else 0):
        idx = np.concatenate([grupy[i] for i in rng.integers(0, len(um), len(um))])
        if len(np.unique(y[idx])) < 2: continue
        bs.append(dopasuj_b(lr[idx], d[idx], y[idx])[0])
    r['b_lo'], r['b_hi'] = (float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))) if bs else (float('nan'),) * 2
    r['istotne'] = bool(bs) and r['b_lo'] > 0 and ok.any() and r['cv_ll_rez'] < r['cv_ll_rynek']
    return r


def przygotuj(z, zamkniecie=False):
    z = z.copy()
    pk = 'p_rynku_zamk' if zamkniecie else 'p_rynku'
    for c in ('p_model', 'p_rynku', 'p_rynku_zamk', 'wynik'):
        if c in z.columns: z[c] = pd.to_numeric(z[c], errors='coerce')
    z = z[z.wynik.isin([0, 1]) & z.p_model.between(0, 1) & z[pk].between(0, 1)].copy()
    z['p_rynku'] = z[pk]
    z['dzien'] = z.data.astype(str).str[:10]
    z['mecz'] = z.dzien + '|' + z.gospodarz.astype(str) + '|' + z.gosc.astype(str)
    z['seg_rynek'] = np.where(z.grupa == '1X2', '1X2', np.where(z.grupa == 'DC', 'DC', 'O/U'))
    z['seg_p'] = np.where(z.p_rynku < 0.5, 'P_rynku<0.5', 'P_rynku>=0.5')
    return z


SEGMENTY = [('WSZYSTKIE', None), ('rynek', 'seg_rynek'), ('druzyny', 'druzyny'), ('P', 'seg_p'), ('zrodlo P', 'zrodlo_p'),
            ('rynek x druzyny', ('seg_rynek', 'druzyny')), ('rynek x P', ('seg_rynek', 'seg_p'))]


def raport(z, boot=1000):
    linie = []
    wiersze = []
    for nazwa, kol in SEGMENTY:
        if kol is None: grupy = [('wszystkie', z)]
        else: grupy = list(z.groupby(list(kol) if isinstance(kol, tuple) else kol))
        for k, x in grupy:
            if len(x) < 20: continue
            etyk = ' x '.join(k) if isinstance(k, tuple) else str(k)
            r = ocen_segment(x, boot)
            r['segment'] = f'{nazwa}: {etyk}'
            wiersze.append(r)
    linie.append(f'{"segment":<34}{"nogi":>6}{"mecze":>6}{"dni":>4} | {"LL rynek":>8}{"LL model":>9}{"w.25":>7}{"w.5":>7}'
                 f' | {"BR ryn":>7}{"BR mod":>7} | {"b":>6} {"95% CI (boot mecze)":>18}{"b_pel":>7} | {"CV LLrez-LLryn":>14}  ')
    for r in wiersze:
        cv = r['cv_ll_rez'] - r['cv_ll_rynek']
        linie.append(f'{r["segment"]:<34}{r["nogi"]:>6}{r["mecze"]:>6}{r["dni"]:>4} | {r["ll_rynek"]:>8.4f}{r["ll_model"]:>9.4f}'
                     f'{r["ll_w0.25"]:>7.4f}{r["ll_w0.5"]:>7.4f} | {r["br_rynek"]:>7.4f}{r["br_model"]:>7.4f} | {r["b"]:>6.3f} '
                     f'[{r["b_lo"]:>6.3f}, {r["b_hi"]:>6.3f}]{r["b_pelny"]:>8.3f} | {cv:>+14.4f}  {"<- b>0 ISTOTNE" if r["istotne"] else ""}')
    ist = [r['segment'] for r in wiersze if r['istotne']]
    linie.append('')
    linie.append('b>0 istotnie (dolna granica 95% CI bootstrap po meczach > 0 i lepszy log-loss w CV po dniach): '
                 + (', '.join(ist) if ist else 'NIGDZIE — model nie dodaje informacji do rynku na tych danych; P = rynek.'))
    return linie, wiersze


def ocena(a):
    if not a: print(__doc__); return 1
    boot = int(a[a.index('--boot') + 1]) if '--boot' in a else 1000
    z0 = pd.read_csv(a[0], dtype=str)
    zam = '--zamkniecie' in a
    z = przygotuj(z0, zam)
    print(f'ZBIOR {a[0]}: {len(z0)} nog, z wynikiem i P: {len(z)} nog, {z.mecz.nunique()} meczow, dni {z.dzien.nunique()} '
          f'({z.dzien.min() if len(z) else "-"} .. {z.dzien.max() if len(z) else "-"}) | kotwica: '
          + ('kurs NAJPOZNIEJSZY (przyblizenie zamkniecia)' if zam else 'kurs NAJWCZESNIEJSZY sprzed meczu'))
    if not len(z): return 0
    print('wg dnia (mecze): ' + str(z.groupby('dzien').mecz.nunique().to_dict()))
    print('wg segmentu (nogi): ' + str(z.seg_rynek.value_counts().to_dict()) + ' ' + str(z.druzyny.value_counts().to_dict())
          + ' ' + str(z.zrodlo_p.value_counts().to_dict()))
    mar = pd.to_numeric(z.get('marza'), errors='coerce')
    print('marza STS (srednio): ' + ', '.join(f'{g} {m:.4f}' for g, m in mar.groupby(z.seg_rynek).mean().items()))
    if not zam and 'p_rynku_zamk' in z0.columns:
        q = przygotuj(z0, True)
        q = q.merge(z[KLUCZ + ['p_rynku']].rename(columns={'p_rynku': 'p_otw'}), on=KLUCZ)
        q = q[pd.to_numeric(q.pobrano_zamk.str.replace(r'\D', '', regex=True), errors='coerce')
              > pd.to_numeric(q.pobrano.str.replace(r'\D', '', regex=True), errors='coerce')]
        if len(q):
            y = q.wynik.to_numpy(float)
            print(f'kontrola zamkniecia (nogi z pozniejszym kursem: {len(q)}): LL kurs najwczesniejszy {logloss(q.p_otw, y):.4f} | '
                  f'najpozniejszy {logloss(q.p_rynku, y):.4f} | LL model {logloss(q.p_model.astype(float), y):.4f}')
    print()
    linie, _ = raport(z, boot)
    print('\n'.join(linie))
    return 0


def main(a):
    if not a or a[0] not in ('zbior', 'ocena'): print(__doc__); return 1
    return zbior(a[1:]) if a[0] == 'zbior' else ocena(a[1:])


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
