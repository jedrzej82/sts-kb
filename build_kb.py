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


def scal_zapis_nazw(allm):
    """23.09.2026, audyt: ten sam klub jako dwa wpisy rozniace sie tylko ZAPISEM — spacja na koncu
    ('Ajax' i 'Ajax ' w Eredivisie, lacznie 9 klubow N1), apostrofem ("M'gladbach" / "MGladbach"),
    wielkoscia liter ("Colon Santa FE" / "Colon Santa Fe"). Klucz: same litery i cyfry po zdjeciu
    diakrytykow — BEZ usuwania slow (FC, CA, SV), bo to one potrafia odrozniac kluby. Sklejamy tylko,
    gdy dwa zapisy nigdy nie graly ze soba i nie maja meczu tego samego dnia."""
    for c in ('HomeTeam', 'AwayTeam'):
        allm[c] = allm[c].astype(str).str.strip().str.replace(r'\s+', ' ', regex=True)
    # Kluby, ktore wrocily do ligi po latach pod inna nazwa w 365scores (historia do 2021, swieze od 2026):
    # canon() w uzupelnij_ligi.py widzi tylko druzyny aktywne od 07.2022, wiec sam ich nie polaczy.
    for (div_, a_), b_ in {('BRA', 'Chapecoense'): 'Chapecoense-SC', ('SUI', 'FC Vaduz'): 'Vaduz'}.items():
        w_ = allm.Division == div_
        gra = ((allm.HomeTeam == a_) & (allm.AwayTeam == b_)) | ((allm.HomeTeam == b_) & (allm.AwayTeam == a_))
        if (w_ & gra).any(): continue
        for c in ('HomeTeam', 'AwayTeam'):
            allm.loc[w_ & (allm[c] == a_), c] = b_
    klucz = lambda x: re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(x)).encode('ascii', 'ignore').decode().lower())
    mapa, ile = {}, 0
    for div, g in allm.groupby('Division'):
        t = pd.concat([g[['MatchDate', 'HomeTeam']].rename(columns={'HomeTeam': 'n'}), g[['MatchDate', 'AwayTeam']].rename(columns={'AwayTeam': 'n'})])
        licz = t.n.value_counts()
        grupy = {}
        for n in licz.index: grupy.setdefault(klucz(n), []).append(n)
        dni = t.groupby('n').MatchDate.apply(set).to_dict()
        pary = set(zip(g.HomeTeam, g.AwayTeam))
        for k_, ns in grupy.items():
            if len(ns) < 2 or not k_: continue
            ok = all(not ((a, b) in pary or (b, a) in pary or (dni[a] & dni[b])) for i, a in enumerate(ns) for b in ns[i + 1:])
            if not ok:
                print(f'  BUILD_KB [{div}]: zapisy {ns} roznia sie tylko znakami, ale graly ze soba albo tego samego dnia — zostaja osobno.')
                continue
            cel = max(ns, key=lambda n: licz[n])
            for n in ns:
                if n != cel: mapa[(div, n)] = cel; ile += 1
    if mapa:
        for c in ('HomeTeam', 'AwayTeam'):
            allm[c] = [mapa.get((d, n), n) for d, n in zip(allm.Division, allm[c])]
        print(f'  BUILD_KB: sklejono {ile} zapisow nazw rozniacych sie tylko spacja/apostrofem/wielkoscia liter '
              f'(np. {", ".join(f"{n!r}->{c!r}" for (d, n), c in list(mapa.items())[:3])}).')
    return allm


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
    allm = scal_zapis_nazw(allm)
    allm = aliasy_z_terminarza(allm)
    allm = przesun_daty_przyblizone(allm)
    allm = wymus_jeden_mecz_dziennie(allm)
    allm = usun_dubel_meczu(allm)
    allm = allm.drop_duplicates(subset=['Division', 'MatchDate', 'HomeTeam', 'AwayTeam'], keep='first')
    DIV_NAME.update({d: d for d in allm.Division.dropna().unique() if d not in DIV_NAME})  # ligi z Sofascore: „Kraj | Liga”
    allm = allm.drop(columns=['src_zrodlo'], errors='ignore')
    allm = allm.sort_values(['MatchDate', 'Division']).reset_index(drop=True)
    intl = pd.read_csv(os.path.join(RAW, 'intl_results.csv')).dropna(subset=['home_score', 'away_score'])
    elo = pd.read_csv(os.path.join(RAW, 'EloRatings.csv'))
    db = sqlite3.connect(os.path.join(HERE, 'kb.sqlite'))
    allm.to_sql('matches', db, if_exists='replace', index=False)
    intl.to_sql('intl', db, if_exists='replace', index=False)
    elo.to_sql('clubelo', db, if_exists='replace', index=False)
    pd.DataFrame(list(DIV_NAME.items()), columns=['Division', 'Name']).to_sql('divisions', db, if_exists='replace', index=False)
    db.execute('CREATE INDEX IF NOT EXISTS ix_m ON matches(Division, MatchDate)')
    db.commit()
    print(f'matches={len(allm)} (openfootball+{len(of)}), intl={len(intl)}, clubelo={len(elo)}, ostatni mecz={allm.MatchDate.max()}')
    if unmatched: print('Niedopasowane nazwy:', sorted(unmatched))


if __name__ == '__main__':
    main()
