"""06.10.2026 — kursy3: para meczow STS <-> Superbet/LVBET nie moze opierac sie na czlonach Town/United/City."""
import pandas as pd

import kursy3


def _z(*pary, t=20 * 60 + 45):
    return pd.DataFrame([dict(sport='PIŁKA NOŻNA', data_meczu='2026-10-06', godzina_meczu='20:45', gospodarz=g, gosc=a, t=t)
                         for g, a in pary])


def test_dwie_pary_town_united_wybrana_wlasciwa():
    # kursy 06.10 11:30 / Superbet 11:34: „Cleethorpes Town - Hyde United” pasowalo tez do „Alfreton Town - United of
    # Manchester” (Town~Town, United~United) -> 2 pary -> brak kursu Superbet/LVBET dla obu meczow
    sts = _z(('Cleethorpes Town', 'Hyde United'), ('Alfreton Town', 'FC United of Manchester'))
    buk = _z(('Alfreton Town', 'United of Manchester'), ('Cleethorpes Town', 'Hyde United'), ('Braintree Town', 'Walton & Hersham'))
    wyn, st = kursy3.dopasuj_mecze(sts, buk)
    assert wyn[('PIŁKA NOŻNA', '2026-10-06', 'Cleethorpes Town', 'Hyde United')] == ('Cleethorpes Town', 'Hyde United')
    assert wyn[('PIŁKA NOŻNA', '2026-10-06', 'Alfreton Town', 'FC United of Manchester')] == ('Alfreton Town', 'United of Manchester')
    assert st['kilka'] == 0


def test_tylko_ogolne_czlony_to_nie_ten_sam_mecz():
    # wlasciwego meczu u bukmachera nie ma — dotad jedyna para „X Town - Y United” stawala sie kursem tej nogi
    wyn, st = kursy3.dopasuj_mecze(_z(('Stockton Town', 'Hyde United')), _z(('Braintree Town', 'Ashton United')))
    assert not wyn and st['brak'] == 1
    # jedna strona wyrazna wystarcza (Villa FC Waterford = Villa FC, „Ck United” — „ck” za krotkie)
    wyn, _ = kursy3.dopasuj_mecze(_z(('Villa FC Waterford', 'Ck United')), _z(('Villa FC', 'Ck United')))
    assert len(wyn) == 1
