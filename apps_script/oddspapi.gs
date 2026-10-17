/**
 * KURSY SUPERBET PL + PINNACLE Z ODDSPAPI — Google Apps Script (17.10.2026), TRYB OBSERWACJI.
 * Nic w przebiegu, typowaniu ani rozliczeniach z tego nie korzysta do pomiaru i decyzji użytkownika.
 * Cel: czy kurs Superbet (gdzie użytkownik gra) bywa wyższy od kursu uczciwego (Pinnacle bez marży) — podstawa AKO.
 *
 * LIMITY (darmowy plan OddsPapi: 250 zapytań/MIESIĄC; odstęp między zapytaniami 1–5 s zależnie od endpointu):
 *  - najwyżej MAKS_DZIEN zapytań na dobę i MAKS_MIESIAC w miesiącu (zapas do 250), liczone PRZED wysłaniem,
 *  - 6 s przerwy między zapytaniami, jeden przebieg naraz (blokada skryptu),
 *  - po 401/403/429 albo błędzie limitu — ŻADNYCH zapytań przez BLOKADA_H godzin,
 *  - dwa okna dziennie (czas polski, także po zmianie czasu): RANO (11:xx, przed przebiegiem 12:00) = lista meczów
 *    na 24 h + kursy, WIECZOR (20:xx, przed przebiegiem 21:00) = kursy tylko lig z meczami po 20:00 (prawie zamknięcie).
 *  Razem najwyżej 6 zapytań/dobę (lista bukmacherów tylko raz) = najwyżej ok. 186/miesiąc.
 *
 * INSTALACJA (OSOBNY projekt — nie wklejaj do projektu „wyniki live”, żeby blokady i liczniki się nie mieszały):
 *  1. https://script.google.com -> „Nowy projekt” -> wklej CAŁY ten plik -> zapisz, nazwij „oddspapi”.
 *  2. Ustawienia projektu (zębatka) -> „Właściwości skryptu” -> ODDSPAPI_KEY = Twój klucz (tylko tutaj, nigdzie indziej).
 *     Opcjonalnie UDOSTEPNIJ = adres konta Google konektora Dysku w Claude (folder zostanie mu udostępniony do odczytu).
 *  3. Wybierz funkcję „ustaw” -> „Uruchom” -> zezwól. Tworzy wyzwalacz co godzinę i wysyła JEDNO zapytanie
 *     (lista bukmacherów: znajduje nazwę Superbet PL). Wynik w „Dzienniku wykonania” i w pliku oddspapi_stan.json.
 *     Ponowne „ustaw” tego samego dnia nie wysyła już nic.
 *  4. (opcjonalnie) „sprawdzTeraz” -> „Uruchom”: próba od razu, 2 zapytania, najwyżej raz na dobę (plik ..._TEST.json.gz).
 *
 * WYNIK: folder „oddspapi” na Dysku, plik oddspapi_RRRR-MM-DD_OKNO.json.gz na okno:
 *  {v, ts, okno, bukmacherzy:[pinnacle, superbet], mecze:[{id, t, kraj, liga, lid, a, b}],
 *   kursy:[[id, bukmacher, rynek, wynik, kurs, opis, glowna]], zapytania:{dzis, miesiac}, bledy:[]}
 *  oraz oddspapi_stan.json (liczniki, blokada, ostatni błąd) — do kontroli bez otwierania skryptu.
 */
var API = 'https://api.oddspapi.io/v4/';
var FOLDER = 'oddspapi';
var PILKA = 10;
var MAKS_DZIEN = 6;
var MAKS_MIESIAC = 200;
var BLOKADA_H = 24;
var PRZERWA_MS = 6000;
var LIG_NA_ZAPYTANIE = 25;
var OKNA = {RANO: {godz: 11, kursy: 2, lista: true}, WIECZOR: {godz: 20, kursy: 2, lista: false}};

function ustaw() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'oddspapi') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('oddspapi').timeBased().everyHours(1).create();
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    var P = PropertiesService.getScriptProperties(), st = stan_(P);
    if (!st.bukmacher) bukmacher_(P, st);
    Logger.log('Superbet: ' + (st.bukmacher || 'nie znaleziono') + ' | zapytania dziś ' + st.dzien.n + ', w miesiącu ' + st.mies.n
               + (st.blad ? ' | ' + st.blad : ''));
    zapiszStan_(P, st);
    plikStanu_(P, st, 'ustaw', 0, 0, st.blad ? [st.blad] : []);
  } finally { lock.releaseLock(); }
}

// Ręczna próba poza oknami (np. zaraz po instalacji): lista meczów + jedna paczka kursów = 2 zapytania, raz na dobę.
function sprawdzTeraz() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    var P = PropertiesService.getScriptProperties(), st = stan_(P);
    if (st.okna.TEST === st.dzien.d) { Logger.log('Próba już była dziś — wynik w pliku oddspapi_stan.json'); return; }
    st.okna.TEST = st.dzien.d;
    zapiszStan_(P, st);
    okno_(P, st, 'TEST', {kursy: 1, lista: true}, new Date());
    zapiszStan_(P, st);
    Logger.log('Mecze/kursy zapisane; zapytania dziś ' + st.dzien.n + ', w miesiącu ' + st.mies.n + (st.blad ? ' | ' + st.blad : ''));
  } finally { lock.releaseLock(); }
}

function oddspapi() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try { oddspapi_(); } finally { lock.releaseLock(); }
}

function oddspapi_() {
  var P = PropertiesService.getScriptProperties(), st = stan_(P), teraz = new Date();
  var godz = +Utilities.formatDate(teraz, 'Europe/Warsaw', 'H'), dzien = st.dzien.d;
  Object.keys(OKNA).forEach(function (nazwa) {
    var o = OKNA[nazwa];
    if (godz !== o.godz || st.okna[nazwa] === dzien) return;
    st.okna[nazwa] = dzien;                          // okno raz na dobę, nawet gdy coś się nie uda (budżet)
    zapiszStan_(P, st);
    okno_(P, st, nazwa, o, teraz);
  });
  zapiszStan_(P, st);
}

function okno_(P, st, nazwa, o, teraz) {
  var bledy = [];
  if (!st.bukmacher && !bukmacher_(P, st)) { bledy.push('brak bukmachera Superbet PL'); return zapiszOkno_(P, st, nazwa, [], [], bledy); }
  var mecze;
  if (o.lista) {
    var od = teraz.toISOString().slice(0, 19) + 'Z', doo = new Date(teraz.getTime() + 24 * 3600000).toISOString().slice(0, 19) + 'Z';
    var lista = pytaj_(P, st, 'fixtures', {sportId: PILKA, from: od, to: doo, hasOdds: 'true', bookmakers: st.bukmacher});
    if (lista.blad) bledy.push('fixtures: ' + lista.blad);
    mecze = (lista.dane || []).map(function (f) {
      return {id: f.fixtureId, t: Math.round(Date.parse(f.startTime) / 1000), kraj: f.categoryName, liga: f.tournamentName,
              lid: f.tournamentId, a: f.participant1Name, b: f.participant2Name};
    });
  }
  var ile = {};
  if (o.lista) {
    var odTeraz = teraz.getTime() / 1000, wieczor = {}, poWieczorze = odTeraz + 8.5 * 3600;   // mecze po ok. 19:30 PL
    mecze.forEach(function (m) {
      if (m.t > odTeraz) ile[m.lid] = (ile[m.lid] || 0) + 1;
      if (m.t > poWieczorze) wieczor[m.lid] = (wieczor[m.lid] || 0) + 1;
    });
    P.setProperty('op_wieczor', JSON.stringify(wieczor));   // tylko id lig i liczby — mieści się w limicie 9 KB
  } else {
    mecze = [];
    try { ile = JSON.parse(P.getProperty('op_wieczor') || '{}'); } catch (e) { ile = {}; }
  }
  var ligi = Object.keys(ile).sort(function (x, y) { return ile[y] - ile[x] || x - y; });
  var kursy = [];
  for (var i = 0; i < o.kursy && i * LIG_NA_ZAPYTANIE < ligi.length; i++) {
    var paczka = ligi.slice(i * LIG_NA_ZAPYTANIE, (i + 1) * LIG_NA_ZAPYTANIE);
    var r = pytaj_(P, st, 'odds-by-tournaments', {tournamentIds: paczka.join(','), bookmakers: 'pinnacle,' + st.bukmacher});
    if (r.blad) { bledy.push('odds: ' + r.blad); break; }
    (r.dane || []).forEach(function (f) { kursy = kursy.concat(wiersze_(f)); });
  }
  if (ligi.length > o.kursy * LIG_NA_ZAPYTANIE) bledy.push('pominięte ligi (budżet): ' + (ligi.length - o.kursy * LIG_NA_ZAPYTANIE));
  zapiszOkno_(P, st, nazwa, mecze, kursy, bledy);
}

// [id meczu, bukmacher, rynek, wynik, kurs, opis bukmachera (np. 2.5/over), linia główna]
function wiersze_(f) {
  var out = [];
  Object.keys(f.bookmakerOdds || {}).forEach(function (bk) {
    var rynki = f.bookmakerOdds[bk].markets || {};
    Object.keys(rynki).forEach(function (r) {
      var wyn = rynki[r].outcomes || {};
      Object.keys(wyn).forEach(function (w) {
        var p = (wyn[w].players || {})['0'];
        if (p && p.active !== false && p.price) out.push([f.fixtureId, bk, +r, +w, p.price, p.bookmakerOutcomeId || '', p.mainLine ? 1 : 0]);
      });
    });
  });
  return out;
}

function bukmacher_(P, st) {
  if (st.szukano === st.dzien.d) return false;      // lista bukmacherów najwyżej raz na dobę (też przy wielu „ustaw”)
  st.szukano = st.dzien.d;
  var r = pytaj_(P, st, 'bookmakers', {});
  var lista = r.dane || [];
  var sb = lista.filter(function (b) { return /superbet/i.test(b.slug + ' ' + b.bookmakerName) && /(^|[^a-z])pl([^a-z]|$)|poland|polska/i.test(b.slug + ' ' + b.bookmakerName); });
  st.bukmacher = sb.length === 1 ? sb[0].slug : '';
  st.bukmacherzyPinnacle = lista.some(function (b) { return b.slug === 'pinnacle'; });
  if (!st.bukmacher) st.blad = 'Superbet PL: ' + (sb.length ? 'kilka kandydatów ' + sb.map(function (b) { return b.slug; }).join(',') : 'brak na liście') + (r.blad ? ' / ' + r.blad : '');
  return !!st.bukmacher;
}

// JEDYNE miejsce, które wysyła zapytanie: budżet doby i miesiąca, blokada, przerwa 6 s
function pytaj_(P, st, endpoint, par) {
  var klucz = P.getProperty('ODDSPAPI_KEY');
  if (!klucz) return {blad: 'brak ODDSPAPI_KEY we właściwościach skryptu'};
  if (st.blokada && Date.now() - st.blokada.ts < BLOKADA_H * 3600000) return {blad: 'blokada do ' + new Date(st.blokada.ts + BLOKADA_H * 3600000).toISOString()};
  if (st.dzien.n >= MAKS_DZIEN) return {blad: 'limit dzienny ' + MAKS_DZIEN};
  if (st.mies.n >= MAKS_MIESIAC) return {blad: 'limit miesięczny ' + MAKS_MIESIAC};
  if (st.ostatnie && Date.now() - st.ostatnie < PRZERWA_MS) Utilities.sleep(PRZERWA_MS);
  st.dzien.n++; st.mies.n++; st.ostatnie = Date.now();
  zapiszStan_(P, st);                                // licznik zapisany, zanim zapytanie wyjdzie
  var q = Object.keys(par).map(function (k) { return k + '=' + encodeURIComponent(par[k]); });
  q.push('apiKey=' + encodeURIComponent(klucz));
  var odp;
  try { odp = UrlFetchApp.fetch(API + endpoint + '?' + q.join('&'), {muteHttpExceptions: true}); }
  catch (e) { return {blad: String(e).slice(0, 200)}; }
  var kod = odp.getResponseCode(), tekst = odp.getContentText(), j = null;
  try { j = JSON.parse(tekst); } catch (e) { /* niżej */ }
  var komunikat = j && j.error ? (j.error.code || '') + ' ' + (j.error.message || '') : '';
  if (kod === 401 || kod === 403 || kod === 429 || /limit|quota|suspend|banned|blocked/i.test(komunikat)) {
    st.blokada = {ts: Date.now(), powod: kod + ' ' + komunikat};
    zapiszStan_(P, st);
    return {blad: 'STOP ' + BLOKADA_H + ' h: ' + kod + ' ' + komunikat};
  }
  if (kod !== 200 || !j || komunikat) return {blad: (kod + ' ' + (komunikat || tekst.slice(0, 200))).trim()};
  return {dane: j};
}

function stan_(P) {
  var st = {};
  try { st = JSON.parse(P.getProperty('op_stan') || '{}'); } catch (e) { st = {}; }
  var dzien = Utilities.formatDate(new Date(), 'UTC', 'yyyy-MM-dd'), mies = dzien.slice(0, 7);
  if (!st.dzien || st.dzien.d !== dzien) st.dzien = {d: dzien, n: 0};
  if (!st.mies || st.mies.m !== mies) st.mies = {m: mies, n: 0};
  st.okna = st.okna || {};
  return st;
}

function zapiszStan_(P, st) {
  P.setProperty('op_stan', JSON.stringify(st));
}

function folder_(P) {
  var it = DriveApp.searchFolders("title = '" + FOLDER + "' and 'me' in owners and trashed = false");
  var f = it.hasNext() ? it.next() : DriveApp.createFolder(FOLDER);
  var chce = (P.getProperty('UDOSTEPNIJ') || '').split(',').map(function (x) { return x.trim().toLowerCase(); }).filter(Boolean);
  var juz = (P.getProperty('op_udost') || '').split(',').filter(Boolean);
  chce.forEach(function (a) {
    if (juz.indexOf(f.getId() + ':' + a) >= 0) return;
    try { f.addViewer(a); juz.push(f.getId() + ':' + a); } catch (e) { Logger.log('udostępnienie ' + a + ': ' + e); }
  });
  P.setProperty('op_udost', juz.join(','));
  return f;
}

function zapiszOkno_(P, st, nazwa, mecze, kursy, bledy) {
  var f = folder_(P), dzien = Utilities.formatDate(new Date(), 'Europe/Warsaw', 'yyyy-MM-dd');
  var o = {v: 1, ts: Math.round(Date.now() / 1000), okno: nazwa, bukmacherzy: ['pinnacle', st.bukmacher], mecze: mecze,
           kursy: kursy, zapytania: {dzis: st.dzien.n, miesiac: st.mies.n}, bledy: bledy};
  var blob = Utilities.gzip(Utilities.newBlob(JSON.stringify(o), 'application/json', 'oddspapi.json'));
  blob.setName('oddspapi_' + dzien + '_' + nazwa + '.json.gz');
  f.createFile(blob);
  st.blad = bledy.join('; ');
  plikStanu_(P, st, nazwa + ' ' + dzien, mecze.length, kursy.length, bledy);
}

function plikStanu_(P, st, okno, meczow, kursow, bledy) {
  var f = folder_(P);
  var s = {ts: Math.round(Date.now() / 1000), bukmacher: st.bukmacher, zapytania: {dzis: st.dzien.n, miesiac: st.mies.n}, limity: {dzien: MAKS_DZIEN, miesiac: MAKS_MIESIAC},
           blokada: st.blokada || null, ostatnie_okno: okno, meczow: meczow, kursow: kursow, bledy: bledy};
  var it = f.getFilesByName('oddspapi_stan.json');
  if (it.hasNext()) it.next().setContent(JSON.stringify(s)); else f.createFile('oddspapi_stan.json', JSON.stringify(s), 'application/json');
}
