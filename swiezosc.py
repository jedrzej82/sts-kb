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



def kompletnosc(daty, etykieta):
    """Sama data ostatniej danej NIE wystarczy. Zmierzone 21.09.2026: plik wyniki_365_pilka_2026-09
    konczyl sie na 20.09, wiec kontrola swiezosci mowila "ok" — a ten dzien mial 624 mecze przy
    2077 i 2087 w dwie poprzednie niedziele. Raport napisal "dane aktualne", podczas gdy z niedzieli
    brakowalo okolo 70% wynikow, czyli wlasnie tych, ktore najmocniej wazą na formie.
    Dlatego porownujemy liczbe meczow z ostatnich dni do MEDIANY tego samego dnia tygodnia
    z poprzednich czterech tygodni. Zwraca liste (data, ile, oczekiwane, udzial) dla dni podejrzanych."""
    d = pd.to_datetime(pd.Series(list(daty)), errors='coerce').dropna().dt.date
    if d.empty: return []
    ile = d.value_counts().sort_index()
    out = []
    for dzien in [x for x in ile.index if x < DZIS][-2:]:          # dwa ostatnie ZAMKNIETE dni
        wzor = [ile.get(dzien - dt.timedelta(days=7 * k), 0) for k in range(1, 5)]
        wzor = [x for x in wzor if x > 0]
        if len(wzor) < 2: continue                                  # za malo historii na werdykt
        ocz = sorted(wzor)[len(wzor) // 2]
        if ocz and ile[dzien] < 0.55 * ocz:
            out.append((dzien, int(ile[dzien]), int(ocz), ile[dzien] / ocz, etykieta))
    return out



def niemozliwe_mecze(pokaz=12):
    """Wykrywa mecze, ktore fizycznie nie mogly sie odbyc. Dwa warunki, oba zerojedynkowe:
      1) klub gra SAM ZE SOBA — dwie rozne nazwy zostaly scalone w jedna,
      2) klub gra DWA RAZY tego samego dnia w tej samej lidze — do jednej nazwy
         przypisano mecze dwoch roznych klubow.
    22.09.2026: w bazie bylo 122 mecze z punktu 1 (m.in. derby Sydney zapisane jako
    "Sydney FC - Sydney FC") i 756 z punktu 2. Wykryto je RECZNIE, przypadkiem, przy
    okazji innego audytu. Ten test istnieje po to, zeby nastepnym razem krzyknely same:
    to jedyna klasa bledu, ktora psuje dane bez zadnego komunikatu o bledzie."""
    baza = os.path.join(HERE, 'kb.sqlite')
    if not os.path.exists(baza):
        print('  kb.sqlite nie istnieje — pomijam kontrole spojnosci.'); return 0
    try:
        con = sqlite3.connect(baza)
        m = pd.read_sql('select Division, MatchDate, HomeTeam, AwayTeam, src from matches', con)
    except Exception as e:
        print(f'  nie udalo sie odczytac kb.sqlite ({type(e).__name__}: {e}) — pomijam.'); return 0
    m = m.dropna(subset=['HomeTeam', 'AwayTeam'])
    zle = 0

    # 23.09.2026, USTERKA U2: mecz z WYNIKIEM i data pozniejsza niz dzis jest niemozliwy. Tak weszly
    # 26 meczow CHN z datami 23.09-02.10.2026 (matryca Wikipedii ukladana za ostatnim meczem), a kontrola
    # swiezosci pokazywala potem 'wiek -10 d' jako 'ok'.
    _dat = pd.to_datetime(m.MatchDate, errors='coerce')
    przysz = m[_dat > pd.Timestamp.today().normalize()]
    if len(przysz):
        zle += 1
        print(f'  MECZE Z PRZYSZLOSCI: {len(przysz)} meczow z wynikiem i data pozniejsza niz dzis.')
        for (d, s_), n in przysz.groupby(['Division', 'src']).size().sort_values(ascending=False).head(pokaz).items():
            print(f'      [{d}] zrodlo {s_} — {n}')
        print('      Wynik z przyszlosci nie istnieje: to zle przypisana data. Forma i Elo tych druzyn')
        print('      licza stare mecze jako najswiezsze. Napraw uklad dat (uzupelnij_ligi.py), nie dane.')

    sam = m[m.HomeTeam == m.AwayTeam]
    if len(sam):
        zle += 1
        print(f'  KLUB GRA SAM ZE SOBA: {len(sam)} meczow, {sam.HomeTeam.nunique()} nazw, '
              f'{sam.Division.nunique()} lig.')
        for (d, t), n in sam.groupby(['Division', 'HomeTeam']).size().sort_values(ascending=False).head(pokaz).items():
            print(f'      [{d}] "{t}" — {n}')
        print('      To znaczy, ze DWA rozne kluby maja w bazie te sama nazwe. Ich Elo i forma sa')
        print('      wymieszane. Napraw mapowanie nazw (uzupelnij_ligi.py / build_kb.py), nie dane.')

    d2 = m.dropna(subset=['MatchDate'])
    dl = pd.concat([d2.assign(k=d2.HomeTeam), d2.assign(k=d2.AwayTeam)])
    g = dl.groupby(['Division', 'MatchDate', 'k']).size()
    r = g[g > 1].reset_index().rename(columns={0: 'ile'})

    # Rozdzielamy dwie rzeczy, bo maja rozna wage. Detektor, ktory krzyczy przy kazdym
    # przebiegu, przestaje cokolwiek znaczyc — a czesc zrodel (matryce wiki) NIE ZNA dat
    # i przypisuje przyblizone, wiec pojedyncze nalozenia sa tam normalne i nieusuwalne.
    ciezkie = r[r.ile >= 4]
    lekkie = r[r.ile < 4]

    if len(ciezkie):
        zle += 1
        print(f'  LICZBA MECZOW NIEMOZLIWA: {len(ciezkie)} przypadkow, gdzie klub ma 4+ meczow')
        print(f'      jednego dnia (maks {int(ciezkie.ile.max())}). Zadna liga tak nie gra —')
        print(f'      to znaczy, ze caly blok terminarza dostal JEDNA date.')
        for x in ciezkie.sort_values('ile', ascending=False).head(pokaz).itertuples():
            print(f'      [{x.Division}] {x.MatchDate} "{x.k}" — {x.ile} meczow')
        print('      Sprawdz przypisywanie dat w uzupelnij_ligi.py (sciezka wiki).')

    if len(lekkie):
        print(f'  Nalozen po 2-3 mecze dziennie: {len(lekkie)} ({lekkie.k.nunique()} nazw). '
              f'To NIE jest zglaszane jako usterka:')
        print('      matryce wiki nie zawieraja dat i dostaja daty przyblizone, wiec pojedyncze')
        print('      nalozenia sa tam nieuniknione. Zglos dopiero, gdy liczba wyraznie urosnie.')

    if not zle:
        print('  Spojnosc nazw: brak meczow niemozliwych.')
    return zle


def main():
    w, uwagi, niepelne = [], [], []
    kb = os.path.join(HERE, 'kb.sqlite')
    if os.path.exists(kb):
        c = sqlite3.connect(kb)
        d = pd.read_sql('select max(MatchDate) d from matches', c).iloc[0].d
        w.append(('pilka kluby (matches)', d, wiek(d), PROG['matches'], ''))
        niepelne += kompletnosc(pd.read_sql(
            "select MatchDate from matches where MatchDate >= date('now','-40 day')", c).MatchDate,
            'pilka kluby')
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
        niepelne += kompletnosc(s.data[s.data >= str(DZIS - dt.timedelta(days=40))], 'inne sporty')
        for sp, g in s.groupby('sport'):
            a = wiek(g.data.max())
            if a is not None and a > 30:
                uwagi.append((sp, g.data.max(), a))
    else:
        w.append(('sporty_hist.csv', 'BRAK', None, None, 'nie uruchomiono hist_import.py'))

    f = os.path.join(HERE, 'tenis_hist.csv')
    if os.path.exists(f):
        _t = pd.read_csv(f, usecols=['date'], low_memory=False).date
        d = _t.max(); w.append(('tenis (tenis_hist)', d, wiek(d), PROG['tenis'], ''))
        niepelne += kompletnosc(_t[_t >= str(DZIS - dt.timedelta(days=40))], 'tenis')

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
    if niepelne:
        print("\nDNI NIEPELNE — data jest swieza, ale wynikow z tego dnia brakuje:")
        print("  porownanie z mediana tego samego dnia tygodnia z 4 poprzednich tygodni.\n")
        for dzien, ile_, ocz, ud, et in sorted(niepelne):
            print(f"    {et:<14} {dzien}  {ile_:5d} meczow  przy oczekiwanych ~{ocz}  ({ud:.0%})")
        print("\n  To NIE jest przerwa w sezonie — to dzien pobrany w polowie.")
        print("  Najczestsza przyczyna: pliki 365 z Dysku nie zostaly odswiezone po zamknieciu dnia.")
        print("  Napisz o tym w raporcie i traktuj forme z tych dni jako niepelna.")

    print()
    print("Spojnosc nazw druzyn (mecze fizycznie niemozliwe):")
    nm = niemozliwe_mecze()

    # 23.09.2026 (wyd. 24): podsumowanie liczylo razem trzy rozne rzeczy jako "zrodla poza progiem",
    # przez co przy tabeli z samymi "ok" wypisywalo "1 zrodel poza progiem" (to byl dzien niepelny 22.09).
    # Kod wyjscia bez zmian (1 przy dowolnym problemie); zmienia sie tylko opis.
    print()
    czesci = []
    if zle: czesci.append(f"{zle} zrodel PRZETERMINOWANYCH (tabela wyzej)")
    if niepelne: czesci.append(f"{len(niepelne)} dni NIEPELNYCH")
    if nm: czesci.append(f"{nm} problemow spojnosci nazw")
    zle += len(niepelne) + nm
    if zle:
        print(f"UWAGA: {'; '.join(czesci)}. Napisz o tym w raporcie i NIE udawaj, ze dane sa aktualne.")
        print("Jesli przeterminowane sa 'pliki zewn/' — dociagnij biezacy miesiac z Dysku i powtorz hist_import.py.")
    else:
        print("Wszystkie bazy w normie — mozesz analizowac.")
    return 1 if zle else 0


if __name__ == '__main__':
    sys.exit(main())
