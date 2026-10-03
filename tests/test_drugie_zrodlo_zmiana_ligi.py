"""03.10.2026 (Raport 21:00 KOREKTA 1) — forma z innej ligi nie jest drugim zrodlem.

Leyma Coruna awansowala z 1ª FEB do ACB: 38 meczow drugiej ligi w bazie wobec jednego w ACB. Model dawal jej
60,6% (Elo zbudowane w 1ª FEB), a `drugie_zrodlo` liczylo forme z `tail(DZ_OKNO)` BEZ WZGLEDU NA LIGE, wiec
„8/10 wygranych” to byly te same mecze drugiej ligi — werdykt ZGODNE powstawal automatycznie. Rynek wycenial
Corune na 46,7%, H2H z Bilbao 0-6.

Bramka jest DOWODOWA (A9: zrodlo ma byc niezalezne), nie kalibracyjna — ZMIANA_LIGI_SPORTY (P124, hokej)
zostaje bez zmian. Tylko odrzuca i zwalnia sie sama po DZ_MIN_MECZOW meczach poza stara liga. Dane syntetyczne.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sporty  # noqa: E402

SPORT = 'koszykówka'
DRUGA, PIERWSZA = 'X | Druga', 'X | Pierwsza'


def _m(w, liga, gosp, gosc, data, wygrywa_gosp):
    w.append(dict(data=pd.Timestamp(data), sport=SPORT, liga=liga, gosp=gosp, gosc=gosc,
                  pg=90 if wygrywa_gosp else 70, pa=70 if wygrywa_gosp else 90, dogrywka=0))


def _baza(meczow_w_nowej=1):
    """Awans: 20 meczow drugiej ligi (16 wygranych, potem 4 porazki), potem `meczow_w_nowej` wygranych w pierwszej.
    Przy 6 meczach w nowej okno 10 ostatnich = 4 porazki + 6 wygranych -> forma 6/10, zgodna z P modelu 60,6%,
    wiec po zwolnieniu bramki drugie zrodlo ma dzialac normalnie (a nie odpadac z innego powodu)."""
    w = []
    for i in range(20):                                     # >= 10 meczow -> zmiana_ligi widzi stara lige
        _m(w, DRUGA, 'Awans', f'D{i % 4 + 1}', '2025-10-01', wygrywa_gosp=i < 16)
        w[-1]['data'] = pd.Timestamp('2025-10-01') + pd.Timedelta(days=10 * i)
    for i in range(21):                                     # pierwsza liga rok wczesniej: INNY komplet druzyn
        _m(w, PIERWSZA, ['P1', 'P2', 'Rywal'][i % 3], 'P9', '2025-10-01', wygrywa_gosp=i % 2 == 0)
        w[-1]['data'] = pd.Timestamp('2025-10-01') + pd.Timedelta(days=10 * i)
    for i in range(meczow_w_nowej):                         # biezacy sezon: Awans juz w pierwszej lidze
        _m(w, PIERWSZA, 'Awans', 'P2', '2026-09-20', wygrywa_gosp=True)
        w[-1]['data'] = pd.Timestamp('2026-09-20') + pd.Timedelta(days=3 * i)
    for i in range(10):                                     # Rywal 5/10 -> log5 nie ucieka w skrajnosc
        _m(w, PIERWSZA, 'Rywal', 'P1', '2026-09-21', wygrywa_gosp=i % 2 == 0)
        w[-1]['data'] = pd.Timestamp('2026-09-21') + pd.Timedelta(days=3 * i)
    return pd.DataFrame(w).sort_values('data').reset_index(drop=True)


def _okno(d, t):
    x = d[d.sport == SPORT]
    return x[(x.gosp == t) | (x.gosc == t)].tail(sporty.DZ_OKNO)


def test_forma_z_drugiej_ligi_nie_jest_drugim_zrodlem():
    d = _baza(meczow_w_nowej=1)
    assert sporty.zmiana_ligi(d, SPORT, 'Awans') == (DRUGA, PIERWSZA, 1)
    z = sporty.forma_z_innej_ligi(d, SPORT, 'Awans', _okno(d, 'Awans'))
    assert z == (DRUGA, PIERWSZA, 1), z
    # caly werdykt drugiego zrodla: brak, mimo ze forma "Awansu" jest swietna (same wygrane w drugiej lidze)
    assert sporty.drugie_zrodlo(d, SPORT, 'Awans', 'Rywal', 0.606) is None


def test_druzyna_bez_zmiany_ligi_nietknieta():
    d = _baza(meczow_w_nowej=1)
    assert sporty.zmiana_ligi(d, SPORT, 'Rywal') is None
    assert sporty.forma_z_innej_ligi(d, SPORT, 'Rywal', _okno(d, 'Rywal')) is None


def test_bramka_zwalnia_sie_po_DZ_MIN_MECZOW_poza_stara_liga():
    """Gdy druzyna rozegra juz DZ_MIN_MECZOW meczow poza stara liga, forma opisuje obecny poziom."""
    d = _baza(meczow_w_nowej=sporty.DZ_MIN_MECZOW)
    assert sporty.zmiana_ligi(d, SPORT, 'Awans') is not None          # wciaz < ZMIANA_LIGI_MIN
    assert sporty.forma_z_innej_ligi(d, SPORT, 'Awans', _okno(d, 'Awans')) is None
    assert sporty.drugie_zrodlo(d, SPORT, 'Awans', 'Rywal', 0.606) is not None


def test_bramka_tylko_odrzuca_i_nie_rusza_kalibracji_hokeja():
    # P130.7: nowe bramki moga tylko ODRZUCAC. Bramka hokejowa z P124 zostaje nietknieta.
    assert sporty.ZMIANA_LIGI_SPORTY == ('hokej',)
    d = _baza(meczow_w_nowej=1)
    assert sporty.drugie_zrodlo(d, SPORT, 'Awans', 'Rywal', 0.606) is None
