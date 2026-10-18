# sts-kb — zasady pracy (dla każdej sesji)

## Zasada nadrzędna użytkownika (29.09.2026)
**Wszystko ma działać poprawnie** — ale bez pętli „przebieg → usterka → poprawka → przebieg” (decyzja użytkownika
01.10.2026). Raport przebiegu to OBSERWACJE, nie lista poprawek. Każda poprawka:
1. jest sprawdzona na prawdziwych danych (albo wprost napisane, czego nie dało się sprawdzić i dlaczego),
2. ma test w `tests/` i przechodzi CI (`python -m pytest -q tests`, pyflakes),
3. trafia do `main` PR-em, a zmiana zachowania przebiegu — do POPRAWEK na Dysku dopiero PO scaleniu kodu
   (reguły nigdy nie wyprzedzają kodu), publikacja tylko między przebiegami (12/15/18/21 PL), z odczytem kontrolnym.

### Tryb pracy z raportami (od 01.10.2026)
- Po przebiegu: ZBIERZ wszystkie obserwacje i SKLASYFIKUJ — nie poprawiaj pierwszej z brzegu. Kategorie:
  regresja (dzialalo, przestalo) | blad z reprodukcja | brak danych (zrodlo) | nowy format | zla identyfikacja
  zdarzenia | prawidlowe UNKNOWN | poza oknem dorozliczenia (historia zamrozona — nie ruszac Rozliczen/Bilansu).
- BLAD = reprodukcja: wejscie + wynik + oczekiwany wynik. Bez reprodukcji to obserwacja, nie PR.
- Od razu (miedzy przebiegami) tylko: regresja albo ryzyko dla zakladu ZA PIENIADZE. Reszta — JEDNA paczka dziennie
  (okno po przebiegu 21:00, przed 12:00 nastepnego dnia), jeden PR „hardening batch”.
- Zloty zbior (`tests/fixtures/zloty_rynki.csv`, test `tests/test_zloty_zbior.py`) — stany:
  OBSERVATION (nowy zapis z raportu, bez oczekiwanego wyniku — tylko zapisany, CI go nie ocenia) →
  ZNANA_ANOMALIA (potwierdzona reprodukcja: wejscie + wynik + oczekiwany; xfail strict, CI zielone) →
  OK (po poprawce w wieczornej paczce). Dopisanie przypadku NIGDY nie robi CI czerwonego i nie wymusza poprawki.
  Wierszy NIE usuwamy — naprawiony przypadek zostaje jako OK, zeby cofniecie obslugi dalo czerwone CI.
- Nie naprawiaj objawu rozszerzeniem parsera (kolejny `if` na kolejny napis), dopoki nie ustalono WARSTWY bledu
  (zapis przebiegu / normalizacja / interpretacja / dopasowanie zdarzenia / zrodlo wynikow). Kazda poprawka
  rozliczen = reprodukcja + test regresji w zlotym zbiorze.

## Czego nie wolno
- Wpisywać do repo danych osobistych i historii zakładów: logów, Bilansu, kursów, Dziennika, Raportu, PDF, e-maili,
  id folderów Dysku (w `apps_script/` zostaje placeholder `WKLEJ_ID_FOLDERU_BAZA_WIEDZY`).
- Luzować CZĘŚCI A (stawki, limity, budżet 300 zł) bez decyzji opartej na backteście.
- Zgadywać nazw drużyn: brak jednoznacznego dopasowania = noga MNIEJ / „BRAK WYNIKU”.
- Usuwać zadania cyklicznego `trig_01LXhx9anABLZ7aaWYpxUcUA`.

## Czas
Użytkownik liczy w czasie polskim: latem UTC+2 (10:00 UTC = 12:00 PL), zimą UTC+1 (11:00 UTC = 12:00 PL); zmiana w ostatnią
niedzielę marca i października. Przebiegi: 12:00, 15:00, 18:00, 21:00 PL (zadanie cykliczne z CRON_TZ=Europe/Warsaw).
Nigdy stałe „+2 h”: w Pythonie `ZoneInfo('Europe/Warsaw')`/`tz_localize('Europe/Warsaw')`, na Termuxie reguła UE (`na_pl`).

## Mapa
- Reguły: Dysk, folder baza-wiedzy — „INSTRUKCJA STS v7” + „POPRAWKI DO INSTRUKCJI v7 — wyd. N” (każde nowsze niż v7).
  Projekt v7: `docs/INSTRUKCJA_v7_projekt.md`; strategia: `docs/STRATEGIA.md`; backtest P48/P58: `docs/BACKTEST_P48.md`.
- Przebieg: `przebieg.py` (build_kb → uzupelnij_ligi → build_kb → hist_import → swiezosc + kontrole plików).
- Typowanie: `typuj.py` (piłka; wiele meczów naraz: `typuj_wsad.py LISTA.txt` — baza raz na proces, wynik jak osobne wywołania), `sporty.py` (inne sporty, linia WERDYKT; wsad: `sporty_wsad.py LISTA.tsv` — SPORT<TAB>Gosp<TAB>Gosc[<TAB>opcje]), `tenis.py` (wsad: `tenis_wsad.py LISTA.tsv` — A<TAB>B[<TAB>--clay/--bo5]; oba: baza/stan Elo raz na proces, blok meczu jak osobne wywolanie + KOD), `sezon.py` (arkusze).
- Kupony: `kupon.py`; rozliczenia i dzienniki: `dzienniki.py` (Settlement v2: kolumna `kategoria` = kod SETTLEMENT_ANOMALY
  z warstwa bledu, tabela `ANOMALIE`; stan/wynik/uwaga bez zmian; `--zaklady zaklady_faktyczne.csv` = FAKTYCZNE zaklady
  STS/LVBET/Superbet — gdy sa wpisy dnia, pieniadze Bilansu tylko z nich, kupony systemu = zalecenia; plik tylko na Dysku); CLV: `clv.py`; porownanie kursow STS/SUPERBET/LVBET i linia „GRAJ U:” kazdego kuponu (Telegram): `kursy3.py kupon` (dane z telefonu: `termux/kursy_bukmacherow.py` -> `kursy_bukmacherow_*.csv.gz` na Dysku; mecz tylko jednoznaczny, roznica >35% = podejrzany); kursy z PDF oferty i kurs_zamkniecia: `oferta.py`.
- Dodatkowe zrodla statystyk (TRYB OBSERWACJI, nic w przebiegu ich nie uzywa do czasu backtestu i decyzji uzytkownika):
  `termux/zrodla.py` na telefonie (Elo reprezentacji, FotMob xG/strzaly/sklady, Sofascore — domyslnie WYLACZONY (403 challenge; `--sofascore` wlacza), Transfermarkt, Understat, Tennis Abstract,
  darty, NHL+bramkarze, pogoda, sedziowie, 90minut.pl: II/III liga i CLJ jako zrodla_90minut_mecze) -> jeden `zrodla_*.zip` na uruchomienie w podfolderze baza-wiedzy/zrodla/
  (NIE w folderze przebiegu); w zipie diagnoza `zrodla_diag_*.txt` i probki `zrodla_surowe_*.jsonl.gz`;
  instalacja: `termux/instaluj_zrodla.sh`.
- Nazwy: `nazwy.py` (wspólne znaczniki), `aliasy.csv` (aliasy jako dane; działają tylko, gdy cel jest w puli),
  `dopasuj.py` (nauka aliasów STS -> baza z dowodów w źródłach: kotwica = jedyny mecz rozpoznanej drużyny w dniu meczu,
  godzina = ten sam mecz w terminarzu ±5 min; sprzeczności z resolverem tylko do raportu, nic nie nadpisują; `dopasuj.py liga` = kotwica ligowa dla meczów jeszcze bez wyniku: jedyny kandydat o pasującym rdzeniu nazwy
  grający w lidze rozpoznanego rywala albo jedyna para kandydatów ze wspólną ligą — wynik do przejrzenia przed dopisaniem).
  `dopasuj.py auto KURSY` (w KAZDYM przebiegu po oferta.py): pewne aliasy z wynikow + kotwica ligowa bez kolizji ->
  `aliasy_auto.csv` (nie w repo), wczytywany po aliasy.csv (reczne wygrywaja); modul „sporty” dopuszcza kilka celow
  jednej nazwy (rozne sporty) — `nazwy.aliasy_wiele`.
- Zdarzenia (TRYB OBSERWACJI, nic w typowaniu jeszcze z tego nie korzysta): `zdarzenia.py KURSY` — kazde zdarzenie z oferty
  -> MATCH / UNKNOWN / CONFLICT + dowody (PARA_W_ZRODLE, GODZINA, WSPOLNA_LIGA, H2H; konflikt RYWAL_INNY, TA_SAMA_DRUZYNA;
  ROZBITA = ten sam klub pod dwiema nazwami w bazie). Cel: 100% zdarzen sklasyfikowanych, 0 blednych MATCH; blokada
  typowania CONFLICT/UNKNOWN dopiero po przegladzie na prawdziwych danych i decyzji uzytkownika.
- Rekord kursu (TRYB OBSERWACJI, 18.10.2026, nic w przebiegu/kuponach nie korzysta): `kursy_rekord.py KURSY_BUK*.csv.gz [--teraz ISO] [--csv]`
  albo `--import PLIK.csv --zrodlo NAZWA` (dane z AUTORYZOWANEGO zrodla; wymagane kolumny bukmacher, gospodarz, gosc, start_utc, rynek,
  kurs, pobrano_utc) -> zrodlo, bukmacher, id_zdarzenia, pobrano_utc, start_utc, liga, rynek, kurs, status_walidacji (OK / BRAK_DANYCH /
  PO_STARCIE / NIEAKTUALNY > 90 min albo mecz trwa / PODEJRZANY > 35% i > 5 pp wzgledem pary MATCH). Para zdarzen: start +-5 min, OBIE
  strony zgodne (ten sam czlon albo skrot >= 5 liter, znaczniki rowne), jedna para w obie strony; inaczej UNKNOWN, CONFLICT = druzyna
  w innej pewnej parze. Plik z telefonu ma od 18.10 na koncu kolumny event_id, liga (Superbet /struct), start_utc, pobrano_utc.
  Zrodla kursow BEZ proxy i bez obchodzenia blokad (decyzja 18.10); Pinnacle tylko przez OddsPapi (klucz).
- Model vs rynek (TRYB OBSERWACJI, nic w przebiegu nie korzysta): `rynek_model.py zbior --typy typy_log.csv [--p-sts P.csv] --kursy K*.csv.gz --wyjscie zbior.csv` (P zapisane przed meczem + kurs STS + wynik, bez dubli) i `rynek_model.py ocena zbior.csv` (log-loss/Brier, model rezydualny logit P_rynku + b*(logit P_model - logit P_rynku) w segmentach, CV po dniach, bootstrap po meczach) — odchylac P od rynku wolno tylko tam, gdzie b>0 istotnie, i po decyzji uzytkownika.
- API-Football (TRYB OBSERWACJI, decyzja uzytkownika 17.10.2026 „zrobmy wszystkie”; nic w przebiegu/typowaniu/rozliczeniach
  nie korzysta do backtestu i decyzji): `apps_script/wyniki_live.gs` zbiera do folderu „api-football” na Dysku (archiwum
  wynikow, kontuzje, statystyki i sklady meczow lig STS po 20 na zapytanie, historia lig — lista lig z `api_ligi.json`);
  `api_football.py ligi|rozliczenia|historia|statystyki|kontuzje` = pomiary. Dopasowanie oferty STS: ta sama godzina startu
  + OBIE druzyny (`ta_sama`: nazwy.znaczniki musza byc rowne, slowa ogolne typu Town/Real/Hapoel nie sa dowodem).
- Apps Script (wkleja użytkownik): `apps_script/terminarz.gs`, `apps_script/ligapro.gs`, `apps_script/arkusze.gs` (arkusze statystyk jako .csv.gz), `apps_script/dzienniki.gs` (wszystkie dzienniki w jednym dzienniki.zip; `python3 przebieg.py --dzienniki`), `apps_script/paczka.gs` (wszystkie dane przebiegu w jednym paczka.zip — przebieg.py rozpakowuje ja sam).
  `apps_script/oddspapi.gs` (TRYB OBSERWACJI, 17.10.2026; uzytkownik gra glownie w SUPERBET, takze LVBET, STS juz nie):
  OSOBNY projekt Apps Script, klucz tylko we wlasciwosci ODDSPAPI_KEY; kursy Superbet PL + Pinnacle (kurs uczciwy) do folderu
  „oddspapi” na Dysku. Platne (250/mies., licza sie tez bledy 4xx): tylko lista meczow raz dziennie 11:xx PL; kursy z DARMOWEGO
  historical-odds po meczu (otwarcie / 6 h przed / zamkniecie), 1 bukmacher na zapytanie; max 10 platnych/dobe, 200/mies., 24 h stop po 401/403/429.
  Przeliczenie wstecz (wariant bezpieczny, decyzja uzytkownika 17.10): 14 dni przed pierwszym uruchomieniem x 60 meczow/dzien
  (oddspapi_W_DATA.json.gz; lista dnia = 1 platne, max 4/dobe), historia darmowa w tym samym limicie 400/dobe i tempie 6 s.
  Pomiar: `oddspapi_analiza.py oddspapi_hist_*.json.gz --listy oddspapi_*_RANO.json.gz` (przewaga Superbet vs Pinnacle bez marzy
  6 h przed i na zamknieciu, EV po podatku 12%, AKO dzienne z nog >= --prog; tylko rynki z tym samym zestawem wynikow u obu;
  `--rynki oddspapi_rynki.json` = nazwy rynkow (1 platne raz), `--rozliczenia oddspapi_rozl_*.json.gz` = WIN/LOSE z settlements
  — platne, skrypt rozlicza max 4 mecze/dobe, tylko z noga Superbet powyzej kursu uczciwego). Pierwsza linia raportu = WERDYKT
  (plan z 17.10): STOP gdy po 7 dniach < 3 okazje/dzien albo srednia przewaga vs zamkniecie <= 0; DALEJ (AKO papierowe, ~50 kuponow,
  potem decyzja uzytkownika) gdy >= 200 nog, srednia >= +3% i dolna granica 95% (bootstrap po meczach) > 0; inaczej ZA MALO DANYCH.
  `apps_script/wyniki_live.gs` (wyniki na zywo dla aplikacji „Prognozy meczowe”: API-Sports — klucz TYLKO we wlasciwosciach
  skryptu APISPORTS_KEY — + OpenLigaDB -> `wyniki_live.json` na Dysku co minute; darmowy plan: kazdy sport najwyzej co 15 min,
  limit 95/dzien; NIE jest czescia przebiegu ani rozliczen).
