/**
 * WYSYLKA WYNIKOW 365scores NA GITHUB — dodatek do projektu "wyniki STS".
 * Cel: zeby analiza nie musiala pobierac kilkunastu plikow z Dysku przez konektor.
 * Po wypchnieciu wystarczy `git clone --depth 1 .../sts-kb.git kb` i pliki sa juz w kb/zewn/.
 *
 * INSTALACJA (raz, ok. 2 minuty):
 *  1. Wklej ten plik do projektu Apps Script "wyniki STS" jako nowy plik (Plik -> Nowy -> Skrypt).
 *  2. Wygeneruj token na github.com/settings/tokens -> Generate new token (classic) -> uprawnienie "repo".
 *  3. W Apps Script: Ustawienia projektu -> Wlasciwosci skryptu -> Dodaj wlasciwosc
 *       nazwa:    GITHUB_TOKEN
 *       wartosc:  <wklejony token>
 *     NIGDY nie wpisuj tokenu w kod — kod trafia do publicznego repozytorium, wlasciwosci nie.
 *  4. Uruchom raz funkcje "ustawPushGitHub" — tworzy wyzwalacz co godzine, 10 minut po pelnej.
 *
 * Wysyla tylko pliki z biezacego i dwoch poprzednich miesiecy. Starsze zostaja na Dysku.
 */

var GH_OWNER = 'jedrzej82';
var GH_REPO  = 'sts-kb';
var GH_DIR   = 'zewn';
var GH_RODZINY = ['wyniki_365_pilka_', 'wyniki_365_inne_', 'wyniki_fs_inne_', 'wyniki_lol_inne_'];

function ustawPushGitHub() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'pushGitHub') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('pushGitHub').timeBased().everyHours(3).nearMinute(10).create();
  Logger.log('Wyzwalacz ustawiony. Uruchamiam pierwszy push...');
  pushGitHub();
}

function _ghMiesiace_() {
  var out = [], d = new Date();
  for (var i = 0; i < 3; i++) {
    out.push(Utilities.formatDate(d, 'UTC', 'yyyy-MM'));
    d.setMonth(d.getMonth() - 1);
  }
  return out;
}

function _ghZadanie_(nazwa) {
  var mm = _ghMiesiace_();
  for (var i = 0; i < GH_RODZINY.length; i++) {
    for (var j = 0; j < mm.length; j++) {
      if (nazwa === GH_RODZINY[i] + mm[j] + '.csv.gz') return true;
    }
  }
  return false;
}

function _ghBlobSha_(bajty) {
  // git liczy sha1 z naglowka "blob <dlugosc>\0" + tresc; pozwala wykryc brak zmian BEZ commita
  var naglowek = Utilities.newBlob('blob ' + bajty.length + '\u0000').getBytes();
  var pelne = naglowek.concat(bajty);
  var sur = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_1, pelne);
  return sur.map(function (b) { return ('0' + (b & 0xFF).toString(16)).slice(-2); }).join('');
}


function _ghSha_(sciezka, token) {
  var url = 'https://api.github.com/repos/' + GH_OWNER + '/' + GH_REPO + '/contents/' + sciezka;
  var r = UrlFetchApp.fetch(url, {
    method: 'get', muteHttpExceptions: true,
    headers: { Authorization: 'token ' + token, Accept: 'application/vnd.github+json', 'User-Agent': GH_OWNER }
  });
  if (r.getResponseCode() !== 200) return null;
  return JSON.parse(r.getContentText()).sha;
}

function pushGitHub() {
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) { Logger.log('BLAD: brak wlasciwosci skryptu GITHUB_TOKEN'); return; }

  var folder = DriveApp.getFolderById(FOLDER_ID);   // FOLDER_ID z wyniki_sts.gs
  var pliki = folder.getFiles(), wyslane = 0, pominiete = 0, bledy = 0;

  while (pliki.hasNext()) {
    var f = pliki.next(), nazwa = f.getName();
    if (!_ghZadanie_(nazwa)) { pominiete++; continue; }

    var sciezka = GH_DIR + '/' + nazwa;
    var bajty = f.getBlob().getBytes();
    var sha = _ghSha_(sciezka, token);
    if (sha && sha === _ghBlobSha_(bajty)) { pominiete++; continue; }   // bez zmian -> bez commita
    var tresc = Utilities.base64Encode(bajty);
    var body = { message: 'wyniki 365scores: ' + nazwa + ' (' + new Date().toISOString() + ')',
                 content: tresc, branch: 'main' };
    if (sha) body.sha = sha;

    var r = UrlFetchApp.fetch('https://api.github.com/repos/' + GH_OWNER + '/' + GH_REPO + '/contents/' + sciezka, {
      method: 'put', contentType: 'application/json', payload: JSON.stringify(body), muteHttpExceptions: true,
      headers: { Authorization: 'token ' + token, Accept: 'application/vnd.github+json', 'User-Agent': GH_OWNER }
    });
    var kod = r.getResponseCode();
    if (kod === 200 || kod === 201) { wyslane++; }
    else { bledy++; Logger.log('BLAD ' + kod + ' przy ' + nazwa + ': ' + r.getContentText().slice(0, 200)); }
    Utilities.sleep(1500);   // nie walimy w limit GitHuba
  }
  Logger.log('push na GitHub: wyslane ' + wyslane + ', pominiete ' + pominiete + ', bledy ' + bledy);
}
