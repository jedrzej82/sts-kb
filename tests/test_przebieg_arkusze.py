"""przebieg.kontrola_arkuszy: arkusze opcjonalne (hokej, reczna, baseball...) odswiezane raz na dobe."""
import pandas as pd

import przebieg


def _arkusz(d, nazwa, godzin):
    t = (przebieg.teraz_pl() - pd.Timedelta(hours=godzin)).strftime('%Y-%m-%d %H:%M')
    pd.DataFrame({'data_aktualizacji': [t]}).to_csv(d / f'{nazwa}.csv', index=False)


def test_opcjonalne_do_30h_bez_uwagi_brak_nie_blokuje(tmp_path, monkeypatch, capsys):
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
