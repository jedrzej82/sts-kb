/**
 * PACZKA STS — samodzielny dodatek do projektu Apps Script „wyniki STS” (30.09.2026).
 * Co 15 minut pakuje WSZYSTKIE dane, ktore przebieg pobiera z folderu „baza-wiedzy”, w JEDEN plik paczka.zip:
 *   zewn/wyniki_*_RRRR-MM.csv.gz (biezacy miesiac; w dniach 1-3 takze poprzedni), zewn/terminarz_fs.csv.gz, zewn/terminarz_365.csv.gz,
 *   statystyki_*.csv.gz i absencje.csv.gz (z arkusze.gs), dzienniki.zip (z dzienniki.gs), zaklady_faktyczne.csv (07.10.2026).
 * PO CO: kazde pobranie przez konektor Dysku kosztuje przebieg ok. 1,5 minuty; 30.09 18:00 poszlo na to ponad 100 min
 * i przebieg nie zdazyl z kuponami. Jedna paczka = jedno pobranie. przebieg.py sam ja rozpakowuje i sprawdza
 * (manifest z rozmiarami, gzip, zip) — przy bledzie przebieg pobiera pliki pojedynczo, jak dotad.
 *
 * INSTALACJA (nie zmienia istniejacego kodu):
 *  1. W projekcie „wyniki STS”: „+” obok „Pliki” → „Skrypt” → nazwij „paczka” → wklej CALY ten plik → Ctrl+S.
 *  2. U gory wybierz funkcje „paczkaUstaw” → „Uruchom” → zezwol na dostep. Tworzy wyzwalacz co 15 minut
 *     i od razu zapisuje paczka.zip. Wylaczenie: „paczkaUsun”.
 *  Log ostatniego przebiegu: paczka_log.txt w tym samym folderze.
 *
 * Paczka jest zapisywana tylko wtedy, gdy zmienil sie ktorys z plikow (id + data zmiany). Nowa paczka powstaje
 * PRZED usunieciem starej. Brak ktoregos pliku nie blokuje paczki — przebieg.py zglosi brak jak dotad.
 */
var PACZKA_FOLDER_ID = 'WKLEJ_ID_FOLDERU_BAZA_WIEDZY';   // ID folderu baza-wiedzy (z adresu folderu na Dysku)

function paczkaUstaw() {
  paczkaUsun();
  ScriptApp.newTrigger('paczkaPracuj').timeBased().everyMinutes(15).create();
  paczkaPracuj(true);
}

function paczkaUsun() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'paczkaPracuj') ScriptApp.deleteTrigger(t);
  });
}

/** Sciezka pliku w paczce (jak w kb/ przebiegu) albo '' — plik nie wchodzi do paczki. */
function paczkaSciezka_(nazwa, miesiace) {
  var m = /^wyniki_[a-z0-9]+_[a-z]+_(\d{4}-\d{2})\.csv\.gz$/.exec(nazwa);
  if (m) return miesiace.indexOf(m[1]) >= 0 ? 'zewn/' + nazwa : '';
  if (nazwa === 'terminarz_fs.csv.gz' || nazwa === 'terminarz_365.csv.gz') return 'zewn/' + nazwa;
  if (/^statystyki_[a-z_]+\.csv\.gz$/.test(nazwa) || nazwa === 'absencje.csv.gz' || nazwa === 'dzienniki.zip') return nazwa;
  // 07.10.2026: faktyczne zaklady (tylko aktualny plik; „zaklady_faktyczne POPRZEDNIA WERSJA …” nie wchodzi)
  if (nazwa === 'zaklady_faktyczne.csv') return nazwa;
  return '';
}

function paczkaMiesiace_() {
  // miesiac liczony w czasie POLSKIM, poprzedni — arytmetycznie z tego samego napisu (bez strefy serwera).
  // Poprzedni miesiac tylko w dniach 1-3: wtedy kopie z repo sa nieaktualne; pozniej przebieg go nie potrzebuje,
  // a paczka rosnie o ok. 1 MB.
  var teraz = new Date(), biez = Utilities.formatDate(teraz, 'Europe/Warsaw', 'yyyy-MM');
  if (+Utilities.formatDate(teraz, 'Europe/Warsaw', 'd') > 3) return [biez];
  var r = +biez.substring(0, 4), m = +biez.substring(5, 7) - 1;
  if (m === 0) { m = 12; r -= 1; }
  return [biez, r + '-' + ('0' + m).slice(-2)];
}

function paczkaPracuj(wszystkie) {
  var folder = DriveApp.getFolderById(PACZKA_FOLDER_ID), P = PropertiesService.getScriptProperties();
  var log = ['paczkaPracuj ' + new Date().toISOString()];
  try {
    var miesiace = paczkaMiesiace_(), wybrane = {}, it = folder.getFiles();
    while (it.hasNext()) {
      var f = it.next(), sc = paczkaSciezka_(f.getName(), miesiace);
      if (!sc) continue;
      if (!wybrane[sc] || f.getLastUpdated() > wybrane[sc].getLastUpdated()) wybrane[sc] = f;   // dubel nazwy: najnowszy
    }
    var sciezki = Object.keys(wybrane).sort();
    var podpis = sciezki.map(function (s) { return s + '@' + wybrane[s].getId() + '@' + wybrane[s].getLastUpdated().getTime(); }).join(',');
    var jest = folder.getFilesByName('paczka.zip').hasNext();
    if (wszystkie !== true && jest && P.getProperty('paczka_podpis') === podpis) {
      log.push('bez zmian (' + sciezki.length + ' plikow)');
    } else if (!sciezki.length) {
      log.push('brak plikow do paczki — zostaje poprzednia paczka.zip');
    } else {
      var blobs = [], man = ['plik,zmieniony,bajty'];
      sciezki.forEach(function (s) {
        var b = wybrane[s].getBlob().setName(s);
        blobs.push(b);
        man.push(s + ',' + wybrane[s].getLastUpdated().toISOString() + ',' + b.getBytes().length);
      });
      blobs.push(Utilities.newBlob(man.join('\n') + '\n', 'text/csv', 'paczka_manifest.csv'));
      var zip = Utilities.zip(blobs, 'paczka.zip');
      var stare = [], s = folder.getFilesByName('paczka.zip');
      while (s.hasNext()) stare.push(s.next());
      folder.createFile(zip);
      stare.forEach(function (x) { x.setTrashed(true); });   // stara paczka usuwana dopiero PO zapisaniu nowej
      P.setProperty('paczka_podpis', podpis);
      log.push('zapisano paczka.zip: ' + sciezki.length + ' plikow, ' + zip.getBytes().length + ' B');
      log.push(sciezki.join('\n'));
    }
  } catch (e) {
    log.push('BLAD ' + e + ' — zostaje poprzednia paczka.zip');
  }
  var sl = folder.getFilesByName('paczka_log.txt');
  while (sl.hasNext()) sl.next().setTrashed(true);
  folder.createFile('paczka_log.txt', log.join('\n'), 'text/plain');
}
