#!/usr/bin/env python3
"""Skladanie kuponow W KODZIE wg INSTRUKCJI v7 (faza 4, 29.09.2026) — zamiast liczenia kombinacji w prozie.
  python3 kupon.py nogi.csv --depozyt KWOTA [--faza 1] [--wydane-dzis 0] [--kupony-dzis 0] [--wydane-lacznie 9] [--k5-dzis 0]

nogi.csv — jedna noga na wiersz, TYLKO nogi dopuszczone przez kod (linia „✔ NOGA DOPUSZCZONA” / „WERDYKT: NOGA
DOPUSZCZONA”), z P do kuponu z tej linii:
  mecz      identyfikator meczu (np. "Legia - Lech"); dwie nogi z jednego meczu nigdy nie trafiaja do jednego kuponu
  rynek     np. 1X, O1.5
  p         P do kuponu (0..1)
  kurs      kurs z PDF / aplikacji
  kolumny opcjonalne: sport, szacunek (0/1), polski (0/1: polski klub / puchar krajowy), marza (overround, np. 1.07),
                      kryteria (0..6 spelnionych kryteriow A4.3; brak = 0 -> poziom D -> papierowy)

Wypisuje K1, K2, K3, K5 (lub „brak”) i linie NAJPEWNIEJSZY MIX (informacyjnie, 02.10.2026) z lacznym P, kursem, EV po podatku, poziomem, stawka i powodem, gdy kupon jest
PAPIEROWY. Kod pilnuje progow z tabeli DEFINICJE KUPONOW i CZESCI A; nie zna skladow ani kursow z aplikacji —
te kroki (A3, 4.6, 6.4, 6.5) zostaja po stronie przebiegu."""
import argparse
import itertools
import math
import sys

import pandas as pd

TAX = 0.88
FAZY = {1: {'A': 5, 'B': 3, 'C': 2}, 2: {'A': 8, 'B': 5, 'C': 2}, 3: {'A': 8, 'B': 5, 'C': 2}}
LIMIT_DZIEN_ZL, LIMIT_DZIEN_KUPONY, BUDZET = 10, 3, 300
MAKS_NOG_KANDYDATOW = 25
PILKA_KURS = (1.50, 2.00)  # 06.10.2026 (uzytkownik): codziennie jeden najpewniejszy AKO z pilki noznej w tym zakresie
BONUS_KURS = (1.75, 2.20)  # 06.10.2026 (uzytkownik): obrot bonusem LVBET — 3 AKO pod rzad, kazdy kurs >= 1,75; podatek pominiety
MIX_MIN_KURS = 1.50        # ponizej wyplata po podatku < 1,32 x stawki — „mix” bez sensu   # najlepsze wg P — kombinacje 4 z 25 to 12 650, liczy sie w sekundy


def ev(p, kurs):
    return p * kurs * TAX - 1


def kelly_cwiartka(p, kurs):
    b = kurs * TAX - 1
    return 0.0 if b <= 0 else max(0.0, (p * b - (1 - p)) / b) / 4


def poziom(kryteria):
    k = min(kryteria)
    return 'A' if k >= 6 else 'B' if k >= 4 else 'C' if k >= 2 else 'D'


# 03.10.2026 (A1 b): "P jako PRZEDZIAL, EV od DOLNEGO krańca; ujemne → nogi nie ma".
# Raport 2026-10-03 15:00 (usterka 2): kupon.py dawal "DO GRY, stawka 2 zl" dla K3 na nodze SS Monopoli
# (szacunek, przedzial 53%-73%) i dla K5b (SaiPa, "SZACUNEK: < 10 meczow"), bo liczyl EV z P punktowego.
# Dla Monopoli EV od dolnego krania to -11,4%, nie +5,3%. typuj.py drukuje przedzialy o szerokosci ok. +-10 pp,
# wiec przy braku jawnej kolumny p_min bierzemy p - 0,10 dla kazdej nogi oznaczonej jako szacunek.
MARGINES_SZACUNKU = 0.10


def wczytaj(plik):
    d = pd.read_csv(plik)
    for c, v in (('sport', ''), ('szacunek', 0), ('polski', 0), ('marza', 1.0), ('kryteria', 0), ('ev_dodatni', 1)):
        d[c] = d[c].fillna(v) if c in d else v   # pusta komorka = wartosc domyslna (NaN psul filtr polski == 0)
    d['p'] = d.p.astype(float); d['kurs'] = d.kurs.astype(float)
    # p_min: dolny kraniec przedzialu P. Jawna kolumna wygrywa; inaczej p - margines dla nog "szacunek".
    jawne = d['p_min'].astype(float) if 'p_min' in d else pd.Series([float('nan')] * len(d), index=d.index)
    d['p_min'] = jawne.fillna(d.p - d.szacunek.astype(float) * MARGINES_SZACUNKU).clip(lower=0.0, upper=1.0)
    return d[(d.p > 0) & (d.kurs > 1)].reset_index(drop=True)


def _kombinacje(d, nmin, nmax):
    idx = list(d.sort_values('p', ascending=False).index[:MAKS_NOG_KANDYDATOW])
    for n in range(nmin, nmax + 1):
        for c in itertools.combinations(idx, n):
            if len({d.at[i, 'mecz'] for i in c}) == n:   # kazda noga z innego meczu (A5)
                yield c


def _opis(d, c):   # indeksy c pochodza z d (ramki bez resetu indeksu — .loc dziala na filtrowanej ramce)
    x = d.loc[list(c)]
    p = float(x.p.prod()); k = float(x.kurs.prod())
    # p_min dolicza wczytaj(); ramki budowane wprost (testy, starsze wywolania) go nie maja — liczymy w locie.
    p_dol = float(x.p_min.prod() if 'p_min' in x else
                  (x.p - x.szacunek.astype(float) * MARGINES_SZACUNKU).clip(lower=0.0).prod())
    return dict(nogi=list(c), p=p, kurs=k, ev=ev(p, k), szacunki=int(x.szacunek.sum()),
                p_dol=p_dol, ev_dol=ev(p_dol, k),
                polski=bool(x.polski.any()), marza_max=float(x.marza.max()), poziom=poziom(list(x.kryteria)))


def najlepszy(d, rodzaj):
    """Zwraca opis kuponu danego rodzaju albo None. Progi z tabeli DEFINICJE KUPONOW (v7)."""
    kand = []
    if rodzaj == 'K1':
        for c in _kombinacje(d, 1, 3):
            o = _opis(d, c)
            if o['p'] >= 0.78 and o['kurs'] >= 1.42 and o['ev'] > 0: kand.append(o)
        klucz = lambda o: (o['p'], o['ev'])
    elif rodzaj == 'K2':
        dd = d[d.p >= 0.75]
        for c in _kombinacje(dd, 2, 4):
            o = _opis(dd, c)
            if 1.9 <= o['kurs'] <= 3.0 and o['ev'] > 0: kand.append(o)
        klucz = lambda o: (o['p'], o['ev'])
    elif rodzaj == 'K3':
        for c in _kombinacje(d[d.p >= 0.55], 1, 1):
            o = _opis(d, c)
            if o['ev'] >= 0.05: kand.append(o)
        klucz = lambda o: (o['ev'], o['p'])
    elif rodzaj == 'K5':
        dd = d[d.p >= 0.70]
        for zakres in ((2.0, 2.5), (1.8, 2.8)):   # brak w 2,00–2,50 -> najblizszy 1,80–2,80 (napisz to)
            for c in _kombinacje(dd, 2, 4):
                o = _opis(dd, c)
                if zakres[0] <= o['kurs'] <= zakres[1] and o['szacunki'] <= 1:
                    o['zakres'] = zakres; kand.append(o)
            if kand: break
        klucz = lambda o: (o['ev'], o['p'])   # K5: najwyzsze EV; EV <= 0 -> PAPIEROWY (nie odpada)
    elif rodzaj == 'MIX':
        # 02.10.2026 (decyzja uzytkownika): „najpewniejszy mix” — kupon o NAJWYZSZYM lacznym P (2-4 nogi z roznych
        # meczow, kurs laczny >= MIX_MIN_KURS, maks. 1 szacunek); przy rownym P — wiecej sportow, potem wyzsze EV.
        # TYLKO INFORMACYJNIE: najwyzsze P to zwykle EV < 0 (podatek 12%), stawke ustala CZESC A, nie ten kupon.
        for c in _kombinacje(d, 2, 4):
            o = _opis(d, c)
            if o['kurs'] >= MIX_MIN_KURS and o['szacunki'] <= 1:
                o['sporty'] = d.loc[list(c), 'sport'].nunique(); kand.append(o)
        klucz = lambda o: (round(o['p'], 4), o['sporty'], o['ev'])
    elif rodzaj == 'BONUS':
        # 06.10.2026 (uzytkownik): obrot bonusem LVBET — trzy AKO pod rzad z kursem >= 1,75, wszystkie musza wejsc.
        # Liczy sie WYLACZNIE szansa wejscia (EV i podatek nieistotne: grane srodki bonusowe). Kurs tuz nad progiem =
        # najwyzsze P, wiec gorna granica 2,20 tylko odcina kupony bez sensu.
        dd = d[d.sport.astype(str).str.lower().isin(['', 'pilka', 'piłka', 'pilka nozna', 'piłka nożna'])]
        for c in _kombinacje(dd, 2, 3):
            o = _opis(dd, c)
            if BONUS_KURS[0] <= o['kurs'] <= BONUS_KURS[1] and o['szacunki'] == 0: kand.append(o)
        kand.sort(key=lambda o: (-round(o['p'], 4), o['kurs']))
        return kand    # lista (najlepsze pierwsze) — przebieg wybiera pierwszy, ktory w LVBET ma kurs >= 1,75
    elif rodzaj == 'PILKA':
        # 06.10.2026 (decyzja uzytkownika): codziennie JEDEN kupon z pilki noznej, kurs laczny 1,50–2,00, 2–3 nogi
        # z roznych meczow, NAJWYZSZE laczne P. Nogi: wszystkie, ktore przeszly bramki typuj.py (takze EV <= 0).
        # Stawka i tak wg CZESCI A (EV <= 0 -> tylko papierowy/bonus) — kupon wybiera najpewniejszy, nie oplacalny.
        dd = d[d.sport.astype(str).str.lower().isin(['', 'pilka', 'piłka', 'pilka nozna', 'piłka nożna'])]
        for c in _kombinacje(dd, 2, 3):
            o = _opis(dd, c)
            if PILKA_KURS[0] <= o['kurs'] <= PILKA_KURS[1] and o['szacunki'] <= 1: kand.append(o)
        klucz = lambda o: (round(o['p'], 4), -o['szacunki'], o['ev'])
    else:
        raise ValueError(rodzaj)
    return max(kand, key=klucz) if kand else None


def za_pieniadze(o, rodzaj, a, wydane_dzis, kupony_dzis):
    """(stawka_zl, powod_papierowy|None) wg CZESCI A i bramek A10 (poza tym, czego kod nie widzi)."""
    if o['ev'] <= 0: return 0, 'EV <= 0'
    if o['polski']: return 0, 'polski klub/puchar (A1 d)'
    if o['szacunki'] > 1: return 0, 'dwie nogi „szacunek” (A1 e)'
    if o['szacunki'] and o.get('ev_dol', o['ev']) <= 0:
        return 0, (f'EV od DOLNEGO krania przedzialu {o["ev_dol"]:+.1%} <= 0 '
                   f'(P {o["p"]:.1%} -> {o["p_dol"]:.1%}; A1 b)')
    if o['marza_max'] > 1.10: return 0, f'marza {o["marza_max"]:.1%} > 110% (6.3)'
    if o['poziom'] == 'D': return 0, 'poziom D (A4.3)'
    lacznie = getattr(a, 'lacznie', a.wydane_lacznie)   # 29.09.2026: z kuponami tego przebiegu (main)
    if lacznie >= BUDZET: return 0, f'budzet {BUDZET} zl wyczerpany (A4.4)'
    if kupony_dzis >= LIMIT_DZIEN_KUPONY: return 0, f'limit {LIMIT_DZIEN_KUPONY} kuponow dziennie (A4.4)'
    kw = FAZY[a.faza][o['poziom']]
    kelly = kelly_cwiartka(o['p'], o['kurs']) * a.depozyt
    st = min(kw, math.floor(kelly), LIMIT_DZIEN_ZL - wydane_dzis, BUDZET - lacznie)
    if rodzaj == 'K5':
        # suma K5 dnia maks. 8 zl (6.7). 29.09.2026 (przeglad): dawniej min(st, 8) bez K5 z wczesniejszych
        # przebiegow — 12:00 K5 5 zl + 15:00 K5 5 zl = 10 zl. Wolajacy podaje --k5-dzis.
        st = min(st, 8 - getattr(a, 'k5_dzis', 0))
        if o['kurs'] < 2.0: st = min(st, 2)      # A10: K5 z kursem < 2,0 -> maks. 2 zl
    if st < 1: return 0, f'stawka < 1 zl (¼ Kelly {kelly:.2f} zl, limit dnia)'
    return int(st), None


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # 07.10.2026 (audyt usterek, Raport 02.10 21:00 nr 7): domyslny depozyt 45,35 zl byl wpisany na sztywno — przebieg bez
    # --depozyt liczyl stawki Kelly z nieaktualnej kwoty (uzytkownik potwierdzil 50 zl 06.10). Depozyt tylko jawnie.
    ap.add_argument('plik'); ap.add_argument('--depozyt', type=float, default=None)
    ap.add_argument('--faza', type=int, default=1, choices=(1, 2, 3))
    ap.add_argument('--wydane-dzis', type=float, default=0); ap.add_argument('--kupony-dzis', type=int, default=0)
    ap.add_argument('--wydane-lacznie', type=float, default=0)
    ap.add_argument('--k5-dzis', type=float, default=0, help='suma stawek K5 postawionych dzis we wczesniejszych przebiegach (limit 8 zl, 6.7)')
    ap.add_argument('--stawka-kd', type=float, default=5.0, help='stala stawka KUPONU DNIA (decyzja uzytkownika 08.10)')
    a = ap.parse_args(argv)
    if a.depozyt is None or a.depozyt <= 0:
        sys.exit('BLAD: podaj --depozyt (aktualny stan konta z Bilansu/POPRAWEK) — bez niego stawki Kelly bylyby z nieaktualnej kwoty')
    wsz = wczytaj(a.plik)
    d = wsz[wsz.ev_dodatni.astype(int) == 1].reset_index(drop=True)   # K1–K5 i MIX: tylko nogi z EV > 0 (jak dotad)
    print(f'KUPON.PY — {len(d)} nog dopuszczonych, faza {a.faza}, depozyt {a.depozyt:.2f} zl, '
          f'dzis {a.wydane_dzis:.0f} zl / {a.kupony_dzis} kup., lacznie {a.wydane_lacznie:.0f}/{BUDZET} zl')
    wydane, kupony, uzyte = a.wydane_dzis, a.kupony_dzis, set()
    a.lacznie = a.wydane_lacznie   # 29.09.2026 (przeglad): budzet 300 zl liczony RAZEM z kuponami tego przebiegu
    for rodzaj in ('K1', 'K2', 'K3', 'K5'):
        dd = d[~d.index.isin(uzyte)] if rodzaj in ('K2', 'K3') else d   # w K1–K3 zdarzenie tylko w jednym kuponie
        # najpierw nogi, ktore moga isc za pieniadze (bez polskich klubow A1 d i marzy > 110% z 6.3);
        # dopiero gdy z nich nie da sie zlozyc kuponu — wszystkie (wynik bedzie PAPIEROWY z powodem)
        o = najlepszy(dd[(dd.polski == 0) & (dd.marza <= 1.10)], rodzaj) or najlepszy(dd, rodzaj)
        if o is None:
            print(f'\n{rodzaj}: brak (zadna kombinacja nie spelnia progow)'); continue
        st, powod = za_pieniadze(o, rodzaj, a, wydane, kupony)
        if rodzaj in ('K1', 'K2', 'K3'): uzyte.update(o['nogi'])
        print(f'\n{rodzaj}: laczne P {o["p"]:.1%} | kurs {o["kurs"]:.2f} | EV {o["ev"]:+.1%} | poziom {o["poziom"]}'
              + (f' | zakres kursu {o["zakres"][0]:.2f}–{o["zakres"][1]:.2f}' if o.get('zakres') and o['zakres'] != (2.0, 2.5) else ''))
        for i in o['nogi']:
            r = d.loc[i]
            print(f'   {r.mecz} | {r.rynek} | P {r.p:.1%} | kurs {r.kurs:.2f}' + (' | SZACUNEK' if r.szacunek else ''))
        if powod:
            print(f'   → PAPIEROWY — POWÓD ODRZUCENIA: {powod}')
        else:
            wydane += st; kupony += 1; a.lacznie += st
            print(f'   → DO GRY: stawka {st} zl (wyplata {st * TAX * o["kurs"]:.2f} zl); kurs minimalny {1 / (o["p"] * TAX):.2f}'
                  f' — PRZED POSTAWIENIEM przepisz kursy z aplikacji i przelicz EV')
    print('\n' + linia_mix(najlepszy(d[(d.polski == 0) & (d.marza <= 1.10)], 'MIX'), d))
    print('\n' + '\n'.join(linie_pilka(wsz, a, wydane, kupony)))
    print('\n' + '\n'.join(linie_bonus(wsz)))
    print('\n' + '\n'.join(linie_niski(wsz)))
    print('\n' + '\n'.join(linie_dnia(wsz, a.stawka_kd)))


# 08.10.2026 (decyzja uzytkownika: „codziennie musze miec jeden kupon AKO, ktory wejdzie”): KUPON DNIA — 2 nogi pilkarskie
# z roznych meczow o NAJWYZSZEJ lacznej szansie, przy kursie lacznym >= 1,15 (wygrana po podatku 12% wieksza od stawki).
# Rozliczenia 28.09–06.10 (dwie najpewniejsze nogi dnia): weszlo 8 z 9 dni, srednie P 75%, kurs 1,29. Pojedyncze nogi
# P 0,85–0,90 trafialy 83% (n=42) — stad korekta 3 pp na noge. EV jest UJEMNE (marza + podatek): to kupon „dla przyjemnosci”,
# stala mala stawka z budzetu 300 zl (CZESC A bez zmian), nie zalecenie zarobkowe.
DNIA_NOGI = 2
DNIA_MIN_P = 0.80          # P nogi po korekcie
DNIA_KOREKTA = 0.03
DNIA_MIN_KURS = 1.15       # 1,15 x 0,88 = 1,012 — wygrany kupon zwraca wiecej niz stawke


def kupon_dnia(wsz):
    """Para nog pilkarskich (rozne mecze, bez szacunkow, bez polskich klubow, marza <= 110%) o najwyzszym iloczynie P po
    korekcie, z kursem lacznym >= DNIA_MIN_KURS. None, gdy takiej pary nie ma."""
    import itertools
    x = wsz[(wsz.sport.astype(str).str.lower().isin(['pilka', 'piłka', ''])) & (wsz.szacunek.astype(int) == 0)
            & (wsz.polski == 0) & (wsz.marza <= 1.10)]
    x = x.assign(pk=x.p - DNIA_KOREKTA)
    x = x[x.pk >= DNIA_MIN_P].sort_values('pk', ascending=False).drop_duplicates('mecz').head(15)
    best = None
    for c in itertools.combinations(x.index, DNIA_NOGI):
        k = float(x.loc[list(c), 'kurs'].prod())
        if k < DNIA_MIN_KURS: continue
        p = float(x.loc[list(c), 'pk'].prod())
        if best is None or p > best['p'] or (p == best['p'] and k > best['kurs']):
            best = dict(nogi=list(c), p=p, kurs=k, ev=p * k * TAX - 1)
    return best


def linie_dnia(wsz, stawka=5.0):
    o = kupon_dnia(wsz)
    if o is None:
        return [f'KUPON DNIA ({DNIA_NOGI} nogi, P nogi >= {DNIA_MIN_P:.0%} po korekcie −{DNIA_KOREKTA * 100:.0f} pp, kurs >= '
                f'{DNIA_MIN_KURS:.2f}): brak w tym przebiegu — za malo pewnych nog pilkarskich']
    out = [f'KUPON DNIA: szansa {o["p"]:.0%} (po korekcie −{DNIA_KOREKTA * 100:.0f} pp/noga) | kurs {o["kurs"]:.2f} | '
           f'stawka {stawka:.0f} zl -> wygrana na reke {stawka * o["kurs"] * TAX:.2f} zl | EV {o["ev"]:+.1%}']
    for i in o['nogi']:
        r = wsz.loc[i]
        out.append(f'   {r.mecz} | {r.rynek} | P {r.p - DNIA_KOREKTA:.1%} | kurs {r.kurs:.2f}')
    out.append(f'   → decyzja uzytkownika 08.10: codziennie jeden — stala stawka {stawka:.0f} zl z budzetu 300 zl, tag KD; '
               f'srednio na minusie (EV {o["ev"]:+.0%}), szansa, ze NIE wejdzie: {1 - o["p"]:.0%}')
    return out


# 07.10.2026 (prosba uzytkownika): AKO NISKI KURS — 6–10 nog pilkarskich o wysokim P na jednym kuponie. Backtest 219 dni
# (03–10.2026, 41 376 meczow spoza czesci uczacej): pojedyncze nogi P 0,90–0,97 sa skalibrowane (0,943 -> 0,943), ale WYBOR
# najpewniejszych nog dnia zawyza: 8 nog P kuponu 80,7%, weszlo 69,9% (ok. 1,8 pp na noge) — stad korekta 2 pp na noge.
# „3 dni z rzedu” wypada w 32% okresow (8 nog) samym przypadkiem. Przy marzy ~5% na noge i podatku 12% zwrot szacowany
# −40% … −55% — dlatego TYLKO PAPIEROWY; za pieniadze dopiero po decyzji uzytkownika (3 dni z rzedu) i z EV > 0 na kursach.
NISKI_NOGI = (6, 10)
NISKI_MIN_P = 0.90
NISKI_KOREKTA = 0.02


def ako_niski(wsz):
    """Najwiecej (do 10) nog pilkarskich z roznych meczow o P - 2 pp >= 90%, malejaco po P; None, gdy < 6."""
    x = wsz[(wsz.sport.astype(str).str.lower().isin(['pilka', 'piłka', ''])) & (wsz.szacunek.astype(int) == 0)]
    x = x.assign(pk=x.p - NISKI_KOREKTA)
    x = x[x.pk >= NISKI_MIN_P].sort_values('pk', ascending=False).drop_duplicates('mecz').head(NISKI_NOGI[1])
    if len(x) < NISKI_NOGI[0]: return None
    p, kurs = float(x.pk.prod()), float(x.kurs.prod())
    return dict(nogi=list(x.index), p=p, kurs=kurs, ev=p * kurs * TAX - 1)


def linie_niski(wsz):
    o = ako_niski(wsz)
    if o is None:
        return [f'AKO NISKI KURS ({NISKI_NOGI[0]}–{NISKI_NOGI[1]} nog, P >= {NISKI_MIN_P:.0%} po korekcie −{NISKI_KOREKTA * 100:.0f} pp): brak — '
                f'za malo pewnych nog pilkarskich z roznych meczow']
    out = [f'AKO NISKI KURS ({len(o["nogi"])} nog): laczne P {o["p"]:.1%} (po korekcie −{NISKI_KOREKTA * 100:.0f} pp/noga) | '
           f'kurs {o["kurs"]:.2f} | EV {o["ev"]:+.1%} | PAPIEROWY (nowy typ — obserwacja)']
    for i in o['nogi']:
        r = wsz.loc[i]
        out.append(f'   {r.mecz} | {r.rynek} | P {r.p - NISKI_KOREKTA:.1%} | kurs {r.kurs:.2f}')
    if o['kurs'] * TAX <= 1:
        # 07.10.2026 (test na ofertach STS 02–06.10): najnizsze kursy dnia (1,01–1,05) daja kurs laczny 1,07–1,14 — kupon
        # wchodzi, ale po podatku 12% wyplata jest MNIEJSZA od stawki (prog: kurs laczny > 1,14)
        out.append(f'   → UWAGA: kurs laczny {o["kurs"]:.2f} — nawet wygrany kupon po podatku 12% zwraca mniej niz stawke '
                   f'(potrzeba > {1 / TAX:.2f})')
    out.append(f'   → zapisz w ako_log jako papierowy (tag AKON); szansa, ze NIE wejdzie: {1 - o["p"]:.0%}; '
               f'3 dni z rzedu samym przypadkiem: ok. {o["p"] ** 3:.0%}')
    return out


def linie_bonus(wsz, ile=3):
    """06.10.2026: AKO BONUS LVBET — do 3 kandydatow (rozne nogi) z najwyzszym P przy kursie >= 1,75."""
    kand = najlepszy(wsz[(wsz.polski == 0) & (wsz.marza <= 1.10)], 'BONUS')   # bez polskich klubow (A1 d) i marzy > 110%
    if not kand:
        return [f'AKO BONUS LVBET (kurs >= {BONUS_KURS[0]:.2f}): brak — za malo pewnych nog pilkarskich (bez szacunkow) na taki kurs']
    out, uzyte = [f'AKO BONUS LVBET (kurs >= {BONUS_KURS[0]:.2f}; liczy sie tylko szansa wejscia — srodki bonusowe):'], set()
    for o in kand:
        if uzyte & set(o['nogi']): continue
        uzyte |= set(o['nogi'])
        nogi = ' + '.join(f'{wsz.at[i, "mecz"]} {wsz.at[i, "rynek"]} ({wsz.at[i, "p"]:.0%} @{wsz.at[i, "kurs"]:.2f})' for i in o['nogi'])
        out.append(f'   {len(out)}. P {o["p"]:.1%} | kurs STS {o["kurs"]:.2f} | {nogi}')
        if len(out) > ile: break
    out.append('   → graj PIERWSZY kandydat, ktory w LVBET ma kurs laczny >= 1,75 (kursy3.py kupon; LVBET bywa nizej niz STS)')
    p1 = kand[0]['p']
    out.append(f'   (szansa wejscia najlepszego: {p1:.0%}; trzy takie kupony pod rzad: ok. {p1 ** 3:.0%} — to nie gwarancja)')
    return out


def linie_pilka(wsz, a, wydane, kupony):
    """06.10.2026: AKO PILKA DNIA — najpewniejszy kupon z pilki 1,50–2,00 (zawsze wypisany; stawka wg CZESCI A)."""
    o = najlepszy(wsz[(wsz.polski == 0) & (wsz.marza <= 1.10)], 'PILKA') or najlepszy(wsz, 'PILKA')
    if o is None:
        return [f'AKO PILKA DNIA ({PILKA_KURS[0]:.2f}–{PILKA_KURS[1]:.2f}): brak — za malo nog pilkarskich po bramkach '
                f'na kurs w tym zakresie (2–3 nogi z roznych meczow)']
    out = [f'AKO PILKA DNIA ({PILKA_KURS[0]:.2f}–{PILKA_KURS[1]:.2f}): laczne P {o["p"]:.1%} | kurs {o["kurs"]:.2f} | '
           f'EV {o["ev"]:+.1%} | poziom {o["poziom"]}']
    for i in o['nogi']:
        r = wsz.loc[i]
        out.append(f'   {r.mecz} | {r.rynek} | P {r.p:.1%} | kurs {r.kurs:.2f}' + (' | SZACUNEK' if r.szacunek else ''))
    st, powod = za_pieniadze(o, 'PILKA', a, wydane, kupony)
    out.append(f'   → za pieniadze: stawka {st} zl wg CZESCI A' if not powod else
               f'   → NIE za wlasne pieniadze ({powod}) — najpewniejszy kupon dnia: papierowy albo ze srodkow bonusowych')
    out.append(f'   (szansa, ze kupon NIE wejdzie: {1 - o["p"]:.0%} — to najpewniejszy kupon dnia, nie pewniak)')
    return out


def linia_mix(o, d):
    """Linia „NAJPEWNIEJSZY MIX” do POWIADOMIENIA (02.10.2026) — zawsze z EV i informacja, ze to nie zalecenie."""
    if o is None:
        return f'NAJPEWNIEJSZY MIX: brak (za malo nog dopuszczonych na kurs laczny >= {MIX_MIN_KURS:.2f})'
    nogi = ' + '.join(f'{d.at[i, "mecz"]} {d.at[i, "rynek"]} ({d.at[i, "p"]:.0%} @{d.at[i, "kurs"]:.2f})' for i in o['nogi'])
    return (f'NAJPEWNIEJSZY MIX: {nogi} | laczne P {o["p"]:.1%} | kurs {o["kurs"]:.2f} | EV {o["ev"]:+.1%} | '
            + ('EV > 0 — mozna rozwazyc (stawka wg CZESCI A)' if o['ev'] > 0
               else 'EV < 0 — informacyjnie, NIE zalecenie (srednio traci po podatku)'))


if __name__ == '__main__':
    main(sys.argv[1:])
