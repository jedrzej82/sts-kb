"""03.10.2026 — paczka po regresji (porownanie werdyktow stary/nowy kod na ofercie 19:00-22:00).

Bramka swiezosci (P130.4) zablokowala 3 mecze. Dwa okazaly sie bledami danych, nie brakiem danych:
  - FC Emmen: klub ma DWA zapisy (FC Emmen = sezony Eredivisie 2018-20, 2022/23; Emmen = reszta do 2026),
    resolver bral martwy — mecz liczyl sie z danych sprzed 1224 dni;
  - US Thionville Lusitanos: resolver obcinal do 'Lusitanos', a to INNY klub (inne grupy N2, inni rywale
    w tych samych dniach). Le Puy X2 z 18:00 bylo liczone przeciw zlej druzynie.
Trzeci (ZEA) — dziura w bazie reprezentacji: biala lista turniejow nie znala Pucharu Zatoki Perskiej,
ASEAN Cup ani Kirin Cup; 41 meczow znanych reprezentacji seniorskich po 26.08 wypadalo po cichu.
"""
import csv
import os
import re
import sqlite3

import pytest

import swiezosc

KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAZA = os.path.join(KORZEN, 'kb.sqlite')


def _aliasy():
    with open(os.path.join(KORZEN, 'aliasy.csv'), encoding='utf-8') as fh:
        return {(r['modul'], r['nazwa']): r['cel'] for r in csv.DictReader(fh)}


def test_alias_fc_emmen():
    assert _aliasy().get(('typuj', 'FC Emmen')) == 'Emmen'


def test_alias_thionville_nie_lusitanos():
    """'Lusitanos' w bazie to inny klub — alias musi kierowac na Thionville."""
    assert _aliasy().get(('typuj', 'US Thionville Lusitanos')) == 'Thionville'


@pytest.mark.parametrize('turniej', ['Arabian Gulf Cup', 'FIFA ASEAN Cup - Division 1', 'FIFA ASEAN Cup - Division 2',
                                     'Kirin Cup (Japan)'])
def test_turnieje_regionalne_sa_rozpoznawane(turniej):
    t = turniej.lower()
    assert re.search(swiezosc._TURNIEJ_REPR, t), turniej
    assert not re.search(swiezosc._TURNIEJ_NIE, t), turniej


@pytest.mark.parametrize('turniej', ['Gulf Club Champions League', 'AFC Champions League', 'ASEAN Club Championship',
                                     'Arabian Gulf Cup U23', 'AFF Women Championship'])
def test_klubowe_i_mlodziezowe_dalej_wykluczone(turniej):
    """Rozszerzenie listy nie moze wpuscic klubow ani mlodziezy do bazy reprezentacji seniorskich."""
    t = turniej.lower()
    assert not (re.search(swiezosc._TURNIEJ_REPR, t) and not re.search(swiezosc._TURNIEJ_NIE, t)), turniej


def test_stare_turnieje_bez_zmian():
    for t in ['uefa nations league', 'world cup qualification', 'friendly international', 'gold cup', 'asian cup']:
        assert re.search(swiezosc._TURNIEJ_REPR, t), t


@pytest.mark.skipif(not os.path.exists(BAZA), reason='wymaga zbudowanej bazy (kb.sqlite)')
def test_emmen_i_fc_emmen_to_ten_sam_klub():
    """Dowod, na ktorym stoi alias: zapisy sie dopelniaja — zero wspolnych dat."""
    c = sqlite3.connect(BAZA)
    daty = lambda t: {r[0] for r in c.execute(
        'select MatchDate from matches where HomeTeam=? or AwayTeam=?', (t, t))}
    a, b = daty('FC Emmen'), daty('Emmen')
    assert a and b and not (a & b)


@pytest.mark.skipif(not os.path.exists(BAZA), reason='wymaga zbudowanej bazy (kb.sqlite)')
def test_lusitanos_i_thionville_to_rozne_kluby():
    """Dowod: w te same dni graja z ROZNYMI rywalami — gdyby to byl jeden klub, rywal bylby ten sam."""
    c = sqlite3.connect(BAZA)
    def mecze(t):
        return {r[0]: (r[2] if r[1] == t else r[1]) for r in c.execute(
            'select MatchDate, HomeTeam, AwayTeam from matches where HomeTeam=? or AwayTeam=?', (t, t))}
    a, b = mecze('Lusitanos'), mecze('Thionville')
    wspolne = set(a) & set(b)
    assert len(wspolne) >= 10
    assert all(a[d] != b[d] for d in wspolne)
