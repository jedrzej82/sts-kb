"""Tozsamosc klubow w bazie pilkarskiej — JEDNO miejsce, z ktorego korzystaja uzupelnij_ligi.py i build_kb.py.

23.09.2026, audyt po przebiegu 12:00. Dwa bledy tej samej natury, oba MYLA DRUZYNY:

1. TEN SAM KLUB POD DWIEMA NAZWAMI. Historia (fbref/xgabora, do 09.2025) i swieze wyniki (365scores,
   od 07.2026) zapisuja klub inaczej: "Slavia Prague" / "Slavia Praha", "Jeju United" / "Jeju SK",
   "Asociacion Deportiva Tarma" / "ADT Tarma". Model bral jeden wpis — albo historie bez formy, albo
   forme bez historii — i oznaczal druzyne jako nieswieza (Tarma: "691 dni"). Po dolozeniu archiwum
   365scores 2025 ten sam mecz wchodzil DWA razy (USL: 28 meczow, "B'ham Legion" i "Birmingham Legion FC").
   Podobienstwo nazw tego nie rozstrzyga (Tochigi City i Tochigi SC to dwa kluby, Univ. Craiova
   i U Craiova tez, GV San Jose zalozono w 2022 obok starego San Jose) — dlatego lista RECZNA,
   kazda para sprawdzona pojedynczo.

2. JEDNA NAZWA DLA KLUBOW Z ROZNYCH KRAJOW. "Santos" to Santos (Brazylia) i Santos Laguna (Meksyk),
   "Nacional" — Portugalia i Urugwaj, "Libertad" — Paragwaj i Ekwador. typuj.py liczy pi-ratingi,
   forme i H2H po nazwie, wiec mieszal mecze dwoch klubow. rozdziel_kraje() nadaje mniejszym
   grupom przyrostek kraju: "Santos [mexico]". typuj.py wybiera wariant z kraju rywala.
"""
import re
import unicodedata

# (Division, nazwa) -> nazwa docelowa. Sprawdzone 23.09.2026, kazda para osobno.
# Celowo NIE MA: Tochigi City/Tochigi SC, Univ. Craiova/U Craiova, GV San Jose/San Jose (klub z 2022),
# Celta B/Celta, Farul/Viitorul, Lierse SK/Lierse Kempenzonen, Lommel/Lommel SK, Beveren/Waasland-Beveren,
# Deportivo Garcilaso/Real Garcilaso, Mes Shahr-E Babak/Mes Rafsanjan, Novi Beograd/IMT, Kharkiv/Metalist,
# Airdrie/Airdrie Utd, Botafogo-SP/Botafogo (RJ), SC Poltava/Vorskla, Gen Caballero/General Caballero JLM
# (w Paragwaju sa DWA kluby General Caballero), FC Osaka/Cerezo Osaka, Tallinna Kalev/Kalev II,
# SC Delhi/Delhi Dynamos (Delhi Dynamos to od 2019 Odisha FC) — to ROZNE kluby albo nie da sie tego potwierdzic.
SCAL_RECZNIE = {
    ('ARG', 'Gimnasia La Plata'): 'Gimnasia L.P.',
    ('ARG', 'San Martín de San Juan'): 'San Martin S.J.',
    ('Argentina | Primera Nacional', 'Colon'): 'Colon Santa FE',   # Colon de Santa Fe, spadl z ARG w 2023
    # 04.10.2026 (Raport 18:00, usterka 2): Sportivo Cerrito (Montevideo) — "Cerrito" w URU do 2022, po spadku 365scores
    # pisze "Club Sportivo Cerrito" w Segunda Division. Jeden klub pod dwiema nazwami: "CS Cerrito" z oferty trafial
    # w stary zapis i Plaza Colonia – Cerrito nie mialo wspolnej ligi (NIEPEWNE DOPASOWANIE).
    ('Uruguay | Segunda Division', 'Club Sportivo Cerrito'): 'Cerrito',
    # 05.10.2026 (Raport 04.10 21:00 usterki 1 i 4): sparingi „Amistosos de Verano” 365scores zapisuja kluby pelna nazwa,
    # a liga — skrotem ze starego zrodla. "Argentinos Juniors" z oferty trafial w JEDEN sparing ze stycznia (ROZNE LIGI
    # BEZ ELO, NIESWIEZA 263 dni). Unión Española po spadku (2025) gra w Primera B jako "U. Española".
    ('Argentina | Amistosos de Verano', 'Argentinos Juniors'): 'Argentinos Jrs',
    ('Argentina | Amistosos de Verano', 'Central Córdoba SdE'): 'Central Cordoba',
    ('Argentina | Amistosos de Verano', 'Instituto AC Cordoba'): 'Instituto',
    ('Chile | First Division B', 'U. Española'): 'Unión Española',
    # 05.10.2026 (Raport 15:00 usterka 4): literowka zrodla — "Taran" zamiast "Tatran" (MFK Tatran Liptovsky Mikulas);
    # oferta STS, LVBET i Superbet pisza Tatran, dopasowanie dzialalo tylko przez terminarz.
    ('Slovakia | 2. Liga', 'Taran Liptovsky Mikulas'): 'Tatran Liptovsky Mikulas',
    # 06.10.2026 (Raport 12:00 usterka 4: „Hyde United NIESWIEZA 2014-04-26”, „Welling United NIESWIEZA 2016-04-30”):
    # ten sam klub z dwoch zrodel — football-data (stara liga, do spadku) i 365scores (od 2025, inny zapis). Oferta
    # trafiala w stary wpis bez meczow od lat. Lista z przegladu calej bazy (rdzen nazwy bez United/Utd/FC/AFC, stary
    # wpis konczy sie przed 2024, nowy gra od 2025, nigdy nie grali ze soba); kazda para sprawdzona recznie.
    # Celowo NIE: Wimbledon – AFC Wimbledon (dwa kluby), Austin (Austin Bold, USL) – Austin FC, Airdrie (Airdrieonians
    # do 2002) – Airdrie Utd, Clydebank (do 2002) – Clydebank FC — nastepcy, nie te same kluby.
    ('England | Non League Premier', 'Hyde'): 'Hyde United',
    ('England | Non League Premier', 'Welling Utd'): 'Welling United',
    ('England | Non League Premier', 'Guiseley AFC'): 'Guiseley',
    ('England | National League N/S', 'Chorley FC'): 'Chorley',
    ('England | National League N/S', 'Maidstone United'): 'Maidstone',
    ('England | National League N/S', 'AFC Telford'): 'AFC Telford United',
    ('EC', 'Telford United'): 'AFC Telford United',       # AFC Telford United (od 2004) — w EC od 2012 bez „AFC”
    ('EC', 'Boston Utd'): 'Boston',                        # Boston United: E3 do 2007, EC od 2024
    ('Ireland | National League', 'Mervue United'): 'Mervue',
    ('Ireland | Division 1', 'UC Dublin FC'): 'UC Dublin',
    ('Peru | Liga 2', 'Pirata FC'): 'Pirata',
    ('Portugal | Liga Portugal 2', 'FC Penafiel'): 'Penafiel',
    ('Russia | Russian First League', 'FC Ufa'): 'Ufa',
    ('Spain | Segunda RFEF', 'Terrassa FC'): 'Terrassa',
    ('Uruguay | Segunda Division', 'Tacuarembó FC'): 'Tacuarembó',
    ('Venezuela | Liga FUTVE 2', 'Aragua FC'): 'Aragua',
    # 06.10.2026 (Raport 18:00: KONFLIKT/MOZLIWY_DUBEL „Alfreton Town=Alfreton”): ten sam przeglad z „Town/City” w rdzeniu.
    # Celowo NIE: Salisbury (Salisbury City FC upadl 2014; Salisbury FC to nastepca).
    ('England | Non League Premier', 'Alfreton'): 'Alfreton Town',
    ('England | Non League Premier', 'Kettering'): 'Kettering Town',
    ('Ireland | Division 1', 'Athlone Town'): 'Athlone',
    ('SC2', 'FC Edinburgh'): 'Edinburgh City',          # Edinburgh City -> FC Edinburgh (2022) -> Edinburgh City
    # 07.10.2026 (audyt usterek, Raport 04.10 15:00 nr 4 i 05.10 12:00 nr 1): zrodlo zmienilo pisownie po spadku / w nowym sezonie;
    # okresy rozlaczne, jeden klub w kraju o tym rdzeniu
    ('Poland | Division 2', 'Leczna'): 'Gornik Leczna',     # POL2 do 05.2026 jako Gornik Leczna, II liga 2026/27: Leczna
    ('IRN', 'Sanat Mes Kerman'): 'Mes Kerman',             # IRN do 2023, Azadegan 2025-26: Mes Kerman
    # ta sama para, kariery z dwoch lig jednoczesnie (zrodlo pisze klub inaczej w kazdej lidze), zero wspolnych dni:
    ('N2', 'Emmen'): 'FC Emmen',                           # dotad tylko alias typuj (aliasy.csv 03.10)
    ('N2', 'FC Dordrecht'): 'Dordrecht',
    ('D3', 'FC Erzgebirge Aue'): 'Erzgebirge Aue',
    ('Uruguay | Segunda Division', 'La Luz'): 'La Luz FC',          # URU do 2023 jako La Luz FC, potem Segunda (365: La Luz)
    # A-League: 365scores dopisuje "FC"; cel = pelna nazwa (sam "Newcastle" koliduje z angielskim klubem).
    # "W Sydney" (Western Sydney Wanderers) i "Sydney FC" to DWA kluby — celowo osobno.
    ('AUS', 'Adelaide'): 'Adelaide United FC',
    ('AUS', 'Brisbane'): 'Brisbane Roar FC',
    ('AUS', 'Newcastle'): 'Newcastle Jets FC',
    ('AUS', 'Melb Heart'): 'Melb City',   # Melbourne Heart -> Melbourne City w 2014
    ('AUT', 'Blau-Weiß Linz'): 'BW Linz',
    ('B2', 'Jong Genk'): 'Genk U23',
    ('B2', 'Lommel United'): 'Lommel SK',   # przemianowany w 2020 (CFG); stary "Lommel" z B1 2001-02 to INNY klub
    ('B2', 'Lommel'): 'Lommel SK',          # w B2 tylko 2024-25, to juz Lommel SK
    ('B1', 'Lommel', '<2004-07-01'): 'Lommel (1932-2003)',   # KFC Lommel SK, rozwiazany w 2003 — INNY klub
    ('B1', 'Lommel', '2004-07-01'): 'Lommel SK',             # po 2004 "Lommel" w B1 to juz dzisiejszy Lommel SK
    ('BOL', 'Universitario de Vinto'): 'FC Universitario',
    ('BOL', 'Independiente Petrolero'): 'Indep Petrolero',
    ('BOL', 'San Antonio'): 'San Antonio Bulo Bulo',
    ('BRA', 'Chapecoense'): 'Chapecoense-SC',
    ('BRA2', 'América Mineiro'): 'América (MG)',
    ('BRA2', 'Atlético Goianiense'): 'Atl Goianiense',
    ('BRA2', 'Operário-PR'): 'Operário',
    ('BUL', 'CSKA 1948 Sofia'): 'CSKA 1948',
    ('BUL', 'Dunav Rousse'): 'Dunav Ruse',
    ('BUL', 'Loko Sofia'): 'Lokomotiv Sofia',
    ('CHI', 'U de Chile'): 'Univ Chile',
    ('CHI', 'Universidad de Chile'): 'Univ Chile',
    ('CHI', 'Universidad Catolica'): 'Univ Católica',
    ('CHN', 'Meizhou Wuhua'): 'Meizhou Hakka',   # 365scores; te same mecze i wyniki co Meizhou Hakka w CSL 2025
    ('CHN', 'Shandong Luneng'): 'Shandong Taishan',
    ('CHN', 'Shanghai SIPG'): 'Shanghai Port',
    ('COL', 'ADU Magdalena'): 'Union Magdalena',   # Asociacion Deportiva Union Magdalena, Primera A 2019
    ('CZE', 'Bohemians Praha'): 'Bohemians 1905',
    ('CZE', 'Slavia Praha'): 'Slavia Prague',
    ('CZE', 'Sparta Praha'): 'Sparta Prague',
    ('D3', "Jahn R'burg"): 'SSV Jahn Regensburg',   # cel = pelna nazwa: pod nia sa swieze mecze i oferta
    ('D3', "W'burg Kickers"): 'Würzburger Kickers',   # jw.; Regionalliga ma ten sam zapis
    ('ECU', 'Universidad Catolica'): 'Univ Católica',
    # 30.09.2026 (przeglad): tylko od 2026 — w 2025 „Vinotinto” z Serie B gralo ROWNOLEGLE z Vinotinto del Ecuador FC
    # z Serie A (07–10.2025 po 4–5 meczow miesiecznie w kazdej lidze, 10.08.2025 oba tego samego dnia) — inny zespol.
    ('Ecuador | Serie B', 'Vinotinto', '2026-01-01'): 'Vinotinto del Ecuador FC',
    ('Spain | Segunda RFEF', 'CD Ourense'): 'UD Ourense',   # 31 meczow do 03.05.2026, od 09.05 baraze jako UD Ourense (awans 31.05)
    ('G1', 'OFI'): 'OFI Crete',
    ('HUN', 'ETO FC Győr'): 'Győr',
    ('IRN', 'Sanat Naft Abadan'): 'Sanat Naft',
    ('JAP', 'Niigata'): 'Albirex Niigata',       # 365scores; bez tego mecze z matrycy wiki wchodzily drugi raz
    ('JAP2', 'Niigata'): 'Albirex Niigata',      # J2 2018-21 i od 2026 (spadek z J1 w 2025)
    ('JAP2', 'Kamatamare'): 'Kamatamare Sanuki',
    ('JAP2', 'Yamaga'): 'Matsumoto Yamaga',
    ('JAP2', 'Thespakusatsu Gunma'): 'Thespa Gunma',   # zmiana nazwy klubu
    # 30.09.2026 (przeglad): fbref do 08.2025 i 365scores od 08.2025 pisza inaczej — historia klubu byla rozcieta na dwie
    # nazwy (bez wspolnych czlonow, wiec canon ich nie laczyl). Zakresy dat sie nie nakladaja. Cel = zapis z J1.
    ('JAP2', 'Montedio'): 'Montedio Yamagata', ('JAP2', 'Yamagata'): 'Montedio Yamagata',
    ('JAP2', 'Vortis'): 'Tokushima', ('JAP2', 'Roasso'): 'Kumamoto',
    ('JAP2', 'Zweigen'): 'Zweigen Kanazawa',
    ('KOR', 'Daejeon Cit'): 'Daejeon Hana Citizen',
    ('KOR', 'Gimcheon Sangmu FC'): 'Sangju Sangmu',   # druzyna wojskowa, od 2021 w Gimcheon
    ('KOR', 'Jeju SK'): 'Jeju United',
    ('KOR', 'Ulsan HD'): 'Ulsan Hyundai',
    ('KSA', 'Ittihad Jeddah'): 'Al-Ittihad',
    ('N1', 'Sparta'): 'Sparta Rotterdam',
    ('N2', 'Jong PSV Eindhoven'): 'Jong PSV',
    ('N2', 'TOP Oss'): 'Oss',
    ('PAR', 'San Lorenzo'): 'CS San Lorenzo',   # Sportivo San Lorenzo; "San Lorenzo" to klub ARGENTYNSKI
    ('PER', 'ADT Tarma'): 'Asociación Deportiva Tarma',
    ('PER', 'Comerciantes'): 'Comerciantes Unidos',   # Cutervo, Liga 1 2016-17 i od 2024
    ('POL', 'Termalica B-B.'): 'Bruk-Bet Termalica Nieciecza',
    ('POL', 'Gornik Z.'): 'Gornik Zabrze',
    ('POL', 'Legia Warsaw'): 'Legia',
    ('ROM', 'FC Csikszereda Miercurea Ciuc'): 'Csikszereda M. Ciuc',
    ('RUS', 'FC Pari Nizhny Novgorod'): 'Pari NN',
    ('RUS', 'Pari Nizhny Novgorod'): 'Pari NN',
    ('SP2', 'Leonesa'): 'Cultural Leonesa',
    ('SRB', 'IMT Belgrad'): 'FK IMT Novi Beograd',
    ('SRB', 'Radnicki 1923'): 'Radnički Krag',
    ('SUI', 'FC Vaduz'): 'Vaduz',
    ('UKR', 'Metalist 1925'): 'FK Metalist 1925 Kharkiv',
    ('UKR', 'SK Poltava'): 'SC Poltava',   # SK/SC to ta sama skrotowa forma w dwoch transliteracjach; zrodla zmieniaja sie 09.2025
    ('UKR', 'FK LNZ-Lebedyn'): 'LNZ Cherkasy',
    ('USL', "B'ham Legion"): 'Birmingham Legion FC',
    ('USL', 'LV Lights FC'): 'Las Vegas Lights',
    ('USL', 'N Carolina'): 'North Carolina FC',
    ('USL', 'North Carolina'): 'North Carolina FC',   # 365scores pisze pelna nazwa
    ('USL', 'Phx Rising'): 'Phoenix Rising FC',
    ('USL', 'Sac Republic'): 'Sacramento Republic',
    ('USL', 'TB Rowdies'): 'Tampa Bay Rowdies',
    ('VEN', 'Estudiantes de Merida'): 'Estud Mérida',
    ('VEN', 'Puerto Cabello'): 'Acad Pr Cabello',
    # Awanse i spadki 2026: klub w nowej lidze pod nazwa z 365scores, historia pod stara nazwa.
    # Skan po KRAJU (nie po lidze), 23.09.2026; kazda para sprawdzona. Celowo NIE: ASU Poli (Timisoara)
    # i Poli Iasi, Gloria Popesti i Gloria Buzau, Real Zaragoza i Real Zaragoza B, Worthing i Worthing
    # United, FC Luanda i Luanda City — rozne kluby albo niepotwierdzone.
    ('Austria | 2. Liga', 'FC Blau Weiss Linz'): 'BW Linz',
    # SK Beveren = Waasland-Beveren przemianowany w 2022; clubelo prowadzi go jako "Beveren". "Beveren" w B1
    # PRZED 2010 to KSK Beveren (rozwiazany w 2010) — inny klub, dostaje etykiete historyczna (wpis z data "<").
    ('B1', 'Beveren', '<2010-07-01'): 'KSK Beveren (do 2010)',
    ('B2', 'SK Beveren'): 'Beveren',
    ('B1', 'Waasland-Beveren'): 'Beveren',
    ('Czechia | Division 2', 'Dukla Praha'): 'Dukla Prague',
    ('EC', 'Hornchurch'): 'AFC Hornchurch',
    ('England | National League N/S', 'Truro City'): 'Truro',
    ('Germany | Regionalliga', '1860 München'): '1860 Munich',
    ('D2', 'Cottbus'): 'Energie Cottbus',
    ('Germany | Regionalliga', 'SSV Ulm 1846'): 'Ulm',
    ('POL2', 'Termalica Nieciecza'): 'Bruk-Bet Termalica Nieciecza',
    ('Portugal | Liga Portugal 2', 'Viseu'): 'Academico Viseu',
    ('Russia | Russian First League', 'FC Pari Nizhny Novgorod'): 'Pari NN',
    ('Russia | Russian First League', 'FK Sochi'): 'Sochi',
    ('Serbia | Prva Liga', 'Javor Matis'): 'Javor Ivanjica',
    ('Serbia | Prva Liga', 'Napredak Krusevac'): 'Napredak Kruš',
    ('Serbia | Prva Liga', 'Spartak Subotica'): 'Spartak Subotic',
    ('Serbia | Prva Liga', 'TSC Bačka Topola'): 'TSC',
    ('Spain | Primera Division RFEF', 'Real Zaragoza'): 'Zaragoza',
    ('Spain | Primera Division RFEF', 'SD Huesca'): 'Huesca',
    # Raport 02.10 18:00: kluby z Primera RFEF 2025/26, ktore wrocily do SP2 — Sofascore pisze pelna nazwe,
    # football-data krotka; bez sklejenia sezon 2025/26 wisial pod martwa nazwa ("CD Eldense NIESWIEZA").
    ('Spain | Primera Division RFEF', 'CD Eldense'): 'Eldense',
    ('Spain | Primera Division RFEF', 'Celta Vigo B'): 'Celta B',
    # 03.10.2026 (zdarzenia.py, CONFLICT MOZLIWY_DUBEL przejrzany recznie): Flashscore zapisuje obecny klub inaczej niz
    # historia z football-data/365 — nazwa z oferty trafiala w MARTWY wpis (KSK Heist 2014-16), a mecze tego sezonu
    # wisialy pod nazwa z FS. Ten sam klub: RWDM (RWD Molenbeek -> RWDM Brussels FC 2024), KSK Heist, KFC Dessel Sport,
    # Llanelli Town (spadek do Cymru South). NIE: Roeselare (KSV upadl 2020, obecny SK Roeselare to inny podmiot).
    ('Belgium | National Division 1 - ACFF', 'RWDM Brussels'): 'RWD Molenbeek',
    ('Belgium | National Division 1 - VV', 'Heist'): 'KSK Heist',
    ('Belgium | National Division 1 - VV', 'Dessel'): 'Dessel Sport',
    ('Wales | Cymru South', 'Llanelli'): 'Llanelli Town',
    ('Switzerland | Challenge League', 'FC Winterthur'): 'Winterthur',
    ('Turkiye | 1. Lig', 'Corum FK'): 'Corum',
    # "Erzurumspor" w T1 2000-01 to dawny, INNY klub; BB Erzurumspor (2018-21) i Erzurumspor FK to jeden klub
    # (clubelo: "Erzurumspor").
    ('T1', 'Erzurumspor', '<2010-07-01'): 'Erzurumspor (do 2010)',
    ('T1', 'Erzurum BB'): 'Erzurumspor',
    ('Turkiye | 1. Lig', 'Erzurumspor FK'): 'Erzurumspor',
    ('Turkiye | 1. Lig', 'Fatih Karagümrük'): 'Karagumruk',
    # 07.10.2026 (paczka wieczorna, Raport 18:00): Serie D 2026/27 z Flashscore pod innym zapisem niz 2025/26 z 365scores.
    # Sprawdzone na zewn/ 07.10: kazda para w tej samej grupie (region), nigdy ze soba nie grala, okresy rozlaczne
    # (stary zapis do 12.2025, nowy od 09.2026), jedyna nazwa z tym rdzeniem w zrodlach. Siracusa: US Siracusa
    # 17. w Serie C/C 2025/26 (strefa spadku), w Serie C 2026/27 jej nie ma, w Serie D/I gra „Siracusa”.
    ('Italy | Serie D', 'Siracusa'): 'US Siracusa',
    ('Italy | Serie D', 'Sanremese'): 'Sanremo',
    ('Italy | Serie D', 'USD Casatese'): 'Casatese Merate',
    ('Italy | Serie D', 'USD Ragusa'): 'Asd Ragusa Calcio',
    ('Italy | Serie D', 'Union Clodiense'): 'ASD Clodiense',
    ('Italy | Serie D', 'Ciserano-Bergamo'): 'Virtus Bergamo',   # Virtus Ciserano Bergamo (STS)
    # Atletico Mineiro: 365scores pisze tak klub w Campeonato Mineiro (osobna liga w bazie, ostatni mecz 03.2026),
    # w BRA ten sam klub to „Atletico-MG” — oferta trafiala w martwy wpis ze stanowej ligi.
    ('Brazil | Mineiro', 'Atlético Mineiro'): 'Atletico-MG',
    # 07.10.2026 (Raport 21:00 usterka 2): „RB Bragantino” z Paulisty (ostatni mecz 02.2026) to ten sam klub co
    # „Bragantino” w BRA (Serie A) — oferta „RB Bragantino – Mirassol” trafiala w martwy wpis ze stanowej ligi.
    ('Brazil | Paulista', 'RB Bragantino'): 'Bragantino',
    # 08.10.2026 (Raport 15:00 nr 3): Al-Okhdood (Nadzran) — 365 do 05.2025 „Al Okhdood SC”, od 08.2025 „Al-Akhdoud”
    # (KSA, od 08.2026 First Division); nigdy nie grali ze soba. Oferta trafiala w martwy wpis (500 dni).
    ('KSA', 'Al Okhdood SC'): 'Al-Akhdoud',
    # 08.10.2026 (Raport 21:00 nr 1): klub z Serie A pod inna nazwa w lidze stanowej / Serie B (365) — oferta trafiala
    # w wpis stanowy (235 dni, ROZNE LIGI BEZ ELO). Audyt lig stanowych BRA 08.10: tylko te pary to ten sam klub.
    ('Brazil | Paranaense', 'Athletico Paranaense'): 'Athletico-PR',
    ('BRA2', 'Ath Paranaense'): 'Athletico-PR',
    ('Brazil | Carioca', 'Botafogo'): 'Botafogo RJ',
    ('Brazil | Carioca', 'Flamengo'): 'Flamengo RJ',
    ('Brazil | Carioca', 'Vasco da Gama'): 'Vasco',
    # 09.10.2026 (Raport 12:00 nr 2): ten sam klub pod stara nazwa (NIESWIEZA, 146–1966 dni); nigdy nie grali ze soba.
    ('D3', 'Bayern Munich II'): 'Bayern München II',
    ('DEN', 'Hvidovre IF'): 'Hvidovre',
    ('Romania | Liga 2', 'Sepsi'): 'Sepsi Sf. Gheorghe',
    # 09.10.2026 (Raport 21:00 nr 2): Omiya Ardija (JAP, xgabora 2012–2018) = RB Omiya Ardija (JAP2, extra — od 2025 nazwa
    # z „RB”, zrodlo pisze ja wstecz od 2015); lata sie nie nakladaja (2016–17 J1, reszta J2) — NIESWIEZA 2875 dni.
    ('JAP', 'Omiya Ardija'): 'RB Omiya Ardija',
    # TP-47 (FS, Kakkonen 2026: TP-47 - Vaajakoski 04.10) = „TP-47 Tornio” (365 i oferta STS, ten sam mecz 04.10).
    ('Finland | Kakkonen', 'TP-47'): 'TP-47 Tornio',
}

# Nazwy (z danej ligi), ktore NIGDY nie moga zostac sklejone — rozne kluby, ktore automat bral za jeden,
# bo po zdjeciu form prawnych nazwy sa rowne, a w danych nie spotkaly sie (grali w innych latach).
# Egzekwowane w uzupelnij_ligi.canon() i build_kb.scal_zapis_nazw(). Przejrzane 23.09.2026 (recenzja).
NIE_SKLEJAJ = {
    'BOL': [('Universitario', 'FC Universitario'), ('Universitario (P)', 'FC Universitario')],   # Sucre vs Vinto
    'UKR': [('SK Dnipro-1', 'Dnipro'), ('Dnipro-1', 'Dnipro'),          # SC Dnipro-1 (2017) vs FC Dnipro (rozw. 2020)
            ('Metalist Kharkiv', 'FK Metalist 1925 Kharkiv'),             # Metalist (rozw. 2016) vs Metalist 1925
            ('FK Metalist Kharkiv', 'Metalist Kharkiv'),                  # FC Metalist (od 2019) vs stary Metalist
            ('FK Metalist Kharkiv', 'FK Metalist 1925 Kharkiv')],
    'F2': [('Rouen', 'Quevilly Rouen'), ('FC Rouen', 'Quevilly Rouen')],  # FC Rouen 1899 vs US Quevilly-Rouen
    'France | Ligue 3': [('Rouen', 'Quevilly Rouen'), ('FC Rouen', 'Quevilly Rouen')],
    'CHN': [('Qingdao Jonoon', 'Qingdao FC')],                           # Jonoon vs Qingdao Huanghai
    'B2': [('Mechelen', 'KRC Mechelen'), ('KV Mechelen', 'KRC Mechelen')],   # KV Mechelen vs Racing Mechelen
    'B1': [('Lommel (1932-2003)', 'Lommel SK')],
    'Spain | Primera Division RFEF': [('UD Ourense', 'Ourense CF')],
    # 'Spain | Segunda RFEF': UD Ourense (2014) i Ourense CF to dwa kluby — wpis nizej (z parami z 07.10)
    'JAP2': [('Fc Osaka', 'Cerezo Osaka'), ('FC Osaka', 'Cerezo Osaka')],
    'IND': [('SC Delhi', 'Delhi Dynamos')],
    # 07.10.2026 (paczka wieczorna): TP-47 (Tornio) i TPV (Tampere) to dwa kluby; norm() zdejmuje cyfry („tp”), a „tp”/„tpv”
    # maja podobienstwo 0,8 — uzupelnij_ligi.match_one dopasowywal „TP-47” do „TPV”.
    'Finland | Kakkonen': [('TP-47', 'TPV'), ('TP-47 Tornio', 'TPV')],
    'Finland | Ykkonen': [('TP-47', 'TPV'), ('TP-47 Tornio', 'TPV')],
    # rezerwy i pierwsza druzyna (ogolnie blokuje to teraz nazwy.znaczniki w match_one; tu jawnie, bo to para z raportu)
    'Spain | Segunda RFEF': [('UD Ourense', 'Ourense CF'), ('CD Ourense', 'Ourense CF'),
                             ('San Sebastian Reyes B', 'San Sebastian Reyes'), ('San Sebastian Reyes B', 'San Sebastian De Los Reyes')],
    'Spain | Tercera RFEF - Group 7': [('San Sebastian Reyes B', 'San Sebastian Reyes'),
                                       ('San Sebastian Reyes B', 'San Sebastian De Los Reyes')],
}


def _div_klucz(d):
    # 07.10.2026: 365scores zapisuje „Segunda RFEF ” ze spacja na koncu; uzupelnij_ligi.canon() dostaje Division w takiej
    # postaci (build_kb dopiero potem ja przycina), wiec wpisy „Spain | Segunda RFEF” w canon() NIE dzialaly.
    return re.sub(r'\s+', ' ', str(d)).strip()


_ZAKAZ = {}
for _d, _l in NIE_SKLEJAJ.items():
    _ZAKAZ.setdefault(_div_klucz(_d), set()).update(frozenset(p) for p in _l)


def zakazane(div, a, b):
    """True, gdy a i b to na pewno rozne kluby (lista NIE_SKLEJAJ dla tej ligi)."""
    return a != b and frozenset((a, b)) in _ZAKAZ.get(_div_klucz(div), ())


# Wpisy z SCAL_RECZNIE dzialajace TYLKO w podanej lidze. Pozostale dzialaja w calym KRAJU tej ligi
# (klub po spadku/awansie ma w innej lidze te sama pisownie ze zrodla — "Cottbus" w D1 i w D2).
# Tu sa nazwy zbyt ogolne, zeby przenosic je na inne ligi kraju.
SCAL_TYLKO_LIGA = {('B2', 'Lommel'), ('B1', 'Lommel', '<2004-07-01'), ('B1', 'Lommel', '2004-07-01'), ('N1', 'Sparta'), ('PER', 'Comerciantes'),
                   ('Argentina | Primera Nacional', 'Colon'), ('BOL', 'San Antonio'), ('AUS', 'Adelaide'),
                   ('AUS', 'Brisbane'), ('AUS', 'Newcastle'), ('Portugal | Liga Portugal 2', 'Viseu'),
                   ('PAR', 'San Lorenzo'), ('B1', 'Beveren', '<2010-07-01'), ('T1', 'Erzurumspor', '<2010-07-01'),
                   ('Ecuador | Serie B', 'Vinotinto', '2026-01-01'),
                   ('Brazil | Carioca', 'Botafogo'), ('Brazil | Carioca', 'Flamengo'), ('Brazil | Carioca', 'Vasco da Gama')}   # 08.10: „Botafogo” to tez PB/SP
# Wpis z trzecim elementem: 'RRRR-MM-DD' = tylko mecze OD tej daty, '<RRRR-MM-DD' = tylko mecze PRZED ta data.

# Nazwa wspolna dla klubow z roznych krajow: ktory kraj zostaje przy nazwie BEZ przyrostka. Stala lista,
# zeby tozsamosc nie przeskakiwala, gdy liczba meczow drugiego klubu przerosnie pierwszy (aliasy w typuj.py
# wskazuja nazwe bez przyrostka). Pierwszenstwo ma kraj z clubelo (tam jest Elo), potem ta lista, potem
# najwieksza liczba meczow.
KRAJ_NAZWY = {'Independiente': 'colombia', 'Libertad': 'paraguay', 'Santos': 'brazil', 'Universitario': 'peru',
              'Univ Católica': 'ecuador', 'River Plate': 'argentina', 'San Lorenzo': 'argentina',
              'Sport Boys': 'peru', 'Alianza FC': 'colombia', 'Internacional': 'brazil', 'Maritimo': 'portugal',
              'Progreso': 'uruguay', 'Platense': 'argentina', 'Colon': 'uruguay', 'Nacional': 'portugal',
              'Red Star': 'france', 'Newcastle': 'england'}
ELO_KRAJ = {'AUT': 'austria', 'BEL': 'belgium', 'DEN': 'denmark', 'ENG': 'england', 'ESP': 'spain', 'FIN': 'finland',
            'FRA': 'france', 'GER': 'germany', 'GRE': 'greece', 'ITA': 'italy', 'NED': 'netherlands', 'NOR': 'norway',
            'POL': 'poland', 'POR': 'portugal', 'ROM': 'romania', 'RUS': 'russia', 'SCO': 'scotland', 'SWE': 'sweden',
            'TUR': 'turkey'}


# Ligi (etykiety z 365scores) pomijane w calosci. "Regional League North" i "Regionalliga Southwest" to
# krotkotrwale (07-12.2025) etykiety tych samych kolejek co glowna "Germany | Regionalliga": 87% i 100% meczow
# to duplikaty, a reszta zawiera bledy — HSC Hannover podpisany jako "Hannover 96 II" (kicker: Weiche Flensburg
# - HSC Hannover 4:0, 3. kolejka 2025/26), inne wyniki i rywale tego samego dnia. Glowny feed ma pelny sezon.
# Recenzja 23.09: pomijanie CALEJ "Regional League North" gubilo prawdziwy mecz (Meppen - Schoningen 5:1, 24.08.2025,
# kicker) — pomijamy tylko wiersze z blednie podpisanym klubem; pozostale duplikaty usuwa usun_dubel_miedzy_ligami.
LIGI_POMIN = set()
WIERSZE_POMIN_DRUZYNA = {('Germany | Regional League North', 'Hannover 96 II')}   # to HSC Hannover
# Pojedyncze wiersze z bledem zrodla (Division, data, gospodarz, gosc) — sprawdzone u zrodla.
WIERSZE_POMIN = {('Germany | Regionalliga', '2025-08-30', 'Schöningen', 'VFB Oldenburg')}   # naprawde Oldenburg 5:2 Schoningen (kicker, 7. kolejka)

_ZNAKI = str.maketrans({'ł': 'l', 'Ł': 'L', 'ø': 'o', 'Ø': 'O', 'æ': 'ae', 'Æ': 'Ae', 'ß': 'ss', 'đ': 'd',
                        'Đ': 'D', 'ı': 'i', 'ð': 'd', 'þ': 'th', 'œ': 'oe'})


def klucz(x):
    """Same litery i cyfry po zdjeciu diakrytykow. 'ß' -> 'ss' PRZED NFKD: NFKD nie rozklada 'ß',
    wiec "Preußen Münster" i "Preussen Munster" dawaly rozne klucze i klub mial dwa wpisy (D2)."""
    s = str(x).translate(_ZNAKI)
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower())


PRZYROSTEK = re.compile(r'^(.*) \[([a-z]+)\]$')


def rozdziel_kraje(allm, kraj_ligi, elo_kraj=None):
    """Nazwa uzywana w ligach z ROZNYCH krajow = rozne kluby. Nazwe bez przyrostka zachowuje: kraj z clubelo
    (elo_kraj: nazwa -> kod kraju clubelo), potem kraj z KRAJ_NAZWY, na koncu grupa z najwieksza liczba
    meczow. Pozostale grupy dostaja przyrostek kraju: "Santos [mexico]". Recenzja 23.09: po samej liczbie
    meczow serbska Crvena zvezda ("Red Star") zabierala nazwe i Elo francuskiemu Red Star."""
    import pandas as pd
    elo_kraj = elo_kraj or {}
    kr = {d: kraj_ligi(d) for d in allm.Division.dropna().unique()}
    t = pd.concat([allm[['Division', 'HomeTeam']].rename(columns={'HomeTeam': 'n'}),
                   allm[['Division', 'AwayTeam']].rename(columns={'AwayTeam': 'n'})])
    t['k'] = t.Division.map(kr)
    t = t.dropna(subset=['k'])
    ile = t.groupby(['n', 'k']).size()
    wiele = ile.groupby(level=0).size()
    wiele = wiele[wiele > 1].index
    mapa, opis = {}, []
    for n in wiele:
        g = ile.loc[n].sort_values(ascending=False, kind='stable')
        glowny = ELO_KRAJ.get(elo_kraj.get(n, ''), None)
        if glowny not in g.index: glowny = KRAJ_NAZWY.get(n)
        if glowny not in g.index: glowny = g.index[0]
        for k in g.index:
            if k != glowny: mapa[(n, k)] = f'{n} [{k}]'
        opis.append(f'{n}: ' + ', '.join(f'{k} {v}' + (' (nazwa)' if k == glowny else '') for k, v in g.items()))
    if not mapa:
        return allm
    kraj_w = allm.Division.map(kr)
    for c in ('HomeTeam', 'AwayTeam'):
        allm[c] = [mapa.get((n, k), n) for n, k in zip(allm[c], kraj_w)]
    print(f'  BUILD_KB: {len(wiele)} nazw oznaczalo kluby z ROZNYCH krajow — rozdzielone przyrostkiem kraju '
          f'(np. {"; ".join(opis[:4])}).')
    return allm
