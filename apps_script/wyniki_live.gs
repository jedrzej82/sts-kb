/**
 * WYNIKI NA ŻYWO DLA APLIKACJI „Prognozy meczowe” — Google Apps Script (17.10.2026).
 * Co minutę pobiera wyniki dnia ze źródeł i zapisuje JEDEN plik „wyniki_live.json” na Twoim Dysku. Aplikacja czyta go
 * przez konektor Google Drive — klucz API zostaje tutaj (we właściwościach skryptu), nigdy w stronie.
 *
 * ŹRÓDŁA:
 *  - API-Sports (licencjonowane API): piłka, hokej, koszykówka, piłka ręczna, siatkówka (lista: SPORTY).
 *    Plan darmowy = 100 zapytań/dzień NA SPORT -> skrypt pyta o każdy sport najwyżej co ODSWIEZ_MIN minut
 *    (domyślnie 15 = 96 zapytań/dzień) i nigdy ponad LIMIT_DZIEN. Plan płatny: ustaw ODSWIEZ_MIN = 1 (na żywo co minutę).
 *  - OpenLigaDB (otwarte dane, bez klucza): 1., 2. i 3. liga niemiecka z golami (minuta, strzelec) — co minutę.
 *
 * INSTALACJA (raz, ok. 5 minut):
 *  1. Załóż darmowe konto na https://dashboard.api-football.com (API-Sports) i skopiuj klucz API („API Key”).
 *  2. https://script.google.com -> „Nowy projekt” -> wklej CAŁY ten plik -> zapisz, nazwij „wyniki live”.
 *  3. Ustawienia projektu (ikona zębatki) -> „Właściwości skryptu” -> dodaj APISPORTS_KEY = Twój klucz.
 *     Opcjonalnie: ODSWIEZ_MIN (domyślnie 15), SPORTY (np. football,hockey,basketball,handball,volleyball).
 *     ODSWIEZ_PILKA_MIN (domyślnie 30): piłka osobno, żeby w darmowym planie zostało ok. 45 zapytań na OBSERWACJĘ (niżej).
 *     Skrypt na INNYM koncie Google niż konektor Dysku w Claude: UDOSTEPNIJ = adres tamtego konta (można kilka po
 *     przecinku) — plik zostanie mu udostępniony do odczytu, a aplikacja znajdzie go wśród udostępnionych.
 *  4. Wybierz funkcję „ustaw” -> „Uruchom” -> zezwól (Dysk + połączenia zewnętrzne). Tworzy wyzwalacz co minutę
 *     i od razu zapisuje pierwszy plik. Błędy źródeł (np. limit planu) są w polu „zrodla” pliku wyniki_live.json.
 *
 * OBSERWACJA DLA SYSTEMU STS (17.10.2026; nic w przebiegu z tego nie korzysta do backtestu i decyzji użytkownika):
 *  folder „api-football” na Dysku (udostępniany kontom z UDOSTEPNIJ), pliki CSV dopisywane:
 *   api_wyniki_RRRR-MM.csv     — wszystkie mecze piłki z poprzedniego dnia (1 zapytanie/dzień, po 03:00)
 *   api_kontuzje_RRRR-MM.csv   — kontuzje i zawieszenia na dziś (1 zapytanie/dzień, po 09:00)
 *   api_statystyki_RRRR-MM.csv — strzały, celne, rożne, kartki, faule, posiadanie, xG zakończonych meczów z lig STS
 *   api_sklady_RRRR-MM.csv     — składy tych meczów (20 meczów na zapytanie)
 *   historia_LIGA_SEZON.csv    — cały sezon ligi (bieżący i poprzedni), kolejka lig z pliku api_ligi.json
 *  Ligi STS = plik api_ligi.json na Dysku (tworzy go api_football.py ligi). Budżet: najpierw wyniki live do północy
 *  UTC (reset limitu API), reszta na obserwację; najwyżej 4 dodatkowe zapytania na minutę (limit API: 10/min).
 *
 * FORMAT wyniki_live.json: {v, ts, data, zrodla:{sport:{ts, n, blad, zostalo}}, mecze:[{s, id, t, kr, lg, a, b, ga, gb,
 *   st, min, pol, gole}]} — t = start (sekundy UTC), st = kod statusu źródła (NS, 1H, HT, FT…), gole = [[min, kto, ga, gb,
 *   1|2, 'k'|'s'|'']] (tylko gdy źródło je podaje).
 */
var PLIK = 'wyniki_live.json';
var SPORTY_DOMYSLNE = 'football,hockey,basketball,handball,volleyball';
var HOSTY = {
  football: 'https://v3.football.api-sports.io/fixtures',
  hockey: 'https://v1.hockey.api-sports.io/games',
  basketball: 'https://v1.basketball.api-sports.io/games',
  handball: 'https://v1.handball.api-sports.io/games',
  volleyball: 'https://v1.volleyball.api-sports.io/games',
  baseball: 'https://v1.baseball.api-sports.io/games',
  rugby: 'https://v1.rugby.api-sports.io/games'
};
var LIMIT_DZIEN = 95;          // darmowy plan: 100/dzień na sport — zostawiamy zapas
var API_PILKA = 'https://v3.football.api-sports.io/';
var FOLDER_API = 'api-football';
var OBS_NA_MINUTE = 4;
var MAKS_LIG = 150;            // właściwość skryptu ma limit 9 KB — stan historii (2 sezony na ligę) musi się zmieścić
var OPENLIGA = ['bl1', 'bl2', 'bl3'];

function ustaw() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'wynikiLive') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('wynikiLive').timeBased().everyMinutes(1).create();
  wynikiLive();
}

function wynikiLive() {
  var P = PropertiesService.getScriptProperties();
  var klucz = P.getProperty('APISPORTS_KEY') || '';
  var co = Math.max(1, +(P.getProperty('ODSWIEZ_MIN') || 15));
  var sporty = (P.getProperty('SPORTY') || SPORTY_DOMYSLNE).split(',').map(function (s) { return s.trim(); }).filter(function (s) { return HOSTY[s]; });
  var teraz = new Date(), dzis = Utilities.formatDate(teraz, 'Europe/Warsaw', 'yyyy-MM-dd');
  var coPilka = Math.max(1, +(P.getProperty('ODSWIEZ_PILKA_MIN') || 30));
  var dzienUtc = teraz.toISOString().slice(0, 10);
  var stan = JSON.parse(P.getProperty('wl_stan') || '{}');
  if (stan.data !== dzienUtc) stan = {data: dzienUtc, sport: {}};   // limit API liczy się od 00:00 UTC
  var stary = czytajPlik_();
  var mecze = (stary && stary.data === dzis ? stary.mecze : []) || [], zrodla = (stary && stary.data === dzis ? stary.zrodla : {}) || {};

  sporty.forEach(function (s) {
    var st = stan.sport[s] || {n: 0, ts: 0};
    if (!klucz) { zrodla[s] = {blad: 'brak APISPORTS_KEY we właściwościach skryptu'}; return; }
    if (teraz.getTime() - st.ts < (s === 'football' ? coPilka : co) * 60000 - 5000) return;   // jeszcze nie pora
    if (st.n >= LIMIT_DZIEN) { zrodla[s] = zrodla[s] || {}; zrodla[s].blad = 'dzienny limit zapytań wyczerpany'; return; }
    st.n++; st.ts = teraz.getTime(); stan.sport[s] = st;
    try {
      var r = UrlFetchApp.fetch(HOSTY[s] + '?date=' + dzis + '&timezone=Europe/Warsaw',
        {headers: {'x-apisports-key': klucz}, muteHttpExceptions: true});
      var j = JSON.parse(r.getContentText() || '{}'), h = r.getHeaders();
      var bl = bladApi_(r.getResponseCode(), j);
      var zost = +(h['x-ratelimit-requests-remaining'] || h['X-RateLimit-Requests-Remaining'] || NaN);
      if (bl) { zrodla[s] = {ts: teraz.toISOString(), blad: bl, zostalo: isNaN(zost) ? null : zost}; return; }
      var nowe = (j.response || []).map(function (x) { return s === 'football' ? meczPilka(x) : meczGra(s, x); }).filter(Boolean);
      mecze = mecze.filter(function (m) { return m.s !== s; }).concat(nowe);
      zrodla[s] = {ts: teraz.toISOString(), n: nowe.length, blad: null, zostalo: isNaN(zost) ? null : zost};
    } catch (e) { zrodla[s] = {ts: teraz.toISOString(), blad: String(e).slice(0, 200)}; }
  });

  OPENLIGA.forEach(function (kod) {
    try {
      var r = UrlFetchApp.fetch('https://api.openligadb.de/getmatchdata/' + kod, {muteHttpExceptions: true});
      if (r.getResponseCode() !== 200) { zrodla['openliga_' + kod] = {ts: teraz.toISOString(), blad: 'HTTP ' + r.getResponseCode()}; return; }
      var nowe = JSON.parse(r.getContentText()).map(function (x) { return meczOpenLiga(kod, x); })
        .filter(function (m) { return m && Utilities.formatDate(new Date(m.t * 1000), 'Europe/Warsaw', 'yyyy-MM-dd') === dzis; });
      mecze = mecze.filter(function (m) { return m.s !== 'openliga_' + kod; }).concat(nowe);
      zrodla['openliga_' + kod] = {ts: teraz.toISOString(), n: nowe.length, blad: null};
    } catch (e) { zrodla['openliga_' + kod] = {ts: teraz.toISOString(), blad: String(e).slice(0, 200)}; }
  });

  if (klucz) {
    try { zrodla.obserwacja = obserwacja_(P, stan, klucz, mecze, teraz, coPilka); }
    catch (e) { zrodla.obserwacja = {blad: String(e).slice(0, 300)}; }
  }
  P.setProperty('wl_stan', JSON.stringify(stan));
  var plik = zapiszPlik_({v: 1, ts: teraz.toISOString(), data: dzis, zrodla: zrodla, mecze: mecze});
  udostepnij_(P, plik);
}

// 17.10.2026: konektor Dysku w Claude bywa na innym koncie niż skrypt — plik musi być mu udostępniony.
// Raz na adres (zapamiętane we właściwości wl_udostepniono), nie co minutę.
function udostepnij_(P, plik) {
  var chce = (P.getProperty('UDOSTEPNIJ') || '').split(',').map(function (x) { return x.trim().toLowerCase(); }).filter(Boolean);
  var juz = (P.getProperty('wl_udostepniono') || '').split(',').filter(Boolean);
  var nowe = chce.filter(function (a) { return juz.indexOf(plik.getId() + ':' + a) < 0; });
  nowe.forEach(function (a) {
    try { plik.addViewer(a); juz.push(plik.getId() + ':' + a); } catch (e) { Logger.log('udostępnienie ' + a + ': ' + e); }
  });
  if (nowe.length) P.setProperty('wl_udostepniono', juz.join(','));
}

// Odpowiedź API-Sports z błędem ma niepuste „errors” (obiekt albo tablica), np. {plan: '…'} albo {token: '…'}
function bladApi_(kod, j) {
  var e = j && j.errors;
  var tekst = Array.isArray(e) ? e.join('; ') : e && typeof e === 'object' ? Object.keys(e).map(function (k) { return k + ': ' + e[k]; }).join('; ') : '';
  if (tekst) return tekst.slice(0, 300);
  if (kod !== 200) return 'HTTP ' + kod;
  return null;
}

// liczba albo obiekt z „total” (koszykówka, baseball)
function _pkt_(v) {
  if (v === null || v === undefined) return null;
  if (typeof v === 'object') return v.total === undefined ? null : v.total;
  return v;
}

function meczPilka(x) {
  if (!x || !x.fixture || !x.teams) return null;
  var f = x.fixture, ht = x.score && x.score.halftime;
  var m = {s: 'football', id: f.id, t: f.timestamp, kr: (x.league && x.league.country) || '', lg: (x.league && x.league.name) || '',
    lid: (x.league && x.league.id) || null, sez: (x.league && x.league.season) || null,
    a: x.teams.home && x.teams.home.name, b: x.teams.away && x.teams.away.name,
    ga: x.goals ? x.goals.home : null, gb: x.goals ? x.goals.away : null,
    st: (f.status && f.status.short) || '', min: (f.status && f.status.elapsed) || null,
    pol: ht && ht.home !== null && ht.home !== undefined ? [ht.home, ht.away] : null};
  // zdarzenia (gdy źródło je podaje, np. w płatnym planie): tylko gole
  if (x.events && x.events.length) {
    var g1 = 0, g2 = 0, dom = x.teams.home && x.teams.home.id;
    m.gole = x.events.filter(function (e) { return e.type === 'Goal' && e.detail !== 'Missed Penalty'; }).map(function (e) {
      var nasz = e.team && e.team.id === dom;
      if (nasz) g1++; else g2++;
      return [e.time ? e.time.elapsed : null, (e.player && e.player.name) || '?', g1, g2, nasz ? 1 : 2,
        e.detail === 'Penalty' ? 'k' : e.detail === 'Own Goal' ? 's' : ''];
    });
  }
  return m;
}

function meczGra(s, x) {
  if (!x || !x.teams) return null;
  var sc = x.scores || {};
  return {s: s, id: x.id, t: x.timestamp, kr: (x.country && x.country.name) || '', lg: (x.league && x.league.name) || '',
    a: x.teams.home && x.teams.home.name, b: x.teams.away && x.teams.away.name,
    ga: _pkt_(sc.home), gb: _pkt_(sc.away), st: (x.status && x.status.short) || '', min: (x.status && x.status.timer) || null, pol: null};
}

function meczOpenLiga(kod, x) {
  if (!x || !x.team1 || !x.matchDateTimeUTC) return null;
  var gole = (x.goals || []).slice().sort(function (p, q) { return (p.matchMinute || 0) - (q.matchMinute || 0); });
  var kon = (x.matchResults || []).filter(function (r) { return r.resultTypeID === 2; })[0];
  var pol = (x.matchResults || []).filter(function (r) { return r.resultTypeID === 1; })[0];
  var ost = gole[gole.length - 1], t = Math.round(Date.parse(x.matchDateTimeUTC) / 1000);
  var ruszyl = Date.now() / 1000 >= t;
  return {s: 'openliga_' + kod, id: x.matchID, t: t, kr: 'Germany', lg: x.leagueName || kod,
    a: x.team1.teamName, b: x.team2.teamName,
    ga: x.matchIsFinished && kon ? kon.pointsTeam1 : ost ? ost.scoreTeam1 : ruszyl ? 0 : null,
    gb: x.matchIsFinished && kon ? kon.pointsTeam2 : ost ? ost.scoreTeam2 : ruszyl ? 0 : null,
    st: x.matchIsFinished ? 'FT' : ruszyl ? 'LIVE' : 'NS', min: null, pol: pol ? [pol.pointsTeam1, pol.pointsTeam2] : null,
    gole: gole.map(function (g) {
      return [g.matchMinute, g.goalGetterName || '?', g.scoreTeam1, g.scoreTeam2, g.scoringTeamId === x.team1.teamId ? 1 : 2,
        g.isPenalty ? 'k' : g.isOwnGoal ? 's' : ''];
    })};
}

function _plik_() {
  var it = DriveApp.searchFiles("title = '" + PLIK + "' and 'me' in owners and trashed = false");
  return it.hasNext() ? it.next() : null;
}

function czytajPlik_() {
  var f = _plik_();
  if (!f) return null;
  try { return JSON.parse(f.getBlob().getDataAsString('UTF-8')); } catch (e) { return null; }
}

function zapiszPlik_(o) {
  var f = _plik_(), txt = JSON.stringify(o);
  if (f) { f.setContent(txt); return f; }
  return DriveApp.createFile(PLIK, txt, 'application/json');
}


/* ---------- obserwacja dla systemu STS ---------- */

// ile zapytań piłki trzeba zostawić na wyniki live do północy UTC (reset limitu)
function rezerwaLive_(teraz, coPilka) {
  var doPolnocy = (Date.UTC(teraz.getUTCFullYear(), teraz.getUTCMonth(), teraz.getUTCDate() + 1) - teraz.getTime()) / 60000;
  return Math.ceil(doPolnocy / coPilka);
}

function zapytajPilka_(stan, klucz, sciezka, limitObs) {
  var st = stan.sport.football || {n: 0, ts: 0};
  if (st.n >= limitObs) return {blad: 'budżet'};
  st.n++; stan.sport.football = st; stan.obsMin = (stan.obsMin || 0) + 1;
  var r = UrlFetchApp.fetch(API_PILKA + sciezka, {headers: {'x-apisports-key': klucz}, muteHttpExceptions: true});
  var j = {};
  try { j = JSON.parse(r.getContentText() || '{}'); } catch (e) { return {blad: 'odpowiedź nie jest JSON'}; }
  var bl = bladApi_(r.getResponseCode(), j);
  return bl ? {blad: bl} : {j: j};
}

function csv_(w) {
  return w.map(function (v) {
    var t = v === null || v === undefined ? '' : String(v);
    return /[",\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t;
  }).join(',');
}

function folderApi_(P) {
  var it = DriveApp.searchFolders("title = '" + FOLDER_API + "' and 'me' in owners and trashed = false");
  var f = it.hasNext() ? it.next() : DriveApp.createFolder(FOLDER_API);
  var chce = (P.getProperty('UDOSTEPNIJ') || '').split(',').map(function (x) { return x.trim().toLowerCase(); }).filter(Boolean);
  var juz = (P.getProperty('wl_folder_udost') || '').split(',').filter(Boolean);
  chce.forEach(function (a) {
    if (juz.indexOf(f.getId() + ':' + a) >= 0) return;
    try { f.addViewer(a); juz.push(f.getId() + ':' + a); } catch (e) { Logger.log('udostępnienie folderu ' + a + ': ' + e); }
  });
  P.setProperty('wl_folder_udost', juz.join(','));
  return f;
}

function dopisz_(folder, nazwa, naglowek, wiersze) {
  if (!wiersze.length) return;
  var txt = wiersze.map(csv_).join('\n') + '\n';
  var it = folder.getFilesByName(nazwa);
  if (it.hasNext()) { var f = it.next(); f.setContent(f.getBlob().getDataAsString('UTF-8') + txt); }
  else folder.createFile(nazwa, csv_(naglowek) + '\n' + txt, 'text/csv');
}

function zapiszCsv_(folder, nazwa, naglowek, wiersze) {
  var txt = csv_(naglowek) + '\n' + wiersze.map(csv_).join('\n') + (wiersze.length ? '\n' : '');
  var it = folder.getFilesByName(nazwa);
  if (it.hasNext()) it.next().setContent(txt); else folder.createFile(nazwa, txt, 'text/csv');
}

var NAGL_WYNIKI = ['data', 'godz_utc', 'fid', 'lid', 'sezon', 'kraj', 'liga', 'gosp', 'gosc', 'gg', 'ga', 'pol_g', 'pol_a', 'status'];
function wierszWyniku(x) {
  if (!x || !x.fixture || !x.teams) return null;
  var f = x.fixture, d = new Date(f.timestamp * 1000).toISOString(), ht = (x.score && x.score.halftime) || {};
  return [Utilities.formatDate(new Date(f.timestamp * 1000), 'Europe/Warsaw', 'yyyy-MM-dd'), d.slice(11, 16), f.id,
    x.league && x.league.id, x.league && x.league.season, x.league && x.league.country, x.league && x.league.name,
    x.teams.home && x.teams.home.name, x.teams.away && x.teams.away.name, x.goals ? x.goals.home : null, x.goals ? x.goals.away : null,
    ht.home, ht.away, f.status && f.status.short];
}

var NAGL_STAT = ['data', 'fid', 'lid', 'liga', 'kraj', 'druzyna', 'strona', 'przeciwnik', 'gole', 'strzaly', 'celne', 'rozne',
  'zolte', 'czerwone', 'faule', 'spalone', 'posiadanie', 'xg'];
var TYPY_STAT = {'Total Shots': 'strzaly', 'Shots on Goal': 'celne', 'Corner Kicks': 'rozne', 'Yellow Cards': 'zolte',
  'Red Cards': 'czerwone', 'Fouls': 'faule', 'Offsides': 'spalone', 'Ball Possession': 'posiadanie', 'expected_goals': 'xg'};
var NAGL_SKLAD = ['data', 'fid', 'lid', 'druzyna', 'strona', 'formacja', 'trener', 'sklad', 'rezerwowi'];

// fixtures?ids= (do 20 meczów): statystyki drużyn i składy
function szczegolyMeczu(x) {
  if (!x || !x.fixture || !x.teams) return {stat: [], sklad: []};
  var data = Utilities.formatDate(new Date(x.fixture.timestamp * 1000), 'Europe/Warsaw', 'yyyy-MM-dd');
  var dom = x.teams.home || {}, wyj = x.teams.away || {}, lg = x.league || {};
  var strona = function (id) { return id === dom.id ? 1 : id === wyj.id ? 2 : null; };
  var stat = (x.statistics || []).map(function (t) {
    var s = strona(t.team && t.team.id), w = {};
    (t.statistics || []).forEach(function (z) { if (TYPY_STAT[z.type]) w[TYPY_STAT[z.type]] = z.value; });
    var pos = w.posiadanie === undefined || w.posiadanie === null ? null : parseFloat(String(w.posiadanie));
    return [data, x.fixture.id, lg.id, lg.name, lg.country, t.team && t.team.name, s, s === 1 ? wyj.name : dom.name,
      x.goals ? (s === 1 ? x.goals.home : x.goals.away) : null, w.strzaly, w.celne, w.rozne, w.zolte, w.czerwone, w.faule,
      w.spalone, isNaN(pos) ? null : pos, w.xg === undefined ? null : w.xg];
  });
  var nazwy = function (l) { return (l || []).map(function (p) { return p.player && p.player.name; }).filter(Boolean).join(';'); };
  var sklad = (x.lineups || []).map(function (l) {
    return [data, x.fixture.id, lg.id, l.team && l.team.name, strona(l.team && l.team.id), l.formation,
      l.coach && l.coach.name, nazwy(l.startXI), nazwy(l.substitutes)];
  });
  return {stat: stat, sklad: sklad};
}

var NAGL_KONT = ['data', 'fid', 'lid', 'liga', 'druzyna', 'zawodnik', 'typ', 'powod'];
function wierszKontuzji(x) {
  if (!x || !x.player) return null;
  return [x.fixture && x.fixture.date ? String(x.fixture.date).slice(0, 10) : '', x.fixture && x.fixture.id,
    x.league && x.league.id, x.league && x.league.name, x.team && x.team.name, x.player.name, x.player.type, x.player.reason];
}

// ligi STS: plik api_ligi.json ({ligi:[{lid, sezon}]}) — najświeższy widoczny dla skryptu; odczyt najwyżej co 6 h
function ligiSts_(P, teraz) {
  var c = JSON.parse(P.getProperty('wl_ligi') || '{}');
  if (c.ts && teraz.getTime() - c.ts < 6 * 3600000) return c.ligi || [];
  var it = DriveApp.searchFiles("title = 'api_ligi.json' and trashed = false"), best = null;
  while (it.hasNext()) { var f = it.next(); if (!best || f.getLastUpdated() > best.getLastUpdated()) best = f; }
  var ligi = [];
  if (best) { try { ligi = (JSON.parse(best.getBlob().getDataAsString('UTF-8')).ligi || []).slice(0, MAKS_LIG); } catch (e) { ligi = []; } }
  P.setProperty('wl_ligi', JSON.stringify({ts: teraz.getTime(), ligi: ligi.map(function (l) { return {lid: l.lid, sezon: l.sezon}; })}));
  return ligi;
}

function obserwacja_(P, stan, klucz, mecze, teraz, coPilka) {
  stan.obsMin = 0;
  var limit = LIMIT_DZIEN - rezerwaLive_(teraz, coPilka);      // tyle wolno wydać łącznie, zostawiając na wyniki live
  var obs = JSON.parse(P.getProperty('wl_obs') || '{}');
  var godz = +Utilities.formatDate(teraz, 'Europe/Warsaw', 'H'), dzis = Utilities.formatDate(teraz, 'Europe/Warsaw', 'yyyy-MM-dd');
  var raport = {limit: limit, uzyte: (stan.sport.football || {}).n || 0};
  var folder = null, fol = function () { return folder || (folder = folderApi_(P)); };
  var mozna = function () { return stan.obsMin < OBS_NA_MINUTE && ((stan.sport.football || {}).n || 0) < limit; };

  // 1. archiwum wczorajszych wyników (raz dziennie po 03:00)
  if (obs.arch !== dzis && godz >= 3 && mozna()) {
    var wczoraj = Utilities.formatDate(new Date(teraz.getTime() - 86400000), 'Europe/Warsaw', 'yyyy-MM-dd');
    var r = zapytajPilka_(stan, klucz, 'fixtures?date=' + wczoraj + '&timezone=Europe/Warsaw', limit);
    if (r.j) { dopisz_(fol(), 'api_wyniki_' + wczoraj.slice(0, 7) + '.csv', NAGL_WYNIKI, (r.j.response || []).map(wierszWyniku).filter(Boolean)); obs.arch = dzis; }
    raport.archiwum = r.blad || 'ok';
  }
  // 2. kontuzje na dziś (raz dziennie po 09:00)
  if (obs.kont !== dzis && godz >= 9 && mozna()) {
    var k = zapytajPilka_(stan, klucz, 'injuries?date=' + dzis, limit);
    if (k.j) { dopisz_(fol(), 'api_kontuzje_' + dzis.slice(0, 7) + '.csv', NAGL_KONT, (k.j.response || []).map(wierszKontuzji).filter(Boolean)); obs.kont = dzis; }
    raport.kontuzje = k.blad || 'ok';
  }
  var ligi = ligiSts_(P, teraz), wLigach = {};
  ligi.forEach(function (l) { wLigach[l.lid] = 1; });
  raport.ligi = ligi.length;
  // 3. statystyki i składy zakończonych meczów z lig STS (po 20 na zapytanie)
  if (obs.szDzien !== dzis) { obs.szDzien = dzis; obs.sz = []; }
  var czeka = mecze.filter(function (m) { return m.s === 'football' && wLigach[m.lid] && FIN_[m.st] && obs.sz.indexOf(m.id) < 0; })
    .map(function (m) { return m.id; });
  while (czeka.length && mozna()) {
    var paczka = czeka.splice(0, 20), q = zapytajPilka_(stan, klucz, 'fixtures?ids=' + paczka.join('-'), limit);
    if (!q.j) { raport.szczegoly = q.blad; break; }
    var st = [], sk = [];
    (q.j.response || []).forEach(function (x) { var d = szczegolyMeczu(x); st = st.concat(d.stat); sk = sk.concat(d.sklad); });
    dopisz_(fol(), 'api_statystyki_' + dzis.slice(0, 7) + '.csv', NAGL_STAT, st);
    dopisz_(fol(), 'api_sklady_' + dzis.slice(0, 7) + '.csv', NAGL_SKLAD, sk);
    obs.sz = obs.sz.concat(paczka); raport.szczegoly = 'ok';
  }
  raport.szczegoly_dzis = obs.sz.length; raport.szczegoly_czeka = czeka.length;
  // 4. historia: bieżący i poprzedni sezon każdej ligi STS (raz na ligę i sezon)
  var hist = JSON.parse(P.getProperty('wl_hist') || '{}');   // osobna właściwość (limit 9 KB na jedną)
  obs.hist = hist;
  var kolejka = [];
  ligi.forEach(function (l) { if (!l.sezon) return; [l.sezon, l.sezon - 1].forEach(function (s) { if (!obs.hist[l.lid + '_' + s]) kolejka.push([l.lid, s]); }); });
  while (kolejka.length && mozna()) {
    var ls = kolejka.shift(), h = zapytajPilka_(stan, klucz, 'fixtures?league=' + ls[0] + '&season=' + ls[1] + '&timezone=Europe/Warsaw', limit);
    if (h.blad === 'budżet') break;
    if (h.j) zapiszCsv_(fol(), 'historia_' + ls[0] + '_' + ls[1] + '.csv', NAGL_WYNIKI, (h.j.response || []).map(wierszWyniku).filter(Boolean));
    obs.hist[ls[0] + '_' + ls[1]] = h.blad ? 'blad: ' + String(h.blad).slice(0, 80) : 'ok';
  }
  var hz = Object.keys(obs.hist);
  raport.historia = {zrobione: hz.filter(function (k) { return obs.hist[k] === 'ok'; }).length, bledy: hz.filter(function (k) { return obs.hist[k] !== 'ok'; }).length, kolejka: kolejka.length,
    przyklad_bledu: hz.map(function (k) { return obs.hist[k]; }).filter(function (v) { return v !== 'ok'; })[0] || null};
  delete obs.hist;
  P.setProperty('wl_hist', JSON.stringify(hist));
  P.setProperty('wl_obs', JSON.stringify(obs));
  raport.uzyte = (stan.sport.football || {}).n || 0;
  return raport;
}
var FIN_ = {FT: 1, AET: 1, PEN: 1};
