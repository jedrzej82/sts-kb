#!/usr/bin/env python3
"""Kontrola swiezosci WSZYSTKICH baz. Uruchamiaj na koncu KROKU 2b, przed analiza.
Wymog uzytkownika (21.09.2026): kazda baza ma siegac dnia zapytania.
  python3 swiezosc.py            — tabela + kod wyjscia 1, jesli cokolwiek przeterminowane
Uwaga na rozroznienie: "brak swiezych meczow" to NIE to samo co "stare dane".
Reprezentacje graja oknami, wiec dla nich liczy sie data konca ZRODLA, nie data ostatniego meczu."""
import os, sys, sqlite3, datetime as dt
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DZIS = dt.date.today()
PROG = {'matches': 2, 'sporty': 2, 'tenis': 2, 'zewn': 2, 'intl': 45}   # dozwolony wiek w dniach


def wiek(d):
    try: return (DZIS - dt.date.fromisoformat(str(d)[:10])).days
    except Exception: return None


def main():
    w, uwagi = [], []
    kb = os.path.join(HERE, 'kb.sqlite')
    if os.path.exists(kb):
        c = sqlite3.connect(kb)
        d = pd.read_sql('select max(MatchDate) d from matches', c).iloc[0].d
        w.append(('pilka kluby (matches)', d, wiek(d), PROG['matches'], ''))
        d = pd.read_sql('select max(date) d from intl', c).iloc[0].d
        w.append(('reprezentacje (intl)', d, wiek(d), PROG['intl'],
                  'graja oknami — sam wiek nie swiadczy o zepsuciu'))
        n = pd.read_sql('select Division, max(MatchDate) m from matches group by Division', c)
        sw = (n.m >= str(DZIS - dt.timedelta(days=60))).sum()
        w.append((f'  w tym lig swiezych (60 dni)', f'{sw}/{len(n)}', None, None, ''))
        c.close()
    else:
        w.append(('kb.sqlite', 'BRAK', None, None, 'nie zbudowano bazy'))

    f = os.path.join(HERE, 'sporty_hist.csv')
    if os.path.exists(f):
        s = pd.read_csv(f, usecols=['data', 'sport'], low_memory=False)
        d = s.data.max(); w.append(('inne sporty (sporty_hist)', d, wiek(d), PROG['sporty'], ''))
        for sp, g in s.groupby('sport'):
            a = wiek(g.data.max())
            if a is not None and a > 30:
                uwagi.append((sp, g.data.max(), a))
    else:
        w.append(('sporty_hist.csv', 'BRAK', None, None, 'nie uruchomiono hist_import.py'))

    f = os.path.join(HERE, 'tenis_hist.csv')
    if os.path.exists(f):
        d = pd.read_csv(f, usecols=['date'], low_memory=False).date.max()
        w.append(('tenis (tenis_hist)', d, wiek(d), PROG['tenis'], ''))

    zd = os.path.join(HERE, 'zewn')
    if os.path.isdir(zd):
        pl = sorted(os.listdir(zd))
        naj = max((dt.date.fromtimestamp(os.path.getmtime(os.path.join(zd, p))) for p in pl), default=None)
        w.append((f'pliki zewn/ ({len(pl)} szt.)', naj, wiek(naj) if naj else None, PROG['zewn'], ''))
    else:
        w.append(('zewn/', 'BRAK', None, None, 'nie pobrano wynikow 365scores'))

    print(f"KONTROLA SWIEZOSCI BAZ — dzien zapytania {DZIS}\n")
    print(f"{'zrodlo':<30} {'ostatnia dana':<14} {'wiek':>6}  {'prog':>5}  uwaga")
    zle = 0
    for nazwa, d, a, prog, uw in w:
        st = ''
        if a is not None and prog is not None:
            if a > prog: st = 'PRZETERMINOWANE'; zle += 1
            else: st = 'ok'
        print(f"{nazwa:<30} {str(d):<14} {('' if a is None else str(a)+' d'):>6}  {('' if prog is None else str(prog)+' d'):>5}  {st} {uw}")
    if uwagi:
        print("\nSPORTY BEZ SWIEZYCH WYNIKOW — to NIE jest automatycznie blad:")
        print("  przerwa miedzysezonowa wyglada tak samo jak zepsute zrodlo. Rozstrzyga jedno pytanie:")
        print("  CZY TEN SPORT JEST DZIS W OFERCIE STS? Jesli tak — to usterka, zglos ja.")
        print("  Jesli nie ma go w ofercie — to przerwa w sezonie i nie rob nic.\n")
        for sp, d, a in sorted(uwagi, key=lambda x: -x[2]):
            print(f"    {sp:<22} ostatni mecz {d}  ({a} dni temu)")
    print()
    if zle:
        print(f"UWAGA: {zle} zrodel poza progiem. Napisz o tym w raporcie i NIE udawaj, ze dane sa aktualne.")
        print("Jesli przeterminowane sa 'pliki zewn/' — dociagnij biezacy miesiac z Dysku i powtorz hist_import.py.")
    else:
        print("Wszystkie bazy w normie — mozesz analizowac.")
    return 1 if zle else 0


if __name__ == '__main__':
    sys.exit(main())
