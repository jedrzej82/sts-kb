/**
 * DZIENNIKI STS — samodzielny dodatek do projektu Apps Script „wyniki STS” (30.09.2026).
 * Co 30 minut pakuje WSZYSTKIE pliki dziennikow z folderu „baza-wiedzy” (nazwa zaczyna sie od typy_log,
 * sporty_typy albo ako_log) w JEDEN plik dzienniki.zip w tym samym folderze.
 * PO CO: przebieg 30.09 18:00 pobieral 62 takie pliki po jednym przez konektor Dysku — 88 minut z budzetu
 * (dane: 436 KB). Przez to nie zdazyl z kuponami, REJESTREM i archiwum. Jeden zip = jedno pobranie.
 * W zipie jest dzienniki_manifest.csv (plik, utworzony, id): przebieg.py ustawia czas pliku = czas utworzenia
 * na Dysku, bo dzienniki.py scal przy powtorzonym wierszu wybiera POZNIEJSZY plik.
 *
 * INSTALACJA (nie zmienia istniejacego kodu):
 *  1. W projekcie „wyniki STS”: „+” obok „Pliki” → „Skrypt” → nazwij „dzienniki” → wklej CALY ten plik → Ctrl+S.
 *  2. U gory wybierz funkcje „dziennikiUstaw” → „Uruchom” → zezwol na dostep. Tworzy wyzwalacz co 30 minut
 *     i od razu zapisuje dzienniki.zip. Wylaczenie: „dziennikiUsun”.
 *  Log ostatniego przebiegu: dzienniki_log.txt w tym samym folderze.
 *
 * Zip jest zapisywany tylko wtedy, gdy zmienil sie zestaw plikow dziennikow albo ktorys z nich (id + data zmiany),
 * wiec wyzwalacz co 30 minut nie zuzywa limitow. Nowy zip powstaje PRZED usunieciem starego.
 */
var DZIENNIKI_FOLDER_ID = 'WKLEJ_ID_FOLDERU_BAZA_WIEDZY';   // ID folderu baza-wiedzy (z adresu folderu na Dysku)
var DZIENNIKI_RODZAJE = ['typy_log', 'sporty_typy', 'ako_log'];

function dziennikiUstaw() {
  dziennikiUsun();
  ScriptApp.newTrigger('dziennikiPracuj').timeBased().everyMinutes(30).create();
  dziennikiPracuj(true);
}

function dziennikiUsun() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'dziennikiPracuj') ScriptApp.deleteTrigger(t);
  });
}

/** Rodzaj dziennika z nazwy pliku (jak dzienniki.py: male litery, spacje -> _) albo ''. */
function dziennikiRodzaj_(nazwa) {
  var n = String(nazwa).toLowerCase().replace(/ /g, '_');
  for (var i = 0; i < DZIENNIKI_RODZAJE.length; i++) if (n.indexOf(DZIENNIKI_RODZAJE[i]) === 0) return DZIENNIKI_RODZAJE[i];
  return '';
}

/** Nazwa pliku w zipie: zaczyna sie od nazwy z Dysku (dzienniki.py rozpoznaje rodzaj po poczatku), bez znakow
 *  niedozwolonych, z numerem, zeby dwa pliki o tej samej nazwie na Dysku nie nadpisaly sie w zipie. */
function dziennikiNazwa_(nazwa, nr) {
  var n = String(nazwa).replace(/[\\\/:*?"<>|\r\n]+/g, '_').replace(/\s+/g, ' ').trim();
  if (n.length > 150) n = n.substring(0, 150);
  return n + ' __' + ('000' + nr).slice(-4) + '.csv';
}

function dziennikiPracuj(wszystkie) {
  var folder = DriveApp.getFolderById(DZIENNIKI_FOLDER_ID), P = PropertiesService.getScriptProperties();
  var log = ['dziennikiPracuj ' + new Date().toISOString()];
  try {
    var pliki = [], it = folder.getFiles();
    while (it.hasNext()) {
      var f = it.next();
      if (!dziennikiRodzaj_(f.getName())) continue;
      var typ = f.getMimeType();
      if (typ !== 'text/csv' && typ !== 'text/plain') { log.push('pominiety (typ ' + typ + '): ' + f.getName()); continue; }
      pliki.push(f);
    }
    pliki.sort(function (a, b) { return a.getDateCreated() - b.getDateCreated(); });
    var podpis = pliki.map(function (f) { return f.getId() + '@' + f.getLastUpdated().getTime(); }).join(',');
    var jest = folder.getFilesByName('dzienniki.zip').hasNext();
    if (wszystkie !== true && jest && P.getProperty('dzienniki_podpis') === podpis) {
      log.push('bez zmian (' + pliki.length + ' plikow)');
    } else if (!pliki.length) {
      log.push('brak plikow dziennikow w folderze — zostaje poprzedni dzienniki.zip');
    } else {
      var blobs = [], man = ['plik,utworzony,id'];
      pliki.forEach(function (f, i) {
        var nazwa = dziennikiNazwa_(f.getName(), i + 1);
        blobs.push(f.getBlob().setName(nazwa));
        man.push('"' + nazwa.replace(/"/g, '""') + '",' + f.getDateCreated().toISOString() + ',' + f.getId());
      });
      blobs.push(Utilities.newBlob(man.join('\n') + '\n', 'text/csv', 'dzienniki_manifest.csv'));
      var zip = Utilities.zip(blobs, 'dzienniki.zip');
      var stare = [], s = folder.getFilesByName('dzienniki.zip');
      while (s.hasNext()) stare.push(s.next());
      folder.createFile(zip);
      stare.forEach(function (x) { x.setTrashed(true); });   // stary zip usuwany dopiero PO zapisaniu nowego
      P.setProperty('dzienniki_podpis', podpis);
      log.push('zapisano dzienniki.zip: ' + pliki.length + ' plikow, ' + zip.getBytes().length + ' B');
    }
  } catch (e) {
    log.push('BLAD ' + e + ' — zostaje poprzedni dzienniki.zip');
  }
  var sl = folder.getFilesByName('dzienniki_log.txt');
  while (sl.hasNext()) sl.next().setTrashed(true);
  folder.createFile('dzienniki_log.txt', log.join('\n'), 'text/plain');
}
