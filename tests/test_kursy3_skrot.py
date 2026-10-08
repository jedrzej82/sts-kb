"""08.10.2026 — Raport 07.10 21:00 nr 4: LVBET „nie znaleziono” CRB Maceió – Atlético Goianiense przy swiezym pliku z telefonu
(20:33). Reprodukcja: STS „CRB Maceió” / Superbet „CRB AL”, LVBET „Clube De Regatas Brasil – Atletico Goianiense” 01:30 —
zaden wspolny czlon. Oczekiwane: para dopasowana (skrot z pierwszych liter czlonow). Plik 20:33, Superbet -> LVBET:
302 -> 303 par, jedyna nowa to ta, zadna inna sie nie zmienila."""
import pandas as pd

import kursy3


def _z(*pary, t=90):
    return pd.DataFrame([dict(sport='PIŁKA NOŻNA', data_meczu='2026-10-08', godzina_meczu='01:30', gospodarz=g, gosc=a, t=t)
                         for g, a in pary])


def test_skrot_crb_to_clube_de_regatas_brasil():
    buk = _z(('Clube De Regatas Brasil', 'Atletico Goianiense'), ('Vila Nova Goiania', 'Cuiaba EC'), ('Botafogo', 'CR Vasco da Gama'))
    for sts in (('CRB Maceió', 'Atlético Goianiense'), ('CRB AL', 'Atletico GO')):
        wyn, st = kursy3.dopasuj_mecze(_z(sts), buk)
        assert wyn == {('PIŁKA NOŻNA', '2026-10-08') + sts: ('Clube De Regatas Brasil', 'Atletico Goianiense')}, sts


def test_skrot_tylko_z_pierwszych_liter_calej_nazwy():
    assert kursy3._skrot('PSG', 'Paris Saint Germain') and kursy3._skrot('WKS', 'Wybrzeze Kosci Sloniowej')
    assert not kursy3._skrot('CR', 'Clube Regatas')            # skrot min. 3 litery, nazwa min. 3 czlony
    assert not kursy3._skrot('CRB', 'Cruzeiro Belo Horizonte')   # c-b-h, nie c-r-b
    assert not kursy3._podobne('Botafogo', 'Vasco da Gama')
    assert not kursy3._skrot('WKS Śląsk Wrocław', 'Wybrzeże Kości Słoniowej')   # skrot formy prawnej + nazwa klubu
    # sam skrot nie wystarcza: druga druzyna musi sie zgadzac
    wyn, st = kursy3.dopasuj_mecze(_z(('CRB AL', 'Atletico GO')), _z(('Clube De Regatas Brasil', 'Sport Recife')))
    assert not wyn and st['brak'] == 1
