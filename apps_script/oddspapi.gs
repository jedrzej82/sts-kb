/**
 * KURSY SUPERBET PL + PINNACLE Z ODDSPAPI — Google Apps Script (17.10.2026), TRYB OBSERWACJI.
 * Nic w przebiegu, typowaniu ani rozliczeniach z tego nie korzysta do pomiaru i decyzji użytkownika.
 * Cel: czy kurs Superbet (gdzie użytkownik gra) bywa wyższy od kursu uczciwego (Pinnacle bez marży) — podstawa AKO.
 *
 * JAK (po próbach na prawdziwym API 17.10.2026):
 *  - PŁATNE (250/miesiąc w planie darmowym; liczy się KAŻDE wywołanie, także z błędem 4xx): tylko lista meczów
 *    piłki z kursami Superbet na 24 h — RAZ dziennie w oknie 11:xx czasu polskiego (+ raz lista bukmacherów i raz nazwy
 *    rynków) oraz najwyżej ROZL_DZIEN rozliczeń dziennie (ok. 160/miesiąc) + jednorazowo 14 list dni wstecz.
 *    odds-by-tournaments odpada: plan darmowy przyjmuje 1 bukmachera i nieopisanie mało lig („Too many tournament IDs”).
 *  - DARMOWE (historical-odds — według dokumentacji nigdy nie liczy się do limitu; odstęp 5 s): pełna historia kursów
 *    meczu u JEDNEGO bukmachera. Co godzinę: mecze zakończone (start ponad 3 h temu), po HIST_NA_PRZEBIEG meczów,
 *    Pinnacle i Superbet osobno. Zapisujemy z każdej serii: kurs otwarcia, kurs 6 h przed startem i kurs zamknięcia.
 *
 * LIMITY: płatne najwyżej MAKS_DZIEN/dobę i MAKS_MIESIAC/miesiąc; darmowe najwyżej HIST_DZIEN/dobę; 6 s przerwy między
 *  KAŻDYMI dwoma zapytaniami; jeden przebieg naraz; po 401/403/429 lub komunikacie o limicie — nic przez BLOKADA_H godzin.
 *
 * INSTALACJA (OSOBNY projekt — nie wklejaj do projektu „wyniki live”, żeby blokady i liczniki się nie mieszały):
 *  1. https://script.google.com -> „Nowy projekt” -> wklej CAŁY ten plik -> zapisz, nazwij „oddspapi”.
 *  2. Ustawienia projektu (zębatka) -> „Właściwości skryptu” -> ODDSPAPI_KEY = Twój klucz (tylko tutaj, nigdzie indziej).
 *     Opcjonalnie UDOSTEPNIJ = adres konta Google konektora Dysku w Claude (folder zostanie mu udostępniony do odczytu).
 *  3. Wybierz funkcję „ustaw” -> „Uruchom” -> zezwól. Tworzy wyzwalacz co godzinę; lista bukmacherów raz na dobę.
 *  5. (opcjonalnie) „sprawdzPlatne” -> „Uruchom”: nazwy rynków + rozliczenie 1 zakończonego meczu = <= 2 płatne, raz na dobę.
 *  4. (opcjonalnie) „sprawdzTeraz” -> „Uruchom”: od razu darmowa historia 2 najbliższych meczów z ostatniej listy
 *     (bez płatnych zapytań), raz na dobę — plik oddspapi_hist_..._TEST.json.gz.
 *
 * WYNIK (folder „oddspapi” na Dysku):
 *  oddspapi_RRRR-MM-DD_RANO.json.gz — {v, ts, okno, mecze:[{id, t, kraj, liga, lid, a, b}], bledy}
 *  oddspapi_hist_RRRR-MM-DD_GGMM.json.gz — {v, ts, mecze:[id…], serie:[[id, bukmacher, rynek, wynik, otwarcie,
 *    kurs_6h_przed, zamkniecie, liczba_zmian]], bledy}
 *  oddspapi_W_RRRR-MM-DD.json.gz — lista meczów dnia z przeszłości (przeliczenie wstecz), jak plik RANO.
 *  oddspapi_hist_..._WRRRR-MM-DD_*.json.gz — historia kursów tych meczów.
 *  oddspapi_rynki.json — nazwy rynków i wyników piłki ({id: [nazwa, handicap, okres, {wynik: nazwa}]}), RAZ (1 płatne).
 *  oddspapi_rozl_RRRR-MM-DD_GGMM.json.gz — {v, ts, wyniki:[[id, rynek, wynik, WIN|LOSE|PUSH|HALFWIN|HALFLOSS|…]], bledy}
 *    PŁATNE: najwyżej ROZL_DZIEN meczów na dobę, tylko te, w których jakaś noga Superbet była powyżej kursu uczciwego
 *    Pinnacle 6 h przed startem (najpierw największa przewaga), najwcześniej ROZL_PO_H h po starcie.
 *  oddspapi_stan.json (liczniki, blokada, ostatnie błędy), oddspapi_zrobione.json (mecze z pobraną historią:
 *    {id: [start, największa przewaga, rozliczony 0/1]}).
 */
var API = 'https://api.oddspapi.io/v4/';
var FOLDER = 'oddspapi';
var PILKA = 10;
var MAKS_DZIEN = 10;                // płatne na dobę (UTC): lista 1 + rozliczenia 4 + listy wstecz 4 + zapas
var MAKS_MIESIAC = 200;
var HIST_DZIEN = 400;
// 18.10.2026: przy 18 meczach x 2 co 6 s (ok. 10 zapytań/min) API odpowiedziało 429 RATE_LIMITED po 3 przebiegach —
// wolniej: 8 meczów x 2 co 12 s = 16 zapytań w ok. 3,2 min (5/min)
var HIST_NA_PRZEBIEG = 8;
var BLOKADA_H = 24;
var PRZERWA_MS = 12000;
var GODZ_LISTY = 11;
var ROZL_DZIEN = 4;                 // płatne rozliczenia (settlements) na dobę — tylko mecze z nogą Superbet > kursu uczciwego
var ROZL_PO_H = 4;                  // rozliczenie najwcześniej 4 h po starcie meczu
// PRZELICZENIE WSTECZ (17.10.2026, wariant „bezpieczny” wybrany przez użytkownika): historia kursów jest darmowa od stycznia
// 2026, więc werdykt nie musi czekać tygodniami. 14 dni przed pierwszym uruchomieniem, z każdego dnia WSTECZ_MECZOW meczów
// (najpierw ligi z >= 4 meczami w dniu, kolejność stała wg skrótu id). Lista dnia = 1 płatne (najwyżej WSTECZ_LIST_DZIEN na
// dobę, jedna na przebieg); historia tych meczów = darmowa, tylko w przebiegach bez bieżącej pracy, w tym samym limicie
// HIST_DZIEN (400/dobę) i tempie (6 s) co zwykle.
var WSTECZ_DNI = 14;
var WSTECZ_MECZOW = 60;
var WSTECZ_LIST_DZIEN = 4;

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
    Logger.log('Superbet: ' + (st.bukmacher || 'nie znaleziono') + ' | płatne dziś ' + st.dzien.n + ', w miesiącu ' + st.mies.n
               + (st.blad ? ' | ' + st.blad : ''));
    zapiszStan_(P, st);
    plikStanu_(P, st, 'ustaw', st.blad ? [st.blad] : []);
  } finally { lock.releaseLock(); }
}

// Ręczna próba: darmowa historia 2 najbliższych meczów z ostatniej listy (zero płatnych zapytań), raz na dobę.
function sprawdzTeraz() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    var P = PropertiesService.getScriptProperties(), st = stan_(P);
    if (st.okna.TEST3 === st.dzien.d) { Logger.log('Próba już była dziś — wynik w pliku oddspapi_stan.json'); return; }
    st.okna.TEST3 = st.dzien.d;
    zapiszStan_(P, st);
    var f = folder_(P), mecze = meczeDni_(f, new Date()).sort(function (x, y) { return x.t - y.t; });
    var n = historia_(P, st, f, mecze.slice(0, 2), 'TEST');
    zapiszStan_(P, st);
    Logger.log('Historia: ' + n + ' serii kursów; darmowe dziś ' + st.hist.n + ', płatne dziś ' + st.dzien.n + (st.blad ? ' | ' + st.blad : ''));
  } finally { lock.releaseLock(); }
}

// Ręczna próba PŁATNYCH części (17.10.2026, prośba użytkownika „testuj”): nazwy rynków (gdy brak pliku) + rozliczenie
// JEDNEGO zakończonego meczu z ostatniej listy = najwyżej 2 płatne; raz na dobę; wolno przekroczyć dzienny bezpiecznik
// o 2 (limit miesięczny bez zmian).
function sprawdzPlatne() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    var P = PropertiesService.getScriptProperties(), st = stan_(P);
    if (st.okna.TEST_PL === st.dzien.d) { Logger.log('Próba płatna już była dziś — wynik w pliku oddspapi_stan.json'); return; }
    st.okna.TEST_PL = st.dzien.d;
    zapiszStan_(P, st);
    var f = folder_(P), bledy = [];
    if (!f.getFilesByName('oddspapi_rynki.json').hasNext()) {
      var r = pytaj_(P, st, 'markets', {language: 'en'}, false, true);
      if (r.blad) bledy.push('markets: ' + r.blad); else f.createFile('oddspapi_rynki.json', JSON.stringify(rynkiPilki_(r.dane)), 'application/json');
    }
    var granica = Date.now() / 1000 - ROZL_PO_H * 3600;
    var m = meczeDni_(f, new Date()).filter(function (x) { return x.t < granica; }).sort(function (a, b) { return b.t - a.t; })[0];
    var wyniki = [];
    if (!m) bledy.push('brak zakończonego meczu na liście');
    else {
      var s = pytaj_(P, st, 'settlements', {fixtureId: m.id}, false, true);
      if (s.blad) bledy.push('settlements: ' + s.blad); else wyniki = wynikiRozl_(m.id, s.dane);
      zapiszGz_(f, 'oddspapi_rozl_' + Utilities.formatDate(new Date(), 'Europe/Warsaw', 'yyyy-MM-dd') + '_TEST.json.gz',
                {v: 2, ts: Math.round(Date.now() / 1000), wyniki: wyniki, bledy: bledy});
    }
    zapiszStan_(P, st);
    plikStanu_(P, st, 'próba płatna: ' + (m ? (m.a + ' - ' + m.b + ', ') : '') + wyniki.length + ' wyników rozliczenia', bledy);
    Logger.log('Rynki: ' + (f.getFilesByName('oddspapi_rynki.json').hasNext() ? 'są' : 'brak') + ' | rozliczenie ' + (m ? m.a + ' - ' + m.b : '-') + ': '
               + wyniki.length + ' wyników | płatne dziś ' + st.dzien.n + ', w miesiącu ' + st.mies.n + (bledy.length ? ' | ' + bledy.join('; ') : ''));
  } finally { lock.releaseLock(); }
}

function rynkiPilki_(dane) {
  var rynki = {};
  (dane || []).forEach(function (x) {
    if (x.sportId !== PILKA || x.playerProp) return;
    var w = {};
    (x.outcomes || []).forEach(function (o) { w[o.outcomeId] = o.outcomeName; });
    rynki[x.marketId] = [x.marketName, x.handicap, x.period, w];
  });
  return rynki;
}

function wynikiRozl_(id, dane) {
  var out = [], rynki = (dane && dane.markets) || {};
  Object.keys(rynki).forEach(function (rk) {
    var wyn = rynki[rk].outcomes || {};
    Object.keys(wyn).forEach(function (w) {
      var g = (wyn[w].players || {})['0'];
      if (g && g.result) out.push([id, +rk, +w, g.result]);
    });
  });
  return out;
}

function oddspapi() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try { oddspapi_(); } finally { lock.releaseLock(); }
}

function oddspapi_() {
  var P = PropertiesService.getScriptProperties(), st = stan_(P), teraz = new Date();
  var godz = +Utilities.formatDate(teraz, 'Europe/Warsaw', 'H'), dzien = st.dzien.d;
  if (godz === GODZ_LISTY && st.okna.RANO !== dzien) {
    st.okna.RANO = dzien;                            // raz na dobę, nawet gdy coś się nie uda (budżet)
    zapiszStan_(P, st);
    lista_(P, st, teraz);
  }
  var f = folder_(P), zrobione = zrobione_(f), granica = teraz.getTime() / 1000 - 3 * 3600;
  var doPobrania = meczeDni_(f, teraz).filter(function (m) { return m.t < granica && !zrobione[m.id]; })
    .sort(function (x, y) { return x.t - y.t; }).slice(0, HIST_NA_PRZEBIEG);
  if (doPobrania.length) historia_(P, st, f, doPobrania, Utilities.formatDate(teraz, 'Europe/Warsaw', 'HHmm'));
  rozliczenia_(P, st, f, teraz);
  wstecz_(P, st, f, teraz, !doPobrania.length);
  zapiszStan_(P, st);
}

function skrot_(t) {
  var h = 0;
  for (var i = 0; i < t.length; i++) h = (h * 31 + t.charCodeAt(i)) | 0;
  return h;
}

function wstecz_(P, st, f, teraz, wolneNaHistorie) {
  if (!st.bukmacher) return;
  // 18.10.2026: wersja 2 — w wersji 1 lista z filtrem statusId/hasOdds/bookmakers zwracała 404 dla dni z przeszłości,
  // a dni odrzucone przez własny dzienny limit zostawały oznaczone jako zrobione; zaczynamy od nowa z tym samym startem
  if (st.wst && !st.wst.v2) st.wst = {start: st.wst.start, v2: 1};
  var w = st.wst = st.wst || {v2: 1};
  if (!w.start) w.start = teraz.getTime() - (teraz.getTime() % 86400000);          // północ UTC dnia pierwszego uruchomienia
  w.listy = w.listy || {}; w.kursor = w.kursor || {};
  if (!w.lim || w.lim.d !== st.dzien.d) w.lim = {d: st.dzien.d, n: 0};
  var dni = [];
  for (var k = 1; k <= WSTECZ_DNI; k++) dni.push(new Date(w.start - k * 86400000).toISOString().slice(0, 10));
  // 1) jedna lista dnia na przebieg (płatna)
  var bez = dni.filter(function (d) { return !w.listy[d]; })[0];
  if (bez && w.lim.n < WSTECZ_LIST_DZIEN && st.dzien.n < MAKS_DZIEN - 1) {   // zostaw 1 płatne na rozliczenia
    w.listy[bez] = 1; w.lim.n++;
    zapiszStan_(P, st);
    var r = pytaj_(P, st, 'fixtures', {sportId: PILKA, from: bez + 'T00:00:00Z', to: bez + 'T23:59:59Z'});
    var wszystkie = (r.dane || []).map(function (x) {
      return {id: x.fixtureId, t: Math.round(Date.parse(x.startTime) / 1000), kraj: x.categoryName, liga: x.tournamentName,
              lid: x.tournamentId, a: x.participant1Name, b: x.participant2Name};
    });
    var ile = {};
    wszystkie.forEach(function (m) { ile[m.lid] = (ile[m.lid] || 0) + 1; });
    var wybrane = wszystkie.sort(function (a, b) {
      return ((ile[b.lid] >= 4) - (ile[a.lid] >= 4)) || (skrot_(a.id) - skrot_(b.id));
    }).slice(0, WSTECZ_MECZOW);
    zapiszGz_(f, 'oddspapi_W_' + bez + '.json.gz', {v: 2, ts: Math.round(Date.now() / 1000), okno: 'WSTECZ', dzien: bez,
                                                    wszystkich: wszystkie.length, mecze: wybrane, bledy: r.blad ? ['fixtures: ' + r.blad] : []});
    if (r.blad && /^limit|^blokada/.test(r.blad)) { delete w.listy[bez]; w.lim.n--; }   // nic nie wysłano — dzień później
    else if (r.blad) w.kursor[bez] = -1;             // odpowiedź API z błędem — dzień pomijamy (bez ponawiania, budżet)
  }
  // 2) darmowa historia jednej porcji meczów z najstarszej nieskończonej listy
  if (!wolneNaHistorie) return;
  for (var i = 0; i < dni.length; i++) {
    var d = dni[i];
    if (!w.listy[d] || w.kursor[d] === -1) continue;
    var it = f.getFilesByName('oddspapi_W_' + d + '.json.gz');
    if (!it.hasNext()) continue;
    var o = null;
    try { o = JSON.parse(Utilities.ungzip(it.next().getBlob()).getDataAsString('UTF-8')); } catch (e) { o = null; }
    var mecze = (o && o.mecze) || [], od = w.kursor[d] || 0;
    if (od >= mecze.length) continue;
    var porcja = mecze.slice(od, od + HIST_NA_PRZEBIEG);
    historia_(P, st, f, porcja, 'W' + d);
    w.kursor[d] = od + st.ostGotowe;
    zapiszStan_(P, st);
    return;
  }
}

function lista_(P, st, teraz) {
  var bledy = [];
  if (!st.bukmacher && !bukmacher_(P, st)) bledy.push('brak bukmachera Superbet PL');
  var mecze = [];
  if (st.bukmacher) {
    var od = teraz.toISOString().slice(0, 19) + 'Z', doo = new Date(teraz.getTime() + 24 * 3600000).toISOString().slice(0, 19) + 'Z';
    var lista = pytaj_(P, st, 'fixtures', {sportId: PILKA, from: od, to: doo, hasOdds: 'true', bookmakers: st.bukmacher});
    if (lista.blad) bledy.push('fixtures: ' + lista.blad);
    mecze = (lista.dane || []).map(function (f) {
      return {id: f.fixtureId, t: Math.round(Date.parse(f.startTime) / 1000), kraj: f.categoryName, liga: f.tournamentName,
              lid: f.tournamentId, a: f.participant1Name, b: f.participant2Name};
    });
  }
  var f = folder_(P), dzien = Utilities.formatDate(teraz, 'Europe/Warsaw', 'yyyy-MM-dd');
  if (!f.getFilesByName('oddspapi_rynki.json').hasNext() && st.okna.RYNKI !== st.dzien.d) {
    st.okna.RYNKI = st.dzien.d;                      // nazwy rynków: raz (przy braku pliku najwyżej raz na dobę)
    var r = pytaj_(P, st, 'markets', {language: 'en'});
    if (r.blad) bledy.push('markets: ' + r.blad);
    else f.createFile('oddspapi_rynki.json', JSON.stringify(rynkiPilki_(r.dane)), 'application/json');
  }
  zapiszGz_(f, 'oddspapi_' + dzien + '_RANO.json.gz', {v: 2, ts: Math.round(Date.now() / 1000), okno: 'RANO', mecze: mecze, bledy: bledy});
  st.blad = bledy.join('; ');
  plikStanu_(P, st, 'RANO ' + dzien + ': ' + mecze.length + ' meczów', bledy);
}

// mecze z list z dziś i wczoraj (czas polski): pliki RANO oraz TEST z wersji 17.10
function meczeDni_(f, teraz) {
  var out = [], byly = {};
  [0, 1].forEach(function (ileDni) {
    var d = Utilities.formatDate(new Date(teraz.getTime() - ileDni * 86400000), 'Europe/Warsaw', 'yyyy-MM-dd');
    ['RANO', 'TEST'].forEach(function (okno) {
      var it = f.getFilesByName('oddspapi_' + d + '_' + okno + '.json.gz');
      while (it.hasNext()) {
        var o = null;
        try { o = JSON.parse(Utilities.ungzip(it.next().getBlob()).getDataAsString('UTF-8')); } catch (e) { o = null; }
        ((o && o.mecze) || []).forEach(function (m) { if (!byly[m.id]) { byly[m.id] = 1; out.push(m); } });
      }
    });
  });
  return out;
}

function zrobione_(f) {
  var it = f.getFilesByName('oddspapi_zrobione.json');
  if (!it.hasNext()) return {};
  try { return JSON.parse(it.next().getBlob().getDataAsString('UTF-8')); } catch (e) { return {}; }
}

function historia_(P, st, f, mecze, etykieta) {
  var serie = [], bledy = [], zrobione = zrobione_(f), gotowe = [];
  for (var i = 0; i < mecze.length; i++) {
    var m = mecze[i], stop = false;
    [['pinnacle'], [st.bukmacher || 'superbet.pl']].forEach(function (bk) {
      if (stop) return;
      var r = pytaj_(P, st, 'historical-odds', {fixtureId: m.id, bookmakers: bk[0]}, true);
      if (r.blad) { bledy.push(m.id + ' ' + bk[0] + ': ' + r.blad); stop = /STOP|blokada|limit/.test(r.blad); return; }
      serie = serie.concat(serie_(m, r.dane));
    });
    if (stop) break;
    var sm = serie.filter(function (x) { return x[0] === m.id; });
    zrobione[m.id] = [m.t, przewaga_(sm), 0]; gotowe.push(m.id);
  }
  zapiszZrobione_(f, zrobione);
  var dzien = Utilities.formatDate(new Date(), 'Europe/Warsaw', 'yyyy-MM-dd');
  zapiszGz_(f, 'oddspapi_hist_' + dzien + '_' + etykieta + '.json.gz', {v: 2, ts: Math.round(Date.now() / 1000), mecze: gotowe, serie: serie, bledy: bledy});
  st.blad = bledy.slice(0, 5).join('; ');
  st.ostGotowe = gotowe.length;
  plikStanu_(P, st, 'historia ' + dzien + ' ' + etykieta + ': ' + gotowe.length + ' meczów, ' + serie.length + ' serii', bledy.slice(0, 20));
  return serie.length;
}

function zapiszZrobione_(f, zrobione) {
  var granica = Date.now() / 1000 - 3 * 86400;      // pamiętamy tylko ostatnie 3 dni
  Object.keys(zrobione).forEach(function (k) {
    if (typeof zrobione[k] === 'number') zrobione[k] = [zrobione[k], null, 0];   // zapis z wersji 17.10 (sam start)
    if (zrobione[k][0] < granica) delete zrobione[k];
  });
  var it = f.getFilesByName('oddspapi_zrobione.json');
  if (it.hasNext()) it.next().setContent(JSON.stringify(zrobione)); else f.createFile('oddspapi_zrobione.json', JSON.stringify(zrobione), 'application/json');
}

// Największa przewaga Superbet nad kursem uczciwym Pinnacle 6 h przed startem w jednym meczu (jak oddspapi_analiza.py:
// tylko rynki z tym samym zestawem wyników u obu, przewagi > 35% pomijane jako podejrzane); null, gdy brak porównania.
function przewaga_(sm) {
  var rynki = {};
  sm.forEach(function (x) {
    var bk = x[1] === 'pinnacle' ? 'p' : 's';
    (rynki[x[2]] = rynki[x[2]] || {p: {}, s: {}})[bk][x[3]] = x[5];
  });
  var naj = null;
  Object.keys(rynki).forEach(function (r) {
    var p = rynki[r].p, s = rynki[r].s, kp = Object.keys(p).sort().join(), ks = Object.keys(s).sort().join();
    if (kp !== ks || Object.keys(p).length < 2) return;
    var suma = 0, ok = true;
    Object.keys(p).forEach(function (w) { if (!(p[w] > 1)) ok = false; else suma += 1 / p[w]; });
    if (!ok) return;
    Object.keys(s).forEach(function (w) {
      if (!(s[w] > 1)) return;
      var e = (1 / p[w]) / suma * s[w] - 1;
      if (e <= 0.35 && (naj === null || e > naj)) naj = e;
    });
  });
  return naj === null ? null : Math.round(naj * 1000) / 1000;
}

// PŁATNE: rozliczenia meczów z nogą powyżej kursu uczciwego, najwyżej ROZL_DZIEN na dobę
function rozliczenia_(P, st, f, teraz) {
  if (!st.rozl || st.rozl.d !== st.dzien.d) st.rozl = {d: st.dzien.d, n: 0};
  if (st.rozl.n >= ROZL_DZIEN) return;
  var zrobione = zrobione_(f), granica = teraz.getTime() / 1000 - ROZL_PO_H * 3600;
  var kand = Object.keys(zrobione).filter(function (k) {
    var z = zrobione[k];
    return Array.isArray(z) && z[1] !== null && z[1] > 0 && !z[2] && z[0] < granica;
  }).sort(function (a, b) { return zrobione[b][1] - zrobione[a][1]; }).slice(0, ROZL_DZIEN - st.rozl.n);
  if (!kand.length) return;
  var wyniki = [], bledy = [];
  for (var i = 0; i < kand.length; i++) {
    st.rozl.n++;
    var r = pytaj_(P, st, 'settlements', {fixtureId: kand[i]});
    if (r.blad) { bledy.push(kand[i] + ': ' + r.blad); if (/STOP|blokada|limit/.test(r.blad)) break; zrobione[kand[i]][2] = 1; continue; }
    wyniki = wyniki.concat(wynikiRozl_(kand[i], r.dane));
    zrobione[kand[i]][2] = 1;
  }
  zapiszZrobione_(f, zrobione);
  var dzien = Utilities.formatDate(teraz, 'Europe/Warsaw', 'yyyy-MM-dd');
  zapiszGz_(f, 'oddspapi_rozl_' + dzien + '_' + Utilities.formatDate(teraz, 'Europe/Warsaw', 'HHmm') + '.json.gz',
            {v: 2, ts: Math.round(Date.now() / 1000), wyniki: wyniki, bledy: bledy});
  plikStanu_(P, st, 'rozliczenia ' + dzien + ': ' + kand.length + ' meczów, ' + wyniki.length + ' wyników', bledy);
}

// [id, bukmacher, rynek, wynik, otwarcie, kurs 6 h przed startem, zamknięcie (ostatni przed startem), liczba zapisów]
function serie_(m, d) {
  var out = [], przed6 = m.t - 6 * 3600;
  var bks = (d && d.bookmakers) || {};
  Object.keys(bks).forEach(function (bk) {
    var rynki = bks[bk].markets || {};
    Object.keys(rynki).forEach(function (r) {
      var wyn = rynki[r].outcomes || {};
      Object.keys(wyn).forEach(function (w) {
        var lista = ((wyn[w].players || {})['0'] || []).map(function (x) { return [Date.parse(x.createdAt) / 1000, x.price, x.active !== false]; })
          .filter(function (x) { return x[1] && x[0] < m.t; }).sort(function (a, b) { return a[0] - b[0]; });
        if (!lista.length) return;
        var w6 = null, zam = null;
        lista.forEach(function (x) { if (x[2]) { zam = x[1]; if (x[0] <= przed6) w6 = x[1]; } });
        out.push([m.id, bk, +r, +w, lista[0][1], w6, zam, lista.length]);
      });
    });
  });
  return out;
}

function zapiszGz_(f, nazwa, o) {
  var baza = nazwa.replace(/\.json\.gz$/, ''), nr = 1;
  while (f.getFilesByName(nazwa).hasNext()) nazwa = baza + '_' + (++nr) + '.json.gz';   // drugi przebieg w tej samej minucie
  var blob = Utilities.gzip(Utilities.newBlob(JSON.stringify(o), 'application/json', 'oddspapi.json'));
  blob.setName(nazwa);
  f.createFile(blob);
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

// JEDYNE miejsce, które wysyła zapytanie: budżet doby i miesiąca (płatne) albo doby (darmowe), blokada, przerwa 6 s
function pytaj_(P, st, endpoint, par, darmowe, ponadDzienny) {
  var klucz = P.getProperty('ODDSPAPI_KEY');
  if (!klucz) return {blad: 'brak ODDSPAPI_KEY we właściwościach skryptu'};
  if (st.blokada && Date.now() - st.blokada.ts < BLOKADA_H * 3600000) return {blad: 'blokada do ' + new Date(st.blokada.ts + BLOKADA_H * 3600000).toISOString()};
  if (darmowe && st.hist.n >= HIST_DZIEN) return {blad: 'limit dzienny darmowych ' + HIST_DZIEN};
  if (!darmowe && st.dzien.n >= MAKS_DZIEN + (ponadDzienny ? 2 : 0)) return {blad: 'limit dzienny ' + MAKS_DZIEN};
  if (!darmowe && st.mies.n >= MAKS_MIESIAC) return {blad: 'limit miesięczny ' + MAKS_MIESIAC};
  if (st.ostatnie && Date.now() - st.ostatnie < PRZERWA_MS) Utilities.sleep(PRZERWA_MS);
  if (darmowe) st.hist.n++; else { st.dzien.n++; st.mies.n++; }
  st.ostatnie = Date.now();
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
  if (!st.hist || st.hist.d !== dzien) st.hist = {d: dzien, n: 0};
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

function plikStanu_(P, st, co, bledy) {
  var f = folder_(P);
  var s = {ts: Math.round(Date.now() / 1000), bukmacher: st.bukmacher, platne: {dzis: st.dzien.n, miesiac: st.mies.n},
           darmowe_dzis: st.hist.n, limity: {dzien: MAKS_DZIEN, miesiac: MAKS_MIESIAC, darmowe_dzien: HIST_DZIEN},
           blokada: st.blokada || null, ostatnio: co, bledy: bledy};
  var it = f.getFilesByName('oddspapi_stan.json');
  if (it.hasNext()) it.next().setContent(JSON.stringify(s)); else f.createFile('oddspapi_stan.json', JSON.stringify(s), 'application/json');
}
