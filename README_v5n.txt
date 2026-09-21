DODATEK v5n (20.09.2026) — piłka: zespół 3 modeli + korekta per rynek. Bez kursów.
1) pi.py — pi-ratings (Constantinou & Fenton 2013): osobny rating domowy/wyjazdowy każdej drużyny, liczony z samych wyników.
   Pokrycie meczów 2025/26: pi 88% vs ClubElo 56% vs Dixon-Coles 82%.
2) ensemble.py — walk-forward backtest 08.2025–09.2026 (14 836 meczów, 78 lig). Wagi wybrane na 1. połowie, sprawdzone na 2.:
   logloss (1X2+O2.5+BTTS+O1.5; niżej lepiej): stary blend DC/Elo 2.9479 | sam DC 2.9516 | sam Elo 2.9532 | sam pi 2.9439 | ZESPÓŁ DC+pi 2.9351.
   Wagi końcowe DC/Elo/pi = 0.5/0.0/0.5 (Elo tylko awaryjnie, gdy brak DC i pi). → ensemble_wagi.json
3) xi_test.py — zanik czasowy DC: półokres 180 d 2.9374 | 365 d 2.9366 | 730 d 2.9377 → zostaje 365 dni (obecne ustawienie).
4) korekta_rynkow.py → korekta_rynkow_v5n.csv: korekta per rynek i przedział P, TYLKO w dół (nowsze mecze ważniejsze).
   Największe: U3.5 przy P 80–90% −4,5 pp; X2 80–90% −2,6 pp; U4.5 90%+ −2,5 pp; 1X 80–90% −1,6 pp; DNB_2 −1,2…−1,9 pp.
   Rynki „poniżej” zawsze min. −4 pp (reguła użytkownika) — typuj.py stosuje to SAM; nie odejmuj drugi raz.
5) typuj.py (nadpisuje v5d) — używa zespołu i korekty automatycznie; bez ensemble_wagi.json działa po staremu.
6) kalibracja_ligi_v5n.csv — ligi, gdzie typy P≥75% trafiają >5 pp rzadziej niż P (n≥60): JAP2 −7,7; UKR −6,5; CAN −5,3; IRN −5,2 pp.
Test kalibracji zespołu (2. połowa, bez podglądania): P 75–80% → 77,3% trafień; 80–85% → 81,4%; 85–90% → 87,1%; 90–95% → 92,6%.
Globalna mapa izotoniczna (tworzy ją ensemble.py) NIE poprawiła przedziału 85–90% (87,6→85,5%) — nieużywana w typuj.py, tylko do porównań.
Co tydzień (poniedziałek): python3 ensemble.py 2025-08-01 <wczoraj> && python3 korekta_rynkow.py → zapisz ensemble_wagi.json i korekta_rynkow_v5n.csv na Drive.
