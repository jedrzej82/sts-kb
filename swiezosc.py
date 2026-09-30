#!/usr/bin/env python3
"""Kontrola swiezosci WSZYSTKICH baz. Uruchamiaj na koncu KROKU 2b, przed analiza.
Wymog uzytkownika (21.09.2026): kazda baza ma siegac dnia zapytania.
  python3 swiezosc.py            — tabela + kod wyjscia 1, jesli cokolwiek przeterminowane
Uwaga na rozroznienie: "brak swiezych meczow" to NIE to samo co "stare dane".
Reprezentacje graja oknami, wiec dla nich liczy sie data konca ZRODLA, nie data ostatniego meczu."""
import os, sys, sqlite3, datetime as dt
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
# 28.09.2026 (Poprawka 55): „dzien zapytania” to dzien POLSKI, nie UTC (kontener chodzi w UTC).
from zoneinfo import ZoneInfo
DZIS = dt.datetime.now(ZoneInfo('Europe/Warsaw')).date()
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
    # 30.09.2026: dni KALENDARZOWE (wczoraj, przedwczoraj), nie dwa ostatnie dni obecne w danych — dzien bez
    # ani jednego wyniku (28.09 brak, 29.09 jest) byl dotad pomijany. Dni po ostatniej danej zostawiamy
    # kontroli wieku (przebieg.py wymaga wynikow z wczoraj), zeby nie dublowac alarmu.
    ost = max(ile.index)
    for dzien in [DZIS - dt.timedelta(days=k) for k in (2, 1)]:
        if dzien > ost: continue
        ile_d = int(ile.get(dzien, 0))
        wzor = [ile.get(dzien - dt.timedelta(days=7 * k), 0) for k in range(1, 5)]
        wzor = [x for x in wzor if x > 0]
        if len(wzor) < 2: continue                                  # za malo historii na werdykt
        ocz = sorted(wzor)[len(wzor) // 2]
        if ocz and ile_d < 0.55 * ocz:
            out.append((dzien, ile_d, int(ocz), ile_d / ocz, etykieta))
    return out


# 29.09.2026 (proba generalna): 28.09 oznaczony jako „dzien NIEPELNY” (47 meczow klubowych przy ~119),
# choc pliki byly kompletne — trwala przerwa reprezentacyjna (Liga Narodow UEFA i CONCACAF, eliminacje PNA).
# Kluby wtedy nie graja, wiec porownanie z mediana zwyklych tygodni daje falszywy alarm.
# Dzien klubowy jest usprawiedliwiony, gdy w plikach zewn/ (365 i Flashscore) w oknie [dzien-3, dzien+1]
# jest co najmniej PROG_PRZERWY meczow SENIORSKICH reprezentacji. Tabela intl sie tu nie nadaje (zrodlo spoznione).
_KRAJE_REPR = {'international', 'world', 'europe', 'africa', 'asia', 'north america', 'south america', 'oceania'}
_TURNIEJ_REPR = r'nations league|qualif|friendly international|world cup|cup of nations|euro|gold cup|copa america|asian cup'
_TURNIEJ_NIE = r'\bu\d\d\b|women|\(w\)|femen|club|champions|europa|conference|libertadores|sudamericana|concacaf cup'
PROG_PRZERWY = 30        # 28.09.2026: 212; zwykle tygodnie 0–20 (pojedyncze sparingi)


def mecze_reprezentacji(katalog=None):
    """Daty meczow seniorskich reprezentacji z plikow zewn/wyniki_*_pilka_* (bez archiwum)."""
    zd = katalog or os.path.join(HERE, 'zewn')
    if not os.path.isdir(zd): return pd.Series(dtype=object)
    cz = []
    for p in sorted(os.listdir(zd)):
        if not (p.startswith('wyniki_') and '_pilka_' in p) or 'archiwum' in p: continue
        try: z = pd.read_csv(os.path.join(zd, p), usecols=['data', 'kraj', 'turniej'], dtype=str).fillna('')
        except Exception: continue
        t = z.turniej.str.lower()
        z = z[z.kraj.str.strip().str.lower().isin(_KRAJE_REPR) & t.str.contains(_TURNIEJ_REPR)
              & ~t.str.contains(_TURNIEJ_NIE)]
        cz.append(z.data.str[:10])
    if not cz: return pd.Series(dtype=object)
    return pd.to_datetime(pd.concat(cz), errors='coerce').dropna().dt.date


def przerwa_reprezentacyjna(dzien, daty_repr):
    """Liczba meczow seniorskich reprezentacji w oknie [dzien-3, dzien+1] (0 = zwykly tydzien klubowy)."""
    if daty_repr is None or len(daty_repr) == 0: return 0
    return int(((daty_repr >= dzien - dt.timedelta(days=3)) & (daty_repr <= dzien + dt.timedelta(days=1))).sum())


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
        print('      to znaczy, ze caly blok terminarza dostal JEDNA date.')
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
    w, uwagi, niepelne, przerwy = [], [], [], []
    kb = os.path.join(HERE, 'kb.sqlite')
    if os.path.exists(kb):
        c = sqlite3.connect(kb)
        d = pd.read_sql('select max(MatchDate) d from matches', c).iloc[0].d
        w.append(('pilka kluby (matches)', d, wiek(d), PROG['matches'], ''))
        kl = kompletnosc(pd.read_sql(
            "select MatchDate from matches where MatchDate >= date('now','-40 day')", c).MatchDate,
            'pilka kluby')
        repr_ = mecze_reprezentacji() if kl else None
        for x in kl:
            n_r = przerwa_reprezentacyjna(x[0], repr_)
            if n_r >= PROG_PRZERWY: przerwy.append(x + (n_r,))
            else: niepelne.append(x)
        d = pd.read_sql('select max(date) d from intl', c).iloc[0].d
        w.append(('reprezentacje (intl)', d, wiek(d), PROG['intl'],
                  'graja oknami — sam wiek nie swiadczy o zepsuciu'))
        n = pd.read_sql('select Division, max(MatchDate) m from matches group by Division', c)
        sw = (n.m >= str(DZIS - dt.timedelta(days=60))).sum()
        w.append(('  w tym lig swiezych (60 dni)', f'{sw}/{len(n)}', None, None, ''))
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
        # 24.09.2026 (Poprawka 50): wczesniej wiek plikow brany z mtime. Plik swiezo sklonowany z repo
        # (stan z 21.09) mial mtime = dzis i swiezosc pisala „0 d ok”, choc wyniki konczyly sie 20.09.
        # Teraz liczy sie NAJPOZNIEJSZA DATA MECZU w plikach biezacego miesiaca (wyniki_*_RRRR-MM).
        pl = sorted(os.listdir(zd))
        mies = DZIS.strftime('%Y-%m')
        # 30.09.2026: 1. dnia miesiaca plik nowego miesiaca nie ma jeszcze wczoraj (jak w przebieg.kontrola_zewn) —
        # wtedy licza sie tez pliki poprzedniego miesiaca; dla kazdego zrodla najnowsza data z obu
        miesiace = [mies] + ([(DZIS - dt.timedelta(days=1)).strftime('%Y-%m')] if DZIS.day == 1 else [])
        biez = [p for p in pl if any(m in p for m in miesiace) and 'archiwum' not in p and p.startswith('wyniki_')]
        per_zrodlo = {}
        for p in biez:
            try:
                d = pd.read_csv(os.path.join(zd, p), usecols=['data'], low_memory=False).data.astype(str).str[:10].max()
                d = dt.date.fromisoformat(d)
                print(f'  zewn/{p}: ostatni mecz {d}')
                if 'lol' not in p:
                    z = p.rsplit('_', 1)[0]                                  # wyniki_365_pilka
                    per_zrodlo[z] = max(per_zrodlo.get(z, d), d)
            except Exception as e:
                print(f'  zewn/{p}: NIE DA SIE ODCZYTAC ({e})')
        naj = min(per_zrodlo.values()) if per_zrodlo else None            # najstarsze zrodlo = waskie gardlo
        uw = '' if biez else f'brak plikow z biezacego miesiaca ({mies}) — pobierz z Dysku'
        w.append((f'pliki zewn/ biezacy miesiac ({len(biez)} szt.)', naj or 'BRAK', wiek(naj) if naj else None, PROG['zewn'], uw))
    else:
        w.append(('zewn/', 'BRAK', None, None, 'nie pobrano wynikow 365scores'))

    print(f"KONTROLA SWIEZOSCI BAZ — dzien zapytania {DZIS}\n")
    print(f"{'zrodlo':<30} {'ostatnia dana':<14} {'wiek':>6}  {'prog':>5}  uwaga")
    zle = 0
    for nazwa, d, a, prog, uw in w:
        st = ''
        if str(d) == 'BRAK':          # 30.09.2026: brak bazy/plikow to blad, nie pusty wiersz tabeli
            st = 'BRAK DANYCH'; zle += 1
        elif a is not None and prog is not None:
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
    if przerwy:
        print("\nPRZERWA REPREZENTACYJNA — mniej meczow klubowych jest normalne (NIE jest to dzien niepelny):")
        for dzien, ile_, ocz, ud, et, n_r in sorted(przerwy):
            print(f"    {et:<14} {dzien}  {ile_:5d} meczow  przy ~{ocz} w zwykle tygodnie; "
                  f"{n_r} meczow reprezentacji w oknie [-3, +1] dni")
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
    if zle: czesci.append(f"{zle} zrodel PRZETERMINOWANYCH albo BRAK DANYCH (tabela wyzej)")
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
