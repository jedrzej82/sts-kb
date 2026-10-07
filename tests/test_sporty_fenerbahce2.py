"""07.10.2026 — Raport 06.10 21:00, obserwacja 6: zdarzenia.py CONFLICT „Harem Spor – Fenerbahce Koleji” (RYWAL_INNY).
Reprodukcja: oferta STS 07.10 18:30 TBL „Harem Spor – Fenerbahce Koleji”; zrodlo wynikow/terminarza pisze od 09.2026
„Fenerbahce 2” (ten sam klub, liga TBL; „Fenerbahce Koleji” do 05.2026). Bylo: CONFLICT i model na danych sprzed
150+ dni; oczekiwane: jeden klub w bazie, nazwa STS rozpoznana jako „Fenerbahce 2”."""
import pandas as pd

import sporty


def _d(*mecze):
    return pd.DataFrame([dict(data=pd.Timestamp(d), sport=s, liga=l, gosp=h, gosc=a, pg=1, pa=0, dogrywka=0)
                         for d, s, l, h, a in mecze])


def test_historia_fenerbahce_koleji_scalona_z_fenerbahce_2():
    d = sporty.scal_recznie(_d(('2026-04-18', 'koszykówka', 'Turkiye | TBL', 'Harem Spor', 'Fenerbahce Koleji'),
                               ('2026-10-03', 'koszykówka', 'Turkiye | TBL', 'Fenerbahce 2', 'CO Basket'),
                               # siatkowka: inny klub/sekcja — bez zmian; Fenerbahce (Super Ligi) — bez zmian
                               ('2026-10-04', 'siatkówka', 'Turkiye | 1. Ligi', 'Kilis Genclik', 'Fenerbahce 2'),
                               ('2026-10-04', 'koszykówka', 'Turkiye | Super Ligi', 'Fenerbahçe', 'Besiktas')))
    assert list(d.gosc[:1]) == ['Fenerbahce 2'] and d.gosp[1] == 'Fenerbahce 2'
    assert 'Fenerbahce Koleji' not in set(d.gosp) | set(d.gosc)
    assert d.gosp[3] == 'Fenerbahçe'


def test_nazwa_sts_rozpoznana_jako_fenerbahce_2_a_nie_pierwsza_druzyna():
    pula = {'Fenerbahce 2', 'Fenerbahçe', 'Harem Spor'}
    assert sporty.resolve('Fenerbahce Koleji', pula, 'koszykówka') == 'Fenerbahce 2'
    assert sporty.resolve('Fenerbahce 2', pula, 'koszykówka') == 'Fenerbahce 2'
