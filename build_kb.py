#!/usr/bin/env python3
"""Buduje bazę meczów: GitHub (xgabora 2000-2026 + openfootball bieżący sezon + reprezentacje) + delta.csv z Drive.
Wynik: kb.sqlite (tabele: matches, intl). Użycie: python3 build_kb.py [--refresh]"""
import os, sys, json, glob, re, sqlite3, subprocess, difflib, unicodedata
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
os.makedirs(RAW, exist_ok=True)
SRC = {
    'Matches.csv': 'https://raw.githubusercontent.com/xgabora/Club-Football-Match-Data-2000-2025/main/data/Matches.csv',
    'EloRatings.csv': 'https://raw.githubusercontent.com/xgabora/Club-Football-Match-Data-2000-2025/main/data/EloRatings.csv',
    'intl_results.csv': 'https://raw.githubusercontent.com/martj42/international_results/master/results.csv',
}
OF_MAP = {'en.1': 'E0', 'en.2': 'E1', 'en.3': 'E2', 'en.4': 'E3', 'es.1': 'SP1', 'es.2': 'SP2', 'de.1': 'D1',
          'de.2': 'D2', 'it.1': 'I1', 'it.2': 'I2', 'fr.1': 'F1', 'fr.2': 'F2', 'nl.1': 'N1', 'pt.1': 'P1',
          'be.1': 'B1', 'sco.1': 'SC0', 'tr.1': 'T1', 'gr.1': 'G1'}
DIV_NAME = {'E0': 'Anglia Premier League', 'E1': 'Anglia Championship', 'E2': 'Anglia League One', 'E3': 'Anglia League Two',
            'EC': 'Anglia National League', 'SP1': 'Hiszpania LaLiga', 'SP2': 'Hiszpania Segunda', 'I1': 'Włochy Serie A',
            'I2': 'Włochy Serie B', 'D1': 'Niemcy Bundesliga', 'D2': 'Niemcy 2. Bundesliga', 'F1': 'Francja Ligue 1',
            'F2': 'Francja Ligue 2', 'N1': 'Holandia Eredivisie', 'P1': 'Portugalia Liga', 'B1': 'Belgia Pro League',
            'T1': 'Turcja Super Lig', 'G1': 'Grecja Super League', 'SC0': 'Szkocja Premiership', 'SC1': 'Szkocja Championship',
            'SC2': 'Szkocja League One', 'SC3': 'Szkocja League Two', 'ARG': 'Argentyna', 'AUT': 'Austria', 'BRA': 'Brazylia',
            'CHN': 'Chiny', 'DEN': 'Dania', 'FIN': 'Finlandia', 'IRL': 'Irlandia', 'JAP': 'Japonia', 'MEX': 'Meksyk',
            'NOR': 'Norwegia', 'POL': 'Polska Ekstraklasa', 'ROM': 'Rumunia', 'RUS': 'Rosja', 'SUI': 'Szwajcaria',
            'SWE': 'Szwecja', 'USA': 'USA MLS'}


def fetch(refresh):
    for fn, url in SRC.items():
        p = os.path.join(RAW, fn)
        if refresh or not os.path.exists(p):
            subprocess.run(['curl', '-s', '-m', '300', '-o', p, url], check=True)
    of = os.path.join(RAW, 'football.json')
    if not os.path.exists(of):
        subprocess.run(['git', 'clone', '-q', '--depth', '1', 'https://github.com/openfootball/football.json.git', of], check=True)
    elif refresh:
        subprocess.run(['git', '-C', of, 'pull', '-q'], check=False)


def norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r"\b(fc|cf|afc|ac|sc|ssc|as|us|ud|cd|rc|rcd|sd|ca|sv|vfl|vfb|tsg|fk|sk|bk|if|club|calcio|balompie|de|futbol|football|1\.|\d{4})\b", ' ', s)
    return re.sub(r'[^a-z]', '', s)


ALIAS = {'Athletic Club': 'Ath Bilbao', 'Borussia Mönchengladbach': "M'gladbach", 'FC Internazionale Milano': 'Inter',
         'NEC': 'Nijmegen', 'Queens Park Rangers FC': 'QPR', 'Sporting Clube de Braga': 'Sp Braga',
         'Sporting Clube de Portugal': 'Sp Lisbon', 'Stade Rennais FC 1901': 'Rennes', 'Wolverhampton Wanderers FC': 'Wolves',
         # 22.09.2026 — cztery pary, w ktorych stare dopasowanie podstawialo INNY klub.
         # Oba kluby z kazdej pary sa w bazie osobno, wiec nie chodzilo o pisownie.
         'RCD Espanyol de Barcelona': 'Espanol', 'RCD Espanyol': 'Espanol', 'Espanyol': 'Espanol',
         'Paris Saint-Germain FC': 'Paris SG', 'Paris Saint-Germain': 'Paris SG',
         'AE Lárissa': 'Larisa', 'AE Larissa': 'Larisa',
         'İstanbul Başakşehir': 'Buyuksehyr', 'Istanbul Basaksehir': 'Buyuksehyr',
         'Aris Saloniki': 'Aris', 'AEK Athen': 'AEK', 'PAOK Saloniki': 'PAOK',
         # Kluby, ktorych ocena podobienstwa wypada PONIZEJ progu, mimo ze dopasowanie jest
         # poprawne. Zmierzone 22.09.2026: oceny par poprawnych (0,50-0,62) NAKLADAJA SIE na
         # oceny par blednych (0,54-0,77) — "Espanyol -> Barcelona" dostawalo 0,77, czyli
         # wiecej niz poprawne "Benfica" (0,62). Zadnym progiem sie ich nie rozdzieli,
         # wiec te przypadki zapisujemy WPROST, zamiast obnizac prog i wpuszczac bledne.
         'Crewe Alexandra': 'Crewe', 'Olympique Lyonnais': 'Lyon', 'Stade Brestois 29': 'Brest',
         'Stade Lavallois': 'Laval', 'AZ': 'AZ Alkmaar', 'PSV': 'PSV Eindhoven',
         'Sport Lisboa e Benfica': 'Benfica'}


def _czlony(s):
    """Czlony nazwy po normalizacji — do porownywania na GRANICACH slow, nie liter."""
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r"\b(fc|cf|afc|ac|sc|ssc|as|us|ud|cd|rc|rcd|sd|ca|sv|vfl|vfb|tsg|fk|sk|bk|if|club|calcio|balompie|de|futbol|football|1\.|\d{4})\b", ' ', s)
    return tuple(t for t in re.findall(r'[a-z]+', s) if t)


def _podobienstwo(zrodlo, baza):
    """Ocena 0..1, jak bardzo nazwa z biezacego sezonu pasuje do nazwy z bazy.
    Laczy podobienstwo liter z dopasowaniem CZLONOW, bo bazy skracaja czlony
    ("Manchester City" -> "Man City", "Olympique Lyonnais" -> "Lyon")."""
    kz, kb = norm(zrodlo), norm(baza)
    if not kz or not kb: return 0.0
    if kz == kb: return 1.0
    ocena = difflib.SequenceMatcher(None, kz, kb).ratio()
    tz, tb = _czlony(zrodlo), _czlony(baza)
    if tz and tb:
        # kazdy czlon bazy, ktory jest przedrostkiem jakiegos czlonu zrodla (lub odwrotnie)
        trafione = 0
        for b in tb:
            for z in tz:
                if b == z or (len(b) >= 3 and z.startswith(b)) or (len(z) >= 3 and b.startswith(z)):
                    trafione += 1; break
        ocena = max(ocena, trafione / max(len(tz), len(tb)))
        if tz[0] == tb[0] or tz[-1] == tb[-1]: ocena += 0.08
    return min(ocena, 0.999)


PROG = 0.62


def map_names(of_names, base_names):
    """Przypisanie GLOBALNE, nie nazwa po nazwie.
    22.09.2026. Poprzednio kazda nazwa szukala sobie dopasowania osobno, regula
    "czy litery jednej zawieraja sie w drugiej", a na koniec difflib z progiem 0.6.
    Skutkiem byly PODMIANY DRUZYN, nie literowki:
      "RCD Espanyol de Barcelona" -> "Barcelona"    (Espanyol to inny klub)
      "Paris Saint-Germain FC"    -> "Paris FC"     (PSG to inny klub)
      "AE Larissa"                -> "Aris"         (Larisa to inny klub)
    Oba kluby z kazdej pary sa w bazie OSOBNO. Mecz ladowal na koncie niewlasciwego
    klubu i psul Elo obu naraz — a poniewaz to build_kb, blad zapisywal sie w bazie.
    Teraz: w jednej lidze przypisanie musi byc ROZNOWARTOSCIOWE (klub bazy trafia
    do co najwyzej jednej nazwy z sezonu). Liczymy oceny wszystkich par i bierzemy
    je od najlepszej; "FC Barcelona" zabiera "Barcelona" wczesniej, niz zdazy po nia
    siegnac "RCD Espanyol de Barcelona", ktore dostaje wtedy "Espanol"."""
    out = {n: None for n in of_names}
    wolne_z = set(of_names)
    wolne_b = set(base_names)

    for n in sorted(of_names):                       # aliasy maja pierwszenstwo
        if n in ALIAS and ALIAS[n] in wolne_b:
            out[n] = ALIAS[n]; wolne_z.discard(n); wolne_b.discard(ALIAS[n])

    pary = []
    for n in sorted(wolne_z):
        for b in sorted(wolne_b):
            o = _podobienstwo(n, b)
            if o >= PROG: pary.append((o, n, b))
    # sortujemy malejaco po ocenie; przy remisie po nazwach, zeby wynik byl powtarzalny
    pary.sort(key=lambda x: (-x[0], x[1], x[2]))
    for o, n, b in pary:
        if n in wolne_z and b in wolne_b:
            out[n] = b; wolne_z.discard(n); wolne_b.discard(b)
            if o < 0.80:
                print(f'  BUILD_KB: "{n}" -> "{b}" (ocena {o:.2f}) — dopasowanie slabe, sprawdz i dopisz do ALIAS.')
    for n in sorted(wolne_z):
        print(f'  BUILD_KB: "{n}" bez dopasowania w bazie — mecze tego klubu pominiete.')
    return out


def openfootball_rows(m):
    rows, unmatched = [], set()
    for f in sorted(glob.glob(os.path.join(RAW, 'football.json', '202[56]-2[67]', '*.json'))):
        code = os.path.basename(f).replace('.json', '')
        if code not in OF_MAP: continue
        div = OF_MAP[code]
        last = m.loc[m.Division == div, 'MatchDate'].max()
        j = json.load(open(f))
        ms = [x for x in j.get('matches', []) if isinstance(x.get('score'), dict) and x['score'].get('ft')
              and x['date'] > last]
        if not ms: continue
        recent = m[(m.Division == div) & (m.MatchDate >= '2025-07-01')]
        names = set(recent.HomeTeam) | set(recent.AwayTeam)
        mp = map_names({x['team1'] for x in ms} | {x['team2'] for x in ms}, names)
        for x in ms:
            h, a = mp.get(x['team1']), mp.get(x['team2'])
            if not h or not a:
                unmatched.update([t for t, v in ((x['team1'], h), (x['team2'], a)) if not v]); continue
            if h == a:
                # klub nie moze grac sam ze soba. Jesli do tego doszlo, dwie rozne nazwy
                # zostaly zlepione w jedna — mecz jest bezwartosciowy, a zapisany psulby Elo.
                print(f'  BUILD_KB: "{x["team1"]}" i "{x["team2"]}" wskazuja na ten sam klub "{h}" '
                      f'({div}, {x["date"]}) — mecz POMINIETY. Dopisz obie nazwy do ALIAS.')
                unmatched.update([x['team1'], x['team2']]); continue
            ht = x['score'].get('ht') or [None, None]
            rows.append(dict(Division=div, MatchDate=x['date'], MatchTime=x.get('time'), HomeTeam=h, AwayTeam=a,
                             FTHome=x['score']['ft'][0], FTAway=x['score']['ft'][1], HTHome=ht[0], HTAway=ht[1], src='openfootball'))
    return pd.DataFrame(rows), unmatched





def _zawiera(x, y):
    """Czy jedna nazwa zawiera sie w drugiej na poziomie CZLONOW, nie liter."""
    tx, ty = set(_czlony(x)), set(_czlony(y))
    return bool(tx) and bool(ty) and (tx <= ty or ty <= tx)


def _aliasy_raz(allm):
    """Znajduje pary nazw oznaczajace TEN SAM klub, na podstawie terminarza, nie napisow.

    22.09.2026. Dwa zrodla opisuja ten sam mecz zupelnie inaczej — po OBU stronach:
        SC Corinthians Paulista 0:2 Fluminense FC   [openfootball]
        Corinthians             0:2 Fluminense      [fbref]
        Santos FC               2:0 CA Mineiro      [openfootball]
        Santos                  2:0 Atletico-MG     [fbref]
    Reguly na napisach sa tu bezradne: "CA Mineiro" i "Atletico-MG" nie maja ze soba nic
    wspolnego, podobnie "Gallos Blancos" i "Queretaro" czy "Aguilas Doradas" i "Rionegro".

    Dlatego kojarzymy MECZE, a nie nazwy, i korzystamy z trzech faktow:
      1) ta sama liga, dzien i wynik — to kandydat na jeden mecz zapisany dwa razy,
      2) wystarczy, ze JEDNA strona pasuje mocno; druga wynika wtedy z eliminacji,
         dokladnie tak, jak czyta to czlowiek,
      3) dwa ROZNE kluby jednej ligi predzej czy pozniej ze soba graja — para, ktora
         nigdy ze soba nie zagrala, to dwie nazwy jednej druzyny.
    Warunek (3) jest zabezpieczeniem: bez niego scalilibysmy kluby, ktore przypadkiem
    zagraly tego samego dnia z takim samym wynikiem."""
    d = allm.dropna(subset=['MatchDate', 'HomeTeam', 'AwayTeam']).copy()

    def sim(a, b):
        ka, kb_ = norm(a), norm(b)
        if not ka or not kb_: return 0.0
        if ka == kb_: return 1.0
        o = difflib.SequenceMatcher(None, ka, kb_).ratio()
        ta, tb = set(_czlony(a)), set(_czlony(b))
        if ta and tb and (ta <= tb or tb <= ta): o = max(o, 0.85)
        return o

    kandydaci = {}
    for _, g in d.groupby(['Division', 'MatchDate', 'FTHome', 'FTAway'], dropna=False):
        if len(g) < 2 or len(g) > 12: continue
        w = list(g.itertuples())
        oceny = []
        for i in range(len(w)):
            for j in range(i + 1, len(w)):
                a, b = w[i], w[j]
                # celowo NIE filtrujemy po src: build_kb nadpisuje je wartoscia "extra"
                # dla wszystkich wierszy z ligi_extra.csv, wiec oryginalne etykiety
                # (openfootball / fbref / sofa) sa tu juz nie do odroznienia.
                sh, sa = sim(a.HomeTeam, b.HomeTeam), sim(a.AwayTeam, b.AwayTeam)
                if str(a.HomeTeam) == str(b.HomeTeam) and str(a.AwayTeam) == str(b.AwayTeam):
                    continue                              # identyczne NAPISY, nic do nauczenia
                    # uwaga: nie wolno porownywac tu ocen — "Vitoria" i "Vitória" maja
                    # ocene 1.0 po normalizacji, a jako napisy sa rozne i wlasnie takie
                    # pary trzeba wychwycic.
                # Strona "mocna" musi byc PEWNA, a nie tylko podobna. 22.09.2026 prog 0.80
                # scalil "Bedford Town" z "Hednesford Town" (ocena rowno 0.800), a przez to
                # takze ich rywali: "Hebburn Town" ze "Spalding United". Cztery rozne kluby.
                # Samo podobienstwo nie rozdziela: poprawne "CA Mineiro"="Atletico-MG" ma 0.118,
                # a bledne "Bedford"/"Hednesford" ma 0.800.
                if max(sh, sa) < 0.90 and not (_zawiera(a.HomeTeam, b.HomeTeam)
                                               or _zawiera(a.AwayTeam, b.AwayTeam)):
                    continue
                oceny.append((sh + sa, i, j, sh, sa))
        oceny.sort(key=lambda x: (-x[0], x[1], x[2]))
        uzyte = set()
        for _, i, j, sh, sa in oceny:
            if i in uzyte or j in uzyte: continue
            uzyte.add(i); uzyte.add(j)
            a, b = w[i], w[j]
            for x, y in ((a.HomeTeam, b.HomeTeam), (a.AwayTeam, b.AwayTeam)):
                if str(x) == str(y): continue
                kl = (a.Division,) + tuple(sorted((str(x), str(y))))
                kandydaci[kl] = kandydaci.get(kl, 0) + 1

    spotkania = set()
    for r in d.itertuples():
        spotkania.add((r.Division,) + tuple(sorted((str(r.HomeTeam), str(r.AwayTeam)))))

    ile = pd.concat([d.HomeTeam, d.AwayTeam]).value_counts()
    mapa, odrzucone = {}, 0
    for (div, x, y), n in sorted(kandydaci.items(), key=lambda kv: (-kv[1], kv[0])):
        if (div, x, y) in spotkania:       # zagrali ze soba, wiec to DWA rozne kluby
            odrzucone += 1; continue
        # Para o NISKIM wlasnym podobienstwie jest wnioskowana z eliminacji, wiec wymaga
        # POTWIERDZENIA: musi wyjsc z co najmniej trzech niezaleznych meczow. Jednorazowe
        # zderzenie to za malo — tak powstalo bledne "Hebburn Town" = "Spalding United".
        if sim(x, y) < 0.90 and not _zawiera(x, y) and n < 3:
            odrzucone += 1; continue
        zwyciezca, przegrany = (x, y) if (ile.get(x, 0), len(x)) >= (ile.get(y, 0), len(y)) else (y, x)
        while (div, zwyciezca) in mapa:    # domykamy lancuchy A->B->C
            zwyciezca = mapa[(div, zwyciezca)]
        if zwyciezca != przegrany:
            mapa[(div, przegrany)] = zwyciezca

    if mapa:
        print(f'  BUILD_KB: rozpoznano {len(mapa)} nazw bedacych aliasem innej druzyny '
              f'(ten sam dzien, wynik i rywal, a nigdy ze soba nie graly). Przyklady:')
        for (div, zle), dobre in sorted(mapa.items())[:10]:
            print(f'      [{div}] "{zle}" = "{dobre}"')
        if odrzucone:
            print(f'      Odrzucono {odrzucone} par, bo te druzyny ze soba GRALY — to rozne kluby.')

    for kol in ('HomeTeam', 'AwayTeam'):
        allm[kol] = [mapa.get((dv, nm), nm) for dv, nm in zip(allm.Division, allm[kol])]
    return allm, len(mapa)


def aliasy_z_terminarza(allm, maks_rund=6):
    """Powtarza rozpoznawanie aliasow, az przestanie cokolwiek znajdowac.
    Jedno przejscie nie wystarcza: dopiero gdy "Fluminense FC" stanie sie "Fluminense",
    wiersze, ktorych wczesniej nie dalo sie skojarzyc, zaczynaja do siebie pasowac
    i odslaniaja kolejne pary ("Gremio"/"Grêmio FBPA", "Botafogo (RJ)"/"Botafogo RJ")."""
    lacznie = 0
    for runda in range(maks_rund):
        allm, n = _aliasy_raz(allm)
        lacznie += n
        if not n: break
        allm = allm.drop_duplicates(subset=['Division', 'MatchDate', 'HomeTeam', 'AwayTeam'], keep='first')
    if lacznie:
        print(f'  BUILD_KB: lacznie {lacznie} aliasow w {runda + 1} rundach.')
    return allm



def przesun_daty_przyblizone(allm):
    """Przesuwa mecze o dacie PRZYBLIZONEJ (zrodlo wiki), gdy koliduja z meczem o dacie
    prawdziwej. Matryce wiki nie zawieraja dat, wiec date im nadajemy — jesli wypadla
    tam, gdzie klub ma juz mecz z prawdziwa data, to nasza data jest bledna, nie tamta.
    Szukamy najblizszego wolnego dnia, zeby nie gubic wyniku."""
    if 'src_zrodlo' not in allm.columns: return allm
    d = allm.dropna(subset=['MatchDate', 'HomeTeam', 'AwayTeam']).copy()
    d['dt'] = pd.to_datetime(d.MatchDate, errors='coerce')
    d = d.dropna(subset=['dt'])

    zajete = set()
    for r in d.itertuples():
        zajete.add((r.Division, str(r.HomeTeam), r.dt)); zajete.add((r.Division, str(r.AwayTeam), r.dt))

    # liczba meczow klubu w danym dniu — liczona RAZ, nie dla kazdego wiersza osobno
    dl = pd.concat([d.assign(kk=d.HomeTeam.astype(str)), d.assign(kk=d.AwayTeam.astype(str))])
    licznik = dl.groupby(['Division', 'dt', 'kk']).size().to_dict()

    przybl = d[d.src_zrodlo == 'wiki']
    zmiany, nieudane = {}, 0
    for r in przybl.itertuples():
        if max(licznik.get((r.Division, r.dt, str(r.HomeTeam)), 0),
               licznik.get((r.Division, r.dt, str(r.AwayTeam)), 0)) < 2:
            continue                                # nie koliduje z nikim
        nowa = None
        for krok in range(1, 40):
            for zn in (1, -1):
                kand = r.dt + pd.Timedelta(days=krok * zn)
                if (r.Division, str(r.HomeTeam), kand) not in zajete and \
                   (r.Division, str(r.AwayTeam), kand) not in zajete:
                    nowa = kand; break
            if nowa is not None: break
        if nowa is None:
            nieudane += 1; continue
        zajete.discard((r.Division, str(r.HomeTeam), r.dt)); zajete.discard((r.Division, str(r.AwayTeam), r.dt))
        zajete.add((r.Division, str(r.HomeTeam), nowa)); zajete.add((r.Division, str(r.AwayTeam), nowa))
        zmiany[r.Index] = nowa.strftime('%Y-%m-%d')

    if zmiany:
        print(f'  BUILD_KB: przesunieto {len(zmiany)} meczow o dacie przyblizonej (wiki), '
              f'bo kolidowaly z meczem o dacie prawdziwej.')
        if nieudane: print(f'      {nieudane} nie udalo sie przesunac — brak wolnego dnia w zasiegu.')
        for idx, nowa in zmiany.items():
            if idx in allm.index: allm.loc[idx, 'MatchDate'] = nowa
    return allm



def wymus_jeden_mecz_dziennie(allm):
    """Ostatnia furtka: w jednej kolejce klub gra DOKLADNIE RAZ.

    Po naprawie nazw i dat zostaja pojedyncze wiersze, ktorych nie da sie pogodzic
    z terminarzem — najczesciej zrodlo podalo zlego rywala albo zla date, np.:
        FK Proleter Novi Sad 0:0 FK Metalac   \  ten sam wynik, ten sam rywal,
        Proleter 023 Zrenjanin 0:0 FK Metalac /   dwa ROZNE kluby jako gospodarz
        FK Pohronie 3:1 Bytca  obok  FK Pohronie 3:1 MFK Skalica
    Nie scalamy ich po nazwie — jedno wystapienie to za malo, zeby uznac dwie nazwy
    za ten sam klub (tak powstalo bledne "Hebburn Town" = "Spalding United").
    Zamiast zgadywac, usuwamy wiersz, ktory lamie terminarz: mecz o zlej dacie albo
    zlym rywalu jest bezwartosciowy, a zostawiony psuje forme i Elo realnych klubow.

    Ktory wiersz zostaje: ten lepiej potwierdzony. Kolejnosc pewnosci:
      1) para, ktora w tym sezonie wystepuje takze w innym terminie (rewanz),
      2) mecz o dacie prawdziwej przed meczem o dacie przyblizonej (wiki),
      3) przy remisie — kolejnosc alfabetyczna, zeby wynik byl powtarzalny."""
    d = allm.dropna(subset=['MatchDate', 'HomeTeam', 'AwayTeam']).copy()
    d['idx'] = d.index
    dl = pd.concat([d.assign(kk=d.HomeTeam.astype(str)), d.assign(kk=d.AwayTeam.astype(str))])
    licz = dl.groupby(['Division', 'MatchDate', 'kk']).size()
    sporne = {(dv, dt) for (dv, dt, _), n in licz.items() if n > 1}
    if not sporne: return allm

    # jak czesto dana para gra ze soba w tej lidze (rewanz = potwierdzenie, ze para istnieje)
    pary = {}
    for r in d.itertuples():
        kl = (r.Division,) + tuple(sorted((str(r.HomeTeam), str(r.AwayTeam))))
        pary[kl] = pary.get(kl, 0) + 1

    usun = []
    for dv, dt in sorted(sporne):
        g = d[(d.Division == dv) & (d.MatchDate == dt)]
        def pewnosc(r):
            kl = (r.Division,) + tuple(sorted((str(r.HomeTeam), str(r.AwayTeam))))
            przybl = 1 if getattr(r, 'src_zrodlo', None) == 'wiki' else 0
            return (-pary.get(kl, 0), przybl, str(r.HomeTeam), str(r.AwayTeam))
        zajete = set()
        for r in sorted(g.itertuples(), key=pewnosc):
            h, a = str(r.HomeTeam), str(r.AwayTeam)
            if h in zajete or a in zajete:
                usun.append((dv, dt, h, a, r.FTHome, r.FTAway, r.idx)); continue
            zajete.add(h); zajete.add(a)

    if usun:
        print(f'  BUILD_KB: usunieto {len(usun)} meczow lamiacych terminarz '
              f'(klub nie moze grac dwa razy tego samego dnia):')
        for dv, dt, h, a, fh, fa, _ in usun[:20]:
            print(f'      [{dv}] {dt}  {h} {fh:.0f}:{fa:.0f} {a}')
        print('      Zrodlo podalo dla nich zla date albo zlego rywala. Zostal wiersz')
        print('      lepiej potwierdzony; usuniety byl nie do pogodzenia z reszta kolejki.')
    return allm.drop(index=[i for _, _, _, _, _, _, i in usun if i in allm.index])


_KRAJ_OSTRZ = []


def _kraj_kanon(div):
    """Kraj ligi w postaci kanonicznej (typuj._kraj_ligi + _KRAJ_KANON) albo None."""
    try:
        from typuj import _kraj_ligi, _KRAJ_KANON
    except Exception as e:
        if not _KRAJ_OSTRZ:   # recenzja 23.09: blad importu wylaczal po cichu grupowanie po kraju
            _KRAJ_OSTRZ.append(1)
            print(f'  BUILD_KB: UWAGA — nie da sie ustalic krajow lig ({e}); sklejanie po kraju i rozdzielanie '
                  f'nazw z roznych krajow WYLACZONE w tym przebiegu.')
        return None
    if not isinstance(div, str) or not div: return None
    k = _kraj_ligi(div)
    return _KRAJ_KANON.get(k, k) if k else None


_ELO_CACHE = {}


def _elo_nazwy():
    """clubelo: nazwa -> (kod kraju, data OSTATNIEJ ZMIANY Elo). Recenzja 23.09: clubelo trzyma czesc klubow pod
    dwiema pisowniami, z ktorych jedna jest martwa — "Nottm Forest" i "MGladbach" maja od 15.12.2024 te sama
    wartosc przepisywana z biezaca data, zywe sa "Nott'm Forest" i "M'gladbach". Data ostatniej zmiany to odroznia."""
    if 'e' in _ELO_CACHE: return _ELO_CACHE['e']
    wyn = {}
    try:
        e = pd.read_csv(os.path.join(RAW, 'EloRatings.csv'), usecols=['club', 'country', 'date', 'elo'])
        e = e.dropna(subset=['club']).sort_values(['club', 'date'])
        zm = e[e.groupby('club').elo.diff().fillna(1) != 0]
        ost = zm.groupby('club').date.max()
        kr = e.groupby('club').country.last()
        wyn = {c: (kr.get(c), pd.Timestamp(ost.get(c))) for c in kr.index}
    except Exception:
        pass
    _ELO_CACHE['e'] = wyn
    return wyn


def _elo_klucz(n, gr, elo):
    """Klucz sortowania: najpierw nazwa z clubelo Z TEGO SAMEGO KRAJU (recenzja: "Newcastle" z clubelo ENG
    przejmowal australijski Newcastle Jets), wsrod nich ta z najswiezsza zmiana Elo."""
    from kluby import ELO_KRAJ
    v = elo.get(n)
    if v is None or ELO_KRAJ.get(v[0]) != gr: return (1, 0)
    return (0, -(v[1].value if pd.notna(v[1]) else 0))


def scal_zapis_nazw(allm):
    """23.09.2026, audyt: ten sam klub jako dwa wpisy rozniace sie tylko ZAPISEM — spacja na koncu
    ('Ajax' i 'Ajax ' w Eredivisie), apostrofem ("M'gladbach" / "MGladbach"), wielkoscia liter, diakrytykami
    albo 'ß'/'ss'. Klucz: same litery i cyfry (kluby.klucz) — BEZ usuwania slow (FC, CA, SV), bo to one potrafia
    odrozniac kluby. Do tego reczna lista kluby.SCAL_RECZNIE (ten sam klub pod INNA nazwa w zrodlach).
    Zasady po recenzji 23.09:
      - grupujemy w obrebie KRAJU (awans/spadek), liga bez kraju tworzy wlasna grupe;
      - nazwa wynikowa: ta, ktora ma clubelo (inaczej model traci Elo: "Hornchurch", "VVV Venlo"),
        potem ta z najwieksza liczba meczow;
      - pary z kluby.NIE_SKLEJAJ nigdy nie sa sklejane; dwa zapisy, ktore GRALY ZE SOBA, to dwa kluby;
      - wspolne dni meczowe: 0; wyjatkiem sa dni, na ktore przypada wiersz z xgabora (daty w ligach spoza
        Europy bywaja tam przesuniete) — wtedy najwyzej 2 i <= 2% meczow mniejszego."""
    from kluby import SCAL_RECZNIE, SCAL_TYLKO_LIGA, klucz, zakazane
    for c in ('HomeTeam', 'AwayTeam'):
        allm[c] = allm[c].astype(str).str.strip().str.replace(r'\s+', ' ', regex=True)
    _d = allm['Division']
    allm['Division'] = _d.where(_d.isna(), _d.astype(str).str.strip().str.replace(r'\s+', ' ', regex=True))
    elo = _elo_nazwy()
    kraj = {d: _kraj_kanon(d) for d in allm.Division.dropna().unique()}
    grupa = allm.Division.map(lambda d: (kraj.get(d) or ('liga:' + d)) if isinstance(d, str) else 'liga:?')
    daty = pd.to_datetime(allm.MatchDate, errors='coerce')

    # (1) NAJPIERW reczna lista, po KLUCZU ("Würzburger Kickers" = "Wurzburger Kickers").
    rr = 0
    for kl, b_ in SCAL_RECZNIE.items():
        div_, a_ = kl[0], kl[1]
        ligi_kr = {d for d in kraj if (kraj.get(d) or ('liga:' + d)) == (kraj.get(div_) or ('liga:' + div_))} | {div_}
        od_ = kl[2] if len(kl) > 2 else None   # 'RRRR-MM-DD' (od) albo '<RRRR-MM-DD' (przed)
        if not (allm.Division == div_).any(): continue
        gr_ = kraj.get(div_) or ('liga:' + div_)
        zakres = (allm.Division == div_) if kl in SCAL_TYLKO_LIGA else (grupa == gr_)
        if od_ is not None:
            zakres = zakres & ((daty < pd.Timestamp(od_[1:])) if od_.startswith('<') else (daty >= pd.Timestamp(od_)))
        ka, kb_ = klucz(a_), klucz(b_)
        w_kr = grupa == gr_
        nazwy_kr = pd.unique(pd.concat([allm.loc[w_kr, 'HomeTeam'], allm.loc[w_kr, 'AwayTeam']]))
        zrodlowe = {n for n in pd.unique(pd.concat([allm.loc[zakres, 'HomeTeam'], allm.loc[zakres, 'AwayTeam']])) if klucz(n) == ka}
        if not zrodlowe: continue
        cele = {n for n in nazwy_kr if klucz(n) == kb_}
        if od_ is None and (zrodlowe & cele): zrodlowe -= cele
        gra = ((allm.HomeTeam.isin(zrodlowe) & allm.AwayTeam.isin(cele)) | (allm.HomeTeam.isin(cele) & allm.AwayTeam.isin(zrodlowe)))
        if (w_kr & gra).any() or any(zakazane(d, x, y) for d in ligi_kr for x in zrodlowe for y in cele | {b_}):
            print(f'  BUILD_KB [{div_}]: NIE sklejam {sorted(zrodlowe)} z "{b_}" mimo wpisu w kluby.py — graly ze soba albo NIE_SKLEJAJ.')
            continue
        # nazwa wynikowa: z clubelo, jesli ktorys zapis ja ma (inaczej wpis w clubelo zostaje bez meczow)
        # (wpis z data wydziela CZESC meczow pod nowa nazwe — tam cel jest zawsze nazwa z listy)
        kandydaci = sorted(zrodlowe | cele | {b_}, key=lambda n: (_elo_klucz(n, gr_, elo), n != b_, n))
        cel = b_ if od_ is not None else kandydaci[0]
        for c in ('HomeTeam', 'AwayTeam'):
            allm.loc[zakres & allm[c].isin(zrodlowe - {cel}), c] = cel
            if cel != b_:
                allm.loc[w_kr & allm[c].isin(cele - {cel}), c] = cel
        rr += 1
    if rr:
        print(f'  BUILD_KB: {rr} nazw sklejonych z recznej listy kluby.SCAL_RECZNIE (ten sam klub, inny zapis w zrodlach).')

    # (2) automatycznie: zapisy rowne po kluczu w obrebie KRAJU.
    xg = (allm['src'] == 'xgabora') if 'src' in allm.columns else pd.Series(False, index=allm.index)
    mapa, ile = {}, 0
    for gr, g in allm.assign(_gr=grupa, _xg=xg).groupby('_gr'):
        t = pd.concat([g[['Division', 'MatchDate', 'HomeTeam', '_xg']].rename(columns={'HomeTeam': 'n'}),
                       g[['Division', 'MatchDate', 'AwayTeam', '_xg']].rename(columns={'AwayTeam': 'n'})])
        licz = t.n.value_counts()
        grupy = {}
        for n in licz.index: grupy.setdefault(klucz(n), []).append(n)
        dni = t.groupby('n').MatchDate.apply(set).to_dict()
        dni_pewne = t[~t._xg].groupby('n').MatchDate.apply(set).to_dict()
        dni_xg = t[t._xg].groupby('n').MatchDate.apply(set).to_dict()
        ligi = t.groupby('n').Division.apply(set).to_dict()
        pary = set(zip(g.HomeTeam, g.AwayTeam))

        def _zgodne(a, b):
            if (a, b) in pary or (b, a) in pary: return False
            if any(zakazane(d, a, b) for d in ligi.get(a, set()) | ligi.get(b, set())): return False
            if dni_pewne.get(a, set()) & dni_pewne.get(b, set()): return False
            wsp = dni[a] & dni[b]
            # wspolny dzien dopuszczalny tylko, gdy po JEDNEJ stronie jest wylacznie wiersz z xgabora (data
            # przesunieta), a po drugiej prawdziwy mecz — dwa wiersze xgabora tego dnia to dwa kluby
            only_xg = lambda n, d: d in dni_xg.get(n, set()) and d not in dni_pewne.get(n, set())
            if any(only_xg(a, d) == only_xg(b, d) for d in wsp): return False
            w = len(wsp)
            return w == 0 or (w <= 2 and w <= 0.02 * min(licz[a], licz[b]))
        for k_, ns in grupy.items():
            if len(ns) < 2 or not k_: continue
            ok = all(_zgodne(a, b) for i, a in enumerate(ns) for b in ns[i + 1:])
            if not ok:
                print(f'  BUILD_KB [{gr}]: zapisy {ns} roznia sie tylko znakami, ale graly ze soba, tego samego dnia albo sa na liscie NIE_SKLEJAJ — zostaja osobno.')
                continue
            cel = min(ns, key=lambda n: (_elo_klucz(n, gr, elo), -licz[n], n))
            for n in ns:
                if n != cel: mapa[(gr, n)] = cel; ile += 1
    if mapa:
        for c in ('HomeTeam', 'AwayTeam'):
            allm[c] = [mapa.get((g_, n), n) for g_, n in zip(grupa, allm[c])]
        print(f'  BUILD_KB: sklejono {ile} zapisow nazw rozniacych sie tylko znakami '
              f'(np. {", ".join(f"{n!r}->{c!r}" for (d, n), c in list(mapa.items())[:3])}).')
    return allm


def warianty_nazw(allm):
    """23.09.2026 (regresja nazw): po sklejeniu klub ma w bazie JEDNA nazwe, a oferta STS pisze czesto ta, ktora
    zniknela ("Hertha Berlin" -> "Hertha", "Red Bull Salzburg" -> "Salzburg", "Los Chankas" -> "CDC Santa Rosa").
    Zapisujemy wszystkie nazwy zrodlowe klubu: z wierszy (_oH/_oA -> nazwa koncowa) i z mapy uzupelnij_ligi
    (ligi_extra_nazwy.json: nazwa zrodla -> nazwa w ligi_extra -> nazwa koncowa). Wariant wskazujacy DWA rozne
    kluby (w roznych ligach) jest pomijany — typuj.py uzywa tabeli tylko tam, gdzie wynik jest jednoznaczny."""
    par = pd.concat([allm[['Division', '_oH', 'HomeTeam']].set_axis(['div', 'z', 'k'], axis=1),
                     allm[['Division', '_oA', 'AwayTeam']].set_axis(['div', 'z', 'k'], axis=1)]).dropna().drop_duplicates()
    kon = {(d, z): k for d, z, k in par.itertuples(index=False)}
    wyn = set((z, k) for _, z, k in par.itertuples(index=False))
    try:
        mapa = json.load(open(os.path.join(HERE, 'ligi_extra_nazwy.json'), encoding='utf-8'))
        for d, m in mapa.items():
            for z, k in m.items():
                if (d, k) in kon: wyn.add((z, kon[(d, k)]))
    except Exception:
        pass
    w = pd.DataFrame(sorted(wyn), columns=['wariant', 'klub'])
    koncowe = set(allm.HomeTeam) | set(allm.AwayTeam)
    w = w[(w.wariant != w.klub) & w.klub.isin(koncowe) & ~w.wariant.isin(koncowe)]
    ile = w.groupby('wariant').klub.nunique()
    w = w[w.wariant.isin(ile[ile == 1].index)].drop_duplicates()
    print(f'  BUILD_KB: tabela warianty_nazw: {len(w)} nazw zrodlowych sklejonych klubow (dla typuj.py).')
    return w


def usun_dubel_miedzy_ligami(allm):
    """23.09.2026 (recenzja): ten sam mecz w DWOCH ligach jednego kraju — 365scores zapisywal kolejke
    Regionalligi raz jako "Regionalliga", raz jako "Regional League North" (ok. 211 meczow podwojnie),
    baraze trafialy i do KOR, i do "K League 2", i do SWE, i do SWE2. Ten sam gospodarz, gosc i wynik,
    data +-1 dzien, kraj ten sam -> zostaje jeden wiersz: z ligi z kodem (E0, SWE), a miedzy ligami
    "Kraj | Liga" — z ligi o mniejszej liczbie druzyn (bardziej szczegolowej)."""
    if not len(allm): return allm
    kraj = {d: _kraj_kanon(d) for d in allm.Division.dropna().unique()}
    a = allm.assign(_k=allm.Division.map(kraj), _dt=pd.to_datetime(allm.MatchDate, errors='coerce').dt.normalize())
    a = a[a._k.notna() & a._dt.notna()]
    druz = pd.concat([allm[['Division', 'HomeTeam']].rename(columns={'HomeTeam': 'n'}),
                      allm[['Division', 'AwayTeam']].rename(columns={'AwayTeam': 'n'})]).groupby('Division').n.nunique()
    a = a.assign(_pr=[(0 if '|' not in str(d) else 1, druz.get(d, 0)) for d in a.Division])
    a = a.sort_values(['_k', 'HomeTeam', 'AwayTeam', 'FTHome', 'FTAway', '_dt'])
    klucz = ['_k', 'HomeTeam', 'AwayTeam', 'FTHome', 'FTAway']
    poprz_dt = a.groupby(klucz, dropna=False)._dt.shift()
    poprz_idx = a.index.to_series().groupby([a[c] for c in klucz], dropna=False).shift()
    poprz_div = a.groupby(klucz, dropna=False).Division.shift()
    dub = ((a._dt - poprz_dt).dt.days.le(1)) & poprz_div.notna() & (poprz_div != a.Division)
    usun = set()
    for i in a.index[dub.values]:
        j = poprz_idx.at[i]
        usun.add(i if a.at[i, '_pr'] >= a.at[j, '_pr'] else j)
    if usun:
        pr = allm.loc[list(usun)].Division.value_counts().head(4).to_dict()
        print(f'  BUILD_KB: usunieto {len(usun)} meczow zapisanych w DWOCH ligach jednego kraju (np. {pr}).')
    allm = allm.drop(index=list(usun))
    # Recenzja 23.09: po sklejeniu "Cuiaba" (BRA, xgabora) z "Cuiabá" (BRA2, 365scores) klub mial dwa mecze
    # 11.01.2021 — wiersz xgabora z Serie A to widmo (klub gral wtedy w Serie B). Klub nie gra dwoch meczow
    # jednego dnia: gdy w dwoch ligach kraju jeden wiersz jest z xgabora, a drugi z innego zrodla, xgabora odpada.
    if 'src' not in allm.columns: return allm
    b = allm.assign(_k=allm.Division.map(kraj), _dt=pd.to_datetime(allm.MatchDate, errors='coerce').dt.normalize())
    b = b[b._k.notna() & b._dt.notna()]
    dl = pd.concat([b[['_k', '_dt', 'Division', 'src', 'HomeTeam']].rename(columns={'HomeTeam': 't'}).assign(_i=b.index),
                    b[['_k', '_dt', 'Division', 'src', 'AwayTeam']].rename(columns={'AwayTeam': 't'}).assign(_i=b.index)])
    gg = dl.groupby(['_k', '_dt', 't'])
    # wiersz spoza xgabora musi miec PRAWDZIWA date (wiki ma daty przyblizone — nie moze niczego wypierac)
    wiki = b['src_zrodlo'].astype(str).eq('wiki') if 'src_zrodlo' in b.columns else pd.Series(False, index=b.index)
    dl = dl.assign(_p=(dl.src.ne('xgabora') & ~dl._i.map(wiki).fillna(False).astype(bool)).values)
    konf = dl[(gg.Division.transform('nunique') > 1) & (dl.groupby(['_k', '_dt', 't'])._p.transform('any')) &
              (gg.src.transform(lambda x: (x == 'xgabora').any()))]
    kolid = sorted(set(konf.loc[konf.src == 'xgabora', '_i']))
    if not kolid: return allm
    # Recenzja 23.09: czesc takich wierszy to NIE widma, tylko mecze z zamienionym dniem i miesiacem w xgabora
    # (BRA 2021: Cuiaba - Bragantino "2021-01-11" to 01.11.2021). Dlatego: (a) ten sam mecz (rywal i wynik)
    # jest juz w innej lidze kraju w ciagu 1 dnia od daty albo od daty z zamienionym dniem/miesiacem -> dubel,
    # usuwamy; (b) dzien <= 12 -> zamieniamy dzien z miesiacem; (c) inaczej usuwamy (daty nie da sie ustalic).
    from kluby import klucz as _kl
    reszta = allm.drop(index=kolid)
    rdt = pd.to_datetime(reszta.MatchDate, errors='coerce').dt.normalize()
    usun2, zamien = [], {}
    for i in kolid:
        r = allm.loc[i]; d0 = pd.to_datetime(r.MatchDate).normalize()
        daty = [d0] + ([pd.Timestamp(year=d0.year, month=d0.day, day=d0.month)] if d0.day <= 12 else [])
        h, a = _kl(r.HomeTeam), _kl(r.AwayTeam)
        blizniak = False
        for dd in daty:
            w = reszta[(rdt - dd).abs().dt.days.le(1) & (reszta.FTHome == r.FTHome) & (reszta.FTAway == r.FTAway)]
            for x in w.itertuples():
                xh, xa = _kl(x.HomeTeam), _kl(x.AwayTeam)
                if (xh.startswith(h) or h.startswith(xh)) and (xa.startswith(a) or a.startswith(xa)):
                    blizniak = True
        if blizniak or d0.day > 12: usun2.append(i)
        else: zamien[i] = daty[1]
    for i, d in zamien.items():
        allm.at[i, 'MatchDate'] = d.strftime('%Y-%m-%d') if isinstance(allm.at[i, 'MatchDate'], str) else d
    if usun2 or zamien:
        print(f'  BUILD_KB: wiersze xgabora kolidujace z meczem klubu tego samego dnia w innej lidze: usunieto {len(usun2)} '
              f'(dubel albo data nie do ustalenia), {len(zamien)} przestawiono (zamieniony dzien z miesiacem).')
    return allm.drop(index=usun2)


def usun_dubel_meczu(allm):
    """23.09.2026, audyt: ten sam mecz dwa razy, przesuniety o 1-2 dni — zrodla zapisuja date w innych
    strefach czasowych, a filtr 'tylko mecze nowsze niz baza' przepuszcza kopie z dnia nastepnego
    (BRA 2026: Coritiba - Cruzeiro 0:1 z 30 i 31.07, i cztery kolejne). Ten sam gospodarz, ten sam gosc
    i ten sam wynik w odstepie <= 2 dni to fizycznie jeden mecz (rewanz ma ZAMIENIONE strony).
    Zostaje wiersz ze zrodla podstawowego (nie 'extra'), a przy remisie zrodel — wczesniejszy."""
    a = allm.assign(_pr=(allm.src == 'extra').astype(int)).sort_values(['Division', 'HomeTeam', 'AwayTeam', 'MatchDate'])
    klucz = ['Division', 'HomeTeam', 'AwayTeam', 'FTHome', 'FTAway']
    _dt = pd.to_datetime(a.MatchDate, errors='coerce')
    grp = [a[c] for c in klucz]
    poprz = _dt.groupby(grp, dropna=False).shift()
    # Druga recenzja: poprzedni wiersz brano z CALEJ ramki (idx[pos-1]), a mogl miec inny wynik —
    # usuwal sie wtedy prawdziwy mecz, a dubel zostawal. Poprzednik musi byc z TEJ SAMEJ grupy.
    poprz_idx = a.index.to_series().groupby(grp, dropna=False).shift()
    dub = (_dt - poprz).dt.days.le(2)
    if not dub.any():
        return allm
    usun = set()
    for i_cur in a.index[dub.values]:
        i_prev = poprz_idx.at[i_cur]
        usun.add(i_cur if a.at[i_cur, '_pr'] >= a.at[i_prev, '_pr'] else i_prev)
    print(f'  BUILD_KB: usunieto {len(usun)} duplikatow meczu przesunietych o 1-2 dni (ten sam gospodarz, gosc i wynik).')
    return allm.drop(index=list(usun))


def main():
    fetch('--refresh' in sys.argv)
    cols = ['Division', 'MatchDate', 'MatchTime', 'HomeTeam', 'AwayTeam', 'HomeElo', 'AwayElo', 'FTHome', 'FTAway',
            'HTHome', 'HTAway', 'HomeShots', 'AwayShots', 'HomeTarget', 'AwayTarget', 'HomeCorners', 'AwayCorners',
            'HomeYellow', 'AwayYellow', 'HomeRed', 'AwayRed', 'HomeFouls', 'AwayFouls']
    m = pd.read_csv(os.path.join(RAW, 'Matches.csv'), usecols=cols, low_memory=False)  # kursy celowo pominięte
    m = m.dropna(subset=['FTHome', 'FTAway'])
    m['src'] = 'xgabora'
    of, unmatched = openfootball_rows(m)
    parts = [m, of]
    delta = os.path.join(HERE, 'delta.csv')  # wyniki dopisywane przez zadania 12/15/18/21 (z Drive)
    if os.path.exists(delta):
        d = pd.read_csv(delta); d['src'] = 'delta'; parts.append(d)
    extra = os.path.join(HERE, 'ligi_extra.csv')  # uzupelnij_ligi.py: FBref (worldfootballR_data) + openfootball + matryce Wikipedii
    if os.path.exists(extra):
        e = pd.read_csv(extra)
        # zachowujemy oryginalne zrodlo: tylko ono mowi, ktory wiersz ma date PRZYBLIZONA
        # (wiki) a ktory prawdziwa (sofa/fbref/espn). Bez tego nie da sie rozstrzygnac,
        # ktora z dwoch kolidujacych dat jest ta wymyslona.
        e['src_zrodlo'] = e['src'] if 'src' in e.columns else None
        e['src'] = 'extra'; parts.append(e)
        try:
            from uzupelnij_ligi import NOWE; DIV_NAME.update({k: v for k, v in NOWE.items() if k not in DIV_NAME})
        except Exception: pass
    allm = pd.concat(parts, ignore_index=True)
    allm = allm.drop_duplicates(subset=['Division', 'MatchDate', 'HomeTeam', 'AwayTeam'], keep='first')
    allm['_oH'], allm['_oA'] = allm.HomeTeam.astype(str).str.strip(), allm.AwayTeam.astype(str).str.strip()   # do tabeli warianty_nazw
    from kluby import LIGI_POMIN, WIERSZE_POMIN_DRUZYNA, WIERSZE_POMIN
    _d10 = pd.to_datetime(allm.MatchDate, errors='coerce').dt.strftime('%Y-%m-%d')
    _pom = allm.Division.isin(LIGI_POMIN)
    for _dv, _t in WIERSZE_POMIN_DRUZYNA:
        _pom |= (allm.Division == _dv) & ((allm.HomeTeam == _t) | (allm.AwayTeam == _t))
    for _dv, _dd, _h, _a in WIERSZE_POMIN:
        _pom |= (allm.Division == _dv) & (_d10 == _dd) & (allm.HomeTeam == _h) & (allm.AwayTeam == _a)
    if _pom.any():
        print(f'  BUILD_KB: pominieto {int(_pom.sum())} wierszy z bledem zrodla (kluby.WIERSZE_POMIN*: zle podpisany klub, odwrocony wynik).')
        allm = allm[~_pom]
    allm = scal_zapis_nazw(allm)
    allm = aliasy_z_terminarza(allm)
    allm = przesun_daty_przyblizone(allm)
    allm = wymus_jeden_mecz_dziennie(allm)
    allm = usun_dubel_meczu(allm)
    allm = usun_dubel_miedzy_ligami(allm)
    from kluby import rozdziel_kraje
    allm = rozdziel_kraje(allm, _kraj_kanon, {n: v[0] for n, v in _elo_nazwy().items()})
    allm = allm.drop_duplicates(subset=['Division', 'MatchDate', 'HomeTeam', 'AwayTeam'], keep='first')
    DIV_NAME.update({d: d for d in allm.Division.dropna().unique() if d not in DIV_NAME})  # ligi z Sofascore: „Kraj | Liga”
    warianty = warianty_nazw(allm)
    allm = allm.drop(columns=['src_zrodlo', '_oH', '_oA'], errors='ignore')
    allm = allm.sort_values(['MatchDate', 'Division']).reset_index(drop=True)
    intl = pd.read_csv(os.path.join(RAW, 'intl_results.csv')).dropna(subset=['home_score', 'away_score'])
    elo = pd.read_csv(os.path.join(RAW, 'EloRatings.csv'))
    db = sqlite3.connect(os.path.join(HERE, 'kb.sqlite'))
    allm.to_sql('matches', db, if_exists='replace', index=False)
    warianty.to_sql('warianty_nazw', db, if_exists='replace', index=False)
    intl.to_sql('intl', db, if_exists='replace', index=False)
    elo.to_sql('clubelo', db, if_exists='replace', index=False)
    pd.DataFrame(list(DIV_NAME.items()), columns=['Division', 'Name']).to_sql('divisions', db, if_exists='replace', index=False)
    db.execute('CREATE INDEX IF NOT EXISTS ix_m ON matches(Division, MatchDate)')
    db.commit()
    print(f'matches={len(allm)} (openfootball+{len(of)}), intl={len(intl)}, clubelo={len(elo)}, ostatni mecz={allm.MatchDate.max()}')
    if unmatched: print('Niedopasowane nazwy:', sorted(unmatched))


if __name__ == '__main__':
    main()
