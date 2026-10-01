/**
 * ARKUSZE STS — samodzielny dodatek do projektu Apps Script „wyniki STS” (30.09.2026).
 * Co 30 minut zapisuje arkusze statystyk jako spakowane CSV: statystyki_druzyn.csv.gz, statystyki_tenis.csv.gz, …,
 * absencje.csv.gz — w tym samym folderze „baza-wiedzy”.
 * PO CO: przebieg pobiera arkusze przez konektor Dysku; eksport CSV wraca W TREŚCI odpowiedzi i trzeba go przepisać
 * w całości. 30.09 (15:00) nie zmieściło się to w budżecie czasu i hokej oraz ręczna trafiły do bazy NIEPEŁNE.
 * Spakowany plik jest kilka razy krótszy, a przebieg.py sprawdza, czy gzip jest cały.
 *
 * INSTALACJA (nie zmienia istniejącego kodu):
 *  1. W projekcie „wyniki STS”: „+” obok „Pliki” → „Skrypt” → nazwij „arkusze” → wklej CAŁY ten plik → Ctrl+S.
 *  2. U góry wybierz funkcję „arkuszeUstaw” → „Uruchom” → zezwól na dostęp. Tworzy wyzwalacz co 30 minut
 *     i od razu zapisuje pliki. Wyłączenie: „arkuszeUsun”.
 *  Log ostatniego przebiegu: arkusze_log.txt w tym samym folderze.
 *
 * Arkusz jest eksportowany tylko wtedy, gdy zmienił się od poprzedniego zapisu (data modyfikacji pliku), więc
 * wyzwalacz co 30 minut nie zużywa limitów. Pusty eksport (sam nagłówek albo nic) NIE nadpisuje poprzedniego pliku.
 *
 * ARCHIWUM (01.10.2026, P57.7/P111.2): raz dziennie, w pierwszym przebiegu po 12:00 czasu polskiego, gdy nie ma jeszcze
 * pliku arkusze_RRRR-MM-DD.zip — pakuje bieżące statystyki_*.csv.gz i absencje.csv.gz (+ arkusze_manifest.csv z datą
 * zmiany każdego arkusza) do arkusze_RRRR-MM-DD.zip w tym samym folderze. PO CO: przebieg 01.10 12:00 zbudował archiwum
 * (388 KB), ale konektor Dysku nie przyjmuje tak dużego pliku binarnego z przebiegu — archiwum dnia nie trafiło na Dysk.
 * Po aktualizacji: wklej CAŁY plik ponownie i uruchom „arkuszeUstaw” (archiwum dnia powstanie samo).
 */
var ARKUSZE_FOLDER_ID = 'WKLEJ_ID_FOLDERU_BAZA_WIEDZY';   // ID folderu baza-wiedzy (z adresu folderu na Dysku)
var ARKUSZE_NAZWY = ['statystyki_druzyn', 'statystyki_tenis', 'statystyki_koszykowka', 'statystyki_siatkowka',
  'statystyki_hokej', 'statystyki_reczna', 'statystyki_baseball', 'statystyki_futbol_amerykanski', 'statystyki_rugby',
  'absencje'];

function arkuszeUstaw() {
  arkuszeUsun();
  ScriptApp.newTrigger('arkuszePracuj').timeBased().everyMinutes(30).create();
  arkuszePracuj(true);
}

function arkuszeUsun() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'arkuszePracuj') ScriptApp.deleteTrigger(t);
  });
}

/** Eksport pierwszego arkusza pliku jako CSV — ten sam wynik, co „Pobierz → CSV” (i konektor z text/csv). */
function arkuszeCsv_(id) {
  var r = UrlFetchApp.fetch('https://docs.google.com/spreadsheets/d/' + id + '/export?format=csv',
    {headers: {Authorization: 'Bearer ' + ScriptApp.getOAuthToken()}, muteHttpExceptions: true});
  if (r.getResponseCode() !== 200) throw new Error('HTTP ' + r.getResponseCode());
  return r.getContentText('UTF-8');
}

/** Czy eksport ma dane: nagłówek + co najmniej jeden wiersz; arkusz statystyk musi mieć kolumnę data_aktualizacji. */
function arkuszeDobry_(nazwa, csv) {
  var linie = csv.split('\n').filter(function (l) { return l.replace(/[\s,]/g, '') !== ''; });
  if (linie.length < 2) return 'pusty eksport (' + linie.length + ' linii)';
  if (nazwa.indexOf('statystyki_') === 0 && linie[0].indexOf('data_aktualizacji') < 0) return 'brak kolumny data_aktualizacji';
  return '';
}

function arkuszePracuj(wszystkie) {
  var folder = DriveApp.getFolderById(ARKUSZE_FOLDER_ID), P = PropertiesService.getScriptProperties();
  var log = ['arkuszePracuj ' + new Date().toISOString()];
  ARKUSZE_NAZWY.forEach(function (nazwa) {
    try {
      var it = folder.getFilesByName(nazwa), plik = null;
      while (it.hasNext()) {
        var f = it.next();
        if (f.getMimeType() === MimeType.GOOGLE_SHEETS && (!plik || f.getLastUpdated() > plik.getLastUpdated())) plik = f;
      }
      if (!plik) { log.push(nazwa + ': brak arkusza w folderze'); return; }
      var zm = String(plik.getLastUpdated().getTime()), klucz = 'arkusze_' + nazwa;
      var gz = nazwa + '.csv.gz', jest = folder.getFilesByName(gz).hasNext();
      if (wszystkie !== true && jest && P.getProperty(klucz) === zm) { log.push(nazwa + ': bez zmian'); return; }
      var csv = arkuszeCsv_(plik.getId()), zly = arkuszeDobry_(nazwa, csv);
      if (zly) { log.push(nazwa + ': ' + zly + ' — zostaje poprzedni ' + gz); return; }
      var stare = [], s = folder.getFilesByName(gz);
      while (s.hasNext()) stare.push(s.next());
      folder.createFile(Utilities.gzip(Utilities.newBlob(csv, 'text/csv', nazwa + '.csv')).setName(gz));
      stare.forEach(function (x) { x.setTrashed(true); });    // stary plik usuwany dopiero PO zapisaniu nowego
      P.setProperty(klucz, zm);
      var n = csv.split('\n').filter(function (l) { return l.trim() !== ''; }).length - 1;   // bez naglowka
      log.push(nazwa + ': zapisano ' + gz + ' (' + n + ' wierszy danych, arkusz z '
        + Utilities.formatDate(plik.getLastUpdated(), 'Europe/Warsaw', 'yyyy-MM-dd HH:mm') + ')');
    } catch (e) {
      log.push(nazwa + ': BŁĄD ' + e + ' — zostaje poprzedni plik');
    }
  });
  try {
    arkuszeArchiwum_(folder, log);
  } catch (e) {
    log.push('archiwum: BŁĄD ' + e);
  }
  var sl = folder.getFilesByName('arkusze_log.txt');
  while (sl.hasNext()) sl.next().setTrashed(true);
  folder.createFile('arkusze_log.txt', log.join('\n'), 'text/plain');
}

/** Nazwa archiwum do zapisania teraz albo '' — dzień i godzina w czasie polskim; archiwum od 12:00, raz dziennie. */
function arkuszeArchiwumNazwa_(dzien, godzina, jest) {
  if (+godzina < 12) return '';
  var nazwa = 'arkusze_' + dzien + '.zip';
  return jest(nazwa) ? '' : nazwa;
}

function arkuszeArchiwum_(folder, log) {
  var teraz = new Date();
  var nazwa = arkuszeArchiwumNazwa_(Utilities.formatDate(teraz, 'Europe/Warsaw', 'yyyy-MM-dd'),
    Utilities.formatDate(teraz, 'Europe/Warsaw', 'H'), function (n) { return folder.getFilesByName(n).hasNext(); });
  if (!nazwa) return;
  var blobs = [], man = ['plik,zmieniony,bajty'];
  ARKUSZE_NAZWY.forEach(function (n) {
    var it = folder.getFilesByName(n + '.csv.gz'), f = null;
    while (it.hasNext()) { var x = it.next(); if (!f || x.getLastUpdated() > f.getLastUpdated()) f = x; }
    if (!f) return;
    var b = f.getBlob().setName(n + '.csv.gz');
    blobs.push(b);
    man.push(n + '.csv.gz,' + f.getLastUpdated().toISOString() + ',' + b.getBytes().length);
  });
  if (!blobs.length) { log.push('archiwum: brak plikow .csv.gz — nie zapisano ' + nazwa); return; }
  blobs.push(Utilities.newBlob(man.join('\n') + '\n', 'text/csv', 'arkusze_manifest.csv'));
  var zip = Utilities.zip(blobs, nazwa);
  folder.createFile(zip);
  log.push('archiwum: zapisano ' + nazwa + ' (' + (blobs.length - 1) + ' arkuszy, ' + zip.getBytes().length + ' B)');
}
