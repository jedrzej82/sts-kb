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
 *  4. Wybierz funkcję „ustaw” -> „Uruchom” -> zezwól (Dysk + połączenia zewnętrzne). Tworzy wyzwalacz co minutę
 *     i od razu zapisuje pierwszy plik. Błędy źródeł (np. limit planu) są w polu „zrodla” pliku wyniki_live.json.
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
  var stan = JSON.parse(P.getProperty('wl_stan') || '{}');
  if (stan.data !== dzis) stan = {data: dzis, sport: {}};
  var stary = czytajPlik_();
  var mecze = (stary && stary.data === dzis ? stary.mecze : []) || [], zrodla = (stary && stary.data === dzis ? stary.zrodla : {}) || {};

  sporty.forEach(function (s) {
    var st = stan.sport[s] || {n: 0, ts: 0};
    if (!klucz) { zrodla[s] = {blad: 'brak APISPORTS_KEY we właściwościach skryptu'}; return; }
    if (teraz.getTime() - st.ts < co * 60000 - 5000) return;            // jeszcze nie pora
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

  P.setProperty('wl_stan', JSON.stringify(stan));
  zapiszPlik_({v: 1, ts: teraz.toISOString(), data: dzis, zrodla: zrodla, mecze: mecze});
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
  var it = DriveApp.getFilesByName(PLIK);
  return it.hasNext() ? it.next() : null;
}

function czytajPlik_() {
  var f = _plik_();
  if (!f) return null;
  try { return JSON.parse(f.getBlob().getDataAsString('UTF-8')); } catch (e) { return null; }
}

function zapiszPlik_(o) {
  var f = _plik_(), txt = JSON.stringify(o);
  if (f) f.setContent(txt);
  else DriveApp.createFile(PLIK, txt, 'application/json');
}
