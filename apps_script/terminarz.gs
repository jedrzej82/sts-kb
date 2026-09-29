/**
 * TERMINARZ STS — samodzielny dodatek do projektu Apps Script „wyniki STS” (29.09.2026, faza 3b).
 * Co godzinę zapisuje mecze DZIŚ i JUTRO z 365scores (także nierozegrane) do terminarz_365.csv.gz w folderze
 * „baza-wiedzy”. typuj.py szuka w nim meczu z oferty po OBU drużynach i odrzuca klub dopasowany do ligi z innego kraju.
 *
 * INSTALACJA (nie zmienia istniejącego kodu):
 *  1. W projekcie „wyniki STS”: „+” obok „Pliki” → „Skrypt” → nazwij „terminarz” → wklej CAŁY ten plik → Ctrl+S.
 *  2. U góry wybierz funkcję „terminarzUstaw” → „Uruchom” → zezwól na dostęp. Tworzy osobny wyzwalacz co godzinę
 *     i od razu zapisuje pierwszy plik. Wszystkie nazwy mają przedrostek „terminarz”, żeby nie kolidować z resztą kodu.
 *  Wyłączenie: uruchom „terminarzUsun”.
 *  Diagnoza pokrycia: uruchom „terminarzDiagnoza” — zapisuje terminarz_diagnoza.txt (liczby meczów przy różnych
 *  parametrach zapytania) do tego samego folderu. Nic nie zmienia w terminarzu.
 *
 * PLIK: terminarz_365.csv.gz (nadpisywany) — kolumny: data,godzina_utc,sport,kraj,turniej,runda,gosp,gosc,status
 *   status 365scores: 2 = przed meczem, 3 = trwa, 4 = koniec. Czas UTC.
 */
var TERMINARZ_FOLDER_ID = 'WKLEJ_ID_FOLDERU_BAZA_WIEDZY';   // ID folderu baza-wiedzy (z adresu folderu na Dysku)
var TERMINARZ_MAX_SPORT = 40;   // identyfikatory sportów 365scores 1..40
var TERMINARZ_UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36',
  'Accept': 'application/json, text/plain, */*', 'Accept-Language': 'en-US,en;q=0.9'};

function terminarzUstaw() {
  terminarzUsun();
  ScriptApp.newTrigger('terminarzPracuj').timeBased().everyHours(1).create();
  terminarzPracuj();
}

function terminarzUsun() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'terminarzPracuj') ScriptApp.deleteTrigger(t);
  });
}

function terminarzPracuj() {
  var dzis = Utilities.formatDate(new Date(), 'UTC', 'yyyy-MM-dd');
  var jutro = Utilities.formatDate(new Date(Date.now() + 86400000), 'UTC', 'yyyy-MM-dd');
  var wiersze = [], nazwySportow = {};
  [dzis, jutro].forEach(function (d) {
    var dm = d.substr(8, 2) + '/' + d.substr(5, 2) + '/' + d.substr(0, 4), ids = [];
    for (var i = 1; i <= TERMINARZ_MAX_SPORT; i++) ids.push(i);
    terminarzPobierz(ids.map(function (id) {
      return 'https://webws.365scores.com/web/games/allscores/?appTypeId=5&langId=1&timezoneName=UTC&userCountryId=1&sports=' + id +
        '&startDate=' + dm + '&endDate=' + dm + '&showOdds=false&onlyMajorGames=false&withTop=false';
    })).forEach(function (r, i) {
      if (r.getResponseCode() !== 200) return;
      var j; try { j = JSON.parse(r.getContentText()); } catch (e) { return; }
      var id = ids[i], strony = [j];
      for (var p = 0; p < 30 && j.paging && j.paging.nextPage; p++) {
        var r2 = terminarzPobierz(['https://webws.365scores.com' + j.paging.nextPage])[0];
        if (r2.getResponseCode() !== 200) break;
        try { j = JSON.parse(r2.getContentText()); } catch (e) { break; }
        strony.push(j);
      }
      var kraje = {}, komp = {};
      strony.forEach(function (x) {
        (x.sports || []).forEach(function (s) { if (s.id === id) nazwySportow[id] = s.nameForURL || s.name; });
        (x.countries || []).forEach(function (c) { kraje[c.id] = c.name; });
        (x.competitions || []).forEach(function (c) { komp[c.id] = c; });
      });
      var sport = id === 1 ? 'football' : String(nazwySportow[id] || ('s' + id)).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      strony.forEach(function (x) {
        (x.games || []).forEach(function (g) {
          var st = String(g.startTime || ''); if (st.substr(0, 10) !== d) return;
          var h = g.homeCompetitor || {}, a = g.awayCompetitor || {}, k = komp[g.competitionId] || {};
          wiersze.push(terminarzCsv([d, st.substr(11, 5), sport, kraje[k.countryId] || '', k.name || g.competitionDisplayName || '',
            g.roundName || g.stageName || '', h.name, a.name, g.statusGroup]));
        });
      });
    });
  });
  if (!wiersze.length) return;
  var tresc = 'data,godzina_utc,sport,kraj,turniej,runda,gosp,gosc,status\n' + wiersze.join('\n');
  var folder = DriveApp.getFolderById(TERMINARZ_FOLDER_ID), stare = folder.getFilesByName('terminarz_365.csv.gz'), doKosza = [];
  while (stare.hasNext()) doKosza.push(stare.next());
  folder.createFile(Utilities.gzip(Utilities.newBlob(tresc, 'text/csv', 'terminarz_365.csv')).setName('terminarz_365.csv.gz'));
  doKosza.forEach(function (f) { f.setTrashed(true); });   // stary plik dopiero PO zapisie nowego
}

function terminarzDiagnoza() {
  var d = Utilities.formatDate(new Date(), 'UTC', 'dd/MM/yyyy'), baza = 'https://webws.365scores.com/web/games/';
  var warianty = {
    'obecny': 'allscores/?appTypeId=5&langId=1&timezoneName=UTC&userCountryId=1&showOdds=false&onlyMajorGames=false&withTop=false',
    'bez_kraju': 'allscores/?appTypeId=5&langId=1&timezoneName=UTC&showOdds=false&onlyMajorGames=false&withTop=false',
    'kraj_PL': 'allscores/?appTypeId=5&langId=1&timezoneName=UTC&userCountryId=35&showOdds=false&onlyMajorGames=false&withTop=false',
    'top': 'allscores/?appTypeId=5&langId=1&timezoneName=UTC&userCountryId=1&showOdds=true&onlyMajorGames=false&withTop=true',
    'games': '?appTypeId=5&langId=1&timezoneName=UTC&userCountryId=1',
    'tydzien_temu': 'allscores/?appTypeId=5&langId=1&timezoneName=UTC&userCountryId=1&showOdds=false&onlyMajorGames=false&withTop=false'
  };
  var d7 = Utilities.formatDate(new Date(Date.now() - 7 * 86400000), 'UTC', 'dd/MM/yyyy');
  var out = ['terminarzDiagnoza ' + new Date().toISOString() + ' dzien ' + d];
  [1, 4, 5, 2].forEach(function (sport) {
    Object.keys(warianty).forEach(function (w) {
      var dd = w === 'tydzien_temu' ? d7 : d;
      var url = baza + warianty[w] + '&sports=' + sport + '&startDate=' + dd + '&endDate=' + dd, r = terminarzPobierz([url])[0];
      var linia = 'sport ' + sport + ' | ' + w + ' | HTTP ' + r.getResponseCode();
      try {
        var j = JSON.parse(r.getContentText()), n = (j.games || []).length, strony = 1, kom = {};
        (j.competitions || []).forEach(function (c) { kom[c.id] = c.name; });
        var ile = {}; (j.games || []).forEach(function (g) { var k = kom[g.competitionId] || g.competitionDisplayName; ile[k] = (ile[k] || 0) + 1; });
        var x = j;
        while (strony < 30 && x.paging && x.paging.nextPage) {
          var r2 = terminarzPobierz(['https://webws.365scores.com' + x.paging.nextPage])[0];
          if (r2.getResponseCode() !== 200) break;
          x = JSON.parse(r2.getContentText()); n += (x.games || []).length; strony++;
        }
        linia += ' | mecze ' + n + ' | strony ' + strony + ' | rozgrywek ' + (j.competitions || []).length +
          ' | klucze ' + Object.keys(j).join(',') + ' | paging ' + JSON.stringify(j.paging || null).substr(0, 200);
        if (w === 'obecny') linia += '\n    ' + Object.keys(ile).map(function (k) { return k + ':' + ile[k]; }).join('; ').substr(0, 1500);
      } catch (e) { linia += ' | blad ' + e; }
      out.push(linia);
    });
  });
  var folder = DriveApp.getFolderById(TERMINARZ_FOLDER_ID), stare = folder.getFilesByName('terminarz_diagnoza.txt');
  while (stare.hasNext()) stare.next().setTrashed(true);
  folder.createFile('terminarz_diagnoza.txt', out.join('\n'), 'text/plain');
}

function terminarzPobierz(urls) {
  var out = [], req = urls.map(function (u) { return {url: u, muteHttpExceptions: true, headers: TERMINARZ_UA}; });
  for (var i = 0; i < req.length; i += 25) UrlFetchApp.fetchAll(req.slice(i, i + 25)).forEach(function (x) { out.push(x); });
  return out;
}

function terminarzCsv(a) {
  return a.map(function (v) {
    v = (v === undefined || v === null) ? '' : String(v);
    return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
  }).join(',');
}
