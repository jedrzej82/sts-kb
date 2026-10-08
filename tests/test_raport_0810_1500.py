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
