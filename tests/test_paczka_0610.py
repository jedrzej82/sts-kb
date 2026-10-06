"""Paczka 06.10.2026 — usterki z Raportu 05.10 21:00."""
import pandas as pd

import dzienniki
import sporty
import tenis

D = '2026-10-02'


def test_remis_koncowy_przegrywa_rynek_regulaminowy_bez_wiedzy_o_dogrywce():
    # Wetzlar – Löwen 30:30, ako_log rynek „2” (czas regulaminowy), dogrywka nieznana (-1): bylo BRAK WYNIKU
    W = dict(pilka=None, tenis=None, inne=pd.DataFrame([dict(d=pd.Timestamp(D), sport='piłka ręczna', h='HSG Wetzlar',
                                                              a='Rhein-Neckar Löwen', pg=30, pa=30, ot=-1)]))
    r = dict(sport='reczna', zdarzenie='HSG Wetzlar - Rhein-Neckar Lowen', rynek='2', data=D, uwaga='')
    assert dzienniki.rozlicz_noge(r, W)[:2] == ('PRZEGRANY', '30:30')
    W['inne'].loc[0, ['pg', 'pa']] = [29, 30]           # wygrana bez wiedzy o dogrywce — dalej nie zgadujemy
    assert dzienniki.rozlicz_noge(r, W)[0] == 'BRAK WYNIKU'


def test_aliasy_lnb_argentyna():
    pula = {'Quimsa', 'Quimsa (W)', 'Atenas', 'Atletico Atenas', 'Club Atenas La Plata'}
    assert sporty.resolve('Quimsa Santiago del Estero', pula, 'koszykówka') == 'Quimsa'
    assert sporty.resolve('Atenas Cordoba', pula, 'koszykówka') == 'Atenas'


def test_tenis_jedna_spacja_w_nazwisku(tmp_path, monkeypatch):
    w = [dict(date=f'2026-06-{10 + i}', zwyciezca=z, przegrany=p, score='6-4 6-4', nawierzchnia='Hard', tour='WTA',
              poziom='C') for i, (z, p) in enumerate([('Alicia  Dudeney', 'Yidi Yang'), ('Alicia Dudeney', 'Himeno Sakatsume'),
                                                      ('Ashlyn Krueger', 'Alicia  Dudeney ')])]
    pd.DataFrame(w).to_csv(tmp_path / 'h.csv', index=False)
    monkeypatch.setattr(tenis, 'HIST', str(tmp_path / 'h.csv'))
    monkeypatch.setattr(tenis, 'DELTA', str(tmp_path / 'brak.csv'))
    d = tenis.load()
    n = set(d.winner_name) | set(d.loser_name)
    assert 'Alicia Dudeney' in n and not any('  ' in x or x != x.strip() for x in n)
