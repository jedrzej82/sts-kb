#!/usr/bin/env python3
"""Skladanie kuponow W KODZIE wg INSTRUKCJI v7 (faza 4, 29.09.2026) — zamiast liczenia kombinacji w prozie.
  python3 kupon.py nogi.csv [--depozyt 45.35] [--faza 1] [--wydane-dzis 0] [--kupony-dzis 0] [--wydane-lacznie 9] [--k5-dzis 0]

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
MIX_MIN_KURS = 1.50        # ponizej wyplata po podatku < 1,32 x stawki — „mix” bez sensu   # najlepsze wg P — kombinacje 4 z 25 to 12 650, liczy sie w sekundy


def ev(p, kurs):
    return p * kurs * TAX - 1


def kelly_cwiartka(p, kurs):
    b = kurs * TAX - 1
    return 0.0 if b <= 0 else max(0.0, (p * b - (1 - p)) / b) / 4


def poziom(kryteria):
    k = min(kryteria)
    return 'A' if k >= 6 else 'B' if k >= 4 else 'C' if k >= 2 else 'D'


def wczytaj(plik):
    d = pd.read_csv(plik)
    for c, v in (('sport', ''), ('szacunek', 0), ('polski', 0), ('marza', 1.0), ('kryteria', 0)):
        d[c] = d[c].fillna(v) if c in d else v   # pusta komorka = wartosc domyslna (NaN psul filtr polski == 0)
    d['p'] = d.p.astype(float); d['kurs'] = d.kurs.astype(float)
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
    return dict(nogi=list(c), p=p, kurs=k, ev=ev(p, k), szacunki=int(x.szacunek.sum()),
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
    else:
        raise ValueError(rodzaj)
    return max(kand, key=klucz) if kand else None


def za_pieniadze(o, rodzaj, a, wydane_dzis, kupony_dzis):
    """(stawka_zl, powod_papierowy|None) wg CZESCI A i bramek A10 (poza tym, czego kod nie widzi)."""
    if o['ev'] <= 0: return 0, 'EV <= 0'
    if o['polski']: return 0, 'polski klub/puchar (A1 d)'
    if o['szacunki'] > 1: return 0, 'dwie nogi „szacunek” (A1 e)'
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
    ap.add_argument('plik'); ap.add_argument('--depozyt', type=float, default=45.35)
    ap.add_argument('--faza', type=int, default=1, choices=(1, 2, 3))
    ap.add_argument('--wydane-dzis', type=float, default=0); ap.add_argument('--kupony-dzis', type=int, default=0)
    ap.add_argument('--wydane-lacznie', type=float, default=0)
    ap.add_argument('--k5-dzis', type=float, default=0, help='suma stawek K5 postawionych dzis we wczesniejszych przebiegach (limit 8 zl, 6.7)')
    a = ap.parse_args(argv)
    d = wczytaj(a.plik)
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
