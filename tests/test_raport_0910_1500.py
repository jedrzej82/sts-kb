"""Raport 09.10 15:00.
  1. sezon.py pilka "HNK Gorica" "Rudes Zagrzeb" -> NIE ZNALEZIONO; arkusz statystyki_druzyn (HNL) pisze „NK Rudes”.
     Sprawdzone na arkuszu z paczki 09.10 06:46: po aliasie SEZON HNK Gorica – NK Rudes (HNL; mecze 8/8).
  3. kursy3 LVBET „nie znaleziono nogi 2” (Al-Jazeera Amman – Al-Wehdat): w pliku z telefonu 09.10 14:46 LVBET tego
     meczu nie ma (jest tylko SUPERBET) — prawidlowe UNKNOWN, bez zmian w kodzie."""
import sezon

HNL = [{'druzyna': n, 'liga': 'HNL', 'mecze_ze_statami': '8'} for n in ('HNK Gorica', 'NK Rudes', 'Dinamo Zagreb')]


def test_alias_arkusza_rudes_zagrzeb():
    w = sezon.znajdz(HNL, 'Rudes Zagrzeb', sport='pilka')[0]
    assert w and w['druzyna'] == 'NK Rudes'
    # bez zmian: pelna nazwa z arkusza i rywal
    assert sezon.znajdz(HNL, 'NK Rudes', sport='pilka')[0]['druzyna'] == 'NK Rudes'
    assert sezon.znajdz(HNL, 'HNK Gorica', sport='pilka')[0]['druzyna'] == 'HNK Gorica'
