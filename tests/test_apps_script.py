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
