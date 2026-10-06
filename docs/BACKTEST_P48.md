# Backtest bramki drugiego zrodla (Poprawka 48) — 29.09.2026

`python3 bt_drugie_zrodlo.py 2026-01-01 2026-09-20` na bazie przebudowanej 29.09 (po naprawie dat P47).
Walk-forward: model dopasowany na danych sprzed miesiaca meczu; P_model jak w typuj.py (zespol v5n z wagami
0.5/0/0.5, korekta_rynkow_v5n.csv, −4 pp dla „ponizej”); P_forma jak `drugie_zrodlo()` (10 meczow, (k+1)/(n+2)).
Tylko pilka klubowa, nogi z P_model >= 70% (te ida na kupony). Bez kursow — mierzy trafnosc P, nie EV.

## Wynik

54 699 nog: zgodne (przepuszczone) 39 016 (71%), rozbiezne (odrzucone) 15 538, bez formy 145.

| P_model | n przepuszcz. | trafnosc | n odrzuc. | trafnosc | srednie P |
|---|---|---|---|---|---|
| 70–75% | 12 549 | 74,7% | 4 838 | 73,2% | 72,6% |
| 75–80% | 9 102 | 78,9% | 3 908 | 77,4% | 77,3% |
| 80–85% | 6 606 | 84,8% | 2 579 | 82,6% | 82,4% |
| 85–90% | 4 164 | 89,9% | 1 791 | 88,7% | 87,3% |
| 90–95% | 5 658 | 93,5% | 2 035 | 93,2% | 92,5% |
| 95%+ | 937 | 95,9% | 387 | 95,1% | 96,2% |

Kalibracja przepuszczonych: P_model srednio 80,4% vs trafnosc 82,2%; **min(P) srednio 77,1% vs trafnosc 82,2%**.
Brier: P_model 0,1411, min(P) 0,1441. Log loss: P_model 0,4488, min(P) 0,4586.
Odrzucone: srednie P_model 80,4%, trafnosc 80,8% — nie sa przeszacowane.

## Wnioski

1. **„P do kuponu = mniejsze z dwoch” zaniza P o ok. 5 pp** i jest gorsze od samego P_model w Brierze i log loss.
   Skutek: EV liczone za nisko, nogi z wartoscia odpadaja. To regula z CZESCI A (A9) i wymog uzytkownika —
   zmiana wymaga decyzji uzytkownika.
2. **Sama bramka zgodnosci ma slaba moc rozrozniania**: przepuszczone trafiaja o 1–2 pp czesciej niz odrzucone
   przy tym samym P_model, ale odrzuca 29% nog, ktore same sa dobrze skalibrowane.
3. **P_model po korektach (korekta rynkow, −4 pp „ponizej”) zaniza o ok. 1,8 pp** — zgodnie z pomiarem na zywych
   typach z 20.09 (P >= 75%: 81,3% vs 88,2% trafien).

## Ograniczenia
- Tylko pilka; sporty z sporty.py (log5) nie byly testowane.
- korekta_rynkow_v5n.csv byla dopasowana na okresie czesciowo pokrywajacym sie z testem (in-sample).
- Brak kursow: nie wiadomo, czy nogi odrzucone mialy EV > 0; CLV (Poprawka 56.3) to odpowie na zywo.

## Inne sporty (sporty.py) — `python3 bt_drugie_zrodlo.py --sporty 2026-01-01`

P faworyta z Elo (sporty.calibrate, bez modelu marzy koszykowki), forma = log5 z 10 meczow (jak sporty.drugie_zrodlo).
3 119 nog z P >= 70% (dart, e-sport LoL, koszykowka, rugby, snooker; hokej/reczna/siatkowka bez dosc danych w okresie).

| | srednie P | trafnosc | Brier | log loss |
|---|---|---|---|---|
| przepuszczone, P_model | 76,7% | 78,7% | 0,1653 | 0,5104 |
| przepuszczone, min(P) | 74,6% | 78,7% | 0,1680 | 0,5176 |
| odrzucone | 76,1% | **79,2%** | | |

Ten sam wzor co w pilce, mocniej: min(P) zaniza, a bramka nie odsiewa gorszych nog (odrzucone trafiaja czesciej).

## Decyzja (29.09.2026, Poprawka 58)
Zgodnosc drugiego zrodla zostaje obowiazkowa (wymog uzytkownika). P do kuponu = P modelu w typuj.py i sporty.py.
Bez zmian (nie testowane): sezon.py (arkusz statystyk) i tenis — tam nadal mniejsze z dwoch.

## Kalibracja per rynek (pilka, P po korektach, jak w kuponie) — Poprawka 58.5

| rynek | n | srednie P | trafnosc | roznica |
|---|---|---|---|---|
| O0.5 | 9 212 | 92,2% | 93,5% | +1,3 pp |
| U4.5 | 8 949 | 82,7% | 85,5% | +2,8 pp |
| 12 | 8 089 | 74,7% | 74,8% | +0,2 pp |
| O1.5 | 7 120 | 77,1% | 78,6% | +1,5 pp |
| gosp_O0.5 | 6 967 | 79,3% | 82,1% | +2,7 pp |
| 1X | 4 528 | 78,5% | 78,9% | +0,4 pp |
| U3.5 | 3 771 | 74,6% | 75,7% | +1,2 pp |
| **U2.5** | 64 | 74,5% | **53,1%** | **−21 pp** |
| **2** | 69 | 75,7% | **65,2%** | **−10 pp** |
| **BTTS_nie** | 60 | 79,7% | **51,7%** | **−28 pp** |
| **BTTS_tak** | 8 | 83,3% | 50,0% | −33 pp |

- Regula „ponizej −4 pp” jest z grubsza trafna (U3.5 +1,2 pp, U4.5 +2,8 pp po jej zastosowaniu) — zostaje.
- U2.5, BTTS i „2” przy P >= 70% sa mocno zawyzone (przy n ~ 60 blad standardowy ~6 pp, wiec to nie przypadek).
  Decyzja: `typuj.werdykt_nogi` — NIE NA KUPON na tych rynkach przy P >= 70% (tylko zaostrza).

## Reprezentacje (typuj.py --intl) — `python3 bt_drugie_zrodlo.py --intl 2024-01-01` (02.10.2026)

Powod: przebieg 02.10 18:00 — 23/23 meczow pilki (7 reprezentacji Ligi Narodow + kluby) z wszystkimi rynkami
„ROZBIEZNE”, wartosci formy co 1/24. **To nie usterka**: 1/24 wynika z wzoru (forma z 10 meczow, (k+1)/12,
srednia dwoch druzyn); rozbieznosci wynosily 26–37 pp (np. Francja – Wlochy 1X 91,4% vs 54,2%), wiec krok 4,2 pp
przy progu 10 pp nie mial znaczenia. Kod sciezki bez zmian od Poprawki 58.

Walk-forward: Elo jak `typuj.intl_elo`, Poisson dopasowany na 2010–2023, testowane mecze 01.2024–08.2026 (baza z 30.09),
P bez korekty rynkow (jak typuj.intl, tylko −4 pp „ponizej”), nogi z P >= 70%.

| P_model | n zgodne | trafnosc | n odrzucone | trafnosc | srednie P |
|---|---|---|---|---|---|
| 70–75% | 3 342 | 72,2% | 2 030 | 71,0% | 72,4% |
| 75–80% | 1 248 | 79,2% | 1 186 | 75,3% | 77,4% |
| 80–85% | 1 223 | 84,6% | 1 300 | 79,4% | 82,6% |
| 85–90% | 956 | 89,2% | 1 576 | 86,9% | 86,8% |
| 90–95% | 1 610 | 91,2% | 1 775 | 90,0% | 91,9% |
| 95%+ | 234 | 96,6% | 1 094 | 95,9% | 97,1% |

- 17 574 nogi; bramka odrzuca **51%** (w klubach 29%). Najmocniej rynki faworyta: 1X zgodne tylko w 14%, „1” w 2%,
  „2” w 6%, gosp_O0.5 w 29% — forma nie zna sily rywali, a faworyt w Lidze Narodow gra z silnymi.
- Odrzucone: srednie P 84,1%, trafnosc 82,4% (−1,7 pp); przepuszczone: 80,3% vs 81,1% (+0,8 pp). Przy tym samym
  P zgodne trafiaja o 1–5 pp czesciej — w reprezentacjach bramka odsiewa troche lepiej niz w klubach.
- Wniosek: zachowanie 18:00 jest zgodne z regula A9/P48/P58 (prawidlowe NIE NA KUPON). Bez zmian w kodzie.
  Lagodniejsza bramka dla reprezentacji (np. forma wazona sila rywala) = zmiana wymogu uzytkownika — tylko jego decyzja.

## Backtest z kursami: wymog „P_model >= P_rynku + N pp” (05.10.2026) — `python3 bt_model_rynek.py 2025-08-01 2026-09-30`

Pytanie z przegladu kuponow papierowych 20.09–04.10: nogi, w ktorych model dawal >= 5 pp wiecej niz rynek, daly +2,9%
po podatku (n=79), nogi zgodne z rynkiem −10,5% (n=158). Czy wymog przewagi nad rynkiem zwiekszylby wygrane?

Dane: 66 240 nog (rynki 1/X/2, 1X/X2/12, O/U 2.5) z ~22 lig europejskich z kursami w raw/Matches.csv (srednie rynkowe),
walk-forward jak typuj.py (zespol DC+Elo+pi, korekta_rynkow_v5n, −4 pp „ponizej”). P_rynku = kurs bez marzy.
Podwojna szansa: kurs syntetyczny z 1X2 (przyblizenie). Zwrot = traf × kurs × 0,88 − 1. Nogi z P_model >= 70%: 13 473.

| roznica P_model − P_rynku | n | P_model | P_rynku | trafnosc | zwrot/noge |
|---|---|---|---|---|---|
| < −5 pp | 1 097 | 75,1% | 82,4% | 84,9% | −16,0% |
| −5…0 pp | 4 759 | 75,6% | 77,5% | 78,0% | −17,8% |
| 0…+5 pp | 6 231 | 76,5% | 74,6% | 74,6% | −18,1% |
| +5…+10 pp | 1 025 | 79,1% | 72,4% | 72,7% | −17,9% |
| +10…+15 pp | 263 | 78,0% | 65,8% | 66,2% | −18,0% |
| > +15 pp | 98 | 77,2% | 57,8% | 54,1% | −24,6% |

| regula (z filtrem 6.4) | n | trafnosc | zwrot/noge |
|---|---|---|---|
| dzis: P >= 70% | 13 370 | 76,3% | −17,8% |
| + wymog +3 pp | 2 689 | 72,8% | −18,0% |
| + wymog +5 pp | 1 288 | 71,4% | −17,9% |
| + wymog +8 pp | 483 | 68,9% | −17,0% |

Brier (P >= 70%): P_model 0,1786, P_rynku **0,1763**.

### Wnioski
1. **Wymog przewagi nad rynkiem NIE zwieksza wygranych.** Gdy model daje wiecej niz rynek, trafnosc idzie za RYNKIEM
   (np. +5…+10 pp: model 79,1%, rynek 72,4%, trafnosc 72,7%). Nadwyzka modelu to szum, nie przewaga; zwrot bez zmian
   (−17…−18% w kazdym przedziale). Wynik +2,9% z kuponow papierowych (n=79) to przypadek w malej probie.
2. **W ligach europejskich z kursami rynek przewiduje lepiej niz model** (Brier), a trafnosc zgadza sie z P_rynku we
   wszystkich przedzialach. Podatek 12% + marza (~6%) daja ok. −17% na noge niezaleznie od reguly wyboru.
3. Filtr 6.4 (odrzuc > 15 pp) jest potwierdzony: nogi > +15 pp trafiaja 54% przy P_model 77%.

### Ograniczenia
- Tylko ligi europejskie z raw/Matches.csv (rynki najbardziej efektywne). Kupony grane sa czesto z lig egzotycznych
  (Ameryka Pld., nizsze ligi), gdzie kursow historycznych nie ma — tam przewagi nie da sie tym testem ani potwierdzic, ani wykluczyc.
- Kursy srednie rynku sa wyzsze niz w STS — w STS wynik bylby gorszy, nie lepszy.
- Podwojna szansa z kursu syntetycznego.

### Decyzja
Bez zmian w regulach (CZESC A, filtr 6.4). Wymogu „model > rynek o N pp” NIE wprowadzamy.

## Rynek 3.5 gola (U3.5 / O3.5) — `python3 bt_ou35.py 2024-08-01 2026-09-30` i `--intl 2022-01-01` (06.10.2026)

Powod: 05.10 przegraly dwie nogi U3.5 z P modelu ok. 70% (Francja – Belgia, Wlochy – Turcja). Sprawdzono CALA skale P,
nie tylko >= 70%. Kluby: 86 534 mecze walk-forward; w 15 327 meczach P rynku z kursow na 2.5 gola (Poisson — kursow
na 3.5 w historii nie ma; ta proxy jest dobrze skalibrowana: roznice < 1 pp w przedzialach 50–90%).

| | n | Brier | uwagi |
|---|---|---|---|
| P_model (po korektach) — wszystkie mecze | 86 534 | 0,1991 | zaniza U3.5 o ok. 2 pp w calej skali (korekta −4 pp za mocna; zostaje — tylko zaostrza) |
| P_rynku (mecze z kursami) | 15 327 | **0,1992** | prawie idealnie skalibrowany |
| P_model na tych samych meczach | 15 327 | 0,2023 | |
| mieszanka w·model + (1−w)·rynek | 7 720 (test) | w = 0 najlepsze | model nic nie dodaje do rynku |

| nogi U3.5 | n | P_model | P_rynku | trafnosc |
|---|---|---|---|---|
| model >= rynek + 5 pp | 624 | 68,0% | 60,5% | **58,8%** |
| model <= rynek − 5 pp | 5 013 | 65,6% | 73,3% | 73,0% |
| P_model >= 70% w ligach ze srednia >= 3,2 gola | 589 | 71,3% | — | **62,1%** |

Reprezentacje (4 989 meczow od 2022): P po korektach zaniza U3.5 o 3–5 pp w srodku skali, ale przy duzej przewadze Elo
model PRZESZACOWUJE gole: P(U3.5) < 30% (czyli O3.5 > 70%) -> U3.5 weszlo w 43% (O3.5 tylko 57%).

### Decyzja (Poprawka 145)
Dla U3.5 i O3.5: **P do kuponu = min(P_modelu, P_rynku bez marzy)** (`rynek.p_kuponu_wg_rynku`, w `typuj.value`).
Tylko obniza (A2). Na nogach U3.5 z P_model >= 70% i kursami: zostaje 5 913 nog (trafnosc 77,6%), odpada 551 nog
z trafnoscia **66,1%** (ponizej progu 70%); Brier 0,1799 -> 0,1791. Na kursach 05.10: Wlochy – Turcja U3.5 1.62 / O3.5 2.30
-> P rynku 58,7%, EV −16,4% — noga NIE NA KUPON (dotad dopuszczona z P 70,4%).

### Czy sam model da sie nauczyc lepiej liczyc 3.5? (06.10.2026, druga czesc)
Uzytkownik: „nie chodzi o podawanie kursu, tylko o lepsze przewidywanie”. Sprawdzono, czy model (bez kursu) da sie poprawic
dodatkowymi informacjami. Regresja logistyczna na P_model + cechy, uczona na meczach do 07.2025, sprawdzona na 68 218 meczach
od 08.2025 (bez przecieku; cechy druzyn z 10 POPRZEDNICH meczow):

| model | Brier (test) |
|---|---|
| P_model (kupon) | 0,2000 |
| + kalibracja | 0,2000 |
| + czestosc U3.5 w lidze | 0,1999 |
| + forma druzyn (U3.5 w 10 meczach) | 0,1998 |
| + srednia goli druzyn | **0,1995** |
| + celne strzaly (tylko 21 lig, 15,6% meczow) | 0,1996 |
| (dla porownania) rynek, mecze z kursami | 0,2017 vs model 0,2048 |

Wniosek: z danych, ktore mamy (wyniki; strzaly tylko w duzych ligach), poprawa jest kosmetyczna (0,25% Brier),
a nowe P bylo w tescie gorzej skalibrowane (przeszacowane o 1,5–2,6 pp). NIE wdrazamy przeliczenia P. Zostaja dwa
miejsca, gdzie model myli sie systematycznie i potwierdzone w obu okresach:
- ligi ze srednia >= 3,2 gola na mecz: U3.5 z P >= 70% trafia 62% (n=589 uczenie, n=571 test);
- reprezentacje: O2.5 z P >= 70%: P 79,6% -> trafnosc 70,1% (n=348). Tamze: przy wielkiej przewadze Elo model zawyza gole
  (P(U3.5) < 30% -> U3.5 weszlo w 44%); reguła −4 pp „ponizej” w reprezentacjach zaniza (P surowe trafniejsze) — zostaje, bo tylko zaostrza.

### Decyzja (Poprawka 146)
`typuj.werdykt_nogi`: U3.5 z P >= 70% w lidze ze srednia >= 3,2 gola (12 mies., wieksza z dwoch lig, >= 30 meczow) — NIE NA KUPON;
reprezentacje: O2.5 z P >= 70% — NIE NA KUPON. Tylko zaostrza (A2). Do poprawy samego przewidywania potrzebne sa nowe dane
(sklady, xG z FotMob/Understat — tryb obserwacji w termux/zrodla.py); po zebraniu — ten sam test.
