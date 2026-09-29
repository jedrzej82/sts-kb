#!/usr/bin/env python3
"""Rejestr aliasow — wszystkie reczne tabele nazw z kodu w JEDNEJ liscie (faza 3, audyt 29.09.2026).
  python3 rejestr.py              — wypisuje podsumowanie i sprzecznosci, zapisuje rejestr_aliasow.csv
  python3 rejestr.py --konflikty  — tylko sprzecznosci (klucz -> rozne kluby w roznych tabelach)

Po co: aliasy siedza w ~17 tabelach w 8 modulach (build_kb, uzupelnij_ligi, kluby, typuj, sporty, sezon,
tenis, zewn). Ta sama nazwa bywa poprawiana w 2-4 miejscach, a kopie sie rozjezdzaja. Rejestr jest krokiem
do jednego zrodla danych: najpierw widac calosc i sprzecznosci, potem tabele przenosi sie do pliku danych.

SPRZECZNOSC = ten sam klucz nazwy zrodlowej wskazuje w dwoch tabelach cele o ROZNYCH kluczach, z ktorych
zaden nie zawiera drugiego (np. "olympiakos" -> "Olympiakos" w typuj i "Olympiacos" w sporty to rozne
zapisy, ale tego samego klubu — trafia do przegladu). Znane i sprawdzone sprzecznosci sa w
rejestr_konflikty_znane.csv; test w CI zglasza tylko NOWE."""
import os
import re
import sys
import unicodedata

import pandas as pd

from nazwy import LITERY

HERE = os.path.dirname(os.path.abspath(__file__))
ZNANE = os.path.join(HERE, 'rejestr_konflikty_znane.csv')


def klucz(s):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(s).translate(LITERY))
                  .encode('ascii', 'ignore').decode().lower())


def zbierz():
    """Wiersze: tabela, zakres (liga/kraj/sport albo ''), nazwa (zrodlowa), klucz, cel."""
    import build_kb, uzupelnij_ligi, kluby, typuj, sporty, sezon, tenis, zewn
    w = []

    def dodaj(tabela, d, zakres=''):
        for n, c in d.items():
            if isinstance(n, tuple): zakres, n = n[0], n[1]   # (liga, nazwa[, okres]) — kluby.py, zewn.py
            w.append((tabela, str(zakres), str(n), klucz(n), str(c)))

    dodaj('build_kb.ALIAS', build_kb.ALIAS)
    for lg, d in uzupelnij_ligi.ALIAS2.items(): dodaj('uzupelnij_ligi.ALIAS2', d, lg)
    dodaj('uzupelnij_ligi.ALIAS_ZEWN', uzupelnij_ligi.ALIAS_ZEWN)
    dodaj('kluby.SCAL_RECZNIE', kluby.SCAL_RECZNIE)
    dodaj('typuj.ALIASES', typuj.ALIASES)
    dodaj('typuj.ALIASES_KLUBY', typuj.ALIASES_KLUBY)
    dodaj('sporty._ALIASY_RECZNE', sporty._ALIASY_RECZNE)
    dodaj('sezon._ALIASY_PILKA', sezon._ALIASY_PILKA)
    dodaj('tenis._LITEROWKI_STS', tenis._LITEROWKI_STS)
    dodaj('zewn._DRUZYNA_FS', zewn._DRUZYNA_FS)
    return pd.DataFrame(w, columns=['tabela', 'zakres', 'nazwa', 'klucz', 'cel'])


def _zgodne(a, b):
    ka, kb = klucz(a), klucz(b)
    return ka == kb or (min(len(ka), len(kb)) >= 4 and (ka in kb or kb in ka))


def konflikty(r):
    """Klucz nazwy zrodlowej -> rozne cele (z roznych tabel), bez zakresu ligi (ALIAS2 per liga pomijamy:
    ta sama nazwa w dwoch ligach moze oznaczac dwa kluby)."""
    x = r[r.tabela != 'uzupelnij_ligi.ALIAS2']
    out = []
    for k, g in x.groupby('klucz'):
        cele = sorted(set(g.cel))
        if len(cele) < 2: continue
        rozne = [(a, b) for i, a in enumerate(cele) for b in cele[i + 1:] if not _zgodne(a, b)]
        if rozne:
            out.append((k, ' | '.join(f'{t}: {c}' for t, c in sorted(set(zip(g.tabela, g.cel))))))
    return pd.DataFrame(out, columns=['klucz', 'cele'])


def nowe_konflikty(r=None):
    k = konflikty(zbierz() if r is None else r)
    znane = set(pd.read_csv(ZNANE).klucz) if os.path.exists(ZNANE) else set()
    return k[~k.klucz.isin(znane)]


def main(a):
    r = zbierz()
    k = konflikty(r)
    if '--konflikty' not in a:
        print(f'Rejestr: {len(r)} wpisow w {r.tabela.nunique()} tabelach')
        print(r.groupby('tabela').size().to_string())
        r.to_csv(os.path.join(HERE, 'rejestr_aliasow.csv'), index=False)
        print('zapisano rejestr_aliasow.csv')
    print(f'\nSPRZECZNOSCI (ten sam klucz -> rozne kluby): {len(k)}')
    for row in k.itertuples(): print(f'  {row.klucz}: {row.cele}')
    n = nowe_konflikty(r)
    if len(n): print(f'\nNOWE (spoza rejestr_konflikty_znane.csv): {len(n)} — ' + ', '.join(n.klucz))


if __name__ == '__main__':
    main(sys.argv[1:])
