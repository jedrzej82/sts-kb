"""tenis.resolve: inicjaly nie moga zastapic nazwiska; aktywny zawodnik rozstrzyga wieloznacznosc (29.09.2026)."""
import pandas as pd

import tenis

PULA = {'Magda Linette', 'Cinalli L. M.', 'Felix Auger Aliassime', 'Alhogbani A. F.', 'Alex De Minaur',
        'Sibanda M. D. A.', 'Casper Ruud', 'Christian Ruud', 'Hubert Hurkacz'}


def test_inicjal_nie_zastapi_nazwiska():
    assert tenis.resolve('Linette M.', PULA) == 'Magda Linette'
    assert tenis.resolve('Auger-Aliassime F.', PULA) == 'Felix Auger Aliassime'
    assert tenis.resolve('De Minaur A.', PULA) == 'Alex De Minaur'
    assert tenis.resolve('Linette M.', PULA - {'Magda Linette'}) is None       # obca osoba z inicjalami -> nic


def test_aktywny_rozstrzyga_inicjal(monkeypatch):
    assert tenis.resolve('Ruud C.', PULA) is None                              # bez dat: nie zgadujemy
    monkeypatch.setattr(tenis, 'OSTATNI', {'Casper Ruud': pd.Timestamp.today(), 'Christian Ruud': pd.Timestamp('2001-05-01')})
    assert tenis.resolve('Ruud C.', PULA) == 'Casper Ruud'
    monkeypatch.setattr(tenis, 'OSTATNI', {'Casper Ruud': pd.Timestamp.today(), 'Christian Ruud': pd.Timestamp.today()})
    assert tenis.resolve('Ruud C.', PULA) is None                              # obaj aktywni -> nie zgadujemy
