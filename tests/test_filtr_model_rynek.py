"""03.10.2026 — naprawa po Raportach 2026-10-03 15:00 i 18:00.

Dwa defekty tej samej rodziny: kod wypisywal "NOGA DOPUSZCZONA" z wysokim EV na danych,
ktore tego EV nie moga udzwignac.

1) FILTR MODEL-RYNEK (KROK 6.4) nie istnial w kodzie — byl wylacznie krokiem recznym.
2) "Drugie zrodlo — forma" liczylo sie z tych samych nieswiezych meczow co model,
   wiec przy druzynie bez meczu od miesiecy zawsze wychodzilo ZGODNE (A9 spelnione pozornie).
"""
import datetime as dt

import pytest

import typuj


# ---------------------------------------------------------------- p_rynku / filtr 6.4

def test_p_rynku_zdejmuje_marze_1x2():
    """Rynek 1X2 z realnej oferty 03.10 (Le Puy): ksiega 109,5%, P rynku dla X2 = 48,4%."""
    kursy = {'1': 1.77, 'X': 3.50, '2': 4.10}
    p1 = typuj.p_rynku('1', kursy)
    assert p1 == pytest.approx(0.5166, abs=0.002)
    assert sum(typuj.p_rynku(k, kursy) for k in ('1', 'X', '2')) == pytest.approx(1.0, abs=1e-9)


def test_p_rynku_podwojna_szansa():
    """X2 dopelnia sie z 1 — ksiega z tej pary, nie z calej trojki."""
    kursy = {'1': 1.77, 'X2': 1.888}
    assert typuj.p_rynku('X2', kursy) == pytest.approx(0.4834, abs=0.005)


def test_p_rynku_bez_dopelnienia_zwraca_none():
    """Brak kursu dopelniajacego = nie liczymy ksiegi i NIE blokujemy nogi w ciemno."""
    assert typuj.p_rynku('X2', {'X2': 1.85}) is None
    assert typuj.p_rynku('rynek_spoza_listy', {'rynek_spoza_listy': 2.0}) is None


def test_filtr_odrzuca_przypadek_le_puy():
    """Le Puy - Lusitanos 03.10: model X2 69,3% vs rynek 48,4% = 20,9 pp > 15 pp."""
    kursy = {'1': 1.77, 'X': 3.50, '2': 4.10, 'X2': 1.888}
    powod = typuj.filtr_model_rynek('X2', 0.6934, kursy)
    assert powod is not None
    assert 'FILTR MODEL-RYNEK (6.4)' in powod
    assert '+20.9 pp' in powod or '+21.0 pp' in powod


def test_filtr_przepuszcza_zgodne_z_rynkiem():
    """Noga blisko rynku przechodzi — filtr ma odrzucac artefakty, nie kazda przewage."""
    kursy = {'1': 1.77, 'X': 3.50, '2': 4.10}
    assert typuj.filtr_model_rynek('1', 0.56, kursy) is None      # +4,3 pp
    assert typuj.filtr_model_rynek('1', 0.66, kursy) is None      # +14,3 pp, tuz pod progiem


def test_filtr_dziala_w_obie_strony():
    """Model DUZO nizszy od rynku to tez rozbieznosc — np. hokej liczony na zlym rynku."""
    kursy = {'1': 1.10, 'X': 9.00, '2': 11.0}
    powod = typuj.filtr_model_rynek('1', 0.55, kursy)
    assert powod is not None and '-' in powod


def test_filtr_nie_dopuszcza_nogi_ktorej_werdykt_odrzucil():
    """Filtr tylko odrzuca: dla kazdego P zwraca None albo powod, nigdy 'mozna grac'."""
    kursy = {'1': 1.77, 'X': 3.50, '2': 4.10}
    for p in (0.01, 0.3, 0.5, 0.7, 0.99):
        assert typuj.filtr_model_rynek('1', p, kursy) in (None,) or isinstance(
            typuj.filtr_model_rynek('1', p, kursy), str)


# ---------------------------------------------------------------- swiezosc drugiego zrodla

def _mecze(ostatni_dzien, t='A', rywal='B', n=10):
    """n meczow druzyny t konczacych sie ostatni_dzien (co 7 dni wstecz)."""
    return [(ostatni_dzien - dt.timedelta(days=7 * i), t, rywal, 1, 0) for i in range(n - 1, -1, -1)]


def test_drugie_zrodlo_odrzuca_nieswieza_druzyne(capsys):
    """Lusitanos: ostatni mecz 140 dni temu. Forma z tych samych meczow nie jest druga opinia."""
    dzis = dt.date.today()
    w = _mecze(dzis - dt.timedelta(days=5), 'Le Puy', 'X') + _mecze(dzis - dt.timedelta(days=140), 'Lusitanos', 'Y')
    rows = [('X2', 0.708, 0.6934)]
    assert typuj.drugie_zrodlo(w, 'Le Puy', 'Lusitanos', rows) == {}
    out = capsys.readouterr().out
    assert 'BRAK DRUGIEGO ZRODLA' in out and 'Lusitanos' in out and '140 dni' in out


def test_drugie_zrodlo_odrzuca_salisbury(capsys):
    """Raport 15:00: Salisbury, ostatni mecz 2014-04-26 (4543 dni) — EV +19,5% z danych sprzed 12 lat."""
    dzis = dt.date.today()
    w = _mecze(dzis - dt.timedelta(days=3), 'Dulwich', 'X') + _mecze(dt.date(2014, 4, 26), 'Salisbury', 'Y')
    assert typuj.drugie_zrodlo(w, 'Salisbury', 'Dulwich', [('X2', 0.66, 0.662)]) == {}
    assert 'BRAK DRUGIEGO ZRODLA' in capsys.readouterr().out


def test_drugie_zrodlo_przepuszcza_swieze_druzyny():
    """Obie druzyny graly w ostatnich dniach — drugie zrodlo dziala jak dotad."""
    dzis = dt.date.today()
    w = _mecze(dzis - dt.timedelta(days=4), 'A', 'X') + _mecze(dzis - dt.timedelta(days=6), 'B', 'Y')
    wynik = typuj.drugie_zrodlo(w, 'A', 'B', [('1X', 0.70, 0.70)])
    assert wynik != {}


def test_prog_swiezosci_jest_zgodny_z_A1a():
    """A1(a): druzyna NIESWIEZA to > 60 dni. Prog w kodzie nie moze byc luzniejszy."""
    assert typuj.MAX_WIEK_FORMY_DNI <= 60


def test_prog_rozbieznosci_jest_zgodny_z_6_4():
    """KROK 6.4 instrukcji v7: rozbieznosc > 15 pp -> odrzuc."""
    assert typuj.MAX_ROZBIEZNOSC_RYNEK <= 0.15


def test_na_date_przyjmuje_rozne_typy():
    assert typuj._na_date(dt.date(2026, 5, 16)) == dt.date(2026, 5, 16)
    assert typuj._na_date(dt.datetime(2026, 5, 16, 20, 45)) == dt.date(2026, 5, 16)
    assert typuj._na_date('2026-05-16') == dt.date(2026, 5, 16)
    assert typuj._na_date('2026-05-16 20:45:00') == dt.date(2026, 5, 16)
    assert typuj._na_date(None) is None
    assert typuj._na_date('nie data') is None
