"""Filtr model-rynek (KROK 6.4 instrukcji v7) — wspolny dla typuj.py i sporty.py.

03.10.2026. Do tej pory 6.4 istnial WYLACZNIE jako krok reczny w instrukcji
("P do kuponu vs P z kursu w aplikacji; rozbieznosc > 15 pp utrzymana -> odrzuc")
i w zadnym przebiegu nie byl wykonywany przez kod: kursy sluzyly tylko do EV,
kursu sprawiedliwego i Kelly'ego.

Nogi z Raportow 2026-10-03, ktore okazaly sie artefaktem danych, a nie przewaga —
kazda lamala ten prog:
  Le Puy - Lusitanos X2        model 69,3% vs rynek 48,4%  (20,9 pp)  gosc bez meczu od 140 dni
  Salisbury - Dulwich Hamlet   model 66,2%, EV +19,5%                 dane goscia z 2014 r.
  EHC Chur - EHC Arosa         P "z dogrywka" kontra rynek 1X2        falszywe EV +22...+23%
  Vitoria SC - FC Porto        model 42,0% vs rynek 5,7%   (36,3 pp)  brak danych rywala

Filtr tylko ODRZUCA nogi — nie jest w stanie zadnej dopuscic (A2: progi wolno
zaostrzac, nie luzowac).
"""

import re

MAX_ROZBIEZNOSC_RYNEK = 0.15

# Rynki dopelniajace sie do 1 — po nich liczymy ksiege (overround) i zdejmujemy marze.
# Z1/Z2 = "Zwyciezca meczu" (wynik koncowy, z dogrywka) w sportach, w ktorych 1/X/2 to czas regulaminowy.
DOPELNIENIA = {'1': ('X', '2'), 'X': ('1', '2'), '2': ('1', 'X'),
               '1X': ('2',), 'X2': ('1',), '12': ('X',),
               'Z1': ('Z2',), 'Z2': ('Z1',),
               'O0.5': ('U0.5',), 'U0.5': ('O0.5',), 'O1.5': ('U1.5',), 'U1.5': ('O1.5',),
               'O2.5': ('U2.5',), 'U2.5': ('O2.5',), 'O3.5': ('U3.5',), 'U3.5': ('O3.5',),
               'O4.5': ('U4.5',), 'U4.5': ('O4.5',),
               'BTTS_tak': ('BTTS_nie',), 'BTTS_nie': ('BTTS_tak',),
               'DNB_1': ('DNB_2',), 'DNB_2': ('DNB_1',)}


def p_rynku(k, kursy):
    """P rynku po zdjeciu marzy. None, gdy nie da sie policzyc ksiegi (brak kursu dopelnienia)."""
    reszta = DOPELNIENIA.get(k)
    if reszta is None or not kursy or k not in kursy: return None
    try:
        if float(kursy[k]) <= 1 or not all(x in kursy and float(kursy[x]) > 1 for x in reszta): return None
        ksiega = 1 / float(kursy[k]) + sum(1 / float(kursy[x]) for x in reszta)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return (1 / float(kursy[k])) / ksiega if ksiega > 0 else None


def p_rynku_szacunek(k, kursy):
    """04.10.2026 (Raport 18:00 usterka 7): Portugalia – Norwegia U3.5 podana BEZ O3.5 -> p_rynku None -> filtr wylaczony
    -> ✔ EV +11,2%; z O3.5 ta sama noga odpadala (+17,3 pp). Lista meczow przebiegu podaje kursy z KEY_MARKETS, gdzie
    nie ma O3.5/O4.5, wiec filtr po cichu nie dzialal na rynkach „ponizej”. Gdy brak dopelnienia, ksiege bierzemy z rynku
    glownego tego samego meczu (1/X/2 albo Z1/Z2) — marza STS na rynkach O/U i 1X2 rozni sie o kilka punktow, a filtr
    ma prog 15 pp. Zwraca None, gdy rynku glownego tez nie ma.
    05.10.2026 (K5-1200, Gwadelupa – Saint Lucia gosp_O0.5): rynki spoza DOPELNIENIA (gol druzyny, HT, pierwszy gol)
    w ogole nie mialy filtra — model 87,5%, rynek 69% (1,33 / 3,00), noga weszla do K5. Teraz ksiega z rynku glownego
    dziala dla KAZDEGO rynku z kursem (filtr tylko odrzuca, wiec szerszy zakres moze najwyzej zabrac noge — A2)."""
    if not kursy or k not in kursy: return None
    for glowny in (('1', 'X', '2'), ('Z1', 'Z2')):
        try:
            if float(kursy[k]) > 1 and all(x in kursy and float(kursy[x]) > 1 for x in glowny):
                ksiega = sum(1 / float(kursy[x]) for x in glowny)
                if ksiega >= 1: return (1 / float(kursy[k])) / ksiega
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    return None


# 06.10.2026 (bt_ou35.py, docs/BACKTEST_P48.md): na rynku 3.5 gola kurs przewiduje lepiej niz model — 86 534 mecze
# klubowe: gdy model daje >= 5 pp wiecej niz rynek, wchodzi tyle, ile mowi rynek (58,8% przy P modelu 68,0%); mieszanka
# model+rynek najlepsza przy wadze modelu 0. Reprezentacje: przy duzej przewadze Elo model przeszacowuje gole.
RYNKI_ZA_RYNKIEM = ('U3.5', 'O3.5')


def p_kuponu_wg_rynku(k, p, kursy):
    """P do kuponu dla rynkow z RYNKI_ZA_RYNKIEM = min(P modelu, P rynku bez marzy). Zwraca (P, uwaga albo None).
    Tylko obniza (A2) — gdy rynek daje wiecej albo nie da sie go policzyc, zostaje P modelu."""
    if k not in RYNKI_ZA_RYNKIEM: return p, None
    pr = p_rynku(k, kursy)
    if pr is None: pr = p_rynku_szacunek(k, kursy)
    if pr is None or pr >= p: return p, None
    return pr, f'P rynku {pr:.1%} < P modelu {p:.1%} — na {k} liczy sie mniejsze (bt_ou35: rynek trafniejszy)'


def filtr_model_rynek(k, p, kursy):
    """KROK 6.4. Zwraca powod odrzucenia albo None.
    Brak kursu dopelniajacego: ksiega z rynku glownego meczu (p_rynku_szacunek); gdy i tego brak — brak filtra
    (nie blokujemy nogi w ciemno)."""
    pr, skad = p_rynku(k, kursy), 'po zdjeciu marzy'
    if pr is None:
        pr, skad = p_rynku_szacunek(k, kursy), 'po zdjeciu marzy rynku glownego (brak kursu dopelnienia)'
    if pr is None: return None
    d = p - pr
    if abs(d) <= MAX_ROZBIEZNOSC_RYNEK: return None
    return (f'FILTR MODEL-RYNEK (6.4): P do kuponu {p:.1%} vs P rynku {pr:.1%} {skad} '
            f'— rozbieznosc {d * 100:+.1f} pp, prog {MAX_ROZBIEZNOSC_RYNEK * 100:.0f} pp')


def kod_rynku(k):
    """05.10.2026 (Raport 18:00, usterka 4): „--kurs gosc_O0.5=1.65” (bez ogonka) dawalo „gosc_O0.5: brak rynku”
    bez ostrzezenia — model zna tylko „gość_O0.5”. Ten sam zapis ASCII rozlicza juz dzienniki.rynek_pilka."""
    return re.sub(r'(?i)^go[sś][cć]_', 'gość_', str(k).strip())


def kursy_z_argv(a):
    """Wyciaga '--kurs RYNEK=KURS' z listy argumentow. Zwraca (reszta_argumentow, {rynek: kurs})."""
    kursy, reszta, i = {}, [], 0
    while i < len(a):
        if a[i] == '--kurs' and i + 1 < len(a):
            k, _, v = a[i + 1].partition('=')
            k = kod_rynku(k)
            try: kursy[k] = float(v)
            except ValueError: pass
            i += 2
        else:
            reszta.append(a[i]); i += 1
    return reszta, kursy
