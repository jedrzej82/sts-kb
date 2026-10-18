"""18.10.2026: aliasy_bukmacherow.csv — dokladne pary nazw tego samego zespolu u Superbet i LVBET, kazda z dowodem z kursow
(plik z telefonu 17-18.10). Odzyskuja pary utracone po zaostrzeniu kursy3._strona (PR #192), bez luzowania regul."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kursy3  # noqa: E402


def _z(*pary, sport='HOKEJ NA LODZIE', t=1140):
    return pd.DataFrame([dict(sport=sport, data_meczu='2026-10-18', godzina_meczu='19:00', gospodarz=g, gosc=a, t=t)
                         for g, a in pary])


def test_plik_aliasow_kompletny():
    a = pd.read_csv(kursy3.ALIASY_PLIK, dtype=str, keep_default_na=False)
    assert list(a.columns) == ['sport', 'nazwa_1', 'nazwa_2', 'dowod'] and len(a) >= 100
    assert (a.dowod.str.contains('mediana roznicy kursow')).all()                 # kazdy wiersz z dowodem
    assert not (a.nazwa_1.str.lower() == a.nazwa_2.str.lower()).any()
    assert not a.duplicated(['nazwa_1', 'nazwa_2']).any()


def test_alias_odzyskuje_pare_przy_pewnym_rywalu():
    wyn, st = kursy3.dopasuj_mecze(_z(('Kolner Haie', 'Pinguins Bremerhaven')), _z(('Kolner Haie', 'Fischtown Pinguins')))
    assert st['jednoznaczne'] == 1


def test_alias_nie_wystarcza_bez_pewnego_rywala():
    # alias po jednej stronie, druga strona inna druzyna -> brak pary (nie zgadujemy)
    wyn, st = kursy3.dopasuj_mecze(_z(('Eisbaren Berlin', 'Pinguins Bremerhaven')), _z(('Kolner Haie', 'Fischtown Pinguins')))
    assert wyn == {}


def test_alias_dokladny_z_markerami():
    # „Gyor” (mezczyzni) i „Gyor (K)” to osobne wiersze — alias mezczyzn nie laczy druzyny kobiet
    assert kursy3._strona('Gyor', 'Gyori ETO KC') and kursy3._strona('Gyor (K)', 'Gyori ETO KC (Wom)')
    assert not kursy3._strona('Gyor (K)', 'Gyori ETO KC')
