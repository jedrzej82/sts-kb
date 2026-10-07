"""07.10.2026 — Raport 07.10 21:00.
  1. regresja: noga AKOP 02.10 „Medvedev Daniil – Struff Jan-Lennard” (Zwyciezca 1); baza: „Jan Lennard Struff”,
     Medvedev 6-4 6-3. Po wymogu przedrostka od 4 liter (PR #154) „janlennard” nie pasowal do „jan” -> BRAK WYNIKU
     „nie dopasowano: Struff Jan-Lennard”; oczekiwane TRAFIONY (tak bylo w Rozliczeniu 02.10 uzupelnionym 06.10).
  2. „RB Bragantino” (oferta, Serie A) trafialo w martwy wpis z Paulisty (ostatni mecz 02.2026); w BRA klub to „Bragantino”.
  3. sezon.py: „CD ABA Ancud” -> NIE ZNALEZIONO, arkusz ma „ABA Ancud”."""
import os

import pandas as pd

import dzienniki
import kluby
import tenis


def test_lacznik_w_imieniu_tenisisty():
    W = dict(pilka=None, inne=None,
             tenis=pd.DataFrame([dict(d=pd.Timestamp('2026-10-03'), w='Daniil Medvedev', l='Jan Lennard Struff', score='6-4 6-3'),
                                 dict(d=pd.Timestamp('2026-10-02'), w='Jan Struff', l='Ivan Ivanov', score='6-1 6-1')]))
    r = dict(sport='tenis', zdarzenie='Medvedev Daniil - Struff Jan-Lennard', rynek='Zwyciezca 1', data='2026-10-02', uwaga='')
    assert dzienniki.rozlicz_noge(r, W)[:2] == ('TRAFIONY', 'Daniil Medvedev 6-4 6-3')
    assert dzienniki._kandydaci_tenis('Struff Jan-Lennard', {'Jan Lennard Struff', 'Jan-Lennard Struff', 'Jan Struff'}) \
        == {'Jan Lennard Struff', 'Jan-Lennard Struff'}
    # przedrostek dalej od 4 liter (Kim Eunchae != Eun Ha Kim)
    assert tenis._zgodnosc('Kim Eunchae', 'Eun Ha Kim') == (1, 1)


def test_rb_bragantino_to_bragantino():
    assert kluby.SCAL_RECZNIE[('Brazil | Paulista', 'RB Bragantino')] == 'Bragantino'
    a = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'aliasy.csv'), dtype=str)
    assert ((a.modul == 'typuj') & (a.nazwa == 'RB Bragantino') & (a.cel == 'Bragantino')).any()
    assert ((a.modul == 'sezon') & (a.nazwa == 'CD ABA Ancud') & (a.cel == 'ABA Ancud')).any()
