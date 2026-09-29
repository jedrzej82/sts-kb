/**
 * LIGA PRO (tenis stołowy, Czechy) — diagnoza źródeł (29.09.2026). Samodzielny plik w projekcie „wyniki STS”;
 * korzysta z TERMINARZ_FOLDER_ID i TERMINARZ_UA z pliku „terminarz”.
 * Flashscore nie podaje już Ligi Pro, Sofascore blokował serwery Google — tu sprawdzamy, co z Google działa.
 * Uruchom „ligaproDiagnoza” → zapisuje ligapro_diagnoza.txt do folderu baza-wiedzy. Niczego nie zmienia.
 */
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
