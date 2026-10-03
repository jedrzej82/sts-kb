"""termux/zrodla.py — parsery dodatkowych zrodel (03.10.2026). Dane wejsciowe = ksztalty odpowiedzi serwisow;
po pierwszym uruchomieniu na telefonie sprawdzane z zrodla_surowe_*.jsonl.gz."""
import gzip
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'termux'))
import zrodla as z  # noqa: E402


def test_elo_reprezentacji():
    w = z.elo_reprezentacji('1\t1\tES\t2172\t2150\n2\t3\tAR\t2140\t2101\nsmiec\n', 'ES\tSpain\nAR\tArgentina\n')
    assert w == [{'pozycja': '1', 'kod': 'ES', 'nazwa': 'Spain', 'elo': 2172},
                 {'pozycja': '2', 'kod': 'AR', 'nazwa': 'Argentina', 'elo': 2140}]


def test_fotmob_mecze_i_szczegoly():
    j = {'leagues': [{'primaryId': 47, 'name': 'Premier League', 'ccode': 'ENG', 'matches': [
        {'id': 1, 'home': {'name': 'Arsenal'}, 'away': {'name': 'Chelsea'},
         'status': {'utcTime': '2026-10-03T14:00:00Z', 'finished': False, 'started': False}}]}]}
    m = z.fotmob_mecze(j, '2026-10-03')
    assert m[0]['gosp'] == 'Arsenal' and m[0]['liga_id'] == 47 and m[0]['start_utc'] == '2026-10-03T14:00:00Z'
    det = {'content': {
        'stats': {'Periods': {'All': {'stats': [{'stats': [{'key': 'expected_goals', 'stats': ['1.84', '0.62']}]}]}}},
        'lineup': {'lineupType': 'standard', 'homeTeam': {'starters': [{'name': 'Raya'}],
                                                          'unavailable': [{'name': 'Saka', 'unavailability': {'type': 'injury', 'expectedReturn': 'Late October'}}]},
                   'awayTeam': {'starters': [{'name': 'Sanchez'}], 'unavailable': []}},
        'matchFacts': {'infoBox': {'Stadium': {'name': 'Emirates', 'city': 'London', 'lat': 51.55, 'long': -0.108},
                                   'Referee': {'text': 'Michael Oliver'}}}}}
    w = z.fotmob_szczegoly(det)
    assert (w['xg_gosp'], w['xg_gosc']) == ('1.84', '0.62')
    assert w['sklad_gosp'] == 'Raya' and w['sklad_status'] == 'standard'
    assert w['nieobecni_gosp'] == 'Saka (injury do Late October)' and w['nieobecni_gosc'] == ''
    assert (w['lat'], w['lon'], w['miasto'], w['sedzia']) == (51.55, -0.108, 'London', 'Michael Oliver')
    assert z.fotmob_szczegoly(None)['xg_gosp'] == ''


def test_sofascore():
    j = {'events': [{'id': 9, 'tournament': {'name': 'LaLiga 2', 'category': {'name': 'Spain'}},
                     'homeTeam': {'name': 'Eldense'}, 'awayTeam': {'name': 'Real Oviedo'}, 'startTimestamp': 1791052200,
                     'status': {'type': 'notstarted'}, 'homeScore': {}, 'awayScore': {}}]}
    m = z.sofa_mecze(j, 'football', '2026-10-03')
    assert m[0]['gosp'] == 'Eldense' and m[0]['status'] == 'notstarted' and m[0]['wynik_g'] == ''
    lu = {'confirmed': True, 'home': {'missingPlayers': [{'player': {'name': 'X Y'}, 'type': 'missing', 'reason': 1}]}, 'away': {}}
    ev = {'event': {'referee': {'name': 'R', 'games': 40, 'yellowCards': 180, 'redCards': 6},
                    'venue': {'city': {'name': 'Elda'}, 'venueCoordinates': {'latitude': 38.47, 'longitude': -0.79}}}}
    w = z.sofa_sklad(lu, ev)
    assert w['potwierdzony'] is True and w['nieobecni_gosp'] == 'X Y (missing/1)' and w['nieobecni_gosc'] == ''
    assert (w['sedzia'], w['sedzia_mecze'], w['sedzia_zolte'], w['lat'], w['miasto']) == ('R', 40, 180, 38.47, 'Elda')
    w0 = z.sofa_sklad(None, None)
    assert w0['potwierdzony'] == '' and w0['sedzia'] == ''


def test_understat_json_i_html():
    d = [{'id': '5', 'isResult': True, 'h': {'title': 'Arsenal'}, 'a': {'title': 'Chelsea'}, 'goals': {'h': '2', 'a': '1'},
          'xG': {'h': '1.9', 'a': '0.7'}, 'datetime': '2025-08-16 16:30:00'}]
    w = z.understat_mecze(json.dumps({'dates': d}), 'EPL', 2025)
    assert w[0]['xg_g'] == '1.9' and w[0]['gosc'] == 'Chelsea' and w[0]['sezon'] == 2025
    zakod = ''.join(f'\\x{b:02X}' for b in json.dumps(d).encode())
    w2 = z.understat_mecze(f"<script>var datesData = JSON.parse('{zakod}');</script>", 'EPL', 2025)
    assert w2 == w


def test_tabele_html_i_nhl_i_bramkarze():
    t = '<table class="items"><tr><th>Gracz</th><th>Kontuzja</th></tr><tr><td><a>Saka&nbsp;B.</a></td><td>Hamstring</td></tr></table>'
    assert z.tabele_html(t, 'items') == [['Gracz', 'Kontuzja'], ['Saka B.', 'Hamstring']]
    assert z.tabele_html(t, 'inna') == []
    g = {'games': [{'id': 1, 'startTimeUTC': '2026-10-08T23:00:00Z', 'gameState': 'FUT',
                    'homeTeam': {'abbrev': 'DAL', 'name': {'default': 'Stars'}}, 'awayTeam': {'abbrev': 'STL', 'name': {'default': 'Blues'}}}]}
    n = z.nhl_mecze(g, '2026-10-08')
    assert n[0]['gosp'] == 'DAL' and n[0]['gosc_nazwa'] == 'Blues' and n[0]['wynik_g'] == ''
    nd = {'props': {'pageProps': {'date': '2026-10-02', 'data': [
        {'dateGmt': '2026-10-02T22:30:00.000Z', 'homeTeamName': 'Detroit Red Wings', 'homeGoalieName': 'John Gibson',
         'homeNewsStrengthName': 'Confirmed', 'homeGoalieSavePercentage': '0.95', 'awayTeamName': 'New York Rangers',
         'awayGoalieName': 'Dylan Garand', 'awayNewsStrengthName': 'Likely'}]}}}
    b = z.bramkarze(f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(nd)}</script>')
    assert (b[0]['data'], b[0]['bramkarz_gosp'], b[0]['status_gosp'], b[0]['sv_proc_gosp']) == ('2026-10-02', 'John Gibson', 'Confirmed', '0.95')
    assert (b[0]['druzyna_gosc'], b[0]['status_gosc'], b[0]['gaa_gosc']) == ('New York Rangers', 'Likely', '')
    assert z.bramkarze('brak') == []


def test_pogoda_na_godzine_i_utc():
    m = [{'mecz_id': 1, 'start_utc': '2026-10-03T14:00:00', 'lat': 1, 'lon': 2}]
    o = {'hourly': {'time': ['2026-10-03T13:00', '2026-10-03T14:00'], 'temperature_2m': [10, 11],
                    'precipitation': [0, 2.5], 'wind_speed_10m': [5, 30]}}
    w = z.pogoda_na_godzine(o, m)
    assert (w[0]['temp'], w[0]['opad_mm'], w[0]['wiatr_kmh']) == (11, 2.5, 30)
    assert str(z.utc_z('2026-10-03T16:00:00+02:00')) == '2026-10-03 14:00:00'
    assert str(z.utc_z(0)) == '1970-01-01 00:00:00' and z.utc_z('x') is None and z.utc_z('') is None


def test_main_bez_sieci_zapisuje_diag(tmp_path, monkeypatch):
    # bez dostepu do sieci (jak w CI) skrypt nie moze sie wywrocic: zapisuje diag i surowe, zwraca 0
    monkeypatch.setattr(z, 'STAN', str(tmp_path / 'stan.json'))
    monkeypatch.setattr(z.Sesja, 'get', lambda self, zr, url, *a, **k: (self.kody.setdefault(zr, {}).setdefault(0, 0), (0, ''))[1])
    assert z.main(['--katalog', str(tmp_path), '--budzet-min', '1']) == 0
    zipy = list(tmp_path.glob('zrodla_*.zip'))
    assert len(zipy) == 1 and [p.name for p in tmp_path.iterdir() if p.name != 'stan.json'] == [zipy[0].name]
    with zipfile.ZipFile(zipy[0]) as zf:
        nazwy = zf.namelist()
        diag = [n for n in nazwy if n.startswith('zrodla_diag_')]
        assert len(diag) == 1 and 'transfermarkt' in zf.read(diag[0]).decode()
        assert any(n.startswith('zrodla_surowe_') for n in nazwy)
        assert not any(n.startswith('zrodla_fotmob_') for n in nazwy)


def test_zapisz(tmp_path):
    p = z.zapisz(str(tmp_path), 'x', [{'a': 1}, {'a': 2, 'b': 3}], 'T')
    with gzip.open(p, 'rt') as f:
        assert f.read().splitlines() == ['a,b', '1,', '2,3']
    assert z.zapisz(str(tmp_path), 'y', [], 'T') is None


def test_tabela_zagniezdzona_tennis_abstract():
    # 03.10 07:50 (telefon): #reportable siedzi w <table width=1000px> — wczesniej parser bral zewnetrzna tabele
    t = ('<table width="1000px"><tr><td><table id="reportable" class="tablesorter"><tr><th>Elo&nbsp;Rank</th><th>Player</th>'
         '<th>Elo</th><th>&nbsp;</th><th>hElo</th></tr><tr><td>1</td><td>Jannik&nbsp;Sinner</td><td>2296.9</td><td></td>'
         '<td>2234.3</td></tr></table></td></tr></table>')
    w = z.tabela_z_naglowkiem(z.tabele_html(t, 'reportable'))
    assert w == [{'Elo Rank': '1', 'Player': 'Jannik Sinner', 'Elo': '2296.9', 'k3': '', 'hElo': '2234.3'}]


def test_transfermarkt_wiersze():
    # uklad z odpowiedzi 03.10: komorka gracza z wewnetrzna tabela (zdjecie, nazwisko, pozycja)
    t = ('<table class="items"><tbody><tr class="odd"><td><table class="inline-table"><tr><td rowspan="2"><img title="X"/></td>'
         '<td class="hauptlink"><a title="Junior Kroupi" href="/junior-kroupi/profil/spieler/955357">Junior Kroupi</a></td></tr>'
         '<tr><td>Centre-Forward</td></tr></table></td><td class="zentriert"><a title="AFC Bournemouth" '
         'href="/afc-bournemouth/startseite/verein/989"><img/></a></td><td class="links">Foot injury</td><td></td></tr>'
         '<tr class="even"><td class="zentriert"><a title="Arsenal FC" href="/fc-arsenal/startseite/verein/11/saison_id/2026"></a></td>'
         '<td class="hauptlink no-border-links"><a title="Arsenal FC" href="/fc-arsenal/startseite/verein/11">Arsenal</a></td>'
         '<td class="rechts">&euro;1.33bn</td></tr></tbody></table>')
    w = z.tm_wiersze(t)
    assert w[0] == {'nazwa': 'Junior Kroupi', 'pozycja': 'Centre-Forward', 'klub': 'AFC Bournemouth', 'klub_id': '989',
                    'komorki': 'Foot injury'}
    assert (w[1]['nazwa'], w[1]['klub_id'], w[1]['komorki']) == ('Arsenal FC', '11', 'Arsenal | €1.33bn')
    assert z.tm_wiersze('brak tabeli') == []


def test_sofascore_blokada_probuje_wariantow_i_przerywa():
    # 03.10: 403 "challenge" na obu adresach — kazdy wariant (urllib, pelne naglowki, curl, curl http2) raz na adres,
    # potem koniec zamiast 28 prob; proby zapisane do diagnozy
    import datetime as dt
    s = z.Sesja(60)
    proby = []
    s.get = lambda zr, url, nag=None, proby_=None, **k: (proby.append((url, k.get('curl'))), (403, '{"error":{"reason":"challenge"}}'))[1]
    w = {}
    z.z_sofa(s, w, dt.date(2026, 10, 3), dt.datetime(2026, 10, 3, 6))
    assert w['sofascore_mecze'] == [] and len(proby) == 2 * len(z.SOFA_WARIANTY)
    assert [p['wariant'] for p in w['sofascore_proby']][::2] == [n for n, _, _ in z.SOFA_WARIANTY]
    assert w['sofascore_proby'][0]['odpowiedz'].startswith('{"error"')


def test_sofascore_pierwszy_dzialajacy_wariant_obsluguje_reszte():
    import datetime as dt
    s = z.Sesja(60)
    uzyte = []

    def get(zr, url, nag=None, proby=2, curl=None, **k):
        uzyte.append(curl)
        if curl is None: return 403, 'challenge'
        return 200, json.dumps({'events': [{'id': 1, 'homeTeam': {'name': 'A'}, 'awayTeam': {'name': 'B'},
                                            'status': {'type': 'finished'}}]})
    s.get = get
    w = {}
    z.z_sofa(s, w, dt.date(2026, 10, 3), dt.datetime(2026, 10, 3, 6))
    assert [p['wariant'] for p in w['sofascore_proby']] == ['urllib', 'urllib', 'urllib_pelne', 'urllib_pelne', 'curl']
    assert len(w['sofascore_mecze']) == 2 * len(z.SOFA_SPORTY) and all(c == ['--http1.1'] for c in uzyte[5:])


def test_curl_get_parsuje_kod(monkeypatch):
    class R:
        stdout = b'{"a":1}\n__KOD__403'
        stderr = b''
    monkeypatch.setattr(z.shutil, 'which', lambda x: '/usr/bin/curl')
    monkeypatch.setattr(z.subprocess, 'run', lambda cmd, **k: R())
    assert z.curl_get('https://x', {'A': 'b'}) == (403, '{"a":1}')


def test_darty_api_i_scalanie():
    # uklad z prawdziwej odpowiedzi 03.10 08:35 (srednia: sumField1/2; % meczow: total_matches/wins)
    sr = {'recordsTotal': 3, 'data': [
        {'player_key': 5403, 'player_name': 'Luke Littler', 'country': 'ENG', 'sumField1': 810748, 'sumField2': 24059,
         'stat': '101.09', 'rank': 1},
        {'player_key': 34, 'player_name': 'Luke Humphries', 'country': 'ENG', 'sumField1': 767928, 'sumField2': 23153,
         'stat': '99.50', 'rank': 2},
        {'player_key': 9, 'player_name': 'Ee Kai', 'country': None, 'sumField1': 0, 'sumField2': 3, 'stat': '0.00', 'rank': 3}]}
    pm = {'data': [{'player_key': 5403, 'player_name': 'Luke Littler', 'country': 'ENG', 'total_matches': 120, 'wins': 95,
                    'stat': '95/120', 'rank': 5},
                   {'player_key': 34, 'player_name': 'Luke Humphries', 'country': 'ENG', 'total_matches': 110, 'wins': 80,
                    'stat': '80/110', 'rank': 9},
                   {'player_key': 9, 'player_name': 'Ee Kai', 'country': None, 'total_matches': 2, 'wins': 0, 'stat': '0/2', 'rank': 900}]}
    w = z.darty_api(sr, 'srednia') + z.darty_api(pm, 'proc_meczow')
    assert w[0]['kraj'] == 'ENG' and w[2]['kraj'] == '' and w[3]['mianownik'] == 120 and w[3]['licznik'] == 95
    sc = z.darty_scal(w)
    assert [x['zawodnik'] for x in sc] == ['Luke Littler', 'Luke Humphries']      # Ee Kai: 2 mecze < 10
    assert sc[0] == {'klucz': 5403, 'zawodnik': 'Luke Littler', 'kraj': 'ENG', 'srednia': '101.09', 'srednia_n': 24059,
                     'mecze': 120, 'wygrane': 95}
    assert z.darty_api(None, 'x') == [] and z.darty_scal([]) == []
