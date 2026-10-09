"""Raport 09.10 21:00.
  1. Rozliczenie 06.10 (P119.2, plik niezapisany): AKOP-2100-1 „Toros del Valle - Sabios de Manizales, Zwyciezca 1”
     (uwaga „mecz 2026-10-07 01:30” — czas polski) -> BRAK WYNIKU KILKA_MECZOW; zapisany plik i P171.1: TRAFIONY 108:59.
     Warstwa: dzien meczu. Zrodla wynikow (365, Flashscore) sa w UTC: mecz 01:30 PL = 06.10 23:30 UTC jest pod 06.10.
     Dzien z uwagi (07.10) nie mial meczu, a w oknie +-1 dnia byl tez nastepny mecz serii (08.10 89:40).
     Sprawdzone na paczce 09.10 07:00: 06.10 zmienia sie tylko ta noga; 05.10, 07.10, 08.10 — bez zmian.
     AKOP-2100-2 Caribbean Storm Islands – Paisas: 365 ma DWA mecze tej pary 07.10 UTC (79:90 i 72:107; seria dzien
     po dniu), Flashscore jeden — godzin wynikow brak, BRAK WYNIKU jest prawidlowy (historia zamrozona: TRAFIONY zostaje).
  2. „Omiya Ardija” NIESWIEZA (2018) — ten sam klub co „RB Omiya Ardija” (JAP2): kluby.SCAL_RECZNIE.
  3. „Platense FC” (Honduras) -> Platense (ARG): ponowne dopasowanie po terminarzu odpadalo na _kraje_znane()
     (Honduras tylko w nazwach lig Flashscore)."""
import pandas as pd

import dzienniki
import kluby
import sporty
import typuj

D = '2026-10-06'
SP = sporty.nazwa_sportu('koszykówka')   # tak jak dzienniki filtruje W['inne']


def _W(inne):
    i = pd.DataFrame([dict(d=pd.Timestamp(d), sport=s, h=h, a=a, pg=pg, pa=pa, ot=ot) for d, s, h, a, pg, pa, ot in inne],
                     columns=['d', 'sport', 'h', 'a', 'pg', 'pa', 'ot'])
    return dict(pilka=pd.DataFrame(columns=['d', 'h', 'a', 'g', 'ga', 'hg', 'ha', 'zr']), inne=i,
                tenis=pd.DataFrame(columns=['d', 'w', 'l', 'score']))


def test_dzien_zrodla_to_data_utc():
    assert dzienniki._dzien_zrodla(dict(data=D, uwaga='mecz 2026-10-07 01:30')) == pd.Timestamp('2026-10-06')
    assert dzienniki._dzien_zrodla(dict(data=D, uwaga='mecz 2026-10-07 03:30')) == pd.Timestamp('2026-10-07')
    assert dzienniki._dzien_zrodla(dict(data=D, uwaga='mecz 2026-10-07 21:00')) == pd.Timestamp('2026-10-07')
    assert dzienniki._dzien_zrodla(dict(data=D, uwaga='mecz 2026-10-07')) == pd.Timestamp('2026-10-07')
    assert dzienniki._dzien_zrodla(dict(data=D, uwaga='')) == pd.Timestamp(D)
    # zima (UTC+1): 00:30 PL = 23:30 UTC dnia poprzedniego
    assert dzienniki._dzien_zrodla(dict(data=D, uwaga='mecz 2026-12-10 00:30')) == pd.Timestamp('2026-12-09')


def test_toros_seria_dzien_po_dniu():
    W = _W([('2026-10-06', SP, 'Toros del Valle', 'Sabios de Manizales', 108, 59, 0),
            ('2026-10-08', SP, 'Toros del Valle', 'Sabios de Manizales', 89, 40, 0)])
    r = dict(sport='koszykowka', zdarzenie='Toros del Valle - Sabios de Manizales', rynek='Zwyciezca 1', data=D,
             uwaga='mecz 2026-10-07 01:30')
    assert dzienniki.rozlicz_noge(r, W)[:2] == ('TRAFIONY', '108:59')   # przed: BRAK WYNIKU (KILKA_MECZOW)


def test_dwa_mecze_tego_samego_dnia_utc_dalej_bez_zgadywania():
    W = _W([('2026-10-07', SP, 'Caribbean Storm Islands', 'Paisas', 79, 90, 0),
            ('2026-10-07', SP, 'Caribbean Storm Islands', 'Paisas', 72, 107, 0)])
    r = dict(sport='koszykowka', zdarzenie='Caribbean Storm Islands - Paisas', rynek='Zwyciezca 2', data=D,
             uwaga='mecz 2026-10-07 03:30')
    stan, _, uw = dzienniki.rozlicz_noge(r, W)
    assert stan == 'BRAK WYNIKU' and 'nie zgadujemy' in uw


def test_omiya_ardija_scalona():
    assert kluby.SCAL_RECZNIE[('JAP', 'Omiya Ardija')] == 'RB Omiya Ardija'
    assert typuj.ALIASES_KLUBY[typuj.norm('Omiya Ardija')] == 'RB Omiya Ardija'


def test_platense_honduras_po_terminarzu(monkeypatch):
    # sprawdzone na bazie i terminarzu 09.10: „Platense FC” -> CD Platense (Honduras | Liga Nacional)
    m = pd.DataFrame([dict(MatchDate='2026-09-18', HomeTeam='CD Platense', AwayTeam='Juticalpa', Division='Honduras | Liga Nacional'),
                      dict(MatchDate='2026-09-20', HomeTeam='Platense', AwayTeam='Boca Juniors', Division='ARG')])
    pool = set(m.HomeTeam) | set(m.AwayTeam)
    mt = dict(kraj='HONDURAS', turniej='Liga Nacional - Apertura', gosp='Platense', gosc='Juticalpa')
    assert typuj._kanon_kraju('honduras') not in typuj._kraje_znane()
    assert typuj._kraj_z_terminarza('Platense FC', 'Juticalpa FC', 'Platense', 'Juticalpa', 'argentina', 'honduras',
                                    pool, m, mt) == ('CD Platense', 'Juticalpa')
    # kraj bez klubow w bazie — jak dotad brak poprawki (noga MNIEJ)
    mt2 = dict(mt, kraj='NICARAGUA')
    assert typuj._kraj_z_terminarza('Platense FC', 'Juticalpa FC', 'Platense', 'Juticalpa', 'argentina', 'honduras',
                                    pool, m, mt2) is None
