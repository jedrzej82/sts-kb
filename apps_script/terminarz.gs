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
 *  FLASHSCORE (od 29.09): 365scores nie ma futsalu, darta, snookera, tenisa stołowego i wielu niższych lig, więc terminarzPracuj zapisuje też
 *  terminarz_fs.csv.gz z Flashscore (te same kolumny) i terminarz_fs_log.txt (liczba meczów per sport, kody HTTP).
 *  typuj.py szuka najpierw we Flashscore, potem w 365scores.
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
  try { terminarzFs(); } catch (e) { Logger.log('terminarzFs: ' + e); }   // błąd Flashscore nie blokuje 365scores
  var dzis = Utilities.formatDate(new Date(), 'UTC', 'yyyy-MM-dd');
  var jutro = Utilities.formatDate(new Date(Date.now() + 86400000), 'UTC', 'yyyy-MM-dd');
  var wiersze = [], nazwySportow = {}, brakPilki = [];
  [dzis, jutro].forEach(function (d) {
    var dm = d.substr(8, 2) + '/' + d.substr(5, 2) + '/' + d.substr(0, 4), ids = [];
    for (var i = 1; i <= TERMINARZ_MAX_SPORT; i++) ids.push(i);
    terminarzPobierz(ids.map(function (id) {
      return 'https://webws.365scores.com/web/games/allscores/?appTypeId=5&langId=1&timezoneName=UTC&userCountryId=1&sports=' + id +
        '&startDate=' + dm + '&endDate=' + dm + '&showOdds=false&onlyMajorGames=false&withTop=false';
    })).forEach(function (r, i) {
      if (r.getResponseCode() !== 200) { if (ids[i] === 1) brakPilki.push(d); return; }
      var j; try { j = JSON.parse(r.getContentText()); } catch (e) { if (ids[i] === 1) brakPilki.push(d); return; }
      var id = ids[i], strony = [j];
      for (var p = 0; p < 30 && j.paging && j.paging.nextPage; p++) {
        var r2 = terminarzPobierz(['https://webws.365scores.com' + j.paging.nextPage])[0];
        if (r2.getResponseCode() !== 200) { if (id === 1) brakPilki.push(d); break; }
        try { j = JSON.parse(r2.getContentText()); } catch (e) { if (id === 1) brakPilki.push(d); break; }
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
  // 30.09.2026 (przegląd): jeden błąd HTTP przy piłce nadpisywał plik terminarzem BEZ piłki na całą godzinę —
  // typuj.py pomijał wtedy po cichu kontrolę kraju/ligi. Niepełna piłka = zostaje poprzedni plik.
  if (brakPilki.length) { Logger.log('terminarz365: piłka niepobrana (' + brakPilki.join(', ') + ') — zostaje poprzedni plik'); return; }
  var tresc = 'data,godzina_utc,sport,kraj,turniej,runda,gosp,gosc,status\n' + wiersze.join('\n');
  var folder = DriveApp.getFolderById(TERMINARZ_FOLDER_ID), stare = folder.getFilesByName('terminarz_365.csv.gz'), doKosza = [];
  while (stare.hasNext()) doKosza.push(stare.next());
  folder.createFile(Utilities.gzip(Utilities.newBlob(tresc, 'text/csv', 'terminarz_365.csv')).setName('terminarz_365.csv.gz'));
  doKosza.forEach(function (f) { f.setTrashed(true); });   // stary plik dopiero PO zapisie nowego
}

// Flashscore: identyfikator sportu -> nazwa w pliku (jak w wyniki_fs_*; piłka jako „football” dla typuj.py)
var TERMINARZ_FS_SPORTY = {1: 'football', 2: 'tennis', 3: 'basketball', 4: 'hockey', 5: 'american-football', 6: 'baseball',
  7: 'handball', 8: 'rugby-union', 9: 'floorball', 10: 'bandy', 11: 'futsal', 12: 'volleyball', 13: 'cricket', 14: 'darts',
  15: 'snooker', 16: 'boxing', 17: 'beach-volleyball', 18: 'aussie-rules', 19: 'rugby-league', 21: 'badminton',
  22: 'waterpolo', 24: 'field-hockey', 25: 'table-tennis', 26: 'beach-soccer', 28: 'mma', 30: 'pesapallo', 36: 'esports'};
var TERMINARZ_FS_HOSTY = ['https://global.flashscore.ninja/2/x/feed/', 'https://d.flashscore.com/x/feed/'];

function terminarzFs() {
  var ids = [];   // wszystkie 1..45: numery spoza mapy trafiają do pliku jako „fsNN” (log pokazuje ich rozgrywki)
  for (var q = 1; q <= 45; q++) ids.push(String(q));
  var wiersze = [], byly = {}, log = ['terminarzFs ' + new Date().toISOString()], brakPilki = [];
  [0, 1].forEach(function (dzien) {   // 0 = dziś, 1 = jutro (strefa 0 = UTC)
    var odp = null, host = '';
    for (var h = 0; h < TERMINARZ_FS_HOSTY.length && !odp; h++) {
      host = TERMINARZ_FS_HOSTY[h];
      var proba = UrlFetchApp.fetchAll(ids.map(function (id) {
        return {url: host + 'f_' + id + '_' + dzien + '_0_en_1', muteHttpExceptions: true,
          headers: {'x-fsign': 'SW9D1eZo', 'User-Agent': TERMINARZ_UA['User-Agent'], 'Referer': 'https://www.flashscore.com/'}};
      }));
      if (proba.some(function (r) { return r.getResponseCode() === 200 && r.getContentText().indexOf('AA÷') >= 0; })) odp = proba;
      else log.push('dzien ' + dzien + ' host ' + host + ': brak danych (' + proba.map(function (r) { return r.getResponseCode(); }).join(',') + ')');
    }
    if (!odp) { brakPilki.push(dzien); return; }
    odp.forEach(function (r, i) {
      var sport = TERMINARZ_FS_SPORTY[ids[i]] || ('fs' + ids[i]), n = 0, kraj = '', turniej = '', pierwsza = '';
      if (r.getResponseCode() !== 200) { log.push('dzien ' + dzien + ' ' + sport + ': HTTP ' + r.getResponseCode()); if (ids[i] === '1') brakPilki.push(dzien); return; }
      r.getContentText().split('~').forEach(function (rek) {
        var f = {};
        rek.split('¬').forEach(function (p) { var k = p.indexOf('÷'); if (k > 0) f[p.substr(0, k)] = p.substr(k + 1); });
        if (f.ZA !== undefined) {   // nagłówek rozgrywek: „KRAJ: Liga”
          var c = f.ZA.indexOf(': ');
          kraj = c > 0 ? f.ZA.substr(0, c) : (f.ZY || ''); turniej = c > 0 ? f.ZA.substr(c + 2) : f.ZA;
          if (!pierwsza) pierwsza = f.ZA;
        } else if (f.AA !== undefined && f.AD && !byly[f.AA]) {
          byly[f.AA] = 1;
          var t = new Date(Number(f.AD) * 1000), st = f.AB === '3' ? 4 : f.AB === '2' ? 3 : 2;
          wiersze.push(terminarzCsv([Utilities.formatDate(t, 'UTC', 'yyyy-MM-dd'), Utilities.formatDate(t, 'UTC', 'HH:mm'), sport,
            kraj, turniej, f.ER || '', f.AE || f.FH || '', f.AF || f.FK || '', st]));
          n++;
        }
      });
      var tekst = r.getContentText();
      if (n || TERMINARZ_FS_SPORTY[ids[i]]) log.push('dzien ' + dzien + ' ' + sport + ' (id ' + ids[i] + '): ' + n + ' meczów' +
        (pierwsza ? ' | np. ' + pierwsza : '') + (!n && tekst ? ' | odpowiedź: ' + tekst.substr(0, 80).replace(/[^ -~]/g, '?') : ''));
    });
  });
  var folder = DriveApp.getFolderById(TERMINARZ_FOLDER_ID);
  // 30.09.2026 (przegląd): jak w terminarz365 — bez kompletnej piłki nie nadpisujemy pliku
  if (brakPilki.length) log.push('piłka niepobrana (dzien ' + brakPilki.join(', ') + ') — zostaje poprzedni terminarz_fs.csv.gz');
  if (wiersze.length && !brakPilki.length) {
    var tresc = 'data,godzina_utc,sport,kraj,turniej,runda,gosp,gosc,status\n' + wiersze.join('\n');
    var stare = folder.getFilesByName('terminarz_fs.csv.gz'), doKosza = [];
    while (stare.hasNext()) doKosza.push(stare.next());
    folder.createFile(Utilities.gzip(Utilities.newBlob(tresc, 'text/csv', 'terminarz_fs.csv')).setName('terminarz_fs.csv.gz'));
    doKosza.forEach(function (f) { f.setTrashed(true); });
  }
  var sl = folder.getFilesByName('terminarz_fs_log.txt');
  while (sl.hasNext()) sl.next().setTrashed(true);
  folder.createFile('terminarz_fs_log.txt', log.join('\n') + '\nrazem ' + wiersze.length, 'text/plain');
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

// 29.09.2026: WYNIKI koszykówki, piłki ręcznej i siatkówki z Flashscore (ten sam kanał co terminarzFs, dzień -1 i -2).
// Wcześniej te sporty były tylko z 365scores — np. Liga Europejska EHF: 24 z 32 drużyn bez żadnego wyniku w bazie.
// Plik miesięczny wyniki_fsx_inne_RRRR-MM.csv.gz (format jak wyniki_fs_inne); zewn.py usuwa mecze, które 365 już ma.
// Wyzwalacz: codziennie ok. 06:00 (ustaw raz: wynikiFsUstaw).
var WYNIKI_FS_SPORTY = {3: 'basketball', 7: 'handball', 12: 'volleyball'};

// 30.09.2026 (przegląd): klucz scalania = 7 pierwszych PÓL CSV (data..gosc). Dotąd split(',') na surowym wierszu —
// przecinek w cudzysłowie („EHF, Group A”) przesuwał pola i dwa mecze tego samego gospodarza jednego dnia się nadpisywały.
function _klucz7_(w) { return Utilities.parseCsv(w)[0].slice(0, 7).join('\u0001'); }

function wynikiFsDruzynowe(dni) {
  var ids = Object.keys(WYNIKI_FS_SPORTY), nowe = {}, log = ['wynikiFsDruzynowe ' + new Date().toISOString()];
  (Array.isArray(dni) ? dni : [-1, -2]).forEach(function (dzien) {
    var odp = null;
    for (var h = 0; h < TERMINARZ_FS_HOSTY.length && !odp; h++) {
      var host = TERMINARZ_FS_HOSTY[h];
      var proba = UrlFetchApp.fetchAll(ids.map(function (id) {
        return {url: host + 'f_' + id + '_' + dzien + '_0_en_1', muteHttpExceptions: true,
          headers: {'x-fsign': 'SW9D1eZo', 'User-Agent': TERMINARZ_UA['User-Agent'], 'Referer': 'https://www.flashscore.com/'}};
      }));
      if (proba.some(function (r) { return r.getResponseCode() === 200 && r.getContentText().indexOf('AA÷') >= 0; })) odp = proba;
    }
    if (!odp) { log.push('dzien ' + dzien + ': brak danych'); return; }
    odp.forEach(function (r, i) {
      var sport = WYNIKI_FS_SPORTY[ids[i]], kraj = '', turniej = '', n = 0;
      if (r.getResponseCode() !== 200) return;
      r.getContentText().split('~').forEach(function (rek) {
        var f = {};
        rek.split('¬').forEach(function (p) { var k = p.indexOf('÷'); if (k > 0) f[p.substr(0, k)] = p.substr(k + 1); });
        if (f.ZA !== undefined) {
          var c = f.ZA.indexOf(': ');
          kraj = c > 0 ? f.ZA.substr(0, c) : (f.ZY || ''); turniej = c > 0 ? f.ZA.substr(c + 2) : f.ZA;
        } else if (f.AA !== undefined && f.AB === '3' && f.AG !== undefined && f.AH !== undefined && f.AD) {
          var t = new Date(Number(f.AD) * 1000), og = [], oa = [];
          [['BA', 'BB'], ['BC', 'BD'], ['BE', 'BF'], ['BG', 'BH'], ['BI', 'BJ']].forEach(function (p) {
            if (f[p[0]] !== undefined && f[p[1]] !== undefined) { og.push(f[p[0]]); oa.push(f[p[1]]); }
          });
          var g = Number(f.AG), a = Number(f.AH);
          nowe[f.AA] = terminarzCsv([Utilities.formatDate(t, 'UTC', 'yyyy-MM-dd'), sport, kraj, turniej, f.ER || '',
            f.AE || f.FH || '', f.AF || f.FK || '', f.AG, f.AH, og.join(';'), oa.join(';'), g > a ? 1 : a > g ? 2 : 0, '']);
          n++;
        }
      });
      log.push('dzien ' + dzien + ' ' + sport + ': ' + n + ' zakonczonych');
    });
  });
  var folder = DriveApp.getFolderById(TERMINARZ_FOLDER_ID), naglowek = 'data,sport,kraj,turniej,runda,gosp,gosc,wg,wa,okresy_g,okresy_a,zwyciezca,nawierzchnia';
  var miesiace = {};
  Object.keys(nowe).forEach(function (id) { var m = nowe[id].substr(0, 7); (miesiace[m] = miesiace[m] || {})[id] = nowe[id]; });
  Object.keys(miesiace).forEach(function (m) {
    var nazwa = 'wyniki_fsx_inne_' + m + '.csv.gz', stare = folder.getFilesByName(nazwa), doKosza = [], wiersze = {};
    while (stare.hasNext()) {
      var plik = stare.next(); doKosza.push(plik);
      Utilities.ungzip(plik.getBlob()).getDataAsString().split('\n').slice(1).forEach(function (w) {
        if (w) wiersze[_klucz7_(w)] = w;   // klucz: data..gosc
      });
    }
    Object.keys(miesiace[m]).forEach(function (id) { var w = miesiace[m][id]; wiersze[_klucz7_(w)] = w; });
    var tresc = naglowek + '\n' + Object.keys(wiersze).map(function (k) { return wiersze[k]; }).join('\n');
    folder.createFile(Utilities.gzip(Utilities.newBlob(tresc, 'text/csv', nazwa.replace('.gz', ''))).setName(nazwa));
    doKosza.forEach(function (f) { f.setTrashed(true); });   // stary plik dopiero PO zapisie nowego
    log.push(nazwa + ': ' + Object.keys(wiersze).length + ' meczow');
  });
  var sl = folder.getFilesByName('wyniki_fsx_log.txt');
  while (sl.hasNext()) sl.next().setTrashed(true);
  folder.createFile('wyniki_fsx_log.txt', log.join('\n'), 'text/plain');
}

function wynikiFsUstaw() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'wynikiFsDruzynowe') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('wynikiFsDruzynowe').timeBased().everyDays(1).atHour(6).create();
  wynikiFsDruzynowe();
}

// Jednorazowo: zaległe 7 dni (Flashscore trzyma wyniki tygodnia wstecz) — więcej meczów do Elo na start.
function wynikiFsTydzien() {
  wynikiFsDruzynowe([-1, -2, -3, -4, -5, -6, -7]);
}

// ---------------------------------------------------------------------------------------------
// 29.09.2026: HISTORIA piłki ręcznej z 365scores (wszystkie ligi, nie tylko te, które zbiera „wyniki STS”).
// Liga Europejska, ligi skandynawskie i polska miały po 1–2 mecze w bazie — model nie mógł ich typować.
// allscores przyjmuje daty z przeszłości: pobieramy dzień po dniu od HIST365_OD do wczoraj i zapisujemy JEDEN plik
// wyniki_365h_inne_archiwum.csv.gz (format jak wyniki_365_inne; zewn.py czyta go sam, duble z 365 usuwa).
// Limit Apps Script (6 min): po ok. 4,5 min zapis postępu — URUCHOM PONOWNIE, aż log pokaże „GOTOWE”.
var HIST365_SPORT = 'handball', HIST365_OD = '2025-07-01', HIST365_PLIK = 'wyniki_365h_inne_archiwum.csv.gz';

function _hist365Sport_(props) {
  var sid = Number(props.getProperty('H365_SID') || 0);
  if (sid) return sid;
  var d = Utilities.formatDate(new Date(Date.now() - 86400000), 'UTC', 'dd/MM/yyyy'), ids = [];
  for (var i = 1; i <= TERMINARZ_MAX_SPORT; i++) ids.push(i);
  terminarzPobierz(ids.map(function (id) {
    return 'https://webws.365scores.com/web/games/allscores/?appTypeId=5&langId=1&timezoneName=UTC&userCountryId=1&sports=' + id +
      '&startDate=' + d + '&endDate=' + d + '&showOdds=false&onlyMajorGames=false&withTop=false';
  })).forEach(function (r, i) {
    if (sid || r.getResponseCode() !== 200) return;
    var j; try { j = JSON.parse(r.getContentText()); } catch (e) { return; }
    (j.sports || []).forEach(function (s) {
      if (s.id === ids[i] && String(s.nameForURL || s.name).toLowerCase() === HIST365_SPORT) sid = s.id;
    });
  });
  if (sid) props.setProperty('H365_SID', String(sid));
  return sid;
}

function wyniki365Historia() {
  var start = Date.now(), props = PropertiesService.getScriptProperties(), log = ['wyniki365Historia ' + new Date().toISOString()];
  var sid = _hist365Sport_(props);
  var folder = DriveApp.getFolderById(TERMINARZ_FOLDER_ID);
  if (!sid) { folder.createFile('wyniki_365h_log.txt', log.concat(['nie znaleziono sportu ' + HIST365_SPORT + ' w 365scores']).join('\n'), 'text/plain'); return; }
  var gotowe = JSON.parse(props.getProperty('H365_DNI') || '{}'), dni = [];
  var wczoraj = Utilities.formatDate(new Date(Date.now() - 86400000), 'UTC', 'yyyy-MM-dd');
  for (var t = new Date(HIST365_OD + 'T12:00:00Z'); Utilities.formatDate(t, 'UTC', 'yyyy-MM-dd') <= wczoraj; t = new Date(t.getTime() + 86400000)) {
    var dd = Utilities.formatDate(t, 'UTC', 'yyyy-MM-dd');
    if (!gotowe[dd] && !(dd <= (props.getProperty('H365_DO') || ''))) dni.push(dd);
  }
  var wiersze = {}, stare = folder.getFilesByName(HIST365_PLIK), doKosza = [];
  while (stare.hasNext()) {
    var plik = stare.next(); doKosza.push(plik);
    Utilities.ungzip(plik.getBlob()).getDataAsString().split('\n').slice(1).forEach(function (w) {
      if (w) wiersze[_klucz7_(w)] = w;
    });
  }
  var nowe = 0, zrobione = 0;
  for (var i = 0; i < dni.length && Date.now() - start < 270000; i += 10) {
    var paczka = dni.slice(i, i + 10);
    terminarzPobierz(paczka.map(function (d) {
      var dm = d.substr(8, 2) + '/' + d.substr(5, 2) + '/' + d.substr(0, 4);
      return 'https://webws.365scores.com/web/games/allscores/?appTypeId=5&langId=1&timezoneName=UTC&userCountryId=1&sports=' + sid +
        '&startDate=' + dm + '&endDate=' + dm + '&showOdds=false&onlyMajorGames=false&withTop=false';
    })).forEach(function (r, k) {
      var d = paczka[k];
      if (r.getResponseCode() !== 200) { log.push(d + ': HTTP ' + r.getResponseCode()); return; }
      var j; try { j = JSON.parse(r.getContentText()); } catch (e) { log.push(d + ': zly JSON'); return; }
      var strony = [j], niepelny = false;
      for (var p = 0; p < 30 && j.paging && j.paging.nextPage; p++) {
        var r2 = terminarzPobierz(['https://webws.365scores.com' + j.paging.nextPage])[0];
        if (r2.getResponseCode() !== 200) { niepelny = true; break; }
        try { j = JSON.parse(r2.getContentText()); } catch (e) { niepelny = true; break; }
        strony.push(j);
      }
      var kraje = {}, komp = {};
      strony.forEach(function (x) {
        (x.countries || []).forEach(function (c) { kraje[c.id] = c.name; });
        (x.competitions || []).forEach(function (c) { komp[c.id] = c; });
      });
      strony.forEach(function (x) {
        (x.games || []).forEach(function (g) {
          var st = String(g.startTime || '');
          if (st.substr(0, 10) !== d || g.statusGroup !== 4) return;
          var h = g.homeCompetitor || {}, a = g.awayCompetitor || {}, kp = komp[g.competitionId] || {};
          var sg = Number(h.score), sa = Number(a.score);
          if (!(sg >= 0) || !(sa >= 0)) return;
          var w = terminarzCsv([d, HIST365_SPORT, kraje[kp.countryId] || '', kp.name || g.competitionDisplayName || '',
            g.roundName || g.stageName || '', h.name, a.name, sg, sa, '', '', sg > sa ? 1 : sa > sg ? 2 : 0, '']);
          var klucz = _klucz7_(w);
          if (!wiersze[klucz]) nowe++;
          wiersze[klucz] = w;
        });
      });
      // 30.09.2026 (przegląd): nieudana dalsza strona — mecze z pierwszych stron zostają, ale dzień NIE jest gotowy
      if (niepelny) { log.push(d + ': niepełne (błąd dalszej strony) — ponowię'); return; }
      gotowe[d] = 1; zrobione++;
    });
  }
  var naglowek = 'data,sport,kraj,turniej,runda,gosp,gosc,wg,wa,okresy_g,okresy_a,zwyciezca,nawierzchnia';
  var tresc = naglowek + '\n' + Object.keys(wiersze).map(function (k) { return wiersze[k]; }).join('\n');
  folder.createFile(Utilities.gzip(Utilities.newBlob(tresc, 'text/csv', HIST365_PLIK.replace('.gz', ''))).setName(HIST365_PLIK));
  doKosza.forEach(function (f) { f.setTrashed(true); });   // stary plik dopiero PO zapisie nowego
  // 29.09.2026 (przeglad): wlasciwosc skryptu ma limit 9 KB — pelna lista dni (ok. 15 B/dzien) przekroczylaby go w 2027.
  // Zapamietujemy date, do ktorej WSZYSTKIE dni sa pobrane (H365_DO), i tylko pojedyncze dni po niej.
  var ciag = props.getProperty('H365_DO') || '';
  for (var t2 = new Date((ciag || HIST365_OD) + 'T12:00:00Z'); ; t2 = new Date(t2.getTime() + 86400000)) {
    var d2 = Utilities.formatDate(t2, 'UTC', 'yyyy-MM-dd');
    if (d2 > wczoraj || (d2 > ciag && !gotowe[d2])) break;
    ciag = d2;
  }
  Object.keys(gotowe).forEach(function (k) { if (k <= ciag) delete gotowe[k]; });
  if (ciag) props.setProperty('H365_DO', ciag);
  props.setProperty('H365_DNI', JSON.stringify(gotowe));
  var zostalo = dni.length - zrobione;
  log.push('sport 365 id ' + sid + '; dni pobrane teraz: ' + zrobione + ', nowych meczow: ' + nowe + ', w pliku: ' + Object.keys(wiersze).length);
  log.push(zostalo > 0 ? 'ZOSTALO ' + zostalo + ' dni — URUCHOM PONOWNIE wyniki365Historia' : 'GOTOWE — wszystkie dni od ' + HIST365_OD);
  var sl = folder.getFilesByName('wyniki_365h_log.txt');
  while (sl.hasNext()) sl.next().setTrashed(true);
  folder.createFile('wyniki_365h_log.txt', log.join('\n'), 'text/plain');
}
