#!/usr/bin/env python3
"""Typowanie meczu wyłącznie ze statystyk.
  python3 typuj.py "Athletic" "Alaves"                 # klubowe (auto-dopasowanie nazw)
  python3 typuj.py "Poland" "Netherlands" --intl [--neutral]
  python3 typuj.py A B --kurs 1X=1.35 --kurs O1.5=1.28   # kursy TYLKO po wyborze: EV po podatku 12%
  python3 typuj.py A B --live 60 1:0 [--czerwona-gosp] [--czerwona-gosc]   # na żywo: minuta i wynik
Wynik: prawdopodobieństwa (skalibrowane backtestem), statystyki formy/H2H/rożnych/kartek, ostrzeżenia."""
import os, sys, re, sqlite3, pickle, difflib, unicodedata, datetime as dt
import functools
import numpy as np, pandas as pd
from model import fit_dc, dc_lambdas, fit_elo_glm, elo_lambdas, markets, blend, load_calibration, calibrate, live_markets
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
_LITERY = str.maketrans({'ł':'l','Ł':'L','đ':'d','Đ':'D','ø':'o','Ø':'O','ß':'ss',
                         'æ':'ae','Æ':'AE','œ':'oe','Œ':'OE','þ':'th','Þ':'TH',
                         'ð':'d','Ð':'D','ı':'i','ŋ':'n','ħ':'h','ŧ':'t'})

def norm(s):
    s = unicodedata.normalize('NFKD', str(s).translate(_LITERY)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]', '', s)


ALIASES = {'lech': 'Lech Poznan', 'lechpoznan': 'Lech Poznan', 'legiawarszawa': 'Legia', 'legiawarsaw': 'Legia', 'rakowczestochowa': 'Rakow', 'jagielloniabialystok': 'Jagiellonia', 'zaglebielubin': 'Zaglebie', 'brukbettermalica': 'Termalica', 'termalicanieciecza': 'Termalica', 'wislaplock': 'Wisla Plock', 'athletic': 'Ath Bilbao', 'athleticbilbao': 'Ath Bilbao', 'athleticclub': 'Ath Bilbao', 'alaves': 'Alaves',
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
_ZNACZNIK = re.compile(r'^(b|ii|iii|2|3|c|k|u-?1[6-9]|u-?2[0-3]|sub-?2[0-3]|jun|juniors?|res|reserves?|'
                       r'young|youth|yth|academy|akademia|w|women|kobiet[ay]?|damen|femenino|femenil|'
                       r'feminin[oa]?|fem)\.?$', re.I)


def _znaczniki(s):
    # 22.09.2026: STS oznacza druzyny kobiece sufiksem "[K]", a czasem "(W)". Bez zdjecia
    # nawiasow token "[K]" nie pasowal do wzorca i "Club Leon [K]" dopasowywalo sie
    # do meskiego "Club Leon" — zmierzone na 5 meczach w przebiegu 21:00 dnia 21.09,
    # bez zadnego ostrzezenia. Model liczyl mecze meskie dla zdarzen kobiecych.
    # 23.09.2026 (wyd. 24, recenzja): liczyl tylko ILE jest znacznikow, nie JAKIE — "Barcelona (K)"
    # (kobiety) trafiala na "Barcelona B" (rezerwy), a "Real Madryt [K]" na "Real Madrid C", bo po obu
    # stronach byl jeden znacznik. Teraz porownujemy RODZAJE: kobiety / rezerwy B / zespol C /
    # kategoria wiekowa (z rocznikiem) / mlodziez ogolnie.
    out = []
    for t in re.split(r'[\s]+', str(s).strip()):
        t = t.strip('[](){}<>.,;:')
        if not _ZNACZNIK.match(t): continue
        t = t.lower().rstrip('.')
        if re.match(r'^(k|w|women|kobiet[ay]?|damen|femenino|femenil|feminin[oa]?|fem)$', t): out.append('kobiety')
        elif re.match(r'^(b|ii|2|res|reserves?)$', t): out.append('rezerwy')
        elif re.match(r'^(c|iii|3)$', t): out.append('zespol_c')
        elif re.match(r'^(u|sub)-?\d+$', t): out.append('u' + re.sub(r'\D', '', t))
        else: out.append('mlodziez')
    return tuple(sorted(out))


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
                 'lommel': 'Lommel SK', 'klommelsk': 'Lommel SK'}

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
    'dania': ('Denmark',), 'dominikana': ('Dominican Republic',), 'egipt': ('Egypt',),
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
                    'club clube klub calcio futbol football fussball handball basket basketball volley volleyball '
                    'hockey sport sports de del la el the da do'.split())


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
    if len(tn) <= len(tk): return wyn
    if tn[:len(tk)] == tk: odp = tn[len(tk):]
    elif tn[-len(tk):] == tk: odp = tn[:-len(tk)]
    else: odp = tuple(t for t in tn if t not in tk)
    if odp and all(t in _OGOLNE for t in odp): return wyn
    inne = sorted(p for p in pula if p != wyn and len(_tokeny(p)) > len(tk)
                  and (_tokeny(p)[:len(tk)] == tk or _tokeny(p)[-len(tk):] == tk))
    if inne:
        print(f'  ODRZUCONO: "{name}" -> "{wyn}" zgubiloby czlon rozrozniajacy, a rdzen "{wyn}" maja '
              f'w bazie tez: {", ".join(inne[:4])}{" ..." if len(inne) > 4 else ""}. '
              f'Nie da sie ustalic, ktory to klub — noga MNIEJ.')
        return None
    print(f'  UWAGA: "{name}" dopasowane do KROTSZEJ nazwy "{wyn}" — pominieto czlon '
          f'rozrozniajacy. Rdzen jest w bazie jednoznaczny, ale sprawdz, czy to ten sam klub.')
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


def _ten_sam_kraj(a, b):
    return _KRAJ_KANON.get(a, a) == _KRAJ_KANON.get(b, b)

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
    if k in ALIASES_KLUBY and ALIASES_KLUBY[k] in pool: return ALIASES_KLUBY[k]
    if k in _WARIANTY and _WARIANTY[k] in pool: return _WARIANTY[k]   # nazwa zrodlowa sklejonego klubu (build_kb)
    c = [p for p in by.values() if _zaw_nazwy(name, p)]
    if c:
        if len(c) == 1:
            wyn = c[0]
        else:   # "Chievo Verona" zawiera i "Chievo", i "Verona" — pierwszy czlon to niemal zawsze wlasciwy klub
            pref = [p for p in c if k.startswith(norm(p)) or norm(p).startswith(k)]
            if len(pref) == 1: wyn = pref[0]
            elif pref: wyn = max(pref, key=lambda p: len(norm(p)))
            else: wyn = min(c, key=lambda p: abs(len(norm(p)) - len(k)))
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


def cached(key, fn):
    p = os.path.join(HERE, 'cache', f'{key}.pkl'); os.makedirs(os.path.dirname(p), exist_ok=True)
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
EGZONIMY = {'madryt': 'Madrid', 'monachium': 'Munich', 'wieden': 'Wien', 'lizbona': 'Lisbon',
            'mediolan': 'Milan', 'rzym': 'Roma', 'neapol': 'Napoli', 'turyn': 'Torino', 'ateny': 'Athens',
            'sewilla': 'Sevilla', 'walencja': 'Valencia', 'stambul': 'Istanbul', 'kopenhaga': 'Copenhagen',
            'bruksela': 'Brussels', 'belgrad': 'Belgrade', 'moskwa': 'Moscow', 'praga': 'Prague',
            'bukareszt': 'Bucharest', 'sztokholm': 'Stockholm', 'kijow': 'Kyiv', 'lwow': 'Lviv',
            'zagrzeb': 'Zagreb', 'genua': 'Genoa', 'saloniki': 'Thessaloniki', 'pireus': 'Piraeus'}


def _przez_egzonim(name, pool):
    czl = str(name).split()
    nowe = [EGZONIMY.get(norm(c), c) for c in czl]
    if nowe == czl: return None
    alt = ' '.join(nowe)
    r = resolve(alt, pool)
    if r: print(f'  UWAGA: "{name}" dopasowane po zamianie polskiej nazwy miasta -> "{alt}" -> {r}.')
    return r


def club(home, away, kursy, live=None):
    con = db()
    m = pd.read_sql('select * from matches', con, parse_dates=['MatchDate'])
    elo = pd.read_sql('select club, country, elo, date from clubelo', con)
    elo = elo.sort_values('date').groupby('club').last()
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
        sys.exit(f'ROZNE KRAJE: "{home}" -> {h} ({dh}, {kh}) | "{away}" -> {a} ({da}, {ka}). '
                 f'W meczu ligi krajowej obie druzyny sa z jednego kraju — jedna z nazw zostala '
                 f'dopasowana do INNEGO klubu. Analiza przerwana, noga MNIEJ. '
                 f'Puchary kontynentalne (Libertadores, Liga Mistrzow...) i sparingi: dodaj --kontynentalny.')
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
            ldc = None; ostrz.append('Beniaminek / mało meczów w tej lidze (<10) — tylko model Elo.')
    else:
        ostrz.append(f'Różne ligi ({dh} vs {da}) — tylko model Elo.')
    glm = cached(f'glm_{today.date()}', lambda: fit_elo_glm(m))
    eh, ea = (elo.elo.get(h), elo.elo.get(a))
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
        R, N, pg = cached(f'pi_{today.date()}', _pi)
        if min(N.get(h, 0), N.get(a, 0)) >= 10:
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
    if sum(x is not None for x in (ldc, lel, lpi)) <= 1:
        ostrz.append('TYLKO JEDEN MODEL — traktuj P jak „szacunek” (max 1 noga na kupon, nie do K1).')
    wp = os.path.join(HERE, 'ensemble_wagi.json')
    if os.path.exists(wp):
        wd, we, wpi = json.load(open(wp))['wagi_dc_elo_pi']
        parts = [(x, l) for x, l in ((wd, ldc), (we, lel), (wpi, lpi)) if l is not None and x > 0] or \
                [(1.0, l) for l in (ldc, lel, lpi) if l is not None]
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
        def calibrate_v5n(k, p):   # korekta per rynek tylko w dół; rynki „poniżej” zawsze min. −4 pp (reguła użytkownika)
            s = 0.0
            for r in KR[KR.rynek == k].itertuples():
                lo, hi = [float(x) for x in str(r.przedzial).strip('[)').split(',')]
                if lo <= p < hi: s = float(r.przesuniecie)
            if k.startswith('U') and p >= 0.5: s = min(s, -0.04)
            return max(p + s, 0.0)
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
            for r in kor[kor.rynek == k].itertuples():
                lo, hi = [float(x) for x in str(r.przedział).strip('[)').split(',')]
                if lo <= pc < hi: pc = (1 - r.waga) * pc + r.waga * r.trafność
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
    value(rows, kursy)
    if ostrz: print('\nOSTRZEŻENIA:', *ostrz, sep='\n - ')
    print('\nUwaga: model nie zna składów, kontuzji i motywacji z dnia meczu — sprawdź je osobno (korekta maks. ±6 pp).')


def value(rows, kursy):
    if not kursy: return
    d = {k: pc for k, p, pc in rows}
    print('\nWARTOŚĆ (kurs użyty dopiero po wyliczeniu P; podatek 12%):')
    for k, o in kursy.items():
        if k not in d: print(f'  {k}: brak rynku'); continue
        p = d[k]; ev = p * o * TAX - 1
        kelly = max(0.0, (p * o * TAX - 1) / (o * TAX - 1)) if o * TAX > 1 else 0
        print(f'  {k} @ {o}: P={p:.1%}, kurs sprawiedliwy={1 / p / TAX:.2f}, EV={ev:+.1%}, ¼ Kelly={kelly / 4:.1%} bankrollu'
              + ('  ✔ wartość' if ev > 0 else '  ✘ brak wartości'))


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
    value(rows, kursy)


if __name__ == '__main__':
    args = [x for x in sys.argv[1:]]
    kursy = {}
    while '--kurs' in args:
        i = args.index('--kurs'); k, v = args[i + 1].split('='); kursy[k] = float(v.replace(',', '.')); del args[i:i + 2]
    live = None
    if '--live' in args:
        i = args.index('--live'); live = (int(args[i + 1]), args[i + 2], args.count('--czerwona-gosp'), args.count('--czerwona-gosc'))
        del args[i:i + 3]
    flags = {x for x in args if x.startswith('--')}; names = [x for x in args if not x.startswith('--')]
    if len(names) != 2: sys.exit(__doc__)
    if '--intl' in flags: intl(names[0], names[1], '--neutral' in flags, kursy)
    else: club(names[0], names[1], kursy, live)
