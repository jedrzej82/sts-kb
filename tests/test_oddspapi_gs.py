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
  else if (u.indexOf('fixtures?') >= 0) { b = []; for (var i = 0; i < 60; i++) b.push({fixtureId: 'id' + i, startTime: new Date(T_MECZU(i)).toISOString(),
      tournamentId: i, tournamentName: 'L' + i, categoryName: 'K', participant1Name: 'A' + i, participant2Name: 'B' + i}); }
  else if (u.indexOf('historical-odds?') >= 0) {
    var bk = u.split('bookmakers=')[1].split('&')[0], fid = u.split('fixtureId=')[1].split('&')[0], t0 = Date.now() - 30 * 3600000;
    var h = function (dt, p, a) { return {createdAt: new Date(t0 + dt * 3600000).toISOString(), price: p, active: a}; };
    b = {fixtureId: fid, bookmakers: {}};
    b.bookmakers[bk] = {markets: {'101': {outcomes: {'101': {players: {'0': [h(5, 2.3, true), h(0, 2.0, true), h(20, 2.2, true), h(40, 9.9, true)]}}}}}};
  }
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
    assert ep.count('bookmakers') == 1 and ep.count('fixtures') == 1 and set(ep) == {'bookmakers', 'fixtures', 'historical-odds'}
    assert w['wyzw'] == ['oddspapi', 'oddspapi']
    rano = json.loads(w['pliki']['oddspapi_2026-10-18_RANO.json.gz'])
    assert len(rano['mecze']) == 60 and 'sportId=10' in w['wyw'][1] and 'bookmakers=superbet.pl' in w['wyw'][1]
    hist = [u for u in w['wyw'] if u.startswith('historical-odds')]
    assert len(hist) == 120                                                              # 60 meczów x 2 bukmacherów
    assert all(u.split('bookmakers=')[1].split('&')[0] in ('pinnacle', 'superbet.pl') for u in hist)
    pliki_h = [k for k in w['pliki'] if k.startswith('oddspapi_hist_')]
    serie = sum((json.loads(w['pliki'][k])['serie'] for k in pliki_h), [])
    assert len({s[0] for s in serie}) == 60 and max(len(json.loads(w['pliki'][k])['mecze']) for k in pliki_h) <= 18
    stan = json.loads(w['pliki']['oddspapi_stan.json'])
    assert stan['platne']['miesiac'] == 2 and stan['bukmacher'] == 'superbet.pl'
    assert 'TAJNY123' not in json.dumps(w['pliki'])


def test_serie_otwarcie_6h_przed_zamkniecie():
    w = _symuluj('2026-10-17T22:30:00Z', 30)
    serie = sum((json.loads(v)['serie'] for k, v in w['pliki'].items() if k.startswith('oddspapi_hist_')), [])
    s = [x for x in serie if x[1] == 'pinnacle'][0]
    # historia (godziny od t0): 0 -> 2.0, 5 -> 2.3, 20 -> 2.2, 40 -> 9.9 (po starcie — pomijana)
    assert s[2:4] == [101, 101] and s[4] == 2.0 and s[6] == 2.2 and s[7] == 3


def test_historia_tylko_po_meczu_i_bez_powtorek():
    w = _symuluj('2026-10-17T22:30:00Z', 30)
    hist = [u.split('fixtureId=')[1].split('&')[0] for u in w['wyw'] if u.startswith('historical-odds')]
    assert len(hist) == len(set(hist)) * 2                                               # każdy mecz raz u każdego bukmachera


def test_okno_listy_po_czasie_polskim_takze_zima():
    w = _symuluj('2026-10-25T23:30:00Z', 24, props={'op_stan': json.dumps({'bukmacher': 'superbet.pl'})})
    assert 'oddspapi_2026-10-26_RANO.json.gz' in w['pliki']                               # 11:xx PL = 10:xx UTC zimą


def test_limit_miesieczny_zatrzymuje_platne():
    st = {'dzien': {'d': '2026-10-18', 'n': 0}, 'mies': {'m': '2026-10', 'n': 200}, 'okna': {}, 'bukmacher': 'superbet.pl'}
    w = _symuluj('2026-10-17T22:30:00Z', 24, props={'op_stan': json.dumps(st)})
    assert 'fixtures' not in _ep(w)
    assert json.loads(w['pliki']['oddspapi_2026-10-18_RANO.json.gz'])['bledy'] == ['fixtures: limit miesięczny 200']


def test_429_stop_na_dobe():
    w = _symuluj('2026-10-17T22:30:00Z', 30, kod=429, props={'op_stan': json.dumps({'bukmacher': 'superbet.pl'})})
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
