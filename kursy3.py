"""KURSY TRZECH BUKMACHEROW (02.10.2026): STS (PDF oferty, oferta.py) + Superbet + LVBET (termux/kursy_bukmacherow.py
z telefonu uzytkownika -> kursy_bukmacherow_*.csv.gz w baza-wiedzy).

Dopasowanie meczu STS do meczu bukmachera — bez zgadywania:
  ten sam sport, ta sama data, godzina +-5 min (czas polski po obu stronach), obie nazwy podobne (dopasuj.podobne),
  te same znaczniki (kobiety / U21 / rezerwy; LVBET „(Wom)” = kobiety) i DOKLADNIE jeden taki mecz.
Kursy porownywane tylko dla tego samego kodu rynku (1, X, 2, 1X, X2, 12, O1.5, U3.5, BTTS_tak, Zwyciezca 1 …).
Kontrola wiarygodnosci: kurs bukmachera rozny od STS o wiecej niz 35% = PODEJRZANY (inny mecz/rynek) — nie uzywany.

Uzycie:
  python3 kursy3.py porownaj KURSY_STS.csv.gz KURSY_BUKMACHEROW.csv.gz [...]   — pokrycie i zgodnosc kursow
  python3 kursy3.py kupon KURSY_STS.csv.gz KURSY_BUKMACHEROW.csv.gz --ako kb/ako_log.csv --data D [--tag K5]
     — dla kazdej nogi kuponu kurs u STS / SUPERBET / LVBET i kurs laczny u kazdego bukmachera"""
import glob
import math
import os
import re
import sys

import pandas as pd

import nazwy

TOLERANCJA_MIN = 5
MAKS_ROZNICA = 0.35


def _zn(n):
    return nazwy.znaczniki(re.sub(r'\((?:Wom|Women)\)', '(W)', str(n), flags=re.I))


def _rdzen(n):
    """Nazwa bez znacznikow (U21, (W), II, Res. …) — znaczniki porownuje _zn, a wspolne „U21” to nie podobna nazwa
    (02.10: „Slowenia U21 - Holandia U21” bylo niejednoznaczne z „Austria U21 - Dania U21” o tej samej godzinie)."""
    t = [x for x in re.split(r'\s+', re.sub(r'\((?:Wom|Women)\)', '', str(n), flags=re.I))
         if not nazwy.ZNACZNIK.match(x.strip('[](){}<>.,;:'))]
    return ' '.join(t) or str(n)


def _podobne(a, b):
    import dopasuj
    return dopasuj.podobne(_rdzen(a), _rdzen(b))


def wczytaj_bukmacherow(pliki):
    cz = [pd.read_csv(p, dtype=str, keep_default_na=False) for p in pliki if os.path.exists(p)]
    return wczytaj_bukmacherow_df(pd.concat(cz, ignore_index=True) if cz else None)


def wczytaj_bukmacherow_df(k):
    if k is None or k.empty:
        return pd.DataFrame(columns=['bukmacher', 'sport', 'data_meczu', 'godzina_meczu', 'gospodarz', 'gosc', 'rynek', 'kurs'])
    k = k[k.rynek != ''].copy()
    k['kurs'] = pd.to_numeric(k.kurs, errors='coerce')
    # najnowszy plik wygrywa (kolejnosc plikow = kolejnosc pobran)
    return k.dropna(subset=['kurs']).drop_duplicates(['bukmacher', 'sport', 'data_meczu', 'gospodarz', 'gosc', 'rynek'], keep='last')


def zdarzenia(k):
    """Unikalne mecze (sport, data, godzina, gospodarz, gosc) z kolumna t = minuty od polnocy."""
    z = k.drop_duplicates(['sport', 'data_meczu', 'godzina_meczu', 'gospodarz', 'gosc'])[
        ['sport', 'data_meczu', 'godzina_meczu', 'gospodarz', 'gosc']].copy()
    z = z[z.gospodarz.astype(str).str.len().gt(0) & z.gosc.astype(str).str.len().gt(0)]
    hm = z.godzina_meczu.astype(str).str.extract(r'(\d{1,2}):(\d{2})').astype(float)
    z['t'] = hm[0] * 60 + hm[1]
    return z.dropna(subset=['t'])


def dopasuj_mecze(sts, buk):
    """Zdarzenia STS -> {(sport, data, gosp, gosc STS): (gosp, gosc u bukmachera)} dla jednego bukmachera."""
    wynik, stat = {}, {'jednoznaczne': 0, 'brak': 0, 'kilka': 0}
    po_dniu = {k: g for k, g in buk.groupby(['sport', 'data_meczu'])}
    for r in sts.itertuples(index=False):
        g = po_dniu.get((r.sport, r.data_meczu))
        if g is None: stat['brak'] += 1; continue
        c = g[(g.t - r.t).abs() <= TOLERANCJA_MIN]
        c = [x for x in c.itertuples(index=False)
             if _podobne(r.gospodarz, x.gospodarz) and _podobne(r.gosc, x.gosc)
             and _zn(r.gospodarz) == _zn(x.gospodarz) and _zn(r.gosc) == _zn(x.gosc)]
        pary = {(x.gospodarz, x.gosc) for x in c}
        if len(pary) == 1:
            wynik[(r.sport, r.data_meczu, r.gospodarz, r.gosc)] = next(iter(pary)); stat['jednoznaczne'] += 1
        else:
            stat['kilka' if pary else 'brak'] += 1
    return wynik, stat


def tabela(sts_k, buk_k):
    """Kurs STS i kazdego bukmachera dla tych samych (mecz, rynek). Kolumny: sport, data_meczu, gospodarz, gosc, rynek,
    STS, SUPERBET, LVBET (+ *_podejrzany)."""
    sts_k = sts_k[sts_k.rynek.astype(str).str.match(r'^(1|X|2|1X|X2|12|[OU]\d+\.5|BTTS_(tak|nie)|DNB_[12]|gosp_O0\.5|gość_O0\.5|Zwyciezca [12])$')].copy()
    sts_k['kurs'] = pd.to_numeric(sts_k.kurs, errors='coerce')
    baza = sts_k.dropna(subset=['kurs']).drop_duplicates(['sport', 'data_meczu', 'gospodarz', 'gosc', 'rynek'])[
        ['sport', 'data_meczu', 'godzina_meczu', 'gospodarz', 'gosc', 'rynek', 'kurs']].rename(columns={'kurs': 'STS'})
    ze = zdarzenia(baza)
    staty = {}
    for b, kb in buk_k.groupby('bukmacher'):
        mapa, staty[b] = dopasuj_mecze(ze, zdarzenia(kb))
        kl = {(r.sport, r.data_meczu, r.gospodarz, r.gosc, r.rynek): r.kurs for r in kb.itertuples(index=False)}
        baza[b] = [kl.get((s, d) + mapa.get((s, d, g, a), (None, None)) + (ry,)) for s, d, g, a, ry in
                   zip(baza.sport, baza.data_meczu, baza.gospodarz, baza.gosc, baza.rynek)]
        baza[b] = pd.to_numeric(baza[b], errors='coerce')
        baza[f'{b}_podejrzany'] = (baza[b] / baza.STS - 1).abs() > MAKS_ROZNICA
        baza.loc[baza[f'{b}_podejrzany'], b] = float('nan')
    return baza, staty


def najlepszy(wiersz, bukmacherzy=('STS', 'SUPERBET', 'LVBET')):
    k = {b: wiersz.get(b) for b in bukmacherzy if b in wiersz and pd.notna(wiersz.get(b))}
    return max(k.items(), key=lambda x: x[1]) if k else (None, None)


def kupon(tab, nogi):
    """nogi: lista (zdarzenie „A - B”, rynek). Zwraca (wiersze nog, kursy laczne per bukmacher — tylko gdy kazda noga ma kurs)."""
    out = []
    for zd, ry in nogi:
        g, a = [x.strip() for x in re.split(r'\s+-\s+', zd, maxsplit=1)]
        x = tab[(tab.gospodarz == g) & (tab.gosc == a) & (tab.rynek == ry)]
        out.append((zd, ry, x.iloc[0].to_dict() if len(x) else {}))
    laczne = {}
    for b in ('STS', 'SUPERBET', 'LVBET'):
        k = [w.get(b) for _, _, w in out]
        if k and all(v is not None and pd.notna(v) for v in k): laczne[b] = math.prod(k)
    return out, laczne


def main(a):
    if not a or a[0] not in ('porownaj', 'kupon'): sys.exit(__doc__)
    sts = pd.read_csv(a[1], dtype=str, keep_default_na=False)
    pliki = [p for x in a[2:] if not x.startswith('--') for p in sorted(glob.glob(x))]
    pliki = [p for p in pliki if p not in (a[a.index('--ako') + 1] if '--ako' in a else '',)]
    tab, st = tabela(sts, wczytaj_bukmacherow(pliki))
    if a[0] == 'porownaj':
        for b, s in st.items(): print(f'{b}: mecze STS dopasowane {s["jednoznaczne"]}, brak {s["brak"]}, niejednoznaczne {s["kilka"]}')
        for b in [c for c in ('SUPERBET', 'LVBET') if c in tab]:
            r = (tab[b] / tab.STS).dropna()
            print(f'{b}: kursow {len(r)}, lepszy niz STS {int((r > 1.001).sum())}, mediana {r.median():.3f}, '
                  f'podejrzane {int(tab[f"{b}_podejrzany"].sum())}')
        return
    from dzienniki import _czytaj
    ako = _czytaj(a[a.index('--ako') + 1]); d = a[a.index('--data') + 1]
    ako = ako[(ako.data == d) & (ako.noga_nr != 'RAZEM')]
    if '--tag' in a: ako = ako[ako.tag == a[a.index('--tag') + 1]]
    for (tag, nr), k in ako.groupby(['tag', 'nr_kuponu'], sort=False):
        out, laczne = kupon(tab, list(zip(k.zdarzenie, k.rynek)))
        print(f'{tag}#{nr}')
        for zd, ry, w in out:
            print(f'  {zd} | {ry} | ' + ' | '.join(f'{b} {w.get(b, float("nan")):.2f}' for b in ('STS', 'SUPERBET', 'LVBET')))
        if laczne:
            b, k_ = max(laczne.items(), key=lambda x: x[1])
            print('  KURS LACZNY: ' + ' | '.join(f'{x} {v:.3f}' for x, v in laczne.items()) + f'  -> najlepiej {b} {k_:.3f}')


if __name__ == '__main__':
    main(sys.argv[1:])
