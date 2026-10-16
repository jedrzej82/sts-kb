"""Raport 15.10 15:00 nr 8 (P77.1 „puchary tylko na papierze”): Union SG – Real Sociedad (--kontynentalny, oba kluby z Elo)
dostal „✔ NOGA DOPUSZCZONA” 1X i trafil do nogi.csv, a kupon.py wzial go do K5/MIX — przebieg odrzucal recznie.
Sprawdzone na bazie: stary kod zapisywal noge (1X @1.75, EV +16%), nowy wypisuje „NIE NA KUPON: PUCHAR” i nogi.csv pusty."""
import typuj


def test_zakaz_nogi_w_pucharze():
    assert typuj.zakaz_pucharu(['typuj.py', 'A', 'B', '--kontynentalny'], None).startswith('PUCHAR')
    assert typuj.zakaz_pucharu(['typuj.py', 'A', 'B'], {'turniej': 'Copa do Brasil', 'kraj': 'Brazil'}).startswith('PUCHAR')
    assert typuj.zakaz_pucharu(['typuj.py', 'A', 'B'], {'turniej': 'Puchar Polski', 'kraj': 'Poland'})
    assert typuj.zakaz_pucharu(['typuj.py', 'A', 'B'], {'turniej': 'Premier League', 'kraj': 'England'}) is None
    assert typuj.zakaz_pucharu(['typuj.py', 'A', 'B'], None) is None


def test_werdykt_blokuje_noge_przy_zakazie():
    typuj.KONTEKST_MECZU.clear()
    typuj.KONTEKST_MECZU['zakaz_nogi'] = typuj.zakaz_pucharu(['--kontynentalny'], None)
    pk, powod = typuj.werdykt_nogi('1X', None)
    assert pk is None and powod.startswith('PUCHAR')
    typuj.KONTEKST_MECZU.clear()


# Raport 15.10 15:00 nr 2–3: nazwy w pucharach kontynentalnych (--kontynentalny). Sprawdzone na bazie i terminarzu 15.10:
# 25/25 meczow z raportu dopasowanych (przed: 23 x MNIEJ), Nacional – Bolivar i Al-Qadisiyah bez aliasu dalej MNIEJ.
import sys

import pandas as pd
import pytest


def _terminarz(w):
    return pd.DataFrame([dict(data='2026-10-15', godzina_utc='16:45', sport='football', kraj='Europe', turniej=t, gosp=g, gosc=d, zrodlo=z)
                         for z, t, g, d in w])


@pytest.fixture
def kont(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['typuj.py', 'A', 'B', '--kontynentalny'])


def test_terminarz_uzupelnia_nazwe_z_oferty(monkeypatch):
    import terminarz
    monkeypatch.setattr(terminarz, 'wczytaj', lambda plik=None: _terminarz([
        ('fs', 'Europa League - League phase', 'Ferencvaros', 'Plzen'),          # „Plzen” niejednoznaczne
        ('365', 'UEFA Europa League', 'Ferencvaros', 'Viktoria Plzen'),
        ('365', 'UEFA Europa League', 'Benfica', 'Celtic')]))
    pool = {'Benfica', 'Celtic', 'Bloem Celtic', 'Killarney Celtic', 'Ferencvaros', 'Viktoria Plzen', 'Petrin Plzen', 'Rapid Plzen'}
    mt, th, ta = typuj.para_z_terminarza_pucharu('Benfica Lizbona', 'Celtic Glasgow', pool)
    assert (th, ta) == ('Benfica', 'Celtic') and 'Europa' in mt['turniej']
    mt, th, ta = typuj.para_z_terminarza_pucharu('Ferencvaros TC', 'Viktoria Pilzno', pool, 'Ferencvaros', 'Viktoria Plzen')
    assert (th, ta) == ('Ferencvaros', 'Viktoria Plzen')      # 365, bo w Flashscore „Plzen” nie rozstrzyga


def test_terminarz_ligowy_nie_jest_pucharem(monkeypatch):
    import terminarz
    monkeypatch.setattr(terminarz, 'wczytaj', lambda plik=None: _terminarz([('365', 'Premier League', 'Arsenal', 'Chelsea')]))
    assert typuj.para_z_terminarza_pucharu('Arsenal', 'Chelsea', {'Arsenal', 'Chelsea'}) == (None, None, None)


def test_nazwa_wspolna_w_pucharze_uefa(kont):
    m = pd.DataFrame([dict(MatchDate=pd.Timestamp('2026-09-20'), Division=d, HomeTeam=t, AwayTeam='X') for t, d in
                      [('Juventus', 'I1'), ('Juventus [haiti]', 'Haiti | Ligue Haitienne'), ('Celta', 'SP1'),
                       ('Red Star', 'F2'), ('Red Star [serbia]', 'SRB'), ('Lugano', 'SUI')]])
    pool = set(m.HomeTeam)
    assert typuj._wariant_kraju('Celta', 'Juventus', m, pool, uefa=True) == ('Celta', 'Juventus')
    with pytest.raises(SystemExit):                                   # bez terminarza UEFA — dalej stop
        typuj._wariant_kraju('Celta', 'Juventus', m, pool)
    with pytest.raises(SystemExit):                                   # oba Red Star z UEFA — stop
        typuj._wariant_kraju('Lugano', 'Red Star [serbia]', m, pool, uefa=True)
    # terminarz zapisal „Crvena zvezda” (nie nazwa wspolna) i wskazal ten sam klub
    assert typuj._wariant_kraju('Lugano', 'Red Star [serbia]', m, pool, uefa=True,
                                potw={'Red Star [serbia]': 'Crvena zvezda'}) == ('Lugano', 'Red Star [serbia]')


def test_aliasy_egzonimy_pucharow():
    import os
    a = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'aliasy.csv'), dtype=str)
    al = {(r.modul, r.nazwa): r.cel for r in a.itertuples()}
    assert al[('typuj', 'Viktoria Pilzno')] == 'Viktoria Plzen' and al[('typuj', 'OFI Kreta')] == 'OFI Crete'
    assert al[('typuj', 'Olympique Marsylia')] == 'Marseille'


def test_alias_ncaaf_texas_state():
    # Raport 15.10 21:00 nr 1: „Texas State Bobcats” pasowalo do 2 wpisow (Texas, Texas State)
    import sporty
    pula = {'Texas', 'Texas State', 'Texas Tech', 'Colorado State', 'Oklahoma', 'Oklahoma State'}
    assert sporty.resolve('Texas State Bobcats', pula, 'futbol_amerykanski') == 'Texas State'
    assert sporty.resolve('Oklahoma Baptist Bison', pula, 'futbol_amerykanski') is None   # brak w zrodle — MNIEJ
