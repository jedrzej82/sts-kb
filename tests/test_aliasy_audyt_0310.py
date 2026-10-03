"""03.10.2026 audyt nazw (porownanie nazw FotMob/Understat/Transfermarkt z baza): typuj.resolve dawal ZLY klub.
Reprodukcja na bazie z 30.09: wejscie (nazwa jak w ofercie STS / zrodlach) -> wynik -> oczekiwany."""
import pytest

import typuj

PULA = {'West Brom', 'Albion', 'QPR', 'Queens Park', 'Barcelona', 'FC Barcelona Atlètic', 'Grasshoppers', 'Zurich',
        'Atl Goianiense', 'Atletico-MG', 'Jazira Abu Dhabi', 'Al Jazira Al Hamra'}


@pytest.mark.parametrize('nazwa,bylo,oczekiwane', [
    ('West Bromwich Albion', 'Albion', 'West Brom'),
    ('Queens Park Rangers', 'Queens Park', 'QPR'),
    ('FC Barcelona', 'FC Barcelona Atlètic', 'Barcelona'),
    ('Grasshopper Club Zurich', 'Zurich', 'Grasshoppers'),
    ('Atlético-GO', 'Atletico-MG', 'Atl Goianiense'),
    ('Al-Jazira', 'Al Jazira Al Hamra', 'Jazira Abu Dhabi'),
])
def test_zly_klub_naprawiony(nazwa, bylo, oczekiwane):
    assert typuj.resolve(nazwa, PULA) == oczekiwane != bylo


@pytest.mark.parametrize('nazwa', ['Queens Park', 'Albion', 'Zurich', 'Barcelona', 'Al Jazira Al Hamra'])
def test_krotkie_nazwy_bez_zmian(nazwa):
    assert typuj.resolve(nazwa, PULA) == nazwa
