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
    assert n[0]['gosp'] == 'DAL' and n[0]['gosp_nazwa'] == 'Dallas Stars' and n[0]['gosc_nazwa'] == 'St. Louis Blues'
    assert n[0]['wynik_g'] == '' and len(z.NHL_PELNE) == 32
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
    assert w == [{'Elo Rank': '1', 'Player': 'Jannik Sinner', 'Elo': '2296.9', 'hElo': '2234.3'}]   # pusta kolumna-odstep usunieta


def test_transfermarkt_wiersze():
    # uklad z odpowiedzi 03.10: komorka gracza z wewnetrzna tabela (zdjecie, nazwisko, pozycja)
    t = ('<table class="items"><tbody><tr class="odd"><td><table class="inline-table"><tr><td rowspan="2"><img title="X"/></td>'
         '<td class="hauptlink"><a title="Junior Kroupi" href="/junior-kroupi/profil/spieler/955357">Junior Kroupi</a></td></tr>'
         '<tr><td>Centre-Forward</td></tr></table></td><td class="zentriert"><a title="AFC Bournemouth" '
         'href="/afc-bournemouth/startseite/verein/989"><img/></a></td><td class="links">Foot injury</td><td></td></tr>'
         '<tr class="even"><td class="zentriert"><a title="Arsenal FC" href="/fc-arsenal/startseite/verein/11/saison_id/2026"></a></td>'
         '<td class="hauptlink no-border-links"><a title="Arsenal FC" href="/fc-arsenal/startseite/verein/11">Arsenal</a></td>'
         '<td class="rechts">&euro;1.33bn</td></tr><tr class="odd"><td>25</td><td>3</td></tr></tbody></table>')
    w = z.tm_wiersze(t)
    assert w[0] == {'nazwa': 'Junior Kroupi', 'pozycja': 'Centre-Forward', 'klub': 'AFC Bournemouth', 'klub_id': '989',
                    'komorki': 'Foot injury'}
    assert (w[1]['nazwa'], w[1]['klub_id'], w[1]['komorki']) == ('Arsenal FC', '11', 'Arsenal | €1.33bn')
    assert len(w) == 2   # wiersz bez nazwy (inna tabela "items") pominiety
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


def test_s24_setka_cup(tmp_path, monkeypatch):
    # 03.10: Setka Cup (93 nazwy z oferty bez gracza w bazie) — slug z listy lig scores24, wiersze jak ligaproWiersz
    assert z.s24_slugi('<a href="/en/table-tennis/l-setka-cup-ukraine">x</a><a href="/en/table-tennis/l-czech-liga-pro">') == \
        ['czech-liga-pro', 'setka-cup-ukraine']
    n = {'id': 77, 'teams': [{'name': 'Smyk Vasyl'}, {'name': 'Dubinin Ihor'}], 'match_date': '2026-10-02T21:15:00Z',
         'result_score': '3:1', 'result_scores': [{'type': '1', 'value': '11:7'}, {'type': '2', 'value': '9:11'},
                                                  {'type': 'final', 'value': '3:1'}, {'type': '3', 'value': '11:5'}, {'type': '4', 'value': '11:8'}]}
    r = z.s24_wiersz(n, 'UKRAINE', 'Setka Cup')
    assert r == {'data': '2026-10-02', 'sport': 'table-tennis', 'kraj': 'UKRAINE', 'turniej': 'Setka Cup', 'runda': 'sc24:77',
                 'gosp': 'Smyk Vasyl', 'gosc': 'Dubinin Ihor', 'wg': 3, 'wa': 1, 'okresy_g': '11;9;11;11', 'okresy_a': '7;11;5;8',
                 'zwyciezca': 1, 'nawierzchnia': ''}
    assert z.s24_wiersz({**n, 'result_score': ''}, 'U', 'S') is None
    # scalanie miesiaca po id: drugi zapis tego samego meczu nie dubluje
    monkeypatch.setattr(z, 'WYNIKI_DIR', str(tmp_path / 'w'))
    kat = tmp_path / 'k'; kat.mkdir()
    z.scal_miesiace([r], 'wyniki_s24_inne', str(kat))
    p = z.scal_miesiace([r, {**r, 'runda': 'sc24:78'}], 'wyniki_s24_inne', str(kat))
    with gzip.open(p[0], 'rt') as f:
        linie = f.read().splitlines()
    assert os.path.basename(p[0]) == 'wyniki_s24_inne_2026-10.csv.gz' and len(linie) == 3
    assert linie[0] == ','.join(z.NAGL_WYNIKI)


def test_s24_okna_i_stan(monkeypatch):
    import datetime as dt
    s = z.Sesja(60)
    adresy = []
    s.get = lambda zr, url, *a, **k: (200, '<a href="/en/table-tennis/l-setka-cup">')
    s.get_json = lambda zr, url, *a, **k: adresy.append(url) or {'data': {'edges': []}}
    w, stan = {}, {}
    teraz = dt.datetime(2026, 10, 3, 10, 0)
    z.z_s24(s, w, teraz, stan, 0, '/tmp')
    assert len(adresy) == 21 * 24 and 'setka-cup/matches' in adresy[0]     # pierwsze uruchomienie (cron): 21 dni wstecz
    assert stan['s24_do'] == '2026-10-03T09:40:00'
    adresy.clear(); z.z_s24(s, w, dt.datetime(2026, 10, 3, 13, 0), stan, 0, '/tmp')
    assert len(adresy) == 3                                                  # kolejne: tylko od ostatniego pobrania


def test_s24_limit_i_kolejnosc(monkeypatch):
    # 03.10: wszystko z crona — zaleglosci s24 nie zjadaja budzetu (limit na uruchomienie, dociaganie w kolejnym)
    import datetime as dt
    s = z.Sesja(600)
    adresy = []
    s.get = lambda zr, url, *a, **k: (200, '<a href="/en/table-tennis/l-setka-cup">')
    s.get_json = lambda zr, url, *a, **k: adresy.append(url) or {'data': {'edges': []}}
    monkeypatch.setattr(z, 'S24_LIMIT_S', -1)
    stan = {}
    z.z_s24(s, {}, dt.datetime(2026, 10, 3, 10, 0), stan, 0, '/tmp')
    assert adresy == [] and stan['s24_do'] == '2026-09-12T10:00:00'       # nic nie pobrane, start zapamietany
    src = open(z.__file__, encoding='utf-8').read()
    assert src.index("('s24', lambda") < src.index("('fotmob', lambda")      # s24 przed dlugimi zrodlami


def test_s24_slug_przez_api_i_90minut_curl(monkeypatch):
    # 03.10 (przebieg 10:19): strony bez Setka Cup -> slug szukany przez API wsrod kandydatow i zapamietany w stanie;
    # 90minut HTTP 0 z Pythona -> druga proba http + curl
    import datetime as dt
    s = z.Sesja(600)
    s.get = lambda zr, url, *a, **k: (200, '<a href="/en/table-tennis/l-czech-liga-pro-1">')
    traf = 'ukraine-setka-cup-1'
    s.get_json = lambda zr, url, *a, **k: {'data': {'edges': [{'node': {}}] if f'/{traf}/' in url else []}}
    stan, w = {}, {}
    z.z_s24(s, w, dt.datetime(2026, 10, 3, 10, 0), stan, 1, '/tmp')
    assert stan['s24_slug'] == traf and any(x['cel'] for x in w['s24_ligi'])
    proby = []
    def get(zr, url, *a, curl=None, **k):
        proby.append((url, curl)); return (0, '') if curl is None else (200, '<a href="/liga/1/liga1.html"><b>CLJ</b></a>')
    s.get = get
    z.z_90minut(s, w, dt.datetime(2026, 10, 3, 10, 0))
    assert proby[1] == ('http://www.90minut.pl/', []) and proby[2] == ('http://www.90minut.pl/liga/1/liga1.html', [])
    assert w['90minut_ligi'] == [{'turniej': 'CLJ U19', 'link': '/liga/1/liga1.html', 'kod': 200, 'mecze': 0}]


def test_90minut_parser_i_kodowanie():
    # 03.10: 90minut.pl jest w ISO-8859-2; wiersze meczow: gospodarz | wynik | gosc [| data], naglowek kolejki z data
    html = ('<html><head><meta http-equiv="Content-Type" content="text/html; charset=iso-8859-2"></head><table>'
            '<tr><td colspan=4><b>Kolejka 11 - 27-28 września 2026</b></td></tr>'
            '<tr><td align="right">Wisła II Płock</td><td><a href="/mecz/1">2-1</a></td><td>Elana Toruń</td><td>27 września, 15:00</td></tr>'
            '<tr><td align="right">Bałtyk Koszalin</td><td>0-0</td><td>Grom Nowy Staw</td><td></td></tr>'
            '<tr><td>Kotwica Kórnik</td><td>-</td><td>Unia Swarzędz</td><td>4 października, 16:00</td></tr></table></html>')
    t = z.dekoduj(html.encode('iso-8859-2'))
    assert 'Wisła II Płock' in t and 'Bałtyk' in t
    r = z.m90_wiersze(t, 'III Liga - Group II', 2026)
    assert [(x['data'], x['gosp'], x['gosc'], x['wg'], x['wa'], x['runda']) for x in r] == [
        ('2026-09-27', 'Wisła II Płock', 'Elana Toruń', 2, 1, '90m:11'), ('2026-09-27', 'Bałtyk Koszalin', 'Grom Nowy Staw', 0, 0, '90m:11')]
    assert z._data_pl('3.10.2026', 2025) == '2026-10-03' and z._data_pl('1 sierpnia', 2026) == '2026-08-01'


def test_s24_kandydaci_raz_na_tydzien():
    import datetime as dt
    s = z.Sesja(600)
    adresy = []
    s.get = lambda zr, url, *a, **k: adresy.append(url) or (200, '<a href="/en/table-tennis/l-czech-liga-pro-1">')
    s.get_json = lambda zr, url, *a, **k: adresy.append(url) or {'data': {'edges': []}}
    stan, w = {}, {}
    z.z_s24(s, w, dt.datetime(2026, 10, 3, 10, 0), stan, 0, '/tmp')
    n1 = len(adresy)
    assert n1 == 1 + len(z.SETKA_STRONY) + len(z.S24_KANDYDACI) and stan['s24_proba'] == '2026-10-03'
    assert len(w['setka_strony']) == len(z.SETKA_STRONY)
    adresy.clear(); z.z_s24(s, {}, dt.datetime(2026, 10, 5, 10, 0), stan, 0, '/tmp')
    assert len(adresy) == 1                                         # 2 dni pozniej: tylko strona glowna
    adresy.clear(); z.z_s24(s, {}, dt.datetime(2026, 10, 10, 10, 0), stan, 0, '/tmp')
    assert len(adresy) == n1                                        # po tygodniu znowu pelne szukanie


def test_90minut_bez_dzisiejszych_wynikow():
    # 03.10 (cron 14:40): wynik meczu z dzisiejsza data moze byc z trakcie gry — tylko mecze do wczoraj
    import datetime as dt
    s = z.Sesja(600)
    strona = ('<tr><td colspan=4>Kolejka 11 - 2 października 2026</td></tr>'
              '<tr><td>A</td><td>1-0</td><td>B</td><td>2 października</td></tr>'
              '<tr><td>C</td><td>7-0</td><td>D</td><td>3 października</td></tr>')
    s.get = lambda zr, url, *a, **k: (200, '<a href="/liga/1/liga1.html">CLJ</a>') if url.endswith('pl/') else (200, strona)
    w = {}
    z.z_90minut(s, w, dt.datetime(2026, 10, 3, 12, 40))
    assert [(x['gosp'], x['data']) for x in w['90minut_mecze']] == [('A', '2026-10-02')]


# 03.10.2026: prawdziwa odpowiedz setkacup.com /api/Tournaments/en?date=2026-10-02 (telefon 15:52) — 2 mecze turnieju
# „2026-10-02 Men Morning Rome” (bez zdjec) i walkower z „Men Evening Europe” (statusId 4, technicalResult 1, wynik L/W)
SETKA_MECZE = [{'id': 832988, 'tournamentId': 63306, 'statusId': 3, 'position': 1, 'player1': {'id': 1312, 'firstName': 'Oleksandr', 'lastName': 'Syksa', 'gender': True}, 'player1ColorId': 2, 'player2': {'id': 1318, 'firstName': 'Oleksandr', 'lastName': 'Lyman', 'gender': True}, 'player2ColorId': 5, 'player1Score': '3', 'player2Score': '1', 'technicalResult': 0, 'startDate': '2026-10-02T04:30:00.000Z', 'activePlayerId': 1318, 'reverse': 1, 'forPositionId': 1, 'tournamentName': '2026-10-02 Men Morning Rome', 'locationId': 13, 'dayPeriodToken': 1, 'correction': 0, 'winner': {'id': 1312, 'firstName': 'Oleksandr', 'lastName': 'Syksa', 'gender': True}, 'setScores': [{'match_id': 832988, 'number': 1, 'p1Score': 6, 'p2Score': 11}, {'match_id': 832988, 'number': 2, 'p1Score': 11, 'p2Score': 4}, {'match_id': 832988, 'number': 3, 'p1Score': 11, 'p2Score': 6}, {'match_id': 832988, 'number': 4, 'p1Score': 14, 'p2Score': 12}]}, {'id': 832989, 'tournamentId': 63306, 'statusId': 3, 'position': 2, 'player1': {'id': 177, 'firstName': 'Dmytro', 'lastName': 'Prylepa', 'gender': True}, 'player1ColorId': 2, 'player2': {'id': 1306, 'firstName': 'Dmytro', 'lastName': 'Kuzmenko', 'gender': True}, 'player2ColorId': 5, 'player1Score': '3', 'player2Score': '2', 'technicalResult': 0, 'startDate': '2026-10-02T05:00:00.000Z', 'activePlayerId': 177, 'reverse': 1, 'forPositionId': 1, 'tournamentName': '2026-10-02 Men Morning Rome', 'locationId': 13, 'dayPeriodToken': 1, 'correction': 0, 'winner': {'id': 177, 'firstName': 'Dmytro', 'lastName': 'Prylepa', 'gender': True}, 'setScores': [{'match_id': 832989, 'number': 1, 'p1Score': 6, 'p2Score': 11}, {'match_id': 832989, 'number': 2, 'p1Score': 11, 'p2Score': 6}, {'match_id': 832989, 'number': 3, 'p1Score': 11, 'p2Score': 8}, {'match_id': 832989, 'number': 4, 'p1Score': 2, 'p2Score': 11}, {'match_id': 832989, 'number': 5, 'p1Score': 11, 'p2Score': 5}]}]
SETKA_WALKOWER = {'id': 833078, 'tournamentId': 63313, 'statusId': 4, 'player1': {'firstName': 'Volodymyr', 'lastName': 'Voronenkov', 'gender': True}, 'player2': {'firstName': 'Andrii', 'lastName': 'Hrabskyi', 'gender': True}, 'player1Score': 'L', 'player2Score': 'W', 'technicalResult': 1, 'startDate': '2026-10-02T10:40:00.000Z', 'setScores': []}


def test_setka_wiersze_z_prawdziwej_odpowiedzi():
    r = z.setka_wiersze([{'id': 63306, 'matches': SETKA_MECZE + [SETKA_WALKOWER]}])
    assert [(x['data'], x['gosp'], x['gosc'], x['wg'], x['wa'], x['zwyciezca']) for x in r] == [
        ('2026-10-02', 'Syksa Oleksandr', 'Lyman Oleksandr', 3, 1, 1), ('2026-10-02', 'Prylepa Dmytro', 'Kuzmenko Dmytro', 3, 2, 1)]
    assert r[0]['okresy_g'] == '6;11;11;14' and r[0]['okresy_a'] == '11;4;6;12'
    assert r[0]['runda'] == 'setka:832988' and r[0]['turniej'] == 'Setka Cup' and r[0]['kraj'] == 'UKRAINE'
    assert set(r[0]) == set(z.NAGL_WYNIKI)


def test_setka_dni_od_stanu_i_limit(tmp_path, monkeypatch):
    import datetime as dt
    monkeypatch.setattr(z, 'WYNIKI_DIR', str(tmp_path / 'w'))
    kat = tmp_path / 'k'; kat.mkdir()
    s = z.Sesja(600)
    pyt = []
    s.get_json = lambda zr, url, *a, **k: pyt.append(url) or [{'id': 1, 'matches': SETKA_MECZE}]
    stan, w = {}, {}
    z.z_setka(s, w, dt.datetime(2026, 10, 3, 13, 0), stan, str(kat))
    assert len(pyt) == z.SETKA_HIST_DNI + 1 and pyt[0].endswith('date=2026-09-12') and pyt[-1].endswith('date=2026-10-03')
    assert stan['setka_do'] == '2026-10-03'                    # dzisiejszy dzien pobierany ponownie przy nastepnym
    assert w['_pliki_wynikow'] and all('wyniki_setka_inne_' in p for p in w['_pliki_wynikow'])
    pyt.clear(); z.z_setka(s, {}, dt.datetime(2026, 10, 3, 16, 0), stan, str(kat))
    assert pyt == ['https://setkacup.com/api/Tournaments/en?date=2026-10-03']
    s.get_json = lambda zr, url, *a, **k: None                    # blad -> stan bez zmian, nastepne uruchomienie ponowi
    z.z_setka(s, {}, dt.datetime(2026, 10, 4, 1, 0), stan, str(kat))
    assert stan['setka_do'] == '2026-10-03'

