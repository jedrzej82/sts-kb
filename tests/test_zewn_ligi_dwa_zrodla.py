"""04.10.2026 (P133.6) — ta sama liga pod dwiema nazwami w DWOCH ZRODLACH.

365scores i Flashscore nazywaja te same rozgrywki inaczej: „Spain | 1ª FEB” / „SPAIN | Primera FEB”,
„Germany | Bundesliga” / „GERMANY | BBL”, „France | Lidl Starligue” / „FRANCE | Starligue”. Baza dostawala
wtedy DWIE ligi zamiast jednej, a zmiana_ligi() widziala w tym awans albo spadek (Cb Zamora dostawalo bramke
z P133, choc nigdzie nie awansowalo). _scal_nazwy_rozgrywek tego nie lapie — dziala wewnatrz jednego zrodla.

Sygnal jest strukturalny: liga FS = liga 365, gdy lacza je POTWIERDZONE DUBLE (ten sam mecz w obu zrodlach).
"""
import pandas as pd

import zewn

KOL = 'data,sport,kraj,turniej,runda,gosp,gosc,wg,wa,okresy_g,okresy_a,zwyciezca,nawierzchnia'.split(',')


def _w(data, sport, kraj, tur, g, a, wg, wa):
    return [data, sport, kraj, tur, '', g, a, wg, wa, '', '', 1 if wg > wa else 2, '']


def _fs(turniej, n):
    """n wierszy FS w danej lidze (tylko kolumny, ktorych uzywa _fsx_mapa_lig)."""
    return pd.DataFrame([dict(sport='basketball', kraj='SPAIN', turniej=turniej) for _ in range(n)])


def test_mapa_lig_jeden_odpowiednik_i_dosc_dubli():
    fs = _fs('Primera FEB', 3)
    pary = {('basketball', 'SPAIN', 'Primera FEB'): {('Spain', '1ª FEB'): 2}}
    assert zewn._fsx_mapa_lig(fs, pary) == {('basketball', 'SPAIN', 'Primera FEB'): ('Spain', '1ª FEB')}


def test_mapa_lig_jeden_wspolny_mecz_to_za_malo():
    """Regresja z _scal_nazwy_rozgrywek: jeden wspolny mecz (baraz) sklejal II lige z I."""
    fs = _fs('Primera FEB', 10)
    pary = {('basketball', 'SPAIN', 'Primera FEB'): {('Spain', '1ª FEB'): 1}}
    assert zewn._fsx_mapa_lig(fs, pary) == {}
    # takze gdy dubli jest >= 2, ale to mniej niz polowa meczow ligi FS
    assert zewn._fsx_mapa_lig(fs, {('basketball', 'SPAIN', 'Primera FEB'): {('Spain', '1ª FEB'): 2}}) == {}


def test_mapa_lig_kilka_celow_nie_zgadujemy():
    fs = _fs('Primera FEB', 4)
    pary = {('basketball', 'SPAIN', 'Primera FEB'): {('Spain', '1ª FEB'): 3, ('Spain', 'ACB'): 3}}
    assert zewn._fsx_mapa_lig(fs, pary) == {}


def test_mapa_lig_eliminacje_nie_sa_rozgrywkami_glownymi():
    """Sam PUCHAR zawiera „women”, wiec nie odroznia eliminacji od turnieju glownego — stad PUCHAR_WLASCIWY."""
    fs = pd.DataFrame([dict(sport='basketball', kraj='EUROPE', turniej='Euroleague Women - Qualification')] * 2)
    pary = {('basketball', 'EUROPE', 'Euroleague Women - Qualification'): {('Europe', 'Euroleague Women'): 2}}
    assert zewn._fsx_mapa_lig(fs, pary) == {}
    # ale eliminacje pucharu wolno zlozyc w ten sam puchar (obie nazwy po tej samej stronie obu filtrow)
    fs2 = pd.DataFrame([dict(sport='basketball', kraj='EUROPE', turniej='FIBA Europe Cup - Qualification')] * 2)
    pary2 = {('basketball', 'EUROPE', 'FIBA Europe Cup - Qualification'): {('Europe', 'FIBA Europe Cup'): 2}}
    assert zewn._fsx_mapa_lig(fs2, pary2)


def test_mapa_lig_ten_sam_zapis_nic_nie_zmienia():
    fs = pd.DataFrame([dict(sport='basketball', kraj='SPAIN', turniej='ACB')] * 2)
    pary = {('basketball', 'SPAIN', 'ACB'): {('Spain', 'ACB'): 2}}
    assert zewn._fsx_mapa_lig(fs, pary) == {}


def test_liga_fs_dostaje_zapis_365_end_to_end(tmp_path, monkeypatch):
    """Dwa mecze wspolne potwierdzaja, ze to ta sama liga; trzeci, ktorego 365 nie ma, dostaje nazwe 365.

    Nazwy druzyn RÓZNIA sie miedzy zrodlami (tak jest w prawdziwych danych) — gdyby byly identyczne,
    mecz mialby ten sam klucz w obu zrodlach i zlapalby go wczesniejszy _scal_nazwy_rozgrywek."""
    s365 = pd.DataFrame([_w('2026-09-26', 'basketball', 'Spain', '1ª FEB', 'Palencia Baloncesto', 'Hestia Menorca', 90, 80),
                         _w('2026-09-27', 'basketball', 'Spain', '1ª FEB', 'CB Zamora', 'Oviedo Baloncesto', 85, 70)], columns=KOL)
    fsx = pd.DataFrame([_w('2026-09-26', 'basketball', 'SPAIN', 'Primera FEB', 'Palencia', 'Menorca', 90, 80),
                        _w('2026-09-27', 'basketball', 'SPAIN', 'Primera FEB', 'Zamora', 'Oviedo', 85, 70),
                        _w('2026-09-28', 'basketball', 'SPAIN', 'Primera FEB', 'Zamora', 'Palencia', 77, 75)], columns=KOL)
    s365.to_csv(tmp_path / 'wyniki_365_inne_2026-09.csv.gz', index=False)
    fsx.to_csv(tmp_path / 'wyniki_fsx_inne_2026-09.csv.gz', index=False)
    monkeypatch.setattr(zewn, 'ZD', str(tmp_path))
    x = zewn.inne()
    assert len(x) == 3                                   # 2 z 365 + 1 z Flashscore (dwa duble odrzucone)
    assert set(x.liga) == {'Spain | 1ª FEB'}             # „Primera FEB” zniknelo: jedna liga, nie dwie
