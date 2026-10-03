"""Klasyfikacja CALYCH zdarzen z oferty: MATCH / UNKNOWN / CONFLICT + lista dowodow (03.10.2026).

Cel (propozycja uzytkownika 03.10): nie „dopasuj 100% nazw”, tylko „100% zdarzen sklasyfikowanych, 0 blednych MATCH”.
Nazwa druzyny to tylko kandydat — zdarzenie jest MATCH dopiero, gdy PARA pasuje (ten sam mecz w zrodle, wspolna liga
albo wczesniejszy mecz tej pary). Rozpoznawanie nazw zostaje w kodzie produkcyjnym (typuj.resolve — pilka,
sporty.resolve — reszta, osobne reguly dla sportow); ten modul dokłada warstwe ZDARZENIA nad nimi.

TRYB OBSERWACJI: nic w przebiegu ani w typowaniu nie korzysta jeszcze ze stanu. Raport porownuje stan z tym, co robi
kod produkcyjny; dopiero po przegladzie (0 blednych MATCH na prawdziwych danych) stan zablokuje typowanie
CONFLICT/UNKNOWN.

Dowody (kody):
  A_/B_: ALIAS (aliasy.csv / aliasy_auto.csv), DOKLADNA (ta sama nazwa po normalizacji), ROZPOZNANA (inna droga
         resolvera: egzonim, skrot, wariant), BRAK.
  PARA_W_ZRODLE   — w wynikach/terminarzu tego dnia jest mecz dokladnie tej pary (strony mozna zamienic),
  GODZINA         — ...i godzina zgodna co do TOLERANCJA_MIN,
  WSPOLNA_LIGA    — obie druzyny graly w ostatnim roku w tej samej lidze,
  H2H             — para grala ze soba wczesniej (puchary, mecze miedzynarodowe),
  RYWAL_INNY      — (konflikt) rozpoznana druzyna gra tego dnia w zrodle z KIMS INNYM (jedyny mecz tej druzyny w dniu),
                    a pary z oferty w zrodle nie ma — jedna z nazw wskazuje zly klub,
  MOZLIWY_DUBEL   — rywal z meczu w zrodle ma nazwe podobna do drugiej strony, ale to INNY wpis w bazie: ten sam klub
                    pod dwiema nazwami ALBO pomylony klub; bez WSPOLNA_LIGA/H2H -> CONFLICT,
  TA_SAMA_DRUZYNA — (konflikt) obie nazwy rozpoznane jako ten sam wpis.
Stan: UNKNOWN gdy ktorakolwiek strona BRAK; CONFLICT gdy jest dowod konfliktu; MATCH gdy jest dowod pary;
inaczej UNKNOWN (BRAK_DOWODU_PARY).

Uzycie:  python3 zdarzenia.py KURSY.csv.gz [--zewn zewn] [--csv wynik.csv]"""
import collections
import contextlib
import functools
import io
import os
import sys

import pandas as pd

import dopasuj
import nazwy

TOLERANCJA_MIN = dopasuj.TOLERANCJA_MIN
STANY = ('MATCH', 'UNKNOWN', 'CONFLICT')


def _klucz(n):
    return ''.join(dopasuj.tokeny(n)) or str(n).lower()


@functools.lru_cache(maxsize=None)
def _czlony(n):
    return frozenset(w for w in dopasuj.tokeny(n) if len(w) >= 3)


def _sposob(S, n, e, jest_alias):
    """Jak nazwa z oferty trafila do bazy (dowod na poziomie druzyny)."""
    if e is None: return 'BRAK'
    if jest_alias(S, n): return 'ALIAS'
    if n == e or _klucz(n) == _klucz(e): return 'DOKLADNA'
    return 'ROZPOZNANA'


def klasyfikuj(ev, z, rozwiaz, pule, ligi=None, h2h=None, jest_alias=lambda S, n: False):
    """ev: dopasuj.zdarzenia_sts (S, d, t, dni, A, B); z: dopasuj.zrodla (S, d, t, gosp, gosc, zrodlo);
    rozwiaz(S, nazwa) -> wpis z puli albo None; pule: {S: zbior}; ligi: {(S, druzyna): {ligi}} (dopasuj.ligi_druzyn);
    h2h: zbior (S, frozenset({a, b})) par, ktore graly ze soba; jest_alias(S, nazwa) -> bool. Zwraca DataFrame: S, d, A, B, eA, eB, stan, dowody."""
    ligi, h2h = ligi or {}, h2h or set()
    pam = {}

    def ent(S, n):
        if (S, n) not in pam:
            pam[(S, n)] = n if n in pule.get(S, ()) else (rozwiaz(S, n) if S in pule else None)
        return pam[(S, n)]

    pod_dniu = collections.defaultdict(list)
    for x in z.itertuples(index=False): pod_dniu[(x.S, x.d)].append(x)
    out = []
    for r in ev.itertuples(index=False):
        eA, eB = ent(r.S, r.A), ent(r.S, r.B)
        dow = [f'A_{_sposob(r.S, r.A, eA, jest_alias)}', f'B_{_sposob(r.S, r.B, eB, jest_alias)}']
        if eA is None or eB is None:
            out.append((r.S, r.d, r.A, r.B, eA, eB, 'UNKNOWN', ';'.join(dow))); continue
        if eA == eB:
            out.append((r.S, r.d, r.A, r.B, eA, eB, 'CONFLICT', ';'.join(dow + ['TA_SAMA_DRUZYNA']))); continue
        # tylko mecze, w ktorych ktoras strona ma wspolny czlon z nazwami zdarzenia — resolver dla tysiecy nazw
        # ze zrodel z calego dnia to ok. 5 min na przebieg; pozostale mecze i tak nie moga byc dowodem
        cz = {w for n in (r.A, r.B, eA, eB) for w in _czlony(n)}
        mecze = [x for d in r.dni for x in pod_dniu.get((r.S, d), []) if cz & (_czlony(x.gosp) | _czlony(x.gosc))]
        para = {eA, eB}
        w_zrodle = [x for x in mecze if {ent(r.S, x.gosp), ent(r.S, x.gosc)} == para]
        if w_zrodle:
            dow.append('PARA_W_ZRODLE')
            if pd.notna(r.t) and any(pd.notna(x.t) and abs((x.t - r.t).total_seconds()) <= TOLERANCJA_MIN * 60 for x in w_zrodle):
                dow.append('GODZINA')
        else:
            # jedyny mecz rozpoznanej druzyny tego dnia jest z innym, ROZPOZNANYM rywalem -> jedna z nazw wskazuje zly klub
            for e in (eA, eB):
                inne = [x for x in mecze if e in (ent(r.S, x.gosp), ent(r.S, x.gosc))]
                if len(inne) == 1:
                    x = inne[0]
                    rywal = ent(r.S, x.gosc) if ent(r.S, x.gosp) == e else ent(r.S, x.gosp)
                    if rywal is not None and rywal not in para:
                        drugi = eB if e == eA else eA
                        # MOZE to byc ten sam klub pod dwiema nazwami w bazie („Troja/Ljungby” / „If Troja/Ljungby”),
                        # ale rownie dobrze INNY klub o podobnej nazwie (przeglad 03.10: „San Antonio FC” z USA zamiast
                        # ekwadorskiego San Antonio; „Zaglebie Lubin W” z I ligi zamiast „Zaglebie W” z Superligi).
                        # Bez wspolnej ligi ani H2H to CONFLICT, nie MATCH.
                        if nazwy.znaczniki(rywal) == nazwy.znaczniki(drugi) and (
                                dopasuj._rdzen_pasuje(dopasuj.tokeny(rywal), dopasuj.tokeny(drugi)) or dopasuj.podobne(rywal, drugi)):
                            dow.append(f'MOZLIWY_DUBEL:{drugi}={rywal}')
                        else:
                            dow.append(f'RYWAL_INNY:{e}~{rywal}')
                        break
        if ligi.get((r.S, eA), set()) & ligi.get((r.S, eB), set()): dow.append('WSPOLNA_LIGA')
        if (r.S, frozenset(para)) in h2h: dow.append('H2H')
        if any(d.startswith('RYWAL_INNY') for d in dow) and 'PARA_W_ZRODLE' not in dow: stan = 'CONFLICT'
        elif any(d.startswith('MOZLIWY_DUBEL') for d in dow) and not {'WSPOLNA_LIGA', 'H2H'} & set(dow): stan = 'CONFLICT'
        elif {'PARA_W_ZRODLE', 'WSPOLNA_LIGA', 'H2H'} & set(dow): stan = 'MATCH'
        else: stan, dow = 'UNKNOWN', dow + ['BRAK_DOWODU_PARY']
        out.append((r.S, r.d, r.A, r.B, eA, eB, stan, ';'.join(dow)))
    return pd.DataFrame(out, columns=['S', 'd', 'A', 'B', 'eA', 'eB', 'stan', 'dowody'])


def _h2h(dni=730):
    """Pary, ktore graly ze soba w ostatnich `dni` (pilka z kb.sqlite, reszta z sporty.load())."""
    with contextlib.redirect_stdout(io.StringIO()):
        import typuj
        import sporty
        od = pd.Timestamp.today() - pd.Timedelta(days=dni)
        m = pd.read_sql('select MatchDate, HomeTeam, AwayTeam from matches', typuj.db(), parse_dates=['MatchDate'])
        m = m[m.MatchDate >= od]
        out = {('pilka', frozenset((a, b))) for a, b in zip(m.HomeTeam, m.AwayTeam)}
        d = sporty.load()
        d = d[d.data >= od]
        odwr = {sporty.nazwa_sportu(s): s for s in set(dopasuj.SPORT_STS.values()) - {'pilka'}}
        for s, a, b in zip(d.sport, d.gosp, d.gosc):
            if s in odwr: out.add((odwr[s], frozenset((a, b))))
    return out


def raport(k):
    """Linie do raportu przebiegu: stany ogolem i per sport, konflikty z dowodem."""
    linie = ['ZDARZENIA (tryb obserwacji): ' + ', '.join(f'{s} {int((k.stan == s).sum())}' for s in STANY) + f' z {len(k)}']
    for S, g in k.groupby('S'):
        linie.append(f'  {S:<14} ' + ', '.join(f'{s} {int((g.stan == s).sum())}' for s in STANY))
    for r in k[k.stan == 'CONFLICT'].itertuples(index=False):
        linie.append(f'  CONFLICT {r.S} {r.d.date()} {r.A} - {r.B} -> {r.eA} - {r.eB} [{r.dowody}]')
    roz = sorted({d.split(':', 1)[1] for x in k.dowody for d in x.split(';') if d.startswith('MOZLIWY_DUBEL:')})
    if roz: linie.append(f'  MOZLIWE DUBLE w bazie (ten sam klub pod dwiema nazwami albo pomylony klub — do przegladu): {len(roz)} — '
                         + '; '.join(roz[:30]))
    return linie


def main(a):
    if not a: print(__doc__); return 1
    zd = a[a.index('--zewn') + 1] if '--zewn' in a else 'zewn'
    ev = dopasuj.zdarzenia_sts(pd.read_csv(a[0], dtype=str))
    z = dopasuj.zrodla(zd)
    rozwiaz, pule = dopasuj._produkcja()
    ligi = dopasuj.ligi_druzyn(dopasuj._mecze_lig())
    with contextlib.redirect_stdout(io.StringIO()):
        import typuj
        import sporty
    reczne = {}
    for plik in (nazwy.ALIASY_CSV, nazwy.ALIASY_AUTO_CSV):
        if os.path.exists(plik):
            x = pd.read_csv(plik, dtype=str)
            for m, n in zip(x.modul, x.nazwa): reczne.setdefault(m, set()).add(n)
    tk = {typuj.norm(n) for n in reczne.get('typuj', ())} | set(typuj.ALIASES)
    sk = {sporty.norm(n) for n in reczne.get('sporty', ())} | {sporty.norm(n) for n in getattr(sporty, '_ALIASY_RECZNE', {})}
    jest_alias = lambda S, n: (typuj.norm(n) in tk) if S == 'pilka' else (sporty.norm(n) in sk)
    k = klasyfikuj(ev, z, rozwiaz, pule, ligi, _h2h(), jest_alias)
    if '--csv' in a: k.to_csv(a[a.index('--csv') + 1], index=False)
    print('\n'.join(raport(k)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
