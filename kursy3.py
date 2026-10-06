"""KURSY TRZECH BUKMACHEROW (02.10.2026): STS (PDF oferty, oferta.py) + Superbet + LVBET (termux/kursy_bukmacherow.py
z telefonu uzytkownika -> kursy_bukmacherow_*.csv.gz w baza-wiedzy).

Dopasowanie meczu STS do meczu bukmachera — bez zgadywania:
  ten sam sport, ta sama data, godzina +-5 min (czas polski po obu stronach), obie nazwy podobne (dopasuj.podobne),
  te same znaczniki (kobiety / U21 / rezerwy; LVBET „(Wom)” = kobiety) i DOKLADNIE jeden taki mecz.
Kursy porownywane tylko dla tego samego kodu rynku (1, X, 2, 1X, X2, 12, O1.5, U3.5, BTTS_tak, Zwyciezca 1 …).
Kontrola wiarygodnosci: kurs bukmachera rozny od STS o wiecej niz 35% = PODEJRZANY (inny mecz/rynek) — nie uzywany.

Uzycie:
  python3 kursy3.py porownaj KURSY_STS.csv.gz KURSY_BUKMACHEROW.csv.gz [...]   — pokrycie i zgodnosc kursow
  python3 kursy3.py kupon KURSY_STS.csv.gz [KURSY_BUKMACHEROW.csv.gz ...] --ako ako_log.csv --data D [--godzina GG:MM] [--tag K5]
     — dla KAZDEGO kuponu linia „GRAJ U: <bukmacher> @kurs” (do POWIADOMIENIA/Telegrama; bez pliku z telefonu = STS)
       i kurs kazdej nogi u STS / SUPERBET / LVBET"""
import glob
import math
import os
import re
import sys

import pandas as pd

import nazwy

TOLERANCJA_MIN = 5
MAKS_ROZNICA = 0.35
BUKMACHERZY = ('STS', 'SUPERBET', 'LVBET')


_OBCIETE = re.compile(r'\s*(?:\.\.\.|…)\s*$')


def _obciete(n):
    """PDF STS ucina dlugie nazwy: „Polonia Lidzbark W...”, „Podravka Kopri...”. Zwraca (czy_obcieta, nazwa bez
    niepelnego ostatniego czlonu). 03.10: ucięte „W...” bylo czytane jako znacznik kobiet, a z „Podravka Kopri...”
    znikal znacznik [K] — mecz nie laczyl sie z LVBET/Superbet."""
    n = str(n)
    if not _OBCIETE.search(n): return False, n
    t = _OBCIETE.sub('', n).split()
    return True, ' '.join(t[:-1]) if len(t) > 1 else ' '.join(t)


def _zn(n):
    """Znaczniki nazwy; None = nieznane (nazwa ucieta w PDF — znacznik mogl byc w ucietej czesci)."""
    ob, n = _obciete(n)
    if ob: return None
    return nazwy.znaczniki(re.sub(r'\((?:Wom|Women)\)', '(W)', str(n), flags=re.I))


def _zn_rowne(a, b):
    return a is None or b is None or a == b


# 02.10.2026: pisownia tego samego miasta u roznych bukmacherow (STS „Pilzno”, Superbet „Plzen”; „Munchen” obok
# „Monachium” -> Munich w nazwy.EGZONIMY). „Konga”: Superbet/LVBET odmieniaja („DR Konga”, „Demokratyczna Republika
# Konga”), STS pisze „DR Kongo” (Raport 02.10 12:00). Tylko porownanie nazw u bukmacherow — rozliczen i typowania nie dotyczy.
PISOWNIA = {'konga': 'kongo', 'pilzno': 'plzen', 'pilsen': 'plzen', 'munchen': 'munich', 'muenchen': 'munich', 'chernigiv': 'chernihiv',
            'kobenhavn': 'copenhagen', 'koebenhavn': 'copenhagen'}
# cala nazwa (nie czlon — „WKS Slask” to klub): 03.10 Superbet „WKS - Kamerun”, STS „Wybrzeże Kości Słoniowej - Kamerun”
CALE_NAZWY = {'wks': 'wybrzeze kosci sloniowej'}


def _pisownia(slowo):
    """ASCII, male litery; niemieckie/skandynawskie oe/ue/ae = o/u/a („Koelner” = „Kolner”, „Nykoebing” = „Nykobing”)."""
    import dopasuj
    def jedno(w):
        w = PISOWNIA.get(w, w)
        return re.sub(r'(?<=[a-z])(o|u|a)e', r'\1', w) if len(w) > 3 else w
    # separatory („Al-Jazira”, „M.Gonzalez/A.Molteni”) zostaja — dziela nazwe na czlony
    return ''.join(jedno(c) if c.isalnum() else c for c in re.split(r'([^a-z0-9]+)', dopasuj._ascii(slowo)))


def _rdzen(n):
    """Nazwa bez znacznikow (U21, (W), II, Res. …) — znaczniki porownuje _zn, a wspolne „U21” to nie podobna nazwa
    (02.10: „Slowenia U21 - Holandia U21” bylo niejednoznaczne z „Austria U21 - Dania U21” o tej samej godzinie)."""
    n = _obciete(n)[1]
    n = CALE_NAZWY.get(_pisownia(str(n).strip().lower()), n)
    t = [x for x in re.split(r'\s+', re.sub(r'\((?:Wom|Women)\)', '', str(n), flags=re.I))
         if not nazwy.ZNACZNIK.match(x.strip('[](){}<>.,;:'))]
    return ' '.join(_pisownia(x) or x for x in t) or str(n)


_STS_SEKCJE = {'1. drużyna - strzeli gola|TAK': 'gosp_O0.5', '2. drużyna - strzeli gola|TAK': 'gość_O0.5',
               'Zakład bez remisu|1': 'DNB_1', 'Zakład bez remisu|2': 'DNB_2'}


def _kod_sts(sts_k):
    """Rynki STS zapisane przez oferta.py jako „sekcja|wybor” -> kody bukmacherow: „Zwycięzca meczu|1” = Zwyciezca 1
    (dwudrogowy, z dogrywka), „Liczba punktów (z dogrywką)|-” z linia 157.5 = U157.5."""
    r = sts_k.rynek.astype(str)
    lin = pd.to_numeric(sts_k.get('linia', pd.Series('', index=sts_k.index)), errors='coerce')
    zw = r.str.extract(r'^Zwycięzca meczu\|([12])$')[0]
    pk = r.str.extract(r'^Liczba punktów \(z dogrywką\)\|([+-])$')[0]
    out = r.where(zw.isna(), 'Zwyciezca ' + zw.fillna(''))
    # 04.10.2026 (Raporty 15:00 i 18:00): rynki pilki zapisane przez oferta.py jako „sekcja|wybor” — telefon zapisuje je
    # kodami (gosp_O0.5, DNB_1), wiec Portugalia – Norwegia gosp_O0.5 nie miala kursu SUPERBET/LVBET mimo obecnosci w pliku.
    out = out.replace(_STS_SEKCJE)
    ok = pk.notna() & lin.notna() & (lin % 1 != 0)
    out = out.where(~ok, pk.map({'+': 'O', '-': 'U'}).fillna('') + lin.map(lambda v: f'{v:g}'))
    return sts_k.assign(rynek=out)


SPORTY_Z_REMISEM = ('pilka', 'piłka', 'pilka nozna', 'piłka nożna', 'hokej', 'hokej na lodzie', 'reczna', 'piłka ręczna',
                    'pilka reczna', 'futsal')


def kod_ako(rynek, sport='', gosp='', gosc=''):
    """Rynek nogi z ako_log (zapisy bywaja rozne: „Liczba goli ponizej 3.5”, „poniżej 3,5 gola”, „Podwojna szansa 12”,
    „Zwyciezca - Fenerbahce”, „1 (60 min)”) -> kod rynku bukmachera. W sportach bez remisu „1”/„2” = Zwyciezca
    (dzienniki._zakres_rynku: caly mecz). Nierozpoznany zapis zostaje bez zmian (wtedy brak kursu, nie zgadujemy)."""
    import dopasuj
    s = re.sub(r'\s+', ' ', str(rynek)).strip()
    t = dopasuj._ascii(s).replace(',', '.').replace('_', ' ').strip()
    remis = str(sport).strip().lower() in SPORTY_Z_REMISEM
    m = re.fullmatch(r'([12x])\s*\(?60\s*min\)?|([12x]) ?60min', t)
    if m: return (m.group(1) or m.group(2)).upper()
    # 04.10.2026 (Raport 15:00 usterka 6): P130 zapisuje nogi „Zwyciezca meczu” kodem Z1/Z2 (hokej, kosz, NFL) —
    # tu nie bylo tego kodu i kazda taka noga miala „SUPERBET nan | LVBET nan”.
    m = re.fullmatch(r'z([12])(?: \(.*\))?', t.lower())
    if m: return f'Zwyciezca {m.group(1)}'
    if t in ('1', '2') and str(sport).strip() and not remis: return f'Zwyciezca {t}'
    m = re.fullmatch(r'(?:podwojna szansa )?(1x|x2|12)', t)
    if m: return m.group(1).upper()
    m = re.fullmatch(r'(?:liczba goli )?(ponizej|powyzej) (\d+(?:\.\d+)?)(?: gol[ai]?)?', t)
    if m: return ('U' if m.group(1) == 'ponizej' else 'O') + f'{float(m.group(2)):g}'
    m = re.fullmatch(r'zwyciezca(?: meczu)?\s*[:\-]?\s*(.+)', t)
    if m:
        k = m.group(1).strip()
        if k in ('1', '2'): return f'Zwyciezca {k}'
        st = [i for i, n in ((1, gosp), (2, gosc)) if n and dopasuj.podobne(k, n)]
        return f'Zwyciezca {st[0]}' if len(st) == 1 else s
    return s


def _podobne(a, b):
    import dopasuj
    return dopasuj.podobne(_rdzen(a), _rdzen(b))


# 06.10.2026: czlony, ktore nie odrozniaja klubow (dopasuj.OGOLNE ich nie ma — tam sluza do nauki aliasow). Przez nie
# STS „Cleethorpes Town - Hyde United” pasowalo w Superbet do siebie ORAZ do „Alfreton Town - United of Manchester”
# (Town~Town, United~United) — dwie pary = brak dopasowania; gdyby wlasciwego meczu nie bylo, zostalaby jedna ZLA para.
GENERYCZNE = frozenset('town united utd city county rovers wanderers athletic athletico atletico sporting sport sports '
                       'real deportivo union club borough albion'.split())


def _wyrazne(a, b):
    """Czy dwie nazwy maja wspolny czlon, ktory odroznia kluby (nie Town/United/City...)."""
    import dopasuj
    for x in dopasuj.tokeny(_rdzen(a)):
        for y in dopasuj.tokeny(_rdzen(b)):
            k, d = (x, y) if len(x) <= len(y) else (y, x)
            if len(k) >= 3 and d.startswith(k) and k not in GENERYCZNE and d not in GENERYCZNE: return True
    return False


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
             and _zn_rowne(_zn(r.gospodarz), _zn(x.gospodarz)) and _zn_rowne(_zn(r.gosc), _zn(x.gosc))
             and not (_zn(r.gospodarz) is None and _zn(r.gosc) is None)]   # obie strony uciete = znaczniki nieznane
        # para musi miec choc jedna strone z wyraznym wspolnym czlonem; z kilku par wygrywa jedyna wyrazna po obu stronach
        c = [x for x in c if _wyrazne(r.gospodarz, x.gospodarz) or _wyrazne(r.gosc, x.gosc)]
        if len({(x.gospodarz, x.gosc) for x in c}) > 1:
            obie = [x for x in c if _wyrazne(r.gospodarz, x.gospodarz) and _wyrazne(r.gosc, x.gosc)]
            if len({(x.gospodarz, x.gosc) for x in obie}) == 1: c = obie
        pary = {(x.gospodarz, x.gosc) for x in c}
        if len(pary) == 1:
            wynik[(r.sport, r.data_meczu, r.gospodarz, r.gosc)] = next(iter(pary)); stat['jednoznaczne'] += 1
        else:
            stat['kilka' if pary else 'brak'] += 1
    return wynik, stat


def tabela(sts_k, buk_k):
    """Kurs STS i kazdego bukmachera dla tych samych (mecz, rynek). Kolumny: sport, data_meczu, gospodarz, gosc, rynek,
    STS, SUPERBET, LVBET (+ *_podejrzany)."""
    sts_k = _kod_sts(sts_k)
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
        # 05.10.2026 (Raport 15:00 usterka 2): „nan” mylil dwa przypadki — meczu nie ma w pliku z telefonu ALBO mecz jest,
        # ale bukmacher nie wystawil tego rynku (LVBET 14:32: Backa Topola bez „gol gospodarza”, Tatran bez O1.5)
        baza[f'{b}_mecz'] = [(s, d, g, a) in mapa for s, d, g, a in zip(baza.sport, baza.data_meczu, baza.gospodarz, baza.gosc)]
        baza[f'{b}_podejrzany'] = (baza[b] / baza.STS - 1).abs() > MAKS_ROZNICA
        baza.loc[baza[f'{b}_podejrzany'], b] = float('nan')
    return baza, staty


def najlepszy(wiersz, bukmacherzy=('STS', 'SUPERBET', 'LVBET')):
    k = {b: wiersz.get(b) for b in bukmacherzy if b in wiersz and pd.notna(wiersz.get(b))}
    return max(k.items(), key=lambda x: x[1]) if k else (None, None)


def kupon(tab, nogi):
    """nogi: lista (zdarzenie „A - B”, rynek[, kurs STS z ako_log[, sport]]) — rynek przez kod_ako. Zwraca (wiersze nog, kursy laczne per bukmacher —
    tylko gdy KAZDA noga ma kurs u tego bukmachera). Kurs STS z ako_log uzupelnia brak w ofercie (kupon zawsze ma STS)."""
    out = []
    for n in nogi:
        zd = n[0]
        g, a = ([x.strip() for x in re.split(r'\s+-\s+', zd, maxsplit=1)] + [''])[:2]
        ry = kod_ako(n[1], n[3] if len(n) > 3 else '', g, a)
        x = tab[(tab.gospodarz == g) & (tab.gosc == a) & (tab.rynek == ry)] if len(tab) else tab
        w = x.iloc[0].to_dict() if len(x) else {}
        if len(n) > 2 and pd.isna(w.get('STS', float('nan'))):
            w['STS'] = pd.to_numeric(str(n[2]).replace(',', '.'), errors='coerce')
        out.append((zd, ry, w))
    laczne = {}
    for b in BUKMACHERZY:
        k = [w.get(b) for _, _, w in out]
        if k and all(v is not None and pd.notna(v) for v in k): laczne[b] = math.prod(k)
    return out, laczne


def gdzie_grac(out, laczne):
    """Linia „GRAJ U: …” do POWIADOMIENIA (Telegram) i AKO DNIA — ZAWSZE jest (02.10.2026, decyzja uzytkownika).
    Najwyzszy kurs laczny u bukmachera, u ktorego jest KAZDA noga; remis -> kolejnosc STS, SUPERBET, LVBET.
    Brak kursow innych bukmacherow -> STS z powodem.
    02.10.2026 (Raport 12:00, K5): noga nieznaleziona w pliku z telefonu to NIE dowod, ze bukmacher jej nie ma
    (LVBET mial „DR Kongo - Uganda” pod inna nazwa i godzina 17:00 zamiast 15:00 i dawal 2,35 przy STS 2,19).
    Gdy bukmacher bez kompletu jest lepszy na nogach, ktore ma — linia mowi wprost: porownanie NIEPELNE, sprawdz."""
    if not laczne:
        return 'GRAJ U: STS (brak kursu lacznego u zadnego bukmachera — sprawdz kurs w aplikacji STS)'
    b = max(BUKMACHERZY, key=lambda x: (laczne.get(x, 0), -BUKMACHERZY.index(x)))
    inne, sprawdz = [], []
    for x in BUKMACHERZY:
        if x == b: continue
        if x in laczne: inne.append(f'{x} {laczne[x]:.3f}'); continue
        brak = [str(i + 1) for i, (_, _, w) in enumerate(out) if pd.isna(w.get(x, float('nan')))]
        bez_rynku = [str(i + 1) for i, (_, _, w) in enumerate(out) if pd.isna(w.get(x, float('nan'))) and w.get(f'{x}_mecz')]
        bez_meczu = [i for i in brak if i not in bez_rynku]
        inne.append(f'{x} ' + '; '.join(([f'nie znaleziono nogi {",".join(bez_meczu)}'] if bez_meczu else [])
                                        + ([f'brak rynku nogi {",".join(bez_rynku)}'] if bez_rynku else [])))
        # na nogach, ktore ma: iloraz kursow wzgledem wybranego bukmachera
        wsp = [(w.get(x), w.get(b)) for _, _, w in out
               if pd.notna(w.get(x, float('nan'))) and pd.notna(w.get(b, float('nan')))]
        if wsp and math.prod(k / kb for k, kb in wsp) > 1.001:
            sprawdz.append(f'{x} (lepszy o {100 * (math.prod(k / kb for k, kb in wsp) - 1):.0f}% na nogach, ktore ma; '
                           f'noga {",".join(brak)} nieznaleziona w pliku)')
    linia = f'GRAJ U: {b} @{laczne[b]:.3f} (' + ' | '.join(inne) + ')'
    if sprawdz:
        linia += ' — POROWNANIE NIEPELNE, sprawdz w aplikacji: ' + '; '.join(sprawdz)
    return linia


def _kurs_opis(w, b):
    k = w.get(b, float('nan'))
    if pd.notna(k): return f'{b} {k:.2f}'
    return f'{b} brak rynku' if w.get(f'{b}_mecz') else f'{b} nan'


def _arg(a, nazwa, dom=None):
    return a[a.index(nazwa) + 1] if nazwa in a else dom


def main(a):
    if not a or a[0] not in ('porownaj', 'kupon'): sys.exit(__doc__)
    sts = pd.read_csv(a[1], dtype=str, keep_default_na=False)
    wartosci = {a[i + 1] for i, x in enumerate(a[:-1]) if x.startswith('--')}
    pliki = [p for x in a[2:] if not x.startswith('--') and x not in wartosci for p in sorted(glob.glob(x))]
    tab, st = tabela(sts, wczytaj_bukmacherow(pliki))
    if a[0] == 'porownaj':
        for b, s in st.items(): print(f'{b}: mecze STS dopasowane {s["jednoznaczne"]}, brak {s["brak"]}, niejednoznaczne {s["kilka"]}')
        for b in [c for c in ('SUPERBET', 'LVBET') if c in tab]:
            r = (tab[b] / tab.STS).dropna()
            print(f'{b}: kursow {len(r)}, lepszy niz STS {int((r > 1.001).sum())}, mediana {r.median():.3f}, '
                  f'podejrzane {int(tab[f"{b}_podejrzany"].sum())}')
        return
    from dzienniki import _czytaj
    ako = _czytaj(_arg(a, '--ako'))
    ako = ako[(ako.data == _arg(a, '--data')) & (ako.noga_nr != 'RAZEM')]
    if '--godzina' in a: ako = ako[ako.godzina_uruchomienia == _arg(a, '--godzina')]
    if '--tag' in a: ako = ako[ako.tag == _arg(a, '--tag')]
    pob = sorted({f'{m.group(1)} {m.group(2)}:{m.group(3)}'
                  for p in pliki for m in [re.search(r'(\d{4}-\d\d-\d\d)_(\d\d)-(\d\d)', p)] if m})
    print('kursy SUPERBET/LVBET: ' + (f'pobrane {pob[-1]}' if pob else 'BRAK pliku z telefonu — wszystkie kupony u STS'))
    for (tag, nr), k in ako.groupby(['tag', 'nr_kuponu'], sort=False):
        out, laczne = kupon(tab, list(zip(k.zdarzenie, k.rynek, k.kurs, k.sport if 'sport' in k else [''] * len(k))))
        print(f'{tag}#{nr} {gdzie_grac(out, laczne)}')
        for zd, ry, w in out:
            print(f'  {zd} | {ry} | ' + ' | '.join(_kurs_opis(w, b) for b in BUKMACHERZY))


if __name__ == '__main__':
    main(sys.argv[1:])
