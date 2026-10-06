#!/usr/bin/env python3
"""Typowanie meczu wyłącznie ze statystyk.
  python3 typuj.py "Athletic" "Alaves"                 # klubowe (auto-dopasowanie nazw)
  python3 typuj.py "Poland" "Netherlands" --intl [--neutral]
  python3 typuj.py A B --kurs 1X=1.35 --kurs O1.5=1.28   # kursy TYLKO po wyborze: EV po podatku 12%
  python3 typuj.py A B --kurs 1X=1.35 --nogi nogi.csv    # nogi DOPUSZCZONE dopisywane do nogi.csv (dla kupon.py)
  python3 typuj.py A B --para 1X+O1.5=1.62 [--nogi nogi.csv]  # para z jednego meczu (Bet Builder, Poprawka 59):
                                                         # laczne P z siatki; kurs = kurs BUILDERA z aplikacji
  python3 typuj.py A B --live 60 1:0 [--czerwona-gosp] [--czerwona-gosc]   # na żywo: minuta i wynik
Wynik: prawdopodobieństwa (skalibrowane backtestem), statystyki formy/H2H/rożnych/kartek, ostrzeżenia."""
import os, sys, re, sqlite3, pickle, difflib, unicodedata, datetime as dt
import functools
import numpy as np, pandas as pd
from model import fit_dc, dc_lambdas, fit_elo_glm, elo_lambdas, markets, blend, load_calibration, calibrate, live_markets, p_pary
import json
# v5n (20.09.2026): zespół DC + Elo + pi-ratings (wagi z ensemble.py) i korekta per rynek (korekta_rynkow.py)

HERE = os.path.dirname(os.path.abspath(__file__))
TAX = 0.88
KEY_MARKETS = ['1', 'X', '2', '1X', 'X2', '12', 'DNB_1', 'DNB_2', 'O0.5', 'O1.5', 'O2.5', 'U2.5', 'U3.5', 'U4.5',
               'BTTS_tak', 'BTTS_nie', 'gosp_O0.5', 'gość_O0.5', 'gosp_O1.5', 'gość_O1.5', '1_strzeli_pierwsza',
               '2_strzeli_pierwsza', 'HT_O0.5', 'HT_1', 'HT_X', 'HT_2']


def db():
    return sqlite3.connect(os.path.join(HERE, 'kb.sqlite'))


# Litery, ktorych NFKD NIE rozklada — encode('ascii','ignore') po prostu je KASUJE.
# 21.09.2026: przez to norm("Wisla Plock" z polskimi znakami) dawalo "wisapock" zamiast
# "wislaplock" i klub w ogole nie pasowal do bazy; ratowalo to tylko dopasowanie rozmyte,
# czyli przypadek. Dotyczy wszystkich nazw z l z kreska, d z kreska, o z kreska itd.
from nazwy import LITERY as _LITERY   # 29.09.2026: jedna tabela dla wszystkich modulow (nazwy.py)

def norm(s):
    s = unicodedata.normalize('NFKD', str(s).translate(_LITERY)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]', '', s)


# Poprawka 51: STS pisze te kluby inaczej niz baza; sprawdzone recznie po lidze z oferty
# (Paragwaj Puchar: Recoleta FC z Asuncion — NIE chilijski Deportes Recoleta; Ekwador Serie B: Vinotinto del Ecuador).
ALIASES = {'cdrecoleta': 'Recoleta FC', 'vinotintofc': 'Vinotinto del Ecuador FC', 'lech': 'Lech Poznan', 'lechpoznan': 'Lech Poznan', 'legiawarszawa': 'Legia', 'legiawarsaw': 'Legia', 'rakowczestochowa': 'Rakow', 'jagielloniabialystok': 'Jagiellonia', 'zaglebielubin': 'Zaglebie', 'brukbettermalica': 'Termalica', 'termalicanieciecza': 'Termalica', 'wislaplock': 'Wisla Plock', 'athletic': 'Ath Bilbao', 'athleticbilbao': 'Ath Bilbao', 'athleticclub': 'Ath Bilbao', 'alaves': 'Alaves',
           'atleticomadrid': 'Ath Madrid', 'atletico': 'Ath Madrid', 'realmadrid': 'Real Madrid', 'intermediolan': 'Inter',
           'internazionale': 'Inter', 'acmilan': 'Milan', 'manchesterunited': 'Man United', 'manchestercity': 'Man City',
           'psg': 'Paris SG', 'parissaintgermain': 'Paris SG', 'bayernmunich': 'Bayern Munich', 'bayernmonachium': 'Bayern Munich',
           'borussiadortmund': 'Dortmund', 'sportingcp': 'Sp Lisbon', 'sporting': 'Sp Lisbon', 'realsociedad': 'Sociedad',
           'rayovallecano': 'Vallecano', 'celtavigo': 'Celta', 'realbetis': 'Betis', 'wolverhampton': 'Wolves',
           'nottinghamforest': "Nott'm Forest", 'newcastleunited': 'Newcastle', 'tottenhamhotspur': 'Tottenham'}


# Znacznik rezerw/mlodziezy/kobiet jako OSOBNY czlon nazwy. Liczymy je po obu stronach i blokujemy
# dopasowanie tylko wtedy, gdy kandydat ma ich WIECEJ niz zrodlo. Samo "czy kandydat zawiera znacznik"
# nie wystarczalo: "Boca Juniors" i "Young Boys" to pierwsze zespoly, a zawieraja "juniors" i "young",
# przez co ochrona sie dla nich wylaczala i "Boca Juniors" lapalo sie na "Boca Juniors Sub-20".


from nazwy import znaczniki as _znaczniki   # historia zmian (22.09 [K]/(W), 23.09 rodzaje): nazwy.py


# 23.09.2026, USTERKA U5: Asociacion Deportivo Cali jest w bazie jako 'AD Cali'.
ALIASES.setdefault('deportivocali', 'AD Cali')
ALIASES.setdefault('asociaciondeportivocali', 'AD Cali')
# 23.09.2026, USTERKI U2/U3 z 12:00: nazwy z oferty STS dla klubow, ktorych rdzen maja tez kluby
# z innych krajow (build_kb rozdziela je przyrostkiem kraju, patrz kluby.py).
for _k, _v in {'libertadasuncion': 'Libertad', 'clublibertad': 'Libertad',
               'sportivosanlorenzo': 'CS San Lorenzo', 'clubsportivosanlorenzo': 'CS San Lorenzo',
               'cafenixmontevideo': 'Fénix', 'fenixmontevideo': 'Fénix', 'centroatleticofenix': 'Fénix',
               'colonfc': 'Colon', 'colonfcmontevideo': 'Colon', 'santoslaguna': 'Santos Laguna',
               'clubsantoslaguna': 'Santos Laguna'}.items():
    ALIASES.setdefault(_k, _v)
# 28.09.2026 (Poprawka 55, USTERKI 3–5 z przebiegu 21:00): rdzen nazwy wspolny dla klubow z roznych
# krajow, a STS dopisuje miasto. Kazda para sprawdzona recznie na kb.sqlite i w plikach zewn/:
#  - "Olimpia Asuncion" -> Olimpia (PAR, 523 mecze; Flashscore zapisuje wprost "Olimpia Asuncion").
#    NIE: CD Olimpia (Honduras), Olimpia De Itá (PAR Primera B), Olimpia Satu-Mare.
#  - "Itagui Leones FC" -> Leones (Colombia | Primera B, jedyne "Leones" w tej lidze; FS: "Leones").
#    NIE: Leones FC (Ekwador), Leones FC [colombia] (zapis Primera A do 2018).
#  - "Independiente Yumbo" -> Independiente Valle del Cauca (Colombia | Primera B; ten sam klub —
#    365scores nazywa jego U20 "Independiente Yumbo U20", Sofascore: team/independiente-yumbo).
#  - "Independiente La Chorrera" -> Independiente [panama] (Liga Panamena). NIE: "... U20" (mlodziez).
for _k, _v in {'olimpiaasuncion': 'Olimpia',
               'itaguileonesfc': 'Leones', 'itaguileones': 'Leones', 'leonesfcitagui': 'Leones',
               'independienteyumbo': 'Independiente Valle del Cauca',
               'independientelachorrera': 'Independiente [panama]',
               'caindependientelachorrera': 'Independiente [panama]'}.items():
    ALIASES.setdefault(_k, _v)
# 23.09.2026 (wyd. 24): polskie nazwy STS dla klubow, ktorych nie ratuje zamiana nazwy miasta
# (sprawdzone recznie na kb.sqlite 23.09.2026; kazdy cel ma setki meczow w lidze swojego kraju).
for _k, _v in {'sportinglizbona': 'Sp Lisbon', 'sportinglisbon': 'Sp Lisbon',
               'szachtardonieck': 'Shakhtar Donetsk', 'szachtar': 'Shakhtar Donetsk',
               'crvenazvezdabelgrad': 'Red Star [serbia]', 'crvenazvezda': 'Red Star [serbia]',
               'olympiakospireus': 'Olympiakos', 'olympiakos': 'Olympiakos',
               'juventusturyn': 'Juventus', 'betissewilla': 'Betis', 'realbetissewilla': 'Betis'}.items():
    ALIASES.setdefault(_k, _v)

# 23.09.2026: warianty nazw z recznej listy kluby.py (ten sam klub, inny zapis w zrodlach) — oferta STS moze
# uzyc DOWOLNEGO z nich ("Jeju SK" albo "Jeju United"). Uzywane DOPIERO, gdy nazwa nie jest dokladnie nazwa
# innego klubu w bazie ("San Lorenzo" zostaje argentynskim San Lorenzo), i tylko dla nazw z co najmniej
# dwoch czlonow — pojedyncze "Sparta", "Colon", "Lommel" sa niejednoznaczne i aliasu nie dostaja.
ALIASES_KLUBY = {'slaviapraga': 'Slavia Prague', 'spartapraga': 'Sparta Prague', 'bohemianspraga': 'Bohemians 1905',
                 'bohemianspraga1905': 'Bohemians 1905', 'independientemedellin': 'Independiente',
                 'deportivoindependientemedellin': 'Independiente', 'lduquito': 'LDU', 'ligadeportivauniversitaria': 'LDU',
                 # A-League: w bazie skroty z historii, oferta pisze pelne nazwy
                 'melbournevictory': 'Melb Victory', 'melbournecity': 'Melb City', 'westernsydneywanderers': 'W Sydney',
                 'westernsydney': 'W Sydney', 'centralcoastmariners': 'Central Coast', 'wellingtonphoenix': 'Wellington',
                 'perthglory': 'Perth Glory FC', 'macarthurfc': 'Macarthur Fc', 'macarthur': 'Macarthur Fc',
                 # "Red Star" (bez przyrostka) to francuski Red Star FC (clubelo); Crvena zvezda ma przyrostek
                 'crvenazvezda': 'Red Star [serbia]', 'fkcrvenazvezda': 'Red Star [serbia]',
                 'redstarbelgrade': 'Red Star [serbia]', 'crvenazvezdabeograd': 'Red Star [serbia]',
                 'lommel': 'Lommel SK', 'klommelsk': 'Lommel SK',
                 # Poprawka 42 (24.09.2026): kluby z oferty 24.09 obecne w bazie pod innym zapisem
                 'unionlacalera': 'U. La Calera',
                 'universidadcatolicasantiago': 'Univ Católica [chile]',
                 'desportessantacruz': 'Deportes Santa Cruz',
                 'atenasdesancarlos': 'Atenas San Carlos',
                 'hapoelacre': 'Hapoel Akko',
                 'mskkiryatyam': 'Kiryat Yam Sc',
                 'csdxelaju': 'Club Xelaju',
                 'alianzafcsansalvador': 'Alianza FC [elsalvador]',
                 'celajeadensers': 'Lajeadense',
                 'ecpassofundo': 'Passo Fundo (RS)',
                 'ceaimorers': 'Aimoré',
                 'bomjesusec': 'Bom Jesus - GO',
                 'goianiago': 'Goiânia EC',
                 # Poprawka 43 (24.09.2026): jedyny kandydat w swojej lidze (sprawdzone na skladzie ligi 2026)
                 'fcashdod': 'SC Ashdod',                 # Izrael National League: jedyny klub z Aszdodu
                 'cebentogoncalvesrs': 'Esportivo/RS',    # Gaucho A2: Clube Esportivo Bento Goncalves
                 'ecguaranirs': 'Guarani-VA',             # Gaucho A2: EC Guarani (Venancio Aires)
                 'uniaofrederiquensedefutebolrs': 'União-RS', 'uniaofrederiquense': 'União-RS',  # Gaucho A2
                 'scgauchopassofundo': 'SC Gaucho',       # Gaucho A2 (dotad przez krotsza nazwe z ostrzezeniem)
                 'cesantacruzrs': 'Santa Cruz RS',}

def _rezerwa(zrodlo, kandydat):
    """Blokuje "Inter Milan" -> "Inter Milan U23" i pierwsza druzyne -> zespol kobiecy/mlodziezowy.
    Test jest SYMETRYCZNY: rozna liczba znacznikow w obie strony znaczy, ze to nie ten sam
    zespol. 22.09.2026: wersja jednostronna przepuszczala "Club Leon [K]" -> "Club Leon"
    i "Barcelona (W)" -> "Barcelona", bo znacznik byl po stronie ZRODLA, nie kandydata."""
    return _znaczniki(kandydat) != _znaczniki(zrodlo)


@functools.lru_cache(maxsize=None)
def _tokeny(s):
    return tuple(re.findall(r'[a-z0-9]+', unicodedata.normalize('NFKD', str(s).translate(_LITERY)).encode('ascii', 'ignore').decode().lower()))


# Nazwy reprezentacji: STS pisze po polsku, bazy po angielsku — i to KAZDA INACZEJ.
# Baza piłkarska (intl) uzywa 'Czech Republic', 'Turkey', 'United States';
# baza 365scores (siatkowka/koszykowka) 'Czechia', 'Turkiye', 'USA'. Dlatego wartoscia
# jest LISTA wariantow sprawdzanych po kolei przeciwko puli danego sportu — pierwszy
# obecny w puli wygrywa. Dopisanie wariantu jest bezpieczne: to test przynaleznosci
# do puli, a nie dopasowanie rozmyte, wiec nie moze wskazac innej druzyny.
_KRAJE_PL = {
    'albania': ('Albania',), 'algieria': ('Algeria',), 'andora': ('Andorra',),
    'anglia': ('England',), 'angola': ('Angola',), 'arabiasaudyjska': ('Saudi Arabia',),
    'argentyna': ('Argentina',), 'armenia': ('Armenia',), 'australia': ('Australia',),
    'austria': ('Austria',), 'azerbejdzan': ('Azerbaijan',), 'belgia': ('Belgium',),
    'bialorus': ('Belarus',), 'boliwia': ('Bolivia',),
    'bosniaihercegowina': ('Bosnia and Herzegovina', 'Bosnia & Herzegovina', 'Bosnia-Herzegovina'),
    'bosnia': ('Bosnia and Herzegovina', 'Bosnia & Herzegovina', 'Bosnia-Herzegovina'),
    'brazylia': ('Brazil',), 'bulgaria': ('Bulgaria',), 'chile': ('Chile',),
    'chiny': ('China', 'China PR'), 'chorwacja': ('Croatia',), 'cypr': ('Cyprus',),
    'czarnogora': ('Montenegro',), 'czechy': ('Czechia', 'Czech Republic'),
    'dania': ('Denmark',), 'dominikana': ('Dominican Republic',), 'dominika': ('Dominica',),   # 30.09: Dominika != Dominikana
    # 30.09 (Rozliczenie 29.09): skroty STS „Pn.”/„Pd.” — „Macedonia Pn.” nie rozliczala sie (BRAK WYNIKU)
    'macedoniapn': ('North Macedonia',), 'irlandiapn': ('Northern Ireland',),
    'koreapd': ('South Korea', 'Korea Republic'), 'koreapn': ('North Korea', 'Korea DPR'),
    'brytyjskiewyspydziewicze': ('British Virgin Islands',), 'wyspydziewiczeusa': ('United States Virgin Islands',),
    # 01.10.2026 (Raport 21:00, Kajmany - Portoryko -> „NIE ZNALEZIONO reprezentacji”): wszystkie reprezentacje meskie
    # z oferty 24-30.09 bez polskiej nazwy w tabeli — kazda jest w bazie intl (54-333 meczow)
    'kajmany': ('Cayman Islands',), 'gwadelupa': ('Guadeloupe',), 'martynika': ('Martinique',),
    'malediwy': ('Maldives',), 'seszele': ('Seychelles',), 'saintkittsinevis': ('Saint Kitts and Nevis',),
    'wyspycooka': ('Cook Islands',),
    # 04.10.2026 (Raport 18:00, usterka 3: „Bahamy”, „Turks i Caicos” -> NIE ZNALEZIONO). Zamiast dwoch napisow —
    # przeglad CALEJ tabeli intl: 63 reprezentacje z >= 8 meczami od 2023 nie mialy wpisu; tu te, ktorych polska
    # nazwa rozni sie od angielskiej (pozostale, np. Aruba, Haiti, Honduras, trafia sama nazwa).
    'bahamy': ('Bahamas',), 'turksicaicos': ('Turks and Caicos Islands',),
    'saintvincentigrenadyny': ('Saint Vincent and the Grenadines',), 'bangladesz': ('Bangladesh',),
    'gujanafrancuska': ('French Guiana',), 'wyspaman': ('Isle of Man',), 'makau': ('Macau',), 'makao': ('Macau',),
    'wyspysalomona': ('Solomon Islands',), 'timorwschodni': ('Timor-Leste',),
    'wyspyswietegotomaszaiksiazeca': ('São Tomé and Príncipe',), 'saotomeiprincipe': ('São Tomé and Príncipe',),
    'amerykanskiewyspydziewicze': ('United States Virgin Islands',), 'egipt': ('Egypt',),
    'ekwador': ('Ecuador',), 'estonia': ('Estonia',), 'filipiny': ('Philippines',),
    'finlandia': ('Finland',), 'francja': ('France',), 'ghana': ('Ghana',),
    'gibraltar': ('Gibraltar',), 'grecja': ('Greece',), 'gruzja': ('Georgia',),
    'hiszpania': ('Spain',), 'holandia': ('Netherlands', 'Holland'),
    'niderlandy': ('Netherlands', 'Holland'), 'indie': ('India',),
    'indonezja': ('Indonesia',), 'iran': ('Iran',),
    'irlandia': ('Republic of Ireland', 'Ireland'),
    'republikairlandii': ('Republic of Ireland', 'Ireland'),
    'irlandiapolnocna': ('Northern Ireland',), 'islandia': ('Iceland',),
    'izrael': ('Israel',), 'japonia': ('Japan',), 'kamerun': ('Cameroon',),
    'kanada': ('Canada',), 'katar': ('Qatar',), 'kazachstan': ('Kazakhstan',),
    'kenia': ('Kenya',), 'kolumbia': ('Colombia',),
    'koreapoludniowa': ('South Korea', 'Korea Republic'),
    'koreapolnocna': ('North Korea', 'Korea DPR'),
    'kosowo': ('Kosovo',), 'kostaryka': ('Costa Rica',), 'kuba': ('Cuba',),
    'liechtenstein': ('Liechtenstein',), 'litwa': ('Lithuania',), 'lotwa': ('Latvia',),
    'luksemburg': ('Luxembourg',), 'macedoniapolnocna': ('North Macedonia',),
    'malta': ('Malta',), 'maroko': ('Morocco',), 'meksyk': ('Mexico',),
    'moldawia': ('Moldova',), 'niemcy': ('Germany',), 'nigeria': ('Nigeria',),
    'norwegia': ('Norway',), 'nowazelandia': ('New Zealand',), 'panama': ('Panama',),
    'paragwaj': ('Paraguay',), 'peru': ('Peru',), 'polska': ('Poland',),
    'portoryko': ('Puerto Rico',), 'portugalia': ('Portugal',),
    'republikapoludniowejafryki': ('South Africa',), 'rpa': ('South Africa',),
    'rosja': ('Russia',), 'rumunia': ('Romania',), 'salwador': ('El Salvador',),
    'sanmarino': ('San Marino',), 'senegal': ('Senegal',), 'serbia': ('Serbia',),
    'slowacja': ('Slovakia',), 'slowenia': ('Slovenia',),
    'stanyzjednoczone': ('USA', 'United States'), 'usa': ('USA', 'United States'),
    'szkocja': ('Scotland',), 'szwajcaria': ('Switzerland',), 'szwecja': ('Sweden',),
    'tajlandia': ('Thailand',), 'tajwan': ('Chinese Taipei', 'Taiwan'),
    'tunezja': ('Tunisia',), 'turcja': ('Turkiye', 'Turkey'), 'ukraina': ('Ukraine',),
    'urugwaj': ('Uruguay',), 'walia': ('Wales',), 'wegry': ('Hungary',),
    'wenezuela': ('Venezuela',), 'wietnam': ('Vietnam',), 'wlochy': ('Italy',),
    'wyspyowcze': ('Faroe Islands',), 'wybrzezekoscisloniowej': ('Ivory Coast',),
    'zjednoczoneemiratyarabskie': ('United Arab Emirates',),
    # Poprawka 42 (24.09.2026): nazwy z oferty 24.09, ktore nie trafialy w baze
    'afganistan': ('Afghanistan',),
    'antiguaibarbuda': ('Antigua and Barbuda',),
    'bahrajn': ('Bahrain',),
    'bermudy': ('Bermuda',),
    'birma': ('Myanmar',),
    'czad': ('Chad',),
    'demokratycznarepublikakonga': ('DR Congo',),
    'drkongo': ('DR Congo',),
    'dzibuti': ('Djibouti',),
    'erytrea': ('Eritrea',),
    'etiopia': ('Ethiopia',),
    'fidzi': ('Fiji',),
    'gujana': ('Guyana',),
    'gwatemala': ('Guatemala',),
    'gwinea': ('Guinea',),
    'gwineabissau': ('Guinea-Bissau',),
    'gwinearownikowa': ('Equatorial Guinea',),
    'hongkong': ('Hong Kong',),
    'irak': ('Iraq',),
    'jamajka': ('Jamaica',),
    'jemen': ('Yemen',),
    'jordania': ('Jordan',),
    'kambodza': ('Cambodia',),
    'kirgistan': ('Kyrgyzstan',),
    'komory': ('Comoros',),
    'kongo': ('Congo',),
    'kuwejt': ('Kuwait',),
    'liban': ('Lebanon',),
    'libia': ('Libya',),
    'madagaskar': ('Madagascar',),
    'malezja': ('Malaysia',),
    'mauretania': ('Mauritania',),
    'mjanma': ('Myanmar',),
    'mozambik': ('Mozambique',),
    'nikaragua': ('Nicaragua',),
    'nowakaledonia': ('New Caledonia',),
    'palestyna': ('Palestine',),
    'papuanowagwinea': ('Papua New Guinea',),
    'republikasrodkowoafrykanska': ('Central African Republic',),
    'republikazielonegoprzyladka': ('Cape Verde',),
    'singapur': ('Singapore',),
    'sudanpoludniowy': ('South Sudan',),
    'surinam': ('Suriname',),
    'tadzykistan': ('Tajikistan',),
    'trynidaditobago': ('Trinidad and Tobago',),
    'wyspyzielonegoprzyladka': ('Cape Verde',),
}


def _kraj_pl(name, pool):
    """Angielska nazwa reprezentacji dla polskiej, wybrana sposrod wariantow obecnych w PULI.
    Zwraca None, gdy zadnego wariantu nie ma — a None jest poprawnym wynikiem."""
    k = norm(name)
    kand = _KRAJE_PL.get(k)
    if kand is None:                      # druzyna kobieca: "Polska [K]", "Niemcy (K)", "Chiny W"
        for suf in ('k', 'w', 'kobiety', 'kobiet'):
            if k.endswith(suf) and k[:-len(suf)] in _KRAJE_PL:
                baza = _KRAJE_PL[k[:-len(suf)]]
                kand = tuple(f'{b} (W)' for b in baza) + tuple(f'{b} W' for b in baza)
                break
    if not kand: return None
    for c in kand:
        if c in pool: return c
    return None

def _zaw_nazwy(a, b):
    """Czy jedna nazwa jest skrotem drugiej. Porownujemy CZLONY nazwy, nie litery.
    21.09.2026, trzecia proba — dwie poprzednie mylily druzyny:
      wersja 1 (udzial dlugosci >=45%): "Legia" wpadalo w "coLEGIAles",
      wersja 2 (prefiks/sufiks na literach): "Inter" wpadalo w "INTERnational Pacific University",
        "Magda" w "MAGDAlena Frech", "South" w "SOUTHern Connecticut State", "Basket" w "BASKETball Lowen".
    Skrot klubu ucina cale czlony z poczatku albo z konca ("MHK Nitra" -> "Nitra",
    "Montpellier Handball" -> "Montpellier"), nigdy polowe slowa. Dlatego czlony musza
    zgadzac sie w calosci i lezec na brzegu nazwy."""
    ta, tb = _tokeny(a), _tokeny(b)
    if not ta or not tb: return False
    d, k = (ta, tb) if len(ta) >= len(tb) else (tb, ta)
    if len(''.join(k)) < 4: return False        # "US", "AC", "Tre" — za malo, zeby cokolwiek rozstrzygac
    return d[:len(k)] == k or d[-len(k):] == k


# Czlony, ktorych brak NIE zmienia klubu: forma prawna / typ klubu i nazwa dyscypliny.
# "FC Barcelona" -> "Barcelona", "MHK Nitra" -> "Nitra", "Montpellier Handball" -> "Montpellier".
# CELOWO NIE MA tu: u19/u21/u23, ii, b, reserves (to INNE druzyny) ani rdzeni typu
# Real/Sporting/Dinamo/Independiente (to ONE sa wspolne dla wielu klubow).
_OGOLNE = frozenset('fc cf sc ac as ss sv fk nk sk bk hk hc mhk vk kk rk ok ks cd ca cs ud sd ec afc cfc fbc sad '
                    'bsc ksv krc kvc rsc kaa kfc '   # 03.10.2026: formy prawne (BSC Young Boys, KSV Roeselare, KRC Genk)

                    'club clube klub calcio futbol football fussball handball basket basketball volley volleyball '
                    'hockey sport sports de del la el the da do'.split())


_SKROTY = {}   # nazwa z oferty -> klub, dopasowane przez przypadek (c) ponizej; sprawdza club()
_SKROTY_OGOLNE = set()   # z tego: nazwy, w ktorych odpadly WYLACZNIE czlony ogolne (przypadek (a))
_PUCHAR = re.compile(r'(?i)\b(cup|puchar|copa|coupe|coppa|pokal|beker|ta[cç]a|kupa|kupasi|trophy|super ?cup)\b')


def skrot_w_pucharze_ok(skroty, mt, kraje):
    """01.10.2026 (Raport 12:00, USTERKA 4): Katar, QSL Cup — „Al-Gharafa SC” -> Al Gharafa, „Al-Mesaimeer SC” ->
    Mesaimeer SC; kluby z dwoch poziomow ligi nie maja wspolnej ligi, wiec kontrola LACZNA zawsze przerywala mecze
    pucharu krajowego. Para jest przyjmowana bez wspolnej ligi TYLKO gdy: terminarz znalazl ten mecz i to PUCHAR,
    kraj terminarza zgadza sie z krajem lig obu klubow, a w kazdej skroconej nazwie odpadly wylacznie czlony
    ogolne (SC, FC, Al…). Czlon rozrozniajacy („Independiente Yumbo”) albo brak terminarza = dalej noga MNIEJ."""
    if not mt or not _PUCHAR.search(str(mt.get('turniej', ''))): return False
    kt = norm(mt.get('kraj', ''))
    if not kt or kt in _KRAJE_OGOLNE or not all(k and _ten_sam_kraj(k, kt) for k in kraje): return False
    return all(n in _SKROTY_OGOLNE for n, _ in skroty)


def _skrot_albo_nic(name, wyn, pula):
    """22.09.2026, USTERKA U1 z przebiegu 21:00: "Independiente Yumbo" (Kolumbia, II liga) zostalo
    policzone jako "Independiente" (Argentyna, Avellaneda) — oczekiwane gole 2,05 : 0,84 z sily
    klubu z innego kraju. Kod wypisywal ostrzezenie i MIMO TO zwracal klub. Ostrzezenie w logu
    nie zatrzymuje modelu, wiec zamiast ostrzegac — rozstrzygamy:
      (a) odpadly wylacznie czlony ogolne (FC, MHK, Handball) — ten sam klub, zwracamy;
      (b) odpadl czlon rozrozniajacy, a zachowany rdzen maja w bazie TAKZE inne kluby — nie da sie
          ustalic, ktory to, zwracamy None;
      (c) odpadl czlon rozrozniajacy, rdzen jednoznaczny ("Chievo Verona" -> "Chievo") — zwracamy
          z ostrzezeniem. Tego przypadku NIE DA SIE odroznic od "Independiente Yumbo" po samym
          napisie (w bazie jest jedno Independiente), dlatego typuj.py sprawdza dodatkowo KRAJ ligi."""
    tn, tk = _tokeny(name), _tokeny(wyn)
    # 30.09.2026 (przeglad): nazwa z oferty KROTSZA niz w bazie ("Crystal" (SVK) -> "Crystal Palace",
    # "Nelson" (ENG) -> "Nelson Suburbs" (NZ)) i roznica w samych czlonach ogolnych ("BK Olympic" (SWE) ->
    # "Olympic" (AUS)) wracaly bez zadnej kontroli. Teraz ida do _SKROTY -> typuj sprawdza wspolna lige pary.
    if len(tn) <= len(tk):
        _SKROTY[name] = wyn
        return wyn
    if tn[:len(tk)] == tk: odp = tn[len(tk):]
    elif tn[-len(tk):] == tk: odp = tn[:-len(tk)]
    else: odp = tuple(t for t in tn if t not in tk)
    if odp and all(t in _OGOLNE for t in odp):
        _SKROTY[name] = wyn
        _SKROTY_OGOLNE.add(name)
        return wyn
    inne = sorted(p for p in pula if p != wyn and len(_tokeny(p)) > len(tk)
                  and (_tokeny(p)[:len(tk)] == tk or _tokeny(p)[-len(tk):] == tk))
    if inne:
        print(f'  ODRZUCONO: "{name}" -> "{wyn}" zgubiloby czlon rozrozniajacy, a rdzen "{wyn}" maja '
              f'w bazie tez: {", ".join(inne[:4])}{" ..." if len(inne) > 4 else ""}. '
              f'Nie da sie ustalic, ktory to klub — noga MNIEJ.')
        return None
    print(f'  UWAGA: "{name}" dopasowane do KROTSZEJ nazwy "{wyn}" — pominieto czlon '
          f'rozrozniajacy. Rdzen jest w bazie jednoznaczny, ale sprawdz, czy to ten sam klub.')
    _SKROTY[name] = wyn
    if all(t in _OGOLNE or t == 'al' for t in odp):   # arabskie „Al-” (Al-Mesaimeer SC -> Mesaimeer SC), rdzen jednoznaczny
        _SKROTY_OGOLNE.add(name)
    return wyn



# Kraj ligi — do kontroli, czy obie druzyny meczu ligowego sa z jednego kraju.
_KRAJ_KODU_EXTRA = {'SC2': 'scotland', 'SC3': 'scotland', 'EC': 'england'}


def _kraj_ligi(div):
    """Kraj rozgrywek z kodu Division, albo None, gdy nie da sie ustalic (wtedy NIE blokujemy).
    Zrodla: 'Kraj | Liga' (ligi spoza mapy, zewn.py), mapa SOFA_DIV z zewn.py (kod -> kraj),
    nazwa wolna z uzupelnij_ligi ('Chile First Division B' -> chile)."""
    if not div: return None
    s = str(div)
    if '|' in s: return norm(s.split('|')[0]) or None
    try:
        from zewn import SOFA_DIV
    except Exception:
        SOFA_DIV = []
    for kraj, _, kod in SOFA_DIV:
        if kod == s: return norm(kraj)
    if s in _KRAJ_KODU_EXTRA: return _KRAJ_KODU_EXTRA[s]
    n = norm(s)
    for kraj in sorted({norm(k) for k, _, _ in SOFA_DIV}, key=len, reverse=True):
        if kraj and n.startswith(kraj): return kraj
    return None


# 23.09.2026 (recenzja): porownanie przez podciag uznawalo za ten sam kraj oman/romania, niger/nigeria,
# northernireland/ireland, sudan/southsudan, congo/drcongo. Fragmenty z SOFA_DIV sprowadzamy do pelnej
# nazwy JAWNA mapa i porownujemy dokladnie.
_KRAJ_KANON = {'turk': 'turkey', 'turkiye': 'turkey', 'turkey': 'turkey', 'saudi': 'saudiarabia',
               'saudiarabia': 'saudiarabia', 'czech': 'czechia', 'czechia': 'czechia', 'czechrepublic': 'czechia',
               'korea': 'southkorea', 'southkorea': 'southkorea', 'korearepublic': 'southkorea',
               'usa': 'usa', 'unitedstates': 'usa', 'unitedstatesofamerica': 'usa'}


# nazwy "krajow" 365scores, ktore nie sa krajem (rozgrywki miedzynarodowe) — tu terminarz nie rozstrzyga
_KRAJE_OGOLNE = frozenset({'world', 'international', 'intl', 'europe', 'asia', 'africa', 'oceania', 'southamerica',
                           'northcentralamerica', 'northandcentralamerica', 'concacaf', 'intercontinental', 'americas',
                           'australiaoceania', 'australiaandoceania'})   # dwa ostatnie: Flashscore


def _kanon_kraju(a):
    # 'and' usuwane z obu stron: Flashscore „BOSNIA AND HERZEGOVINA”, SofaScore „Bosnia & Herzegovina”
    return _KRAJ_KANON.get(a, a).replace('and', '')


def _ten_sam_kraj(a, b):
    return _kanon_kraju(a) == _kanon_kraju(b)


@functools.lru_cache(maxsize=1)
def _kraje_znane():
    """Kraje lig z bazy (SOFA_DIV) po kanonizacji — terminarz blokuje tylko przy kraju z tej listy."""
    try:
        from zewn import SOFA_DIV
    except Exception:
        SOFA_DIV = []
    return frozenset(_kanon_kraju(norm(k)) for k, _, _ in SOFA_DIV if norm(k)) | \
        frozenset(_kanon_kraju(v) for v in _KRAJ_KANON.values()) | \
        frozenset(_kanon_kraju(norm(w)) for ws in _KRAJE_PL.values() for w in ws)   # nazwy panstw (reprezentacje)

try:
    from kluby import SCAL_RECZNIE as _SR
    for _kl, _b in _SR.items():
        _a = _kl[1]
        if len(_kl) == 2 and len(_tokeny(_a)) >= 2:   # wpis z data dzieli nazwe na dwa kluby — nie jest aliasem
            ALIASES_KLUBY.setdefault(norm(_a), _b)
except ImportError:
    pass


_WARIANTY = {}


def wczytaj_warianty(con):
    """Tabela warianty_nazw z build_kb: nazwa zrodlowa (np. "Hertha Berlin") -> nazwa klubu w bazie ("Hertha").
    Klucz po norm(); klucz wskazujacy dwa rozne kluby jest pomijany."""
    try:
        w = pd.read_sql('select wariant, klub from warianty_nazw', con)
    except Exception:
        return
    # warianty z samych slow ogolnych ("Atletico", "Santa Fe", "Real") pasuja do wielu klubow — pomijamy
    ogolne = {'atletico', 'deportivo', 'sporting', 'real', 'union', 'nacional', 'independiente', 'santa', 'fe', 'san',
              'racing', 'city', 'united', 'athletic', 'dynamo', 'dinamo', 'olimpia', 'universidad', 'universitario',
              'juventud', 'alianza', 'america', 'sport', 'sports', 'rovers', 'town', 'county', 'wanderers', 'deportes'}
    d = {}
    for a, b in zip(w.wariant, w.klub):
        k = norm(a)
        t = set(_tokeny(a))
        if not k or not t or t <= ogolne: continue
        d.setdefault(k, set()).add(b)
    _WARIANTY.clear()
    _WARIANTY.update({k: v.pop() for k, v in d.items() if len(v) == 1})


def resolve(name, pool):
    """Zwraca nazwe z bazy albo None. None jest POPRAWNYM wynikiem — wolacz ma sie wtedy zatrzymac.
    21.09.2026: naprawiony blad, przez ktory zwracalo ZAWSZE cos, takze dla nieznanych druzyn.
    Przyczyna: w bazie jest druzyna "Pyx" zapisana cyrylica; norm() usuwa znaki spoza ASCII,
    wiec jej klucz byl PUSTYM ciagiem, a pusty ciag zawiera sie w kazdym napisie ("kk in k").
    Stawala sie przez to uniwersalnym jokerem: "Redditch United", "RC Warwick" i
    "Virtus Ciserano Bergamo" dostawaly jej statystyki i pelna, wiarygodnie wygladajaca tabele P.
    Dlatego ponizej odrzucamy z puli wszystkie nazwy, ktore po normalizacji sa puste."""
    k = norm(name)
    if not k: return None
    if k in ALIASES and ALIASES[k] in pool: return ALIASES[k]
    # mapa krajow DOPIERO po ALIASES: alias jest reczna nadpiska i musi wygrywac,
    # gdyby w ktoryms sporcie polska nazwa kraju oznaczala co innego niz reprezentacje.
    _kr = _kraj_pl(name, pool)
    if _kr: return _kr
    # sorted(): pool to zbior, a kolejnosc iteracji zbioru zalezy od losowego ziarna
    # hasha w danym procesie. Bez tego przy dwoch nazwach o tym samym kluczu wynik
    # bywal RAZ jeden, RAZ drugi — ta sama nazwa z oferty dawala rozne druzyny.
    by = {norm(p): p for p in sorted(pool) if norm(p) and not _rezerwa(name, p)}   # <-- bez tego filtra wraca blad z 21.09
    # dwie ROZNE nazwy moga uproscic sie do tego samego klucza ("Andreeva" i "Andreev A.",
    # "Rangers" i "Ranger's") — slownik zostawia wtedy jedna z nich po cichu. Ostrzegamy.
    _kol = {}
    for _p in sorted(pool):
        _k = norm(_p)
        if _k: _kol.setdefault(_k, set()).add(_p)
    if k in _kol and len(_kol[k]) > 1:
        print(f'  UWAGA: "{name}" pasuje do {len(_kol[k])} roznych wpisow w bazie '
              f'({", ".join(sorted(_kol[k]))}) — sprawdz, ktory to.')
    if k in by: return by[k]
    # 29.09.2026 (rozliczenie 27.09): druzyna kobiet — STS pisze "Bay FC [K]", baza "Bay FC W" / "Bay FC (W)".
    # Szukamy nazwy BEZ znacznika tylko wsrod druzyn kobiet z puli (znacznik tego samego rodzaju), dokladnie.
    if 'kobiety' in _znaczniki(name):
        _bez = lambda s: ' '.join(x for x in re.split(r'\s+', str(s).strip()) if not _znaczniki(x.strip('[](){}<>.,;:')))
        kob = {}
        for p in sorted(pool):
            if _znaczniki(p) == _znaczniki(name): kob.setdefault(norm(_bez(p)), set()).add(p)
        kb_ = norm(_bez(name))
        if kb_ and len(kob.get(kb_, ())) == 1: return next(iter(kob[kb_]))
    if k in ALIASES_KLUBY and ALIASES_KLUBY[k] in pool: return ALIASES_KLUBY[k]
    if k in _WARIANTY and _WARIANTY[k] in pool: return _WARIANTY[k]   # nazwa zrodlowa sklejonego klubu (build_kb)
    c = [p for p in by.values() if _zaw_nazwy(name, p)]
    if c:
        if len(c) == 1:
            wyn = c[0]
        else:   # "Chievo Verona" zawiera i "Chievo", i "Verona" — pierwszy czlon to niemal zawsze wlasciwy klub
            pref = [p for p in c if k.startswith(norm(p)) or norm(p).startswith(k)]
            if len(pref) == 1: wyn = pref[0]
            else:
                # 29.09.2026: wczesniej wybor najdluzszego / najblizszego dlugoscia kandydata — zgadywanie
                # („Dinamo” -> „Dinamo Samarkand”, „Spartak” -> „Spartak Kostroma”, „Sparta” -> „Sparta
                # Rotterdam”, „Real” -> „Real Madrid Castilla”). Kilku kandydatow = noga MNIEJ.
                print(f'  ODRZUCONO: "{name}" pasuje do {len(c)} klubow ({", ".join(sorted(c)[:5])}) — '
                      f'nie zgadujemy, noga MNIEJ.')
                return None
        # 03.10.2026: „Dukla Praga” -> „Praga” (maly klub z Prazsky prebor, nowy w bazie), a cala nazwa po zamianie
        # miasta to „Dukla Prague”. Pelna nazwa (egzonim) wygrywa z dopasowaniem do czesci nazwy.
        if len(_tokeny(name)) > len(_tokeny(wyn)):
            alt = ' '.join(EGZONIMY.get(norm(x), x) for x in str(name).split())
            if alt != name:
                r2 = resolve(alt, pool)
                if r2 and r2 != wyn and len(_tokeny(r2)) > len(_tokeny(wyn)): return _przez_egzonim(name, pool)
        # 03.10.2026: „Wisła II Płock” -> „Wisla II” (Flashscore: rezerwy Wisly KRAKOW, III liga gr. IV). Odpadl czlon
        # rozrozniajacy („plock”), a w bazie jest INNY klub z rdzeniem i tym czlonem („Wisla Plock”) — skrot nalezy
        # do innego klubu tej samej nazwy. Nie zgadujemy: noga MNIEJ.
        _rdz = {t for t in _tokeny(wyn) if not _znaczniki(t) and t not in _OGOLNE}
        _odp = {t for t in _tokeny(name) if t not in _tokeny(wyn) and not _znaczniki(t) and t not in _OGOLNE}
        if _rdz and _odp:
            inny = [p for p in pool if p != wyn and (_rdz | _odp) <= set(_tokeny(p)) and set(_znaczniki(p)) <= set(_znaczniki(name))]
            if inny:
                print(f'  ODRZUCONO: "{name}" -> "{wyn}", ale w bazie jest "{sorted(inny)[0]}" (czlon {", ".join(sorted(_odp))}) — '
                      f'skrot moze nalezec do innego klubu, noga MNIEJ.')
                return None
        return _skrot_albo_nic(name, wyn, by.values())
    # prog 0.55 byl za luzny: "RC Warwick" trafialo na "RKC Waalwijk", a "Virtus Ciserano Bergamo"
    # na "Virtus Lanciano". Lepiej zwrocic None i zatrzymac analize, niz policzyc nie ten mecz.
    # rozmyte tylko dla dluzszych nazw i z wysokim progiem (0,87 zamiast 0,80:
    # przy 0,80 "Argentinos"->"Argentino MM", "Champions"->"Campion", "Karlstad"->"Harstad") — przy 3-5 znakach prog 0,80 osiaga sie trywialnie
    # i dawal "Nart"->"Lenart", "Amal"->"Samail", "Pro"->"Paro", "Cuba"->"Cuiaba"
    m = difflib.get_close_matches(k, list(by), n=1, cutoff=0.90) if len(k) >= 8 else []
    # dodatkowo pierwsze trzy znaki musza sie zgadzac: przy samym progu 0,90
    # przechodzilo jeszcze "Champions"->"Campion" i "Academico"->"Academica" (dwa rozne kluby).
    # Brak dopasowania to noga MNIEJ na kuponie, pomylona druzyna to kupon przegrany —
    # ta asymetria kaze wybrac ostroznosc.
    m = [x for x in m if x[:3] == k[:3]]
    if m:
        print(f'  UWAGA: "{name}" dopasowane ROZMYTO do "{by[m[0]]}" — upewnij sie, ze to ta sama druzyna.')
        return by[m[0]]
    return None


def stan_bazy():
    """Znacznik stanu kb.sqlite (czas modyfikacji + rozmiar) do kluczy cache."""
    f = os.path.join(HERE, 'kb.sqlite')
    return f'{int(os.path.getmtime(f))}_{os.path.getsize(f)}' if os.path.exists(f) else '0'


def kalibruj_v5n(KR, k, p):
    """Korekta per rynek z korekta_rynkow_v5n.csv (tylko w dol); rynki „ponizej” zawsze min. −4 pp (regula uzytkownika).
    30.09.2026: wyjete z main(), zeby test_ostatnie.py oceniał ten sam model, ktory typuje."""
    s = 0.0
    for r in KR[KR.rynek == k].itertuples():
        lo, hi = [float(x) for x in str(r.przedzial).strip('[)').split(',')]
        if lo <= p < hi: s = float(r.przesuniecie)
    if k.startswith('U') and p >= 0.5: s = min(s, -0.04)
    return max(p + s, 0.0)


def korekta_wlasna(pc, kor_rynku):
    """Korekta z wlasnych rozliczonych typow (korekta_wlasna.csv, wiersze jednego rynku).
    30.09.2026 (przeglad): przedzial wybierany po P PRZED korekta i tylko jeden — dotad korekta mogla przesunac P
    do nastepnego przedzialu i dostac druga (0,72 -> 0,77 -> 0,89), czyli zawyzyc P."""
    for r in kor_rynku.itertuples():
        lo, hi = [float(x) for x in str(r.przedział).strip('[)').split(',')]
        if lo <= pc < hi:
            return (1 - r.waga) * pc + r.waga * r.trafność
    return pc


def cached(key, fn):
    # 30.09.2026 (przeglad): klucz byl sama data — dopasowania DC/GLM/pi z pierwszego wywolania dnia zostawaly
    # w cache/ i nie widzialy wynikow dopisanych pozniej (przebudowa bazy). Teraz klucz zawiera stan kb.sqlite.
    p = os.path.join(HERE, 'cache', f'{key}_{stan_bazy()}.pkl'); os.makedirs(os.path.dirname(p), exist_ok=True)
    if os.path.exists(p): return pickle.load(open(p, 'rb'))
    v = fn(); pickle.dump(v, open(p, 'wb')); return v


def team_stats(m, team, n=10):
    t = m[(m.HomeTeam == team) | (m.AwayTeam == team)].sort_values('MatchDate').tail(n)
    if t.empty: return None
    home = t.HomeTeam == team
    gf = np.where(home, t.FTHome, t.FTAway); ga = np.where(home, t.FTAway, t.FTHome)
    res = np.where(gf > ga, 'W', np.where(gf == ga, 'D', 'L'))
    tot = gf + ga
    s = dict(forma=''.join(res), pkt=int((res == 'W').sum() * 3 + (res == 'D').sum()), gole=f'{int(gf.sum())}:{int(ga.sum())}',
             O15=(tot > 1.5).mean(), O25=(tot > 2.5).mean(), U35=(tot < 3.5).mean(), BTTS=((gf > 0) & (ga > 0)).mean(),
             CS=(ga == 0).mean(), FTS=(gf == 0).mean(), ostatni=t.MatchDate.max().date(),
             mecze=[f"{r.MatchDate.date()} {r.HomeTeam} {int(r.FTHome)}:{int(r.FTAway)} {r.AwayTeam}" for r in t.tail(5).itertuples()])
    cf = np.where(home, t.HomeCorners, t.AwayCorners); ca = np.where(home, t.AwayCorners, t.HomeCorners)
    yc = np.where(home, t.HomeYellow, t.AwayYellow); sh = np.where(home, t.HomeTarget, t.AwayTarget)
    if np.isfinite(cf.astype(float)).sum() >= 3:
        s['rożne_za'] = np.nanmean(cf.astype(float)); s['rożne_przeciw'] = np.nanmean(ca.astype(float))
        s['żółte'] = np.nanmean(yc.astype(float)); s['strzały_celne'] = np.nanmean(sh.astype(float))
    return s


def venue_stats(m, team, where, since):
    col = 'HomeTeam' if where == 'dom' else 'AwayTeam'
    t = m[(m[col] == team) & (m.MatchDate >= since)]
    if len(t) < 3: return None
    gf = t.FTHome if where == 'dom' else t.FTAway; ga = t.FTAway if where == 'dom' else t.FTHome
    return dict(n=len(t), W=(gf > ga).mean(), D=(gf == ga).mean(), L=(gf < ga).mean(), gf=gf.mean(), ga=ga.mean(),
                O15=((gf + ga) > 1.5).mean(), U35=((gf + ga) < 3.5).mean(), BTTS=((gf > 0) & (ga > 0)).mean(),
                strzela_pierwszy_HT=(((t.HTHome if where == 'dom' else t.HTAway) > 0)).mean())


_PRZYR = re.compile(r'^(.*) \[([a-z]+)\]$')


def _jawny_kraj(name, pool, m):
    """"Nacional [portugal]" dla klubu, ktory w bazie ma nazwe BEZ przyrostka: gdy nazwa z przyrostkiem nie
    istnieje, a klub bez przyrostka jest z tego kraju — zwraca nazwe bez przyrostka. Inaczej None."""
    mm = _PRZYR.match(str(name).strip())
    if not mm or name in pool: return None
    base, kr = mm.group(1), mm.group(2)
    if base not in pool: return None
    w = m[(m.HomeTeam == base) | (m.AwayTeam == base)]
    if w.empty: return None
    k = _kraj_ligi(w.sort_values('MatchDate').Division.iloc[-1])
    return base if k and _KRAJ_KANON.get(k, k) == kr else None


def _wariant_kraju(h, a, m, pool, jawne=(False, False)):
    """23.09.2026: jedna nazwa bywa uzywana przez kluby z ROZNYCH krajow ("Santos": Brazylia i Meksyk,
    "Nacional": Portugalia i Urugwaj). build_kb zostawia nazwe jednemu klubowi (kluby.KRAJ_NAZWY / clubelo),
    reszcie dodaje przyrostek kraju ("Nacional [uruguay]").
    Recenzja 23.09: automatyczny wybor wariantu "z kraju rywala" byl bledem — w pucharze (Libertad - LDU,
    Copa Sudamericana) przerabial paragwajski Libertad na ekwadorski i omijal kontrole ROZNE KRAJE; przy dwoch
    niejednoznacznych nazwach wybral pare z ligi Aruby. Dlatego NICZEGO nie zamieniamy: gdy kraje sie nie
    zgadzaja, a istnieje wariant z przyrostkiem, zatrzymujemy i podajemy dokladna nazwe do uzycia."""
    niejedn = []
    for t, jaw in zip((h, a), jawne):
        if t is None: continue
        mm = _PRZYR.match(t); base = mm.group(1) if mm else t
        inne = sorted(p for p in pool if p != t and (p == base or (p.startswith(base + ' [') and _PRZYR.match(p))))
        if inne and not jaw:
            niejedn.append((t, inne))
            print(f'  UWAGA: nazwa "{base}" oznacza kilka klubow z roznych krajow ({", ".join([t] + inne)}). '
                  f'Wybrano "{t}". Jesli chodzi o inny klub, podaj jego nazwe z przyrostkiem, np. "{inne[0]}".')
    if h is None or a is None:
        return h, a
    if '--kontynentalny' in sys.argv:
        # Recenzja 23.09: w pucharze nie ma kraju rywala do porownania, wiec "Nacional" - "Bolivar" liczylo
        # po cichu portugalski Nacional. Nazwa wspolna bez jawnego kraju = stop.
        if niejedn:
            t, inne = niejedn[0]
            sys.exit(f'NAZWA WSPOLNA DLA KLUBOW Z ROZNYCH KRAJOW w meczu miedzynarodowym: "{t}" (inne: {", ".join(inne)}). '
                     f'Nie zgaduje. Podaj nazwe z krajem, np. "{inne[0]}" albo "{t} [<kraj>]" dla klubu bez przyrostka.')
        return h, a

    def warianty(t):
        mm = _PRZYR.match(t); base = mm.group(1) if mm else t
        return ([base] if base in pool else []) + sorted(p for p in pool if p.startswith(base + ' [') and _PRZYR.match(p))

    def kraj(t):
        mm = _PRZYR.match(t)
        if mm: return mm.group(2)
        w = m[(m.HomeTeam == t) | (m.AwayTeam == t)]
        if w.empty: return None
        k = _kraj_ligi(w.sort_values('MatchDate').Division.iloc[-1])
        return _KRAJ_KANON.get(k, k) if k else None

    wh, wa = warianty(h), warianty(a)
    if len(wh) <= 1 and len(wa) <= 1: return h, a
    kh, ka = kraj(h), kraj(a)
    if kh and ka and kh == ka: return h, a
    zgodne = [(x, y) for x in wh for y in wa if kraj(x) and kraj(x) == kraj(y)]
    ile = lambda t: int(((m.HomeTeam == t) | (m.AwayTeam == t)).sum())
    zgodne.sort(key=lambda p: -(ile(p[0]) + ile(p[1])))
    if zgodne:
        prop = '; '.join(f'"{x}" "{y}"' for x, y in zgodne[:3])
        sys.exit(f'NAZWA WSPOLNA DLA KLUBOW Z ROZNYCH KRAJOW: "{h}" ({kh}) i "{a}" ({ka}). Nie zgaduje, ktory to klub. '
                 f'Mecz ligi krajowej: uruchom ponownie z dokladnymi nazwami, np. {prop}. '
                 f'Puchar miedzynarodowy: dodaj --kontynentalny (wtedy "{h}" i "{a}" zostaja jak sa).')
    return h, a


def skrot_z_terminarza(home, h, a, skroty, mt, pool, m):
    """04.10.2026 (Raport 18:00, usterka 2): "CA Chacarita Juniors" -> "CA Chacarita Juniors (Aimogasta)" (amatorzy z La
    Rioja), choc terminarz 365 pisze ten mecz "Chacarita Juniors – Patronato" (Primera Nacional). Skrot z oferty trafil
    w INNY klub o tym samym rdzeniu; zapis z terminarza wskazuje wlasciwy. Przyjmujemy go WYLACZNIE, gdy nowa para
    grala w jednej lidze (kotwica ligowa) — inaczej None i jak dotad NIEPEWNE DOPASOWANIE (noga MNIEJ)."""
    from nazwy import wspolna_liga
    nowe = [h, a]
    for n, t in skroty:
        i = 0 if n == home else 1
        r = resolve(mt['gosp'] if i == 0 else mt['gosc'], pool)
        if not r: return None
        # 05.10.2026 (Raport 04.10 21:00 usterka 2): Godoy Cruz – CA Los Andes — OBIE nazwy byly skrotami, a terminarz
        # potwierdzal pierwsza (Godoy Cruz = Godoy Cruz). Potwierdzenie to nie powod do rezygnacji: ta strona zostaje.
        nowe[i] = r
    if nowe == [h, a] or nowe[0] == nowe[1] or not wspolna_liga(m, *nowe): return None
    print(f'  TERMINARZ ROZSTRZYGA SKROT: {"; ".join(f"{n!r} -> {t}" for n, t in skroty)} to inny klub; zapis terminarza '
          f'({mt["gosp"]} – {mt["gosc"]}) -> {nowe[0]} | {nowe[1]}, wspolna liga w ostatnich 2 latach.')
    return tuple(nowe)


def _kraj_z_terminarza(home, away, h, a, kh, ka, pool, m, mt=None):
    """30.09.2026 (audyt oferty 01.10): „CD Junior Barranquilla” -> CD Junior (Nikaragua), „CD Platense Zacatecoluca” ->
    CD Platense (Honduras). Kontrola krajow tylko odrzucala noge. Terminarz ZNA kraj meczu i zapis nazw 365/Flashscore —
    druzyne z innego kraju szukamy ponownie WSROD KLUBOW KRAJU MECZU (zapis z terminarza, potem z oferty).
    Zwraca (h, a) albo None (brak meczu, kraj ogolny, niejednoznacznie) — wtedy jak dotad noga MNIEJ."""
    if mt is None:
        try:
            import terminarz as _tm
            mt = _tm.znajdz(home, away) or _tm.znajdz(home, away, luzno=True)
        except Exception:
            return None
    if not mt: return None
    kt = norm(mt['kraj'])
    if not kt or kt in _KRAJE_OGOLNE or _kanon_kraju(kt) not in _kraje_znane(): return None
    nowe = [h, a]
    for i, (n, t_, k, zt) in enumerate(((home, h, kh, mt['gosp']), (away, a, ka, mt['gosc']))):
        if t_ is not None and (not k or _ten_sam_kraj(k, kt)): continue   # kraj nieznany nie przeczy terminarzowi
        r_ = _w_kraju((zt, n), kt, pool, m)
        if not r_: return None
        if r_ != t_:
            print(f'  UWAGA: "{n}" dopasowane w kraju meczu z terminarza ({mt["kraj"]}, {mt["turniej"]}: '
                  f'{mt["gosp"]} – {mt["gosc"]}) -> {r_} (zamiast {t_}).')
        nowe[i] = r_
    if nowe[0] == nowe[1]: return None
    print(f'Dopasowano (po terminarzu): "{home}" → {nowe[0]} | "{away}" → {nowe[1]}')
    return tuple(nowe)


def _w_kraju(nazwy, kraj, pool, m):
    """Jedna nazwa z bazy dla pierwszej z `nazwy`, ktora rozwiazuje sie JEDNOZNACZNIE wsrod klubow, ktorych ostatnia
    liga jest z kraju `kraj` (kraj z terminarza). None, gdy zadna nie daje wyniku albo wyniki sa rozne."""
    ost = pd.concat([m[['MatchDate', 'HomeTeam', 'Division']].rename(columns={'HomeTeam': 't'}),
                     m[['MatchDate', 'AwayTeam', 'Division']].rename(columns={'AwayTeam': 't'})])
    ost = ost.sort_values('MatchDate').groupby('t').agg(Division=('Division', 'last'), d=('MatchDate', 'max'))
    # 30.09.2026 (Raport 21:00): „San Luis Quillota” trafialo w „San Luis” — ten sam klub, ale zapis z bazy konczy sie
    # w 2018 (dzis „San Luis de Quillota”). Klub bez meczu od 2 lat nie jest kandydatem do meczu z dzisiejszej oferty.
    od = pd.to_datetime(ost.d).max() - pd.Timedelta(days=730)
    ost = ost[pd.to_datetime(ost.d) >= od].Division
    pula = {t for t in pool if t in ost.index and _ten_sam_kraj(_kraj_ligi(ost[t]) or '', kraj)}
    if not pula: return None
    import io, contextlib
    wyn = set()
    for n in nazwy:
        with contextlib.redirect_stdout(io.StringIO()):
            r = resolve(n, pula) or _przez_egzonim(n, pula)
        if r: wyn.add(r)
    return next(iter(wyn)) if len(wyn) == 1 else None


def _z_meczami(t, m):
    """Nazwa bez meczow w bazie (sam wpis clubelo, np. "Nott'm Forest"), a obok ten sam zapis po kluczu
    Z meczami ("Nottm Forest") — bierzemy ten z meczami. Klucz = te same litery i cyfry, wiec to ten sam klub."""
    if t is None or ((m.HomeTeam == t) | (m.AwayTeam == t)).any(): return t
    al = ALIASES_KLUBY.get(norm(t))   # "Lommel": sam wpis clubelo, mecze sa pod "Lommel SK"
    if al and ((m.HomeTeam == al) | (m.AwayTeam == al)).any():
        print(f'  "{t}" nie ma meczow w bazie (tylko wpis clubelo) — uzyto "{al}" (kluby.py / aliasy).')
        return al
    try:
        from kluby import klucz
    except ImportError:
        return t
    k = klucz(t)
    kand = sorted({n for n in pd.unique(pd.concat([m.HomeTeam, m.AwayTeam])) if klucz(n) == k})
    if len(kand) == 1:
        print(f'  "{t}" nie ma meczow w bazie — uzyto zapisu "{kand[0]}" (ten sam klub, inna pisownia).')
        return kand[0]
    return t


# 23.09.2026 (wyd. 24): STS pisze nazwy miast po polsku ("Real Madryt Castilla", "Austria Wiedeń",
# "Panathinaikos Ateny"), a baza ma zapis zrodlowy. Zamiana calych CZLONOW nazwy, i to dopiero wtedy,
# gdy nazwa oryginalna nie dala trafienia — dopasowanie po zamianie przechodzi przez te same
# zabezpieczenia resolve() (znaczniki rezerw/kobiet, kontrola kraju), wiec nie omija zadnej blokady.
from nazwy import EGZONIMY  # 29.09.2026: lista wspolna z sporty.py (nazwy.py)


def skladniki_zespolu(wagi, ldc, lel, lpi):
    """Skladniki zespolu v5n: (waga, lambdy) modeli z waga > 0; gdy zaden taki nie jest dostepny — to, co jest,
    z waga 1. Liczba skladnikow to liczba modeli, z ktorych NAPRAWDE policzono P (kontrola TYLKO JEDEN MODEL)."""
    return [(x, l) for x, l in zip(wagi, (ldc, lel, lpi)) if l is not None and x > 0] or \
           [(1.0, l) for l in (ldc, lel, lpi) if l is not None]


def _przez_egzonim(name, pool):
    czl = str(name).split()
    nowe = [EGZONIMY.get(norm(c), c) for c in czl]
    if nowe == czl: return None
    alt = ' '.join(nowe)
    r = resolve(alt, pool)
    if r: print(f'  UWAGA: "{name}" dopasowane po zamianie polskiej nazwy miasta -> "{alt}" -> {r}.')
    # 30.09.2026 (przeglad): resolve() zapisal skrot pod nazwa PO zamianie — club() szuka nazwy z oferty,
    # wiec „Atletico Turyn” -> Torino omijalo kontrole wspolnej ligi, a „Atletico Torino” ja przechodzilo
    if r and _SKROTY.get(alt) == r:
        _SKROTY[name] = r
        if alt in _SKROTY_OGOLNE: _SKROTY_OGOLNE.add(name)
    return r


# 29.09.2026 (proba generalna): clubelo (xgabora) przestal aktualizowac AUT, DEN, FIN, NOR, POL, ROM, RUS, SWE
# w 06.2025 — wartosc jest przepisywana z biezaca data, wiec „date” wyglada swiezo. Legia dostawala Elo 1491
# sprzed 15 miesiecy jako biezace (mecze roznych lig licza sie z samego Elo). Liczy sie data OSTATNIEJ ZMIANY
# wartosci; starsze niz MAKS_WIEK_ELO_DNI = brak Elo (200 dni: zimowa przerwa w Skandynawii ok. 4,5 mies.).
MAKS_WIEK_ELO_DNI = 200


def elo_aktualne(elo, dzis):
    """clubelo (club, country, elo, date) -> (ostatni wiersz na klub z kolumna zmiana = data ostatniej zmiany Elo,
    zbior klubow z Elo nieaktualnym)."""
    e = elo.sort_values(['club', 'date'])
    zm = e[e.groupby('club').elo.diff().fillna(1) != 0].groupby('club').date.max()
    ost = e.groupby('club').last()
    ost['zmiana'] = pd.to_datetime(zm.reindex(ost.index), errors='coerce')
    stare = set(ost.index[ost.zmiana < pd.Timestamp(dzis) - pd.Timedelta(days=MAKS_WIEK_ELO_DNI)])
    return ost, stare


_BAZA = {}   # 03.10.2026: tryb wsadowy (typuj_wsad.py) — baza wczytana RAZ na proces, kazdy mecz dostaje kopie


def _baza(con):
    """(mecze, clubelo) z kb.sqlite; w jednym procesie czytane raz na stan bazy (wczytanie = ok. 4 s z 7 s wywolania)."""
    k = stan_bazy()
    if k not in _BAZA:
        _BAZA.clear()
        _BAZA[k] = (pd.read_sql('select * from matches', con, parse_dates=['MatchDate']),
                    pd.read_sql('select club, country, elo, date from clubelo', con))
    m, e = _BAZA[k]
    return m.copy(), e.copy()


def club(home, away, kursy, live=None):
    con = db()
    m, _elo = _baza(con)
    elo, elo_stare = elo_aktualne(_elo, dt.date.today())
    pool = set(m.HomeTeam) | set(m.AwayTeam) | set(elo.index)
    wczytaj_warianty(con)
    jh, ja = _jawny_kraj(home, pool, m), _jawny_kraj(away, pool, m)
    h = jh or resolve(home, pool) or _przez_egzonim(home, pool)
    a = ja or resolve(away, pool) or _przez_egzonim(away, pool)
    h, a = _z_meczami(h, m), _z_meczami(a, m)
    jawne = (bool(jh) or bool(_PRZYR.match(str(home).strip())), bool(ja) or bool(_PRZYR.match(str(away).strip())))
    h, a = _wariant_kraju(h, a, m, pool, jawne)
    if h is not None and h == a:
        # patrz komentarz w sporty.py: dwie rozne nazwy z oferty wskazujace jeden wpis
        # w bazie daja mecz druzyny z sama soba i P okolo 50% dla obu stron — liczby
        # wygladaja normalnie, a sa bez wartosci.
        sys.exit(f'TA SAMA DRUZYNA PO OBU STRONACH: "{home}" i "{away}" wskazuja na "{h}" '
                 f'— analiza przerwana. Sprawdz nazwy w bazie przed dalsza praca.')
    print(f'Dopasowano: "{home}" → {h} | "{away}" → {a}')
    if (not h or not a) and '--kontynentalny' not in sys.argv:
        # 30.09.2026 (audyt oferty 01.10): „Cerro Porteno Asuncion” -> None, choc „Cerro Porteño” jest w bazie, a mecz
        # w terminarzu (Paragwaj). Nieznana nazwa szukana wsrod klubow kraju meczu z terminarza (jak wyzej).
        popr = _kraj_z_terminarza(home, away, h, a, None, None, pool, m)
        if popr: h, a = popr
    if not h or not a: sys.exit('Nie znaleziono drużyny w bazie — podaj inną pisownię.')
    today = pd.Timestamp(dt.date.today())
    ostrz = []
    div_of = lambda t: (m[(m.HomeTeam == t) | (m.AwayTeam == t)].sort_values('MatchDate').Division.iloc[-1]
                        if ((m.HomeTeam == t) | (m.AwayTeam == t)).any() else None)
    dh, da = div_of(h), div_of(a)
    # 22.09.2026, USTERKA U1: "Independiente Yumbo" (Kolumbia) -> Independiente (Argentyna), skrypt
    # wypisal "liga: ARG/COL" i policzyl model. W meczu LIGI KRAJOWEJ druzyny z dwoch krajow sa
    # niemozliwe — to znaczy, ze jedna z nazw trafila w cudzy klub. Po samym napisie nie da sie
    # tego wykryc ("Chievo Verona" -> "Chievo" ma ten sam ksztalt), po kraju ligi — tak.
    kh, ka = _kraj_ligi(dh), _kraj_ligi(da)
    if kh and ka and not _ten_sam_kraj(kh, ka) and '--kontynentalny' not in sys.argv:
        popr = _kraj_z_terminarza(home, away, h, a, kh, ka, pool, m)
        if popr:
            h, a = popr; dh, da = div_of(h), div_of(a); kh, ka = _kraj_ligi(dh), _kraj_ligi(da)
    if kh and ka and not _ten_sam_kraj(kh, ka) and '--kontynentalny' not in sys.argv:
        sys.exit(f'ROZNE KRAJE: "{home}" -> {h} ({dh}, {kh}) | "{away}" -> {a} ({da}, {ka}). '
                 f'W meczu ligi krajowej obie druzyny sa z jednego kraju — jedna z nazw zostala '
                 f'dopasowana do INNEGO klubu. Analiza przerwana, noga MNIEJ. '
                 f'Puchary kontynentalne (Libertadores, Liga Mistrzow...) i sparingi: dodaj --kontynentalny.')
    # 29.09.2026 (faza 3b, TERMINARZ): mecz z oferty szukany w terminarzu 365scores po OBU druzynach naraz
    # (zewn/terminarz_365.csv.gz, Apps Script). Terminarz podaje kraj rozgrywek — klub dopasowany do ligi
    # z innego kraju to pomylony klub. Brak pliku / meczu / kraj ogolny (World, Europe…) = bez kontroli.
    mt = None
    if '--kontynentalny' not in sys.argv:
        try:
            import terminarz as _tm
            mt = _tm.znajdz(home, away)
        except Exception as e:
            mt = None
            print(f'  UWAGA: kontrola terminarza pominieta ({type(e).__name__}: {e})')
        if mt:
            kt = norm(mt['kraj'])
            print(f'  TERMINARZ: {mt["gosp"]} – {mt["gosc"]} | {mt["kraj"]} | {mt["turniej"]}')
            if kt and kt not in _KRAJE_OGOLNE and _kanon_kraju(kt) not in _kraje_znane():
                print(f'  (kraj terminarza „{mt["kraj"]}” spoza listy krajow lig — bez kontroli kraju)')
            elif kt and kt not in _KRAJE_OGOLNE:
                zle = [(n, t, k) for n, t, k in ((home, h, kh), (away, a, ka)) if k and not _ten_sam_kraj(k, kt)]
                if zle:
                    popr = _kraj_z_terminarza(home, away, h, a, kh, ka, pool, m, mt)
                    if popr:
                        h, a = popr; dh, da = div_of(h), div_of(a); kh, ka = _kraj_ligi(dh), _kraj_ligi(da)
                        zle = []
                if zle:
                    sys.exit('NIEZGODNE Z TERMINARZEM: ' + '; '.join(f'"{n}" -> {t} (liga z kraju {k})' for n, t, k in zle)
                             + f', a mecz w terminarzu jest w kraju {mt["kraj"]} ({mt["turniej"]}). '
                             f'Nazwa trafila w INNY klub. Analiza przerwana, noga MNIEJ.')
    # 29.09.2026 (faza 3, dopasowanie LACZNE): gdy nazwa zgubila czlon rozrozniajacy (przypadek (c)
    # w _skrot_albo_nic: "Independiente Yumbo" -> "Independiente"), sam napis nie rozstrzyga — para z oferty
    # tak: dwa kluby jednego meczu ligowego graja w jednej lidze. Kontrola kraju (wyzej) nie lapie dwoch lig
    # tego samego kraju ani pucharu. Brak wspolnej ligi w 2 latach = noga MNIEJ (bezpieczny kierunek bledu).
    from nazwy import wspolna_liga
    skroty = [(n, t) for n, t in ((home, h), (away, a)) if _SKROTY.get(n) == t]
    if skroty and not wspolna_liga(m, h, a) and mt and (popr := skrot_z_terminarza(home, h, a, skroty, mt, pool, m)):
        h, a = popr; dh, da = div_of(h), div_of(a); kh, ka = _kraj_ligi(dh), _kraj_ligi(da)
        skroty = []
    if skroty and not wspolna_liga(m, h, a) and skrot_w_pucharze_ok(skroty, mt, (kh, ka)):
        print(f'  PUCHAR KRAJOWY ({mt["kraj"]}, {mt["turniej"]}): {h} i {a} bez wspolnej ligi — w pucharze to normalne; '
              'skrocone nazwy zgubily tylko czlony ogolne, kraj zgodny z terminarzem — dopasowanie przyjete.')
    elif skroty and not wspolna_liga(m, h, a):
        sys.exit('NIEPEWNE DOPASOWANIE: ' + '; '.join(f'"{n}" -> {t} (zgubiony czlon rozrozniajacy)' for n, t in skroty)
                 + f', a {h} i {a} nie graly w jednej lidze w ostatnich 2 latach — to prawdopodobnie INNY klub. '
                 f'Analiza przerwana, noga MNIEJ. Jesli to ten sam klub, dopisz pare do ALIASES (typuj.py).')
    # 22.09.2026, USTERKA U3: KROK 2b wymaga ostrzezenia dla ligi bez meczow z ostatnich 60 dni,
    # a skrypt go nie wypisywal. Liga PAR konczyla sie w bazie 2025-07-31, Sol de America mial ostatni
    # mecz 2024-06-06 (838 dni), a model podawal dla tego meczu rynki z dokladnoscia do dziesiatych
    # procenta. Stara historia daje sile druzyny sprzed roku — innego skladu, czasem innej ligi.
    # Wypisujemy OD RAZU, nie tylko w zbiorczej liscie na koncu, zeby nie zginelo pod tabela P.
    for t_, d_ in ((h, dh), (a, da)):
        ost_l = m.loc[m.Division == d_, 'MatchDate'].max() if d_ else pd.NaT
        ost_t = m.loc[(m.HomeTeam == t_) | (m.AwayTeam == t_), 'MatchDate'].max()
        for co, ost in ((f'LIGA {d_}', ost_l), (f'DRUZYNA {t_}', ost_t)):
            if pd.notna(ost) and (today - ost).days > 60:
                msg = (f'{co} NIESWIEZA: ostatni mecz w bazie {ost.date()} ({(today - ost).days} dni temu) '
                       f'— P to SZACUNEK: podawaj przedzial, nie dziesiate czesci procenta; max 1 noga na kupon.')
                if msg not in ostrz:
                    print('  ' + msg)
                    ostrz.append(msg)
    ldc, rho = None, -0.05
    if dh and dh == da:
        mdl = cached(f'dc_{dh}_{today.date()}', lambda: fit_dc(m[m.Division == dh], today))
        ldc = dc_lambdas(mdl, h, a); rho = mdl['rho'] if mdl else rho
        if mdl and min(mdl['cnt'].get(h, 0), mdl['cnt'].get(a, 0)) < 10:
            ldc = None; ostrz.append('Beniaminek / mało meczów w tej lidze (<10) — model DC pominięty.')
    else:
        ostrz.append(f'Różne ligi ({dh} vs {da}) — tylko model Elo.')
    glm = cached(f'glm_{today.date()}', lambda: fit_elo_glm(m))
    eh, ea = (elo.elo.get(h), elo.elo.get(a))
    for t_ in (h, a):
        if t_ in elo_stare:
            ostrz.append(f'Elo {t_} nieaktualne (ostatnia zmiana {elo.zmiana[t_]:%Y-%m-%d}, clubelo nie prowadzi juz tej ligi) — pominiete.')
    eh, ea = (None if h in elo_stare else eh), (None if a in elo_stare else ea)
    lel = elo_lambdas(glm, eh, ea, dh if dh == da else None) if eh and ea else None
    if lel is None: ostrz.append('Brak Elo jednej z drużyn.')
    if dh != da and lel is None:
        # 23.09.2026 (wyd. 24): Puchar Paragwaju, Fernando de la Mora (Division Intermedia) – Libertad
        # (Primera): bez Elo zostaje samo pi, a oceny pi z dwoch roznych lig nie sa porownywalne
        # (kazda liga ma wlasna srednia) — wyszlo Libertad 53% przy kursie 1,20. To nie jest
        # szacunek z szerokim przedzialem, tylko liczba bez znaczenia. Wypisujemy od razu i
        # oznaczamy jak szacunek; nogi z takiego meczu nie budujemy (instrukcja: puchary tylko papier).
        msg = (f'ROZNE LIGI BEZ ELO: {h} ({dh}) i {a} ({da}) — model nie zna roznicy poziomu lig, '
               f'P NIEPOROWNYWALNE; nie buduj nogi kuponu z tego meczu.')
        print('  ' + msg); ostrz.append(msg)
    lpi = None
    try:
        from pi import prepare, fit_pi_glm, pi_lambdas, gd_hat_for
        def _pi():
            mm, R, N = prepare(m.dropna(subset=['FTHome', 'FTAway']))
            return R, N, fit_pi_glm(mm[mm.MatchDate >= today - pd.Timedelta(days=365 * 4)])
        R, N, pg = cached(f'pi2_{today.date()}', _pi)   # pi2: 30.09.2026 srednie lig sciagane (pi.K_LIGA)
        if dh != da and lel is not None:
            # 30.09.2026 (przeglad): przy wagach Elo = 0 (ensemble_wagi.json) mecz dwoch lig liczyl sie z SAMEGO pi,
            # choc oceny pi z roznych lig sa nieporownywalne (patrz ROZNE LIGI BEZ ELO wyzej) — a wynik mial gwiazdki.
            ostrz.append('pi-ratings pominięte — różne ligi, oceny pi nieporównywalne.')
        elif min(N.get(h, 0), N.get(a, 0)) >= 10:
            lpi = pi_lambdas(pg, gd_hat_for(R, h, a), dh if dh == da else None)
        else: ostrz.append('pi-ratings: <10 meczów jednej z drużyn — pominięte.')
    except Exception as e:
        ostrz.append(f'pi-ratings niedostępne ({e}).')
    # v5p: odrzuć składnik z nierealną sumą goli (błąd danych ligi, np. Chacarita–Quilmes 0,68–0,16 z 20.09.2026)
    for nm_ in ('ldc', 'lel', 'lpi'):
        l_ = locals()[nm_]
        if l_ is not None and not (1.2 <= l_[0] + l_[1] <= 5.5):
            ostrz.append(f'{nm_[1:].upper()}: nierealna suma goli {l_[0] + l_[1]:.2f} — składnik pominięty (błąd danych ligi).')
            if nm_ == 'ldc': ldc = None
            elif nm_ == 'lel': lel = None
            else: lpi = None
    wp = os.path.join(HERE, 'ensemble_wagi.json')
    if os.path.exists(wp):
        wd, we, wpi = json.load(open(wp))['wagi_dc_elo_pi']
        parts = skladniki_zespolu((wd, we, wpi), ldc, lel, lpi)
        n_modeli = len(parts)          # 30.09.2026: liczy sie to, co WESZLO do zespolu (Elo ma wage 0)
    else:
        n_modeli = sum(x is not None for x in (ldc, lel, lpi))
    if n_modeli <= 1:
        ostrz.append('TYLKO JEDEN MODEL — traktuj P jak „szacunek” (max 1 noga na kupon, nie do K1).')
    if os.path.exists(wp):
        lam = tuple(float(np.exp(sum(x * np.log(l[k]) for x, l in parts) / sum(x for x, _ in parts))) for k in (0, 1)) if parts else None
        zrodla = '+'.join(n for n, (x, l) in zip(('DC', 'Elo', 'pi'), ((wd, ldc), (we, lel), (wpi, lpi))) if l is not None and (x > 0 or len(parts) and parts[0][0] == 1.0))
        print(f'Model v5n: zespół {zrodla} (wagi DC/Elo/pi = {wd}/{we}/{wpi})')
    else:
        W = float(open(os.path.join(HERE, 'blend_weight.txt')).read()) if os.path.exists(os.path.join(HERE, 'blend_weight.txt')) else 0.5
        lam = blend(ldc, lel, W)
    if lam is None: sys.exit('Za mało danych do modelu.')
    if live:
        mn, sc, rh_, ra_ = live
        gh, ga = [int(x) for x in sc.split(':')]
        lm = live_markets(lam[0], lam[1], mn, gh, ga, rh_, ra_, rho)
        print(f'\n=== NA ŻYWO {h} {gh}:{ga} {a} | {mn}. min | czerwone {rh_}/{ra_} ===')
        print(f'Przedmeczowe λ {lam[0]:.2f}–{lam[1]:.2f} → pozostały czas λ {lm["λ_reszta_gosp"]:.2f}–{lm["λ_reszta_gość"]:.2f}')
        for k, p in sorted(((k, v) for k, v in lm.items() if not k.startswith('λ')), key=lambda x: -x[1]):
            print(f'{k:<22}{p:7.1%}' + (' ★' if p >= 0.75 else ''))
        print('(walidacja w przerwie na 6000 meczach 2025/26: P 75% → 76% trafień, 84% → 83%, Brier 0.159)')
        value([(k, v, v) for k, v in lm.items()], kursy)
        return
    mk = markets(*lam, rho)
    kr_p = os.path.join(HERE, 'korekta_rynkow_v5n.csv')
    if os.path.exists(kr_p) and os.path.exists(os.path.join(HERE, 'ensemble_wagi.json')):
        KR = pd.read_csv(kr_p); cal = {}
        calibrate_v5n = lambda k, p: kalibruj_v5n(KR, k, p)
    else:
        calibrate_v5n = None
        cal = load_calibration(os.path.join(HERE, 'kalibracja_mapa.csv'))
    print(f'\n=== {h} – {a} | liga: {dh}/{da} | Elo {eh and round(eh)} vs {ea and round(ea)} ===')
    print(f'Oczekiwane gole: {lam[0]:.2f} – {lam[1]:.2f} (DC: {ldc and tuple(round(x, 2) for x in ldc)}, Elo: {lel and tuple(round(x, 2) for x in lel)}, pi: {lpi and tuple(round(x, 2) for x in lpi)})')
    print('Najczęstsze wyniki:', mk['wyniki'])
    kor = pd.read_csv(os.path.join(HERE, 'korekta_wlasna.csv')) if os.path.exists(os.path.join(HERE, 'korekta_wlasna.csv')) else None
    rows = []
    for k in KEY_MARKETS:
        p = mk[k]; pc = calibrate_v5n(k, p) if calibrate_v5n else calibrate(cal, k, p)
        if kor is not None:  # uczenie na własnych rozliczonych typach
            pc = korekta_wlasna(pc, kor[kor.rynek == k])
        rows.append((k, p, pc))
    print('\nRynek            P_model  P_skalibr.' + ('   (v5n: korekta per rynek z backtestu; „poniżej” już −4 pp — nie odejmuj drugi raz)' if calibrate_v5n else ''))
    # 23.09.2026, USTERKA U4: przy danych nieswiezych albo jednym modelu tabela nie moze udawac
    # pewnosci. Nacional Potosi - Real Potosi (22.09): obie druzyny NIESWIEZE (370 i 1738 dni), model
    # tylko z pi, a wydruk pokazywal 1X 98,6% z gwiazdka. Wtedy: przedzial zamiast dziesiatych procenta
    # i bez gwiazdek. Liczby do EV (value) zostaja jak byly — to czesc obliczeniowa, nie komunikat.
    szac = [o for o in ostrz if 'NIESWIEZA' in o or 'TYLKO JEDEN MODEL' in o or 'ROZNE LIGI BEZ ELO' in o]
    if szac:
        print('SZACUNEK — P JAKO PRZEDZIAL, BEZ ★ (' + '; '.join(o.split(':')[0] for o in szac) + ')')
    for k, p, pc in sorted(rows, key=lambda r: -r[2]):
        if szac:
            lo, hi = max(pc - 0.10, 0.0), min(pc + 0.10, 0.95)
            print(f'{k:<18}{p:7.1%}  ok. {lo:.0%}–{hi:.0%}')
        else:
            flag = ' ★' if pc >= 0.75 else ''
            print(f'{k:<18}{p:7.1%}  {pc:7.1%}{flag}')
    for t, lbl in ((h, 'GOSP'), (a, 'GOŚĆ')):
        s = team_stats(m, t)
        if s:
            print(f'\n[{lbl}] {t}: ost.10 {s["forma"]} ({s["pkt"]} pkt, {s["gole"]}) | O1.5 {s["O15"]:.0%} O2.5 {s["O25"]:.0%} '
                  f'U3.5 {s["U35"]:.0%} BTTS {s["BTTS"]:.0%} CS {s["CS"]:.0%} bez gola {s["FTS"]:.0%} | ostatni mecz w bazie {s["ostatni"]}')
            if 'rożne_za' in s:
                print(f'   rożne {s["rożne_za"]:.1f}/{s["rożne_przeciw"]:.1f} | żółte {s["żółte"]:.1f} | strzały celne {s["strzały_celne"]:.1f}')
            for x in s['mecze']: print('   ', x)
            if (today - pd.Timestamp(s['ostatni'])).days > 60:
                ostrz.append(f'{t}: ostatni mecz w bazie {s["ostatni"]} — dane nieaktualne, dopisz wyniki do delta.')
    since = today - pd.Timedelta(days=400)
    vh, va = venue_stats(m, h, 'dom', since), venue_stats(m, a, 'wyjazd', since)
    if vh: print(f'\n{h} u siebie (13 mies., n={vh["n"]}): W{vh["W"]:.0%} D{vh["D"]:.0%} L{vh["L"]:.0%}, gole {vh["gf"]:.2f}:{vh["ga"]:.2f}, O1.5 {vh["O15"]:.0%}, U3.5 {vh["U35"]:.0%}, BTTS {vh["BTTS"]:.0%}')
    if va: print(f'{a} na wyjeździe (n={va["n"]}): W{va["W"]:.0%} D{va["D"]:.0%} L{va["L"]:.0%}, gole {va["gf"]:.2f}:{va["ga"]:.2f}, O1.5 {va["O15"]:.0%}, U3.5 {va["U35"]:.0%}, BTTS {va["BTTS"]:.0%}')
    hh = m[((m.HomeTeam == h) & (m.AwayTeam == a)) | ((m.HomeTeam == a) & (m.AwayTeam == h))].sort_values('MatchDate').tail(8)
    if len(hh):
        print('\nH2H (ost. 8):', ' | '.join(f"{r.MatchDate.date()} {r.HomeTeam} {int(r.FTHome)}:{int(r.FTAway)} {r.AwayTeam}" for r in hh.itertuples()))
    _mm = m[(m.HomeTeam.isin([h, a]) | m.AwayTeam.isin([h, a])) & m.FTHome.notna() & m.FTAway.notna()].sort_values('MatchDate')
    global LIGA_BEZ_TESTU
    LIGA_BEZ_TESTU = liga_bez_testu(m, {dh, da})
    if LIGA_BEZ_TESTU: print(f'\nLIGA BEZ TESTU: {LIGA_BEZ_TESTU} — P informacyjnie, ZADNA noga z tego meczu NIE idzie na kupon.')
    dz = drugie_zrodlo([(r.MatchDate, r.HomeTeam, r.AwayTeam, int(r.FTHome), int(r.FTAway)) for r in _mm.itertuples()], h, a, rows)
    value(rows, kursy, dz, mecz=f'{home} - {away}', szacunek=bool(szac), polski='poland' in (kh, ka))
    for a_, b_, k_ in PARY:
        para(rows, lam, rho, a_, b_, k_, dz, mecz=f'{home} - {away}', szacunek=bool(szac), polski='poland' in (kh, ka))
    if ostrz: print('\nOSTRZEŻENIA:', *ostrz, sep='\n - ')
    print('\nUwaga: model nie zna składów, kontuzji i motywacji z dnia meczu — sprawdź je osobno (korekta maks. ±6 pp).')


# 24.09.2026 (Poprawka 48, wymog uzytkownika: „Musisz zawsze miec drugie zrodlo danych”).
# Drugie zrodlo = FORMA z ostatnich meczow obu druzyn, liczona wprost z wynikow (czestosc zdarzenia),
# niezalezna od modelu (Elo/DC/pi). Noga wchodzi na kupon TYLKO gdy oba zrodla sa zgodne (roznica <= 10 pp)
# i kazda druzyna ma >= 6 meczow; do kuponu idzie MNIEJSZE z dwoch P (ostroznie). Wygladzanie (k+1)/(n+2),
# zeby 6/6 nie dawalo 100%. To NIE zastepuje sprawdzenia nieobecnosci w sieci — to drugi, liczbowy filtr.
# 03.10.2026 (naprawa po Raportach 15:00 i 18:00): A1(a) mowi, ze druzyna bez meczu od > 60 dni to SZACUNEK,
# ale "drugie zrodlo — forma" liczylo sie z DOKLADNIE TYCH SAMYCH meczow, z ktorych liczy model. Przy druzynie
# nieswiezej oba "zrodla" powtarzaly ten sam przestarzaly obraz i zawsze wychodzilo ZGODNE — A9 bylo spelnione
# formalnie, nie merytorycznie. Przyklady z 03.10: Lusitanos (ostatni mecz 2026-05-16, 140 dni: model X2 69,3%,
# forma 70,8% -> ZGODNE -> NOGA DOPUSZCZONA, EV +12,9%, przy P rynku 48,4%) i Salisbury (ostatni mecz 2014-04-26,
# 4543 dni: X2 66,2%, EV +19,5%). Od teraz nieswieza druzyna = BRAK DRUGIEGO ZRODLA.
MAX_WIEK_FORMY_DNI = 60


def _ostatni_mecz(w, t):
    """Data ostatniego meczu druzyny t w zbiorze w (None, gdy brak)."""
    x = [r[0] for r in w if r[1] == t or r[2] == t]
    return max(x) if x else None


def _na_date(d):
    """Normalizuje date meczu (datetime / date / tekst) do datetime.date albo None."""
    import datetime as _dt
    if d is None: return None
    if isinstance(d, _dt.datetime): return d.date()
    if isinstance(d, _dt.date): return d
    try: return _dt.date.fromisoformat(str(d)[:10])
    except Exception:
        try: return d.to_pydatetime().date()        # pandas.Timestamp
        except Exception: return None


def _forma_druzyny(w, t, n=10):
    x = [r for r in w if r[1] == t or r[2] == t][-n:]
    out = []
    for d, hh, aa, gh, ga in x:
        gz, gs = (gh, ga) if hh == t else (ga, gh)
        out.append((gz, gs))
    return out


def drugie_zrodlo(w, h, a, rows, n=10):
    """w: lista (data, gosp, gosc, gole_g, gole_a) posortowana rosnaco po dacie."""
    fh, fa = _forma_druzyny(w, h, n), _forma_druzyny(w, a, n)
    print(f'\nDRUGIE ZRODLO — forma z ostatnich meczow (N {len(fh)}/{len(fa)}), niezalezna od modelu:')
    if min(len(fh), len(fa)) < 6:
        print('  BRAK DRUGIEGO ZRODLA (mniej niz 6 meczow jednej z druzyn) — ZADNA noga z tego meczu NIE idzie na kupon.')
        return {}
    # 03.10.2026: niezaleznosc drugiego zrodla wymaga, zeby forma byla ze SWIEZYCH meczow. Forma z tego samego
    # przestarzalego okna co model nie jest druga opinia (A1c), tylko powtorzeniem pierwszej.
    import datetime as _dt
    dzis = _dt.date.today()
    for t in (h, a):
        od = _na_date(_ostatni_mecz(w, t))
        if od is None: continue
        wiek = (dzis - od).days
        if wiek > MAX_WIEK_FORMY_DNI:
            print(f'  BRAK DRUGIEGO ZRODLA: forma druzyny "{t}" liczy sie z meczow sprzed {wiek} dni '
                  f'(ostatni {od}, prog {MAX_WIEK_FORMY_DNI} dni z A1a) — to TE SAME nieswieze dane, '
                  f'z ktorych liczy model, wiec nie jest zrodlem niezaleznym (A9 + A1c).')
            print('  ZADNA noga z tego meczu NIE idzie na kupon.')
            return {}
    r = lambda k, m: (k + 1) / (m + 2)
    def cz(f, war): return sum(1 for g in f if war(*g)), len(f)
    wh, nh = cz(fh, lambda z, s: z > s); dh, _ = cz(fh, lambda z, s: z == s); lh, _ = cz(fh, lambda z, s: z < s)
    wa, na = cz(fa, lambda z, s: z > s); da, _ = cz(fa, lambda z, s: z == s); la, _ = cz(fa, lambda z, s: z < s)
    sr = lambda war: (r(*cz(fh, war)) + r(*cz(fa, war))) / 2
    P = {'1': (r(wh, nh) + r(la, na)) / 2, '2': (r(wa, na) + r(lh, nh)) / 2,
         'X': (r(dh, nh) + r(da, na)) / 2,
         '1X': (r(wh + dh, nh) + r(la + da, na)) / 2, 'X2': (r(wa + da, na) + r(lh + dh, nh)) / 2,
         '12': 1 - (r(dh, nh) + r(da, na)) / 2,
         'O0.5': sr(lambda z, s: z + s >= 1), 'O1.5': sr(lambda z, s: z + s >= 2), 'O2.5': sr(lambda z, s: z + s >= 3),
         'U2.5': sr(lambda z, s: z + s <= 2), 'U3.5': sr(lambda z, s: z + s <= 3), 'U4.5': sr(lambda z, s: z + s <= 4),
         'BTTS_tak': sr(lambda z, s: z > 0 and s > 0), 'BTTS_nie': sr(lambda z, s: z == 0 or s == 0),
         'gosp_O0.5': (r(*cz(fh, lambda z, s: z > 0)) + r(*cz(fa, lambda z, s: s > 0))) / 2,
         'gość_O0.5': (r(*cz(fa, lambda z, s: z > 0)) + r(*cz(fh, lambda z, s: s > 0))) / 2}
    # 29.09.2026 (Poprawka 58, docs/BACKTEST_P48.md): zgodnosc zostaje OBOWIAZKOWA, ale P do kuponu = P modelu,
    # nie mniejsze z dwoch. Backtest 54 699 nog (P >= 70%, 01-09.2026): min(P) srednio 77,1% przy trafnosci
    # 82,2% (P modelu 80,4%), gorszy Brier (0,1441 vs 0,1411) i log loss — zanizal EV o ok. 5 pp.
    wynik = {}
    print(f'  {"Rynek":<12}{"P_model":>8}{"P_forma":>9}  werdykt')
    for k, p, pc in sorted(rows, key=lambda x: -x[2]):
        if k not in P or pc < 0.60: continue
        pf = P[k]; ok = abs(pc - pf) <= 0.10
        wynik[k] = pc if ok else None
        print(f'  {k:<12}{pc:8.1%}{pf:9.1%}  ' + (f'ZGODNE → P do kuponu {pc:.1%} (P modelu)' if ok
              else f'ROZBIEZNE ({(pf - pc) * 100:+.0f} pp) → NIE NA KUPON'))
    print('  Zasada (Poprawki 48 i 58): na kupon tylko ZGODNE; P do kuponu = P modelu; do tego sprawdz nieobecnosci w sieci.')
    return wynik


def ev_kelly(p, o):
    """EV po podatku 12% i pelny Kelly (0, gdy kurs po podatku nie przekracza 1)."""
    ev = p * o * TAX - 1
    return ev, (max(0.0, ev / (o * TAX - 1)) if o * TAX > 1 else 0.0)


# 03.10.2026: FILTR MODEL-RYNEK (KROK 6.4) mieszka w rynek.py — wspolny z sporty.py.
# Nazwy reeksportowane, bo testy i starsze wywolania siegaja po typuj.p_rynku / typuj.MAX_ROZBIEZNOSC_RYNEK.
from rynek import MAX_ROZBIEZNOSC_RYNEK, filtr_model_rynek, p_rynku, kod_rynku, p_kuponu_wg_rynku    # noqa: F401

__all__ = ['MAX_ROZBIEZNOSC_RYNEK', 'filtr_model_rynek', 'p_rynku']


# 29.09.2026 (Poprawka 58.5, docs/BACKTEST_P48.md): rynki, na ktorych model przy P >= 70% mocno ZAWYZA.
# Backtest walk-forward 01-09.2026 (po korektach, jak w kuponie): U2.5 n=64 P 74,5% -> trafnosc 53,1%;
# BTTS_nie n=60 79,7% -> 51,7%; BTTS_tak n=8 83,3% -> 50,0%; "2" n=69 75,7% -> 65,2%. Wlasnie takie nogi
# wygladaja na wartosc (wysokie P, wysoki kurs). Do czasu ponownego backtestu: NIE NA KUPON przy P >= 70%.
RYNKI_ZAWYZONE_P70 = {'U2.5': (64, 0.745, 0.531), 'BTTS_nie': (60, 0.797, 0.517),
                      'BTTS_tak': (8, 0.833, 0.500), '2': (69, 0.757, 0.652)}


LIGA_BEZ_TESTU = None   # 03.10.2026: powod blokady meczu z ligi bez historii/testu (ustawia main po rozpoznaniu lig)
MIN_MECZOW_NA_KUPON = 60


def liga_bez_testu(m, ligi):
    """03.10.2026: ligi dolaczone do bazy dla rozpoznawania nazw (kobiety, mlodziez, rezerwy, amatorzy, ligi z < 60 meczami)
    licza P, ale NIE ida na kupon, dopoki nie maja historii i testu wstecznego. Zwraca powod albo None."""
    import zewn
    for l in ligi:
        if not isinstance(l, str): continue
        if '|' in l and zewn.INNE_DRUZYNY.search(l.split('|', 1)[1]):
            return f'liga {l} (kobiety/mlodziez/rezerwy/amatorzy) bez testu wstecznego'
        n = int((m.Division == l).sum())
        # 03.10.2026: liga z Flashscore bez slowa „Women/U19” w nazwie („Japan | WE League”), ale z druzynami „X W”
        if n and 'HomeTeam' in m.columns:
            zn = [_znaczniki(x) for x in m.HomeTeam[m.Division == l]]
            if sum(any(z == 'kobiety' or z == 'mlodziez' or re.match(r'u\d+$', z) for z in t) for t in zn) > n / 2:
                return f'liga {l} (druzyny kobiet/mlodziezowe) bez testu wstecznego'
        if n < MIN_MECZOW_NA_KUPON:
            return f'liga {l}: {n} meczow w bazie (< {MIN_MECZOW_NA_KUPON}) — za malo historii'
    return None


def werdykt_nogi(k, dz):
    """P do kuponu wg Poprawek 48/58 i powod, gdy noga odpada.
    dz = wynik drugie_zrodlo(): {} (brak drugiego zrodla), {rynek: P | None}."""
    if LIGA_BEZ_TESTU: return None, f'LIGA BEZ TESTU — {LIGA_BEZ_TESTU}'
    if dz is None: return None, 'drugie zrodlo nie liczone'
    if not dz: return None, 'BRAK DRUGIEGO ZRODLA'
    if k not in dz: return None, 'rynek bez drugiego zrodla'
    if dz[k] is None: return None, 'ROZBIEZNE zrodla'
    if k in RYNKI_ZAWYZONE_P70 and dz[k] >= 0.70:
        n, p, t = RYNKI_ZAWYZONE_P70[k]
        return None, f'rynek {k} przy P >= 70% ZAWYZONY w backtescie (n={n}: P {p:.0%} -> trafnosc {t:.0%}; Poprawka 58.5)'
    return dz[k], None


NOGI_PLIK = None   # --nogi PLIK: nogi DOPUSZCZONE dopisywane do CSV dla kupon.py (faza 4)


def _dopisz_noge(mecz, rynek, p, kurs, szacunek, polski):
    """Wiersz dla kupon.py. marza i kryteria (A4.3) zostaja puste — uzupelnia przebieg; bez kryteriow kupon.py
    daje poziom D, czyli PAPIEROWY (bezpieczny kierunek)."""
    import csv
    nowy = not os.path.exists(NOGI_PLIK)
    with open(NOGI_PLIK, 'a', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        if nowy: w.writerow(['mecz', 'rynek', 'p', 'kurs', 'szacunek', 'polski', 'marza', 'kryteria'])
        w.writerow([mecz, rynek, f'{p:.4f}', kurs, int(szacunek), int(polski), '', ''])


def value(rows, kursy, dz=None, mecz=None, szacunek=False, polski=False):
    """29.09.2026: wczesniej wynik drugie_zrodlo() byl wyrzucany — bramka z Poprawki 48 istniala tylko jako tekst
    do przeczytania. Teraz: noga bez zgodnego drugiego zrodla ma wprost werdykt NIE NA KUPON, a EV i Kelly do
    kuponu licza sie z P po bramce (od Poprawki 58: P modelu, gdy zrodla zgodne)."""
    if not kursy: return
    d = {k: pc for k, p, pc in rows}
    print('\nWARTOŚĆ (kurs użyty dopiero po wyliczeniu P; podatek 12%):')
    for k, o in kursy.items():
        if k not in d:   # 05.10.2026: literowka w kodzie rynku nie moze przejsc po cichu
            print(f'  {k}: brak rynku — UWAGA: model nie zna kodu „{k}” (sprawdz zapis; znane: {", ".join(sorted(d))})'); continue
        p = d[k]; ev, kelly = ev_kelly(p, o)
        print(f'  {k} @ {o}: P={p:.1%}, kurs sprawiedliwy={1 / p / TAX:.2f}, EV={ev:+.1%}, ¼ Kelly={kelly / 4:.1%} bankrollu'
              + ('  ✔ wartość' if ev > 0 else '  ✘ brak wartości'))
        pk, powod = werdykt_nogi(k, dz)
        if powod:
            print(f'      → NIE NA KUPON: {powod} (Poprawka 48)')
        elif (pow_r := filtr_model_rynek(k, pk, kursy)):
            print(f'      → NIE NA KUPON: {pow_r}')
        else:
            pk, uw = p_kuponu_wg_rynku(k, pk, kursy)   # 06.10.2026: U3.5/O3.5 — mniejsze z modelu i rynku
            if uw: print(f'      → {uw}')
            evk, kk = ev_kelly(pk, o)
            print(f'      → P do kuponu {pk:.1%}: EV={evk:+.1%}, ¼ Kelly={kk / 4:.1%}'
                  + ('  ✔ NOGA DOPUSZCZONA' if evk > 0 else '  ✘ NIE NA KUPON: EV ≤ 0 po bramce'))
            if evk > 0 and NOGI_PLIK and mecz:
                _dopisz_noge(mecz, k, pk, o, szacunek, polski)
                print(f'      (zapisano do {NOGI_PLIK} — uzupelnij marza i kryteria A4.3 przed kupon.py)')


PARY = []   # --para A+B[=kurs Buildera]


def para(rows, lam, rho, a, b, kurs, dz, mecz=None, szacunek=False, polski=False):
    """29.09.2026 (Poprawka 59, A5 pkt 1 i 5): para z jednego meczu na zwyklym AKO jest w STS niedozwolona
    (liczy sie tylko wyzszy kurs, reszta po 1,0), wiec za pieniadze tylko przez Bet Builder, ktorego kurs NIE jest
    iloczynem kursow. Laczne P z siatki wynikow, skorygowane w dol tak jak nogi (korekta rynkow i bramka 48/58);
    kazda noga musi sama przejsc werdykt_nogi. EV wylacznie z kursu Buildera."""
    d = {k: (p, pc) for k, p, pc in rows}
    print(f'\nPARA {a} + {b} (jeden mecz — tylko Bet Builder; zwykly AKO niedozwolony, Poprawka 59):')
    if a == b or a not in d or b not in d:
        print('  → NIE NA KUPON: nieznany rynek albo ten sam rynek dwa razy'); return
    pj = p_pary(lam[0], lam[1], rho, a, b)
    if pj is None:
        print('  → NIE NA KUPON: rynek spoza siatki wyniku koncowego (DNB, HT, pierwszy gol) — brak lacznego P'); return
    (pa, pca), (pb, pcb) = d[a], d[b]
    naiw = pca * pcb
    powody = []
    ka, ra = werdykt_nogi(a, dz); kb, rb = werdykt_nogi(b, dz)
    if ra: powody.append(f'{a}: {ra}')
    if rb: powody.append(f'{b}: {rb}')
    ka, kb = ka if ka is not None else pca, kb if kb is not None else pcb
    pk = min(pj * min(1.0, ka / pa if pa else 0) * min(1.0, kb / pb if pb else 0), ka, kb)
    if pk < 1e-6: powody.append('laczne P = 0 (rynki wykluczaja sie)')
    print(f'  P1 {a} {ka:.1%} | P2 {b} {kb:.1%} | iloczyn naiwny {naiw:.1%} | P z siatki {pj:.1%} (model) '
          f'→ P do kuponu {pk:.1%} ({(pk - naiw) * 100:+.1f} pp vs iloczyn)')
    if pk >= 1e-6: print(f'  kurs sprawiedliwy po podatku {1 / pk / TAX:.2f}')
    if kurs is None:
        powody.append('brak kursu Buildera (--para A+B=KURS z aplikacji)')
    else:
        ev, kelly = ev_kelly(pk, kurs)
        print(f'  kurs Buildera {kurs:.2f}: EV={ev:+.1%}, ¼ Kelly={kelly / 4:.1%}')
        if ev <= 0: powody.append('EV ≤ 0 z kursu Buildera')
    if powody:
        print('  → NIE NA KUPON: ' + '; '.join(powody)); return
    print('  ✔ PARA DOPUSZCZONA (jedna noga kuponu; maks. 2 nogi z meczu — A5 pkt 4)')
    if NOGI_PLIK and mecz:
        _dopisz_noge(mecz, f'{a}+{b}', pk, kurs, szacunek, polski)
        print(f'  (zapisano do {NOGI_PLIK} jako jedna noga — uzupelnij marza i kryteria A4.3 przed kupon.py)')


# ---------------- reprezentacje ----------------
K_T = [('FIFA World Cup qualification', 40), ('FIFA World Cup', 60), ('UEFA Euro qualification', 40), ('UEFA Euro', 50),
       ('Nations League', 40), ('Copa América', 50), ('African Cup of Nations', 50), ('AFC Asian Cup', 50),
       ('Gold Cup', 50), ('Friendly', 20)]


def intl_elo(df):
    R = {}; rows = []
    for r in df.itertuples():
        k = next((v for t, v in K_T if t in r.tournament), 30)
        rh, ra = R.get(r.home_team, 1500.0), R.get(r.away_team, 1500.0)
        adv = 0 if r.neutral in (True, 'TRUE', 1) else 100
        rows.append((rh, ra, adv))
        e = 1 / (1 + 10 ** (-(rh + adv - ra) / 400)); gd = abs(r.home_score - r.away_score)
        g = 1 if gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8)
        s = 1 if r.home_score > r.away_score else (0.5 if r.home_score == r.away_score else 0)
        R[r.home_team] = rh + k * g * (s - e); R[r.away_team] = ra - k * g * (s - e)
    return R, rows


def intl(home, away, neutral, kursy):
    df = pd.read_sql('select * from intl order by date', db())
    R, pre = cached(f'intl_{dt.date.today()}', lambda: intl_elo(df))
    h, a = resolve(home, set(R)), resolve(away, set(R))
    if h is not None and h == a:
        # patrz komentarz w sporty.py: dwie rozne nazwy z oferty wskazujace jeden wpis
        # w bazie daja mecz druzyny z sama soba i P okolo 50% dla obu stron — liczby
        # wygladaja normalnie, a sa bez wartosci.
        sys.exit(f'TA SAMA DRUZYNA PO OBU STRONACH: "{home}" i "{away}" wskazuja na "{h}" '
                 f'— analiza przerwana. Sprawdz nazwy w bazie przed dalsza praca.')
    print(f'Dopasowano: {h} | {a}')
    if h is None or a is None:
        # Poprawka 42: wczesniej KeyError: None (Traceback) — teraz jak w meczach klubowych.
        brak = [n for n, r in ((home, h), (away, a)) if r is None]
        sys.exit(f'NIE ZNALEZIONO reprezentacji: {", ".join(repr(x) for x in brak)} — noga MNIEJ. '
                 f'Dopisz polska nazwe do _KRAJE_PL tylko, gdy druzyna jest w tabeli intl.')
    df = df.assign(rh=[p[0] for p in pre], ra=[p[1] for p in pre], adv=[p[2] for p in pre])
    d = df[df.date >= '2010-01-01']
    x = ((d.rh + d.adv - d.ra) / 100).values

    def fit(y, sgn):
        X = np.c_[np.ones_like(x), sgn * x]; b = np.zeros(2)
        for _ in range(30):
            lam = np.exp(X @ b); b += np.linalg.solve((X * lam[:, None]).T @ X, X.T @ (y - lam))
        return b
    bh, ba = fit(d.home_score.values.astype(float), 1), fit(d.away_score.values.astype(float), -1)
    xx = (R[h] + (0 if neutral else 100) - R[a]) / 100
    lh, la = float(np.exp(bh[0] + bh[1] * xx)), float(np.exp(ba[0] - ba[1] * xx))
    mk = markets(lh, la, -0.05)
    print(f'\n=== {h} – {a} | Elo {R[h]:.0f} vs {R[a]:.0f} {"(neutralny)" if neutral else ""} ===')
    print(f'Oczekiwane gole: {lh:.2f} – {la:.2f} | wyniki: {mk["wyniki"]}')
    # 23.09.2026 (wyd. 24), USTERKA z przebiegu 20:00 (Aruba – Antigua, Turks i Caicos – Montserrat):
    # (1) sciezka reprezentacji nie miala kontroli swiezosci — Antigua (ostatni mecz 18.11.2025)
    #     i Montserrat (10.06.2025) dostawaly gwiazdki jak druzyny z pelna forma. Reprezentacje graja
    #     oknami FIFA, wiec prog jest dluzszy niz 60 dni u klubow: 270 dni = trzy okna bez meczu;
    # (2) rynki „poniżej” nie mialy −4 pp (sciezka klubowa ma je w P_skalibr.) — ta sama regula tu.
    today = pd.Timestamp(dt.date.today()); szac = []
    for t in (h, a):
        ost = pd.to_datetime(df.loc[(df.home_team == t) | (df.away_team == t), 'date']).max()
        if pd.notna(ost) and (today - ost).days > 270:
            szac.append(f'REPREZENTACJA {t} NIESWIEZA: ostatni mecz w bazie {ost.date()} '
                        f'({(today - ost).days} dni temu)')
    rows = [(k, mk[k], max(mk[k] - 0.04, 0.0) if k.startswith('U') and mk[k] >= 0.5 else mk[k]) for k in KEY_MARKETS]
    for x in szac: print('  ' + x + ' — P to SZACUNEK: podawaj przedzial; max 1 noga na kupon.')
    print('\nRynek            P_model  P_skalibr.   („poniżej” już −4 pp — nie odejmuj drugi raz)')
    if szac: print('SZACUNEK — P JAKO PRZEDZIAL, BEZ ★ (' + '; '.join(x.split(':')[0] for x in szac) + ')')
    for k, p, pc in sorted(rows, key=lambda r: -r[2]):
        if szac:
            print(f'{k:<18}{p:7.1%}  ok. {max(pc - 0.10, 0.0):.0%}–{min(pc + 0.10, 0.95):.0%}')
        else:
            print(f'{k:<18}{p:7.1%}  {pc:7.1%}' + (' ★' if pc >= 0.75 else ''))
    for t in (h, a):
        t10 = df[(df.home_team == t) | (df.away_team == t)].tail(6)
        print(f'\n{t} ost. 6:', ' | '.join(f'{r.date} {r.home_team} {int(r.home_score)}:{int(r.away_score)} {r.away_team} ({r.tournament})' for r in t10.itertuples()))
    hh = df[((df.home_team == h) & (df.away_team == a)) | ((df.home_team == a) & (df.away_team == h))].tail(6)
    if len(hh): print('\nH2H:', ' | '.join(f'{r.date} {r.home_team} {int(r.home_score)}:{int(r.away_score)} {r.away_team}' for r in hh.itertuples()))
    dz = drugie_zrodlo([(r.date, r.home_team, r.away_team, int(r.home_score), int(r.away_score)) for r in df.itertuples()
                        if pd.notna(r.home_score) and pd.notna(r.away_score)], h, a, rows)
    value(rows, kursy, dz, mecz=f'{home} - {away}', szacunek=bool(szac), polski='Poland' in (h, a))
    for a_, b_, k_ in PARY:
        para(rows, (lh, la), -0.05, a_, b_, k_, dz, mecz=f'{home} - {away}', szacunek=bool(szac), polski='Poland' in (h, a))


# 29.09.2026 (faza 3b): aliasy z pliku danych aliasy.csv (modul=typuj) — na koncu, zeby wpisy w kodzie wygrywaly
from nazwy import aliasy_z_pliku as _aliasy_z_pliku
import nazwy as _nazwy
_aliasy_z_pliku('typuj', norm, ALIASES)
_aliasy_z_pliku('typuj', norm, ALIASES, _nazwy.ALIASY_AUTO_CSV)   # dopasuj.py auto (03.10.2026)

def main(argv):
    """Jedno wywolanie typuj.py (argumenty jak w wierszu polecen). Wolane tez przez typuj_wsad.py dla wielu meczow."""
    global NOGI_PLIK, LIGA_BEZ_TESTU
    NOGI_PLIK, LIGA_BEZ_TESTU = None, None
    PARY.clear()
    args = list(argv)
    kursy = {}
    if '--nogi' in args:
        i = args.index('--nogi'); NOGI_PLIK = args[i + 1]; del args[i:i + 2]
    while '--para' in args:
        i = args.index('--para'); x = args[i + 1]; del args[i:i + 2]
        ab, _, k = x.partition('='); a_, _, b_ = ab.partition('+')
        PARY.append((a_, b_, float(k.replace(',', '.')) if k else None))
    while '--kurs' in args:
        i = args.index('--kurs'); k, v = args[i + 1].split('='); kursy[kod_rynku(k)] = float(v.replace(',', '.')); del args[i:i + 2]
    live = None
    if '--live' in args:
        i = args.index('--live'); live = (int(args[i + 1]), args[i + 2], args.count('--czerwona-gosp'), args.count('--czerwona-gosc'))
        del args[i:i + 3]
    flags = {x for x in args if x.startswith('--')}; names = [x for x in args if not x.startswith('--')]
    if len(names) != 2: sys.exit(__doc__)
    if '--intl' in flags: intl(names[0], names[1], '--neutral' in flags, kursy)
    else: club(names[0], names[1], kursy, live)


if __name__ == '__main__':
    main(sys.argv[1:])
