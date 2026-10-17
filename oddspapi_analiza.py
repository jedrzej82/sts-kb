"""oddspapi_analiza.py — kurs Superbet a kurs uczciwy Pinnacle (TRYB OBSERWACJI, 17.10.2026).
Nic w przebiegu, typowaniu ani rozliczeniach z tego nie korzysta do pomiaru i decyzji użytkownika. Dane zbiera
apps_script/oddspapi.gs do folderu „oddspapi” na Dysku: oddspapi_hist_*.json.gz (serie kursów) i oddspapi_*_RANO.json.gz
(lista meczów z nazwami).

  python3 oddspapi_analiza.py oddspapi_hist_*.json.gz [--listy oddspapi_*_RANO.json.gz ...] [--prog 0.03]
                              [--podatek 0.12] [--nog 4] [--csv nogi.csv]
                              [--rynki oddspapi_rynki.json] [--rozliczenia oddspapi_rozl_*.json.gz ...]

--rynki: nazwy rynków i wyników (inaczej numery OddsPapi). --rozliczenia: wynik nogi (WIN/LOSE/PUSH…) z OddsPapi
settlements — skrypt rozlicza tylko mecze z nogą powyżej kursu uczciwego, więc to wynik NAPRAWDĘ granych okazji:
zysk na 1 zł po podatku (WIN: kurs*(1-podatek)-1, LOSE: -1, PUSH/CANCELLED: 0, połówki po połowie).

Kurs uczciwy = Pinnacle bez marży (proporcjonalnie w obrębie jednego rynku; tylko rynki, w których Pinnacle i Superbet
mają ten sam zestaw >= 2 wyników — inaczej niepełny rynek zawyża P). Mecz jeszcze nierozegrany: „zamknięcie” = ostatni kurs.
Dla każdego wyniku, który ma też Superbet:
  przewaga = P_uczciwe * kurs_Superbet - 1        (przed podatkiem)
  EV       = P_uczciwe * kurs_Superbet * (1 - podatek) - 1
Dwa momenty Pinnacle: 6 h przed startem (to, co wiadomo w chwili gry) i zamknięcie (najlepsza miara prawdy).
Kurs Superbet: 6 h przed startem (tyle przed meczem gramy kupony z przebiegu 12:00).
Przewaga > PODEJRZANE (35%, jak w kursy3.py) = prawie na pewno inna linia/rynek albo stary kurs — liczona osobno.

AKO na dzień: z nóg o przewadze >= --prog względem Pinnacle 6 h przed (jedna, najlepsza noga z meczu), --nog najlepszych;
EV kuponu = iloczyn(P_zamkniecia * kurs) * (1 - podatek) - 1 — podatek płaci się raz od kuponu, przewagi nóg się mnożą.
"""
import argparse
import collections
import datetime as dt
import gzip
import json
import math
import sys
from zoneinfo import ZoneInfo

PL = ZoneInfo('Europe/Warsaw')
PODEJRZANE = 0.35
RYNKI = {101: '1X2'}            # znane identyfikatory OddsPapi; reszta jako „rynek NNN”
WYNIKI = {101: '1', 102: 'X', 103: '2'}


def wczytaj(sciezka):
    with open(sciezka, 'rb') as f:
        dane = f.read()
    if dane[:2] == b'\x1f\x8b':
        dane = gzip.decompress(dane)
    return json.loads(dane.decode('utf-8'))


def serie(pliki):
    """{(id, rynek): {'pinnacle': {wynik: (otw, w6, zam)}, 'superbet': {...}}} — ostatni plik wygrywa przy dublach."""
    out = collections.defaultdict(lambda: collections.defaultdict(dict))
    for p in pliki:
        for s in wczytaj(p).get('serie', []):
            fid, bk, rynek, wynik, otw, w6, zam = s[:7]
            bk = 'pinnacle' if bk == 'pinnacle' else 'superbet' if bk.startswith('superbet') else bk
            out[(fid, int(rynek))][bk][int(wynik)] = (otw, w6, zam)
    return out


def mecze(listy):
    m = {}
    for p in listy or []:
        for x in wczytaj(p).get('mecze', []):
            m[x['id']] = x
    return m


def rynki(sciezka):
    if not sciezka:
        return {}
    return {int(k): v for k, v in wczytaj(sciezka).items()}


def rozliczenia(pliki):
    out = {}
    for p in pliki or []:
        for fid, rynek, wynik, res in wczytaj(p).get('wyniki', []):
            out[(fid, int(rynek), int(wynik))] = res
    return out


def zysk(res, kurs, podatek):
    """Zysk na 1 zł stawki po podatku (podatek od stawki, jak w Polsce); None, gdy nierozstrzygnięty."""
    wygrana = kurs * (1 - podatek) - 1
    return {'WIN': wygrana, 'LOSE': -1.0, 'PUSH': 0.0, 'CANCELLED': 0.0, 'HALFWIN': wygrana / 2, 'HALFLOSS': -0.5}.get(res)


def nazwa_nogi(n, ryn):
    r = ryn.get(n['rynek'])
    if not r:
        return f"{RYNKI.get(n['rynek'], n['rynek'])} {WYNIKI.get(n['wynik'], n['wynik']) if n['rynek'] == 101 else n['wynik']}"
    nazwa, handicap, okres, wyn = r[0], r[1], r[2], r[3]
    return f"{nazwa}{' ' + str(handicap) if handicap else ''}{'' if okres in (None, 'fulltime') else ' (' + str(okres) + ')'}: " \
           f"{wyn.get(str(n['wynik']), n['wynik'])}"


def uczciwe(kursy):
    """{wynik: kurs} -> {wynik: P bez marży}; None, gdy < 2 wyniki albo brak kursu."""
    if len(kursy) < 2 or any(not k or k <= 1 for k in kursy.values()):
        return None
    odw = {w: 1 / k for w, k in kursy.items()}
    s = sum(odw.values())
    return {w: v / s for w, v in odw.items()}


def nogi(dane, podatek):
    out = []
    for (fid, rynek), bk in dane.items():
        pin, sb = bk.get('pinnacle', {}), bk.get('superbet', {})
        # 17.10.2026 (prawdziwe dane, Roma - Genoa): Pinnacle z niepełnym zestawem wyników rynku dawał po zdjęciu marży
        # zawyżone P i „przewagę” +20% — liczymy tylko rynki, gdzie oba bukmacherzy mają TEN SAM zestaw wyników
        if not pin or not sb or set(pin) != set(sb):
            continue
        p6 = uczciwe({w: v[1] for w, v in pin.items()})
        pz = uczciwe({w: v[2] for w, v in pin.items()})
        for wynik, (_, k6, _) in sb.items():
            if not k6 or wynik not in pin:
                continue
            n = dict(id=fid, rynek=rynek, wynik=wynik, kurs_sb=k6, kurs_pin6=pin[wynik][1], kurs_pinz=pin[wynik][2])
            n['p6'] = p6[wynik] if p6 else None
            n['pz'] = pz[wynik] if pz else None
            n['przewaga6'] = n['p6'] * k6 - 1 if n['p6'] else None
            n['przewagaz'] = n['pz'] * k6 - 1 if n['pz'] else None
            n['ev_z'] = n['pz'] * k6 * (1 - podatek) - 1 if n['pz'] else None
            out.append(n)
    return out


def _proc(x):
    return '—' if x is None else f'{100 * x:+.1f}%'


def raport(lista, mecze_info, prog, podatek, ile_nog, ryn=None, rozl=None):
    ryn, rozl = ryn or {}, rozl or {}
    linie = []
    ok = [n for n in lista if n['przewaga6'] is not None]
    podejrz = [n for n in ok if n['przewaga6'] > PODEJRZANE or (n['przewagaz'] or 0) > PODEJRZANE]
    dobre = [n for n in ok if n not in podejrz]
    meczow = len({n['id'] for n in lista})
    linie.append(f'NOGI: {len(lista)} wyników Superbet z kursem Pinnacle w {meczow} meczach; z kursem uczciwym {len(ok)}; '
                 f'podejrzane (> {PODEJRZANE:.0%}) {len(podejrz)} — pominięte')
    if not dobre:
        linie.append('Brak nóg do oceny.')
        return linie
    for nazwa, klucz in (('vs Pinnacle 6 h przed', 'przewaga6'), ('vs Pinnacle zamknięcie', 'przewagaz')):
        w = sorted(n[klucz] for n in dobre if n[klucz] is not None)
        if not w:
            continue
        sr = sum(w) / len(w)
        linie.append(f'PRZEWAGA Superbet {nazwa}: średnio {_proc(sr)}, mediana {_proc(w[len(w) // 2])}; '
                     f'> 0: {sum(x > 0 for x in w)}/{len(w)}, >= 3%: {sum(x >= 0.03 for x in w)}, >= 5%: {sum(x >= 0.05 for x in w)}, '
                     f'>= podatek ({podatek:.0%}): {sum(x >= podatek / (1 - podatek) for x in w)}')
    po_rynku = collections.defaultdict(list)
    for n in dobre:
        if n['przewagaz'] is not None:
            po_rynku[RYNKI.get(n['rynek'], f"rynek {n['rynek']}") if n['rynek'] in RYNKI and not ryn else f"rynek {n['rynek']}"].append(n['przewagaz'])
    for r, w in sorted(po_rynku.items(), key=lambda kv: -len(kv[1]))[:8]:
        if ryn and r.startswith('rynek '):
            x = ryn.get(int(r.split()[1]))
            r = f"{x[0]}{' ' + str(x[1]) if x and x[1] else ''}" if x else r
        linie.append(f'  {r}: {len(w)} nóg, średnia przewaga vs zamknięcie {_proc(sum(w) / len(w))}, > 0: {sum(x > 0 for x in w)}')
    # AKO dziennie
    po_dniu = collections.defaultdict(dict)
    for n in dobre:
        if n['przewaga6'] < prog or n['pz'] is None:
            continue
        t = mecze_info.get(n['id'], {}).get('t')
        dzien = dt.datetime.fromtimestamp(t, PL).date().isoformat() if t else '?'
        best = po_dniu[dzien].get(n['id'])
        if best is None or n['przewaga6'] > best['przewaga6']:
            po_dniu[dzien][n['id']] = n
    linie.append(f'AKO (nogi z przewagą >= {prog:.0%} vs Pinnacle 6 h przed, jedna z meczu, najwyżej {ile_nog}; EV vs zamknięcie, '
                 f'podatek {podatek:.0%} raz od kuponu):')
    if not po_dniu:
        linie.append('  brak nóg spełniających próg')
    for dzien in sorted(po_dniu):
        wyb = sorted(po_dniu[dzien].values(), key=lambda n: -n['przewaga6'])[:ile_nog]
        kurs = math.prod(n['kurs_sb'] for n in wyb)
        ev = math.prod(n['pz'] * n['kurs_sb'] for n in wyb) * (1 - podatek) - 1
        wyn = [rozl.get((n['id'], n['rynek'], n['wynik'])) for n in wyb]
        if all(wyn):
            traf = 'WSZEDŁ' if all(x == 'WIN' for x in wyn) else 'nie wszedł' if any(x in ('LOSE', 'HALFLOSS') for x in wyn) else 'zwrot/połowa'
        else:
            traf = f'rozliczone {sum(bool(x) for x in wyn)}/{len(wyn)} nóg'
        linie.append(f'  {dzien}: dostępnych nóg {len(po_dniu[dzien])}, w kuponie {len(wyb)}, kurs {kurs:.2f}, EV {_proc(ev)} — {traf}')
    rozliczone = [(n, rozl.get((n['id'], n['rynek'], n['wynik']))) for n in dobre if n['przewaga6'] >= prog]
    rozliczone = [(n, r) for n, r in rozliczone if zysk(r, n['kurs_sb'], podatek) is not None]
    if rozl:
        z = [zysk(r, n['kurs_sb'], podatek) for n, r in rozliczone]
        if z:
            linie.append(f'WYNIKI nóg z przewagą >= {prog:.0%} (rozliczenia OddsPapi): {len(z)} nóg, trafione '
                         f"{sum(r == 'WIN' for _, r in rozliczone)}, zysk {sum(z):+.2f} zł na {len(z)} zł stawek "
                         f'({_proc(sum(z) / len(z))}), oczekiwany wg zamknięcia {_proc(sum(n["ev_z"] for n, _ in rozliczone) / len(z))}')
        else:
            linie.append(f'WYNIKI: brak rozliczonych nóg z przewagą >= {prog:.0%}')
    linie.append('NAJWIĘKSZE PRZEWAGI (vs zamknięcie):')
    for n in sorted([n for n in dobre if n['przewagaz'] is not None], key=lambda n: -n['przewagaz'])[:15]:
        m = mecze_info.get(n['id'], {})
        nazwa = f"{m.get('a', '?')} - {m.get('b', '?')}" if m else n['id']
        res = rozl.get((n['id'], n['rynek'], n['wynik']))
        linie.append(f"  {nazwa} | {nazwa_nogi(n, ryn)}{' [' + res + ']' if res else ''} | Superbet {n['kurs_sb']} | "
                     f"Pinnacle 6h {n['kurs_pin6']} zam. {n['kurs_pinz']} | przewaga {_proc(n['przewagaz'])}, EV po podatku {_proc(n['ev_z'])}")
    return linie


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('pliki', nargs='+')
    ap.add_argument('--listy', nargs='*', default=[])
    ap.add_argument('--prog', type=float, default=0.03)
    ap.add_argument('--podatek', type=float, default=0.12)
    ap.add_argument('--nog', type=int, default=4)
    ap.add_argument('--csv')
    ap.add_argument('--rynki')
    ap.add_argument('--rozliczenia', nargs='*', default=[])
    a = ap.parse_args(argv)
    lista = nogi(serie(a.pliki), a.podatek)
    info = mecze(a.listy)
    for l in raport(lista, info, a.prog, a.podatek, a.nog, rynki(a.rynki), rozliczenia(a.rozliczenia)):
        print(l)
    if a.csv:
        import csv
        with open(a.csv, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(lista[0]) if lista else ['id'])
            w.writeheader()
            w.writerows(lista)
    return lista


if __name__ == '__main__':
    main(sys.argv[1:])
