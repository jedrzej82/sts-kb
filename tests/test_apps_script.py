"""30.09.2026 (przeglad Apps Script): skryptow nie da sie uruchomic w CI — pilnujemy kolejnosci krokow w kodzie
i klucza scalania (ten ostatni: node, jesli jest)."""
import json
import os
import re
import shutil
import subprocess

import pytest

AS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'apps_script')


def _txt(n):
    return open(os.path.join(AS, n), encoding='utf-8').read()


def _cialo(txt, funkcja):
    i = txt.index(f'function {funkcja}(')
    j = txt.find('\nfunction ', i + 1)
    return txt[i:j if j > 0 else None]


def test_ligapro_postep_po_zapisie_plikow():
    c = _cialo(_txt('ligapro.gs'), 'ligaproPracuj')
    assert c.index('ligaproZapisz(nowe)') < c.index("P.setProperty('ligapro_hist'")


def test_terminarz_bez_pilki_nie_nadpisuje():
    t = _txt('terminarz.gs')
    for f in ('terminarzFs',):
        c = _cialo(t, f)
        assert 'brakPilki' in c and c.index('brakPilki.length') < c.index("folder.createFile(Utilities.gzip")
    c = t[t.index('var wiersze = [], nazwySportow = {}, brakPilki = []'):t.index('// Flashscore: identyfikator sportu')]
    assert c.index('if (brakPilki.length)') < c.index('folder.createFile(Utilities.gzip')


def test_historia_niepelny_dzien_nie_jest_gotowy():
    c = _cialo(_txt('terminarz.gs'), 'wyniki365Historia')
    assert c.index('if (niepelny)') < c.index('gotowe[d] = 1')


def test_klucz_scalania_z_pol_csv():
    t = _txt('terminarz.gs')
    assert not re.search(r"split\(','\)\.slice\(0, 7\)", t)
    if not shutil.which('node'):
        pytest.skip('brak node')
    csv = _cialo(t, 'terminarzCsv'); kl = _cialo(t, '_klucz7_')
    js = csv + '\n' + kl + r'''
    // Utilities.parseCsv — prosty parser RFC 4180 (tylko do testu)
    var Utilities = {parseCsv: function (s) { var o = [], f = '', q = false;
      for (var i = 0; i < s.length; i++) { var ch = s[i];
        if (q) { if (ch === '"' && s[i + 1] === '"') { f += '"'; i++; } else if (ch === '"') q = false; else f += ch; }
        else if (ch === '"') q = true; else if (ch === ',') { o.push(f); f = ''; } else f += ch; }
      o.push(f); return [o]; }};
    var a = terminarzCsv(['2026-09-28', 'handball', 'Europe', 'EHF, Group A', '', 'Kielce', 'Veszprem', 30, 28]);
    var b = terminarzCsv(['2026-09-28', 'handball', 'Europe', 'EHF, Group A', '', 'Kielce', 'Szeged', 27, 27]);
    var stary = function (w) { return w.split(',').slice(0, 7).join(','); };
    console.log(JSON.stringify([stary(a) === stary(b), _klucz7_(a) === _klucz7_(b), _klucz7_(a).split('\u0001')[6]]));
    '''
    r = subprocess.run(['node', '-e', js], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = r.stdout.strip()
    assert out == '[true,false,"Veszprem"]'                  # stary klucz: kolizja; nowy: rozne mecze


def _node_wyniki_live(kod_testu):
    if not shutil.which('node'):
        pytest.skip('brak node')
    t = _txt('wyniki_live.gs')
    js = '\n'.join(_cialo(t, f) for f in ('bladApi_', '_pkt_', 'meczPilka', 'meczGra', 'meczOpenLiga')) + '\n' + kod_testu
    r = subprocess.run(['node', '-e', js], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_wyniki_live_normalizacja_zrodel():
    # 17.10.2026: ksztalty odpowiedzi API-Sports (pilka v3 /fixtures, inne v1 /games) i OpenLigaDB (prawdziwy mecz 16.10)
    w = _node_wyniki_live(r'''
    var pil = meczPilka({fixture: {id: 7, timestamp: 1792252200, status: {short: '2H', elapsed: 67}},
      league: {name: 'Championship', country: 'England'}, teams: {home: {id: 1, name: 'Southampton'}, away: {id: 2, name: 'Bolton'}},
      goals: {home: 1, away: 2}, score: {halftime: {home: 0, away: 1}},
      events: [{type: 'Goal', detail: 'Normal Goal', time: {elapsed: 20}, team: {id: 2}, player: {name: 'X'}},
               {type: 'Card', detail: 'Yellow Card', time: {elapsed: 30}, team: {id: 1}, player: {name: 'Y'}},
               {type: 'Goal', detail: 'Penalty', time: {elapsed: 55}, team: {id: 1}, player: {name: 'Z'}},
               {type: 'Goal', detail: 'Missed Penalty', time: {elapsed: 60}, team: {id: 1}, player: {name: 'Z'}},
               {type: 'Goal', detail: 'Own Goal', time: {elapsed: 66}, team: {id: 2}, player: {name: 'Q'}}]});
    var kosz = meczGra('basketball', {id: 9, timestamp: 1792260000, status: {short: 'Q3', timer: '5'}, league: {name: 'Energa Basket Liga'},
      country: {name: 'Poland'}, teams: {home: {name: 'Anwil'}, away: {name: 'Trefl'}}, scores: {home: {quarter_1: 20, total: 61}, away: {total: 58}}});
    var hok = meczGra('hockey', {id: 3, timestamp: 1, status: {short: 'NS'}, league: {name: 'KHL'}, country: {name: 'Russia'},
      teams: {home: {name: 'A'}, away: {name: 'B'}}, scores: {home: null, away: null}});
    var ol = meczOpenLiga('bl1', {matchID: 83203, matchDateTimeUTC: '2026-10-16T18:30:00Z', leagueName: '1. Fußball-Bundesliga 2026/2027',
      team1: {teamId: 91, teamName: 'Eintracht Frankfurt'}, team2: {teamId: 65, teamName: '1. FC Köln'}, matchIsFinished: true,
      matchResults: [{resultTypeID: 1, pointsTeam1: 0, pointsTeam2: 0}, {resultTypeID: 2, pointsTeam1: 1, pointsTeam2: 0}],
      goals: [{scoreTeam1: 1, scoreTeam2: 0, matchMinute: 77, goalGetterName: 'Younes Ebnoutalib', scoringTeamId: 91, isPenalty: false, isOwnGoal: false}]});
    console.log(JSON.stringify([pil, kosz, hok, ol, bladApi_(200, {errors: {plan: 'Free plans do not have access to this season'}}),
      bladApi_(200, {errors: []}), bladApi_(499, {}), meczPilka({}), meczGra('hockey', null)]));
    ''')
    pil, kosz, hok, ol, e1, e2, e3, n1, n2 = w
    assert [pil[k] for k in ('a', 'b', 'ga', 'gb', 'st', 'min', 'pol', 'kr', 'lg')] == ['Southampton', 'Bolton', 1, 2, '2H', 67, [0, 1], 'England', 'Championship']
    assert pil['gole'] == [[20, 'X', 0, 1, 2, ''], [55, 'Z', 1, 1, 1, 'k'], [66, 'Q', 1, 2, 2, 's']]
    assert [kosz[k] for k in ('s', 'ga', 'gb', 'st', 'kr')] == ['basketball', 61, 58, 'Q3', 'Poland']
    assert hok['ga'] is None and hok['st'] == 'NS'
    assert [ol[k] for k in ('t', 'a', 'b', 'ga', 'gb', 'st', 'pol')] == [1792175400, 'Eintracht Frankfurt', '1. FC Köln', 1, 0, 'FT', [0, 0]]
    assert ol['gole'] == [[77, 'Younes Ebnoutalib', 1, 0, 1, '']]
    assert e1 == 'plan: Free plans do not have access to this season' and e2 is None and e3 == 'HTTP 499'
    assert n1 is None and n2 is None


def test_wyniki_live_klucz_tylko_we_wlasciwosciach():
    t = _txt('wyniki_live.gs')
    assert "P.getProperty('APISPORTS_KEY')" in t and not re.search(r"x-apisports-key'\s*:\s*'[0-9a-f]{20,}", t)
    c = _cialo(t, 'wynikiLive')
    # budzet darmowego planu: limit sprawdzany przed zapytaniem, licznik zapisany po petli
    assert c.index('st.n >= LIMIT_DZIEN') < c.index('UrlFetchApp.fetch(HOSTY[s]') < c.index("P.setProperty('wl_stan'")


def test_wyniki_live_udostepnia_raz_na_adres():
    # 17.10.2026: skrypt na hernackijedrzej@, konektor Dysku w Claude na innym koncie — plik nie byl widoczny
    if not shutil.which('node'):
        pytest.skip('brak node')
    js = _cialo(_txt('wyniki_live.gs'), 'udostepnij_') + r'''
    var props = {UDOSTEPNIJ: ' Konto@Gmail.com, , drugie@x.pl'}, dodani = [];
    var P = {getProperty: function (k) { return props[k] || null; }, setProperty: function (k, v) { props[k] = v; }};
    var plik = {getId: function () { return 'F1'; }, addViewer: function (a) { dodani.push(a); }};
    var Logger = {log: function () {}};
    udostepnij_(P, plik); udostepnij_(P, plik);
    console.log(JSON.stringify([dodani, props.wl_udostepniono]));
    '''
    r = subprocess.run(['node', '-e', js], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [['konto@gmail.com', 'drugie@x.pl'], 'F1:konto@gmail.com,F1:drugie@x.pl']
    c = _cialo(_txt('wyniki_live.gs'), '_plik_')
    assert "'me' in owners" in c   # nie nadpisujemy cudzego pliku o tej samej nazwie


_ATRAPY_GS = r'''
var props = PROPS, pliki = {}, foldery = 0, wyw = [], log = [];
var PropertiesService = {getScriptProperties: function () { return {getProperty: function (k) { return props[k] === undefined ? null : props[k]; },
  setProperty: function (k, v) { if (String(v).length > 9000) throw new Error('za duza wlasciwosc ' + k); props[k] = v; }}; }};
function plikAtrapa(n, t) { return {n: n, t: t, getBlob: function () { var s = this; return {getDataAsString: function () { return s.t; }}; },
  setContent: function (x) { this.t = x; }, getId: function () { return 'P_' + n; }, addViewer: function () {}, getLastUpdated: function () { return new Date(0); }}; }
var folder = {getId: function () { return 'FOLD'; }, addViewer: function (a) { log.push('udost ' + a); },
  getFilesByName: function (n) { var f = pliki[n]; return {hasNext: function () { return !!f; }, next: function () { return f; }}; },
  createFile: function (n, t) { return pliki[n] = plikAtrapa(n, t); }};
var LIGI = LIGI_JSON;
var DriveApp = {searchFolders: function () { return {hasNext: function () { return foldery > 0; }, next: function () { return folder; }}; },
  createFolder: function () { foldery++; return folder; },
  searchFiles: function (q) { var f = q.indexOf('api_ligi.json') >= 0 && LIGI ? plikAtrapa('api_ligi.json', JSON.stringify(LIGI)) : null, d = false;
    return {hasNext: function () { return !!f && !d; }, next: function () { d = true; return f; }}; },
  createFile: function (n, t) { return pliki['DRIVE_' + n] = plikAtrapa(n, t); }};
var Logger = {log: function (x) { log.push(String(x)); }};
var Utilities = {formatDate: function (d, tz, f) {
  var p = {}; new Intl.DateTimeFormat('en-GB', {timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23'})
    .formatToParts(d).forEach(function (x) { p[x.type] = x.value; });
  return f === 'H' ? String(+p.hour) : p.year + '-' + p.month + '-' + p.day; }};
var fx = function (id, lid, st, h, a) { return {fixture: {id: id, timestamp: 1792252800, status: {short: st, elapsed: 90}}, league: {id: lid, season: 2026, name: 'L' + lid, country: 'X'},
  teams: {home: {id: 1, name: h}, away: {id: 2, name: a}}, goals: {home: 2, away: 1}, score: {halftime: {home: 1, away: 0}},
  statistics: [{team: {id: 1}, statistics: [{type: 'Total Shots', value: 14}, {type: 'Shots on Goal', value: 6}, {type: 'Corner Kicks', value: 7},
    {type: 'Yellow Cards', value: 2}, {type: 'Ball Possession', value: '58%'}, {type: 'expected_goals', value: '1.84'}]},
    {team: {id: 2}, statistics: [{type: 'Total Shots', value: 8}, {type: 'Corner Kicks', value: null}, {type: 'Red Cards', value: 1}]}],
  lineups: [{team: {id: 1, name: h}, formation: '4-3-3', coach: {name: 'Trener'}, startXI: [{player: {name: 'A, B'}}, {player: {name: 'C'}}], substitutes: [{player: {name: 'D'}}]}]}; };
var UrlFetchApp = {fetch: function (u) { wyw.push(u.replace(/^https:\/\/v\d\.[a-z]+\.api-sports\.io\//, ''));
  var b = {response: []};
  if (u.indexOf('fixtures?ids=') >= 0) b.response = u.split('ids=')[1].split('-').map(function (i) { return fx(+i, 39, 'FT', 'H' + i, 'A' + i); });
  else if (u.indexOf('injuries') >= 0) b.response = [{player: {name: 'Kowalski', type: 'Missing Fixture', reason: 'Knee Injury'}, team: {name: 'H1'}, fixture: {id: 1, date: '2026-10-17T15:00:00+00:00'}, league: {id: 39, name: 'L39'}}];
  else if (u.indexOf('league=') >= 0) b = u.indexOf('season=2025') >= 0 ? {errors: {plan: 'Free plans do not have access to this season'}, response: []} : {response: [fx(900, 39, 'FT', 'X', 'Y')]};
  else if (u.indexOf('football') >= 0) b.response = DZIS;
  return {getResponseCode: function () { return 200; }, getContentText: function () { return JSON.stringify(b); }, getHeaders: function () { return {}; }}; }};
'''


def _symulacja(teraz_iso, props, ligi, dzis_mecze, przebiegi=1):
    if not shutil.which('node'):
        pytest.skip('brak node')
    src = _txt('wyniki_live.gs')
    js = (_ATRAPY_GS.replace('PROPS', json.dumps(props)).replace('LIGI_JSON', json.dumps(ligi)).replace('DZIS', dzis_mecze)
          + src + r'''
    var RD = Date, T0 = RD.parse('%s'), krok = 0;
    Date = function (x) { return arguments.length ? new RD(x) : new RD(T0 + krok * 60000); };
    Date.now = function () { return T0 + krok * 60000; }; Date.UTC = RD.UTC; Date.parse = RD.parse;
    for (; krok < %d; krok++) wynikiLive();
    var feed = JSON.parse(pliki['DRIVE_wyniki_live.json'] ? pliki['DRIVE_wyniki_live.json'].t : '{}');
    var tresc = {}; Object.keys(pliki).forEach(function (k) { tresc[k] = pliki[k].t; });
    console.log(JSON.stringify({wyw: wyw, obs: feed.zrodla && feed.zrodla.obserwacja, pliki: tresc, props: props, log: log}));
    ''' % (teraz_iso, przebiegi))
    r = subprocess.run(['node', '-e', js], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


def test_wyniki_live_obserwacja_pelny_dzien():
    # 17.10.2026: obserwacja dla STS — archiwum, kontuzje, statystyki i składy (20 meczów/zapytanie), historia lig
    dzis = 'Array.apply(null, {length: 25}).map(function (_, i) { return fx(100 + i, i < 22 ? 39 : 77, i < 21 ? "FT" : "NS", "H" + i, "A" + i); })'
    w = _symulacja('2026-10-17T10:00:00Z', {'APISPORTS_KEY': 'K', 'SPORTY': 'football', 'UDOSTEPNIJ': 'jedrzej.hernacki@gmail.com'},
                   {'ligi': [{'lid': 39, 'sezon': 2026}]}, dzis, przebiegi=3)
    sciezki = [x for x in w['wyw'] if not x.startswith('http')]   # bez OpenLigaDB
    assert sciezki[0].startswith('fixtures?date=2026-10-17')          # wyniki live
    assert any(s.startswith('fixtures?date=2026-10-16') for s in sciezki)   # archiwum wczoraj
    assert any(s.startswith('injuries?date=2026-10-17') for s in sciezki)
    ids = [s for s in sciezki if s.startswith('fixtures?ids=')]
    # 21 zakończonych w lidze 39 (mecz w lidze 77 i nierozpoczęte pominięte) -> 20 + 1, każdy mecz raz
    assert [len(s.split('=')[1].split('-')) for s in ids] == [20, 1]
    assert 'fixtures?league=39&season=2026&timezone=Europe/Warsaw' in sciezki and any('season=2025' in s for s in sciezki)
    # najwyżej 4 zapytania obserwacji na minutę (limit API 10/min)
    p = w['pliki']
    stat = p['api_statystyki_2026-10.csv'].splitlines()
    assert stat[0].startswith('data,fid,lid') and len(stat) == 1 + 21 * 2
    assert stat[1].split(',')[9:12] == ['14', '6', '7'] and stat[1].endswith(',58,1.84')
    assert '"A, B;C"' in p['api_sklady_2026-10.csv']
    assert 'Kowalski,Missing Fixture,Knee Injury' in p['api_kontuzje_2026-10.csv']
    assert p['historia_39_2026.csv'].count('\n') == 2
    h = json.loads(w['props']['wl_hist'])
    assert h['39_2026'] == 'ok' and h['39_2025'].startswith('blad: plan')
    assert 'udost jedrzej.hernacki@gmail.com' in w['log']
    assert w['obs']['szczegoly_dzis'] == 21 and w['obs']['szczegoly_czeka'] == 0
    assert len(sciezki) <= 1 + 3 * 4    # 1 odczyt live (co 30 min) + najwyżej 4 zapytania obserwacji na minutę


def test_wyniki_live_obserwacja_nie_zjada_budzetu_live():
    # 66 zużytych o 10:00 UTC: rezerwa na wyniki live co 30 min do północy UTC = 28, limit obserwacji 95-28=67 — live bierze 67,
    # na obserwację nic nie zostaje
    dzis = '[fx(1, 39, "FT", "H", "A")]'
    w = _symulacja('2026-10-17T10:00:00Z', {'APISPORTS_KEY': 'K', 'SPORTY': 'football',
                                            'wl_stan': json.dumps({'data': '2026-10-17', 'sport': {'football': {'n': 66, 'ts': 0}}})},
                   {'ligi': [{'lid': 39, 'sezon': 2026}]}, dzis)
    api = [x for x in w['wyw'] if not x.startswith('http')]
    assert api == ['fixtures?date=2026-10-17&timezone=Europe/Warsaw'] and w['obs']['limit'] == 95 - 28


def test_wyniki_live_pusta_lista_lig_nie_na_6_godzin():
    # 17.10.2026: pierwsze uruchomienie (14:02) bez api_ligi.json zapamiętało pustą listę na 6 h — po 10 min ma czytać znów
    dzis = '[fx(1, 39, "FT", "H", "A")]'
    stara = json.dumps({'ts': 1792230000000, 'ligi': []})   # 09:40 UTC, 20 min przed przebiegiem
    w = _symulacja('2026-10-17T10:00:00Z', {'APISPORTS_KEY': 'K', 'SPORTY': 'football', 'wl_ligi': stara},
                   {'ligi': [{'lid': 39, 'sezon': 2026}]}, dzis)
    assert w['obs']['ligi'] == 1 and any(x.startswith('fixtures?ids=1') for x in w['wyw'])
