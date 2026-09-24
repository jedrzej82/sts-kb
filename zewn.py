#!/usr/bin/env python3
"""Wczytywanie wyników pobieranych przez Google Apps Script (apps_script/wyniki_sts.gs) z ESPN i Sofascore.
Pliki z Drive (folder baza-wiedzy) kładzie się do kb/zewn/:
  wyniki_espn_RRRR-MM.csv, wyniki_sofa_pilka_RRRR-MM.csv, wyniki_sofa_inne_RRRR-MM.csv
Funkcje używane przez uzupelnij_ligi.py (piłka) i hist_import.py / tenis.py (reszta). Kursy nie są pobierane."""
import os, re, glob, unicodedata, functools, pandas as pd, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ZD = os.path.join(HERE, 'zewn')

ESPN_DIV = {'nor.1': 'NOR', 'swe.1': 'SWE', 'swe.2': 'SWE2', 'den.1': 'DEN', 'fin.1': 'FIN', 'irl.1': 'IRL', 'sui.1': 'SUI',
            'aut.1': 'AUT', 'rus.1': 'RUS', 'rou.1': 'ROM', 'pol.1': 'POL', 'pol.2': 'POL2', 'mex.1': 'MEX', 'usa.1': 'USA',
            'usa.usl.1': 'USL', 'arg.1': 'ARG', 'bra.1': 'BRA', 'bra.2': 'BRA2', 'jpn.1': 'JAP', 'jpn.2': 'JAP2', 'chn.1': 'CHN',
            'cze.1': 'CZE', 'cro.1': 'CRO', 'srb.1': 'SRB', 'ukr.1': 'UKR', 'kor.1': 'KOR', 'ksa.1': 'KSA', 'aus.1': 'AUS',
            'bul.1': 'BUL', 'hun.1': 'HUN', 'chi.1': 'CHI', 'col.1': 'COL', 'ecu.1': 'ECU', 'uru.1': 'URU', 'per.1': 'PER',
            'par.1': 'PAR', 'bol.1': 'BOL', 'ven.1': 'VEN', 'rsa.1': 'RSA', 'can.1': 'CAN', 'bel.1': 'B1', 'bel.2': 'B2',
            'ger.1': 'D1', 'ger.2': 'D2', 'ger.3': 'D3', 'ned.1': 'N1', 'ned.2': 'N2', 'eng.1': 'E0', 'eng.2': 'E1', 'eng.3': 'E2',
            'eng.4': 'E3', 'esp.1': 'SP1', 'esp.2': 'SP2', 'ita.1': 'I1', 'ita.2': 'I2', 'fra.1': 'F1', 'fra.2': 'F2', 'por.1': 'P1',
            'tur.1': 'T1', 'gre.1': 'G1', 'sco.1': 'SC0', 'isr.1': 'ISR', 'cyp.1': 'CYP', 'svk.1': 'SVK', 'svn.1': 'SVN'}
NOWE_DIV = {'POL2': 'Polska I liga', 'ISR': 'Izrael', 'CYP': 'Cypr', 'SVK': 'Słowacja', 'SVN': 'Słowenia'}

# Sofascore: (fragment kraju, wzorzec nazwy rozgrywek) → Division kb; reszta lig → „Kraj | Liga” (każda liga świata)
SOFA_DIV = [('england', r'^premier league$', 'E0'), ('england', r'^championship$', 'E1'), ('england', r'^league one$', 'E2'),
            ('england', r'^league two$', 'E3'), ('england', r'^national league$', 'EC'), ('spain', r'^laliga$', 'SP1'),
            ('spain', r'laliga 2|hypermotion|^segunda division$', 'SP2'), ('germany', r'^bundesliga$', 'D1'), ('germany', r'^2\. bundesliga$|^bundesliga 2$', 'D2'),
            ('germany', r'^3\. liga$', 'D3'), ('italy', r'^serie a$', 'I1'), ('italy', r'^serie b$', 'I2'), ('france', r'^ligue 1$', 'F1'),
            ('france', r'^ligue 2$', 'F2'), ('netherlands', r'^eredivisie$', 'N1'), ('netherlands', r'eerste divisie|keuken kampioen', 'N2'),
            ('portugal', r'liga portugal$|^liga portugal betclic|primeira liga', 'P1'), ('belgium', r'^(jupiler )?pro league$|jupiler', 'B1'),
            ('belgium', r'challenger pro league', 'B2'), ('scotland', r'^(scottish )?premiership$', 'SC0'), ('scotland', r'^(scottish )?championship$', 'SC1'),
            ('scotland', r'^(scottish )?league one$', 'SC2'), ('scotland', r'^(scottish )?league two$', 'SC3'),
            ('turk', r'^(trendyol )?s[uü]per lig$', 'T1'), ('greece', r'super league( 1)?$|stoiximan', 'G1'),
            ('norway', r'^eliteserien$', 'NOR'), ('sweden', r'^allsvenskan$', 'SWE'), ('sweden', r'^superettan$', 'SWE2'),
            ('denmark', r'superliga', 'DEN'), ('finland', r'veikkausliiga', 'FIN'), ('ireland', r'premier division', 'IRL'),
            ('switzerland', r'^super league$', 'SUI'), ('austria', r'^bundesliga$', 'AUT'), ('russia', r'^premier (league|liga)$', 'RUS'),
            ('romania', r'^(superliga|liga i|liga 1)$', 'ROM'), ('poland', r'^ekstraklasa$', 'POL'), ('poland', r'^(i liga|1\. liga|betclic 1\. liga)$', 'POL2'),
            ('mexico', r'^liga mx', 'MEX'), ('usa', r'^mls$', 'USA'), ('usa', r'usl championship', 'USL'),
            ('argentina', r'liga profesional', 'ARG'), ('brazil', r'^(brasileir[aã]o\W+)?s[eé]rie a$', 'BRA'), ('brazil', r'^(brasileir[aã]o\W+)?s[eé]rie b$', 'BRA2'),
            ('japan', r'^j1 league$', 'JAP'), ('japan', r'^j2 league$', 'JAP2'), ('china', r'super league', 'CHN'),
            ('czech', r'(1\. liga|chance liga)$', 'CZE'), ('croatia', r'hnl$', 'CRO'), ('serbia', r'super ?liga', 'SRB'),
            ('ukraine', r'^premier league$', 'UKR'), ('korea', r'^k league 1$', 'KOR'), ('saudi', r'pro league|^saudi league$', 'KSA'),
            ('australia', r'^a-league( men)?$', 'AUS'), ('india', r'^indian super league$', 'IND'), ('bulgaria', r'(parva liga|efbet liga|first league)', 'BUL'),
            ('hungary', r'^nb i$|otp bank liga', 'HUN'), ('chile', r'liga de primera|primera divisi|^first division$', 'CHI'), ('colombia', r'primera a|^liga betplay$', 'COL'),
            ('ecuador', r'^liga ?pro$', 'ECU'), ('uruguay', r'primera divisi|^uruguayan championship$', 'URU'), ('peru', r'^liga 1', 'PER'),
            ('paraguay', r'primera divisi|^copa de primera$', 'PAR'), ('bolivia', r'divisi[oó]n profesional', 'BOL'), ('venezuela', r'^(liga futve|primera divisi[oó]n)$', 'VEN'),
            ('south africa', r'premiership|^premier league$', 'RSA'), ('iran', r'pro league', 'IRN'), ('canada', r'canadian premier league', 'CAN'),
            ('israel', r'premier league', 'ISR'), ('cyprus', r'1st division|first division|cyta championship', 'CYP'),
            ('slovakia', r'(nike liga|super liga|1\. liga)', 'SVK'), ('slovenia', r'prvaliga', 'SVN')]
# Ligi, w ktorych nazwie jest slowo pucharowe, a to sa rozgrywki LIGOWE. Paragwajska ekstraklasa
# w 365scores nazywa sie "Copa de Primera" i filtr PUCHAR wyrzucal ja w calosci — dlatego liga PAR
# stala w bazie na 2025-07-31. Wyjatek wymaga kraju i DOKLADNEJ nazwy, zeby nie otworzyc furtki
# pucharom krajowym (Copa Paraguay dalej jest odrzucana).
LIGA_NIE_PUCHAR = [('paraguay', r'^copa de primera$')]


def _liga_nie_puchar(kraj, turniej):
    k, t = _n(kraj), _n(turniej)
    return any(kk in k and re.search(rx, t) for kk, rx in LIGA_NIE_PUCHAR)


PUCHAR = re.compile(r'cup|pokal|copa|coupe|coppa|ta[cç]a|beker|pohar|puchar|friendl|qualif|play-?off|super ?cup|trophy|shield|u1\d|u2\d|youth|reserv|amateur|femen|feminin|women|frauen|damen|\(w\)|liga f$|premier league 2|primavera|juvenil|sub-?\d\d', re.I)


def _n(s): return unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower().strip()


def _scal_nazwy_rozgrywek(d):
    """Ta sama liga pod dwiema nazwami. 365scores przemianowuje rozgrywki w trakcie sezonu:
    Andora 20.09.2026 ma jedna kolejke zapisana i jako 'Super League', i jako 'Primera Divisio';
    Ekwador ma 'Liga Basquet Pro' i 'Liga Nacional'. Division powstaje jako 'kraj | turniej',
    wiec bez sklejenia JEDNA liga wchodzi do bazy jako DWIE — historia rozjezdza sie na pol,
    a mecze z dnia przemianowania licza sie dwa razy.

    Nazwy sklejamy STRUKTURALNIE, nie po podobienstwie: jezeli ten sam mecz (data, sport,
    gospodarz, gosc, wynik) wystepuje pod dwiema nazwami rozgrywek tego samego kraju, to sa
    te same rozgrywki — zaden prog podobienstwa nie odroznilby 'Primera Divisio' od
    'Segunda Divisio', a te trzeba trzymac osobno. Zostaje nazwa czestsza."""
    if not {'kraj', 'turniej', 'sport'} <= set(d.columns) or not len(d): return d
    kol_w = [c for c in ('wg', 'wa', 'gg', 'ga', 'pg', 'pa') if c in d.columns]
    mecz = [c for c in ('data', 'sport', 'gosp', 'gosc') if c in d.columns] + kol_w
    if len(mecz) < 5: return d

    rodzic = {}

    def znajdz(x):
        while rodzic.setdefault(x, x) != x:
            rodzic[x] = rodzic[rodzic[x]]
            x = rodzic[x]
        return x

    wezly = list(zip(d.sport, d.kraj, d.turniej))
    d = d.assign(_wez=wezly)
    # 23.09.2026 (recenzja): JEDEN wspolny mecz wystarczal, zeby skleic dwie ligi — baraz zapisany
    # w II i I lidze przenosil CALA II lige do I, a mecz ligowy zapisany tez jako sparing przemianowywal
    # cala lige na sparingi (i filtr PUCHAR ja kasowal). Teraz sklejamy tylko gdy:
    #   ten sam sport i TEN SAM KRAJ, obie nazwy po tej samej stronie filtra PUCHAR,
    #   i wspolne mecze to co najmniej POLOWA meczow mniejszej z nazw (przemianowanie, nie baraz).
    licz = d['_wez'].value_counts()
    wspolne = {}
    for _, g in d.groupby(mecz, sort=False)['_wez']:
        u = sorted(set(g))
        for i_, a_ in enumerate(u):
            for b_ in u[i_ + 1:]:
                wspolne[(a_, b_)] = wspolne.get((a_, b_), 0) + 1
    kraw = []
    for (a_, b_), n_ in wspolne.items():
        if a_[0] != b_[0] or _n(a_[1]) != _n(b_[1]): continue
        if bool(PUCHAR.search(str(a_[2]))) != bool(PUCHAR.search(str(b_[2]))): continue
        if n_ < 0.5 * min(licz.get(a_, 0), licz.get(b_, 0)): continue
        kraw.append((a_, b_))
    # Druga recenzja: sklejanie jest PRZECHODNIE — mala nazwa ('Liguilla', 1 mecz wspolny z I liga i 1 z II)
    # laczyla I i II lige w jedna. Przemianowanie to relacja JEDEN-DO-JEDNEGO: sklejamy tylko pary,
    # w ktorych KAZDA z nazw ma dokladnie jednego partnera.
    stopien = {}
    for a_, b_ in kraw:
        stopien[a_] = stopien.get(a_, 0) + 1; stopien[b_] = stopien.get(b_, 0) + 1
    for a_, b_ in kraw:
        if stopien[a_] != 1 or stopien[b_] != 1:
            print(f'  zewn: NIE sklejam "{a_[1]} | {a_[2]}" z "{b_[1]} | {b_[2]}" — jedna z nazw laczy sie z kilkoma innymi.')
            continue
        ra, rb = znajdz(a_), znajdz(b_)
        if ra != rb: rodzic[rb] = ra

    if not any(znajdz(w) != w for w in set(wezly)):
        return d.drop(columns='_wez')

    licz = d['_wez'].value_counts()
    kanon = {}
    for w in set(wezly):
        k = znajdz(w)
        grupa = [x for x in set(wezly) if znajdz(x) == k]
        naj = max(grupa, key=lambda x: (licz.get(x, 0), x[2]))
        kanon[w] = naj
    zmienione = {w: n for w, n in kanon.items() if w != n}
    for w, n in sorted(zmienione.items()):
        print(f'  zewn: te same rozgrywki pod dwiema nazwami — "{w[1]} | {w[2]}" -> "{n[1]} | {n[2]}" '
              f'({int(licz.get(w, 0))} meczow przeniesionych)')
    d['turniej'] = [kanon[w][2] for w in wezly]
    d['kraj'] = [kanon[w][1] for w in wezly]
    return d.drop(columns='_wez')


def czytaj(wzor, bez=None):
    fs = sorted(glob.glob(os.path.join(ZD, wzor)) + glob.glob(os.path.join(ZD, wzor + '.gz')))
    if bez: fs = [f for f in fs if not re.search(bez, os.path.basename(f))]
    if not fs: return pd.DataFrame()
    d = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in fs], ignore_index=True).drop_duplicates()

    # 22.09.2026. Pliki z Apps Script zawieraja pojedyncze wiersze uszkodzone przy zapisie,
    # np. "\t\t\t\t   (W): 2" w kolumnie daty. To nie jest mecz — to smiec z parsowania.
    # Wchodzil do bazy jako drużyna o nazwie z tabulatorow i zasmiecal pule nazw, przez co
    # dopasowanie nazw mialo o jednego falszywego kandydata wiecej. Odrzucamy wiersze,
    # ktorych DATA sie nie parsuje, i glosno zglaszamy ile — cicha strata bylaby gorsza.
    if 'data' in d.columns and len(d):
        n0 = len(d)
        ok = pd.to_datetime(d.data, errors='coerce').notna()
        if not ok.all():
            zle = d.loc[~ok, 'data'].astype(str).str.strip().replace('', '(puste)')
            przyk = ', '.join(repr(x[:30]) for x in zle.head(3))
            print(f'  zewn: pominieto {int((~ok).sum())} z {n0} wierszy bez poprawnej daty '
                  f'(np. {przyk}) — uszkodzone przy zapisie przez Apps Script.')
            d = d[ok].reset_index(drop=True)

    # 22.09.2026. Do klucza dochodzi WYNIK i TURNIEJ. Bez nich dwa rozne mecze tej samej pary
    # tego samego dnia zlewaly sie w jeden: baseball (MLB, meksykanska LMB) gra dwumecze,
    # zostawal tylko ostatni. Zmierzone na snapshocie zewn/: 175 meczow traconych cicho
    # (167 baseball/inne, 5 pilka, 1 boks). Powtorka zapisu z Apps Script ma wynik IDENTYCZNY,
    # wiec dalej jest odsiewana — a tych bylo duzo: 17-19.09 kazdy mecz siedzial w pliku 2-4 razy.
    d = _scal_nazwy_rozgrywek(d)   # jedna liga pod dwiema nazwami -> jedna nazwa, ZANIM odsiejemy

    # 23.09.2026 (recenzja): wynik w kluczu przepuszczal DUPLIKATY meczow, ktore Apps Script zapisal
    # z roznym wynikiem (Shams Azar - Aluminium Arak 1:2 i 2:2, Liverpool - Como 0:0 i 2:0). Dwa mecze
    # tej samej pary jednego dnia sa realne tylko w baseballu (dwumecze MLB i LMB) — tylko tam wynik
    # rozroznia mecze. W pozostalych sportach zostaje JEDEN wiersz: pelniejszy, a przy rownych ostatni.
    _kw = [c for c in ('wg', 'wa', 'gg', 'ga', 'pg', 'pa') if c in d.columns]
    if 'sport' in d.columns and _kw:
        _dw = d.sport.astype(str).str.lower().isin({'baseball'})
        d = d.assign(_wyn=d[_kw].astype(str).agg(':'.join, axis=1).where(_dw, ''))
    else:
        d = d.assign(_wyn='')
    klucz = [c for c in ('data', 'sport', 'liga', 'turniej', 'gosp', 'gosc', '_wyn') if c in d.columns]
    if 'okresy_g' in d.columns:   # ten sam mecz pobrany ponownie: zostaje wiersz z pełniejszymi danymi (okresy/nawierzchnia)
        d = d.assign(_pel=(d.okresy_g != '').astype(int) + (d.get('nawierzchnia', '') != '').astype(int)).sort_values('_pel', kind='stable')
        d = d.drop(columns='_pel')
    # Druga recenzja: przy RÓZNYCH wynikach tego samego meczu keep='last' bralo wiersz pozniejszy w PLIKU,
    # a nie wynik koncowy (Shams Azar - Aluminium Arak: zostawalo 1:2, koncowy byl 2:2). Punkty/gole nie
    # maleja w trakcie meczu, wiec wynik koncowy to ten, ktory jest >= wszystkim pozostalym w OBU skladowych.
    # Gdy takiego nie ma (Chertsey 1:2 i 2:1 — sprzeczne), mecz odrzucamy: brak meczu jest lepszy niz zly wynik.
    if len(_kw) >= 2 and len(d):
        g1, g2 = _kw[0], _kw[1]
        v1, v2 = pd.to_numeric(d[g1], errors='coerce'), pd.to_numeric(d[g2], errors='coerce')
        d = d.assign(_v1=v1, _v2=v2)
        wynik_kl = list(klucz)   # z '_wyn': w baseballu rozne wyniki to rozne mecze (dwumecz), nie sprzecznosc
        rozne = d.groupby(wynik_kl, dropna=False)[[g1, g2]].transform(lambda s_: s_.nunique()).max(axis=1) > 1
        if rozne.any():
            zostaw, sprzeczne = [], 0
            for _, gr in d[rozne].groupby(wynik_kl, dropna=False):
                if gr[['_v1', '_v2']].isna().any().any():
                    zostaw.append(gr.index[-1]); continue            # wynik nieliczbowy (np. boks KO/TKO)
                dom = gr[(gr._v1 >= gr._v1.max()) & (gr._v2 >= gr._v2.max())]
                if len(dom): zostaw.append(dom.index[-1])
                else: sprzeczne += 1
            d = pd.concat([d[~rozne], d.loc[zostaw]])
            if sprzeczne:
                print(f'  zewn: odrzucono {sprzeczne} meczow ze SPRZECZNYM wynikiem w zrodle (np. 1:2 i 2:1) — nie da sie ustalic koncowego.')
        if 'sport' in d.columns:   # baseball: wynik w kluczu, wiec migawka w trakcie meczu nie jest odsiewana — ostrzegamy
            b = d[d.sport.astype(str).str.lower() == 'baseball']
            if len(b):
                pod = 0
                for _, gr in b.groupby(['data', 'gosp', 'gosc']):
                    if len(gr) > 1 and gr._v1.notna().all():
                        x = gr[['_v1', '_v2']].values
                        pod += sum(1 for i in range(len(x)) for j in range(len(x)) if i != j and (x[i] <= x[j]).all())
                if pod:
                    print(f'  zewn: baseball — {pod} par meczow tego samego dnia, w ktorych jeden wynik jest <= drugiemu w obu skladowych '
                          f'(moze to byc migawka w trakcie meczu, a nie drugi mecz dwumeczu).')
        d = d.drop(columns=['_v1', '_v2'])
    return d.drop_duplicates(klucz, keep='last').drop(columns='_wyn').reset_index(drop=True)


def sofa_div(kraj, turniej):
    k, t = _n(kraj), _n(turniej)
    for kk, rx, div in SOFA_DIV:
        if kk in k and re.search(rx, t): return div
    return None


def pilka():
    """Mecze piłkarskie z ESPN (z rożnymi/faulami/strzałami/kartkami) i Sofascore (wszystkie ligi świata)."""
    out = []
    e = czytaj('wyniki_espn_*.csv')
    if len(e):
        e = e[e.liga.isin(ESPN_DIV)]
        num = lambda c: pd.to_numeric(e[c], errors='coerce')
        out.append(pd.DataFrame(dict(Division=e.liga.map(ESPN_DIV), MatchDate=pd.to_datetime(e.data), HomeTeam=e.gosp, AwayTeam=e.gosc,
                                     FTHome=num('gg'), FTAway=num('ga'), HomeCorners=num('rozne_g'), AwayCorners=num('rozne_a'),
                                     HomeFouls=num('faule_g'), AwayFouls=num('faule_a'), HomeShots=num('strzaly_g'), AwayShots=num('strzaly_a'),
                                     HomeTarget=num('celne_g'), AwayTarget=num('celne_a'), HomeYellow=num('zolte_g'), AwayYellow=num('zolte_a'),
                                     HomeRed=num('czerwone_g'), AwayRed=num('czerwone_a'), src='espn')))
    # Poprawka 46b: Apps Script zapisuje pilke z Flashscore do wyniki_fs_pilka_* — NIE moze wejsc tu jak 365scores
    # (bez odsiewania dubli). Wchodzi wylacznie przez _pilka_fs.
    s = czytaj('wyniki_*_pilka_*.csv', bez=r'^wyniki_fs_')
    s = _pilka_fs(s)
    if len(s):
        _puchar = s.turniej.str.contains(PUCHAR) & ~pd.Series([_liga_nie_puchar(k, t) for k, t in zip(s.kraj, s.turniej)], index=s.index, dtype=bool)
        s = s[~_puchar & ~s.kraj.str.contains(r'^(?:international|world|europe|south america|africa|asia|oceania|north america|north (?:and|&) central america|club.*)$', case=False)]
        div = [sofa_div(k, t) or f'{k} | {t}' for k, t in zip(s.kraj, s.turniej)]
        s = s.assign(Division=div)
        n = s.groupby('Division').Division.transform('size')
        s = s[(n >= 60) | s.Division.isin(set(ESPN_DIV.values()) | {kod for _, _, kod in SOFA_DIV})]   # nieznane ligi: tylko z historią ≥60 meczów
        out.append(pd.DataFrame(dict(Division=s.Division, MatchDate=pd.to_datetime(s.data), HomeTeam=s.gosp, AwayTeam=s.gosc,
                                     FTHome=pd.to_numeric(s.wg, errors='coerce'), FTAway=pd.to_numeric(s.wa, errors='coerce'),
                                     HTHome=pd.to_numeric(s.okresy_g.str.split(';').str[0], errors='coerce'),
                                     HTAway=pd.to_numeric(s.okresy_a.str.split(';').str[0], errors='coerce'), src='sofa')))
    if not out: return pd.DataFrame()
    d = pd.concat(out, ignore_index=True).dropna(subset=['FTHome', 'FTAway', 'MatchDate'])
    d[['FTHome', 'FTAway']] = d[['FTHome', 'FTAway']].astype(int)
    return d


SPORT = {'ice-hockey': ('hokej', 3), 'basketball': ('koszykówka', 4), 'volleyball': ('siatkówka', 0), 'handball': ('piłka ręczna', 2),
         'futsal': ('futsal', 2), 'darts': ('dart', 0), 'snooker': ('snooker', 0), 'rugby': ('rugby', 2),
         'american-football': ('futbol amerykański', 4), 'baseball': ('baseball', 0), 'floorball': ('unihokej', 3),
         'waterpolo': ('piłka wodna', 4), 'cricket': ('krykiet', 0), 'badminton': ('badminton', 0),
         'beach-volley': ('siatkówka plażowa', 0), 'aussie-rules': ('futbol australijski', 0), 'table-tennis': ('tenis stołowy', 0)}


ALIAS_SPORT = {'hockey': 'ice-hockey', 'a-football': 'american-football', 'ice-hockey': 'ice-hockey', 'e-sports': 'esports', 'esport': 'esports', 'beach-volleyball': 'beach-volley',
               'australian-football': 'aussie-rules', 'aussie-rules-football': 'aussie-rules', 'water-polo': 'waterpolo',
               'rugby-union': 'rugby', 'soccer': 'football', 'ping-pong': 'table-tennis'}
NAZWA_PL = {'mma': 'mma', 'boxing': 'boks', 'field-hockey': 'hokej na trawie', 'netball': 'netball', 'bandy': 'bandy',
            'lacrosse': 'lacrosse', 'squash': 'squash', 'rugby-league': 'rugby league', 'beach-soccer': 'piłka plażowa',
            'pesapallo': 'pesapallo', 'field-hockey': 'hokej na trawie', 'padel': 'padel', 'kabaddi': 'kabaddi', 'speedway': 'żużel'}
WYGRANA = {'mma', 'boks', 'krykiet'}   # liczy się zwycięzca, nie punkty




# Poprawka 46 (24.09.2026): pilka z Flashscore dla lig, ktorych 365scores nie obejmuje (np. Szwecja Division 2 —
# 365 ma tylko Allsvenskan i Superettan; Goiano 2 bez Crixas). Apps Script: FS_SPORTY 1: 'football'.
# Zasady (jak w hokeju, ale ostrzej, bo w pilce kluby wielu lig maja podobne nazwy):
#  1) mecz z Flashscore ODPADA, gdy 365scores ma tego dnia (+-1 dzien) w tym samym kraju mecz, w ktorym
#     gospodarz LUB gosc ma ten sam zapis (bez diakrytykow) albo jego nazwa zawiera sie w nazwie z 365 —
#     wtedy to ten sam mecz pod inna nazwa ligi/druzyny;
#  2) odpada takze cala liga FS, ktorej nazwa (kraj + liga) jest identyczna jak liga w 365 (duble lig top);
#  3) nazwa druzyny FS zamieniana na zapis 365 TYLKO przy jednoznacznym kandydacie w tym samym kraju.
_ZNACZNIK_FS = re.compile(r'^(?:b|c|ii|iii|u1\d|u2[0-3]|w|women|res|reserves?|youth|jun|juniors?|am)$')
_MLODZI_KOBIETY_FS = re.compile(r'\bU-?\d{2}\b|\byouth\b|\bjunior|\bjuvenil|\bprimavera\b|\bwomen\b|\bfemin|\(W\)|'
                                r'\bW$|\breserve|\bII$|\bB$|\bfriendl|\bu-?\d{2}$', re.I)


@functools.lru_cache(maxsize=None)
def _tok_fs(t):
    n = _nrm(t)
    return frozenset(n), frozenset(x for x in n if _ZNACZNIK_FS.match(x)), max((len(w) for w in n), default=0)


def _znaczniki_fs(t):
    return _tok_fs(t)[1]


def _pilka_fs(s):
    fs = pd.concat([czytaj('wyniki_fs_pilka_*.csv'), czytaj('wyniki_fs_inne_*.csv')], ignore_index=True)
    if not len(fs): return s
    fs = fs[fs.sport.isin(['football', 'soccer'])].drop_duplicates().copy()
    if not len(fs): return s
    n0 = len(fs)
    fs['kraj'] = fs.kraj.map(_kraj_365)
    fs['sport'] = 'football'
    # mlodziez, kobiety, rezerwy, sparingi — tylko przez 365 (tam sa oznaczone); z FS nie wchodza wcale
    mk = [bool(_MLODZI_KOBIETY_FS.search(f'{t}')) or bool(_MLODZI_KOBIETY_FS.search(a_.strip())) or bool(_MLODZI_KOBIETY_FS.search(b_.strip()))
          for t, a_, b_ in zip(fs.turniej, fs.gosp, fs.gosc)]
    fs = fs[[not x for x in mk]]
    n_mk = sum(mk)
    ligi365 = set(zip(s.kraj.str.lower(), s.turniej.str.lower())) if len(s) else set()
    fs = fs[[(k.lower(), t.lower()) not in ligi365 for k, t in zip(fs.kraj, fs.turniej)]]

    def _pasuje(ta, tb):   # nazwy: ten sam zapis albo jedna zawiera druga; znaczniki (B, II, U19, W) MUSZA byc te same
        nt, mt, lt = _tok_fs(ta); z, mz, lz = _tok_fs(tb)
        if mt != mz or not nt or not z: return False
        if nt == z: return True
        if nt <= z: return lt >= 4
        if z <= nt: return lz >= 4
        return False

    # puchary z FS nie wchodza (w 365 tez sa odsiewane), a przed przypisaniem ligi — zeby puchar nie trafil do ligi
    pu = fs.turniej.str.contains(PUCHAR) & ~pd.Series([_liga_nie_puchar(k, t) for k, t in zip(fs.kraj, fs.turniej)], index=fs.index, dtype=bool)
    fs = fs[~pu]

    # 1) liga FS -> liga 365 TYLKO gdy: nazwy lig maja wspolny czlon (>=4 znaki, np. "Serie D - Group A" / "Serie D",
    #    "Kakkonen - Lohko B" / "Kakkonen") ORAZ >=2 druzyny FS maja identyczny zapis w tej lidze 365 i to >=60% trafien.
    druzyny_ligi = {}
    if len(s):
        for k, t, a_, b_ in zip(s.kraj.str.lower(), s.turniej, s.gosp, s.gosc):
            druzyny_ligi.setdefault((k, t), set()).update((a_, b_))
    klucz = lambda x: (_tok_fs(x)[0], _tok_fs(x)[1])
    idx_nazw = {}
    for (k, t), dr in druzyny_ligi.items():
        for x in dr: idx_nazw.setdefault((k, klucz(x)), set()).add(t)
    ogolne = {'league', 'liga', 'division', 'group', 'serie', 'primera', 'segunda', 'first', 'second', 'third', 'premier',
              'championship', 'national', 'regional', 'stage', 'round', 'north', 'south', 'east', 'west', 'lohko', 'grupo', 'girone'}
    czl = lambda t: {w for w in _nrm(t) if len(w) >= 4 and w not in ogolne} | ({' '.join(_nrm(t)[:2])} if len(_nrm(t)) >= 2 else set())
    lmapa = {}
    for (k, t), g in fs.groupby([fs.kraj.str.lower(), fs.turniej]):
        traf = [lg for x in set(g.gosp) | set(g.gosc) for lg in idx_nazw.get((k, klucz(x)), ())]
        if len(traf) < 2: continue
        naj = max(set(traf), key=traf.count)
        if traf.count(naj) >= 0.6 * len(traf) and (czl(t) & czl(naj)): lmapa[(k, t)] = naj
    fs['turniej'] = [lmapa.get((k.lower(), t), t) for k, t in zip(fs.kraj, fs.turniej)]

    # 2) nazwy druzyn: w DOCELOWEJ lidze (ta sama zasada co w pilka(): sofa_div albo "Kraj | Liga").
    #    Druzyna FS bez jednoznacznego odpowiednika w lidze znanej z 365 -> mecz ODPADA (inaczej klub rozpadlby sie na dwa:
    #    "Atl. Nacional" obok "Atletico Nacional"). W lidze nowej (brak w 365) nazwy zostaja jak w FS.
    _SKR = {'atl': 'atletico', 'dep': 'deportivo', 'dyn': 'dynamo', 'utd': 'united', 'univ': 'universidad', 'r': 'real',
            'sp': 'sporting', 'int': 'internacional', 'cd': '', 'fc': '', 'cf': '', 'sc': '', 'ac': '', 'fk': '', 'sk': ''}
    def _luz(x):
        return frozenset(w for w in (_SKR.get(v, v) for v in _nrm(x)) if w)
    def _pasuje_luzno(ta, tb):
        if _znaczniki_fs(ta) != _znaczniki_fs(tb): return False
        a1, b1 = _luz(ta), _luz(tb)
        if not a1 or not b1: return False
        mn = a1 if len(a1) <= len(b1) else b1
        return (a1 <= b1 or b1 <= a1) and max(len(w) for w in mn) >= 3
    cel = lambda k, t: sofa_div(k, t) or f'{k} | {t}'
    druzyny_celu = {}
    if len(s):
        for k, t, a_, b_ in zip(s.kraj, s.turniej, s.gosp, s.gosc):
            druzyny_celu.setdefault(cel(k, t), set()).update((a_, b_))
    fs_cel = [cel(k, t) for k, t in zip(fs.kraj, fs.turniej)]
    mapa, zle = {}, set()
    for c_, x in set(zip(fs_cel, fs.gosp)) | set(zip(fs_cel, fs.gosc)):
        kand = druzyny_celu.get(c_, set())
        if not kand or x in kand: continue
        for test in (lambda c: klucz(c) == klucz(x), lambda c: _pasuje(x, c), lambda c: _pasuje_luzno(x, c)):
            w = [c for c in kand if test(c)]
            if len(w) == 1: mapa[(c_, x)] = w[0]; break
            if len(w) > 1: break
        else:
            pass
        if (c_, x) not in mapa: zle.add((c_, x))
    ok = [(c_, a_) not in zle and (c_, b_) not in zle for c_, a_, b_ in zip(fs_cel, fs.gosp, fs.gosc)]
    for col in ('gosp', 'gosc'):
        fs[col] = [mapa.get((c_, x), x) for c_, x in zip(fs_cel, fs[col])]
    n_zle = len(ok) - sum(ok)
    fs = fs[ok]

    # 3) dubel: (a) ten kraj, +-1 dzien, gospodarz LUB gosc pasuje; (b) dowolny kraj, +-1 dzien, OBIE druzyny pasuja
    po_kraju, po_dniu = {}, {}
    if len(s):
        for d, k, a_, b_ in zip(s.data.str[:10], s.kraj.str.lower(), s.gosp, s.gosc):
            po_kraju.setdefault((k, d), []).extend((a_, b_))
            po_dniu.setdefault(d, []).append((a_, b_))
    def dni(d):
        t = pd.Timestamp(d); return [d, str((t + pd.Timedelta(days=1)).date()), str((t - pd.Timedelta(days=1)).date())]
    dubel = []
    for d, k, a_, b_ in zip(fs.data.str[:10], fs.kraj.str.lower(), fs.gosp, fs.gosc):
        dd = dni(d)
        z = [x for q in dd for x in po_kraju.get((k, q), [])]
        jest = any(_pasuje(a_, y) or _pasuje(b_, y) for y in z)
        if not jest:
            jest = any((_pasuje_luzno(a_, h) and _pasuje_luzno(b_, g)) or (_pasuje_luzno(a_, g) and _pasuje_luzno(b_, h))
                       for q in dd for h, g in po_dniu.get(q, []))
        dubel.append(jest)
    fs = fs[~pd.Series(dubel, index=fs.index, dtype=bool)]
    print(f'  zewn: pilka z Flashscore: {n0} meczow; odrzucono {n_mk} mlodziezowych/kobiecych/rezerw/sparingow; po odsianiu lig '
          f'i meczow obecnych w 365scores zostaje {len(fs)} ({fs.kraj.nunique()} krajow); '
          f'{len(mapa)} nazw druzyn i {len(lmapa)} lig przypisanych do zapisu 365; {n_zle} meczow odrzuconych, bo druzyna '
          f'z ligi znanej w 365 nie ma jednoznacznego odpowiednika.')
    return pd.concat([s, fs[s.columns]], ignore_index=True) if len(s) else fs

# Poprawka 44 (24.09.2026): hokej z Flashscore. 365scores nie prowadzi sezonu 2026/27 Liigi, SHL, DEL,
# czeskiej Extraligi ani szwajcarskiej NL (zmierzone: allscores 23.09 zwraca tylko NHL, KHL, Danie, Slowacje;
# Liiga: ostatni mecz 13.05.2026, terminarz pusty), wiec Apps Script pobiera hokej takze z Flashscore
# (FS_SPORTY 4: 'hockey'). Ten sam mecz z dwoch zrodel mialby rozne nazwy druzyn i liczylby sie DWA razy
# (jak NFL/KBO/NPB przed 23.09). Zasada: wiersz hokeja z Flashscore zostaje TYLKO, gdy 365scores nie ma
# zadnego meczu hokeja z tego kraju w tym dniu. Kraj z Flashscore ("FINLAND") ujednolicony do zapisu 365.
_KRAJ_FS = {'czech republic': 'Czechia', 'usa': 'USA', 'south korea': 'South Korea', 'great britain': 'England',
            # Poprawka 46b: rozbieznosci zmierzone na pilce z 17-23.09 (131 krajow FS vs zapis 365)
            'turkey': 'Turkiye', 'bosnia and herzegovina': 'Bosnia & Herzegovina', 'philippines': 'The Phillipines',
            'taiwan': 'Chinese Taipei', 'united arab emirates': 'UAE'}


def _kraj_365(k):
    k = str(k).strip()
    return _KRAJ_FS.get(k.lower(), k.title() if k.isupper() else k)


def _hokej_fs_bez_dubli(s):
    fs = czytaj('wyniki_fs_inne_*.csv')
    if not len(fs) or not len(s): return s
    hk = lambda d: d.sport.isin(['hockey', 'ice-hockey'])
    fs = fs[hk(fs)]
    if not len(fs): return s
    kol = list(s.columns)
    klucz_fs = set(map(tuple, fs[kol].astype(str).values))
    jest_fs = pd.Series([tuple(r) in klucz_fs for r in s[kol].astype(str).values], index=s.index) & hk(s)
    kraj = s.kraj.map(_kraj_365)
    dzien_365 = set(zip(s.loc[hk(s) & ~jest_fs, 'data'].str[:10], kraj[hk(s) & ~jest_fs].str.lower()))
    dubel = jest_fs & pd.Series([(d[:10], k.lower()) in dzien_365 for d, k in zip(s.data, kraj)], index=s.index)
    if jest_fs.any():
        print(f'  zewn: hokej z Flashscore: {int(jest_fs.sum())} meczow, odrzucono {int(dubel.sum())} '
              f'(ten kraj i dzien sa juz w 365scores), zostaje {int((jest_fs & ~dubel).sum())}.')
    zostaje = jest_fs & ~dubel
    s = s.copy()
    s.loc[zostaje, 'kraj'] = kraj[zostaje]
    s.loc[zostaje, 'turniej'] = [_LIGA_FS.get((k, t), t) for k, t in zip(s.loc[zostaje, 'kraj'], s.loc[zostaje, 'turniej'])]
    s = s[~dubel]
    return _hokej_fs_nazwy(s, zostaje[~dubel])


# Poprawka 44b: Flashscore i 365scores zapisuja inaczej te same ligi i druzyny. Bez mapowania druzyna
# rozpadalaby sie na dwie (osobne Elo): "Leksand"/"Leksands IF", "IFK Helsinki"/"HIFK".
_LIGA_FS = {('Slovakia', 'Tipsport liga'): 'Extraliga', ('Denmark', 'Metal Ligaen'): 'Ligaen',
            ('Belarus', 'Extraleague'): 'Extraliga', ('Norway', 'EHL'): 'Eliteserien'}
# nieregularne — kazda para sprawdzona recznie (ta sama liga, ten sam klub)
_DRUZYNA_FS = {('Finland | Liiga', 'IFK Helsinki'): 'HIFK',
               ('Austria | ICE Hockey League', 'Klagenfurt'): 'EC-KAC',
               ('Austria | ICE Hockey League', 'Bolzano'): 'HCB Südtirol',
               ('Austria | ICE Hockey League', 'HK Olimpija'): 'Olimpija Ljubljana',
               ('Belarus | Extraliga', 'Baranavichy'): 'Baranovichi',
               ('Denmark | Ligaen', 'Sonderjyske Ishockey'): 'Sonderjyske',
               ('Austria | ICE Hockey League', 'Graz99ers'): 'Graz 99ers',
               ('Sweden | HockeyAllsvenskan', 'AIK'): 'AIK IF',
               ('Sweden | HockeyAllsvenskan', 'Leksand'): 'Leksands IF',   # spadek z SHL 2026
               ('Sweden | SHL', 'Leksand'): 'Leksands IF',
               # 24.09: pelny tydzien 17-23.09 (kazda para sprawdzona)
               ('Canada | OHL', 'Ottawa 67s'): "Ottawa 67's",
               ('Czechia | Extraliga', 'Mountfield HK'): 'HC Mountfield Hradec Kralove',
               ('Czechia | Extraliga', 'Sparta Prague'): 'Sparta Praha',
               ('Finland | Liiga', 'JYP'): 'Jyvaskyla',
               ('Finland | Liiga', 'Hameenlinna'): 'HPK',              # Hameenlinnan Pallokerho
               ('Germany | DEL', 'Grizzly Wolfsburg'): 'Grizzlys Wolfsburg',
               ('Germany | DEL', 'Nurnberg Ice Tigers'): 'Thomas Sabo Ice Tigers',
               ('Germany | DEL2', 'Bietigheim/Bissingen'): 'Bietigheim Steelers',
               ('Sweden | SHL', 'Djurgarden'): 'Djurgardens IF',
               ('Sweden | SHL', 'Farjestad'): 'Farjestads BK',
               ('Sweden | SHL', 'Linkoping'): 'Linkopings HC',
               ('Sweden | SHL', 'IF Bjorkloven'): 'Björklöven',        # awans z Allsvenskan
               ('Switzerland | National League', 'EHC Kloten'): 'Kloten Flyers',
               ('Switzerland | National League', 'Langnau Tigers'): 'SCL Tigers',
               ('Switzerland | National League', 'Zug'): 'EV Zug',
               ('Switzerland | National League', 'Zurich'): 'ZSC Lions'}


def _nrm(x):
    return re.sub(r'[^a-z0-9 ]', ' ', unicodedata.normalize('NFKD', str(x)).encode('ascii', 'ignore').decode().lower()).split()


def _hokej_fs_nazwy(s, maska_fs):
    hk = s.sport.isin(['hockey', 'ice-hockey'])
    liga = s.kraj + ' | ' + s.turniej
    baza = s[hk & ~maska_fs]
    pula = {}
    for lg, a, b in zip(liga[hk & ~maska_fs], baza.gosp, baza.gosc):
        pula.setdefault(lg, set()).update((a, b))
    mapa, nowe = {}, set()
    for lg, t in set(zip(liga[maska_fs], s.gosp[maska_fs])) | set(zip(liga[maska_fs], s.gosc[maska_fs])):
        kand = pula.get(lg, set())
        # reczna para: cel musi istniec w 365 w tym samym KRAJU (awans/spadek zmienia lige, nie klub)
        kraj_lg = lg.split(' | ')[0]
        w_kraju = set().union(*[v for k, v in pula.items() if k.split(' | ')[0] == kraj_lg]) if pula else set()
        if (lg, t) in _DRUZYNA_FS and _DRUZYNA_FS[(lg, t)] in w_kraju: mapa[(lg, t)] = _DRUZYNA_FS[(lg, t)]; continue
        if t in kand: continue
        nt = _nrm(t)
        rowne = [k for k in kand if _nrm(k) == nt]
        zawiera = [k for k in kand if nt and _nrm(k) and (set(nt) <= set(_nrm(k)) or set(_nrm(k)) <= set(nt))
                   and max(len(w) for w in nt) >= 4]
        wyb = rowne if len(rowne) == 1 else (zawiera if len(zawiera) == 1 else [])
        if not wyb:
            # awans/spadek: identyczny zapis (bez diakrytykow) w innej lidze TEGO SAMEGO kraju = ten sam klub
            rowne_kraj = sorted(k for k in w_kraju if _nrm(k) == nt)
            if len(rowne_kraj) == 1: wyb = rowne_kraj
        if wyb: mapa[(lg, t)] = wyb[0]
        elif kand: nowe.add((lg, t))
    if mapa:
        s = s.copy()
        for col in ('gosp', 'gosc'):
            s.loc[maska_fs, col] = [mapa.get((lg, t), t) for lg, t in zip(liga[maska_fs], s.loc[maska_fs, col])]
        print(f'  zewn: hokej z Flashscore: {len(mapa)} nazw druzyn ujednoliconych do zapisu 365scores.')
    if nowe:
        print(f'  zewn: hokej z Flashscore: {len(nowe)} nazw bez odpowiednika w tej samej lidze 365 '
              f'(nowa druzyna albo inny zapis — sprawdz): ' + ', '.join(f'{t} [{lg}]' for lg, t in sorted(nowe)[:12]))
    return s

def inne():
    """Sporty drużynowe i indywidualne (bez tenisa) → wiersze w formacie sporty_hist (data,sport,liga,gosp,gosc,pg,pa,dogrywka)."""
    s = czytaj('wyniki_*_inne_*.csv')
    if not len(s): return pd.DataFrame()
    # te ligi sa z GitHuba (hist_import: nhl/espn/mlb/nfl/kbo_npb). 23.09.2026: NFL, KBO i NPB nie byly
    # wykluczone i wchodzily DRUGI raz pod innymi nazwami druzyn ("USA | NFL" obok "NFL", "Japan | NPB" obok "NPB").
    s = s[~(s.kraj + ' ' + s.turniej).str.contains(r'\b(?:NHL|NBA|WNBA|MLB|NFL|KBO|NPB)\b')]
    s = _hokej_fs_bez_dubli(s)
    rows = []
    s = s.assign(sport=s.sport.map(lambda x: ALIAS_SPORT.get(x, x)))
    kt = s.kraj + ' ' + s.turniej
    s = s[~kt.str.contains(r'friendl|\bu-?1\d\b|\bu-?2[0-3]\b|youth|junior|juvenil|\bu\d\d\b', case=False)]
    kob = (s.kraj + ' ' + s.turniej).str.contains(r'women|\(w\)|female|femen|feminin|damen|frauen|ladies|wnba|wta', case=False)
    dop = lambda n: n if re.search(r'(?:\(W\)|\(K\)|\bW|\bWomen)$', str(n).strip()) else f'{n} (W)'
    s = s.assign(gosp=np.where(kob, s.gosp.map(dop), s.gosp), gosc=np.where(kob, s.gosc.map(dop), s.gosc))
    for r in s.itertuples():
        if r.sport in ('tennis', 'football'): continue
        pg, pa = pd.to_numeric(r.wg, errors='coerce'), pd.to_numeric(r.wa, errors='coerce')
        sp0 = SPORT[r.sport][0] if r.sport in SPORT else NAZWA_PL.get(r.sport, r.sport.replace('-', ' '))
        if pd.isna(pg) or pd.isna(pa) or sp0 in WYGRANA:
            if str(r.zwyciezca) not in ('1', '2'): continue
            pg, pa = (1, 0) if str(r.zwyciezca) == '1' else (0, 1)
        liga = f'{r.kraj} | {r.turniej}'
        if r.sport == 'esports' and 'league of legends' in _n(r.kraj) and 'lol' != _n(r.kraj): continue   # LoL z lolesports (pełne dane)
        if r.sport == 'esports':
            k = _n(r.kraj + ' ' + r.turniej)
            sp = 'esport_cs2' if 'counter' in k or 'cs2' in k or 'cs:' in k else 'esport_lol' if 'league of legends' in k or 'lol' in k.split() \
                else 'esport_dota' if 'dota' in k else 'esport_val' if 'valorant' in k else 'esport'
            if sp == 'esport_lol':   # w bazie LoL = pojedyncze mapy
                rows += [(r.data, sp, liga, r.gosp, r.gosc, 1, 0, 0)] * int(pg) + [(r.data, sp, liga, r.gosp, r.gosc, 0, 1, 0)] * int(pa)
                continue
            rows.append((r.data, sp, liga, r.gosp, r.gosc, pg, pa, 0)); continue
        sp, nreg = SPORT.get(r.sport, (sp0, 0)); ot = 0
        if nreg:
            try:
                g = [float(x) for x in str(r.okresy_g).split(';') if x != ''][:nreg]; a = [float(x) for x in str(r.okresy_a).split(';') if x != ''][:nreg]
                if len(g) == nreg and len(a) == nreg:
                    ot = 1 if (sum(g) != pg or sum(a) != pa) else 0
                else:
                    # 22.09.2026: BRAK wynikow tercji/kwart to NIE JEST "mecz bez dogrywki", tylko
                    # BRAK INFORMACJI. Wczesniej zostawalo tu 0, czyli "rozstrzygniety w regulaminowym
                    # czasie" — a w hokeju z 365scores pole okresow jest puste dla WSZYSTKICH meczow.
                    # Skutek: statystyka remisow liczyla same zera i P(X) w hokeju wychodzilo 3,1%
                    # dla kazdego meczu, przy rzeczywistych 20-23%. Wartosc -1 wyklucza mecz
                    # ze statystyki remisow (sporty.py to obsluguje), wiec model wraca do prioru.
                    ot = -1
            except ValueError: ot = -1
        rows.append((r.data, sp, liga, r.gosp, r.gosc, pg, pa, ot))
    return pd.DataFrame(rows, columns=['data', 'sport', 'liga', 'gosp', 'gosc', 'pg', 'pa', 'dogrywka'])


# Challengery/WTA125 bez nawierzchni w API: turnieje ziemne (reszta = twarda; trawa tylko czerwiec–lipiec)
ZIEMNE = '''aix en provence bergamo biella bordeaux braga brasov buenos aires cagliari campinas cordoba curitiba
 florianopolis genoa montreux antalya genova guayaquil heilbronn iasi lima lisbon lyon madrid marbella medellin milan modena montevideo
 mestre napoli oeiras olbia orleans? ostrava perugia piracicaba poznan prague praha prostejov rome roma sabadell salzburg
 san marino santa cruz santiago sao leopoldo sao paulo sevilla seville sibiu skopje split szczecin tigre todi trieste tulln
 tunis verona vicenza wroclaw zadar zagreb caldas da rainha bucharest bucuresti la bisbal rabat valencia ljubljana
 bogota barranquilla tampere bastad palermo iasi grodzisk ambato asuncion lima villa maria mar del plata porto alegre
 cordenons san benedetto amersfoort hamburg kitzbuhel umag gstaad kiel meerbusch luedenscheid troisdorf'''.split()
ZIEMNE_S = {w.rstrip('?') for w in ZIEMNE} | {'caldas da rainha', 'la bisbal', 'sao paulo', 'buenos aires', 'san marino', 'santa cruz',
            'sao leopoldo', 'villa maria', 'mar del plata', 'porto alegre', 'san benedetto'}
TRAWIASTE = '''ilkley nottingham surbiton birmingham eastbourne halle queens queen's s-hertogenbosch mallorca newport
 bad homburg berlin wimbledon'''.split()


def _nawierzchnie(glowne=None):
    znane = {}
    try:
        # 23.09.2026 (wyd. 24): z danych glownych przekazanych przez hist_import (TennisCourtLog w pamieci),
        # a NIE z tenis_hist.csv. Ten plik jest WYNIKIEM hist_import — na czystym klonie go nie ma,
        # wiec kazdy automatyczny przebieg (jedno uruchomienie) tracil nawierzchnie i pelne nazwiska.
        th = (glowne[['tourney_name', 'nawierzchnia']] if glowne is not None else
              pd.read_csv(os.path.join(HERE, 'tenis_hist.csv'), usecols=['tourney_name', 'nawierzchnia'], low_memory=False)).dropna()
        th['m'] = th.tourney_name.map(lambda t: _n(re.sub(r'\b(open|challenger|cup|ii|2|125k?|wta|atp|itf)\b', ' ', str(t))).strip())
        znane = th.groupby('m').nawierzchnia.agg(lambda x: x.value_counts().index[0]).replace({'Carpet': 'Hard'}).to_dict()
    except Exception as e:
        # bylo "pass": gdy tenis_hist.csv nie wczytal sie, WSZYSTKIE nawierzchnie stawaly sie nieznane
        # i model tenisowy liczyl dalej bez slowa — cichy spadek jakosci zamiast bledu
        print(f'UWAGA: nawierzchnie z tenis_hist.csv nie wczytane ({e}) — zostaja tylko turnieje z list ZIEMNE/TRAWIASTE.')
    for w in ZIEMNE: znane.setdefault(w.rstrip('?'), 'Clay')
    znane['sao paulo'] = 'Hard'   # WTA 250 São Paulo (wrzesień) — twarda
    for w in TRAWIASTE: znane.setdefault(w, 'Grass')
    return znane


def tenis(max_tcl=None, glowne=None):
    """Tenis z Sofascore (Challenger, ITF, a ATP/WTA po ostatniej dacie TennisCourtLog) → format tenis_hist."""
    s = czytaj('wyniki_*_inne_*.csv')
    if not len(s): return pd.DataFrame()
    s = s[(s.sport == 'tennis') & ~s.gosp.str.contains('/') & ~s.gosc.str.contains('/') & s.zwyciezca.isin(['1', '2'])]
    k = (s.kraj + ' ' + s.turniej).map(_n)
    tour = np.select([k.str.contains('challenger'), k.str.contains('itf') & k.str.contains('women'), k.str.contains('itf'),
                      k.str.contains('wta'), k.str.contains('atp')], ['CH', 'ITF-W', 'ITF', 'WTA', 'ATP'], 'INNE')
    poziom = np.select([k.str.contains('125'), k.str.contains('davis|billie jean|united cup'), k.str.contains('challenger')],
                       ['WTA125', 'DC', 'CH'], tour)
    s = s.assign(tour=tour, poz=poziom)
    s = s[s.tour != 'INNE']
    # krecz/walkower: zwycięzca bez kompletu setów (365 podaje tylko sety) — do bazy Elo nie wchodzi
    wg_, wa_ = pd.to_numeric(s.wg, errors='coerce'), pd.to_numeric(s.wa, errors='coerce')
    s = s[np.maximum(wg_, wa_) >= 2]
    # 22.09.2026: filtr odsiewal duplikaty po TOUR, a nie po POZIOMIE turnieju. TennisCourtLog
    # pokrywa tylko glowny cykl (WTA 1000/500/250, Grand Slam i odpowiedniki ATP), natomiast
    # WTA 125 dostaje tour='WTA' — przez co CALY WTA 125 byl wyrzucany jako "duplikat" czegos,
    # czego w TCL nigdy nie bylo. Zmierzone: z 1 220 wierszy singlowych WTA/WTA 125K do bazy
    # trafialo 13. Dlatego zawodniczki z drabinek 125 mialy zero albo jeden mecz i model
    # wypisywal dla nich "BRAK DANYCH RYWALA". Meski Challenger (tour='CH') filtra nie dotyczyl.
    if max_tcl is not None: s = s[~s.poz.isin(['ATP', 'WTA']) | (pd.to_datetime(s.data) > max_tcl)]
    g = (s.ground.fillna('') if 'ground' in s else s.nawierzchnia.fillna('')) + ' ' + s.turniej.fillna('')   # Flashscore: „Monastir (Tunisia), hard”
    surf = np.where(g.str.contains('clay|ziem|terre', case=False), 'Clay', np.where(g.str.contains('grass|trawa', case=False), 'Grass',
                    np.where(g.str.contains('hard|carpet|indoor', case=False), 'Hard', '')))
    # brak nawierzchni w źródle → z historii turnieju (TennisCourtLog + wcześniejsze pobrania) albo z tabeli NAWIERZCHNIE
    miasto = s.turniej.map(lambda t: _n(re.sub(r'\b(open|challenger|cup|ii|2|125k?|wta|atp|itf|m\d+|w\d+)\b', ' ', str(t))).strip())
    znane = _nawierzchnie(glowne)
    niski = s.poz.isin(['CH', 'WTA125', 'ITF', 'ITF-W']).values   # Challenger/125/ITF: lista ZIEMNE (historia to turnieje główne w tym mieście)
    mies = pd.to_datetime(s.data).dt.month.values
    zg = [('Clay' if m in ZIEMNE_S else 'Hard') if n else znane.get(m, 'Hard') for m, n in zip(miasto, niski)]
    zg = [('Clay' if m in ZIEMNE_S else 'Hard') if z == 'Grass' and mm not in (6, 7) else z for z, m, mm in zip(zg, miasto, mies)]
    surf = np.where(surf != '', surf, zg)
    # LiveScore podaje „Nazwisko I.” — zamiana na pełne imię i nazwisko, gdy JEDNOZNACZNE.
    # 23.09.2026 (wyd. 24, recenzja): kandydaci = dane glowne (TennisCourtLog, przekazane z hist_import)
    # + pelne nazwiska z TYCH SAMYCH plikow 365/Flashscore, z PLCIA i aktywnoscia. Wczesniej lista
    # pochodzila z tenis_hist.csv (wyniku poprzedniego przebiegu, na czystym klonie go nie ma) i nie
    # znala plci: "Wang J." z ITF kobiet rozwijalo sie do "Jimmy Wang", "Rahmani K." z ITF mezczyzn do
    # "Kimia Rahmani", "Estevez J." (ITF-W) do "Juan Estevez". Teraz kandydat musi byc tej samej plci
    # i grac w ciagu 3 lat przed najstarszym meczem z plikow; przy dwoch kandydatach skrot zostaje.
    try:
        PL = {'ATP': 'M', 'CH': 'M', 'ITF': 'M', 'WTA': 'W', 'ITF-W': 'W'}
        if glowne is not None:
            th = glowne[['tour', 'zwyciezca', 'przegrany', 'date']]
        else:
            th = pd.read_csv(os.path.join(HERE, 'tenis_hist.csv'), usecols=['tour', 'zwyciezca', 'przegrany', 'date'], low_memory=False)
        th = th[th.tour.isin(['ATP', 'WTA'])]
        od = pd.to_datetime(s.data).min() - pd.Timedelta(days=3 * 365)
        th = th[pd.to_datetime(th.date) >= od]
        skrot = re.compile(r'^(.+?)\s+([A-Z])\.?(?:-[A-Z]\.)?$')
        # kandydaci: (nazwisko, inicjal, plec) -> {pelna nazwa: 'glowne' albo zbior dat w plikach 365}
        idx = {}
        def _gr(poz): return 'glowny' if poz in ('ATP', 'WTA', 'DC') else 'nizszy'
        def _dodaj(f, pl, dt=None):
            f = str(f)
            if f == 'nan' or skrot.match(f.strip()): return      # skrot nie jest kandydatem na pelne nazwisko
            p = f.split()
            if len(p) < 2 or pl is None: return
            k_ = idx.setdefault((_n(' '.join(p[1:])), _n(p[0])[:1], pl), {})
            if dt is None: k_.setdefault(f, set())
            else: k_.setdefault(f, set()).add(dt)
        for col in ('zwyciezca', 'przegrany'):
            for f, t_ in zip(th[col], th.tour): _dodaj(f, PL.get(t_))
        dat_s = pd.to_datetime(s.data)
        for col in ('gosp', 'gosc'):
            for f, t_, dt, pz in zip(s[col], s.tour, dat_s, s.poz): _dodaj(f, PL.get(t_), (dt, _gr(pz)))
        glowne_n = set(pd.concat([th.zwyciezca, th.przegrany]).astype(str))
        def pelne(n, pl, poz, dt):
            m = skrot.match(str(n).strip())
            if not m: return n
            c = idx.get((_n(m.group(1)), m.group(2).lower(), pl))
            if not c or len(c) != 1: return n
            f, daty = next(iter(c.items()))
            # recenzja (wyd. 24): "jedyny znany" to za malo przy popularnych nazwiskach (Zhang Y. z W35
            # Shenyang -> "Ying Zhang" znana tylko z 4 meczow WTA). Rozwijamy, gdy pelna nazwa gra w TYCH
            # SAMYCH plikach 365/Flashscore na TYM SAMYM poziomie (glowny cykl albo Challenger/125/ITF) lub
            # w ciagu 30 dni, albo gdy skrot pochodzi
            # z turnieju ATP/WTA, a pelna nazwa z danych glownych (ATP/WTA). Inaczej skrot zostaje.
            if any(g == _gr(poz) or abs((dt - x).days) <= 30 for x, g in daty): return f
            if poz in ('ATP', 'WTA') and f in glowne_n: return f
            return n
        plec_s = s.tour.map(PL)
        s = s.assign(gosp=[pelne(n, pl, pz, dt) for n, pl, pz, dt in zip(s.gosp, plec_s, s.poz, dat_s)],
                     gosc=[pelne(n, pl, pz, dt) for n, pl, pz, dt in zip(s.gosc, plec_s, s.poz, dat_s)])
    except Exception as e:
        # bylo "pass": nazwiska zostawaly w formie skroconej "Nowak J.", co psuje pozniejsze dopasowanie
        print(f'UWAGA: rozwijanie skroconych nazwisk tenisistow nie powiodlo sie ({e}) — zostaja skroty.')
    w1 = s.zwyciezca == '1'
    def wynik(a, b, first, n=None):
        A = [x for x in str(a).split(';') if x != '']; B = [x for x in str(b).split(';') if x != '']
        if n: A, B = A[:n], B[:n]   # 365scores: po setach bywa wpis zbiorczy — tylko rozegrane sety (wg+wa)
        return ' '.join(f'{x}-{y}' if first else f'{y}-{x}' for x, y in zip(A, B))
    nset = (pd.to_numeric(s.wg, errors='coerce').fillna(0) + pd.to_numeric(s.wa, errors='coerce').fillna(0)).astype(int)
    score = [wynik(a, b, f, n) for a, b, f, n in zip(s.okresy_g, s.okresy_a, w1, nset)]
    bo = np.where(np.maximum(pd.to_numeric(s.wg, errors='coerce').fillna(0), pd.to_numeric(s.wa, errors='coerce').fillna(0)) >= 3, 5, 3)
    return pd.DataFrame(dict(date=s.data, tour=np.where(s.tour == 'CH', 'ATP', s.tour), tourney_name=s.turniej, poziom=s.poz,
                             nawierzchnia=surf, round=s.runda,
                             best_of=bo, zwyciezca=np.where(w1, s.gosp, s.gosc), przegrany=np.where(w1, s.gosc, s.gosp), score=score))


if __name__ == '__main__':
    p, i, t = pilka(), inne(), tenis()
    print('piłka:', len(p), p.groupby('Division').size().sort_values(ascending=False).head(30).to_dict() if len(p) else '')
    print('inne:', len(i), i.groupby('sport').size().to_dict() if len(i) else '')
    print('tenis:', len(t), t.groupby('tour').size().to_dict() if len(t) else '')
