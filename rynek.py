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


def filtr_model_rynek(k, p, kursy):
    """KROK 6.4. Zwraca powod odrzucenia albo None.
    Brak kursu dopelniajacego = brak filtra (nie blokujemy nogi w ciemno)."""
    pr = p_rynku(k, kursy)
    if pr is None: return None
    d = p - pr
    if abs(d) <= MAX_ROZBIEZNOSC_RYNEK: return None
    return (f'FILTR MODEL-RYNEK (6.4): P do kuponu {p:.1%} vs P rynku {pr:.1%} po zdjeciu marzy '
            f'— rozbieznosc {d * 100:+.1f} pp, prog {MAX_ROZBIEZNOSC_RYNEK * 100:.0f} pp')


def kursy_z_argv(a):
    """Wyciaga '--kurs RYNEK=KURS' z listy argumentow. Zwraca (reszta_argumentow, {rynek: kurs})."""
    kursy, reszta, i = {}, [], 0
    while i < len(a):
        if a[i] == '--kurs' and i + 1 < len(a):
            k, _, v = a[i + 1].partition('=')
            try: kursy[k] = float(v)
            except ValueError: pass
            i += 2
        else:
            reszta.append(a[i]); i += 1
    return reszta, kursy
