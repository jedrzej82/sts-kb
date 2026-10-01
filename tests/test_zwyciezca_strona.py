"""01.10.2026: rynek „zwyciezca meczu: Luke Woodhouse” przy zdarzeniu „Woodhouse Luke - Aspinall Nathan” (dart, tenis:
imie i nazwisko w odwrotnej kolejnosci) — noga konczylaby jako BEZ STRONY. Te same slowa = ta sama strona; bez zgadywania."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dzienniki  # noqa: E402


def test_odwrocona_kolejnosc_imienia():
    t = dzienniki._typ_zwyciezcy
    assert t('zwyciezca meczu: Luke Woodhouse', 'Woodhouse Luke', 'Aspinall Nathan', 'H', 'G') == 'H'
    assert t('zwyciezca: Valentin Royer', 'Royer Valentin', 'Walton Adam', 'H', 'G') == 'H'
    assert t('zwyciezca: Adam Walton', 'Royer Valentin', 'Walton Adam', 'H', 'G') == 'G'


def test_bez_zgadywania():
    t = dzienniki._typ_zwyciezcy
    assert t('zwyciezca: Luke', 'Woodhouse Luke', 'Humphries Luke', 'H', 'G') is None      # oba maja „Luke”
    assert t('zwyciezca', 'Hapoel Jerozolima', 'Rostock Seawolves', 'H', 'G') is None       # bez strony
    assert t('Zwyciezca 1', 'A', 'B', 'H', 'G') == 'H' and t('2', 'A', 'B', 'H', 'G') == 'G'
    assert t('Zwyciezca meczu - Grabher', 'Julia Grabher', 'Alice Tubello', 'H', 'G') == 'H'
