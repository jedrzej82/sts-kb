/**
 * WYNIKI DLA BAZY STS — Google Apps Script (działa na serwerach Google, więc może pobierać ESPN, LiveScore i 365scores,
 * których nie widzi środowisko w chmurze Claude). Zapisuje CSV do folderu Drive „baza-wiedzy”.
 *
 * INSTALACJA (raz, ok. 3 minuty):
 *  1. Wejdź na https://script.google.com na koncie, które ma folder „baza-wiedzy” (TWOJE_KONTO@gmail.com),
 *     „Nowy projekt”, wklej CAŁY ten plik zamiast przykładowego kodu, zapisz (Ctrl+S), nazwij „wyniki STS”.
 *  2. Na górze wybierz funkcję „ustaw” → „Uruchom” → zezwól na dostęp (Drive + połączenia zewnętrzne).
 *     To tworzy wyzwalacz co godzinę. Historia dociąga się od najnowszych dni wstecz do 01.07.2025
 *     (kilka dni, w limitach Google); codziennie dochodzą wczoraj i przedwczoraj.
 *  ŹRÓDŁO: 365scores — WSZYSTKIE sporty i wszystkie rozgrywki (piłka ze wszystkich lig świata, tenis z Challengerami,
 *  koszykówka, hokej, ręczna, siatkówka, futbol amerykański, baseball, rugby, krykiet, e-sport, MMA, dart, snooker… — ile API poda).
 *  Surowe dane bez filtrów — filtrowanie (młodzież, kobiety, sparingi) robi dopiero baza (zewn.py).
 *  ESPN, LiveScore i Sofascore odrzucają serwery Google (403/404) — wyłączone.
 *  3. Postęp: plik „wyniki_status.txt” w folderze baza-wiedzy (co pobrano i ewentualne BŁĘDY źródeł).
 *
 * PLIKI WYJŚCIOWE (miesięczne, dopisywane, skompresowane gzip — mniejsze do pobrania):
 *  wyniki_espn_RRRR-MM.csv.gz        — piłka (ESPN): data,liga,gosp,gosc,gg,ga,rozne_g,rozne_a,faule_g,faule_a,strzaly_g,strzaly_a,celne_g,celne_a,zolte_g,zolte_a,czerwone_g,czerwone_a
 *  wyniki_ls_pilka_RRRR-MM.csv.gz    — piłka (LiveScore, wszystkie ligi świata, z wynikiem do przerwy)
 *  wyniki_ls_inne / wyniki_365_inne  — hokej, koszykówka, tenis (z Challenger/ITF), krykiet (LiveScore);
 *                                      siatkówka, piłka ręczna (365scores)
 *  (Sofascore blokuje Google — wyłączony, UZYJ_SOFA = false)
 *  wyniki_sofa_inne_RRRR-MM.csv.gz   — tenis (z Challenger/ITF), tenis stołowy, siatkówka, ręczna, hokej, koszykówka,
 *                                   futsal, dart, snooker, esport, rugby, baseball, unihokej, piłka wodna, krykiet, badminton…
 *     kolumny sofa: data,sport,kraj,turniej,runda,gosp,gosc,wg,wa,okresy_g,okresy_a,zwyciezca,nawierzchnia
 * Kursy NIE są pobierane.
 */
var FOLDER_ID = 'WKLEJ_ID_FOLDERU_BAZA_WIEDZY';
var START = '2025-07-01';
var MAX_FETCH_DZIEN = 17000;
var ESPN_LIGI = ['nor.1', 'swe.1', 'swe.2', 'den.1', 'fin.1', 'irl.1', 'sui.1', 'aut.1', 'rus.1', 'rou.1', 'pol.1', 'pol.2',
  'mex.1', 'usa.1', 'usa.usl.1', 'arg.1', 'bra.1', 'bra.2', 'jpn.1', 'jpn.2', 'chn.1', 'cze.1', 'cro.1', 'srb.1', 'ukr.1',
  'kor.1', 'ksa.1', 'aus.1', 'bul.1', 'hun.1', 'chi.1', 'col.1', 'ecu.1', 'uru.1', 'per.1', 'par.1', 'bol.1', 'ven.1',
  'rsa.1', 'can.1', 'bel.1', 'bel.2', 'ger.1', 'ger.2', 'ger.3', 'ned.1', 'ned.2', 'eng.1', 'eng.2', 'eng.3', 'eng.4',
  'esp.1', 'esp.2', 'ita.1', 'ita.2', 'fra.1', 'fra.2', 'por.1', 'tur.1', 'gre.1', 'sco.1', 'isr.1', 'cyp.1', 'svk.1',
  'svn.1', 'uefa.champions', 'uefa.europa', 'uefa.europa.conf'];
var SOFA_SPORTY = ['football', 'tennis', 'table-tennis', 'volleyball', 'handball', 'ice-hockey', 'basketball', 'futsal',
  'darts', 'snooker', 'esports', 'rugby', 'american-football', 'baseball', 'floorball', 'waterpolo', 'cricket',
  'badminton', 'beach-volley', 'aussie-rules'];
var UZYJ_SOFA = false;   // Sofascore blokuje serwery Google (404) — wyłączone
var LS_SPORTY = {soccer: 'football', hockey: 'ice-hockey', basketball: 'basketball', tennis: 'tennis', cricket: 'cricket'};
var S365_MAX = 40;   // 365scores: sprawdzane są WSZYSTKIE identyfikatory sportów 1..40 (nazwa sportu z odpowiedzi API)
var UZYJ_LS = false, UZYJ_ESPN = false;   // LiveScore i ESPN odrzucają serwery Google (403)
var UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36',
  'Accept': 'application/json, text/plain, */*', 'Accept-Language': 'en-US,en;q=0.9', 'Referer': 'https://www.sofascore.com/',
  'Origin': 'https://www.sofascore.com'};

function ustaw() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'pracuj') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('pracuj').timeBased().everyHours(1).create();
  pracuj();
}

function pracuj() {
  var t0 = Date.now(), P = PropertiesService.getScriptProperties();
  var dzis = Utilities.formatDate(new Date(), 'Europe/Warsaw', 'yyyy-MM-dd');
  if (P.getProperty('licznik_dzien') !== dzis) { P.setProperty('licznik_dzien', dzis); P.setProperty('licznik', '0'); }
  var bufor = {}, log = [];
  if (P.getProperty('wersja') !== '5') {   // wersja 5: 365scores — WSZYSTKIE sporty + sety tenisa; historia od nowa, od najnowszych dni wstecz
    P.deleteProperty('hist_sofa'); P.deleteProperty('hist_espn'); P.deleteProperty('biezace'); P.deleteProperty('ponow');
    P.deleteProperty('klucze365');
    P.setProperty('hist_wstecz', dodaj(dzis, -3)); P.setProperty('wersja', '5');
  }
  ponowBledy(bufor, log);
  // 1) raz dziennie: wczoraj i przedwczoraj (wyniki późnych meczów)
  if (P.getProperty('biezace') !== dzis) {
    [dodaj(dzis, -1), dodaj(dzis, -2)].forEach(function (d) { inneDzien(d, bufor, log); });
    P.setProperty('biezace', dzis);
  }
  // 2) historia: od najnowszych dni wstecz do START (limit ~3,5 min na uruchomienie — limity Google)
  var dh = P.getProperty('hist_wstecz') || dodaj(dzis, -3);
  while (Date.now() - t0 < 210000 && dh >= START && Number(P.getProperty('licznik')) < MAX_FETCH_DZIEN) {
    inneDzien(dh, bufor, log); dh = dodaj(dh, -1); P.setProperty('hist_wstecz', dh);
  }
  zapisz(bufor);
  var st = 'Aktualizacja ' + new Date().toISOString() + '\nhistoria gotowa od: ' + (dh < START ? START + ' (KOMPLET)' : dodaj(dh, 1)) +
    ' do wczoraj\npobrań dziś: ' + P.getProperty('licznik') + '\ndo ponowienia: ' + JSON.parse(P.getProperty('ponow') || '[]').length +
    '\nsporty w API: ' + P.getProperty('sporty365') + '\n' + log.slice(-40).join('\n') + '\n\nPOLA API (diagnostyka):\n' +
    Object.keys(JSON.parse(P.getProperty('klucze365') || '{}')).map(function (k) { return k + ': ' + JSON.parse(P.getProperty('klucze365'))[k]; }).join('\n');
  plik('wyniki_status.txt', st, false);
}

function pobierz(urls) {
  var P = PropertiesService.getScriptProperties();
  P.setProperty('licznik', String(Number(P.getProperty('licznik') || 0) + urls.length));
  var req = urls.map(function (u) { return {url: u, muteHttpExceptions: true, headers: UA}; });
  var out = [];
  for (var i = 0; i < req.length; i += 25) {
    var r = UrlFetchApp.fetchAll(req.slice(i, i + 25));
    r.forEach(function (x) { out.push(x); });
  }
  return out;
}

function sofaDzien(d, bufor, log) {
  var urls = SOFA_SPORTY.map(function (s) { return 'https://api.sofascore.com/api/v1/sport/' + s + '/scheduled-events/' + d; });
  var res = pobierz(urls), zle = [];
  res.forEach(function (r, i) {
    var sport = SOFA_SPORTY[i], code = r.getResponseCode();
    if (code !== 200) {  // zapasowy host
      var r2 = UrlFetchApp.fetch('https://www.sofascore.com/api/v1/sport/' + sport + '/scheduled-events/' + d, {muteHttpExceptions: true, headers: UA});
      if (r2.getResponseCode() !== 200) { zle.push(sport + ':' + code); return; }
      r = r2;
    }
    var j; try { j = JSON.parse(r.getContentText()); } catch (e) { zle.push(sport + ':json'); return; }
    (j.events || []).forEach(function (e) {
      if (!e.status || e.status.type !== 'finished' || !e.homeScore || e.homeScore.current === undefined) return;
      var dd = Utilities.formatDate(new Date(e.startTimestamp * 1000), 'Europe/Warsaw', 'yyyy-MM-dd');
      if (dd !== d) return;
      var per = function (s) { var a = []; for (var k = 1; k <= 7; k++) if (s['period' + k] !== undefined) a.push(s['period' + k]); return a.join(';'); };
      var t = e.tournament || {}, ut = t.uniqueTournament || {}, cat = t.category || {};
      var row = [dd, sport, cat.name || '', ut.name || t.name || '', (e.roundInfo && (e.roundInfo.name || e.roundInfo.round)) || '',
        (e.homeTeam || {}).name, (e.awayTeam || {}).name, e.homeScore.current, (e.awayScore || {}).current,
        per(e.homeScore), per(e.awayScore || {}), e.winnerCode || '', e.groundType || ''];
      if (sport === 'football' && /\b(U1\d|U2\d|Youth|Reserve|Amateur|Friendl)/i.test((ut.name || t.name || '') + ' ' + (cat.name || ''))) return;
      var klucz = 'wyniki_sofa_' + (sport === 'football' ? 'pilka' : 'inne') + '_' + dd.substr(0, 7) + '.csv.gz';
      (bufor[klucz] = bufor[klucz] || []).push(csv(row));
    });
  });
  log.push('sofa ' + d + (zle.length ? ' BŁĘDY: ' + zle.join(',') : ' ok'));
}

function inneDzien(d, bufor, log) {
  if (UZYJ_SOFA) sofaDzien(d, bufor, log);
  if (UZYJ_LS) lsDzien(d, bufor, log);
  s365Dzien(d, bufor, log);
  if (UZYJ_ESPN) espnZakres(d, d, bufor, log);
}

function dopisz(bufor, zrodlo, sport, dd, row) {
  var klucz = 'wyniki_' + zrodlo + '_' + (sport === 'football' ? 'pilka' : 'inne') + '_' + dd.substr(0, 7) + '.csv.gz';
  (bufor[klucz] = bufor[klucz] || []).push(csv(row));
}

/** LiveScore (publiczne API aplikacji): piłka, hokej, koszykówka, tenis (z Challenger/ITF), krykiet. */
function lsDzien(d, bufor, log) {
  var kl = Object.keys(LS_SPORTY), zle = [], n = 0;
  var urls = kl.map(function (s) { return 'https://prod-public-api.livescore.com/v1/api/app/date/' + s + '/' + d.replace(/-/g, '') + '/0?MD=1'; });
  pobierz(urls).forEach(function (r, i) {
    var sport = LS_SPORTY[kl[i]];
    if (r.getResponseCode() !== 200) { zle.push(kl[i] + ':' + r.getResponseCode()); return; }
    var j; try { j = JSON.parse(r.getContentText()); } catch (e) { zle.push(kl[i] + ':json'); return; }
    (j.Stages || []).forEach(function (st) {
      (st.Events || []).forEach(function (e) {
        var eps = String(e.Eps || '');
        if (!(e.Esid === 6 || /^(FT|AET|AP|AOT|AP|Ended|FIN|Fin|Ret)/.test(eps))) return;
        if (e.Tr1 === undefined || e.Tr2 === undefined || e.Tr1 === '' || e.Tr2 === '') return;
        var esd = String(e.Esd || ''), dd = esd.length >= 8 ? esd.substr(0, 4) + '-' + esd.substr(4, 2) + '-' + esd.substr(6, 2) : d;
        if (dd !== d) return;
        var okr = function (p) {   // wyniki okresów/setów: klucze typu Tr1S1, Tr1Q1, Tr1P1… (poza Tr1, Tr1OR, Trh1)
          var ks = Object.keys(e).filter(function (k) { return k.indexOf(p) === 0 && /\d$/.test(k) && k !== p && k.substr(0, 3) !== 'Trh' && !/OR$/.test(k); });
          ks.sort(); return ks.map(function (k) { return e[k]; }).join(';');
        };
        var og = e.Trh1 !== undefined && sport === 'football' ? e.Trh1 + ';' : okr('Tr1');
        var oa = e.Trh2 !== undefined && sport === 'football' ? e.Trh2 + ';' : okr('Tr2');
        var w = Number(e.Tr1) > Number(e.Tr2) ? 1 : Number(e.Tr1) < Number(e.Tr2) ? 2 : 3;
        var turniej = st.CompN || st.Snm || '';
        if (sport === 'football' && /\b(U1\d|U2\d|Youth|Reserve|Amateur|Friendl)/i.test(turniej + ' ' + (st.Snm || '') + ' ' + (st.Cnm || ''))) return;
        dopisz(bufor, 'ls', sport, dd, [dd, sport, st.Cnm || '', turniej, (st.Snm && st.Snm !== turniej) ? st.Snm : '', ((e.T1 || [])[0] || {}).Nm,
          ((e.T2 || [])[0] || {}).Nm, e.Tr1, e.Tr2, og, oa, w, '']);
        n++;
      });
    });
  });
  log.push('livescore ' + d + ': ' + n + ' meczów' + (zle.length ? ' BŁĘDY: ' + zle.join(',') : ''));
}

/** 365scores: WSZYSTKIE sporty (id 1..S365_MAX), wszystkie rozgrywki, wynik końcowy + okresy/sety gdy dostępne.
 *  Nieudane pobrania (np. 504) trafiają do kolejki „ponow” i są powtarzane przy następnym uruchomieniu. */
function s365Dzien(d, bufor, log, tylko) {
  var ids = tylko || [], dm = d.substr(8, 2) + '/' + d.substr(5, 2) + '/' + d.substr(0, 4), zle = [], ile = {}, n = 0;
  if (!tylko) for (var i = 1; i <= S365_MAX; i++) ids.push(i);
  var url = function (id) {
    return 'https://webws.365scores.com/web/games/allscores/?appTypeId=5&langId=1&timezoneName=UTC&userCountryId=1&sports=' + id +
      '&startDate=' + dm + '&endDate=' + dm + '&showOdds=false&onlyMajorGames=false&withTop=false';
  };
  var P = PropertiesService.getScriptProperties(), klucze = JSON.parse(P.getProperty('klucze365') || '{}');
  pobierz(ids.map(url)).forEach(function (r, i) {
    var id = ids[i], strony = [];
    if (r.getResponseCode() !== 200) { zle.push(id + ':' + r.getResponseCode()); return; }
    var j; try { j = JSON.parse(r.getContentText()); } catch (e) { zle.push(id + ':json'); return; }
    strony.push(j);
    for (var p = 0; p < 30 && j.paging && j.paging.nextPage; p++) {   // stronicowanie, jeśli API dzieli dzień
      var r2 = pobierz(['https://webws.365scores.com' + j.paging.nextPage])[0];
      if (r2.getResponseCode() !== 200) { zle.push(id + ':strona' + r2.getResponseCode()); break; }
      try { j = JSON.parse(r2.getContentText()); } catch (e) { zle.push(id + ':strona-json'); break; }
      strony.push(j);
    }
    var nazwa = null, kraje = {}, komp = {};
    strony.forEach(function (x) {
      (x.sports || []).forEach(function (s) { if (s.id === id) nazwa = s.nameForURL || s.name; });
      (x.countries || []).forEach(function (c) { kraje[c.id] = c.name; });
      (x.competitions || []).forEach(function (c) { komp[c.id] = c; });
    });
    if (nazwa) { var ods = JSON.parse(P.getProperty('sporty365') || '{}'); if (!ods[id]) { ods[id] = nazwa; P.setProperty('sporty365', JSON.stringify(ods)); } }
    var sport = id === 1 ? 'football' : String(nazwa || ('s' + id)).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    strony.forEach(function (x) {
      (x.games || []).forEach(function (g) {
        if (g.statusGroup !== 4) return;
        var h = g.homeCompetitor || {}, a = g.awayCompetitor || {};
        var bezWyniku = h.score === undefined || a.score === undefined || h.score < 0 || a.score < 0;
        if (bezWyniku && !h.isWinner && !a.isWinner) return;   // MMA/boks/wyścigi itp.: bez punktów, ale ze zwycięzcą — zostaje
        var dd = String(g.startTime || '').substr(0, 10); if (dd !== d) return;
        if (!klucze[sport]) {   // diagnostyka: jakie pola ma mecz danego sportu (raz na sport)
          klucze[sport] = Object.keys(g).join(' ') + ' | comp: ' + Object.keys(h).join(' ');
        }
        var k = komp[g.competitionId] || {};
        var okr = function (c, strona) {   // wyniki okresów/setów: tenis ma je w g.stages (gemy w setach)
          var st = (g.stages || []).filter(function (x) { return /set|period|quarter|half|inning|kwarta|tercja/i.test(x.name || x.shortName || '') || x.homeCompetitorScore !== undefined; });
          if (st.length) {
            if (!klucze[sport + '_stages']) klucze[sport + '_stages'] = JSON.stringify(g.stages).substr(0, 400);
            return st.map(function (x) {
              var v = strona === 'h' ? (x.homeCompetitorScore !== undefined ? x.homeCompetitorScore : x.homeScore) : (x.awayCompetitorScore !== undefined ? x.awayCompetitorScore : x.awayScore);
              return (v === undefined || v === null || v < 0) ? '' : v;
            }).join(';');
          }
          var s = c.scores || c.periodScores || g.scores;
          if (!s || !s.length) return '';
          return s.map(function (v) { return typeof v === 'object' ? (v.score !== undefined ? v.score : '') : v; }).join(';');
        };
        var w = h.isWinner ? 1 : a.isWinner ? 2 : (h.score > a.score ? 1 : h.score < a.score ? 2 : 3);
        var nawierzchnia = g.groundTypeName || g.courtType || g.surface || k.surface || k.groundType || '';
        dopisz(bufor, '365', sport, dd, [dd, sport, kraje[k.countryId] || '', k.name || g.competitionDisplayName || '',
          g.roundName || g.stageName || '', h.name, a.name, bezWyniku ? '' : h.score, bezWyniku ? '' : a.score, okr(h, 'h'), okr(a, 'a'), w, nawierzchnia]);
        n++; ile[sport] = (ile[sport] || 0) + 1;
      });
    });
  });
  P.setProperty('klucze365', JSON.stringify(klucze));
  if (zle.length) {   // do ponowienia
    var q = JSON.parse(P.getProperty('ponow') || '[]');
    zle.forEach(function (z) { var id = Number(z.split(':')[0]); if (id) q.push([d, id]); });
    P.setProperty('ponow', JSON.stringify(q.slice(-500)));
  }
  log.push('365scores ' + d + ': ' + n + ' meczów (' + Object.keys(ile).map(function (s) { return s + ' ' + ile[s]; }).join(', ') + ')' +
    (zle.length ? ' BŁĘDY (ponowię): ' + zle.join(',') : ''));
}

function ponowBledy(bufor, log) {
  var P = PropertiesService.getScriptProperties(), q = JSON.parse(P.getProperty('ponow') || '[]');
  if (!q.length) return;
  P.setProperty('ponow', '[]');
  var wg = {};
  q.forEach(function (x) { (wg[x[0]] = wg[x[0]] || []).push(x[1]); });
  Object.keys(wg).forEach(function (d) { s365Dzien(d, bufor, log, wg[d]); });
}

function espnZakres(d1, d2, bufor, log) {
  var zakres = d1.replace(/-/g, '') + (d2 !== d1 ? '-' + d2.replace(/-/g, '') : '');
  var urls = ESPN_LIGI.map(function (l) { return 'https://site.api.espn.com/apis/site/v2/sports/soccer/' + l + '/scoreboard?dates=' + zakres + (d2 !== d1 ? '&limit=500' : ''); });
  var res = pobierz(urls), zle = [], ligi = ESPN_LIGI.slice();
  // ESPN czasem nie przyjmuje zakresu dat (400) — wtedy dzień po dniu dla tej ligi
  if (d2 !== d1) {
    var dni = []; for (var d = d1; d <= d2; d = dodaj(d, 1)) dni.push(d);
    var dodatkowe = [], dl = [];
    res.forEach(function (r, i) {
      if (r.getResponseCode() === 400) dni.forEach(function (x) {
        dodatkowe.push('https://site.api.espn.com/apis/site/v2/sports/soccer/' + ESPN_LIGI[i] + '/scoreboard?dates=' + x.replace(/-/g, ''));
        dl.push(ESPN_LIGI[i]);
      });
    });
    if (dodatkowe.length) { res = res.concat(pobierz(dodatkowe)); ligi = ligi.concat(dl); }
  }
  res.forEach(function (r, i) {
    var liga = ligi[i];
    if (r.getResponseCode() !== 200) { if (!(d2 !== d1 && r.getResponseCode() === 400)) zle.push(liga + ':' + r.getResponseCode()); return; }
    var j; try { j = JSON.parse(r.getContentText()); } catch (e) { zle.push(liga + ':json'); return; }
    (j.events || []).forEach(function (e) {
      var c = (e.competitions || [])[0]; if (!c || !e.status || !e.status.type || !e.status.type.completed) return;
      var h = null, a = null;
      (c.competitors || []).forEach(function (x) { if (x.homeAway === 'home') h = x; else a = x; });
      if (!h || !a) return;
      var st = function (x, n) { var v = ''; (x.statistics || []).forEach(function (s) { if (s.name === n) v = s.displayValue; }); return v; };
      var dd = Utilities.formatDate(new Date(e.date), 'Europe/Warsaw', 'yyyy-MM-dd');
      var row = [dd, liga, h.team.displayName, a.team.displayName, h.score, a.score,
        st(h, 'wonCorners'), st(a, 'wonCorners'), st(h, 'foulsCommitted'), st(a, 'foulsCommitted'), st(h, 'totalShots'), st(a, 'totalShots'),
        st(h, 'shotsOnTarget'), st(a, 'shotsOnTarget'), st(h, 'yellowCards'), st(a, 'yellowCards'), st(h, 'redCards'), st(a, 'redCards')];
      var klucz = 'wyniki_espn_' + dd.substr(0, 7) + '.csv.gz';
      (bufor[klucz] = bufor[klucz] || []).push(csv(row));
    });
  });
  log.push('espn ' + zakres + (zle.length ? ' błędy: ' + zle.slice(0, 8).join(',') + (zle.length > 8 ? '…(' + zle.length + ')' : '') : ' ok'));
}

var NAGLOWKI = {
  espn: 'data,liga,gosp,gosc,gg,ga,rozne_g,rozne_a,faule_g,faule_a,strzaly_g,strzaly_a,celne_g,celne_a,zolte_g,zolte_a,czerwone_g,czerwone_a',
  sofa: 'data,sport,kraj,turniej,runda,gosp,gosc,wg,wa,okresy_g,okresy_a,zwyciezca,nawierzchnia'
};

function zapisz(bufor) {
  Object.keys(bufor).forEach(function (nazwa) {
    var nag = nazwa.indexOf('espn') >= 0 ? NAGLOWKI.espn : NAGLOWKI.sofa;
    plik(nazwa, bufor[nazwa].join('\n'), true, nag);
  });
}

function plik(nazwa, tresc, dopisz, naglowek) {
  var f = DriveApp.getFolderById(FOLDER_ID), it = f.getFilesByName(nazwa), stara = null, pop = '';
  if (it.hasNext()) {
    stara = it.next();
    if (dopisz) {
      var b = stara.getBlob();
      pop = /\.gz$/.test(nazwa) ? Utilities.ungzip(b.setContentType('application/x-gzip')).getDataAsString() : b.getDataAsString();
    }
  }
  var calosc = pop ? pop + '\n' + tresc : (dopisz && naglowek ? naglowek + '\n' : '') + tresc;
  if (/\.gz$/.test(nazwa)) {
    var gz = Utilities.gzip(Utilities.newBlob(calosc, 'text/csv', nazwa.replace(/\.gz$/, ''))).setName(nazwa);
    f.createFile(gz);
    if (stara) stara.setTrashed(true);
  } else if (stara) {
    stara.setContent(calosc);
  } else {
    f.createFile(nazwa, calosc, MimeType.PLAIN_TEXT);
  }
}

function csv(a) {
  return a.map(function (v) {
    v = (v === undefined || v === null) ? '' : String(v);
    return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
  }).join(',');
}

function dodaj(d, n) { var x = new Date(d + 'T12:00:00Z'); x.setUTCDate(x.getUTCDate() + n); return x.toISOString().substr(0, 10); }
function minS(a, b) { return a < b ? a : b; }

/** Ręcznie: zacznij historię od nowa (np. po zmianie listy lig). */
function resetHistorii() { var P = PropertiesService.getScriptProperties(); P.deleteProperty('wersja'); }
