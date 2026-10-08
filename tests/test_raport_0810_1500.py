"""08.10.2026 — Raport 08.10 15:00 (i 12:00).
  1. PDF STS: „Al‑Duhail SC” z twardym lacznikiem U+2011 — ascii-ignore sklejal „alduhail”, kursy3 nie znajdowal meczu
     u Superbet/LVBET; oczekiwane: zwykly „-”.
  2. „Al-Nasr Dubai – Hatta SC”: NIEZGODNE Z TERMINARZEM (liga z kraju uae / terminarz United Arab Emirates).
  3. „Al-Okhdood FC” -> martwy wpis „Al Okhdood SC” (KSA do 05.2025); klub gra jako „Al-Akhdoud”.
  4–5. „Universitatea Cluj”, „HJK Helsinki” -> sam wpis clubelo (liga None, ROZNE LIGI BEZ ELO), a warianty_nazw z
     build_kb wskazuje klub z meczami („U. Cluj”, „HJK”); „VPS Vassa” (literowka STS) -> None."""
import os

import pandas as pd

import dopasuj
import kluby
import kursy3
import oferta
import typuj


def test_twardy_lacznik_to_zwykly_lacznik():
    assert oferta._bialy('Al‑Shamal SC – Al‑Duhail SC') == 'Al-Shamal SC – Al-Duhail SC'
    assert oferta._bialy('Kra­kow') == 'Krakow'
    assert dopasuj.tokeny('Al‑Duhail SC') == dopasuj.tokeny('Al-Duhail SC')
    assert kursy3._podobne('Al‑Duhail SC', 'Al Duhail') and kursy3._wyrazne('Al‑Duhail SC', 'Al Duhail SC')


def test_uae_to_zjednoczone_emiraty():
    assert typuj._ten_sam_kraj(typuj.norm('UAE'), typuj.norm('United Arab Emirates'))
    assert not typuj._ten_sam_kraj(typuj.norm('UAE'), typuj.norm('Qatar'))


def test_al_okhdood_i_vps_vassa():
    assert kluby.SCAL_RECZNIE[('KSA', 'Al Okhdood SC')] == 'Al-Akhdoud'
    a = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'aliasy.csv'), dtype=str)
    t = a[a.modul == 'typuj']
    assert set(t[t.nazwa.isin(['Al-Okhdood FC', 'VPS Vassa'])].cel) == {'Al-Akhdoud', 'VPS'}


def test_wpis_clubelo_bez_meczow_przez_warianty_nazw(monkeypatch):
    m = pd.DataFrame(dict(HomeTeam=['HJK', 'CFR Cluj'], AwayTeam=['VPS', 'U. Cluj']))
    monkeypatch.setattr(typuj, '_WARIANTY', {typuj.norm('HJK Helsinki'): 'HJK', typuj.norm('Universitatea Cluj'): 'U. Cluj',
                                              typuj.norm('Inny Klub'): 'Brak W Bazie'})
    assert typuj._z_meczami('HJK Helsinki', m) == 'HJK'
    assert typuj._z_meczami('Universitatea Cluj', m) == 'U. Cluj'
    assert typuj._z_meczami('CFR Cluj', m) == 'CFR Cluj'           # ma mecze — bez zmian
    assert typuj._z_meczami('Inny Klub', m) == 'Inny Klub'         # cel bez meczow — bez zmian


def test_terminarz_krotkie_czlony_al_ain():
    # Raport 08.10 12:00 nr 2: „Al-Ain FC” -> Al-Ain (KSA); terminarz „Al Ain – Kalba” (UAE) nie byl znajdowany,
    # bo „al”, „ain” < 4 litery — korekta kraju z terminarza nie startowala (ROZNE KRAJE, noga MNIEJ)
    import terminarz
    assert terminarz.pasuje('Al-Ain FC', 'Al Ain')
    assert not terminarz.pasuje('Al Ain', 'Al Ahly') and not terminarz.pasuje('FC', 'FC')
    t = pd.DataFrame([dict(data='2026-10-08', sport='football', kraj='UAE', turniej='League Cup', gosp='Al Ain', gosc='Kalba')])
    assert terminarz.znajdz('Al-Ain FC', 'Al-Ittihad Kalba', t)['kraj'] == 'UAE'


def test_oferta_mecz_rozbity_na_warianty_nazwy():
    # Raport 08.10 12:00 nr 11: PDF 11:30 „Port FC – Persib Bandung” (1X2) i „Thai Port FC – Persib Bandung” (reszta)
    r = lambda zd, g, a, sek, godz='14:00': dict(data_meczu='2026-10-08', godzina_meczu=godz, sport='PIŁKA NOŻNA',
                                                 zdarzenie=zd, gospodarz=g, gosc=a, sekcja=sek)
    d = pd.DataFrame([r('Port FC - Persib Bandung', 'Port FC', 'Persib Bandung', '1X2'),
                      r('Thai Port FC - Persib Bandung', 'Thai Port FC', 'Persib Bandung', 'Liczba goli'),
                      r('Lion City - Buriram', 'Lion City', 'Buriram', '1X2'),          # inny rywal — bez zmian
                      r('Lion City Sailors - Johor', 'Lion City Sailors', 'Johor', '1X2'),
                      r('Port FC - Persib Bandung', 'Port FC', 'Persib Bandung', 'BTTS', godz='16:00')])   # inna godzina
    o = []
    w = oferta.scal_zdarzenia(d, o)
    assert list(w.zdarzenie[:2]) == ['Thai Port FC - Persib Bandung'] * 2
    assert list(w.zdarzenie[2:]) == ['Lion City - Buriram', 'Lion City Sailors - Johor', 'Port FC - Persib Bandung']
    assert any('scalono warianty nazwy' in x for x in o)
