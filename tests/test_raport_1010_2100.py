"""Raport 10.10 21:00 nr 1 (i 18:00 nr 4): spadek liczby par kursy3 o 33% przy ofercie STS mniejszej o 2/3 — to nie awaria
pliku z telefonu. kursy3 wypisuje odsetek dopasowanych (niezalezny od wielkosci oferty): 18:00 LVBET 363/(363+86) ok. 81%,
21:00 243/(243+67) ok. 78%."""
import kursy3


def test_odsetek_dopasowanych(capsys):
    kursy3._dopasowane({'LVBET': {'jednoznaczne': 243, 'brak': 67, 'kilka': 0}, 'SUPERBET': {'jednoznaczne': 0, 'brak': 0, 'kilka': 0}})
    out = capsys.readouterr().out.splitlines()
    assert out[0] == 'LVBET: mecze STS dopasowane 243, brak 67, niejednoznaczne 0 (78% dopasowanych)'
    assert out[1] == 'SUPERBET: mecze STS dopasowane 0, brak 0, niejednoznaczne 0'
