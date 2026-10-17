"""17.10.2026: apps_script/oddspapi.gs (TRYB OBSERWACJI) — twarde limity darmowego planu OddsPapi (250/miesiąc)."""
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
var folder = {getId: function () { return 'F'; }, addViewer: function () {},
  getFilesByName: function (n) { var f = pliki[n]; return {hasNext: function () { return !!f; }, next: function () { return f; }}; },
  createFile: function (n, t) { if (typeof n === 'object') { pliki[n.name] = {t: n.dane}; return; } pliki[n] = {t: t, setContent: function (x) { this.t = x; }}; }};
var DriveApp = {searchFolders: function () { return {hasNext: function () { return false; }}; }, createFolder: function () { return folder; }};
var ScriptApp = {getProjectTriggers: function () { return []; }, deleteTrigger: function () {},
  newTrigger: function (f) { wyzw.push(f); return {timeBased: function () { return {everyHours: function () { return {create: function () {}}; }}; }}; }};
var Logger = {log: function () {}};
var LockService = {getScriptLock: function () { return {tryLock: function () { return true; }, releaseLock: function () {}}; }};
var Utilities = {sleep: function (ms) { spanie += ms; },
  newBlob: function (t) { return {dane: t, name: '', setName: function (n) { this.name = n; }}; }, gzip: function (b) { return b; },
  formatDate: function (d, tz, f) { var p = {}; new Intl.DateTimeFormat('en-GB', {timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23'})
    .formatToParts(d).forEach(function (x) { p[x.type] = x.value; }); return f === 'H' ? String(+p.hour) : p.year + '-' + p.month + '-' + p.day; }};
var KOD = KOD_HTTP;
var UrlFetchApp = {fetch: function (u) { wyw.push(u.replace('https://api.oddspapi.io/v4/', ''));
  var b;
  if (KOD !== 200) b = {error: {code: 'RATE_LIMIT', message: 'Too many requests'}};
  else if (u.indexOf('bookmakers?') >= 0) b = [{slug: 'pinnacle', bookmakerName: 'Pinnacle'}, {slug: 'superbet.ro', bookmakerName: 'Superbet RO'},
      {slug: 'superbet.pl', bookmakerName: 'Superbet PL'}];
  else if (u.indexOf('fixtures?') >= 0) { b = []; for (var i = 0; i < 60; i++) b.push({fixtureId: 'id' + i, startTime: new Date(Date.now() + (i % 2 ? 2 : 10) * 3600000).toISOString(),
      tournamentId: i, tournamentName: 'L' + i, categoryName: 'K', participant1Name: 'A' + i, participant2Name: 'B' + i}); }
  else b = [{fixtureId: 'id1', bookmakerOdds: {pinnacle: {markets: {'101': {outcomes: {'101': {players: {'0': {active: true, price: 2.1, bookmakerOutcomeId: 'home', mainLine: true}}},
      '102': {players: {'0': {active: false, price: 3.3}}}}}}}, 'superbet.pl': {markets: {'101': {outcomes: {'101': {players: {'0': {active: true, price: 2.2}}}}}}}}}];
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
    if (%s) { sprawdzTeraz(); sprawdzTeraz(); }
    for (; krok < %d; krok++) { oddspapi(); oddspapi(); }
    console.log(JSON.stringify({wyw: wyw, pliki: pliki, props: props, spanie: spanie, wyzw: wyzw}));
    ''' % (start_iso, 'true' if ustaw else 'false', 'true' if sprawdz else 'false', godzin))
    r = subprocess.run(['node', '-e', js], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


def test_doba_dwa_okna_najwyzej_szesc_zapytan():
    w = _symuluj('2026-10-17T22:30:00Z', 24, ustaw=True)   # 00:30 PL 18.10, cała doba co godzinę (po 2 wywołania)
    eps = [u.split('?')[0] for u in w['wyw']]
    assert eps == ['bookmakers', 'fixtures'] + ['odds-by-tournaments'] * 4
    assert len(w['wyw']) <= 6 and w['wyzw'] == ['oddspapi', 'oddspapi']
    assert 'bookmakers=pinnacle%2Csuperbet.pl' in w['wyw'][2] and 'sportId=10' in w['wyw'][1]
    rano = json.loads(w['pliki']['oddspapi_2026-10-18_RANO.json.gz']['t'])
    assert len(rano['mecze']) == 60 and rano['bledy'] == ['pominięte ligi (budżet): 10']
    assert ['id1', 'pinnacle', 101, 101, 2.1, 'home', 1] in rano['kursy'] and ['id1', 'superbet.pl', 101, 101, 2.2, '', 0] in rano['kursy']
    assert not any(k[1] == 'pinnacle' and k[3] == 102 for k in rano['kursy'])        # nieaktywny kurs pominięty
    # wieczorem tylko ligi z meczami po ok. 19:30 PL (30 lig parzystych) -> paczki 25 + 5
    wiecz = [u.split('tournamentIds=')[1].split('&')[0].split('%2C') for u in w['wyw'][4:]]
    assert [len(x) for x in wiecz] == [25, 5] and all(int(x) % 2 == 0 for x in sum(wiecz, []))
    assert w['spanie'] >= 6000 * 2                                                      # przerwa między zapytaniami
    stan = json.loads(w['pliki']['oddspapi_stan.json']['t'])
    assert stan['zapytania'] == {'dzis': 5, 'miesiac': 6}   # doba liczona w UTC: lista bukmacherow 17.10 22:30 UTC and stan['bukmacher'] == 'superbet.pl'
    assert 'TAJNY123' not in json.dumps(w['pliki'])                                    # klucz nigdy w plikach


def test_okna_po_czasie_polskim_takze_zima():
    w = _symuluj('2026-10-25T23:30:00Z', 24)   # po zmianie czasu: 11:xx PL = 10:xx UTC
    assert sorted(k for k in w['pliki'] if k.endswith('.gz')) == ['oddspapi_2026-10-26_RANO.json.gz', 'oddspapi_2026-10-26_WIECZOR.json.gz']


def test_limit_miesieczny_zatrzymuje():
    st = {'dzien': {'d': '2026-10-18', 'n': 0}, 'mies': {'m': '2026-10', 'n': 200}, 'okna': {}, 'bukmacher': 'superbet.pl'}
    w = _symuluj('2026-10-17T22:30:00Z', 24, props={'op_stan': json.dumps(st)})
    assert w['wyw'] == []
    assert json.loads(w['pliki']['oddspapi_2026-10-18_RANO.json.gz']['t'])['bledy'] == ['fixtures: limit miesięczny 200']


def test_429_stop_na_dobe():
    w = _symuluj('2026-10-17T22:30:00Z', 30, kod=429, props={'op_stan': json.dumps({'bukmacher': 'superbet.pl'})})
    assert len(w['wyw']) == 1                                                           # jedno zapytanie, potem cisza
    assert json.loads(w['props']['op_stan'])['blokada']['powod'].startswith('429')


def test_brak_klucza_zero_zapytan():
    w = _symuluj('2026-10-17T22:30:00Z', 24, props={'ODDSPAPI_KEY': ''}, ustaw=True)
    assert w['wyw'] == []


def test_sprawdz_teraz_dwa_zapytania_raz_na_dobe():
    w = _symuluj('2026-10-17T18:30:00Z', 0, props={'op_stan': json.dumps({'bukmacher': 'superbet.pl'})}, sprawdz=True)
    assert [u.split('?')[0] for u in w['wyw']] == ['fixtures', 'odds-by-tournaments']   # drugie wywolanie nic nie wysyla
    t = json.loads(w['pliki']['oddspapi_2026-10-17_TEST.json.gz']['t'])
    assert len(t['mecze']) == 60 and t['kursy'] and t['zapytania'] == {'dzis': 2, 'miesiac': 2}
