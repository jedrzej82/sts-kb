/**
 * LIGA PRO (tenis stołowy) — wyniki ze scores24 (29.09.2026). Samodzielny plik w projekcie „wyniki STS”;
 * korzysta z TERMINARZ_FOLDER_ID i TERMINARZ_UA z pliku „terminarz”.
 * Flashscore podaje Ligę Pro tylko do 06.2024, Sofascore/Tipsport/BetsAPI blokują Google (diagnozy 1–5 niżej).
 * Źródło: https://scores24.live/rapi/leagues/table-tennis/{liga}/matches (bez klucza; wymagane date_between).
 *
 * INSTALACJA: plik „ligapro” w projekcie → wklej CAŁY ten plik → Ctrl+S → uruchom „ligaproUstaw” (wyzwalacz co godzinę
 * + pierwsze pobranie). Wyłączenie: „ligaproUsun”.
 * PLIKI (folder baza-wiedzy): wyniki_lp_inne_RRRR-MM.csv.gz — format jak wyniki_fs_inne (zewn.inne() czyta je sam),
 *   runda = id meczu scores24 (klucz bez duplikatów); ligapro_log.txt — ile meczów na ligę i okno, stan historii.
 * HISTORIA: każde uruchomienie dociąga też wstecz kolejne dni (do LIGAPRO_DNI_WSTECZ), aż do limitu czasu.
 */
var LIGAPRO_LIGI = {'czech-liga-pro-1': ['CZECH REPUBLIC', 'Liga Pro'], 'tt-cup': ['CZECH REPUBLIC', 'TT Cup'],
  'setka-cup': ['UKRAINE', 'Setka Cup']};   // slug scores24 -> [kraj, turniej]; nieistniejący slug = 0 meczów w logu
var LIGAPRO_DNI_WSTECZ = 60;
var LIGAPRO_OKNO_H = 2;          // okno zapytania w godzinach (limit 100 meczów na odpowiedź)
var LIGAPRO_LIMIT_MS = 4.5 * 60 * 1000;

function ligaproUstaw() {
  ligaproUsun();
  ScriptApp.newTrigger('ligaproPracuj').timeBased().everyHours(1).create();
  ligaproPracuj();
}

function ligaproUsun() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'ligaproPracuj') ScriptApp.deleteTrigger(t);
  });
}

function ligaproPracuj() {
  var start = Date.now(), log = ['ligaproPracuj ' + new Date().toISOString()], nowe = {};
  var teraz = Math.floor(Date.now() / 3600000) * 3600000;
  ligaproOkres(teraz - 30 * 3600000, teraz + 3600000, nowe, log);          // ostatnie 30 h
  var P = PropertiesService.getScriptProperties(), dol = Number(P.getProperty('ligapro_hist') || (teraz - 30 * 3600000));
  var granica = teraz - LIGAPRO_DNI_WSTECZ * 86400000;
  while (dol > granica && Date.now() - start < LIGAPRO_LIMIT_MS * 0.6) {   // historia: dzień po dniu wstecz
    ligaproOkres(dol - 86400000, dol, nowe, log);
    dol -= 86400000;
    P.setProperty('ligapro_hist', String(dol));
  }
  log.push('historia do ' + new Date(dol).toISOString().substr(0, 10) + (dol <= granica ? ' (komplet)' : ' (ciąg dalszy w następnym uruchomieniu)'));
  var zapisane = ligaproZapisz(nowe);
  log.push('zapisano: ' + JSON.stringify(zapisane));
  var folder = DriveApp.getFolderById(TERMINARZ_FOLDER_ID), sl = folder.getFilesByName('ligapro_log.txt');
  while (sl.hasNext()) sl.next().setTrashed(true);
  folder.createFile('ligapro_log.txt', log.join('\n'), 'text/plain');
}

function ligaproCzas(ms) { return Utilities.formatDate(new Date(ms), 'UTC', 'yyyy-MM-dd HH:mm:ss'); }

/** Zakończone mecze wszystkich lig z [od, do) w oknach LIGAPRO_OKNO_H -> nowe[miesiac][id] = wiersz CSV. */
function ligaproOkres(od, doo, nowe, log) {
  var zad = [], opis = [];
  Object.keys(LIGAPRO_LIGI).forEach(function (slug) {
    for (var a = od; a < doo; a += LIGAPRO_OKNO_H * 3600000) {
      var b = Math.min(a + LIGAPRO_OKNO_H * 3600000, doo);
      zad.push({url: 'https://scores24.live/rapi/leagues/table-tennis/' + slug + '/matches?lang=en&audience=en&first=100' +
        '&status=ended&with_statistics=false&date_between[]=' + encodeURIComponent(ligaproCzas(a)) +
        '&date_between[]=' + encodeURIComponent(ligaproCzas(b)), muteHttpExceptions: true,
        headers: {'User-Agent': TERMINARZ_UA['User-Agent'], 'Accept': 'application/json'}});
      opis.push(slug);
    }
  });
  var ile = {}, bledy = {}, pelne = 0;
  for (var i = 0; i < zad.length; i += 20) {
    UrlFetchApp.fetchAll(zad.slice(i, i + 20)).forEach(function (r, k) {
      var slug = opis[i + k];
      ile[slug] = ile[slug] || 0;
      if (r.getResponseCode() !== 200) { bledy[slug] = r.getResponseCode(); return; }
      var j; try { j = JSON.parse(r.getContentText()); } catch (e) { bledy[slug] = 'json'; return; }
      var e = ((j.data && j.data.edges) || j.edges || []);
      if (e.length >= 100) pelne++;
      e.forEach(function (x) {
        var w = ligaproWiersz(x.node || x, LIGAPRO_LIGI[slug]);
        if (!w) return;
        (nowe[w.mies] = nowe[w.mies] || {})[w.id] = w.csv;
        ile[slug]++;
      });
    });
  }
  log.push(ligaproCzas(od).substr(0, 13) + ' – ' + ligaproCzas(doo).substr(0, 13) + ': ' + JSON.stringify(ile) +
    (Object.keys(bledy).length ? ' | HTTP ' + JSON.stringify(bledy) : '') + (pelne ? ' | UWAGA: ' + pelne + ' okien z limitem 100' : ''));
}

/** Węzeł scores24 -> {id, mies, csv} w kolumnach wyniki_fs_inne albo null (mecz bez wyniku). */
function ligaproWiersz(n, liga) {
  var t = n.teams || [], wynik = String(n.resultScore || '').split(':');
  if (t.length !== 2 || wynik.length !== 2 || !n.matchDate) return null;
  var wg = Number(wynik[0]), wa = Number(wynik[1]);
  if (isNaN(wg) || isNaN(wa) || wg === wa) return null;
  var sety = (n.resultScores || []).filter(function (s) { return /^\d+$/.test(String(s.type)); })
    .sort(function (x, y) { return Number(x.type) - Number(y.type); }).map(function (s) { return String(s.value).split(':'); });
  var d = String(n.matchDate).substr(0, 10);
  return {id: String(n.id), mies: d.substr(0, 7), csv: terminarzCsv([d, 'table-tennis', liga[0], liga[1], 'sc24:' + n.id,
    t[0].name, t[1].name, wg, wa, sety.map(function (s) { return s[0]; }).join(';'), sety.map(function (s) { return s[1]; }).join(';'),
    wg > wa ? 1 : 2, ''])};
}

/** Dopisuje nowe wiersze do wyniki_lp_inne_RRRR-MM.csv.gz (bez duplikatów po id w kolumnie runda). */
function ligaproZapisz(nowe) {
  var folder = DriveApp.getFolderById(TERMINARZ_FOLDER_ID), wynik = {};
  var NAGL = 'data,sport,kraj,turniej,runda,gosp,gosc,wg,wa,okresy_g,okresy_a,zwyciezca,nawierzchnia';
  Object.keys(nowe).forEach(function (mies) {
    var nazwa = 'wyniki_lp_inne_' + mies + '.csv.gz', stare = folder.getFilesByName(nazwa), doKosza = [], wiersze = {};
    while (stare.hasNext()) {
      var f = stare.next(); doKosza.push(f);
      Utilities.ungzip(f.getBlob().setContentType('application/x-gzip')).getDataAsString().split('\n').slice(1).forEach(function (l) {
        var m = l.match(/,sc24:([^,]+),/); if (m) wiersze[m[1]] = l;
      });
    }
    var przed = Object.keys(wiersze).length;
    Object.keys(nowe[mies]).forEach(function (id) { wiersze[id] = nowe[mies][id]; });
    var ids = Object.keys(wiersze);
    if (ids.length === przed && doKosza.length) { wynik[mies] = '0 nowych'; return; }
    var tresc = NAGL + '\n' + ids.map(function (id) { return wiersze[id]; }).sort().join('\n');
    folder.createFile(Utilities.gzip(Utilities.newBlob(tresc, 'text/csv', 'wyniki_lp_inne_' + mies + '.csv')).setName(nazwa));
    doKosza.forEach(function (f) { f.setTrashed(true); });   // stary plik dopiero PO zapisie nowego
    wynik[mies] = (ids.length - przed) + ' nowych, razem ' + ids.length;
  });
  return wynik;
}

// ---------------- diagnozy (29.09.2026) — zostają dla przyszłych zmian źródła ----------------
function ligaproDiagnoza() {
  var d = Utilities.formatDate(new Date(), 'UTC', 'yyyy-MM-dd');
  var zrodla = {
    'sofa_api': 'https://api.sofascore.com/api/v1/sport/table-tennis/scheduled-events/' + d,
    'sofa_www': 'https://www.sofascore.com/api/v1/sport/table-tennis/scheduled-events/' + d,
    'flashscore_strona': 'https://www.flashscore.com/table-tennis/others-men/liga-pro-cz/',
    'tipsport_wyniki': 'https://www.tipsport.cz/vysledky/stolni-tenis/stolni-tenis-muzi-dvouhra/liga-pro-84987',
    'betsapi': 'https://betsapi.com/le/22742/Czech-Liga-Pro',
    'scores24': 'https://scores24.live/en/table-tennis/l-czech-liga-pro',
    '24live': 'https://24live.com/page/sport/event/table-tennis-22/22338?lang=en'
  };
  var nazwy = Object.keys(zrodla), out = ['ligaproDiagnoza ' + new Date().toISOString()];
  var odp = UrlFetchApp.fetchAll(nazwy.map(function (n) {
    return {url: zrodla[n], muteHttpExceptions: true, followRedirects: true,
      headers: {'User-Agent': TERMINARZ_UA['User-Agent'], 'Accept': 'text/html,application/json;q=0.9,*/*;q=0.8',
        'Accept-Language': 'cs-CZ,cs;q=0.9,en;q=0.8'}};
  }));
  odp.forEach(function (r, i) {
    var t = r.getContentText() || '', ile = (t.match(/liga pro/gi) || []).length;
    var linia = nazwy[i] + ' | HTTP ' + r.getResponseCode() + ' | ' + t.length + ' znakow | "Liga Pro" x' + ile +
      ' | rok 2026 x' + (t.match(/2026/g) || []).length;
    if (nazwy[i].indexOf('sofa') === 0 && r.getResponseCode() === 200) {
      try {
        var ev = JSON.parse(t).events || [], lp = ev.filter(function (e) { return /liga pro/i.test((e.tournament || {}).name || ''); });
        linia += ' | mecze ' + ev.length + ', Liga Pro ' + lp.length +
          (lp[0] ? ' | np. ' + lp[0].homeTeam.name + ' - ' + lp[0].awayTeam.name : '');
      } catch (e) { linia += ' | JSON blad ' + e; }
    }
    var k = t.search(/liga pro/i);
    linia += '\n    ' + (k >= 0 ? t.substr(Math.max(0, k - 150), 400) : t.substr(0, 300)).replace(/\s+/g, ' ');
    out.push(linia);
  });
  var folder = DriveApp.getFolderById(TERMINARZ_FOLDER_ID), stare = folder.getFilesByName('ligapro_diagnoza.txt');
  while (stare.hasNext()) stare.next().setTrashed(true);
  folder.createFile('ligapro_diagnoza.txt', out.join('\n'), 'text/plain');
}

/** Diagnoza 2: jak wyglądają dane na stronach, które odpowiadają z Google (Flashscore, scores24). */
function ligaproDiagnoza2() {
  var zrodla = {
    'fs_wyniki': 'https://www.flashscore.com/table-tennis/others-men/liga-pro-cz/results/',
    'fs_terminarz': 'https://www.flashscore.com/table-tennis/others-men/liga-pro-cz/fixtures/',
    'scores24': 'https://scores24.live/en/table-tennis/l-czech-liga-pro',
    'scores24_wyniki': 'https://scores24.live/en/table-tennis/l-czech-liga-pro/results'
  };
  var nazwy = Object.keys(zrodla), out = ['ligaproDiagnoza2 ' + new Date().toISOString()];
  var odp = UrlFetchApp.fetchAll(nazwy.map(function (n) {
    return {url: zrodla[n], muteHttpExceptions: true, followRedirects: true,
      headers: {'User-Agent': TERMINARZ_UA['User-Agent'], 'Accept': 'text/html,*/*', 'Accept-Language': 'en-US,en;q=0.9'}};
  }));
  odp.forEach(function (r, i) {
    var t = r.getContentText() || '', ad = (t.match(/AD÷(\d{10})/g) || []).map(function (x) { return Number(x.substr(3)); });
    var linia = nazwy[i] + ' | HTTP ' + r.getResponseCode() + ' | ' + t.length + ' znakow | AA÷ x' + (t.match(/AA÷/g) || []).length +
      (ad.length ? ' | AD od ' + new Date(Math.min.apply(null, ad) * 1000).toISOString() + ' do ' + new Date(Math.max.apply(null, ad) * 1000).toISOString() : '') +
      ' | ld+json x' + (t.match(/application\/ld\+json/g) || []).length + ' | SportsEvent x' + (t.match(/SportsEvent/g) || []).length +
      ' | __NEXT_DATA__ ' + (t.indexOf('__NEXT_DATA__') >= 0) + ' | window.__ x' + (t.match(/window\.__[A-Z_]+/g) || []).length +
      ' ' + ((t.match(/window\.__[A-Z_]+/g) || []).slice(0, 5).join(','));
    var k = t.indexOf('AA÷'); if (k < 0) k = t.search(/SportsEvent/); if (k < 0) k = t.search(/"homeTeam"|"competitors"|"teams"/);
    linia += '\n    ' + (k >= 0 ? t.substr(Math.max(0, k - 200), 1500) : '(brak znacznikow danych)').replace(/\s+/g, ' ');
    out.push(linia);
  });
  var folder = DriveApp.getFolderById(TERMINARZ_FOLDER_ID), stare = folder.getFilesByName('ligapro_diagnoza.txt');
  while (stare.hasNext()) stare.next().setTrashed(true);
  folder.createFile('ligapro_diagnoza.txt', out.join('\n'), 'text/plain');
}

/** Diagnoza 3: dane wbudowane w stronę scores24 (window.__…__) i fragmenty wokół dzisiejszej daty. */
function ligaproDiagnoza3() {
  var url = 'https://scores24.live/en/table-tennis/l-czech-liga-pro', d = Utilities.formatDate(new Date(), 'UTC', 'yyyy-MM-dd');
  var r = UrlFetchApp.fetch(url, {muteHttpExceptions: true, followRedirects: true,
    headers: {'User-Agent': TERMINARZ_UA['User-Agent'], 'Accept': 'text/html,*/*', 'Accept-Language': 'en-US,en;q=0.9'}});
  var t = r.getContentText() || '', out = ['ligaproDiagnoza3 ' + new Date().toISOString() + ' | HTTP ' + r.getResponseCode() + ' | ' + t.length];
  var re = /window\.(__[A-Z_]+__)\s*=\s*/g, m;
  while ((m = re.exec(t)) !== null) {
    var s = m.index + m[0].length, e = t.indexOf('</script>', s);
    out.push('ZMIENNA ' + m[1] + ' | dlugosc ' + (e - s) + '\n    ' + t.substr(s, 1200).replace(/\s+/g, ' '));
  }
  var k = -1;
  for (var i = 0; i < 4; i++) {
    k = t.indexOf(d, k + 1); if (k < 0) break;
    out.push('DATA ' + d + ' @' + k + '\n    ' + t.substr(Math.max(0, k - 700), 1400).replace(/\s+/g, ' '));
  }
  var j = t.search(/"(slug|name)":"[^"]*-[^"]*"[^{}]{0,300}"(score|startTime|start_time|timestamp)"/);
  if (j >= 0) out.push('MECZ? @' + j + '\n    ' + t.substr(Math.max(0, j - 300), 1500).replace(/\s+/g, ' '));
  var folder = DriveApp.getFolderById(TERMINARZ_FOLDER_ID), stare = folder.getFilesByName('ligapro_diagnoza.txt');
  while (stare.hasNext()) stare.next().setTrashed(true);
  folder.createFile('ligapro_diagnoza.txt', out.join('\n'), 'text/plain');
}

/** Diagnoza 4: bieżąca liga (czech-liga-pro-1) — mecze z __REACT_QUERY_STATE__ i adres API rapi z kodu strony. */
function ligaproDiagnoza4() {
  var h = {'User-Agent': TERMINARZ_UA['User-Agent'], 'Accept': 'text/html,*/*', 'Accept-Language': 'en-US,en;q=0.9'};
  var out = ['ligaproDiagnoza4 ' + new Date().toISOString()];
  ['czech-liga-pro-1', 'czech-liga-pro'].forEach(function (slug) {
    var r = UrlFetchApp.fetch('https://scores24.live/en/table-tennis/l-' + slug, {muteHttpExceptions: true, headers: h});
    var t = r.getContentText() || '';
    out.push('STRONA ' + slug + ' | HTTP ' + r.getResponseCode() + ' | ' + t.length);
    var m = t.match(/window\.__REACT_QUERY_STATE__\s*=\s*JSON\.parse\(("(?:[^"\\]|\\.)*")\)/);
    if (!m) { out.push('   brak __REACT_QUERY_STATE__'); return; }
    try {
      var st = JSON.parse(JSON.parse(m[1]));
      (st.queries || []).forEach(function (q) {
        var k = (q.queryKey || [])[0] || {}, d = ((q.state || {}).data || {}).data;
        if (k._id !== 'leaguesMatches') return;
        var e = (d && d.edges) || [];
        out.push('   ' + JSON.stringify(k.query) + ' -> ' + e.length + ' meczow');
        e.slice(0, 3).forEach(function (x) { out.push('      ' + JSON.stringify(x.node).substr(0, 700)); });
      });
    } catch (err) { out.push('   JSON blad ' + err); }
    if (slug === 'czech-liga-pro-1') {   // adres API: szukamy „leaguesMatches” w skryptach strony
      var src = (t.match(/<script[^>]+src="([^"]+\.js)"/g) || []).map(function (s) { return s.match(/src="([^"]+)"/)[1]; });
      out.push('   skrypty: ' + src.length);
      for (var i = 0; i < src.length && i < 25; i++) {
        var u = src[i].indexOf('http') === 0 ? src[i] : 'https://scores24.live' + src[i];
        var js = UrlFetchApp.fetch(u, {muteHttpExceptions: true, headers: h}).getContentText() || '';
        var p = js.indexOf('leaguesMatches');
        while (p >= 0 && out.length < 60) {
          out.push('   JS ' + u.split('/').pop() + ' @' + p + ': ' + js.substr(Math.max(0, p - 300), 700).replace(/\s+/g, ' '));
          p = js.indexOf('leaguesMatches', p + 1);
        }
      }
    }
  });
  var folder = DriveApp.getFolderById(TERMINARZ_FOLDER_ID), stare = folder.getFilesByName('ligapro_diagnoza.txt');
  while (stare.hasNext()) stare.next().setTrashed(true);
  folder.createFile('ligapro_diagnoza.txt', out.join('\n'), 'text/plain');
}

/** Diagnoza 5: adres API rapi dla leaguesMatches (definicja w skrypcie strony) + próby wprost. */
function ligaproDiagnoza5() {
  var h = {'User-Agent': TERMINARZ_UA['User-Agent'], 'Accept': 'application/json,text/html,*/*', 'Accept-Language': 'en-US,en;q=0.9'};
  var out = ['ligaproDiagnoza5 ' + new Date().toISOString()];
  var t = UrlFetchApp.fetch('https://scores24.live/en/table-tennis/l-czech-liga-pro-1', {muteHttpExceptions: true, headers: h}).getContentText();
  var tok = (t.match(/window\.__API_TOKEN__\s*=\s*"([^"]+)"/) || [])[1] || '';
  out.push('token ' + tok.length + ' znakow');
  var src = (t.match(/<script[^>]+src="([^"]+\.js)"/g) || []).map(function (s) { return s.match(/src="([^"]+)"/)[1]; });
  src.forEach(function (s) {
    var u = s.indexOf('http') === 0 ? s : 'https://scores24.live' + s, js = UrlFetchApp.fetch(u, {muteHttpExceptions: true, headers: h}).getContentText() || '';
    [/Dne=/g, /\/matches[`'"?]/g, /__API_TOKEN__/g, /rapi/g].forEach(function (re) {
      var m, n = 0;
      while ((m = re.exec(js)) !== null && n < 4) {
        out.push('JS ' + re.source + ' @' + m.index + ': ' + js.substr(Math.max(0, m.index - 250), 600).replace(/\s+/g, ' ')); n++;
      }
    });
  });
  var q = 'lang=en&first=20&status=ended&audience=en&with_statistics=false';
  ['https://scores24.live/rapi/table-tennis/leagues/czech-liga-pro-1/matches?',
   'https://scores24.live/rapi/sports/table-tennis/leagues/czech-liga-pro-1/matches?',
   'https://scores24.live/rapi/leagues/table-tennis/czech-liga-pro-1/matches?',
   'https://scores24.live/rapi/leagues/czech-liga-pro-1/matches?sportSlug=table-tennis&'].forEach(function (u) {
    [{}, {'Authorization': 'Bearer ' + tok}, {'X-Api-Token': tok}].forEach(function (x, i) {
      var hh = {}; Object.keys(h).forEach(function (k) { hh[k] = h[k]; }); Object.keys(x).forEach(function (k) { hh[k] = x[k]; });
      var r = UrlFetchApp.fetch(u + q, {muteHttpExceptions: true, headers: hh});
      out.push('PROBA ' + u + ' naglowek ' + i + ' | HTTP ' + r.getResponseCode() + ' | ' + (r.getContentText() || '').substr(0, 250).replace(/\s+/g, ' '));
    });
  });
  var folder = DriveApp.getFolderById(TERMINARZ_FOLDER_ID), stare = folder.getFilesByName('ligapro_diagnoza.txt');
  while (stare.hasNext()) stare.next().setTrashed(true);
  folder.createFile('ligapro_diagnoza.txt', out.join('\n'), 'text/plain');
}
