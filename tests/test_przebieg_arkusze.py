"""przebieg.kontrola_arkuszy: arkusze opcjonalne (hokej, reczna, baseball...) odswiezane raz na dobe."""
import pandas as pd

import przebieg


def _arkusz(d, nazwa, godzin):
    t = (przebieg.teraz_pl() - pd.Timedelta(hours=godzin)).strftime('%Y-%m-%d %H:%M')
    pd.DataFrame({'data_aktualizacji': [t]}).to_csv(d / f'{nazwa}.csv', index=False)


def test_opcjonalne_do_30h_bez_uwagi_brak_nie_blokuje(tmp_path, monkeypatch, capsys):
    import terminarz
    t = pd.DataFrame({'data': ['2020-01-01'], 'sport': ['baseball'], 'gosp': ['a'], 'gosc': ['b']})   # terminarz jest, dzis bez baseballu
    monkeypatch.setattr(terminarz, 'wczytaj', lambda plik=None: t)
    monkeypatch.setattr(przebieg, 'HERE', str(tmp_path))
    for a in przebieg.ARKUSZE: _arkusz(tmp_path, a, 1)
    _arkusz(tmp_path, 'statystyki_hokej', 15)       # wieczorny zapis, w poludnie ok. 15 h — aktualny
    _arkusz(tmp_path, 'statystyki_reczna', 35)      # starszy niz 30 h — ostrzezenie
    assert przebieg.kontrola_arkuszy() == []        # opcjonalne nigdy nie blokuja przebiegu
    out = capsys.readouterr().out
    hokej = [l for l in out.splitlines() if 'statystyki_hokej' in l][0]
    reczna = [l for l in out.splitlines() if 'statystyki_reczna' in l][0]
    baseball = [l for l in out.splitlines() if 'statystyki_baseball' in l][0]
    assert 'UWAGA' not in hokej and 'UWAGA' in reczna and 'jest na Dysku' in baseball


def test_brak_wymaganego_to_blad(tmp_path, monkeypatch):
    monkeypatch.setattr(przebieg, 'HERE', str(tmp_path))
    assert len(przebieg.kontrola_arkuszy()) == len(przebieg.ARKUSZE)


def test_arkusz_opcjonalny_sport_w_terminarzu(tmp_path, monkeypatch, capsys):
    import terminarz
    t = pd.DataFrame({'data': [str(przebieg.DZIS)] * 3 + ['2020-01-01'], 'sport': ['hockey', 'hockey', 'football', 'hockey'],
                      'gosp': list('abcd'), 'gosc': list('efgh')})
    monkeypatch.setattr(terminarz, 'wczytaj', lambda plik=None: t)
    assert przebieg.mecze_w_terminarzu('hockey') == 2 and przebieg.mecze_w_terminarzu('handball') == 0
    monkeypatch.setattr(przebieg, 'HERE', str(tmp_path))
    monkeypatch.setattr(przebieg, 'DO_POBRANIA', [])
    for a in przebieg.ARKUSZE:
        pd.DataFrame({'data_aktualizacji': [przebieg.teraz_pl().strftime('%Y-%m-%d %H:%M')]}).to_csv(tmp_path / f'{a}.csv', index=False)
    przebieg.kontrola_arkuszy()
    out = capsys.readouterr().out
    assert 'JEST DZIS W TERMINARZU (2 meczow)' in out and przebieg.DO_POBRANIA == ['statystyki_hokej']


def test_arkusz_opcjonalny_bez_terminarza_do_pobrania(tmp_path, monkeypatch, capsys):
    # Raport 29.09 18:00, usterka 6: terminarza nie pobrano, MLB w ofercie, arkusza baseball nie pobrano
    import terminarz
    monkeypatch.setattr(terminarz, 'wczytaj', lambda plik=None: None)
    assert przebieg.mecze_w_terminarzu('baseball') is None
    monkeypatch.setattr(przebieg, 'HERE', str(tmp_path))
    monkeypatch.setattr(przebieg, 'DO_POBRANIA', [])
    for a in przebieg.ARKUSZE + ('statystyki_hokej',):
        pd.DataFrame({'data_aktualizacji': [przebieg.teraz_pl().strftime('%Y-%m-%d %H:%M')]}).to_csv(tmp_path / f'{a}.csv', index=False)
    przebieg.kontrola_arkuszy()
    out = capsys.readouterr().out
    assert 'terminarza nie ma' in out and 'statystyki_baseball' in przebieg.DO_POBRANIA
    assert 'statystyki_hokej' not in przebieg.DO_POBRANIA           # jest na miejscu


def test_swiezosc_brak_danych_zatrzymuje_przebieg(tmp_path, monkeypatch, capsys):
    # 30.09.2026 (przeglad): przebieg akceptowal kazdy kod swiezosc.py — „BRAK DANYCH” (kod 2) konczyl sie „PRZEBIEG OK”
    monkeypatch.setattr(przebieg, 'kontrola_zewn', lambda: [])
    monkeypatch.setattr(przebieg, 'kontrola_arkuszy', lambda: [])
    monkeypatch.setattr(przebieg, 'uruchom', lambda s, t: (2 if s == 'swiezosc.py' else 0, False))
    monkeypatch.setattr(przebieg.sys, 'argv', ['przebieg.py'])
    assert przebieg.main() == 3 and 'swiezosc.py zakonczyl sie bledem' in capsys.readouterr().out
    monkeypatch.setattr(przebieg, 'uruchom', lambda s, t: (1 if s == 'swiezosc.py' else 0, False))
    monkeypatch.setattr(przebieg, 'kontrola_bazy', lambda: [])
    monkeypatch.setattr(przebieg, 'kontrola_kalibracji', lambda: None)
    assert przebieg.main() != 3                                  # ostrzezenia (kod 1) nie zatrzymuja
