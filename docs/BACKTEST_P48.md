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
