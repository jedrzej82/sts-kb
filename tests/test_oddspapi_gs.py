"""17.10.2026: apps_script/oddspapi.gs (TRYB OBSERWACJI) — limity OddsPapi: płatne 250/miesiąc, historical-odds darmowe."""
import json
import os
import shutil
import subprocess

import pytest

_GS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'apps_script', 'oddspapi.gs')

_ATRAPY = r'''
var props = PROPS, pliki = {}, wyw = [], spanie = 0, wyzw = [];
var PropertiesService = {getScriptProperties: function () { return {getProperty: function (k) { return props[k] === undefined ? null : props[k]; },
  setProperty: function (k, v) { if (String(v).length > 9000) throw new Error('za duza wlasciwosc ' + k); props[k] = String(v); }}; }};
function plik(n, t) { return {t: t, getBlob: function () { var s = this; return {dane: s.t, getDataAsString: function () { return s.t; }}; },
  setContent: function (x) { this.t = x; }}; }
var folder = {getId: function () { return 'F'; }, addViewer: function () {},
  getFilesByName: function (n) { var f = pliki[n], d = false; return {hasNext: function () { return !!f && !d; }, next: function () { d = true; return f; }}; },
  createFile: function (n, t) { if (typeof n === 'object') { pliki[n.name] = plik(n.name, n.dane); return; } pliki[n] = plik(n, t); }};
var DriveApp = {searchFolders: function () { return {hasNext: function () { return false; }}; }, createFolder: function () { return folder; }};
var ScriptApp = {getProjectTriggers: function () { return []; }, deleteTrigger: function () {},
  newTrigger: function (f) { wyzw.push(f); return {timeBased: function () { return {everyHours: function () { return {create: function () {}}; }}; }}; }};
var Logger = {log: function () {}};
var LockService = {getScriptLock: function () { return {tryLock: function () { return true; }, releaseLock: function () {}}; }};
var Utilities = {sleep: function (ms) { spanie += ms; },
  newBlob: function (t) { return {dane: t, name: '', setName: function (n) { this.name = n; }}; }, gzip: function (b) { return b; },
  ungzip: function (b) { return {getDataAsString: function () { return b.dane; }}; },
  formatDate: function (d, tz, f) { var p = {}; new Intl.DateTimeFormat('en-GB', {timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'})
    .formatToParts(d).forEach(function (x) { p[x.type] = x.value; });
    return f === 'H' ? String(+p.hour) : f === 'HHmm' ? p.hour + p.minute : p.year + '-' + p.month + '-' + p.day; }};
var KOD = KOD_HTTP, T_MECZU = function (i) { return Date.now() + (i % 2 ? 2 : 10) * 3600000; };
var UrlFetchApp = {fetch: function (u) { wyw.push(u.replace('https://api.oddspapi.io/v4/', ''));
  var b;
  if (KOD !== 200) b = {error: {code: 'REQUEST_LIMIT_EXCEEDED', message: 'Request limit exceeded'}};
  else if (u.indexOf('bookmakers?') >= 0) b = [{slug: 'pinnacle', bookmakerName: 'Pinnacle'}, {slug: 'superbet.ro', bookmakerName: 'Superbet RO'},
      {slug: 'superbet.pl', bookmakerName: 'Superbet PL'}];
  else if (u.indexOf('fixtures?') >= 0 && u.indexOf('statusId=2') >= 0) {      // lista dnia z przeszłości: 90 meczów, ligi po 1..9
    var d = u.split('from=')[1].slice(0, 10); b = [];
    for (var i = 0; i < 90; i++) b.push({fixtureId: 'w' + d + '_' + i, startTime: d + 'T15:00:00Z', tournamentId: i < 60 ? 1000 + (i % 12) : 1000 + i,
      tournamentName: 'W' + i, categoryName: 'K', participant1Name: 'C' + i, participant2Name: 'D' + i}); }
  else if (u.indexOf('fixtures?') >= 0) { b = []; for (var i = 0; i < 60; i++) b.push({fixtureId: 'id' + i, startTime: new Date(T_MECZU(i)).toISOString(),
      tournamentId: i, tournamentName: 'L' + i, categoryName: 'K', participant1Name: 'A' + i, participant2Name: 'B' + i}); }
  else if (u.indexOf('historical-odds?') >= 0) {
    var bk = u.split('bookmakers=')[1].split('&')[0], fid = u.split('fixtureId=')[1].split('&')[0], t0 = Date.now() - 30 * 3600000;
    var h = function (dt, p, a) { return {createdAt: new Date(t0 + dt * 3600000).toISOString(), price: p, active: a}; };
    var c = bk === 'pinnacle' ? 1 : (fid[0] === 'w' || +fid.slice(2) % 2 ? 0.9 : 1.1);              // Superbet: parzyste mecze powyżej uczciwego
    b = {fixtureId: fid, bookmakers: {}};
    b.bookmakers[bk] = {markets: {'101': {outcomes: {'101': {players: {'0': [h(5, 2.3 * c, true), h(0, 2.0 * c, true), h(20, 2.2 * c, true), h(40, 9.9, true)]}},
      '102': {players: {'0': [h(0, bk === 'pinnacle' ? 2.0 : 1.8, true)]}}}}}};
  }
  else if (u.indexOf('markets?') >= 0) b = [{marketId: 101, sportId: 10, marketName: 'Full Time Result', handicap: 0, period: 'fulltime', playerProp: false,
      outcomes: [{outcomeId: 101, outcomeName: '1'}, {outcomeId: 102, outcomeName: 'X'}]}, {marketId: 900, sportId: 11, outcomes: []}];
  else if (u.indexOf('settlements?') >= 0) b = {fixtureId: u.split('fixtureId=')[1].split('&')[0], markets: {'101': {outcomes: {'101': {players: {'0': {result: 'WIN'}}},
      '102': {players: {'0': {result: 'LOSE'}}}}}}};
  return {getResponseCode: function () { return KOD; }, getContentText: function () { return JSON.stringify(b); }}; }};
'''


def _symuluj(start_iso, godzin, props=None, kod=200, ustaw=False, sprawdz=False):
    if not shutil.which('node'):
        pytest.skip('brak node')
    p = {'ODDSPAPI_KEY': 'TAJNY123'}
    p.update(props or {})
    js = (_ATRAPY.replace('PROPS', json.dumps(p)).replace('KOD_HTTP', str(kod)) + open(_GS, encoding='utf-8').read() + r'''
    var RD = Date, T0 = RD.parse('%s'), krok = 0;
    Date = function (x) { return arguments.length ? new RD(x) : new RD(T0 + krok * 3600000); };
    Date.now = function () { return T0 + krok * 3600000; }; Date.UTC = RD.UTC; Date.parse = RD.parse;
    if (%s) { ustaw(); ustaw(); }
    for (; krok < %d; krok++) { oddspapi(); oddspapi(); }
    if (%s) { sprawdzTeraz(); sprawdzTeraz(); }
    var tresc = {}; Object.keys(pliki).forEach(function (k) { tresc[k] = pliki[k].t; });
    console.log(JSON.stringify({wyw: wyw, pliki: tresc, props: props, spanie: spanie, wyzw: wyzw}));
    ''' % (start_iso, 'true' if ustaw else 'false', godzin, 'true' if sprawdz else 'false'))
    r = subprocess.run(['node', '-e', js], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


def _ep(w):
    return [u.split('?')[0] for u in w['wyw']]


def test_doba_jedno_platne_lista_reszta_darmowa_historia():
    w = _symuluj('2026-10-17T22:30:00Z', 30, ustaw=True)   # 00:30 PL 18.10, 30 godzin co godzinę (po 2 wywołania)
    ep = _ep(w)
    biez = [u for u in w['wyw'] if 'statusId=2' not in u and '=w20' not in u]                 # bez przeliczenia wstecz
    assert ep.count('bookmakers') == 1 and [u.split('?')[0] for u in biez].count('fixtures') == 1 and ep.count('markets') == 1
    assert set(ep) == {'bookmakers', 'fixtures', 'markets', 'historical-odds', 'settlements'}
    assert json.loads(w['pliki']['oddspapi_rynki.json']) == {'101': ['Full Time Result', 0, 'fulltime', {'101': '1', '102': 'X'}]}
    # rozliczenia: tylko mecze z nogą Superbet powyżej uczciwego (parzyste), najwyżej 4 na dobę UTC, płatne razem <= 6/dobę
    rozl = [u.split('fixtureId=')[1].split('&')[0] for u in w['wyw'] if u.startswith('settlements')]
    assert rozl and all(int(x[2:]) % 2 == 0 for x in rozl) and len(rozl) == len(set(rozl)) <= 8
    wyn = sum((json.loads(v)['wyniki'] for k, v in w['pliki'].items() if k.startswith('oddspapi_rozl_')), [])
    assert [rozl[0], 101, 101, 'WIN'] in wyn
    zr = json.loads(w['pliki']['oddspapi_zrobione.json'])
    assert zr['id2'][1] > 0 and zr['id1'][1] < 0 and all(zr[k][2] == 1 for k in rozl)
    assert w['wyzw'] == ['oddspapi', 'oddspapi']
    rano = json.loads(w['pliki']['oddspapi_2026-10-18_RANO.json.gz'])
    assert len(rano['mecze']) == 60 and 'sportId=10' in w['wyw'][1] and 'bookmakers=superbet.pl' in w['wyw'][1]
    hist = [u for u in biez if u.startswith('historical-odds')]
    assert len(hist) == 120                                                              # 60 meczów x 2 bukmacherów
    assert all(u.split('bookmakers=')[1].split('&')[0] in ('pinnacle', 'superbet.pl') for u in hist)
    pliki_h = [k for k in w['pliki'] if k.startswith('oddspapi_hist_')]
    serie = sum((json.loads(w['pliki'][k])['serie'] for k in pliki_h), [])
    assert len({s[0] for s in serie}) == 60 and max(len(json.loads(w['pliki'][k])['mecze']) for k in pliki_h) <= 18
    stan = json.loads(w['pliki']['oddspapi_stan.json'])
    listy = [u for u in w['wyw'] if 'statusId=2' in u]
    assert stan['bukmacher'] == 'superbet.pl' and stan['platne']['miesiac'] == 3 + len(rozl) + len(listy)
    assert 'TAJNY123' not in json.dumps(w['pliki'])


def test_serie_otwarcie_6h_przed_zamkniecie():
    w = _symuluj('2026-10-17T22:30:00Z', 30)
    serie = sum((json.loads(v)['serie'] for k, v in w['pliki'].items() if k.startswith('oddspapi_hist_')), [])
    s = [x for x in serie if x[1] == 'pinnacle' and x[3] == 101 and x[0].startswith('id')][0]
    # historia (godziny od t0): 0 -> 2.0, 5 -> 2.3, 20 -> 2.2, 40 -> 9.9 (po starcie — pomijana)
    assert s[2:4] == [101, 101] and s[4] == 2.0 and s[6] == 2.2 and s[7] == 3


def test_historia_tylko_po_meczu_i_bez_powtorek():
    w = _symuluj('2026-10-17T22:30:00Z', 30)
    hist = [u.split('fixtureId=')[1].split('&')[0] for u in w['wyw'] if u.startswith('historical-odds')]
    assert len(hist) > 120                                                               # także mecze z przeliczenia wstecz
    assert len(hist) == len(set(hist)) * 2                                               # każdy mecz raz u każdego bukmachera


def test_okno_listy_po_czasie_polskim_takze_zima():
    w = _symuluj('2026-10-25T23:30:00Z', 24, props={'op_stan': json.dumps({'bukmacher': 'superbet.pl'})})
    assert 'oddspapi_2026-10-26_RANO.json.gz' in w['pliki']                               # 11:xx PL = 10:xx UTC zimą


def test_limit_miesieczny_zatrzymuje_platne():
    st = {'dzien': {'d': '2026-10-18', 'n': 0}, 'mies': {'m': '2026-10', 'n': 200}, 'okna': {}, 'bukmacher': 'superbet.pl'}
    w = _symuluj('2026-10-17T22:30:00Z', 24, props={'op_stan': json.dumps(st)})
    assert 'fixtures' not in _ep(w)
    assert json.loads(w['pliki']['oddspapi_2026-10-18_RANO.json.gz'])['bledy'] == ['fixtures: limit miesięczny 200', 'markets: limit miesięczny 200']


def test_429_stop_na_dobe():
    w = _symuluj('2026-10-17T22:30:00Z', 20, kod=429, props={'op_stan': json.dumps({'bukmacher': 'superbet.pl'})})
    assert len(w['wyw']) == 1                                                           # jedno zapytanie, potem cisza
    assert json.loads(w['props']['op_stan'])['blokada']['powod'].startswith('429')


def test_brak_klucza_zero_zapytan():
    w = _symuluj('2026-10-17T22:30:00Z', 24, props={'ODDSPAPI_KEY': ''}, ustaw=True)
    assert w['wyw'] == []


def test_sprawdz_teraz_darmowa_historia_z_listy_test():
    # lista z próby 17.10 (plik TEST), sprawdzTeraz: 2 najbliższe mecze x 2 bukmacherów, zero płatnych, raz na dobę
    mecze = [{'id': 'idA', 't': 1792280000}, {'id': 'idB', 't': 1792270000}, {'id': 'idC', 't': 1792290000}]
    w = _symuluj('2026-10-17T18:40:00Z', 0, props={'op_stan': json.dumps({'bukmacher': 'superbet.pl'})}, sprawdz=True)
    assert w['wyw'] == []                                                               # brak listy -> nic
    js_pliki = {'oddspapi_2026-10-17_TEST.json.gz': json.dumps({'mecze': mecze})}
    w = _symuluj_z_plikami('2026-10-17T18:40:00Z', js_pliki)
    assert [u.split('fixtureId=')[1].split('&')[0] for u in w['wyw']] == ['idB', 'idB', 'idA', 'idA']
    assert json.loads(w['pliki']['oddspapi_hist_2026-10-17_TEST.json.gz'])['mecze'] == ['idB', 'idA']


def _symuluj_z_plikami(start_iso, pliki):
    js = (_ATRAPY.replace('PROPS', json.dumps({'ODDSPAPI_KEY': 'K', 'op_stan': json.dumps({'bukmacher': 'superbet.pl'})})).replace('KOD_HTTP', '200')
          + open(_GS, encoding='utf-8').read() + r'''
    var RD = Date, T0 = RD.parse('%s');
    Date = function (x) { return arguments.length ? new RD(x) : new RD(T0); }; Date.now = function () { return T0; }; Date.UTC = RD.UTC; Date.parse = RD.parse;
    var start = %s; Object.keys(start).forEach(function (k) { pliki[k] = plik(k, start[k]); });
    sprawdzTeraz(); sprawdzTeraz();
    var tresc = {}; Object.keys(pliki).forEach(function (k) { tresc[k] = pliki[k].t; });
    console.log(JSON.stringify({wyw: wyw, pliki: tresc}));
    ''' % (start_iso, json.dumps(pliki)))
    r = subprocess.run(['node', '-e', js], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


def test_sprawdz_platne_dwa_zapytania_ponad_dzienny_raz():
    mecze = [{'id': 'id4', 't': 1792240000, 'a': 'A4', 'b': 'B4'}, {'id': 'id6', 't': 1792245000, 'a': 'A6', 'b': 'B6'},
             {'id': 'id8', 't': 1792300000, 'a': 'A8', 'b': 'B8'}]                           # id8 jeszcze trwa
    st = {'bukmacher': 'superbet.pl', 'dzien': {'d': '2026-10-17', 'n': 5}, 'mies': {'m': '2026-10', 'n': 5}, 'okna': {}}
    js = (_ATRAPY.replace('PROPS', json.dumps({'ODDSPAPI_KEY': 'K', 'op_stan': json.dumps(st)})).replace('KOD_HTTP', '200')
          + open(_GS, encoding='utf-8').read() + r"""
    var RD = Date, T0 = RD.parse('2026-10-17T19:10:00Z');
    Date = function (x) { return arguments.length ? new RD(x) : new RD(T0); }; Date.now = function () { return T0; }; Date.UTC = RD.UTC; Date.parse = RD.parse;
    pliki['oddspapi_2026-10-17_TEST.json.gz'] = plik('x', %s);
    sprawdzPlatne(); sprawdzPlatne();
    var tresc = {}; Object.keys(pliki).forEach(function (k) { tresc[k] = pliki[k].t; });
    console.log(JSON.stringify({wyw: wyw, pliki: tresc, props: props}));
    """ % json.dumps(json.dumps({'mecze': mecze})))
    if not shutil.which('node'):
        pytest.skip('brak node')
    r = subprocess.run(['node', '-e', js], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    w = json.loads(r.stdout)
    assert [u.split('?')[0] for u in w['wyw']] == ['markets', 'settlements'] and 'fixtureId=id6' in w['wyw'][1]
    assert json.loads(w['pliki']['oddspapi_rozl_2026-10-17_TEST.json.gz'])['wyniki'][0] == ['id6', 101, 101, 'WIN']
    assert '101' in json.loads(w['pliki']['oddspapi_rynki.json'])
    assert json.loads(w['props']['op_stan'])['dzien']['n'] == 7                         # 5 + 2, drugie wywołanie nic


def test_przeliczenie_wstecz_bezpieczne():
    w = _symuluj('2026-10-17T22:30:00Z', 72, props={'op_stan': json.dumps({'bukmacher': 'superbet.pl'})})
    listy = [u for u in w['wyw'] if 'statusId=2' in u]
    dni = [u.split('from=')[1][:10] for u in listy]
    # start 17.10 22:30 UTC: 2 przebiegi do północy UTC, potem po 4 listy na dobę -> 14 dni w 72 h, każdy dzień raz
    assert dni[:2] == ['2026-10-16', '2026-10-15'] and len(dni) == 14
    assert len(set(dni)) == len(dni) and min(dni) >= '2026-10-03'
    o = json.loads(w['pliki']['oddspapi_W_2026-10-16.json.gz'])
    assert o['wszystkich'] == 90 and len(o['mecze']) == 60
    assert all(int(m['id'].split('_')[1]) < 60 for m in o['mecze'])                      # najpierw ligi z >= 4 meczami
    wst = [u.split('fixtureId=')[1].split('&')[0] for u in w['wyw'] if u.startswith('historical-odds') and '=w' in u]
    assert wst and len(wst) == len(set(wst)) * 2                                         # każdy mecz raz u 2 bukmacherów
    st = json.loads(w['props']['op_stan'])
    assert st['wst']['kursor']['2026-10-16'] == 60 and st['wst']['lim']['n'] <= 4 and st['hist']['n'] <= 400 and st['dzien']['n'] <= 10
    assert any(k.startswith('oddspapi_hist_') and '_W2026-10-16_' in k for k in w['pliki'])
