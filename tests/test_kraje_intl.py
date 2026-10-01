"""01.10.2026 (Raport 21:00): „Kajmany” - „Portoryko” --intl -> „NIE ZNALEZIONO reprezentacji”, a Cayman Islands jest w bazie
intl. Sprawdzone na ofercie 24-30.09: 180 nazw reprezentacji, 7 meskich bez polskiej nazwy w _KRAJE_PL (kazda w bazie);
6 pozostalych to druzyny kobiet [K] — baza intl ich nie ma (P95.4, prawidlowe UNKNOWN)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sporty  # noqa: E402
import typuj  # noqa: E402

NOWE = [('Kajmany', 'Cayman Islands'), ('Gwadelupa', 'Guadeloupe'), ('Martynika', 'Martinique'), ('Malediwy', 'Maldives'),
        ('Seszele', 'Seychelles'), ('Saint Kitts i Nevis', 'Saint Kitts and Nevis'), ('Wyspy Cooka', 'Cook Islands')]
POOL = {en for _, en in NOWE} | {'Puerto Rico', 'Dominica', 'Cayman Islands FC'}


@pytest.mark.parametrize('pl,en', NOWE)
def test_reprezentacja_po_polsku(pl, en):
    assert typuj.resolve(pl, POOL) == en
    assert sporty.resolve(pl, POOL) == en


def test_kobiety_nie_trafiaja_w_mezczyzn():
    assert typuj.resolve('Kajmany [K]', POOL) is None
